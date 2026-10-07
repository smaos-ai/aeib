# SMAOS / AEIB System Boundaries & Epistemic Calibration (v0.2.4)

To preserve execution integrity and enforce fail-closed containment under the stated operational model, SMAOS establishes governed succession across whole-system execution boundaries. Passing an examination does not manufacture greater authority; evidence proves what it proves and stops there.

---

## 1. Whole-System Boundary Examination Matrix

| Boundary | State Transition | Evaluation Criteria | Enforcement Mechanism | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Boundary 1: Wire & Transport** | Network Transport ➔ Agent SDK | Does internal agent state match physical socket state? | Wire-trap interception (`127.0.0.1`); catches HTTP 504 / TCP RST, halts speculative retries, and stages candidate acts in `DISPATCHED_UNCONFIRMED`. | **Tier 1 (Tested)** |
| **Boundary 2: Agent Handoff** | Agent A ➔ Agent B (Delegation) | Does delegation scope survive inter-agent handoff without privilege escalation? | Validates predecessor `prior_state_hash` & authority ceiling before allowing Agent B execution. | **Tier 1 (Tested)** |
| **Boundary 3: Context & Policy** | Context ➔ Pipeline | Does the agent possess unexpired session mandates & active authority? | Pre-dispatch admissibility check validating mandate TTL & authority freshness before tool execution. | **Tier 1 (Tested)** |
| **Boundary 4: Evidence & Outcome** | Outcome ➔ Audit Witness | Is telemetry cryptographically immutable and offline-verifiable? | Ed25519 signed receipts canonicalized via RFC 8785 JCS + offline verification via `aeib_verify.py`. | **Tier 1 (Tested)** |

---

## 2. Negative State Assertions (Falsifier Engine)

Every verification cycle actively asserts the following negative boolean state constraints:
- `privilege_escalation_detected`: **false** (Successor payloads inherited strictly equal or narrower scopes).
- `authority_created`: **false** (Verification did not expand baseline permissions).
- `external_execution_unauthorized`: **false** (Zero uninspected packets breached local loopback).
- `freeze_authorized`: **false** (No silent freezing of state occurred).
- `duplicate_mutations`: **0** (Authoritative downstream state prober blocks duplicate execution in tested sample).

---

## 3. 📊 3-Tier Research Component Maturity Classification

In strict adherence to IETF 126 nomenclature, all capabilities are classified into three distinct maturity tiers to prevent evidence transfer from the verified core to prototype extensions:

### Tier 1: Implemented & Locally Verified (Staging Grade)
- **AEIB Core Harness**: 500-episode deterministic evaluation under synthetic fault injection (0/500 observed duplicates, Rule-of-Three 95% upper bound $\approx 0.60\%$, p50 latency $\approx 0.86\text{ms}$).
- **Out-of-Band State Probers**: Authoritative SQLite and PostgreSQL state reconciliation with connection pooling and statement timeouts (`SET LOCAL statement_timeout = 3000`).
- **Cryptographic Action Receipts**: RFC 8785 JCS payload canonicalization, Noun/Verb CAID derivation, and offline verifier (`aeib_verify.py`).
- **Local Saga Compensation**: Eventual consistency engine preserving the net-balance invariant ($\sum \Delta_{\text{net}} = 0.00$) locally.
- **Ghost Audit Scanner (`ghost_audit_scanner.py`)**: Local AST, environment, and line-stop inspection crawler.

### Tier 2: Implemented Prototype (Evaluated Locally)
- **Toxiproxy Chaos Harness**: Raw socket TCP RST / half-open drop injection harness evaluated in containerized socket loops.
- **BBS+ Selective Disclosure**: Rust prototype crate gated under Cargo feature flag; pending complete C-ABI dynamic linking.
- **Cross-Benchmark Adapters**: Local adapters around external benchmark suites (`duplicate-side-effect-desk`, `agent-runtime-integrity-bench`, `AgentDisruptBench`, $\tau^2$-bench 083–085).

### Tier 3: Scaffold or Deferred (Phase 3 Research Roadmap)
- **JVM Virtual-Thread Implementation**: Structural Project Loom multi-tenant scaffold; pending physical multi-tenant integration.
- **eBPF LSM Enforcement**: Kernel-level LSM `bprm_check_security` hooks deferred to Phase 3 Linux kernel roadmap.
- **Physical PKCS#11 HSM**: Software PKCS#11 wrapper tested; physical HSM bus pending.
- **TDX / SEV-SNP Hardware Attestation**: Linux ioctl hooks structured; does not validate hardware-backed production enclaves.
- **Cross-Datacenter WAN Consensus**: Cross-datacenter consensus and live WAN network splits deferred.

---

## 4. ⚠️ Epistemic Boundaries & Non-Claims

1. **Local Staging Scope**: Evidence is gathered under a declared local fault injection harness. It characterizes staging behavior and does not replace institutional integration testing.
2. **Statistical Confidence**: Under the **Rule of Three** for zero observed events ($3/N$), 0/500 empirical trials establish a **95% confidence upper bound of ~0.60%** on the failure rate under the stated fault model. It does not establish universal zero-failure rates across untested environments.
3. **Single-Authority Scope**: The prober validates state against a single authoritative database instance (`authority_scope="single_authority:postgresql"`). It does not claim multi-resource distributed transaction atomicity (2PC/XA).
4. **No Statutory Certification**: This software produces structured technical audit trails. It does not constitute formal statutory compliance certification under DORA (Regulation (EU) 2022/2554) or the EU AI Act without independent supervisory assessment.

---

## 5. Reasoning Plane: Ollama Model Environment Split

The Reasoning Plane separates cognitive planning from execution authorization. To maintain SLSA L3 reproducibility, deterministic speed, and production scaling:

| Environment | Model Tag | Target Purpose | Rationale |
| :--- | :--- | :--- | :--- |
| **Local Development & CI** | `qwen2.5:7b` | Rapid evaluation & regression testing | Enables single-command 500-episode benchmarks to complete in minutes while preserving semantic drift characteristics. |
| **Sovereign Node Production** | `qwen2.5:32b` | Enterprise edge & on-premise execution | Primary production target for autonomous tool use and high-fidelity structured output. (*Note: The Qwen 2.5 lineup comprises 7B, 14B, 32B, and 72B parameter architectures; there is no 35B model.*) |
| **Air-Gapped Enterprise Swarms** | `qwen2.5:72b` | Highly regulated, mission-critical nodes | Full-density reasoning plane for complex multi-agent orchestration and compliance verification. |

### Configuration:
- Local / CI:
  ```bash
  ollama pull qwen2.5:7b
  export AEIB_OLLAMA_MODEL="qwen2.5:7b"
  ```
- Sovereign Node Production:
  ```bash
  ollama pull qwen2.5:32b
  export AEIB_OLLAMA_MODEL="qwen2.5:32b"
  ```
