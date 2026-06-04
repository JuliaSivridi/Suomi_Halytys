"""
Halytys — Finnish emergency alert Telegram bot.

Personal use:  start the bot in DM, set your city, get notifications.
Channel use:   add bot as admin, post /setchannel <City> in the channel.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from functools import partial

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, Update
from telegram.error import TelegramError

import config
import storage
from emojis import get_emoji
from telegram.ext import Application, CommandHandler, ContextTypes, filters
from scrapers import SCRAPER_FALLBACK_CHAIN, fetch_description
from scrapers.base import Alert

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_TIME_TOLERANCE_MIN = 5
_MAX_EVENT_AGE_H = 25
_STARTUP_SEND_AGE_H = 24


# ── Time helpers ──────────────────────────────────────────────────────────────

def _now_local() -> datetime:
    """Current Finnish time (UTC+3 in summer). Events use Finnish local time."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3)


def _norm_time(event_time: str) -> str:
    try:
        dt = datetime.fromisoformat(event_time)
        rounded = dt.replace(
            minute=(dt.minute // _TIME_TOLERANCE_MIN) * _TIME_TOLERANCE_MIN, second=0
        )
        return rounded.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return event_time


def _norm_type(alert_type: str) -> str:
    t = alert_type.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _is_future(event_time: str) -> bool:
    try:
        return datetime.fromisoformat(event_time) > _now_local() + timedelta(minutes=30)
    except ValueError:
        return False


def _is_too_old(event_time: str, max_hours: int = _MAX_EVENT_AGE_H) -> bool:
    try:
        return datetime.fromisoformat(event_time) < _now_local() - timedelta(hours=max_hours)
    except ValueError:
        return False


# ── Formatting ────────────────────────────────────────────────────────────────

def _format_message(alert: Alert) -> str:
    emoji = get_emoji(alert.alert_type)
    title = alert.alert_type.capitalize()
    desc = alert.description.strip() if alert.description else ""
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


# ── Sending ───────────────────────────────────────────────────────────────────

async def _send(bot: Bot, chat_id: str, msg: str) -> bool:
    for _ in range(2):
        try:
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            return True
        except TelegramError as e:
            err = str(e)
            if "Flood control" in err or "429" in err:
                m = re.search(r"Retry in (\d+)", err)
                wait = int(m.group(1)) + 2 if m else 30
                logger.warning("Flood control for %s, waiting %ds", chat_id, wait)
                await asyncio.sleep(wait)
            elif "blocked" in err.lower() or "deactivated" in err.lower() or "chat not found" in err.lower():
                logger.info("Removing unreachable subscriber %s", chat_id)
                storage.unsubscribe(chat_id)
                return False
            else:
                logger.error("Send error to %s: %s", chat_id, e)
                return False
    return False


# ── Core scrape+notify loop ───────────────────────────────────────────────────

async def _scrape_city(city: str) -> list[Alert]:
    """Try scrapers in fallback order, return first non-empty result."""
    loop = asyncio.get_event_loop()
    for source_name, scrape_fn in SCRAPER_FALLBACK_CHAIN:
        try:
            alerts = await loop.run_in_executor(None, partial(scrape_fn, city=city))
        except Exception as exc:
            logger.error("Scraper %s [%s] crashed: %s", source_name, city, exc)
            alerts = []
        if alerts:
            logger.info("Source: %s [%s] → %d alerts", source_name, city, len(alerts))
            return alerts
        logger.warning("%s [%s]: 0 alerts, trying next", source_name, city)
    return []


async def check_and_notify(bot: Bot, silent: bool = False,
                            max_age_h: int | None = None) -> None:
    storage.purge_old()

    cities = storage.get_unique_cities()
    if not cities:
        logger.debug("No subscribers yet.")
        return

    for city in cities:
        alerts = await _scrape_city(city)
        subscribers = storage.get_subscribers_for_city(city)

        for alert in alerts:
            if _is_future(alert.event_time):
                continue
            if _is_too_old(alert.event_time):
                continue
            if max_age_h is not None and _is_too_old(alert.event_time, max_age_h):
                continue

            norm_time = _norm_time(alert.event_time)
            norm_type = _norm_type(alert.alert_type)
            alert_id = storage.make_id(norm_time, norm_type, alert.location)

            if storage.is_known(alert_id):
                continue

            # Fetch detail page description if available
            if alert.url and alert.source == "tilannehuone.fi" and not alert.description:
                desc = await asyncio.get_event_loop().run_in_executor(
                    None, fetch_description, alert.url
                )
                if desc:
                    alert.description = desc

            storage.save(
                alert_id=alert_id,
                city=city,
                event_time=alert.event_time,
                alert_type=alert.alert_type,
                location=alert.location,
                description=alert.description,
                source=alert.source,
                raw_text=alert.raw_text,
            )

            if silent:
                continue

            msg = _format_message(alert)
            for chat_id in subscribers:
                if await _send(bot, chat_id, msg):
                    logger.info("[%s] Sent to %s: %s / %s",
                                city, chat_id, alert.event_time, alert.alert_type)
                await asyncio.sleep(0.5)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🚒 <b>Halytys-botti</b>\n\n"
        "Lähetän pelastustoimen hälytykset haluamaltasi paikkakunnalta.\n\n"
        "<b>Komennot:</b>\n"
        "/setcity <i>Kaupunki</i> — tilaa kaupunki\n"
        "/removecity <i>Kaupunki</i> — poista kaupunki\n"
        "/mycities — näytä tilauksesi\n"
        "/stop — peruuta kaikki tilaukset\n\n"
        "<b>Kanavan ylläpitäjille:</b>\n"
        "/setchannel <i>Kaupunki</i> — lisää kaupunki kanavalle\n"
        "/removechannel <i>Kaupunki</i> — poista kaupunki kanavalta\n"
        "/channelcities — näytä kanavan kaupungit",
        parse_mode="HTML",
    )


async def cmd_setcity(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text(
            "Anna kaupungin nimi: <code>/setcity Lappeenranta</code>",
            parse_mode="HTML",
        )
        return
    city = " ".join(ctx.args).strip().capitalize()
    chat_id = update.effective_chat.id
    storage.subscribe(chat_id, city, kind="personal")
    cities = storage.get_cities(chat_id)
    await update.message.reply_text(
        f"✅ Lisätty: <b>{city}</b>\n"
        f"📍 Kaikki tilauksesi: {', '.join(cities)}",
        parse_mode="HTML",
    )
    logger.info("Subscriber %s added city %s", chat_id, city)


async def cmd_removecity(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text(
            "Anna kaupungin nimi: <code>/removecity Tampere</code>",
            parse_mode="HTML",
        )
        return
    city = " ".join(ctx.args).strip().capitalize()
    chat_id = update.effective_chat.id
    removed = storage.unsubscribe_city(chat_id, city)
    if removed:
        cities = storage.get_cities(chat_id)
        remaining = f"📍 Jäljellä: {', '.join(cities)}" if cities else "Et tilaa enää mitään."
        await update.message.reply_text(f"🗑 Poistettu: <b>{city}</b>\n{remaining}", parse_mode="HTML")
    else:
        await update.message.reply_text(f"Et tilaa kaupunkia <b>{city}</b>.", parse_mode="HTML")


async def cmd_mycities(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cities = storage.get_cities(update.effective_chat.id)
    if cities:
        await update.message.reply_text(
            "📍 <b>Tilauksesi:</b>\n" + "\n".join(f"• {c}" for c in cities),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "Et tilaa mitään. Käytä /setcity lisätäksesi kaupunki."
        )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    removed = storage.unsubscribe_all(update.effective_chat.id)
    if removed:
        await update.message.reply_text("🔕 Kaikki tilaukset peruttu.")
    else:
        await update.message.reply_text("Et ole tilannut mitään.")


def _is_channel(update: Update) -> bool:
    from telegram import Chat
    return update.effective_chat.type == Chat.CHANNEL


_NOT_A_CHANNEL = "Tämä komento toimii vain kanavassa. Kirjoita se suoraan kanavallesi."


async def cmd_setchannel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not _is_channel(update):
        await ctx.bot.send_message(chat.id, _NOT_A_CHANNEL)
        return
    city = " ".join(ctx.args).strip().capitalize() if ctx.args else ""
    if not city:
        await ctx.bot.send_message(
            chat.id,
            "Anna kaupungin nimi: <code>/setchannel Lappeenranta</code>",
            parse_mode="HTML",
        )
        return
    storage.subscribe(chat.id, city, kind="channel")
    cities = storage.get_cities(chat.id)
    await ctx.bot.send_message(
        chat.id,
        f"✅ Lisätty: <b>{city}</b>\n"
        f"📍 Kanavan kaupungit: {', '.join(cities)}",
        parse_mode="HTML",
    )
    logger.info("Channel %s added city %s", chat.id, city)


async def cmd_removechannel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not _is_channel(update):
        await ctx.bot.send_message(chat.id, _NOT_A_CHANNEL)
        return
    city = " ".join(ctx.args).strip().capitalize() if ctx.args else ""
    if not city:
        await ctx.bot.send_message(
            chat.id,
            "Anna kaupungin nimi: <code>/removechannel Tampere</code>",
            parse_mode="HTML",
        )
        return
    removed = storage.unsubscribe_city(chat.id, city)
    if removed:
        cities = storage.get_cities(chat.id)
        remaining = f"📍 Jäljellä: {', '.join(cities)}" if cities else "Kanavalla ei enää kaupunkeja."
        await ctx.bot.send_message(chat.id, f"🗑 Poistettu: <b>{city}</b>\n{remaining}", parse_mode="HTML")
    else:
        await ctx.bot.send_message(chat.id, f"Kanavalla ei ole kaupunkia <b>{city}</b>.", parse_mode="HTML")


async def cmd_channelcities(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not _is_channel(update):
        await ctx.bot.send_message(chat.id, _NOT_A_CHANNEL)
        return
    cities = storage.get_cities(chat.id)
    if cities:
        await ctx.bot.send_message(
            chat.id,
            "📍 <b>Kanavan kaupungit:</b>\n" + "\n".join(f"• {c}" for c in cities),
            parse_mode="HTML",
        )
    else:
        await ctx.bot.send_message(
            chat.id,
            "Kanavalla ei ole kaupunkeja. Käytä /setchannel lisätäksesi.",
        )


# ── Main ──────────────────────────────────────────────────────────────────────

async def post_init(app: Application) -> None:
    storage.init_db()
    bot = app.bot
    me = await bot.get_me()
    logger.info("Bot started: @%s", me.username)
    logger.info("First run: silent catch-up...")
    await check_and_notify(
        bot,
        silent=config.SILENT_FIRST_RUN,
        max_age_h=_STARTUP_SEND_AGE_H if not config.SILENT_FIRST_RUN else None,
    )
    logger.info("First run done.")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_and_notify,
        "interval",
        minutes=config.CHECK_INTERVAL,
        args=[bot],
        next_run_time=datetime.now() + timedelta(minutes=config.CHECK_INTERVAL),
    )
    scheduler.start()
    app.scheduler = scheduler  # keep reference for shutdown


def main() -> None:
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env")

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Personal commands (DM)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("setcity", cmd_setcity))
    app.add_handler(CommandHandler("removecity", cmd_removecity))
    app.add_handler(CommandHandler("mycities", cmd_mycities))
    app.add_handler(CommandHandler("stop", cmd_stop))
    # Channel commands — filters.ALL to catch channel_post updates
    app.add_handler(CommandHandler("setchannel", cmd_setchannel, filters=filters.ALL))
    app.add_handler(CommandHandler("removechannel", cmd_removechannel, filters=filters.ALL))
    app.add_handler(CommandHandler("channelcities", cmd_channelcities, filters=filters.ALL))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
