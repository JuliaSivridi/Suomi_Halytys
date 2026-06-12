"""Scraper for paloasema.fi/<city> — fallback source."""
import logging
import re
from bs4 import BeautifulSoup
from .base import Alert
from .utils import get, parse_datetime, clean

logger = logging.getLogger(__name__)
SOURCE = "paloasema.fi"


def scrape(city: str = "Lappeenranta") -> list[Alert]:
    url = f"https://www.paloasema.fi/{city.lower()}"
    resp = get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    alerts: list[Alert] = []

    for item in soup.select("ul li, .alert-list li, .incidents li"):
        raw = clean(item.get_text(" | ", strip=True))
        if not raw or not re.search(r"\d{1,2}:\d{2}", raw):
            continue
        if any(h in raw.lower() for h in ["aika", "tyyppi", "sijainti"]):
            continue

        parts = [p.strip() for p in raw.split("|") if p.strip()]
        date_str = ""
        time_str = ""
        location = city
        alert_type = ""
        description = ""

        for p in parts:
            pl = p.lower()
            if pl.startswith("klo"):
                # The page lists history: "09.06.2026 | klo 12:28" or "Eilen | klo 13:37".
                # "klo" only means "today" when no date part was seen — overwriting an
                # already-parsed date here made every historical alert look like today's
                # and re-sent the whole page as new.
                time_str = p
                if not date_str:
                    date_str = "tänään"
            elif pl.startswith("eilen"):
                date_str = "eilen"
                if re.search(r"\d{1,2}:\d{2}", p):
                    time_str = p
            elif re.match(r"^\d{1,2}\.\d{1,2}", p):
                sub = p.split()
                date_str = sub[0]
                if len(sub) > 1:
                    time_str = sub[1]
            elif re.match(r"^\d{1,2}:\d{2}", p):
                time_str = p
            elif city.lower() in pl:
                # Strip the label colon ("Lappeenranta:") so the dedup id matches
                # the same event coming from other sources
                location = p.rstrip(":").strip()
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

    logger.info("%s [%s]: %d alerts", SOURCE, city, len(alerts))
    return alerts
