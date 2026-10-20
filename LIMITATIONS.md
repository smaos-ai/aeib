# AEIB Limitations and Boundary Conditions

```text
Specification Version : 1.0.0-rc.5-preprod
Status                : Pre-Production Release Candidate Specification
Execution Model       : Local Zero-Mock Test Suite Evaluation & Air-Gapped Hardware Vault
Formal Assurance      : Evaluated Locally Under Stated Model (No Independent Reproduction / No Third-Party Certification Claimed)
Regulatory Role       : Operational Evidence Generator (Not a Turnkey QMS or Statutory Exemption)
```

---

## 1. Release Status and Assurance Scope

AEIB v1.0.0-rc.5-preprod is a requirement-driven specification and pre-production release candidate.
- Local zero-mock verification suites report passing results in the development environment.
- Passing local suites verify assertion logic against local state machines and cryptographic primitives. They **do not** constitute independent third-party reproduction, formal proof about external systems, or regulatory certification.
- **No independent reproduction, third-party certification, or formal verification (e.g., TLA+/Kani/Coq) is claimed.**
- **Release Sequencing**:
  - `v1.0.0-rc.4-preprod`: clean-room reproduction.
  - `v1.0.0-rc.5`: temporal conformance checker, agent chaos injector, real-target ambiguous refund, direct I/O WAL (`DirectIoWal`), external NVMe cold vault reproducer.
  - `v1.0.0-rc.6`: EBV alignment specification, real hybrid PQC envelope (ML-DSA-65 FIPS 204), execution-integrity telemetry (AEIT).
- **Forward Workstreams Statement**:
  > AEIB proposes three forward workstreams: EBV alignment with the cited Internet-Draft vocabulary, a hybrid Ed25519/ML-DSA-65 evidence-envelope design, and execution-integrity telemetry for operator risk monitoring. These are specification and implementation targets, not completed standards, verified post-quantum protections, or insurance underwriting decisions.
- Performance and architectural targets for a native Rust/eBPF/TEE data plane (`crates/aeib-data-plane`) are scaffolded and staged; direct I/O WAL (`DirectIoWal`) provides sector-aligned storage with Darwin `F_FULLFSYNC` / Linux `O_DIRECT`, while kernel enforcement requires active BPF_LSM policies deployed on target Linux hosts.

---

## 2. Execution Boundary Scope

AEIB governs only those actions that traverse its configured Station 1 and Station 2 boundaries.
- In userspace deployments, AEIB does not intercept actions that bypass the configured gateway (e.g., direct raw socket syscalls, unproxied UDP/QUIC traffic, or out-of-band shell execution) unless paired with host/kernel-level network and file-system enforcement (e.g., `BPF_LSM` / Cilium Tetragon policies in `compliance/tetragon_aeib_enforcer.yaml`, network namespaces) that is deployed and adversarially tested in the target environment.
- The native data-plane crate (`crates/aeib-data-plane` / `aeib-data-plane`) provides compiled Rust implementations of Station 1 constant-time 5-tuple admissibility checks, static ring-buffer group-commit WAL (with Darwin `F_FULLFSYNC` physical NVMe write-through barrier), ephemeral TEE key zeroization on drop, and RFC 9162 / RFC 9942 SCITT Merkle inclusion trees.
- If the agent or host environment bypasses the AEIB gateway and no kernel LSM policy is active, AEIB provides no protection and no evidence for that action.

---

## 3. Local Atomic Reservation vs. External Third-Party Finality

A local database transaction (SQLite ACID or a local WAL group commit) cannot make an external network side effect atomic.
- AEIB provides **local atomic budget reservation (escrow)** and **durable uncertainty (`EFFECT_INDETERMINATE`)** before and during external dispatch.
- AEIB **does not** provide distributed two-phase commit (2PC) or automatic rollback across third-party banks, payment processors, or external APIs. Consensus among AEIB nodes (if deployed) coordinates AEIB's own state only; it cannot force an external system to commit or roll back.
- Consistent with the impossibility result reported in LIMBO (arXiv:2609.29095), no verification-only policy can deliver exactly-once execution under unbounded late commits without a known in-flight-time bound. When a downstream target times out or returns an ambiguous response, AEIB halts blind retries and preserves the uncertain state until bounded authoritative reconciliation (`get_transaction_status` or idempotency-key replay) resolves the outcome, or escalates to a human supervisor.
- Exactly-once outcomes are only achievable where the target supports bounded, authoritative idempotency or status lookup.

---

## 4. Credential Isolation, Host Trust Assumptions & DDR5 Interposer (TEE.Fail) Limits

AEIB enforces `agent_holds_downstream_credentials: false` by keeping downstream API keys and signing instruments in a host-side gateway outside the agent's context window and process memory.
- Userspace credential isolation **does not** mitigate a compromised host OS kernel, rootkit, compromised secret vault, memory-scraping malware, key-custody mismanagement, misuse by authorized operators, or a malicious host administrator.
- Hardware memory encryption and attestation require deployment inside a verified Trusted Execution Environment (e.g., AWS Nitro Enclaves, Intel TDX, AMD SEV-SNP) with an explicit enclave key-provisioning ceremony. TEEs carry their own published attack history and trust assumptions (vendor root of trust, firmware, microcode updates); they reduce but do not eliminate host trust.
- **DDR5 Physical Interposer & TEE.Fail Limits:** Hardware memory encryption (Intel TDX, AMD SEV-SNP) protects against software hypervisor inspection, but physical attacks using DDR5 memory bus interposers (such as TEE.Fail or bus-level impedance taps) exploit unencrypted or unauthenticated bus lines on commodity motherboards. TEE attestation proves firmware measurement and key isolation against software adversaries; it does not mitigate physical hardware interposers with direct bus access.
- "Zero-key agent runtimes" applies strictly to the isolated agent process, not the broader host environment.

---

## 5. Linux io_uring Kernel Attack Surface Caveats

While high-throughput ring-buffer group commit can utilize Linux `io_uring` (with `O_DIRECT`), the kernel `io_uring` subsystem has historically presented an elevated local privilege escalation attack surface.
- Hardened multi-tenant production environments (such as Google ChromeOS/production and default Docker seccomp profiles) explicitly block or restrict `io_uring` syscalls (`io_uring_setup`, `io_uring_enter`).
- In environments where `io_uring` is restricted or unvetted, AEIB falls back to POSIX `pwritev` with physical write-through barriers (`fcntl(F_FULLFSYNC)` on Darwin, `fdatasync` on Linux).

---

## 6. Egress, MicroVM Isolation, and Local MCP Boundaries

### 6.1 SPACE-Inspired MicroVM Isolation Topology
AEIB v1.0.0-rc.4 adopts a SPACE-inspired deployment topology for runtime isolation:
1. **Agent Runtime (Untrusted Guest):** Runs inside a dedicated microVM (e.g. Firecracker guest) with no external network egress and zero bearer credentials.
2. **Host-Side AEIB Boundary:** Evaluates exact action binding (`CAID`), policy ceilings, identity/lineage, and durable uncertainty latches (`EFFECT_INDETERMINATE`).
3. **Host Egress Proxy / Gateway:** Controls destination allowlists, TLS termination, audit logging, and external credential injection.

```text
┌────────────────────────────────────────────┐
│ Firecracker guest / agent runtime          │
│  - untrusted agent                         │
│  - no downstream credentials               │
│  - no direct external egress               │
└───────────────┬────────────────────────────┘
                │ VSOCK / controlled channel
                ↓
┌────────────────────────────────────────────┐
│ Host-side AEIB boundary                    │
│  - identity and process lineage            │
│  - exact action / CAID validation          │
│  - policy, budget, delegation, halt        │
│  - durable escrow / uncertainty latch      │
└───────────────┬────────────────────────────┘
                │
                ↓
┌────────────────────────────────────────────┐
│ Host egress proxy / gateway                │
│  - credential injection                    │
│  - destination allowlist                   │
│  - TLS termination                         │
│  - rate limits and audit logging           │
└───────────────┬────────────────────────────┘
                │
                ↓
┌────────────────────────────────────────────┐
│ External target / payment rail             │
└────────────────────────────────────────────┘
```

> [!NOTE]
> MicroVM isolation reduces the blast radius of guest escapes but does not eliminate host, hypervisor, or target vulnerabilities. Escape resistance must be evaluated per platform.

### 6.2 Local MCP Trust Boundary
A localhost MCP server is not automatically trusted merely because it binds to `127.0.0.1`.
- TCP localhost listeners are denied by default in hardened configurations.
- Unix Domain Sockets (`0o600`) are the preferred local transport.
- OS kernel peer credentials (`SO_PEERCRED` on Linux, `LOCAL_PEERCRED` / `LOCAL_PEEREPID` on Darwin) verify peer UID/GID/PID at connection time, but do not by themselves prevent binary substitution or PID reuse.
- AEIB couples peer credential checks with executable SHA-256 binary pinning, creation-timestamp PID reuse protection, and Ed25519 capability token gating.
- Invoking untrusted external tools (`TIER_2_UNTRUSTED_EXTERNAL`) degrades the session consequence ceiling until an authorized supervisor step-up warrant is supplied.

### 6.3 Egress Policy Limits
Gateway allowlists and `TLS SNI == HTTP Host` checks apply only to traffic routed through the gateway.
- They **do not** automatically defeat DNS rebinding, IPv6 routing bypasses, shared-CDN IP laundering, domain fronting, HTTP redirects, QUIC tunneling, or kernel-level bypasses unless every transport layer is locked and adversarially tested in the target deployment.

---

## 7. Cryptographic Receipts and Legal Liability

Operation-bound signed receipts record what action (`CAID`) was proposed, which policy epoch and harness digest were active, which key signed the warrant, and what transport outcome was observed.
- Receipts support technical attribution, auditability, and forensic investigation under stated key-custody assumptions.
- Receipts **do not** create, transfer, or extinguish legal liability, which remains governed by applicable contract, agency, tort, employment, and statutory law. A receipt shows a policy authorized a dispatch; it does not show the policy was legally sound.

---

## 8. Regulatory Evidence vs. Legal Certification (EU AI Act / EN 18286, DORA, ISO/IEC 27090)

AEIB generates structured technical operational evidence to support an operator's quality-management or security program. Compliance is an organizational control, not a software feature:
- **EN 18286:2026:** Contributes technical lifecycle and logging artifacts toward an operator's EU AI Act Article 17 Quality Management System. It **does not** itself constitute a complete QMS, a conformity assessment, or a legal presumption of conformity.
- **ISO/IEC 27090:** Aligns with AI lifecycle cybersecurity guidance; it does not "fulfill" or certify against the standard.
- **DORA (Regulation (EU) 2022/2554):** Provides tamper-evident audit logs for ICT operations. It cannot classify incident materiality, file regulatory reports, or discharge a financial entity's supervisory obligations.

---

## 9. Fast-Path Classification and Benchmarks

- Any probabilistic or lightweight classifier may only route strictly `read_only`, non-networked, non-credentialed, non-mutating requests above a calibrated confidence threshold, and must fail closed to `full_gate` on any uncertainty. The deterministic bitmask gate in `src/constant_time_group_commit_latch.py` is the preferred mechanism.
- Reported internal benchmark metrics (speedups, token savings, duplicate reduction, latch latency) apply solely to the configured test harness, fault schedule, random seeds, and hardware, and may not be generalized without independent clean-room reproduction.
- "Zero-latency" claims are not made. Latency figures marked `[MEASURED-LOCAL]` describe one developer machine; `[TARGET]` figures are unmeasured.

```yaml
fast_path:
  eligible_only_if:
    - read_only
    - no_external_network
    - no_credentials
    - no_state_mutation
    - classifier_confidence_above_threshold
  on_uncertainty:
    route: full_gate
  audit:
    classifier_version: required
    decision: required
    false_negative_monitoring: required
```

---

## 10. Isolation Terminology

AEIB uses OS-specific user-space and kernel-assisted boundaries (e.g., file immutability, LSMs, seccomp, containers). 
Terms like "Ring 0" or "Ring 3" are used conceptually to denote immutable policy vs. mutable optimization zones. They **do not** imply x86 hardware privilege rings or hypervisor-enforced isolation unless explicitly deployed in such an environment.

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

---

## 11. The Defensible Requirement Schema

```yaml
agent_execution_integrity_requirements:
  exact_action_binding:
    canonical_action_digest: required
    canonicalization: versioned
    binding_scope:
      - operation_id
      - action_class
      - target
      - amount
      - currency
      - recipient
      - policy_epoch
      - harness_digest

  authority_separation:
    agent_holds_downstream_credentials: false
    credential_injection: host_side_gateway_only
    credential_lifetime: bounded
    key_custody: operator_defined

  temporal_authorization:
    valid_at_dispatch_time: required
    clock_source: documented
    clock_drift_tolerance: deployment_defined
    stale_authorization_action: deny

  harness_context_binding:
    harness_digest: required
    mutable_context: declared
    protected_policy: declared
    tamper_response: deny_and_halt

  durable_uncertainty:
    ambiguous_effect_must_not_retry_blindly: true
    uncertainty_state: durable
    uncertainty_resolution: bounded

  bounded_reconciliation:
    authoritative_evidence_source: required
    evidence_freshness: required
    max_attempts: required
    unresolved_state: preserved_and_escalated

  evidence:
    operation_bound: required
    canonical_serialization: required
    signature_or_equivalent_integrity: required
    offline_verification: required
    negative_vectors: required

  external_halt:
    durable: required
    checked_before_dispatch: required
    clear_requires_authorized_supervisor: required

  least_privilege:
    default_deny: required
    scope_ceilings: required

  assurance:
    local_suite_pass: reported
    independent_reproduction: required_for_external_claim
    real_target_integration: required_for_production_claim
```

---

## 12. Epistemic Calibration & Corrected Claims

| Prior Colloquial Phrasing | Corrected Engineering Statement |
| :--- | :--- |
| "Complete, mathematically grounded, industry-validated architecture" | A layered pre-production architecture informed by current isolation, attestation, and MCP-security practices. |
| "Secure against kernel escapes" | Designed to reduce blast radius through VM isolation and host-side egress policy; escape resistance must be tested per platform. |
| "Protected against Chain-of-Thought unfaithfulness" | Does not treat CoT as authorization evidence; authorization depends strictly on structured, signed, and durable inputs. |
| "Compliant with EU AI Act EN 18286 and DORA" | May support an operator's EU AI Act QMS and DORA logging program; compliance remains operator- and context-specific. |
| "Optimized for sub-millisecond execution" | Performance targets require measured p50/p99/p999 latency under load and fault conditions. |
| "Credential Starvation Principle" | An internal design principle ensuring the agent process holds zero external bearer credentials. |
| "SPACE-style Firecracker microVM" | SPACE-inspired Firecracker microVM isolation topology. |

---

## 13. W3C BBS+ Cryptosuite Standards-Tracking Prototype Status

The selective disclosure module (`src/bbs_plus_redactable.py`) implements vector commitments based on BLS12-381:
- The **W3C Data Integrity BBS Cryptosuites v1.0** specification is currently a **Candidate Recommendation**, dependent on finalization of the underlying pairing-friendly curves and BBS signature primitives in the IETF CFRG (`draft-irtf-cfrg-bbs-signatures`).
- In AEIB, BBS+ selective redaction is categorized as a **standards-tracking interoperability prototype**. It demonstrates mathematical resolution of the tension between GDPR Article 17 (Right to Erasure) and DORA / EU AI Act Article 12 (Immutable Audit Logging), but does not constitute an immutable, final cryptographic standard.

---

## 14. Kernel eBPF LSM & Hardware TPM Scaffolding Boundaries

The eBPF LSM controller crate (`crates/aeib-ebpf-lsm`) and TPM attestation module (`src/tpm_pcr_attestation.py`):
- **Development & Local Test Environments:** On Darwin/macOS or unprivileged hosts, these components operate as **clean-room software simulation scaffolds**. They evaluate policy state machines, map capacity, and event serialization, but do not provide live Ring 0 syscall interception or hardware PCR extension.
- **Production Kernel Requirements:** Real kernel enforcement requires deploying onto an evaluated Linux kernel (e.g. Linux 6.1 LTS, 6.6 LTS, or 6.12 LTS) compiled with `CONFIG_BPF_LSM=y`, valid BTF (`/sys/kernel/btf/vmlinux`), and execution within the host root namespace with `CAP_SYS_ADMIN` or `CAP_BPF`.
- **Hardware Root of Trust:** Platform attestation quotes require physical TPM 2.0 chips, virtual TPMs (vTPM), or cloud confidential computing enclaves (AMD SEV-SNP, Intel TDX, AWS Nitro Enclaves). Software simulation does not establish a hardware-rooted cryptographic chain.

---

## 15. Standards & Claim Re-Calibration Matrix (v1.0.0-rc.5)

| Component / Standard | Previous Claim | Corrected v1.0.0-rc.5 Engineering Classification |
| :--- | :--- | :--- |
| **W3C Data Integrity BBS+ (bbs-2023)** | "Production-final selective disclosure cryptosuite" | **Standards-Tracking / Interoperability Prototype:** W3C Data Integrity BBS Cryptosuites v1.0 is a W3C Candidate Recommendation (CR-vc-di-bbs-20) dependent on CFRG BBS draft finalization. Production receipts default to Ed25519 (RFC 8032) and ECDSA P-256 (FIPS 186-5). |
| **TPM 2.0 / Enclave Attestation** | "Hardware-rooted PCR attestation proven" | **Software-Modeled in Local CI; Hardware-Dependent in Production:** Local tests exercise a deterministic software PCR model. Platform-rooted assurance requires physical TPM 2.0 (`tpm2_quote`), AWS Nitro Enclaves (`nsm`), or Apple Secure Enclave hardware receipts. |
| **eBPF LSM Enforcement** | "Kernel-enforced zero-bypass boundary" | **Host-Kernel Dependent Control:** Requires Linux kernel with `CONFIG_BPF_LSM=y` and verified `bpftool` attachment receipts across the target LTS kernel matrix. |
| **Security & Financial Posture** | "Prevents all unauthorized actions" | **Fail-closed controls intended to reduce specified execution risks** under the declared threat model, with documented residual risks. |



