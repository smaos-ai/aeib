# AEIB: Agent-Effect Integrity Benchmark

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: v0.1.0](https://img.shields.io/badge/Status-v0.1.0-blue.svg)](PUBLIC_REPRODUCTION_REPORT.md)
[![Network: Disabled](https://img.shields.io/badge/Network-disabled-orange.svg)](ENVIRONMENT.md)

> **Target Audience**: **AI Safety Researchers, QA Engineers, Agentic Framework Authors**  
> **The Problem**: Agent state machines fail unpredictably when downstream microservices return non-deterministic errors.  
> **Quantified Benefit**: **100% Offline Reproducibility** | **0 Cloud Egress / $0 Telemetry Tax**.

---

> **AEIB is an offline benchmark for testing whether an agent harness preserves uncertainty when a consequential external action cannot be confirmed.**

## Overview

Most agent evaluations measure the final answer. **AEIB** evaluates a narrower operational question: when an agent dispatches a consequential action and the downstream system times out, fails, or returns contradictory evidence, does the harness preserve uncertainty?

Part of the **SMAOS** framework for **Agent Evidence Integrity**.

- **Reference benchmark** — tests disposition precedence and preservation of unresolved `UNKNOWN` outcomes against 10 declared synthetic JSONL scenarios.
- **Offline reference execution** — container runs under `network_mode: "none"` with zero credentials or network egress.
- **Deterministic scoring** — evaluates classification outputs against six declared dispositions:

```text
INVALID_INPUT
→ MISSING_EVIDENCE
→ CONFLICT
→ REFUSED
→ CONFIRMED
→ UNKNOWN
```

## Core Invariant

When qualifying external evidence is absent or contradictory, an attempted action must not be represented as confirmed merely because a dispatch occurred, a retry was attempted, or an ambiguous response was received.

## Quickstart

Run the benchmark locally using Docker:

```bash
git clone --branch v0.1.0 https://github.com/smaos-ai/aeib.git
cd aeib
docker compose run --rm benchmark
```

The documented reference container uses `network_mode: "none"` and requires no credentials or cloud services. This describes the reference invocation, not every possible host, plugin, or developer configuration.

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

AEIB is the only component in this repository. Other SMAOS tools and commercial services are separate projects and are not required to run AEIB. Commercial evaluation services, if available, are scoped separately from this repository.

Some future SMAOS services may be relevant to evidence-handling or operational-risk work associated with DORA Articles 28–30 and EU AI Act Articles 12 and 14. This repository does not assess applicability, determine compliance, or provide legal advice.

## Limitations & Disclaimer

AEIB v0.1.0 demonstrates reproducibility of the benchmark under the stated test environment. It does not establish production security, DORA or EU AI Act compliance, regulatory incident classification, external-system or ledger truth, complete telemetry coverage, or universal agent safety.

See [LIMITATIONS.md](LIMITATIONS.md) and [PUBLIC_REPRODUCTION_REPORT.md](PUBLIC_REPRODUCTION_REPORT.md) for full normative disclaimers and reproduction telemetry.

## Independent Reproduction & Telemetry

We log independent third-party reproduction runs to document the cross-platform determinism of the benchmark package.

Submit telemetry using the [Reproduction Report issue template](.github/ISSUE_TEMPLATE/reproduction.yml). Required fields are host OS, CPU architecture, Docker/Python versions, exit code, scorecard match count, and the tag or commit tested.

Do not submit proprietary logs, production data, or enterprise credentials. Submit only synthetic reproduction telemetry or sanitized examples.

See [PUBLIC_REPRODUCTION_REPORT.md](PUBLIC_REPRODUCTION_REPORT.md) for our clean-machine baseline report.

## Alternate-Language Implementations

AEIB is designed as a language-agnostic specification of action uncertainty. We invite researchers and developers to create independent implementations of the reference classifier and scorer in Rust, Go, TypeScript, or other languages.

Alternate implementations must conform to the six-disposition priority cascade specified in `SPEC.md` and match the expected disposition and required reason markers for all 10 canonical fixtures.

Open an issue or pull request to link an implementation. See `CONTRIBUTING.md` for contribution guidelines.

## Security & Responsible Disclosure

For security inquiries or vulnerability reports, see [SECURITY.md](SECURITY.md). Please report vulnerabilities privately via GitHub Private Vulnerability Reporting or to `andrejlo123@gmail.com`.

---

### 💼 Staging Forensic Audit
Operating mutating AI workflows? We deliver 5-day bounded audits (€1,500 intro rate / €2,500 standard) under NDA with a guaranteed `git apply fix.patch`.  
- **Tier 1 Diagnostic (€1,500 / 48-Hour Sprint)**: Ingest 250+ staging traces, compute Toxic Receipt Index (TRI %), map retry hazards.
- **Tier 2 Forensic Audit (€2,500 / 5-Day Sprint)**: Full wire-level fault injection, 30-day trace analysis, and delivery of a `git apply fix.patch` remediation.

📩 **Contact**: [andrejlo123@gmail.com](mailto:andrejlo123@gmail.com)

