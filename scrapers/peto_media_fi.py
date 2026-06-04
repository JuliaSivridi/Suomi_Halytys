"""
Scraper for peto-media.fi — official Finnish Rescue Services RSS feed.

Feed URL: http://www.peto-media.fi/tiedotteet/rss.xml
Contains the 100 most recent rescue tasks for all of Finland.
Each item is filtered by city name after fetching the shared feed.

Title format: "CityFi[/CitySv], alert_type[: scale]"
  e.g. "Lappeenranta/Villmanstrand, rakennuspalo: pieni"
       "Helsinki/Helsingfors, palohälytys"
"""
import logging
import re
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from .base import Alert
from .utils import get

logger = logging.getLogger(__name__)

SOURCE = "peto-media.fi"
FEED_URL = "http://www.peto-media.fi/tiedotteet/rss.xml"

# "CityFi[/CitySv], alert_type[: scale]"
_TITLE_RE = re.compile(r"^([^,]+),\s*(.+)$")


def _parse_city(city_part: str) -> str:
    """Return Finnish city name (before slash if bilingual)."""
    return city_part.split("/")[0].strip()


def _city_matches(city_part: str, wanted: str) -> bool:
    """Case-insensitive match against either Finnish or Swedish city name."""
    return wanted.lower() in city_part.lower()


def _parse_pubdate(pub_date: str) -> str:
    """Convert RFC 2822 pubDate (with +0300) to 'YYYY-MM-DD HH:MM' local string."""
    try:
        dt = parsedate_to_datetime(pub_date)
        # pubDate already carries +0300; format as naive local string for consistency
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return pub_date


def scrape(city: str = "Lappeenranta") -> list[Alert]:
    resp = get(FEED_URL)
    if not resp:
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        logger.error("%s: XML parse error: %s", SOURCE, e)
        return []

    alerts: list[Alert] = []
    channel = root.find("channel")
    if channel is None:
        return []

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        m = _TITLE_RE.match(title)
        if not m:
            continue

        city_part, type_part = m.group(1).strip(), m.group(2).strip()
        if not _city_matches(city_part, city):
            continue

        # Split "rakennuspalo: pieni" → alert_type="rakennuspalo", description="pieni"
        if ": " in type_part:
            alert_type, description = type_part.split(": ", 1)
        else:
            alert_type, description = type_part, ""

        event_time = _parse_pubdate(pub_date) if pub_date else ""
        location = _parse_city(city_part)
        raw = f"{city_part} | {event_time} | {type_part}"

        alerts.append(Alert(
            event_time=event_time,
            alert_type=alert_type.strip(),
            location=location,
            description=description.strip(),
            source=SOURCE,
            raw_text=raw,
            url="",  # feed has no per-event detail links
        ))

    logger.info("%s [%s]: %d alerts", SOURCE, city, len(alerts))
    return alerts
