#!/usr/bin/env bash
# ==============================================================================
# Sovereign Multi-Agent OS (SMAOS) / AEIB
# Script: scripts/assemble_review_candidate.sh
# Purpose: Assembles the verified AEIB v0.4.0 Review Candidate distribution
#          archive into aeib-v0.4.0-review-candidate.tar.gz with deterministic
#          bit-for-bit reproducibility.
# ==============================================================================

set -euo pipefail

# 1. Resolve Workspace Root (supports /workspace/scratch or local repository root)
if [ -d "/workspace/scratch" ] && [ -f "/workspace/scratch/README.md" ]; then
    WORKSPACE_ROOT="/workspace/scratch"
elif [ -n "${REPO_ROOT:-}" ] && [ -d "$REPO_ROOT" ]; then
    WORKSPACE_ROOT="$REPO_ROOT"
else
    WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$WORKSPACE_ROOT"

echo "========================================================================"
echo "  AEIB v0.4.0 REVIEW CANDIDATE ARCHIVE PACKAGER"
echo "  Target Root: $WORKSPACE_ROOT"
echo "========================================================================"

# 2. Pre-Flight Verification Gates
echo "[*] Gate 1: Enforcing AST purity across codebase..."
if python3 scripts/ast_purity_scanner.py; then
    echo "    [✓] AST Purity verified: Zero mock modules, test doubles, or bypass gates."
else
    echo "    [✗] Gate 1 failed: Mock purity violation detected!" >&2
    exit 1
fi

echo "[*] Gate 2: Checking CRVP Attestation status..."
if [ ! -f "compliance/crvp_attestation.json" ]; then
    echo "    [*] Attestation missing, generating signed manifest..."
    python3 scripts/generate_crvp_attestation.py
fi

if jq -r '.ast_purity_status.clean' compliance/crvp_attestation.json | grep -q "true"; then
    echo "    [✓] CRVP Attestation confirmed clean."
else
    echo "    [✗] Gate 2 failed: Attestation indicates dirty state!" >&2
    exit 1
fi

echo "[*] Gate 3: Verifying Zone Boundary purity..."
if python3 compliance/check_zone_boundary.py; then
    echo "    [✓] Zone Boundary integrity confirmed (0 Zone 1 -> Zone 2 imports)."
else
    echo "    [✗] Gate 3 failed: Zone boundary violation!" >&2
    exit 1
fi

echo "[*] Gate 4: Running core verification test matrix..."
if pytest tests/test_industrial_protection_matrix.py \
          tests/test_ansi_50bf_breaker_failure.py \
          tests/test_saga_compensation.py \
          tests/test_falsifiability_matrix.py \
          tests/test_mcp_acceptance_criteria.py -q; then
    echo "    [✓] Core protection, falsifiability, and MCP test matrix passed."
else
    echo "    [✗] Gate 4 failed: Test suite regression detected!" >&2
    exit 1
fi

# 3. Assemble Distribution Archive Deterministically via Python Embed
echo "[*] Assembling reproducible aeib-v0.4.0-review-candidate.tar.gz archive..."
mkdir -p dist audit_out

python3 - <<'EOF'
import os
import sys
import io
import gzip
import tarfile
import hashlib
from pathlib import Path

WORKSPACE = Path(".").resolve()
OUT_ROOT = WORKSPACE / "aeib-v0.4.0-review-candidate.tar.gz"
OUT_DIST = WORKSPACE / "dist" / "aeib-v0.4.0-review-candidate.tar.gz"

INCLUDED_PATHS = [
    "README.md",
    "LICENSE",
    "REPRODUCE.md",
    "LIMITATIONS.md",
    "THREAT_MODEL.md",
    "ASSURANCE_PROFILE.md",
    "CLAIMS_EVIDENCE.md",
    "TEVV.md",
    "FOR_REVIEWERS.md",
    "SYSTEM_BOUNDARIES.md",
    "RELATED_WORK.md",
    "VERIFICATION_TRANSCRIPT_TEMPLATE.md",
    "pyproject.toml",
    "pytest.ini",
    "config/claims.jsonl",
    "config/signer_profiles.json",
    "schemas/aeib-receipt-v0.4.0.json",
    "schemas/aeib_v0.5.0_receipt_schema.json",
    "schemas/scitt_continuity_receipt_schema.json",
    "compliance/crvp_attestation.json",
    "compliance/check_zone_boundary.py",
    "compliance/ast_purity.py",
    "compliance/no_mock_enforcer.py",
    "compliance/tycho_verifier.py",
    "scripts/ast_purity_scanner.py",
    "scripts/generate_crvp_attestation.py",
    "scripts/ci_claims_verifier.py",
    "cleanroom/Dockerfile",
    "cleanroom/verify_from_scratch.py",
    "cleanroom/tcp_chaos_server.py",
    "verifier/verify_attestation.py",
    "ebpf/aeib_sock_filter.c",
]

INCLUDED_DIRS = [
    "src",
    "tests",
    "benchmarks/aeib_execution_integrity",
    "aei_core",
    "compliance",
    "schemas",
]

FIXED_MTIME = 1791331200  # 2026-10-07 00:00:00 UTC

def filter_tarinfo(tarinfo):
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    tarinfo.mtime = FIXED_MTIME
    tarinfo.mode = 0o644 if tarinfo.isreg() else 0o755
    return tarinfo

def collect_entries():
    entries = []
    seen = set()
    # Add files
    for rel_path in sorted(INCLUDED_PATHS):
        p = WORKSPACE / rel_path
        if p.exists() and p.is_file():
            arcname = f"aeib-v0.4.0-review-candidate/{rel_path}"
            if arcname not in seen:
                entries.append((str(p), arcname))
                seen.add(arcname)

    # Add directories
    for dir_rel in sorted(INCLUDED_DIRS):
        d = WORKSPACE / dir_rel
        if not d.exists():
            continue
        for root, dirnames, files in os.walk(d):
            dirnames[:] = [x for x in dirnames if not x.startswith(".") and x != "__pycache__" and x != "venv"]
            for f in sorted(files):
                if f.endswith((".py", ".json", ".yaml", ".yml", ".md", ".toml", ".sh")):
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(WORKSPACE)
                    arcname = f"aeib-v0.4.0-review-candidate/{rel_p}"
                    if arcname not in seen:
                        entries.append((str(full_p), arcname))
                        seen.add(arcname)

    entries.sort(key=lambda x: x[1])
    return entries

entries = collect_entries()

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

tar_bytes = tar_buf.getvalue()

gz_buf = io.BytesIO()
with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buf, mtime=0) as gz:
    gz.write(tar_bytes)

final_bytes = gz_buf.getvalue()
sha256 = hashlib.sha256(final_bytes).hexdigest()

OUT_ROOT.write_bytes(final_bytes)
OUT_DIST.write_bytes(final_bytes)

(WORKSPACE / "aeib-v0.4.0-review-candidate.tar.gz.sha256").write_text(f"{sha256}  aeib-v0.4.0-review-candidate.tar.gz\n")
(WORKSPACE / "dist" / "aeib-v0.4.0-review-candidate.tar.gz.sha256").write_text(f"{sha256}  aeib-v0.4.0-review-candidate.tar.gz\n")

print(f"[+] Total files bundled: {len(entries)}")
print(f"[+] Archive size:        {len(final_bytes)} bytes")
print(f"[+] SHA-256 Digest:      {sha256}")
EOF

# 4. Verification Check
CANDIDATE_HASH=$(shasum -a 256 aeib-v0.4.0-review-candidate.tar.gz | cut -d' ' -f1)

echo "========================================================================"
echo "✅ AEIB v0.4.0 REVIEW CANDIDATE ARCHIVE SUCCESSFULLY ASSEMBLED"
echo "📦 Archive Path: $WORKSPACE_ROOT/aeib-v0.4.0-review-candidate.tar.gz"
echo "📦 Dist Path:    $WORKSPACE_ROOT/dist/aeib-v0.4.0-review-candidate.tar.gz"
echo "🔒 SHA-256:      $CANDIDATE_HASH"
echo "========================================================================"
echo "[*] Verification complete. Review candidate is ready for peer dispatch."
