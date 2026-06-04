"""Scraper for paloasema.fi/lappeenranta"""
import logging
import re
from bs4 import BeautifulSoup
from .base import Alert
from .utils import get, parse_datetime, clean

logger = logging.getLogger(__name__)
URL = "https://www.paloasema.fi/lappeenranta"
SOURCE = "paloasema.fi"


def scrape() -> list[Alert]:
    resp = get(URL)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    alerts: list[Alert] = []

    # Site uses <ul><li><a> structure with SVG icons, location, type, time
    for item in soup.select("ul li, .alert-list li, .incidents li"):
        raw = clean(item.get_text(" | ", strip=True))
        if not raw or not re.search(r"\d{1,2}:\d{2}", raw):
            continue
        if any(h in raw.lower() for h in ["aika", "tyyppi", "sijainti"]):
            continue

        parts = [p.strip() for p in raw.split("|") if p.strip()]

        date_str = ""
        time_str = ""
        location = "Lappeenranta"
        alert_type = ""
        description = ""

        for p in parts:
            if p.lower().startswith("klo"):
                time_str = p
                date_str = "tänään"
            elif p.lower().startswith("eilen"):
                date_str = "eilen"
                time_str = p
            elif re.match(r"^\d{1,2}\.\d{1,2}", p):
                sub = p.split()
                date_str = sub[0]
                if len(sub) > 1:
                    time_str = sub[1]
            elif re.match(r"^\d{1,2}:\d{2}", p):
                time_str = p
            elif "lappeenranta" in p.lower() or "villmanstrand" in p.lower():
                location = p
            elif not alert_type:
                alert_type = p
            else:
                description += " " + p

        if not time_str:
            continue

        event_time = parse_datetime(date_str, time_str)
        alerts.append(Alert(
            event_time=event_time,
            alert_type=alert_type.strip(),
            location=location,
            description=description.strip(),
            source=SOURCE,
            raw_text=raw,
        ))

    logger.info("%s: %d alerts", SOURCE, len(alerts))
    return alerts
