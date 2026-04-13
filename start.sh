#!/bin/bash

echo "=========================================="
echo "🚀 Starting Earning Hub Bot Services..."
echo "=========================================="

# Install Node.js if not found
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    apt-get update -qq
    apt-get install -y -qq curl
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>/dev/null
    apt-get install -y -qq nodejs
    echo "✅ Node.js installed: $(node -v)"
else
    echo "✅ Node.js already available: $(node -v)"
fi

# Install npm packages (force)
echo "📦 Installing npm packages..."
npm install
echo "✅ npm install done"

# Install python packages
echo "🐍 Installing Python packages..."
pip install "python-telegram-bot==21.3" pyotp --quiet
echo "✅ Python packages installed"

# Start Baileys server in background
echo "📱 Starting Baileys server..."
node baileys_server.js &
BAILEYS_PID=$!
echo "✅ Baileys started (PID: $BAILEYS_PID)"

sleep 3

# Start Python bot
echo "🤖 Starting Telegram bot..."
python bot.py
