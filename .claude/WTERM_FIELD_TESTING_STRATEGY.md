# wterm Field Testing & Performance Baseline Strategy

**Phase:** TRACK D — wterm Observability Prototype (2 weeks)  
**Target Deployment:** Conflict zones (Ukraine, Gaza, Israel), field nodes with intermittent connectivity  
**Objective:** Validate wterm + USB tethering integration under realistic constraints

---

## 1. Test Environment Setup (3-Node Cluster)

### 1.1 Hardware Configuration

**Node A: Primary Edge Node (dashboard + wterm server)**
- Option 1: Intel NUC (i5-12600, 16 GB RAM, 512 GB SSD) — Production grade
- Option 2: Raspberry Pi 4B 8GB + USB-C hub — Field-hardened
- OS: Ubuntu 24.04 or Debian bookworm
- Network: USB 3.0 tether (from Node C), WiFi fallback

**Node B: Optional secondary (load testing)**
- Laptop (macOS or Linux)
- Role: Simulate 10-50 concurrent wterm sessions

**Node C: Data Source (Android Phone)**
- Android 11+ (API 30+)
- USB-C cable (for gnirehtet reverse tether)
- Starlink Mini (optional for connectivity test)
- Connectivity modes: USB tether, WiFi hotspot, offline

### 1.2 Pre-Test Checklist

```bash
# Node A (Edge)
□ ADB installed: adb --version
□ gnirehtet binary + driver: ./gnirehtet install-driver
□ Node.js 20.14+: node --version
□ siss-dashboard built: cd services/siss-dashboard && npm run build
□ Rust toolchain: cargo --version (for siss-job-router mock)
□ Disk space: >2 GB free (logs + metrics)

# Node C (Phone)
□ USB debugging enabled: Settings → Developer Options → USB Debugging
□ Phone unlocked during test (gnirehtet requires interactive auth)
□ Starlink app installed (if using)
□ Battery: >80% or charger connected
```

---

## 2. Test Scenarios (Priority-Ranked)

### Scenario 1: Basic Connectivity & Latency (CRITICAL)

**Objective:** Verify WebSocket + terminal rendering latency is <100ms end-to-end

**Duration:** 30 minutes

**Setup:**
```bash
# Node A
cd services/siss-dashboard
npm run dev &

# Node C (phone)
adb connect <phone-ip>
./gnirehtet rt-server &
sleep 3

# Measure
curl -i http://localhost:2026  # Verify server up
```

**Test Procedure:**
1. Open browser on Node A: `http://localhost:2026/command-center`
2. Verify wterm terminal loads (WASM initialization)
3. Type: `echo "latency-test-$(date +%s%N)"`
4. Record timestamp at keystroke and at output display
5. Repeat 10 times, calculate average

**Success Criteria:**
- Server responds within 2 seconds
- Terminal renders within 5 seconds
- Round-trip latency <100ms (p95)

**Metrics to Log:**
```json
{
  "test": "scenario-1-latency",
  "timestamp": "2026-05-29T14:00:00Z",
  "results": {
    "p50_ms": 25,
    "p95_ms": 87,
    "p99_ms": 120,
    "server_response_ms": 1800,
    "wterm_render_ms": 4200,
    "sample_count": 10
  }
}
```

---

### Scenario 2: Memory Stability (24-Hour Soak Test)

**Objective:** Detect memory leaks under continuous streaming

**Duration:** 24 hours (automated)

**Setup:**
```bash
# Mock job event stream (emit every 100ms)
node mock-job-events.js &

# Monitor memory every 10 seconds
node monitor-memory.js > /tmp/memory-soak.jsonl &
```

**Mock Event Script:** `mock-job-events.js`
```javascript
const fs = require('fs');
const WebSocket = require('ws');

const ws = new WebSocket('ws://localhost:2026/api/ws');

ws.on('open', () => {
  let counter = 0;
  setInterval(() => {
    ws.send(JSON.stringify({
      type: 'output',
      data: `[${new Date().toISOString()}] Job ${counter++} routed\r\n`,
    }));
  }, 100);
});

ws.on('error', (e) => console.error('WebSocket error:', e));
```

**Memory Monitor Script:** `monitor-memory.js`
```javascript
const os = require('os');
const fs = require('fs');

setInterval(() => {
  const mem = process.memoryUsage();
  fs.appendFileSync('/tmp/memory-soak.jsonl', JSON.stringify({
    timestamp: new Date().toISOString(),
    heap_used_mb: Math.round(mem.heapUsed / 1024 / 1024),
    heap_total_mb: Math.round(mem.heapTotal / 1024 / 1024),
    external_mb: Math.round(mem.external / 1024 / 1024),
  }) + '\n');
}, 10000);
```

**Success Criteria:**
- Heap size stable within ±50 MB over 24h
- No process crash
- GC pauses <500ms (check via Node.js perf hooks)

**Analysis After 24h:**
```bash
# Check for memory leak trend
node analyze-memory.js /tmp/memory-soak.jsonl

# Output:
# ✓ Linear regression slope: 0.002 MB/hour (stable)
# ✓ Max heap: 180 MB (acceptable)
# ✗ Pause time spike at 14h (investigate)
```

---

### Scenario 3: USB Tether Stability & Reconnection

**Objective:** Validate gnirehtet bridge handles USB disconnection gracefully

**Duration:** 1 hour (manual intervention)

**Procedure:**
1. Start tether: `./bootstrap-usb-tether.sh <phone-serial>`
2. Verify terminal streaming job events (5 min)
3. Physically unplug USB cable
4. Observe: Does terminal freeze? Error message?
5. Wait 30 seconds, replug USB
6. Observe: Does terminal resume streaming?

**Expected Behavior:**
- ✅ Terminal displays "Connection lost" message
- ✅ Automatic reconnection attempt (with backoff)
- ✅ Resume streaming without manual intervention
- ✅ No data corruption

**Failure Handling (what NOT to do):**
- ❌ Silent disconnect (user unaware)
- ❌ Crash entire dashboard
- ❌ Require page reload

**Code (error handling):**
```typescript
// In CommandCenter component
const [connectionStatus, setConnectionStatus] = useState('connected');

useEffect(() => {
  let reconnectAttempts = 0;
  const maxRetries = 10;

  const connect = () => {
    ws = new WebSocket(`ws://${window.location.host}/api/ws`);
    
    ws.onopen = () => {
      setConnectionStatus('connected');
      reconnectAttempts = 0;
    };

    ws.onerror = () => setConnectionStatus('error');

    ws.onclose = () => {
      setConnectionStatus('disconnected');
      if (reconnectAttempts < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
        setTimeout(connect, delay);
        reconnectAttempts++;
      }
    };
  };

  connect();
}, []);

return (
  <>
    <Terminal ... />
    {connectionStatus === 'disconnected' && (
      <div className="bg-yellow-900 p-4 text-white">
        ⚠️ Connection lost. Reconnecting...
      </div>
    )}
  </>
);
```

---

### Scenario 4: Accessibility VoiceOver/TalkBack Test

**Objective:** Verify WCAG 2.1 AA compliance on real devices

**Duration:** 1 hour per device

**Device Setup:**
- macOS: Built-in VoiceOver (Cmd+F5)
- iOS (optional): Safari + VoiceOver
- Android: TalkBack enabled in Settings → Accessibility

**Test Cases (per device):**

| Test Case | Action | Expected Behavior | Pass |
|-----------|--------|-------------------|------|
| **A1** | Open localhost:2026 | Page title announced | ✅ |
| **A2** | Tab to terminal | Terminal region announced (role=textbox) | ✅ |
| **A3** | Type "hello" | Voice reads "h", "e", "l", "l", "o" (optional) | ⚠️ |
| **A4** | Press Escape | Focus returns to previous region | ✅ |
| **A5** | Job completes | Status message announced via aria-live | ✅ |
| **A6** | Tab to disconnect msg | "Connection lost" announced | ✅ |

**Pass Criteria:**
- ≥5/6 test cases pass on each device
- Failing cases: document as "known limitation" + add GitHub issue

**Test Report Template:**
```markdown
## Accessibility Test Report

**Date:** 2026-05-29  
**Device:** macOS 14 + VoiceOver  

| Test Case | Result | Notes |
|-----------|--------|-------|
| A1 | ✅ | Page title "SISS Command Center" announced |
| A2 | ✅ | Terminal region detected as textbox |
| A3 | ⚠️ | Character echoing not announced (minor) |
| A4 | ✅ | Escape works, focus moves to menu |
| A5 | ✅ | "Job complete" announced via aria-live |
| A6 | ✅ | Disconnect message announced |

**Compliance Score:** 5/6 (83%)  
**WCAG Level:** AA compliant (except A3 which is AAA)  
**Recommendation:** A3 is cosmetic; prioritize other fixes if WCAG baseline met.
```

---

### Scenario 5: Load Testing (10+ Concurrent Terminals)

**Objective:** Measure server stability under multi-user load

**Duration:** 30 minutes

**Setup:**
```bash
# Install load testing tool
npm install -g autocannon

# Or use raw script
node load-test-ws.js 10  # 10 concurrent WebSocket clients
```

**Load Test Script:** `load-test-ws.js`
```javascript
const WebSocket = require('ws');
const http = require('http');

const clientCount = parseInt(process.argv[2]) || 5;
const eventInterval = 100; // ms

let successCount = 0;
let errorCount = 0;

async function runClient(id) {
  return new Promise((resolve) => {
    const ws = new WebSocket('ws://localhost:2026/api/ws');
    let messageCount = 0;

    ws.on('open', () => {
      const ticker = setInterval(() => {
        if (messageCount++ > 100) {
          clearInterval(ticker);
          ws.close();
          successCount++;
          resolve();
        }
        ws.send(JSON.stringify({
          type: 'output',
          data: `[Client ${id}] Message ${messageCount}\r\n`,
        }));
      }, eventInterval);

      ws.on('error', () => {
        errorCount++;
        clearInterval(ticker);
        resolve();
      });

      ws.on('close', () => {
        clearInterval(ticker);
        if (messageCount < 100) errorCount++;
        resolve();
      });
    });
  });
}

Promise.all(
  Array.from({ length: clientCount }, (_, i) => runClient(i))
).then(() => {
  console.log(`Results: ${successCount} success, ${errorCount} errors`);
  process.exit(errorCount > 0 ? 1 : 0);
});
```

**Success Criteria:**
- ≥95% of clients successfully connect and stream 100+ messages
- Server memory increase <200 MB (10 concurrent)
- No timeouts or dropped connections

**Metrics:**
```json
{
  "test": "scenario-5-load-test",
  "concurrent_clients": 10,
  "messages_per_client": 100,
  "success_rate": 0.98,
  "error_count": 1,
  "server_memory_delta_mb": 85,
  "avg_latency_ms": 45,
  "p99_latency_ms": 210
}
```

---

### Scenario 6: Offline Resilience (Intermittent Connectivity)

**Objective:** Verify graceful degradation when phone loses connectivity

**Duration:** 30 minutes

**Test Procedure:**
1. Start tethering: `./bootstrap-usb-tether.sh <phone-serial>`
2. Verify streaming (5 min)
3. Disable WiFi on phone (Settings → WiFi toggle OFF)
4. Disable mobile data (Settings → Mobile Network toggle OFF)
5. Observe terminal behavior for 10 minutes
6. Re-enable mobile data, observe recovery

**Expected Behavior:**
- ✅ Terminal shows buffered messages (up to scrollback limit)
- ✅ New events queued on server (not dropped)
- ✅ Once connectivity restored, events flush to terminal
- ⚠️ Older events (>1000 lines) may be truncated (acceptable)

**Success Criteria:**
- No data corruption
- No crash
- Graceful reconnection within 30 seconds

---

## 3. Performance Baseline Targets

| Metric | Target | Acceptable | Fail |
|--------|--------|-----------|------|
| **Latency (p95)** | <50ms | <100ms | >150ms |
| **Memory per instance** | <20 MB | <50 MB | >100 MB |
| **Max memory (10 clients)** | <150 MB | <250 MB | >500 MB |
| **CPU per terminal** | <5% | <15% | >30% |
| **WebSocket uptime** | 99.9% | 99% | <99% |
| **WCAG compliance** | AA | AA | Below AA |
| **Accessibility (% pass)** | 100% | 80%+ | <80% |
| **Reconnection time** | <5s | <15s | >30s |

---

## 4. Data Collection & Logging

### 4.1 Instrumentation

**Browser (DevTools):**
```javascript
// In wterm component
const perfObserver = new PerformanceObserver((list) => {
  list.getEntries().forEach((entry) => {
    console.log({
      name: entry.name,
      duration: entry.duration,
      timestamp: entry.startTime,
    });
  });
});

perfObserver.observe({ entryTypes: ['measure', 'navigation'] });
```

**Server-side (Axum):**
```rust
use tracing::{info, debug};
use std::time::Instant;

async fn handle_ws(socket: WebSocket) {
    let start = Instant::now();
    let client_id = uuid::Uuid::new_v4();
    
    info!(client_id = %client_id, "WebSocket connected");
    
    // ... message loop ...
    
    let duration = start.elapsed();
    info!(client_id = %client_id, duration_ms = duration.as_millis(), "WebSocket disconnected");
}
```

**Log Aggregation:**
```bash
# Ship logs to central storage
docker run -d \
  -p 5144:5144/udp \
  -v /tmp/logs:/var/log/syslog-ng \
  syslog-ng:latest

# Configure app to ship logs (optional, Cargo.toml dependency)
cargo add tracing-syslog
```

### 4.2 Metrics Collection Checklist

**Per test scenario, collect:**
- [ ] Timestamp (UTC, 2026-05-29T14:30:00Z format)
- [ ] Latency histogram (p50, p95, p99)
- [ ] Memory snapshot (before, during, after)
- [ ] Error logs (if any)
- [ ] Browser console (warnings, errors)
- [ ] Network tab (WebSocket frames)

**Automated collection script:**
```bash
#!/bin/bash
# run-test-suite.sh

RESULTS_DIR="test-results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "Running scenario 1: latency..."
npm run test:scenario-1 > "$RESULTS_DIR/scenario-1.json"

echo "Running scenario 2: memory soak (24h)..."
# ... (triggered separately)

echo "Running scenario 4: accessibility..."
npm run test:scenario-4 > "$RESULTS_DIR/scenario-4.json"

echo "Running scenario 5: load test..."
npm run test:scenario-5 > "$RESULTS_DIR/scenario-5.json"

echo "✅ All tests complete. Results in $RESULTS_DIR"
```

---

## 5. Failure Modes & Troubleshooting

| Symptom | Likely Cause | Troubleshooting |
|---------|--------------|-----------------|
| **Terminal black screen** | WASM not loaded | Check: `npm run build`, no CSP restrictions, browser console |
| **Latency >500ms** | Network lag or server overload | Check: `top`, network tab (WebSocket frame size), run on direct USB |
| **Memory leak (heap grows steadily)** | Event listener not cleaned up | Check: `useEffect` cleanup, DevTools heap snapshots |
| **VoiceOver can't read terminal** | Missing `role=textbox` or `aria-label` | Wrap Terminal in accessible div with ARIA attributes |
| **gnirehtet connection timeout** | ADB driver not installed | Run: `./gnirehtet install-driver`, restart ADB |
| **Can't connect to localhost:2026** | Server not running or port conflict | Check: `lsof -i :2026`, verify `npm run dev` started |

---

## 6. Regression Testing (Post-Deployment)

**Weekly Checklist (automated):**
```bash
# Daily smoke test
curl -s http://localhost:2026 | grep -q "SISS Command Center" && echo "✓" || echo "✗"

# Weekly performance regression
npm run test:baseline > /tmp/baseline-$(date +%Y%m%d).json
# Compare against last week's baseline
```

---

## 7. Report Template & Sign-Off

**Test Report:** `field-test-report-2026-05-29.md`

```markdown
# wterm Field Testing Report

**Date:** 2026-05-29 to 2026-05-31  
**Environment:** 3-node cluster (Intel NUC + RPi4B + Android 12)  
**Tester:** [Name], [Organization]  

## Summary

✅ **PASS:** wterm integration validated for production deployment  
⚠️ **CAUTION:** Memory monitoring recommended for >24h continuous operation  
❌ **FAIL:** None  

## Scenario Results

| Scenario | Status | Notes |
|----------|--------|-------|
| 1. Latency | ✅ PASS | p95: 42ms (target: <50ms) |
| 2. Memory (24h) | ✅ PASS | Stable within ±30 MB |
| 3. USB Reconnection | ✅ PASS | Reconnects in <8s |
| 4. Accessibility | ✅ PASS | WCAG 2.1 AA compliant (5/6 tests) |
| 5. Load (10 concurrent) | ✅ PASS | 98% success rate |
| 6. Offline Resilience | ✅ PASS | Buffer preserved, no data loss |

## Recommendations

1. **Deploy:** Approved for field use with Raspberry Pi 4B+ (8GB RAM minimum)
2. **Monitor:** Implement server-side memory profiling (daily snapshot)
3. **Fallback:** Keep ttyd binary available; swap if wterm crashes
4. **Accessibility:** Enhance A3 (character echoing) for AAA compliance (optional)

## Sign-Off

- [ ] Performance metrics meet baselines
- [ ] Accessibility tested on 2+ devices
- [ ] Offline resilience validated
- [ ] Fallback mechanism available
- [ ] Ready for production

**Approver:** ________________________  
**Date:** ________________________
```

---

## 8. Timeline & Owner Assignment

| Week | Task | Owner | Deliverable |
|------|------|-------|-------------|
| W1 (May 29–Jun 2) | Setup 3-node cluster + Scenario 1-2 | Agent: Infra | Latency + memory baselines |
| W1 (parallel) | Scenario 3-4 (USB + A11y) | Agent: QA | USB reconnection proof + WCAG report |
| W2 (Jun 2–5) | Scenario 5-6 + regression suite | Agent: Perf | Load test results + offline resilience |
| W2 (end) | Compile final report + sign-off | Agent: PM | Field-test-report-2026-05-29.md |

---

## Appendix: Monitoring Commands

**Real-time server metrics:**
```bash
# Watch memory + connections
watch -n 1 'ps aux | grep siss-dashboard; netstat -an | grep 2026 | wc -l'

# CPU profile (Node.js)
node --prof services/siss-dashboard/app.js
node --prof-process isolate-*.log > profile.txt

# WebSocket frame inspection (Chrome DevTools)
# Network tab → Filter "WS" → Click frame → Messages subtab
```

**Local load test (quick sanity check):**
```bash
# 5 clients, 10 messages each
timeout 30 node load-test-ws.js 5

# Or use Apache Bench (if using HTTP, not WS)
ab -n 1000 -c 10 http://localhost:2026/
```

---

**Document Version:** 1.0  
**Status:** READY TO EXECUTE  
**Expected Completion:** June 2–5, 2026
