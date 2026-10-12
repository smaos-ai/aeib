# AEIB Release Verification Guide (`VERIFY_RELEASE.md`)

**Target Release:** `v1.0.0-rc.2` (`release/v1.0-review-candidate`; supersedes `v1.0.0-rc.1`)  
**Epistemic Boundary:** Build provenance is generated with `slsa-framework/slsa-github-generator` (`generator_generic_slsa3.yml@v2.1.0`) on GitHub-hosted runners and emits an `.intoto.jsonl` attestation. Formal SLSA Level 3 conformance depends on verifier check results and trust-root policy. This does not claim SLSA Source Track certification or hardware-isolated builder silicon.

## Release Tag Integrity

Release candidate tags (`v1.0.0-rc.1`, `v1.0.0-rc.2`, etc.) are treated as immutable once published. Subsequent corrections are published as new release candidate tags rather than force-updating existing tags.

---

## 1. Verify Gradle Wrapper & Dependency Lock Integrity

Before building from source, verify the pinned Gradle 8.5 wrapper JAR and distribution SHA-256 digests:

```bash
# 1. Verify Gradle 8.5 wrapper JAR SHA-256
echo "d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd  gradle/wrapper/gradle-wrapper.jar" | sha256sum -c -
# Expected: gradle/wrapper/gradle-wrapper.jar: OK

echo "d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd  aeib-native-runtime/gradle/wrapper/gradle-wrapper.jar" | sha256sum -c -
# Expected: aeib-native-runtime/gradle/wrapper/gradle-wrapper.jar: OK

# 2. Verify pinned distributionSha256Sum in gradle-wrapper.properties
grep "distributionSha256Sum=9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026" gradle/wrapper/gradle-wrapper.properties
# Expected: distributionSha256Sum=9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026
```

To regenerate or verify Gradle dependency metadata (`gradle/verification-metadata.xml`) on a JDK 21 host:

```bash
./gradlew --write-verification-metadata sha256 help --no-daemon
# Expected: BUILD SUCCESSFUL and exit code 0
```

---

## 2. Verify SLSA Build Provenance (`slsa-verifier`)

Artifacts built by `.github/workflows/aeib-ci.yml` emit a tamper-evident `.intoto.jsonl` provenance attestation signed via Fulcio/Rekor OIDC by the isolated `slsa-framework/slsa-github-generator` workflow:

```bash
slsa-verifier verify-artifact \
  release-artifacts/aeib-verifier-1.0.0-rc.1.jar \
  --provenance-path multiple.intoto.jsonl \
  --source-uri github.com/smaos-ai/aeib \
  --source-branch release/v1.0-review-candidate
# Expected: Verified build using builder "https://github.com/slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@refs/tags/v2.1.0" and exit code 0 ("PASSED: SLSA verification passed")
```

---

## 3. Verify GitHub Artifact Attestations (`gh attestation verify`)

Artifacts attested by `.github/workflows/aeib-rc-verify.yml` (`actions/attest-build-provenance@e8998f949152b193b063cb0ec769d69d929409be`, `v4.1.0`) can be verified using the GitHub CLI against the Sigstore public good instance (or an offline bundle):

```bash
# Online verification against Sigstore public trust root
gh attestation verify release-artifacts/aeib-verifier/lib/aeib-verifier-1.0.0-rc.1.jar \
  --repo smaos-ai/aeib \
  --signer-workflow smaos-ai/aeib/.github/workflows/aeib-rc-verify.yml
# Expected: Verification succeeded! and exit code 0

gh attestation verify release-artifacts/bom.json \
  --repo smaos-ai/aeib \
  --signer-workflow smaos-ai/aeib/.github/workflows/aeib-rc-verify.yml
# Expected: Verification succeeded! and exit code 0
```

---

## 4. Verify Sigstore / Cosign Keyless Bundles (`cosign verify-blob`)

When verifying detached `.sigstore.json` bundles in air-gapped environments using a pinned Sigstore `trusted_root.json`:

```bash
cosign verify-blob \
  release-artifacts/aeib-verifier-1.0.0-rc.1.jar \
  --bundle release-artifacts/aeib-verifier-1.0.0-rc.1.jar.sigstore.json \
  --certificate-identity-regexp "^https://github.com/smaos-ai/aeib/\.github/workflows/aeib-(ci|rc-verify)\.yml@refs/(heads/release/v1\.0-review-candidate|tags/v1\.0\.0-rc\.[0-9]+)$" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  --offline
# Expected: Verified OK and exit code 0
```

---

## 5. Verify Reproducible Build & Cross-Language Receipt Parity

1. **Reproducible Archive Verification (Action 19):**
   ```bash
   ./gradlew :aeib-verifier:jar --no-daemon
   SHA1=$(sha256sum aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.1.jar | awk '{print $1}')
   ./gradlew :aeib-verifier:jar --rerun-tasks --no-daemon
   SHA2=$(sha256sum aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.1.jar | awk '{print $1}')
   test "$SHA1" = "$SHA2" && echo "Reproducible JAR digest verified: $SHA1"
   # Expected: Reproducible JAR digest verified: 4e448ce23f02c3b45db51c268760b8261a4c70078e85ebf3d7ebeb7436f9b5e7 (0 B divergence, exit code 0)
   ```
2. **Standalone Offline Java 21 Verifier CLI:**
   ```bash
   ./aeib-native-runtime/aeib-verifier/build/install/aeib-verifier/bin/aeib-verifier \
     --receipt aeib-native-runtime/aeib-verifier/src/test/resources/vectors/valid/receipt.json \
     --pubkey aeib-native-runtime/aeib-verifier/src/test/resources/vectors/valid/public.pem
   # Expected: VERIFIED | operationId=OP-2026-0001 | caid=caid-valid-0001 | keyId=aeib-test-ed25519-01 (exit code 0)
   ```
3. **Cross-Language Java 21 vs. Python 3 Differential Verifier (`14/14` Vectors):**
   ```bash
   python3 benchmarks/jvm_native_diff_engine.py
   # Expected: 14/14 receipt vectors matched | verdict_mismatches=0 | canonical_jcs_divergence=0 bytes (exit code 0)
   ```
