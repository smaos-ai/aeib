# Phase 25 HANDOFF — Behavioral Firewall: ReBAC + AP2 Policy Engine

**Date:** 2026-05-22  
**Status:** Ready for Implementation (TDD)  
**Crate:** `siss-behavioral-firewall` (expand existing)  
**Wave Structure:** Sequential (Wave 1) → Parallel (Wave 2, 3 agents) → Sequential (Wave 3)

---

## Overview

5 atomic tasks across 3 waves. Each task owns distinct file domains (zero merge conflicts).

**Architectural Decisions (LOCKED):**
- **Decision 1:** PostgreSQL-backed ReBAC (durable governance state)
- **Decision 2:** Cache-first AP2 attributes (50µs lookups, immediate invalidation)
- **Decision 3:** Transitive delegation with cycle detection (max depth 3)
- **Decision 4:** Immediate cache invalidation (100% consistency guarantee)
- **Decision 5:** TTL + Archive audit logs (90-day hot, S3 cold storage)

---

## Task 1: ReBAC Foundation & PostgreSQL Persistence *(Wave 1 — Sequential)*

**Goal:** Build ReBAC graph, PostgreSQL schema, and relationship lifecycle.

**Owns:**
- `crates/siss-behavioral-firewall/src/rebac/mod.rs` (create)
- `crates/siss-behavioral-firewall/src/rebac/graph.rs` (create)
- `crates/siss-behavioral-firewall/src/rebac/relationship.rs` (create)
- `crates/siss-behavioral-firewall/src/rebac/queries.rs` (create)
- `crates/siss-behavioral-firewall/src/lib.rs` (modify: add pub mod rebac)
- `migrations/001_create_relationships_table.sql` (create)

**Key Types:**
```rust
pub enum RelationType {
    Owner,      // Full control
    Operator,   // Lifecycle management
    Observer,   // Read-only
    Delegate,   // Grant permissions
    Participant,// Consensus voting
    Initiator,  // Resource creator
}

pub struct Relationship {
    pub id: Uuid,
    pub from: SovereignIdentity,
    pub to_resource: PolicyResource,
    pub rel_type: RelationType,
    pub created_at: SystemTime,
    pub expires_at: Option<SystemTime>,
}
```

**PostgreSQL Schema:**
```sql
CREATE TABLE relationships (
    id UUID PRIMARY KEY,
    from_sovereign UUID NOT NULL,
    to_resource_type TEXT NOT NULL,
    to_resource_id UUID NOT NULL,
    relationship_type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE relationship_audit (
    id BIGSERIAL PRIMARY KEY,
    relationship_id UUID REFERENCES relationships(id),
    event_type TEXT NOT NULL,
    event_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_relationships_from ON relationships(from_sovereign);
CREATE INDEX idx_relationships_expires ON relationships(expires_at);
```

**Tests (12+):**
- Grant relationship (success + duplicate error)
- Revoke relationship
- Verify relationship with action mapping
- Expired relationships filtered
- List relationships for sovereign
- Action mapping per RelationType

**Success Criteria:**
- [ ] `cargo check -p siss-behavioral-firewall` passes
- [ ] `cargo test -p siss-behavioral-firewall` 12/12 ✓
- [ ] No clippy warnings
- [ ] PostgreSQL schema compiles (sqlx prepare)

---

## Task 2: AP2 Evaluator + Sovereign Attribute Cache *(Wave 2 — Parallel)*

**Goal:** Build AP2 policy engine and cache-first attribute store.

**Owns:**
- `crates/siss-behavioral-firewall/src/ap2/mod.rs` (create)
- `crates/siss-behavioral-firewall/src/ap2/evaluator.rs` (create)
- `crates/siss-behavioral-firewall/src/ap2/attribute_store.rs` (create)
- `crates/siss-behavioral-firewall/src/ap2/rules.rs` (create)
- `crates/siss-behavioral-firewall/src/lib.rs` (modify: add pub mod ap2)
- `migrations/002_create_attributes_tables.sql` (create)

**Key Types:**
```rust
pub enum AttributePredicate {
    TrustLevel(u32),
    ReputationScore(i32),
    SenioritySince(SystemTime),
    NotBlacklisted,
    HasCertification(String),
    And(Box<AttributePredicate>, Box<AttributePredicate>),
    Or(Box<AttributePredicate>, Box<AttributePredicate>),
    Not(Box<AttributePredicate>),
}

pub struct SovereignAttributes {
    pub trust_level: u32,    // 0-100
    pub reputation: i32,
    pub joined_at: SystemTime,
    pub blacklisted: bool,
    pub certifications: Vec<String>,
}

pub struct SovereignAttributeCache {
    cache: Arc<DashMap<Uuid, CachedAttribute>>,
    freshness_window: Duration, // 5 minutes
}
```

**Tests (15+):**
- Attribute cache hit + miss
- Freshness window (>5min → re-fetch)
- Invalidation on demand
- All AttributePredicate variants
- Priority-ordered rule evaluation
- Deny-override rule

**Success Criteria:**
- [ ] `cargo test -p siss-behavioral-firewall` 15+ ✓
- [ ] Cache freshness enforced (5-minute window)
- [ ] Immediate invalidation working
- [ ] No clippy warnings

---

## Task 3: TemporalGuard + Rate Limiting *(Wave 2 — Parallel)*

**Goal:** Implement rate limiting (60 req/min), UTC time windows, blackout dates.

**Owns:**
- `crates/siss-behavioral-firewall/src/temporal/mod.rs` (create)
- `crates/siss-behavioral-firewall/src/temporal/guard.rs` (create)
- `crates/siss-behavioral-firewall/src/temporal/rate_limiter.rs` (create)
- `crates/siss-behavioral-firewall/src/temporal/window_checker.rs` (create)
- `crates/siss-behavioral-firewall/src/lib.rs` (modify: add pub mod temporal)

**Key Types:**
```rust
pub struct TemporalGuard {
    rate_limiter: Arc<DashMap<Uuid, RateLimit>>,
    time_windows: Arc<Vec<TimeWindow>>,
}

pub struct TimeWindow {
    pub applies_to: PolicyAction,
    pub allowed_hours: Vec<(u8, u8)>,      // UTC only
    pub blackout_dates: Vec<(u32, u32)>,   // (month, day)
}
```

**Rate Limit Logic:**
- 60 requests per minute per sovereign
- Sliding window (old requests expire after 60s)
- In-memory (DashMap), no DB

**Time Windows:**
- UTC only (chrono::Utc)
- Allowed hours: (0-23, 0-23)
- Blackout dates: (1-12, 1-31)

**Tests (12+):**
- Rate limit (60 allowed, 61st denied)
- Sliding window expiry
- Time window enforcement (allowed hours)
- Blackout date blocking
- UTC-only (no Local time)
- Multiple sovereigns isolated

**Success Criteria:**
- [ ] `cargo test -p siss-behavioral-firewall` 12+ ✓
- [ ] Rate limiter thread-safe (DashMap)
- [ ] All time ops use UTC
- [ ] No clippy warnings

---

## Task 4: PolicyEngine Composition + Cycle Detection *(Wave 2 — Parallel)*

**Goal:** Wire ReBAC, AP2, TemporalGuard. Add cycle detection and decision cache.

**Owns:**
- `crates/siss-behavioral-firewall/src/policy_engine.rs` (create)
- `crates/siss-behavioral-firewall/src/mandate_verifier.rs` (create)
- `crates/siss-behavioral-firewall/src/cycle_detection.rs` (create)
- `crates/siss-behavioral-firewall/src/cache.rs` (create)
- `crates/siss-behavioral-firewall/src/lib.rs` (modify: export + pub trait MandateVerifier)

**Key Types:**
```rust
pub trait MandateVerifier: Send + Sync {
    fn verify_mandate(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        resource: &PolicyResource,
        context: &RequestContext,
    ) -> Result<Mandate, DenyReason>;
}

pub enum AllowDeny {
    Allow,
    Deny,
}

pub struct Mandate {
    pub decision: AllowDeny,
    pub reasons: Vec<String>,
    pub audit_id: Uuid,
}

pub enum DenyReason {
    ReBAC(String),
    AP2(String),
    TemporalViolation(String),
    Unknown(String),
}
```

**Three-Phase Evaluation:**
1. ReBAC: Verify relationship
2. AP2: Evaluate attributes
3. Temporal: Check rate limit + time window
→ **All must pass. One deny = entire deny.**

**Cycle Detection (DFS):**
- Max depth = 3
- Reject if cycle found
- RelationType::Delegate only

**Decision Cache:**
- DashMap-based key="{requester}:{action}:{resource}"
- Invalidate immediately on relationship changes
- Atomic invalidation per sovereign

**Tests (18+):**
- Three-phase evaluation (all pass → Allow)
- One phase fails → Deny
- Decision cache hit + miss
- Immediate invalidation
- Cycle detection (DFS, max depth 3)
- Audit ID generation
- All DenyReason variants

**Success Criteria:**
- [ ] `cargo test -p siss-behavioral-firewall` 18+ ✓
- [ ] All three phases evaluated in order
- [ ] Deny-override rule (one deny = deny all)
- [ ] Cycle detection working (max depth 3)
- [ ] Cache invalidation immediate
- [ ] No clippy warnings

---

## Task 5: Audit Logging + S3 Archive Export *(Wave 3 — Sequential)*

**Goal:** Build audit logging and 90-day TTL + S3 archive export.

**Owns:**
- `crates/siss-behavioral-firewall/src/audit.rs` (create)
- `crates/siss-behavioral-firewall/src/archive.rs` (create)
- `crates/siss-behavioral-firewall/src/lib.rs` (modify: add pub mod audit, pub mod archive)
- `migrations/003_create_audit_tables.sql` (create)

**Audit Schema:**
```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    audit_id UUID UNIQUE,
    requester UUID NOT NULL,
    action TEXT NOT NULL,
    decision TEXT NOT NULL, -- 'Allow' or 'Deny'
    reasons JSONB NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '90 days'
);

CREATE INDEX idx_audit_expires ON audit_log(expires_at);
```

**Audit Entry:**
```rust
pub struct AuditEntry {
    pub audit_id: Uuid,
    pub requester: SovereignIdentity,
    pub action: PolicyAction,
    pub resource: PolicyResource,
    pub decision: AllowDeny,
    pub reasons: Vec<String>,
    pub timestamp: SystemTime,
}
```

**S3 Archive Export:**
- Format: JSONL + gzip
- Trigger: 90-day expiry
- Delete from hot storage after export
- Immutable append-only S3 storage

**Tests (10+):**
- AuditEntry creation (Allow + Deny)
- Audit log insertion
- S3 export (mock client)
- JSONL compression
- 90-day TTL enforcement
- Deletion after export

**Success Criteria:**
- [ ] `cargo test -p siss-behavioral-firewall` 10+ ✓
- [ ] Audit logs to PostgreSQL
- [ ] S3 export working (gzipped JSONL)
- [ ] 90-day TTL + delete working
- [ ] No clippy warnings

---

## Wave Execution Plan

```
Wave 1 (Sequential)
└─ Task 1: ReBAC Foundation
   └─ GATE: Tests pass + schema valid
   
Wave 2 (Parallel — 3 agents)
├─ Task 2: AP2 Evaluator
├─ Task 3: TemporalGuard
└─ Task 4: PolicyEngine + Cycle Detection
   └─ GATE: All three tasks merge clean
   
Wave 3 (Sequential)
└─ Task 5: Audit + Archive
   └─ Complete: All tests pass
```

---

## Final Merge & Completion

After all 5 tasks:
1. Merge Wave 1 → main
2. Merge Wave 2 (Tasks 2, 3, 4 topologically) → main
3. Merge Wave 3 (Task 5) → main
4. Final: `git commit -m "Phase 25: Behavioral Firewall complete — ReBAC+AP2 policy engine active"`

**Success Metrics:**
- [ ] All 55+ tests passing
- [ ] `cargo clippy --all -- -D warnings` zero warnings
- [ ] SPEC.md locked with architectural decisions
- [ ] HANDOFF.md complete + verified
- [ ] EXEC_LOG.json updated with Phase 25 checkpoint
- [ ] Dispatcher/Router integration hooks ready (not wired yet)

---

**Status:** Ready to begin Wave 1 implementation (Task 1: ReBAC Foundation).
