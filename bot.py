"""
Halytys — Telegram bot that monitors Finnish emergency alert sites
and sends deduplicated notifications for Lappeenranta.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.error import TelegramError

import config
import storage
from emojis import get_emoji
from scrapers import SCRAPER_FALLBACK_CHAIN
from scrapers.base import Alert
from scrapers.tilannehuone_fi import fetch_description

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_TIME_TOLERANCE_MIN = 5
# Don't send events older than this on any cycle (catches bad date parses)
_MAX_EVENT_AGE_H = 25
# On first run (SILENT_FIRST_RUN=false), only send events from last N hours
_STARTUP_SEND_AGE_H = 24


def _norm_time(event_time: str) -> str:
    """Round down to nearest 5 minutes for fuzzy deduplication."""
    try:
        dt = datetime.fromisoformat(event_time)
        rounded = dt.replace(minute=(dt.minute // _TIME_TOLERANCE_MIN) * _TIME_TOLERANCE_MIN, second=0)
        return rounded.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return event_time


def _norm_type(alert_type: str) -> str:
    """Normalise alert type for deduplication: lowercase, strip punctuation/icons."""
    t = alert_type.lower()
    t = re.sub(r"[^\w\s]", " ", t)   # punctuation → space
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _now_local() -> datetime:
    """Current time in Finnish timezone (UTC+3 in summer, UTC+2 in winter).
    Events from sites have no tz info and use Finnish local time.
    Server runs UTC, so we offset by 3h to avoid filtering valid events as 'future'.
    """
    from datetime import timezone, timedelta as td
    return datetime.now(timezone.utc).replace(tzinfo=None) + td(hours=3)


def _is_future(event_time: str) -> bool:
    """Return True if parsed event_time is more than 30 min in the future (bad parse)."""
    try:
        dt = datetime.fromisoformat(event_time)
        return dt > _now_local() + timedelta(minutes=30)
    except ValueError:
        return False


def _is_too_old(event_time: str) -> bool:
    try:
        dt = datetime.fromisoformat(event_time)
        return dt < _now_local() - timedelta(hours=_MAX_EVENT_AGE_H)
    except ValueError:
        return False


def _format_message(alert: Alert) -> str:
    emoji = get_emoji(alert.alert_type)
    title = alert.alert_type.capitalize()
    desc = alert.description.strip() if alert.description else ""
    # Drop description if it's just icons/symbols or identical to type
    if desc and _norm_type(desc) != _norm_type(alert.alert_type) and re.search(r"\w", desc):
        title += f" — {desc.lower()}"
    try:
        dt = datetime.fromisoformat(alert.event_time)
        time_str = dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        time_str = alert.event_time
    lines = [f"{emoji} <b>{title}</b>", f"🕐 {time_str}"]
    if alert.url:
        lines.append(f'🔗 <a href="{alert.url}">Lisätiedot</a>')
    return "\n".join(lines)


async def _send_with_retry(bot: Bot, msg: str) -> bool:
    """Send a message, retrying once on flood control. Returns True on success."""
    for attempt in range(2):
        try:
            await bot.send_message(chat_id=config.CHAT_ID, text=msg, parse_mode="HTML")
            return True
        except TelegramError as e:
            err = str(e)
            if "Flood control" in err or "429" in err:
                # Parse retry_after from message "Retry in X seconds"
                m = re.search(r"Retry in (\d+)", err)
                wait = int(m.group(1)) + 2 if m else 30
                logger.warning("Flood control, waiting %ds", wait)
                await asyncio.sleep(wait)
            else:
                logger.error("Failed to send message: %s", e)
                return False
    return False


async def check_and_notify(bot: Bot, silent: bool = False, max_age_h: int | None = None) -> None:
    """Scrape all sources, deduplicate, optionally send new alerts.
    silent=True: marks everything as seen without sending (used on first run by default).
    max_age_h: if set, skip events older than this many hours (used on startup send).
    """
    storage.purge_old()
    new_count = 0

    alerts: list[Alert] = []
    for source_name, scrape_fn in SCRAPER_FALLBACK_CHAIN:
        try:
            alerts = await asyncio.get_event_loop().run_in_executor(None, scrape_fn)
        except Exception as exc:
            logger.error("Scraper %s crashed: %s", source_name, exc)
            alerts = []
        if alerts:
            logger.info("Using source: %s (%d alerts)", source_name, len(alerts))
            break
        logger.warning("%s returned 0 alerts, trying next source...", source_name)

    for alert in alerts:
        if _is_future(alert.event_time):
            continue
        if _is_too_old(alert.event_time):
            continue
        if max_age_h is not None:
            try:
                dt = datetime.fromisoformat(alert.event_time)
                if dt < _now_local() - timedelta(hours=max_age_h):
                    continue
            except ValueError:
                pass

        norm_time = _norm_time(alert.event_time)
        norm_type = _norm_type(alert.alert_type)
        alert_id = storage.make_id(norm_time, norm_type, alert.location)

        if storage.is_known(alert_id):
            continue

        storage.save(
            alert_id=alert_id,
            event_time=alert.event_time,
            alert_type=alert.alert_type,
            location=alert.location,
            description=alert.description,
            source=alert.source,
            raw_text=alert.raw_text,
        )

        # Fetch detail page description (address/notes) for tilannehuone events
        if alert.url and alert.source == "tilannehuone.fi" and not alert.description:
            desc = await asyncio.get_event_loop().run_in_executor(
                None, fetch_description, alert.url
            )
            if desc:
                alert.description = desc
                # Update the stored description too
                storage.update_description(alert_id, desc)

        if silent:
            continue

        msg = _format_message(alert)
        if await _send_with_retry(bot, msg):
            new_count += 1
            logger.info("Sent: %s / %s", alert.event_time, alert.alert_type)
        await asyncio.sleep(1.5)

    if new_count:
        logger.info("Sent %d new alert(s) this cycle.", new_count)


async def main() -> None:
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env")
    if not config.CHAT_ID:
        raise ValueError("CHAT_ID is not set in .env")

    storage.init_db()
    bot = Bot(token=config.BOT_TOKEN)

    me = await bot.get_me()
    logger.info("Bot started: @%s — checking every %d min", me.username, config.CHECK_INTERVAL)

    # First cycle: by default silently mark current events as seen to avoid startup spam.
    # Set SILENT_FIRST_RUN=false in .env to send everything found on startup (for testing).
    logger.info("First run: scanning existing alerts (silent=%s)...", config.SILENT_FIRST_RUN)
    await check_and_notify(
        bot,
        silent=config.SILENT_FIRST_RUN,
        max_age_h=_STARTUP_SEND_AGE_H if not config.SILENT_FIRST_RUN else None,
    )
    logger.info("First run complete. Future new alerts will be sent.")

    await bot.send_message(
        chat_id=config.CHAT_ID,
        text=(
            "🚒 <b>Halytys-botti käynnistetty!</b>\n"
            f"Seuraan hälytyksiä Lappeenrannassa.\n"
            f"Tarkistusväli: {config.CHECK_INTERVAL} min"
        ),
        parse_mode="HTML",
    )

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_and_notify,
        "interval",
        minutes=config.CHECK_INTERVAL,
        args=[bot],
        next_run_time=datetime.now() + timedelta(minutes=config.CHECK_INTERVAL),
    )
    scheduler.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
