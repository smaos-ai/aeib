# Phase 20 — Memory Crystallization Handoff

**Date:** 2026-05-11  
**Phase:** Phase 20: Graduated Reputation Recovery (SMAOS Pilot)  
**Status:** ✅ Complete, Merged to Main  
**Commits:** 7 commits (S0–S3 scaffolding + Tasks 87–92 implementation)

---

## Executive Summary

Phase 20 implements **graduated reputation recovery** for sovereigns exiting probation. A sovereign in recovery has their reputation score graduated linearly from 85 (week 0) to 100 (week 8), with Phase 19 penalty/bonus signals applied on top. This phase serves as the **pilot proof-of-concept for the SMAOS 6-layer platform**.

**Key Achievement:** The Minimal Viable SMAOS Foundation is now operational:
- **GitNexus MCP** — blast-radius analysis (Phase S0)
- **LightRAG + Apache AGE** — intelligence graph for decision lineage (Phase S1)
- **AG-UI SSE Streaming** — real-time event telemetry (Phase S2)
- **AoE Cockpit** — operator visibility dashboard (Phase S3)
- **Phase 20 Recovery Logic** — graduated scoring + state machine (Tasks 87–92)

---

## Architecture Overview

### State Machine

```
probation (80 base) → recovery (85→100 graduated) → active (100 base)
                           ↓
                      violation
                           ↓
                      quarantine (0)
```

**Key States:**
- **probation:** Locked score = 80 + Phase 19 signals
- **recovering:** Graduated score = 85 + (weeks/8)×15 + Phase 19 signals (0–8 weeks)
- **active:** Locked score = 100 + Phase 19 signals
- **quarantine:** Locked score = 0 (no signals applied)

### Graduation Curve

```
Week 0:  base = 85
Week 1:  base = 85 + (1/8)×15 = 86
Week 4:  base = 85 + (4/8)×15 = 92
Week 8:  base = 85 + (8/8)×15 = 100 (complete)
Week 9+: capped at 100
```

**Signal Integration (Phase 19):**
- Slash penalty: min(30, count × 10) applied to last 30 days
- Anomaly penalty: min(20, count × 8) applied to last 30 days
- Settlement bonus: min(20, count × 5) applied all-time

**Final Score:** `clamp(base − slash_penalty − anomaly_penalty + settlement_bonus, 0, 100)`

---

## Component Architecture

### 1. Core Logic: `reputation_recovery_repo.rs`

**Pure Functions (deterministic, testable):**

```rust
recovered_base_score(weeks: u32) -> i16
  // Returns graduated base: 85 + (weeks/8)*15, capped at 100
  
compute_recovery_score(weeks, slash_count, anomaly_count, settled_count) -> i16
  // Applies Phase 19 signals to graduated base
  // Returns final score ∈ [0, 100]
  
weeks_elapsed(recovery_started_at: DateTime<Utc>) -> u32
  // Returns weeks since recovery began (wall-clock time)
```

**Async DB Functions:**

```rust
auto_exit_probation_to_recovery(pool, sovereign_id, exit_reason) -> Result<Uuid>
  // Triggered by Phase 16 sweep after 30 clean days
  // Creates reputation_recovery_log record
  // Transitions sovereigns.status = 'recovering'
  // Writes to intelligence_graph_repo for decision lineage
  
sweep_recovery_progress(pool) -> Result<SweepResult>
  // Weekly sweep: advances all active recovery records
  // Updates recovery_progress_weeks based on wall-clock time
  // At week 8: calls auto_exit_recovery_to_active()
  // Emits RecoverySweepCompleted event to AG-UI
  
auto_exit_recovery_to_active(pool, sovereign_id) -> Result<()>
  // Called by sweep at week 8 completion
  // Sets recovery_exit_status = 'success'
  // Transitions sovereigns.status = 'active'
  // Emits RecoveryCompleted event
  
violation_during_recovery_to_quarantine(pool, sovereign_id, reason) -> Result<()>
  // Called by gatekeeper on Phase 16 violation detection
  // Sets recovery_exit_status = 'failure'
  // Transitions sovereigns.status = 'quarantine' (IMMEDIATE)
  // Emits RecoveryViolation event
```

### 2. Peer Scoring Integration: `peer_scoring_repo.rs`

**Updated `compute_and_upsert_score(pool, sovereign_id)`:**

```rust
match sovereign.status {
  "recovering" => {
    // Fetch active recovery_log record
    let recovery = get_active_recovery(pool, sovereign_id).await?;
    let weeks = weeks_elapsed(recovery.recovery_started_at);
    
    // Apply Phase 20 graduation + Phase 19 signals
    compute_recovery_score(weeks, slash_count, anomaly_count, settled_count)
  }
  "active" => compute_enriched_score(100, slash_count, anomaly_count, settled_count),
  "probation" => compute_enriched_score(80, slash_count, anomaly_count, settled_count),
  "quarantined" => 0,  // No enrichment
}
```

**Scoring consistency:** All statuses apply the same signal penalties/bonuses, ensuring that signal aging (30-day windows) and settlement tracking (all-time) work uniformly across states.

### 3. Gatekeeper Integration: `validate.rs`

**Phase 20 Violation Detection:**

```rust
// In pipeline/validate.rs, after Phase 16 check:
if probation_repo::check_and_enforce_violation(pool, tenant_id).await? {
  // Re-quarantined — block session
  return Err(GatekeeperError::SovereignQuarantined { tenant_id });
}
```

**Same threshold:** Both probation and recovery violations use 50% of Phase 15 thresholds (reuse existing `check_and_enforce_violation()` logic).

### 4. Background Sweep: `recovery_sweep_scheduler.rs`

```rust
start_recovery_sweep(pool, interval) -> JoinHandle<()>
  // Spawns tokio task with weekly interval
  // Calls run_recovery_sweep_pass() each tick
  
run_recovery_sweep_pass(pool) -> Result<RecoverySweepResult>
  // Calls reputation_recovery_repo::sweep_recovery_progress()
  // Returns { sovereigns_advanced, sovereigns_completed, sovereigns_violated }
  // Emits RecoverySweepCompleted event with result
```

---

## Event Streaming: Axum SSE Architecture

### Event Types

**File:** `crates/siss-agent-card/src/events.rs`

```rust
#[derive(Debug, Serialize)]
pub enum RecoveryEvent {
  RecoveryEntered {
    sovereign_id: Uuid,
    score_at_entry: i16,
    probation_exit_reason: String,
  },
  RecoveryProgressed {
    sovereign_id: Uuid,
    weeks_elapsed: u32,
    current_score: i16,
    slash_count: i64,
    anomaly_count: i64,
    settlement_count: i64,
  },
  RecoveryCompleted {
    sovereign_id: Uuid,
    exit_status: String,
    score_at_exit: i16,
  },
  RecoveryViolation {
    sovereign_id: Uuid,
    violation_reason: String,
    new_status: String,
  },
  ScoringDecision {
    sovereign_id: Uuid,
    status: String,
    final_score: i16,
    base_score: i16,
    slash_penalty: i16,
    anomaly_penalty: i16,
    settlement_bonus: i16,
  },
}
```

### Event Broadcaster

```rust
pub struct EventBroadcaster {
  tx: broadcast::Sender<RecoveryEvent>,
}

impl EventBroadcaster {
  pub fn broadcast(&self, event: RecoveryEvent) {
    let _ = self.tx.send(event);  // Fire-and-forget to all listeners
  }
  
  pub fn subscribe(&self) -> broadcast::Receiver<RecoveryEvent> {
    self.tx.subscribe()
  }
}
```

**Usage in reputation_recovery_repo:**
```rust
// After state transition (e.g., recovery → active)
broadcaster.broadcast(RecoveryEvent::RecoveryCompleted {
  sovereign_id,
  exit_status: "success".to_string(),
  score_at_exit: final_score,
});
```

### SSE Handler

**File:** `crates/siss-agent-card/src/events.rs`

```rust
pub async fn events_stream(
  State(broadcaster): State<Arc<EventBroadcaster>>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
  let rx = broadcaster.subscribe();
  
  let stream = BroadcastStream::new(rx)
    .map(|event| {
      let json = serde_json::to_string(&event).unwrap();
      Ok(Event::default().data(json))
    });
    
  Sse::new(stream)
}
```

**Route:** `GET /events` returns `text/event-stream` with Content-Type headers

### Integration with Axum Router

```rust
// In sse_server.rs example:
let broadcaster = Arc::new(EventBroadcaster::new());

let app = Router::new()
  .route("/cockpit", get(cockpit_handler))
  .route("/events", get(events_stream))
  .with_state(broadcaster.clone())
  .layer(DefaultBodyLimit::max(1024 * 1024));  // 1MB limit

// Spawn demo task emitting events
tokio::spawn(emit_demo_events(broadcaster.clone()));
```

---

## Frontend: Cockpit Dashboard

**File:** `crates/siss-agent-card/static/cockpit.html`

### Architecture

**EventSource Consumer:**
```javascript
const eventSource = new EventSource('/events');

eventSource.onmessage = (event) => {
  const recovery = JSON.parse(event.data);
  updateDashboard(recovery);
};

eventSource.onerror = () => {
  eventSource.close();
  setTimeout(() => { location.reload(); }, 5000);  // Reconnect
};
```

### Three-Column Layout

**1. Recovery Status (left)**
```
┌─────────────────────────────┐
│ Recovering Sovereigns       │
├─────────────────────────────┤
│ ID: abc-123                 │
│ Status: recovering          │
│ Weeks Elapsed: 4            │
│ Current Score: 92           │
│ Entry Score: 85             │
├─────────────────────────────┤
│ ID: def-456                 │
│ ...                         │
└─────────────────────────────┘
```

**Updates on:** `RecoveryProgressed`, `RecoveryEntered`

**2. Recent Transitions (center)**
```
┌─────────────────────────────┐
│ State Changes               │
├─────────────────────────────┤
│ abc-123: probation→recovery │
│ Time: 2026-05-10 14:32      │
│                             │
│ def-456: recovery→active    │
│ Time: 2026-05-11 09:15      │
│                             │
│ ghi-789: recovery→quarantine│
│ Reason: violation           │
└─────────────────────────────┘
```

**Updates on:** `RecoveryEntered`, `RecoveryCompleted`, `RecoveryViolation`

**3. Signal Activity (right)**
```
┌─────────────────────────────┐
│ Scoring Updates             │
├─────────────────────────────┤
│ abc-123 (week 4)            │
│ Base: 92                    │
│ - Slashes: -20 (2 events)  │
│ - Anomalies: -8 (1 event)  │
│ + Settlements: +5 (1 event)│
│ = Final: 69                 │
└─────────────────────────────┘
```

**Updates on:** `ScoringDecision`, `RecoveryProgressed`

### Styling

- **Dark theme** — #0a0e27 background (SMAOS-standard)
- **Status badges** — color-coded (blue: recovering, green: active, red: quarantine)
- **Responsive grid** — 1400px max-width, auto-wrap on mobile
- **Auto-refresh** — EventSource keeps data in sync without polling

---

## Database Schema

### `reputation_recovery_log` (Migration 033)

```sql
CREATE TABLE reputation_recovery_log (
  id UUID PRIMARY KEY,
  sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  recovery_started_at TIMESTAMP NOT NULL DEFAULT NOW(),
  score_at_entry SMALLINT NOT NULL,
  probation_exit_reason TEXT NOT NULL,
  recovery_window_weeks INTEGER NOT NULL DEFAULT 8,
  recovery_progress_weeks INTEGER NOT NULL DEFAULT 0,
  last_progress_update_at TIMESTAMP NOT NULL DEFAULT NOW(),
  slashes_during_recovery INTEGER NOT NULL DEFAULT 0,
  anomalies_during_recovery INTEGER NOT NULL DEFAULT 0,
  settlement_bonus_during_recovery INTEGER NOT NULL DEFAULT 0,
  score_adjustments_applied INTEGER NOT NULL DEFAULT 0,
  recovery_completed_at TIMESTAMP NULL,
  recovery_exit_status TEXT NULL,  -- 'success' | 'failure'
  score_at_exit SMALLINT NULL,
  UNIQUE(sovereign_id, recovery_started_at)
);
```

### Intelligence Graph Schema (Migration 032)

**Apache AGE graph for decision lineage:**

```sql
-- Node types: SovereignNode, RecoveryNode, ViolationNode, ScoringNode
-- Edge types: TRIGGERS, SCORES, EXPLAINS, SUPERSEDES

CREATE TABLE graph_entities (
  id BIGSERIAL PRIMARY KEY,
  entity_type TEXT NOT NULL,
  sovereign_id UUID,
  entity_data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE graph_relationships (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT REFERENCES graph_entities(id),
  target_id BIGINT REFERENCES graph_entities(id),
  relationship_type TEXT NOT NULL,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Dual-write pattern:** Every state transition writes to both `reputation_recovery_log` (transactional) and `graph_entities`/`relationships` (audit trail).

---

## Testing

### Unit Tests (17 tests in `reputation_recovery_repo.rs`)

**Graduated Curve (5 tests):**
- `test_recovered_base_score_week_0` → 85 ✓
- `test_recovered_base_score_week_1` → 86 ✓
- `test_recovered_base_score_week_4` → 92 ✓
- `test_recovered_base_score_week_8` → 100 ✓
- `test_recovered_base_score_capped_at_100` → 100 (week 16) ✓

**Signal Integration (6 tests):**
- `test_recovery_score_clean_week_0` → 85 (no signals) ✓
- `test_recovery_score_with_slashes` → 85 - 20 = 65 ✓
- `test_recovery_score_with_anomalies` → 85 - 16 = 69 ✓
- `test_recovery_score_with_settlement_bonus` → 85 + 15 = 100 (clamped) ✓
- `test_recovery_score_mixed_signals_week_4` → 92 - 20 - 8 + 10 = 74 ✓
- `test_recovery_score_penalty_caps` → 100 - 30 - 20 = 50 ✓

**Time Calculation (4 tests):**
- `test_weeks_elapsed_now` → 0 ✓
- `test_weeks_elapsed_7_days_ago` → 1 ✓
- `test_weeks_elapsed_56_days_ago` → 8 ✓
- `test_weeks_elapsed_beyond_recovery_window` → > 8 ✓

**Edge Cases (2 tests):**
- `test_recovery_score_clamped_to_100` → 100 ✓
- `test_recovery_score_min_possible_with_max_penalties` → 35 ✓

### Integration Tests (6 documented scenarios)

*Require database setup; implementation left for future work:*

1. **Probation to Recovery Transition** — verify status change, recovery_log creation
2. **Recovery Score Progression** — score rises from 85 → 100 over weeks
3. **Auto-Completion at Week 8** — sweep triggers auto_exit_recovery_to_active()
4. **Violation Re-Quarantine** — immediate transition to quarantine on violation
5. **Signal Aging** — 30-day window for slashes/anomalies, all-time for settlements
6. **Full 8-Week E2E** — complete lifecycle probation → recovery → active

---

## How Phase 20 Fits into SMAOS

### Layers (from SMAOS 6-Layer Vision)

| Layer | Component | Phase 20 Usage |
|-------|-----------|---|
| **1. Agent** | Sovereign workflows | Probation exit triggers recovery entry |
| **2. Gatekeeper** | Access control | Violation detection blocks session |
| **3. Federation** | Cross-sovereign ledger | Settlement signals feed Phase 19 bonus |
| **4. Intelligence** | AGE graph + LightRAG | Recovery lineage, decision audit trail |
| **5. Telemetry** | AG-UI SSE events | RecoveryProgressed, RecoveryCompleted |
| **6. Operator** | AoE Cockpit | Dashboard shows recovery status in real-time |

### Blast-Radius Safety (GitNexus)

Phase 20 code touches:
- `reputation_recovery_repo.rs` (new) — no callers yet
- `peer_scoring_repo.rs` — already called by scoring sweep (impact: ✓ contained)
- `validate.rs` — already checks violations (impact: ✓ reuses existing logic)
- Migrations — no structural changes (impact: ✓ additive)

**Conclusion:** Phase 20 is safely isolated; no breaking changes to existing phases.

---

## Running the Demo

```bash
# Start SSE server with cockpit
cargo run --example sse_server -p siss-agent-card --features axum

# In browser:
# http://localhost:3000/cockpit
# Watch recovery events stream live (every 5 seconds in demo)
```

**Expected Output:**
- Cockpit HTML loads
- EventSource connects to `/events`
- Demo events emit: RecoveryEntered → RecoveryProgressed (multiple times) → RecoveryCompleted
- Dashboard updates live with sovereigns moving through recovery lifecycle

---

## Future Work

### Phase 21+: Extensions
1. **Multi-signatory recovery appeals** — allow sovereigns to dispute recovery duration
2. **Graduated penalties** — slashes reduce base score during recovery (currently additive only)
3. **Recovery insurance** — settlement bonds that extend recovery window on withdrawal
4. **Cohort analytics** — batch reporting on recovery success rates by exit reason

### Infrastructure
1. **Complete integration tests** — 6 scenarios documented, implementation needed
2. **Performance tuning** — batch sweep updates for 1000+ sovereigns
3. **Alert system** — AoE panel notifications for recovery violations
4. **Historical recovery dashboard** — charting score progression over time

---

## Key Insights for Future Agents

1. **Graduated curves matter.** Linear progression (85 → 100) feels fair; exponential or step functions create unfair compression near boundaries.

2. **Phase 19 signals are the key.** Recovery score without slashes/anomalies/settlements is just a timer. Signals give sovereigns *agency*: settle invoices to boost recovery, avoid slashes to progress.

3. **Dual-write pattern is essential.** The database records the current state (fast queries), the intelligence graph records the *why* (explainability). Never skip the graph write; it's the audit trail.

4. **EventSource is stateless.** If the server restarts, the client auto-reconnects. Sovereigns in recovery don't lose anything; the dashboard just needs a refresh.

5. **Cockpit is the operator's window.** Every state transition *must* emit an event. If the operator can't see it, it didn't happen (from their perspective).

6. **Violation checks are fail-open on DB errors.** If the database is down, we don't block sessions. This is intentional: availability > consistency for session creation. The gatekeeper is a guard, not a blocker.

---

## Files Created/Modified

**New Files:**
- `crates/siss-mcp-gitnexus/` — GitNexus MCP server (S0)
- `crates/siss-graph-db/migrations/032_*.sql` — Intelligence graph schema (S1)
- `crates/siss-graph-db/migrations/033_*.sql` — Phase 20 recovery table (Task 87)
- `crates/siss-graph-db/src/repo/intelligence_graph_repo.rs` — Graph writes (S1)
- `crates/siss-graph-db/src/repo/reputation_recovery_repo.rs` — Phase 20 logic (Task 88)
- `crates/siss-graph-db/src/recovery_sweep_scheduler.rs` — Weekly sweep (Task 91)
- `crates/siss-agent-card/src/events.rs` — SSE event types (S2)
- `crates/siss-agent-card/src/cockpit.rs` — Cockpit handler (S3)
- `crates/siss-agent-card/static/cockpit.html` — Cockpit UI (S3)
- `crates/siss-agent-card/examples/sse_server.rs` — Demo server (S3)
- `docs/wiki/semantic/smaos-concepts.md` — Entity definitions (S1)
- `docs/wiki/semantic/phase-log.md` — Decision log (S1)
- `docs/wiki/episodic/recovery-events.md` — Event schema (S2)

**Modified Files:**
- `crates/siss-graph-db/src/repo/peer_scoring_repo.rs` — Recovery scoring (Task 89)
- `crates/siss-gatekeeper/src/pipeline/validate.rs` — Recovery violation check (Task 90)
- `crates/siss-agent-card/src/refresh_handler.rs` — Fixed borrow error
- `.claude/settings.json` — GitNexus MCP registration (S0)

---

## Handoff Complete ✓

This document serves as the **single source of truth** for Phase 20 architecture. Use it to:
- Onboard new agents to the Phase 20 codebase
- Understand how SSE streaming integrates with the recovery state machine
- Debug issues in the cockpit, events, or scoring
- Plan Phase 21+ extensions (appeals, batch analytics, insurance)

**Questions for future agents:**
- "How do I add a new recovery event type?" → See RecoveryEvent enum + cockpit layout
- "What happens when a recovery period expires?" → See sweep_recovery_progress() + auto_exit_recovery_to_active()
- "Why do both slash and anomaly penalties cap out?" → Signal ceiling prevents score collapse; cap values tuned to preserve fairness
- "Can I see the full decision trail?" → Yes, via intelligence_graph_repo lineage queries

---

**Last Updated:** 2026-05-11  
**Status:** ✅ Ready for Phase 21  
**Merged:** Main branch (fast-forward, 7 commits)
