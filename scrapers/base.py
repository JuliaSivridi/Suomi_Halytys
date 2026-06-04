from dataclasses import dataclass


@dataclass
class Alert:
    event_time: str   # normalized "YYYY-MM-DD HH:MM"
    alert_type: str   # Finnish type string
    location: str
    description: str
    source: str
    raw_text: str
    url: str = ""     # optional link to detail page
