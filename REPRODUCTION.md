# AEIB Reproduction Guide & Clean-Room Verification Manual

```text
Specification Version : 1.0.0-rc.5-preprod
Evaluation Status     : Pre-Production Local Verification Baseline
Reproducibility Model : Clean-Room Hermetic Execution & Air-Gapped Hardware Vault
```

This guide details the procedure for reproducing the local verification baseline for **AEIB v1.0.0-rc.5-preprod**. To evaluate the AEIB execution boundary without host OS contamination or filesystem caching illusions, auditors may execute the clean-room suite using either standard containerized/host isolation or a physically isolated external NVMe SSD.

---

## Option A: Standard Clean-Room Environment (CI / Air-Gapped Host)

Execute the following commands in a clean environment with zero external network dependencies:

### 1. Static AST & Architectural Boundary Verification
Execute the pre-commit static AST gates to confirm that dynamic code execution primitives (`eval`, `exec`, `compile`, `importlib`), stubs, and unvetted imports are absent from governed modules:

```bash
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py
python3 compliance/aeib_p3c_ast_gate.py
```

*Expected Result:* All scripts exit with code `0` and report `0` violations.

### 2. Core Remediation, Temporal Conformance & Chaos Fuzzing
Run the remediation suite verifying Station 1 invariants (AT69–AT74, RFC 8785 JCS canonicalization, Ed25519 signatures, Merkle tree root recovery, and atomic journal persistence):

```bash
pytest \
  tools/aeib_offline_verifier.py \
  tests/test_complete_remediation_at69_to_at74.py \
  tests/test_real_local_ambiguous_refund.py \
  tests/test_final_gap_closures.py \
  tools/temporal_conformance.py \
  -v
```

*Expected Result:* All tests report `PASSED` in under 3 seconds.

### 3. Apple Native Swift 6 Concurrency & Cross-Language Byte Parity (macOS Environments)
Run the native Swift 6 test suite under complete strict concurrency checking:

```bash
swift test -Xswiftc -strict-concurrency=complete
```

*Expected Result:* 11 passed (0 failed) in under 0.2 seconds. Cross-language golden vector SHA-256 matches bit-for-bit with the Python reference implementation.

### 4. 10,000-Schedule Deterministic Simulation Testing (DST)
Execute the deterministic simulation testing (DST) harness under PRNG seed `20261020`:

```bash
python3 tools/aeib_dst_harness.py \
  --schedules 10000 \
  --seed 20261020 \
  --save-traces output/dst-traces-20261020 \
  --report output/dst-report-20261020.json
```

*Observed Baseline Metrics (`seed=20261020`):*
- Schedules Evaluated: `10,000`
- Ambiguous Timeouts Intercepted: `3,018`
- Retries Blocked: `3,018`
- Total Reconciled: `6,520`
- Observed Duplicate Mutations: `0`
- Invariant Violations: `0` (I1–I7 clean)

### 5. Forward Workstream Prototype Verification (v1.0.0-rc.6 Targets)
Validate the real FIPS 204 ML-DSA-65 + Ed25519 hybrid envelope tests and execution integrity telemetry:

```bash
pytest \
  tests/test_hybrid_pqc_envelope.py \
  tests/test_execution_integrity_telemetry.py \
  -v
```

---

## Option B: The Air-Gapped External NVMe SSD "Cold Vault" (Maximum Rigor)

To evaluate physical execution isolation against host kernel interception, filesystem spoofing, or memory tampering, auditors can execute the reproduction suite on bare metal using a bootable external NVMe SSD.

### Prerequisites
- High-speed external NVMe SSD (Thunderbolt 3/4 or USB 3.2 Gen 2x2).
- Partitioned into two volumes:
  - `AEIB-BOOT`: Bootable Ubuntu 24.04 LTS (Compiled with `CONFIG_BPF_LSM=y` and `lsm=lockdown,capability,landlock,yama,apparmor,bpf`).
  - `AEIB-EVIDENCE` (ext4 / APFS Encrypted): Dedicated evidence vault mounted with direct I/O.

### Execution Steps
1. **Boot Bare Metal**:
   Plug in the external SSD, restart the host machine, select the external drive in startup options, and boot directly into the isolated Linux environment. (Host internal drives remain unmounted).

2. **Mount Evidence Vault with Direct I/O**:
   ```bash
   sudo mkdir -p /mnt/aeib_vault
   sudo mount -o o_direct /dev/nvme1n1p2 /mnt/aeib_vault
   export AEIB_EVIDENCE_VAULT_PATH="/mnt/aeib_vault"
   ```

3. **Run Verification & Bare-Metal eBPF LSM Receipts**:
   ```bash
   git clone https://github.com/SovereignNexus/sovereign-nexus-aeib.git /mnt/aeib_vault/repo
   cd /mnt/aeib_vault/repo
   git checkout feat/v1.1-temporal-standing

   # Run real kernel BPF_LSM attachment check (when deployed on Linux host)
   bash scripts/verify_real_ebpf_lsm_kernel.sh || true

   # Run full test battery pointing directly to the hardware vault
   python3 tools/aeib_dst_harness.py \
     --schedules 10000 \
     --seed 20261020 \
     --report /mnt/aeib_vault/output/dst-report.json
   ```

4. **The Cable-Yank Durability Test (Empirical Chaos Verification)**:
   - While running high-concurrency DST dispatches that trigger `EFFECT_INDETERMINATE` escrow states, physically disconnect the external SSD cable.
   - Reconnect the drive, reboot into the environment, and execute recovery verification:
   ```bash
   python3 tools/temporal_conformance.py --verify-vault /mnt/aeib_vault
   ```
   - *Evaluated Property*: Evaluates whether direct I/O (`O_DIRECT`) and write-through barriers (`F_FULLFSYNC` / `fdatasync`) preserved the chain tip and uncertainty latch without journal corruption.

---

## 3. Cryptographic Verification of Evidence Artifacts

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

## 4. Epistemic Notice & Forward Workstreams

These reproduction steps verify local implementation conformance and deterministic behavior under the stated test harness and fault schedules. They do not constitute third-party certification or universal claims about external network services.

> **AEIB proposes three forward workstreams: EBV alignment with the cited Internet-Draft vocabulary, a hybrid Ed25519/ML-DSA-65 evidence-envelope design, and execution-integrity telemetry for operator risk monitoring. These are specification and implementation targets, not completed standards, verified post-quantum protections, or insurance underwriting decisions.**
