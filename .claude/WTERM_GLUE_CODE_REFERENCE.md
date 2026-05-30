# wterm + siss-command-center Glue Code Reference

**Purpose:** Copy-paste ready integration code (Phase 1 implementation)  
**Language:** TypeScript (frontend) + Rust (backend)  
**Integration Points:**
1. React component (`CommandCenter.tsx`)
2. Axum WebSocket route (`src/routes/ws.rs`)
3. Event formatting from siss-job-router
4. Bootstrap script for USB tethering

---

## Part 1: Frontend Integration (@wterm/react Component)

**File:** `services/siss-dashboard/components/CommandCenter.tsx`

```typescript
'use client';

import { Terminal } from '@wterm/react';
import { useEffect, useRef, useState, useCallback } from 'react';

interface JobEvent {
  type: 'routing' | 'complete' | 'telemetry' | 'error';
  data: string;
  timestamp?: number;
  level?: 'info' | 'warn' | 'error';
}

export function CommandCenter() {
  const wsRef = useRef<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<
    'connecting' | 'connected' | 'disconnected' | 'error'
  >('connecting');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const maxRetries = 10;
  const terminalRef = useRef<HTMLDivElement>(null);

  // Establish WebSocket connection with exponential backoff
  const connectWebSocket = useCallback(() => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = window.location.host;
      const wsUrl = `${protocol}://${host}/api/ws`;

      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('[WS] Connected');
        setConnectionStatus('connected');
        setReconnectAttempts(0);

        // Send initial handshake
        wsRef.current?.send(
          JSON.stringify({
            type: 'hello',
            client_id: crypto.randomUUID(),
            version: '1.0',
          })
        );
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          // Forward to terminal via onData callback
          // (Terminal component handles this internally)
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      wsRef.current.onerror = (event) => {
        console.error('[WS] Error:', event);
        setConnectionStatus('error');
      };

      wsRef.current.onclose = () => {
        console.log('[WS] Closed');
        setConnectionStatus('disconnected');

        // Exponential backoff reconnection
        if (reconnectAttempts < maxRetries) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttempts),
            30000
          );
          console.log(`[WS] Reconnecting in ${delay}ms...`);

          setTimeout(() => {
            setReconnectAttempts((prev) => prev + 1);
            connectWebSocket();
          }, delay);
        } else {
          console.error('[WS] Max reconnection attempts reached');
        }
      };
    } catch (error) {
      console.error('[WS] Connection error:', error);
      setConnectionStatus('error');
    }
  }, [reconnectAttempts]);

  // Initialize WebSocket on mount
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmount');
      }
    };
  }, [connectWebSocket]);

  const handleTerminalData = useCallback((data: string) => {
    // Send user input to backend
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'input',
          data,
          timestamp: Date.now(),
        })
      );
    } else {
      console.warn('[Terminal] WebSocket not ready');
    }
  }, []);

  const handleTerminalResize = useCallback((cols: number, rows: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'resize',
          cols,
          rows,
          timestamp: Date.now(),
        })
      );
    }
  }, []);

  const handleTerminalTitle = useCallback((title: string) => {
    document.title = `SISS Command Center — ${title}`;
  }, []);

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">
              SISS Command Center
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Real-time job routing & telemetry dashboard
            </p>
          </div>

          {/* Connection Status Indicator */}
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${
              connectionStatus === 'connected'
                ? 'bg-green-900 text-green-100'
                : connectionStatus === 'disconnected'
                  ? 'bg-yellow-900 text-yellow-100'
                  : connectionStatus === 'error'
                    ? 'bg-red-900 text-red-100'
                    : 'bg-blue-900 text-blue-100'
            }`}
          >
            <div
              className={`w-2 h-2 rounded-full ${
                connectionStatus === 'connected'
                  ? 'bg-green-400 animate-pulse'
                  : connectionStatus === 'disconnected'
                    ? 'bg-yellow-400'
                    : connectionStatus === 'error'
                      ? 'bg-red-400'
                      : 'bg-blue-400'
              }`}
            />
            {connectionStatus === 'connecting'
              ? 'Connecting...'
              : connectionStatus === 'connected'
                ? 'Connected'
                : connectionStatus === 'disconnected'
                  ? 'Disconnected'
                  : 'Error'}
            {reconnectAttempts > 0 && ` (attempt ${reconnectAttempts})`}
          </div>
        </div>
      </header>

      {/* Terminal Container */}
      <main className="flex-1 overflow-hidden p-6">
        <div
          ref={terminalRef}
          className="w-full h-full bg-black rounded-lg border border-gray-800 shadow-lg overflow-hidden"
        >
          <Terminal
            cols={120}
            rows={40}
            theme="solarized-dark"
            autoResize={true}
            cursorBlink={true}
            onData={handleTerminalData}
            onResize={handleTerminalResize}
            onTitle={handleTerminalTitle}
            className="w-full h-full"
            style={{
              fontFamily: 'JetBrains Mono, Courier New, monospace',
              fontSize: '14px',
              lineHeight: '1.5',
            }}
          />
        </div>
      </main>

      {/* Status Bar */}
      <footer className="bg-gray-900 border-t border-gray-800 px-6 py-2 text-xs text-gray-400">
        <div className="flex justify-between items-center">
          <div>
            {wsRef.current?.readyState === WebSocket.OPEN
              ? '✓ WebSocket active'
              : '✗ WebSocket inactive'}
          </div>
          <div>
            Press <kbd className="bg-gray-800 px-2 py-1 rounded">Ctrl+C</kbd>{' '}
            to send signal |{' '}
            <kbd className="bg-gray-800 px-2 py-1 rounded">Esc</kbd> to focus
            menu
          </div>
        </div>
      </footer>

      {/* Accessibility live region */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {connectionStatus === 'connected'
          ? 'Connected to SISS command center'
          : connectionStatus === 'disconnected'
            ? 'Disconnected from command center'
            : null}
      </div>
    </div>
  );
}
```

**CSS for accessibility (globals.css):**

```css
/* Screen reader only (hide visually, keep in DOM) */
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

/* Terminal focus indicator */
.terminal-container:focus {
  outline: 3px solid #4299e1;
  outline-offset: 2px;
}

/* Smooth theme transition */
.terminal-container {
  transition: border-color 0.2s ease;
}

.terminal-container:focus {
  border-color: #4299e1;
}
```

---

## Part 2: Backend WebSocket Route (Axum)

**File:** `services/siss-dashboard/src/routes/ws.rs`

```rust
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::IntoResponse,
    Router,
};
use futures::{
    sink::SinkExt,
    stream::{SplitSink, SplitStream, StreamExt},
};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::broadcast;
use tracing::{debug, error, info, warn};

// Shared state for broadcasting job events
pub struct AppState {
    pub job_events_tx: broadcast::Sender<JobEvent>,
}

#[derive(Clone, Debug)]
pub struct JobEvent {
    pub event_type: String,
    pub data: String,
    pub timestamp: i64,
    pub level: String,
}

pub fn router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/api/ws", axum::routing::get(ws_handler))
        .with_state(Arc::new(AppState {
            job_events_tx: broadcast::channel(1000).0,
        }))
}

/// WebSocket upgrade handler
async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_socket(socket, state))
}

/// Main WebSocket message loop
async fn handle_socket(socket: WebSocket, state: Arc<AppState>) {
    let (sender, receiver) = socket.split();
    let client_id = uuid::Uuid::new_v4();

    info!(client_id = %client_id, "New WebSocket connection");

    tokio::spawn(async move {
        if let Err(e) = handle_messages(sender, receiver, state, client_id).await {
            error!(client_id = %client_id, error = ?e, "WebSocket error");
        }
        info!(client_id = %client_id, "WebSocket connection closed");
    });
}

/// Core message handling logic
async fn handle_messages(
    mut sender: SplitSink<WebSocket, Message>,
    mut receiver: SplitStream<WebSocket>,
    state: Arc<AppState>,
    client_id: uuid::Uuid,
) -> Result<(), Box<dyn std::error::Error>> {
    // Subscribe to job events
    let mut job_rx = state.job_events_tx.subscribe();

    // Send initial welcome message
    let welcome = json!({
        "type": "welcome",
        "message": "Connected to SISS Command Center",
        "client_id": client_id.to_string(),
        "timestamp": chrono::Local::now().to_rfc3339(),
    });

    sender.send(Message::Text(welcome.to_string())).await?;
    info!(client_id = %client_id, "Sent welcome message");

    loop {
        tokio::select! {
            // Forward job events to terminal
            Ok(event) = job_rx.recv() => {
                let output = format_event_for_terminal(&event);
                debug!(client_id = %client_id, data = %output, "Sending event to terminal");

                if let Err(e) = sender.send(Message::Text(output)).await {
                    warn!(client_id = %client_id, error = ?e, "Failed to send to client");
                    break;
                }
            }

            // Handle incoming messages from terminal
            Some(msg) = receiver.next() => {
                match msg {
                    Ok(Message::Text(input)) => {
                        debug!(client_id = %client_id, input = %input, "Received terminal input");

                        if let Err(e) = handle_terminal_input(&input, &state).await {
                            error!(client_id = %client_id, error = ?e, "Failed to handle input");
                        }
                    }

                    Ok(Message::Close(_)) => {
                        info!(client_id = %client_id, "Client sent close frame");
                        break;
                    }

                    Ok(_) => {
                        debug!(client_id = %client_id, "Received non-text message");
                    }

                    Err(e) => {
                        error!(client_id = %client_id, error = ?e, "WebSocket error");
                        break;
                    }
                }
            }

            // Heartbeat (optional, for keep-alive)
            _ = tokio::time::sleep(tokio::time::Duration::from_secs(30)) => {
                debug!(client_id = %client_id, "Sending heartbeat");
                let heartbeat = json!({"type": "heartbeat", "timestamp": chrono::Local::now().to_rfc3339()});
                if sender.send(Message::Text(heartbeat.to_string())).await.is_err() {
                    break;
                }
            }
        }
    }

    Ok(())
}

/// Format siss-job-router events for terminal display
fn format_event_for_terminal(event: &JobEvent) -> String {
    match event.event_type.as_str() {
        "routing" => {
            format!(
                "[ROUTE] {}\r\n",
                event.data
            )
        }
        "complete" => {
            format!(
                "[DONE] {}\r\n",
                event.data
            )
        }
        "telemetry" => {
            format!(
                "[METRIC] {}\r\n",
                event.data
            )
        }
        "error" => {
            format!(
                "[ERROR] {}\r\n",
                event.data
            )
        }
        _ => {
            format!("[LOG] {}\r\n", event.data)
        }
    }
}

/// Handle commands from terminal (e.g., "cancel <job_id>")
async fn handle_terminal_input(
    input: &str,
    _state: &Arc<AppState>,
) -> Result<(), Box<dyn std::error::Error>> {
    let trimmed = input.trim();

    if let Some(job_id) = trimmed.strip_prefix("cancel ") {
        info!(job_id = %job_id, "Canceling job");
        // TODO: Call siss-job-router cancel API
        // Example: send HTTP request to /api/jobs/{job_id}/cancel
    } else if trimmed == "help" {
        info!("User requested help");
        // TODO: Display help text in terminal
    } else {
        debug!(input = %trimmed, "Unrecognized command");
    }

    Ok(())
}

// USAGE: Add to main.rs
//
// #[tokio::main]
// async fn main() {
//     let app = Router::new()
//         .nest("/api", routes::ws::router());
//
//     let listener = tokio::net::TcpListener::bind("127.0.0.1:2026")
//         .await
//         .unwrap();
//
//     axum::serve(listener, app).await.unwrap();
// }
```

---

## Part 3: Event Injection from siss-job-router

**File:** `services/siss-dashboard/src/routes/job_events.rs`

```rust
// This demonstrates how to subscribe to siss-job-router events
// and broadcast them to connected WebSocket clients.

use crate::routes::ws::{AppState, JobEvent};
use std::sync::Arc;
use tracing::info;

/// Start background task that subscribes to job router events
pub async fn start_job_event_listener(state: Arc<AppState>) {
    tokio::spawn(async move {
        // TODO: Replace with actual siss-job-router event subscription
        // This could be:
        // 1. HTTP polling to /api/jobs/stream
        // 2. gRPC streaming
        // 3. Shared memory queue
        // 4. Message bus (Redis, NATS, etc.)

        let mut counter = 0;

        loop {
            // Simulate job events for now
            counter += 1;
            let event = JobEvent {
                event_type: "routing".to_string(),
                data: format!("Job {} routed to facility-1", counter),
                timestamp: chrono::Local::now().timestamp(),
                level: "info".to_string(),
            };

            if let Err(e) = state.job_events_tx.send(event) {
                if state.job_events_tx.receiver_count() == 0 {
                    // No subscribers, continue anyway
                    info!("No WebSocket clients listening");
                } else {
                    eprintln!("Failed to broadcast event: {}", e);
                }
            }

            tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
        }
    });
}
```

---

## Part 4: USB Tethering Bootstrap Script

**File:** `bootstrap-usb-tether.sh`

```bash
#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PHONE_SERIAL="${1:?Usage: $0 <phone-serial> [port]}"
EDGE_PORT="${2:-2026}"
GNIREHTET_DIR="./gnirehtet"
DASHBOARD_DIR="./services/siss-dashboard"

echo -e "${BLUE}[SISS USB Tether Bootstrap]${NC}"
echo ""

# Step 1: Verify ADB and gnirehtet
echo -e "${BLUE}[1/5]${NC} Checking prerequisites..."

if ! command -v adb &> /dev/null; then
    echo -e "${RED}✗ ADB not found. Install Android SDK:${NC}"
    echo "  macOS: brew install android-platform-tools"
    echo "  Linux: sudo apt-get install android-tools-adb"
    exit 1
fi

if [ ! -f "$GNIREHTET_DIR/gnirehtet" ]; then
    echo -e "${YELLOW}⚠ gnirehtet binary not found at $GNIREHTET_DIR/gnirehtet${NC}"
    echo "  Downloading..."
    mkdir -p "$GNIREHTET_DIR"
    
    OS=$(uname -s)
    if [ "$OS" == "Darwin" ]; then
        ARCH="osx"
    elif [ "$OS" == "Linux" ]; then
        ARCH="linux"
    else
        echo -e "${RED}✗ Unsupported OS: $OS${NC}"
        exit 1
    fi
    
    # Download from GitHub releases (adjust version as needed)
    curl -L https://github.com/Genymobile/gnirehtet/releases/download/v2.4/gnirehtet-${ARCH}.zip \
        -o /tmp/gnirehtet.zip
    unzip /tmp/gnirehtet.zip -d "$GNIREHTET_DIR"
    chmod +x "$GNIREHTET_DIR/gnirehtet"
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Step 2: Connect and verify phone
echo -e "${BLUE}[2/5]${NC} Connecting to phone ($PHONE_SERIAL)..."

adb connect "$PHONE_SERIAL" || {
    echo -e "${RED}✗ Failed to connect. Trying USB mode...${NC}"
    adb devices | grep -q "$PHONE_SERIAL" || {
        echo -e "${RED}✗ Phone not found. Check USB connection and adb devices${NC}"
        exit 1
    }
}

# Verify API level
API_LEVEL=$(adb -s "$PHONE_SERIAL" shell getprop ro.build.version.sdk)
if [ "$API_LEVEL" -lt 21 ]; then
    echo -e "${RED}✗ Phone API level $API_LEVEL < 21 (Android 5.0 required)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Connected (Android API $API_LEVEL)${NC}"
echo ""

# Step 3: Install ADB driver (one-time, safe to retry)
echo -e "${BLUE}[3/5]${NC} Installing gnirehtet ADB driver..."

if ! "$GNIREHTET_DIR/gnirehtet" install-driver 2>/dev/null; then
    echo -e "${YELLOW}⚠ Driver installation had issues, but continuing...${NC}"
else
    echo -e "${GREEN}✓ Driver ready${NC}"
fi
echo ""

# Step 4: Start reverse tether
echo -e "${BLUE}[4/5]${NC} Starting USB reverse tether..."

# Start in background
"$GNIREHTET_DIR/gnirehtet" rt-server > /tmp/gnirehtet.log 2>&1 &
GNIREHTET_PID=$!
echo "  PID: $GNIREHTET_PID"

# Wait for tether to stabilize
sleep 3

# Verify tether is active
if ! kill -0 $GNIREHTET_PID 2>/dev/null; then
    echo -e "${RED}✗ gnirehtet died. Check /tmp/gnirehtet.log:${NC}"
    cat /tmp/gnirehtet.log
    exit 1
fi

echo -e "${GREEN}✓ USB tether active${NC}"
echo ""

# Step 5: Start web server
echo -e "${BLUE}[5/5]${NC} Starting SISS dashboard on localhost:$EDGE_PORT..."

cd "$DASHBOARD_DIR"

# Check for node_modules
if [ ! -d "node_modules" ]; then
    echo "  Installing dependencies..."
    npm install
fi

# Start development server
export EDGE_PORT
export PHONE_SERIAL
npm run dev > /tmp/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "  PID: $DASHBOARD_PID"

sleep 5

# Test server
if curl -s http://localhost:$EDGE_PORT | grep -q "SISS"; then
    echo -e "${GREEN}✓ Dashboard running${NC}"
else
    echo -e "${YELLOW}⚠ Dashboard may not be fully started${NC}"
    echo "  Check: curl http://localhost:$EDGE_PORT"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Bootstrap complete!${NC}"
echo ""
echo "Access dashboard:"
echo -e "  ${BLUE}http://localhost:$EDGE_PORT${NC}"
echo ""
echo "Phone details:"
echo -e "  Serial: ${BLUE}$PHONE_SERIAL${NC}"
echo -e "  API Level: ${BLUE}$API_LEVEL${NC}"
echo -e "  USB Tether: ${GREEN}Active${NC}"
echo ""
echo "Logs:"
echo "  gnirehtet: /tmp/gnirehtet.log"
echo "  dashboard: /tmp/dashboard.log"
echo ""
echo "Cleanup (when done):"
echo -e "  ${BLUE}kill $GNIREHTET_PID $DASHBOARD_PID${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

# Cleanup handler
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $GNIREHTET_PID 2>/dev/null || true
    kill $DASHBOARD_PID 2>/dev/null || true
    wait 2>/dev/null || true
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

trap cleanup EXIT INT TERM

# Keep running
wait
```

**Usage:**
```bash
chmod +x bootstrap-usb-tether.sh
./bootstrap-usb-tether.sh emulator-5554    # Android emulator
./bootstrap-usb-tether.sh RF8N61D0K96      # Real phone
./bootstrap-usb-tether.sh 192.168.1.100:5555  # Network connected
```

---

## Part 5: Configuration & Dependencies

**File:** `services/siss-dashboard/package.json` (add dependencies)

```json
{
  "dependencies": {
    "@wterm/react": "^1.1.0",
    "ws": "^8.17.0"
  },
  "devDependencies": {
    "@types/ws": "^8.5.0"
  }
}
```

**Run:**
```bash
npm install
```

**Rust Cargo.toml (if using Axum backend):**

```toml
[dependencies]
axum = { version = "0.7", features = ["json", "macros", "ws"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
tracing = "0.1"
tracing-subscriber = "0.3"
futures = "0.3"
```

---

## Part 6: Minimal Testing Script

**File:** `test-wterm-integration.sh`

```bash
#!/bin/bash

echo "Testing wterm + WebSocket integration..."
echo ""

# Test 1: Server starts
echo "Test 1: Server startup"
timeout 10 npm run dev &
SERVER_PID=$!
sleep 3
curl -s http://localhost:2026 | grep -q "SISS Command Center" && echo "✓ Server OK" || echo "✗ Server failed"
kill $SERVER_PID

echo ""
echo "Test 2: WebSocket connection"
node -e "
  const WebSocket = require('ws');
  const ws = new WebSocket('ws://localhost:2026/api/ws');
  ws.on('open', () => {
    console.log('✓ WebSocket connected');
    ws.close();
  });
  ws.on('error', () => {
    console.log('✗ WebSocket failed');
    process.exit(1);
  });
  setTimeout(() => {
    console.log('✗ WebSocket timeout');
    process.exit(1);
  }, 5000);
" || true

echo ""
echo "All tests complete!"
```

---

## Debugging Tips

### 1. WebSocket debugging (Chrome DevTools)

```javascript
// In browser console
const ws = new WebSocket('ws://localhost:2026/api/ws');
ws.addEventListener('message', (event) => {
  console.log('RX:', event.data);
});
ws.send(JSON.stringify({ test: 'hello' }));
```

### 2. Server-side tracing

```bash
# Enable debug logs
RUST_LOG=debug cargo run

# Or Node.js
DEBUG=* npm run dev
```

### 3. Network inspection

```bash
# Capture WebSocket frames
tcpdump -i lo -A 'port 2026'

# Or use browser Network tab (DevTools → WS filter)
```

---

**Status:** Ready to implement  
**Expected time:** 3 hours (Phase 1) + 5 hours (Phase 2 + testing)
