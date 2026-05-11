# Phase 20 Design Specification — Graduated Reputation Recovery

**Date:** 2026-05-11  
**Status:** Design Complete (Ready for Implementation Planning)  
**Author:** Claude Code (Brainstorming Process)

---

## Executive Summary

Phase 20 extends Phase 16's probation remediation pathway with positive reinforcement: when a sovereign exits probation cleanly, they enter an explicit **'recovering'** state and are graduated back to **'active'** over 8 weeks (week 1 = score 85, week 4 = 92, week 8 = 100). This prevents instant score restoration and reinforces the message that trust must be earned incrementally.

**Key invariant:** Recovery is not a shield. Phase 19's multi-dimensional signals (slashing, anomalies, settlement bonus) apply continuously during recovery, ensuring transparent, deterministic scoring.

**Violation during recovery triggers immediate re-quarantine** (no appeal cooldown), closing the feedback loop at the highest enforcement level.

---

## 1. Lifecycle & State Machine

### Complete Remediation Pathway

```
ACTIVE (score 100)
  │
  └─ Violation detected → PROBATION (30 days, reduced thresholds)
      │
      ├─ Clean exit (30 days no violations)
      │         ↓
      │    RECOVERING (8 weeks, graduated score 85→100)
      │         │
      │         ├─ Week 8 clean → ACTIVE (score 100) [auto-transition]
      │         │
      │         └─ Violation detected → QUARANTINE (hard reset, no appeal cooldown)
      │
      └─ Violation during probation → QUARANTINE (Phase 16 behavior, unchanged)

QUARANTINE (score 0, requires consensus appeal)
  │
  └─ 72h cooldown + consensus appeal
      │
      ├─ Appeal approved + behavioral improvement → PROBATION
      │
      └─ Appeal denied → stay QUARANTINE
```

### State Transition Conditions

| From | To | Condition | Enforcement |
|------|-----|-----------|-------------|
| probation | recovering | 30 days clean (no violations) | Auto-transition (Phase 16 sweep) |
| recovering | active | 8 weeks elapsed clean | Auto-transition (weekly sweep) |
| recovering | quarantine | Any violation of Phase 16 thresholds | Immediate (no appeal cooldown) |

---

## 2. Score Calculation During Recovery

### Graduation Formula

**Recovered base score** (time-dependent):
```
recovered_base_score(weeks_elapsed) = 85 + (weeks_elapsed / 8) × 15

Week 0: 85
Week 1: 86.875
Week 2: 88.75
Week 4: 92.5
Week 6: 96.25
Week 8: 100
```

**Phase 19 Signal Integration:**

```
final_score = clamp(
    recovered_base_score(weeks_elapsed)
    - slash_penalty(slashes_30d)
    - anomaly_penalty(anomalies_30d)
    + settlement_bonus(settled_all_time),
    0, 100
)
```

Where:
- `slash_penalty = min(30, slashes_30d × 10)` — recent economic penalties
- `anomaly_penalty = min(20, anomalies_30d × 8)` — recent behavioral issues
- `settlement_bonus = min(20, settled_all_time × 5)` — cooperation history

**Example score trajectories:**
| Scenario | Week 0 | Week 4 | Week 8 | Interpretation |
|----------|--------|--------|--------|---|
| Clean recovery | 85 | 92.5 | 100 | No signal penalties; smooth restoration |
| 2 slashes mid-recovery | 85-20=65 | 92.5-20=72.5 | 100 | Slashes age out after 30d; score recovers |
| High settlement activity | 85+20=105 → 100 | 92.5+20=100 | 100 | Settlement bonus caps at +20; score capped at 100 |

---

## 3. Data Model

### Migration 031: Reputation Recovery Log

**File:** `crates/siss-graph-db/src/migrations/031_add_phase20_reputation_recovery.sql`

```sql
CREATE TABLE reputation_recovery_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Entry Conditions (lifecycle transition anchor)
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    recovery_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    score_at_entry INT NOT NULL,
    probation_exit_reason VARCHAR(32) NOT NULL
        CHECK (probation_exit_reason IN ('clean_30_days', 'manual_override', 'appeal_success')),
    
    -- Recovery Progress (8-week window)
    recovery_window_weeks INT NOT NULL DEFAULT 8,
    recovery_progress_weeks INT NOT NULL DEFAULT 0,
    last_progress_update_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Signals During Recovery (Phase 19 integration)
    slashes_during_recovery INT NOT NULL DEFAULT 0,
    anomalies_during_recovery INT NOT NULL DEFAULT 0,
    settlement_bonus_during_recovery INT NOT NULL DEFAULT 0,
    score_adjustments_applied INT NOT NULL DEFAULT 0,
    
    -- Exit Conditions (success or failure)
    recovery_completed_at TIMESTAMPTZ,
    recovery_exit_status VARCHAR(32)
        CHECK (recovery_exit_status IS NULL OR recovery_exit_status IN ('success', 'failure')),
    score_at_exit INT,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_recovery_sovereign ON reputation_recovery_log(sovereign_id, recovery_started_at DESC);
CREATE INDEX idx_recovery_active ON reputation_recovery_log(sovereign_id) WHERE recovery_exit_status IS NULL;
CREATE INDEX idx_recovery_completed ON reputation_recovery_log(sovereign_id, recovery_completed_at DESC) 
    WHERE recovery_exit_status IS NOT NULL;
```

### Sovereigns Table (No Changes)

`sovereigns.status VARCHAR(32)` already supports `'recovering'` as a value. No enum constraints exist.

---

## 4. Computational Components

### Pure Functions (Testable, Deterministic)

**In `crates/siss-graph-db/src/repo/reputation_recovery_repo.rs`:**

```rust
/// Compute recovered base score from weeks elapsed.
/// Formula: 85 + (weeks / 8) × 15, clamped to [85, 100]
pub fn recovered_base_score(weeks_elapsed: u32) -> i16 {
    let progress = std::cmp::min(weeks_elapsed, 8) as i16;
    85 + (progress * 15) / 8
}

/// Compute final recovery score: base + Phase 19 signals
pub fn compute_recovery_score(
    weeks_elapsed: u32,
    slash_count: i64,
    anomaly_count: i64,
    settled_count: i64,
) -> i16 {
    let base = recovered_base_score(weeks_elapsed);
    
    // Reuse Phase 19 penalty/bonus functions
    let slash_penalty = slash_penalty_from_count(slash_count);
    let anomaly_penalty = anomaly_penalty_from_count(anomaly_count);
    let settlement_bonus = settlement_bonus_from_count(settled_count);
    
    let score = (base as i32 - slash_penalty as i32 - anomaly_penalty as i32 
        + settlement_bonus as i32) as i16;
    score.clamp(0, 100)
}

/// Calculate weeks elapsed since recovery started.
pub fn weeks_elapsed(recovery_started_at: DateTime<Utc>) -> u32 {
    let elapsed = Utc::now() - recovery_started_at;
    (elapsed.num_days() / 7) as u32
}
```

### Repository Functions (Database Integration)

**In `reputation_recovery_repo.rs`:**

```rust
/// Auto-transition probation → recovery (triggered by Phase 16 sweep)
pub async fn auto_exit_probation_to_recovery(
    pool: &PgPool,
    sovereign_id: Uuid,
    exit_reason: &str, // 'clean_30_days', 'manual_override', 'appeal_success'
) -> Result<Uuid, RecoveryError>

/// Weekly sweep: advance recovery progress, check for completion
pub async fn sweep_recovery_progress(pool: &PgPool) -> Result<Vec<Uuid>, RecoveryError>

/// Auto-transition recovery → active (success, called by sweep at week 8)
pub async fn auto_exit_recovery_to_active(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<(), RecoveryError>

/// Immediate re-quarantine on violation (called by gatekeeper)
pub async fn violation_during_recovery_to_quarantine(
    pool: &PgPool,
    sovereign_id: Uuid,
    violation_reason: &str,
) -> Result<(), RecoveryError>

/// Get active recovery record for scoring (called by peer_scoring_repo)
pub async fn get_active_recovery(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Option<RepRecover>, RecoveryError>
```

### Peer Scoring Integration

**In `crates/siss-graph-db/src/repo/peer_scoring_repo.rs`:**

Modify `compute_and_upsert_score()`:

```rust
pub async fn compute_and_upsert_score(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<i16, sqlx::Error> {
    let status = fetch_sovereign_status(pool, sovereign_id).await?;
    
    let score = match status.as_str() {
        "recovering" => {
            // Phase 20: Graduated recovery with Phase 19 signals
            let recovery = get_active_recovery(pool, sovereign_id).await?;
            if let Some(rec) = recovery {
                let weeks = weeks_elapsed(rec.recovery_started_at);
                let slash_count = fetch_slash_count_30d(pool, sovereign_id).await?;
                let anomaly_count = fetch_anomaly_count_30d(pool, sovereign_id).await?;
                let settled_count = fetch_settled_count(pool, sovereign_id).await?;
                
                compute_recovery_score(weeks, slash_count, anomaly_count, settled_count)
            } else {
                // Stale status; should not happen (gatekeeper should clean up)
                50 // unknown
            }
        }
        "active" => {
            // Phase 19: existing logic (unchanged)
            let base = 100;
            let slash_count = fetch_slash_count_30d(pool, sovereign_id).await?;
            let anomaly_count = fetch_anomaly_count_30d(pool, sovereign_id).await?;
            let settled_count = fetch_settled_count(pool, sovereign_id).await?;
            
            compute_enriched_score(base, slash_count, anomaly_count, settled_count)
        }
        "probation" => {
            // Phase 16: existing logic (unchanged)
            let base = 80;
            let slash_count = fetch_slash_count_30d(pool, sovereign_id).await?;
            let anomaly_count = fetch_anomaly_count_30d(pool, sovereign_id).await?;
            let settled_count = fetch_settled_count(pool, sovereign_id).await?;
            
            compute_enriched_score(base, slash_count, anomaly_count, settled_count)
        }
        _ => 50, // unknown/quarantined
    };
    
    upsert_peer_score(pool, sovereign_id, score).await?;
    Ok(score)
}
```

### Gatekeeper Integration

**In `crates/siss-gatekeeper/src/refresh.rs`:**

Modify probation exit logic:
- On clean 30-day exit: call `auto_exit_probation_to_recovery()` instead of direct active transition
- On violation: call `violation_during_recovery_to_quarantine()` (if status == 'recovering')

---

## 5. Error Handling & Edge Cases

### Edge Case 1: Stale Recovery Status
**Scenario:** Sovereign's status is 'recovering', but no active recovery record exists.

**Resolution:** 
- Gatekeeper validates on every session refresh
- If status 'recovering' with no recovery record: log warning, reset to 'probation' or 'active' (depends on context)
- Prevent scoring from crashing

### Edge Case 2: Multiple Recovery Cycles
**Scenario:** Sovereign fails recovery (re-quarantine), appeals again, gets probation again, exits cleanly again.

**Resolution:**
- `reputation_recovery_log` is append-only
- Each recovery cycle is a new record
- Queries use `WHERE recovery_exit_status IS NULL` to find active recovery
- Historical cycles auditable

### Edge Case 3: Settlement Bonus During Recovery
**Scenario:** Sovereign receives settlement credit (settled invoice) during week 5 of recovery.

**Resolution:**
- Phase 19 signals fetch all-time settled invoices
- Next peer score computation sees the new settlement
- Score ticks up (bonus applies)
- Transparent in peer_scoring table and recovery audit trail

### Edge Case 4: Signal Aging (30-day windows)
**Scenario:** Sovereign slashed on day 1 of recovery, now at day 31 of recovery (week 4.4).

**Resolution:**
- Slash penalty queries use `WHERE slashed_at >= NOW() - 30 days`
- On day 31, slash falls out of window
- Score bounces back up to recovered_base_score
- No manual intervention needed (deterministic)

### Edge Case 5: Re-Quarantine → Appeal → Probation (not Recovery)
**Scenario:** Sovereign violates during recovery week 5 → re-quarantine. Later appeals and is approved.

**Resolution:**
- Recovery record marked as `recovery_exit_status='failure'`
- New appeal cycle starts (Phase 16: 72h cooldown)
- If appeal approved: new probation record created
- Recovery can **only** be entered from clean probation exit
- No shortcuts

---

## 6. Test Coverage Plan

### Unit Tests (Pure Functions)

**File:** `crates/siss-graph-db/src/repo/reputation_recovery_repo.rs` (tests module)

```rust
#[cfg(test)]
mod tests {
    // Graduation curve tests
    #[test] fn test_recovered_base_score_week_0() { assert_eq!(recovered_base_score(0), 85); }
    #[test] fn test_recovered_base_score_week_4() { assert_eq!(recovered_base_score(4), 92); }
    #[test] fn test_recovered_base_score_week_8() { assert_eq!(recovered_base_score(8), 100); }
    #[test] fn test_recovered_base_score_capped_at_100() { assert_eq!(recovered_base_score(16), 100); }
    
    // Score computation with signals
    #[test] fn test_recovery_score_clean_week_0() { /* no slashes, no anomalies */ }
    #[test] fn test_recovery_score_with_slashes() { /* 2 slashes = -20 penalty */ }
    #[test] fn test_recovery_score_with_anomalies() { /* 1 anomaly = -8 penalty */ }
    #[test] fn test_recovery_score_with_settlement_bonus() { /* 3 settlements = +15 bonus */ }
    #[test] fn test_recovery_score_clamped_to_0() { /* penalty exceeds base */ }
    #[test] fn test_recovery_score_clamped_to_100() { /* base + bonus exceeds 100 */ }
    
    // Weeks elapsed
    #[test] fn test_weeks_elapsed_day_0() { assert_eq!(weeks_elapsed(now), 0); }
    #[test] fn test_weeks_elapsed_day_7() { assert_eq!(weeks_elapsed(7_days_ago), 1); }
    #[test] fn test_weeks_elapsed_day_56() { assert_eq!(weeks_elapsed(56_days_ago), 8); }
}
```

### Integration Tests

**File:** `crates/siss-graph-db/src/tests/phase20_recovery.rs`

```rust
#[tokio::test]
async fn test_probation_to_recovery_transition() {
    // Setup: sovereign in probation, 30 days elapsed, no violations
    // Call: auto_exit_probation_to_recovery()
    // Assert: status = 'recovering', recovery_log created
}

#[tokio::test]
async fn test_recovery_score_computation() {
    // Setup: sovereign in recovery at week 4, 2 slashes
    // Call: compute_and_upsert_score()
    // Assert: score = 92 - 20 = 72
}

#[tokio::test]
async fn test_recovery_sweep_at_week_8() {
    // Setup: sovereign in recovery, 8+ weeks elapsed
    // Call: sweep_recovery_progress()
    // Assert: status = 'active', recovery_completed_at set, score computed
}

#[tokio::test]
async fn test_violation_during_recovery() {
    // Setup: sovereign in recovery, violation detected
    // Call: violation_during_recovery_to_quarantine()
    // Assert: status = 'quarantined', recovery_exit_status = 'failure', no appeal cooldown
}

#[tokio::test]
async fn test_settlement_bonus_during_recovery() {
    // Setup: sovereign in recovery, settle an invoice
    // Call: compute_and_upsert_score()
    // Assert: score includes settlement bonus
}

#[tokio::test]
async fn test_signal_aging_during_recovery() {
    // Setup: sovereign in recovery, slashed 31 days ago, now at week 5
    // Call: compute_and_upsert_score()
    // Assert: slash penalty not applied (aged out of 30-day window)
}
```

### End-to-End Test

**File:** `crates/siss-gatekeeper/src/tests/phase20_recovery_e2e.rs`

```rust
#[tokio::test]
async fn test_full_recovery_lifecycle() {
    // 1. Sovereign in active, commits violation → probation
    // 2. Phase 16 processes: 30 clean days → recovery
    // 3. Phase 20 processes: 8 weeks graduated score
    // 4. Assert: final status = active, score = 100
}

#[tokio::test]
async fn test_recovery_with_mid_cycle_slashing() {
    // 1. Sovereign enters recovery at week 0
    // 2. Week 3: slashed (score drops from ~90 to ~70)
    // 3. Week 6: slash ages out of 30-day window (score recovers)
    // 4. Week 8: exits to active with score ~100
}
```

---

## 7. Task Breakdown

| # | Task | Description | Owner |
|---|------|-------------|-------|
| 87 | Migration & Schema | Create migration 031, add indexes, verify sovereigns.status | TBD |
| 88 | Reputation Recovery Repo | Implement `reputation_recovery_repo.rs` with all 6 functions | TBD |
| 89 | Peer Scoring Integration | Modify `peer_scoring_repo.rs` to handle 'recovering' status | TBD |
| 90 | Gatekeeper Integration | Update `refresh.rs` probation exit & violation logic | TBD |
| 91 | Sweep Job Registration | Create `recovery_sweep.rs`, register weekly job | TBD |
| 92 | Testing & Verification | Unit + integration + E2E tests, verify all phases integrate | TBD |

---

## 8. Constitutional Invariants (Phase 20)

1. **RECOVERY_IS_EXPLICIT_LIFECYCLE** — 'recovering' is a first-class status in sovereigns table
2. **GRADUATED_RECOVERY_DETERMINISTIC** — Score curve is 85 + (weeks/8)×15, purely time-dependent (until signals apply)
3. **SIGNALS_ALWAYS_APPLY** — Phase 19 penalties/bonuses apply during recovery, no exceptions
4. **VIOLATION_ENDS_RECOVERY** — Any probation threshold breach during recovery → immediate quarantine (no appeal cooldown)
5. **RECOVERY_ONLY_FROM_CLEAN_PROBATION** — Recovery can only be entered via clean 30-day probation exit
6. **AUTO_TRANSITIONS_DETERMINISTIC** — All state transitions (probation→recovery, recovery→active, recovery→quarantine) are automated via scheduled sweeps
7. **FULL_AUDITABILITY** — `reputation_recovery_log` tracks entry, progress, signals, and exit for complete transparency

---

## 9. Architectural Alignment

### Closes Feedback Loops

1. **Phase 15 + 20:** Quarantine now has a full remediation path (appeal → probation → recovery → active)
2. **Phase 16 + 20:** Probation exit is not instant active; recovery provides graduated trust restoration
3. **Phase 17 + 20:** Network peers can observe recovery progress via peer_scoring; recovering sovereigns are correctly ranked below active
4. **Phase 19 + 20:** Multi-dimensional signals apply consistently across all states, including recovery

### Consistency With System Philosophy

- **Explicit lifecycle states** (Phases 15, 16, now 20)
- **Network-visible trust signals** (Phase 17, 19, now 20)
- **Deterministic, rule-based enforcement** (Phase 15–16, now 20)
- **Fail-closed design** (violation during recovery → quarantine, no mercy)

---

## 10. Implementation Prerequisites

Before starting Phase 20 tasks:

1. **Phase 19 complete** ✓ (peer_scoring_repo.rs with enriched scoring)
2. **Phase 16 complete** ✓ (probation lifecycle with thresholds)
3. **Migration 030 applied** ✓ (appeal_proposals, behavioral_improvements, probation_audit_log)
4. **Job router ready** ✓ (sweep infrastructure in place)

---

## Sign-Off

**Phase 20 Design:** Graduated Reputation Recovery — READY FOR IMPLEMENTATION PLANNING

All architectural decisions made. All edge cases identified. All state transitions specified. All signal integrations defined. Ready to move to task planning and implementation.

