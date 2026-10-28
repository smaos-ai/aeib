# DRAFT for MCP issue #3394: late-commit counterexample and fence/deadline vectors

> **Status: draft, not posted.** Everything here comes from this repository (prototype, single host, loopback HTTP). A human author should review it and post it under their own name with an AI-assistance disclosure; SEP-3182 was closed partly over undisclosed AI authorship (research lane, GitHub API). Nothing here is a claim about any real MCP server.

## 1. The scenario

A client sends a mutating `tools/call`. The transport times out. The client asks the server whether the call was applied. The server answers "not applied" **while the original request is still being processed**. The client sends the call again. Both then commit.

Row C of the #3394 conformance discussion says the same thing in other words: in flight plus read-back "not found" is **Unknown**, not safe to retry. LIMBO (arXiv:2609.29095) Proposition 1 states the general result: no verification-only policy is exactly-once under late commits unless the in-flight time has a known bound.

## 2. Seven-step counterexample (exhaustive search, not a sample)

`python3 src/eo1_protocol_model_checker.py` (explicit-state search over 48,927 states and 196,154 transitions for the config that trusts a "not applied" read):

```
AuthorizeAndReserve(op1) -> Transport(op1, timeout_late) -> Readback(op1, NOT_APPLIED)
-> LateCommit(op1) -> ReconcileRefuted(op1) -> Redispatch(op1) -> Transport(op1, 200)
```

`SafetyNoDuplicateEffect` is violated. Two variants hold all five invariants: a fenced variant (34,047 states, 116,952 transitions) and a fail-closed variant (2,759 states, 8,670 transitions). The TLA+ module `formal/tlaplus/AEIBStation1And2.tla` was also checked with **TLC v1.8.0** (`bash scripts/run_tlc_formal_gate.sh`): the fenced model finishes with no error and **34,047 distinct states, the same count as the Python checker**; the unfenced model violates `SafetyNoDuplicateEffect` with the same seven actions. TLC covers the fenced and unfenced models only; the fail-closed variant exists only in the Python checker. TLC v1.8.0 is marked a prerelease upstream.

## 3. Measured result on the real client class

`python3 benchmarks/eo1_real_duplicate_benchmark.py --n 300 --seed 42` (loopback HTTP target with its own idempotency off; fault F9 = write held past the client timeout, read-back answers NOT_APPLIED while it is in flight, then it commits after a seeded delay). Fault F9 only, 33 intents per arm:

| Policy | Intents with a duplicate effect (Wilson 95%) | Left unresolved |
|---|---|---|
| naive retry (negative control) | 33/33 (100% [89.6, 100]) | 0 |
| trust a "not applied" read | 21/33 (63.6% [46.6, 77.8]) | 0 |
| same, 3 spaced confirmations | 3/33 (9.1% [3.1, 23.6]) | 0 |
| **fail closed on an unfenced "not applied"** | **0/33 ([0, 10.4])** | 21 |
| **attempt fence before the retry** | **0/33 ([0, 10.4])** | 0 (21 late writes refused by the target) |

The duplicate rate of the "trust" policy depends on how late the commit lands relative to the probe schedule: 0/12, 9/9, 9/9, 3/3 at late-commit factors 0.6, 1.3, 2.4, 4.2 (factor = delay relative to the client timeout). The fault mix is fixed by the harness, so the aggregate across faults is not a field rate. Over all nine faults (300 intents) the fail-closed policy leaves 104 intents unresolved and the fenced policy leaves 33 (all from a read-back that itself timed out).

## 4. What the target has to support

Read-back alone is not enough. At least one of these is needed to settle "not applied" as retryable:

| # | Target capability | How our prototype uses it |
|---|---|---|
| a | at-most-once per key, repeat returns the original result (LIMBO Prop 2) | not simulated; this is the idempotency-key case |
| b | **attempt fence**: the target refuses any in-flight write with an attempt number below a fence | client calls a fence probe, then retries with `attempt_no + 1` |
| c | **server-enforced not-after deadline**: after the deadline plus clock skew, the target will not commit | client forwards a deadline and retries only after it has passed |
| d | cancel/void that atomically marks the key dead | not simulated |

If none exists, the client must keep the call **unresolved** and escalate. Our default does exactly that (`NOT_APPLIED_UNFENCED`).

## 5. What our prototype puts on the wire (so you can see its limits)

- Each dispatch carries `_meta.aeib_attempt_no` (integer, per effect identity, starts at 1) and, when configured, `_meta.aeib_not_after_ms`.
- The fence call itself is a client-side callback (`fence_probe_fn(tool, caid, next_attempt_no) -> bool`). **We have not specified a wire format for it.** That is the open design question for a SEP: a `tools/call` variant, a new `operations/*` method, or a capability flag.
- The proxy cannot verify that the target really enforces a fence or deadline; it trusts the target's acknowledgement.

## 6. Reproduce

```
python3 src/eo1_protocol_model_checker.py
python3 benchmarks/eo1_real_duplicate_benchmark.py --n 300 --seed 42      # about 20 minutes
python3 -m pytest tests/test_eo1_reconciliation_adapter.py tests/test_idempotent_mcp_proxy.py tests/test_eo1_protocol_model_checker.py -q
```

Full write-up and per-fault tables: `docs/benchmarks/EO1_REAL_DUPLICATE_BENCHMARK.md`.

## 7. Limitations

Single host, loopback HTTP, one filesystem, one target implementation written by us. No network partitions, no transport redelivery, no Byzantine read-back. The retry-delay mix in F9 is our choice. The fence and deadline paths are tested against our own cooperating target; no third-party MCP server was tested. Not evidence of anything about production systems.
