#!/bin/bash

echo "=========================================="
echo "🚀 Starting Earning Hub Bot Services..."
echo "=========================================="

# Start Baileys server in background
echo "📱 Starting Baileys server..."
node baileys_server.js &
BAILEYS_PID=$!
echo "✅ Baileys started (PID: $BAILEYS_PID)"

sleep 3

# Start Python bot
echo "🤖 Starting Telegram bot..."
python bot.py
