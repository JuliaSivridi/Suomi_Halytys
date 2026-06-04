# LPR Halytys Bot

A Telegram bot that monitors Finnish emergency alert websites and sends real-time notifications for Lappeenranta.

## Features

- Scrapes multiple sources with automatic fallback if the primary source is unavailable
- Deduplicates events across sources and across check cycles
- Emoji-coded alert types for quick visual recognition
- Includes a link to the detail page when available
- Retains event history for 7 days, auto-purges older records
- Respects Telegram rate limits with automatic retry on flood control

## Alert sources (fallback order)

| Source | Notes |
|---|---|
| [tilannehuone.fi](https://www.tilannehuone.fi/kysely.php?paikkakunta=Lappeenranta&vrk=on) | Primary — reliable times, detail page links |
| [paloasema.fi](https://www.paloasema.fi/lappeenranta) | First fallback |
| [hälytyslista.fi](https://xn--hlytyslista-l8a.fi/halytykset/lappeenranta) | Second fallback |

The bot uses the first source that returns results. If tilannehuone.fi is up, the other sources are never queried.

## Emoji reference

| Emoji | Alert type |
|---|---|
| 🏠🔥 | Rakennuspalo (building fire) |
| 🚗🔥 | Liikennevälinepalo (vehicle fire) |
| 🌿🔥 | Maastopalo (terrain/forest fire) |
| 💨 | Savuhavainto (smoke detected) |
| 🔔🔥 | Palohälytys (fire alarm) |
| 🚗💥 | Liikenneonnettomuus (traffic accident) |
| 🚑 | Ensihoito (medical emergency) |
| 💧 | Vesivahinko (water damage) |
| ⚡ | Sähkövika (electrical fault) |
| ☣️ | Vaarallinen aine (hazmat) |
| 🆘 | Pelastustehtävä (rescue operation) |
| 🚨 | Other |

## Setup

### 1. Create a Telegram bot and channel

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token
2. Create a Telegram channel (public or private)
3. Add the bot as an admin with **Post Messages** permission
4. Get the channel ID: forward any message from the channel to [@userinfobot](https://t.me/userinfobot)

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=your_telegram_bot_token
CHAT_ID=@yourchannel        # or numeric ID like -1001234567890
CHECK_INTERVAL=5            # minutes between checks
```

### 3. Run with Docker

```bash
docker compose up -d
```

Logs:

```bash
docker compose logs -f
```

The `data/` directory is mounted as a volume — the SQLite database persists across container restarts and rebuilds.

## Updating

```bash
git pull
docker compose up -d --build
```

The database is preserved; the bot will silently catch up with current events on startup and only send new ones going forward.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Telegram bot token (required) |
| `CHAT_ID` | — | Target channel/chat ID (required) |
| `CHECK_INTERVAL` | `5` | Check interval in minutes |
| `DB_PATH` | `alerts.db` | SQLite database path |
| `SILENT_FIRST_RUN` | `true` | If `false`, sends last 24 h of events on startup (useful for testing) |
