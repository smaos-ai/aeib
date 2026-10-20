# AEIB Threat Model and Abuse Cases Analysis
**Regulatory Cross-Reference:** DORA (Regulation (EU) 2022/2554) Article 9 (Protection and Prevention), Article 17; ISO/IEC 27090; NIST SP 800-53 Rev. 5 (RA-3, SC-7).
**System Boundary:** Autonomous Agent Execution Boundary (AEIB v1.0.0-rc.5 pre-production baseline).
**Status:** Evaluated and tested under declared deterministic simulation models.

---

## 1. Executive Summary & Epistemic Posture

Under the stated threat model, autonomous agents operating in financial workflows (such as payment dispatch, refunds, and voucher generation) cannot be treated as trusted principals. All instructions, tool invocations, and state mutations emitted by LLM-driven agents are evaluated as potentially untrusted inputs subject to prompt injection, model drift, or compromised lineage.

This threat model establishes the formal trust boundaries, identifies core assets, models adversary capabilities, and documents verified countermeasures across eight primary abuse cases.

---

## 2. Protected Assets & Trust Boundaries

### 2.1 Core Assets
1. **Tenant Budget Ledgers & Escrow Limits**: Minor-unit balance conservation protecting against unauthorized financial outflow.
2. **Content-Addressed Action Identifiers (CAIDs)**: RFC 8785 JCS canonical cryptographic hashes binding intents to idempotent executions.
3. **Cryptographic Signing Keys**: Host and supervisor Ed25519 private keys used for receipt generation and capability token issuance.
4. **Append-Only Write-Ahead Logs (WAL)**: Synchronously flushed mutation ledgers supporting bitemporal crash recovery.
5. **Transparency Receipts & Audit Ledgers**: Offline-verifiable cryptographic proof bundles for supervisory review.

### 2.2 Trust Boundaries

```
[ Untrusted LLM Guest Runtime ]
            |
            | (Tool Proposal / Wire Frame)
            v  <-- Trust Boundary 1: Host Wire Protocol (Unix Domain Socket / Localhost TCP)
[ AEIB Station 1 Gatekeeper ]
    |-- Taint Lattice Monotonicity Governor
    |-- Dual-Window Quota & Budget Interlock
    |-- Pre-Dispatch Intent Latch (WAL with Direct-I/O fsync)
            |
            | (Authorized Dispatch / CAID Token)
            v  <-- Trust Boundary 2: Kernel Syscall & Network Boundary (eBPF-LSM)
[ Linux Kernel (Tetragon BPF-LSM) / Hardware Substrate ]
            |
            | (Egress to Pinned IP/Port)
            v  <-- Trust Boundary 3: Downstream Banking / Settlement Core
[ Core Banking / Payment System Twin ]
```

---

## 3. Adversary Profiles & Capabilities

| Threat Actor | Access Level | Stated Capability | Modeled Attack Vectors |
|---|---|---|---|
| **A-1: Indirect Prompt Injector** | Untrusted external web/document data | Manipulates tool responses ingested by agent | Token smuggling, homoglyph substitution, hidden instructions |
| **A-2: Malicious / Rogued Agent Code** | Guest process execution | Emits arbitrary API payloads and tool calls | Budget escalation, payee alteration, un-scoped tool execution |
| **A-3: Untrusted Peer Agent** | Peer connection on local network | Seeks authority escalation | Confused deputy attacks, taint de-escalation, capability reuse |
| **A-4: Network Disruptor** | Intermediate transport | Injects latency, drops packets, duplicates frames | Blind retry flooding, post-commit drop (504 timeout), split-brain |
| **A-5: Host Insider / Operator** | Local host non-root account | Attempts to tamper with historical audit trails | File truncation, log modification, receipt forgery |

---

## 4. Formal Abuse Cases & Mitigation Verification

### AC-01: Double-Mutation via Blind Timeout Retry
- **Attack Vector**: Agent initiates financial mutation (e.g. `POST /v1/refunds`). Network disruption drops the downstream HTTP 200 acknowledgment. The agent emits a retry with a new transient identifier, causing a duplicate bank transfer.
- **Observed Defense**: `PreDispatchIntentInterlock` writes intent and locks CAID before dispatch. On drop or 504, entry transitions to `EFFECT_INDETERMINATE`. Replay with identical CAID returns the latched state; mutation with new CAID is blocked if parent reservation is pending.
- **Verification Evidence**: Deterministic simulation tested across 500 fault episodes: 0 duplicate mutations observed.

### AC-02: In-Flight Payee IBAN Alteration
- **Attack Vector**: Compromised intermediary modifies the recipient IBAN from an authorized supplier to an attacker-controlled account after intent generation.
- **Observed Defense**: The CAID is computed strictly over RFC 8785 canonical JSON bytes including payee IBAN. Mutating the IBAN alters the CAID, causing immediate Ed25519 signature rejection and gateway halt.
- **Verification Evidence**: Evaluated in `test_audit_disproving_verifier.py` (CAND-002 rejected).

### AC-03: Budget Inflation via Negative Spend Parameters
- **Attack Vector**: Agent submits negative transfer amounts (`amount = -5000.00`) to artificially inflate available budget ceilings.
- **Observed Defense**: Station 1 schema normalization enforces integer minor units with strict lower bound check (`amount_minor > 0`). In zk-AEIB circuit, bit-decomposition range proofs enforce non-negative spending.
- **Verification Evidence**: Tested in `test_zk_budget_proof_engine.py` (fails closed with `HALT_ZK_NEGATIVE_SPEND_DETECTED`).

### AC-04: Confused Deputy via Un-Scoped Tool Delegation
- **Attack Vector**: Client agent authorized only for read-only catalog queries submits execution commands to sensitive admin tools (`admin_settle_funds`).
- **Observed Defense**: Unix Domain Socket (UDS) boundary enforces Ed25519 capability tokens with strict `allowed_tools` scope sets. Requests targeting unauthorized tools fail closed.
- **Verification Evidence**: Tested in `test_secure_mcp_uds_boundary.py` (`HALT_TOOL_SCOPE_NOT_AUTHORIZED`).

### AC-05: Context Taint Downgrade without Supervisor Step-Up
- **Attack Vector**: Subagent ingesting untrusted web data attempts to de-escalate taint tier from `TIER_2_UNTRUSTED_EXTERNAL` to `TIER_0_SYSTEM_PINNED` to bypass execution gates.
- **Observed Defense**: Monotonic taint lattice enforcer prohibits downward transitions unless accompanied by a cryptographically signed supervisor step-up token (`RFC 9470`).
- **Verification Evidence**: Tested in `test_governed_cross_model_handoff.py` (`HALT_TAINT_DOWNGRADE_FORBIDDEN`).

### AC-06: Nonce & CAID Replay under Network Partition
- **Attack Vector**: Adversary captures valid dispatch packet and replays it across cluster nodes during an asymmetric network partition.
- **Observed Defense**: Quorum consensus (>= 2 of 3 nodes) required before state transition confirmation. Isolated minority node fails closed with `HALT_CONSENSUS_QUORUM_UNAVAILABLE`.
- **Verification Evidence**: Tested across 100 seeded partition schedules in `test_dst_multi_region_partition.py` (0 duplicate reservations).

### AC-07: High-Speed Burst Starvation (Parallel Inference Exhaustion)
- **Attack Vector**: Parallel inference models (e.g. Stanford NCM generating 31x tool calls) fire concurrent writes simultaneously, attempting thread pool starvation or lock inversion.
- **Observed Defense**: Group-commit WAL latch coalesces concurrent requests into ring-buffered batch flushes with bounded flush windows, achieving >150x fsync coalescing.
- **Verification Evidence**: Evaluated up to 2,500 concurrent threads on physical NVMe SSD (0 lost updates).

### AC-08: Path Traversal against Audit Evidence Storage
- **Attack Vector**: Agent requests download of `../../etc/shadow` or attempts writing outside the designated evidence repository.
- **Observed Defense**: Sandbox containment verifies resolved path prefix against locked root directory; eBPF-LSM profile (`bpf_lsm_profile_compiler.py`) hooks `security_file_open` to block unauthorized directory traversal.
- **Verification Evidence**: Evaluated in `test_bpf_lsm_profile_compiler.py` and `test_audit_disproving_verifier.py`.
