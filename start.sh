#!/bin/bash
echo "======================================="
echo "📱 Starting Baileys WhatsApp Server..."
echo "======================================="

# Remove broken .venv and install correct version
rm -rf /app/.venv
pip install --break-system-packages python-telegram-bot==20.7 pyotp aiohttp

# Start Baileys (Node)
if command -v node &> /dev/null; then
    node baileys_server.js &
    BAILEYS_PID=$!
    echo "✅ Baileys PID: $BAILEYS_PID"
else
    echo "📦 Node: NOT FOUND"
fi

echo "======================================="
echo "🚀 Starting UPDATE Otp Bot Services..."
echo "======================================="

# Check Node
if command -v node &> /dev/null; then
    echo "📦 Node: $(node --version)"
else
    echo "📦 Node: NOT FOUND"
fi

# Start Python bot
echo "🐍 Python: $(python3 --version)"
echo "🐍 Starting Telegram Bot..."
python3 bot.py &
BOT_PID=$!
echo "✅ Python Bot PID: $BOT_PID"
echo "✅ All services started!"

wait $BOT_PID
