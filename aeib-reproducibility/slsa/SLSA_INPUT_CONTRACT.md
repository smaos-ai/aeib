# SLSA Generator Input Contract (`v2.1.0`)

- **Generator Repository:** `slsa-framework/slsa-github-generator`
- **Pinned Version:** `v2.1.0`
- **Reusable Workflow:** `.github/workflows/generator_generic_slsa3.yml@v2.1.0`
- **Input Parameter:** `base64-subjects`
- **Source URL:** `https://raw.githubusercontent.com/slsa-framework/slsa-github-generator/v2.1.0/.github/workflows/generator_generic_slsa3.yml`
- **Retrieved:** `2026-10-09T04:27:22Z` (verified in hosted CI on `2026-10-10T13:18:26Z`, runs `38055110173` and `38055279949`)

## 1. Required Encoding & Subject Format

Per the `generator_generic_slsa3.yml@v2.1.0` workflow definition:
> *"Artifacts for which to generate provenance, formatted the same as the output of sha256sum (SHA256 NAME\n[...]) and base64 encoded."*

Each line before Base64 encoding must follow standard `sha256sum` output format (two spaces separating lowercase hex SHA-256 digest and artifact filename, newline-delimited):

```text
<64-char-hex-sha256>  <artifact-name>
```

### Valid Construction (Used in `.github/workflows/aeib-ci.yml`)
```bash
cd release-artifacts
HASHES=$(find . -maxdepth 1 -type f -exec sha256sum {} + | sed 's| \./| |' | sort -k2 | base64 -w0)
echo "hashes=$HASHES" >> "$GITHUB_OUTPUT"
```

### Invalid Formats
- Unencoded raw `sha256sum` text output
- Multi-line Base64 output with 76-character line wraps (must pass `-w0` on GNU coreutils)
- Leading `./` path prefixes in subject names when matching flat release assets

## 2. Verified Gradle Project, Task, and Artifact Paths

| Artifact | Gradle Task / Source | On-Disk Build Path |
| :--- | :--- | :--- |
| `aeib-verifier` | `:aeib-verifier:installDist` | `aeib-native-runtime/aeib-verifier/build/install/aeib-verifier/bin/aeib-verifier` |
| `aeib-verifier-1.0.0-rc.1.jar` | `:aeib-verifier:jar` (via `installDist`) | `aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.1.jar` |
| `bom.json` | `cyclonedxBom` | `aeib-native-runtime/build/reports/bom.json` |
| `receipt.json` | `:aeib-tests:test` (`Gate4IntegrationTest`) | `aeib-native-runtime/build/test-results/receipt.json` |
| `ledger-public.pem` | `:aeib-tests:test` (`Gate4IntegrationTest`) | `aeib-native-runtime/build/test-results/ledger-public.pem` |
| `AEIB-RECEIPT-SPEC.md` | Tracked specification at repository root | `AEIB-RECEIPT-SPEC.md` |
| `jvm_native_diff_engine.py` | Tracked Python 3 reference verifier | `benchmarks/jvm_native_diff_engine.py` |

## 3. Epistemic Scope Note
The resulting `multiple.intoto.jsonl` DSSE bundle provides verifiable cryptographic evidence linking the listed subject digests to the hosted GitHub Actions build workflow (`38055110173` / `38055279949`) at commit `b2166a3ffc8f9535a4299dac382dad12ffce85ec`. It does not establish runtime binary integrity outside the build provenance boundary.
