# AEIB v1.0 — Release Notes (Zone 1 Open Core)

## Scope

This release distributes the Zone 1 open-core specification under Apache 2.0:
- Transport-to-disposition mapping (18-entry versioned contract: 15 transport-fault vectors + 3 governor patterns).
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
python3 replication/reproduce_all.py
```

Zone 1 verification suite: 41 reproduced test cases (32 core baseline tests + 9 integration extension cases).

Observed (seed 42, `--episodes 500`):
- Arm 1 (naive retry): 302/500 duplicate external writes (on the 302 episodes where the initial write succeeded before transport fault).
- Arm 2 (payload-derived key): 187/500 (37.4%) duplicate external writes under simulated timestamp/UUID payload drift.
- Arm 3 (server-side stable key): 0 duplicate external writes, 198 unresolved.
- Arm 4 (AEIB): `duplicate_external_writes: 0 / 500` in a deterministic simulation; `duplicate_retry_attempts_blocked: 302` (`blocked_by_dispatch_gate: 234`, `blocked_by_ledger_deduplication: 68` after a stale-replica probe). The remaining 198 episodes end in policy refusal (`99`), not-found after grace (`66`), or reconciliation conflict (`33`).

About the harness:
- The 500-episode harness is a deterministic simulation of the retry-duplication mechanism over 15 fault classes, using an in-memory ledger.
- It demonstrates internal consistency of the AEIB protocol logic (uncertain-transport outcome classification, retry blocking, reconciliation), not real-world duplicate rates.
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
