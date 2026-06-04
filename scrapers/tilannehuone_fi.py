"""Scraper for tilannehuone.fi — accepts any Finnish city via paikkakunta param."""
import logging
import re
from bs4 import BeautifulSoup, Tag
from .base import Alert
from .utils import get, clean

logger = logging.getLogger(__name__)
BASE = "https://www.tilannehuone.fi/"
SOURCE = "tilannehuone.fi"

_DATE_TIME_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})")
_EXTRA = {"Referer": "https://www.tilannehuone.fi/"}


def _resolve(href: str) -> str:
    return href if href.startswith("http") else BASE + href.lstrip("/")


def _find_result_table(soup: BeautifulSoup) -> Tag | None:
    for tbl in soup.find_all("table"):
        for row in tbl.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 4 and _DATE_TIME_RE.search(cells[2].get_text()):
                return tbl
    return None


def fetch_description(detail_url: str) -> str:
    """Fetch event detail page and return human-written description (may contain address)."""
    resp = get(detail_url, extra_headers=_EXTRA)
    if not resp:
        return ""
    soup = BeautifulSoup(resp.text, "lxml")
    for tbl in soup.find_all("table"):
        if len(tbl.find_all(["h1", "h2", "h3"])) < 2:
            continue
        for td in tbl.find_all("td"):
            if td.find(["h1", "h2", "h3"]):
                continue
            text = clean(td.get_text(" ", strip=True))
            if not text or re.match(r"^\d{2}\.\d{2}\.\d{4}", text):
                continue
            if text.lower().startswith("lisätty"):
                continue
            if "sijaintia ei ole tarkennettu" in text.lower():
                continue
            if len(text) > 10 and re.search(r"\w{3,}", text):
                text = re.sub(r"\s*Lisätty:.*$", "", text, flags=re.IGNORECASE).strip()
                if text:
                    return text
    return ""


def scrape(city: str = "Lappeenranta") -> list[Alert]:
    url = f"https://www.tilannehuone.fi/kysely.php?paikkakunta={city}&vrk=on"
    resp = get(url, extra_headers=_EXTRA)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    result_table = _find_result_table(soup)
    if not result_table:
        logger.warning("%s: could not find result table for %s", SOURCE, city)
        return []

    alerts: list[Alert] = []

    for row in result_table.find_all("tr"):
        cells = row.find_all("td")

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

        detail_url = ""
        for a in row.find_all("a", href=True):
            if "tehtava.php" in a["href"]:
                detail_url = _resolve(a["href"])
                break

        raw = f"{location} | {dt_text} | {alert_type}"
        alerts.append(Alert(
            event_time=event_time,
            alert_type=alert_type,
            location=location or city,
            description="",
            source=SOURCE,
            raw_text=raw,
            url=detail_url,
        ))

    logger.info("%s [%s]: %d alerts", SOURCE, city, len(alerts))
    return alerts
