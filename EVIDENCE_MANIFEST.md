# AEIB — Evidence Manifest (`v1.0.0-rc.1` / `v1.0.0-rc.2` Candidate)

## Thesis & Bounded Claim
> **AEIB v1.0.0-rc.1 provides a reproducible evidence bundle for a bounded dispatch-boundary claim: pinned manifests, pre-dispatch standing checks, explicit uncertain-transport handling, bounded reconciliation, RFC 8785 + Ed25519 receipts, and verifier parity for the supplied vectors. It does not prove model trustworthiness, universal exactly-once effects, regulatory compliance, or complete governance.**
>
> **The Release Rule:** *Signals inform priorities. Hosted CI proves implemented behavior under the stated workflow. Separate-party reproduction proves Gate 3. External examination proves a bounded external assessment.*
>
> **Release Tag Immutability Rule:** *A release tag is immutable after hosted CI begins. Never use `git tag -f` or `git push --force` for a published release tag. If the candidate changes after a tag is created, create a new immutable release-candidate tag (e.g., `v1.0.0-rc.2`).*

---

## Source Provenance
```yaml
baseline_rc1_commit_sha: cea4b5c9800902b043eb085a74cc3697a5161f5b
branch:                  release/v1.0-review-candidate
tag_ref:                 v1.0.0-rc.2 (immutable successor tag; v1.0.0-rc.1 frozen)
tag_verification_cmd:    git verify-tag v1.0.0-rc.2
slsa_provenance_bundle:  aeib-reproducibility/evidence/v1.0.0-rc.1/multiple.intoto.jsonl
slsa_bundle_sha256:      0863f43be67065fbac0e96e4c3730926da8d58c812d98328e123768a34b381c5
hosted_ci_runs_on_cea4b5c9:
  - 38211901816 (AEIB Release & Provenance -> success)
  - 38211901792 (AEIB v1.0 Minimal CI Baseline -> success)
  - 38211901499 (AEIB RC Verification and Provenance -> success)
  - 38211899056 (AEIB v1.0 Minimal CI Baseline -> success)
  - 38211898969 (AEIB RC Verification and Provenance -> success)
hosted_ci_runs_on_addfe3ca:
  - 38246098060 (AEIB Release & Provenance -> success)
  - 38246098049 (AEIB v1.0 Minimal CI Baseline -> success)
  - 38246097748 (AEIB RC Verification and Provenance -> success)
  - 38246094658 (AEIB v1.0 Minimal CI Baseline -> success)
  - 38246094308 (AEIB RC Verification and Provenance -> success)
```

## Build Environment & Dependency Identity
```yaml
jdk_version:               21 (Eclipse Adoptium Temurin / OpenJDK)
container_image:           gradle:8.5-jdk21 (eclipse-temurin:21-jdk base)
gradle_version:            8.5
gradle_wrapper_sha256:     d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd
distributionSha256Sum:     9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026
verification_metadata_xml: 96126b5696e4b325ae3f98da9d29a3ae76a6dc53c36da5f894c2ddbe14ffb075
gradle.lockfile_sha256:    32c18865f15ccad306d20447fee69d3e20022180985d3f5cdd4f564e3c363697
tests_lockfile_sha256:     e195c95e7c4a33e3688c59086ef9cc3e0ed270dc73389d0aba1e9162ae119d64
verifier_lockfile_sha256:  ee7b426936710b537ae94777d025a594f93fdc2177179506342ea04aa9ea07e9
```

## Separated Test Evidence Counts
```yaml
jvm_suite:
  task:           :test (:aeib-tests:test, :aeib-verifier:test)
  passed:         20
  failed:         0
  skipped:        0
  junit_xml_paths:
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.DomainRecordsTest.xml (7 passed)
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Gate4IntegrationTest.xml (1 passed: CONFIRMED, REFUTED, CONFLICT & RESOLUTION_RECEIPT)
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.MandatoryNegativeTestSuite.xml (4 passed)
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Station2ConcurrencyTest.xml (1 passed)
    - aeib-native-runtime/aeib-verifier/build/test-results/test/TEST-com.aeib.verifier.VerifierCliTest.xml (7 passed)
differential_verifier_suite:
  command:        python3 benchmarks/jvm_native_diff_engine.py
  vectors_passed: 14 / 14
  jcs_divergence: 0 bytes
cli_negative_vector_suite:
  cases_passed:   5 / 5 (exit codes 0, 2, 3, 3, 1)
python_governance_protection_falsifiability_suite:
  passed:         56 (24 in tests/test_unified_governance_stack.py + 32 in protection/50bf/saga/falsifiability suites)
  failed:         0
```

## Benchmark Evidence
```yaml
benchmark_name:                   Track-B-Gate4 / AEIB Tier 1 Execution Integrity
benchmark_command:                python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
benchmark_parameters:             --episodes 500 --seed 42
benchmark_result_path:            benchmark_results.json
duplicate_external_writes:        0 / 500
duplicate_retry_attempts_blocked: 302
blocked_by_dispatch_gate:         234
blocked_by_ledger_deduplication:  68
benchmark_dispositions:           OUTCOME_VERIFIED=302 NOT_FOUND_AFTER_GRACE=66 POLICY_REFUSED=99 RECONCILIATION_CONFLICT=33
mapped_4_state_summary:           CONFIRMED=302 REFUTED=165 INDETERMINATE=0 CONFLICT=33
```

* **Definition of `duplicate_external_writes`:** A duplicate external write means evidence that the same logical mutation was applied more than once at the target. A blocked retry attempt is not itself a duplicate write.
* **Separation of `NEG-06` from the 500-Episode Benchmark:** `NEG-01` through `NEG-08` are targeted adversarial tests. The 500-episode benchmark is a separate workload and does not include the `NEG-06` delayed/spoofed-target scenario where reconciliation remains unresolved at probe budget exhaustion. Therefore, zero `INDETERMINATE` outcomes in the 500-episode benchmark summary does not imply that AEIB cannot produce `EFFECT_INDETERMINATE`.

## Adversarial Negative-Test Ledger (`NEG-01` – `NEG-08`)

| Scenario ID | Test Input Vector | Enforcing Boundary / Reconciler | Expected Disposition | Observed Disposition | RFC 8785 JCS + Ed25519 Receipt SHA-256 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NEG-01** | MCP Tool-List Poisoning | `Station0AdmissionGate` + `TypedOwaspPreDispatchGate` | `BLOCKED` | `BLOCKED` | `b52a9860cb163a77307e790cb509de8021937dd011047ec306cfee8146520d70` |
| **NEG-02** | Tool-Response Injection | `ForkAndFlushContextBoundary` | `BLOCKED` | `BLOCKED` | `4b0b50d41448ff9935237b2e67075dcb35b21d4440ae62b4a5eaafc452a1ec23` |
| **NEG-03** | RAG / Source Substitution | `TemporalMemoryDigest` (`STALE_DONT_TRUST_YET`) | `BLOCKED` | `BLOCKED` | `09a18d03cd702622bb9a782d1ad706b97f3c439649b566a837d50153ee3078f8` |
| **NEG-04** | Stale Grant Replay | `Station1DispatchInterlock` + `PAD016HeartbeatChain` | `BLOCKED` | `BLOCKED` | `1b6f6a04c746b7b2133caadd9fc7add762974bf8b5c16902851d2f1c751e1bfd` |
| **NEG-05** | Compromised-Agent Replay w/ Valid Key | `LicitraSentryProxyGate` (Single-Use Ticket Burn) | `HOLD` | `HOLD` | `499b917972fffd8b04d90d6b691aeda0cbf84a7d38048b5216ea813093cf243f` |
| **NEG-06** | Target-Endpoint Delay / Spoofing | `Station2EffectReconciler` + `AntiSpecGamingReconciler` | `EFFECT_INDETERMINATE` | `EFFECT_INDETERMINATE` | `6fffed6106e4113f77b17059a503f788003beca97f59b544ccbbf4bea45dc62e` |
| **NEG-07** | Partial Write w/ Reconciler Failure | `SagaReconciler` (Eventual Consistency Queue) | `COMPENSATED_RECORD_RECORDED` | `COMPENSATED_RECORD_RECORDED` | `4d2e45f7b8e34b1e1811d3eea38325738ce984a8d7aaa89a21d610fff115d526` |
| **NEG-08** | Rollback During Open Saga | `Station3ContinuousLedger` (`ContinuityReceipt`) | `RECORDED_FAILURE` | `RECORDED_FAILURE` | `f1c924f55217ec2af557d01b9c5562cd669fdb7edb86db151a797730c9a21bd5` |

* **Operational Meaning of `HOLD` (`NEG-05`):** `HOLD` means AEIB withheld dispatch pending an explicit authorization decision (because the single-use ticket for that operation was already consumed). It does not mean AEIB detected key compromise, revoked the key, or prevented all future use of the key on new authorized tickets.
* **Operational Meaning of `COMPENSATED_RECORD_RECORDED` (`NEG-07`):** AEIB recorded a compensation intent or compensation evidence path in its local ledger. It does not establish that an external target accepted, executed, or completed a compensating action.

## Release Artifact Hashes (SHA-256)
```yaml
container_bom.json:            fbba439d29019bbb44eb68e692479858d6aa8b2a449146396da7ebc8cb1e8eb4
hosted_evidence_bom:           5fcd835d3433e5535619bd17dae2d0ddbaa7da6b857cba0ed5854d39c6ff2d3a
aeib-verifier-1.0.0-rc.1.jar:  4e448ce23f02c3b45db51c268760b8261a4c70078e85ebf3d7ebeb7436f9b5e7 (reproducible Build 1 == Build 2, 0 B divergence)
bin/aeib-verifier:             75e44a96f9f32a7291fa256ae5f02d237209da0af91edbe0e3195b88e42bdc70
aeib-verifier.tar.gz:          b53c9fe4c6f2e26a233f9a230cc9e2639a31a7128e8989b2596be911612a2c31
aeib-verifier.sig:             2339ff9441161aab243916827b48393a6b87e4a9a92dd1983b8372e7576a6052
smaos_wasm_verifier_bg.wasm:   ddd27bc8485e108670b92c33f886d7913e6175a1efa981926eaf1bd9f26a8960
smaos-verify.html:             eecab838785ac4f5796736536c98db37ecd3356a0d103c61be84200f9a53e030
container_gate4_rcpt:          df637e7d7ec6f97f33944621d351120a916109678e3d1da26834fc3582c3fbc2
container_gate4_pubkey:        e75c8efc1a72b3b6810fa46f84d8ed6c5c16bba9e8f76c3cb0cffa88e8d739bf
hosted_gate4_valid_rcpt:       356a6522a9c4bb4689e567683ec91736a10eb40d0d4ab26e8a5ee4414dd80831
hosted_gate4_tampered:         92bb4a19871dba86e9f81faa3053f1cb100fe1d0f9425b87a22ecfab81b62f88
hosted_gate4_pubkey_sha:       90dee4edb70bc3b3c16ecf101b06c165e6058c087c2e4026054df726297a18bb
```

## Reproduction Instructions
```yaml
reproduction:
  clean_checkout: |
    git clone https://github.com/smaos-ai/aeib.git
    cd aeib
    git fetch origin --tags
    git checkout v1.0.0-rc.2
    git rev-parse v1.0.0-rc.2^{commit}
  hosted_ci:
    - Inspect runs 38211901816, 38211901792, 38211901499 (cea4b5c9) and 38246098060, 38246098049, 38246097748 (addfe3ca).
    - Confirm each run concluded with success on its respective commit.
  local_tests:
    command: ./gradlew clean test --dependency-verification strict --no-daemon --stacktrace
    expected: BUILD SUCCESSFUL
    expected_jvm_tests: 20 passed, 0 failed, 0 skipped
  verifier_vectors:
    command: python3 benchmarks/jvm_native_diff_engine.py
    expected: 14/14 vectors matched; verdict_mismatches=0; canonical_jcs_divergence=0 bytes
  benchmark:
    command: python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
    expected_result_path: benchmark_results.json
    expected_duplicate_external_writes: 0
  artifact_verification:
    command: sha256sum aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.1.jar
    expected: 4e448ce23f02c3b45db51c268760b8261a4c70078e85ebf3d7ebeb7436f9b5e7
```

## 5-Gate Release Protocol Status

| Gate | Requirement | Evidence / Artifact | Bounded Status |
| :--- | :--- | :--- | :--- |
| **Gate 1: Hosted CI Execution** | Hosted GitHub Actions runners report `success` on candidate SHA | Runs `38211901816`, `38211901792`, `38211901499` (`cea4b5c9`) & `38246098060`, `38246098049`, `38246097748` (`addfe3ca`) | **`VERIFIED under stated CI-review procedure`** |
| **Gate 2: Verifier Parity** | Java 21 (`ReceiptVerifier`) & Python 3 (`jvm_native_diff_engine.py`) parity | `14/14` receipt vectors matched with `0 B` RFC 8785 JCS divergence + Wycheproof/ZIP-215 & Cyberphone vectors | **`VERIFIED for the 14 supplied vectors`** |
| **Gate 3: Supply Chain Attestation** | CycloneDX 1.6 SBOM + SLSA v1.1-compatible provenance + `verification-metadata.xml` | `bom.json` (`specVersion: "1.6"`), `multiple.intoto.jsonl`, `VERIFY_RELEASE.md`, `gradle/verification-metadata.xml` (`SLSA v1.1-compatible provenance generated and verified for the stated build; build-level claim subject to generator configuration, runner isolation, and predicate verification`) | **`VERIFIED for artifact presence and stated checks; SLSA level claim requires explicit basis`** |
| **Gate 4: Manifest Completion** | `EVIDENCE_MANIFEST.md` populated with adversarial ledger (`NEG-01`–`NEG-08`) & Category A–E calibration | [`EVIDENCE_MANIFEST.md`](file:///Users/andriileukhin/Documents/SovereignNexus/EVIDENCE_MANIFEST.md) + [`TPRM_BUYER_SECURITY_AND_COMPLIANCE_PACK.md`](file:///Users/andriileukhin/Documents/SovereignNexus/docs/TPRM_BUYER_SECURITY_AND_COMPLIANCE_PACK.md) | **`COMPLETE for v1.0.0-rc.1 manifest requirements`** |
| **Gate 5: Separate-Party Reproduction** | Independent clean-room reproduction outside author environment | Container harness (`scripts/run_live_container_verification.sh`) verified locally; external third-party sign-off tracked separately | **`READY FOR EXTERNAL REPRODUCTION`** |

## Schema & Cryptographic Profile Separation
```yaml
receipt_schema_id:       urn:aeib:receipt:1.0 (AEIB-RECEIPT-SPEC.md)
receipt_schema_version:  1.0
v1_1_memory_schema_id:   https://smaos.ai/schemas/aeib-memory-digest-v1.1.schema.json
signing_profile_v1_0:    Ed25519 (RFC 8032) over RFC 8785 JCS canonical statement bytes
signing_profile_v1_1:    Composite detached Ed25519 (RFC 8032) + ML-DSA-65 (FIPS 204); fail-closed REJECT on missing/invalid component
channel_kem_profile:     X25519MLKEM768 (FIPS 203 ML-KEM) for confidential transit channel establishment (strictly distinct from receipt signing)
```

## Station 1 Standing & Tripartite Memory Admissibility (`v1.0` & `v1.1` Roadmap)
$$\text{AuthorizationAdmissibility} = \text{GrantValid} \land \text{PolicyEpochFresh} \land \text{SourceEpochFresh} \land \text{ControlHealthy} \land \text{RiskProfileWithinGrantLimits}$$

$$\text{MemoryAdmissible} = \text{BlockIntegrityValid} \land \text{ProvenanceValid} \land \text{EpochFresh} \land \text{GrantScopeValid}$$

$$\text{IsStale} \iff (t_{\text{current}} - t_{\text{source}} > \text{TTL}) \lor (\text{Epoch}_{\text{policy}} \neq \text{Epoch}_{\text{active}}) \lor (\text{Epoch}_{\text{source}} \neq \text{Epoch}_{\text{source\_active}}) \lor \text{IsRevoked}(\text{Channel}_{\text{rev}})$$

* **`BlockIntegrityValid`**: Cryptographic hash check over the restored $\le 16\text{k}$-token KV block or canonicalized workspace payload.
* **`ProvenanceValid`**: Traceability to verified source documents, tool outputs, or workspace facts.
* **`EpochFresh`**: Mechanical metadata check ($t_{\text{current}} - t_{\text{source}} \le \text{TTL}$ and matching active policy/source epochs).
* **`GrantScopeValid`**: Active authorization grant covering the target effect URI and capability.

## Explicit Scope Limitations (Bounded Claims under the Stated Model)
- Does **NOT** verify model memory truth or prevent upstream memory poisoning.
- Does **NOT** verify retrieval-source provenance or RAG document authenticity in `v1.0.0-rc.1`.
- Does **NOT** claim universal exactly-once side-effects on uncooperative target APIs.
- Does **NOT** provide external SCITT transparency ledger anchoring in `v1.0.0-rc.1`.
- Does **NOT** implement automatic public key lookup or PKI discovery (caller must supply the pinned SPKI public key).
- Does **NOT** claim ISO 42001, EU AI Act, SOC 2, or DORA regulatory compliance out of the box.
- Positions **LuMay AI Framework** strictly as an 8-layer governance taxonomy reference (AEIB contributes evidence for narrow subsets of Layer 6 *Controls* and Layer 7 *Monitoring & Audit* only).
- **Context Mode Reference:** AEIB does not incorporate Context Mode code or distribute it under AEIB. Context Mode is treated as an architectural reference only, subject to license and dependency review before any future integration.
- Treats the boundary, policy engine, executor, and audit log as high-value attack surfaces requiring minimal privilege, zero-I/O evaluation, and strict isolation.
