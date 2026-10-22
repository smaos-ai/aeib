# EU DORA (Regulation (EU) 2022/2554) Primary Technical Crosswalk

## 1. Regulatory Scope
Maps AEIB / SMF runtime controls to the Digital Operational Resilience Act (DORA) technical standards for financial entities deploying autonomous AI workflows, evaluated under the stated model.

| DORA Article | Regulatory Requirement | AEIB Architectural Control & Module | Verification Gate |
| --- | --- | --- | --- |
| **Article 9** | Protection and Prevention (ICT access & cryptographic policy) | Station 1 Ed25519 capability warrants, tenant namespace isolation (`AT66`), and RFC 8785 JCS CAID pinning (`src/runtime_boundary/runtime_execution_boundary.py`). | `tools/phase0_integrity_reset_core.py` |
| **Article 10** | Detection (Anomalous activity & drift detection) | Sybil dual-window velocity tracking (`AT56`), Defection Activation Probe (`src/defection_activation_probe.py`), and Hypergraph Causal Collusion detector (`src/hypergraph_causal_audit.py`). | `tests/test_sybil_rotator_and_smurfing.py` |
| **Article 11** | Response and Recovery (Deterministic containment) | Station 2 `EFFECT_INDETERMINATE` escrow hold (`AT58`) and Non-Dilutable Conflict Register (`compliance/eac_typestate_conflict_engine.py`). | `benchmarks/stochastic_saga_chaos/run_chaosbench.py` |
| **Article 17** | ICT-Related Incident Management & Classification | 3-Question Incident Evidence Separation (`attempted_model_proposal`, `boundary_authorization_state`, `observed_target_consequence`) in `tools/scitt_ap2_x402_otel_engine.py`. | `tools/scitt_ap2_x402_otel_engine.py` |
| **Article 19** | Reporting of Major ICT-Related Incidents | Offline-verifiable RFC 9052 `COSE_Sign1` + RFC 9942 SCITT transparency receipts (`tools/standalone_offline_verifier.py`). | `tests/test_standalone_offline_verifier.py` |
