# AEIB v1.0.0-rc.1 Committed-Tree Local Developer Preflight Report

## Epistemic & Scope Disclosures

1. **Committed-Tree Archive Source (`git archive`)**: This preflight executes against an archive created directly from `HEAD` via `git archive --format=tar.gz HEAD` and extracted into an isolated temporary directory, **not a dirty host-mounted working directory**. Untracked files and uncommitted working-tree modifications in the developer workspace are excluded from the extracted source tree.
2. **Local Developer Preflight Only**: This execution is a **local developer preflight**, **NOT a clean-room reproduction** (Gate 3) and **NOT a substitute for hosted-CI success**. Gate 3 remains pending and is not called complete until separate-party reproduction evidence from the signed tag exists.

---

## Preflight Artifact & Commit Metadata

| Parameter | Recorded Value |
|---|---|
| **Harness Script** | `aeib-reproducibility/preflight/run_committed_tree_preflight.sh` |
| **Execution Timestamp (UTC)** | `2026-10-10T15:24:24Z` |
| **Git Tag / Branch** | `v1.0.0-rc.1` (`release/v1.0-review-candidate`) |
| **HEAD Commit SHA** | `b2166a3ffc8f9535a4299dac382dad12ffce85ec` |
| **Archive Command** | `git archive --format=tar.gz HEAD` |
| **Archive Size** | `300328509 bytes` |
| **Archive SHA-256 Digest** | `767fb4cd57e9b7d99c516d041c8fe0c302db7c192d0fcb9046988e83f3537b2d` |
| **Extracted Committed Files** | `47480` |
| **Java Compilation Units Verified** | `25` `.java` source files + `6` `gradle.lockfile` manifests |
| **Aggregate Java Source SHA-256** | `3e86e996a761979241c3b9114681b101a66080a51b7151f20ef5e0afedf3c893` |
| **Evaluated Gate 4 Receipt SHA-256** | `356a6522a9c4bb4689e567683ec91736a10eb40d0d4ab26e8a5ee4414dd80831` |
| **Evaluated Public Key SHA-256** | `90dee4edb70bc3b3c16ecf101b06c165e6058c087c2e4026054df726297a18bb` |

---

## Executed Verification Steps & Observed Results

1. **Committed-Tree Archive Generation & Extraction**:
   - Exported `HEAD` (`b2166a3ffc8f9535a4299dac382dad12ffce85ec`) via `git archive --format=tar.gz` and verified archive SHA-256 digest `767fb4cd57e9b7d99c516d041c8fe0c302db7c192d0fcb9046988e83f3537b2d`.
   - Extracted archive to an isolated temporary directory and confirmed presence of `AEIB-RECEIPT-SPEC.md`, all 6 `gradle.lockfile` files, 25 Java source compilation units, `aeib-verifier/src/test/resources/vectors/manifest.json`, and `benchmarks/jvm_native_diff_engine.py`.

2. **Cross-Language Differential Parity Engine (`python3 benchmarks/jvm_native_diff_engine.py`)**:
   - **Axis 1 (RFC 8785 JCS Canonicalization)**: 6 vectors evaluated, `byte_divergence=0 bytes`.
   - **Axis 2 (SHA-256 `chainTip` Derivation)**: 2 multi-event chain derivations evaluated, 32-byte digest parity confirmed.
   - **Axis 3 (Gate 4 Live Receipt Artifact)**: Target A (JVM) = `ACCEPT (exit 0)` | Target B (Python) = `ACCEPT (exit 0)` | `jcs_divergence=0 bytes`.
   - **Axis 4 (Manifest Vectors)**: `14/14` receipt vectors matched (`verdict_mismatches=0`, `canonical_jcs_divergence=0 bytes`).

3. **Standalone Receipt Exit-Code Verification**:
   - Valid receipt (`receipt.json`, SHA-256 `356a6522a9c4bb4689e567683ec91736a10eb40d0d4ab26e8a5ee4414dd80831`): `ACCEPT` with exit code `0`.
   - Tampered signature vector (`tampered-signature/receipt.json`): `REJECT` with non-zero exit code `2`.
   - Tampered statement vector (`tampered-statement/receipt.json`): `REJECT` with non-zero exit code `2`.

---

## Full Execution Transcript

```text
==============================================================================
  AEIB v1.0.0-rc.1 COMMITTED-TREE LOCAL DEVELOPER PREFLIGHT
==============================================================================
[*] Scope Notice 1    : Uses a committed-tree archive (git archive --format=tar.gz HEAD),
                        NOT a dirty host-mounted working directory.
[*] Scope Notice 2    : This is a local developer preflight, NOT a clean-room
                        reproduction and NOT a substitute for hosted-CI success.
[*] Timestamp (UTC)   : 2026-10-10T15:24:24Z
[*] Source Repository : /Users/andriileukhin/Documents/SovereignNexus
[*] HEAD Commit SHA   : b2166a3ffc8f9535a4299dac382dad12ffce85ec

[1/6] Creating committed-tree archive from HEAD via git archive...
  Archive Path        : /var/folders/y7/fxmrtvyn21j3ns3zng5kn6x80000gn/T//aeib-committed-preflight.vfbLx3/aeib-head-b2166a3ffc8f.tar.gz
  Archive Size        : 300328509 bytes
  Archive SHA-256     : 767fb4cd57e9b7d99c516d041c8fe0c302db7c192d0fcb9046988e83f3537b2d

[2/6] Extracting committed-tree archive to isolated temporary directory...
  Extracted Directory : /var/folders/y7/fxmrtvyn21j3ns3zng5kn6x80000gn/T//aeib-committed-preflight.vfbLx3/tree
  Extracted Files     : 47480

[3/6] Verifying committed-tree Java sources, Gradle lockfiles, and spec presence...
  Verified 25 committed Java compilation units and 6 Gradle lockfiles.
  Aggregate Java source tree SHA-256: 3e86e996a761979241c3b9114681b101a66080a51b7151f20ef5e0afedf3c893

[4/6] Staging pinned Gate 4 test-result artifacts for offline differential check...
  Staged Gate 4 artifacts from aeib-reproducibility/evidence/v1.0.0-rc.1 (CI run 38055279949)

[5/6] Running Cross-Language Differential Parity Engine inside extracted committed tree...
==============================================================================
  AEIB v1.1 DIFFERENTIAL PARITY ENGINE (JAVA 21 / GRAALVM vs PYTHON 3)
==============================================================================
[+] Axis 1 (RFC 8785 JCS Canonicalization): 6 vectors evaluated, byte_divergence=0 bytes
[+] Axis 2 (SHA-256 chainTip Derivation):   2 chain derivations evaluated, 32-byte digest parity confirmed
[+] Axis 3 (Gate 4 Live Receipt Artifact):  Target A=ACCEPT(0) | Target B=ACCEPT(0) | jcs_divergence=0 bytes
------------------------------------------------------------------------------
VECTOR ID                  | TARGET A (JVM)   | TARGET B (PY)    | JCS DIFF
------------------------------------------------------------------------------
valid                      | ACCEPT (exit 0)  | ACCEPT (exit 0)  | 0 B
tampered-statement         | REJECT (exit 2)  | REJECT (exit 2)  | 0 B
tampered-signature         | REJECT (exit 2)  | REJECT (exit 2)  | 0 B
wrong-key                  | REJECT (exit 2)  | REJECT (exit 2)  | 0 B
unknown-keyid              | REJECT (exit 2)  | REJECT (exit 2)  | 0 B
non-canonical-statement    | REJECT (exit 2)  | REJECT (exit 2)  | 71 B (expected >0)
missing-keyid              | REJECT (exit 3)  | REJECT (exit 3)  | 0 B
malformed-json             | REJECT (exit 3)  | REJECT (exit 3)  | 0 B
trailing-token             | REJECT (exit 3)  | REJECT (exit 3)  | 0 B
oversized-receipt          | REJECT (exit 3)  | REJECT (exit 3)  | 0 B
missing-receipt            | REJECT (exit 3)  | REJECT (exit 3)  | 0 B
missing-public-key         | REJECT (exit 3)  | REJECT (exit 3)  | 0 B
directory-as-receipt       | REJECT (exit 3)  | REJECT (exit 3)  | 0 B
------------------------------------------------------------------------------
Differential Summary: 14/14 receipt vectors matched | verdict_mismatches=0 | canonical_jcs_divergence=0 bytes
==============================================================================

[6/6] Asserting valid (exit 0) and tampered (exit 2) receipt verification inside extracted tree...
  Receipt SHA-256    : 356a6522a9c4bb4689e567683ec91736a10eb40d0d4ab26e8a5ee4414dd80831
  Public Key SHA-256 : 90dee4edb70bc3b3c16ecf101b06c165e6058c087c2e4026054df726297a18bb
  Valid receipt check    : ACCEPT (exit_code=0)
  Tampered sig check     : REJECT (exit_code=2)
  Tampered stmt check    : REJECT (exit_code=2)

==============================================================================
  COMMITTED-TREE LOCAL DEVELOPER PREFLIGHT PASSED
  HEAD Commit SHA : b2166a3ffc8f9535a4299dac382dad12ffce85ec
  Archive SHA-256 : 767fb4cd57e9b7d99c516d041c8fe0c302db7c192d0fcb9046988e83f3537b2d
==============================================================================
```
