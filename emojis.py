"""Map Finnish alert type keywords → emoji."""

_RULES: list[tuple[list[str], str]] = [
    # Building / structure fires
    (["rakennuspalo", "rakennuspalon"], "🏠🔥"),
    # Vehicle fire
    (["liikennevälinepalo", "ajoneuvopalo"], "🚗🔥"),
    # Forest / terrain fire
    (["maastopalo", "metsäpalo", "ruohikkopalo"], "🌿🔥"),
    # Wildfire / outdoor
    (["nuotiopalo", "roskispalo", "jätepalo"], "🗑️🔥"),
    # Smoke observation
    (["savuhavainto", "savuhälytys", "savu"], "💨"),
    # Fire alarm (automatic)
    (["palohälytys", "automaattinen paloilmoitin", "paloilmoitin"], "🔔🔥"),
    # Traffic accident
    (["tieliikenneonnettomuus", "liikenneonnettomuus", "kolari"], "🚗💥"),
    # Medical / first aid
    (["ensihoito", "sairaankuljetus", "elvytys", "sydänkohtaus"], "🚑"),
    # Water / flooding
    (["vesivahinko", "tulva", "vesivuoto", "putkivuoto"], "💧"),
    # Electrical
    (["sähkövika", "sähköpalo", "sähkövaara"], "⚡"),
    # Hazmat / gas
    (["vaarallinen aine", "kaasuvuoto", "kemikaalivuoto", "öljyvahinko"], "☣️"),
    # Rescue / person in danger
    (["henkilöpelastus", "ihminen vedessä", "pelastustehtävä", "maastopelastus"], "🆘"),
    # Animal
    (["eläinpelastus", "eläin"], "🐾"),
    # False alarm
    (["turha hälytys", "erheellinen"], "✅"),
]

_DEFAULT = "🚨"


def get_emoji(alert_type: str) -> str:
    text = alert_type.lower()
    for keywords, emoji in _RULES:
        if any(kw in text for kw in keywords):
            return emoji
    return _DEFAULT
