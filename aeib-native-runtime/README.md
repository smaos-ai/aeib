# AEIB Native Runtime (v1.0.0-rc.1)

Java 21 LTS deterministic execution-integrity runtime for agentic systems.

---

## 🏛️ Epistemic Stance & Core Bounded Capabilities

AEIB operates under a strict epistemic lock. It does not claim universal exactly-once execution, absence of remote duplicate mutations, complete prompt-injection prevention, or blanket regulatory conformity.

The core capability statements of AEIB are locked to these exact, verified bounds:
* **Pins and verifies a declared execution manifest.**
* **Evaluates declared standing locally before network dispatch.**
* **Represents uncertain transport outcomes explicitly.**
* **Reconciles uncertain outcomes under declared policy and probe budgets.**
* **Produces operation-bound, tamper-evident receipts.**

---

## 🏗️ Architecture: Four Stations Pipeline

1. **Station 0 / 1: Pre-Dispatch Admissibility & Dispatch Interlock**
   * Pinned manifest verification (`ActionManifest`, `DomainRecords`).
   * Deterministic Content-Addressed Action Identifier (`CaidEngine`) using RFC 8785 JSON Canonicalization Scheme (JCS).
2. **Station 2: Transport & Outcome Reconciliation**
   * Reconciles transport ambiguities (HTTP 504, TCP RST, timeout) via out-of-band probes.
   * Enforces single-flight coalescing (`SingleFlightCoalescer`) to eliminate duplicate concurrent probe requests.
   * Latches non-resolvable outcomes as `EFFECT_INDETERMINATE` under absolute operation-level deadline (`ProbeBudget`).
3. **Station 3: Signed Receipt & Evidence Preservation**
   * Emits RFC 8785 canonical statement bound to root receipt fields.
   * Pure SunEC Ed25519 digital signature (`Ed25519ProofEngine`).
4. **Station 4: Offline Verification (`aeib-verifier`)**
   * Linear, single-responsibility pipeline (`ReceiptVerifier`, `PublicKeyReader`, `ReceiptFileReader`, `ReceiptParser`).
   * Strict input bounds (1 MiB receipt limit, 64 KiB key limit, regular non-symlink files).
   * Strict PEM-encoded X.509 `SubjectPublicKeyInfo` format pinning.
   * Deterministic exit codes: `0` (valid), `1` (CLI usage), `2` (cryptographic / field mismatch), `3` (input / format / schema error), `4` (internal failure).

---

## 🧪 Local Verification & Test Execution

Run the complete test suite and verifier build:

```bash
# Clean and run all unit, integration, and negative test suites
./gradlew clean test

# Build the standalone offline verifier distribution
./gradlew :aeib-verifier:installDist

# Generate CycloneDX Software Bill of Materials (SBOM)
./gradlew cyclonedxBom
```

### Deterministic Test Vectors

The offline verifier suite includes 13 committed deterministic test vectors under `aeib-verifier/src/test/resources/vectors/` indexed by `manifest.json`:
- `valid` (Exit code `0`)
- `tampered-statement` (Exit code `2`)
- `tampered-signature` (Exit code `2`)
- `wrong-key` (Exit code `2`)
- `unknown-keyid` (Exit code `2`)
- `non-canonical-statement` (Exit code `2`)
- `missing-keyid` (Exit code `3`)
- `malformed-json` (Exit code `3`)
- `trailing-token` (Exit code `3`)
- `oversized-receipt` (Exit code `3`)
- `missing-receipt` (Exit code `3`)
- `missing-public-key` (Exit code `3`)
- `directory-as-receipt` (Exit code `3`)

---

## 🏛️ External Examination Candidate

```markdown
Prerequisites:
- Signed v1.0.0 release tag
- Hosted CI evidence
- Published acceptance suite
- Independent clean-room reproduction
- Independent cryptographic review
- Preserved limitations

Status:
- Not scheduled
- No examiner engaged
- No target determination assumed
```

---

## 📊 Summary Verdict Matrix

| External Signal | AEIB Decision & Scope Boundary |
| :--- | :--- |
| **Airgorah** | Documentation & layout pattern reference only. |
| **TA-14 / HSG** | Future external-validation model reference; **no equivalence claimed**. |
| **API-Gateway Separation** | Consistent design principle; candidate input for v1.1 specification. |
| **HERMES Benchmark** | Specific research context; **no generalized claims on model vs. harness**. |
| **SkillOpt / Memory Research** | Informs v1.1 procedural-write threat model candidate (**TM-12 / TM-13**). |
| **Inference & Market Signals** | Market and documentation context only. |

---

## 📄 License

Licensed under the Apache License, Version 2.0. See the top-level `LICENSE` file for details.
