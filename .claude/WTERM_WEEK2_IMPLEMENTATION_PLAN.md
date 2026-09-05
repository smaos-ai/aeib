# wterm Week 2 Implementation Plan (June 4-11)

**Phase 1 Status:** COMPLETE (49 tests passing, committed)
**Phase 2 Goal:** TUI rendering, error recovery, field testing setup
**Field Gate:** June 18, 18:00 UTC

## Work Breakdown

### Goal 1: TUI Rendering (3 days, ~50 lines per file)

**File:** `crates/siss-console/src/tui/mod.rs`

#### TUI Components
```rust
pub struct TerminalUI {
    bridge: Arc<WsBridge>,
    agents: HashMap<String, AgentStatus>,
    selected_agent: Option<String>,
    scroll_offset: u16,
}

impl TerminalUI {
    // Render agent list with memory/task visualizations
    pub fn render_agents(&self) -> Vec<Line>;
    
    // Render selected agent detail panel
    pub fn render_detail(&self) -> Vec<Line>;
    
    // Handle keyboard input (up/down arrows, enter)
    pub async fn handle_input(&mut self, key: KeyEvent) -> Result<()>;
    
    // Update from broadcast channel
    pub async fn update_from_feed(&mut self, status: AgentStatus);
}

pub struct AgentVisualization {
    memory_bar: ProgressBar,
    task_indicator: TaskCount,
    status_badge: StatusBadge,
}
```

#### Tests (12+ tests)
- `test_tui_create` — creates TerminalUI with bridge
- `test_tui_render_empty` — renders when no agents connected
- `test_tui_render_single_agent` — renders single agent with memory bar
- `test_tui_render_multiple_agents` — renders list of agents
- `test_tui_select_agent` — highlight/select agent with arrow keys
- `test_tui_memory_bar_low` — memory bar shows low usage (green)
- `test_tui_memory_bar_high` — memory bar shows high usage (red)
- `test_tui_task_indicator_idle` — shows "0 tasks" badge
- `test_tui_task_indicator_running` — shows "N tasks active" badge
- `test_tui_status_badge_running` — renders running state
- `test_tui_status_badge_failed` — renders error state with message
- `test_tui_scroll_handling` — scrolls list when >N agents

#### Key Features
- Memory visualization: `[████████░░░░░░]  256MB / 512MB (50%)`
- Task counter: `3 tasks active` (or `idle`)
- Status badge: `[RUNNING]`, `[IDLE]`, `[FAILED: timeout]`
- Real-time updates: async broadcast from WsBridge
- Keyboard: Up/Down (navigate), Enter (detail), Q (quit)

---

### Goal 2: Error Recovery (2 days, ~80 lines)

**Files:**
- `crates/siss-console/src/recovery.rs` (reconnection logic)
- `crates/siss-console/src/state_sync.rs` (state recovery after reconnect)

#### Reconnection Logic
```rust
pub struct ReconnectionManager {
    max_retries: u32,
    initial_backoff_ms: u64,
    max_backoff_ms: u64,
    attempt: u32,
}

impl ReconnectionManager {
    pub async fn reconnect(&mut self, bridge: &WsBridge) -> Result<()> {
        // Exponential backoff: 1s, 2s, 4s, 8s, max 60s
        // Attempt up to 10 times before fallback
    }
    
    pub fn should_fallback(&self) -> bool {
        // After 10 failed attempts, trigger USB fallback
    }
}
```

#### State Sync
```rust
pub struct StateSyncManager {
    bridge: Arc<WsBridge>,
    checkpoint: LastKnownState,
}

impl StateSyncManager {
    pub async fn sync_after_reconnect(&mut self) -> Result<()> {
        // 1. Fetch current agent list from feed
        // 2. Diff against checkpoint
        // 3. Request missing status updates
    }
}
```

#### Tests (8+ tests)
- `test_reconnection_first_attempt_immediate` — retries immediately
- `test_reconnection_exponential_backoff` — 1s, 2s, 4s pattern
- `test_reconnection_max_backoff_capped` — never exceeds 60s
- `test_reconnection_fallback_after_10_attempts` — triggers USB tunnel
- `test_state_sync_fetch_current_list` — gets all agents on reconnect
- `test_state_sync_diff_detection` — identifies missing agents
- `test_state_sync_request_updates` — asks for stale status
- `test_state_sync_idempotent` — safe to call multiple times

#### Trigger Conditions
- **Immediate Reconnect:** WS close, timeout (1s wait)
- **Exponential Backoff:** Network errors, no heartbeat for 10s
- **USB Fallback:** 10 failed attempts OR manual user override

---

### Goal 3: Field Testing Script (2 days, ~200 lines)

**File:** `crates/siss-console/src/bin/field_test.rs`

#### Test Scenarios
```rust
pub enum TestScenario {
    Stable4Hours,                // No disconnections
    NetworkPartition10s,         // Drop connection 10s, reconnect
    Latency300ms,               // Add 300ms latency
    Bandwidth100kbps,           // Throttle to 100kbps
    UsbFallback,                // Switch to USB tunnel mid-test
}

pub struct FieldTestRunner {
    scenarios: Vec<TestScenario>,
    metrics: Metrics,
}

impl FieldTestRunner {
    pub async fn run(&mut self) -> TestReport;
}
```

#### Metrics Collected
```rust
pub struct Metrics {
    pub uptime_percentage: f64,
    pub avg_latency_ms: f64,
    pub peak_latency_ms: f64,
    pub disconnections: usize,
    pub reconnection_time_ms: u64,
    pub bandwidth_usage_mbs: f64,
    pub cpu_usage_percent: f64,
    pub memory_peak_mb: u32,
}
```

#### Test Execution
```bash
# Run 4-hour stability test
cargo run --release --bin field_test -- --scenario stable_4h --output report.json

# Network partition test (simulate 3G, 10s drops)
cargo run --release --bin field_test -- --scenario partition_10s --latency 100ms --bandwidth 100kbps

# USB fallback test
cargo run --release --bin field_test -- --scenario usb_fallback --duration 1h
```

#### Success Criteria (Gate Decision)
- [ ] Stable 4h: 99.5% uptime
- [ ] USB tethering: <2s reconnection time
- [ ] Screen reader: VoiceOver reads all status updates
- [ ] Bandwidth: <1 MB/min (3 status/sec × ~3KB/msg = 9KB/s < 1000KB/60s)
- [ ] Latency: <2s delay on USB (tested on iPhone 16 Pro)

---

### Goal 4: Documentation (1 day)

**Files:**
- `docs/wterm/CLI_USAGE.md` — command-line interface reference
- `docs/wterm/USB_SETUP.md` — iPhone/Android tethering guide
- `docs/wterm/DEPLOYMENT_CONFLICT_ZONES.md` — field deployment runbook

#### CLI Usage Example
```bash
# Connect to job-router WebSocket
wterm connect ws://localhost:9000

# Switch to USB tunnel
wterm usb --device /dev/ttyUSB0 --baudrate 115200

# Display agent list
wterm list

# Show agent detail
wterm detail alpha_001

# Export metrics
wterm export --format json > agents.json
```

#### USB Setup (iPhone 16 Pro)
1. Enable USB tethering in Settings > Personal Hotspot
2. Connect to macOS via Lightning cable
3. Run: `wterm usb --device /dev/tty.usbmodem* --baudrate 115200`
4. Status: `connected to alpha_001 (1.2 MB/s)`

---

## Timeline

```
June 4-5:   TUI rendering + 12 tests
June 6-7:   Error recovery + 8 tests
June 8-9:   Field testing script + metrics
June 10:    Documentation + edge case testing
June 11:    Integration testing, final fixes
June 12-17: Field validation (manual testing)
June 18:    Field gate decision (18:00 UTC)
```

## Deliverables Summary

**By June 11:**
- ✅ TUI rendering (ratatui-based)
- ✅ Reconnection logic (exponential backoff)
- ✅ State sync (diff-based recovery)
- ✅ Field testing script (4 scenarios)
- ✅ Metrics collection (8 KPIs)
- ✅ Documentation (3 guides)
- ✅ 30+ new tests
- ✅ All tests passing

**By June 18:**
- ✅ Manual field testing (4 hours stable)
- ✅ USB tethering validation (iPhone 16 Pro)
- ✅ Screen reader validation (VoiceOver)
- ✅ Bandwidth verification (<1 MB/min)
- ✅ Latency validation (<2s on USB)

**Decision Gate (June 18, 18:00 UTC):**
- If PASS: Proceed to 4-week hardening (June 18-July 16)
- If FAIL: Fallback to ttyd (same-day, no delay)

---

## File Ownership

**Phase 2 Deliverables:**
- `crates/siss-console/src/tui/` — TUI rendering
- `crates/siss-console/src/recovery.rs` — Reconnection logic
- `crates/siss-console/src/state_sync.rs` — State recovery
- `crates/siss-console/src/bin/field_test.rs` — Test runner
- `docs/wterm/` — 3 guide documents

**No changes to Phase 1:**
- `ws_bridge.rs` — finalized
- `usb_tunnel.rs` — finalized
- `types.rs` — finalized
- `a11y/screen_reader.rs` — finalized
- `siss-command-center/` — finalized

---

## Testing Checklist

Before June 11:
- [ ] All TUI tests passing (12+)
- [ ] All recovery tests passing (8+)
- [ ] Field test scenarios runnable
- [ ] Metrics collection working
- [ ] No new clippy warnings
- [ ] cargo test -p siss-console passes
- [ ] Integration test: WsBridge → TUI → USB

Before June 18:
- [ ] 4-hour stable test passes
- [ ] USB reconnect <2s
- [ ] VoiceOver reads all updates
- [ ] Bandwidth <1 MB/min
- [ ] Latency <2s on USB

---

**Status:** Ready for subagent parallel execution
**Next:** Subagent Dev assignments (TUI × 1, Recovery × 1, Testing × 1)
