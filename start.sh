#!/bin/bash
echo "🚀 Starting Earning Hub Bot..."

# Baileys server background এ চালাও
echo "📱 Starting Baileys WhatsApp Server..."
node baileys_server.js &
BAILEYS_PID=$!
echo "✅ Baileys Server PID: $BAILEYS_PID"

# 3 সেকেন্ড অপেক্ষা করো
sleep 3

# Main bot চালাও
echo "🤖 Starting Telegram Bot..."
node bot.js

# Bot বন্ধ হলে Baileys ও বন্ধ করো
kill $BAILEYS_PID 2>/dev/null
