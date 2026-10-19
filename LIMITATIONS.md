# AEIB Limitations and Boundary Conditions

```text
Specification Version : 1.0.0-rc.3
Status                : Release Candidate Specification
Execution Model       : Local Zero-Mock Test Suite Evaluation
Formal Assurance      : Evaluated Locally Under Stated Model (No Independent Reproduction / No Third-Party Certification Claimed)
Regulatory Role       : Operational Evidence Generator (Not a Turnkey QMS or Statutory Exemption)
```

---

## 1. Release Status and Assurance Scope

AEIB v1.0.0-rc.3 is a requirement-driven specification and release candidate (repository tags `v1.0.0-rc.29`+ carry this specification).
- Local zero-mock verification suites report passing results in the development environment.
- Passing local suites verify assertion logic against local state machines and cryptographic primitives. They **do not** constitute independent third-party reproduction, formal proof about external systems, or regulatory certification.
- **No independent reproduction, third-party certification, or formal verification (e.g., TLA+/Kani/Coq) is claimed.**
- Performance and architectural targets for a native Rust/eBPF/TEE data plane (planned `v1.0.0-rc.4`) remain designated `[TARGET]` until measured in a published clean-room environment. That data plane does not exist in this release; `ebpf/` and `hardware_attestation/` are structural scaffolding only.

---

## 2. Execution Boundary Scope

AEIB governs only those actions that traverse its configured Station 1 and Station 2 boundaries.
- In userspace deployments (`v1.0.0-rc.3`), AEIB does not intercept actions that bypass the configured gateway (e.g., direct raw socket syscalls, unproxied UDP/QUIC traffic, or out-of-band shell execution) unless paired with host/kernel-level network and file-system enforcement (e.g., `BPF_LSM` / Cilium Tetragon policies in `compliance/tetragon_aeib_enforcer.yaml`, network namespaces) that is deployed and adversarially tested in the target environment.
- The native data-plane crate (`crates/aeib-data-plane`) provides compiled Rust implementations of Station 1 constant-time 5-tuple admissibility checks, static ring-buffer group-commit WAL (with Darwin `F_FULLFSYNC` physical NVMe write-through barrier), ephemeral TEE key zeroization on drop, and RFC 9162 / RFC 9942 SCITT Merkle inclusion trees.
- If the agent or host environment bypasses the AEIB gateway and no kernel LSM policy is active, AEIB provides no protection and no evidence for that action.

---

## 3. External Effects and Transactional Finality

A local database transaction (SQLite ACID or a local WAL group commit) cannot make an external network side effect atomic.
- AEIB provides **local atomic budget reservation (escrow)** and **durable uncertainty (`EFFECT_INDETERMINATE`)** before and during external dispatch.
- AEIB **does not** provide distributed two-phase commit (2PC) or automatic rollback across third-party banks, payment processors, or external APIs. Consensus among AEIB nodes (if deployed) coordinates AEIB's own state only; it cannot force an external system to commit or roll back.
- Consistent with the impossibility result reported in LIMBO (arXiv:2609.29095), no verification-only policy can deliver exactly-once execution under unbounded late commits without a known in-flight-time bound. When a downstream target times out or returns an ambiguous response, AEIB halts blind retries and preserves the uncertain state until bounded authoritative reconciliation (`get_transaction_status` or idempotency-key replay) resolves the outcome, or escalates to a human supervisor.
- Exactly-once outcomes are only achievable where the target supports bounded, authoritative idempotency or status lookup.

---

## 4. Credential Isolation and Host Trust Assumptions

AEIB enforces `agent_holds_downstream_credentials: false` by keeping downstream API keys and signing instruments in a host-side gateway outside the agent's context window and process memory.
- Userspace credential isolation **does not** mitigate a compromised host OS kernel, rootkit, compromised secret vault, memory-scraping malware, key-custody mismanagement, misuse by authorized operators, or a malicious host administrator.
- Hardware memory encryption and attestation require deployment inside a verified Trusted Execution Environment (e.g., AWS Nitro Enclaves, Intel TDX, AMD SEV-SNP) with an explicit enclave key-provisioning ceremony. TEEs carry their own published attack history and trust assumptions (vendor root of trust, firmware, side channels); they reduce but do not remove host trust.
- "Zero-key agent runtimes" applies strictly to the isolated agent process, not the broader host environment.

---

## 5. Egress and Sandbox Controls

Gateway allowlists and `TLS SNI == HTTP Host` checks apply only to traffic routed through the gateway.
- They **do not** automatically defeat DNS rebinding, IPv6 routing bypasses, shared-CDN IP laundering, domain fronting, HTTP redirects, QUIC tunneling, or kernel-level bypasses unless every transport layer is locked and adversarially tested in the target deployment.

---

## 6. Cryptographic Receipts and Legal Liability

Operation-bound signed receipts record what action (`CAID`) was proposed, which policy epoch and harness digest were active, which key signed the warrant, and what transport outcome was observed.
- Receipts support technical attribution, auditability, and forensic investigation under stated key-custody assumptions.
- Receipts **do not** create, transfer, or extinguish legal liability, which remains governed by applicable contract, agency, tort, employment, and statutory law. A receipt shows a policy authorized a dispatch; it does not show the policy was legally sound.

---

## 7. Regulatory Alignment (EU AI Act / EN 18286, DORA, ISO/IEC 27090)

AEIB can generate structured operational evidence to support an operator's quality-management or security program. Compliance is an organizational control, not a software feature.
- **EN 18286:2026:** Contributes technical lifecycle and logging artifacts toward an operator's EU AI Act Article 17 Quality Management System. It **does not** itself constitute a complete QMS, a conformity assessment, or a legal presumption of conformity.
- **ISO/IEC 27090:** Aligns with AI lifecycle cybersecurity guidance; it does not "fulfill" or certify against the standard.
- **DORA (Regulation (EU) 2022/2554):** Provides tamper-evident audit logs for ICT operations. It cannot classify incident materiality, file regulatory reports, or discharge a financial entity's supervisory obligations.

---

## 8. Fast-Path Classification and Benchmarks

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

## 9. Isolation Terminology

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

## 10. The Defensible Requirement Schema

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
