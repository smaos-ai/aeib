# EO1 Real Duplicate-Side-Effect Benchmark

`benchmarks/eo1_real_duplicate_benchmark.py` runs the **real**
`src/eo1_write_before_execute.PreDispatchIntentInterlock` against a **real** local effect
target. It is a prototype measurement harness, evaluated on one macOS host under the stated
configuration. It is not a model of production traffic.

`benchmarks/aeib_execution_integrity/run_episodes.py` is a self-contained simulation. This
benchmark is different: every A2/A3/A4 dispatch goes through the interlock's actual code. That
includes the ledger append with fsync, the `flock` admission lock, latch markers, and
startup recovery. F4 and F5 use real OS subprocesses, and F4 kills the client with a real
`SIGKILL`.


## Effect target

The target is a stdlib `ThreadingHTTPServer` on `127.0.0.1`. Each committed effect appends
one JSON line to `effects.jsonl` in a temporary directory. The metrics come from reading that
file after every in-flight write has finished. The target's own idempotency-key handling is
**off** by default; enable it with `--target-idempotency on`.

EO1 arms send the CAID as the `X-AEIB-CAID` header. The target records it with each effect and
answers `GET /readback?caid=<caid>` with `{"caid", "applied"}`. The CAID is used only for
read-back and fencing; the target never de-duplicates on it.

For A5 the target also exposes `POST /fence?caid=..&below=n`. Under its lock, the target does
two things at once: it records the fence, and it reports whether the CAID is already applied.
From then on it refuses, at commit time, any write for that CAID whose `X-AEIB-Attempt` token is
below `n`.

## Fault schedule

The schedule is a balanced list of the nine faults, shuffled with `random.Random(seed)`. For
F4 the seed picks whether the target commits before the kill. For F9 it picks the late-commit
factor. Faults F1–F4 and the F7/F8/F9 write fault fire only on the first write the target sees
for an intent.

Fault names are matched where possible to Table 2 ("Fault modes") of arXiv:2609.29095v1,
*Where Does Exactly-Once Live?* (LIMBO). We read that paper's abstract and HTML full text
through the arXiv API, using the `literature-search-arxiv` skill:
<https://arxiv.org/abs/2609.29095>.

| Fault | Injected behaviour | LIMBO row |
|---|---|---|
| F1 | target commits, then holds the response past the client timeout (ack lost) | `timeout_post` |
| F2 | target holds past the client timeout and never commits | `timeout_pre` |
| F3 | target commits, then returns HTTP 500 | `http500_post` |
| F4 | client subprocess gets SIGKILL while its request is held at the target (before or after commit, seeded); a new process then retries | no direct row (client-side crash) |
| F5 | two subprocesses submit the same intent behind a stdin barrier; the target adds a 30 ms commit window | no direct row; loosely related to `duplicate_delivery`, which LIMBO defines as transport-side redelivery |
| F6 | clean success, then a same-process re-issue, then a new client instance re-issues | no direct row |
| F7 | as F1 (commit, ack lost), and every read-back for the intent is held past the probe timeout | no direct row (read-back unavailable) |
| F8 | regenerated retry: as F1, then a crash/restore (new client and interlock over the same ledger; reconciling arms first run their pass on the pre-crash CAID), then the agent re-issues the call with a changed `memo`, a new `client_request_id` UUID and reordered `tags`/`options` | no direct row; failure mode described by ACRFence, arXiv:2603.20625 |
| F9 | **late commit**: the target holds the first write past the client timeout. While the write is in flight, read-back answers `NOT_APPLIED`. The write then commits at factor × client timeout, with the factor seeded from {0.6, 1.3, 2.4, 4.2}. A write refused by a fence does not commit | `timeout_late` |

How the F9 factors line up with the arms, with T = client timeout = 0.35 s:

- **0.6 T**: the write commits before the client times out, so every reconcile pass reads it as `APPLIED`.
- **1.3 T**: the write commits after a single reconcile pass. That pass reads at about T and retries at about T + 20 ms.
- **2.4 T**: between A4N3's second probe (about 1.7 T) and its third probe (about 3.1 T).
- **4.2 T**: after A4N3's third probe.

LIMBO's `timeout_late_tail` mode is not injected separately. F2 still never commits late.

Every arm sends the same JSON tool-call body (`tool_call_payload` in the benchmark):

- The identity fields depend only on the intent key.
- The incidental fields depend on the variant: 0 is the original call, 1 is the F8 regenerated call.
- The `client_request_id` is a UUIDv5 derived from (key, variant).

## Arms

- **A0**: naive retry. One attempt plus up to 3 retries on any transport error or 5xx. No key, no ledger.
- **A1**: in-memory idempotency key, random per process, with the same retry loop as A0. It also skips a same-process re-issue of an intent that was already acknowledged.
- **A2**: the real `PreDispatchIntentInterlock.dispatch(...)`. It never retries; a wire fault latches the CAID as `EFFECT_INDETERMINATE`. F5 workers use `auto_recover=False`; F4 restart workers use `auto_recover=True`.
- **A3**: A2 plus `src/eo1_reconciliation_adapter.Eo1ReconciliationAdapter`. After each intent's scenario it runs one reconcile pass: up to 3 read-back probes, 0.35 s timeout each, backoff 0.05 s then 0.1 s. The pass settles the latch through EO1's own `reconcile_out_of_band`, which writes an Ed25519-signed `CONTINUITY_RECEIPT`. A `NOT_COMMITTED` settlement is re-submitted once. **Basis for NOT_APPLIED: the explicit unsafe opt-in `trust_not_applied_without_fence=True`** (recorded as `settlement_basis = "unsafe_trust_not_applied"`).
- **A4**: A3, with the CAID taken from `src/eo1_effect_key.py` (schema-declared identity fields) instead of the full payload. Same unsafe opt-in.
- **A4N3**: A4 (unsafe opt-in) with `not_applied_confirmations=3`. Probes are spaced 0.7 T and then 1.4 T, i.e. at about T, 1.7 T and 3.1 T.
- **A4D**: A4 with the adapter's **fail-closed default**. A `NOT_APPLIED` read without a fence or deadline leaves the CAID latched with reason `NOT_APPLIED_UNFENCED`, and there is no retry.
- **A5**: A4 plus **attempt fencing**.
  - Every write carries `X-AEIB-Attempt = count_dispatch_attempts(ledger, caid) + 1`.
  - On a `NOT_APPLIED` read, the adapter calls the `FenceProbe` with `below = recorded attempts + 1`.
  - If the fence answers `FENCED_NOT_APPLIED`, the adapter settles `NOT_COMMITTED` (basis `fence`) and the client retries with the next attempt number.
  - If the fence answers `APPLIED`, the adapter settles `COMMITTED` (basis `fence_observed_applied`).
  - If the fence fails or times out, the CAID stays latched (`LATCHED_FENCE_FAILED`).

All EO1 processes of one arm share one Ed25519 boundary key, stored in the run's temporary
directory with mode 0600.

### Settlement basis: why NOT_APPLIED is fail-closed by default

- **LIMBO (arXiv:2609.29095), Proposition 1:** no verification-only policy is exactly-once under late commits without a known bound on in-flight time. That paper reports that 69% of 297 late-commit re-issues duplicated. We did not re-run their experiment.
- **MCP conformance issue #3394, row C:** a request that is in flight while read-back says "not found" is classified as UNKNOWN, not safe to retry.

The adapter therefore settles `NOT_APPLIED` as `NOT_COMMITTED` only on one of three bases:

1. A fence acked by the target (`fence`).
2. A server-enforced not-after deadline (`DeadlineContract`) that has elapsed, plus a clock-skew margin (`deadline`).
3. The loudly named opt-in `trust_not_applied_without_fence=True` (`unsafe_trust_not_applied`).

The basis is written into the signed receipt. Read-back, fencing and deadlines all need target
cooperation (LIMBO Proposition 2). A tool that offers none of them stays `EFFECT_INDETERMINATE` by
design.

Adapter tests changed by the new default:

- `test_not_applied_settles_not_committed_and_allows_one_fresh_attempt` was renamed `..._with_unsafe_opt_in_...` and now uses the opt-in.
- `test_restart_mid_reconcile_is_idempotent` now settles NOT_APPLIED through a real fence.
- `test_not_applied_confirmations_require_consecutive_reads` now uses the opt-in for its settling case.

In the benchmark, A3 and A4 declare the opt-in.

## Metrics

All metrics are computed from the effects file, after all target writes have drained, and from
the on-disk ledger state.

- **Effects / duplicate effects**: per-key line counts at the target. Duplicate effects = Σ max(0, count − 1).
- **Duplicate rate**: the share of intents with more than one effect, with a Wilson 95% interval.
- **Lost (unflagged)**: intents with zero effects that are *not* flagged INDETERMINATE.
- **INDETERMINATE (residual)**: after all passes, a fresh interlock probe still finds the CAID latched or with an unresolved `DISPATCH_INTENT`.
- **Reconcile probes, fence calls, fenced write refusals**: read-back requests, `POST /fence` calls, and writes refused at commit time because of a fence.
- **Latency**: `time.perf_counter` around client submit calls, plus the reconcile pass(es) and the single retry for reconciling arms. "Added vs A0" is the per-intent paired difference against A0.

## Measured result (N=300, seed 42, client timeout 0.35 s, target idempotency off)

Run: `python3 benchmarks/eo1_real_duplicate_benchmark.py --n 300 --seed 42` (wall 1191.1 s,
darwin, Python 3.14.3; output `/tmp/eo1_real_duplicate_benchmark_seed42_n300_idemoff.{json,md}`).
**Adding F9 changed the fault mix** (34 intents each for F1–F3, 33 each for F4–F9), and three arms
were added. The numbers are not directly comparable with the earlier eight-fault run (A0–A4, 38/37
per fault).

| Arm | Intents | Effects | Dup effects | Dup rate [Wilson 95%] | Lost (unflagged) | INDETERMINATE (applied/absent) | Refused | Reconcile probes | p50/p95 latency ms | added vs A0 p50/p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 naive retry | 300 | 616 | 316 | 83.3% [78.7, 87.1] | 0 | 0 (0/0) | 0 | 0 | 352.2/353.8 | 0.0/0.0 |
| A1 in-memory key | 300 | 583 | 283 | 83.3% [78.7, 87.1] | 0 | 0 (0/0) | 0 | 0 | 352.0/352.8 | -0.7/0.7 |
| A2 EO1 interlock | 300 | 283 | 33 | 11.0% [7.9, 15.0] | 0 | 234 (184/50) | 132 | 0 | 365.7/391.4 | 17.6/37.7 |
| A3 reconciler, unsafe opt-in | 300 | 354 | 54 | 18.0% [14.1, 22.7] | 0 | 33 (33/0) | 132 | 300 | 376.8/1580.9 | 26.9/1227.2 |
| A4 effect key, unsafe opt-in | 300 | 321 | 21 | 7.0% [4.6, 10.5] | 0 | 33 (33/0) | 165 | 300 | 375.0/1580.5 | 23.6/1227.0 |
| A4N3 unsafe opt-in, 3 confirmations | 300 | 303 | 3 | 1.0% [0.3, 2.9] | 0 | 33 (33/0) | 165 | 433 | 378.5/2165.6 | 25.8/1813.0 |
| A4D fail-closed default | 300 | 250 | 0 | 0.0% [0.0, 1.3] | 0 | 104 (54/50) | 165 | 300 | 371.5/1585.9 | 25.0/1232.7 |
| A5 fenced | 300 | 300 | 0 | 0.0% [0.0, 1.3] | 0 | 33 (33/0) | 165 | 300 | 376.8/1582.8 | 26.4/1229.7 |

A3's 54 duplicates are 33 on F8 (full-payload CAID) plus 21 on F9; A2's 33 are all F8.

Each cell below reads dup effects / effects / residual INDETERMINATE. Lost (unflagged) was 0 in every cell.

| Fault | n | A0 | A1 | A2 | A3 | A4 | A4N3 | A4D | A5 |
|---|---|---|---|---|---|---|---|---|---|
| F1 | 34 | 34/68/0 | 34/68/0 | 0/34/34 | 0/34/0 | 0/34/0 | 0/34/0 | 0/34/0 | 0/34/0 |
| F2 | 34 | 0/34/0 | 0/34/0 | 0/0/34 | 0/34/0 | 0/34/0 | 0/34/0 | 0/0/34 | 0/34/0 |
| F3 | 34 | 34/68/0 | 34/68/0 | 0/34/34 | 0/34/0 | 0/34/0 | 0/34/0 | 0/34/0 | 0/34/0 |
| F4 | 33 | 17/50/0 | 17/50/0 | 0/17/33 | 0/33/0 | 0/33/0 | 0/33/0 | 0/17/16 | 0/33/0 |
| F5 | 33 | 33/66/0 | 33/66/0 | 0/33/0 | 0/33/0 | 0/33/0 | 0/33/0 | 0/33/0 | 0/33/0 |
| F6 | 33 | 66/99/0 | 33/66/0 | 0/33/0 | 0/33/0 | 0/33/0 | 0/33/0 | 0/33/0 | 0/33/0 |
| F7 | 33 | 33/66/0 | 33/66/0 | 0/33/33 | 0/33/33 | 0/33/33 | 0/33/33 | 0/33/33 | 0/33/33 |
| F8 | 33 | 66/99/0 | 66/99/0 | 33/66/33 | 33/66/0 | 0/33/0 | 0/33/0 | 0/33/0 | 0/33/0 |
| F9 | 33 | 33/66/0 | 33/66/0 | 0/33/33 | 21/54/0 | 21/54/0 | 3/36/0 | 0/33/21 | 0/33/0 |

### F9 late commit: the three-way product comparison

| Arm | NOT_APPLIED basis | n | Intents with duplicate | Dup-intent rate [Wilson 95%] | Effects | Residual INDETERMINATE | Fenced write refusals |
|---|---|---|---|---|---|---|---|
| A0 (negative control) | no reconciler | 33 | 33 | 100.0% [89.6, 100.0] | 66 | 0 | 0 |
| A2 | no reconciler | 33 | 0 | 0.0% [0.0, 10.4] | 33 | 33 | 0 |
| A4 | unsafe opt-in | 33 | 21 | 63.6% [46.6, 77.8] | 54 | 0 | 0 |
| A4N3 | unsafe opt-in, 3 spaced confirmations | 33 | 3 | 9.1% [3.1, 23.6] | 36 | 0 | 0 |
| A4D | fail-closed default | 33 | 0 | 0.0% [0.0, 10.4] | 33 | 21 | 0 |
| A5 | fence | 33 | 0 | 0.0% [0.0, 10.4] | 33 | 0 | 21 |

Duplicates on F9 by late-commit factor (dup/n): A3 and A4 0/12, 9/9, 9/9, 3/3 for factors 0.6, 1.3, 2.4, 4.2. A4N3 0/12, 0/9, 0/9, 3/3. A4D and A5 0 at every factor. A0 duplicated 33 of 33.

Reconcile outcomes across all faults:

| Arm | Settled COMMITTED | Settled NOT_COMMITTED (retried once) | Stayed latched | Fence calls / fenced refusals | Reconcile pass p50/p95 |
|---|---|---|---|---|---|
| A3 / A4 | 130 | 71 | 33 UNKNOWN | — | 12.0/1215.3 ms / 11.5/1214.9 ms |
| A4N3 | 148 | 53 | 33 UNKNOWN | — | 14.1/1800.0 ms |
| A4D | 130 | 0 | 33 UNKNOWN + 71 NOT_APPLIED_UNFENCED | — | 13.7/1216.2 ms |
| A5 | 130 | 71 | 33 UNKNOWN | 71 / 21 | 12.4/1215.7 ms |

### F8 regenerated retry (unchanged prediction: full-payload CAID duplicates, effect key does not)

| Arm | n | Intents with duplicate | Dup-intent rate [Wilson 95%] | Effects | Refused |
|---|---|---|---|---|---|
| A0 | 33 | 33 | 100.0% [89.6, 100.0] | 99 | 0 |
| A2 | 33 | 33 | 100.0% [89.6, 100.0] | 66 | 0 |
| A3 | 33 | 33 | 100.0% [89.6, 100.0] | 66 | 0 |
| A4 / A4N3 / A4D / A5 | 33 each | 0 | 0.0% [0.0, 10.4] | 33 | 33 |

## False-merge direction (labelled pairs)

An effect key can fail in the opposite direction from F8. It can merge two effects that were both intended,
and then the second one is refused. `tests/data/effect_key_pairs.json` holds 51 labelled pairs over four
tools: a SEPA payment, an e-mail send, ticket creation and an object put. 27 pairs are labelled
`same_effect`. Examples: regenerated memo, new UUID, timestamp, list order, IBAN spacing and case, currency
case, amount given as a digit string, NFD vs NFC. 24 pairs are labelled `different_effect`. Examples:
amount ±1 cent or ×10, a different creditor or debtor, a different currency, a different business reference,
two intended identical payments with distinct references, a refund sign, plus-addressing, a second reminder.
**The set is hand-written for this prototype. It is not field data and says nothing about rates in real
traffic.** It includes four deliberate hard cases. In one, the agent also regenerated the business
reference. In another, the amount arrives as a major-unit float. In a third, the reference is dropped. In
the fourth, an IBAN fails its checksum.

Run: `python3 -m src.eo1_effect_key --pairs tests/data/effect_key_pairs.json`

| Keying | Same key, same effect | False split (same effect, different key) | False merge (different effects, same key) | Different key, different effect | Refused (fail closed) |
|---|---|---|---|---|---|
| Full-payload CAID (A2/A3) | 1 | 26 | 0 | 24 | 0 |
| Effect-key CAID (A4) | 24 | 1 | 0 | 23 | 3 |

- The single full-payload merge is pair `pay-s05`: only the object member order differs, and JCS sorts keys.
- The effect key's one false split is `pay-s14`: the regenerated call also changed the business reference. An effect key cannot merge that case.
- The three refusals are `pay-s15` (float amount), `pay-s16` (business reference missing) and `pay-d12` (IBAN fails mod-97). In each case the key derivation refuses, and the caller must not dispatch.
- No false merges on this labelled set for either keying. This holds only because the payment schema includes the debtor account and the business reference. Without the debtor IBAN, pair `pay-d11` (the same payment debited from another account) would merge.


## Interpretation

- **Late commits break the read-back reconciler's own claim.** With the unsafe opt-in, a `NOT_APPLIED` read during an in-flight write led to a retry. The late write then landed as well. A4 duplicated 21 of 33 F9 intents (63.6%, Wilson [46.6, 77.8]%), which is every intent whose commit landed after the single reconcile pass. This is the LIMBO Proposition 1 failure, reproduced on our own harness.
- **More confirmations narrow the window but do not close it.** A4N3 cut F9 duplicates to 3 of 33 (9.1%, [3.1, 23.6]%). Those 3 are exactly the 4.2 T commits, which landed after its third probe. Any fixed probe schedule loses to a long enough in-flight time.
- **The fail-closed default removes the duplicates by giving up liveness.** A4D had 0 F9 duplicates, but 21 F9 intents stayed INDETERMINATE. It also leaves every F2 intent and every pre-commit F4 kill INDETERMINATE: 104 residual in total versus 33 for A5, and 50 of those intents had no effect at the target.
- **Fencing gave both properties in this run.** A5 had 0 duplicates overall ([0.0, 1.3]%) and 0 on F9 ([0, 10.4]%). Its residual INDETERMINATE was 33, the same as A3/A4: all F7, where the read-back itself timed out. Its fences refused the 21 late writes.
  - The cost is target cooperation. The target must accept an attempt token, install a fence, and check-and-fence atomically. A target that ignores the fence would defeat it.
  - A5 issued 71 fence calls, one per NOT_APPLIED settlement. Its added latency vs A0 was 26.4/1229.7 ms (p50/p95), against 23.6/1227.0 ms for A4 in this single run.
- **A0 is the negative control.** It duplicated on F9 33 of 33 times, so the fault is able to produce duplicates.

## Limitations

- Single host, loopback HTTP, one filesystem (APFS). NFS, Windows and network partitions were not evaluated.
- F9 delays come from a fixed, discrete set relative to the client timeout. Real in-flight time distributions (`timeout_late_tail`) were not modelled. The A4N3 result depends directly on that set.
- The fence is honest by construction: the local target enforces it atomically under one lock. A target that acks a fence but does not enforce it, or that enforces it only on some replicas, was not evaluated.
- The `DeadlineContract` basis is unit-tested only. No benchmark arm uses it.
- The attempt counter reads the local ledger file. Writers on other hosts that share a CAID were not evaluated.
- No transport-level redelivery is injected. F6 and F8 restarts happen in-process; real process restarts are exercised only in F4.
- Fault fractions are fixed by design (1/9 each), so aggregate rates depend on the mix. Use the per-fault tables.
- Latency uses short timeouts (0.35 s client and probe, 0.875 s target hold) and is host-dependent.
- UndoBench (arXiv:2610.05622) is an external benchmark to run later. It has not been run.

## Verification

```
python3 -m pytest tests/test_eo1_reconciliation_adapter.py tests/test_eo1_protocol_model_checker.py tests/test_eo1_real_duplicate_benchmark.py -q
python3 compliance/ast_purity.py src/eo1_reconciliation_adapter.py src/eo1_protocol_model_checker.py benchmarks/eo1_real_duplicate_benchmark.py tests/test_eo1_reconciliation_adapter.py tests/test_eo1_protocol_model_checker.py tests/test_eo1_real_duplicate_benchmark.py
python3 compliance/claim_integrity_gate.py --paths src/eo1_reconciliation_adapter.py src/eo1_protocol_model_checker.py benchmarks/eo1_real_duplicate_benchmark.py tests/test_eo1_reconciliation_adapter.py tests/test_eo1_protocol_model_checker.py tests/test_eo1_real_duplicate_benchmark.py
python3 tools/mutation_adequacy_gate.py --target src/eo1_reconciliation_adapter.py --tests tests/test_eo1_reconciliation_adapter.py --max-mutants 30 --seed 42
python3 tools/mutation_adequacy_gate.py --target src/eo1_protocol_model_checker.py --tests tests/test_eo1_protocol_model_checker.py --max-mutants 30 --seed 42
python3 src/eo1_protocol_model_checker.py
```

Model checker (`src/eo1_protocol_model_checker.py`) results with the late-commit transition. These come from exhaustive BFS; **TLC was not run** (no `tla2tools.jar` on the host):

- `A4_EFFECT_KEY_AND_RECONCILER` (trusts NOT_APPLIED): 48927 states, 196154 transitions. It violates `SafetyNoDuplicateEffect`; the shortest trace has 7 steps: Authorize → Transport(timeout_late) → Readback(NOT_APPLIED) → LateCommit → ReconcileRefuted → Redispatch → Transport(200).
- `A5_FENCED`: 34047 states, 116952 transitions. All 5 invariants hold.
- `A4_DEFAULT_FAIL_CLOSED`: 2759 states, 8670 transitions. All 5 invariants hold, and it never re-dispatches.
- With late commits disabled, A4 and A5 both reproduce the earlier 5175 states and 14140 transitions with no violations.

The benchmark tests make per-intent predictions keyed on the F9 factor. Each is asserted as a measured outcome, so it can fail:

- A0 always duplicates.
- A3/A4 duplicate exactly when the factor is above 1.
- A4N3 duplicates exactly when the factor is above 3.1.
- A4D never duplicates, and stays INDETERMINATE exactly when the factor is above 1.
- A5 never duplicates, and refuses exactly the late writes.

The F1–F8 assertions from earlier waves are kept.

The adapter tests use a real HTTP server and a real interlock. Beyond the earlier paths, they cover:

- the unfenced default stays latched;
- a real late commit duplicates under the opt-in and is refused after a real fence;
- a fence that observes the commit settles `COMMITTED`;
- a fence that is unsupported or times out stays latched;
- a fence failure falls back to an elapsed deadline;
- the deadline boundaries;
- the ledger attempt-counting helpers.
