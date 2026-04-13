#!/bin/bash
set -e

echo "=========================================="
echo "🚀 Starting Earning Hub Bot Services..."
echo "=========================================="

# Install npm packages if node_modules missing
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm packages..."
    npm install
fi

# Install python packages if needed
echo "🐍 Checking Python packages..."
pip install -r requirements.txt --quiet

# Start Baileys server in background
echo "📱 Starting Baileys server..."
node baileys_server.js &
BAILEYS_PID=$!
echo "✅ Baileys server started (PID: $BAILEYS_PID)"

# Wait a bit for Baileys to initialize
sleep 3

# Start Python bot (foreground - keeps container alive)
echo "🤖 Starting Telegram bot..."
python bot.py

# If bot exits, kill baileys too
kill $BAILEYS_PID 2>/dev/null || true
