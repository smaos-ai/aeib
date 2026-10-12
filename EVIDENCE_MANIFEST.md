# AEIB v1.0.0-rc.1 — Evidence Manifest

## Thesis & Bounded Claim
> **The batch identifies the governance problems AEIB addresses. `v1.0.0-rc.1` is the first reproducible evidence bundle for that bounded claim—not proof of universal safety or complete governance.**
>
> **Operating Thesis:** AI systems generate plausible proposals, rationales, and memories. AEIB does not attempt to make the model trustworthy; it makes the authorized effect independently checkable—by binding intent, policy epoch, source epoch, and execution result to verifiable evidence at the moment of action.

---

## Source Provenance
```yaml
commit_sha:              872653436d392efdd5569e85bd2e90abf745be2c
baseline_tag_commit_sha: 9c791b3ed5e53d1119c92a3d1a42875d95c09a83
branch:                  release/v1.0-review-candidate
signed_tag_plan:         v1.0.0-rc.1 (deferred until hosted CI green on candidate commit)
tag_verification_cmd:    git tag -v v1.0.0-rc.1
slsa_provenance_bundle:  aeib-reproducibility/evidence/v1.0.0-rc.1/multiple.intoto.jsonl
slsa_bundle_sha256:      0863f43be67065fbac0e96e4c3730926da8d58c812d98328e123768a34b381c5
```

## Build Environment & Dependency Identity
```yaml
jdk_version:             21 (Eclipse Adoptium Temurin / OpenJDK)
container_image:         gradle:8.5-jdk21 (eclipse-temurin:21-jdk base)
gradle_version:          8.5
gradle_wrapper_sha256:   d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd
distributionSha256Sum:   9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026
gradle.lockfile_sha256:  32c18865f15ccad306d20447fee69d3e20022180985d3f5cdd4f564e3c363697
tests_lockfile_sha256:   e195c95e7c4a33e3688c59086ef9cc3e0ed270dc73389d0aba1e9162ae119d64
verifier_lockfile_sha256: ee7b426936710b537ae94777d025a594f93fdc2177179506342ea04aa9ea07e9
```

## Test Evidence (JVM Suite, Cross-Language Parity & Python Governance Suite)
```yaml
test_task:               :test (:aeib-tests:test, :aeib-verifier:test)
jvm_test_count_total:    19
jvm_test_count_passed:   19
jvm_test_count_failed:   0
jvm_test_count_skipped:  0
junit_xml_paths:
  - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.DomainRecordsTest.xml (7 passed)
  - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Gate4IntegrationTest.xml (1 passed)
  - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.MandatoryNegativeTestSuite.xml (3 passed)
  - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Station2ConcurrencyTest.xml (1 passed)
  - aeib-native-runtime/aeib-verifier/build/test-results/test/TEST-com.aeib.verifier.VerifierCliTest.xml (7 passed)
differential_verifier:   benchmarks/jvm_native_diff_engine.py (14/14 receipt vectors matched, 0 B canonical RFC 8785 JCS divergence)
python_governance_tests: 43 passed (tests/test_unified_governance_stack.py + core protection/saga/falsifiability suites)
```

## Benchmark Evidence
```yaml
benchmark_name:          Track-B-Gate4 / AEIB Tier 1 Execution Integrity
benchmark_command:       python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
benchmark_parameters:    --episodes 500 --seed 42
benchmark_result_path:   benchmark_results.json
duplicate_writes:        0 / 500 (302 duplicate retry attempts blocked: gate=234, ledger=68)
benchmark_dispositions:  OUTCOME_VERIFIED=302 NOT_FOUND_AFTER_GRACE=66 POLICY_REFUSED=99 RECONCILIATION_CONFLICT=33
mapped_4_state_summary:  CONFIRMED=302 REFUTED=165 INDETERMINATE=0 CONFLICT=33
```

## Adversarial Negative-Test Ledger (`NEG-01` – `NEG-08`)

| Scenario ID | Test Input Vector | Enforcing Boundary / Reconciler | Expected Disposition | Observed Disposition | RFC 8785 JCS + Ed25519 Receipt SHA-256 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NEG-01** | MCP Tool-List Poisoning | `Station0AdmissionGate` + `TypedOwaspPreDispatchGate` | `BLOCKED` | `BLOCKED` | `b52a9860cb163a77307e790cb509de8021937dd011047ec306cfee8146520d70` |
| **NEG-02** | Tool-Response Injection | `ForkAndFlushContextBoundary` | `BLOCKED` | `BLOCKED` | `4b0b50d41448ff9935237b2e67075dcb35b21d4440ae62b4a5eaafc452a1ec23` |
| **NEG-03** | RAG / Source Substitution | `TemporalMemoryDigest` (`STALE_DONT_TRUST_YET`) | `BLOCKED` | `BLOCKED` | `09a18d03cd702622bb9a782d1ad706b97f3c439649b566a837d50153ee3078f8` |
| **NEG-04** | Stale Grant Replay | `Station1DispatchInterlock` + `PAD016HeartbeatChain` | `BLOCKED` | `BLOCKED` | `1b6f6a04c746b7b2133caadd9fc7add762974bf8b5c16902851d2f1c751e1bfd` |
| **NEG-05** | Compromised-Agent Replay w/ Valid Key | `LicitraSentryProxyGate` (Single-Use Ticket Burn) | `HOLD` | `HOLD` | `499b917972fffd8b04d90d6b691aeda0cbf84a7d38048b5216ea813093cf243f` |
| **NEG-06** | Target-Endpoint Delay / Spoofing | `Station2EffectReconciler` + `AntiSpecGamingReconciler` | `EFFECT_INDETERMINATE` | `EFFECT_INDETERMINATE` | `6fffed6106e4113f77b17059a503f788003beca97f59b544ccbbf4bea45dc62e` |
| **NEG-07** | Partial Write w/ Reconciler Failure | `SagaReconciler` (Eventual Consistency Queue) | `COMPENSATED` | `COMPENSATED` | `4d2e45f7b8e34b1e1811d3eea38325738ce984a8d7aaa89a21d610fff115d526` |
| **NEG-08** | Rollback During Open Saga | `Station3ContinuousLedger` (`ContinuityReceipt`) | `RECORDED_FAILURE` | `RECORDED_FAILURE` | `f1c924f55217ec2af557d01b9c5562cd669fdb7edb86db151a797730c9a21bd5` |

## Release Artifact Hashes (SHA-256)
```yaml
container_bom.json:      6ea3ea743c4e645695fda1ed564e5ae3860de58f1373d8d031e0fd5c2c2611f0
hosted_evidence_bom:     5fcd835d3433e5535619bd17dae2d0ddbaa7da6b857cba0ed5854d39c6ff2d3a
aeib-verifier-1.0.0-rc.1.jar: 9dfde412353cc77471321f88bbcf736e271f99a6dc5e2e7652e189326ebc41b6
bin/aeib-verifier:       75e44a96f9f32a7291fa256ae5f02d237209da0af91edbe0e3195b88e42bdc70
container_gate4_rcpt:    df637e7d7ec6f97f33944621d351120a916109678e3d1da26834fc3582c3fbc2
container_gate4_pubkey:  e75c8efc1a72b3b6810fa46f84d8ed6c5c16bba9e8f76c3cb0cffa88e8d739bf
hosted_gate4_valid_rcpt: 356a6522a9c4bb4689e567683ec91736a10eb40d0d4ab26e8a5ee4414dd80831
hosted_gate4_tampered:   92bb4a19871dba86e9f81faa3053f1cb100fe1d0f9425b87a22ecfab81b62f88
hosted_gate4_pubkey_sha: 90dee4edb70bc3b3c16ecf101b06c165e6058c087c2e4026054df726297a18bb
```

## Schema & Cryptographic Profile Separation
```yaml
receipt_schema_id:       urn:aeib:receipt:1.0 (AEIB-RECEIPT-SPEC.md)
receipt_schema_version:  1.0
v1_1_memory_schema_id:   https://smaos.ai/schemas/aeib-memory-digest-v1.1.schema.json
signing_profile_v1_0:    Ed25519 (RFC 8032) over RFC 8785 JCS canonical statement bytes
signing_profile_v1_1:    Composite detached Ed25519 (RFC 8032) + ML-DSA-65 (FIPS 204); fail-closed REJECT on missing/invalid component
channel_kem_profile:     X25519MLKEM768 (FIPS 203 ML-KEM) for confidential transit channel establishment (strictly distinct from receipt signing)
```

## Formal Memory Admissibility & Mechanical Staleness (`v1.1` Roadmap)
$$\text{MemoryAdmissible} = \text{BlockIntegrityValid} \land \text{ProvenanceValid} \land \text{EpochFresh} \land \text{GrantScopeValid}$$

$$\text{IsStale} \iff (t_{\text{current}} - t_{\text{source}} > \text{TTL}) \lor (\text{Epoch}_{\text{policy}} \neq \text{Epoch}_{\text{active}}) \lor (\text{Epoch}_{\text{source}} \neq \text{Epoch}_{\text{source\_active}}) \lor \text{IsRevoked}(\text{Channel}_{\text{rev}})$$

* **`BlockIntegrityValid`**: Cryptographic hash check over the restored KV block or canonicalized workspace payload.
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
- Treats the boundary, policy engine, executor, and audit log as high-value attack surfaces requiring minimal privilege, zero-I/O evaluation, and strict isolation.
