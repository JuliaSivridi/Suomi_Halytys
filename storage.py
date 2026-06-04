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
                event_time  TEXT NOT NULL,
                alert_type  TEXT NOT NULL,
                location    TEXT NOT NULL,
                description TEXT,
                source      TEXT,
                raw_text    TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        db.commit()


def make_id(event_time: str, alert_type: str, location: str) -> str:
    """Stable fingerprint for deduplication across sources."""
    key = f"{event_time.strip()}|{alert_type.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha1(key.encode()).hexdigest()


def is_known(alert_id: str) -> bool:
    with _conn() as db:
        row = db.execute("SELECT 1 FROM alerts WHERE id=?", (alert_id,)).fetchone()
    return row is not None


def save(alert_id: str, event_time: str, alert_type: str,
         location: str, description: str, source: str, raw_text: str) -> None:
    with _conn() as db:
        db.execute(
            """INSERT OR IGNORE INTO alerts
               (id, event_time, alert_type, location, description, source, raw_text, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (alert_id, event_time, alert_type, location,
             description, source, raw_text, datetime.utcnow().isoformat()),
        )
        db.commit()


def purge_old() -> int:
    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    with _conn() as db:
        cur = db.execute("DELETE FROM alerts WHERE created_at < ?", (cutoff,))
        db.commit()
    return cur.rowcount
