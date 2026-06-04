from .base import Alert
from .tilannehuone_fi import scrape as _scrape_tilannehuone
from .paloasema_fi import scrape as _scrape_paloasema
from .hlytyslista_fi import scrape as _scrape_hlytyslista
from .tilannehuone_fi import fetch_description  # re-export for bot.py

# Each entry: (name, scrape_fn)
# scrape_fn accepts city: str keyword argument
SCRAPER_FALLBACK_CHAIN = [
    ("tilannehuone.fi", _scrape_tilannehuone),
    ("paloasema.fi",    _scrape_paloasema),
    ("hälytyslista.fi", _scrape_hlytyslista),
]
