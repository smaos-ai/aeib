# AEIB — Evidence Manifest (`v1.0.0-rc.2` Review Candidate / `v1.0.0-rc.3` Prepared Target)

## Thesis & Bounded Claim
> **AEIB v1.0.0-rc.2 at commit `7bfd43dc` is ready for external review of its bounded dispatch-boundary evidence bundle. It provides pinned manifests, pre-dispatch standing checks, explicit uncertain-transport classification, bounded reconciliation, RFC 8785 + Ed25519 receipts, and 14/14 Java/Python verifier-vector parity under the stated model. Gate 5 separate-party reproduction remains pending.**
>
> **Bounded Scope:** *AEIB provides a reproducible evidence bundle for a bounded dispatch-boundary claim: pinned manifests, pre-dispatch standing checks, explicit uncertain-transport handling, bounded reconciliation, RFC 8785 + Ed25519 receipts, and verifier parity for the supplied vectors. It does not prove model trustworthiness, universal exactly-once effects, regulatory compliance, or complete governance.*
>
> **Release Tag Policy (Operationally Immutable):** *Release-candidate tags are operationally immutable under the project’s release policy. The project must not delete, force-move, or re-tag a published release candidate. If the candidate changes, create a new tag (e.g., `v1.0.0-rc.3`).*

```text
One manifest = one tag = one commit = one artifact set.
Do not mix tag evidence with working-tree evidence.
Do not present historical NEG hashes as rc.2 proof.
Do not claim the boundary halts arbitrary agents.
Do not force-move a published release candidate.
Gate 5 completes only after separate-party reproduction.
```

---

## Source Provenance
```yaml
target_release: v1.0.0-rc.2
commit_sha: 7bfd43dcc27f741d04a67500abf1bc3b2a5888c4
branch: release/v1.0-review-candidate
tag_ref: v1.0.0-rc.2
slsa_provenance_bundle: aeib-reproducibility/evidence/v1.0.0-rc.2/multiple.intoto.jsonl
slsa_bundle_sha256: f84ebe8d8f41656ee0deb63ad0ab38432e4c601b465d5a6381e48225653fbf67

# Prepared working-tree version identity for next immutable candidate tag (v1.0.0-rc.3):
prepared_next_candidate:
  target_release: v1.0.0-rc.3
  gradle_project_version: 1.0.0-rc.3
  artifact: aeib-verifier-1.0.0-rc.3.jar

hosted_ci_runs_green:
  - 38248861219  # AEIB Release & Provenance, v1.0.0-rc.2 (tag)
  - 38248861416  # AEIB v1.0 Minimal CI Baseline, v1.0.0-rc.2 (tag)
  - 38248861063  # AEIB RC Verification and Provenance, v1.0.0-rc.2 (tag)
  - 38248086522  # AEIB v1.0 Minimal CI Baseline, 7bfd43dc (branch)
  - 38248086315  # AEIB RC Verification and Provenance, 7bfd43dc (branch)

historical_ci_evidence:
  rc1_commit: cea4b5c9800902b043eb085a74cc3697a5161f5b
  rc1_runs:
    - 38211901816
    - 38211901792
    - 38211901499
    - 38211899056
    - 38211898969
  rc1_tag_commit: addfe3cad550baffe3500394723c9b746e34e802
  rc1_tag_runs:
    - 38246098060
    - 38246098049
    - 38246097748
    - 38246094658
    - 38246094308
```

## Build Environment & Dependency Identity
```yaml
jdk_version:               21 (Eclipse Adoptium Temurin / OpenJDK)
container_image:           gradle:8.5-jdk21 (eclipse-temurin:21-jdk base)
gradle_version:            8.5
rc2_tag_gradle_version:    1.0.0-rc.1 (declared in aeib-native-runtime/build.gradle at commit 7bfd43dc; tag v1.0.0-rc.2 is an evidence-calibration tag that emits aeib-verifier-1.0.0-rc.1.jar)
rc3_working_tree_version:  1.0.0-rc.3 (updated in aeib-native-runtime/build.gradle and .github/workflows/*.yml so v1.0.0-rc.3 emits aeib-verifier-1.0.0-rc.3.jar)
gradle_wrapper_sha256:     d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd
distributionSha256Sum:     9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026
verification_metadata_xml: 96126b5696e4b325ae3f98da9d29a3ae76a6dc53c36da5f894c2ddbe14ffb075
gradle.lockfile_sha256:    32c18865f15ccad306d20447fee69d3e20022180985d3f5cdd4f564e3c363697
tests_lockfile_sha256:     e195c95e7c4a33e3688c59086ef9cc3e0ed270dc73389d0aba1e9162ae119d64
verifier_lockfile_sha256:  ee7b426936710b537ae94777d025a594f93fdc2177179506342ea04aa9ea07e9
```

## Separated Test Evidence Counts
```text
RC.2 tag evidence: 56/56 Python tests at commit 7bfd43dc.
Post-rc.2 working-tree evidence: 62/62 Python tests, not attributable to tag v1.0.0-rc.2 until committed, tagged, and re-run in hosted CI.
```

```yaml
jvm_suite:
  task:           :test (:aeib-tests:test, :aeib-verifier:test)
  passed:         20
  failed:         0
  skipped:        0
  junit_xml_paths_and_rc2_sha256:
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.DomainRecordsTest.xml (7 passed; sha256=0b8b54d1323ffd5806e6539050a72ffd966218a39dce515c387419977f2d11bb)
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Gate4IntegrationTest.xml (1 passed; sha256=5e737b990eaa79e9678dcb0878cc0775371e4cd43ff54a8cb1e48be200996284)
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.MandatoryNegativeTestSuite.xml (4 passed; sha256=ba327407201df25beac60cd4706b1fcbc179aeb81ebb8d2b1dcb4d62d283744b)
    - aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Station2ConcurrencyTest.xml (1 passed; sha256=ed2145135176809b4c8c1f7743173f04785edc5c94dc795fa1108bc618df58ad)
    - aeib-native-runtime/aeib-verifier/build/test-results/test/TEST-com.aeib.verifier.VerifierCliTest.xml (7 passed; sha256=a262ee61988f4a7f3d69fe402736cc4bba4f2c13381aeba48c59bb6bb743de04)
differential_verifier_suite:
  command:        python3 benchmarks/jvm_native_diff_engine.py
  vectors_passed: 14 / 14
  jcs_divergence: 0 bytes
cli_negative_vector_suite:
  cases_passed:   5 / 5 (exit codes 0, 2, 3, 3, 1)
python_governance_protection_falsifiability_suite:
  rc2_tag_evidence_7bfd43dc:      56 / 56 passed (0 failed)
  post_rc2_working_tree_evidence: 62 / 62 passed (0 failed; not attributable to tag v1.0.0-rc.2)
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

```text
All NEG-01–NEG-08 scenarios were re-executed at rc.2 commit 7bfd43dc (and verified in the post-rc.2 working tree).
NEG evidence status: NEG-01–NEG-06 and NEG-08 receipt hashes are identical between rc.1 (addfe3ca), rc.2 (7bfd43dc), and the current working tree. At rc.2 commit 7bfd43dc, NEG-07 hashed the legacy disposition string "COMPENSATED" (4d2e45f7b8e34b1e1811d3eea38325738ce984a8d7aaa89a21d610fff115d526); in the post-rc.2 working tree (prepared for v1.0.0-rc.3), NEG-07 hashes "COMPENSATED_RECORD_RECORDED" (64226b3467504d1474dee66a61fe0fae9f129fd36d3807204c38279801d733fa). Historical results are retained and do not backfill or certify future tag behavior.
```

| Scenario ID | Test Input Vector | Enforcing Boundary / Reconciler | Expected Disposition | Observed Disposition | RFC 8785 JCS + Ed25519 Receipt SHA-256 | Evidence Attribution |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NEG-01** | MCP Tool-List Poisoning | `Station0AdmissionGate` + `TypedOwaspPreDispatchGate` | `BLOCKED` | `BLOCKED` | `b52a9860cb163a77307e790cb509de8021937dd011047ec306cfee8146520d70` | Re-executed at `rc.2` (`7bfd43dc`) |
| **NEG-02** | Tool-Response Injection | `ForkAndFlushContextBoundary` | `BLOCKED` | `BLOCKED` | `4b0b50d41448ff9935237b2e67075dcb35b21d4440ae62b4a5eaafc452a1ec23` | Re-executed at `rc.2` (`7bfd43dc`) |
| **NEG-03** | RAG / Source Substitution | `TemporalMemoryDigest` (`STALE_DONT_TRUST_YET`) | `BLOCKED` | `BLOCKED` | `09a18d03cd702622bb9a782d1ad706b97f3c439649b566a837d50153ee3078f8` | Re-executed at `rc.2` (`7bfd43dc`) |
| **NEG-04** | Stale Grant Replay | `Station1DispatchInterlock` + `PAD016HeartbeatChain` | `BLOCKED` | `BLOCKED` | `1b6f6a04c746b7b2133caadd9fc7add762974bf8b5c16902851d2f1c751e1bfd` | Re-executed at `rc.2` (`7bfd43dc`) |
| **NEG-05** | Compromised-Agent Replay w/ Valid Key | `LicitraSentryProxyGate` (Single-Use Ticket Burn) | `HOLD` | `HOLD` | `499b917972fffd8b04d90d6b691aeda0cbf84a7d38048b5216ea813093cf243f` | Re-executed at `rc.2` (`7bfd43dc`) |
| **NEG-06** | Target-Endpoint Delay / Spoofing | `Station2EffectReconciler` + `AntiSpecGamingReconciler` | `EFFECT_INDETERMINATE` | `EFFECT_INDETERMINATE` | `6fffed6106e4113f77b17059a503f788003beca97f59b544ccbbf4bea45dc62e` | Re-executed at `rc.2` (`7bfd43dc`) |
| **NEG-07** | Partial Write w/ Reconciler Failure | `SagaReconciler` (Eventual Consistency Queue) | `COMPENSATED_RECORD_RECORDED` | `COMPENSATED_RECORD_RECORDED` | `4d2e45f7b8e34b1e1811d3eea38325738ce984a8d7aaa89a21d610fff115d526` (`7bfd43dc` `"COMPENSATED"`) / `64226b3467504d1474dee66a61fe0fae9f129fd36d3807204c38279801d733fa` (post-`rc.2` `"COMPENSATED_RECORD_RECORDED"`) | `4d2e45f7…` at `rc.2` (`7bfd43dc`); `64226b34…` in post-`rc.2` working tree |
| **NEG-08** | Rollback During Open Saga | `Station3ContinuousLedger` (`ContinuityReceipt`) | `RECORDED_FAILURE` | `RECORDED_FAILURE` | `f1c924f55217ec2af557d01b9c5562cd669fdb7edb86db151a797730c9a21bd5` | Re-executed at `rc.2` (`7bfd43dc`) |

> **Evidence Status**: The `NEG-01`–`NEG-08` rows above were generated by the deterministic Python adversarial test harness (`tests/test_unified_governance_stack.py::test_formal_memory_admissibility_equation_and_adversarial_negative_ledger`) using fixed Ed25519 test keys (`_key(0x42)` / `_key(0x99)`). They verify code-level rejection and receipt-binding behavior under the stated test model; they are not external production incident logs. Historical results are retained for continuity and do not backfill, replace, or certify future tag behavior.

* **Operational Meaning of `HOLD` (`NEG-05`):** `HOLD` means AEIB withheld dispatch pending an explicit authorization decision (because the single-use ticket for that operation was already consumed). It does not mean AEIB detected key compromise, revoked the key, or prevented all future use of the key on new authorized tickets.
* **Operational Meaning of `COMPENSATED_RECORD_RECORDED` (`NEG-07`):** AEIB recorded a compensation intent or compensation evidence path in its local ledger. It does not establish that an external target accepted, executed, or completed a compensating action.

## Release Artifact Hashes (`v1.0.0-rc.2` Commit `7bfd43dc`, Hosted Run `38248861416`, SHA-256)
```yaml
# Note on JAR filename at commit 7bfd43dc (v1.0.0-rc.2):
# aeib-native-runtime/build.gradle line 8 declares version = '1.0.0-rc.1' at commit 7bfd43dc,
# so building tag v1.0.0-rc.2 emits aeib-verifier-1.0.0-rc.1.jar (attested in multiple.intoto.jsonl).
rc2_verifier_jar_filename:     aeib-verifier-1.0.0-rc.1.jar (built from tag v1.0.0-rc.2 / commit 7bfd43dc)
rc2_verifier_jar_sha256:       4e448ce23f02c3b45db51c268760b8261a4c70078e85ebf3d7ebeb7436f9b5e7 (reproducible Build 1 == Build 2 == Hosted Run 38248861416, 0 B divergence)
rc2_bin_aeib_verifier_sha256:  75e44a96f9f32a7291fa256ae5f02d237209da0af91edbe0e3195b88e42bdc70
rc2_hosted_bom_json_sha256:    65b1074941a264999a65d0cc27d9897bbf33c9bfcf36164605f7887bcfa1fe5d
rc2_slsa_intoto_jsonl_sha256:  f84ebe8d8f41656ee0deb63ad0ab38432e4c601b465d5a6381e48225653fbf67
rc2_receipt_spec_md_sha256:    131d2d4a7fc73f7079ed57905b16370ccbddac8762cd4763fa580b0085c67c3a
rc2_diff_engine_py_sha256:     b843d048016fb27a7b4ee115349e5161bcb5c74fad4d5c44999fc840e90f3bcd
rc2_hosted_gate4_receipt_json: 07c6d95e1424f53f99bdab783019314ecd30098b19a1966ef06b15d5d077219c
rc2_hosted_gate4_pubkey_pem:   86476dc05e0edcf5b6fcf08da564c1cfd73da03aae8cde26d3d1f7b0d9973853
smaos_wasm_verifier_bg.wasm:   ddd27bc8485e108670b92c33f886d7913e6175a1efa981926eaf1bd9f26a8960
smaos-verify.html:             eecab838785ac4f5796736536c98db37ecd3356a0d103c61be84200f9a53e030
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
    git verify-tag v1.0.0-rc.2

  hosted_ci:
    - Inspect runs 38248861219, 38248861416, and 38248861063.
    - Confirm each run is associated with commit
      7bfd43dcc27f741d04a67500abf1bc3b2a5888c4
      and concluded successfully.

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

  artifact_verification_rc2:
    # Historical rc.2 artifact (at commit 7bfd43dc where build.gradle declared version = '1.0.0-rc.1'):
    command: sha256sum aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.1.jar
    expected: 4e448ce23f02c3b45db51c268760b8261a4c70078e85ebf3d7ebeb7436f9b5e7

  artifact_verification_rc3:
    # Candidate rc.3 artifact (where build.gradle declares version = '1.0.0-rc.3'):
    command: sha256sum aeib-native-runtime/aeib-verifier/build/libs/aeib-verifier-1.0.0-rc.3.jar
    expected: <emitted-by-hosted-ci-run-on-rc.3>
```

## 5-Gate Release Protocol Status

| Gate | Requirement | Evidence / Artifact | Bounded Status |
| :--- | :--- | :--- | :--- |
| **Gate 1: Hosted CI Execution** | Hosted GitHub Actions runners report `success` on tag-triggered CI runs | Tag runs `38248861219`, `38248861416`, `38248861063` (plus branch runs `38248086522`, `38248086315`) on `7bfd43dcc27f741d04a67500abf1bc3b2a5888c4` | **`VERIFIED for the three tag-triggered CI runs`** |
| **Gate 2: Verifier Parity** | Java 21 (`ReceiptVerifier`) & Python 3 (`jvm_native_diff_engine.py`) parity | `14/14` receipt vectors matched with `0 B` RFC 8785 JCS divergence + Wycheproof/ZIP-215 & Cyberphone vectors | **`VERIFIED for the 14 supplied differential verifier vectors`** |
| **Gate 3: Supply Chain Attestation** | CycloneDX 1.6 SBOM + SLSA v1.1-compatible provenance + `verification-metadata.xml` | `bom.json` (`65b10749...`), `aeib-reproducibility/evidence/v1.0.0-rc.2/multiple.intoto.jsonl` (`f84ebe8d...`), `VERIFY_RELEASE.md`, `gradle/verification-metadata.xml` | **`VERIFIED for artifact presence and stated checks; SLSA level claim requires explicit basis`** |
| **Gate 4: Manifest Completion** | `EVIDENCE_MANIFEST.md` populated with adversarial ledger (`NEG-01`–`NEG-08`) & Category A–E calibration | [`EVIDENCE_MANIFEST.md`](EVIDENCE_MANIFEST.md) + [`TPRM_BUYER_SECURITY_AND_COMPLIANCE_PACK.md`](docs/TPRM_BUYER_SECURITY_AND_COMPLIANCE_PACK.md) | **`COMPLETE for v1.0.0-rc.3 manifest requirements`** |
| **Gate 5: Separate-Party Reproduction** | Independent clean-room reproduction outside author environment | Container harness (`scripts/run_live_container_verification.sh`) verified locally; external third-party sign-off tracked separately | **`PENDING — READY FOR EXTERNAL REPRODUCTION`** |

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
- Does **NOT** verify retrieval-source provenance or RAG document authenticity in `v1.0.0-rc.2` / `v1.0.0-rc.3`.
- Does **NOT** claim universal exactly-once side-effects on uncooperative target APIs.
- Does **NOT** provide external SCITT transparency ledger anchoring in `v1.0.0-rc.2` / `v1.0.0-rc.3`.
- Does **NOT** implement automatic public key lookup or PKI discovery (caller must supply the pinned SPKI public key).
- Does **NOT** claim ISO 42001, EU AI Act, SOC 2, or DORA regulatory compliance out of the box.
- Positions **LuMay AI Framework** strictly as an 8-layer governance taxonomy reference (AEIB contributes evidence for narrow subsets of Layer 6 *Controls* and Layer 7 *Monitoring & Audit* only).
- **Context Mode Reference:** AEIB does not incorporate Context Mode code or distribute it under AEIB. Context Mode is treated as an architectural reference only, subject to license and dependency review before any future integration.
- Treats the boundary, policy engine, executor, and audit log as high-value attack surfaces requiring minimal privilege, zero-I/O evaluation, and strict isolation.
- **Context vs. Validation & The Mirroring Rule:** External regulatory signals (MAS Guidelines, NIST SP 800-18r2, EU AI Act, DORA) and industry frameworks (OWASP AIBOM, `iFixAi`, Microsoft AGT, UK AI Safety) illustrate complementary enterprise demand for runtime evidence; they do not validate AEIB, establish mandatory requirements for AEIB, or alter the release scope. *"If the manifest cannot overclaim, the commentary about the manifest cannot either."*

## Epistemic Alignment on External Signals & `v1.1` Backlog Prerequisites
* **Athena:** Persistent-state/reasoning layer context; AEIB operates strictly as the wire dispatch boundary.
* **USB Rubber Ducky:** Endpoint/physical-access control context; physical host compromise invalidates higher software layers, but does not alter AEIB's wire-boundary scope.
* **Governed Intelligence Systems:** Peer context for out-of-model 4-station/hash-chain architectures; cognitive alignment ("moral substrate") is explicitly rejected.
* **MIT AI Risk Initiative (Broad Landscape Context):** Expert-elicitation risk taxonomy covering catastrophic and societal concerns; provides general risk background only; does not evaluate AEIB, specify runtime controls, or establish that AEIB mitigates listed risks; strictly excluded from capability claims.
* **OECD Artificial Intelligence Papers No. 65 (Practitioner-Acknowledged Gap):** Empirical observation across sectors confirming agentic AI is in production while governance, oversight, and accountability frameworks remain immature; documents that the governance gap is real, urgent, and practitioner-acknowledged at an intergovernmental level; describes the problem space; does not endorse or specify AEIB as the solution.
* **David Marques — Agent Harness Anatomy (Architectural Reference):** Source-grounded, commit-linked teardown of 9 production agent harnesses (`pi`, `aider`, `Cline`, `Goose`, `Codex CLI`, `OpenHands`, `OpenCode`, `Hermes`, `OpenClaw`); validates the "harness is where the design lives" principle; informs AEIB's v1.1 Gateway Adapter research (Codex CLI and OpenHands as primary approval-gate analogues).
* **Buyer-Safe Boundary Formulation:**
  > *These artifacts provide context and design references. The OECD report documents practitioner-recognized governance needs; the harness teardowns offer source-grounded architectural comparisons across 9 production harnesses; the MIT report provides broad risk taxonomy. None validates AEIB, establishes market demand for AEIB, or changes the `v1.0.0-rc.3` scope.*
* **Frozen Release Baseline Invariant:**
  ```text
  The evidence remains the work: hosted CI, reproducible artifacts, 
  verifier vectors, benchmark evidence, and separate-party Gate 5 reproduction.
  ```
* **Refused Concepts:** Theological/mystical vocabulary, moral agency claims, cognitive-layer enforcement, and unfalsifiable AI-generated topology diagrams.
* **`v1.1` Backlog Prerequisites:** Trust anchor rotation, per-operation truth trail (`GET /operations/{opId}/trail`), declared enforcement levels (`STRICT_FAIL_CLOSED`, `AUDIT_ONLY`, `DEGRADED_PERMITTED`), and constitutional amendment logging require explicit schemas and transition rules prior to implementation.
* **Containment vs. Action Governance (Operational Allocation):**
  - **LiteBox / OS Containment:** L2–L4 system-call interception and host attack-surface reduction. Evaluates binary allow/deny on low-level OS operations (file paths, sockets, kernel interface). Emits ephemeral host logs. Experimental lifecycle (v0.1.0; interfaces subject to change).
  - **AEIB Wire Governance:** L7 consequential action authorization, transport ambiguity latching (`EFFECT_INDETERMINATE`), bounded reconciliation (`ProbeBudget: 1`), and RFC 8785 canonical, Ed25519-signed `ContinuityReceipt` linear hash chains.
  - **Key Distinction:** Containment constrains *where and how* code runs on the host OS; AEIB determines *whether a specific consequential action may take place* across the network wire and records verifiable evidence of the outcome.
* **Sandbox Interaction Topologies (Inside, Beside, Outside):**
  - **Option 1: Inside Sandbox (REJECTED):** Running AEIB inside the guest/container alongside the agent shares the compromise and crash failure domain; rejected for high-consequence actions.
  - **Option 2: Beside Sandbox (RECOMMENDED Sidecar Pattern):** The agent executes inside the sandbox (LiteBox, microVM, container); network access is restricted exclusively to a local IPC or loopback channel routed to an out-of-process AEIB sidecar. LiteBox enforces syscall/kernel confinement; AEIB evaluates semantic action authorization, commits pre-dispatch intent, opens the external socket, and handles transport ambiguity.
  - **Option 3: Hypervisor Edge (MULTI-TENANT):** AEIB sits at the host hypervisor egress gateway (Firecracker / gVisor host), intercepting guest virtual network traffic to govern external API writes across multiple sandboxed worker instances.
* **Codified Epistemic Corrections:**
  - *"Containment is a major, actively evolving agent-security concern across cloud platforms."* (Replaces claims of containment commoditization).
  - *"Platform vendors are developing diverse, often experimental containment and isolation primitives."* (Replaces category saturation claims).
  - *"Rust is increasingly utilized in security-sensitive systems programming (e.g., LiteBox), but does not constitute an industry-wide standard."*
  - *"Containment and action governance are complementary, requiring explicit separation of concerns for network egress, credentials, and syscall handling."*
  - *"Hardware-backed CVM attestation (such as AMD SEV-SNP or Intel TDX) is a candidate research profile; key custody and quote verification are not verified in v1.0."*
  - *"AEIB targets a specific, narrow combination of pre-dispatch intent binding, transport ambiguity latching, and offline-verifiable receipts."*
* **v1.1 Research Candidates:**
  - *Sandbox Deployment Profile:* Define a formal integration specification for deploying AEIB alongside sandboxed runtimes (LiteBox, Firecracker, gVisor), detailing socket-delegation boundaries and credential isolation.
  - *Confidential Computing Scaffolding:* Formalize key-custody models, measurement bindings, and quote-verification requirements before making claims regarding hardware enclave attestation.

## Financial & Transport Ambiguity Contract
```text
1. No financial action without a declared idempotency contract.
2. No blind retry after an uncertain mutating dispatch.
3. No guessed reconciliation status without an authenticated target endpoint.
```

* **`EFFECT_INDETERMINATE` Latching:** For an AEIB-governed mutating dispatch with an ambiguous transport outcome (`HTTP_504`, `TCP_RST`, `BLACKHOLE_DROP`, `TIMEOUT`), AEIB classifies the disposition as `EFFECT_INDETERMINATE`, sets `retry_safe` to `false`, and blocks automated retry through the AEIB-governed path.
* **Single-Probe Reconciliation (`ProbeBudget: 1`):** Probes the target status endpoint at most once over an authenticated interface using the declared idempotency-key contract; UUID v4 is the recommended key format where supported by the target (`idempotencyKeyDigest`). Resolves to `CONFIRMED` or `REFUTED` only upon authenticated target evidence; otherwise transitions to `CONFLICT` or remains `EFFECT_INDETERMINATE` for human step-up.
* **Append-Only Recovery Lineage:** Failover or recovery attempts append linked records (`originalOperationId` $\rightarrow$ `recoveryActionId` chained via `prevChainTip`). They do not edit, backfill, or delete historical uncertain receipts. Tamper-evidence and completeness depend on ledger integrity, signing-key custody, replication, and the deployment trust model.
* **Privacy by Design:** Receipts store cryptographic digests (`idempotencyKeyDigest`, `evidenceDigest`) and UUID references rather than raw credentials, account identifiers, card data, full idempotency keys, or sensitive enterprise payloads.

## The 3 Terminal Release Rules
```text
1. One manifest = one tag = one commit = one artifact set.
2. No blind retry after an uncertain mutating dispatch through the AEIB-governed path.
3. Gate 5 completes ONLY after separate-party reproduction.
```

---

## v1.1 Prototype Workstream & Governed Financial Action Boundary Evidence (Track B & C)

> **Two-Track Release Separation Directive:**  
> The artifacts and test evidence in this section represent physical prototype modules, evaluation test suites, and compliance documentation belonging to **Track B** (`v1.1-roadmap/`) and **Track C** (`docs/compliance/`). Per the project's release policy, these modules are strictly decoupled from the frozen `v1.0` release baseline and candidate tag `v1.0.0-rc.3`. They are evaluated under their stated simulation models and are not claimed as frozen v1.0 release artifacts.

### 1. Prototype Component & Verification Summary

| Component | Physical File Location | Test Suite | Test Results | Status |
| :--- | :--- | :--- | :---: | :---: |
| **Governed Financial Action Boundary** | `v1.1-roadmap/governed_financial_action_boundary.py` | `tests/test_governed_financial_action_boundary.py` | 13 / 13 passed | `INTEGRATED` |
| **Production Readiness Chaos Harness** | `v1.1-roadmap/production_readiness_chaos_harness.py` | `tests/test_production_readiness_chaos_harness.py` | 19 / 19 passed | `EVALUATED` |
| **Durable Dispatch Executor (EO-1)** | `v1.1-roadmap/tier1_durable_executor.py` | `tests/test_tier1_durable_delivery_contract.py` | 9 / 9 passed | `PROTOTYPE` |
| **Aggregate Probe Scheduler** | `v1.1-roadmap/aggregate_probe_scheduler.py` | `tests/test_tier1_aggregate_probe_scheduler.py` | 7 / 7 passed | `PROTOTYPE` |
| **Real MCP Wire Adapter** | `v1.1-roadmap/real_mcp_wire_adapter.py` | `tests/test_tier2_real_mcp_wire_adapter.py` | 7 / 7 passed | `PROTOTYPE` |
| **Multi-Hop Delegation Verifier** | `v1.1-roadmap/delegation_chain_verifier.py` | `tests/test_tier2_delegation_and_profile.py` | 5 / 5 passed | `PROTOTYPE` |
| **Signed Deployment Profile** | `v1.1-roadmap/signed_deployment_profile.py` | `tests/test_tier2_delegation_and_profile.py` | 2 / 2 passed | `PROTOTYPE` |
| **RFC 9052 COSE_Sign1 Profile & CBOR** | `v1.1-roadmap/rfc9052_cose_profile.py` | `tests/test_tier3_rfc9052_cose_interop.py` | 52 / 52 passed | `PROTOTYPE` |
| **OpenTelemetry Semantic Bridge** | `v1.1-roadmap/telemetry_correlation_bridge.py` | `tests/test_tier3_telemetry_and_checkpoints.py` | 4 / 4 passed | `PROTOTYPE` |
| **External Checkpoint Anchor** | `v1.1-roadmap/external_checkpoint_anchor.py` | `tests/test_tier3_telemetry_and_checkpoints.py` | 7 / 7 passed | `PROTOTYPE` |
| **EU Compliance Evidence Pack** | `docs/compliance/EU_COMPLIANCE_EVIDENCE_PACK.md` | Verification Scanners | Verified | `DELIVERED` |
| **Live Financial Boundary Demo** | `scripts/run_financial_boundary_demo.py` | Terminal Execution (6 Acts) | Exit Code 0 | `EVALUATED` |
| **Combined Track B Test Suite** | — | `tests/test_tier*.py`, `tests/test_governed*.py` | **125 / 125 passed** | `EVALUATED` |

### 2. Production Readiness Chaos Benchmark Evidence (18 Failure Scenarios)
```yaml
benchmark_harness:             v1.1-roadmap/production_readiness_chaos_harness.py
scenarios_evaluated:           18 / 18 passed (0 failed)
duplicate_governed_dispatches: 0 (Strictly zero duplicate mutations on target ledger)
blind_retries_detected:        0 (Zero blind retry storms across governed boundary)
authorization_latency_p50:     0.0 µs (Sub-microsecond static in-memory lookup)
authorization_latency_p95:     0.0 µs
e2e_action_latency_p50:        1.6 ms
receipt_verification_time:     294.58 µs (Ed25519 + RFC 8785 JCS offline verification)
total_storage_footprint:       19,067 bytes
```

### 3. Core Operational Invariants Observed:
1. **Zero Duplicate Governed Dispatch:** Target-side authoritative ledger commit count matches declared contract across nominal, transport-dropped, and crash-recovery executions.
2. **Preserved Uncertainty:** When target status is unavailable (`HTTP 503` or timeout during probe), `PRESERVED_UNCERTAINTY` is latched with `retry_safe: false`.
3. **ProbeBudget Invariant:** Out-of-band reconciliation is strictly bounded to `ProbeBudget: 1`. No runaway probing occurs.
4. **Crash Recovery Resynchronization:** Mid-syscall and post-commit process crashes recover clean state upon restart without re-dispatching duplicate mutations.
5. **Offline Verifiability:** All emitted receipts verify offline with zero network egress using pinned public keys.


