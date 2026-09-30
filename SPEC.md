# AEIB v0.2.1 Core Technical Specification (`SPEC.md`)

**Standard:** Agent Execution Integrity Benchmark (AEIB)  
**Status:** Synthetic Prototype Specification (v0.2.1)  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus project)  
**Full Architectural Specification:** [`docs/architecture/AEIB_SPECIFICATION.md`](docs/architecture/AEIB_SPECIFICATION.md)  
**Known Limitations & Boundaries:** [`LIMITATIONS.md`](LIMITATIONS.md)  

---

## ⚡ The Mechanics of Phases 1–3 Synthesized

```text
[ Pre-Dispatch ]              [ Wire Write ]            [ Fault / Lock ]
Key-Sort + SHA-256    ──►   X-Idempotency-Key   ──►   Intercept 504 / ECONNRESET
UUIDv5 Namespace             Injected on Header        retry_permitted = false
                                                       State = DISPATCHED_UNCONFIRMED
```

### 1. Phase 1: Pre-Dispatch Normalization & Idempotency Injection
* **Why it matters**: Standard agent SDKs allow LLMs to re-serialize JSON on retries, altering whitespace, parameter ordering, or key formatting.
* **The Mechanism**: Enforcing canonical key-sorting (JCS subset) and hashing the byte stream produces an immutable `unsigned_payload_hash`. Deriving a deterministic **UUIDv5** from this hash creates an unshakeable idempotency anchor bound to the exact payload *before* socket dispatch.

### 2. Phase 2: Socket-Level Wire-Fault Interception
* **Why it matters**: HTTP client libraries (like `axios`, `requests`, or `httpx`) routinely catch socket drops and wrap them in generic, retryable network exceptions—masking the fault from governance layers.
* **The Mechanism**: Intercepting post-write drops (`HTTP 504`, `ECONNRESET`, stdio pipe EOF) directly at the transport layer forces state transition to **`DISPATCHED_UNCONFIRMED`** before any runtime exception handler can trigger a blind retry.

### 3. Phase 3: Hard Policy Lock (Retry Suppression)
* **Why it matters**: If an LLM sees a raw 504 error string, its ReAct loop interprets it as "task incomplete" and attempts a semantic re-reasoning retry.
* **The Mechanism**: Setting `retry_permitted: false` and returning a fail-closed JSON-RPC `HOLD` response strips the agent of retry authority and freezes execution until out-of-band reconciliation completes.

---

## 🔗 Bridging to Phases 4–6: State Resolution & Cryptographic Proof

Phases 1–3 set the trap; Phases 4–6 resolve state and seal the proof:

* **Phase 4 (Out-of-Band Prober)**: Queries the downstream register (SQL database, payment provider, or OS accessibility tree) using the pre-dispatch **UUIDv5** handle to verify whether the side effect actually committed downstream:
  - *Committed* → `OUTCOME_VERIFIED` (Retry locked; already settled).
  - *Absent* → `RECONCILIATION_NOT_FOUND` (Safe to redispatch).
  - *Conflict/Corrupt* → `RECONCILIATION_FAILED` (Quarantined for audit).
* **Phase 5 (Receipt Emission)**: Assembles the `aeib-0.2` receipt containing the `context_lineage` bundle, `transport_evidence`, and `outcome_probe` data, signing it with Ed25519.
* **Phase 6 (Offline Verification)**: Enables third-party auditors and CISOs to run `python3 verifier/aeib_verify.py` locally to verify the full signature chain and rule mapping with zero vendor trust.

---

## 🧱 The Minimal Sufficient Deliverable

1. **Idempotency Key Derivation Engine** (UUIDv5 derived from canonical JSON payload).
2. **Transport Fault Interceptor** (Trapping 504, connection resets, read timeouts).
3. **Disposition State Machine** (Enforcing `EXECUTE` → `HOLD` → `BLOCK` transitions).
4. **Authoritative Out-of-Band Prober** (Target state verification via UUIDv5).
5. **Ed25519 Receipt Signer** (Hash-chained, tamper-evident JSON records).
6. **Offline Verifier Script** (Self-contained, deterministic audit validation).
