#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tools/build_master_delivery_archive.py — Master 12-Item Delivery Archive Builder & NVMe Mirror

Packages the finalized 12-item pre-production release candidate scope into a deterministic,
air-gapped archive with bit-for-bit reproducible SHA-256 digests and mirrors to external NVMe.
"""

import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXED_EPOCH = 1760918400  # 2025-10-20T00:00:00Z deterministic build timestamp

MASTER_DELIVERY_FILES = [
    # Layer 1: Cryptographic & Escrow Core
    "src/eo1_write_before_execute.py",
    "adapters/mcp/idempotent_mcp_proxy.py",
    "src/runtime_boundary/runtime_execution_boundary.py",
    "tests/test_runtime_boundary_and_state_machine.py",
    # Layer 2: MicroVM Isolation & Starvation Proxy
    "src/microvm_vsock_channel.py",
    "tests/test_microvm_vsock_channel.py",
    "src/credential_starvation_proxy.py",
    "tests/test_space_egress_and_harness2_lock.py",
    # Layer 3: Local MCP UDS Transport & Dynamic Code Policy
    "src/secure_mcp_uds_boundary.py",
    "tests/test_secure_mcp_uds_boundary.py",
    "compliance/dynamic_code_policy_gate.py",
    "tests/test_dynamic_code_policy_gate.py",
    "src/bpf_lsm_profile_compiler.py",
    # Layer 4: Governed Cross-Model Handoff & OWASP MCP Gate
    "src/governed_cross_model_handoff.py",
    "tests/test_governed_cross_model_handoff.py",
    "tests/test_owasp_mcp_security_gate.py",
    # Layer 5: ContextCart AST Slicing & Perception Plane
    "tests/test_contextcart_20_tasks.py",
    "src/perception_fast_path_router.py",
    "tests/test_perception_fast_path_router.py",
    # Layer 6: SCITT Audit Engine & 10k DST Suite
    "src/scitt_bitemporal_audit_engine.py",
    "tests/test_scitt_bitemporal_audit_engine.py",
    "benchmarks/run_10k_dst_protocol_suite.py",
    "tests/test_10k_dst_protocol_suite.py",
    "evidence/dst_10k_benchmark_results.json",
    # Layer 7: Offline WASM Verifier & ML-BOM
    "tools/cyclonedx_mlbom_generator.py",
    "tests/test_offline_wasm_and_mlbom.py",
    "evidence/cyclonedx_mlbom.json",
    "smaos_verify.wasm",
    "tests/test_smaos_verify_wasm.js",
    # Publications & Whitepapers
    "papers/vldb_non_compensable_effects/manuscript.md",
    "papers/vldb_non_compensable_effects/references.bib",
    "rfcs/mcp_idempotency_and_indeterminacy_v1.md",
    "docs/whitepapers/CISO_COT_EVASION_AND_WIRE_BOUNDARIES.md",
]


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_master_tarball(repo_root: Path, output_tar_gz: Path) -> Tuple[str, Dict[str, str]]:
    manifest: Dict[str, str] = {}
    buf = io.BytesIO()

    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel_path in sorted(MASTER_DELIVERY_FILES):
            fpath = repo_root / rel_path
            if not fpath.exists():
                raise FileNotFoundError(f"Missing master delivery file: {rel_path}")

            data = fpath.read_bytes()
            manifest[rel_path] = compute_sha256(data)

            tarinfo = tarfile.TarInfo(name=f"aeib-master-v1.0.0-rc.5/{rel_path}")
            tarinfo.size = len(data)
            tarinfo.mtime = FIXED_EPOCH
            tarinfo.mode = 0o644 if not os.access(fpath, os.X_OK) else 0o755
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = ""
            tarinfo.gname = ""

            tar.addfile(tarinfo, io.BytesIO(data))

    raw_tar = buf.getvalue()
    gz_buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buf, mtime=FIXED_EPOCH) as gz:
        gz.write(raw_tar)

    compressed = gz_buf.getvalue()
    output_tar_gz.parent.mkdir(parents=True, exist_ok=True)
    output_tar_gz.write_bytes(compressed)

    tar_sha = compute_sha256(compressed)
    return tar_sha, manifest


def mirror_to_nvme(tar_path: Path, manifest: Dict[str, str], tar_sha: str) -> None:
    nvme_dir = Path("/Volumes/EXTssd/SovereignNexus_Backup/releases")
    if not nvme_dir.exists():
        print(f"[!] Warning: NVMe target {nvme_dir} not mounted; skipping mirror.")
        return

    dest_tar = nvme_dir / tar_path.name
    shutil.copy2(tar_path, dest_tar)

    manifest_path = nvme_dir / f"{tar_path.name}.manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"archive_sha256": tar_sha, "manifest": manifest}, f, indent=2)

    sha_file = nvme_dir / f"{tar_path.name}.sha256"
    sha_file.write_text(f"{tar_sha}  {tar_path.name}\n", encoding="utf-8")
    print(f"[✓] Mirrored to NVMe: {dest_tar} (SHA-256: {tar_sha})")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "output" / "master_delivery"
    out_tar = out_dir / "aeib_v1.0.0_rc5_master_12item_bundle.tar.gz"

    print("[*] Building deterministic master 12-item release candidate archive...")
    tar_sha, manifest = build_master_tarball(repo_root, out_tar)
    print(f"[✓] Master Archive built: {out_tar}")
    print(f"    SHA-256: {tar_sha}")
    print(f"    Files indexed: {len(manifest)}")

    # Cleanroom extraction test
    with tempfile.TemporaryDirectory() as cleanroom:
        print(f"[*] Verifying cleanroom extraction in: {cleanroom}")
        with tarfile.open(out_tar, mode="r:gz") as tar:
            tar.extractall(cleanroom)

        extracted_root = Path(cleanroom) / "aeib-master-v1.0.0-rc.5"
        for rel_path, expected_hash in manifest.items():
            ext_file = extracted_root / rel_path
            assert ext_file.exists(), f"Missing extracted file: {rel_path}"
            actual_hash = compute_file_sha256(ext_file)
            assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}"

        print(f"[✓] All {len(manifest)} files verified bit-for-bit in cleanroom sandbox!")

    # Mirror to NVMe
    mirror_to_nvme(out_tar, manifest, tar_sha)


if __name__ == "__main__":
    main()
