# AEIB v0.1.0 Reproduction Report

## Scope

AEIB v0.1.0 is the Agent-Effect Integrity Benchmark. It evaluates ten synthetic JSONL scenarios using six declared dispositions:

INVALID_INPUT
→ MISSING_EVIDENCE
→ CONFLICT
→ REFUSED
→ CONFIRMED
→ UNKNOWN

The benchmark does not establish production security, DORA compliance, external-system truth, regulatory classification, or universal agent safety.

## Repository Details

- Repository: `smaos-ai/aeib`
- Tag: `v0.1.0`
- Commit: `7df056e6e49bb119efb611a9a17241b7c8b2c68c`
- Entrypoints: `run.py`, `score.py`

## Quickstart Procedure

```bash
git clone --branch v0.1.0 https://github.com/smaos-ai/aeib.git
cd aeib
docker compose run --rm benchmark
```

The benchmark container was run with `network_mode: "none"` in the reported test.

## Test Environments

### Run A (macOS Execution)
- OS: macOS 15.3.1 (Darwin 24.3.0)
- Architecture: arm64 (Apple Silicon M3 Pro)
- Python: 3.14.3
- Docker: 29.1.3
- Container Isolation: `network_mode: "none"`

### Run B (Linux Execution)
- OS: Ubuntu 24.04.1 LTS
- Architecture: x86_64
- Python: 3.12.3
- Docker: 27.3.1
- Container Isolation: `network_mode: "none"`

## Execution Results

- Fixture Inputs Tested: 10
- Expected Outputs Matched: 10
- Scorecard Match Rate: 100% (10/10)
- Runner Exit Code: 0
- Second-Run Output Difference: 0 bytes
- Hash Manifest Verification (`verification.txt`): 21/21 SHA-256 digests OK

## Experimental Memory Extension (Separate Appendix)

The isolated memory benchmark measures constraint recall, procedural ordering, and locality across five synthetic compaction scenarios.

- Observed decay slope: −0.0133 per pass.
- Locality-leak change: −100 percentage points (from 100% to 0% in synthetic test).

This result is experimental and is not zero; no conclusion about production memory stability is drawn. The memory module is decoupled from AEIB v0.1.0 core scoring.

## Interpretation

The reported run demonstrates that the released AEIB package produced the same benchmark outputs under the stated local test procedure and environment.

This result does not establish:
- production security;
- DORA or EU AI Act compliance;
- regulatory incident classification;
- external-system or ledger truth;
- complete telemetry coverage;
- universal agent safety;
- effectiveness of the benchmark against all agent architectures.
