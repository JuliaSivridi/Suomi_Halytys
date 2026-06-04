import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5"))
DB_PATH = os.getenv("DB_PATH", "alerts.db")
# Set to false to send all found events on first run (useful for testing)
SILENT_FIRST_RUN = os.getenv("SILENT_FIRST_RUN", "true").lower() != "false"

# How many days to keep events
RETENTION_DAYS = 7

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
