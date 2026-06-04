"""Scraper for tilannehuone.fi/kysely.php?paikkakunta=Lappeenranta&vrk=on

Actual table structure (verified via browser):
  row: [ <td/> | <td>Lappeenranta</td> | <td>04.06.2026 10:37:13</td> | <td>savuhavainto</td> | <td/> ]
  optional next row: [ <td colspan> Yksiköt: Willimies <a href="tehtava.php?hash=...">Avaa tehtäväsivu</a> ]
"""
import logging
import re
from bs4 import BeautifulSoup, Tag
from .base import Alert
from .utils import get, clean

logger = logging.getLogger(__name__)
URL = "https://www.tilannehuone.fi/kysely.php?paikkakunta=Lappeenranta&vrk=on"
BASE = "https://www.tilannehuone.fi/"
SOURCE = "tilannehuone.fi"

_DATE_TIME_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})")


def _resolve(href: str) -> str:
    return href if href.startswith("http") else BASE + href.lstrip("/")


def _find_result_table(soup: BeautifulSoup) -> Tag | None:
    """Find the table that contains Lappeenranta alert rows."""
    for tbl in soup.find_all("table"):
        rows = tbl.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 4:
                # Cell[2] should contain combined datetime "DD.MM.YYYY HH:MM:SS"
                if _DATE_TIME_RE.search(cells[2].get_text()):
                    return tbl
    return None


def scrape() -> list[Alert]:
    resp = get(URL, extra_headers={"Referer": "https://www.tilannehuone.fi/"})
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    result_table = _find_result_table(soup)

    if not result_table:
        logger.warning("%s: could not find result table", SOURCE)
        return []

    alerts: list[Alert] = []
    pending_url = ""  # link found in "Yksiköt" continuation row

    for row in result_table.find_all("tr"):
        cells = row.find_all("td")

        # Continuation row: "Yksiköt: ... Avaa tehtäväsivu »"
        if cells and "yksiköt" in cells[0].get_text().lower():
            for a in row.find_all("a", href=True):
                if "tehtava.php" in a["href"]:
                    pending_url = _resolve(a["href"])
                    break
            if alerts:
                alerts[-1].url = pending_url
            pending_url = ""
            continue

        if len(cells) < 4:
            continue

        location = clean(cells[1].get_text())
        if "lappeenranta" not in location.lower() and "villmanstrand" not in location.lower():
            continue

        dt_text = clean(cells[2].get_text())
        m = _DATE_TIME_RE.search(dt_text)
        if not m:
            continue

        date_str, time_str = m.group(1), m.group(2)
        # Parse "DD.MM.YYYY" → "YYYY-MM-DD"
        d, mo, y = date_str.split(".")
        event_time = f"{y}-{mo}-{d} {time_str}"

        alert_type = clean(cells[3].get_text())
        if not alert_type:
            continue

        # Check for inline link in this row
        detail_url = ""
        for a in row.find_all("a", href=True):
            if "tehtava.php" in a["href"]:
                detail_url = _resolve(a["href"])
                break

        raw = f"{location} | {dt_text} | {alert_type}"
        alerts.append(Alert(
            event_time=event_time,
            alert_type=alert_type,
            location=location,
            description="",
            source=SOURCE,
            raw_text=raw,
            url=detail_url,
        ))

    logger.info("%s: %d alerts", SOURCE, len(alerts))
    return alerts
