# Executive Briefing: The Agent Execution Integrity Boundary (AEIB)

**Audience:** Systems Architects, Cryptographic Engineers & AI Safety Researchers  
**Author:** SovereignNexus Architecture Group  
**Document Ref:** `AEIB-PEER-BRIEF-v1.1`  
**Epistemic Notice:**  
*Evaluated under the stated model. Permitted terms: observed, tested, evaluated, configured, prototype, scaffold. Banned words: zero. AEIB is an out-of-process wire boundary enforcing deterministic execution invariants on autonomous agent tool mutations.*

---

### 1. The Core Theoretical Problem: The Execution Ambiguity Gap

When an autonomous AI agent interacts with mutable external infrastructure (payment rails, industrial controllers, cloud APIs), existing security layers treat tool calls as synchronous RPCs. However, distributed systems inherently exhibit **transport ambiguity**:

$$\text{Dispatch}(A) \xrightarrow{\quad\text{HTTP 504 / TCP RST}\quad} \text{Outcome}(A) \in \{\text{Executed}, \text{Dropped}, \text{Pending}\}$$

Probabilistic language models and agent frameworks cannot resolve this uncertainty without out-of-band state reconciliation. If an agent naively retries an unconfirmed mutation whose underlying action was already committed by the server, it causes silent duplicate side-effects.

---

### 2. The Architectural Solution: Four Deterministic Wire Invariants

AEIB interposes an independent, out-of-process execution boundary directly at the Layer 7 socket edge, enforcing four mathematical invariants:

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         AEIB 4-STATION EXECUTION BOUNDARY                        │
├───────────────────┬──────────────────────────────────────────────────────────────┤
│ STATION           │ FORMAL MECHANISM & MATHEMATICAL INVARIANT                     │
├───────────────────┼──────────────────────────────────────────────────────────────┤
│ Station 0         │ Zero-Allocation Admission Hook: O(1) in-memory standing eval │
│ (Admission)       │ drops unauthorized callers in < 15 µs before JCS allocation. │
├───────────────────┼──────────────────────────────────────────────────────────────┤
│ Station 1         │ CAID Payload Binding & Tn Standing Check:                     │
│ (Interlock)       │   CAID = SHA-256( JCS( CandidateActionPayload ) )            │
│                   │ Evaluates epoch freshness at exact dispatch instant Tn.      │
│                   │ If stale, drops mutation with strictly 0 wire bytes.         │
├───────────────────┼──────────────────────────────────────────────────────────────┤
│ Station 2         │ Post-Dispatch Fault Latch: Wire drops (HTTP 504, TCP RST)    │
│ (Reconciler)      │ transition state to EFFECT_INDETERMINATE with retry_safe:    │
│                   │ False. Probes downstream target via refund_status_v1.        │
├───────────────────┼──────────────────────────────────────────────────────────────┤
│ Station 3         │ Continuous Ledger & Offline Receipt Verifier:                │
│ (Ledger)          │   chainTip_n = SHA-256( chainTip_{n-1} || eventBytes_n )     │
│                   │ Signs Ed25519 receipts for independent offline verification. │
└───────────────────┴──────────────────────────────────────────────────────────────┘
```

---

### 3. Strict Pre-Dispatch Intent Commitment (\\(\text{EO-1}\\))

Under the **\\(\text{EO-1}\\) (Evidence-Before-Effect)** principle, wire access is conditioned on an immutable pre-dispatch ledger record:

1. **Write-Before-Execute:** Prior to opening any outbound TCP socket, the runtime writes an Ed25519-signed `DISPATCH_INTENT` record to disk. If disk I/O fails, dispatch is aborted fail-closed with **0 connections and 0 bytes transmitted**.
2. **Crash Recovery:** If a process crashes or receives `SIGKILL` mid-syscall, the next boot scans the ledger. Any intent lacking a terminal receipt is automatically latched into `EFFECT_INDETERMINATE`, halting subsequent execution on that \\(\text{CAID}\\) until target status is confirmed.

---

### 4. Calibrated Trust Hierarchy

To avoid overclaiming attribution across organizational boundaries, AEIB formalizes three explicit trust tiers:

* **Level 1 (Agent-Signed):** Proves an internal signer inside the agent runtime signed a payload. Does not prove the runtime was uncompromised.
* **Level 2 (Boundary-Signed):** Proves an out-of-process boundary observed or authorized a dispatch (Restraint Records). Does not establish target-side effect.
* **Level 3 (Target-Attested):** Proves an authenticated downstream target attested to state under a versioned contract (`refund_status_v1`).

---

### 5. Cross-Language Native Verification & Code Purity

* **Core Runtime:** Pure Java 21 virtual thread engine (`aeib-native-runtime`) and Python reference implementation.
* **Cryptographic Purity:** Strict RFC 8785 JSON Canonicalization Scheme (JCS) and real Ed25519 asymmetric signatures. Zero mock cryptography, zero bypass gates.
* **Offline Verification:** Verification CLI (`tools/verify_adversarial_evidence.py` and `tools/verify_pre_execution_evidence.py`) validates receipts and hash-chains air-gapped without network egress.
