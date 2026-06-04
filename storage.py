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
        db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id     TEXT PRIMARY KEY,
                city        TEXT NOT NULL,
                kind        TEXT NOT NULL DEFAULT 'personal',  -- 'personal' | 'channel'
                created_at  TEXT NOT NULL
            )
        """)
        # Migrate old alerts table (no city column) transparently
        cols = {r[1] for r in db.execute("PRAGMA table_info(alerts)")}
        if "city" not in cols:
            db.execute("ALTER TABLE alerts ADD COLUMN city TEXT NOT NULL DEFAULT ''")
        db.commit()


# ── Subscribers ───────────────────────────────────────────────────────────────

def subscribe(chat_id: str | int, city: str, kind: str = "personal") -> None:
    city = city.strip().capitalize()
    with _conn() as db:
        db.execute(
            """INSERT INTO subscribers (chat_id, city, kind, created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(chat_id) DO UPDATE SET city=excluded.city, kind=excluded.kind""",
            (str(chat_id), city, kind, datetime.utcnow().isoformat()),
        )
        db.commit()


def unsubscribe(chat_id: str | int) -> bool:
    with _conn() as db:
        cur = db.execute("DELETE FROM subscribers WHERE chat_id=?", (str(chat_id),))
        db.commit()
    return cur.rowcount > 0


def get_city(chat_id: str | int) -> str | None:
    with _conn() as db:
        row = db.execute(
            "SELECT city FROM subscribers WHERE chat_id=?", (str(chat_id),)
        ).fetchone()
    return row[0] if row else None


def get_all_subscribers() -> list[tuple[str, str]]:
    """Return list of (chat_id, city)."""
    with _conn() as db:
        return db.execute("SELECT chat_id, city FROM subscribers").fetchall()


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
