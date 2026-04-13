#!/bin/bash

echo "=========================================="
echo "🚀 Starting Earning Hub Bot Services..."
echo "=========================================="

# Install Node.js
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi
echo "✅ Node: $(node -v)"

# Install npm packages
cd /app
npm install --legacy-peer-deps

# Start Baileys server in background
echo "📱 Starting Baileys server..."
node baileys_server.js &
echo "✅ Baileys started"

sleep 3

# Start Python bot
echo "🤖 Starting Telegram bot..."
python bot.py
