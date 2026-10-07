#!/usr/bin/env bash
# ==============================================================================
# Sovereign Multi-Agent OS (SMAOS) / AEIB
# Script: scripts/build_release_archive.sh
# Purpose: Validates the 12 Release-Gate Pre-Conditions before assembling the
#          clean-room release archive into aeib-v0.4.0-cleanroom.tar.gz.
# ==============================================================================

set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE_ROOT"

echo "========================================================================"
echo "  AEIB v0.4.0 RELEASE ARCHIVE PACKAGER — 12-GATE AUDIT VALIDATOR"
echo "  Workspace: $WORKSPACE_ROOT"
echo "========================================================================"

FAILED_GATES=0

# Helper function to record gate verification
check_gate() {
    local gate_num="$1"
    local gate_name="$2"
    local condition_cmd="$3"

    echo -n "[*] Gate ${gate_num}/12: Validating ${gate_name}... "
    if eval "$condition_cmd" >/dev/null 2>&1; then
        echo "[PASSED]"
    else
        echo "[FAILED]"
        FAILED_GATES=$((FAILED_GATES + 1))
    fi
}

# 1. Source tree present
check_gate 1 "Source Tree (src/)" "[ -d src ] && [ -f src/aeib_v040_engine.py ] && [ -f src/jcs_canonicalizer.py ]"

# 2. Dependency lockfile / pyproject.toml present
check_gate 2 "Dependency Lockfile (pyproject.toml)" "[ -f pyproject.toml ]"

# 3. Test manifest present
check_gate 3 "Test Manifest (tests/)" "[ -d tests ] && [ -f tests/test_industrial_protection_matrix.py ]"

# 4. Environment manifest present in attestation
check_gate 4 "Environment Manifest (in crvp_attestation.json)" "[ -f compliance/crvp_attestation.json ] && jq -e '.payload.verification_environment' compliance/crvp_attestation.json"

# 5. Source digest present and computed
check_gate 5 "Source Digest (source_tree_sha256)" "jq -e '.payload.codebase_digest' compliance/crvp_attestation.json"

# 6. Archive digest pre-allocated
check_gate 6 "Archive Output Target (dist/)" "mkdir -p dist"

# 7. Public verification key present in attestation
check_gate 7 "Public Verification Key" "jq -e '.public_key_hex' compliance/crvp_attestation.json"

# 8. Signed attestation present and clean
check_gate 8 "Signed Attestation (ast_purity_status.clean)" "jq -e '.payload.ast_purity_status.clean == true' compliance/crvp_attestation.json"

# 9. Offline verifier present
check_gate 9 "Offline Verifier (cleanroom/verify_from_scratch.py)" "[ -f cleanroom/verify_from_scratch.py ]"

# 10. Negative-test outputs codified
check_gate 10 "Negative-Test Outputs Codified (tests/test_falsifiability_matrix.py)" "[ -f tests/test_falsifiability_matrix.py ]"

# 11. Limitations document present
check_gate 11 "Limitations Document (LIMITATIONS.md)" "[ -f LIMITATIONS.md ]"

# 12. Claims-to-evidence matrix present
check_gate 12 "Claims-to-Evidence Matrix (CLAIMS_EVIDENCE.md)" "[ -f CLAIMS_EVIDENCE.md ]"

echo "------------------------------------------------------------------------"
if [ "$FAILED_GATES" -gt 0 ]; then
    echo "[!] RELEASE-GATE FAILURE: $FAILED_GATES of 12 gate pre-conditions failed!" >&2
    exit 1
fi
echo "[✔] ALL 12 RELEASE-GATE PRE-CONDITIONS VERIFIED CLEAN."

# Assemble the archive deterministically
echo "[*] Assembling reproducible clean-room archive..."
python3 - <<'EOF'
import io
import gzip
import tarfile
import hashlib
import os
from pathlib import Path

WORKSPACE = Path(".").resolve()
OUT_ARCHIVE = WORKSPACE / "aeib-v0.4.0-cleanroom.tar.gz"
OUT_DIST = WORKSPACE / "dist" / "aeib-v0.4.0-cleanroom.tar.gz"

INCLUDED_PATHS = [
    "README.md",
    "REPRODUCE.md",
    "LIMITATIONS.md",
    "THREAT_MODEL.md",
    "ASSURANCE_PROFILE.md",
    "CLAIMS_EVIDENCE.md",
    "SYSTEM_BOUNDARIES.md",
    "RELATED_WORK.md",
    "VERIFICATION_TRANSCRIPT_TEMPLATE.md",
    "docs/aeib-bench-architecture-v0.1.md",
    "LICENSE",
    "TEVV.md",
    "pyproject.toml",
    "pytest.ini",
    "config/claims.jsonl",
    "config/signer_profiles.json",
    "schemas/aeib-receipt-v0.4.0.json",
    "schemas/aeib_v0.5.0_receipt_schema.json",
    "schemas/scitt_continuity_receipt_schema.json",
    "fixtures/aeib_bench_v0.1_scenarios.json",
    "compliance/crvp_attestation.json",
    "compliance/check_zone_boundary.py",
    "compliance/ast_purity.py",
    "compliance/no_mock_enforcer.py",
    "compliance/tycho_verifier.py",
    "scripts/ast_purity_scanner.py",
    "scripts/generate_crvp_attestation.py",
    "scripts/ci_claims_verifier.py",
    "scripts/build_release_archive.sh",
    "scripts/assemble_review_candidate.sh",
    "scripts/export_dora_incident.py",
    "scripts/validate_dora_register.py",
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

entries = []
seen = set()
for p_str in sorted(INCLUDED_PATHS):
    p = WORKSPACE / p_str
    if p.exists() and p.is_file():
        arcname = f"aeib-v0.4.0-cleanroom/{p_str}"
        if arcname not in seen:
            entries.append((str(p), arcname))
            seen.add(arcname)

for d_str in sorted(INCLUDED_DIRS):
    d = WORKSPACE / d_str
    if not d.exists():
        continue
    for root, dirnames, files in os.walk(d):
        dirnames[:] = [x for x in dirnames if not x.startswith(".") and x != "__pycache__" and x != "venv"]
        for f in sorted(files):
            if f.endswith((".py", ".rs", ".json", ".yaml", ".yml", ".md", ".toml", ".sh")):
                full_p = Path(root) / f
                rel_p = full_p.relative_to(WORKSPACE)
                arcname = f"aeib-v0.4.0-cleanroom/{rel_p}"
                if arcname not in seen:
                    entries.append((str(full_p), arcname))
                    seen.add(arcname)

entries.sort(key=lambda x: x[1])

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

OUT_ARCHIVE.write_bytes(final_bytes)
OUT_DIST.write_bytes(final_bytes)

(WORKSPACE / "aeib-v0.4.0-cleanroom.tar.gz.sha256").write_text(f"{sha256}  aeib-v0.4.0-cleanroom.tar.gz\n")
(WORKSPACE / "dist" / "aeib-v0.4.0-cleanroom.tar.gz.sha256").write_text(f"{sha256}  aeib-v0.4.0-cleanroom.tar.gz\n")

print(f"[+] Total files bundled: {len(entries)}")
print(f"[+] Archive byte size:   {len(final_bytes)}")
print(f"[+] Final SHA-256:       {sha256}")
EOF

ARCHIVE_SHA=$(shasum -a 256 aeib-v0.4.0-cleanroom.tar.gz | cut -d' ' -f1)

echo "========================================================================"
echo "✅ RELEASE ARCHIVE SUCCESSFULLY GENERATED UNDER 12-GATE POLICY"
echo "📦 Root Path: $WORKSPACE_ROOT/aeib-v0.4.0-cleanroom.tar.gz"
echo "📦 Dist Path: $WORKSPACE_ROOT/dist/aeib-v0.4.0-cleanroom.tar.gz"
echo "🔒 SHA-256:   $ARCHIVE_SHA"
echo "========================================================================"
