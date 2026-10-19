# AEIB Limitations and Boundary Conditions

```text
Specification Version : 1.0.0-rc.3
Status                : Release Candidate Specification
Execution Model       : Local Zero-Mock Test Suite Evaluation
Formal Assurance      : Evaluated Locally Under Stated Model (No Independent Reproduction / No Third-Party Certification Claimed)
Regulatory Role       : Operational Evidence Generator (Not a Turnkey QMS or Statutory Exemption)
```

---

## 1. Status and Verification

AEIB v1.0.0-rc.3 is a release candidate and a requirement-driven specification. 
Local test suites report passing results under zero-mock enforcement. 
**No independent reproduction, third-party certification, or formal verification (e.g., TLA+/Coq) is claimed.** 
Passing local suites demonstrate internal logic consistency, not production readiness or comprehensive security.

---

## 2. Execution Boundary Scope

AEIB governs actions that are explicitly routed through its configured out-of-process boundary. 
It does not intercept, govern, or log actions that bypass the boundary via unmonitored syscalls, direct network sockets, or un-instrumented agent runtimes. 
If the agent or host environment bypasses the AEIB gateway, AEIB provides zero protection or evidence.

---

## 3. External Effects and Transactional Finality

AEIB provides **local atomic reservation and durable uncertainty** for external effects. 
It **does not** provide distributed atomic commit (Two-Phase Commit) across third-party payment rails, banking systems, or external APIs. 
If an external system commits a mutation but the network drops the acknowledgment, the external effect is irreversible. AEIB preserves `EFFECT_INDETERMINATE` to prevent blind retries, but it cannot force an external system to roll back. Exactly-once semantics are only achievable if the target system supports bounded, authoritative idempotency.

---

## 4. Credential and Key Isolation

AEIB aims to prevent agent-readable downstream credentials via credential starvation and host-side injection. 
It **does not** eliminate host compromise, vault compromise, memory-scraping malware, key misuse by authorized operators, or insider threats. 
"Zero-key agent runtimes" applies strictly to the isolated agent process, not the broader host environment.

---

## 5. Egress and Network Controls

Proxy and gateway controls cover configured transports (e.g., HTTP/HTTPS via explicit proxy). 
They **do not** automatically cover or prevent DNS rebinding, IPv6 leakage, QUIC tunneling, HTTP redirects, domain fronting, or raw syscall-level bypasses unless explicitly implemented, tested, and enforced at the OS/kernel layer (e.g., via eBPF/LSM or strict network namespaces).

---

## 6. Evidence and Legal Liability

Signed receipts (JCS/COSE) and append-only ledgers support cryptographic integrity, attribution, and investigation under stated key-custody assumptions. 
They **do not** create, transfer, or eliminate legal liability. Liability depends on contract law, agency, employment, negligence, jurisdiction, and specific facts. An AEIB receipt proves a policy authorized a dispatch; it does not prove the policy was legally sound or that the operator is shielded from regulatory action.

---

## 7. Regulatory Compliance

AEIB may generate structured, machine-verifiable evidence useful to an operator’s EU AI Act (EN 18286), DORA, or ISO/IEC 27090 compliance program. 
It **does not** constitute a Quality Management System (QMS), replace legal analysis, satisfy conformity assessment bodies, or automatically fulfill statutory reporting obligations. Compliance is an organizational control, not a software feature.

* **EN 18286:2026**: Supports Article 17 QMS requirements for providers of high-risk AI systems (presumption of conformity under Article 40 once cited in OJEU). AEIB contributes technical records to an operator's technical documentation; it does not certify the system.
* **ISO/IEC 27090**: Provides lifecycle cybersecurity guidance rather than mandatory certifiable management system controls (ISO/IEC 42001).
* **EU DORA**: Governs financial entity ICT risk and incident management. AEIB provides machine-verifiable audit trails; the financial entity retains sole responsibility for materiality determination and statutory reporting.

---

## 8. Benchmarks and Performance

Internal benchmark results (e.g., speedup multipliers, token savings, duplicate reduction) apply **strictly and only** to the stated workload, fault model, random seeds, and environment configuration. 
They are not comparable to other systems without a common, standardized benchmark and independent reproduction. 
"Zero-latency" or "sub-millisecond" claims are not made; fast-path classifiers introduce probabilistic latency and must fail closed to the full gate upon any uncertainty.

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
