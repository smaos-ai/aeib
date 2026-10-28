#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# AEIB v0.4.0 CRVP-Verified Reproducible Archive Generator
"""
Packages verified v0.4.0 artifacts into bit-for-bit reproducible archive:
aeib-v0.4.0-crvp-verified.tar.gz and dist/aeib-v0.4.0-crvp-verified.tar.gz.

1. Asserts compliance/crvp_attestation.json is clean (ast_purity_status.clean == True).
2. Generates canonical compliance/aeib_manifest.jsonl.
3. Builds bit-for-bit deterministic tar.gz with fixed mtime, uid/gid=0, and sorted entries.
4. Validates reproducibility across builds (sha1 == sha2).
"""

import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files included in the canonical v0.4.0 distribution
CANONICAL_FILES = [
    "README.md",
    "LICENSE",
    "config/claims.jsonl",
    "schemas/aeib-receipt-v0.4.0.json",
    "compliance/crvp_attestation.json",
    "compliance/check_zone_boundary.py",
    "compliance/ast_purity.py",
    "compliance/no_mock_enforcer.py",
    "src/aeib_v040_engine.py",
    "src/jcs_canonicalizer.py",
    "src/cose_signer.py",
    "src/cose_verifier.py",
    "src/mcp_schema_pinning.py",
    "src/probe_coalescer.py",
    "src/pqc_signer_bridge.py",
    "src/sqlite_probe_adapter.py",
    "scripts/ast_purity_scanner.py",
    "scripts/generate_crvp_attestation.py",
    "scripts/ci_claims_verifier.py",
    "cleanroom/Dockerfile",
    "cleanroom/verify_from_scratch.py",
    "cleanroom/tcp_chaos_server.py",
]

FIXED_MTIME = 1791331200  # 2026-10-07 00:00:00 UTC


def verify_crvp_status():
    attestation_path = REPO_ROOT / "compliance" / "crvp_attestation.json"
    if not attestation_path.exists():
        print(f"[!] Error: {attestation_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(attestation_path.read_text(encoding="utf-8"))
    clean = data.get("ast_purity_status", {}).get("clean", False)
    if not clean:
        print("[!] Error: CRVP attestation ast_purity_status.clean is not true!", file=sys.stderr)
        sys.exit(1)

    print("[+] CRVP attestation confirmed clean.")


def update_manifest():
    manifest_path = REPO_ROOT / "compliance" / "aeib_manifest.jsonl"
    lines = []
    for rel_path in sorted(CANONICAL_FILES):
        p = REPO_ROOT / rel_path
        if not p.exists():
            print(f"[!] Warning: Missing canonical file {rel_path}", file=sys.stderr)
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(json.dumps({"file": rel_path, "sha256": h}))

    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[+] Canonical manifest written to {manifest_path} ({len(lines)} entries).")


def filter_tarinfo(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    tarinfo.mtime = FIXED_MTIME
    tarinfo.mode = 0o644 if tarinfo.isreg() else 0o755
    return tarinfo


def build_tar_bytes() -> bytes:
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        for rel_path in sorted(CANONICAL_FILES + ["compliance/aeib_manifest.jsonl"]):
            disk_path = REPO_ROOT / rel_path
            if not disk_path.exists():
                continue
            arcname = f"aeib-v0.4.0/{rel_path}"
            tarinfo = tar.gettarinfo(str(disk_path), arcname=arcname)
            tarinfo = filter_tarinfo(tarinfo)
            if tarinfo.isreg():
                with open(disk_path, "rb") as f:
                    tar.addfile(tarinfo, f)
            else:
                tar.addfile(tarinfo)

    tar_bytes = tar_buf.getvalue()

    # Compress with fixed gzip mtime
    gz_buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buf, mtime=0) as gz:
        gz.write(tar_bytes)

    return gz_buf.getvalue()


def main():
    print("[*] Verifying CRVP attestation status...")
    verify_crvp_status()

    print("[*] Updating canonical manifest with CRVP artifact...")
    update_manifest()

    print("[*] Generating reproducible v0.4.0 archive...")
    bytes1 = build_tar_bytes()
    sha1 = hashlib.sha256(bytes1).hexdigest()

    bytes2 = build_tar_bytes()
    sha2 = hashlib.sha256(bytes2).hexdigest()

    if sha1 != sha2:
        print("[!] FATAL: Non-deterministic build detected! Hashes diverge.", file=sys.stderr)
        sys.exit(1)

    # Write to root and dist/
    out_paths = [
        REPO_ROOT / "aeib-v0.4.0-crvp-verified.tar.gz",
        REPO_ROOT / "dist" / "aeib-v0.4.0-crvp-verified.tar.gz"
    ]

    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bytes1)
        sha_file = p.with_suffix(p.suffix + ".sha256")
        sha_file.write_text(f"{sha1}  {p.name}\n", encoding="utf-8")

    print("========================================================")
    print("✅ AEIB v0.4.0 ARCHIVE SUCCESSFULLY LOCKED")
    print("📦 Artifact: aeib-v0.4.0-crvp-verified.tar.gz")
    print(f"🔒 SHA-256:  {sha1}")
    print(f"📁 Size:     {len(bytes1)} bytes")
    print("========================================================")
    print("[*] Ready for Zenodo deposition and Gate 3 reviewer dispatch.")


if __name__ == "__main__":
    main()
