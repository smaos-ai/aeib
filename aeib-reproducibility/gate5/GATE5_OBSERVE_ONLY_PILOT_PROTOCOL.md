# AEIB Gate 5: Single-Tenant Observe-Only Pilot Protocol (`v1.0.0-rc.1`)

- **Target Release Reference:** `v1.0.0-rc.1` (`b2166a3ffc8f9535a4299dac382dad12ffce85ec`)
- **Current Gate 5 Status:** **NOT STARTED (QUEUED POST-GATE 3)**
- **Prerequisite Blocker:** Gate 3 independent reproduction (`third_party_verification_transcript.txt` produced by a separate operator or independent CI runner from the signed tag `v1.0.0-rc.1`) must close before Gate 5 execution begins.

> **Epistemic Boundary Notice:**  
> *Do not claim operational or pilot readiness until every checklist item in this protocol is executed, evidenced, and signed off by a named design partner.*  
> Gate 5 evaluates operational integration in a bounded, single-tenant, observe-only shadow topology under the stated model. It does not establish universal exactly-once execution across uncooperative targets, external SCITT anchoring, automatic key lookup, memory/retrieval provenance, or regulatory compliance.

---

## 1. Gate 5 Entry Criteria (Prerequisites)

Gate 5 cannot be initiated until all four prior gates are verified:

| Prerequisite Gate | Required Artifact / Evidence | Status |
| :--- | :--- | :--- |
| **Gate 1 — Working Core** | Hosted CI run [`38055110173`](https://github.com/smaos-ai/aeib/actions/runs/38055110173) (`./gradlew clean test --no-daemon`) | **Passed** |
| **Gate 2 — Reproducible Artifacts** | [SLSA_INPUT_CONTRACT.md](file:///Users/andriileukhin/Documents/SovereignNexus/aeib-reproducibility/slsa/SLSA_INPUT_CONTRACT.md), [bom.json](file:///Users/andriileukhin/Documents/SovereignNexus/aeib-reproducibility/evidence/v1.0.0-rc.1/bom.json), [gradle.lockfile](file:///Users/andriileukhin/Documents/SovereignNexus/aeib-reproducibility/evidence/v1.0.0-rc.1/gradle.lockfile), [multiple.intoto.jsonl](file:///Users/andriileukhin/Documents/SovereignNexus/aeib-reproducibility/evidence/v1.0.0-rc.1/multiple.intoto.jsonl) | **Passed in Hosted CI** |
| **Gate 4 — Real-Target Fault Injection** | Hosted CI run [`38055279949`](https://github.com/smaos-ai/aeib/actions/runs/38055279949) & [verifier_transcript.txt](file:///Users/andriileukhin/Documents/SovereignNexus/aeib-reproducibility/evidence/v1.0.0-rc.1/verifier_transcript.txt) (`1 mutation, 1 dispatch, 1 probe, 0 retry mutations`; valid exit `0`, tampered exit `2`) | **Passed** |
| **Gate 3 — Independent Reproduction** | `third_party_verification_transcript.txt` executed from signed tag `v1.0.0-rc.1` under `network_mode: none` by a separate party | **Pending (Entry Blocker)** |

---

## 2. Written Pilot Scope & Architecture (`Observe-Only` Mode)

### 2.1 Single-Tenant Boundary
- **Tenant Isolation:** Deployed for exactly one designated single-tenant workflow in a non-blocking shadow/observe-only path.
- **Target API Class:** One bounded mutating HTTP endpoint paired with one read-only status/reconciliation endpoint (`TargetStatusClient`) supporting `Idempotency-Key` lookup.
- **No Inline Mutation Blocking During Initial Shadow Window:** In observe-only mode, AEIB evaluates candidate payloads, computes RFC 8785 `CAID` digests, records `EFFECT_INDETERMINATE` transport observations, runs bounded read-only status probes (`ProbeBudget`), and emits detached Ed25519 `ContinuityReceipt` envelopes out-of-band without altering or delaying the primary application response path.

### 2.2 Pinned Runtime Configuration
- **Station 0 (`Station0AdmissionGate`):** Pinned manifest SHA-256 digest loaded from local read-only disk (zero external I/O).
- **Station 1 (`Station1DispatchInterlock`):** Stateless RFC 8785 JCS canonicalization (`ALGORITHM_ID = "RFC 8785 JCS"`).
- **Station 2 (`Station2EffectReconciler`):** Configured with explicit `ProbeBudget`:
  - `maxConcurrentProbes`: `4`
  - `maxProbesPerMinute`: `60`
  - `probeTimeout`: `2000 ms`
  - `reconciliationDeadline`: `+10000 ms` from fault observation
- **Station 3 (`Station3ContinuousLedger`):** Single-algorithm `Ed25519` (RFC 8032) signing over canonical statement bytes with an explicit `keyId` and exported SPKI public key (`ledger-public.pem`).
- **Station 4 (`VerifierCli`):** Scheduled out-of-band verification of emitted receipts against the caller-supplied `ledger-public.pem` (asserting exit code `0`).

---

## 3. Mandatory Operational Drills

### Drill A — Kill-Switch Verification Drill
**Objective:** Verify that an operator can immediately bypass and disable AEIB shadow interception and Station 2 status probing without restarting the host application or dropping primary tenant traffic.

1. **Trigger Mechanism:** Toggle the runtime kill-switch control flag (`AEIB_OBSERVE_KILLSWITCH=1` / administrative circuit-interlock latch).
2. **Expected Observations:**
   - Station 2 `Station2EffectReconciler` immediately halts new `TargetStatusClient` probe dispatches (`activeProbes` drained/cancelled).
   - Primary application requests continue with zero added latency or error rate perturbation.
   - Time-to-disengage (`T_disengage`) measured from operator toggle to last observed probe is recorded (target threshold: `< 1000 ms`).
3. **Required Evidence Artifact:** `gate5_killswitch_drill_log.txt` containing timestamps, before/after probe counters, and primary traffic error-rate telemetry.

### Drill B — Rollback Procedure Drill
**Objective:** Verify that the AEIB runtime adapter and verifier distribution can be cleanly rolled back or removed, restoring the pre-pilot baseline configuration with zero residual state corruption.

1. **Execution Steps:**
   - Engage kill-switch (`AEIB_OBSERVE_KILLSWITCH=1`).
   - Detach the AEIB observe-only hook / sidecar configuration and restore the previous deployment manifest.
   - Archive emitted `ContinuityReceipt` files and `ledger-public.pem` to immutable cold storage and verify the final receipt chain tip offline via `aeib-verifier`.
2. **Expected Observations:**
   - Application health checks pass continuously throughout rollback.
   - Final exported receipt batch passes offline `aeib-verifier` check (`exit_code = 0`).
   - Elapsed rollback duration (`T_rollback`) is recorded (target threshold: `< 5 minutes`).
3. **Required Evidence Artifact:** `gate5_rollback_drill_log.txt` with command sequence, elapsed duration, and post-rollback health check output.

---

## 4. Gate 5 Execution Checklist

```text
[ ] Confirm Gate 3 is closed (third_party_verification_transcript.txt committed and verified).
[ ] Select single-tenant observe-only pilot environment and target workflow.
[ ] Define and countersign written pilot scope (target endpoints, ProbeBudget bounds, observation window).
[ ] Deploy AEIB v1.0.0-rc.1 (commit b2166a3f) in observe-only mode.
[ ] Verify offline ContinuityReceipt generation and Station 4 verification (exit code 0).
[ ] Execute Drill A: Kill-switch drill and record gate5_killswitch_drill_log.txt.
[ ] Execute Drill B: Rollback procedure test and record gate5_rollback_drill_log.txt.
[ ] Obtain named design-partner sign-off (gate5_partner_signoff.md).
[ ] Do not claim operational pilot completion until all items above are complete.
```

---

## 5. Design-Partner Sign-Off Template (`gate5_partner_signoff.md`)

Once all drills and the observation window conclude, the designated partner reviewer completes the following record:

```text
=== AEIB v1.0.0-rc.1 GATE 5 OBSERVE-ONLY PILOT SIGN-OFF ===
Design Partner Organization : <Organization Name>
Reviewer Name & Title       : <Full Name, Role>
Evaluated Release Tag       : v1.0.0-rc.1 (b2166a3ffc8f9535a4299dac382dad12ffce85ec)
Observation Window (UTC)    : <Start ISO-8601> to <End ISO-8601>
Deployment Mode             : Single-Tenant Observe-Only

1. Written Pilot Scope Adhered To               : [ YES / NO ]
2. Observe-Only Receipt Verification (Exit 0)   : [ PASS / FAIL ] (Receipts evaluated: <N>)
3. Kill-Switch Drill Verified                   : [ PASS / FAIL ] (Observed T_disengage: <ms>)
4. Rollback Procedure Verified                  : [ PASS / FAIL ] (Observed T_rollback: <sec>)
5. Unintended Primary Traffic Impact Observed   : [ NONE / DETAILS ]

Partner Reviewer Signature / Key Fingerprint    : <Signature / PGP or SSH Fingerprint>
Date (UTC)                                      : <YYYY-MM-DD>
```
