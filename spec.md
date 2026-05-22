# Phase 25 SPEC — Behavioral Firewall: ReBAC + AP2 Policy Engine

**Status:** Design Review (Pre-Implementation)  
**Date:** 2026-05-22  
**Crate:** `siss-behavioral-firewall` (existing, to be expanded)  
**Priority:** CRITICAL (security-gating layer before scale)

---

## 1. Executive Summary

The SISS v2.0 system must not process any agent request, task dispatch, or consensus decision without first **verifying the mandate to act**. This phase implements a **Relationship-Based Access Control (ReBAC) + Attribute-Based Access Control (AP2) Policy Engine** that acts as an impenetrable behavioral firewall.

**Key Decision:** No scale without this layer. All agent actions, task assignments, and consent grants flow through mandatory policy evaluation.

---

## 1a. LOCKED Architectural Decisions (User-Approved)

### Decision 1: Relationship Persistence → **PostgreSQL-Backed** ✅
**Rationale:** Governance state cannot be volatile. Durability and queryability are non-negotiable. While in-memory graphs offer microsecond lookups, deterministic execution and governance layers require durable, auditable records that survive restarts. PostgreSQL ensures Fail-Closed semantics.

**Implementation:** ReBAC graph persisted to `siss_relationships` table with triggers for audit trail auto-logging.

### Decision 2: AP2 Attribute Source → **Cache-First** ✅
**Rationale:** High-velocity swarm orchestration (1000+ tasks/min) cannot afford database round-trips. 50µs cache hits are mandatory. Strict freshness windows (5-60s) mitigate staleness risks. Contingent on Decision 4 (immediate invalidation).

**Implementation:** `SovereignAttributeCache` with DashMap + TTL eviction. Invalidate on attribute mutations.

### Decision 3: Delegation Model → **Transitive with Cycle Detection** ✅
**Rationale:** Enterprise adoption requires transitive delegation (A → B → C) to mirror real org hierarchies. Phase 6 Delegation Chains specification mandates this. Direct-only delegation creates unacceptable operational friction. Enforce max depth = 3 to prevent infinite loops.

**Implementation:** Depth-first cycle detection on every delegation grant. Reject if depth > 3 or cycle detected.

### Decision 4: Cache Invalidation → **Immediate (Eager)** ✅
**Rationale:** 60-second TTL windows violate Zero-Trust architecture and Correctness Doctrine. If trust_level drops or a mandate is revoked, policy state must update instantly. Accept higher overhead on relationship churn to guarantee 100% consistency.

**Implementation:** On every relationship/attribute mutation, invalidate all cached decisions for that sovereign immediately (DashMap::clear_namespace).

### Decision 5: Audit Log Retention → **TTL + Archive (90-day hot, S3 cold)** ✅
**Rationale:** Indefinite hot logs in PostgreSQL degrade ReBAC query performance and cockpit latency. 90-day TTL keeps operational database lean. S3 cold storage preserves 100-year cryptographic paper trail required by AP2 Timestamp and Burn Protocol.

**Implementation:** Hot logs in `audit_log` table with 90-day expiry trigger. Daily batch export to S3 immutable archive.

---

## 2. Strategic Architecture

### 2.1 System Integration Points

```
Agent Request
    ↓
[MandateVerifier] ← evaluate policy
    ↓
   ✓ ALLOWED → dispatcher/task-router
   ✗ DENIED  → audit log + reject signal
```

**Three evaluation phases (all must pass):**
1. **ReBAC Phase:** Does the requester have the necessary *relationships* to agents/tasks/resources?
2. **AP2 Phase:** Do the requester's *attributes* satisfy policy predicates?
3. **Temporal Phase:** Is the request within valid time windows and not violating rate limits?

If ANY phase denies → request is **REJECTED** (fail-closed).

---

## 3. Core Traits & Types

### 3.1 MandateVerifier Trait

```rust
/// Unified mandate verification interface.
/// Evaluates whether an action should proceed based on ReBAC + AP2 + temporal constraints.
pub trait MandateVerifier: Send + Sync {
    /// Verify if an agent may perform an action on a resource.
    /// Returns Ok(Mandate) if approved, Err(DenyReason) if rejected.
    fn verify_mandate(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        resource: &PolicyResource,
        context: &RequestContext,
    ) -> Result<Mandate, DenyReason>;

    /// Async version for high-latency policy evaluations (external services, etc).
    async fn verify_mandate_async(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        resource: &PolicyResource,
        context: &RequestContext,
    ) -> Result<Mandate, DenyReason> {
        // Default: call sync version
        self.verify_mandate(requester, action, resource, context)
    }
}

/// Approval decision with audit trail.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Mandate {
    pub decision: AllowDeny,
    pub reasons: Vec<EvaluationReason>,
    pub expires_at: Option<Instant>,
    pub audit_id: Uuid,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AllowDeny {
    Allow,
    Deny,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DenyReason {
    ReBAC(String),                    // No required relationship found
    AP2(String),                      // Attribute predicate failed
    TemporalViolation(String),        // Outside valid window or rate limit exceeded
    AuditBlocked(String),             // Explicit audit flag
    Unknown(String),
}
```

### 3.2 PolicyEngine (Core Implementation)

```rust
/// Main policy evaluation engine. Composes ReBAC, AP2, and temporal rules.
pub struct PolicyEngine {
    rebac_graph: ReBAC,
    ap2_evaluator: AP2Evaluator,
    temporal_guard: TemporalGuard,
    audit_log: Arc<Mutex<Vec<AuditEntry>>>,
    decision_cache: Arc<DashMap<String, CachedDecision>>,
}

impl PolicyEngine {
    pub fn new(
        rebac_graph: ReBAC,
        ap2_evaluator: AP2Evaluator,
        temporal_guard: TemporalGuard,
    ) -> Self { ... }

    /// Evaluate all three phases in order.
    fn evaluate_mandate_internal(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        resource: &PolicyResource,
        context: &RequestContext,
    ) -> Result<Mandate, DenyReason> {
        // Phase 1: ReBAC — relationship verification
        let rebac_result = self.rebac_graph.verify_relationship(requester, resource, action)?;

        // Phase 2: AP2 — attribute evaluation
        let ap2_result = self.ap2_evaluator.evaluate(requester, action, context)?;

        // Phase 3: Temporal — time & rate constraints
        let temporal_result = self.temporal_guard.check(requester, action, context)?;

        // Combine results into Mandate
        Ok(Mandate {
            decision: AllowDeny::Allow,
            reasons: vec![
                EvaluationReason::ReBAC(rebac_result),
                EvaluationReason::AP2(ap2_result),
                EvaluationReason::Temporal(temporal_result),
            ],
            expires_at: temporal_result.expiration,
            audit_id: Uuid::new_v4(),
        })
    }
}

impl MandateVerifier for PolicyEngine {
    fn verify_mandate(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        resource: &PolicyResource,
        context: &RequestContext,
    ) -> Result<Mandate, DenyReason> {
        // Check cache first
        let cache_key = format!("{:?}:{:?}:{:?}", requester, action, resource);
        if let Some(cached) = self.decision_cache.get(&cache_key) {
            if !cached.expires_at.has_passed() {
                return Ok(cached.mandate.clone());
            }
        }

        // Evaluate fresh
        let mandate = self.evaluate_mandate_internal(requester, action, resource, context)?;

        // Cache for TTL
        self.decision_cache.insert(
            cache_key,
            CachedDecision {
                mandate: mandate.clone(),
                expires_at: Instant::now() + Duration::from_secs(60), // 60s cache TTL
            },
        );

        Ok(mandate)
    }
}
```

### 3.3 ReBAC Trait & Graph Model

```rust
/// Relationship-Based Access Control graph.
/// Models relationships (sovereign → agent, agent → task, etc.) and validates if
/// the requester has the necessary relationships to perform an action.
pub trait ReBAC {
    /// Check if requester has the required relationship to access resource.
    fn verify_relationship(
        &self,
        requester: &SovereignIdentity,
        resource: &PolicyResource,
        action: &PolicyAction,
    ) -> Result<String, DenyReason>;

    /// Enumerate all relationships a sovereign has with agents/tasks/resources.
    fn list_relationships(
        &self,
        requester: &SovereignIdentity,
    ) -> Vec<Relationship>;
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PolicyResource {
    Agent(Uuid),                   // Agent node
    Task(Uuid),                    // Task
    ConsentGrant(Uuid),            // Grant approval
    ArbitrationCycle(Uuid),        // Cycle healing decision
    FeedbackChannel(Uuid),         // Feedback route
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PolicyAction {
    // Agent lifecycle
    Spawn,
    Pause,
    Resume,
    Abort,
    Terminate,
    
    // Task dispatch
    AssignTask,
    CancelTask,
    FinalizeTask,
    
    // Consensus
    InitiateConsent,
    VoteConsent,
    RevokeGrant,
    
    // Observability
    ReadMetrics,
    StreamEvents,
    
    // Admin
    CreatePolicy,
    UpdatePolicy,
    DeletePolicy,
}

/// Relationship graph structure (in-memory + persistent).
pub struct ReBAC {
    graph: Arc<DashMap<SovereignIdentity, Vec<Relationship>>>,
    db: Arc<PgPool>, // For persistence
}

#[derive(Debug, Clone, Serialize, Deserialize, Hash, Eq, PartialEq)]
pub struct Relationship {
    pub from: SovereignIdentity,
    pub to: PolicyResource,
    pub rel_type: RelationType,
    pub created_at: Instant,
    pub expires_at: Option<Instant>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, Hash, Eq, PartialEq)]
pub enum RelationType {
    Owner,          // Full control over resource
    Operator,       // Can manage resource lifecycle
    Observer,       // Read-only access to metrics/events
    Delegate,       // Can grant permissions to others
    Participant,    // Can contribute to consensus
    Initiator,      // Initiated the resource
}

impl ReBAC {
    pub fn verify_relationship(
        &self,
        requester: &SovereignIdentity,
        resource: &PolicyResource,
        action: &PolicyAction,
    ) -> Result<String, DenyReason> {
        // Lookup requester's relationships
        let Some(relationships) = self.graph.get(requester) else {
            return Err(DenyReason::ReBAC(
                format!("No relationships found for {:?}", requester)
            ));
        };

        // Find matching relationship & validate action
        for rel in relationships.iter() {
            if rel.to == *resource && !rel.is_expired() {
                if Self::action_allowed_for_relation(action, rel.rel_type) {
                    return Ok(format!("{:?} permits {:?}", rel.rel_type, action));
                }
            }
        }

        Err(DenyReason::ReBAC(
            format!("No valid relationship to perform {:?} on {:?}", action, resource)
        ))
    }

    fn action_allowed_for_relation(action: &PolicyAction, rel_type: RelationType) -> bool {
        match (action, rel_type) {
            // Owner can do anything
            (_, RelationType::Owner) => true,
            
            // Operator can manage lifecycle
            (PolicyAction::Pause | PolicyAction::Resume | PolicyAction::Abort, RelationType::Operator) => true,
            (PolicyAction::AssignTask | PolicyAction::CancelTask, RelationType::Operator) => true,
            
            // Observer can only read
            (PolicyAction::ReadMetrics | PolicyAction::StreamEvents, RelationType::Observer) => true,
            
            // Delegate can grant perms
            (PolicyAction::CreatePolicy | PolicyAction::UpdatePolicy, RelationType::Delegate) => true,
            
            // Participant can vote
            (PolicyAction::VoteConsent, RelationType::Participant) => true,
            
            // Initiator can cancel their own work
            (PolicyAction::CancelTask | PolicyAction::Abort, RelationType::Initiator) => true,
            
            _ => false,
        }
    }
}
```

### 3.4 AP2 (Attribute-Based Access Control) Evaluator

```rust
/// Attribute-based policy evaluation.
pub struct AP2Evaluator {
    attribute_db: Arc<AttributeStore>,
    policy_rules: Arc<Vec<PolicyRule>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyRule {
    pub id: Uuid,
    pub name: String,
    pub predicate: AttributePredicate,
    pub applies_to: PolicyAction,
    pub priority: u32,
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AttributePredicate {
    TrustLevel(u32),
    ReputationScore(i32),
    SenioritySince(Instant),
    NotBlacklisted,
    HasCertification(String),
    And(Box<AttributePredicate>, Box<AttributePredicate>),
    Or(Box<AttributePredicate>, Box<AttributePredicate>),
    Not(Box<AttributePredicate>),
}

impl AP2Evaluator {
    pub fn evaluate(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        context: &RequestContext,
    ) -> Result<String, DenyReason> {
        let attributes = self.attribute_db.get_attributes(requester)?;
        let applicable_rules: Vec<_> = self.policy_rules
            .iter()
            .filter(|r| r.applies_to == *action && r.enabled)
            .collect();

        if applicable_rules.is_empty() {
            return Ok("No AP2 restrictions apply".to_string());
        }

        let mut sorted_rules = applicable_rules;
        sorted_rules.sort_by_key(|r| std::cmp::Reverse(r.priority));

        for rule in sorted_rules {
            if !self.evaluate_predicate(&rule.predicate, &attributes)? {
                return Err(DenyReason::AP2(
                    format!("Policy '{}' denied: {}", rule.name, rule.id)
                ));
            }
        }

        Ok("All AP2 policies satisfied".to_string())
    }

    fn evaluate_predicate(
        &self,
        predicate: &AttributePredicate,
        attributes: &SovereignAttributes,
    ) -> Result<bool, DenyReason> {
        match predicate {
            AttributePredicate::TrustLevel(required) => {
                Ok(attributes.trust_level >= *required)
            }
            AttributePredicate::ReputationScore(required) => {
                Ok(attributes.reputation >= *required)
            }
            AttributePredicate::SenioritySince(cutoff) => {
                Ok(attributes.joined_at <= *cutoff)
            }
            AttributePredicate::NotBlacklisted => {
                Ok(!attributes.blacklisted)
            }
            AttributePredicate::HasCertification(cert) => {
                Ok(attributes.certifications.contains(cert))
            }
            AttributePredicate::And(left, right) => {
                Ok(self.evaluate_predicate(left, attributes)? &&
                   self.evaluate_predicate(right, attributes)?)
            }
            AttributePredicate::Or(left, right) => {
                Ok(self.evaluate_predicate(left, attributes)? ||
                   self.evaluate_predicate(right, attributes)?)
            }
            AttributePredicate::Not(inner) => {
                Ok(!self.evaluate_predicate(inner, attributes)?)
            }
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SovereignAttributes {
    pub trust_level: u32,
    pub reputation: i32,
    pub joined_at: Instant,
    pub blacklisted: bool,
    pub certifications: Vec<String>,
    pub organization: Option<String>,
}
```

### 3.5 TemporalGuard

```rust
/// Temporal constraints: time windows, rate limits, and expiration.
pub struct TemporalGuard {
    rate_limiter: Arc<DashMap<SovereignIdentity, RateLimit>>,
    policy_windows: Arc<Vec<TimeWindow>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeWindow {
    pub id: Uuid,
    pub name: String,
    pub allowed_hours: Vec<(u8, u8)>,    // UTC (start_hour, end_hour) tuples
    pub blackout_dates: Vec<(u32, u32)>,  // (month, day) no operations allowed
    pub applies_to: PolicyAction,
}

#[derive(Debug, Clone)]
pub struct RateLimit {
    pub max_requests_per_minute: u32,
    pub requests: VecDeque<Instant>,
    pub last_check: Instant,
}

impl TemporalGuard {
    pub fn check(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        context: &RequestContext,
    ) -> Result<TemporalResult, DenyReason> {
        self.check_rate_limit(requester, action)?;
        self.check_time_window(action)?;
        
        Ok(TemporalResult {
            evaluation: "Temporal constraints satisfied".to_string(),
            expiration: Some(Instant::now() + Duration::from_secs(60)),
        })
    }
}

#[derive(Debug, Clone)]
pub struct TemporalResult {
    pub evaluation: String,
    pub expiration: Option<Instant>,
}
```

---

## 4. Integration Points

All policy checks gate critical operations:
- **Dispatcher:** Verify mandate before spawning agents
- **Task Router:** Verify mandate before assigning tasks
- **Consensus:** Verify mandate before recording votes
- **Feedback:** Verify mandate before routing feedback

---

## 5. Edge Cases

1. **Circular relationships:** Detect and reject cycles (max depth = 3)
2. **Temporal boundaries:** Use UTC only, never local time
3. **Deny-override rule:** One deny = entire request denied
4. **Cache invalidation:** Invalidate immediately on relationship changes
5. **Attribute freshness:** Re-fetch if older than 5 minutes

---

## 6. Crate Structure

```
crates/siss-behavioral-firewall/
├── src/
│   ├── lib.rs
│   ├── mandate_verifier.rs      ← MandateVerifier trait
│   ├── policy_engine.rs         ← PolicyEngine core
│   ├── rebac/mod.rs, graph.rs   ← ReBAC implementation
│   ├── ap2/mod.rs, evaluator.rs ← AP2 rules & evaluation
│   ├── temporal/mod.rs          ← Rate limiting & time windows
│   ├── audit.rs                 ← Audit logging
│   └── tests/
│       ├── rebac_tests.rs
│       ├── ap2_tests.rs
│       ├── temporal_tests.rs
│       └── integration_tests.rs
├── Cargo.toml
└── README.md
```

---

## 7. Test Strategy (TDD)

**Wave 1:** ReBAC relationship graph tests  
**Wave 2:** AP2 attribute evaluation tests + TemporalGuard  
**Wave 3:** Full PolicyEngine integration  
**Wave 4:** Edge case coverage + cycle detection

---

## 8. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Decision latency | <50ms (p99) |
| Cache hit rate | >80% |
| Audit completeness | 100% |
| Deny-override precision | 100% |
| Temporal accuracy | ±1 second |
| Scalability | 1000+ sovereigns |

---

## 9. Open Design Questions

1. **Relationship persistence:** In-memory or PostgreSQL?
2. **AP2 attribute source:** Cached or on-demand?
3. **Delegation depth:** Direct only or transitive?
4. **Cache invalidation:** Immediate or timeout-based?
5. **Audit retention:** Indefinite or TTL + archive?

---

**Status:** Ready for rigorous design review and user decisions on open questions.
