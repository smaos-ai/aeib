# AEIB: Agent-Effect Integrity Benchmark

> **AEIB is an offline benchmark for testing whether an agent harness preserves uncertainty when a consequential external action cannot be confirmed.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Release Candidate](https://img.shields.io/badge/Status-v0.1.0_Verified-green.svg)](LIMITATIONS.md)
[![Isolation: Air-Gapped](https://img.shields.io/badge/Network---network_none-orange.svg)](ENVIRONMENT.md)

---

## Overview

Most agent evaluations measure the final answer. **AEIB** evaluates a narrower operational question: when an agent dispatches a consequential action and the downstream system times out, fails, or returns contradictory evidence, does the harness preserve uncertainty?

Part of the **SMAOS** framework for **Agent Evidence Integrity**.

- **Reference benchmark** — tests disposition precedence and UNKNOWN-state handling against 10 synthetic JSONL scenarios.
- **Air-gapped execution** — container runs under `network_mode: "none"` with zero credentials or network egress.
- **Deterministic scoring** — evaluates classification outputs against six declared precedence states:

```text
INVALID_INPUT
→ MISSING_EVIDENCE
→ CONFLICT
→ REFUSED
→ CONFIRMED
→ UNKNOWN
```

## Quickstart

Run the benchmark locally using Docker:

```bash
git clone --branch v0.1.0 https://github.com/smaos-ai/aeib.git
cd aeib
docker compose run --rm benchmark
```

The container executes the reference runner (`run.py`) and scoring script (`score.py`) internally without network access.

## Disposition Precedence

When evaluating external action evidence, AEIB verifies whether the harness respects the following strict priority cascade:

- **`INVALID_INPUT`**: Malformed event payloads or broken schema structures.
- **`MISSING_EVIDENCE`**: Required execution proof or receipt is absent.
- **`CONFLICT`**: Contradictory evidence returned from counterparty or logs.
- **`REFUSED`**: Action explicitly rejected or blocked downstream.
- **`CONFIRMED`**: Downstream action positively confirmed with valid evidence.
- **`UNKNOWN`**: Unresolved timeout or indeterminate response state.

## Related Work

AEIB is the only component in this repository. Other SMAOS tools and commercial services are separate projects and are not required to run AEIB. Their availability, scope, and interfaces are documented separately.

Some future SMAOS services may be relevant to evidence-handling or operational-risk work associated with DORA Articles 28–30 and EU AI Act Articles 12 and 14. This repository does not assess applicability, determine compliance, or provide legal advice.

## Limitations & Disclaimer

AEIB v0.1.0 demonstrates reproducibility of the benchmark under the stated test environment. It does not establish production security, DORA or EU AI Act compliance, regulatory incident classification, external-system or ledger truth, complete telemetry coverage, or universal agent safety.

See [LIMITATIONS.md](LIMITATIONS.md) for full normative disclaimers.

## Independent Reproduction & Telemetry

We log independent third-party reproduction runs to document the cross-platform determinism of the benchmark package.

- **How to report**: Submit your run telemetry via the [Reproduction Report Issue Template](.github/ISSUE_TEMPLATE/reproduction_report.md).
- **Required fields**: Host OS, CPU architecture, Docker/Python versions, exit code, and scorecard match count.
- **Zero Proprietary Data Policy**: Do **not** submit proprietary logs, production data, or enterprise credentials. Submit only synthetic reproduction telemetry or sanitized examples.
- **Public Report**: View our clean-machine baseline report in [PUBLIC_REPRODUCTION_REPORT.md](PUBLIC_REPRODUCTION_REPORT.md).

## Alternate-Language Implementations

AEIB is designed as a language-agnostic specification of action uncertainty. We invite researchers and developers to create independent implementations of the reference classifier and scorer in **Rust**, **Go**, **TypeScript**, or other languages:

- Alternate implementations MUST adhere strictly to the 6-disposition priority cascade specified in [SPEC.md](SPEC.md).
- Implementations MUST produce bit-exact matches against the golden scorecards in `expected/` for all 10 canonical fixtures.
- Open an issue or pull request to link your implementation. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Security & Responsible Disclosure

For security inquiries or vulnerability reports, see [SECURITY.md](SECURITY.md). Please report vulnerabilities privately via GitHub Private Vulnerability Reporting or to `security@smaos.ai`.
