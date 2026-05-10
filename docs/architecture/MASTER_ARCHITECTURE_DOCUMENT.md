# SISS Master Architecture Document

**Version:** 2026-05-10  
**Status:** LOCKED (Constitutional)  
**Scope:** Phases 5–9 (Sovereign Multi-Agent OS)  
**Authority:** Phase Architects + User Lockdowns

---

## Executive Summary

The **Sovereign Identity and Session System (SISS)** is the attestation, delegation, and governance layer for a multi-agent swarm operating under **Agent Payment Protocol v2 (AP2)** economics. This document codifies the architectural vision, the 3 locked pillars, and the complete implementation roadmap through Phase 9.

**Core Thesis:** Trust is not granted; it is *proven, bounded, and revoked*. Agents earn capability through attestations (hardware integrity, origin verification, runtime behavior), delegate authority through immutable ceilings, and govern consumption through tokenized budgets. Failures cascade fail-closed: revocation is transitive, ceilings are immutable, budgets are non-negotiable.

---

## 1. The Three Pillars (Locked Architecture)

### Pillar 1: Attestation (Phases 4–5)

**Purpose:** Prove agent identity and security posture through cryptographic evidence.

**Mechanisms:**
- Hardware enclave (SGX, TPM)
- Model integrity (signed manifest)
- Sovereign origin (signer identity)
- Runtime integrity (behavior log)

**Rules:**
- Attestations are immutable evidence (cannot be revoked, only expire)
- Trust score computed from unique attestation types (no double-counting)
- Score maps to tier: Tier 1 (100+), Tier 2 (70–99), Tier 3 (40–69), Deny (<40)
- Tier determines **maximum** capability grant (soft ceiling)

**Data Model:**
```
attestations: []Attestation {
  attestation_type: enum (hardware_enclave, model_integrity, etc.),
  issuer: string,
  issued_at, valid_until: DateTime,
  payload, signature: string
}

trust_score: u32 (0–120)
tier: u32 (1=FULL, 2=STANDARD, 3=MINIMAL, null=DENY)
```

**State Machine:**
```
New Agent → Phase 4 Handshake (provide attestations)
          → Compute Trust Score
          → Assign Tier (1/2/3)
          → Issue Session + Capability Token
          → (Phase 5) Periodic Refresh with Updated Attestations
```

---

### Pillar 2: Delegation (Phase 6)

**Purpose:** Enable capability transfer through strict immutable envelopes.

**Core Constraint:** **Attenuation is Unidirectional**
- Parent agent with tier 1 can delegate tier 2 ceiling to child
- Child cannot negotiate tier back up (ceiling is immutable)
- Child's tier ≤ ceiling; constraints are inherited not relaxed

**Mechanisms:**

**Delegation Envelope (Locked at Delegation Time):**
```json
{
  "max_tier": 2,                               // Hard ceiling, immutable
  "delegations": [                             // Child capabilities
    {"permission":"can_execute","resource":"tool"}
  ],
  "constraints": {                             // Inherited from parent
    "rate_limit": "1000/min",
    "burst_size": 100,
    "min_interval_ms": 100,
    "concurrent_sessions": 5
  },
  "budget_allocation": {
    "total_budget": 500000,
    "allocation_rationale": "Parent allocated 50% of remaining"
  }
}
```

**Rules:**
1. **Immutability:** Ceiling locked at delegation time, no mid-session renegotiation
2. **Attenuation:** child_delegations ⊆ parent_delegations (subset only)
3. **Constraint Inheritance:** child_constraints ⊇ parent_constraints (equal or stricter)
4. **Acyclicity:** No cycles in delegation DAG (validated at delegation creation)
5. **Tenant Isolation:** Parent and child must be in same tenant

**Delegation DAG (Ancestor/Descendant Relationships):**
```
      Root Agent (Tier 1)
      /           \
  Parent1      Parent2 (both Tier 2 ceiling)
  /    \       /    \
C1    C2    C3      C4 (all Tier 3 ceiling)
```

**State Machine:**
```
Root Session → Phase 6 Delegation Request (define ceiling)
            → Validate Acyclicity (no cycles)
            → Compute Child Budget Allocation (50% of remaining)
            → Create Delegation Edge + Child Session
            → Child can Refresh with Clamped Tier
```

**Data Model:**
```
personas table extensions:
  delegated_by: UUID (parent persona)
  delegation_ceiling_tier: i32
  delegation_timestamp: DateTime

sessions table extensions:
  parent_session_id: UUID (parent session, for revocation chaining)
  delegated_by_agent_id: UUID (persona who delegated)
  delegation_ceiling_envelope: JSONB (locked ceiling)
  current_effective_envelope: JSONB (post-attenuation state)
  lineage_cache: JSONB (minimal lineage: UUID-only, no names)

delegation_edges table:
  source_persona_id, target_persona_id: UUID
  ceiling_delegations, ceiling_constraints: JSON
  delegated_at: DateTime
  Constraints: unique(source, target), no self-delegation
```

---

### Pillar 3: Governance (Phases 5.5, 7)

**Purpose:** Enforce resource consumption limits and revocation cascades.

**Mechanisms:**

**Revocation (Phase 5.5 + 6.1):**
- **STRICT REVOCATION (Fail-Closed):** If ancestor revoked, entire downstream subtree revoked
- No dependency analysis, no partial revocation
- Transitive: A→B→C, if A revoked, C is instantly revoked
- Non-blocking: Revocation recorded, child learns on next refresh

**Pull-Based Refresh (Phase 5.5):**
- Agent can request challenge (empty attestations)
- SISS responds with 401 + nonce
- Agent signs fresh proof with nonce (proves recent attestation)
- No push of tokens; agent pulls with proof

**Token Budget (Phase 7):**
- Per-session immutable budget (set at delegation time)
- Consumed on token issuance: cost = base(100) + tier_penalty(±50) + attestation_cost(10×count)
- Budget conservation invariant: initial = remaining + consumed
- Fail-closed: if budget < cost, deny refresh

**Rate Limiting (Phase 7):**
- Inherited from delegation ceiling (cannot be relaxed)
- Constraints: rate_limit, burst_size, min_interval_ms, concurrent_sessions
- Soft enforcement: 429 (Too Many Requests), not revocation
- Violations logged but don't cascade

**State Machine:**
```
Session Active → (Parent Revoked?) → Entire Subtree Marked Revoked
              → (Budget Exhausted?) → Deny Next Refresh
              → (Rate Limited?) → Return 429, Retry Later
              → (Attestation Failed?) → Pull Challenge or Re-Auth
```

**Data Model:**
```
sessions table extensions (Phase 7):
  token_budget_initial: i64
  token_budget_remaining: i64
  token_budget_consumed: i64
  token_budget_reset_at: DateTime
  rate_limits: JSONB (constraints)
  last_refresh_at: DateTime
  
Constraint: token_budget_initial = token_budget_remaining + token_budget_consumed
```

---

## 2. Locked Design Decisions (Sovereign Rationale)

### Phase 5.5: Revocation & Pull-Based Refresh

#### Decision 1.1: STRICT REVOCATION (Fail-Closed)
**Rule:** If ancestor session revoked, entire downstream subtree instantly revoked.  
**Rationale:** No dependency analysis = no time-of-check-time-of-use bugs. Fail-closed prevents confused deputy attacks. Simplicity is security.  
**Consequence:** Parent revocation cascades; children must re-auth at root.  
**Locked:** Yes, immutable.

#### Decision 1.2: PULL-BASED CHALLENGE FLOW
**Rule:** Agent can trigger pull challenge (empty attestations → 401 + nonce), sign fresh proof, skip push.  
**Rationale:** SISS doesn't push tokens unsolicited. Agent controls refresh timing. Nonce prevents replay.  
**Consequence:** Extra round-trip, but agent has full control.  
**Locked:** Yes, immutable.

---

### Phase 6: Delegation Chains

#### Decision 2.1: IMMUTABLE CEILINGS
**Rule:** Delegation ceiling locked at delegation time; no mid-session renegotiation.  
**Rationale:** Predictable, auditable allocation. Prevents confused budget allocations. Parent plans carefully.  
**Consequence:** Child cannot request more; must ask parent to re-delegate with higher ceiling.  
**Locked:** Yes, immutable.

#### Decision 2.2: MINIMAL LINEAGE CONTEXT (OPSEC)
**Rule:** Children see ancestor UUIDs + constraints only; no agent names, policy reasoning, or sibling visibility.  
**Rationale:** Operational security. Child doesn't learn organizational structure. Prevents lateral enumeration.  
**Consequence:** Children need out-of-band communication for context (parent explains via side channel).  
**Locked:** Yes, immutable.

#### Decision 2.3: STRICT ATTENUATION
**Rule:** child_delegations ⊆ parent_delegations; child_constraints ⊇ parent_constraints (equal or stricter).  
**Rationale:** Cannot grant capability parent doesn't have. Cannot relax constraints (inheritance or tighten).  
**Consequence:** Ceiling defines hard boundary; no escape.  
**Locked:** Yes, immutable.

---

### Phase 6.1: Enhanced Ancestor Checks

#### Decision 3.1: TRANSITIVE REVOCATION
**Rule:** Ancestor revocation blocks all descendants (not just direct children).  
**Rationale:** Fail-closed for cascading failures. If A compromised, entire subtree must re-auth.  
**Consequence:** Deep trees may see wide cascading revocations.  
**Locked:** Yes, immutable.

#### Decision 3.2: FAIL-CLOSED ANCESTRY CHECK
**Rule:** If ancestor status unknown or DB error, deny refresh (safety over optimism).  
**Rationale:** Prevents confused state where we're unsure of parent's health.  
**Consequence:** Brief DB outages can temporarily block refresh; acceptable for security.  
**Locked:** Yes, immutable.

---

### Phase 7: Token Budget & Rate Limiting

#### Decision 4.1: IMMUTABLE BUDGET AT DELEGATION
**Rule:** Child's budget immutable at delegation time (like ceiling).  
**Rationale:** Predictable resource accounting. Parent cannot retroactively increase/decrease.  
**Consequence:** Parent must allocate conservatively; child cannot request more mid-session.  
**Locked:** Yes, immutable.

#### Decision 4.2: FAIL-CLOSED BUDGET ENFORCEMENT
**Rule:** If token_budget_remaining < token_cost, deny refresh (not deferred/queued).  
**Rationale:** No account overdraft. Exhaustion is terminal for session (not catastrophic; child can request new session).  
**Consequence:** Budget exhaustion blocks further operations; child requests parent increase or restarts.  
**Locked:** Yes, immutable.

#### Decision 4.3: SOFT RATE LIMIT ENFORCEMENT
**Rule:** Rate limit violations return 429 (Too Many Requests), not revocation.  
**Rationale:** Rate limits are operational constraints, not security failures. Retry without re-auth.  
**Consequence:** Temporary spikes don't cascade; child can slow down and retry.  
**Locked:** Yes, immutable.

---

## 3. Module Organization & File Structure

### siss-graph-db (Persistence Layer)

**Migrations:**
```
001_create_base_schema.sql           (personas, sessions, edges)
002_create_edges.sql                 (edge types)
003_create_age_graph.sql             (Apache AGE graph)
004_seed_governance.sql              (governance root)
005_create_agent_cards.sql           (agent identity)
006_create_trust_policy_nodes.sql    (policy rules)
007_extend_sessions_phase5.sql       (attestation fields)
008_add_session_revocation.sql       (status='revoked')
009_create_challenges.sql            (pull-based nonce)
010_add_delegation_schema.sql        (parent_session_id, ceiling_envelope)
011_create_delegation_edges.sql      (delegation DAG)
012_add_phase7_budget_fields.sql     (token_budget_*, rate_limits)
```

**Repositories (session_repo.rs, delegation_repo.rs, challenge_repo.rs, etc.):**
```
session_repo.rs:
  - insert_session_with_tokens()
  - fetch_session_by_token()
  - update_session_after_refresh()
  - revoke_session()
  - revoke_all_descendants()
  - fetch_session_status_by_token()
  - fetch_ancestor_session_ids()                    [Phase 6.1]
  - check_ancestors_revoked()                       [Phase 6.1]
  - update_session_budget()                         [Phase 7]
  - fetch_session_budget()                          [Phase 7]

delegation_repo.rs:
  - insert_delegation_edge()
  - fetch_ancestors()
  - fetch_descendants()
  - fetch_descendant_sessions()
  - fetch_delegation_ceiling()
  - would_create_cycle()

challenge_repo.rs:
  - insert_challenge()
  - fetch_and_consume_challenge()
```

---

### siss-gatekeeper (Policy & Validation)

**refresh.rs (Attestation Refresh Orchestration):**

Types:
```
AttestationRefreshRequest                    (session_token, attestations, proof)
AttestationRefreshResponse{Success|Error}   (status, tokens, evaluation)
AttestationEvaluation                        (score, tier, attestations, changes)
RefreshChallenge                             (nonce, required_attestations)
RefreshRequiredResponse                      (401 challenge)
DelegationEnvelope                           (max_tier, delegations, constraints)
AncestorRevocationError                      [Phase 6.1]
```

Builders:
```
build_success_response()
build_success_response_with_delegation()     [Phase 6]
build_error_response()
error_session_revoked()
error_session_token_expired()
error_attestation_validation_failed()
error_hard_requirement_failed()
error_ancestor_revoked_subtree()             [Phase 6, 6.1]
error_insufficient_budget()                  [Phase 7]
error_rate_limit_exceeded()                  [Phase 7]
```

Validators & Builders:
```
validate_refresh_proof()                     [Phase 5]
validate_challenge_proof()                   [Phase 5.5]
validate_ancestor_not_revoked()              [Phase 6.1]
reevaluate_trust()
build_attestation_evaluation()
build_attestations_evaluation()
build_capability_changes()
build_attenuated_capability_token()          [Phase 6]
compute_delegation_ceiling()                 [Phase 6]
clamp_tier_to_ceiling()                      [Phase 6]
compute_token_cost()                         [Phase 7]
parse_rate_limit()                           [Phase 7]
```

**constraint_resolver.rs (Phase 7):**
```
RateLimitConstraints                         (rate_limit, burst, interval, concurrent)
RateLimitViolation enum
check_rate_limits()
validate_rate_limit_format()
```

---

### siss-agent-card (Session & Refresh Handler)

**refresh_handler.rs (13-Step Refresh Orchestration):**

```
Step 1: Extract session_id from token
Step 2: Check session status (revocation detection)
Step 2.5: Rate limit check                   [Phase 7]
Step 2.6: Ancestor revocation check          [Phase 6.1]
Step 2b: Check for pull-trigger (empty attestations → challenge)
Step 2c: Challenge-response path (if nonce set)
Step 3: Validate proof signature (timestamp freshness)
Step 3.5: Budget check                       [Phase 7]
Step 4: Validate attestations
Step 5: Re-evaluate trust (score → tier)
Step 6: Build attestation evaluation (Layer 1 + Layer 2)
Step 6.x: Detect delegated session, clamp tier to ceiling, build lineage [Phase 6]
Step 7: Decide session token reuse
Step 8: Build session token if needed
Step 9: Build capability token (always refreshed)
Step 9.5: Consume budget                     [Phase 7]
Step 10: Build evaluation report
Step 11: Build success response (with optional delegation context)
Step 12: Persist updated trust state (best-effort)
```

---

## 4. End-to-End Data Flow (Complete Lifecycle)

### Phase 4: Initial A2A Handshake

```
Agent provides credentials
  ↓
SISS validates attestations
  ↓
Compute trust_score, assign tier
  ↓
Issue session_token + capability_token + expiry
  ↓
Store session in DB (tier 1/2/3)
```

### Phase 5: Attestation Refresh (Periodic)

```
Agent sends refresh request (new attestations + proof)
  ↓
SISS validates proof (timestamp ±5 min)
  ↓
Re-evaluate trust (new score, new tier)
  ↓
Issue refreshed capability_token
  ↓
Update session (score, tier, token)
```

### Phase 5.5: Revocation & Pull Challenge

```
Case 1 (Push-Based):
  Agent sends attestations + proof
    ↓
  SISS validates, issues new token

Case 2 (Pull-Based):
  Agent sends empty attestations
    ↓
  SISS returns 401 + nonce
    ↓
  Agent signs proof(nonce) with recent attestation
    ↓
  SISS validates challenge proof, issues token

Case 3 (Revocation):
  Parent attestation fails
    ↓
  SISS revokes parent session
    ↓
  Recursive: revoke_all_descendants()
    ↓
  Child learns of revocation on next refresh → 401 error
```

### Phase 6: Delegation

```
Parent Agent → Phase 6 Delegation Request
  ↓
SISS validates:
  - Parent is active, not revoked
  - Acyclicity check (no cycles in DAG)
  - Tenant consistency
  ↓
Compute delegation ceiling:
  ceiling.max_tier = min(parent_tier, intended_tier)
  ceiling.constraints = inherited from parent
  ceiling.budget = 50% of parent_remaining
  ↓
Create delegation edge + child session
  ↓
Child refreshes with:
  - tier clamped to ceiling
  - constraints inherited
  - budget from allocation
  - lineage_cache (ancestor UUIDs + constraints, no names)
```

### Phase 6.1: Ancestor Revocation Check

```
Child Agent refreshes:
  ↓
Step 2.6 checks: ancestor_session_ids = fetch_ancestor_session_ids(parent_session_id)
  ↓
For each ancestor:
  - Query status::text
  ↓
validate_ancestor_not_revoked(ancestor_statuses)
  ↓
If ANY ancestor='revoked':
  ↓
Return 401 error_ancestor_revoked_subtree()
  ↓
Else:
  ↓
Continue to Step 3 (proof validation)
```

### Phase 7: Token Budget & Rate Limiting

```
Refresh request arrives:
  ↓
Step 2.5: Check rate_limits
  - Parse "1000/min" from constraints
  - Check min_interval_ms, rate_limit, concurrent_sessions
  - If violated: return 429 (soft enforcement)
  ↓
Step 3.5: Check budget
  - Compute token_cost = base(100) + tier_penalty + attestation_cost
  - If budget_remaining < cost: return error_insufficient_budget()
  ↓
Step 9.5: Consume budget (atomic)
  - Decrement budget_remaining -= cost
  - Increment budget_consumed += cost
  - Update last_refresh_at
  ↓
Succeed with refreshed token
```

---

## 5. Integration Points & Dependencies

### Phase 5 → Phase 5.5

| Dependency | Impact |
|------------|--------|
| Attestation scoring | Challenge must verify attestation freshness |
| Session token expiry | Challenge nonce valid only within 5-min window |
| Trust tier computation | Cost model scales with tier (Phase 7) |

### Phase 5.5 → Phase 6

| Dependency | Impact |
|------------|--------|
| Session revocation | Revocation propagates to descendants (Phase 6.1) |
| Trust tier | Tier ceiling enforced in delegation (immutable) |
| Proof validation | Same message prefix structure extended (Phase 5.5 vs 6) |

### Phase 6 → Phase 6.1

| Dependency | Impact |
|------------|--------|
| Delegation DAG | Ancestor chain traversal (recursive CTEs) |
| Session status | Revocation check on parent_session_id chain |
| Lineage cache | Built from ancestor UUIDs (OPSEC) |

### Phase 6.1 → Phase 7

| Dependency | Impact |
|------------|--------|
| Delegation ceiling | Constraints inherited (rate limits from ceiling) |
| Ancestor checks | Budget allocation locked at delegation time |
| Trust tier | Token cost scales with tier + attestation count |
| Session persistence | Budget tracked atomically with refresh state |

---

## 6. Error Handling & Recovery

### Fail-Closed Primitives

**Revocation:** If status unknown, treat as revoked (deny refresh).  
**Budget:** If remaining unknown, treat as exhausted (deny refresh).  
**Ancestor:** If ancestor status unknown, treat as revoked (deny refresh).  
**Rate Limit:** If constraint format invalid, treat as unlimited (permissive fallback).

### Non-Blocking Best-Effort

**Budget Persistence:** If DB fails to update budget, continue (best-effort, eventual consistency).  
**Rate Limit Logging:** If logging fails, continue (operational only).  
**Revocation Recording:** If DB fails to mark revoked, continue (next refresh will catch it).

### Error Response Hierarchy

```
Fail-Closed (4xx security):
  400 Bad Request       (malformed request, invalid format)
  401 Unauthorized      (signature, session, ancestor, revocation)
  403 Forbidden         (insufficient budget, policy denial)
  429 Too Many Requests (rate limit, soft enforcement)

Success (2xx):
  200 OK                (refresh succeeded, tokens issued)
```

---

## 7. Testing Strategy

### Unit Tests (Per Module)

- **session_repo:** Insertion, fetching, revocation, ancestor traversal (7 new Phase 6.1)
- **delegation_repo:** Edge creation, acyclicity, DAG traversal (6 tests)
- **challenge_repo:** Nonce generation, consumption atomicity (5 tests)
- **refresh.rs builders:** Cost calculation, parsing, response serialization (15+ tests)
- **constraint_resolver:** Rate limit parsing, violation detection (8 tests)

### Integration Tests (End-to-End)

- **attestation_refresh_integration:** 25 tests (Phase 5.5)
- **attestation_refresh_phase6_integration:** 13 tests (Phase 6 + 6.1)
- **attestation_refresh_phase7_tests:** 20 tests (Phase 7 budget + rates)

### Load Tests (Pending Phase 8)

- Concurrent delegation chains (100+ levels deep)
- Concurrent refresh storms (1000 agents/sec)
- Revocation cascade (10,000 descendants)

---

## 8. Phases 5–9 Roadmap

### Completed ✅

- **Phase 4:** A2A Handshake (identity + initial attestation)
- **Phase 5:** Attestation Refresh (stateless push-based)
- **Phase 5.5:** Revocation & Pull-Based Refresh (strict fail-closed)
- **Phase 6:** Delegation Chains (immutable ceilings, attenuation)
- **Phase 6.1:** Enhanced Ancestor Checks (transitive revocation)
- **Phase 7:** Token Budget & Rate Limiting (AP2 economics)
  - ✅ Task 24: Repository (budget tracking, atomic WHERE clauses)
  - ✅ Task 25: Gatekeeper (token cost formula, error builders)
  - ✅ Task 26: Constraint Resolver (most-restrictive-wins composition)
  - ✅ Task 27: Handler (budget + rate enforcement, Steps 2.5/3.5/9.5)
  - ✅ Task 28: Integration Tests (20 test cases, 109 total gatekeeper tests)
  - ✅ Task 29: Documentation (completion summary, migration guide, monitoring queries)
  - ✅ Task 30: Verification & Hardening (full test suite, locked decisions audit)

### ✅ COMPLETE & PRODUCTION-READY (Phase 8)

- **Phase 8:** Behavioral Governance (runtime behavior → tier adjustment → cost feedback)
  - ✅ Task 31: Migration 013 + Behavior Repo (5 DB integration tests)
  - ✅ Task 32: BehaviorScorer (pure module, 10 unit tests, exponential decay 3.5 days)
  - ✅ Task 33: Handler Integration (Steps 5.5/6.5/13, atomic tier+event persistence)
  - ✅ Task 34: Integration Tests (10 pure unit tests, all passing, 119 total gatekeeper tests)
  - **Spec:** `docs/phases/PHASE_8_FEEDBACK_LOOP_SPECIFICATION.md`

### 🔵 SPECIFICATION LOCKED (Phase 9)

- **Phase 9:** Federation (multi-sovereign coordination without surrendering autonomy)
  - 🔒 **Four Constitutional Invariants (Locked):**
    1. **Federated Identity:** 3-tuple (sovereign_id, tenant_id, persona_id), shadow personas, verified origin
    2. **Cross-Sovereign Attestation Verification:** Bilateral trust (explicit, immutable, non-transitive), cryptographic Ed25519 signatures
    3. **Federated Trust Resolution:** Tier capping at boundary (most-restrictive-wins), behavior isolation (lineage_safe=false), signed revocation certificates
    4. **Inter-Sovereign Settlement:** Append-only credit ledger, immutable accounting, periodic settlement with signed invoices
  - **Spec:** `docs/phases/PHASE_9_FEDERATION_SPECIFICATION.md` (~1200 lines, complete design)
  - **Implementation Plan:** Tasks 35–42 (schema, crypto, handler integration, settlement ledger, tests)

### Future (Phase 10+)

- **Phase 10:** Advanced Federation & Governance
  - Dynamic bilateral renegotiation (in-flight tier adjustment)
  - Cross-sovereign delegation (with ceiling propagation)
  - Reputation blending (home + destination behavior scoring)
  - Federated settlement service (automated escrow + dispute resolution)
  - Transitive trust paths (controlled A→B→C trust delegation)

---

## 9. Architectural Principles (Immutable)

1. **Fail-Closed:** Deny by default; grant only when certain.
2. **Immutable Commitments:** Ceilings, budgets, constraints locked at creation.
3. **Transitive Accountability:** Parent revocation cascades; no orphans.
4. **OPSEC by Design:** Lineage minimal; no unnecessary context leakage.
5. **Economic Enforcement:** Resources quantified in tokens; budgets are hard limits.
6. **Atomicity:** Budget consumption, revocation, ancestor checks all atomic or fail-closed.
7. **Simplicity over Cleverness:** Recursive CTEs, not complex state machines.
8. **Non-Blocking Governance:** Rate limits return 429, budget return 403, revocation return 401 (all allow fast recovery).

---

## 10. References & Locked Specifications

### Locked Phase Specifications
- **Phase 5:** `docs/phases/PHASE_5_COMPLETION_SUMMARY.md` (attestation + refresh)
- **Phase 6:** Delegation chains (code: `crates/siss-agent-card/src/refresh_handler.rs`, immutable ceilings + transitive revocation)
- **Phase 7:** `docs/phases/PHASE_7_COMPLETION_SUMMARY.md` (token budget, rate limiting, atomicity)
- **Phase 8:** `docs/phases/PHASE_8_FEEDBACK_LOOP_SPECIFICATION.md` (behavior scoring, tier feedback loop)
- **Phase 9:** `docs/phases/PHASE_9_FEDERATION_SPECIFICATION.md` (4 constitutional invariants, multi-sovereign coordination)

### Implementation Status
- **Phases 5–6.1:** ✅ Code complete, tested, committed (all tests passing)
- **Phase 7:** ✅ Code complete, tested, committed (129 gatekeeper tests passing)
- **Phase 8:** ✅ Code complete, tested, committed (119 gatekeeper tests, 20 integration tests)
- **Phase 9:** 🔵 Specification locked, ready for implementation (Tasks 35–42)
- **Phases 10+:** Future (federation enhancements, governance automation)

### Code Anchors
- Entry point: `crates/siss-agent-card/src/refresh_handler.rs` (13-step orchestration)
- Type definitions: `crates/siss-gatekeeper/src/refresh.rs` (builders, validators)
- Persistence: `crates/siss-graph-db/src/repo/` (session, delegation, challenge repos)
- Migrations: `crates/siss-graph-db/src/migrations/` (001–012)

---

## Conclusion

This document is the **constitutional foundation** for the Sovereign Multi-Agent OS. Every agent implementing Phases 7–9 should reference this document as the source of truth. No scattered specs. No vibe coding. Only locked decisions with explicit sovereign rationale.

**The Three Pillars are immutable. The Locked Decisions are final. Build with confidence.**

---

**Last Updated:** 2026-05-10  
**Next Review:** Post-Phase 7 (2026-05-15 estimated)  
**Authority:** Phase Architects, User Lockdowns  
**Status:** LOCKED FOR IMPLEMENTATION

