/**
 * Baileys WhatsApp Server
 * Railway deployment ready
 */

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} = require("@whiskeysockets/baileys");

const express = require("express");
const fs = require("fs");
const path = require("path");
const pino = require("pino");

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const DATA_DIR = process.env.RAILWAY_VOLUME_MOUNT_PATH || __dirname;
const SESSIONS_DIR = path.join(DATA_DIR, "wa_sessions");

if (!fs.existsSync(SESSIONS_DIR)) {
  fs.mkdirSync(SESSIONS_DIR, { recursive: true });
}

// ─── Active sockets store ───
const sockets = {}; // { userId: socket }
const connectionStatus = {}; // { userId: "connected" | "disconnected" }

// ─── Logger (silent) ───
const logger = pino({ level: "silent" });

// ─── Start session for a user ───
async function startSession(userId) {
  if (sockets[userId]) {
    console.log(`⚠️ Session already exists for ${userId}`);
    return;
  }

  const sessionDir = path.join(SESSIONS_DIR, userId);
  if (!fs.existsSync(sessionDir)) {
    fs.mkdirSync(sessionDir, { recursive: true });
  }

  const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    logger,
    printQRInTerminal: false,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    generateHighQualityLinkPreview: false,
    syncFullHistory: false,
  });

  sockets[userId] = sock;
  connectionStatus[userId] = "disconnected";

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect } = update;

    if (connection === "open") {
      connectionStatus[userId] = "connected";
      console.log(`✅ WhatsApp connected: ${userId}`);
    }

    if (connection === "close") {
      connectionStatus[userId] = "disconnected";
      const shouldReconnect =
        lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;

      console.log(`🔴 WhatsApp disconnected: ${userId}, reconnect: ${shouldReconnect}`);

      delete sockets[userId];

      if (shouldReconnect) {
        setTimeout(() => startSession(userId), 5000);
      } else {
        // Logged out — session delete করো
        try {
          fs.rmSync(path.join(SESSIONS_DIR, userId), { recursive: true, force: true });
        } catch (e) {}
        delete connectionStatus[userId];
      }
    }
  });

  return sock;
}

// ─── Disconnect session ───
async function disconnectSession(userId) {
  try {
    if (sockets[userId]) {
      await sockets[userId].logout();
      delete sockets[userId];
    }
    connectionStatus[userId] = "disconnected";
    // Session files delete করো
    const sessionDir = path.join(SESSIONS_DIR, userId);
    if (fs.existsSync(sessionDir)) {
      fs.rmSync(sessionDir, { recursive: true, force: true });
    }
    delete connectionStatus[userId];
    console.log(`🔴 Logged out: ${userId}`);
  } catch (e) {
    console.error(`Logout error ${userId}:`, e.message);
  }
}

// ─── Boot: existing sessions restore করো ───
async function restoreExistingSessions() {
  try {
    if (!fs.existsSync(SESSIONS_DIR)) return;
    const dirs = fs.readdirSync(SESSIONS_DIR);
    for (const userId of dirs) {
      const sessionDir = path.join(SESSIONS_DIR, userId);
      if (fs.statSync(sessionDir).isDirectory()) {
        console.log(`🔄 Restoring session: ${userId}`);
        await startSession(userId);
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
  } catch (e) {
    console.error("Restore sessions error:", e.message);
  }
}

// ══════════════════════════════════════════
//               API ENDPOINTS
// ══════════════════════════════════════════

// ─── Health check ───
app.get("/", (req, res) => {
  res.json({
    status: "ok",
    message: "Baileys WhatsApp Server Running",
    sessions: Object.keys(sockets).length,
  });
});

// ─── Start session ───
app.post("/start", async (req, res) => {
  const { userId } = req.body;
  if (!userId) return res.status(400).json({ error: "userId required" });

  try {
    await startSession(userId.toString());
    res.json({ success: true, message: "Session started" });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ─── Get pairing code ───
app.post("/pair", async (req, res) => {
  const { phone, userId } = req.body;
  if (!phone || !userId)
    return res.status(400).json({ error: "phone and userId required" });

  try {
    const uid = userId.toString();
    let sock = sockets[uid];

    // যদি already connected থাকে
    if (sock && connectionStatus[uid] === "connected") {
      return res.json({ connected: true });
    }

    // নতুন session start করো
    if (!sock) {
      sock = await startSession(uid);
      await new Promise((r) => setTimeout(r, 3000));
    }

    // Pairing code request করো
    const digits = phone.replace(/\D/g, "");
    const code = await sock.requestPairingCode(digits);

    console.log(`🔑 Pairing code for +${digits}: ${code}`);
    res.json({ code, success: true });
  } catch (e) {
    console.error("Pair error:", e.message);
    res.status(500).json({ error: e.message });
  }
});

// ─── Check status ───
app.get("/status", (req, res) => {
  const userId = req.query.userId;
  if (!userId) return res.status(400).json({ error: "userId required" });

  const uid = userId.toString();
  const connected =
    !!sockets[uid] && connectionStatus[uid] === "connected";

  res.json({ connected, userId: uid });
});

// ─── Check WhatsApp numbers ───
app.post("/check", async (req, res) => {
  const { numbers, userId } = req.body;
  if (!numbers || !userId)
    return res.status(400).json({ error: "numbers and userId required" });

  const uid = userId.toString();
  const sock = sockets[uid];

  if (!sock || connectionStatus[uid] !== "connected") {
    return res.status(400).json({ error: "Not connected" });
  }

  try {
    const results = {};
    for (const num of numbers) {
      try {
        const digits = num.replace(/\D/g, "");
        const jid = digits + "@s.whatsapp.net";
        const [result] = await sock.onWhatsApp(jid);
        results[digits] = result?.exists === true;
      } catch (e) {
        results[num] = null;
      }
    }
    res.json({ results, success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ─── Disconnect ───
app.post("/disconnect", async (req, res) => {
  const { userId } = req.body;
  if (!userId) return res.status(400).json({ error: "userId required" });

  try {
    await disconnectSession(userId.toString());
    res.json({ success: true, message: "Disconnected" });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ─── Send message (optional) ───
app.post("/send", async (req, res) => {
  const { userId, to, message } = req.body;
  if (!userId || !to || !message)
    return res.status(400).json({ error: "userId, to, message required" });

  const uid = userId.toString();
  const sock = sockets[uid];

  if (!sock || connectionStatus[uid] !== "connected") {
    return res.status(400).json({ error: "Not connected" });
  }

  try {
    const digits = to.replace(/\D/g, "");
    const jid = digits + "@s.whatsapp.net";
    await sock.sendMessage(jid, { text: message });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ══════════════════════════════════════════
//               START SERVER
// ══════════════════════════════════════════
app.listen(PORT, async () => {
  console.log("=====================================");
  console.log(`🚀 Baileys Server running on port ${PORT}`);
  console.log(`📁 Sessions: ${SESSIONS_DIR}`);
  console.log("=====================================");

  // Existing sessions restore করো
  await restoreExistingSessions();
});

process.on("uncaughtException", (err) => {
  console.error("Uncaught Exception:", err.message);
});

process.on("unhandledRejection", (err) => {
  console.error("Unhandled Rejection:", err?.message || err);
});