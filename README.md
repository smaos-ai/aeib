# Agent External Invariant Benchmark (AEIB) v0.1

AEIB is a public reference benchmark for testing whether an agent harness preserves uncertainty when an external effect cannot be confirmed. Anyone can run the same scenarios locally, inspect the expected outcomes, and submit reproducible results.

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
├── LICENSE
├── README.md
├── SPEC.md
├── verification.txt
├── verify_release.sh
├── Makefile
├── pyproject.toml
├── fixtures/
│   ├── source_contract.json
│   ├── 01_confirmed_settlement.jsonl
│   ├── 02_http_504_timeout.jsonl
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
│   └── verifier.py
└── expected/
    ├── 01_confirmed_settlement.json
    ├── 02_http_504_timeout.json
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

### 1. Verify Manifest Integrity
Verify that all test fixtures and expected scorecards match their cryptographic hashes:
```bash
python3 runner/verifier.py --manifest verification.txt
```

### 2. Run Reference Evaluation
Execute the benchmark harness over the test fixtures (designed for deterministic offline verification):
```bash
python3 runner/reference_runner.py fixtures/
```
Outputs `results.json` and `scorecard.json`.

### 3. Run Clean-Machine Release Verification
```bash
bash verify_release.sh aeib-v0.1.0.zip
```
