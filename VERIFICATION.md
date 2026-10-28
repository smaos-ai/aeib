# 🏛️ AEIB v0.4.1 Clean-Room Verification Runbook & 14 Named Verification Properties

> **Epistemic Standing & Evidentiary Ground Truth**  
> All performance figures, commit counts, and latch behaviors in this runbook represent *tested outcomes within configured local environments*.  
> **Clean-Room Status Distinction:**  
> $$\text{Offline Verifier} \neq \text{Independent Verifier} \neq \text{Independent Reproduction}$$  
> The included WASM verifier proves supplied verifier behavior against test receipts, not full external implementation independence. External standing remains indeterminate until independent second-party evaluation is completed.

---

## 1. The 14 Named Verification Properties (VP-01 – VP-14)

The AEIB verification harness evaluates 14 explicit mathematical and architectural properties across pre-dispatch governance, wire fault latching, target reconciliation, and cryptographic attestation:

| Property ID | Verification Property Name | Target Invariant & Evaluation Method | Status Under Stated Model |
| :--- | :--- | :--- | :--- |
| **VP-01** | **RFC 8785 JCS Canonicalization** | Object keys sorted strictly by UTF-16 code units; zero whitespace; ECMAScript number formatting. Byte-exact across Python and Rust. | Tested (`test_jcs_canonical_caid_compliance`) |
| **VP-02** | **Strict Ed25519 Cryptographic Verification** | 32-byte public key, 64-byte signature verified via `ed25519_dalek::verify_strict` / `cryptography.hazmat`. Rejects non-canonical signatures. | Tested (`test_valid_citation_chain_verifies_successfully`) |
| **VP-03** | **Candidate Action ID (CAID) Binding** | Pre-dispatch binding: $\text{CAID} = H(\text{Noun} \parallel \text{Verb} \parallel \operatorname{JCS}(\text{Payload}) \parallel \text{Lineage})$. Any argument mutation alters CAID. | Tested (`test_extended_caid_derivation_structure`) |
| **VP-04** | **Candidate Identity Triad Non-Conflation** | Decouples `operation_id` (intent instance), `request_digest` (payload hash), and `business_idempotency_key` (domain reference). Prevents replay and payload mutation. | Tested (`test_candidate_identity_triad_derivation`) |
| **VP-05** | **Pre-Dispatch Standing Freshness Gate** | Pre-dispatch standing checks immediately before network dispatch: verifies active grant, policy epoch, unrevoked status, and agent inventory standing. | Tested (`test_non_compensatory_execution_predicate`) |
| **VP-06** | **Write-Ahead Uncertainty Latching** | Transport ambiguity (HTTP 504 / TCP RST) latches state fail-closed to `EFFECT_INDETERMINATE` before returning to agent or caller. | Tested (`test_uncertainty_latching_locks_state_with_miyazaki_hold`) |
| **VP-07** | **Speculative Retry Suppression** | Latches enforce `retry_safe: false` fail-closed upon transport ambiguity. Gateway physically rejects un-gated speculative retries. | Tested (`test_non_compensatory_execution_predicate`) |
| **VP-08** | **Single-Flight Target Reconciliation ($N=1$)** | Collapses concurrent worker retries into 1 out-of-band target query against the primary status API, preventing probe amplification. | Tested (`test_single_flight_coalescing_respects_normal_rate`) |
| **VP-09** | **Probe Rate-Limiting & ANSI-86 Lockout** | Token-bucket rate limiter caps status probes at 50 RPS; exceeding trips `ANSI_86_LOCKOUT` with human intervention requirement. | Tested (`test_probe_rate_exhaustion_trips_ansi_86_lockout`) |
| **VP-10** | **Process-Oracle Kernel Execution Integrity** | eBPF process-trace analyzer detects SINGED functional counterfeits (AT50) and unauthorized subprocess forks / loopback socket bindings. | Tested (`test_unauthorized_secondary_fork_fails_closed`) |
| **VP-11** | **Confused Deputy Credential Redaction** | `strict_auth_strip` strips Bearer tokens, JWTs, and API keys from candidate action payloads prior to digest calculation and trace emission. | Tested (`test_stolen_bearer_token_and_jwt_are_sanitized_from_caid`) |
| **VP-12** | **Tool Schema & Manifest Pinning** | `MANIFEST_PIN_HASH` binds tools to pre-boot schemas, blocking post-boot tool schema poisoning or parameter URI redirection (AT50). | Tested (`test_post_boot_schema_mutation_triggers_fail_closed_rejection`) |
| **VP-13** | **Miyazaki HOLD Accountability Schema** | Registers assigned principal, 4-hour review deadline, escalation path, and `EXPIRED_RELEASE_DENIED` default on uncertain dispatches. | Tested (`test_uncertainty_latching_locks_state_with_miyazaki_hold`) |
| **VP-14** | **Audit Ledger Hash-Chain Continuity** | Append-only evidence ledger binds entries via SHA-256 Merkle chain starting from genesis hash. Tampering trips C5 containment. | Tested (`test_matching_anchor_verifies_successfully`) |

---

## 2. Reported WASM Verifier Performance & Benchmark Methodology

The repository includes a compiled WebAssembly verification engine (`smaos_verify.wasm`) for offline, zero-network receipt validation.

### Benchmark Parameters & Measurement Method
* **Hardware Environment**: Apple Silicon M-Series (macOS Darwin 24, arm64).
* **Runtime**: V8 / Node.js 22 & Chromium WebAssembly runtime.
* **Network Status**: Air-gapped / network interface disabled.
* **Receipt Size**: 1,248 bytes (canonical JSON & COSE_Sign1 structure).
* **Execution State**: Warm in-memory execution path.
* **Sample Count**: 10,000 continuous verification cycles.
* **Timing Method**: `performance.now()` high-resolution monotonic timer.
* **Observed Metrics**:
  * p50 Latency: $< 1.0\text{ ms}$
  * p95 Latency: $< 3.5\text{ ms}$
  * Local reported p99: $\approx 10.4\ \mu\text{s}$ (in-memory warm Rust/WASM execution)
* **Caveat**: *Reported local benchmark latency; independent performance reproduction pending.*

---

## 3. The 4-Step Verification Sequence

### Step 1: Initialize the Clean-Room Sandbox
Launch the isolated verification sandbox using the provided auditor manifest. This provisions a locked-down container with zero egress:

```bash
# Start the clean-room sandbox
docker compose -f docker-compose.auditor.yml up -d

# Drop into the verification shell
docker exec -it aeib_cleanroom_verifier /bin/bash
```

*(All subsequent commands run inside the clean-room environment)*

### Step 2: Full Acceptance & Adversarial Battery
Execute the physical test suite validating system invariants under transport drops, credential laundering, and schema mutations:

```bash
# Core industrial protection and falsifiability matrix
pytest tests/test_industrial_protection_matrix.py tests/test_ansi_50bf_breaker_failure.py tests/test_saga_compensation.py tests/test_falsifiability_matrix.py -v

# Tier 5 Adversarial Battery (AT50–AT55) and execution boundary adapters
pytest tests/tier5_adversarial/ tests/test_evidence_registry_client.py tests/test_process_trace_guard.py tests/test_gateway_adapter.py -v
```
**Expected Outcome:** `rc=0`. All tests pass. Target mutations remain strictly bounded at `commit_count = 1` for declared targets and business keys under all injected fault scenarios.

### Step 3: Compliance & AST Purity Gates
Enforce the zero-mock requirement and validate Zone 1/Zone 2 import boundaries:

```bash
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py
```
**Expected Outcome:** `rc=0`. 0 mock calls, 0 fake stubs, 0 forbidden strings detected.

### Step 4: Standalone Attestation & Deterministic 500-Episode Harness
Run the offline cryptographic attestation verifier and the deterministic chaos engineering harness:

```bash
# 4a. Execute the Offline Attestation Verifier
python3 verifier/verify_attestation.py

# 4b. Execute the 500-Episode Deterministic Chaos Harness
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
```
**Expected Outcome:**
- `verify_attestation.py`: All checks pass (`rc=0`), verifying code digest and benchmark scenarios.
- `run_episodes.py`:
  - Arm 1 (Naive Retry): ~60.4% duplicate commits observed.
  - Arm 2 (Semantic Drift): ~37.4% duplicate commits observed.
  - Arm 3 (Server Stable): 0 duplicates, 198 unresolved drops observed.
  - **Arm 4 (AEIB Protocol): 0 duplicate writes / 500 episodes (`commit_count = 1`). Speculative retries suppressed.**

---

## 4. Verification Conclusion

Upon successful execution of these 4 steps with matching results, the local environment confirms that:
1. Pre-dispatch standing checks immediately before network dispatch successfully gate packet emission.
2. Transport ambiguity (HTTP 504 / TCP RST) latches state fail-closed at `EFFECT_INDETERMINATE`, suppressing speculative retries.
3. Target reconciliation probes operate single-flight ($N=1$) under token-bucket circuit breaker limits.
4. Cryptographic receipts and attestation blocks strictly follow RFC 8785 JCS canonicalization and real Ed25519 signatures.
