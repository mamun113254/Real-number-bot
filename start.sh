#!/bin/bash

echo "======================================="
echo "🚀 Starting UPDATE Otp Bot Services..."
echo "======================================="

# Find node in nix store
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
NODE_BIN=$(find /nix/store -name "node" -type f 2>/dev/null | grep "bin/node$" | head -1)
if [ -n "$NODE_BIN" ]; then
  export PATH="$(dirname $NODE_BIN):$PATH"
fi

echo "📦 Node: $(node --version 2>/dev/null || echo NOT FOUND)"
echo "🐍 Python: $(python3 --version 2>/dev/null || echo NOT FOUND)"
echo "======================================="

# Baileys WhatsApp Server
if [ -f "baileys_server.js" ]; then
  echo "📱 Starting Baileys WhatsApp Server..."
  node baileys_server.js &
  echo "✅ Baileys PID: $!"
  sleep 3
fi

# Telegram Bot - use bot.js if node works, else bot.py
if command -v node &>/dev/null && [ -f "bot.js" ]; then
  echo "🤖 Starting Telegram Bot (Node.js)..."
  node bot.js &
  echo "✅ Bot PID: $!"
elif [ -f "bot.py" ]; then
  echo "🐍 Starting Telegram Bot (Python fallback)..."
  python3 bot.py &
  echo "✅ Python Bot PID: $!"
fi

echo "✅ All services started!"
wait
