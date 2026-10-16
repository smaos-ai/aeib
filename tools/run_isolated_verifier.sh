#!/usr/bin/env bash
# tools/run_isolated_verifier.sh
# ==============================================================================
# Strict isolated command executor for aeib-verifier subagents.
# Enforces command allowlist and prevents arbitrary shell execution.
# Preserves strict epistemic lock and zero-egress purity.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CMD="${1:-help}"
shift || true

ISOLATED_TMP="${WORKTREE_PATH:-/tmp}/aeib_isolated_tmp_$$"
mkdir -p "${ISOLATED_TMP}"

cleanup() {
    rm -rf "${ISOLATED_TMP}"
}
trap cleanup EXIT

case "${CMD}" in
    zone_boundary)
        echo "[*] Running Zone Boundary Check..."
        python3 compliance/check_zone_boundary.py
        ;;
    ast_purity)
        echo "[*] Running AST Purity and No-Mock Checks..."
        python3 compliance/ast_purity.py .
        python3 compliance/no_mock_enforcer.py
        ;;
    phase2_evidence)
        echo "[*] Verifying Phase 2 Evidence..."
        python3 tools/verify_phase2_evidence.py --all
        ;;
    phase3_evidence)
        echo "[*] Verifying Phase 3 Evidence..."
        python3 tools/verify_phase3_evidence.py --all
        ;;
    pack)
        echo "[*] Verifying Evidence Pack..."
        python3 dist/aeib-pilot-evidence-pack-v1.1.0/verifiers/verify_pack.py
        ;;
    pytest)
        echo "[*] Running Scoped Pytest under ${ISOLATED_TMP}..."
        pytest --basetemp="${ISOLATED_TMP}/pytest_tmp" "$@"
        ;;
    5arm_benchmark)
        echo "[*] Running 5-Arm Benchmark Invariants..."
        pytest benchmarks/aeib_execution_integrity/test_episodes.py --basetemp="${ISOLATED_TMP}/pytest_tmp" -v
        ;;
    help|--help|-h)
        echo "Usage: tools/run_isolated_verifier.sh <command> [args...]"
        echo "Allowed commands: zone_boundary | ast_purity | phase2_evidence | phase3_evidence | pack | pytest | 5arm_benchmark"
        exit 0
        ;;
    *)
        echo "[!] ERROR: Command '${CMD}' is not in the aeib-verifier allowlist." >&2
        echo "    Allowed commands: zone_boundary | ast_purity | phase2_evidence | phase3_evidence | pack | pytest | 5arm_benchmark" >&2
        exit 2
        ;;
esac
