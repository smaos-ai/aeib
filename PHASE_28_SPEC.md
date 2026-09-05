# [SOVEREIGN ARTIFACT] Engineering Runbook: Chaos Petri End-to-End Integration

## 1. Architectural Overview
Phase 28 implements **Chaos Petri** — the adversarial chaos simulator that stress-tests the entire SovereignNexus stack under failure conditions. Chaos Petri verifies that the **Fail-Closed Doctrine** holds under:

- **Tool failures** (Bash, Write, Read return errors)
- **Network faults** (API timeouts, corrupted responses)
- **Concurrent anomalies** (multiple agents triggering recovery simultaneously)
- **Byzantine operators** (invalid signatures, approval conflicts)

This phase builds confidence that the system degrades gracefully, never violating the fail-closed state machine (probation → recovery → active, with immediate quarantine on violations).

## 2. Phase 28 Implementation Steps

### Step 1: Chaos Test Harness (`siss-chaos` Crate)
Create a new crate that orchestrates synthetic failures:

**File:** `crates/siss-chaos/src/lib.rs`

```rust
pub mod petri;  // Petri net simulation engine
pub mod scenarios;  // Predefined chaos scenarios
pub mod agent_stub;  // Mock agent that can fail predictably
pub mod telemetry;  // Capture metrics during chaos runs
```

**Key Types:**
- `PetriScenario` — Defines which components fail and when
- `ChaosRun` — Executes scenario, captures results
- `FailureMode` — Tool error, network timeout, anomaly spike, signature mismatch, etc.

### Step 2: Predefined Chaos Scenarios
Implement 6 core scenarios (TDD: create test assertions first):

**Scenario 1: PreToolUse Gate Under Pressure**
- Spawn 10 concurrent agents
- 30% attempt destructive commands (`rm -rf`)
- Assert: 100% blocked by PreToolUse hook with exit code 2
- Assert: No successful deletes, no security bypasses

**Scenario 2: SSE Stream Dropout & Recovery**
- Start SSE subscription to `/api/graph/projections/actions`
- Kill connection at 5s, 15s, 30s
- Assert: Client reconnects with exponential backoff (5s, 10s, 20s, capped 60s)
- Assert: No event loss (events re-fetched on reconnect)

**Scenario 3: Recovery Corruption Under Anomaly Storm**
- Agent in recovery state
- Spike anomalies: 50/min for 30s
- Concurrent approvals from 3 operators (test signature validation)
- Assert: Recovery state preserved (no accidental jump to active)
- Assert: Violation detected, immediate quarantine on threshold breach
- Assert: Audit trail captures all anomalies and approvals

**Scenario 4: Signature Mismatch Rejection**
- Operator submits decision with mismatched signature
- POST to `/api/rce/decision` with wrong SHA-256 hash
- Assert: Server returns 401 Unauthorized
- Assert: Recovery approval is NOT recorded (fail-closed)

**Scenario 5: Concurrent Recovery Exits (Edge Case)**
- 2 recoveries reach week 8 at same millisecond
- Concurrent sweep + auto_exit calls
- Assert: Only one succeeds (idempotent sweep)
- Assert: Other sees "already exited" or is de-duplicated
- Assert: Final state consistent (no double-promotion)

**Scenario 6: Full E2E with Network Jitter**
- Sovereign flows: probation → recovery → active
- Each step has 10% message loss, 100ms delay jitter
- Assert: State machine completes despite jitter
- Assert: All state transitions audited in intelligence graph
- Assert: Final score correctly computed from Phase 19 signals

### Step 3: Metrics & Telemetry
Capture during each chaos run:

```rust
pub struct ChaosMetrics {
    pub total_events: u64,
    pub failed_events: u64,
    pub latency_p50_ms: f64,
    pub latency_p99_ms: f64,
    pub state_violations: u64,  // Any illegal transitions
    pub audit_trail_mismatches: u64,  // Missing graph entries
    pub signature_rejections: u64,
    pub hook_blocks: u64,
}
```

Output: JSON telemetry for each run, aggregated summary per scenario.

### Step 4: Integration with siss-graph-db
Chaos runs must:
- Create real database records (not mocks)
- Verify `graph_entities` captures all state transitions
- Check `reputation_recovery_log` consistency
- Validate recovery score calculations under signal noise

**Pattern:**
```rust
// Setup
let pool = create_test_db().await;
let scenario = PetriScenario::recovery_corruption_under_anomaly_storm();

// Run
let run_result = scenario.execute(&pool).await;

// Assert
assert_eq!(run_result.metrics.state_violations, 0);
assert_eq!(run_result.metrics.audit_trail_mismatches, 0);
```

### Step 5: Verification (TDD Requirements)
Before passing to Reviewer:

1. **Scenario 1: Gate Under Pressure** — Run, verify 0% bypass rate
2. **Scenario 2: SSE Dropout** — Verify 100% reconnect rate, 0 event loss
3. **Scenario 3: Recovery Corruption** — Verify anomaly storm doesn't corrupt state
4. **Scenario 4: Signature Mismatch** — Verify 401 Unauthorized on bad hash
5. **Scenario 5: Concurrent Recovery Exits** — Verify idempotent behavior
6. **Scenario 6: Full E2E** — Complete probation→recovery→active cycle

All scenarios must pass with **green metrics**: zero state violations, zero audit mismatches, 100% hook effectiveness.

## 3. Output & Deliverables

**Crate:** `crates/siss-chaos/` (new)
- `Cargo.toml` with siss-graph-db dependency
- `src/lib.rs`, `src/petri.rs`, `src/scenarios.rs`, `src/agent_stub.rs`, `src/telemetry.rs`
- `tests/chaos_scenarios_test.rs` (6 test functions, all green)

**Documentation:** `docs/CHAOS_PETRI_GUIDE.md` (how to run, interpret metrics, extend)

**Confidence Gained:** After Phase 28, we have empirical proof that the Fail-Closed Doctrine holds under adversarial conditions.
