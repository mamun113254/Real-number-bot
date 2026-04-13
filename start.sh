#!/bin/bash
echo "🚀 Starting services..."

# Start Baileys WhatsApp server in background
node baileys_server.js &
BAILEYS_PID=$!
echo "✅ Baileys server started (PID: $BAILEYS_PID)"

# Wait a bit for baileys to initialize
sleep 3

# Start Telegram bot
echo "✅ Starting Telegram bot..."
node bot.js

# If bot exits, kill baileys too
kill $BAILEYS_PID 2>/dev/null
