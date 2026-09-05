# Phase 6: Delegation Chains — Specification

**Date:** 2026-05-10  
**Status:** LOCKED (Sovereignty Constraints Finalized)  
**Scope:** Enable agents to delegate capabilities to child agents within a bounded, verifiable ancestry tree.  
**Dependency:** Phase 4 (Handshake), Phase 5 (Refresh), Phase 5.5 (Revocation)

---

## 🔒 LOCKED DESIGN DECISIONS (2026-05-10)

This specification enforces three **cryptographically non-negotiable** sovereignty constraints:

1. **Strict Revocation (Fail-Closed)**: When a parent's critical attestation fails, the entire downstream subtree is instantly revoked. No dependency analysis.
2. **Minimal Lineage (OPSEC-Aware)**: Children see ancestor UUIDs + effective constraints only. No agent names, no policy reasoning.
3. **Immutable Ceilings**: Delegation ceiling locked at delegation time. No mid-session renegotiation. Expanding requires new delegation.

These constraints ensure the Phase 6 Delegation Chains are as cryptographically secure as a hardware enclave.

---

## 1. Overview

Phase 6 extends the A2A protocol to support **delegation chains**: agent-to-agent capability handoff with strict attenuation, transparent lineage visibility, and ancestor-aware revocation.

### Motivation

- **Sovereign workflows**: Autonomous agents spawning sub-agents for parallel tasks without centralized delegation proxies.
- **Precision revocation**: When an ancestor's trust degrades, only descendants whose capabilities *depend on that attestation type* are revoked—not the entire subtree.
- **Transparent trust**: Delegated agents see their full ancestor context, enabling autonomous recovery decisions.

### Philosophical Commitments

1. **Token Attenuation**: Fresh child tokens, strictly attenuated from parent, with local upgradability within a ceiling.
2. **Hybrid Revocation**: Re-evaluate children; only revoke where dependency exists (not blunt cascade).
3. **DAG Shape**: Arbitrary delegation graph, per-agent sessions, independent refresh.
4. **Lineage Context**: Full ancestry visibility, structured for programmatic reasoning.

---

## 2. Core Concepts

### 2.1 Delegation DAG

A directed acyclic graph where nodes are agents and edges represent delegation relationships.

- **Ancestor**: An agent A such that there exists a path from A to some other agent B.
- **Ceiling**: The maximum capability envelope an agent can grant to its descendants. Defined by:
  - Parent's current delegations (scope)
  - Parent's current tier (trust level cap)
  - Parent's constraints (hardware, rate limits, duration)
- **Delegation Envelope**: The intersection of all ancestor ceilings on a path from root to agent. This is the agent's hard capability bound.

### 2.2 Token Attenuation

A child's capability_token is **strictly attenuated** from its parent's:

```
child_delegations ⊆ parent_delegations (by scope)
child_constraints ⊇ parent_constraints (equal or stricter)
child_tier ≤ parent_tier (at delegation time)
```

But the child can **improve** its own trust:

```
child_attestations_new may be stronger than parent's
  → child_tier_new can rise (up to delegation ceiling)
```

The delegation ceiling never moves up; the child can only climb within it.

### 2.3 Ancestor Envelope

For agent C in tree A → B → C:

```
effective_ceiling(C) = min(
  capabilities(A),      // root ceiling
  capabilities(B),      // parent ceiling
  capabilities(C)       // self (always ≤ parent)
)
```

### 2.4 Lineage Context

The full path from root to self, with context at each node:

```
[
  {
    agent_id: <root>,
    tier: <Tier 2>,
    key_constraints: ["hardware_enclave_required"],
    attenuation_applied: None,
  },
  {
    agent_id: <parent>,
    tier: <Tier 1>,
    key_constraints: ["rate_limit: 1000/min"],
    attenuation_applied: ["removed: high_risk_tool_X"],
  },
  {
    agent_id: <self>,
    tier: <Tier 1>,
    key_constraints: ["max_duration: 3600s"],
    attenuation_applied: ["narrowed: allowed_tools"],
  }
]
```

---

## 3. Data Model

### 3.1 New Persona Attributes (for delegated agents)

**Persona node extensions:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `delegated_by` | `uuid` | Parent agent's persona_id. Null if root. |
| `delegation_ceiling_tier` | `u32` | Maximum achievable tier (set at delegation time). |
| `delegation_timestamp` | `timestamp` | When delegation occurred. |

### 3.2 New Session Attributes (for delegated agents)

**Session node extensions:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `parent_session_id` | `uuid` | Parent agent's session_id. Null if root. |
| `delegated_by_agent_id` | `uuid` | Persona that delegated to this agent. |
| `delegation_ceiling_envelope` | `json` | Serialized delegation envelope at creation. |
| `current_effective_envelope` | `json` | Memoized envelope for this session (updated on ancestor revocation). |
| `lineage_cache` | `json` | Cached lineage array (refreshed on ancestor changes). |

### 3.3 New Edge Types

| Edge | Direction | Description |
|------|-----------|-------------|
| `DELEGATES_TO` | Persona → Persona | Direct delegation link. Attributes: `ceiling_delegations`, `ceiling_constraints`, `delegated_at`. |
| `HAS_ACTIVE_SESSION` | Persona → Session | Current active session for this agent. |

### 3.4 Modified Edge: CAN_EXECUTE

Extend `CAN_EXECUTE` to track **attenuation context**:

```
CAN_EXECUTE {
  source: Persona,
  target: Tool,
  base_allowed: bool,           // True if inherited or direct
  attenuated_by_ancestor: uuid, // Which ancestor imposed the restriction
  reason: enum(rate_limit, hardware_constraint, risk_class, explicit_deny)
}
```

---

## 4. Token Attenuation Algorithm

### Input

- `parent_session`: Session of the parent agent (includes parent's current delegations, tier, constraints)
- `child_attestations`: Fresh attestations from child agent
- `delegation_specs`: Explicit attenuation rules (if any)

### Output

- `child_capability_token`: New token with attenuated delegations
- `delegation_ceiling`: Envelope cap for this child
- `lineage`: Array of ancestor context

### Algorithm

```
1. Validate child is authorized to be delegated to (check AP2 mandate, firewall rules)

2. Fetch parent_envelope = parent_session.current_effective_envelope
   (this is already ancestor-bounded from parent's creation or ancestor re-eval)

3. Fetch parent_delegations = parent_session.capability_token.delegations

4. For each delegation D in parent_delegations:
     - If explicit attenuation rule says "remove D" → skip
     - If explicit attenuation rule says "narrow D to resources R" → create narrowed D'
     - Else → include D as-is
   delegations_candidate = [D_modified, ...]

5. Merge constraints:
   constraints_candidate = parent_constraints ∪ delegation_specs.additional_constraints
   (use set union; any conflict, parent's constraint wins)

6. Score child's own attestations:
   (score_child, tier_child) = reevaluate_trust(child_attestations)

7. Determine effective tier:
   tier_ceiling = min(
     parent_session.attestation_tier,
     delegation_specs.max_tier (if present),
     tier_child
   )

8. Build DelegationCeiling:
   ceiling = {
     delegations: delegations_candidate,
     constraints: constraints_candidate,
     max_tier: tier_ceiling,
   }

9. Issue child_capability_token:
   token = {
     delegations: delegations_candidate,
     constraints: constraints_candidate,
     issued_at: NOW(),
     valid_until: min(parent_token.valid_until, NOW() + child_ttl),
   }

10. Build lineage:
    lineage = [
      ancestor contexts from parent_session.lineage_cache,
      {
        agent_id: parent_session.persona_id,
        tier: parent_session.attestation_tier,
        key_constraints: extract_key_constraints(parent_constraints),
        attenuation_applied: delegation_specs.description,
      }
    ]

11. Create child_session and persist:
    child_session = {
      persona_id: child_persona_id,
      parent_session_id: parent_session.id,
      delegation_ceiling_envelope: ceiling,
      current_effective_envelope: ceiling,  // initially same
      lineage_cache: lineage,
      session_token: new_session_token,
      capability_token: child_capability_token,
      attestation_score: score_child,
      attestation_tier: tier_child,
      session_expires_at: token.valid_until,
    }

12. Return (child_capability_token, ceiling, lineage)
```

---

## 5. Revocation Propagation Algorithm

### Design Decision: STRICT REVOCATION (Fail-Closed)

**Phase 6.0 enforces Fail-Closed semantics: when a parent agent's critical attestation fails, the entire downstream subtree is instantly revoked.**

**Rationale**: In a sovereign environment, precision is a luxury; absolute containment is a necessity. We cannot trust dependency graph analysis to perfectly calculate which child agents are "safe" to keep running. If a root node is compromised, zero unauthorized execution must be guaranteed. Dependency-based precision will be explored in Phase 6.1.

### Trigger

Ancestor agent A's critical attestation T fails or is downgraded. SISS marks A's session as `revoked` (not `downgraded`).

Critical attestations (require immediate revocation of entire subtree):
- `hardware_enclave` (TEE compromise)
- `sovereign_origin` (origin validation failure)
- `model_integrity` (if tier-critical for policy)

Non-critical attestations (Phase 6.1+):
- `runtime_integrity` (may allow child re-evaluation in Phase 6.1)

### Input

- `ancestor_session_id`: Session that was revoked
- `critical_attestation_type`: The attestation that failed

### Output

For each descendant D in subtree(A):
- `D.status = 'revoked'`
- `D.revoked_at = NOW()`
- `D.revoked_reason = f"ancestor {A} revoked due to {critical_attestation_type} failure"`

### Algorithm

```
1. Fetch ancestor_session (A)
   Verify A.status = 'revoked'

2. For each descendant_session D in descendants_of(A):
   
   2a. Mark D as revoked:
       D.status = 'revoked'
       D.revoked_at = NOW()
       D.revoked_reason = f"ancestor {A.persona_id} revoked"
   
   2b. Recursively revoke children of D:
       For each grandchild_session G in descendants_of(D):
         G.status = 'revoked'
         G.revoked_at = NOW()
         G.revoked_reason = f"ancestor {A.persona_id} revoked"

3. Emit audit trail:
   For each revoked D:
     create_audit_edge(REVOKED_BY, A.session_id, D.session_id)

4. Notify all revoked descendants (via next refresh attempt or webhook):
   Each revoked agent receives: error_ancestor_revoked_subtree()
```

### Handler Behavior (Revoked Agent Refresh)

When a revoked agent calls refresh:

```
1. Fetch session
2. Check status
3. If status == 'revoked':
   Return 401 Unauthorized:
   {
     "status": "denied",
     "reason": "session_revoked_ancestor",
     "detail": "Your delegation ancestor was revoked due to critical attestation failure. You must obtain new delegation.",
     "remediation": [
       "Contact parent agent to request new delegation",
       "Or return to root and restart Phase 4 handshake"
     ]
   }
```

---

## 6. Refresh Flow for Delegated Agents

### Request

Delegated agent C wants to refresh its attestations and potentially improve its tier.

**Endpoint**: `POST /.well-known/a2a/refresh`

**Request Payload** (Phase 5 + new fields):

```json
{
  "session_token": "...",
  "attestations": [...],
  "ephemeral_nonce": "...",
  "timestamp": "...",
  "proof_signature": "...",
  "include_lineage": true
}
```

### Handler Steps

```
1. Extract session_id from session_token (Phase 5 standard)

2. Fetch session from DB:
   db_session = fetch_session_by_token(session_token)

3. Check revocation status:
   If db_session.status == 'revoked' → return error_session_revoked()

4. Validate proof (Phase 5 standard) ✅

5. Validate attestations (Phase 5 standard) ✅

6. Re-evaluate trust:
   (score, tier) = reevaluate_trust(attestations)

7. [NEW] Clamp tier to delegation ceiling:
   effective_tier = min(tier, db_session.delegation_ceiling_envelope.max_tier)

8. [NEW] Check ancestor revocations (STRICT):
   If any ancestor is revoked:
     → return error_ancestor_revoked_subtree()
     (No dependency analysis; fail-closed: entire subtree is revoked)

9. Build attestation evaluation (Phase 5 standard) ✅

10. [NEW] Build capability changes in context of delegation ceiling:
    before_tier = db_session.attestation_tier
    after_tier = effective_tier
    capability_changes = build_capability_changes(
      before_tier, after_tier,
      context = {
        delegation_ceiling: db_session.delegation_ceiling_envelope,
        attenuated_by_ancestor: [list of ancestors that impose constraints],
      }
    )

11. [NEW] Build lineage:
    lineage = build_lineage_context(db_session)

12. Decide session token reuse (Phase 5 standard) ✅

13. Build response:
    return {
      status: "refreshed",
      session_token_reused: bool,
      session_token: Option<SessionToken>,
      capability_token: CapabilityToken,
      attestation_evaluation: AttestationEvaluation,
      [NEW] lineage: Option<LineageContext>,
      [NEW] effective_envelope: DelegationEnvelope,
    }

14. Persist to DB (Phase 5 standard) ✅
```

---

## 7. Lineage Context Structure

### Design Decision: MINIMAL CONTEXT + UUIDs (OPSEC-Aware)

**Phase 6.0 enforces reduced lineage transparency: a child agent sees its ancestor chain (UUIDs only) and the exact effective capability constraints, but NOT the policy reasoning or human-readable names.**

**Rationale**: Phase 5 established Radical Transparency for single-agent debugging. Phase 6 introduces cross-tenant and inter-departmental workflows. Exposing why an ancestor was downgraded leaks organizational security policy (e.g., geographic jurisdiction checks, compliance frameworks). The child agent only needs the mathematical boundaries of its execution sandbox, not the political or security reasoning.

### Type Definition

```rust
pub struct LineageContext {
    pub root_agent_id: Uuid,
    pub path: Vec<LineageNode>,
    pub effective_ceiling: DelegationEnvelope,
}

pub struct LineageNode {
    pub agent_id: Uuid,  // UUID only; NO agent_name
    pub tier: u32,
    pub effective_constraints: Vec<String>,  // Only constraints affecting THIS child
    // NO: attenuation_applied (policy reasoning hidden)
    // NO: revoked_reason (political context hidden)
    pub status: enum(active, revoked),
}

pub struct DelegationEnvelope {
    pub delegations: Vec<Delegation>,
    pub constraints: DelegationConstraints,
    pub max_tier: u32,
}
```

### Example Response (Minimal Context)

```json
{
  "status": "refreshed",
  "capability_token": { ... },
  "lineage": {
    "root_agent_id": "550e8400-e29b-41d4-a716-446655440000",
    "path": [
      {
        "agent_id": "550e8400-e29b-41d4-a716-446655440000",
        "tier": 2,
        "effective_constraints": [
          "hardware_enclave_required",
          "rate_limit: 2000/min"
        ],
        "status": "active"
      },
      {
        "agent_id": "550e8400-e29b-41d4-a716-446655440001",
        "tier": 1,
        "effective_constraints": [
          "rate_limit: 1000/min",
          "max_duration: 7200s"
        ],
        "status": "active"
      },
      {
        "agent_id": "550e8400-e29b-41d4-a716-446655440002",
        "tier": 1,
        "effective_constraints": [
          "rate_limit: 500/min",
          "max_concurrent: 5"
        ],
        "status": "active"
      }
    ],
    "effective_ceiling": {
      "max_tier": 1,
      "delegations": [ ... ],
      "constraints": { ... }
    }
  }
}
```

### OPSEC Properties

- ✅ **No agent names**: UUIDs only. Ancestor identities hidden.
- ✅ **No policy reasoning**: Child sees `rate_limit: 500/min` but NOT `"because of geographic jurisdiction check"`.
- ✅ **Only effective constraints**: Only constraints that affect THIS child's capabilities are shown.
- ✅ **Revocation status minimal**: Child sees `status: "revoked"` but not the reason (parent will communicate via separate error response).

---

## 8. Error Cases & Rejection Paths

### Case 1: Child Has No Authorization to Delegate

```
Prerequisite check fails: Child Persona not marked as allowed to spawn.
Response: 403 Forbidden, reason: "persona_cannot_delegate"
Remediation: Parent must explicitly enable delegation via policy or ACTS_AS edge.
```

### Case 2: Child Requests Capabilities Parent Doesn't Have

```
Child requests: can_execute(high_risk_tool_X)
Parent has: can_execute(high_risk_tool_X) = false (attenuated by own ancestor)
Response: 400 Bad Request, reason: "capability_not_in_parent_envelope"
Remediation: Request parent to expand its own attestations first.
```

### Case 3: Ancestor Revoked, Child Tries to Refresh (STRICT REVOCATION)

```
Child calls refresh.
Handler detects: ancestor_session.status = 'revoked'
Response: 401 Unauthorized, reason: "session_revoked_ancestor"
Remediation: "Contact parent to request new delegation, or restart Phase 4 handshake"

Note: There is NO dependency analysis. The entire subtree is instantly revoked.
```

### Case 4: Child Requests Higher Ceiling (IMMUTABLE CEILING)

```
Child tries to expand its capability envelope mid-session.
Handler detects: requested_ceiling > delegation_ceiling_envelope.max_tier
Response: 403 Forbidden, reason: "ceiling_immutable"
Remediation: "Terminate this session and request new delegation with expanded ceiling"
```

### Case 5: Parent Attempts to Expand Child's Ceiling (IMMUTABLE CEILING)

```
Parent tries to "renegotiate" child's ceiling mid-session.
Handler rejects: ceiling changes are not allowed mid-session.
Response: 400 Bad Request, reason: "ceiling_cannot_be_renegotiated"
Remediation: "Revoke current session and delegate again with new ceiling"
```

---

## 9. Integration with Phase 4 & 5

### Phase 4 (Handshake)

- A root agent initiates Phase 4 handshake normally.
- Returns `session_token`, `capability_token`, `persona`.
- On success, Persona and Session are marked as root (delegated_by = NULL).

### Phase 5 (Refresh)

- Root agent can refresh attestations using Phase 5.
- Delegated agents **also** use Phase 5 refresh (same endpoint).
- Key difference: delegated agents' refresh responses include `lineage` + `effective_envelope`.

### Phase 5.5 (Revocation)

- If a root agent's session is revoked, Phase 5.5 propagation applies.
- Descendants of the revoked root are evaluated using Phase 6 revocation logic.

---

## 10. Implementation Roadmap

### Task 16: Schema Extensions (Migrations)
- Extend `personas` table with `delegated_by`, `delegation_ceiling_tier`, `delegation_timestamp`
- Extend `sessions` table with `parent_session_id`, `delegation_ceiling_envelope`, `current_effective_envelope`, `lineage_cache`
- Create `delegation_edges` table (or extend existing `edges` table)

### Task 17: Token Attenuation (Repo + Builder Functions)
- `delegation_repo.rs`: `insert_delegation_edge()`, `fetch_ancestor_envelope()`, `fetch_descendants()`
- `refresh.rs`: `build_attenuated_capability_token()`, `compute_delegation_ceiling()`
- `session_repo.rs`: update with delegation-aware queries

### Task 18: Revocation Propagation (Gatekeeper)
- `refresh.rs`: `propagate_ancestor_revocation()`
- Dependency analysis: `find_affected_descendants()`
- Attenuation pruning: `prune_delegations_by_policy()`

### Task 19: Refresh Handler Extensions (Agent Card)
- Extend `attestation_refresh_handler()` to detect delegated sessions
- Add lineage caching logic
- Add effective envelope update on ancestor revocation

### Task 20: Integration Tests
- Delegation attenuation (parent can't delegate what it lacks)
- Upgradability within ceiling
- Revocation propagation (dependency-based, policy-aware)
- Lineage visibility
- DAG shape validation (no cycles)

---

## 11. Locked Design Decisions — Phase 6.0 Sovereignty Constraints

### 🔒 **Revocation Precision: STRICT REVOCATION (LOCKED)**

**Decision**: Phase 6.0 enforces fail-closed semantics. When a parent agent's critical attestation fails, the entire downstream subtree is instantly revoked.

**Why Strict**: In sovereign environments, precision is a luxury; absolute containment is a necessity. We cannot trust dependency graph analysis to perfectly identify "safe" descendants. Cryptographic containment is non-negotiable.

**Future**: Phase 6.1 will explore dependency-based precision (revoke only descendants whose capabilities depend on the failed attestation type).

**Immutable**: This design is locked into Phase 6.0 and will not change.

---

### 🔒 **Lineage Exposure: MINIMAL CONTEXT + UUIDs (LOCKED)**

**Decision**: Children see ancestor UUIDs + exact effective constraints, but NOT policy reasoning or human-readable names.

**Why Minimal**: Phase 5 transparency was for single-agent debugging. Phase 6 introduces cross-tenant workflows. Exposing "downgraded due to geographic jurisdiction check" leaks organizational security policy. Mathematical boundaries suffice; political context is OPSEC-restricted.

**Immutable**: This design is locked into Phase 6.0. Full lineage debugging will be available only to root agents and system administrators.

---

### 🔒 **Delegation Ceiling Mutability: IMMUTABLE (LOCKED)**

**Decision**: Delegation ceiling is locked at the moment of delegation and cannot be renegotiated mid-session.

**Why Immutable**: This mirrors the Agent Payment Protocol (AP2) Intent Mandate. Cryptographic authorization tokens cannot be morphable mid-execution without breaking the audit trail and enabling privilege escalation attacks.

**How to Expand**: If a child needs a higher ceiling, the current session must be terminated. Parent must explicitly spin up a new delegation chain with a new signed envelope (equivalent to re-running Phase 4 handshake for the child).

**Immutable**: This design is locked into Phase 6.0 and will not change.

---

## 12. Success Criteria (Phase 6.0 Sovereignty Constraints)

The Phase 6 design is correct when:

1. ✅ An agent A can delegate to agent B with attenuated delegations (scope ⊆ parent, constraints ⊇ parent).
2. ✅ Agent B cannot execute tools that A cannot execute (strict subset enforcement).
3. ✅ Agent B can improve its own trust (via stronger attestations) up to A's ceiling (local upgradability within hard cap).
4. ✅ A DAG of 3+ agents (A → B → C, A → D) is fully supported (no cycles enforced).
5. ✅ **When A is revoked, B and C are instantly revoked (strict fail-closed, no dependency analysis).**
6. ✅ **B sees only ancestor UUIDs + effective constraints on refresh; no agent names, no policy reasoning (OPSEC-minimal).**
7. ✅ **Delegation ceiling is immutable; if B needs higher ceiling, session terminates and new delegation must be requested (no mid-session renegotiation).**
8. ✅ A refresh response for B includes `lineage` (minimal context) + `effective_envelope` (mathematical bounds).
9. ✅ Cycles in the delegation graph are prevented (enforced in schema).
10. ✅ All Phase 5 tests continue to pass (backward compatible).
11. ✅ Revoked agents receive clear error messages with remediation paths.

---

**Status**: Skeleton ready for user iteration on revocation precision, lineage exposure, and ceiling mutability.

