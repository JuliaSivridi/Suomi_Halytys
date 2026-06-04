import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Legacy: if set, this channel is auto-registered on first start with DEFAULT_CITY
CHAT_ID = os.getenv("CHAT_ID", "")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Lappeenranta")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5"))
DB_PATH = os.getenv("DB_PATH", "alerts.db")
RETENTION_DAYS = 7
SILENT_FIRST_RUN = os.getenv("SILENT_FIRST_RUN", "true").lower() != "false"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
