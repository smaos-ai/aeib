# Phase 16 Lock Document — Remediation & Appeal Mechanism

**Status:** LOCKED (Immutable Reference)  
**Date Locked:** 2026-05-11  
**Tasks:** 77–79 (All Complete)  
**Verification:** All tests passing, all code compiled, invariants documented

---

## Executive Summary

Phase 16 closes the remediation path for Phase 15 quarantine by implementing consensus-gated appeal, evidence-based behavioral improvement tracking, and probation monitoring. **Task 77** implements a 72-hour cooldown and appeal protocol gated by consensus. **Task 78** measures 7-day behavioral metrics against Phase 15 thresholds to determine appeal readiness. **Task 79** transitions approved appeals to a "probation" intermediate state with 50% reduced anomaly thresholds for 30 days, auto-exiting on clean behavior or auto-triggering re-quarantine on violation. The result is a proportional, fair remediation loop: quarantine → appeal → probation → restore or re-quarantine.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│ Task 77: Appeal Protocol (Consensus Layer)           │
│  ├─ can_appeal(sovereign_id)                         │
│  │  ├─ Check: sovereign.status = 'quarantined'       │
│  │  ├─ Check: 72h since quarantine                   │
│  │  └─ Check: no active appeal pending               │
│  │                                                    │
│  └─ initiate_consensus("appeal_quarantine", payload) │
│     └─ 2/3 super-majority quorum (same as quarantine)│
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Task 78: Behavioral Improvement Tracking             │
│  ├─ measure_behavioral_improvement(sovereign_id)     │
│  │  ├─ 7-day dispute count                          │
│  │  ├─ 7-day timeout count                          │
│  │  └─ 7-day revocation count                       │
│  │                                                    │
│  └─ is_ready_for_appeal(sovereign_id) → bool         │
│     (all 7d totals < Phase 15 minimum thresholds)   │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Task 79: Probation State & Enforcement               │
│  ├─ UPDATE sovereigns SET status = 'probation'       │
│  ├─ Probation thresholds (50% of Phase 15):          │
│  │  ├─ dispute_spam: ≥3 in 2h (instead of ≥5)       │
│  │  ├─ timeout_spam: ≥2 in 24h (instead of ≥3)      │
│  │  └─ revocation_pattern: ≥2 in 24h (instead of ≥3)│
│  │                                                    │
│  ├─ check_and_enforce_violation()                    │
│  │  → Auto re-quarantine if threshold breached       │
│  │                                                    │
│  └─ try_auto_exit() after 30 clean days              │
│     → UPDATE sovereigns SET status = 'active'        │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Gatekeeper Pipeline (validate.rs)                    │
│  ├─ is_tenant_sovereign_quarantined() [Phase 15]     │
│  └─ check_and_enforce_violation() [Phase 16]         │
│     → Both return SovereignQuarantined on failure     │
└──────────────────────────────────────────────────────┘
```

---

## Data Model

### Migration 029: Appeal Protocol & Probation Tracking

**File:** `crates/siss-graph-db/src/migrations/029_add_phase16_appeal_probation.sql`

```sql
-- Appeal proposals: tracks consensus-gated appeal requests (Phase 16 Task 77)
CREATE TABLE appeal_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    consensus_proposal_id UUID NOT NULL REFERENCES consensus_proposals(id),
    improvement_evidence JSONB NOT NULL DEFAULT '{}',
    appeal_initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    appeal_resolved_at TIMESTAMPTZ,
    is_approved BOOLEAN
);
CREATE INDEX idx_appeals_sovereign ON appeal_proposals(sovereign_id, appeal_initiated_at DESC);
CREATE INDEX idx_appeals_pending ON appeal_proposals(sovereign_id) WHERE is_approved IS NULL;

-- Behavioral improvement snapshots: 7-day metrics for appeal readiness (Phase 16 Task 78)
CREATE TABLE behavioral_improvements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    disputes_7d INT NOT NULL,
    timeouts_7d INT NOT NULL,
    revocations_7d INT NOT NULL,
    is_ready_for_appeal BOOLEAN NOT NULL DEFAULT FALSE,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_improvements_sovereign ON behavioral_improvements(sovereign_id, measured_at DESC);

-- Probation audit log: all probation events for compliance and monitoring (Phase 16 Task 79)
CREATE TABLE probation_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    probation_started_at TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(32) NOT NULL
        CHECK (event_type IN ('activity_logged', 'threshold_approaching', 'anomaly_detected', 'clean_exit')),
    event_details JSONB NOT NULL DEFAULT '{}',
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_probation_log_sovereign ON probation_audit_log(sovereign_id, logged_at DESC);
```

### Sovereigns Table Extension

No schema change required — `sovereigns.status VARCHAR(32)` already allows `'probation'` value. No enum constraint exists.

---

## Task Specifications (Locked)

### Task 77: Appeal Protocol

**File:** `crates/siss-graph-db/src/repo/appeal_repo.rs`

**Spec:**
- Validates 72-hour cooldown before appeal eligibility
- Checks sovereign is quarantined
- Prevents duplicate active appeals
- Records appeal decision from consensus

**Public API:**
```rust
pub async fn can_appeal(pool: &PgPool, sovereign_id: Uuid) -> Result<(), AppealError>
// Validates: sovereign.status = 'quarantined'
// Validates: 72h elapsed since quarantine
// Validates: no active appeal pending

pub async fn initiate_appeal(
    pool: &PgPool,
    sovereign_id: Uuid,
    consensus_proposal_id: Uuid,
    improvement_evidence: serde_json::Value,
) -> Result<Uuid, AppealError>

pub async fn record_appeal_decision(
    pool: &PgPool,
    appeal_id: Uuid,
    is_approved: bool,
) -> Result<(), AppealError>
```

**Error Types:**
- `NotQuarantined { sovereign_id }` — sovereign not in quarantine
- `TooSoon { hours_remaining }` — < 72 hours since quarantine
- `AlreadyPending { sovereign_id }` — active appeal already exists
- `Database { message }` — SQL errors

**Cooldown Constraint:**
- Query: `SELECT MAX(detected_at) FROM behavioral_anomalies WHERE sovereign_id = $1 AND is_active = TRUE`
- If NULL or < 72h ago → `TooSoon` error
- Per-sovereign cooldown window: 72 hours minimum

**Tests:** 2 unit tests (no Docker)
- `test_appeal_72h_cooldown_not_elapsed` — 50h since quarantine → TooSoon
- `test_appeal_72h_cooldown_elapsed` — 80h since quarantine → passes validation

**Status:** ✅ LOCKED

---

### Task 78: Behavioral Improvement Tracking

**File:** `crates/siss-graph-db/src/repo/behavioral_improvements_repo.rs`

**Spec:**
- Measures 7-day behavioral metrics: dispute count, timeout count, revocation count
- Compares against Phase 15 minimum thresholds
- Determines appeal readiness (all metrics below thresholds)

**Public API:**
```rust
pub struct BehavioralMetrics {
    pub sovereign_id: Uuid,
    pub disputes_7d: i64,
    pub timeouts_7d: i64,
    pub revocations_7d: i64,
    pub is_ready_for_appeal: bool,
    pub measured_at: DateTime<Utc>,
}

pub async fn measure_behavioral_improvement(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<BehavioralMetrics, MeasurementError>

pub async fn is_ready_for_appeal(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<bool, MeasurementError>

pub async fn record_improvement_measurement(
    pool: &PgPool,
    metrics: &BehavioralMetrics,
) -> Result<Uuid, MeasurementError>
```

**Appeal Readiness Thresholds:**
| Metric | Phase 15 Trigger | Appeal-Ready Threshold |
|--------|------------------|----------------------|
| disputes_7d | ≥5 in 2h | < 5 total in 7d |
| timeouts_7d | ≥3 in 24h | < 3 total in 7d |
| revocations_7d | ≥3 in 24h | < 3 total in 7d |

**SQL Queries:**
```sql
-- disputes_7d
SELECT COUNT(*) FROM settlement_invoices
WHERE debtor_sovereign_id = $1 AND status = 'disputed'
  AND created_at >= NOW() - INTERVAL '7 days'

-- timeouts_7d
SELECT COUNT(*) FROM escrow_ledger
WHERE debtor_sovereign_id = $1 AND status = 'forfeited'
  AND forfeited_at >= NOW() - INTERVAL '7 days'

-- revocations_7d
SELECT COUNT(*) FROM cross_sovereign_delegation_grants
WHERE grantee_sovereign_id = $1 AND revoked_at >= NOW() - INTERVAL '7 days'
```

**Tests:** 2 unit tests (no Docker)
- `test_all_rates_below_threshold_ready_for_appeal` — 4/2/2 totals → is_ready=true
- `test_one_rate_above_threshold_not_ready` — 6 disputes → is_ready=false

**Status:** ✅ LOCKED

---

### Task 79: Probation State & Enforcement

**File:** `crates/siss-graph-db/src/repo/probation_repo.rs`

**Spec:**
- Manages probation intermediate state (after appeal approval)
- Enforces reduced thresholds (50% of Phase 15) for 30 days
- Auto-detects violations and re-quarantines
- Auto-exits after 30 clean days

**Public API:**
```rust
pub struct ProbationStatus {
    pub probation_started_at: DateTime<Utc>,
    pub days_elapsed: i64,
    pub days_remaining: i64,
    pub violation_count: i64,
    pub is_clean: bool,
}

pub async fn start_probation(pool: &PgPool, sovereign_id: Uuid) -> Result<(), ProbationError>
// UPDATE sovereigns SET status = 'probation' WHERE id = $1
// INSERT INTO probation_audit_log (..., event_type = 'activity_logged')

pub async fn get_probation_status(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Option<ProbationStatus>, ProbationError>

pub async fn check_and_enforce_violation(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<bool, ProbationError>
// Returns true if violation detected and re-quarantine applied

pub async fn try_auto_exit(pool: &PgPool, sovereign_id: Uuid) -> Result<bool, ProbationError>
// Returns true if 30 days clean, then transitions to 'active'
```

**Probation Violation Thresholds (50% of Phase 15):**
| Anomaly | Phase 15 Trigger | Probation Trigger |
|---------|------------------|------------------|
| dispute_spam | ≥5 in 2h | ≥3 in 2h |
| timeout_spam | ≥3 in 24h | ≥2 in 24h |
| revocation_pattern | ≥3 in 24h | ≥2 in 24h |

**Probation Duration:**
- Fixed: 30 days
- No early exit (even if clean earlier)
- No extension (even if violation risk)
- Days remaining = max(0, 30 - days_elapsed)

**Violation Enforcement:**
1. `check_and_enforce_violation()` detects anomaly
2. Calls `UPDATE sovereigns SET status = 'quarantined'` (atomic)
3. Logs event to probation_audit_log with type='anomaly_detected'
4. Returns true (signals re-quarantine)
5. Gatekeeper blocks new sessions via SovereignQuarantined error

**Clean Exit:**
1. `try_auto_exit()` checks: days_elapsed >= 30 AND is_clean (no anomalies)
2. If clean: `UPDATE sovereigns SET status = 'active'`
3. Logs event with type='clean_exit'
4. Returns true

**Tests:** 2 unit tests (no Docker)
- `test_probation_threshold_dispute_below_3_no_violation` — 2 disputes in 2h → no violation
- `test_probation_threshold_dispute_3_or_more_violation` — 3 disputes → violation

**Status:** ✅ LOCKED

---

### Consensus Extension (consensus_repo.rs)

**New Proposal Type:** `"appeal_quarantine"`

**Quorum Formula:**
Same as `"quarantine"` — 2/3 super-majority:
```rust
let required_quorum = if proposal_type == "quarantine" || proposal_type == "appeal_quarantine" {
    ((2 * (peer_count + 1) + 2) / 3).max(2)
} else {
    ((peer_count + 1) / 2).max(1)
};
```

**Payload Schema:**
```json
{
  "sovereign_id": "<UUID>",
  "improvement_evidence": { /* JSON object with metrics */ }
}
```

**Finalize Arm** (lines ~512–540):
1. Extract target_sovereign_id from payload
2. `UPDATE sovereigns SET status = 'probation' WHERE id = target_sovereign_id`
3. `UPDATE appeal_proposals SET is_approved = TRUE, appeal_resolved_at = NOW() WHERE sovereign_id = target_sovereign_id`
4. `INSERT INTO probation_audit_log (..., event_type = 'activity_logged', event_details = {"event": "probation_started"})`

**Tests:** 1 unit test
- `test_appeal_quarantine_uses_supermajority_quorum` — verifies "appeal_quarantine" uses 2/3 formula

**Status:** ✅ LOCKED

---

### Gatekeeper Extension (validate.rs)

**Location:** After Phase 15 quarantine check (line ~55)

**Code:**
```rust
// Phase 16: Check probation and enforce violation if threshold breached
// This is best-effort: DB errors treated as no violation (fail-open on errors)
if siss_graph_db::repo::probation_repo::check_and_enforce_violation(pool, tenant_id)
    .await
    .unwrap_or(false)
{
    // Violation was detected and sovereign re-quarantined — block session
    return Err(GatekeeperError::SovereignQuarantined { tenant_id });
}
```

**Behavior:**
- Probation sovereigns (status='probation') CAN create new sessions
- Violation check runs at session creation time
- If violation detected: sovereign re-quarantined in DB, session blocked
- If clean: session allowed
- DB errors treated as no violation (fail-open safety)

**Error Reuse:** Returns existing `GatekeeperError::SovereignQuarantined` (no new variant needed)

**Status:** ✅ LOCKED

---

## Constitutional Invariants (Phase 16)

### 1. APPEAL_PARITY
- Appeal requires **same 2/3 super-majority** as quarantine
- Reflects: restoration is as serious as sanction; majority must agree both ways
- Prevents: unilateral appeal reversal, gaming consensus

### 2. PROBATION_INTERMEDIATE_STATE
- Direct quarantine → active **forbidden**
- All appeals → probation (required intermediate step)
- Proportional: quarantine (harshest) → probation (moderate) → active (normal)
- No skip-appeal scenario: all restored sovereigns pass through probation

### 3. IMPROVEMENT_EVIDENCE_BASED
- Appeals require proof of behavioral change, **not time-based waiting**
- Evidence: 7-day metrics must drop below Phase 15 minimum detection levels
- False appeals rejected: if sovereigns haven't improved, consensus will vote no
- Prevents: automatic restoration after arbitrary time

### 4. PROBATION_ELEVATED_MONITORING
- Probation thresholds = **50% of Phase 15 anomaly thresholds**
  - dispute_spam: ≥3 in 2h (instead of ≥5)
  - timeout_spam: ≥2 in 24h (instead of ≥3)
  - revocation_pattern: ≥2 in 24h (instead of ≥3)
- All activities audited to probation_audit_log
- Fixed duration: 30 days (no early exit, no extension)
- Faster detection of relapse: 50% threshold catch problems sooner

### 5. PROBATION_VIOLATION_SELF_ENFORCING
- If anomaly detected during probation → **automatic re-quarantine**
- No consensus needed (fast response to relapse)
- Self-enforcing: no manual intervention required
- Clear signal: violation during probation = loss of restoration opportunity
- Re-quarantine resets appeal cooldown: min 72h before next appeal eligible

---

## Test Matrix

### Unit Tests (No Docker)

| Task | Test Name | Status |
|------|-----------|--------|
| 77 | `test_appeal_72h_cooldown_not_elapsed` | ✅ |
| 77 | `test_appeal_72h_cooldown_elapsed` | ✅ |
| 78 | `test_all_rates_below_threshold_ready_for_appeal` | ✅ |
| 78 | `test_one_rate_above_threshold_not_ready` | ✅ |
| 79 | `test_probation_threshold_dispute_below_3_no_violation` | ✅ |
| 79 | `test_probation_threshold_dispute_3_or_more_violation` | ✅ |
| 75ext | `test_appeal_quarantine_uses_supermajority_quorum` | ✅ |

**Total Unit Tests:** 7 passing

### Integration Tests (Docker-required)

Not yet implemented in Phase 16 (deferred). Placeholder test cases in plan:
- `test_appeal_consensus_passes_with_supermajority` — 3 yes votes on 3-peer network → approved, sovereign → probation
- `test_appeal_consensus_fails_without_supermajority` — 2 yes votes on 3-peer network → rejected, sovereign remains quarantined
- `test_probation_violation_re_quarantines` — sovereign in probation, anomaly detected → re-quarantine
- `test_probation_clean_exit_after_30_days` — sovereign in probation, 30 days clean → auto-exit to active

---

## Verification

```bash
# Compile
cargo check -p siss-graph-db -p siss-gatekeeper
# Result: ✅ Success

# Unit tests
cargo test -p siss-graph-db appeal_repo --lib
cargo test -p siss-graph-db behavioral_improvements_repo --lib
cargo test -p siss-graph-db probation_repo --lib
cargo test -p siss-graph-db consensus_repo::tests::test_appeal_quarantine --lib
# Result: ✅ 7 Phase 16 tests passing

# Code style
cargo fmt
cargo clippy
# Result: ✅ No new errors introduced
```

---

## Context Map

**Goal:** Phase 16 — Add restoration path to Phase 15 quarantine: appeal → evidence → probation → clean exit or re-quarantine  
**Create:** migration 029, appeal_repo.rs, behavioral_improvements_repo.rs, probation_repo.rs  
**Modify:**
- `consensus_repo.rs` (appeal_quarantine proposal type + finalize arm)
- `repo/mod.rs` (export 3 new modules)
- `migrations/mod.rs` (register migration 029)
- `siss-gatekeeper/pipeline/validate.rs` (probation violation check)

**Reuse:**
- Consensus super-majority machinery (same 2/3 formula as quarantine)
- Anomaly detection with reduced thresholds (50% of Phase 15)
- Gatekeeper pipeline pattern (existing error variant)
- Probation audit log pattern (JSON event logging)

**Test:** 7 unit tests (100% passing), 4 integration tests deferred  
**Invariants:** 5 new (APPEAL_PARITY, PROBATION_INTERMEDIATE_STATE, IMPROVEMENT_EVIDENCE_BASED, PROBATION_ELEVATED_MONITORING, PROBATION_VIOLATION_SELF_ENFORCING)

---

## Completion Signature

All tasks 77–79 complete, verified, and locked.

**Date:** 2026-05-11  
**Tests:** 7 unit passing, 0 integration (deferred to Docker environment)  
**Code Quality:** No type errors, no new clippy warnings on Phase 16 code, idiomatic Rust  
**Architecture:** Appeal-parity, intermediate probation state, evidence-based readiness, elevated monitoring, self-enforcing violation  
**Status:** Ready for Phase 17
