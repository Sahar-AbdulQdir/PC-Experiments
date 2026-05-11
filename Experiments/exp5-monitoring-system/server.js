/**
 * Smart Home Monitor — Node.js Server
 * Sensors: MQ-2 + Flame only
 */

const express   = require('express');
const http      = require('http');
const WebSocket = require('ws');
const path      = require('path');

const PORT   = 3000;
const app    = express();
const server = http.createServer(app);

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const wss = new WebSocket.Server({ server });

let latestData = {
  gasRaw: 0, gasDelta: 0, gasPct: 0,
  gasStatus: 'SAFE', flame: false,
  timestamp: new Date().toISOString(),
  connected: false
};

const dataHistory  = [];
const MAX_HISTORY  = 60;
let lastESP32Post  = 0;
const ESP32_TIMEOUT = 8000;

/* ── ESP32 posts here ──────────────────────────────────── */
app.post('/data', (req, res) => {
  const b = req.body;
  if (typeof b.gasRaw !== 'number') {
    return res.status(400).json({ error: 'Invalid payload' });
  }

  lastESP32Post = Date.now();
  latestData = {
    gasRaw    : b.gasRaw    ?? 0,
    gasDelta  : b.gasDelta  ?? 0,
    gasPct    : b.gasPct    ?? 0,
    gasStatus : b.gasStatus ?? 'SAFE',
    flame     : b.flame     ?? false,
    timestamp : new Date().toISOString(),
    connected : true
  };

  dataHistory.push({ gasPct: latestData.gasPct, timestamp: latestData.timestamp });
  if (dataHistory.length > MAX_HISTORY) dataHistory.shift();

  const payload = JSON.stringify({ ...latestData, history: dataHistory });
  let n = 0;
  wss.clients.forEach(c => {
    if (c.readyState === WebSocket.OPEN) { c.send(payload); n++; }
  });

  console.log(
    `[${new Date().toLocaleTimeString()}]  ` +
    `Gas: ${latestData.gasPct}%  [${latestData.gasStatus}]  ` +
    `Flame: ${latestData.flame ? 'DETECTED ⚠' : 'clear'}  ` +
    `→ ${n} browser(s)`
  );

  res.json({ status: 'ok', clients: n });
});

/* ── Latest snapshot ───────────────────────────────────── */
app.get('/latest', (req, res) => {
  const isOnline = (Date.now() - lastESP32Post) < ESP32_TIMEOUT;
  res.json({ ...latestData, connected: isOnline, history: dataHistory });
});

app.get('/health', (req, res) => {
  res.json({
    status     : 'ok',
    wsClients  : wss.clients.size,
    esp32Online: (Date.now() - lastESP32Post) < ESP32_TIMEOUT,
    uptime     : Math.floor(process.uptime())
  });
});

/* ── WebSocket — send snapshot on browser connect ──────── */
wss.on('connection', (ws) => {
  const isOnline = (Date.now() - lastESP32Post) < ESP32_TIMEOUT;
  ws.send(JSON.stringify({ ...latestData, connected: isOnline, history: dataHistory }));
  console.log(`[WS] Browser connected  (total: ${wss.clients.size})`);
  ws.on('close', () => console.log(`[WS] Browser disconnected (total: ${wss.clients.size})`));
  ws.on('error', err => console.error('[WS] Error:', err.message));
});

/* ── ESP32 offline detection ───────────────────────────── */
setInterval(() => {
  if (!lastESP32Post) return;
  const isOnline = (Date.now() - lastESP32Post) < ESP32_TIMEOUT;
  if (!isOnline && latestData.connected) {
    latestData.connected = false;
    const payload = JSON.stringify({ ...latestData, history: dataHistory });
    wss.clients.forEach(c => { if (c.readyState === WebSocket.OPEN) c.send(payload); });
    console.log('[!!] ESP32 went offline');
  }
}, 3000);

/* ── Start ─────────────────────────────────────────────── */
server.listen(PORT, '0.0.0.0', () => {
  console.log('\n╔══════════════════════════════════════════╗');
  console.log('║   Smart Home Monitor — Server Ready      ║');
  console.log(`║   Dashboard → http://localhost:${PORT}        ║`);
  console.log('╚══════════════════════════════════════════╝\n');
  const { networkInterfaces } = require('os');
  const nets = networkInterfaces();
  for (const name of Object.keys(nets))
    for (const net of nets[name])
      if (net.family === 'IPv4' && !net.internal) {
        console.log(`   Network  : http://${net.address}:${PORT}`);
        console.log(`   ESP32 URL: "http://${net.address}:${PORT}/data"\n`);
      }
});
