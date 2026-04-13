#!/bin/bash
echo "🔧 Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>/dev/null
apt-get install -y nodejs 2>/dev/null || true

echo "📦 Installing npm packages..."
npm install

echo "🚀 Starting services..."
node baileys_server.js &
echo "✅ Baileys server started (PID: $!)"

echo "✅ Starting Telegram bot..."
python bot.py