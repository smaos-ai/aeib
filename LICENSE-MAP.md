# AEIB v0.4.1 License Mapping & Dual-Licensing Architecture

This repository adopts an explicit, clean separation between executable software implementation and specification/documentation assets to ensure seamless enterprise adoption, auditability, and academic reuse.

---

## 1. Summary of Applicable Licenses

| Asset Category | Applicable License | Canonical License Text | Scope & Target Directory |
| :--- | :--- | :--- | :--- |
| **Software Core & Harnesses** | **Apache-2.0** | [`LICENSES/APACHE-2.0.txt`](LICENSES/APACHE-2.0.txt) | `src/`, `tests/`, `benchmarks/`, `scripts/`, `verifier/`, `ebpf/`, `public_html/`, build scripts |
| **Specifications & Evidence** | **CC-BY-4.0** | [`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt) | `docs/`, `schemas/`, `compliance/`, `evidence/`, `fixtures/`, regulatory templates |

---

## 2. Directory Breakdown

### A. Apache License 2.0 (`Apache-2.0`)
Applies to all source code, software libraries, tests, benchmark runners, Docker definitions, and offline verification binaries:
- `src/`: Core Python runtime modules (`aeib_gateway_adapter.py`, `probe_coalescer.py`, `process_trace_guard.py`, `evidence_registry_client.py`, `mcp_schema_pinning.py`, `jcs_canonicalizer.py`, `governance_boundary.py`, etc.).
- `verifier/`: Offline verification engines (`smaos_verify.wasm`, `verify_attestation.py`).
- `tests/`: Adversarial batteries, unit tests, and integration test suites (`tests/tier5_adversarial/`, `tests/test_*.py`).
- `benchmarks/`: Deterministic 500-episode execution-integrity harnesses and simulation vectors.
- `ebpf/`: Linux kernel execution filter scaffolds (`aeib_sock_filter.c`, `ebpf_lsm_agent_guard.c`).
- `public_html/`: Offline browser verifier UI application.
- Container configs: `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `pyproject.toml`.

### B. Creative Commons Attribution 4.0 International (`CC-BY-4.0`)
Applies to all formal specifications, documentation, threat models, regulatory crosswalks, schema specifications, and evaluation reports:
- `docs/`: Technical specifications, architectural blueprints, prior art analyses, CISO runbooks, threat models.
- `schemas/`: Machine-readable schemas (RFC 8785 canonical profiles, receipt payloads, DORA event definitions).
- `compliance/`: Regulatory guidance mappings (DORA RTS 2024/1772, ITS 2024/2956, ISO 42001 SoA documentation).
- `evidence/`: Canonical evidence fixtures, mock-free receipt envelopes, audit logs, and test vectors.
- `fixtures/`: Physical wire scenario definition fixtures (HTTP 504, TCP RST, Refused, Confirmed).

---

## 3. Zenodo Two-Record Deposit Alignment (Option A)

For permanent archival deposit, the package is separated into two cross-referenced Zenodo records:

1. **Zenodo Record 1 — Software (`.zenodo.software.json`)**:
   - Title: `AEIB v0.4.1: Execution-Integrity Reference Software and Test Harness`
   - Upload Type: `software`
   - License: `Apache-2.0`
   - Creator: `Leukhin, Andrej` (ORCID: `0009-0004-9543-8263`, Affiliation: `SovereignNexus`)
   - Relation: `isSupplementTo` Record 2

2. **Zenodo Record 2 — Specifications and Evidence Artifacts (`.zenodo.spec.json`)**:
   - Title: `AEIB v0.4.1: Benchmark Specifications and Regulatory Evidence Artifacts`
   - Upload Type: `publication`
   - License: `cc-by-4.0`
   - Creator: `Leukhin, Andrej` (ORCID: `0009-0004-9543-8263`, Affiliation: `SovereignNexus`)
   - Relation: `isSupplementedBy` Record 1
