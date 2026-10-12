#!/usr/bin/env bash
set -euo pipefail

echo "================================================================================"
echo "[1/5] Verifying Gradle 8.5 Wrapper JAR SHA-256..."
echo "================================================================================"
echo "d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd  gradle/wrapper/gradle-wrapper.jar" | sha256sum -c -
echo "d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd  aeib-native-runtime/gradle/wrapper/gradle-wrapper.jar" | sha256sum -c -

echo "================================================================================"
echo "[2/6] Running Clean Build, JUnit Test Suite, installDist, CycloneDX 1.6 SBOM & generateSlsaSubjects (Strict Dependency Verification)..."
echo "================================================================================"
./gradlew clean check :aeib-verifier:installDist cyclonedxBom generateSlsaSubjects --dependency-verification strict --no-daemon --info

echo "================================================================================"
echo "[3/6] Running Reproducible Build-Twice-and-Diff Check (Action 19)..."
echo "================================================================================"
SHA1=$(sha256sum aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.1.jar | awk '{print $1}')
./gradlew :aeib-verifier:jar --dependency-verification strict --rerun-tasks --no-daemon
SHA2=$(sha256sum aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.1.jar | awk '{print $1}')
echo "Build 1 JAR SHA-256: $SHA1"
echo "Build 2 JAR SHA-256: $SHA2"
if [ "$SHA1" != "$SHA2" ]; then
  echo "ERROR: Reproducible build check failed: $SHA1 != $SHA2"
  exit 1
fi
echo "OK: Reproducible JAR build verified (0-byte divergence)."

echo "================================================================================"
echo "[4/6] Verifying CycloneDX 1.6 SBOM Output (Action 17)..."
echo "================================================================================"
grep -q '"specVersion"[[:space:]]*:[[:space:]]*"1.6"' aeib-native-runtime/build/reports/bom.json
echo "OK: CycloneDX 1.6 SBOM (aeib-native-runtime/build/reports/bom.json) verified."

echo "================================================================================"
echo "[5/6] Staging release-artifacts & Computing SLSA Base64 Hashes (aeib-rc-verify.yml Parity)..."
echo "================================================================================"
rm -rf release-artifacts
mkdir -p release-artifacts
test -d aeib-native-runtime/aeib-verifier/build/install/aeib-verifier
cp -a aeib-native-runtime/aeib-verifier/build/install/aeib-verifier release-artifacts/
test -f aeib-native-runtime/build/reports/bom.json
cp aeib-native-runtime/build/reports/bom.json release-artifacts/
test -f aeib-native-runtime/build/reports/slsa/subjects.json
cp aeib-native-runtime/build/reports/slsa/subjects.json release-artifacts/
cp aeib-native-runtime/build/reports/slsa/subjects.base64 release-artifacts/
test -f aeib-native-runtime/build/test-results/receipt.json
cp aeib-native-runtime/build/test-results/receipt.json release-artifacts/
test -f aeib-native-runtime/build/test-results/ledger-public.pem
cp aeib-native-runtime/build/test-results/ledger-public.pem release-artifacts/
test -d aeib-native-runtime/aeib-verifier/src/test/resources/vectors
cp -a aeib-native-runtime/aeib-verifier/src/test/resources/vectors release-artifacts/
test -f release-artifacts/bom.json
test -f release-artifacts/aeib-verifier/lib/aeib-verifier-1.0.0-rc.1.jar
FILES=$(find release-artifacts -type f | sort)
HASHES=$(sha256sum $FILES | base64 -w0)
echo "OK: Staged release-artifacts and computed SLSA Base64 digest (${#HASHES} chars)."

echo "================================================================================"
echo "[6/6] Executing All 5 Standalone Verifier CLI Exit-Code Checks (aeib-rc-verify.yml Parity)..."
echo "================================================================================"
chmod +x release-artifacts/aeib-verifier/bin/aeib-verifier

# 1. Valid Receipt (Exit Code 0)
set +e
./release-artifacts/aeib-verifier/bin/aeib-verifier \
  --receipt release-artifacts/receipt.json \
  --pubkey release-artifacts/ledger-public.pem
status=$?
set -e
if [ "$status" -ne 0 ]; then
  echo "ERROR: valid receipt failed verification with exit code $status"
  exit 1
fi
echo "OK [1/5]: valid receipt verified with exit code 0"

# 2. Tampered Statement Vector (Exit Code 2)
set +e
./release-artifacts/aeib-verifier/bin/aeib-verifier \
  --receipt release-artifacts/vectors/tampered-statement/receipt.json \
  --pubkey release-artifacts/vectors/tampered-statement/public.pem
status=$?
set -e
if [ "$status" -ne 2 ]; then
  echo "ERROR: tampered statement did not exit with code 2, got: $status"
  exit 1
fi
echo "OK [2/5]: tampered statement rejected with exit code 2"

# 3. Malformed JSON Vector (Exit Code 3)
set +e
./release-artifacts/aeib-verifier/bin/aeib-verifier \
  --receipt release-artifacts/vectors/malformed-json/receipt.json \
  --pubkey release-artifacts/vectors/malformed-json/public.pem
status=$?
set -e
if [ "$status" -ne 3 ]; then
  echo "ERROR: malformed JSON did not exit with code 3, got: $status"
  exit 1
fi
echo "OK [3/5]: malformed JSON rejected with exit code 3"

# 4. Missing File Input (Exit Code 3)
set +e
./release-artifacts/aeib-verifier/bin/aeib-verifier \
  --receipt release-artifacts/nonexistent-receipt.json \
  --pubkey release-artifacts/ledger-public.pem
status=$?
set -e
if [ "$status" -ne 3 ]; then
  echo "ERROR: missing receipt did not exit with code 3, got: $status"
  exit 1
fi
echo "OK [4/5]: missing receipt rejected with exit code 3"

# 5. CLI Usage Error (Exit Code 1)
set +e
./release-artifacts/aeib-verifier/bin/aeib-verifier \
  --receipt release-artifacts/receipt.json
status=$?
set -e
if [ "$status" -ne 1 ]; then
  echo "ERROR: missing required option did not exit with code 1, got: $status"
  exit 1
fi
echo "OK [5/5]: CLI usage error rejected with exit code 1"
rm -rf release-artifacts

echo "================================================================================"
echo "ALL LIVE CONTAINER CHECKS (INCLUDING FULL AEIB-RC-VERIFY PARITY) PASSED!"
echo "================================================================================"
