# AEIB v1.0 — Release Notes (Zone 1 Open Core)

## Scope

This release distributes the Zone 1 open-core specification under Apache 2.0:
- Transport-to-disposition mapping (15-vector normative contract).
- CAID derivation (RFC 8785 JCS).
- Industrial-protection-inspired execution safeguards.
- Offline SCITT-style receipt verifier.
- 500-episode deterministic benchmark harness.

Zone 2 enterprise components (connection lease poolers, HSM enclaves, regulatory exporters, multi-tenant RLS) are not included and remain under the Sovereign Commercial License.

## Verification

```bash
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
pytest tests/test_industrial_protection_matrix.py tests/test_ansi_50bf_breaker_failure.py tests/test_saga_compensation.py tests/test_falsifiability_matrix.py -v
```

Zone 1 verification suite: 32 tests across protection matrix, probe-failure escalation, saga compensation, and falsifiability.
Additional six-gaps tests exist under Zone 2 and are not part of the open-core distribution.

Observed (seed 42, `--episodes 500`):
- Arm 1 (naive retry): 500/500 duplicate writes (by construction).
- Arm 2 (payload-derived key): 314/500 (62.8%) duplicate writes. 62.8% is a configured drift target, not an empirical measurement of agent behavior.
- Arm 3 (server-side stable key): 0 duplicate writes, 99 unresolved.
- Arm 4 (AEIB): 0 duplicate writes out of 500 episodes in a deterministic simulation; 368 duplicate retry attempts were blocked by AEIB logic (334 by the probe gate, 34 by ledger idempotency after a stale-replica probe). The remaining 132 episodes end in refusal, conflict, or not-found dispositions without a dispatch.

About the harness:
- The 500-episode harness is a deterministic simulation of the retry-duplication mechanism over 15 fault classes, using an in-memory ledger.
- It demonstrates internal consistency of the AEIB protocol logic (finality, retry blocking, reconciliation), not real-world duplicate rates.
- The Rule-of-Three bound (<= 0.60%) applies to this simulation only.

Latency:
- In-process Python verifier (`scripts/benchmark_latency.py`, 10,000 iterations): p99 of roughly 5-10 us and about 230k receipts/s single-threaded on the development machine. Figures vary run to run. This is not a WASM measurement.

## Known limitations

- Industrial-protection terminology is conceptual only; AEIB does not implement ANSI/IEEE/IEC protection functions or interoperate with IEC 61850 equipment.
- LaTeX source is provided uncompiled.
- Zenodo DOI for this release is pending final deposit.
- The VERITAS OS citation's DOI is pending verification and will be corrected before arXiv submission.

## Licensing

Zone 1: Apache-2.0. Zone 2: Commercial / trade secret (not included).
Contact: andrejlo123@gmail.com
