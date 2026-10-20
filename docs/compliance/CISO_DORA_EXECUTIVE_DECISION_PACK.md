# CISO & Risk Committee Decision Pack: Governed Agent Execution Boundary
## Technical & Regulatory Evaluation under DORA (Articles 9–11, 17) and EU AI Act (Articles 12, 14, 15)

> **Document Status:** Pre-Production Architecture & Evidence Dossier (`v1.0.0-rc.4-preprod`)  
> **Target Audience:** Chief Information Security Officers (CISOs), Enterprise Risk Committees, DORA Lead Overseers, Internal Audit  
> **Epistemic Notice:** All technical capabilities and performance metrics in this pack describe properties **observed**, **tested**, **evaluated**, and **configured** **under the stated model** of our local verification harnesses and prototype scaffolds. AEIB is designed as a modular execution boundary; it does not replace banking licenses, core ledger consensus, or organization-specific operational risk programs.

---

### 1. Executive Summary & Problem Formulation

Large Language Model (LLM) agents deployed for automated financial transactions, customer refunds, credit allocation, or IT infrastructure mutations present a fundamental governance gap: **stochastic neural reasoning cannot provide deterministic execution bounds.** 

When an agent suffers from context injection, tool poisoning, network timeouts, or multi-agent race conditions, standard application-level controls fail because the agent itself holds the bearer credentials or API keys.

**AEIB (Agent Execution Integrity Boundary)** solves this architectural mismatch by decoupling untrusted agent reasoning from consequential action dispatch through a host-side, fail-closed enforcement layer.

```
+───────────────────────────────────────────────────────────────────────────────────+
| GUEST AGENT RUNTIME (Untrusted Reasoning)                                         |
| • Prompt reasoning & planning               • Zero external network egress        |
| • Proposes wire action payload              • ZERO bearer keys / API tokens       |
+─────────────────────────────────────────┬─────────────────────────────────────────+
                                          │ Local UDS (0o600) + Signed Intent
                                          ▼
+───────────────────────────────────────────────────────────────────────────────────+
| AEIB HOST GATEWAY (Station 1: Authority & Invariant Evaluation)                   |
| 1. Exact Action Binding (CAID = SHA256(JCS(Action)))                              |
| 2. Monotonic Taint Check (Bell-LaPadula: External context cannot downgrade)       |
| 3. Budget & Attenuation Ledger (Monotonic decrement; cap per operation)          |
| 4. Tool Provenance Scan (Ed25519 publisher signature & pre-dispatch SHA256)       |
+─────────────────────────────────────────┬─────────────────────────────────────────+
                                          │ Authorized & Latched
                                          ▼
+───────────────────────────────────────────────────────────────────────────────────+
| HOST PROXY SIDECAR (Station 2: Wire Dispatch & Ambiguity Latching)                |
| • Injects DPoP / SigV4 / mTLS tokens        • Derives RFC Idempotency-Key         |
| • Captures HTTP 504 / TCP drops             • Latches EFFECT_INDETERMINATE        |
+─────────────────────────────────────────┬─────────────────────────────────────────+
                                          │ Out-of-Band State Probe
                                          ▼
+───────────────────────────────────────────────────────────────────────────────────+
| AUDIT & RECONCILIATION LEDGER (Station 3: RFC 9943 SCITT Transparency)            |
| • Bitemporal Merkle Tree inclusion proof    • OpenTelemetry GenAI span export     |
| • Offline independent verification via standalone WASM (Node.js / browser)        |
+───────────────────────────────────────────────────────────────────────────────────+
```

---

### 2. Regulatory Control Mapping (DORA & EU AI Act)

| Regulatory Article | Mandatory Obligation | AEIB Technical Countermeasure | Test & Evidence ID |
| :--- | :--- | :--- | :--- |
| **DORA Art. 9(2)**<br>*(Protection & Prevention)* | Policies limiting physical and logical access to ICT assets to authorized personnel and tools. | **Credential Starvation & UDS 0o600**: Guest microVM holds 0 bearer keys. Local socket checks `SO_PEERCRED` / `LOCAL_PEERCRED` and pinned executable binary SHA-256. | `test_secure_mcp_uds_boundary.py`<br>`test_dpop_token_exchange_gate.py` |
| **DORA Art. 9(4)(c)**<br>*(Data Authenticity)* | Cryptographic protection of data in transit and at rest against tampering or unauthorized modification. | **Exact Action ID (CAID)**: RFC 8785 JCS canonicalization + SHA-256 hash binding of exact parameters (including `recipient_iban` and `amount`). | `AT69` (P0 Verification)<br>`test_complete_remediation_at69_to_at74.py` |
| **DORA Art. 10(1)–(2)**<br>*(Anomalous Detection)* | Prompt detection of anomalous activities, ICT performance issues, and multiple failure events. | **Taint & Tool Provenance Gates (`AT57b`, `AT63`)**: Banning of dynamic code primitives (`eval`, `exec`, `ctypes`) and detection of tool descriptor rug-pulls. | `compliance/dynamic_code_policy_gate.py`<br>`test_tool_provenance_and_otel_interop.py` |
| **DORA Art. 11 & 17**<br>*(Incident Response)* | ICT business continuity, containment of indeterminate states, and rapid containment. | **Bounded Uncertainty Latching**: Ambiguous timeouts latch `EFFECT_INDETERMINATE`. Blind autonomous retries are suppressed fail-closed. | `AT70a`, `AT70b`<br>`test_dst_seeded_invariants.py` |
| **EU AI Act Art. 12**<br>*(Automatic Logging)* | Continuous, automatic recording of events over the high-risk AI system's lifecycle. | **SCITT Merkle Transparency Log (RFC 9942/9943)**: Append-only hash chain anchoring all dispatches, timeouts, and refutations with Ed25519 quotes. | `src/cbom_and_scitt_otel_exporter.py`<br>`evidence/cbom.json` |
| **EU AI Act Art. 14**<br>*(Human Oversight)* | Ability for natural persons to oversee, intervene, or halt autonomous execution safely. | **Supervisor Step-Up Warrants & Halt Latches**: Taint violations or spend overages trigger `HALT_*` states requiring signed supervisor intervention. | `test_sybil_rotator_and_smurfing.py`<br>`test_agent_chaos_injector.py` |
| **EU AI Act Art. 15**<br>*(Cybersecurity & Robustness)* | Resilience against prompt injection, data poisoning, and unauthorized system influence. | **Monotonic Taint Invariant**: Context from `TIER_2_UNTRUSTED_EXTERNAL` cannot be downgraded by intermediate models without step-up authorization. | `test_governed_cross_model_handoff.py`<br>`test_at64_rail_interop_and_mcp_tool_taint.py` |

---

### 3. The 5 Operational Invariants

1. **Exact Action Identifier (CAID) Invariant:**  
   The execution payload on the wire must match the byte-for-byte RFC 8785 JCS SHA-256 digest pre-signed by the delegating principal. Modifying a single character of the payload, payee IBAN, or amount fails closed (`ERR_SIGNATURE_OR_PAYEE_MISMATCH`).
2. **Credential Starvation Invariant:**  
   The agent execution process is configured without bearer credentials, private keys, or API tokens. Credentials reside strictly on the host-side proxy, injected only after Station 1 validates the intent, budget ceiling, and taint level.
3. **Bounded Uncertainty & Idempotency Invariant:**  
   Any network timeout (`HTTP 504`), socket reset, or dropped acknowledgement enters the `EFFECT_INDETERMINATE` state. The system derives a deterministic idempotency key (`draft-ietf-httpapi-idempotency-key-header`) and locks the operation until an authoritative out-of-band status probe resolves it to `CONFIRMED` or `REFUTED`.
4. **Bitemporal Merkle Audit Invariant:**  
   Every state transition is anchored into an append-only RFC 9162 Merkle tree. SCITT inclusion proofs are embedded into standard OpenTelemetry GenAI spans (`execute_tool`), enabling external auditors to verify compliance without accessing raw database tables.
5. **Fail-Closed Hard Halt Invariant:**  
   Any detected integrity anomaly (e.g., local state rollback, unpinned tool hash divergence, monotonic clock skew $>5\text{s}$, or memory taint downgrade) immediately engages a `HALT_*` circuit breaker that requires a cryptographically signed recovery warrant to release.

---

### 4. Empirical Verification & Benchmark Summary

The local release candidate (`v1.0.0-rc.4-preprod`) was evaluated under comprehensive stress and fault-injection suites:

* **Protocol-Aware Deterministic Simulation (DST) — 10,000 Schedules:**  
  Evaluated under PRNG seed `20261020` across 6,520 dispatches with 3,018 simulated transport timeouts:  
  **Result:** 3,018/3,018 timeouts were latched into `EFFECT_INDETERMINATE`; **0 duplicate mutations observed** (0.00% error rate). Artifact: `output/dst-report-20261020.json`.
* **AgentChaos 16-Vector Fault Injection:**  
  Evaluated against corrupted ledger bytes, detached chains, clock jumps, concurrency spikes, and unauthorized step-up injections:  
  **Result:** 16/16 vectors handled fail-closed with 0 unhandled runtime crashes and 0 unauthorized spend mutations.
* **Apple Native Swift 6 Concurrency & Byte-Parity:**  
  Cross-language byte-level parity between Python, Rust, and Swift 6 Sendable actors:  
  **Result:** 11/11 conformance tests passed in 0.067s (`tests/test_swift_temporal_parity.py`).
* **Standalone WebAssembly Verifier (`smaos_verify.wasm`):**  
  Zero-dependency 199 KB WebAssembly binary (SHA-256: `6ecc360af19008632c950d94910b70220e3c2cc36a5cc29fe0c33ba64d2bb041`):  
  **Result:** Evaluated in Node.js runtime (`test_smaos_verify_wasm.js`), successfully rejecting tampered Ed25519 signatures (`rc = -4`), Merkle boundary violations (`rc = -2`), and invalid timestamps (`rc = -5`).

---

### 5. Deployment Topology & Integration Checklist

```
+───────────────────────────────────────────────────────────────────────────────+
| Recommended Enterprise Architecture Topology                                  |
+───────────────────────────────────────────────────────────────────────────────+
| 1. MicroVM Boundary:    Firecracker or container sandbox with seccomp/LSM     |
| 2. IPC Transport:        Unix Domain Socket (mode 0o600, uid/gid matched)     |
| 3. Host Sidecar:         Station 1 & 2 gateway colocated on host node         |
| 4. Outbound Egress:      Zero direct internet access from guest; egress only  |
|                          via host proxy with DPoP/SigV4 token binding         |
| 5. Telemetry / SIEM:     OpenTelemetry GenAI spans with RFC 9943 SCITT headers|
| 6. Audit Tooling:        Offline verification via smaos_verify.wasm or CLI    |
+───────────────────────────────────────────────────────────────────────────────+
```

#### Enterprise Procurement Evaluation Matrix

| Procurement Question | CISO Concern | AEIB Architectural Reality |
| :--- | :--- | :--- |
| *"Can an attacker who achieves prompt injection exfiltrate customer data or funds?"* | Lateral movement and unauthorized payment initiation. | **Blocked at boundary**: The guest holds no credentials. The action must be pre-signed by the root sponsor with an exact CAID and conform to pinned allowlists. |
| *"What happens during an AWS/Cloud network outage when an API call times out?"* | Double-charge or duplicate balance decrement. | **Latched**: The operation enters `EFFECT_INDETERMINATE`. Autonomous retries are blocked; settlement status is verified out-of-band before budget update. |
| *"Can the agent modify its own code or install unauthorized packages?"* | Privilege escalation and runtime tampering. | **AST Gate & Binary Hash Pinning**: Pre-commit AST scanner blocks `eval`/`exec`/`importlib`/`ctypes`. Pre-dispatch checks verify pinned executable SHA-256. |
| *"Does this comply with DORA requirements for external audit independence?"* | Vendor lock-in and unverifiable black-box audit logs. | **Offline Portable Verifier**: Standalone 199 KB WASM module validates all receipts and Merkle proofs client-side without network access. |

---

### 6. Sign-Off & Verification Commands

To independently evaluate and reproduce all claims on local hardware without network egress:

```bash
# 1. Zone & AST Purity Gate (Zero mocks, 0 dynamic execution)
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py

# 2. Core Industrial Protection & Chaos Tests
pytest tests/test_industrial_protection_matrix.py tests/test_agent_chaos_injector.py -v

# 3. Native WebAssembly Offline Acceptance Suite
node tests/test_smaos_verify_wasm.js

# 4. Deterministic 500-Episode Conformance Benchmark
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
```
