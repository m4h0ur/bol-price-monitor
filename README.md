# Bol.com Price Monitor Bot

A Telegram bot that monitors Bol.com product prices and sends notifications when prices change.

## Features
- Monitor multiple products
- Get notifications on price changes
- Easy to use Telegram interface
- Docker support

## Setup

1. Create a Telegram bot:
   - Talk to [@BotFather](https://t.me/botfather) on Telegram
   - Create a new bot with `/newbot`
   - Save the bot token

2. Run with Docker:
```bash
# Clone the repository
git clone https://github.com/m4h0ur/bol-price-monitor.git
cd bol-price-monitor

# Set your bot token
nano docker-compose.yml  # Edit TELEGRAM_BOT_TOKEN

# Start the bot
docker-compose up -d
```

3. Use the bot:
- Start: `/start`
- Add product: `/add URL`
- List products: `/list`
- Remove product: `/remove`

