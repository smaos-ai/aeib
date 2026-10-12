#!/usr/bin/env bash
set -euo pipefail

echo "================================================================================"
echo "[1/5] Verifying Gradle 8.5 Wrapper JAR SHA-256..."
echo "================================================================================"
echo "d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd  gradle/wrapper/gradle-wrapper.jar" | sha256sum -c -
echo "d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd  aeib-native-runtime/gradle/wrapper/gradle-wrapper.jar" | sha256sum -c -

echo "================================================================================"
echo "[2/5] Running Clean Build, JUnit Test Suite, installDist & CycloneDX 1.6 SBOM (Strict Dependency Verification)..."
echo "================================================================================"
./gradlew clean test :aeib-verifier:installDist cyclonedxBom --dependency-verification strict --no-daemon --info

echo "================================================================================"
echo "[3/5] Running Reproducible Build-Twice-and-Diff Check (Action 19)..."
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
echo "[4/5] Verifying CycloneDX 1.6 SBOM Output (Action 17)..."
echo "================================================================================"
grep -q '"specVersion"[[:space:]]*:[[:space:]]*"1.6"' aeib-native-runtime/build/reports/bom.json
echo "OK: CycloneDX 1.6 SBOM (aeib-native-runtime/build/reports/bom.json) verified."

echo "================================================================================"
echo "[5/5] Executing Standalone Offline Verifier CLI against Gate 4 Live Receipt..."
echo "================================================================================"
chmod +x aeib-native-runtime/aeib-verifier/build/install/aeib-verifier/bin/aeib-verifier
./aeib-native-runtime/aeib-verifier/build/install/aeib-verifier/bin/aeib-verifier \
  --receipt aeib-native-runtime/build/test-results/receipt.json \
  --pubkey aeib-native-runtime/build/test-results/ledger-public.pem

echo "================================================================================"
echo "ALL LIVE CONTAINER CHECKS PASSED!"
echo "================================================================================"
