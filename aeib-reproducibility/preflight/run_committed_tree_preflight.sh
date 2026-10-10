#!/usr/bin/env bash
# ==============================================================================
# AEIB v1.0.0-rc.1 Committed-Tree Local Developer Preflight Harness
#
# EPISTEMIC & SCOPE DISCLOSURES:
# 1. This script builds and extracts a committed-tree archive (`git archive
#    --format=tar.gz HEAD`) into an isolated temporary directory rather than
#    running against a dirty host-mounted working directory.
# 2. This is a LOCAL DEVELOPER PREFLIGHT, NOT an independent clean-room
#    reproduction (Gate 3) and NOT a substitute for hosted-CI success.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

COMMIT_SHA="$(git rev-parse HEAD)"
TIMESTAMP_UTC="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

WORK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/aeib-committed-preflight.XXXXXX")"
ARCHIVE_PATH="${WORK_ROOT}/aeib-head-${COMMIT_SHA:0:12}.tar.gz"
EXTRACT_DIR="${WORK_ROOT}/tree"
mkdir -p "${EXTRACT_DIR}"

cleanup() {
  rm -rf "${WORK_ROOT}"
}
trap cleanup EXIT

echo "=============================================================================="
echo "  AEIB v1.0.0-rc.1 COMMITTED-TREE LOCAL DEVELOPER PREFLIGHT"
echo "=============================================================================="
echo "[*] Scope Notice 1    : Uses a committed-tree archive (git archive --format=tar.gz HEAD),"
echo "                        NOT a dirty host-mounted working directory."
echo "[*] Scope Notice 2    : This is a local developer preflight, NOT a clean-room"
echo "                        reproduction and NOT a substitute for hosted-CI success."
echo "[*] Timestamp (UTC)   : ${TIMESTAMP_UTC}"
echo "[*] Source Repository : ${REPO_ROOT}"
echo "[*] HEAD Commit SHA   : ${COMMIT_SHA}"

echo ""
echo "[1/6] Creating committed-tree archive from HEAD via git archive..."
git archive --format=tar.gz --output="${ARCHIVE_PATH}" HEAD
ARCHIVE_SHA256="$(shasum -a 256 "${ARCHIVE_PATH}" | awk '{print $1}')"
ARCHIVE_BYTES="$(wc -c < "${ARCHIVE_PATH}" | tr -d ' ')"
echo "  Archive Path        : ${ARCHIVE_PATH}"
echo "  Archive Size        : ${ARCHIVE_BYTES} bytes"
echo "  Archive SHA-256     : ${ARCHIVE_SHA256}"

echo ""
echo "[2/6] Extracting committed-tree archive to isolated temporary directory..."
tar -xzf "${ARCHIVE_PATH}" -C "${EXTRACT_DIR}"
EXTRACTED_FILE_COUNT="$(find "${EXTRACT_DIR}" -type f | wc -l | tr -d ' ')"
echo "  Extracted Directory : ${EXTRACT_DIR}"
echo "  Extracted Files     : ${EXTRACTED_FILE_COUNT}"

echo ""
echo "[3/6] Verifying committed-tree Java sources, Gradle lockfiles, and spec presence..."
(
  cd "${EXTRACT_DIR}"
  test -f "AEIB-RECEIPT-SPEC.md"
  test -f "aeib-native-runtime/gradle.lockfile"
  test -f "aeib-native-runtime/aeib-core/gradle.lockfile"
  test -f "aeib-native-runtime/aeib-crypto/gradle.lockfile"
  test -f "aeib-native-runtime/aeib-runtime/gradle.lockfile"
  test -f "aeib-native-runtime/aeib-verifier/gradle.lockfile"
  test -f "aeib-native-runtime/aeib-tests/gradle.lockfile"
  test -f "aeib-native-runtime/aeib-verifier/src/test/resources/vectors/manifest.json"
  test -f "benchmarks/jvm_native_diff_engine.py"
  python3 - <<'PY'
import hashlib
from pathlib import Path

java_files = sorted(Path("aeib-native-runtime").rglob("*.java"))
print(f"  Verified {len(java_files)} committed Java compilation units and 6 Gradle lockfiles.")
h = hashlib.sha256()
for jf in java_files:
    h.update(jf.read_bytes())
print(f"  Aggregate Java source tree SHA-256: {h.hexdigest()}")
PY
)

echo ""
echo "[4/6] Staging pinned Gate 4 test-result artifacts for offline differential check..."
# Because build/ is gitignored in HEAD, populate build/test-results in the isolated
# extraction from the pinned hosted-CI evidence bundle (run 38055279949 for commit HEAD)
EVIDENCE_BUNDLE="${REPO_ROOT}/aeib-reproducibility/evidence/v1.0.0-rc.1"
mkdir -p "${EXTRACT_DIR}/aeib-native-runtime/build/test-results"
mkdir -p "${EXTRACT_DIR}/aeib-native-runtime/aeib-verifier/build/test-results/test"
mkdir -p "${EXTRACT_DIR}/aeib-native-runtime/aeib-tests/build/test-results/test"

if [ -f "${EVIDENCE_BUNDLE}/receipt.json" ]; then
  cp "${EVIDENCE_BUNDLE}/receipt.json" "${EXTRACT_DIR}/aeib-native-runtime/build/test-results/receipt.json"
  cp "${EVIDENCE_BUNDLE}/ledger-public.pem" "${EXTRACT_DIR}/aeib-native-runtime/build/test-results/ledger-public.pem"
  cp "${EVIDENCE_BUNDLE}/hosted-test-reports/TEST-com.aeib.verifier.VerifierCliTest.xml" \
     "${EXTRACT_DIR}/aeib-native-runtime/aeib-verifier/build/test-results/test/"
  cp "${EVIDENCE_BUNDLE}/hosted-test-reports/"*.xml \
     "${EXTRACT_DIR}/aeib-native-runtime/aeib-tests/build/test-results/test/"
  echo "  Staged Gate 4 artifacts from aeib-reproducibility/evidence/v1.0.0-rc.1 (CI run 38055279949)"
else
  cp "${REPO_ROOT}/aeib-native-runtime/build/test-results/receipt.json" \
     "${EXTRACT_DIR}/aeib-native-runtime/build/test-results/receipt.json"
  cp "${REPO_ROOT}/aeib-native-runtime/build/test-results/ledger-public.pem" \
     "${EXTRACT_DIR}/aeib-native-runtime/build/test-results/ledger-public.pem"
  cp "${REPO_ROOT}/aeib-native-runtime/aeib-verifier/build/test-results/test/TEST-com.aeib.verifier.VerifierCliTest.xml" \
     "${EXTRACT_DIR}/aeib-native-runtime/aeib-verifier/build/test-results/test/"
  cp "${REPO_ROOT}/aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Gate4IntegrationTest.xml" \
     "${EXTRACT_DIR}/aeib-native-runtime/aeib-tests/build/test-results/test/"
  echo "  Staged Gate 4 artifacts from local build/test-results"
fi

echo ""
echo "[5/6] Running Cross-Language Differential Parity Engine inside extracted committed tree..."
(
  cd "${EXTRACT_DIR}"
  python3 benchmarks/jvm_native_diff_engine.py
)

echo ""
echo "[6/6] Asserting valid (exit 0) and tampered (exit 2) receipt verification inside extracted tree..."
(
  cd "${EXTRACT_DIR}"
  python3 - <<'PY'
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from benchmarks.jvm_native_diff_engine import verify_receipt_target_b

receipt_path = Path("aeib-native-runtime/build/test-results/receipt.json")
pubkey_path = Path("aeib-native-runtime/build/test-results/ledger-public.pem")
tampered_sig_path = Path("aeib-native-runtime/aeib-verifier/src/test/resources/vectors/tampered-signature/receipt.json")
tampered_sig_pub = Path("aeib-native-runtime/aeib-verifier/src/test/resources/vectors/tampered-signature/public.pem")
tampered_stmt_path = Path("aeib-native-runtime/aeib-verifier/src/test/resources/vectors/tampered-statement/receipt.json")
tampered_stmt_pub = Path("aeib-native-runtime/aeib-verifier/src/test/resources/vectors/tampered-statement/public.pem")

r_sha = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
k_sha = hashlib.sha256(pubkey_path.read_bytes()).hexdigest()
print(f"  Receipt SHA-256    : {r_sha}")
print(f"  Public Key SHA-256 : {k_sha}")

out_valid = verify_receipt_target_b(receipt_path, pubkey_path)
assert out_valid.exit_code == 0, f"Expected exit_code 0 for valid receipt, got {out_valid.exit_code}"
print(f"  Valid receipt check    : {out_valid.verdict} (exit_code={out_valid.exit_code})")

out_tampered_sig = verify_receipt_target_b(tampered_sig_path, tampered_sig_pub)
assert out_tampered_sig.exit_code == 2, f"Expected exit_code 2 for tampered-signature, got {out_tampered_sig.exit_code}"
print(f"  Tampered sig check     : {out_tampered_sig.verdict} (exit_code={out_tampered_sig.exit_code})")

out_tampered_stmt = verify_receipt_target_b(tampered_stmt_path, tampered_stmt_pub)
assert out_tampered_stmt.exit_code == 2, f"Expected exit_code 2 for tampered-statement, got {out_tampered_stmt.exit_code}"
print(f"  Tampered stmt check    : {out_tampered_stmt.verdict} (exit_code={out_tampered_stmt.exit_code})")
PY
)

echo ""
echo "=============================================================================="
echo "  COMMITTED-TREE LOCAL DEVELOPER PREFLIGHT PASSED"
echo "  HEAD Commit SHA : ${COMMIT_SHA}"
echo "  Archive SHA-256 : ${ARCHIVE_SHA256}"
echo "=============================================================================="
