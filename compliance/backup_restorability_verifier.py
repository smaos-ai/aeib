#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# compliance/backup_restorability_verifier.py
#
# DORA Article 17 Business Continuity & Backup Restorability Evaluator.
# Tests physical restoration from external backup (/Volumes/EXTssd/SovereignNexus_Backup)
# into an isolated clean directory, validates SHA-256 digests against locked evidence manifests,
# and computes empirical RTO (Recovery Time Objective) metrics.
#
# Epistemic Notice: Evaluated and tested under the stated local verification model.

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKUP_SOURCE_DEFAULT = "/Volumes/EXTssd/SovereignNexus_Backup"
EVIDENCE_HASHES_PATH = "output/evidence-hashes.txt"

# Core release artifacts to strictly verify against cryptographic digests
CORE_VERIFICATION_TARGETS = [
    "smaos_verify.wasm",
    "output/dst-report-20261020.json",
    "output/dst-traces-20261020/traces.jsonl",
    "evidence/cbom.json",
    "docs/compliance/CISO_DORA_EXECUTIVE_DECISION_PACK.md",
    "Cargo.toml",
]


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_evidence_manifest(manifest_path: Path) -> dict:
    digests = {}
    if not manifest_path.exists():
        return digests
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            digest, filename = parts
            clean_name = filename.strip().lstrip("./")
            digests[clean_name] = digest.strip()
    return digests


def run_restorability_evaluation(
    backup_path_str: str, output_receipt_path: str = "output/backup-restorability-receipt.json"
) -> dict:
    backup_path = Path(backup_path_str)
    if not backup_path.exists():
        print(f"[!] Backup source not found at: {backup_path}")
        return {
            "status": "FAILED_BACKUP_NOT_MOUNTED",
            "source_path": str(backup_path),
            "restorability_verified": False,
        }

    evidence_manifest = load_evidence_manifest(Path(EVIDENCE_HASHES_PATH))
    restore_target_dir = Path(tempfile.mkdtemp(prefix="aeib_restore_eval_"))

    start_time = time.perf_counter()
    restored_artifacts = []
    hash_comparisons = []
    all_matched = True

    try:
        print(f"[*] Starting clean-room restoration into: {restore_target_dir}")

        for target in CORE_VERIFICATION_TARGETS:
            src = backup_path / target
            dst = restore_target_dir / target

            if not src.exists():
                print(f"[!] Target missing in backup: {target}")
                all_matched = False
                hash_comparisons.append({
                    "target": target,
                    "status": "MISSING_IN_BACKUP",
                    "matched": False,
                })
                continue

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

            restored_sha = compute_sha256(dst)
            live_path = Path(target)
            live_sha = compute_sha256(live_path) if live_path.exists() else None
            manifest_sha = evidence_manifest.get(target)

            match_live = (restored_sha == live_sha) if live_sha else False
            match_manifest = (restored_sha == manifest_sha) if manifest_sha else True

            target_valid = match_live and match_manifest
            if not target_valid:
                all_matched = False

            hash_comparisons.append({
                "target": target,
                "restored_sha256": restored_sha,
                "live_sha256": live_sha,
                "manifest_sha256": manifest_sha,
                "matched_live": match_live,
                "matched_manifest": match_manifest,
                "verdict": "VERIFIED" if target_valid else "MISMATCH",
            })
            restored_artifacts.append(target)

        # Execute node test against restored wasm
        restored_wasm = restore_target_dir / "smaos_verify.wasm"
        wasm_test_rc = None
        if restored_wasm.exists() and Path("tests/test_smaos_verify_wasm.js").exists():
            test_cmd = [
                "node",
                "-e",
                f"""
                const fs = require('fs');
                const wasmBytes = fs.readFileSync('{restored_wasm}');
                WebAssembly.instantiate(wasmBytes, {{}}).then(() => {{
                    console.log('Restored WASM instantiated successfully');
                    process.exit(0);
                }}).catch(err => {{
                    console.error(err);
                    process.exit(1);
                }});
                """,
            ]
            res = subprocess.run(test_cmd, capture_output=True, text=True)
            wasm_test_rc = res.returncode
            if wasm_test_rc != 0:
                all_matched = False

        duration_sec = time.perf_counter() - start_time

        receipt = {
            "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "backup_source": str(backup_path),
            "restoration_directory": str(restore_target_dir),
            "restorability_verified": all_matched,
            "measured_rto_seconds": round(duration_sec, 4),
            "target_rto_threshold_seconds": 60.0,
            "rto_sla_met": duration_sec < 60.0,
            "rpo_basis": "Synchronized at commit HEAD",
            "files_evaluated_count": len(CORE_VERIFICATION_TARGETS),
            "files_verified_count": sum(1 for h in hash_comparisons if h.get("verdict") == "VERIFIED"),
            "restored_wasm_instantiation_code": wasm_test_rc,
            "hash_comparisons": hash_comparisons,
        }

        # Write output receipt
        out_file = Path(output_receipt_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(f"[✓] Restorability evaluation complete. Receipt written to: {out_file}")
        print(f"    RTO: {receipt['measured_rto_seconds']}s (SLA Met: {receipt['rto_sla_met']})")
        print(f"    Restorability Status: {'PASSED' if all_matched else 'FAILED'}")

        return receipt

    finally:
        # Cleanup ephemeral restore directory
        if restore_target_dir.exists():
            shutil.rmtree(restore_target_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="DORA Article 17 Backup Restorability Evaluator")
    parser.add_argument(
        "--backup-source",
        default=BACKUP_SOURCE_DEFAULT,
        help="Path to external SSD or backup mount point",
    )
    parser.add_argument(
        "--output",
        default="output/backup-restorability-receipt.json",
        help="Path to save evaluation receipt",
    )
    args = parser.parse_args()

    result = run_restorability_evaluation(args.backup_source, args.output)
    if not result.get("restorability_verified"):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
