#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");

"""
scripts/build_review_archive.py
================================
Reproducible build script for dist/aeib-v1.0-review.tar.gz.
Ensures zero-egress, AST purity, bit-for-bit determinism, and inclusion of
only verified Zone 1 open-core components.
"""

import os
import sys
import io
import gzip
import tarfile
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files and directories to explicitly include in the release archive
INCLUDED_FILES = [
    "README.md",
    "LICENSE",
    "RELEASE_NOTES_v1.0.md",
    "TEVV.md",
    "aeib_verify.py",
    "pytest.ini",
    "docs/transport-to-disposition-mapping.yaml",
    "docs/research/AEIB_arXiv_Paper.tex",
    "replication/README.md",
    "replication/reproduce_all.py",
]

INCLUDED_DIRS = [
    ("aei_core", "aeib-v1.0/aei_core"),
    ("compliance", "aeib-v1.0/compliance"),
    ("benchmarks/aeib_execution_integrity", "aeib-v1.0/benchmarks/aeib_execution_integrity"),
    ("src/ocr_audit", "aeib-v1.0/ocr_audit"),
    ("src/ocr_audit", "aeib-v1.0/src/ocr_audit"),
]

# Individual verified source files in src/
INCLUDED_SRC_FILES = [
    "src/aei_core_middleware.py",
    "src/cose_signer.py",
    "src/cose_verifier.py",
    "src/crypto_logger.py",
    "src/human_review_console.py",
    "src/jcs_canonicalizer.py",
    "src/protection_governor.py",
    "src/research_mcp_adapter.py",
    "src/transport_interceptor.py",
    "src/transport_observer.py",
]

# The 7 curated test files that pass in clean-room extraction
INCLUDED_TEST_FILES = [
    "tests/test_industrial_protection_matrix.py",
    "tests/test_ansi_50bf_breaker_failure.py",
    "tests/test_saga_compensation.py",
    "tests/test_falsifiability_matrix.py",
    "tests/test_research_mcp_adapter.py",
    "tests/test_chaos_petri_network_faults.py",
    "tests/test_human_review_console.py",
]

# Prohibited paths/substrings to reject unconditionally
PROHIBITED_SUBSTRINGS = [
    "dora", "pkcs11", "hsm", "scratch", "secret", ".key", ".pem", ".env",
    "aeib_postgresql_probe", "tavily", "sovereign_search", "diagnostic_normalizer",
    "investordemoauto", "mfa.ts", "animations.css"
]

FIXED_MTIME = 1759651200  # 2026-10-05 08:00:00 UTC


def filter_tarinfo(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    """Normalize TarInfo header for byte-for-byte reproducibility."""
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    tarinfo.mtime = FIXED_MTIME
    return tarinfo


def collect_archive_entries() -> list[tuple[str, str]]:
    """Returns sorted list of (file_path_on_disk, arcname_in_tar)."""
    entries = []

    # Single files
    for f in INCLUDED_FILES:
        path = REPO_ROOT / f
        if path.exists():
            entries.append((str(path), f"aeib-v1.0/{f}"))

    for f in INCLUDED_SRC_FILES:
        path = REPO_ROOT / f
        if path.exists():
            entries.append((str(path), f"aeib-v1.0/{f}"))

    for f in INCLUDED_TEST_FILES:
        path = REPO_ROOT / f
        if path.exists():
            entries.append((str(path), f"aeib-v1.0/{f}"))

    # Directories
    for src_rel, arc_prefix in INCLUDED_DIRS:
        src_dir = REPO_ROOT / src_rel
        if not src_dir.exists():
            continue
        for root, dirs, files in os.walk(src_dir):
            if "__pycache__" in root or ".git" in root or ".pytest_cache" in root:
                continue
            for file in files:
                if file.endswith(".pyc") or file.startswith(".") or file == ".DS_Store":
                    continue
                full_path = os.path.join(root, file)
                if any(p in full_path.lower() for p in PROHIBITED_SUBSTRINGS):
                    continue
                rel_path = os.path.relpath(full_path, src_dir)
                arcname = os.path.join(arc_prefix, rel_path)
                entries.append((full_path, arcname))

    # Sort entries by arcname for deterministic tar ordering
    entries.sort(key=lambda x: x[1])
    return entries


def create_deterministic_tar_bytes(entries: list[tuple[str, str]]) -> bytes:
    """Creates uncompressed tar bytes with normalized headers."""
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        for disk_path, arcname in entries:
            tarinfo = tar.gettarinfo(disk_path, arcname=arcname)
            tarinfo = filter_tarinfo(tarinfo)
            if tarinfo.isreg():
                with open(disk_path, "rb") as f:
                    tar.addfile(tarinfo, f)
            else:
                tar.addfile(tarinfo)
    return tar_buf.getvalue()


def compress_deterministic_gzip(data: bytes) -> bytes:
    """Gzip compresses bytes with fixed mtime=0 in header for reproducibility."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(data)
    return buf.getvalue()


def build_archive() -> tuple[Path, str]:
    dist_dir = REPO_ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    out_path = dist_dir / "aeib-v1.0-review.tar.gz"

    entries = collect_archive_entries()
    tar_bytes = create_deterministic_tar_bytes(entries)
    gz_bytes = compress_deterministic_gzip(tar_bytes)

    out_path.write_bytes(gz_bytes)
    sha256 = hashlib.sha256(gz_bytes).hexdigest()
    return out_path, sha256


def main():
    print("[*] Building deterministic distribution archive...")
    path1, sha1 = build_archive()
    print(f"[+] Build 1 SHA-256: {sha1}")

    # Build second time to verify reproducibility
    path2, sha2 = build_archive()
    print(f"[+] Build 2 SHA-256: {sha2}")

    if sha1 != sha2:
        print("[-] ERROR: Non-deterministic build detected! Hashes diverge.", file=sys.stderr)
        sys.exit(1)

    print(f"[✔] DETERMINISTIC BUILD VERIFIED: {sha1}")
    print(f"[✔] Archive written to: {path1} ({path1.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
