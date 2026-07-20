# STREAM 3 Implementation Plan
**Status:** READY FOR EXECUTION  
**Date:** July 18, 2026  
**Duration:** Aug 1 – Sep 30 (9 weeks)  
**Agents:** 3 parallel workers (file-orthogonal, Phase 30 orchestration)  
**Merge Order:** Baseline → AntiYou → TimeCapsule → Market Vision → Integration Tests  

---

## Overview

This plan translates STREAM_3_CAPSULE_ECOSYSTEM_SPEC.md into 5 sequential phases with 3 parallel worker agents (Wave 2) following Phase 30 orchestration pattern. Zero file collisions guaranteed.

**The Golden Rule:** Each agent owns isolated subsystems.
- Agent 1 (Worker-AntiYou): `crates/siss-capsules/src/anti_you/`
- Agent 2 (Worker-TimeCapsule): `crates/siss-capsules/src/time_capsule/`
- Agent 3 (Worker-MarketVision): `crates/siss-capsules/src/market_vision/`
- Baseline (Sequential-Pre): `crates/siss-capsules/src/baseline_capsule.rs` + `base_impl.rs`

**Success Definition:** 40 tests passing, zero clippy warnings, €3M ARR pricing locked, investor demo ready.

---

## Phase 1: Sequential Setup (Aug 1–5, 1 dispatcher agent)

### Task 1.1: Create Crate Structure & Baseline

**Owner:** Dispatcher (sequential pre-work)  
**Files owned:**
- `crates/siss-capsules/Cargo.toml`
- `crates/siss-capsules/src/lib.rs`
- `crates/siss-capsules/src/baseline_capsule.rs`
- `crates/siss-capsules/src/base_impl.rs`
- `crates/siss-capsules/src/events/mod.rs`
- `crates/siss-capsules/src/events/store.rs`
- `crates/siss-capsules/src/governance/mod.rs`
- `crates/siss-capsules/src/governance/rebac.rs`
- Database migrations (PostgreSQL schema)

**Goals:**
1. Create `crates/siss-capsules/` directory
2. Define `BaselineCapsule` trait (event emission, policy check, approval gating)
3. Implement base_impl (PostgreSQL event store, policy delegation, signing)
4. Create immutable event log schema
5. Wire up telemetry sender for ARR metrics

**Test Verification:**
- `cargo check -p siss-capsules`
- `cargo clippy -p siss-capsules`

**Acceptance Criteria:**
- BaselineCapsule trait compiles
- PostgreSQL schema created (migrations applied)
- Event emission tested: create event → store in DB → verify signature
- Policy evaluation delegates to siss-gatekeeper
- Crate exports pub mod anti_you, time_capsule, market_vision

**Estimated LOC:** 300 (trait + basic impl)

---

## Phase 2: Wave 1 — AntiYou (Aug 6–15, 1 agent)

**Owner:** Worker-AntiYou  
**Files owned (exclusive):**
- `crates/siss-capsules/src/anti_you/mod.rs`
- `crates/siss-capsules/src/anti_you/model.rs` (AntiYouRecord, AntiYouStatus enum)
- `crates/siss-capsules/src/anti_you/service.rs` (publish, rollback, expiry)
- `crates/siss-capsules/src/anti_you/policy.rs` (ReBAC policy checks)
- `crates/siss-capsules/src/anti_you/tests.rs` (10 tests)
- `crates/siss-capsules/tests/anti_you_integration.rs`
- Database table: `anti_you_records`

**Goals:**
1. Define AntiYouRecord model (content snapshot, deadlines, status)
2. Implement publish service (create record, emit event, snapshot content)
3. Implement rollback service (check 24h policy, approve replacement, emit events)
4. Implement expiry handler (TTL cleanup, GDPR erasure)
5. Write 10 tests (TDD first)

**Test Plan (RED → GREEN):**

```rust
#[test]
async fn test_anti_you_record_creates_on_publish() {
    // Publish content with AntiYou enabled
    // Assert: AntiYouRecord created, content_snapshot captured, deadline set
}

#[test]
async fn test_anti_you_rollback_within_24h_allowed() {
    // Publish content, wait 1h, request rollback
    // Assert: Policy returns ALLOW, rollback succeeds
}

#[test]
async fn test_anti_you_rollback_after_24h_denied() {
    // Publish content, wait 25h, request rollback
    // Assert: Policy returns DENY (expired window)
}

#[test]
async fn test_anti_you_reversion_content_requires_approval() {
    // Rollback with replacement_content provided
    // Assert: Blocks until creator approves, emits ApprovalGranted
}

#[test]
async fn test_anti_you_subscribers_notified_on_rollback() {
    // Publish with engagement > 100, then rollback
    // Assert: Notification sent to feedback router
}

#[test]
async fn test_anti_you_engagement_snapshot_captured() {
    // Publish, wait 10 mins, rollback
    // Assert: engagement_snapshot has views, likes, shares at rollback time
}

#[test]
async fn test_anti_you_immutable_log_signed() {
    // Emit multiple events
    // Assert: All events signed with creator key, Merkle root computed
}

#[test]
async fn test_anti_you_ttl_cleanup_after_24h() {
    // Publish, wait 24h + epsilon
    // Assert: TTL triggers, status=Expired, snapshot deleted, events retained
}

#[test]
async fn test_anti_you_creator_can_rollback_multiple_times() {
    // Publish content A, rollback; publish content B, rollback
    // Assert: Both records independent, multiple rollbacks allowed per creator
}

#[test]
async fn test_anti_you_gdpr_erasure_cleans_snapshot() {
    // Publish content, trigger GDPR erasure for creator
    // Assert: content_snapshot deleted, event log retained
}
```

**Acceptance Criteria:**
- [ ] All 10 tests passing
- [ ] `cargo clippy -p siss-capsules` zero warnings
- [ ] Policy check delegates to siss-gatekeeper (no hardcoded logic)
- [ ] Events signed and verified
- [ ] TTL cleanup tested and working

**Estimated LOC:** 400 (model + service + tests)

**Definition of Done:** All 10 tests green, merged to main.

---

## Phase 3: Wave 2 — TimeCapsule (Aug 6–15, parallel with AntiYou)

**Owner:** Worker-TimeCapsule  
**Files owned (exclusive):**
- `crates/siss-capsules/src/time_capsule/mod.rs`
- `crates/siss-capsules/src/time_capsule/model.rs` (TimeCapsule, DeliveryCondition, RecurrenceRule)
- `crates/siss-capsules/src/time_capsule/service.rs` (schedule, revoke, deliver, recurrence)
- `crates/siss-capsules/src/time_capsule/scheduler.rs` (cron-based delivery task)
- `crates/siss-capsules/src/time_capsule/policy.rs` (ReBAC policy checks)
- `crates/siss-capsules/src/time_capsule/tests.rs` (12 tests)
- `crates/siss-capsules/tests/time_capsule_integration.rs`
- Database table: `time_capsules`

**Goals:**
1. Define TimeCapsule model (scheduled_for, revocation_deadline, delivery_conditions)
2. Implement schedule service (validate, create record, emit event)
3. Implement revoke service (check 1h deadline, approval, emit events)
4. Implement scheduler (background task, delivery at scheduled_for, recurrence)
5. Write 12 tests (TDD first)

**Test Plan (RED → GREEN):**

```rust
#[test]
async fn test_time_capsule_schedule_creates_record() {
    // Schedule content for 1h from now
    // Assert: TimeCapsule created, status=Scheduled, deadline calculated
}

#[test]
async fn test_time_capsule_revocation_allowed_before_1h_deadline() {
    // Schedule content, wait 30 mins, request revoke
    // Assert: Policy returns ALLOW, revoke succeeds
}

#[test]
async fn test_time_capsule_revocation_denied_after_1h_deadline() {
    // Schedule content, wait 61 mins, request revoke
    // Assert: Policy returns DENY (deadline passed)
}

#[test]
async fn test_time_capsule_replacement_content_requires_approval() {
    // Revoke with replacement_content
    // Assert: Blocks until creator approves
}

#[test]
async fn test_time_capsule_delivery_condition_evaluated_at_publish() {
    // Schedule with conditional_logic = "BTC > 100K", verify false at delivery time
    // Assert: Publish suppressed, status=Expired, event logged
}

#[test]
async fn test_time_capsule_automatic_publish_at_scheduled_time() {
    // Schedule for now + 1 min
    // Assert: Cron job publishes after deadline, status=Published
}

#[test]
async fn test_time_capsule_recurrence_creates_next_instance() {
    // Schedule weekly for next Monday
    // Assert: On delivery, next TimeCapsule created with same series_id
}

#[test]
async fn test_time_capsule_rate_limit_enforced_per_creator() {
    // Create 101 scheduled posts in 24h
    // Assert: 101st rejected by policy (rate_limit=100)
}

#[test]
async fn test_time_capsule_immutable_log_tracks_all_state_changes() {
    // Schedule → Revoke → Deliver
    // Assert: 3 events in log, all signed
}

#[test]
async fn test_time_capsule_replacement_content_published_on_approval() {
    // Revoke + provide replacement, approve
    // Assert: Replacement published at original scheduled_for time
}

#[test]
async fn test_time_capsule_gdpr_erasure_removes_snapshots() {
    // Schedule content, trigger GDPR erasure
    // Assert: Snapshots deleted, events retained
}

#[test]
async fn test_time_capsule_conditional_logic_syntax_validated() {
    // Schedule with invalid condition syntax
    // Assert: Rejected at creation time with ValidationError
}
```

**Acceptance Criteria:**
- [ ] All 12 tests passing
- [ ] `cargo clippy -p siss-capsules` zero warnings
- [ ] Scheduler task runs in background (tokio::spawn)
- [ ] Delivery at scheduled_for verified
- [ ] Recurrence creates next instance correctly
- [ ] Rate limit policy enforced

**Estimated LOC:** 500 (model + service + scheduler + tests)

**Definition of Done:** All 12 tests green, merged to main.

---

## Phase 4: Wave 2 — Market Vision (Aug 6–20, parallel with AntiYou & TimeCapsule)

**Owner:** Worker-MarketVision  
**Files owned (exclusive):**
- `crates/siss-capsules/src/market_vision/mod.rs`
- `crates/siss-capsules/src/market_vision/model.rs` (CreatorProfile, AnomalySignal, AnomalyType)
- `crates/siss-capsules/src/market_vision/profiler.rs` (Learning algorithm, 50-post bootstrap)
- `crates/siss-capsules/src/market_vision/detector.rs` (Anomaly scoring, z-score calculation)
- `crates/siss-capsules/src/market_vision/consensus.rs` (Subscriber consensus model)
- `crates/siss-capsules/src/market_vision/policy.rs` (ReBAC policy checks)
- `crates/siss-capsules/src/market_vision/tests.rs` (13 tests)
- `crates/siss-capsules/tests/market_vision_integration.rs`
- Database tables: `creator_profiles`, `anomaly_signals`

**Goals:**
1. Define CreatorProfile model (publishing pattern, linguistic profile, consensus)
2. Implement profiler (extract features, compute baseline, 50-post learning)
3. Implement detector (z-score anomaly detection, severity scoring)
4. Implement consensus model (subscriber agreement tracking)
5. Write 13 tests (TDD first)

**Dependency on Feature:** Sentiment analysis library (vader-sentiment or transformers)
- Sentiment: VADER (simple, fast, no ML)
- Formality: Flesch-Kincaid readability score (simple formula)
- Vocabulary entropy: Count unique words / total words

**Test Plan (RED → GREEN):**

```rust
#[test]
async fn test_market_vision_profile_learning_requires_50_posts() {
    // Create creator, publish 40 posts
    // Assert: Anomaly detection disabled (training_samples < 50)
    // Publish 10 more posts (total 50)
    // Assert: Anomaly detection enabled on post 51
}

#[test]
async fn test_market_vision_timing_anomaly_detected() {
    // Creator normally posts 9am UTC
    // Post at 2am UTC (unusual)
    // Assert: timing_anomaly detected, severity ≥ 5
}

#[test]
async fn test_market_vision_topic_deviation_detected() {
    // Tech creator (90% tech posts)
    // Post on pottery (0% historical)
    // Assert: topic_deviation detected, severity ≥ 5
}

#[test]
async fn test_market_vision_sentiment_shift_detected() {
    // Creator baseline sentiment = +0.5 (positive)
    // Post with sentiment = -0.8 (negative)
    // Assert: sentiment_shift detected, severity ≥ 6
}

#[test]
async fn test_market_vision_formality_shift_detected() {
    // Creator baseline formality = 0.8 (formal)
    // Post with formality = 0.1 (casual)
    // Assert: formality_shift detected, severity ≥ 5
}

#[test]
async fn test_market_vision_vocabulary_anomaly_detected() {
    // Creator vocabulary entropy = 0.7 (diverse)
    // Post with entropy = 0.2 (repetitive)
    // Assert: vocabulary_anomaly detected, severity ≥ 4
}

#[test]
async fn test_market_vision_severity_score_calculated() {
    // Multiple anomalies: timing + topic + sentiment
    // Assert: Severity = 5 + 5 + 6 = 16 (capped at 10)
}

#[test]
async fn test_market_vision_compromise_signal_detected() {
    // 3+ compromise indicators: VPN, new device, unusual location
    // Assert: compromise_signal detected, severity = 10, requires 2FA
}

#[test]
async fn test_market_vision_subscriber_consensus_boosts_severity() {
    // Anomaly detected (severity = 6)
    // Subscriber agreement = 0.8 (80% agree with creator's normal voice)
    // Assert: Severity boosted to 8 (severity + 2)
}

#[test]
async fn test_market_vision_high_severity_requires_approval() {
    // Post with severity = 7
    // Assert: Policy blocks publish until creator approves
}

#[test]
async fn test_market_vision_critical_severity_requires_2fa() {
    // Post with severity = 9 (compromise_signal)
    // Assert: Suppresses publish, requires 2FA override
}

#[test]
async fn test_market_vision_profile_updated_every_100_posts() {
    // Create creator, publish 150 posts
    // Assert: ProfileUpdated events at post 100 and 200
}

#[test]
async fn test_market_vision_creator_can_override_anomaly_detection() {
    // Post with bypass_anomaly_detection = true
    // Assert: Detection skipped, post published
}
```

**Feature Flag Note:** Use conditional compilation for sentiment analysis (optional dependency).
```rust
#[cfg(feature = "market_vision_sentiments")]
fn compute_sentiment(...) -> f32 { ... }

#[cfg(not(feature = "market_vision_sentiments"))]
fn compute_sentiment(...) -> f32 { 0.0 } // Stub
```

**Acceptance Criteria:**
- [ ] All 13 tests passing
- [ ] `cargo clippy -p siss-capsules` zero warnings
- [ ] Sentiment detection working (VADER)
- [ ] Z-score calculation verified with manual examples
- [ ] Profile learning at 50-post threshold
- [ ] Subscriber consensus model tracking correctly

**Estimated LOC:** 600 (model + profiler + detector + consensus + tests)

**Definition of Done:** All 13 tests green, merged to main.

---

## Phase 5: Sequential Merge & Integration (Aug 20–31)

**Owner:** Integration Agent  
**Goals:**
1. Merge all three capsule branches in order: AntiYou → TimeCapsule → MarketVision
2. Resolve any cross-capsule conflicts (should be zero due to file orthogonality)
3. Write 5 cross-capsule integration tests
4. Verify full test suite (40 tests)
5. Run clippy, format, check

**Files owned:**
- `crates/siss-capsules/tests/integration_test.rs` (cross-capsule tests)

**Test Plan (RED → GREEN):**

```rust
#[test]
async fn test_multiple_capsules_emit_independent_events() {
    // Creator uses AntiYou + TimeCapsule + MarketVision
    // Assert: All 3 capsules emit events independently to shared immutable log
}

#[test]
async fn test_capsule_events_form_coherent_audit_trail() {
    // Publish with all 3 capsules enabled
    // Assert: Event log shows all actions in correct sequence, all signed
}

#[test]
async fn test_rollback_from_anti_you_affects_other_capsules() {
    // Rollback content via AntiYou
    // Assert: TimeCapsule scheduled for same content updates, MarketVision alerts
}

#[test]
async fn test_all_capsules_respect_shared_baseline_policy() {
    // Creator tier = 2, policy limits all capsules
    // Assert: AntiYou, TimeCapsule, MarketVision all respect tier ceiling
}

#[test]
async fn test_gdpr_erasure_cleans_all_capsule_snapshots() {
    // Creator deletes account
    // Assert: Snapshots from AntiYou, TimeCapsule, MarketVision all deleted
    //        Event logs retained in immutable_events table
}
```

**Merge Order (Git Commands):**

```bash
# Baseline merged first
git checkout main
git merge --no-ff baseline/phase-3-baseline

# AntiYou merged
git merge --no-ff worker-anti-you/phase-3-anti-you

# TimeCapsule merged
git merge --no-ff worker-time-capsule/phase-3-time-capsule

# MarketVision merged
git merge --no-ff worker-market-vision/phase-3-market-vision

# Integration tests merged last
git merge --no-ff integration/phase-3-integration
```

**Final Verification:**

```bash
cargo test --all
cargo clippy --all -- -D warnings
cargo fmt --check
```

**Expected Output:**
- 40 tests passing
- Zero clippy warnings
- All files formatted

**Definition of Done:** All merges complete, all 40 tests green, investor demo ready.

---

## Phase 6: Documentation & Investor Demo (Sep 1–30)

**Owner:** Docs + Demo Agent  
**Goals:**
1. Write API documentation (OpenAPI/Swagger for each capsule)
2. Create investor deck (pricing, TAM, revenue projections)
3. Build demo script (create creator → use all 3 capsules → show events)
4. Performance baseline (latency metrics)
5. Launch checklist validation

**Files:**
- `crates/siss-capsules/API.md` (endpoint reference)
- `docs/stream-3-investor-deck.md`
- `scripts/demo_stream_3.sh`
- `docs/stream-3-performance-baseline.md`

**Launch Checklist:**
- [ ] All 40 tests passing
- [ ] API documented
- [ ] Demo script works end-to-end
- [ ] Performance baseline <100ms for policy checks
- [ ] Pricing model validated with finance
- [ ] Investor deck reviewed and approved
- [ ] Ready for Series A due diligence

---

## File Ownership Matrix

| File | Phase | Owner | Notes |
|------|-------|-------|-------|
| `crates/siss-capsules/Cargo.toml` | 1 | Dispatcher | Feature gates: anti_you, time_capsule, market_vision |
| `crates/siss-capsules/src/baseline_capsule.rs` | 1 | Dispatcher | BaselineCapsule trait |
| `crates/siss-capsules/src/base_impl.rs` | 1 | Dispatcher | Event store, policy delegation |
| `crates/siss-capsules/src/events/mod.rs` | 1 | Dispatcher | CapsuleEvent enum |
| `crates/siss-capsules/src/anti_you/*` | 2 | Worker-AntiYou | Exclusive ownership |
| `crates/siss-capsules/src/time_capsule/*` | 3 | Worker-TimeCapsule | Exclusive ownership |
| `crates/siss-capsules/src/market_vision/*` | 4 | Worker-MarketVision | Exclusive ownership |
| `crates/siss-capsules/tests/*` | 5 | Integration Agent | Cross-capsule tests |

**Golden Rule Compliance:** ✅ Zero file overlaps. Each agent owns isolated subsystems.

---

## Timeline (Gantt-style)

```
Aug 1–5:   Phase 1 — Baseline (Dispatcher)
Aug 6–15:  Wave 2 — AntiYou (Worker-AntiYou) || TimeCapsule (Worker-TimeCapsule)
Aug 6–20:  Wave 2 — MarketVision (Worker-MarketVision)
Aug 20–31: Phase 5 — Integration + Merges
Sep 1–30:  Phase 6 — Docs + Demo
```

**Parallel Execution Window:** Aug 6–20 (14 days) — 3 agents working independently.

---

## Success Criteria (Investor-Grade)

| Criteria | Target | Status |
|----------|--------|--------|
| Specs locked | Aug 31 | Design doc approved ✅ |
| 40 tests passing | Aug 31 | TDD approach enforced ✅ |
| Zero clippy warnings | Aug 31 | Code quality gate ✅ |
| ARR model validated | Sep 15 | Pricing locked: €2–5/creator/mo ✅ |
| Demo ready | Sep 30 | End-to-end walkthrough ✅ |
| Investor due diligence | Oct 15 | Series A gate ✅ |

---

## Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Sentiment analysis library unavailable | Low | Medium | Use VADER (MIT license, no deps) + fallback to stub |
| Cross-capsule event conflicts | Medium | High | Immutable event log + Merkle roots prevent collisions |
| GDPR erasure complexity | Medium | High | Separate snapshots (erasable) from events (permanent) |
| Performance regression | Low | Medium | Baseline latency test (target <100ms) |
| Series A timeline slip | Medium | Medium | Ship MVP without MarketVision if needed (Aug 20 gate) |

---

## Dependencies & Blockers

**External Dependencies:**
- ✅ `siss-gatekeeper` — ReBAC policy evaluation (assumed ready)
- ✅ `siss-feedback-router` — Subscriber notifications (assumed ready)
- ⚠️ `siss-context-cartography` — Creator context (optional, Phase 25 backfill)

**Blocker:** None. All upstream systems assumed functional.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Wave 1** | Sequential work (Baseline) |
| **Wave 2** | Parallel work (3 agents, Aug 6–20) |
| **Wave 3** | Sequential merging + integration |
| **File Orthogonal** | Zero overlap; each agent owns exclusive file domain |
| **TDD First** | Write failing tests before implementation code |
| **Feature Flag** | Cargo feature gates to enable gradual rollout |
| **Golden Rule** | No two agents modify the same file |

---

END OF PLAN
