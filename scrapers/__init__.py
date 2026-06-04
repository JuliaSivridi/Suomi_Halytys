from .base import Alert
from .tilannehuone_fi import scrape as scrape_tilannehuone_fi
from .paloasema_fi import scrape as scrape_paloasema_fi
from .hlytyslista_fi import scrape as scrape_hlytyslista_fi

# Tried in order — next source is used only if the previous returned 0 alerts or failed
SCRAPER_FALLBACK_CHAIN = [
    ("tilannehuone.fi", scrape_tilannehuone_fi),
    ("paloasema.fi",    scrape_paloasema_fi),
    ("hälytyslista.fi", scrape_hlytyslista_fi),
]
