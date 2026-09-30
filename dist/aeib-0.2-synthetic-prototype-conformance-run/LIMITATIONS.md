# Limitations & Operational Boundaries

**Classification:** Synthetic Engineering Prototype Specification  
**Status:** Engineering Review Deliverable (AEIB v0.2.0)  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  

---

## 1. Explicit Disclaimers & Regulatory Boundary

> **MANDATORY NOTICE FOR REVIEWING ENGINEERS:**
> 1. **Not a Production Security Control**: This is a synthetic prototype for engineering review, not a production security control.
> 2. **Standards Baseline**: This prototype is **not RFC 8785 compliant** and **not COSE_Sign1 compliant**. It is an Ed25519-signed JSON receipt prototype designed to illustrate the 5-stage signature lifecycle and out-of-band evidence binding.
> 3. **Synthetic Data**: This package **uses synthetic data for engineering review only**. It does not interact with live banking accounts, real SWIFT networks, or production ledgers.
> 4. **No Certification Claim**: This prototype does not certify regulatory compliance with EU DORA, the EU AI Act, or ISO/IEC 42006.

---

## 2. The Architectural Stance: Post-Dispatch Reconciliation Layer

SMAOS does not replace NVIDIA OpenShell, Archipelo, or established policy enforcement points. 

Instead, SMAOS serves as the **missing post-dispatch reconciliation layer**:
- **Complements Front-End Proxies**: Sits alongside transport proxies (like `mcp-shield`) and receipt envelopes (like IETF SCITT drafts).
- **Extends Ambiguity Physics**: Injects a deterministic **7-state ambiguity taxonomy** (`OUTCOME_VERIFIED`, `ACK_UNVERIFIED`, `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, `RECONCILIATION_FAILED`, `PROBE_EXCEPTION`, `REFUSED`).
- **Enforces Retry Invariants**: Physically blocks unhedged agent retry loops when a network drop (`HTTP 504`, `TCP RST`) occurs, requiring authoritative probe resolution before consequence release.

---

## 3. Physical Limitations & Assumptions

1. **Transport Severing Is Not Execution Failure**:
   - An HTTP 504 Gateway Timeout or TCP socket drop proves only that the connection terminated before a response was received. It cannot prove whether downstream writes succeeded or aborted.
   - Authoritative state must be resolved via out-of-band target probing (`ServerIdempotencyAdapter`).

2. **Idempotency Symmetry**:
   - Client-side UUIDv5 idempotency key minting prevents the agent from sending differing payloads under the same logical handle. However, true exactly-once execution requires that the downstream service honors the `X-Idempotency-Key` header.

3. **Signed Namespace Protection**:
   - In accordance with AEIB specifications, the `org.smaos.aeib` namespace (containing the disposition verdict, retry policy, and evidence hashes) resides **strictly inside the signed payload view**, preventing header-stripping attacks.
