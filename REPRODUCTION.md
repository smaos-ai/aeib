# AEIB Reproduction Guide & Clean-Room Verification Manual

```text
Specification Version : 1.0.0-rc.4-preprod
Evaluation Status     : Pre-Production Local Verification Baseline
Reproducibility Model : Clean-Room Hermetic Execution
```

This guide details the procedure for reproducing the local verification baseline for **AEIB v1.0.0-rc.4-preprod**.

---

## 1. Prerequisites & Environment

The test suites and benchmarks have been evaluated under the following environment:
- **Operating System**: macOS Darwin (arm64, Apple Silicon) or Linux (x86_64 / arm64)
- **Python**: 3.12+ (tested under Python 3.14.3)
- **Swift**: Swift 6.0+ toolchain supporting complete strict concurrency
- **Rust**: Cargo 1.80+ (for compiled native data-plane workspace crates)
- **Node.js**: v20+ (for WASM and MCP tool tests)

---

## 2. Step-by-Step Clean-Room Reproduction

### Step 1: Static AST and Architectural Boundary Verification
Execute the pre-commit static AST gates to confirm that dynamic code execution primitives (`eval`, `exec`, `compile`, `importlib`) and unvetted imports are absent from governed modules:

```bash
python3 compliance/aeib_p3c_ast_gate.py
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py
```

*Expected Result:* All scripts exit with code `0` and report `0` violations.

### Step 2: Core Unit & Integration Remediation Tests
Run the remediation suite verifying Station 1 invariants (AT69–AT74, RFC 8785 JCS canonicalization, Ed25519 signatures, Merkle tree root recovery, and atomic journal persistence):

```bash
pytest tools/aeib_offline_verifier.py \
       tests/test_complete_remediation_at69_to_at74.py \
       tests/test_real_local_ambiguous_refund.py \
       tests/test_final_gap_closures.py \
       tools/aeib_dst_harness.py -v
```

*Expected Result:* 8 passed in under 2 seconds.

### Step 3: Apple Native Swift 6 Concurrency & Cross-Language Byte Parity
Run the native Swift 6 test suite under complete concurrency checking:

```bash
swift test -Xswiftc -strict-concurrency=complete
```

*Expected Result:* 11 passed (0 failed) in under 0.2 seconds. Cross-language golden vector SHA-256 matches bit-for-bit with the Python reference implementation.

### Step 4: 10,000-Schedule Protocol-Aware DST Benchmark
Execute the deterministic simulation testing (DST) harness under PRNG seed `20261020`:

```bash
python3 tools/aeib_dst_harness.py \
       --schedules 10000 \
       --seed 20261020 \
       --report output/dst-report-20261020.json \
       --save-traces output/dst-traces-20261020
```

*Observed Baseline Metrics (`seed=20261020`):*
- Schedules Evaluated: `10,000`
- Total Dispatches: `6,520`
- Ambiguous Timeouts Intercepted: `3,018`
- Retries Blocked: `3,018`
- Total Reconciled: `6,520`
- Observed Duplicate Mutations: `0`
- Invariant Violations: `0` (I1–I7 clean)

### Step 5: Verification of Evidence Artifact Hashes
Verify the computed cryptographic digests of emitted evidence artifacts:

```bash
shasum -a 256 smaos_verify.wasm \
               output/dst-report-20261020.json \
               output/dst-traces-20261020/traces.jsonl \
               output/dst-traces-20261020/trace_manifest.json
```

Compare the resulting SHA-256 values with `output/evidence-hashes.txt`:
- `smaos_verify.wasm`: `6ecc360af19008632c950d94910b70220e3c2cc36a5cc29fe0c33ba64d2bb041`
- `output/dst-report-20261020.json`: `3f2c3c01b510225092b46ea604ab88f873012d9149abb2bd1771c0ad401510d2`
- `output/dst-traces-20261020/traces.jsonl`: `796ab2307c17c2a3fe529972143c986581b86556869e2f5e4d2b1f00f0466197`
- `output/dst-traces-20261020/trace_manifest.json`: `1ee8e840e51416e9045183b8514dd0bdc767b18fd836b3331c93c31c0d82d706`

---

## 3. Epistemic Notice

These reproduction steps verify local implementation conformance and deterministic behavior under the stated test harness and fault schedules. They do not constitute third-party certification or universal proofs about external network services.
