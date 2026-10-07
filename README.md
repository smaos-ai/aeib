# Agent Evidence Interlock Boundary (AEIB) v0.4.0
### Review Candidate and Reproducibility Package

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Verification: CRVP-v1.0](https://img.shields.io/badge/Verification-CRVP--v1.0-green.svg)](compliance/crvp_attestation.json)
[![Status: Review Candidate](https://img.shields.io/badge/Status-Review%20Candidate-orange.svg)](REPRODUCE.md)

> **"Don't trust. No unprovable promises. Show Me. Change It. Prove It."**  
> *AEIB shifts the burden of proof from self-reported agent claims to offline mathematical attestation, bit-for-bit clean-room reproducibility, and target-side ledger ground truth.*

---

## 🏛️ Epistemic Stance: Fluff → Clarity → Precision

AEIB operates under a strict epistemic lock. It does not claim universal exactly-once execution, absence of remote duplicate mutations, complete prompt-injection prevention, or blanket regulatory conformity. 

Execution finality is grounded in physical wire observations, RFC 8785 JSON Canonicalization Scheme (JCS), deterministic Content-Addressed Action Identifiers (CAID), and out-of-band target ledger probes.

### The 5 Strictly Approved Claims (External Boundary)
Only these 5 empirical statements are permitted in documentation, audits, and external deliverables:
1. **"No duplicate retry was issued by the controlled gateway in the tested scenario."**
2. **"The gateway preserved an ambiguous outcome after the tested transport fault."**
3. **"The verifier detected tampering in the supplied artifact bundle."**
4. **"The benchmark grades against target-side state rather than agent self-report."**
5. **"The adapter integrates with existing identity and gateway controls."**

---

## 📦 The 3 Core Deliverable Products

### Product 1: `aeib-bench` v0.1 — Target-Side Fault & Effect-Integrity Benchmark
* **Specification**: [`schemas/aeib_bench_v0.1_spec.json`](schemas/aeib_bench_v0.1_spec.json)
* **Test Implementation**: [`tests/test_acceptance_test_12.py`](tests/test_acceptance_test_12.py)
* **Ground-Truth Invariant**: Benchmark scoring is derived **exclusively from target-side ledger state** (`SHOW ME. CHANGE IT. PROVE IT.`), completely ignoring agent text output, model reasoning chains, or proxy self-reports.
* **Coverage**: Evaluates 12 wire-fault scenarios across 4 target capability classes:
  - *Idempotency Key + Status API*: Optimal duplicate control; single-flight probe reconciliation.
  - *Idempotency Key Only*: Safe retry suppression; idempotency token binding.
  - *Status API Only*: Post-fault reconciliation; target determines duplicate prevention.
  - *Browser-Only Workflow*: Response ambiguity; state freezing at `EFFECT_INDETERMINATE`.
  - *No Cooperation*: Complete uncertainty preservation; fail-closed latching.
* **Headline Metrics**: Evaluates unauthorized retries, duplicate dispatches, duplicate target effects, false confirmations, indeterminate resolution latency, and operator intervention costs.

### Product 2: AEIB Gateway Adapter — Inline Uncertainty Preservation & Single-Flight Coalescing
* **Core Engine**: [`src/aeib_v040_engine.py`](src/aeib_v040_engine.py)
* **Concurrency Primitive**: [`src/probe_coalescer.py`](src/probe_coalescer.py)
* **P0 Invariant Suite**: [`tests/test_p0_durable_ledger.py`](tests/test_p0_durable_ledger.py)
* **Core Mechanics**:
  - **Deterministic CAID**: Content-Addressed Action Identifier derived via $H(\text{Noun} \parallel \text{Verb} \parallel \text{JCS}(\text{Payload}))$ per RFC 8785.
  - **Inline Uncertainty Latching**: When post-dispatch faults occur (HTTP 504 / TCP RST), execution freezes at `RECONCILIATION_NOT_FOUND_AFTER_GRACE` or `EFFECT_INDETERMINATE` with `retry_safe: false` and `latch_engaged: true`. Speculative retries are blocked fail-closed.
  - **Single-Flight Coalescing**: When multiple concurrent workers encounter ambiguous transport drops for the same `effect_id`, `ProbeCoalescer` executes exactly 1 authoritative target probe bounded by a global semaphore; all workers share the verified outcome.
  - **Release Separation**: *"Verified is not Released"*. AEIB receipts verify evidence completeness and mapping validity; release authority remains decoupled.

### Product 3: Regulated Evidence Export — DORA Article 17 & 28(3) Exporters
* **Incident Timeline Exporter (DORA Art. 17 / RTS 2025/301)**: [`scripts/export_dora_incident.py`](scripts/export_dora_incident.py) converts raw transport fault traces and unconfirmed latch events into structured 4-hour materiality notifications with explicit deadlines.
* **Register of Information Exporter (DORA Art. 28(3) / ITS 2024/2956)**: [`scripts/validate_dora_register.py`](scripts/validate_dora_register.py) compiles ICT service dependencies and adapter references into standardized xBRL-CSV templates (RT.01.01 to RT.02.03) for third-party risk management.

---

## 🔒 Clean-Room Verification Protocol (CRVP)

AEIB enforces **Zero-Mock & Cryptographic Purity**:
* **Zero Fake Crypto**: No `mock_signature` or `stub_hash`. All signing uses real `cryptography.hazmat` (Ed25519) primitives.
* **Zero Bypass Gates**: No conditional shortcuts or test mocks.
* **RFC 8785 JCS Compliance**: Canonical JSON conforms strictly to UTF-16 code unit ordering and ECMAScript number formatting.
* **Offline Attestation Manifest**: [`compliance/crvp_attestation.json`](compliance/crvp_attestation.json) binds the exact source-tree SHA-256 digest to an Ed25519 digital signature.

### Standalone Verifier (`aeib-verify`)
The verification suite is decoupled from the runtime. An independent, zero-dependency verifier ([`verifier/verify_attestation.py`](verifier/verify_attestation.py)) reproduces the on-disk codebase digest bit-for-bit without trusting local test reports.

---

## 🚀 Independent Second-Environment Reproduction Sequence

To reproduce the reported results on a clean host terminal:

```bash
# 1. Enforce AST mock purity across codebase
python3 scripts/ast_purity_scanner.py

# 2. Verify grounded claims without bypasses
python3 scripts/ci_claims_verifier.py

# 3. Run core protection, falsifiability, MCP gate, durable ledger, and benchmark matrix
pytest tests/test_industrial_protection_matrix.py \
       tests/test_ansi_50bf_breaker_failure.py \
       tests/test_saga_compensation.py \
       tests/test_falsifiability_matrix.py \
       tests/test_mcp_acceptance_criteria.py \
       tests/test_bbs_plus_redactable.py \
       tests/test_p0_durable_ledger.py \
       tests/test_acceptance_test_12.py -v

# 4. Verify signed CRVP attestation and codebase SHA-256 digest bit-for-bit
python3 verifier/verify_attestation.py

# 5. Run deterministic 500-episode transport-fault baseline harness
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
```

---

## 📊 Baseline Benchmark Results (500 Episodes, Seed 42)

* **Arm 1 (Naive Retry Baseline):** 60.4% duplicate mutations (302/500).
* **Arm 2 (Payload Key / Semantic Drift):** 37.4% duplicate mutations (187/500) under stochastic parameter drift.
* **Arm 3 (Server Stable Key):** 0 duplicate mutations, 198 unresolved drops.
* **Arm 4 (AEIB Protocol):** **0 duplicate mutations** observed under stated synthetic model; 302 retry attempts blocked (gate=234, ledger=68). Rule-of-Three 95% CI upper bound $\le 0.60\%$.

---

## 📦 Reproducible Archive Bundles

* **Review Candidate Archive**: `dist/aeib-v0.4.0-review-candidate.tar.gz`
* **Clean-Room Verification Archive**: `dist/aeib-v0.4.0-cleanroom.tar.gz`
* **Attestation Manifest**: `compliance/crvp_attestation.json`

---

## ⚠️ Known Limitations & Boundaries

1. **Simulation Model Bounds:** The 500-episode harness is a deterministic simulation of retry-duplication mechanics across 15 synthetic fault classes. It evaluates internal protocol logic under the declared model, not live public Internet conditions.
2. **Target Idempotency Reliance:** Authoritative settlement depends on target systems providing idempotency keys or queryable state APIs. When targets provide no cooperation, AEIB freezes at `DISPATCHED_UNCONFIRMED` and halts fail-closed.
3. **Regulatory Context:** DORA Article 17/28(3) exporters format technical traces and service registers into regulatory schemas. They do not constitute autonomous regulatory certification or legal compliance.
4. **Scaffolding Code:** Code in `ebpf/` is architectural scaffolding. It does not provide live kernel packet interception in this package.

---

## 📄 Licensing

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.
