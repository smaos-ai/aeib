# Objective Comparative Evaluation: Agent Execution Governance & Transport Fault Handling

**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus Project)  
**Date:** October 2026  
**Artifact Revision:** `AEIB v0.2.4`  

---

## 1. Evaluation Methodology & Ground Rules

To ensure scientific honesty and avoid arbitrary scoreboard grading, this evaluation rejects speculative point scoring (such as "X/6") in favor of evidence-based criteria derived strictly from primary published sources:

* **Evaluation Standard**: Each capability must be grounded in published academic papers, active standards specifications (IETF / W3C), or open-source repositories with runnable test suites.
* **Absence of Proof is Not Proof of Absence**: "Not found in reviewed public materials" indicates that a feature or test case was not identified during the specific literature review of publicly accessible repositories and papers; it must never be construed as an assertion that the capability does not exist in unreviewed, proprietary, or newer releases.
* **Standardized Classification Taxonomy**:
  1. `Demonstrated in AEIB artifact`: Verified by local code, test logs, or release artifacts in this repository.
  2. `Demonstrated by cited external artifact`: Confirmed via primary external research paper, codebase, or official specification.
  3. `Not found in reviewed public materials`: Not identified in reviewed repositories, documentation, or publications.
  4. `Not applicable`: The system is designed for an orthogonal layer or distinct operational problem.
  5. `Unknown`: Insufficient public data to assess.

---

## 2. Source-Backed Evaluation Matrix

| Governance Capability | VERITAS OS | Microsoft AGT | LF TRACE | NVIDIA OpenShell / MUXI | AEIB v0.2.4 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Domain / Focus Layer** | Kernel-level AI agent operating system | Multi-language enterprise agent governance | Supply-chain attestation & identity architecture | Pre-dispatch sandboxing & app serving | Post-dispatch transport reconciliation |
| **Unresolved Outcome State** | `Demonstrated by cited external artifact` (`EFFECT_UNKNOWN`) | `Not found in reviewed public materials` | `Not applicable` | `Not applicable` | `Demonstrated in AEIB artifact` (`DISPATCHED_UNCONFIRMED`) |
| **Out-of-Band State Probing** | `Demonstrated by cited external artifact` (PostgreSQL authorization check) | `Not found in reviewed public materials` | `Not applicable` | `Not applicable` | `Demonstrated in AEIB artifact` (SQLite & PostgreSQL probe adapters) |
| **Machine-Readable Mapping Contract** | `Not found in reviewed public materials` | `Not found in reviewed public materials` | `Not applicable` | `Not applicable` | `Demonstrated in AEIB artifact` (`transport-to-disposition-mapping.yaml`) |
| **Offline-Verifiable Receipt Format** | `Demonstrated by cited external artifact` | `Not found in reviewed public materials` | `Demonstrated by cited external artifact` (SCITT / RATS) | `Not applicable` | `Demonstrated in AEIB artifact` (JCS + Ed25519 verifier) |
| **OWASP Agentic Top 10 Coverage** | `Unknown` | `Demonstrated by cited external artifact` (>13k test suite) | `Not applicable` | `Unknown` | `Not applicable` (Scoped to post-dispatch faults) |
| **Hardware Attestation Integration** | `Unknown` | `Not found in reviewed public materials` | `Demonstrated by cited external artifact` (EAT / RATS / CVM) | `Not applicable` | `Not found in v0.2.4 release` (Deferred to future work) |
| **Tested Failure Mode** | Lost-response authorization consumption | Prompt injection, policy violations, unsafe tools | Supply-chain tampering, unauthorized binaries | Syscall abuse, filesystem/egress leakage | Post-commit HTTP 504 / TCP drops |

*Note on table entries*: Classifications of `Not found in reviewed public materials` reflect the scope of reviewed materials; absence of proof in public documentation is not proof of absence in the underlying platforms.

---

## 3. Primary Sources & Detailed System Profiles

### 3.1 VERITAS OS
* **Primary Citations**:
  - *VERITAS: Verifiable Execution and Resilient Identity Tracking for Autonomous Systems*, Academic Preprint & Zenodo Research Archive, 2026.
  - VERITAS OS Implementation Artifact: Kernel-level agent execution manager evaluating post-transport reconciliation and authorization consumption under network disconnection.
* **Direct Related Work**: VERITAS OS is an essential peer in this research area. Published materials demonstrate that it explicitly defines unresolved outcome states (`EFFECT_UNKNOWN`), mandates authenticated reconciliation prior to retry, and evaluates real PostgreSQL authorization consumption under lost transport responses.
* **AEIB Boundary & Delta**: AEIB does not claim to be the first or only system to address transport faults. Rather, AEIB provides a complementary, highly focused contribution:
  1. A standalone, versioned transport-to-disposition mapping contract decoupled from a monolithic OS runtime.
  2. An explicit disposition-to-retry policy vocabulary for client-side sidecar interposition.
  3. A standalone, zero-network-egress offline verifier script designed for air-gapped auditor evaluation.

### 3.2 Microsoft Agent Governance Toolkit (AGT)
* **Primary Citations**:
  - Microsoft Corporation, *Microsoft Agent Governance Toolkit (AGT)*, GitHub Repository: `https://github.com/microsoft/agent-governance-toolkit`, MIT License, 2025–2026.
  - OWASP Foundation, *OWASP Top 10 for Large Language Model Applications & Agentic AI*, 2025–2026.
* **Enterprise Platform Profile**: AGT is an open-source, multi-language platform with extensive automated test coverage (>13,000 tests) addressing the OWASP Agentic Top 10. It focuses on pre-dispatch policy enforcement, multi-modal guardrails, and compliance telemetry.
* **Boundary Distinction**: AGT optimizes for pre-dispatch policy filtering and prompt evaluation. It does not focus on post-commit network drops or out-of-band SQL reconciliation. The two systems address distinct, non-competing layers of the agent lifecycle.

### 3.3 Linux Foundation TRACE
* **Primary Citations**:
  - Linux Foundation Decentralized Trust, *TRACE Project: Trust, Receipt, and Attestation for Confidential Execution*, Linux Foundation, 2025–2026.
  - Birkholz, H., et al., *Remote ATtestation procedureS (RATS) Architecture*, IETF RFC 9334, 2023.
  - Birkholz, H., Delignat-Lavaud, A., Fournet, C., Goyal, Y., and Barnes, R., *An Architecture for Trustworthy and Transparent Digital Supply Chains*, IETF Internet-Draft `draft-ietf-scitt-architecture-08`, 2024.
  - Cloud Native Computing Foundation (CNCF), *SPIFFE: Secure Production Identity Framework for Everyone*, SPIFFE/SPIRE Specification, 2024.
* **Standards Profile**: TRACE is an established, community-backed evidence architecture implementing IETF RATS, EAT, SCITT, and SPIFFE/SPIRE for confidential computing attestation and supply chain transparency.
* **Boundary Distinction**: TRACE establishes identity and provenance for compute enclaves and container images. AEIB operates at the application protocol layer, generating execution receipts that can serve as payloads within broader SCITT/RATS transparency systems.

### 3.4 NVIDIA OpenShell & MUXI
* **Primary Citations**:
  - NVIDIA Corporation, *NeMo Guardrails & Runtime Container Isolation*, GitHub: `https://github.com/NVIDIA/NeMo-Guardrails`, Apache 2.0, 2024–2026.
  - NVIDIA Developer Documentation, *Container Runtime & Secure Sandboxing for LLM Microservices*, 2025.
* **Runtime Layer**: OpenShell enforces kernel-level isolation (syscall filtering, network interface allowlists). MUXI acts as an AI application server managing agent formations and RBAC.
* **Boundary Distinction**: Both platforms govern pre-dispatch execution. AEIB operates downstream when an authorized, sandboxed network dispatch experiences mid-flight network severance.

---

## 4. Current Status of the AEIB v0.2.4 Artifact

The official status of the AEIB release is strictly defined as:

> **v0.2.4: Locally executed and internally reproducible; external reproduction pending; competitive claims under revision; no regulatory endorsement.**

### Verified Local Evidence:
* **PostgreSQL Integration Suite**: 4 passed, 0 skipped (`test_integration_pg_probe.py`), verifying active `statement_timeout = 200ms` cancellation, connection rollback, and connection pool recovery on live PostgreSQL 16.
* **SQLite Fault Campaign**: 0 duplicate mutations observed in 50 trials under post-commit 504 drops (Rule-of-Three 95% upper bound failure rate: ~5.8%).
* **Control Matrix**: C0=100% duplicate rate, C1=0%, C2=100%.
* **Negative Controls**: 20/20 fail-closed (`RECONCILIATION_NOT_FOUND`, 95% upper bound false positive rate: ~15.0%).
* **Offline Verification**: Zero-network-egress offline verification via local Ed25519 and JCS signature verification.
* **Artifact Manifest**: All tracked file digests verified against release manifest.

### Scope of Empirical Latency Profiling:
Empirical latency profiling ($p_{50} = 0.057\text{ ms}$ for SQLite in-process probe; $p_{50} = 0.228\text{ ms}$ for PostgreSQL out-of-band probe) reflects measurements obtained on a local development testbed (Apple Silicon M-series, local loopback, $N=100$ trials). These figures characterize the specific local test harness and are **not** universal, cloud-scale, or distributed network performance claims.

### Explicit Operational Disclaimers:
1. **Regulatory Disclaimer**: No endorsement, approval, sponsorship, or regulatory pathway by the Czech Agency for Standardization (ČAS), the Czech National Bank (ČNB), or any statutory regulatory body is claimed or implied.
2. **Preliminary Local Status**: Results reflect a controlled, deterministic synthetic fault model and do not constitute certified compliance with DORA, GDPR, or the EU AI Act.
