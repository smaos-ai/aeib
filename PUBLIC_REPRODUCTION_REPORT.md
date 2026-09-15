# AEIB v0.1.0 Reproduction Report

## Scope

AEIB v0.1.0 is the Agent-Effect Integrity Benchmark. It evaluates ten
synthetic JSONL scenarios using six declared dispositions:

```text
INVALID_INPUT
MISSING_EVIDENCE
CONFLICT
REFUSED
CONFIRMED
UNKNOWN
```

The benchmark does not establish production security, DORA compliance,
external-system truth, regulatory incident classification, complete telemetry
coverage, or universal agent safety.

## Repository Details

- Repository: `smaos-ai/aeib`
- Tag: `v0.1.0`
- Tag commit: `7df056e6e49bb119efb611a9a17241b7c8b2c68c`
- Entrypoints: `run.py`, `score.py`

This report was added to the `main` branch after the v0.1.0 tag and documents reproduction of that immutable tag.

## Quickstart Procedure

```bash
git clone --branch v0.1.0 https://github.com/smaos-ai/aeib.git
cd aeib
docker compose run --rm benchmark
```

The benchmark container was run with `network_mode: "none"` in both reported
tests. The declared container command executed the reference runner and
score comparison from the repository root.

## Test Environments

### Run A: macOS

- OS: macOS 15.3.1, Darwin 24.3.0
- Architecture: arm64, Apple Silicon M3 Pro
- Python: 3.14.3
- Docker: 29.1.3
- Container isolation: `network_mode: "none"`

### Run B: Linux

- OS: Ubuntu 24.04.1 LTS
- Architecture: x86_64
- Python: 3.12.3
- Docker: 27.3.1
- Container isolation: `network_mode: "none"`

## Execution Results

- Fixture inputs tested: 10
- Expected outputs matched: 10/10
- Scorecard match rate: 100%
- Runner exit code: 0
- Scoring command: `python3 score.py`
- Scoring exit code: 0
- Consecutive-run console difference: 0 bytes
- Generated result artifacts: identical across both runs
- SHA-256 manifest verification: 21/21 entries verified

The 21 manifest entries comprise 10 fixture inputs, 10 expected outputs,
and 1 verification metadata file.

## Experimental Memory Extension

This section is not part of AEIB v0.1.0 scoring.

The isolated memory benchmark measures constraint recall, procedural ordering,
and locality across five synthetic compaction scenarios.

- Observed decay slope: −0.0133 per pass.
- Locality-leak change: −100 percentage points, from 100% to 0% in the stated synthetic test.

These are observed results from synthetic scenarios. They do not establish
production memory stability, complete multi-tenant isolation, or universal
protection against context degradation.

## Interpretation

The reported runs demonstrate that the released AEIB package produced the same
benchmark outputs under the stated local procedures and environments.

They do not establish:

- production security;
- DORA or EU AI Act compliance;
- regulatory incident classification;
- external-system or ledger truth;
- complete telemetry coverage;
- universal agent safety;
- effectiveness against all agent architectures.
