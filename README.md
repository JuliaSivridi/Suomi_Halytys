# Suomi Halytys Bot

A Telegram bot that monitors Finnish emergency alert websites and sends real-time notifications — for any city in Finland.

Users can subscribe personally or connect a Telegram channel to a specific city.

## Features

- Any Finnish city supported — powered by tilannehuone.fi
- Personal subscriptions via DM or channel subscriptions via `/setchannel`
- Automatic fallback between sources if the primary is unavailable
- Fetches human-written descriptions and addresses from event detail pages
- Emoji-coded alert types for quick visual recognition
- Deduplicates events across sources and check cycles
- Retains event history for 7 days, auto-purges older records
- Unreachable subscribers (blocked/deactivated) are removed automatically

## Commands

| Command | Where | Description |
|---|---|---|
| `/start` | DM | Introduction and usage instructions |
| `/setcity Tampere` | DM | Subscribe to alerts for a city |
| `/mycity` | DM | Show your current city |
| `/stop` | DM | Unsubscribe |
| `/setchannel Tampere` | In channel | Register the channel to receive alerts for a city |

### How to set up a channel

1. Create a Telegram channel
2. Add the bot as admin with **Post Messages** permission
3. Post `/setchannel YourCity` in the channel
4. Done — the bot will send all new alerts for that city to the channel

## Alert sources (fallback order)

| Source | Notes |
|---|---|
| [tilannehuone.fi](https://www.tilannehuone.fi) | Primary — reliable times, detail page links, all cities |
| [paloasema.fi](https://www.paloasema.fi) | First fallback |
| [hälytyslista.fi](https://xn--hlytyslista-l8a.fi) | Second fallback |

The bot queries the primary source first. If it returns no results, the next source is tried. Only one source is used per cycle.

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

### 1. Create a Telegram bot

Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=your_telegram_bot_token
CHECK_INTERVAL=5
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

The database is preserved. The bot silently catches up with current events on startup and only sends new ones going forward.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Telegram bot token (required) |
| `CHECK_INTERVAL` | `5` | Minutes between checks |
| `DB_PATH` | `alerts.db` | SQLite database path |
| `SILENT_FIRST_RUN` | `true` | Set to `false` to send last 24 h of events on startup (testing) |
