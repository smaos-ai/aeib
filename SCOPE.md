# AEIB (`v1.0.0-rc.5-preprod`) — Scope & Epistemic Boundary Manifest

## 1. Frozen Core Scope
AEIB (`v1.0.0-rc.5-preprod`) is a **pre-production reference prototype and deterministic verification harness** for an **Agent Execution Integrity Boundary (AEIB)** operating across 3 Stations and 7 Core Components:

1. **Station 1 — Pre-Dispatch Authorization & Escrow Gate**:
   - Canonical RFC 8785 / `canonical_json_v1` serialization and Content-Addressed Action Identifier (`CAID`) verification.
   - Pure taint-tier provenance enforcement (`AT57b`: `TIER_2_UNTRUSTED` consequential mutations blocked structurally without keyword heuristics).
   - Monotonic delegation attenuation (`max_per_call_minor` and `sprint_limit_minor`).
   - Explicit versioned workflow preconditions (`required_prior_effects`).
2. **Station 2 — Durable Escrow State Machine & Uncertainty Latch**:
   - Synchronous SQLite WAL reservation (`DISPATCHED -> CONFIRMED | REFUTED | EFFECT_INDETERMINATE | UNRESOLVED_ESCALATED`).
   - Preserves budget reservations across HTTP `5xx` / timeout failures (`AT58`) and blocks blind retries until out-of-band target reconciliation completes.
   - Multi-AZ `SerializableMultiNodeConsensusBackend` (`2-of-3` quorum with per-replica Kleppmann monotonic `fencing_token` enforcement).
3. **Station 3 — Offline-Verifiable Receipts & Supply-Chain Transparency**:
   - Boot-time ledger re-verification (`G3`: recomputes every `CAID`, verifies every Ed25519 signature, validates hash-chain continuity, and checks external continuity anchors).
   - IETF SCITT (`RFC 9943`) & COSE Merkle inclusion proofs (`RFC 9942`, header label `394`).
   - OpenTelemetry GenAI (`v1.43.0`) span/event privacy separation and ECMA-424 CycloneDX `v1.6` CBOM export.
4. **Decide v4.5 Epistemic & Mathematical Anti-Decay Engine**:
   - Solves Knowledge Integration Decay (`SAKE`, `arXiv:2602.09517`), Shannon Data Processing Inequality handoff loss (`DPI`, `arXiv:2604.02460`), Submodular Search Exhaustion (`IG-Search` + `CELF`, `arXiv:2604.15148`), and Step-Level 3-Way Verification (`Pass^8` across 5-hop trajectories).

## 2. Out-of-Scope / Structural Scaffolding Boundaries
- **Hardware TEE & Kernel eBPF (`ebpf/`, `hardware_attestation/`)**: Structural user-space contracts and policy compilers (`src/bpf_lsm_profile_compiler.py`) ready for Linux kernel `BPF_LSM` / hardware enclave integration; not claimed as live kernel enforcement on macOS/Darwin hosts.
- **Distributed Saga Compensation**: Provides eventual consistency via asynchronous compensation queues, whereas `Station 1/2` TCC escrow + target fencing tokens provide pre-dispatch reservation locks.
- **Live Third-Party LLM Weights**: `benchmarks/public_sota_adapter.py` executes deterministic seeded archetype replays (`claim_tier = "MEASURED_LOCAL_ARCHETYPE_DETERMINISTIC_REPLAY_SEED_42"`), explicitly distinguished from live frontier weight API runs.

## 3. Epistemic Language Calibration
All documentation, code comments, and compliance artifacts strictly adhere to `AGENTS.md` Rule 1:
- **Permitted Terms**: `"observed"`, `"tested"`, `"evaluated"`, `"configured"`, `"under the stated model"`, `"prototype"`, `"scaffold"`, `"pre-production"`.
- **Prohibited Promotional Language**: Any absolute security claims, universal proof claims, or unverified readiness labels are strictly excluded and enforced via `compliance/ast_purity.py` and `tests/test_epistemic_regression_e01_e14.py`.
