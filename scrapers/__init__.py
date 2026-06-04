from .base import Alert
from .peto_media_fi import scrape as _scrape_peto_media
from .tilannehuone_fi import scrape as _scrape_tilannehuone
from .paloasema_fi import scrape as _scrape_paloasema
from .hlytyslista_fi import scrape as _scrape_hlytyslista
from .tilannehuone_fi import fetch_description  # re-export for bot.py

# Each entry: (name, scrape_fn)
# scrape_fn accepts city: str keyword argument
# peto-media.fi is the official Finnish Rescue Services feed (primary source).
# All other sites ultimately pull from it — we go straight to the source.
SCRAPER_FALLBACK_CHAIN = [
    ("peto-media.fi",   _scrape_peto_media),
    ("tilannehuone.fi", _scrape_tilannehuone),
    ("paloasema.fi",    _scrape_paloasema),
    ("hälytyslista.fi", _scrape_hlytyslista),
]
