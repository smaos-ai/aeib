#!/usr/bin/env bash
# Real-TLC gate for formal/tlaplus/AEIBStation1And2.tla. Fails closed. No network access.
#
#   A5 model (fence enabled): TLC must finish with "No error has been found" and the distinct-state
#       count must equal the count produced by src/eo1_protocol_model_checker.py (34047).
#   A4 model (negative control, no fence): TLC must report a violation of SafetyNoDuplicateEffect.
#       If TLC does NOT find it, the model or the invariants are not exercising late commits.
#
# Exit codes: 0 pass | 1 gate failure | 2 prerequisite missing (jar absent / digest mismatch / no java)
# A missing jar is never reported as a pass: run scripts/fetch_tla2tools.sh first.
set -uo pipefail

EXPECTED_SHA256="78f7e2c6bf9a8b65eda665a23e94431255587e0b43a834a4e2af1723562d9b4a"
EXPECTED_A5_DISTINCT_STATES=34047   # equals the Python checker's A5_FENCED state count
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JAR="${ROOT}/formal/bin/tla2tools.jar"
SPEC_DIR="${ROOT}/formal/tlaplus"
JAVA_BIN="${JAVA_BIN:-$(command -v java || true)}"
[ -z "$JAVA_BIN" ] && [ -x "${HOME}/.sdkman/candidates/java/current/bin/java" ] && JAVA_BIN="${HOME}/.sdkman/candidates/java/current/bin/java"

if [ -z "$JAVA_BIN" ]; then echo "[PREREQ] java not found" >&2; exit 2; fi
if [ ! -f "$JAR" ]; then echo "[PREREQ] ${JAR} missing; run scripts/fetch_tla2tools.sh" >&2; exit 2; fi
ACTUAL="$(shasum -a 256 "$JAR" | awk '{print $1}')"
if [ "$ACTUAL" != "$EXPECTED_SHA256" ]; then
    echo "[PREREQ] tla2tools.jar digest mismatch: ${ACTUAL}" >&2; exit 2
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/tlc_gate.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
run_tlc() {  # $1 = model tag, $2 = cfg
    ( cd "$SPEC_DIR" && "$JAVA_BIN" -XX:+UseParallelGC -cp "$JAR" tlc2.TLC -workers 1 \
        -metadir "${WORK}/$1" -config "$2" AEIBStation1And2.tla > "${WORK}/$1.out" 2>&1 )
    return $?
}

FAIL=0
run_tlc a5 AEIBStation1And2_A5.cfg; RC5=$?
DISTINCT5="$(grep -Eo '[0-9]+ distinct states found' "${WORK}/a5.out" | awk '{print $1}' | tail -n 1)"
if [ "$RC5" -eq 0 ] && grep -q "No error has been found" "${WORK}/a5.out" \
   && [ "${DISTINCT5:-}" = "$EXPECTED_A5_DISTINCT_STATES" ]; then
    echo "[PASS] A5 (fenced): no error, ${DISTINCT5} distinct states"
else
    echo "[FAIL] A5 (fenced): rc=${RC5} distinct=${DISTINCT5:-none} (expected ${EXPECTED_A5_DISTINCT_STATES})" >&2
    tail -n 15 "${WORK}/a5.out" >&2; FAIL=1
fi

run_tlc a4 AEIBStation1And2_A4.cfg; RC4=$?
if [ "$RC4" -ne 0 ] && grep -q "Invariant SafetyNoDuplicateEffect is violated" "${WORK}/a4.out"; then
    STEPS="$(grep -Ec '^State [0-9]+:' "${WORK}/a4.out")"
    echo "[PASS] A4 negative control: SafetyNoDuplicateEffect violated as expected (${STEPS}-state trace)"
else
    echo "[FAIL] A4 negative control: TLC did not report the expected violation (rc=${RC4})" >&2
    tail -n 15 "${WORK}/a4.out" >&2; FAIL=1
fi
exit "$FAIL"
