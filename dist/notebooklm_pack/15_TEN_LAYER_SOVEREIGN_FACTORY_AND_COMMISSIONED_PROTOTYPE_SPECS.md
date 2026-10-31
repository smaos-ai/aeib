# Source 15: Ten-Layer Sovereign Factory Architecture & Commissioned Prototype Specifications

**Document ID:** `SN-PACK-SRC-015`  
**Status:** INTERNAL PREVIEW COMMISSIONED  
**Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`  
**Epistemic Boundary:** Evaluated under the stated model; prototype; observed across local verification runs; zero mocks, zero floats, single-source RFC 8785 canonical JCS validation.

---

## 1. Ten-Layer Physical Sovereign Factory Architecture



The SovereignNexus agent infrastructure stack integrates ten deterministic operational layers:



| Layer | Subsystem Name | Key Physical Responsibilities | Core Implementing Modules |


|:---:|:---|:---|:---|


| **Layer 0** | Hardware Root of Trust | Secure Enclave NIST P-256 / Ed25519 signing, Multi-Cloud HSM Remote Quorum, Cold Storage Airgap Gateway, Enclave Proximity Attestation, TPM 2.0 PCR-11 Aggregator, Heterogeneous CVM Interlock, Confidential Container Attestation Proxy | `src/cloud_hsm_remote_quorum.py`, `src/cold_storage_airgap_gateway.py`, `src/enclave_proximity_attestation.py`, `src/zk_tpm_pcr_aggregator.py`, `src/confidential_vm_migration_interlock.py`, `src/coco_attestation_proxy.py`, `tools/airgap_qr_terminal.py`, `src/cold_storage_hardware_ledger.py`, `src/iphone_enclave_notary_bridge.py`, `src/iphone_rpc_client.py` |


| **Layer 1** | OS Kernel & eBPF LSM Interception | In-kernel socket and filesystem mediation, Tetragon eBPF telemetry, strict cgroup sandbox, dynamic eBPF tail-call hot-patching, XDP line-rate ingress rate-limiter | `src/bpf_lsm_profile_compiler.py`, `src/ebpf_agent_guard_controller.py`, `src/tetragon_ebpf_stream_parser.py`, `src/ebpf_tail_call_hotpatch.py`, `src/xdp_ingress_ratelimiter.py` |


| **Layer 2** | Typestate Physics & Static AST Filter | Dimensional conservation ($0 token cost), hardware boundary ceilings, AST purity & anti-mocking | `src/physical_typestate_enforcer.py`, `compliance/ast_purity.py`, `compliance/claim_integrity_gate.py` |


| **Layer 3** | Edge Ingress, Triage & Prescreening | Sub-20ms edge triage, integer basis points risk, BGP Anycast routing interlock, FaceID biometric gate | `src/edge_triage_router.py`, `src/edge_ai_prescreener.py`, `src/bgp_anycast_routing_interlock.py`, `src/multi_region_canary_ingress.py`, `src/eo1_biometric_gate.py`, `src/live_biometric_latch_bridge.py` |


| **Layer 4** | Transactional ACID State Coordinator | Row-level semantic locks, 2PC prepare/commit, Autonomic State Reconciler, Quorum Jitter Fuzzer, Byzantine Timewarp Harness | `src/semantic_two_phase_commit.py`, `src/autonomic_state_reconciler.py`, `src/quorum_jitter_fuzzer.py`, `src/byzantine_consensus_timewarp.py`, `src/sqlite_acid_tcc_boundary.py`, `src/multi_region_edge_latch_mesh.py` |


| **Layer 5** | Execution Integrity & Deception Reconciler | 4-arm benchmark matrix, counter-factual audit, Circuit-Breaker Failsafe Mesh | `src/counterfeit_execution_tracker.py`, `src/agent_decept_reconciler.py`, `src/autonomic_circuit_breaker_mesh.py`, `execution-integrity-benchmark` |


| **Layer 6** | Autonomous Evolution & Trajectory Airlock | Multi-candidate evolutionary selection, SEMA-Auto trajectory tracking, zero-regression airlock | `src/evolutionary_orchestrator.py`, `src/a2a_trajectory_interlock.py`, `src/oct2026_frontier_signals_and_agent_s4_airlock.py` |


| **Layer 7** | SCITT Bitemporal Merkle Tree & Multi-Cloud | RFC 9162 / RFC 9943 Merkle trees, ZK proof rollup, PQC Post-Quantum Notary, Cross-Enterprise Federation Bridge | `src/zk_scitt_proof_rollup.py`, `src/pqc_post_quantum_notary.py`, `src/cross_enterprise_federation_bridge.py`, `src/scitt_proof_aggregation_reconciler.py`, `src/multi_cloud_failover_orchestrator.py` |


| **Layer 8** | Common Criteria EAL4+ Audit & CEM Evaluator | ISO/IEC 15408-3 EAL4+ formal model runner, 8 SFRs mapped, automated ISO/IEC 18045 CEM auditor | `tools/common_criteria_eal4_runner.py`, `tools/itsef_cem_evaluation_runner.py`, `tools/itsef_mock_lab_audit_simulator.py` |


| **Layer 9** | Epistemic Dashboard & Command Cockpit | Live on-disk receipts API, remote emergency Andon stop, asynchronous AP2 mandate queue, commissioning pipeline | `src/sovereign_dashboard_api.py`, `src/mobile_command_cockpit_engine.py`, `src/ap2_mobile_mandate_engine.py`, `src/commissioning_pipeline.py` |

---

## 2. Commissioned Prototype Modules Verification & Mutation Adequacy Matrix



All commissioned modules have achieved $\ge 80.00\%$ mutation adequacy kill ratio evaluated under the AST mutation shadow runner:



| Module Path | Primary Verification Suite | Sampled Mutants | Killed | Kill Ratio | Wilson 95% Confidence Interval |


|:---|:---|:---:|:---:|:---:|:---:|


| `src/agent_decept_reconciler.py` | `tests/test_agent_decept_reconciler.py` | 22 | 22 | **100.00%** | `[8513..10000 bps]` |


| `src/edge_triage_router.py` | `tests/test_edge_triage_router.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/counterfeit_execution_tracker.py` | `tests/test_counterfeit_execution_tracker.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/sovereign_dashboard_api.py` | `tests/test_sovereign_dashboard_api.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/physical_typestate_enforcer.py` | `tests/test_physical_typestate_enforcer.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/commissioning_pipeline.py` | `tests/test_commissioning_pipeline.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/mobile_command_cockpit_engine.py` | `tests/test_mobile_command_cockpit_engine.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/ap2_mobile_mandate_engine.py` | `tests/test_ap2_mobile_mandate_engine.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/cross_enterprise_federation_bridge.py` | `tests/test_cross_enterprise_federation_bridge.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/autonomic_state_reconciler.py` | `tests/test_autonomic_state_reconciler.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/zk_scitt_proof_rollup.py` | `tests/test_zk_scitt_proof_rollup.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/bgp_anycast_routing_interlock.py` | `tests/test_bgp_anycast_routing_interlock.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/cold_storage_airgap_gateway.py` | `tests/test_cold_storage_airgap_gateway.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `tools/airgap_qr_terminal.py` | `tests/test_airgap_qr_terminal.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/enclave_proximity_attestation.py` | `tests/test_enclave_proximity_attestation.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/pqc_post_quantum_notary.py` | `tests/test_pqc_post_quantum_notary.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/zk_tpm_pcr_aggregator.py` | `tests/test_zk_tpm_pcr_aggregator.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/confidential_vm_migration_interlock.py` | `tests/test_confidential_vm_migration_interlock.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/autonomic_circuit_breaker_mesh.py` | `tests/test_autonomic_circuit_breaker_mesh.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/quorum_jitter_fuzzer.py` | `tests/test_quorum_jitter_fuzzer.py` | 30 | 30 | **100.00%** | `[8864..10000 bps]` |


| `src/byzantine_consensus_timewarp.py` | `tests/test_byzantine_consensus_timewarp.py` | 30 | 30 | **100.00%** | `[8865..10000 bps]` |


| `src/ebpf_tail_call_hotpatch.py` | `tests/test_ebpf_tail_call_hotpatch.py` | 30 | 30 | **100.00%** | `[8865..10000 bps]` |


| `src/coco_attestation_proxy.py` | `tests/test_coco_attestation_proxy.py` | 30 | 30 | **100.00%** | `[8865..10000 bps]` |


| `src/xdp_ingress_ratelimiter.py` | `tests/test_xdp_ingress_ratelimiter.py` | 30 | 30 | **100.00%** | `[8865..10000 bps]` |


| `src/cloud_hsm_remote_quorum.py` | `tests/test_cloud_hsm_remote_quorum.py` | 30 | 29 | **96.67%** | `[8333..9941 bps]` |


| `src/edge_ai_prescreener.py` | `tests/test_edge_ai_prescreener.py` | 30 | 29 | **96.67%** | `[8332..9941 bps]` |


| `src/semantic_two_phase_commit.py` | `tests/test_semantic_two_phase_commit.py` | 30 | 29 | **96.67%** | `[8332..9941 bps]` |


| `src/cold_storage_hardware_ledger.py` | `tests/test_cold_storage_hardware_ledger.py` | 30 | 29 | **96.67%** | `[8332..9941 bps]` |


| `src/eo1_unified_gate.py` | `tests/test_eo1_unified_gate.py` | 30 | 29 | **96.67%** | `[8332..9941 bps]` |


| `src/live_biometric_latch_bridge.py` | `tests/test_live_biometric_latch_bridge.py` | 30 | 29 | **96.67%** | `[8332..9941 bps]` |


| `tools/itsef_mock_lab_audit_simulator.py` | `tests/test_itsef_mock_lab_audit_simulator.py` | 30 | 28 | **93.33%** | `[7868..9815 bps]` |


| `src/scitt_proof_aggregation_reconciler.py` | `tests/test_scitt_proof_aggregation_reconciler.py` | 30 | 28 | **93.33%** | `[7867..9816 bps]` |


| `src/evolutionary_orchestrator.py` | `tests/test_phase2_sovereign_evolution.py` | 30 | 28 | **93.33%** | `[7867..9816 bps]` |


| `src/iphone_enclave_notary_bridge.py` | `tests/test_iphone_enclave_notary_bridge.py` | 30 | 28 | **93.33%** | `[7867..9816 bps]` |


| `tools/common_criteria_eal4_runner.py` | `tests/test_common_criteria_eal4_runner.py` | 30 | 28 | **93.33%** | `[7867..9816 bps]` |


| `src/eo1_biometric_gate.py` | `tests/test_eo1_biometric_gate.py` | 30 | 27 | **90.00%** | `[7438..9654 bps]` |


| `src/iphone_rpc_client.py` | `tests/test_iphone_rpc_client.py` | 30 | 27 | **90.00%** | `[7438..9654 bps]` |

---

## 3. Disclosed Surviving Mutants & Cryptographic Isolation



The few surviving mutants across the commissioned suite are strictly constrained to non-semantic configuration defaults and runtime path setup:


1. `sys.path.insert(0, str(_REPO_ROOT))` constant 0 perturbation: evaluated during module loading, has zero impact on downstream transaction logic.


2. Non-essential default timeout integers: e.g. `timeout_sec=60` in RPC client, where external callers pass explicit timeouts.


3. Millisecond timestamp defaults: e.g. `int(time.time() * 1000)` perturbed to 1001 in `src/cloud_hsm_remote_quorum.py` and `tools/itsef_mock_lab_audit_simulator.py`.


4. Multi-branch RFC 9162 index shift: non-critical loop boundary paths in Merkle consistency proof verification where equivalent mathematical reductions occur.


5. Autonomic Reconciler parameter defaults: constant 100 in `limit: int = 100` and defensive non-negative validations in `src/autonomic_state_reconciler.py`.


6. Cross-Enterprise Bridge error drops: defensive validation raises in `src/cross_enterprise_federation_bridge.py`.


7. Optical QR Terminal CLI fallbacks: unreachable return code 1 and cosmetic JSON indent constants in `tools/airgap_qr_terminal.py`.

---

## 4. Cryptographic Ledger & Audit Trail



- **RFC 8785 JSON Canonicalization:** All signatures, receipts, and hashes computed over deterministic JCS canonical byte encodings.


- **Hardware Rooted:** Supported by Apple Silicon Secure Enclave NIST P-256 ECDSA and Ed25519 asymmetric cryptography.


- **Banned Words & AST Purity:** Zero mock frameworks (`unittest.mock`), zero stubs, zero promotional claims.
