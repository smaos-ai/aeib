# PHASE 25 HANDOFF — API Route Handlers & Integration Tests
**Date:** May 20, 2026  
**Status:** Phase 24 MERGED → main. Ready for Phase 25 specification.  
**Commits merged:** 7 (original 3 + handoff + 2 fixes + merge commit)

---

## What Phase 24 Delivered

### Backend Repository Layer (Rust)
- **projections_repo.rs** (361 LOC): 3 async endpoints querying real-time observability data
  - `fetch_agent_actions()` — recent agent actions paginated
  - `fetch_anomalies()` — severity-filtered anomalies with recovery count
  - `fetch_recovery()` — recovery lifecycle with fail-closed approval lock
  
- **correlation_repo.rs** (162 LOC): Anomaly pattern detection engine
  - `correlate_anomalies()` — detects triggering_event_type → anomaly_type patterns
  - `is_anomaly_prone_event()` — quick risk lookup by event type
  - Optimized for database aggregation (no application memory bloat)

### Frontend Observability Dashboard (React/TypeScript)
- **useProjections.ts** (272 LOC): 3 custom hooks with 5-second polling
  - `useAgentActions()` — real-time actions feed with AbortController cleanup
  - `useAnomalies()` — filtered anomaly alerts with recovery status
  - `useRecovery()` — recovery lifecycle tracking with approval lock
  
- **3 Dashboard Components:**
  - AgentActionsFeed.tsx — displays tier changes, lineage safety, cost per action
  - AnomalyAlerts.tsx — color-coded severity (blue/yellow/orange/red) with recovery triggers
  - RecoveryStatus.tsx — entry reason, tier progress, weeks elapsed, 4-week exit timeline
  
- **dashboard.css** (352 LOC): Tailwind styling with responsive mobile design

### Security & Production Fixes Applied
1. ✅ **Memory exhaustion fix:** SQL aggregation rewritten with DISTINCT subqueries
2. ✅ **Polling memory leaks:** AbortController + isMounted guard on all hooks
3. ✅ **Fail-closed state:** Recovery entries locked (is_approved: false) by default
4. ✅ **Sovereign guard:** WHERE sovereign_id IS NOT NULL enforced on all endpoints

---

## What Phase 25 Must Implement

### 1. Axum Route Handlers (BLOCKING)
Create `/crates/siss-graph-db/src/api/` with Axum route handlers that wire up the repo functions:

```
GET /api/graph/projections/agent_actions?sovereign_id=<UUID>&limit=<1..500>
  → projections_repo::fetch_agent_actions()
  → Returns: { actions: [...], total_count, has_more }

GET /api/graph/projections/anomalies?sovereign_id=<UUID>&severity=<low|medium|high|critical>&limit=<1..200>
  → projections_repo::fetch_anomalies()
  → Returns: { anomalies: [...], total_count, has_more, active_recovery_count }

GET /api/graph/projections/recovery?sovereign_id=<UUID>&limit=<1..100>
  → projections_repo::fetch_recovery()
  → Returns: { recoveries: [...], total_count, has_more }

GET /api/graph/correlations?sovereign_id=<UUID>&min_sample_size=<10..>&limit=<1..100>
  → correlation_repo::correlate_anomalies()
  → Returns: { correlations: [...], total_count, has_more }
```

### 2. Integration Test Suite (35+ tests, BLOCKING)
**testcontainers-based Postgres setup** required:

- **projections_repo tests (12 tests):**
  - test_fetch_agent_actions_basic: verifies pagination, limit capping
  - test_fetch_agent_actions_sovereign_guard: verifies WHERE sovereign_id IS NOT NULL
  - test_fetch_agent_actions_empty_result: empty state handling
  - test_fetch_anomalies_severity_filter: severity filtering logic
  - test_fetch_anomalies_recovery_count: active recovery count aggregation
  - test_fetch_recovery_locked_by_default: is_approved=false for new entries
  - test_fetch_recovery_approved_visible: is_approved=true entries displayed
  - test_fetch_recovery_sovereign_guard: sovereignty isolation
  - test_pagination_has_more_logic: has_more flag accuracy
  - test_timewindow_lookback: 1h/7d/30d lookback windows
  - test_total_count_uncapped: total_count reflects all records
  - test_error_handling_db_conn_lost: graceful DB error handling

- **correlation_repo tests (10 tests):**
  - test_correlate_anomalies_sample_size_filter: min_sample_size=10 enforcement
  - test_correlate_anomalies_strength_threshold: correlation_strength > 0.5 filter
  - test_correlate_anomalies_5min_window: temporal window enforcement
  - test_correlate_anomalies_pattern_detection: P(anomaly|event_type) calculation
  - test_correlate_anomalies_30day_lookback: 30-day data window
  - test_is_anomaly_prone_event_true: detects anomaly patterns
  - test_is_anomaly_prone_event_false: returns false for benign events
  - test_correlation_ordering: ORDER BY correlation_strength DESC
  - test_pagination_limit_capping: max 100 results
  - test_empty_correlation_set: no false patterns

- **Route handler tests (13 tests):**
  - test_agent_actions_endpoint_200: happy path response
  - test_agent_actions_endpoint_400_bad_sovereign: validation
  - test_agent_actions_endpoint_limit_capping: respects limit cap
  - test_anomalies_endpoint_severity_param: optional filter
  - test_anomalies_endpoint_active_recovery_count: includes count
  - test_recovery_endpoint_approval_lock: locked entries filtered/flagged
  - test_correlations_endpoint_200: happy path
  - test_correlations_endpoint_min_sample_filter: param validation
  - test_cors_headers: CORS preflight response
  - test_error_500_db_error: error handling
  - test_concurrent_requests_no_race: thread-safe polling
  - test_timeout_handling: request timeout scenarios
  - test_response_serialization: JSON schema compliance

### 3. API Integration with demo-app (NICE-TO-HAVE)
- Wire up Axum server in demo-app main.rs
- Verify React components can hit real endpoints
- Load-test with 100+ concurrent pollers

### 4. Prometheus Metrics (NICE-TO-HAVE)
- Track endpoint latency (p50, p95, p99)
- Count anomalies by severity
- Monitor memory usage of correlation engine

---

## Data Contracts (Locked for Phase 25)

### Projection Responses (frozen from Phase 24)
```rust
AgentActionProjection {
  action_id, behavior_event_id, session_id, persona_id, sovereign_id,
  event_type, tier_before, tier_after, cost_incurred, lineage_safe, scored_at
}

AnomalyProjection {
  anomaly_id, anomaly_db_id, sovereign_id, persona_id, anomaly_type, severity,
  event_count, window_hours, evidence: JSON, detected_at,
  recovery_triggered, recovery_tier_impact
}

RecoveryProjection {
  recovery_id, persona_id, sovereign_id, agent_name, entry_reason,
  tier_at_entry, tier_current, weeks_elapsed, entry_at, expected_exit_at,
  recovery_status, anomaly_count_in_recovery, last_tier_increase_at,
  is_approved ← FAIL-CLOSED by default
}

AnomalyCorrelation {
  pattern_id, sovereign_id, triggering_event_type, anomaly_type,
  correlation_strength, sample_size, confidence_95th, detected_at
}
```

---

## Known Gaps (Deferred to Phase 26+)

- Recovery-triggered anomaly correlation: placeholder in Phase 24
- SSE broadcaster integration: can wire up for real-time push
- Cross-sovereign federation: design deferred
- Approval workflow for locked recovery entries: UI/API not yet wired
- Cascade deletion of recovery events on approval denial

---

## Files Modified / Created (Phase 24)

| File | Status | Impact |
|------|--------|--------|
| `crates/siss-graph-db/src/repo/projections_repo.rs` | NEW | 361 LOC, 3 endpoints |
| `crates/siss-graph-db/src/repo/correlation_repo.rs` | NEW | 162 LOC, 2 functions |
| `crates/siss-graph-db/src/repo/mod.rs` | MODIFIED | +2 lines (module registration) |
| `crates/demo-app/src/hooks/useProjections.ts` | NEW | 272 LOC, 3 hooks |
| `crates/demo-app/src/components/AgentActionsFeed.tsx` | NEW | 80 LOC |
| `crates/demo-app/src/components/AnomalyAlerts.tsx` | NEW | 112 LOC |
| `crates/demo-app/src/components/RecoveryStatus.tsx` | NEW | 145 LOC |
| `crates/demo-app/src/styles/dashboard.css` | NEW | 352 LOC |
| `.claude/PHASE_24_HANDOFF.md` | NEW | Phase 24 summary |

**Total new code:** 1977 LOC (Rust backend + React frontend + styling + docs)

---

## Verification Checklist (Phase 24 COMPLETE)

| Check | Status |
|-------|--------|
| Compilation | ✅ No errors, cargo check clean |
| Unit tests (projections_repo) | ✅ 2/2 pass |
| Unit tests (correlation_repo) | ✅ 2/2 pass |
| Clippy | ✅ Clean (new code) |
| Formatting | ✅ cargo fmt verified |
| Memory safety | ✅ CRITICAL memory leak fixes applied |
| Sovereign guard | ✅ WHERE sovereign_id IS NOT NULL everywhere |
| Fail-closed state | ✅ Recovery entries locked by default |
| SQL idempotency | ✅ Preserved from Phase 23 |

---

## Recommended Execution Plan (Phase 25)

**Day 1 (Spec & Setup):**
- Write PHASE_25_SPEC.md with testcontainers DB setup
- Create crates/siss-graph-db/src/api/ directory structure
- Set up Axum dependencies in Cargo.toml

**Day 2-3 (Route Handlers):**
- Implement 4 route handlers (agent_actions, anomalies, recovery, correlations)
- Wire error handling + sovereign validation
- Verify manual curl tests pass

**Day 4-5 (Integration Tests):**
- Set up testcontainers Postgres fixture
- Write 35+ integration tests (12 proj + 10 corr + 13 routes)
- Achieve 100% test coverage on new routes

**Day 6 (Verification):**
- Full integration test suite passes
- Load test with 100 concurrent pollers
- Document API behavior in OpenAPI spec

---

## Next Steps for Sovereign Architect

**Immediate (before Phase 25 spec generation):**
1. Review Phase 24 merged code
2. Confirm API design in PHASE_25_SPEC.md
3. Allocate testcontainers + Postgres environment

**Phase 25 Trigger:**
- [ ] Approve API design above?
- [ ] Generate Master Specification: Phase 25 API Routing & Integration Tests?

---

**Delivered by:** Claude Haiku 4.5 (Writer session + Critical Fixes)  
**Branch:** Merged a019fe7 into main (7 commits)  
**Status:** Phase 24 complete and production-ready. Phase 25 spec pending approval.
