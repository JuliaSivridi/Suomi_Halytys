"""Shared helpers for scrapers."""
import re
import logging
from datetime import datetime, date

import requests
from config import HEADERS

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::\d{2})?")


def get(url: str, timeout: int = 15, extra_headers: dict | None = None) -> requests.Response | None:
    headers = {**HEADERS, **(extra_headers or {})}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


def parse_datetime(date_str: str, time_str: str, today: date | None = None) -> str:
    """Return 'YYYY-MM-DD HH:MM' from various Finnish date/time strings."""
    today = today or date.today()

    # Normalize date
    dm = _DATE_RE.search(date_str)
    if dm:
        d = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
    elif "tänään" in date_str.lower() or date_str.strip() == "":
        d = today
    elif "eilen" in date_str.lower():
        from datetime import timedelta
        d = today - timedelta(days=1)
    else:
        d = today

    # Normalize time
    tm = _TIME_RE.search(time_str)
    if tm:
        t = f"{int(tm.group(1)):02d}:{tm.group(2)}"
    else:
        t = "00:00"

    return f"{d.isoformat()} {t}"


def clean(text: str) -> str:
    return " ".join(text.split())
