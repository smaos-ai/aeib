# Phase 9: Federation — Constitutional Specification

**Status:** 🔵 SPECIFICATION LOCKED (Ready for Implementation)  
**Date:** 2026-05-10  
**Scope:** Federated identity, cross-sovereign attestation verification, federated trust resolution, inter-sovereign settlement  
**Locked Decisions:** 4 constitutional invariants + 4 overarching physics rules

---

## Executive Summary

Phase 9 enables multi-sovereign federation: independent SovereignNexus nodes coordinate securely without surrendering local autonomy. An agent from Sovereign A can operate in Sovereign B only if:

1. **Federated Identity is verifiable** — cryptographic proof of origin via signed attestation
2. **Cross-sovereign attestations are cryptographically validated** — bilateral agreement grants explicit trust
3. **Trust tier is capped at the boundary** — the foreign sovereign's tier cannot exceed the bilateral ceiling
4. **Resource consumption is settled** — Sovereign B records immutable credit for resources consumed by agents from A

The four invariants are constitutional: they define the physics of inter-sovereign trust. All Phase 9 implementation (Tasks 35–42) derives from them deterministically. No implementation detail contradicts these invariants.

---

## Invariant 1: Federated Identity

### The Law

**An agent's canonical identity is a 3-tuple: `(sovereign_id, tenant_id, persona_id)`. No operation crosses a sovereign boundary without the full 3-tuple being cryptographically verifiable.**

### Core Rules

#### Sovereign Registration
- Each sovereign node has a stable `sovereign_id` (UUID, globally unique)
- Each sovereign publishes a public key in a `sovereigns` table (federated, eventually-consistent)
- `sovereigns (id, name, public_key_pem, status, established_at)`

#### Identity Resolution
- All existing identifiers (`tenant_id`, `persona_id`) remain unchanged
- `sovereign_id` is a new layer **above** tenant_id (not replacing it)
- A local agent's full identity: `(home_sovereign_id, tenant_id, persona_id)`
- A foreign agent's identity: `(origin_sovereign_id, shadow_tenant_id, shadow_persona_id)` where `shadow_persona_id` is a **local proxy record**

#### Shadow Personas (Foreign Agents)
When an agent from Sovereign A first enters Sovereign B:
1. Sovereign B creates a shadow persona record: `personas { id: new_uuid, origin_sovereign_id: A's sovereign_id, name: "foreign-{origin_id}-{agent_id}", delegation_ceiling_tier: bilateral_max_tier }`
2. The shadow persona is local (FK to B's tenant), but tagged with `origin_sovereign_id` to track provenance
3. Shadow personas' tier ceiling is immutable at the bilateral agreement cap — they cannot be elevated by local operations
4. Sessions for shadow personas are marked `is_federated_session = true`

#### Verified Identity Entry Point
A foreign agent enters a sovereign's boundary via the **attestation refresh endpoint** with a signed `SovereignOrigin` attestation in the request. See Invariant 2 for cryptographic details.

### Key Decision: Verification Over Trust

**Identity is verified, never assumed.**

A foreign agent is rejected at the boundary (fail-closed) unless they present:
1. A valid `SovereignOrigin` attestation
2. Cryptographic proof of origin (signature verified against the source sovereign's registered public key)
3. A bilateral grant in `federation_peers` allowing this sovereign pair

### Schema Extensions

```sql
CREATE TABLE sovereigns (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  public_key_pem TEXT NOT NULL,          -- Ed25519 public key in PEM format
  status VARCHAR(32) NOT NULL DEFAULT 'active',  -- active, suspended, revoked
  established_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE tenants
  ADD COLUMN sovereign_id UUID NOT NULL REFERENCES sovereigns(id);

ALTER TABLE personas
  ADD COLUMN origin_sovereign_id UUID REFERENCES sovereigns(id);
  -- NULL = local persona, non-NULL = foreign (shadow persona)

ALTER TABLE sessions
  ADD COLUMN is_federated_session BOOLEAN NOT NULL DEFAULT FALSE;
```

### Example: Shadow Persona Lifecycle

```
Scenario: Agent "alice" from Sovereign A (UUID: a-uuid) operates in Sovereign B (UUID: b-uuid)

1. alice@A sends attestation refresh request to B with SovereignOrigin attestation
   payload = {sovereign_id: a-uuid, agent_id: alice, issued_at: T, signature: sig}

2. B verifies signature against sovereigns[a-uuid].public_key_pem ✓
3. B checks federation_peers[a-uuid, b-uuid] → max_admitted_tier = 3 ✓
4. B creates shadow persona:
   INSERT INTO personas (id, name, origin_sovereign_id, delegation_ceiling_tier)
   VALUES (shadow-uuid, "foreign-a-alice", a-uuid, 3)

5. B creates federated session:
   INSERT INTO sessions (persona_id, is_federated_session, ...)
   VALUES (shadow-uuid, true, ...)

6. alice's operations in B are recorded with persona_id=shadow-uuid
   All behavior_events for this persona: lineage_safe = false (isolated scoring)
```

---

## Invariant 2: Cross-Sovereign Attestation Verification

### The Law

**Attestations from a foreign sovereign are only trusted if:**
1. **Cryptographically signed by that sovereign's registered public key**, and
2. **A bilateral agreement explicitly grants trust to that attestation type**

### Core Rules

#### Bilateral Trust Table
```sql
CREATE TABLE federation_peers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sovereign_a_id UUID NOT NULL REFERENCES sovereigns(id),
  sovereign_b_id UUID NOT NULL REFERENCES sovereigns(id),
  max_admitted_tier SMALLINT NOT NULL,        -- highest tier A agents can claim in B
  granted_attestation_types TEXT[] NOT NULL,  -- {"HardwareEnclave", "ModelIntegrity", "SovereignOrigin"}
  foreign_agent_budget_cap BIGINT NOT NULL,   -- max tokens per foreign session (Phase 9 + Phase 7)
  granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,                     -- optional: agreement expiry
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  PRIMARY KEY (sovereign_a_id, sovereign_b_id, granted_at)
  -- Composite key: (A, B, timestamp) allows versioning
);
```

#### Cryptographic Verification Contract

**SovereignOrigin Attestation Payload Structure:**
```json
{
  "sovereign_id": "<UUID of source sovereign>",
  "agent_id": "<agent identifier in source sovereign>",
  "issued_at": "<ISO8601 timestamp>",
  "tier": <trust tier at source>,
  "attestation_summary": {
    "hardware_enclave_present": boolean,
    "model_integrity_verified": boolean,
    "runtime_integrity_verified": boolean
  }
}
```

**Signature Computation:**
```
canonical_json = sort_keys_recursively(payload_without_signature)
signature = Ed25519_sign(
  private_key = source_sovereign.private_key,
  message = canonical_json
)
```

**Verification in `validate_attestation()`:**
1. Extract `sovereign_id` and `signature` from attestation
2. Lookup `sovereigns[sovereign_id].public_key_pem`
3. Parse payload JSON, reconstruct canonical form
4. Verify: `Ed25519_verify(public_key, canonical_json, signature)` must succeed
5. Check `federation_peers[source_sovereign, destination_sovereign]` for grant
6. Verify attestation type is in `granted_attestation_types[]`

**Fail-closed conditions:**
- Signature verification fails → return HTTP 403 (forbidden)
- No bilateral grant exists → return HTTP 403
- Attestation type not granted → return HTTP 403
- Source sovereign not in `sovereigns` table → return HTTP 403
- Public key lookup fails (DB error) → return HTTP 500, deny refresh

#### Promotion of TRUSTED_ISSUERS to Federation Peers

**Today (Phases 1-8):** `TRUSTED_ISSUERS` is a compile-time constant array in `refresh_handler.rs:16`:
```rust
const TRUSTED_ISSUERS: &[&str] = &["intel", "intel-sgx", "anthropic", "origin-issuer", "runtime"];
```

**Phase 9 behavior:**
- Intra-sovereign (local agents): `validate_attestation()` still checks compile-time `TRUSTED_ISSUERS` (backward compat)
- Cross-sovereign (foreign agents): `validate_attestation()` uses `federation_peers[source, dest]` bilateral grant

### Key Decision: Explicit, Immutable, Non-Transitive Trust

**Bilateral trust is explicit.** There is no implicit trust. If A trusts B and B trusts C, A does NOT automatically trust C. Every cross-sovereign path requires its own bilateral grant in `federation_peers`.

**Bilateral trust is immutable for its grant lifetime.** When A and B establish a trust grant:
- The grant is versioned by `(sovereign_a_id, sovereign_b_id, granted_at)` composite key
- Old grants are never mutated; they remain valid for existing sessions
- Renegotiation creates a new grant record with a new `granted_at` timestamp
- Existing sessions continue to use their original grant version (consistent behavior)

**Bilateral trust is directional.** Trust A→B (A's agents in B) is separate from B→A (B's agents in A). Both directions require explicit grants.

### Schema Extensions

```sql
CREATE TABLE federation_peers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sovereign_a_id UUID NOT NULL REFERENCES sovereigns(id),
  sovereign_b_id UUID NOT NULL REFERENCES sovereigns(id),
  max_admitted_tier SMALLINT NOT NULL,
  granted_attestation_types TEXT[] NOT NULL,
  foreign_agent_budget_cap BIGINT NOT NULL,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  PRIMARY KEY (sovereign_a_id, sovereign_b_id, granted_at)
);

CREATE INDEX idx_federation_peers_bilateral ON federation_peers(sovereign_a_id, sovereign_b_id);
```

### Attestation Vector Jurisdiction Field

**Phase 5-8 behavior:** `AttestationVector.jurisdiction` is always `None`.

**Phase 9 behavior:** Populated from `SovereignOrigin` attestation payload as `{sovereign_id, agent_id}`.

```rust
pub struct AttestationVector {
    pub score: u32,
    pub tier: u32,
    pub jurisdiction: Option<(String, String)>, // (sovereign_id, agent_id)
    // ... other fields
}
```

This enables `TrustPolicyNode` to enforce jurisdiction-based capability overrides (Phase 9 enhancement):
```rust
pub struct TrustPolicyNode {
    pub allowed_organizations: Vec<String>,     // now: sovereign_id strings
    pub jurisdiction_overrides: Vec<(String, CapabilityRule)>,  // sovereign-specific rules
    // ... other fields
}
```

---

## Invariant 3: Federated Trust Resolution

### The Law

**An agent's trust tier at a foreign sovereign is always the minimum of:**
1. **The tier they claim at their home sovereign** (source_tier), and
2. **The bilateral agreement's max_admitted_tier** (destination's ceiling)

**Behavior history does not transfer. The foreign sovereign's behavior scoring starts fresh.**

### Core Rules

#### Tier Clamping at Boundary

```rust
pub fn resolve_federated_tier(
    source_tier: u32,
    source_sovereign: Uuid,
    destination_sovereign: Uuid,
) -> Result<u32, FederationError> {
    // 1. Lookup bilateral agreement
    let bilateral = fetch_federation_peers(source_sovereign, destination_sovereign)?;
    
    // 2. Apply most-restrictive-wins ceiling
    let admitted_tier = std::cmp::min(source_tier, bilateral.max_admitted_tier);
    
    // 3. Return clamped tier (always ∈ [1, 13])
    Ok(std::cmp::max(1, std::cmp::min(13, admitted_tier)))
}
```

**Example:**
- Agent is Tier 1 (FULL trust) at Sovereign A
- Bilateral grant A→B caps admission at Tier 3 (MINIMAL)
- Agent operates at Tier 3 in Sovereign B (higher number = less trust, cost increases)
- Agent's behavior in B doesn't affect their Tier 1 status at A (isolation)

#### Behavior Event Isolation

All behavior events for cross-sovereign sessions are marked `lineage_safe = false`:

```sql
INSERT INTO behavior_events (
  session_id, event_type, tier_before, tier_after, tier_delta,
  cost_incurred, lineage_safe, scored_at
) VALUES (
  foreign_session_id, 'refresh_success', 3, 3, 0,
  150, false,  -- lineage_safe = false (ALWAYS for foreign agents)
  NOW()
);
```

**Scoring consequence (Phase 8):** `BehaviorScorer.compute_tier_delta()` filters out `lineage_safe = false` events. Foreign agent behavior is completely isolated from local behavior scoring.

```rust
for event in &self.events {
    if !event.lineage_safe {
        continue;  // Skip foreign events entirely
    }
    // ... apply decay and accumulate delta
}
```

**Result:** A malicious foreign agent cannot poison the local agent's trust score. Cross-sovereign behavior is invisible to intra-sovereign scoring.

#### Signed Trust Credential (Optional, Future)

**Phase 9 does not require this; it's a Phase 10 optimization.**

A source sovereign may issue a signed trust credential summarizing an agent's tier + evidence:
```json
{
  "agent_id": "alice",
  "sovereign_id": "<source UUID>",
  "tier": 1,
  "attestations_present": ["HardwareEnclave", "ModelIntegrity"],
  "issued_at": "2026-05-10T12:00:00Z",
  "signature": "<Ed25519 signature>"
}
```

Foreign sovereign can cache this and use it as `source_tier` without re-validating individual attestations.

#### Revocation Propagation

Cross-sovereign revocation uses **signed revocation certificates**, not DB cascade:

```sql
CREATE TABLE revocation_certificates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id VARCHAR(255) NOT NULL,
  source_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  revoked_at TIMESTAMPTZ NOT NULL,
  signature TEXT NOT NULL,  -- Ed25519 signature from source sovereign
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_revocation_certificates_agent ON revocation_certificates(agent_id, source_sovereign_id);
```

**Revocation Certificate Payload:**
```json
{
  "agent_id": "alice",
  "sovereign_id": "<source UUID>",
  "revoked_at": "<ISO8601>",
  "reason": "attestation integrity failure"
}
```

**Signature = Ed25519_sign(source_sovereign.private_key, canonical_json(payload_without_signature))**

**At each refresh:**
1. Check `revocation_certificates` for this agent + source sovereign
2. Verify signature against `sovereigns[source_sovereign].public_key_pem`
3. If found and verified, reject refresh (fail-closed)

### Key Decision: One-Directional Trust Flow

**Trust flows from source sovereign (certifier) to destination sovereign (capper).**

- Source sovereign says: "I certify this agent is Tier X"
- Destination sovereign says: "I accept Tier X, but I cap it at Tier Z (more conservative)"
- No negotiation, no amplification at the boundary
- Destination never elevates a foreign agent above the bilateral ceiling

**This mirrors Phase 6 Immutable Ceilings at inter-sovereign scale.**

### Schema Extensions

```sql
CREATE TABLE revocation_certificates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id VARCHAR(255) NOT NULL,
  source_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  revoked_at TIMESTAMPTZ NOT NULL,
  signature TEXT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_revocation_certificates_agent ON revocation_certificates(agent_id, source_sovereign_id);
CREATE INDEX idx_revocation_certificates_time ON revocation_certificates(received_at);
```

---

## Invariant 4: Inter-Sovereign Settlement

### The Law

**When an agent from Sovereign A consumes resources at Sovereign B, Sovereign B records a signed credit entry. Periodic settlement transfers the balance. The ledger is append-only, immutable, and conservative.**

### Core Rules

#### Credit Ledger

```sql
CREATE TABLE sovereign_credit_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creditor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  debtor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  session_id UUID NOT NULL REFERENCES sessions(id),
  tokens_consumed BIGINT NOT NULL,
  cost_breakdown JSONB NOT NULL,  -- {base: 100, tier: 50, attestations: 30, ...}
  scored_at TIMESTAMPTZ NOT NULL,
  settled_at TIMESTAMPTZ,  -- NULL until settled; never updated once set
  PRIMARY KEY (id)
);

CREATE INDEX idx_sovereign_credit_creditor ON sovereign_credit_entries(creditor_sovereign_id);
CREATE INDEX idx_sovereign_credit_debtor ON sovereign_credit_entries(debtor_sovereign_id);
CREATE INDEX idx_sovereign_credit_settled ON sovereign_credit_entries(settled_at) WHERE settled_at IS NULL;
```

#### Token Cost Formula (Phase 7 unchanged)

The existing formula from Phase 7 applies to foreign agents identically:

```
cost = max(50, 100 + tier_penalty + 10×attestations + delegation_cost)
```

A foreign agent at admitted Tier 3 with 2 attestations costs the same as a local agent at Tier 3 with 2 attestations.

#### Foreign Agent Budget Cap (Bilateral)

```sql
ALTER TABLE federation_peers
  ADD COLUMN foreign_agent_budget_cap BIGINT NOT NULL;
```

Per bilateral grant, a hard ceiling on tokens a foreign agent can consume per session:

```
If session.tokens_consumed + cost > federation_peers[source, dest].foreign_agent_budget_cap:
  DENY refresh with HTTP 402 (PAYMENT_REQUIRED)
  Detail: "Foreign agent budget cap exceeded"
```

This is a secondary safety limit (above settlement accounting) to prevent runaway consumption.

#### Credit Entry Recording

At each refresh by a foreign agent:

```rust
if is_federated_session {
    // 1. Check foreign agent budget cap
    if session.tokens_consumed + token_cost > federation_peers.foreign_agent_budget_cap {
        return 402_PAYMENT_REQUIRED;
    }
    
    // 2. Deduct tokens from session budget (Phase 7 atomic UPDATE)
    update_session_budget(session_id, token_cost).await?;
    
    // 3. Record credit entry (append-only, best-effort, never blocks)
    insert_sovereign_credit_entry(
        creditor: destination_sovereign_id,
        debtor: source_sovereign_id,
        session_id,
        tokens_consumed: token_cost,
        cost_breakdown,
        scored_at: now()
    ).await;
}
```

#### Settlement Flow (Periodic)

**Sovereign B (creditor) initiates settlement with Sovereign A (debtor):**

1. Query pending credit entries: `WHERE debtor = A AND creditor = B AND settled_at IS NULL`
2. Aggregate total tokens + cost breakdown
3. Create **Settlement Invoice** (JSON):
   ```json
   {
     "creditor_sovereign_id": "b-uuid",
     "debtor_sovereign_id": "a-uuid",
     "period_start": "2026-05-01T00:00:00Z",
     "period_end": "2026-05-31T23:59:59Z",
     "credit_entries": [
       {
         "id": "entry-uuid",
         "session_id": "session-uuid",
         "tokens_consumed": 500,
         "scored_at": "2026-05-15T12:00:00Z"
       }
     ],
     "total_tokens": 5000,
     "cost_usd": 25.00,
     "issued_at": "2026-06-01T00:00:00Z",
     "signature": "<Ed25519 signature from B>"
   }
   ```
4. Sign with B's private key: `Ed25519_sign(b_private_key, canonical_json(invoice_without_signature))`
5. Send to A (out-of-band, e.g., HTTP POST to A's `POST /federation/settle` endpoint)
6. A verifies signature, transfers funds/tokens, responds with signed **Settlement Receipt**:
   ```json
   {
     "invoice_id": "hash of invoice",
     "acknowledged": true,
     "settled_at": "2026-06-01T12:00:00Z",
     "signature": "<Ed25519 signature from A>"
   }
   ```
7. B receives receipt, marks credit entries as settled: `UPDATE sovereign_credit_entries SET settled_at = NOW() WHERE id IN (...)`

#### Conservation Invariant (Extended)

Phase 7 invariant for sessions: `token_budget_initial = token_budget_remaining + token_budget_consumed`

Phase 9 extends this to inter-sovereign level:

**For each Sovereign B receiving services from Sovereign A:**
```
total_credits_from_A = SUM(tokens_consumed) for all credit_entries where debtor=A AND creditor=B
total_credits_from_A = settled_credits + pending_credits
```

Credit entries are immutable. Once `settled_at` is set, that entry cannot be modified. This prevents retroactive fraud.

### Key Decision: Append-Only, Immutable Settlement

**The settlement ledger is the source of truth for inter-sovereign debt.**

- Credit entries are inserted exactly once (no updates, no deletes)
- `settled_at` is set only once, by Sovereign B, after receiving A's signed receipt
- No retroactive adjustments: if a dispute exists, it's a protocol-level negotiation, not a ledger edit
- This extends Phase 7's conservation invariant into federation: economic integrity is guaranteed by immutability, not by application logic

---

## Overarching Physics: Four Meta-Rules Governing All Invariants

### Rule 1: Fail-Closed at Every Boundary

**If any cross-sovereign check fails, deny by default. Never admit on ambiguity.**

Examples:
- Signature verification fails → 403 FORBIDDEN
- No bilateral grant exists → 403 FORBIDDEN
- Revocation certificate found and valid → 403 FORBIDDEN
- Foreign agent budget cap exceeded → 402 PAYMENT_REQUIRED
- DB fetch error for public key → 500 INTERNAL_SERVER_ERROR (deny refresh)

**No soft failures. No "best-effort" admission of foreign agents. If the invariant is violated, the boundary closes.**

### Rule 2: Immutable Bilateral Agreements

**Federation peer agreements are versioned and immutable once established.**

- Composite key: `(sovereign_a_id, sovereign_b_id, granted_at)`
- Old grants remain valid for existing sessions (backward compatibility)
- Renegotiation creates a new grant record with a new `granted_at`
- No mutation of existing grants (prevents retroactive privilege escalation)

**This mirrors Phase 6 Immutable Ceilings at the sovereign level.**

### Rule 3: Local Sovereignty is Inviolable

**Phase 4-8 invariants apply to all agents, local or foreign. Federation adds constraints; it never removes policy.**

Examples:
- A foreign agent still subject to local `TrustPolicyNode` rules
- Local ReBAC deny-first evaluation applies to foreign agents
- A foreign agent cannot access a local resource unless local policy permits it
- Phase 7 token budget constraints apply (foreign agents respect budget limits)
- Phase 8 behavior scoring isolation (lineage_safe=false) is mandatory

**Federation is a constraining layer, not a privilege escalation mechanism.**

### Rule 4: Explicit Bilateral Trust, Non-Transitive

**A ↔ B and B ↔ C does NOT imply A ↔ C.**

- Every cross-sovereign path requires its own bilateral grant
- If A's only path to C is through B, A still cannot trust C unless A and C establish a direct bilateral agreement
- This bounds the blast radius of a compromised sovereign (if B is compromised, only A↔B and B↔C are affected; A↔C remains unaffected)

**Trust is explicit at every hop. No implicit chains. No transitive amplification.**

---

## Data Schema Overview

### New Tables (Phase 9)

| Table | Purpose | Key Columns |
|-------|---------|---|
| `sovereigns` | Sovereign node registry | `id (PK), name, public_key_pem, status, established_at` |
| `federation_peers` | Bilateral trust grants | `(sovereign_a_id, sovereign_b_id, granted_at) (composite PK), max_admitted_tier, granted_attestation_types, foreign_agent_budget_cap` |
| `revocation_certificates` | Signed revocation notices | `id (PK), agent_id, source_sovereign_id, revoked_at, signature, received_at` |
| `sovereign_credit_entries` | Settlement ledger | `id (PK), creditor_sovereign_id, debtor_sovereign_id, session_id, tokens_consumed, cost_breakdown JSONB, scored_at, settled_at` |

### Modified Tables (Phase 9)

| Table | Changes |
|-------|---------|
| `tenants` | Add `sovereign_id FK → sovereigns(id)` |
| `personas` | Add `origin_sovereign_id FK → sovereigns(id) [nullable]` |
| `sessions` | Add `is_federated_session BOOLEAN DEFAULT FALSE` |

### Cryptographic Contracts

All cross-sovereign communication involving sensitive data uses **Ed25519 digital signatures**:

1. **SovereignOrigin Attestation Signature**
   - Message: canonical JSON of payload (excluding signature field)
   - Algorithm: Ed25519
   - Verification: `Ed25519_verify(sovereigns[source_id].public_key_pem, canonical_json, signature)`

2. **Revocation Certificate Signature**
   - Message: canonical JSON of `{agent_id, sovereign_id, revoked_at, reason}`
   - Algorithm: Ed25519
   - Verification: same as above

3. **Settlement Invoice Signature**
   - Message: canonical JSON of invoice (excluding signature field)
   - Algorithm: Ed25519
   - Verification: same as above

4. **Settlement Receipt Signature**
   - Message: canonical JSON of `{invoice_id, acknowledged, settled_at}`
   - Algorithm: Ed25519
   - Verification: same as above (verified by issuing sovereign)

---

## Error Semantics

### HTTP Status Codes (Cross-Sovereign Operations)

| Status | Reason | Remediation |
|--------|--------|---|
| **200 OK** | Refresh succeeded | (no action) |
| **400 BAD_REQUEST** | Malformed attestation | Check payload schema, try again |
| **402 PAYMENT_REQUIRED** | Foreign agent budget cap or token budget exhausted | Request higher budget ceiling from destination sovereign |
| **403 FORBIDDEN** | Signature verification failed, no bilateral grant, wrong attestation type, revocation certificate found, or tier admission failure | Verify identity, check bilateral agreement status, verify source sovereign's public key |
| **500 INTERNAL_SERVER_ERROR** | Sovereign registry lookup failure, public key fetch error, DB error | Destination sovereign may have connectivity issues; retry after delay |

### Response Body (403 Example)

```json
{
  "status": "denied",
  "reason": "cross_sovereign_verification_failed",
  "detail": "Signature verification failed for SovereignOrigin attestation from sovereign a-uuid",
  "remediation": [
    "Verify source sovereign's public key is registered in destination's sovereigns table",
    "Check bilateral agreement federation_peers[source, dest] exists",
    "Verify attestation was issued by source sovereign's private key"
  ]
}
```

---

## Specification Compliance Checklist

- [ ] Invariant 1 (Federated Identity): 3-tuple (sovereign_id, tenant_id, persona_id), shadow personas, sovereign registration
- [ ] Invariant 2 (Cross-Sovereign Attestation Verification): bilateral grants, cryptographic verification, non-transitive trust
- [ ] Invariant 3 (Federated Trust Resolution): min(source_tier, bilateral_max), behavior isolation (lineage_safe=false), revocation propagation
- [ ] Invariant 4 (Inter-Sovereign Settlement): append-only credit ledger, budget caps, conservation invariant
- [ ] Rule 1 (Fail-Closed): all boundary checks return 403/402/500, never silently admit
- [ ] Rule 2 (Immutable Bilateral Agreements): composite key versioning, old grants remain valid
- [ ] Rule 3 (Local Sovereignty Inviolable): Phase 4-8 rules apply to foreign agents
- [ ] Rule 4 (Explicit Bilateral Trust, Non-Transitive): no implicit chains, every path requires grant

---

## Known Limitations & Future Work

### Phase 9 Limitations

1. **No dynamic trust renegotiation**: Bilateral grants are immutable for their lifetime. Renegotiation requires a new grant (new `granted_at`). No in-flight renegotiation of existing sessions.
2. **Settlement is offline**: Settlement invoices are sent out-of-band (not HTTP endpoint yet). Phase 10 may add a federation settlement service.
3. **No transitive delegation**: An agent cannot delegate cross-sovereign (Phase 6 delegation is intra-sovereign only). Phase 10 may add cross-sovereign delegation.
4. **No reputation blending**: A foreign agent's home tier is simply capped, not harmonized. No scoring function that blends home and destination behavior.
5. **Revocation is eventual-consistent**: Revocation certificates must be fetched and cached. A source sovereign revoking an agent is not instantly visible to all destinations (gossip delay).

### Phase 10+ Enhancements

- **Dynamic bilateral renegotiation**: In-flight session tier adjustment if bilateral grant is updated
- **Cross-sovereign delegation**: Enable an agent to delegate to a foreign agent (with caps propagating)
- **Reputation blending**: Weighted scoring function combining home and destination behavior
- **Trust transitivity (controlled)**: Explicit "trust path" grant: A grants B permission to trust A's decisions about C
- **Federated settlement service**: Automated, real-time settlement with escrow and dispute resolution
- **Sovereign reputation**: Aggregate trust score for sovereigns based on their agents' behavior elsewhere

---

## Migration Preview

### Migration 014: Sovereign Identity Schema

```sql
CREATE TABLE sovereigns (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  public_key_pem TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  established_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE tenants ADD COLUMN sovereign_id UUID NOT NULL REFERENCES sovereigns(id);
ALTER TABLE personas ADD COLUMN origin_sovereign_id UUID REFERENCES sovereigns(id);
ALTER TABLE sessions ADD COLUMN is_federated_session BOOLEAN NOT NULL DEFAULT FALSE;
```

### Migration 015: Bilateral Trust & Revocation

```sql
CREATE TABLE federation_peers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sovereign_a_id UUID NOT NULL REFERENCES sovereigns(id),
  sovereign_b_id UUID NOT NULL REFERENCES sovereigns(id),
  max_admitted_tier SMALLINT NOT NULL,
  granted_attestation_types TEXT[] NOT NULL,
  foreign_agent_budget_cap BIGINT NOT NULL,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  PRIMARY KEY (sovereign_a_id, sovereign_b_id, granted_at)
);

CREATE TABLE revocation_certificates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id VARCHAR(255) NOT NULL,
  source_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  revoked_at TIMESTAMPTZ NOT NULL,
  signature TEXT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Migration 016: Settlement Ledger

```sql
CREATE TABLE sovereign_credit_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creditor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  debtor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  session_id UUID NOT NULL REFERENCES sessions(id),
  tokens_consumed BIGINT NOT NULL,
  cost_breakdown JSONB NOT NULL,
  scored_at TIMESTAMPTZ NOT NULL,
  settled_at TIMESTAMPTZ
);
```

---

## Deployment Checklist

- [ ] Backup existing database
- [ ] Run migrations 014, 015, 016
- [ ] Register home sovereign in `sovereigns` table with public key (setup task)
- [ ] Establish bilateral agreements with peer sovereigns in `federation_peers` table
- [ ] Implement Ed25519 cryptographic verification in `validate_attestation()`
- [ ] Implement `resolve_federated_tier()` function
- [ ] Implement `insert_sovereign_credit_entry()` in refresh handler (Step 9.5 + Phase 7)
- [ ] Test: send cross-sovereign attestation, verify signature validation and tier capping
- [ ] Test: deplete foreign agent budget cap, verify 402 response
- [ ] Test: issue revocation certificate, verify next refresh is denied
- [ ] Test: record credit entry, verify conservation (pending + settled = total)
- [ ] Send notification to operators about Phase 9 federation endpoints + bilateral setup process

---

## Summary: The Federation Physics

**Phases 4–8 built a single sovereign's substrate: attestation-driven trust, delegation ceilings, economic constraints, behavioral feedback.**

**Phase 9 scales it to a network: multiple sovereigns coordinate without surrendering autonomy.**

The four constitutional invariants ensure:
1. **Identity is verifiable** (not assumed)
2. **Trust is explicit and bilateral** (not implicit or transitive)
3. **Tier is capped at boundaries** (no privilege amplification)
4. **Resources are settled** (no invisible debt)

Four overarching meta-rules guarantee fail-closed execution, immutability, local sovereignty preservation, and non-transitive trust propagation.

**Everything else in Phase 9 implementation (Tasks 35–42) is mechanically derived from these invariants and rules.**
