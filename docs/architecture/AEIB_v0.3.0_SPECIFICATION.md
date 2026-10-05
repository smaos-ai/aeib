# AEIB v0.3.0 Consolidated Specification: Bounded Detection Authority & Transport-Disposition Contract

**Standard Version:** 0.3.0  
**Status:** Canonical Engineering Specification  
**Classification:** Open Core Profile under Apache-2.0  
**Scope:** Post-Dispatch Transport Ambiguity & Execution Integrity Boundary for AI Agent Tool Calls  

---

## Executive Architectural Summary

AEIB (Agent Execution Integrity Benchmark) formalizes the post-dispatch execution boundary between probabilistic agent reasoning and physical external mutation sinks. Traditional agent middleware assumes that tool execution is either synchronously confirmed or safely absent upon exception. Under distributed network transports, however, ambiguous transport anomalies (e.g., HTTP 504 Gateway Timeout, dropped TCP sockets, connection resets) leave external ledger states indeterminate.

AEIB v0.3.0 establishes an immutable, non-subsumable pipeline grounded in **bounded detection authority, immutable wire facts, explicit probe metadata, and fail-closed retry safety**, strictly enforcing the foundational boundary: **"Verified is not released."**

---

## 🏛️ The 11-Part Specification Architecture

### Part 1: Functional Layering
The execution boundary is split into four explicit, non-subsumable layers:
* **Layer 7a (Transport Observation):** Captures physical wire facts (status codes, connection resets, network drops).
* **Layer 7b (Authoritative Probing):** Performs read-only queries against external target state stores where interfaces exist.
* **Layer 7c (Disposition Derivation):** Evaluates a deterministic mapping contract combining Layer 7a and 7b facts into a discrete disposition and binding retry policy.
* **Layer 8 (Evidence Verification):** Canonicalizes recorded execution traces (RFC 8785 JCS) and seals them into Ed25519/COSE-signed, SCITT-inspired receipts for offline inspection.

Upstream Layer 1–6 models handle reasoning and intent formulation; downstream Layer 9 authorities consume verified receipts to determine release or manual compensation.

---

### Part 2: Immutable Transport Fact
* **Rule:** The `aeib.transport.observation` attribute represents an immutable, physical event recorded at Layer 7a (e.g., `http_504_after_dispatch`, `tcp_reset`, `econnrefused`).
* **Non-Subsumability:** An upstream model hypothesis, prompt re-evaluation, or speculative reasoning trace (Layer 1–6) **cannot overwrite, mask, or downgrade** the recorded wire observation.

---

### Part 3: Explicit Probe Scope & Consistency Model
* **Scope Binding:** Every Layer 7b probe execution must explicitly declare two metadata attributes:
  * `aeib.probe.authority_scope`: The exact domain or target boundary queried (e.g., `provider_primary`, `local_cache`, `replica_read`).
  * `aeib.probe.consistency_model`: The transaction/read guarantee of the queried sink (`strong_read`, `read_after_write`, or `eventual_read`).
* **Indeterminacy Invariant:** If a target system exhibits replica lag or eventual consistency (`consistency_model = eventual_read`), a negative read (record not found) cannot prove absence. In such cases, Layer 7c must emit `EFFECT_INDETERMINATE` rather than assuming non-execution.

---

### Part 4: Provider-Bound Retry & Fail-Closed Safety
* **Default Safe State:** When an authoritative probe cannot verify downstream execution after the grace period, Layer 7c defaults to:
  ```json
  {
    "disposition": "RECONCILIATION_NOT_FOUND_AFTER_GRACE",
    "retry_safe": false,
    "quarantine_latch": true
  }
  ```
* **Re-Issue Precondition:** `retry_safe` may evaluate to `true` **if and only if** an explicit provider idempotency contract (e.g., IETF AADP compliance, enforced UUIDv5 CAID primary key deduction) guarantees downstream server-side deduplication. Without such proof, the workflow latches closed.

---

### Part 5: OpenTelemetry Semantic Convention Integration
AEIB emits execution events as structured `LogRecord` instances under the dedicated namespace `aeib.*`, designed to nest cleanly within existing OpenTelemetry GenAI spans:
* **Span Preservation:** Does not corrupt or overwrite standard `gen_ai.tool.call` spans.
* **Event Name:** `aeib.effect_disposition`
* **Core Attributes:**
  * `aeib.caid`: Content-Addressed Action Identifier ($H(\text{Noun} \parallel \text{Verb} \parallel \text{JCS}(\text{Payload}))$).
  * `aeib.transport.observation`: Physical Layer 7a wire outcome.
  * `aeib.disposition`: Contract-derived state (`OUTCOME_VERIFIED`, `DISPATCHED_UNCONFIRMED`, `PROBE_UNAVAILABLE`, `RECONCILIATION_CONFLICT`, `RECONCILIATION_NOT_FOUND_AFTER_GRACE`).
  * `aeib.retry_safe`: Boolean flag governing execution re-dispatch.
  * `aeib.release_authorization`: Strictly `"not_provided"` inside the disposition event.

---

### Part 6: Registry Schema & `cannot_assert` Authority Bounds
To prevent cross-layer authority leaks, every participant in the AEIB pipeline operates under a machine-readable JSON schema defining explicit bounds:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AEIB Authority Registration",
  "type": "object",
  "required": ["layer", "authority_class", "can_assert", "cannot_assert"],
  "properties": {
    "layer": { "type": "string", "enum": ["L7a", "L7b", "L7c", "L8"] },
    "authority_class": { "type": "string" },
    "can_assert": { "type": "array", "items": { "type": "string" } },
    "cannot_assert": { 
      "type": "array", 
      "items": { "type": "string" },
      "description": "Attributes this layer is structurally forbidden from asserting."
    }
  }
}
```
* **L7a cannot assert:** `downstream_commit_status`, `release_authorization`.
* **L7b cannot assert:** `retry_policy`, `release_authorization`.
* **L7c cannot assert:** `release_authorization`.

---

### Part 7: Honest Boundary Claims & ANSI 86 Interlock
* **Epistemic Clarity:** AEIB replaces unrealistic claims of Ring 0 kernel interception or unverified hardware attestation with an **ANSI 86-inspired software lockout** executed at the controlled adapter boundary.
* **Software Interlock:** When a transport fault triggers an unconfirmed state, the adapter engages a latch that physically rejects any subsequent dispatch using the same CAID until an explicit reset event is presented.

---

### Part 8: Unified L7 Flow
The end-to-end execution flow is strictly sequential and non-subsumable:
```text
[ Model Intent ] 
       │
       ▼
[ L1–L6: Reasoning, Prompting & Policy Authorization ]
       │
       ▼
[ L7a: Transport Observation (HTTP/TCP Wire Dispatch) ]
       │
       ▼
[ L7b: Authoritative Probe (State Endpoint / DB Query) ]
       │
       ▼
[ L7c: Disposition & Retry Policy Derivation (YAML Contract) ]
       │
       ▼
[ L8: Evidence Receipt Canonicalization & COSE Signing (JCS) ]
       │
       ▼
[ L9: Release Authorization & Human Escalation ]
```

---

### Part 9: The 6-Point Conformance Oracle
A software harness is conformant with AEIB v0.3.0 if and only if it satisfies all six assertions under an injected `HTTP 504` post-dispatch fault:
1. **Transport Fact Preservation:** Layer 7a records `aeib.transport.observation = "http_504_after_dispatch"`.
2. **No Layer Override:** Upstream model reasoning fields (`aeib.model_hypothesis`) cannot alter the L7a transport observation.
3. **Explicit Probe Scope:** Layer 7b records `authority_scope` and `consistency_model`.
4. **Fail-Closed Retry Derivation:** Layer 7c outputs `retry_safe = false` if `consistency_model = eventual_read` or no idempotency contract is verified.
5. **Release Authorization Separation:** `aeib.release_authorization` remains `"not_provided"`.
6. **Attribution Isolation:** All output attributes are strictly contained within their registered layer authority classes.

---

### Part 10: Final Positioning & Standards Crosswalk
AEIB does not claim novelty for transactional outboxes, execution finality, or authorization tokens. Its value proposition is defined as:
* A **versioned, portable mapping contract** from transport observations to execution dispositions.
* A **detection-authority registry** enforcing cross-layer non-subsumability.
* Standards Crosswalk:
  * **IETF CAID (`draft-schrock-canonical-action-identifier`):** Supplies canonical action identity.
  * **IETF AADP (`draft-saha-aadp`):** Supplies pre-dispatch decision context.
  * **IETF SCITT (`draft-noa-scitt-ai-agent-receipt`):** Supplies receipt container specification.
  * **OpenTelemetry GenAI:** Supplies telemetry embedding.

---

### Part 11: The Single Sentence
> *Electrical relays own physical phenomena; AEIB publishes the open registry and versioned mapping contract that consume wire facts and derive post-dispatch dispositions without assuming release authority.*
