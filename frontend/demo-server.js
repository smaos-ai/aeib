/**
 * SMAOS Public Demo Server
 * Safe endpoint for public demos (no sensitive data exposed)
 *
 * Features:
 * - Serves beautiful SMAOS UI
 * - Uses mock data (no real backend)
 * - Watermarked as "DEMO MODE"
 * - Public-safe (no IP exposure)
 */

const express = require('express');
const path = require('path');
const cors = require('cors');

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Serve static frontend (build output)
app.use(express.static(path.join(__dirname, 'dist')));

// Mock API endpoints (safe demo data)
app.get('/api/pool/status', (req, res) => {
  res.json({
    timestamp: new Date().toISOString(),
    containers: {
      ready: 2,
      total: 2,
      age: 1741.5,
      merkle: '3bc3e299f8d47dca395f7b6a18e0ca86'
    },
    message: '[DEMO MODE] Sandbox pool online'
  });
});

app.get('/api/metrics', (req, res) => {
  res.json({
    timestamp: new Date().toISOString(),
    tokenSpeed: 39.3,
    memoryUsage: 2.4,
    cpuUsage: 45,
    networkEgress: 0,
    requestsPerMin: 42,
    message: '[DEMO MODE] Real-time metrics'
  });
});

app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    mode: 'DEMO',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    warning: 'This is a demo environment. No actual AI agent running.'
  });
});

// Fallback to index.html (SPA)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist/index.html'));
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════════════════════════════╗
║           SMAOS PUBLIC DEMO SERVER RUNNING                     ║
╠════════════════════════════════════════════════════════════════╣
║  URL:          http://localhost:${PORT}                             ║
║  Mode:         DEMO (safe for public)                          ║
║  Backend:      Mock/Synthetic data                             ║
║  Exposed:      UI, Flows, Examples                             ║
║  Protected:    Infrastructure, Algorithms, Real data           ║
╚════════════════════════════════════════════════════════════════╝
  `);
});
