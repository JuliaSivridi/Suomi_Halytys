"""Scraper for tilannehuone.fi/kysely.php?paikkakunta=Lappeenranta&vrk=on

Main listing table structure (verified via browser):
  row: [ <td/> | <td>Lappeenranta</td> | <td>04.06.2026 10:37:13</td> | <td>savuhavainto</td> | <td/> ]
  optional next row: [ <td colspan> Yksiköt: Willimies <a href="tehtava.php?hash=...">Avaa tehtäväsivu</a> ]

Detail page (tehtava.php?hash=...) may contain a human-written description
with street address, e.g.:
  "Savut tulleet omakotitaloon sisälle, ei rakennuspaloa Tampereentiellä."
We fetch it once per new event that has a URL.
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
_EXTRA = {"Referer": "https://www.tilannehuone.fi/"}


def _resolve(href: str) -> str:
    return href if href.startswith("http") else BASE + href.lstrip("/")


def _find_result_table(soup: BeautifulSoup) -> Tag | None:
    """Find the table that contains Lappeenranta alert rows."""
    for tbl in soup.find_all("table"):
        for row in tbl.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 4 and _DATE_TIME_RE.search(cells[2].get_text()):
                return tbl
    return None


def fetch_description(detail_url: str) -> str:
    """Fetch the event detail page and return the human-written description, if any.

    The description lives in the main event table, after the two headings
    (city name and alert type). It often contains a street address.
    Returns empty string if not found or if the page says location not specified.
    """
    resp = get(detail_url, extra_headers=_EXTRA)
    if not resp:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")

    # Find the table that has a heading matching the alert type pattern
    for tbl in soup.find_all("table"):
        headings = tbl.find_all(["h1", "h2", "h3"])
        if len(headings) < 2:
            continue

        # Collect all text nodes in the table that are NOT:
        # - a heading, - a timestamp, - "Lisätty:", - share/social links
        candidates = []
        for td in tbl.find_all("td"):
            # Skip cells that only contain headings or timestamps
            if td.find(["h1", "h2", "h3"]):
                continue
            text = clean(td.get_text(" ", strip=True))
            if not text:
                continue
            if re.match(r"^\d{2}\.\d{2}\.\d{4}", text):
                continue
            if text.lower().startswith("lisätty"):
                continue
            if "sijaintia ei ole tarkennettu" in text.lower():
                continue
            if len(text) > 10 and re.search(r"\w{3,}", text):
                # Remove the "Lisätty: ..." trailer if present
                text = re.sub(r"\s*Lisätty:.*$", "", text, flags=re.IGNORECASE).strip()
                if text:
                    candidates.append(text)

        if candidates:
            return candidates[0]

    return ""


def scrape() -> list[Alert]:
    resp = get(URL, extra_headers=_EXTRA)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    result_table = _find_result_table(soup)

    if not result_table:
        logger.warning("%s: could not find result table", SOURCE)
        return []

    alerts: list[Alert] = []

    for row in result_table.find_all("tr"):
        cells = row.find_all("td")

        # Continuation row: "Yksiköt: ... Avaa tehtäväsivu »"
        if cells and "yksiköt" in cells[0].get_text().lower():
            for a in row.find_all("a", href=True):
                if "tehtava.php" in a["href"]:
                    if alerts:
                        alerts[-1].url = _resolve(a["href"])
                    break
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
        d, mo, y = date_str.split(".")
        event_time = f"{y}-{mo}-{d} {time_str}"

        alert_type = clean(cells[3].get_text())
        if not alert_type:
            continue

        # Inline link (rare on listing page)
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
