import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta
from config import DB_PATH, RETENTION_DAYS

logger = logging.getLogger(__name__)


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _conn() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id          TEXT PRIMARY KEY,
                city        TEXT NOT NULL,
                event_time  TEXT NOT NULL,
                alert_type  TEXT NOT NULL,
                location    TEXT NOT NULL,
                description TEXT,
                source      TEXT,
                raw_text    TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        # composite PK: one row per (chat_id, city) → multiple cities per subscriber
        db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id     TEXT NOT NULL,
                city        TEXT NOT NULL,
                kind        TEXT NOT NULL DEFAULT 'personal',
                created_at  TEXT NOT NULL,
                PRIMARY KEY (chat_id, city)
            )
        """)
        # Migrate old single-city subscribers table if needed
        cols = {r[1] for r in db.execute("PRAGMA table_info(subscribers)")}
        if "city" in cols:
            # Check if old PK was just chat_id (no composite)
            idx = db.execute(
                "SELECT COUNT(*) FROM pragma_index_list('subscribers') "
                "WHERE origin='pk'"
            ).fetchone()[0]
            # If only one PK column, migrate
            try:
                db.execute(
                    "ALTER TABLE subscribers RENAME TO subscribers_old"
                )
                db.execute("""
                    CREATE TABLE subscribers (
                        chat_id     TEXT NOT NULL,
                        city        TEXT NOT NULL,
                        kind        TEXT NOT NULL DEFAULT 'personal',
                        created_at  TEXT NOT NULL,
                        PRIMARY KEY (chat_id, city)
                    )
                """)
                db.execute(
                    "INSERT OR IGNORE INTO subscribers SELECT chat_id, city, kind, created_at "
                    "FROM subscribers_old"
                )
                db.execute("DROP TABLE subscribers_old")
                logger.info("Migrated subscribers table to composite PK")
            except Exception:
                pass  # already migrated or new install

        # Migrate alerts table (add city column if missing)
        alert_cols = {r[1] for r in db.execute("PRAGMA table_info(alerts)")}
        if "city" not in alert_cols:
            db.execute("ALTER TABLE alerts ADD COLUMN city TEXT NOT NULL DEFAULT ''")
        db.commit()


# ── Subscribers ───────────────────────────────────────────────────────────────

def subscribe(chat_id: str | int, city: str, kind: str = "personal") -> None:
    city = city.strip().capitalize()
    with _conn() as db:
        db.execute(
            """INSERT INTO subscribers (chat_id, city, kind, created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(chat_id, city) DO UPDATE SET kind=excluded.kind""",
            (str(chat_id), city, kind, datetime.utcnow().isoformat()),
        )
        db.commit()


def unsubscribe_city(chat_id: str | int, city: str) -> bool:
    """Remove one city from a subscriber."""
    city = city.strip().capitalize()
    with _conn() as db:
        cur = db.execute(
            "DELETE FROM subscribers WHERE chat_id=? AND city=?",
            (str(chat_id), city),
        )
        db.commit()
    return cur.rowcount > 0


def unsubscribe_all(chat_id: str | int) -> bool:
    """Remove all cities for a subscriber."""
    with _conn() as db:
        cur = db.execute("DELETE FROM subscribers WHERE chat_id=?", (str(chat_id),))
        db.commit()
    return cur.rowcount > 0


def get_cities(chat_id: str | int) -> list[str]:
    """Return all cities for a subscriber."""
    with _conn() as db:
        rows = db.execute(
            "SELECT city FROM subscribers WHERE chat_id=? ORDER BY city",
            (str(chat_id),),
        ).fetchall()
    return [r[0] for r in rows]


def get_unique_cities() -> list[str]:
    with _conn() as db:
        rows = db.execute("SELECT DISTINCT city FROM subscribers").fetchall()
    return [r[0] for r in rows]


def get_subscribers_for_city(city: str) -> list[str]:
    with _conn() as db:
        rows = db.execute(
            "SELECT chat_id FROM subscribers WHERE city=?", (city,)
        ).fetchall()
    return [r[0] for r in rows]


# ── Alerts ────────────────────────────────────────────────────────────────────

def make_id(event_time: str, alert_type: str, location: str) -> str:
    key = f"{event_time.strip()}|{alert_type.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha1(key.encode()).hexdigest()


def is_known(alert_id: str) -> bool:
    with _conn() as db:
        row = db.execute("SELECT 1 FROM alerts WHERE id=?", (alert_id,)).fetchone()
    return row is not None


def save(alert_id: str, city: str, event_time: str, alert_type: str,
         location: str, description: str, source: str, raw_text: str) -> None:
    with _conn() as db:
        db.execute(
            """INSERT OR IGNORE INTO alerts
               (id, city, event_time, alert_type, location, description,
                source, raw_text, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (alert_id, city, event_time, alert_type, location,
             description, source, raw_text, datetime.utcnow().isoformat()),
        )
        db.commit()


def update_description(alert_id: str, description: str) -> None:
    with _conn() as db:
        db.execute("UPDATE alerts SET description=? WHERE id=?", (description, alert_id))
        db.commit()


def purge_old() -> int:
    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    with _conn() as db:
        cur = db.execute("DELETE FROM alerts WHERE created_at < ?", (cutoff,))
        db.commit()
    return cur.rowcount
