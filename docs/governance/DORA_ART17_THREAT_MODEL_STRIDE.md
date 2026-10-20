# DORA Article 17 Threat Model: Agent Execution Integrity Boundary (AEIB)
## STRIDE & PASTA Threat Analysis for Governed Autonomous Agent Operations

> **Regulatory Applicability:** DORA (Regulation (EU) 2022/2554) Articles 9, 10, 11, 17; Commission Delegated Regulation (EU) 2025/301; EU AI Act (Regulation (EU) 2024/1689) Articles 12, 14, 15  
> **Classification:** Pre-Production Architecture Threat Model (`v1.0.0-rc.4-preprod`)  
> **Epistemic Notice:** This threat model outlines threats, controls, and residual risks evaluated under the stated model of our local execution boundary prototype. It does not replace an operator's entity-wide ICT risk management framework.

---

### 1. Scope, System Assets & Trust Boundaries

AEIB governs consequential actions initiated by semi-autonomous and multi-agent AI systems.

#### 1.1 Primary Assets

| Asset ID | Asset Description | Confidentiality | Integrity | Availability |
| :--- | :--- | :--- | :--- | :--- |
| **A-1** | **Root Sponsor Private Keys** (Ed25519 / HSM-backed) | High | Critical | High |
| **A-2** | **Station 1 Authority Ledger (WAL)** | Medium | Critical | Critical |
| **A-3** | **Pre-Signed Delegation Warrants & Step-Up Tokens** | Medium | Critical | High |
| **A-4** | **Wire Mutation Payloads (CAID-bound parameters)** | Medium | Critical | High |
| **A-5** | **Downstream Payment & Actuator Credentials** (DPoP, SigV4) | Critical | Critical | High |
| **A-6** | **Tool Descriptors & Skill Manifests** | Low | Critical | High |
| **A-7** | **SCITT Transparency Merkle Tree & Inclusion Receipts** | Low | Critical | High |

#### 1.2 Trust Boundaries

```
[ UNTRUSTED ZONE: Guest MicroVM ]
  │  • Model Reasoning (Stochastic / Untrusted)
  │  • Zero bearer credentials; ambient external networking blocked
  │
═══════════════════════════════════════════════════════════════════════════════════
  ▼ TRUST BOUNDARY 1: Local UDS (0o600) + Kernel SO_PEERCRED + Executable Pinning
═══════════════════════════════════════════════════════════════════════════════════
  │
[ ENFORCEMENT ZONE: Host Node Gateway (Station 1) ]
  │  • Exact Action Binding (CAID = SHA256(JCS(Action)))
  │  • Monotonic Taint Enforcer (Bell-LaPadula)
  │  • Monotonic Budget Ledger & Delegation Attenuation
  │  • Tool Descriptor Integrity & AST Scanner
  │
═══════════════════════════════════════════════════════════════════════════════════
  ▼ TRUST BOUNDARY 2: Inter-Process Authorized Intent Dispatch
═══════════════════════════════════════════════════════════════════════════════════
  │
[ EGRESS CONTROL ZONE: Host Proxy Sidecar (Station 2) ]
  │  • Holds External API Tokens / Keys (Credential Starvation)
  │  • Translates CAID to Signed Wire Request (RFC 9449 DPoP / AWS SigV4)
  │  • Derives Deterministic Idempotency Key
  │  • Latches Ambiguous States (EFFECT_INDETERMINATE on 504 / drop)
  │
═══════════════════════════════════════════════════════════════════════════════════
  ▼ TRUST BOUNDARY 3: External TLS Transport to Downstream Rails & APIs
═══════════════════════════════════════════════════════════════════════════════════
  │
[ AUDIT & RECONCILIATION ZONE: Station 3 & Target System ]
     • Authoritative Status Reconciliation Probe
     • Append-Only SCITT Merkle Ledger (RFC 9942/9943)
     • OpenTelemetry GenAI Semantic Spans
```

---

### 2. Threat Actor Characterization

| Threat Actor | Motivation | Capabilities | Entry Vector |
| :--- | :--- | :--- | :--- |
| **TA-1: External Prompt Injector** | Data theft, unauthorized fund transfer, sabotage. | Indirect prompt injection via ingested web/document context; jailbreak phrasing. | Ingested text, user prompts, untrusted search results (`TIER_2`). |
| **TA-2: Rogue / Poisoned MCP Tool** | Privilege abuse, credential extraction, tool rug-pull. | Mutates tool description or input schema post-approval; returns covert instructions. | Remote or dynamic MCP tool server registration. |
| **TA-3: Byzantine / Colluding Subagent** | Budget smurfing, Sybil quota bypass, taint erasure. | Rapid parallel requests, hopping between accounts, dropping security metadata. | Multi-agent coordination bus, task handoff messages. |
| **TA-4: Adversarial Network Environment** | Cause double-execution or inconsistent state. | Drops TCP ACKs, injects `HTTP 504 Gateway Timeout`, resets connections mid-flight. | Egress transit network, cloud API gateway boundary. |
| **TA-5: Compromised Local Co-Tenant** | Lateral movement, intercept local IPC. | Local non-root process attempting to connect to host gateway socket. | Local Unix Domain Socket, local filesystem access. |

---

### 3. STRIDE Threat Analysis & Technical Controls

#### 3.1 Spoofing (Identity & Origin)
* **Threat S-1: Agent impersonates Root Sponsor or parent subagent.**  
  * *Countermeasure:* Every subagent action proposal requires an unbroken cryptographic chain of Ed25519-signed warrants (`RootSponsorPolicy` $\to$ `SubAgentDelegationCert`). Warrants must be signed over canonical RFC 8785 JCS bytes. Replayed or forged signatures fail closed (`ERR_SIGNATURE_OR_PAYEE_MISMATCH`).
* **Threat S-2: Unauthorized local process connects to Station 1 gateway.**  
  * *Countermeasure:* The Unix Domain Socket is created with file mode `0o600`. On connection, the gateway executes kernel peer credential validation (`SO_PEERCRED` on Linux, `LOCAL_PEERCRED` on macOS), verifying that `peer_uid == gateway_uid` and that the connecting binary matches pinned SHA-256 digests (`test_secure_mcp_uds_boundary.py`).

#### 3.2 Tampering (Data & Integrity)
* **Threat T-1: Wire action payload parameters mutated after validation (e.g. changing payee or amount).**  
  * *Countermeasure:* Exact Action Binding (CAID). The action payload is hashed using SHA-256 over its canonical JCS representation. The host proxy sidecar injects credentials only for the exact CAID pre-signed by Station 1. Any alteration of `recipient_iban`, `amount_minor`, or target URI breaks the digest and is rejected (`AT69`).
* **Threat T-2: Tool description or schema mutated post-approval (MCP Tool Rug-Pull).**  
  * *Countermeasure:* Pre-dispatch tool provenance verification (`AT63`). Tool descriptors (`name`, `description`, `input_schema`, source code) are pinned and signed by an authorized publisher. If the live file hash differs from the pinned descriptor, execution halts immediately (`HALT_TOOL_RUG_PULL_HASH_MISMATCH`).
* **Threat T-3: Local ledger rollback or truncation attack.**  
  * *Countermeasure:* Two-file wipe protection and embedded SCITT Merkle roots (`AT70b`, `AT72`). Every ledger line contains the hash of the previous line and an Ed25519 gate signature. On startup, Station 1 re-verifies the entire chain. Divergence engages `HALT_CHAIN_TIP_MISMATCH_ROLLBACK_DETECTED`.

#### 3.3 Repudiation (Audit Trail)
* **Threat R-1: Operator or agent denies having initiated an authorized disbursement or infrastructure mutation.**  
  * *Countermeasure:* RFC 9052 `COSE_Sign1` receipts and RFC 9162 Merkle tree inclusion proofs (`src/cbom_and_scitt_otel_exporter.py`). Every state transition (`DISPATCHED`, `EFFECT_INDETERMINATE`, `CONFIRMED`, `REFUTED`) is anchored to an append-only transparency log. Receipts can be validated offline via the standalone WebAssembly verifier (`smaos_verify.wasm`) without access to live production databases.

#### 3.4 Information Disclosure (Confidentiality)
* **Threat I-1: Malicious agent exfiltrates bearer API keys or customer PII.**  
  * *Countermeasure:* Credential Starvation. The agent process in the guest microVM holds zero bearer keys or payment tokens. Egress traffic is restricted to the local UDS socket. Outbound external calls are made exclusively by the host proxy sidecar. PII in audit receipts is redactable via W3C BBS+ selective disclosure vector commitments (`src/bbs_plus_redactable.py`).

#### 3.5 Denial of Service (Availability & Stability)
* **Threat D-1: High-concurrency burst smurfing to exhaust sprint budget (50 concurrent threads).**  
  * *Countermeasure:* Dual-layer serialization using in-process locks and OS-level `fcntl.flock` (`AT56`). All spend updates are evaluated against a shared rolling-window deque. Evaluated in `test_sybil_rotator_and_smurfing.py`: exactly 2 requests admitted (€1,998.00); 48 requests halted with `HALT_SPRINT_LIMIT_EXCEEDED`.
* **Threat D-2: Network outage causes ambiguous timeouts, leading to duplicate spend retries.**  
  * *Countermeasure:* Bounded Uncertainty Latching (`AT60`, `AT70a`). Ambiguous outcomes (`HTTP 504`, dropped connection) latch into `EFFECT_INDETERMINATE`. Autonomous retries are blocked until an authoritative out-of-band status probe resolves finality.

#### 3.6 Elevation of Privilege (Access Control)
* **Threat E-1: Untrusted context or lower-tier model downgrades taint to bypass human oversight.**  
  * *Countermeasure:* Bell-LaPadula Monotonic Taint Invariant (`AT57b`, `src/governed_cross_model_handoff.py`). Once tainted by `TIER_2_UNTRUSTED_EXTERNAL` data, the task consequence ceiling degrades. Downstream models cannot lower the taint tier without an Ed25519-signed supervisor step-up warrant.
* **Threat E-2: Agent executes dynamic runtime code to bypass policy (`eval`, `exec`, `ctypes`).**  
  * *Countermeasure:* Pre-commit AST visitor scanner (`compliance/dynamic_code_policy_gate.py`) and Linux eBPF LSM `file_mprotect` ($W \oplus X$ memory protection).

---

### 4. Residual Risks & Explicit Non-Goals

1. **Hypervisor & Physical Hardware Compromise (Out of Scope):**  
   If an adversary achieves physical host tampering, arbitrary Ring 0 memory corruption, or CPU hardware fault injection (e.g., Rowhammer / microarchitectural side-channels), AEIB execution boundary controls can be bypassed. Protection relies on host-level hardening, microVM isolation, and measured boot (TPM 2.0).
2. **Within-Boundary Model Hallucination:**  
   If an agent constructs a valid, pre-authorized transaction that conforms strictly to the sponsor's policy, budget limit, and pinned payee allowlist, but was logically suboptimal from a business perspective, AEIB will permit it. Cryptographic execution boundaries constrain *authority and wire parameters*, not LLM business judgment.
3. **Target System Finality Discrepancies:**  
   AEIB tracks eventual consistency and compensates via asynchronous saga workflows. If an external bank or API vendor experiences an unannounced ledger rollback or silent split-brain without exposing status probe endpoints, manual operational intervention is required.
