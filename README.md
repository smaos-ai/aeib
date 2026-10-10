# Agent Evidence Interlock Boundary (AEIB) v1.0.0-rc.1
### Reference Implementation, Receipt Specification (`AEIB-RECEIPT-SPEC.md`), and Reproducibility Package

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Receipt Spec: v1.0 Frozen RC1](https://img.shields.io/badge/Spec-AEIB--RECEIPT--SPEC%20v1.0-blue.svg)](AEIB-RECEIPT-SPEC.md)
[![Hosted CI: Passing](https://github.com/smaos-ai/aeib/actions/workflows/aeib-ci.yml/badge.svg)](https://github.com/smaos-ai/aeib/actions/workflows/aeib-ci.yml)
[![SLSA Provenance: Staged & Hosted CI Executed](https://img.shields.io/badge/SLSA-Provenance%20Staged-blue.svg)](aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md)

> **Final Bounded Claim (`v1.0.0-rc.1`):**  
> **AEIB v1.0.0-rc.1 is a Java 21-compatible deterministic execution-integrity runtime for agentic systems. It is designed to verify a pinned manifest, evaluate candidate actions locally before dispatch without external I/O, represent ambiguous transport outcomes as `EFFECT_INDETERMINATE`, resolve uncertainty through declared semantic reconciliation with bounded probe budgets, and produce tamper-evident RFC 8785–bound Ed25519 hash-chain receipts. The standalone verifier requires the caller to supply the public key associated with the receipt’s `keyId`. AEIB does not claim universal exactly-once execution across uncooperative targets, provide external SCITT anchoring, implement automatic key lookup, validate memory or retrieval provenance, or claim regulatory compliance. Hosted branch/tag CI has executed (`38055110173`, `38055279949`); independent third-party reproduction from the signed tag remains pending.**

---

## 📜 Frozen Receipt Specification & Cross-Language Verification (`v1.0.0-rc.1`)

* **Standalone Specification**: [`AEIB-RECEIPT-SPEC.md`](AEIB-RECEIPT-SPEC.md) (also mirrored at [`docs/AEIB-RECEIPT-SPEC.md`](docs/AEIB-RECEIPT-SPEC.md) and [`RECEIPT_SPEC.md`](RECEIPT_SPEC.md)) — Frozen `RC1` specification defining the RFC 8785 (JCS) canonical statement, detached Ed25519 envelope, `EFFECT_INDETERMINATE` wire-fault settlement semantics, and the 5-step language-agnostic offline verification algorithm.
* **Java 21 Reference Runtime & Standalone Verifier**: [`aeib-native-runtime/`](aeib-native-runtime/) (`./gradlew clean test --no-daemon --stacktrace`) — Executes real HTTP/TCP socket wire-fault tests (`Gate4IntegrationTest`) and standalone offline receipt verification (`com.aeib.verifier.ReceiptVerifier`) under a caller-supplied public key.
* **Standalone Non-Java Reference Verifier (Python 3)**: [`benchmarks/jvm_native_diff_engine.py`](benchmarks/jvm_native_diff_engine.py) & [`aeib_verify.py`](aeib_verify.py) — Zero-JVM Python 3 standalone verifier designed for offline verification (RFC 8785 JCS via `src/jcs_canonicalizer.py` and Ed25519 signature verification via `cryptography.hazmat`) that evaluates the Java-minted `receipt.json` and all 13 negative/positive conformance vectors (`14/14` matched, `0 B` canonical JCS divergence); independence requires separate execution and evidence.
* **Air-Gapped Rust/WebAssembly Verifier**: [`smaos-wasm-verifier/`](smaos-wasm-verifier/) (`smaos_verify.wasm` + [`dist/verifier.html`](dist/verifier.html)) — Pure Rust `ed25519-dalek` `verify_strict` standalone verifier compiled to `wasm32-unknown-unknown` for offline browser verification.
* **SLSA Provenance Contract & Hosted CI Execution**: [`v1.0.0-rc.1` Release](https://github.com/smaos-ai/aeib/releases/tag/v1.0.0-rc.1) — SLSA provenance contract documented in [`aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md`](aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md) and executed in hosted CI (`38055110173`, `38055279949`) via `slsa-framework/slsa-github-generator` (`generator_generic_slsa3.yml@v2.1.0`); independent third-party verification remains pending.

---

## 🏛️ Epistemic Stance: Fluff → Clarity → Precision

AEIB operates under a strict epistemic lock. It does not claim universal exactly-once execution, absence of remote duplicate mutations, complete prompt-injection prevention, or blanket regulatory conformity. 

Execution evaluation is grounded in wire observations, RFC 8785 JSON Canonicalization Scheme (JCS), deterministic Content-Addressed Action Identifiers (CAID), and target-provided semantic state under AEIB’s declared reconciliation policy.

### The 5 Strictly Approved Claims (External Boundary)
Only these 5 empirical statements are permitted in documentation, audits, and external deliverables:
1. **"No duplicate retry was issued by the controlled gateway in the tested scenario."**
2. **"The gateway preserved an ambiguous outcome after the tested transport fault."**
3. **"The verifier detected tampering in the supplied artifact bundle."**
4. **"The benchmark grades against target-side state rather than agent self-report."**
5. **"The adapter integrates with existing identity and gateway controls."**

### Core Bounded Capabilities
The core capability statements of AEIB are locked to these exact, verified bounds:
* **Pins and verifies a declared execution manifest.**
* **Evaluates declared standing locally before network dispatch.**
* **Represents uncertain transport outcomes explicitly.**
* **Reconciles uncertain outcomes under declared policy and probe budgets.**
* **Produces operation-bound, tamper-evident receipts.**

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
  - **Single-Flight Coalescing**: When multiple concurrent workers encounter ambiguous transport drops for the same `effect_id`, `ProbeCoalescer` executes at most 1 target-state probe under AEIB's declared reconciliation policy and bounded probe budget; concurrent workers share the evaluated semantic state.
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
* **Offline Attestation Manifest**: [`compliance/crvp_attestation.json`](compliance/crvp_attestation.json) binds the source-tree SHA-256 digest to an Ed25519 digital signature verified under the supplied public key.

### Standalone Verifier (`aeib-verify`)
The verification suite is decoupled from the runtime. A standalone verifier designed for offline verification ([`verifier/verify_attestation.py`](verifier/verify_attestation.py)) evaluates the on-disk codebase digest and signature under the supplied public key; independence requires separate execution and evidence.

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
2. **Target Idempotency Reliance:** Target-provided semantic state reconciliation under AEIB’s declared policy depends on target systems providing idempotency keys or queryable state APIs. When targets provide no cooperation, AEIB freezes at `EFFECT_INDETERMINATE` or `DISPATCHED_UNCONFIRMED` and halts fail-closed.
3. **Regulatory Context:** DORA Article 17/28(3) exporters format technical traces and service registers into regulatory schemas. They do not constitute autonomous regulatory certification or legal compliance.
4. **Scaffolding Code:** Code in `ebpf/` is architectural scaffolding. It does not provide live kernel packet interception in this package.

---

## External Examination Candidate (`v1.1` Candidate)

Prerequisites & Current Status:
- [x] Signed `v1.0.0-rc.1` release tag ([`v1.0.0-rc.1`](https://github.com/smaos-ai/aeib/releases/tag/v1.0.0-rc.1))
- [x] Hosted branch/tag CI execution (`38055110173`, `38055279949`) and SLSA provenance contract documented in [`aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md`](aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md)
- [x] Published receipt specification ([`AEIB-RECEIPT-SPEC.md`](AEIB-RECEIPT-SPEC.md)) & acceptance suite
- [x] Cross-language standalone verifier check ([`benchmarks/jvm_native_diff_engine.py`](benchmarks/jvm_native_diff_engine.py) — Python 3 vs. Java 21 over 14 receipt vectors, 0-byte JCS divergence)
- [ ] Independent third-party reproduction from the signed tag (Gate 3 harness ready in [`aeib-reproducibility/gate3/`](aeib-reproducibility/gate3/); separate-party evidence pending)
- [ ] Independent external cryptographic & institutional examination (v1.1 candidate; not scheduled)
- [x] Preserved limitations ([`LIMITATIONS.md`](LIMITATIONS.md))

External Examination Status:
- Not scheduled
- No examiner engaged
- No target determination assumed

---

## Summary Verdict Matrix

| External Signal | AEIB Decision & Scope Boundary |
| :--- | :--- |
| **Airgorah** | Documentation & layout pattern reference only. |
| **TA-14 / HSG** | Future external-validation model reference; **no equivalence claimed**. |
| **API-Gateway Separation** | Consistent design principle; candidate input for v1.1 specification. |
| **HERMES Benchmark** | Specific research context; **no generalized claims on model vs. harness**. |
| **SkillOpt / Memory Research** | Informs v1.1 procedural-write threat model candidate (**TM-12 / TM-13**). |
| **Inference & Market Signals** | Market and documentation context only. |

---

## 📄 Licensing

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.
