# Suomi Halytys Bot

[![@Suomi_Halytys_bot](https://img.shields.io/badge/@Suomi__Halytys__bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/Suomi_Halytys_bot)

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

A Telegram bot that monitors Finnish emergency alert websites and sends real-time notifications for any city in Finland.

Users subscribe personally via DM or connect a Telegram channel to one or more cities.

## Features

- Any Finnish city supported — powered by tilannehuone.fi
- Multiple cities per subscriber or channel
- Personal subscriptions via DM, channel subscriptions via `/setchannel`
- Automatic source fallback if the primary is unavailable
- Fetches human-written descriptions and addresses from event detail pages
- Emoji-coded alert types for quick visual recognition
- Deduplicates events across sources and check cycles
- Retains event history for 7 days, auto-purges older records
- Unreachable subscribers are removed automatically

## Commands

### Personal (DM)

| Command | Description |
|---|---|
| `/start` | Introduction and usage |
| `/setcity Tampere` | Subscribe to alerts for a city (additive) |
| `/removecity Tampere` | Remove one city from subscription |
| `/mycities` | List your current subscriptions |
| `/stop` | Cancel all subscriptions |

### Channel (post inside the channel)

| Command | Description |
|---|---|
| `/setchannel Tampere` | Add a city to the channel |
| `/removechannel Tampere` | Remove a city from the channel |
| `/channelcities` | List all cities registered for the channel |

### How to set up a channel

1. Create a Telegram channel
2. Add the bot as admin with **Post Messages** permission
3. Post `/setchannel YourCity` in the channel — repeat for each city
4. Done

## Alert sources (fallback order)

| Source | Notes |
|---|---|
| 1️⃣ [peto-media.fi](https://www.peto-media.fi) | Primary — **official** Finnish Rescue Services RSS feed |
| 2️⃣ [tilannehuone.fi](https://www.tilannehuone.fi) | First fallback — provides event detail page links |
| 3️⃣ [paloasema.fi](https://www.paloasema.fi) | Second fallback |
| 4️⃣ [hälytyslista.fi](https://xn--hlytyslista-l8a.fi) | Third fallback |

Each cycle the primary source is tried first. The next source is used only if the previous returns no results.

All aggregator sites ultimately pull from the same official Pelastustoimen mediapalvelu feed — the bot goes straight to the source.

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

Create a bot via [@BotFather](https://t.me/BotFather), copy the token, and set the commands:

```
setcity - Tilaa kaupunki (esim. /setcity Tampere)
removecity - Poista kaupunki tilauksesta
mycities - Näytä omat tilaukset
stop - Peruuta kaikki tilaukset
setchannel - Lisää kaupunki kanavalle (käytä kanavassa)
removechannel - Poista kaupunki kanavalta (käytä kanavassa)
channelcities - Näytä kanavan kaupungit (käytä kanavassa)
```

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

View logs:

```bash
docker compose logs -f
```

The `data/` directory is mounted as a volume — the SQLite database persists across restarts and rebuilds.

## Updating

```bash
git pull
docker compose up -d --build
```

The database is preserved and auto-migrated on startup.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Telegram bot token (required) |
| `CHECK_INTERVAL` | `5` | Minutes between checks |
| `DB_PATH` | `alerts.db` | SQLite database path |
| `SILENT_FIRST_RUN` | `true` | Set to `false` to send last 24 h of events on startup (testing) |
