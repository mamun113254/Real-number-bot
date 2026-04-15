#!/bin/bash

echo "======================================="
echo "🚀 Starting UPDATE Otp Bot Services..."
echo "======================================="

# PATH fix
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

echo "📦 Node: $(node --version 2>/dev/null || echo NOT FOUND)"
echo "🐍 Python: $(python3 --version 2>/dev/null || echo NOT FOUND)"

# ─── Baileys WhatsApp Server ───
if [ -f "baileys_server.js" ]; then
  echo "📱 Starting Baileys WhatsApp Server..."
  node baileys_server.js &
  echo "✅ Baileys Server PID: $!"
  sleep 3
fi

# ─── Telegram Bot (Node.js) ───
if [ -f "bot.js" ]; then
  echo "🤖 Starting Telegram Bot..."
  node bot.js &
  echo "✅ Telegram Bot PID: $!"
fi

# ─── Python Bot ───
if [ -f "bot.py" ]; then
  echo "🐍 Starting Python Bot..."
  python3 bot.py &
  echo "✅ Python Bot PID: $!"
fi

echo "======================================="
echo "✅ All services started!"
echo "======================================="

wait
