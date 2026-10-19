# AEIB Operational Limitations & Residual Risk Disclosure

```text
Release Baseline   : AEIB v1.0.0-rc.3 / v1.0.0-rc.24 (Commit f7273968)
Status             : Release candidate with passing local test suites
Verification State : Local zero-mock test suites passed. Not independently verified. Not certified.
Defensible Anchor  : AEIB is a prototype governed execution boundary for consequential agent mutations.
                     It does not constitute an AI Act QMS, conformity assessment, certification, or legal compliance.
```

---

## ⚖️ The Defensible Baseline

> **AEIB v1.0.0-rc.3 is a release candidate whose local suites report passing results. It is not independently verified, not certified, not automatically compliant with the EU AI Act or DORA, and not yet a decadal industry standard.**

AEIB proposes a governed execution boundary for autonomous agents:
- Model reasoning is treated as an untrusted proposal.
- Exact actions, authority, policy epoch, harness/context identity, and target contracts are validated before dispatch.
- Ambiguous external transport effects are preserved as `EFFECT_INDETERMINATE` rather than blindly retried.
- Operation-bound evidence is retained for independent auditability.

Its next proof obligations are hosted clean-room reproduction, adversarial and egress-bypass testing, real-target integration, external verifier validation, and legally reviewed regulatory applicability.

---

## 1. Corrected Regulatory Claims

### 1.1 EN 18286:2026 is Real, but Narrow
CEN-CENELEC EN 18286:2026 (*Artificial intelligence — Quality management system for EU AI Act regulatory purposes*) has been cited in the Official Journal of the European Union under Commission Implementing Decision (EU) 2026/2274. It supports Article 17 quality-management-system requirements for providers of high-risk AI systems and can provide a presumption of conformity for the requirements it covers under Article 40.

It does **not** automatically make AEIB compliant, certify AEIB, satisfy every AI Act requirement, or cover deployer obligations, DORA incident reporting, payment-rail rules, or financial-sector supervision.

```text
AEIB may contribute evidence to an operator’s EN 18286-aligned QMS.
It does not itself constitute an AI Act QMS, conformity assessment, certification, or legal compliance.
```

### 1.2 ISO/IEC 27090:2026 is Guidance, Not a QMS
ISO/IEC 27090 addresses AI-specific security threats and compromises across the AI lifecycle. ISO publishes this standard as security guidance and technical controls, not as requirements for an institutional AI management system (which is the domain of ISO/IEC 42001).

```text
AEIB can align with ISO/IEC 27090 guidance.
It does not “fulfill” ISO/IEC 27090.
```

### 1.3 DORA is Not Satisfied by Receipts
Regulation (EU) 2022/2554 (DORA) applies to regulated financial entities and their ICT risk management frameworks, incident reporting mechanisms, digital operational resilience testing, and third-party risk management. 

AEIB produces verifiable technical evidence useful to a financial entity’s incident management process, but it cannot automatically file regulatory reports, classify incidents as major, determine materiality under RTS (EU) 2024/1772, or discharge the regulated entity’s statutory responsibilities.

---

## 2. Corrected External Transparency & SCITT Claims

IETF RFC 9943 (*An Architecture for Trustworthy and Transparent Digital Supply Chains*) and RFC 9942 (*COSE Receipts*) define an external architecture for digital supply chain transparency.

A local append-only ledger (`ledger.jsonl`) is locally verifiable at best. It does not constitute a transparency service. A SCITT-compatible transparency service introduces an external registration and independent Merkle auditing model with its own operational trust assumptions.

```text
AEIB may emit COSE receipts and optionally register statements or receipts
with a SCITT-compatible transparency service.
Local ledger integrity and external transparency anchoring are different assurance properties.
```

---

## 3. Corrected "Zero-Mock Verification" Claims

In AEIB, "zero-mock" denotes that the test suites execute without mocking frameworks (`unittest.mock`, stubbed hashes, hardcoded signatures, or synthetic assertions). 

**What "Zero Mocks" Does NOT Mean:**
- Real payment rails were not used.
- Real production banks were not used.
- Real external production targets were not used.
- Independent third parties have not yet reproduced results.
- Full production failure modes were not covered.
- Security properties were not formally proven across infinite state spaces.

```text
Defensible statement: Local zero-mock test suites passed.
Prohibited statement: Fully verified.
```

---

## 4. Corrected Test-Suite Interpretation

Passing test suites provide evidence about those tests' specific assertions under local execution conditions. A passing test ID is not mathematical proof that every threat in the named category is comprehensively eliminated.

**Standard Reporting Template:**
```text
At commit f7273968, in Python 3.14 / macOS Darwin ARM64,
the following core test suites reported pass:
- tests/test_industrial_protection_matrix.py (18/18 passed)
- tests/test_ansi_50bf_breaker_failure.py (2/2 passed)
- tests/test_saga_compensation.py (5/5 passed)
- tests/test_falsifiability_matrix.py (5/5 passed)
- tests/test_at73_sovereign_signer_allowlist_gate.py (6/6 passed)
- tests/test_scitt_otel_and_pqc_cbom_agility.py (5/5 passed)
Raw logs and evidence manifest: evidence/
```

---

## 5. The Six-Pillar Architecture: Scope vs. What Remains Unproven

| Architecture Pillar | Correct Scope | What Remains Unproven |
|---|---|---|
| **1. Wire & Egress** | Enforces allowlists, SNI/Host consistency, and authenticated dispatch at a controlled loopback gateway. | DNS rebinding, domain fronting, IPv6 bypass, proxies, HTTP redirects, QUIC transport, and bypass via non-proxied raw syscalls. |
| **2. Credential Isolation** | Keeps downstream credentials out of agent-readable memory; injects narrowly scoped credentials at the host gateway. | Key-compromise recovery procedures, credential rotation cascades, vault compromise, and privileged insider threats. |
| **3. Harness Immutability** | Binds harness digests and protects policy artifacts from agent modifications via OS-specific controls. | User-space bypass if container rootfs is writable; requires explicit OS-level containment models. |
| **4. Context Cartography** | Preserves raw-byte digests while exposing compressed views for token efficiency; propagates provenance taint. | Does not prevent semantic poisoning; compressed view may omit safety-relevant contextual nuances. |
| **5. Transactional Finality** | Enforces local ACID escrow accounting, state locking, and conflict resolution. | Cannot create distributed two-phase commit (2PC) across external banking or payment systems. |
| **6. Regulatory Evidence** | Generates canonical RFC 8785 JCS, Ed25519-signed, machine-readable evidence artifacts. | Does not determine legal applicability or satisfy conformity assessment without notified body review. |

---

## 6. Policy Protection & Anti-Tamper Enforcement Model

File-level policy locks on ordinary Linux/UNIX systems operate via user-space or kernel-assisted primitives—not CPU Ring 0. 

### 6.1 Policy Protection Model
```yaml
policy_protection:
  enforcement_layer: OS-specific
  options:
    - read_only_mount
    - immutable_file_attribute
    - LSM_policy
    - seccomp_profile
    - separate_service_identity
  failure_behavior: deny_and_halt
```

### 6.2 Anti-Tamper Mitigation Specifications
To prevent an agent process from tampering with its own execution guardrails:
1. **Remounting Policy Path:** The agent runs in a container or mount namespace where the policy mount is strictly read-only (`MS_RDONLY`), without `CAP_SYS_ADMIN`, preventing remounting.
2. **Editing Copied Policy File:** The execution runtime strictly hashes and verifies the pinned canonical filesystem path, rejecting caller-supplied alternate paths.
3. **Replacing Verifier Binary:** Enforced via read-only container root filesystems or immutable filesystem attributes (`chattr +i`).
4. **Spoofing Policy Loader:** Policy manifests require mutual cryptographic signature verification with the root sponsor key before activation.
5. **Restarting into Permissive Configuration:** Station 1 boot-continuity checks inspect historical hash-chains and halt fail-closed (`HALT_MISSING_CONTINUITY_LEDGER`) if the state is altered.

---

## 7. Transactional Finality vs. External Distributed Systems

Local SQLite / PostgreSQL ACID transactions provide local transactional integrity. They do **not** provide distributed commit across external, heterogeneous banking systems:
$$\text{Agent} \longrightarrow \text{AEIB} \longrightarrow \text{Payment Rail} \longrightarrow \text{Bank Core} \longrightarrow \text{Beneficiary}$$

An external payment can commit after an AEIB timeout, network drop, or crash. Therefore:
- `EFFECT_INDETERMINATE` is a durable state that must survive restarts.
- Reconciliation probes must be strictly bounded (`ProbeBudget: 1`).
- The system provides local escrow and conflict control, not distributed two-phase commit.

```text
AEIB provides local escrow and conflict control.
It does not provide distributed commit across external systems.
```

---

## 8. Performance & Latency Claims

Sub-millisecond latency cannot be asserted universally without measuring in the target production environment.

### 8.1 Fast-Path Classification Controls
Any fast-path optimization introduced to reduce latency for low-risk actions introduces misclassification risk. Required engineering controls:
```yaml
fast_path:
  eligible:
    - read_only
    - no_external_network
    - no_credentials
    - no_state_mutation
    - below_risk_threshold
  fallback:
    any_uncertainty: full_gate
  audit:
    classifier_version: required
    decision: required
    override_rate: monitored
```

---

## 9. Requirements for an Agent Execution Integrity Standard

Rather than claiming that AEIB *is* an industry standard, the requirements that an open standard for agent execution integrity must satisfy are defined as follows:

```yaml
agent_execution_integrity_requirements:
  exact_action_binding:
    canonical_action_digest: required
  authority_separation:
    agent_holds_downstream_credentials: false
  temporal_authorization:
    valid_at_dispatch_time: required
  harness_context_binding:
    harness_digest: required
  durable_uncertainty:
    ambiguous_effect_must_not_retry_blindly: true
  bounded_reconciliation:
    authoritative_evidence_source: required
    max_attempts: required
  evidence:
    operation_bound: required
    canonical_serialization: required
    signature_or_equivalent_integrity: required
    offline_verification: required
  external_halt:
    durable: required
    checked_before_dispatch: required
  least_privilege:
    default_deny: required
  independent_verifiability:
    standalone_verifier: required
    negative_vectors: required
```

---

## 10. Immediate Delivery Plan: Closing the Core Loop

Rather than expanding simultaneously into ancillary protocols, AEIB prioritizes closing the core verification loop:

```text
1. Publish exact commit, environment, commands, and raw suite logs.
2. Publish canonical receipt schema and standalone offline verifier.
3. Publish negative verification test vectors.
4. Run one real local-target ambiguous-refund scenario end-to-end.
5. Run fresh-checkout reproduction in a cleanroom directory.
6. Package and transmit evidence pack to an independent reproducer.
7. Maintain and enforce this LIMITATIONS.md specification.
8. Only subsequent to 1–7: expand optional COSE, SCITT, AP2, x402, and PQC profiles.
```
