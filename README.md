# Agent-Effect Integrity Benchmark (AEIB) v0.1

Reference benchmark for action uncertainty — Tests fail-closed precedence and UNKNOWN-state handling when an external effect cannot be confirmed. Anyone can run the same scenarios locally, inspect the expected outcomes, and submit reproducible results.

The reference benchmark is configured to run without network access and does not require cloud services. Container execution uses `network_mode: "none"`; the reference benchmark does not require prompts, source code, or cloud services. This describes the reference configuration, not every possible host, plugin, or developer invocation.

## Overview

In autonomous agent systems, external state transitions (such as payment dispatches, database writes, or remote API calls) are subject to network timeouts, partitions, and ambiguous responses. A reliable agent harness must preserve uncertainty: an unconfirmed external effect must never be recorded as an unsupported success.

AEIB evaluates harnesses against 10 standardized synthetic scenarios representing timeout conditions, retry collisions, missing evidence, payload divergences, explicit refusals, and malformed inputs.

## AEIB v0.1 Evaluation Precedence

```text
INVALID_INPUT
→ MISSING_EVIDENCE
→ CONFLICT
→ REFUSED
→ CONFIRMED
→ UNKNOWN
```

### Dispositions and Meanings

- **`INVALID_INPUT`**: The row or event stream violates the input schema, cannot be parsed, or contains an invalid required structure.
- **`MISSING_EVIDENCE`**: Required dispatch or attribution evidence is absent, so the action cannot be reliably evaluated.
- **`CONFLICT`**: Valid evidence contains contradictory outcomes, payloads, ownership, or confirmation identities.
- **`REFUSED`**: The action was explicitly rejected and no higher-priority condition applies.
- **`CONFIRMED`**: A qualifying, matching confirmation exists and no higher-priority condition applies.
- **`UNKNOWN`**: The action was dispatched or claimed, but no qualifying confirmation, refusal, or conflict resolves the outcome.

### Precedence Rule

> Implementations MUST evaluate each action using the precedence order above. Implementations MUST NOT reorder the precedence per scenario. A higher-priority condition MUST determine the final disposition even when lower-priority evidence is also present. Secondary findings MAY be emitted, but they MUST NOT change the primary disposition.

## Directory Layout

```text
aeib/
├── .gitignore
├── Dockerfile
├── ENVIRONMENT.md
├── LICENSE
├── LIMITATIONS.md
├── Makefile
├── README.md
├── SPEC.md
├── docker-compose.yml
├── pyproject.toml
├── run.py
├── score.py
├── verification.txt
├── verify_release.sh
├── fixtures/
│   ├── 01_confirmed_settlement.jsonl
│   ├── 02_timeout_unknown.jsonl
│   ├── 03_missing_dispatch_evidence.jsonl
│   ├── 04_idempotency_collision.jsonl
│   ├── 05_conflicting_state_claim.jsonl
│   ├── 06_refused_policy_violation.jsonl
│   ├── 07_mismatched_payload.jsonl
│   ├── 08_malformed_input.jsonl
│   ├── 09_circuit_breaker_refusal.jsonl
│   └── 10_divergent_retry_payload.jsonl
├── runner/
│   ├── __init__.py
│   ├── reference_runner.py
│   ├── runner.py
│   ├── scorer.py
│   ├── spec_validator.py
│   └── verifier.py
└── expected/
    ├── 01_confirmed_settlement.json
    ├── 02_timeout_unknown.json
    ├── 03_missing_dispatch_evidence.json
    ├── 04_idempotency_collision.json
    ├── 05_conflicting_state_claim.json
    ├── 06_refused_policy_violation.json
    ├── 07_mismatched_payload.json
    ├── 08_malformed_input.json
    ├── 09_circuit_breaker_refusal.json
    └── 10_divergent_retry_payload.json
```

## Quickstart

### 1. Run in Isolated Container (Recommended)
Run the complete reference benchmark in an air-gapped container (`network_mode: "none"`):
```bash
docker compose run --rm benchmark
```
Expected output: `Total: 10, Passed: 10, Failed: 0` (exit code 0).

### 2. Verify Manifest Integrity
Verify that all 20 test fixtures and expected scorecards match their cryptographic hashes:
```bash
python3 runner/verifier.py --manifest verification.txt
```

### 3. Run Rule-Grounding Oracle
Run the standalone, independent specification oracle (zero runner dependencies):
```bash
python3 runner/spec_validator.py fixtures expected
```

### 4. Direct Python Execution
Run evaluation across all 10 scenarios and score against expected baselines:
```bash
python3 run.py fixtures/
python3 score.py
```
Or evaluate a single scenario:
```bash
python3 run.py fixtures/02_timeout_unknown.jsonl
```
