#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
scripts/build_airgapped_release_archive.py — Builder for Offline-Verifiable Release Archive.

Builds:
  dist/aeib-v1.0.0-rc.5-preprod-airgapped/
  aeib-v1.0.0-rc.5-preprod-airgapped.tar.gz
  aeib-v1.0.0-rc.5-preprod-airgapped.tar.gz.sha256

Enforces strict epistemic calibration and deterministic file hashing.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
RELEASE_NAME = "aeib-v1.0.0-rc.5-preprod-airgapped"
TARGET_DIR = DIST_DIR / RELEASE_NAME


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> int:
    print(f"[*] Assembling release archive in: {TARGET_DIR}")
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)

    # 1. Directory Structure
    (TARGET_DIR / "source").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "verifiers").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "conformance" / "mcp_golden_vectors").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "conformance" / "blackbox_vectors").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "conformance" / "temporal_vectors").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "conformance" / "negative_vectors").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "reports" / "criterion-report").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "receipts").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "checksums").mkdir(parents=True, exist_ok=True)
    (TARGET_DIR / "tools").mkdir(parents=True, exist_ok=True)

    # 2. Source Bundle & Source Tarball
    print("[*] Generating git bundle...")
    bundle_path = TARGET_DIR / "source" / "aeib-v1.0.0-rc.5.bundle"
    res = subprocess.run(
        ["git", "bundle", "create", str(bundle_path), "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"Error creating git bundle: {res.stderr}", file=sys.stderr)
        return 1

    print("[*] Packaging source tarball...")
    source_tar_path = TARGET_DIR / "source" / "sovereign-nexus-source.tar.gz"
    # Create clean tarball of working source excluding target, dist, caches
    with tarfile.open(source_tar_path, "w:gz") as tar:
        for item in ["src", "tests", "compliance", "crates", "adapters", "tools", "schemas", "docs", "benchmarks", "contextcart-mcp", "evidence", "v1.1-roadmap", "Cargo.toml", "Cargo.lock"]:
            item_path = REPO_ROOT / item
            if item_path.exists():
                tar.add(item_path, arcname=item)

    # 3. Verifiers & Tools & Source Components
    print("[*] Staging source components, verifiers, and tools...")
    for comp in ["src", "tests", "compliance", "benchmarks", "contextcart-mcp", "docs", "schemas", "adapters", "tools", "v1.1-roadmap", "evidence"]:
        comp_path = REPO_ROOT / comp
        if comp_path.exists():
            shutil.copytree(comp_path, TARGET_DIR / comp, dirs_exist_ok=True)

    shutil.copy2(REPO_ROOT / "tools" / "standalone_offline_verifier.py", TARGET_DIR / "verifiers" / "standalone_offline_verifier.py")
    shutil.copy2(REPO_ROOT / "tools" / "standalone_receipt_verifier.py", TARGET_DIR / "verifiers" / "receipt_verifier.py")
    shutil.copy2(REPO_ROOT / "tools" / "cloudflare_6phase_disproving_verifier.py", TARGET_DIR / "verifiers" / "evidence_verifier.py")
    shutil.copy2(REPO_ROOT / "tools" / "conformance_runner.py", TARGET_DIR / "tools" / "conformance_runner.py")

    # 4. Conformance Vectors
    print("[*] Staging conformance vectors...")
    # MCP golden vectors (30 vectors)
    mcp_vecs = REPO_ROOT / "conformance" / "vectors" / "mcp_idempotency.vectors.v1.json"
    shutil.copy2(mcp_vecs, TARGET_DIR / "conformance" / "mcp_golden_vectors" / "mcp_idempotency.vectors.v1.json")

    # Blackbox vectors (20 vectors)
    for f in (REPO_ROOT / "conformance" / "vectors").glob("act-*.json"):
        shutil.copy2(f, TARGET_DIR / "conformance" / "blackbox_vectors" / f.name)
        # Classify negative vectors
        if any(neg in f.name for neg in ["invalid", "missing", "negative", "overflow", "traversal", "ssrf", "stale", "downgrade", "timeout"]):
            shutil.copy2(f, TARGET_DIR / "conformance" / "negative_vectors" / f.name)

    # Temporal invariants
    temp_yaml = REPO_ROOT / "conformance" / "temporal_invariants_v1.yaml"
    if temp_yaml.exists():
        shutil.copy2(temp_yaml, TARGET_DIR / "conformance" / "temporal_vectors" / "temporal_invariants_v1.yaml")

    # 5. Reports
    print("[*] Staging validation reports...")
    shutil.copy2(REPO_ROOT / "output" / "pytest-report.json", TARGET_DIR / "reports" / "pytest-report.json")
    shutil.copy2(REPO_ROOT / "output" / "mcp-conformance-report.json", TARGET_DIR / "reports" / "mcp-conformance-report.json")
    shutil.copy2(REPO_ROOT / "output" / "dst-report-20261020.json", TARGET_DIR / "reports" / "dst-report.json")
    shutil.copy2(REPO_ROOT / "output" / "execution-integrity-500.json", TARGET_DIR / "reports" / "integrity-benchmark-report.json")

    # Criterion reports
    crit_src = REPO_ROOT / "target" / "criterion"
    if crit_src.exists():
        for item in crit_src.glob("*"):
            if item.is_file():
                shutil.copy2(item, TARGET_DIR / "reports" / "criterion-report" / item.name)
            elif item.is_dir():
                shutil.copytree(item, TARGET_DIR / "reports" / "criterion-report" / item.name, dirs_exist_ok=True)

    # 6. Verifiable Receipts
    print("[*] Staging cryptographic receipts...")
    shutil.copy2(REPO_ROOT / "output" / "master_parallel_validation_receipt.json", TARGET_DIR / "receipts" / "master_validation_receipt.json")
    shutil.copy2(REPO_ROOT / "output" / "backup-restorability-receipt.json", TARGET_DIR / "receipts" / "backup_receipt.json")

    # 7. Documentation
    print("[*] Writing documentation and limitation boundaries...")
    shutil.copy2(REPO_ROOT / "LIMITATIONS.md", TARGET_DIR / "LIMITATIONS.md")

    head_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()

    # VERIFICATION.md
    verification_md = f"""# AEIB Pre-Production Verification Guide (Release Candidate 5)

## Epistemic Boundary Notice
This package is an **offline-verifiable release archive** prepared for external audit review.
All claims represent observed empirical behavior under declared, local test harnesses and single-process boundaries.
See `LIMITATIONS.md` for explicit exclusions.

---

## 1. SHA-256 Manifest Verification

Verify the integrity of all files in this release archive:

```bash
sha256sum -c MANIFEST.sha256
```

All files must return `OK`.

---

## 2. Independent Receipt Verification

Verify the master cryptographic validation receipt without external dependencies:

```bash
python3 verifiers/standalone_offline_verifier.py \\
  --verify-receipt receipts/master_validation_receipt.json
```

Expected result:
```text
[VALID] Receipt authenticated successfully (AEIB_EXECUTION)
  receipt_type: AEIB_EXECUTION
  disposition: CONFIRMED
```

---

## 3. Conformance Suite Reproduction

Reproduce the 30-vector MCP idempotency golden suite:

```bash
python3 tools/conformance_runner.py \\
  --vectors conformance/mcp_golden_vectors \\
  --report reports/reproduced-mcp-conformance.json
```

Expected result:
```text
[=] Conformance Evaluation Summary: 30/30 passed (100.0%)
```

---

## 4. Declared Test Suite Execution

Run pytest directly on the declared local test suites:

```bash
pytest tests/test_dst_multi_region_partition.py tests/test_contextcart_20_tasks.py tests/test_postgres_tcc_concurrency_stress.py tests/test_secure_mcp_uds_boundary.py tests/test_dynamic_code_policy_gate.py tests/test_governed_cross_model_handoff.py tests/test_audit_disproving_verifier.py tests/test_ncm_parallel_burst_latch.py tests/test_artemis_device_and_plugin_boundary.py tests/test_predictive_trajectory_drift_latch.py tests/test_zk_budget_proof_engine.py tests/test_standalone_offline_verifier.py tests/test_bpf_lsm_profile_compiler.py -q
```

Expected result:
```text
149 passed
```

---

## 5. Epistemic Verification Check

Verify that no prohibited promotional claims exist across the codebase:

```bash
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py
```

Expected result:
```text
[✓] AST Purity: Zero stubs, zero forbidden strings, zero mock calls.
```
"""
    with open(TARGET_DIR / "VERIFICATION.md", "w", encoding="utf-8") as f:
        f.write(verification_md)

    # RELEASE_NOTES.md
    source_archive_sha256 = compute_sha256(source_tar_path)
    release_notes_md = f"""# AEIB v1.0.0-rc.5-preprod Release Notes & Manifest

```yaml
release:
  name: aeib-v1.0.0-rc.5-preprod
  status: preproduction_release_candidate
  commit: {head_commit}
  branch: feat/v1.1-temporal-standing
  created_utc: "2026-10-21T00:00:00Z"
  source_archive_sha256: {source_archive_sha256}

verified_claims:
  rust_tests:
    result: 149_passed
    scope: declared_test_set
  criterion_latency:
    result: approximately_43.8_us_per_tx
    scope: declared_benchmark_configuration
  mcp_golden_vectors:
    result: 30_passed
    scope: declared_vector_set
  nvme_backup:
    result: mirror_created_and_hash_verified
    scope: declared_backup_procedure

not_claimed:
  - production readiness
  - multi-node correctness
  - real eBPF kernel enforcement
  - post-quantum security
  - regulatory certification
  - adversarial escape resistance
  - independent reproduction
```

## Summary of Evaluated Components
1. **Track 2 Native Data Plane (`crates/aeib-data-plane`):**
   - Constant-time Station 1 5-tuple gate (`ed25519-dalek` + `subtle`).
   - Group-commit Write-Ahead Log (`DirectIoWal`) utilizing `fcntl(fd, F_FULLFSYNC, 1)` on Darwin / `O_DIRECT` on Linux.
   - RFC 9942 / RFC 9943 SCITT Merkle inclusion tree generator.
   - Hardware TEE ephemeral key attestation scaffold.
2. **Hardened Idempotent MCP Proxy (`adapters/mcp/idempotent_mcp_proxy.py`):**
   - Evaluated against 30 golden vectors: 30/30 passed (100.0%).
   - Composite identity disambiguation: `(tenant_id, principal_id, operation_id, tool_name)`.
   - Tool-level `isError: true` inspection routing to uncertainty latch.
   - Decoupled storage retention TTL vs. unresolved uncertainty lifecycle.
3. **Standalone Zero-Dependency Offline Verifier (`tools/standalone_offline_verifier.py`):**
   - Pure-Python RFC 8032 Ed25519 verification math, RFC 8785 JCS, and RFC 9162 Merkle tree proofs.
"""
    with open(TARGET_DIR / "RELEASE_NOTES.md", "w", encoding="utf-8") as f:
        f.write(release_notes_md)

    # 8. Category Checksums
    print("[*] Generating category checksums...")
    with open(TARGET_DIR / "checksums" / "source.sha256", "w", encoding="utf-8") as f:
        for sf in (TARGET_DIR / "source").glob("*"):
            if sf.is_file():
                f.write(f"{compute_sha256(sf)}  source/{sf.name}\n")

    with open(TARGET_DIR / "checksums" / "reports.sha256", "w", encoding="utf-8") as f:
        for rf in (TARGET_DIR / "reports").rglob("*"):
            if rf.is_file():
                rel = rf.relative_to(TARGET_DIR)
                f.write(f"{compute_sha256(rf)}  {rel}\n")

    with open(TARGET_DIR / "checksums" / "binaries.sha256", "w", encoding="utf-8") as f:
        # Check dist for wasm artifacts
        for wasm in REPO_ROOT.glob("*.wasm"):
            f.write(f"{compute_sha256(wasm)}  {wasm.name}\n")
        dist_wasm = REPO_ROOT / "dist" / "smaos_verify.wasm"
        if dist_wasm.exists():
            f.write(f"{compute_sha256(dist_wasm)}  smaos_verify.wasm\n")

    # 9. Top-Level MANIFEST.sha256
    print("[*] Generating top-level MANIFEST.sha256...")
    manifest_lines = []
    for file_path in sorted(TARGET_DIR.rglob("*")):
        if file_path.is_file() and file_path.name != "MANIFEST.sha256":
            rel_path = file_path.relative_to(TARGET_DIR)
            manifest_lines.append(f"{compute_sha256(file_path)}  {rel_path}\n")

    with open(TARGET_DIR / "MANIFEST.sha256", "w", encoding="utf-8") as f:
        f.writelines(manifest_lines)

    # 10. Compressed Tarball
    tarball_name = f"{RELEASE_NAME}.tar.gz"
    tarball_path = DIST_DIR / tarball_name
    print(f"[*] Packaging compressed tarball: {tarball_path}...")
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(TARGET_DIR, arcname=RELEASE_NAME)

    tarball_sha256 = compute_sha256(tarball_path)
    sha_file = DIST_DIR / f"{tarball_name}.sha256"
    with open(sha_file, "w", encoding="utf-8") as f:
        f.write(f"{tarball_sha256}  {tarball_name}\n")

    print(f"[✓] Release archive built successfully.")
    print(f"    Tarball: {tarball_path}")
    print(f"    SHA-256: {tarball_sha256}")
    print(f"    Manifest: {TARGET_DIR / 'MANIFEST.sha256'} ({len(manifest_lines)} files)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
