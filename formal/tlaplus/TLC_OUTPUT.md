# Exhaustive State-Space Model Checker Output: AEIB Station 1 & 2 + EO1 Settle-Before-Retry

**Formal Specification:** [`formal/tlaplus/AEIBStation1And2.tla`](file:///Users/andriileukhin/Documents/SovereignNexus/formal/tlaplus/AEIBStation1And2.tla)  
**Exhaustive BFS/DFS Model Checker:** [`src/eo1_protocol_model_checker.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/eo1_protocol_model_checker.py) (tests: [`tests/test_eo1_protocol_model_checker.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_eo1_protocol_model_checker.py))  
**Evaluation Date:** 2026-10-27 (TLC run); 2026-10-26 (Python checker)  
**Status:** Two independent checkers agree on the fenced model. TLC v1.8.0 (upstream prerelease; SHA-256 pinned in `scripts/fetch_tla2tools.sh`) was run on the `.tla` by `scripts/run_tlc_formal_gate.sh`:

| Config | TLC result (run 2026-10-27) | Python checker (`src/eo1_protocol_model_checker.py`) |
|---|---|---|
| `AEIBStation1And2_A5.cfg` (fence on) | no error; 116,953 states generated, **34,047 distinct**, depth 21 | `A5_FENCED`: 34,047 states, 0 violations |
| `AEIBStation1And2_A4.cfg` (no fence) | `SafetyNoDuplicateEffect` violated; 8-state trace (initial state + 7 actions): AuthorizeAndReserve, Transport(timeout_late), Readback(NOT_APPLIED), LateCommit, ReconcileRefuted, Redispatch, Transport(200) | `A4_EFFECT_KEY_AND_RECONCILER`: same 7-action trace |

TLC does not cover the fail-closed variant or the regenerated-retry ablation configs; those exist only in the Python checker. Bounds: 2 operations, amounts 1..2, sprint limit 3, 2 attempts, one worker thread. Results hold for the stated model only. Re-run: `bash scripts/fetch_tla2tools.sh && bash scripts/run_tlc_formal_gate.sh`.

---

## 1. Specification & Invariants (`formal/tlaplus/AEIBStation1And2.tla`)

An earlier revision of `AEIBStation1And2.tla` defined `SafetyEscrowIdentity` using `CHOOSE s \in Nat : TRUE` (vacuous) and cited 27 states here without an executable checker in `src/`. On 2026-10-26:
1. `CHOOSE s \in Nat : TRUE` was replaced with a non-vacuous `RECURSIVE SumAmounts(_)` fold over active and confirmed operations.
2. Five safety invariants were specified and checked exhaustively by `src/eo1_protocol_model_checker.py` across `Operations = {"op1", "op2"}`, `Amounts = {1, 2}`, `MaxPerCallMinor = 2`, `SprintLimitMinor = 3`, `MaxAttempts = 2`, wire faults (`200`, `timeout_pre`, `timeout_post`, `http500_post`), read-back outcomes (`APPLIED`, `NOT_APPLIED`, `UNKNOWN`), and regenerated retry:
   - `SafetyBudgetConservation`: `reservedMinor + settledMinor <= SprintLimitMinor`
   - `SafetyEscrowIdentity`: `reservedMinor = SumAmounts(active)` and `settledMinor = SumAmounts(confirmed)`
   - `SafetyNoDuplicateEffect`: `\A op \in Operations : targetEffects[op] <= 1`
   - `SafetyNeverReleaseLatchWithoutReadback`: an `INDETERMINATE` operation never transitions to `REFUTED` unless read-back observed `NOT_APPLIED`
   - `SafetyF7StaysIndeterminate`: if read-back is `UNKNOWN` (timeout), the operation remains `INDETERMINATE` and `targetEffects[op]` does not increment

---

## 2. Exhaustive BFS/DFS Model Checker Results (`python3 src/eo1_protocol_model_checker.py`)

| Protocol Configuration | Distinct Reachable States | Transitions Evaluated | Violated Invariants (Shortest Counterexample Trace Length) |
| :--- | ---: | ---: | :--- |
| `A4_EFFECT_KEY_AND_RECONCILER` | 5,175 | 14,140 | **None** (max depth 18, 409 terminal states; confirmed by independent DFS) |
| `BUG_VACUOUS_ESCROW_DRIFT` | 2,079 | 5,628 | `SafetyEscrowIdentity` (trace length 4) |
| `BUG_NAIVE_RETRY_NO_LATCH` | 18,063 | 62,262 | `SafetyNoDuplicateEffect` (trace length 4: `timeout_post -> NaiveRetry -> 200`), `SafetyNeverReleaseLatchWithoutReadback` (3) |
| `BUG_RETRY_ON_READBACK_UNKNOWN` | 20,367 | 60,012 | `SafetyF7StaysIndeterminate` (4), `SafetyNeverReleaseLatchWithoutReadback` (4), `SafetyNoDuplicateEffect` (6) |
| `BUG_FULL_PAYLOAD_CAID_ON_REGENERATED_RETRY` | 8,607 | 19,508 | `SafetyNoDuplicateEffect` (trace length 3: `200 -> RegeneratedRetry` with changed incidental fields), `SafetyF7StaysIndeterminate` (4) |

**Scope & non-modelled faults:** Late commits after a `NOT_APPLIED` read-back (`timeout_late`), Byzantine/lying read-back responses, and transport-layer packet redelivery are not modelled in this finite state machine.
