#!/usr/bin/env bash
set -euo pipefail

VERSION="v1.0.0-rc.5-preprod"
DIST_NAME="aeib-${VERSION}-airgapped"
STAGE_DIR="/tmp/${DIST_NAME}"
CLEANROOM_DIR="/tmp/aeib-cleanroom"
TARBALL="${DIST_NAME}.tar.gz"

echo "=== [1/4] Staging frozen 3-Station / 7-Component tree into ${STAGE_DIR} ==="
rm -rf "${STAGE_DIR}" "${CLEANROOM_DIR}"
mkdir -p "${STAGE_DIR}/tools" "${STAGE_DIR}/tests" "${STAGE_DIR}/scripts" "${STAGE_DIR}/src" "${STAGE_DIR}/compliance" "${STAGE_DIR}/benchmarks" "${STAGE_DIR}/output"

cp SCOPE.md "${STAGE_DIR}/"
cp EVIDENCE_MANIFEST.md "${STAGE_DIR}/"
cp tools/phase0_integrity_reset_core.py "${STAGE_DIR}/tools/"
cp tools/standalone_offline_verifier.py "${STAGE_DIR}/tools/"
cp tests/test_scitt_ap2_mcp_pqc_interop.py "${STAGE_DIR}/tests/"
cp tests/test_structural_cve_boundary_fixtures.py "${STAGE_DIR}/tests/"
cp tests/test_global_dominance_g1_g2_g3.py "${STAGE_DIR}/tests/"
cp tests/test_epistemic_regression_e01_e14.py "${STAGE_DIR}/tests/"
cp src/jcs_canonicalizer.py "${STAGE_DIR}/src/"
cp src/transactional_storage_backend.py "${STAGE_DIR}/src/"
cp src/sovereign_nexus_mcp_gateway.py "${STAGE_DIR}/src/"
cp src/decide_evaluation_rate_and_decay_solver.py "${STAGE_DIR}/src/"
cp src/decide_autonomous_query_research_engine.py "${STAGE_DIR}/src/"
cp src/en18286_dora_audit_bundler.py "${STAGE_DIR}/src/"
cp benchmarks/public_sota_adapter.py "${STAGE_DIR}/benchmarks/"
cp output/public_sota_benchmark_report.json "${STAGE_DIR}/output/"
cp output/en18286_dora_compliance_bundle_v45.json "${STAGE_DIR}/output/"
cp compliance/check_zone_boundary.py "${STAGE_DIR}/compliance/"
cp compliance/ast_purity.py "${STAGE_DIR}/compliance/"
cp compliance/no_mock_enforcer.py "${STAGE_DIR}/compliance/"

echo "=== [2/4] Enforcing Epistemic & Zero-Mock Gate ==="
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py "${STAGE_DIR}"
python3 compliance/no_mock_enforcer.py

echo "=== [3/4] Building Deterministic Tarball & SHA-256 Digest ==="
python3 - "${STAGE_DIR}" "${TARBALL}" "${DIST_NAME}" <<'PYEOF'
import gzip
import hashlib
import io
import os
import sys
import tarfile

stage_dir, tarball_path, dist_name = sys.argv[1], sys.argv[2], sys.argv[3]
FIXED_MTIME = 1761091200  # 2025-10-22T00:00:00Z deterministic epoch

rel_paths = []
for root, dirs, files in os.walk(stage_dir):
    dirs.sort()
    for f in sorted(files):
        full = os.path.join(root, f)
        rel = os.path.relpath(full, stage_dir)
        rel_paths.append((rel, full))
rel_paths.sort(key=lambda item: item[0])

tar_buf = io.BytesIO()
with tarfile.open(fileobj=tar_buf, mode="w") as tf:
    for rel, full in rel_paths:
        arcname = f"{dist_name}/{rel}"
        with open(full, "rb") as fh:
            data = fh.read()
        info = tarfile.TarInfo(name=arcname)
        info.size = len(data)
        info.mtime = FIXED_MTIME
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mode = 0o755 if full.endswith(".sh") or full.endswith(".py") else 0o644
        tf.addfile(info, io.BytesIO(data))

raw_tar = tar_buf.getvalue()
with open(tarball_path, "wb") as out_f:
    with gzip.GzipFile(filename="", mode="wb", fileobj=out_f, mtime=FIXED_MTIME) as gz:
        gz.write(raw_tar)

digest = hashlib.sha256( open(tarball_path, "rb").read() ).hexdigest()
with open(f"{tarball_path}.sha256", "w", encoding="utf-8") as sf:
    sf.write(f"{digest}  {tarball_path}\n")
print(f"Built {tarball_path} -> SHA-256: {digest}")
PYEOF

echo "=== [4/4] Clean-Room Air-Gapped Extraction & Verification ==="
mkdir -p "${CLEANROOM_DIR}"
cp "${TARBALL}" "${TARBALL}.sha256" "${CLEANROOM_DIR}/"
(
  cd "${CLEANROOM_DIR}"
  shasum -a 256 -c "${TARBALL}.sha256"
  tar -xzf "${TARBALL}"
  cd "${DIST_NAME}"
  PYTHONPATH=. python3 tools/phase0_integrity_reset_core.py
  PYTHONPATH=. pytest tools/phase0_integrity_reset_core.py \
         tests/test_scitt_ap2_mcp_pqc_interop.py \
         tests/test_structural_cve_boundary_fixtures.py \
         tests/test_global_dominance_g1_g2_g3.py -v
)

echo "=== AIR-GAPPED RELEASE ${TARBALL} VERIFIED ==="
