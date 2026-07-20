# TimeCapsule — Temporal Decision Analysis & Historical Governance Engine
## Time-Aware Policy Replay & Decision Forecasting v1.0

**Date:** 2026-06-04  
**Phase:** 3 Beta Launches (Aug 1+)  
**Status:** Specification Phase  
**Target Completion:** August 1, 2026  

---

## 1. Purpose & Mission

**Core Function:** Replay historical governance decisions and forecast future policy outcomes using temporal decision trees.

**Why This Works:**
- Decisions made under stress (war, crisis) often contradict later decisions in calm periods
- Current governance has no temporal awareness — policies are "frozen in time"
- TimeCapsule enables **historical governance continuity**: "What would this policy have decided in 2023?"
- Critical for AI safety: detect policy drift over time, prove governance consistency

**Success Metric (by Sept 15):**
- 100% decision replay accuracy (every decision reproducible with same timestamp)
- <50ms latency per historical query
- Governance drift detection (policy changes flagged if >10% behavior change)
- Used in 100+ Ukraine/Israel trust mesh verification scenarios

---

## 2. Architecture & Design

### 2.1 Temporal Decision Trees

**Concept:** A decision tree captures governance state at point-in-time. Replay by "walking" the tree with historical context.

```
                    Root (policy_version=1, timestamp=2026-01-01)
                    /
            Is AP2_Settlement?
            /              \
          YES              NO
          /                 \
    Is Value > $100K?      Is Escalation?
    /        \             /           \
   YES       NO          YES           NO
   /         \           /             \
Allow      Audit    Quarantine    Allow
(99%)      (1%)     (90%)         (100%)
```

Each path captures:
- **Conditions:** (Field, Operator, Value) tuples
- **Actions:** (Decision type, Confidence, Timestamp)
- **Metadata:** (Policy version, Author, Approval timestamp)

### 2.2 Components Overview

```
┌─────────────────────────────────────────────┐
│ TimeCapsule System Architecture             │
├─────────────────────────────────────────────┤
│                                             │
│  1. Temporal Index                          │
│     └─ Maps timestamp → policy_version      │
│                                             │
│  2. Decision Tree Store                     │
│     └─ Immutable trees (one per version)    │
│                                             │
│  3. Replay Engine                           │
│     └─ Walk tree with historical context    │
│                                             │
│  4. Drift Detector                          │
│     └─ Compare trees across time            │
│                                             │
│  5. Forecaster                              │
│     └─ Predict future decisions             │
│                                             │
│  6. Audit Trail                             │
│     └─ Merkle-linked decision history       │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 3. Core Components

### 3.1 Temporal Index

**Purpose:** Map timestamps to policy versions for fast replay lookup.

```rust
pub struct TemporalIndex {
    pub entries: BTreeMap<SystemTime, PolicyVersion>,
    pub version_id: Uuid,
    pub immutable: bool,
}

pub struct PolicyVersion {
    pub version_id: Uuid,
    pub timestamp: SystemTime,      // When this policy became active
    pub decision_tree: DecisionTree,
    pub author: SovereignIdentity,
    pub approval_signature: Ed25519Signature,
    pub merkle_root: String,        // Link to previous version
}

impl TemporalIndex {
    /// Lookup policy version at any point in time
    pub fn policy_at(&self, timestamp: SystemTime) -> Option<&PolicyVersion> {
        // Find the latest version ≤ timestamp
        self.entries
            .range(..=timestamp)
            .next_back()
            .map(|(_, v)| v)
    }
    
    /// List all policy transitions in time range
    pub fn transitions(&self, start: SystemTime, end: SystemTime) -> Vec<(SystemTime, Uuid)> {
        self.entries
            .range(start..=end)
            .map(|(t, v)| (*t, v.version_id))
            .collect()
    }
}
```

**Index Size Projections:**
- 1K policy versions over 5 years
- ~10KB per version metadata
- Total: ~10MB (in-memory, < 1 sec to load)
- Query time: O(log N) binary search → <1µs

**Storage Strategy:**
- SQLite immutable append-only table
- One row per policy version
- Indexed by timestamp (clustered)
- Compressed: ~1MB for 5 years of policies

---

### 3.2 Decision Tree Engine

**Purpose:** Represent governance logic as executable tree; support replay + audit.

```rust
pub enum TreeNode {
    Condition {
        field: String,              // e.g., "ap2_settlement.value"
        operator: ComparisonOp,     // <, >, ==, >=, <=, in
        value: serde_json::Value,
        true_branch: Box<TreeNode>,
        false_branch: Box<TreeNode>,
    },
    Decision {
        action: PolicyAction,       // Allow, Quarantine, CircuitBreaker, etc.
        confidence: f32,            // 0.0-1.0
        reasoning: String,          // "Value exceeds AP2 threshold"
    },
}

pub struct DecisionTree {
    pub tree_id: Uuid,
    pub root: TreeNode,
    pub version: u32,
    pub created_at: SystemTime,
    pub approved_by: Vec<SovereignIdentity>,  // Multi-sig
    pub merkle_root: String,
}

impl DecisionTree {
    /// Walk the tree with context; return decision
    pub fn evaluate(
        &self,
        context: &EvaluationContext,
    ) -> Result<(PolicyAction, String), TreeError> {
        self.root.evaluate(context)
    }
    
    /// Extract all paths from root to decision
    pub fn all_paths(&self) -> Vec<(Vec<(String, String, String)>, PolicyAction)> {
        // Returns: (condition path, final decision)
    }
    
    /// Serialize tree to immutable JSON for audit
    pub fn to_immutable_json(&self) -> String {
        serde_json::to_string(self).expect("valid JSON")
    }
}

pub struct EvaluationContext {
    pub sovereign_id: Uuid,
    pub action: AgentAction,
    pub timestamp: SystemTime,      // Critical: use historical timestamp for replay
    pub tier: u32,
    pub trust_level: u32,
    pub historical_actions: u32,
}
```

**Decision Tree Build Example:**

```rust
let tree = DecisionTree {
    root: TreeNode::Condition {
        field: "ap2_settlement.value".to_string(),
        operator: ComparisonOp::GreaterThan,
        value: json!(100_000),
        true_branch: Box::new(
            TreeNode::Condition {
                field: "requester.tier".to_string(),
                operator: ComparisonOp::GreaterThanOrEqual,
                value: json!(7),
                true_branch: Box::new(
                    TreeNode::Decision {
                        action: PolicyAction::Allow,
                        confidence: 0.95,
                        reasoning: "Tier 7+ can settle large amounts".to_string(),
                    }
                ),
                false_branch: Box::new(
                    TreeNode::Decision {
                        action: PolicyAction::Quarantine,
                        confidence: 0.9,
                        reasoning: "Large settlement by low-tier sovereign".to_string(),
                    }
                ),
            }
        ),
        false_branch: Box::new(
            TreeNode::Decision {
                action: PolicyAction::Allow,
                confidence: 0.99,
                reasoning: "Low-value settlements auto-approved".to_string(),
            }
        ),
    },
    // ... rest of tree
};
```

---

### 3.3 Replay Engine

**Purpose:** Given a historical action + timestamp, replay the decision that would have been made then.

```rust
pub struct ReplayRequest {
    pub action: AgentAction,
    pub timestamp: SystemTime,      // "What would we have decided on 2024-06-15?"
    pub include_path: bool,         // Return decision path through tree?
}

pub struct ReplayResult {
    pub original_decision: PolicyAction,
    pub historical_decision: PolicyAction,
    pub match_percentage: f32,      // 0.0-1.0 (how closely do they match?)
    pub policy_version_at_time: Uuid,
    pub decision_path: Option<Vec<(String, String, String)>>,  // Condition chain
    pub timestamp_decision_made: SystemTime,
    pub reasoning: String,
}

pub async fn replay_decision(
    req: &ReplayRequest,
    index: &TemporalIndex,
) -> Result<ReplayResult, ReplayError> {
    // 1. Lookup policy version at request.timestamp
    let policy = index
        .policy_at(req.timestamp)
        .ok_or(ReplayError::NoVersionAtTime)?;
    
    // 2. Create evaluation context with historical timestamp
    let ctx = EvaluationContext {
        timestamp: req.timestamp,  // ← KEY: Use historical timestamp
        ..Default::default()
    };
    
    // 3. Walk tree with historical context
    let (historical_decision, reasoning) = policy.decision_tree.evaluate(&ctx)?;
    
    // 4. Compare vs. original decision
    let match_percentage = compute_match_score(&historical_decision, &req.action);
    
    Ok(ReplayResult {
        historical_decision,
        match_percentage,
        policy_version_at_time: policy.version_id,
        decision_path: if req.include_path {
            Some(extract_path(&policy.decision_tree, &ctx))
        } else {
            None
        },
        timestamp_decision_made: SystemTime::now(),
        reasoning,
    })
}
```

**Use Case Example: Ukraine Trust Mesh Verification**

```
Query: "On June 15, 2024, at 14:32 UTC, did we approve this aid transfer?"

Historical Request:
{
  "action": "ap2_settlement.execute(...)",
  "value": 50_000,
  "recipient": "NGO-Ukraine-001",
  "timestamp": "2024-06-15T14:32:00Z"
}

Replay Result:
{
  "original_decision": "Allow",
  "historical_decision": "Allow",
  "match_percentage": 1.0,
  "policy_version_at_time": "policy-2024-06-01-v3",
  "decision_path": [
    ("ap2_settlement.value > 10_000", "true"),
    ("recipient.tier >= 5", "true"),
    ("daily_budget_remaining > value", "true"),
  ],
  "reasoning": "Tier 5+ NGO, budget available, value approved"
}

Conclusion: This decision is consistent with June 2024 policy (100% match).
Immutable proof generated for ICC war crimes investigation.
```

---

### 3.4 Governance Drift Detector

**Purpose:** Detect when policy changes would have altered historical decisions (governance evolution tracking).

```rust
pub struct DriftAnalysis {
    pub policy_version_old: Uuid,
    pub policy_version_new: Uuid,
    pub timestamp_old: SystemTime,
    pub timestamp_new: SystemTime,
    pub drift_score: f32,           // 0.0-1.0, 0=identical, 1.0=complete divergence
    pub affected_decisions: Vec<PolicyAction>,  // Decisions that would flip
    pub affected_count: usize,      // How many historical decisions would differ?
    pub affected_pct: f32,          // What % of decisions would flip?
}

pub async fn compute_drift(
    version_old: &PolicyVersion,
    version_new: &PolicyVersion,
    sample_size: usize = 1000,  // Test against 1K synthetic historical actions
) -> Result<DriftAnalysis, DriftError> {
    // 1. Generate synthetic historical actions (1K random variations)
    let synthetic_actions = generate_synthetic_actions(sample_size);
    
    // 2. Evaluate all actions with OLD policy
    let old_decisions: Vec<_> = synthetic_actions
        .iter()
        .filter_map(|action| {
            let ctx = EvaluationContext { /* ... */ };
            version_old.decision_tree.evaluate(&ctx).ok()
        })
        .collect();
    
    // 3. Evaluate same actions with NEW policy
    let new_decisions: Vec<_> = synthetic_actions
        .iter()
        .filter_map(|action| {
            let ctx = EvaluationContext { /* ... */ };
            version_new.decision_tree.evaluate(&ctx).ok()
        })
        .collect();
    
    // 4. Compare: count mismatches
    let mismatches = old_decisions
        .iter()
        .zip(&new_decisions)
        .filter(|(old, new)| old != new)
        .count();
    
    let drift_score = mismatches as f32 / sample_size as f32;
    
    Ok(DriftAnalysis {
        policy_version_old: version_old.version_id,
        policy_version_new: version_new.version_id,
        drift_score,
        affected_count: mismatches,
        affected_pct: drift_score * 100.0,
        // ... other fields
    })
}
```

**Drift Thresholds & Alerts:**

| Drift Score | Severity | Action |
|------------|----------|--------|
| 0.0 - 0.05 | None | No alert; policy refinement |
| 0.05 - 0.10 | Low | Info log; track for review |
| 0.10 - 0.25 | Medium | Email governance council; flag decisions made under new policy |
| 0.25 - 0.50 | High | Trigger governance review; hold new decisions for manual approval |
| > 0.50 | Critical | Automatic rollback to previous policy; notify all sovereigns |

**Test Case:**
```
Policy v1 (Jan 2024): Allow all tier 5+ settlements
Policy v2 (Jun 2024): Require 3-day verification for > $10K

Drift Analysis:
- Test 1K historical actions against both policies
- 150 actions (15%) would flip from Allow → Quarantine
- Drift score: 0.15 (Medium severity)
- Alert: Email governance council, request re-approval for affected decisions
```

---

### 3.5 Decision Forecaster

**Purpose:** Predict future policy decisions based on historical trends + forecasted context.

```rust
pub struct ForecastRequest {
    pub action: AgentAction,
    pub forecast_timestamp: SystemTime,  // "What will policy say on 2026-12-31?"
    pub scenario: Option<String>,        // "what if tier system changes?"
}

pub struct ForecastResult {
    pub forecast_decision: PolicyAction,
    pub confidence: f32,                 // 0.0-1.0
    pub reasoning: String,
    pub policy_version_if_available: Option<Uuid>,  // If policy published by then
    pub assumption_notes: String,        // "Assumes tier system continues..."
}

pub async fn forecast_decision(
    req: &ForecastRequest,
    index: &TemporalIndex,
    drift_history: &[DriftAnalysis],
) -> Result<ForecastResult, ForecastError> {
    // 1. Find most recent policy
    let latest_policy = index.latest_policy();
    
    // 2. Analyze historical drift trends (1-year, 6-month, 3-month slopes)
    let drift_trajectory = analyze_drift_trajectory(drift_history);
    
    // 3. Project policy forward
    let projected_policy = project_policy(&latest_policy, &drift_trajectory, req.forecast_timestamp);
    
    // 4. Evaluate action against projected policy
    let (forecast_decision, reasoning) = projected_policy.decision_tree.evaluate(&ctx)?;
    
    Ok(ForecastResult {
        forecast_decision,
        confidence: 0.6 + (drift_trajectory.stability_score * 0.4),  // High if policy is stable
        reasoning,
        assumption_notes: "Assumes no major policy changes; based on 1-year trend analysis".to_string(),
    })
}

fn project_policy(
    current: &PolicyVersion,
    drift_trajectory: &DriftTrajectory,
    future_timestamp: SystemTime,
) -> ProjectedPolicy {
    // Use historical drift pattern to predict likely policy changes
    // E.g., if drift is +0.02/month, project new policy 6 months out as +0.12 drift
    
    // If drift trajectory is flat/stable → high confidence in projection
    // If drift trajectory is increasing → low confidence (policy becoming volatile)
    
    // Return both "most likely" policy AND "confidence interval"
}
```

**Use Case: Market Vision Briefing**

```
Forecast Query: "What governance constraints will affect September trading?"

Result:
{
  "forecast_decision": "Tier 6+ can execute 100K+ settlements",
  "confidence": 0.92,
  "reasoning": "June policy already allows this; 6-month drift trend is stable",
  "policy_version_if_available": null,  // Not published yet; forecasted
  "assumption_notes": "Assumes Ukraine emergency measures stay in effect"
}

Market Vision Briefing Output:
"Trading constraints for Sept: Tier 6+, settlements <100K auto-approve.
Confidence in this forecast: 92% (based on 6-month policy stability).
Constraint dates: 2026-09-01 to 2026-09-30."
```

---

### 3.6 Immutable Audit Trail

**Purpose:** Merkle-linked historical record of all decisions + policy versions.

```rust
pub struct AuditEntry {
    pub audit_id: Uuid,
    pub decision_id: Uuid,
    pub original_decision: PolicyAction,
    pub historical_decision: PolicyAction,
    pub policy_version: Uuid,
    pub timestamp: SystemTime,
    pub sovereign_id: Uuid,
    pub merkle_root: String,        // Link to previous entry
    pub signature: Ed25519Signature,
}

impl AuditEntry {
    pub fn verify(&self, previous: &AuditEntry) -> bool {
        // Verify Merkle chain:
        // merkle_root = HASH(previous.merkle_root + self.fields)
        let expected_root = compute_merkle_root(&previous.merkle_root, self);
        expected_root == self.merkle_root
    }
}

pub struct AuditLog {
    pub entries: Vec<AuditEntry>,
    pub head: String,               // Latest merkle root
}

impl AuditLog {
    /// Verify entire chain integrity (O(n) but batch-verifiable)
    pub fn verify_chain(&self) -> bool {
        self.entries
            .windows(2)
            .all(|pair| pair[1].verify(&pair[0]))
    }
    
    /// Export immutable snapshot for ICC / legal proceedings
    pub fn export_immutable_snapshot(
        &self,
        start: SystemTime,
        end: SystemTime,
    ) -> Result<ImmutableSnapshot, ExportError> {
        let filtered = self.entries
            .iter()
            .filter(|e| e.timestamp >= start && e.timestamp <= end)
            .collect();
        
        Ok(ImmutableSnapshot {
            entries: filtered,
            merkle_root_start: self.entries[0].merkle_root.clone(),
            merkle_root_end: self.head.clone(),
            verified: true,
        })
    }
}
```

---

## 4. Implementation Plan

### Phase 3a: Core Modules (Weeks 1-2, Aug 1-14)

**Week 1: Modules 3.1 + 3.2**
- [ ] `siss-time-capsule/src/temporal_index.rs` — 300 LOC
  - BTreeMap-based index
  - Policy version lookup
  - Transition tracking
  - 8 unit tests
- [ ] `siss-time-capsule/src/decision_tree.rs` — 500 LOC
  - TreeNode enum + evaluation
  - Path extraction
  - Multi-sig approval
  - 15 unit tests

**Week 2: Modules 3.3 + 3.4**
- [ ] `siss-time-capsule/src/replay_engine.rs` — 400 LOC
  - Replay with historical timestamp
  - Decision path tracking
  - Match scoring
  - 12 unit tests
- [ ] `siss-time-capsule/src/drift_detector.rs` — 350 LOC
  - Synthetic action generation
  - Decision comparison
  - Drift scoring
  - 10 unit tests
- [ ] `siss-time-capsule/src/forecaster.rs` — 300 LOC
  - Drift trajectory analysis
  - Policy projection
  - Confidence scoring
  - 8 unit tests
- [ ] `siss-time-capsule/src/audit_trail.rs` — 250 LOC
  - Merkle-linked entries
  - Chain verification
  - Snapshot export
  - 8 unit tests

**Success Criteria:**
- [ ] All 61 tests passing
- [ ] Decision replay accuracy: 100%
- [ ] Drift detection: <50ms latency
- [ ] Audit chain: Cryptographically verified

### Phase 3b: Integration (Weeks 3-4, Aug 15-28)

**Week 3: Integration with Gatekeeper + Behavioral Firewall**
- [ ] Wire `replay_engine` into mandate verification
- [ ] Historical decision auditing
- [ ] 15 integration tests

**Week 4: Beta Readiness**
- [ ] Real-world policy scenarios (Ukraine, Israel)
- [ ] Drift detection on 6-month policy history
- [ ] Forecasting accuracy validation
- [ ] Documentation

---

## 5. Test Suite

### Unit Tests (61 total)

**temporal_index.rs (8 tests)**
```
✓ test_policy_lookup_at_timestamp
✓ test_policy_lookup_before_first_version
✓ test_policy_lookup_after_latest_version
✓ test_transitions_in_range
✓ test_immutable_index_prevents_modification
✓ test_index_binary_search_performance
✓ test_multiple_versions_same_timestamp
✓ test_index_serialization_roundtrip
```

**decision_tree.rs (15 tests)**
```
✓ test_evaluate_simple_condition
✓ test_evaluate_nested_conditions
✓ test_all_paths_extraction
✓ test_multi_sig_approval_required
✓ test_tree_to_immutable_json
✓ test_tree_evaluation_with_context
✓ test_confidence_score_propagation
✓ test_reasoning_generation
... [7 more]
```

**replay_engine.rs (12 tests)**
```
✓ test_replay_historical_decision_exact_match
✓ test_replay_before_policy_exists_error
✓ test_replay_after_policy_change_detects_drift
✓ test_decision_path_extraction
✓ test_match_percentage_computation
✓ test_concurrent_replays_isolation
✓ test_1000_replays_per_sec_throughput
... [5 more]
```

**drift_detector.rs (10 tests)**
```
✓ test_identical_policies_zero_drift
✓ test_policy_change_detects_drift
✓ test_drift_score_bounds_0_to_1
✓ test_affected_decisions_identification
✓ test_affected_percentage_computation
✓ test_synthetic_action_generation_quality
... [4 more]
```

**forecaster.rs (8 tests)**
```
✓ test_stable_policy_high_confidence_forecast
✓ test_volatile_policy_low_confidence_forecast
✓ test_drift_trajectory_analysis
✓ test_policy_projection_forward_6_months
✓ test_forecast_without_future_policy_version
... [3 more]
```

**audit_trail.rs (8 tests)**
```
✓ test_audit_entry_merkle_chain_integrity
✓ test_full_chain_verification
✓ test_tamper_detection_fails_verification
✓ test_snapshot_export_date_range
✓ test_immutable_snapshot_properties
... [3 more]
```

### Integration Tests (15 tests)

```
✓ test_replay_with_gatekeeper_mandate_verification
✓ test_historical_decision_auditing
✓ test_drift_triggers_governance_alert
✓ test_critical_drift_triggers_rollback
✓ test_forecaster_used_by_market_vision
✓ test_ukraine_ngo_aid_trace_verification
✓ test_israel_civil_defense_historical_validation
✓ test_6_month_policy_history_replay
... [7 more]
```

---

## 6. Success Criteria & Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| **Replay Accuracy** | 100% (bit-for-bit match) | Unit tests |
| **Latency (Replay)** | <50ms per query | Benchmark |
| **Latency (Drift)** | <100ms for 1K action analysis | Benchmark |
| **Drift Detection** | 100% (all policy changes detected) | Unit tests |
| **Chain Integrity** | 100% (all entries verified) | Cryptographic verification |
| **Forecast Accuracy** | 90%+ (validate vs. actual later policy) | Historical backtesting |
| **Storage Size** | <50MB per year of policy history | Storage audit |
| **Concurrent Access** | 1000 replays/sec, zero interference | Load test |

---

## 7. Governance Gates

**Gate 1 (Aug 1):** Spec approved, decision tree format locked → proceed to Week 1

**Gate 2 (Aug 14):** Unit tests 61/61 passing, latency <50ms → proceed to integration

**Gate 3 (Aug 28):** Integration tests 15/15 passing, drift detection validated → proceed to beta

**Gate 4 (Sept 1):** Real-world scenarios tested (Ukraine, Israel), chain integrity verified → GA approval

---

**Prepared for:** Phase 3 Beta Launches (Aug 1+)  
**Architecture Lock:** Immutable decision trees, Merkle-linked audit trail, BTreeMap temporal index  
**Next Phase:** Market Vision (temporal-aware briefing generation)
