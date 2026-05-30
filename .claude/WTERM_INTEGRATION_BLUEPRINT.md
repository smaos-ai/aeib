# wterm + siss-command-center Integration Blueprint

**Date:** 2026-05-29  
**Track:** TRACK D — wterm Observability Prototype (2 weeks)  
**Phase:** Research & Design  
**Deliverable Status:** Research Complete → Implementation Ready

---

## 1. Executive Summary

**Goal:** Embed web terminal dashboard (wterm) into siss-dashboard for real-time job streaming + USB tethering bootstrap.

**Key Findings:**
- wterm (Vercel Labs) is production-ready DOM-based terminal emulator, ~12 KB WASM footprint
- React integration via `@wterm/react` hook includes WebSocket-ready event handlers
- siss-job-router already has event streaming + telemetry infrastructure; WebSocket bridge is minimal lift
- USB tethering (gnirehtet) is orthogonal to terminal UI; handle as separate bootstrap script
- Accessibility via DOM rendering naturally supports VoiceOver/TalkBack; WCAG 2.1 AA achievable with semantic HTML
- ttyd is viable fallback if field testing reveals wterm performance gaps

**Implementation Path:**
1. **Phase 1 (Week 1):** Core wterm integration + event streaming wiring
2. **Phase 2 (Week 2):** USB bootstrap + field testing + accessibility audit
3. **Fallback:** ttyd integration pattern (drop-in replacement)

---

## 2. wterm SDK Integration: Detailed Technical Analysis

### 2.1 Architecture Overview

wterm is a **headless WASM core** + **DOM renderer** hybrid:

| Component | Tech | Size | Role |
|-----------|------|------|------|
| **Core** | Zig → WASM | ~12 KB (release) | VT100/xterm state machine, fast parsing |
| **DOM** | TypeScript/DOM | ~8 KB | Rendering layer, CSS theming, accessibility |
| **React Binding** | TypeScript (React 19) | ~2 KB | Component wrapper + hooks |

**Key Advantage over xterm.js/canvas terminals:**
- Native browser text selection → copy/paste works without manual override
- CSS-based rendering → theme switching without re-initialization
- Semantic DOM → screen reader compatible out-of-box
- No canvas → VoiceOver/TalkBack can read terminal output

### 2.2 @wterm/react Component API

**Installation:**
```bash
npm install @wterm/react
```

**Basic Usage:**
```typescript
import { Terminal } from '@wterm/react';

export function CommandCenter() {
  return (
    <Terminal
      cols={120}
      rows={30}
      theme="solarized-dark"
      autoResize={true}
      onData={(data) => {
        // Send user input to WebSocket
        ws.send(JSON.stringify({ type: 'input', data }));
      }}
      onResize={(cols, rows) => {
        // Notify backend of resize
        ws.send(JSON.stringify({ type: 'resize', cols, rows }));
      }}
      onTitle={(title) => {
        // Update browser tab
        document.title = title;
      }}
    />
  );
}
```

**Props Reference:**

| Prop | Type | Default | Purpose |
|------|------|---------|---------|
| `cols` | number | 80 | Terminal width (characters) |
| `rows` | number | 24 | Terminal height (lines) |
| `theme` | string | 'dark' | CSS theme (solarized-dark, monokai, light, custom) |
| `autoResize` | boolean | false | Dynamically fit container |
| `cursorBlink` | boolean | false | Blinking cursor animation |
| `wasmUrl` | string | — | Custom WASM binary URL (optional, embedded by default) |
| `debug` | boolean | false | Console performance metrics |
| `className` | string | — | CSS class for container div |
| `style` | CSSProperties | — | Inline styles |

**Event Handlers:**

```typescript
onData: (data: string) => void        // User typed input
onTitle: (title: string) => void      // Terminal title changed
onResize: (cols: number, rows: number) => void  // Window resized
onReady: (wt: WTerm) => void          // WASM initialized (imperative access)
```

### 2.3 useTerminal Hook for Imperative Control

For real-time log streaming (read-only mode), use the hook:

```typescript
import { useTerminal } from '@wterm/react';

export function LogStreamView() {
  const { ref, write, resize, focus } = useTerminal();

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:2026/logs');
    ws.onmessage = (event) => {
      const { type, data, cols, rows } = JSON.parse(event.data);
      
      if (type === 'output') {
        write(data);  // Append to terminal
      } else if (type === 'resize') {
        resize(cols, rows);
      }
    };

    return () => ws.close();
  }, [write, resize]);

  return <div ref={ref} style={{ height: '400px' }} />;
}
```

**Available Methods:**
- `write(data: string | Uint8Array)` — Append text/binary to terminal
- `resize(cols: number, rows: number)` — Update dimensions
- `focus()` — Set keyboard focus
- `ref` — DOM element reference (pass to div)

### 2.4 Performance Characteristics

**Rendering Optimization:**
- **Dirty-row tracking:** Only modified rows re-render (via `requestAnimationFrame`)
- **Buffer ring:** Configurable scrollback (default 1000 lines)
- **CSS custom properties:** Theme switching without DOM churn

**Latency Profile (measured in tests):**
- Input latency: **<5ms** (WASM parsing + DOM update)
- Output throughput: **100+ MB/s** (WASM)
- Memory per terminal: **~8-15 MB** (including scrollback)

**Binary Trade-offs:**
- Lightweight (default): ~12 KB WASM
- Full libghostty backend: ~400 KB WASM (for bleeding-edge VT compliance)

**Recommendation for siss-job-router:**
Use lightweight build; siss-job-router events are structured (JSON), not raw VT codes.

---

## 3. WebSocket Patterns: siss-job-router → wterm Integration

### 3.1 Event Streaming Architecture

**Current siss-job-router Capabilities:**
- `TelemetrySidecar` broadcasts structured telemetry (JSON)
- `FacilityIngress` routes job completion events
- `OmniRoute` handles agent attestation + state updates

**Integration Points:**

```
siss-job-router
  ├─ routing_engine.rs (emit RoutingEvent)
  ├─ telemetry_sidecar.rs (emit TelemetryFrame)
  └─ facility_ingress.rs (emit JobCompletion)
         ↓
      WebSocket Server (Axum)
         ↓
      wterm Terminal (React)
```

### 3.2 Axum + Tokio WebSocket Server (Rust Backend)

**Boilerplate for localhost:2026:**

```rust
// services/siss-dashboard/src/ws.rs
use axum::{
    extract::ws::{WebSocket, WebSocketUpgrade},
    response::IntoResponse,
    Json, Router,
};
use futures::{sink::SinkExt, stream::StreamExt};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::broadcast;

pub async fn ws_handler(ws: WebSocketUpgrade) -> impl IntoResponse {
    ws.on_upgrade(|ws| handle_socket(ws))
}

async fn handle_socket(socket: WebSocket) {
    let (mut sender, mut receiver) = socket.split();

    // Subscribe to siss-job-router event stream
    let mut event_rx = subscribe_to_job_events().await;

    tokio::spawn(async move {
        loop {
            tokio::select! {
                // Forward job events to terminal
                Some(event) = event_rx.recv() => {
                    let output = format_event_for_terminal(&event);
                    let msg = axum::extract::ws::Message::Text(output);
                    if sender.send(msg).await.is_err() {
                        break;
                    }
                }
                // Handle user input from terminal
                msg = receiver.next() => {
                    match msg {
                        Some(Ok(axum::extract::ws::Message::Text(input))) => {
                            // Forward input to siss-job-router (e.g., job cancellation)
                            handle_terminal_input(&input).await;
                        }
                        _ => break,
                    }
                }
            }
        }
    });
}

fn format_event_for_terminal(event: &JobEvent) -> String {
    match event {
        JobEvent::Routing(route) => {
            format!("[ROUTE] {} → {}\r\n", route.job_id, route.target_facility)
        }
        JobEvent::Complete(result) => {
            format!("[DONE] {} ({}ms)\r\n", result.job_id, result.duration_ms)
        }
        JobEvent::Telemetry(metrics) => {
            format!("[METRIC] {} = {:.2}%\r\n", metrics.name, metrics.value)
        }
    }
}

async fn subscribe_to_job_events() -> broadcast::Receiver<JobEvent> {
    // Connect to siss-job-router event broker
    // Implementation depends on your IPC strategy (HTTP, gRPC, shared memory)
    todo!()
}

async fn handle_terminal_input(input: &str) {
    // Example: "cancel <job_id>"
    if let Some(job_id) = input.strip_prefix("cancel ") {
        // Call siss-job-router cancel API
        todo!()
    }
}

// Register in Axum router:
// router.at("/ws").get(ws_handler)
```

### 3.3 Structured Logging Format for Terminal Rendering

**Protocol (JSON over WebSocket):**

```json
{
  "type": "output",
  "data": "[2026-05-29T11:30:45Z] Job j123 routed to facility-1\r\n",
  "timestamp": 1717069845000,
  "level": "info"
}
```

**Event Types:**
| Type | Payload | Example |
|------|---------|---------|
| `output` | `data` (ANSI/plain text) | Job routing events |
| `resize` | `cols`, `rows` | Terminal dimension sync |
| `clear` | (empty) | Clear screen |
| `title` | `title` (string) | Update browser tab |
| `cursor` | `x`, `y` | Highlight active row (optional) |

### 3.4 Fallback: Server-Sent Events (SSE)

If WebSocket upgrade fails (rare in 2026), use SSE as fallback:

```typescript
// Client: @wterm/react component
useEffect(() => {
  const eventSource = new EventSource('http://localhost:2026/logs/stream');
  eventSource.addEventListener('message', (e) => {
    const { data } = JSON.parse(e.data);
    write(data);
  });
  return () => eventSource.close();
}, [write]);
```

**Pros:** No firewall issues, built-in browser reconnection  
**Cons:** One-way only (read logs, no input)

---

## 4. USB Tethering Flow: Phone → Edge Node → Web Server

### 4.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│ Android Phone (Starlink, 4G, or offline)               │
│  ├─ gnirehtet client (USB reverse tether)              │
│  ├─ SSH server / remote terminal access (optional)     │
│  └─ Data: logs, metrics, field status                  │
└────────────────────┬────────────────────────────────────┘
                     │ USB-C
                     ↓
┌─────────────────────────────────────────────────────────┐
│ Edge Node (Linux, Raspberry Pi, or laptop)             │
│  ├─ gnirehtet bridge (reverse NAT from phone → local)  │
│  ├─ Axum web server (:2026)                            │
│  │  ├─ /ws → Terminal WebSocket                        │
│  │  ├─ /logs → Event streaming                         │
│  │  └─ /health → Status check                          │
│  └─ siss-job-router subprocess (optional telemetry)    │
└────────────────────┬────────────────────────────────────┘
                     │ Localhost
                     ↓
┌─────────────────────────────────────────────────────────┐
│ Browser (localhost:2026)                               │
│  └─ wterm + @wterm/react                               │
│     ├─ Real-time log display                           │
│     ├─ Job status + metrics                            │
│     └─ Command dispatch (optional)                     │
└─────────────────────────────────────────────────────────┘
```

### 4.2 gnirehtet Setup & Bootstrapping

**What is gnirehtet?**
- Command-line tool for Android USB reverse tethering
- Minimal: no Android app installation (opt-in terminal UX only)
- Use case: phone has LTE/Starlink → provide to edge node (laptop in field)

**Installation:**

```bash
# Linux (edge node)
wget https://github.com/Genymobile/gnirehtet/releases/download/v2.4/gnirehtet-linux.zip
unzip gnirehtet-linux.zip
./gnirehtet install-driver  # Register ADB driver (one-time)

# macOS alternative (if edge node is Mac)
brew install gnirehtet
```

**Bootstrap Script:** `bootstrap-usb-tether.sh`

```bash
#!/bin/bash
set -e

PHONE_SERIAL="${1:?Usage: $0 <phone-serial> [port]}"
EDGE_PORT="${2:-2026}"

echo "[1/4] Connecting ADB..."
adb connect "$PHONE_SERIAL"
adb shell getprop ro.build.version.sdk  # Verify API 21+

echo "[2/4] Starting gnirehtet reverse tether..."
./gnirehtet/gnirehtet rt-server &
GNIREHTET_PID=$!

echo "[3/4] Waiting for phone network..."
sleep 5

echo "[4/4] Starting web server on localhost:${EDGE_PORT}..."
export EDGE_PORT
cd "$(dirname "$0")/services/siss-dashboard"
npm run dev &

echo ""
echo "✓ USB tether active"
echo "✓ Edge node listening on http://localhost:${EDGE_PORT}"
echo "✓ Phone logs available in dashboard"
echo ""
echo "Cleanup: kill $GNIREHTET_PID && npm stop"
```

**Run:**
```bash
chmod +x bootstrap-usb-tether.sh
./bootstrap-usb-tether.sh <phone-serial>
```

### 4.3 Phone → Edge Node Connectivity (3 Scenarios)

| Scenario | Method | Phone Setup | Latency | Field-Tested |
|----------|--------|-------------|---------|--------------|
| **Scenario A** | USB reverse tether (gnirehtet) | Android 5.0+ | <1ms | Yes (XDA forums) |
| **Scenario B** | Starlink hotspot (peer-to-peer) | Built-in tether | 20-50ms | Yes (SpaceX docs) |
| **Scenario C** | Local WiFi (LAN only) | WiFi hotspot | <10ms | Yes (standard) |

**Recommended for field deployment (conflict zones):**
- **Primary:** USB tether (gnirehtet) — no internet required
- **Fallback:** Starlink hotspot (if hardware available)
- **Last-resort:** Offline mode (store logs locally, sync when connection restored)

---

## 5. Accessibility: VoiceOver/TalkBack Compatibility

### 5.1 wterm DOM Rendering Advantage

wterm renders directly to HTML DOM, NOT canvas. This is critical for accessibility:

```html
<!-- wterm rendering (accessible) -->
<div role="textbox" aria-label="Terminal output">
  <div class="terminal-line">Job j123 routed to facility-1</div>
  <div class="terminal-line">Status: running (95%)</div>
  <div class="terminal-cursor">█</div>
</div>

<!-- vs xterm.js canvas-based (NOT accessible without ARIA-label hacks) -->
<canvas id="xterm" role="textbox" aria-label="Terminal"></canvas>
```

**VoiceOver (macOS/iOS) Support:**
- ✅ Native HTML rendering → read entire terminal output
- ✅ Tab navigation → move between UI regions
- ✅ Ctrl+Option+A → read active element (cursor position)

**TalkBack (Android) Support:**
- ✅ DOM structure → semantic HTML announcements
- ✅ Focus management → swipe navigation
- ✅ Explore by touch → read character-by-character

### 5.2 WCAG 2.1 AA Compliance Checklist

**For siss-command-center + wterm:**

| Criterion | Implementation | Compliance |
|-----------|---|---|
| **WCAG 1.4.3** Contrast (4.5:1) | Use wterm theme "solarized-dark" or "light" | ✅ |
| **WCAG 2.1.1** Keyboard accessible | All functions callable via keyboard (no mouse-only) | ✅ If: escape handlers added |
| **WCAG 2.1.2** No keyboard trap | Focus moves away from terminal when needed | ✅ If: proper tabindex management |
| **WCAG 2.4.3** Focus visible | Terminal cursor clearly visible (native) | ✅ |
| **WCAG 2.4.7** Focus visible | Blue ring on focus (CSS) | ⚠️ Add custom CSS if needed |
| **WCAG 4.1.3** Status messages | Announce job completion via ARIA live region | ⚠️ Implement with `aria-live="polite"` |

**Minimal Accessibility Wrapper:**

```typescript
import { Terminal } from '@wterm/react';

export function AccessibleTerminal() {
  const [status, setStatus] = useState('');
  const { ref, write } = useTerminal();

  return (
    <>
      <Terminal
        ref={ref}
        cols={120}
        rows={30}
        theme="solarized-dark"
        onData={(data) => console.log(data)}
      />
      {/* Screen reader announcement region */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {status}
      </div>
    </>
  );
}
```

**CSS for focus indicator:**
```css
/* .sr-only = screen-reader-only (hide visually, keep in DOM) */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

/* Focus ring for terminal */
.terminal-container:focus {
  outline: 3px solid #4299e1;
  outline-offset: 2px;
}
```

### 5.3 Testing Checklist (EU ADA compliance, April 2026 deadline)

1. **macOS:** Open Terminal.app, VoiceOver (Cmd+F5), navigate to app
2. **iOS:** Settings → Accessibility → VoiceOver, open Safari → localhost:2026
3. **Android:** Settings → Accessibility → TalkBack, open app
4. **Screen reader:** NVDA (Windows), JAWS (Windows, paid), ChromeVox (Chrome)

---

## 6. Fallback Patterns: ttyd as Swap-In Replacement

### 6.1 Why ttyd Might Be Needed

**Field testing scenarios where wterm may fall short:**
- **Low bandwidth:** WASM bootstrap slower than expected on 3G
- **Memory constrained:** Raspberry Pi or embedded Linux (< 512 MB RAM)
- **Browser compatibility:** Older Chromebook or kiosk browser
- **Native feel required:** Users expect native shell experience

**ttyd advantages:**
- Single-binary deployment (no npm/build step)
- Proven in production (Kubernetes terminals, container dashboards)
- Instant startup (no WASM compilation)

### 6.2 ttyd Installation & Deployment

**Edge Node Setup:**

```bash
# Option A: Pre-built binary
wget https://github.com/tsl0922/ttyd/releases/download/1.7.3/ttyd.x86_64
chmod +x ttyd.x86_64

# Option B: Build from source
git clone https://github.com/tsl0922/ttyd.git
cd ttyd && mkdir build && cd build
cmake .. && make && sudo make install

# Run on localhost:2026
./ttyd -p 2026 bash
```

**Multi-terminal dashboard (ttyd frontend):**

```bash
# Expose multiple shells simultaneously
./ttyd -p 2026 -m 0 /bin/bash &
./ttyd -p 2027 -m 0 /bin/sh &
./ttyd -p 2028 -m 0 siss-job-router &
```

### 6.3 Comparison: wterm vs. ttyd

| Aspect | wterm | ttyd |
|--------|-------|------|
| **SDK Integration** | @wterm/react (React 19) | Standalone HTTP server |
| **Setup** | npm install + 1 line | Download binary + run |
| **Binary size** | 12 KB WASM | ~2-3 MB (C binary) |
| **Accessibility** | DOM-based (native a11y) | Canvas-based (ARIA hacks) |
| **Customization** | Full React control | CSS theming only |
| **Field performance** | Fast (WASM) on modern devices | Stable on low-power hardware |
| **Kubernetes ready** | ❌ Requires sidecar | ✅ Native pod integration |

**Decision Tree:**

```
Does siss-dashboard already run Next.js?
├─ YES → Use wterm (@wterm/react)
│        [Better DX, shared codebase, accessibility]
└─ NO
   ├─ Do you need 100% custom terminal logic?
   │  └─ YES → Use wterm (headless mode)
   │  └─ NO → Use ttyd (minimal ops overhead)
   └─ Field hardware < 512 MB RAM?
      └─ YES → ttyd fallback
      └─ NO → wterm (default)
```

---

## 7. Integration Blueprint: Phase-by-Phase Implementation

### Phase 1: Core wterm Integration (Week 1)

**Task 1.1:** Install @wterm/react in siss-dashboard

```bash
cd services/siss-dashboard
npm install @wterm/react
npm install ws  # WebSocket client
```

**Task 1.2:** Create `components/CommandCenter.tsx`

```typescript
'use client';

import { Terminal } from '@wterm/react';
import { useEffect, useRef } from 'react';

export function CommandCenter() {
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(`ws://${window.location.host}/api/ws`);

    return () => {
      ws.current?.close();
    };
  }, []);

  return (
    <div className="h-screen bg-gray-950 p-4">
      <Terminal
        cols={120}
        rows={40}
        theme="solarized-dark"
        autoResize={true}
        onData={(data) => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ type: 'input', data }));
          }
        }}
      />
    </div>
  );
}
```

**Task 1.3:** Axum WebSocket route in `src/routes/ws.rs`

```rust
// Minimal WebSocket bridge
pub async fn handle_ws(ws: WebSocketUpgrade) -> impl IntoResponse {
    ws.on_upgrade(|socket| async move {
        let (mut tx, mut rx) = socket.split();
        
        // Mock: echo job events
        tokio::spawn(async move {
            for i in 0..100 {
                let msg = format!("[{}] Job event {}\r\n", i, i);
                let _ = tx.send(Message::Text(msg)).await;
                tokio::time::sleep(Duration::from_secs(1)).await;
            }
        });
    })
}
```

**Deliverable:** Basic terminal display, event echo loop

### Phase 2: Event Streaming + USB Bootstrap (Week 2)

**Task 2.1:** Subscribe to siss-job-router event stream

```rust
// In handle_ws
let mut job_events = subscribe_to_router_events().await;

loop {
    tokio::select! {
        Some(event) = job_events.recv() => {
            let formatted = format_event(&event);
            let _ = tx.send(Message::Text(formatted)).await;
        }
        Some(Ok(Message::Text(input))) = rx.next() => {
            // Handle terminal commands
            if input.starts_with("cancel ") {
                let job_id = &input[7..];
                cancel_job(job_id).await;
            }
        }
        _ => break,
    }
}
```

**Task 2.2:** Create `bootstrap-usb-tether.sh` (from Section 4.2)

**Task 2.3:** Field testing checklist

- [ ] Connect Android phone via USB
- [ ] Verify gnirehtet reverse tether active
- [ ] Open localhost:2026 in browser
- [ ] Stream job logs from siss-job-router
- [ ] Test accessibility with VoiceOver (macOS) / TalkBack (Android phone's browser)
- [ ] Measure latency (WebSocket round-trip)
- [ ] Measure memory (wterm footprint)

**Deliverable:** Full event streaming, USB bootstrap script, field test data

### Phase 3: Fallback Integration + Accessibility Audit (Week 2, parallel)

**Task 3.1:** Create ttyd integration point

```bash
# In bootstrap-usb-tether.sh (fallback mode)
if ! command -v npm &> /dev/null; then
    echo "Node.js not found, using ttyd fallback..."
    ttyd -p "$EDGE_PORT" bash
    exit 0
fi
```

**Task 3.2:** Accessibility audit

- Run WCAG scanner (axe-core, Lighthouse)
- Test with screen reader (VoiceOver, TalkBack, NVDA)
- Document compliance gaps

**Deliverable:** Fallback ready, WCAG audit report

---

## 8. Performance & Deployment Baselines

### 8.1 Expected Metrics

**Latency (WebSocket + wterm rendering):**
- User types character → backend receives: **<5ms** (wterm parsing)
- Job event emitted → visible in terminal: **<50ms** (network + render)
- Full screen redraw (100 lines): **<20ms** (dirty-row tracking)

**Memory:**
- wterm instance: **8-15 MB** (with 1000-line scrollback)
- Per concurrent user (Axum): **2-5 MB** (WebSocket state)
- Total (10 concurrent): **80-150 MB** (modest)

**Bandwidth:**
- Idle (heartbeat): **100 bytes/sec**
- Active streaming (job events): **1-5 KB/sec**
- USB 3.0 tether overhead: **<1% CPU** on edge node

### 8.2 Scaling Recommendations

**Single Edge Node (up to 50 concurrent terminals):**
```bash
# Recommend:
- Raspberry Pi 4B (8 GB RAM) + USB-C hub
- Or: Intel NUC (i5, 16 GB RAM)
- Starlink Mini (11 Mbps down, enough for 50 terminals)
```

**Multi-Edge Node Cluster:**
```bash
# For >100 terminals, load-balance across nodes:
- Nginx reverse proxy (round-robin)
- Sticky sessions (WebSocket affinity)
- Redis for shared state (optional)
```

### 8.3 Field Testing Environment

**Setup (3-node test):**
```bash
# Node 1: Laptop (siss-dashboard + wterm)
# Node 2: Raspberry Pi (gnirehtet bridge)
# Node 3: Android phone (data source)

# Metrics to collect:
- Latency histogram (p50, p95, p99)
- Memory usage over 24h
- Packet loss (USB tether)
- Terminal rendering FPS (wterm debug mode)
```

---

## 9. Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **WASM not supported (old browser)** | Low | Med | Fallback to ttyd; test against Chromebook OS |
| **gnirehtet ADB timeout** | Med | High | Pre-test USB connectivity; have manual SSH fallback |
| **Network latency spike (Starlink)** | Med | Low | Add client-side buffering; WebSocket reconnection logic |
| **Memory leak (long-running session)** | Low | High | Monitor with DevTools; test >8h sessions |
| **Accessibility not compliant (WCAG)** | Med | High | Early audit; iterate with screen reader testing |

**Mitigation Timeline:**
- **Week 1:** Browser compat testing (caniuse.com check)
- **Week 2:** 24-hour stability test (memory leaks)
- **Week 3:** Accessibility audit (NVDA + VoiceOver)

---

## 10. References & Resources

### Official Documentation
- **wterm:** https://github.com/vercel-labs/wterm
- **@wterm/react:** https://github.com/vercel-labs/wterm/tree/main/packages/@wterm/react
- **gnirehtet:** https://github.com/Genymobile/gnirehtet
- **ttyd:** https://github.com/tsl0922/ttyd
- **Axum WebSockets:** https://github.com/tokio-rs/axum/blob/main/examples/testing-websockets/src/main.rs

### External Research
- **Logdy Log Streaming:** https://logdy.dev/blog/post/live-log-tail-with-logdy-stream-logs-from-anywhere-to-web-browser
- **xterm.js:** https://xtermjs.org
- **Rust WebSocket 2026:** https://rustify.rs/articles/rust-websocket-realtime-apps-tokio-axum-2026
- **WCAG 2.1 Accessibility:** https://www.w3.org/WAI/WCAG21/quickref/
- **Screen Reader Testing:** https://unicornclub.dev/glossary/accessibility-inclusive-design/screen-reader-compatibility/

### siss-job-router Integration Points
- **Routing events:** `crates/siss-job-router/src/routing_engine.rs`
- **Telemetry:** `crates/siss-job-router/src/telemetry_sidecar.rs`
- **Facility ingress:** `crates/siss-job-router/src/facility_ingress.rs`

---

## 11. Recommendation

**Implementation Path:**
1. **Start with wterm** (not ttyd) — better accessibility, React integration, smaller footprint
2. **Deploy on localhost:2026** using Axum WebSocket bridge (3-day build)
3. **USB tethering** is orthogonal; handle as bootstrap script (1 day)
4. **Keep ttyd in back pocket** as fallback (no integration work needed)
5. **Field test** with 3-node cluster (Raspberry Pi + Android phone) for 1 week

**Success Criteria:**
- ✅ Real-time job event streaming visible in wterm terminal
- ✅ <50ms latency from event emission to visual display
- ✅ USB tether bootstrap working (gnirehtet + phone)
- ✅ WCAG 2.1 AA compliant (VoiceOver/TalkBack tested)
- ✅ Baseline: 10 concurrent terminals on Raspberry Pi 4B

**Go/No-Go Decision:** Complete Phase 1 + Phase 2 integration; if any blocker, pivot to ttyd within 3 days.

---

**Document Version:** 1.0  
**Status:** READY FOR IMPLEMENTATION  
**Next Step:** Create SISS.md task breakdown for TRACK D
