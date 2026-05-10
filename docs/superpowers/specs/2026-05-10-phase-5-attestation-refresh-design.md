# Phase 5: Attestation Refresh & Mid-Session Trust Updates — Design Specification

> **Architectural Status:** APPROVED
> **Date:** 2026-05-10
> **Scope:** Mid-session attestation refresh, capability re-evaluation, verifiable trust, self-correcting error loops

---

## 1. Overview

Phase 5 enables external agents to refresh their attestations mid-session without re-running the full Phase 4 handshake. When an external agent obtains fresh evidence (new TEE quote, updated model signature, refreshed jurisdiction proof, etc.), it can POST attestations to a dedicated refresh endpoint. SISS re-evaluates trust against the current TrustPolicyNode, reissues tokens, and returns a transparent audit trail showing exactly how the agent's trust status changed.

**Core Design Principle:** Verifiable Trust, Not Black-Box Trust.

SISS is not a hidden oracle. Every trust decision is transparent, deterministic, and programmable. External agents can read the evaluation and understand exactly why their access expanded, contracted, or was denied.

---

## 2. Attestation Refresh Architecture

### 2.1 Core Semantic

Attestation refresh has three layered meanings:

**Layer 1 — Primary Meaning (Push)**  
External agent proactively POSTs new attestations mid-session.
- Agent obtains fresh evidence (new TEE quote, new model signature, jurisdiction update)
- Agent generates ephemeral nonce and cryptographic proof
- SISS re-evaluates trust, may issue new capability_token, updates session_token if needed
- Agent gains deterministic visibility into why its capabilities changed

**Layer 2 — Optional Meaning (Pull)**  
SISS requests updated attestations when trust boundaries are crossed.
- SISS detects: attestation about to expire, policy changed, high-risk tool invoked, or suspicious behavior
- SISS returns 401 with "refresh_required" and expected criteria
- Agent responds with fresh attestations
- No full re-handshake, no re-negotiation of auth scheme

**Layer 3 — Emergent Behavior (Continuity)**  
Sessions extend without full Phase 4 handshake.
- Same session_token (identity is stable)
- New capability_token (trust is updated)
- Deterministic, evidence-driven, revocable
- This is the sovereign equivalent of OAuth2 refresh tokens

### 2.2 Initiation Model: Hybrid (Push-First, Pull-Second)

**MVP (Phase 5.0):** Push-based refresh only
- External agent initiates refresh anytime it has new evidence
- SISS accepts/rejects deterministically
- Simple, agent-driven, stateless on SISS side

**Phase 5.5 Enhancement:** Pull capability
- SISS can return 401 with "refresh_required" error
- Error includes expected attestation criteria
- Agent responds with fresh attestations
- No complex challenge flows yet; simple request/response

This design preserves sovereignty (SISS controls trust) while maximizing agent autonomy (agent can proactively improve trust tier).

---

## 3. Attestation Refresh Endpoint: POST /.well-known/a2a/refresh

### 3.1 Discovery and Separation

The refresh endpoint is **separate from Phase 4's handshake endpoint** for architectural clarity:

```
Phase 4 (Handshake):
  GET  /.well-known/agent.json          (discovery: agent card)
  POST /.well-known/a2a/handshake       (negotiation: auth scheme + initial tokens)

Phase 5 (Refresh):
  POST /.well-known/a2a/refresh         (mid-session: update attestations + tokens)
```

**Why separate endpoints:**
- Handshake = initial trust establishment (complex, stateful)
- Refresh = mid-session trust update (simple, lightweight)
- Distinct request/response schemas
- Independent versioning (/.well-known/a2a/v1/refresh, v2/refresh, etc.)
- Follows well-known protocol patterns (OIDC, ActivityPub, MCP)

### 3.2 Request Payload: AttestationRefreshRequest

External agent POSTs a refresh request with:
- Session token (proves existing session)
- Updated attestations (new evidence)
- Cryptographic proof of key possession (prevents replay/spoofing)

**Schema:**

```json
{
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "attestations": [
    {
      "type": "hardware_enclave",
      "format": "sgx_quote",
      "payload": "<base64-encoded SGX quote>",
      "signature": "<signature-over-payload>",
      "issuer": "intel-sgx-signer",
      "issued_at": "2026-05-10T14:32:00Z",
      "valid_until": "2026-05-11T14:32:00Z"
    }
  ],
  "ephemeral_nonce": "<64-byte random hex>",
  "timestamp": "2026-05-10T14:33:15Z",
  "proof_signature": "<signature-over-refresh-message>"
}
```

**Proof Signature Computation (Stateless, Replay-Safe):**

The external agent constructs a refresh message and signs it with its private key:

```
refresh_message = concat(
  "SISS:A2A:REFRESH",
  session_id (extracted from session_token),
  SHA256(ephemeral_nonce),
  timestamp,
  SHA256(canonical_json(attestations))
)

proof_signature = sign(refresh_message, agent_private_key)
```

**Cryptographic Guarantees:**

- **Replay prevention:** Nonce + timestamp make each request unique
- **Key possession proof:** Only the agent's private key can produce valid signature
- **Attestation binding:** Signature covers hash of attestations; modifying attestations invalidates signature
- **Session binding:** Signature covers session_id; cannot reuse signature in another session
- **Stateless validation:** SISS validates timestamp freshness (±5 min window, configurable) + signature + attestations without storing nonce

---

## 4. Response Payload: AttestationRefreshResponse (Success Case)

When SISS receives a valid refresh request, it:

1. **Validates the request** (signature, timestamp freshness, session_token validity)
2. **Validates each attestation** (signature, issuer, freshness, schema compliance)
3. **Re-evaluates trust** (same algorithm as Phase 4, against current TrustPolicyNode)
4. **Issues updated tokens** (session_token if needed, new capability_token)
5. **Returns transparent evaluation** (Why the trust status changed)

**Success Response Schema:**

```json
{
  "status": "refreshed",
  "session_token": {
    "token": "<new-or-existing-session-jwt>",
    "expires_in": 3600,
    "token_type": "Bearer"
  } | null,
  "session_token_reused": boolean,
  "capability_token": {
    "token": "<signed-capability-envelope>",
    "delegations": [
      {
        "permission": "can_execute",
        "resource_type": "tool",
        "resource_ids": ["tool-uuid-1", "tool-uuid-2"],
        "constraints": {
          "rate_limit": "1000/minute",
          "max_concurrent": 5,
          "allowed_hardware": ["LocalMlx", "Hybrid"]
        }
      }
    ],
    "issued_at": "2026-05-10T14:33:15Z",
    "valid_until": "2026-05-11T14:33:15Z"
  },
  "attestation_evaluation": {
    "score": 80,
    "tier": 2,
    "attestations": {
      "hardware_enclave": {
        "passed": true,
        "score_contribution": 50,
        "issuer": "intel-sgx",
        "freshness_seconds": 120
      },
      "model_integrity": {
        "passed": true,
        "score_contribution": 30,
        "issuer": "anthropic",
        "model_id": "claude-opus-4.6",
        "hash": "sha256:abc123def456..."
      },
      "sovereign_origin": {
        "passed": false,
        "score_contribution": 0,
        "reason": "jurisdiction_not_in_allowlist",
        "required_jurisdictions": ["EU"],
        "provided_jurisdiction": "US",
        "policy_reference": "TrustPolicyNode:persona-alice"
      },
      "runtime_integrity": {
        "passed": false,
        "score_contribution": 0,
        "reason": "tpm_pcr_mismatch",
        "expected_pcr": "sha256:def456ghi789...",
        "provided_pcr": "sha256:xyz789abc123...",
        "last_verified": "2026-05-10T14:32:00Z"
      }
    },
    "policy_overrides_applied": [
      "rate_limit_reduced_to_500_per_minute",
      "max_concurrent_reduced_to_2"
    ],
    "capability_changes": {
      "can_execute_high_risk_tools": {
        "before": true,
        "after": false,
        "reason": "sovereign_origin_failed"
      },
      "can_access_eu_only_data": {
        "before": true,
        "after": false,
        "reason": "sovereign_origin_failed"
      },
      "can_run_long_lived_sessions": {
        "before": true,
        "after": false,
        "reason": "runtime_integrity_failed"
      },
      "can_execute_standard_tools": {
        "before": true,
        "after": true,
        "reason": null
      }
    }
  }
}
```

**Field Semantics:**

- `session_token`: Renewed session token if near expiry (1-hour default); null if reused
- `session_token_reused`: Boolean flag indicating whether session_token is new or unchanged
- `capability_token`: Updated delegations + constraints based on new trust evaluation
- `attestation_evaluation.score`: Recomputed attestation score (0–120)
- `attestation_evaluation.tier`: Assigned security tier (1=full, 2=standard, 3=minimal)
- `attestation_evaluation.attestations`: Per-type evaluation with reason codes for failures
- `attestation_evaluation.policy_overrides_applied`: List of TrustPolicyNode rules that tightened constraints
- `attestation_evaluation.capability_changes`: Before/after view of what the agent can do, plus reason why each changed

---

## 5. Response Payload: AttestationRefreshResponse (Failure Cases)

When attestation refresh fails, SISS returns an error response with:
- Clear reason code
- Full attestation evaluation (showing why the request was rejected)
- Remediation hints (guiding the external agent on how to fix the problem)

**Failure Response Schema:**

```json
{
  "status": "denied",
  "reason": "<reason-code>",
  "detail": "<human-readable-explanation>",
  "remediation": [
    "<action-1>",
    "<action-2>"
  ],
  "attestation_evaluation": {
    "score": 0,
    "tier": null,
    "attestations": {
      "hardware_enclave": {
        "passed": false,
        "reason": "not_evaluated_signature_failed"
      },
      "model_integrity": {
        "passed": false,
        "reason": "not_evaluated_signature_failed"
      },
      "sovereign_origin": {
        "passed": false,
        "reason": "not_evaluated_signature_failed"
      },
      "runtime_integrity": {
        "passed": false,
        "reason": "not_evaluated_signature_failed"
      }
    }
  }
}
```

**Common Failure Scenarios:**

**Case 1: Request Signature Invalid**
```json
{
  "status": "denied",
  "reason": "signature_invalid",
  "detail": "Could not verify proof_signature with agent's public key from AgentCard",
  "remediation": [
    "Verify your private key matches the public key in your AgentCard",
    "Ensure you signed the correct message format: SISS:A2A:REFRESH || session_id || SHA256(nonce) || timestamp || SHA256(attestations)",
    "Check that your signature algorithm matches TrustPolicyNode requirements (e.g., Ed25519, ECDSA)"
  ]
}
```

**Case 2: Session Token Expired**
```json
{
  "status": "denied",
  "reason": "session_token_expired",
  "detail": "Session token expired at 2026-05-10T15:33:00Z; current time 2026-05-10T16:00:00Z",
  "remediation": [
    "Re-run Phase 4 handshake to establish a new session",
    "POST to /.well-known/a2a/handshake with your current attestations"
  ]
}
```

**Case 3: Attestation Validation Failed**
```json
{
  "status": "denied",
  "reason": "attestation_validation_failed",
  "detail": "hardware_enclave attestation signature verification failed against intel-sgx issuer key",
  "remediation": [
    "Obtain a fresh hardware_enclave attestation from your TEE (SGX enclave, TPM, etc.)",
    "Ensure the attestation issuer (intel-sgx, arm-tee, etc.) is in TrustPolicyNode.allowed_issuers",
    "Check that the attestation is not expired: valid_until > current_time"
  ],
  "attestation_evaluation": {
    "score": 0,
    "attestations": {
      "hardware_enclave": {
        "passed": false,
        "reason": "signature_verification_failed",
        "issuer": "intel-sgx",
        "expected_issuers": ["intel-sgx"]
      }
    }
  }
}
```

**Case 4: Trust Policy Hard Requirement Not Met**
```json
{
  "status": "denied",
  "reason": "hard_requirement_failed",
  "detail": "TrustPolicyNode requires hardware_enclave attestation; none provided",
  "remediation": [
    "Obtain hardware_enclave attestation from your deployment environment (SGX, SEV, Nitro, etc.)",
    "Include the attestation in your next refresh request"
  ]
}
```

---

## 6. Trust Re-Evaluation Algorithm (Refresh Path)

When SISS receives a valid refresh request, it runs the same three-stage evaluation as Phase 4, but with updated inputs:

### Stage 1: Attestation Validation
For each attestation in the refresh request:
- Verify signature against issuer's public key (from graph)
- Check freshness (issued_at is recent)
- Check expiry (valid_until > current_time)
- Check against TrustPolicyNode.attestation_requirements

### Stage 2: Attestation Scoring
Compute security score based on what passed:
- hardware_enclave: +50 points
- model_integrity: +30 points
- sovereign_origin: +20 points (jurisdiction-specific)
- runtime_integrity: +20 points
- **Maximum score: 120 points**

### Stage 3: Tier Assignment & Capability Granting
Assign tier from score:
- score ≥ 100 → Tier 1 (FULL delegation)
- score ≥ 70 → Tier 2 (STANDARD delegation)
- score ≥ 40 → Tier 3 (MINIMAL delegation)
- score < 40 → DENY

Then apply TrustPolicyNode decision tree:
- Hard requirements must pass (else DENY)
- Capability overrides tighten/deny specific capabilities
- Rate limits applied from tier + overrides
- capability_token constructed from final delegations

**Key Difference from Phase 4:** The evaluation is incremental. SISS re-scores attestations independently; previous tier/score is not carried forward. Each refresh is a fresh evaluation against current TrustPolicyNode.

---

## 7. Token Lifecycle on Refresh

### Session Token Behavior

**Default (Option B):**
- If session_token is still valid (TTL > 10 minutes remaining), reuse it
- Set `session_token_reused: true`
- No new session_token in response (null)

**When session_token is rotated:**
- If session_token is near expiry (< 10 minutes remaining), issue new one
- Set `session_token_reused: false`
- Include new session_token in response
- Old session_token becomes invalid immediately

### Capability Token Behavior

**Always refreshed:**
- New capability_token issued on every refresh
- Old capability_token is revoked immediately
- New token includes updated delegations based on re-evaluation

**Why separate tokens:**
- session_token = authentication (identity + scheme)
- capability_token = authorization (delegations + constraints)
- Attestation refresh affects authorization, not identity
- This separation allows gradual trust updates without breaking sessions

### Token Expiry Rules

**Session Token Expiry:**
- Configured per persona in TrustPolicyNode.session_token_expiry_seconds
- Default: 3600 seconds (1 hour)
- On refresh: expiry reset to (now + session_token_expiry_seconds)

**Capability Token Expiry:**
- Configured per persona in TrustPolicyNode.capability_token_expiry_seconds
- Default: 86400 seconds (24 hours)
- On refresh: expiry = min(now + capability_token_expiry_seconds, earliest_attestation_expiry)
- **Key invariant:** Capability token cannot live longer than the shortest-lived attestation it's based on

---

## 8. Verifiable Trust: The Attestation Evaluation Report

The `attestation_evaluation` object in the response serves two purposes:

### 8.1 Why It Exists: Agentic Transparency

External agents are not passive consumers of access decisions. They are **autonomous orchestrators** that need to:

1. **Understand why they were downgraded or denied**
   - Agent received new tier 3 instead of tier 1
   - Agent reads: `"failed_attestations": ["sovereign_origin"]`
   - Agent understands: "I'm in US, policy requires EU. I need to route through EU node."

2. **Make deterministic decisions about fallback strategies**
   - Agent reads: `"can_execute_high_risk_tools": { "after": false, "reason": "sovereign_origin_failed" }`
   - Agent knows: "Don't attempt high-risk tools, switch to standard tool set"

3. **Debug cryptographic failures without wasting compute**
   - Signature verification failed? Agent sees reason code
   - Agent can fix the key or nonce and retry
   - No blind "guess and check" loops

### 8.2 Structure: Hybrid B+C (Why + What)

The evaluation has two layers:

**Layer 1 (Why): Attestations Detail**
```json
"attestations": {
  "hardware_enclave": {
    "passed": true,
    "score_contribution": 50,
    "issuer": "intel-sgx",
    "freshness_seconds": 120
  },
  "sovereign_origin": {
    "passed": false,
    "reason": "jurisdiction_not_in_allowlist",
    "required_jurisdictions": ["EU"],
    "provided_jurisdiction": "US"
  }
}
```

Agent's reasoning:
- "Score is 50 from TEE, need 70 for standard tier"
- "Sovereign origin failed because I'm in US"
- "To reach tier 2, I need either model_integrity (+30) or sovereign_origin (+20)"
- "Action: Obtain model_integrity attestation or switch to EU"

**Layer 2 (What): Capability Changes**
```json
"capability_changes": {
  "can_execute_high_risk_tools": {
    "before": true,
    "after": false,
    "reason": "sovereign_origin_failed"
  },
  "can_access_eu_only_data": {
    "before": true,
    "after": false,
    "reason": "sovereign_origin_failed"
  }
}
```

Agent's execution logic:
- "I lost `can_execute_high_risk_tools`"
- "I lost `can_access_eu_only_data`"
- "Don't attempt these operations"
- "Switch to available capabilities: standard tools, public data"

---

## 9. Pull-Based Refresh (Phase 5.5 Future)

### Why Pull is Phase 5.5, not MVP

Push-based refresh is stateless and simple for Phase 5.0. Pull-based refresh adds complexity:
- SISS must track "attestation expiry timers" per session
- SISS must construct challenges and nonce management
- SISS must interrupt sessions to request proof

**When Pull becomes essential (Phase 5.5):**
- High-risk tools require real-time trust proof ("Are you still in a TEE?")
- Policy changes need immediate enforcement ("New jurisdiction rules apply now")
- Behavioral anomalies trigger trust revalidation ("Why did you access that data?")
- Session longevity demands continuous evidence ("Prove you're still the same agent")

### Pull Mechanism (Sketch)

On high-risk operation, SISS can return:

```json
{
  "status": 401,
  "error": "refresh_required",
  "challenge": {
    "nonce": "<64-byte random hex>",
    "required_attestations": ["hardware_enclave"],
    "issued_at": "2026-05-10T14:35:00Z",
    "expires_at": "2026-05-10T14:40:00Z"
  }
}
```

Agent responds by POSTing to `POST /.well-known/a2a/refresh` with the nonce in the proof signature:

```
refresh_message = concat(
  "SISS:A2A:REFRESH:CHALLENGE",
  session_id,
  SHA256(nonce),  // <- from challenge
  timestamp,
  SHA256(attestations)
)
```

SISS validates the nonce matches the issued challenge (single-use), then processes the refresh normally.

---

## 10. Integration with Phase 4 & Future Phases

### Dependency Chain

**Phase 4 (Handshake):**
- Establishes initial session_token + capability_token
- Runs first trust evaluation
- Creates SessionNode in graph

**Phase 5 (Attestation Refresh):**
- Updates capability_token mid-session
- Runs incremental trust re-evaluation
- No SessionNode changes (same session)
- Foundation for all downstream phases

**Phase 5.5 (Revocation + Pull):**
- SISS can revoke tokens by marking SessionNode as revoked
- Revocation triggers pull-based refresh challenge
- Attestation expiry becomes revocation trigger

**Phase 6 (Delegation Chains):**
- Delegated agents use refresh to prove they're still trusted
- Each agent in chain has transparent evaluation
- Revocation propagates through delegation tree

**Phase 7 (Multi-Party Negotiation):**
- Three+ agents coordinate via refresh
- Each agent sees evaluation in context of others
- Sovereign multi-agent workflows enabled

---

## 11. Design Decisions & Rationale

**Why separate endpoint (not reuse handshake)?**
- Handshake is complex (auth scheme negotiation, agent card exchange, initial trust)
- Refresh is lightweight (just attestation + proof)
- Distinct concerns → distinct endpoints
- Allows independent versioning (/v1/refresh, /v2/refresh)

**Why stateless proof (not server nonce storage)?**
- Eliminates session store scaling bottleneck
- Enables multi-instance SISS deployments (no shared state)
- Timestamp + signature gives SISS what it needs to validate
- Matches modern API security best practices (JWT, PKCE, etc.)

**Why capability_token refresh on every call (not incremental)?**
- Ensures deterministic, revocable authorization
- Prevents overlapping authority windows
- Simplifies policy enforcement logic
- Matches least-privilege principle

**Why transparent evaluation (not black-box)?**
- Enables agentic self-correction (not blind retries)
- Establishes verifiable trust (not faith-based access)
- Supports enterprise audit requirements (reproducible decisions)
- Aligns with sovereign substrate philosophy

**Why hybrid B+C error response (not minimal)?**
- Minimal errors leave agents confused
- Detailed errors enable autonomous recovery
- Remediation hints prevent token wastage on failed attempts
- Audit trail proves SISS made deterministic decision

---

## 12. Crate Mapping

| Component | Crate | Status |
|-----------|-------|--------|
| Attestation Validation | siss-gatekeeper (extend) | Phase 5 |
| Refresh Handler | siss-agent-card (extend) | Phase 5 |
| Trust Re-Evaluation | siss-gatekeeper (reuse) | Phase 4 (reuse) |
| Session Validation | siss-agent-card + siss-graph-db | Phase 5 |
| Evaluation Reporting | siss-gatekeeper (new module) | Phase 5 |

---

## 13. Open Questions & Future Phases

- **Pull challenge flows:** How does SISS construct and manage challenge nonces? (Phase 5.5)
- **Revocation mechanism:** How are tokens revoked and sessions terminated? (Phase 5.5)
- **Delegation refresh:** Do delegated agents refresh independently or through delegator? (Phase 6)
- **Multi-agent trust composition:** How do three+ agents coordinate refresh? (Phase 7)

---
