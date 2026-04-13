const express = require("express");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");
const pino = require("pino");
const QRCode = require("qrcode");
const path = require("path");
const fs = require("fs");

const app = express();
app.use(express.json());

const PORT = process.env.BAILEYS_PORT || 3000;

const DATA_DIR = process.env.RAILWAY_VOLUME_MOUNT_PATH || __dirname;
const SESSIONS_DIR = path.join(DATA_DIR, "wa_sessions");

if (!fs.existsSync(SESSIONS_DIR)) {
  fs.mkdirSync(SESSIONS_DIR, { recursive: true });
}

// Store active sockets
const sockets = {};
const qrCodes = {};
const connectionStatus = {};

async function createSession(sessionId) {
  const sessionPath = path.join(SESSIONS_DIR, sessionId);
  if (!fs.existsSync(sessionPath)) {
    fs.mkdirSync(sessionPath, { recursive: true });
  }

  const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: "silent" }),
    printQRInTerminal: false,
  });

  sockets[sessionId] = sock;
  connectionStatus[sessionId] = "connecting";

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      try {
        qrCodes[sessionId] = await QRCode.toDataURL(qr);
        connectionStatus[sessionId] = "qr_ready";
        console.log(`📱 QR ready for session: ${sessionId}`);
      } catch (e) {
        console.error("QR error:", e);
      }
    }

    if (connection === "close") {
      const shouldReconnect =
        lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      connectionStatus[sessionId] = "disconnected";
      console.log(`🔴 Session ${sessionId} disconnected. Reconnect: ${shouldReconnect}`);
      if (shouldReconnect) {
        setTimeout(() => createSession(sessionId), 5000);
      }
    }

    if (connection === "open") {
      connectionStatus[sessionId] = "connected";
      qrCodes[sessionId] = null;
      console.log(`✅ Session ${sessionId} connected!`);
    }
  });

  sock.ev.on("creds.update", saveCreds);

  return sock;
}

// ─── API Routes ───

// Health check
app.get("/health", (req, res) => {
  res.json({ status: "ok", sessions: Object.keys(sockets) });
});

// Create/get session
app.post("/session/:sessionId", async (req, res) => {
  const { sessionId } = req.params;
  try {
    if (!sockets[sessionId]) {
      await createSession(sessionId);
    }
    res.json({ success: true, sessionId, status: connectionStatus[sessionId] });
  } catch (e) {
    res.status(500).json({ success: false, error: e.message });
  }
});

// Get QR code
app.get("/session/:sessionId/qr", (req, res) => {
  const { sessionId } = req.params;
  const qr = qrCodes[sessionId];
  const status = connectionStatus[sessionId];

  if (status === "connected") {
    return res.json({ success: true, connected: true });
  }
  if (!qr) {
    return res.json({ success: false, message: "QR not ready yet. Try again in a moment." });
  }
  res.json({ success: true, qr, status });
});

// Get session status
app.get("/session/:sessionId/status", (req, res) => {
  const { sessionId } = req.params;
  res.json({
    success: true,
    sessionId,
    status: connectionStatus[sessionId] || "not_started",
    connected: connectionStatus[sessionId] === "connected",
  });
});

// Send message
app.post("/send", async (req, res) => {
  const { sessionId, number, message } = req.body;
  if (!sessionId || !number || !message) {
    return res.status(400).json({ success: false, error: "sessionId, number, message required" });
  }

  const sock = sockets[sessionId];
  if (!sock || connectionStatus[sessionId] !== "connected") {
    return res.status(400).json({ success: false, error: "Session not connected" });
  }

  try {
    const jid = number.includes("@") ? number : `${number}@s.whatsapp.net`;
    await sock.sendMessage(jid, { text: message });
    res.json({ success: true, message: "Sent!" });
  } catch (e) {
    res.status(500).json({ success: false, error: e.message });
  }
});

// Delete session
app.delete("/session/:sessionId", (req, res) => {
  const { sessionId } = req.params;
  if (sockets[sessionId]) {
    sockets[sessionId].end();
    delete sockets[sessionId];
    delete qrCodes[sessionId];
    delete connectionStatus[sessionId];
  }
  res.json({ success: true, message: "Session removed" });
});

app.listen(PORT, () => {
  console.log(`✅ Baileys WhatsApp Server running on port ${PORT}`);
});
