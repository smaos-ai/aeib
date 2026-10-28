# AEIB: Evidence-Only Summary for Design Partners

> **Scope of this page (2026-10-26):** every statement below is tied to a command that was run, or a test file that was executed, on one macOS (darwin, Python 3.14) development host. Anything without a command is listed under "What is not claimed". This is a **prototype**, evaluated under the stated configuration. It is not a hosted service, and no customer has deployed it.

## 1. The problem we are testing against

When an AI agent calls a tool with a **non-idempotent side effect** (a payment, a ticket, an email, a ledger write) and the call times out or returns 5xx, the agent does not know whether the effect happened. Retrying can duplicate the effect. Not retrying can lose it.

*Motivation (not validation of AEIB):* arXiv:2609.29095, *Where Does Exactly-Once Live?* (LIMBO). It reports that retried in-flight agent activities are at-least-once in common orchestration stacks. It also reports that provider idempotency keys reduce duplicates substantially, but only where the provider supports them. That paper does not evaluate AEIB.

**Positioning:** *settle-before-retry* for non-idempotent agent side effects. Before dispatch, AEIB durably records the intent under a content-addressed ID (CAID). Any intent whose outcome is unknown is **latched INDETERMINATE**, and AEIB refuses to re-dispatch it until it is settled.

## 2. Measured result: real-class EO1 benchmark (Arms A0–A5, Faults F1–F9)

Command: `python3 benchmarks/eo1_real_duplicate_benchmark.py --n 300 --seed 42` (re-run 2026-10-26, wall 1191 s). Full write-up: [EO1_REAL_DUPLICATE_BENCHMARK.md](benchmarks/EO1_REAL_DUPLICATE_BENCHMARK.md). Tests: `python3 -m pytest tests/test_eo1_real_duplicate_benchmark.py tests/test_eo1_reconciliation_adapter.py tests/test_eo1_effect_key.py -q`.

Setup:
- The benchmark uses the real `src/eo1_write_before_execute.PreDispatchIntentInterlock`, with fsync'd ledger, signed high-water mark (`<ledger>.hwm`), `flock` and recovery.
- The effect target is a real loopback HTTP server with its own idempotency **off**.
- Nine fault types run across 300 intents (34 or 33 per fault):
  - F1 post-commit timeout; F2 pre-commit timeout; F3 post-commit HTTP 500;
  - F4 real `SIGKILL` of the client; F5 two-process race; F6 re-issue across restart;
  - F7 read-back timeout; F8 regenerated retry (ACRFence, arXiv:2603.20625);
  - **F9 late commit**: the target answers read-back `NOT_APPLIED` while the original write is still in flight, then commits it (LIMBO `timeout_late`, arXiv:2609.29095).

| Arm | Dup-intent rate [Wilson 95%] | Left INDETERMINATE (applied / absent) | Added latency vs A0, p50 / p95 |
|---|---|---|---|
| A0 naive retry | 83.3% [78.7, 87.1] | 0 | baseline |
| A1 in-memory idempotency key | 83.3% [78.7, 87.1] | 0 | −0.7 / +0.7 ms |
| A2 EO1 interlock, no reconciler | 11.0% [7.9, 15.0] (all F8) | 234 (184 / 50) | +17.6 / +37.7 ms |
| A3 reconciler, full-payload CAID, *unsafe opt-in* | 18.0% [14.1, 22.7] (F8 + F9) | 33 (all F7) | +26.9 / +1227.2 ms |
| A4 effect-key CAID, *unsafe opt-in* | 7.0% [4.6, 10.5] (all F9) | 33 (all F7) | +23.6 / +1227.0 ms |
| A4D effect-key CAID, **fail-closed default** | **0.0% [0.0, 1.3]** | 104 (54 / 50) | +25.0 / +1232.7 ms |
| **A5 effect-key CAID + attempt fencing** | **0.0% [0.0, 1.3]** | **33 (33 / 0, all F7)** | **+26.4 / +1229.7 ms** |

> [!IMPORTANT]
> **What the numbers say, including what went against us:**
> 1. **Trusting a `NOT_APPLIED` read-back is unsafe under late commits.** On F9 (n=33), A4 with the unsafe opt-in duplicated **21/33 (63.6% [46.6, 77.8])**. Three spaced confirmations (A4N3) cut that to 3/33 but did not remove it. This reproduces LIMBO Prop 1. The exhaustive model checker gives the same result: `A4_EFFECT_KEY_AND_RECONCILER` violates `SafetyNoDuplicateEffect` with a 7-step trace (`python3 src/eo1_protocol_model_checker.py`).
> 2. **The adapter's default is now fail closed (A4D).** An unfenced `NOT_APPLIED` stays latched (`NOT_APPLIED_UNFENCED`). Result: 0 duplicates, but 104 intents are left for reconciliation, 50 of them never applied at the target.
> 3. **Attempt fencing (A5) removes both problems when the target cooperates.** Before re-dispatching, the target is told to refuse older attempts for that CAID. Result: 0 duplicates; the fence refused 21 late writes; residual INDETERMINATE is 33, all F7 where the read-back itself failed. Model checker `A5_FENCED`: 34,047 states / 116,952 transitions, all 5 invariants hold. **Fencing, like read-back, requires the target to support it** (LIMBO Prop 2). Without it, the honest outcome is INDETERMINATE.
> 4. **Regenerated retries (F8):** full-payload CAID (A2/A3) duplicated 33/33. Effect-key CAID (A4/A4D/A5) duplicated 0/33 [0.0, 10.4]. On 51 hand-written labelled pairs (not field data) the effect key showed 0 false merges, 1 false split and 3 fail-closed refusals (`python3 -m src.eo1_effect_key --pairs tests/data/effect_key_pairs.json`).

Limitations: single host, loopback HTTP, APFS only. Transport redelivery not injected. Fault mix is fixed (1/9 each), so read the per-fault tables in [EO1_REAL_DUPLICATE_BENCHMARK.md](benchmarks/EO1_REAL_DUPLICATE_BENCHMARK.md) rather than the aggregate. EO1 crash torture (380 SIGKILLs, `tests/test_eo1_crash_torture.py` + scratch harness) found 0 false halts, 0 lost acknowledged intents and 0 re-admissions; power loss was not tested.

**Simulation harness (separate from the above):** `python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42` (re-run 2026-10-26, exit 0). This is a **deterministic simulation**, not real I/O:

| Arm | Duplicates | Notes |
|---|---|---|
| Naive retry | 302/500 (60.4%) | |
| Payload-derived key | 187/500 (37.4%) | |
| Server-side stable key | 0/500 | 198 unresolved |
| AEIB protocol | 0/500 | rule-of-three 95% upper bound ≈ 0.6% |

## 3. Test suite & mutation adequacy

- Full suite, re-run 2026-10-27 after Wave 6: **3447 passed / 0 failed / 11 skipped** (368 s).
  - Command: `python3 -m pytest tests/ -q -p no:cacheprovider`.
  - The 11 skips need a PQC signer binary, Docker, or a running service.
- Repo verification gates (`compliance/check_zone_boundary.py`, `compliance/ast_purity.py`, `compliance/no_mock_enforcer.py`, `compliance/claim_integrity_gate.py --all`, `tools/run_all_verification_gates.py`) exited 0 on the same date.
- **TLC Model Checker & Exhaustive state-space model checker (`scripts/run_tlc_formal_gate.sh`, `src/eo1_protocol_model_checker.py`, `formal/tlaplus/AEIBStation1And2.tla`):**
  - Replaced the vacuous `CHOOSE s \in Nat : TRUE` in `formal/tlaplus/AEIBStation1And2.tla` with a non-vacuous `RECURSIVE SumAmounts(_)` fold and 5 safety invariants (`SafetyBudgetConservation`, `SafetyEscrowIdentity`, `SafetyNoDuplicateEffect`, `SafetyNeverReleaseLatchWithoutReadback`, `SafetyF7StaysIndeterminate`).
  - TLC (`tla2tools.jar` v1.8.0, SHA-256 pinned in `scripts/fetch_tla2tools.sh`) executed via `scripts/run_tlc_formal_gate.sh`: verified `A5_FENCED` across all **34,047 distinct states and 116,952 transitions** (max depth 21, 0 errors), and confirmed `SafetyNoDuplicateEffect` violation on `A4` with an 8-state trace.
  - The Python BFS model checker (`src/eo1_protocol_model_checker.py`) independently confirms the same state space and produces shortest counterexample traces for all 4 ablation/bug configurations.
- **Mutation adequacy (`tools/mutation_adequacy_gate.py --max-mutants 30 --seed 42` across all tests of each module):**
  - `src/eo1_write_before_execute.py` (all 6 EO1 test files): **90.0% (27/30)** after adding `tests/test_eo1_mutation_hardening.py` and `tests/test_eo1_hwm_performance.py` (up from 50.0% before hardening).
  - `src/eo1_reconciliation_adapter.py`: **100.0% (30/30)**.
  - `src/eo1_effect_key.py`: **100.0% (30/30)**.
  - `src/eo1_protocol_model_checker.py`: **100.0% (30/30)**.
  - `src/coinbase_x402_agent_gateway.py`: **90.0% (27/30)**.
  - `src/secure_mcp_uds_boundary.py`: **90.0% (27/30)**.
  - `aeib_mcp_proxy.py`: **90.0% (27/30)** (up from 23.3% before test hardening).
  - `adapters/mcp/idempotent_mcp_proxy.py`: **100.0% (30/30)** (up from 73.3%).
  - `tools/standalone_offline_verifier.py`: **90.0% (27/30)**.
  - `tools/standalone_receipt_verifier.py`: **86.7% (26/30)** (4 survivors in unreachable dead code and self-test failure branches).
  - `src/package_install_gate.py`, `src/protected_path_egress_policy.py`, `src/mcp_schema_pinning.py`: **100.0% (30/30)** each (`mcp_schema_pinning.py` now pins `name`, `title`, `description`, `inputSchema`, and `annotations`).
  - `src/sources/dbsnp.py`: **96.9% (62/64 all-sites)**.

## 4. Internal red-team findings and fixes (2026-10-26)

| Area | What the red team broke | Status | Test evidence |
|---|---|---|---|
| Offline receipt verifier | Small-order public key forged any receipt; embedded key trusted when none was pinned; truncated Merkle proof accepted | Fixed; 7/7 attacks now rejected. Also fixed an RFC 9162 loop bug that had rejected honest proofs across tree sizes 1..33. Mutation kill 90% | `tests/test_standalone_offline_verifier.py` |
| x402 payment gate | Negative or boolean amounts; unpinned SIWx signer; nonce replay; backdated epoch; URL canonicalisation; binding reuse across intents; re-dispatch after REFUTED; unbound query string; `http://` downgrade; multi-process journal race | Fixed (`target_query` & `target_scheme` signed in `SIWxBinding`, `http://` rejected by default, cross-process `fcntl.flock` + incremental journal replay + `DISPATCHING` state). 91 tests pass (incl. 2-process races). Mutation kill 93.3% (28/30) | `tests/test_coinbase_x402_agent_gateway.py` |
| EO1 ledger | Forged or edited receipts unlocked latched CAIDs; ledger rollback; symlink following | Fixed:<br>• receipts verified on load<br>• signed high-water mark file (`<ledger>.hwm`) + `min_hwm_seq` external anchor support<br>• `O_NOFOLLOW` + owner checks<br>• Darwin `F_BARRIERFSYNC` + single trailing directory `F_FULLFSYNC` (`record_intent` mean ≈7.5 ms, down from ≈12.0 ms)<br>**Residual:** restoring a *matching* older ledger + high-water-mark pair is undetectable unless `min_hwm_seq` / `high_water_mark_digest()` is anchored outside the directory | `tests/test_eo1_ledger_integrity.py`, `tests/test_eo1_mutation_hardening.py`, `tests/test_eo1_hwm_performance.py` |
| MCP Unix-socket boundary & proxies | Unbounded frame; idle-client DoS; bind race; nonces kept only in memory; duplicate JSON keys; unpinned `tools/list` (`title`/`annotations` drift); regenerated retry after timeout | Fixed. `loads_strict` (I-JSON duplicate-key & NaN rejection) and `McpToolPinGuard` (`name`, `title`, `description`, `inputSchema`, `annotations` pinned) wired across all 3 MCP boundaries; `bind_effect_key` (`effect_caid` + `raw_payload_digest`) and `reconcile_probe_fn` wired into `HardenedIdempotentMcpProxy` | `tests/test_secure_mcp_uds_boundary.py`, `tests/test_mcp_boundary_hardening_wiring.py`, `tests/test_idempotent_mcp_proxy.py` |
| Oracle verdict line | In-process `exec` + forged verdict line | Fixed (child process `python -I`, empty env, temp cwd, CPU 10 s + 64 open-file rlimits, token-bound single verdict line). Mutation kill 96.7%. **Process isolation, not a sandbox.** Red-team re-run 2026-10-26 21:49 (`a6_child_oracle.py`): forged verdict defended, but the child **can** write outside its temp cwd, **can** see `~/.ssh`, and a 512 MiB allocation succeeded (`RLIMIT_AS` is not enforced by macOS). Do not run untrusted candidates on a host with secrets | `tests/test_repo_reverse_engineering_engine.py` |
| JCS canonicalisation | Divergence on exponents such as `1e+21` and UTF-16 code-unit sorting across local copies | Fixed across 50 modules + standalone tools; 0 divergences across all 69 repository canonicalizers on 343 RFC 8785 / edge payloads | `tests/test_jcs_single_source.py` |

## 5. What is NOT claimed

- **No compliance certification or attestation of any kind:** not EU AI Act, DORA, SOC 2, ISO 27001/42001, HIPAA, CMMC, SEC 17a-4 or any classified-system accreditation. Some modules emit regulatory *label mappings*. Those are descriptive and unsigned.
- **No customers, paying pilots, signed LOIs or revenue.** No contract, LOI or invoice exists in the repository. Investor materials that say otherwise are listed in [UNVERIFIED_CLAIMS_REGISTER.md](UNVERIFIED_CLAIMS_REGISTER.md) and must not be relied on.
- **No zero-knowledge proofs, TPM/TDX/SEV attestation or eBPF kernel enforcement.**
  - Code under `ebpf/` and `hardware_attestation/` is structural scaffolding.
  - `src/ocr_audit/kernel_omission_enforcer.py` is an in-memory model.
  - `src/process_trace_guard.py` validates caller-supplied traces and captures nothing.
- **No Lean-checked proofs of product behaviour.** `lean` is not installed on the host, so no `.lean` file in the repo has been checked here. The `siss-night-cycle` crate contains none.
- **No post-quantum signatures in the default path.** `src/ocr_audit/reporter.py` produces no signature (relabelled 2026-10-26). An ML-DSA path exists only through an external Rust signer binary (`tools/hybrid_pqc_envelope.py`), and its tests skip on this host.
- **Single-host ledger.** EO1 durability was evaluated on one APFS filesystem. Distributed, NFS and multi-host operation were not evaluated. The saga compensator provides **eventual consistency** via asynchronous queues, not atomic distributed rollback (2PC).
- **Not exactly-once on uncooperative targets.** EO1 avoids duplicates by refusing to re-dispatch unsettled intents. It cannot make an uncooperative target exactly-once.

## 6. What a design partner would help us measure

1. A real non-idempotent tool of yours, with a read-back endpoint, so INDETERMINATE intents can be reconciled automatically. We would then re-run the benchmark against it.
2. Your actual fault mix, to replace our fixed 1/6-per-fault schedule.
3. Latency budget: whether +14 ms p50 per side effect (two fsyncs) is acceptable, or whether group-commit is required.
