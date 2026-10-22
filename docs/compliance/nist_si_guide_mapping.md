# NIST / CISA / NSA 5-Stage Software Integrity & Agent Security Crosswalk

## 1. Scope
Maps the 5-stage Software & Execution Integrity lifecycle to AEIB / SMF (`v1.0.0-rc.3`) controls, evaluated under the stated model.

| Lifecycle Stage | Control Objective | AEIB / SMF Implementation | Verification Test |
| --- | --- | --- | --- |
| **Stage 1: Code & Context Provenance** | Prevent unverified code execution and context poisoning | Bell-LaPadula `TIER_2_UNTRUSTED` taint lattice (`AT57b`, `AT60`) + PERSIST memory gate (`src/persist_memory_gate.py`). | `tests/test_hlc_hypergraph_and_persist_gate.py` |
| **Stage 2: Supply-Chain & Tool Pinning** | Defeat MCP tool description rug pulls and cross-server shadowing | MCP `tools/list` JCS CAID pinning (`AT63`, `AT63b`) in `tools/scitt_ap2_x402_otel_engine.py`. | `tests/test_tool_provenance_and_otel.py` |
| **Stage 3: Pre-Dispatch Authorization** | Enforce non-bypassable epistemic-ontic ordering and budget ceilings | Typestate Epistemic-Ontic Gate (`compliance/eac_typestate_conflict_engine.py`) + SQLite WAL TCC Escrow (`AT58`). | `tests/test_eac_typestate_conflict_engine.py` |
| **Stage 4: Runtime Sandboxing & Hot-Reload Lock** | Block mid-session self-authored plugin injection and RCE | Pre-session registry freeze (`AT67`, `AT68`) and AST policy gate (`CVE-2026-33017`). | `tests/test_opencode_codemode_hotreload.py` |
| **Stage 5: Cryptographic Transparency & CBOM** | Post-quantum algorithm agility and verifiable audit trails | RFC 9052 `COSE_Sign1`, RFC 9942 SCITT Merkle log, and ECMA-424 CycloneDX v1.6 CBOM. | `tools/scitt_ap2_x402_otel_engine.py` |
