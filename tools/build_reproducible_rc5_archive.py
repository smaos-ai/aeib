"""
Deterministic Air-Gapped Reproducible Evidence Archive Builder (`v1.0.0-rc.5-preprod`).
- Runs Phase 0 + Tracks 1, 2, 3, and 4.
- Produces canonical, timestamp-free JSON evidence reports.
- Packages all source modules, TLA+ models, and reports into a deterministic tarball
  with fixed mtime (`SOURCE_DATE_EPOCH = 1760918400`), uid=0, gid=0, and sorted entries.
- Extracts the archive into an isolated clean-room directory and verifies every SHA-256 digest.
"""
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_agent_deception_interlock import (
    test_deception_interlock_nominal_and_tripwire_catches,
)
from tests.test_leviathan_and_cross_tenant_isolation import (
    test_cross_tenant_governor_seven_isolation_properties,
    test_leviathan_fts5_bounded_cards_and_invariant_retention,
)
from tests.test_otel_genai_evidence_chain import (
    test_evidence_receipt_hash_chain_and_tamper_detection,
    test_human_override_ledger_warrant_validation,
    test_otel_genai_semantic_span_attributes,
)
from tests.test_runtime_boundary_and_state_machine import (
    test_runtime_boundary_falsifications_and_uncertainty_latch,
    test_runtime_boundary_nominal_and_consequential_flow,
)
from tests.test_structural_cve_boundary_fixtures import (
    test_all_four_structural_cve_fixtures_and_aeib_containment,
)
from tests.test_cve_2026_33017_langflow_rce import (
    test_cve_2026_33017_aeib_ast_policy_gate_containment,
    test_cve_2026_33017_aeib_station1_taint_and_authorization_gate,
)
from tests.test_vibe_coding_and_long_horizon_guard import (
    test_gitai_bisect_isolates_breaking_patch,
    test_iaps_agent_honeypot_detection_and_deterrence,
    test_vibe_coding_missing_auth_and_rls_detection,
)
from tests.test_local_system1_leviathan_daemon import (
    test_screener_read_only_fast_path,
    test_screener_state_mutation_routing,
    test_daemon_subagent_handback_bounding,
    test_daemon_parent_memory_ceiling_and_packing,
    test_daemon_scoped_forgetting,
    test_banned_words_absence as test_local_daemon_banned_words,
)
from tests.test_hlc_hypergraph_and_persist_gate import (
    test_hlc_monotonicity_and_causal_ordering,
    test_causal_visibility_fence,
    test_hypergraph_emergent_collusion_sink_convergence,
    test_persist_memory_gate_memmorph_tool_redirect,
    test_banned_words_absence as test_hlc_gate_banned_words,
)
from tests.test_hansard_and_defection_probe import (
    test_hansard_choke_point_witnessing_and_dag_tip,
    test_hansard_attribution_laundering_detection,
    test_hansard_additive_harms_no_laundering,
    test_defection_probe_initialization_and_validation,
    test_defection_probe_benign_activation,
    test_defection_probe_defection_activation_halt,
    test_defection_probe_sigmoid_numerical_stability,
    test_banned_words_absence as test_hansard_defection_banned_words,
)
from tests.test_poseidon2_merkle_tree import (
    test_sbox_and_field_properties,
    test_linear_layers,
    test_poseidon2_permutation_avalanche_and_non_commutativity,
    test_poseidon2_hash_bytes_and_canonical_json,
    test_poseidon2_merkle_tree_construction_and_padding,
    test_poseidon2_merkle_tree_all_leaves_proof_verification,
    test_poseidon2_proof_serialization_roundtrip,
    test_tampered_leaf_rejected,
    test_tampered_sibling_rejected,
    test_wrong_expected_root_rejected,
    test_invalid_leaf_index_raises,
    test_empty_leaves_raises,
    test_banned_words_absence as test_poseidon2_banned_words,
)
from tests.test_tier3_post_perfection_matrix import (
    test_nash_equilibrium_nominal_and_exploit_detection,
    test_nash_equilibrium_matrix_validation,
    test_tee_cvm_lifecycle_allocation_and_read,
    test_tee_cvm_hardware_key_shredding_and_memory_scrubbing,
    test_tee_cvm_remanence_detection_falsification,
    test_wasm_symbolic_path_explorer_clean_and_bounds_check,
    test_wasm_symbolic_path_explorer_violations,
    test_actuarial_multisig_risk_calculation_and_escalation,
    test_actuarial_multisig_signature_verification,
    test_banned_words_absence as test_tier3_banned_words,
)
from scripts.verify_research_claims import (
    test_antigravity_decide_claim_verifier,
)
from tools.aeib_surviving_principles_engine import (
    test_five_surviving_principles_engine,
)
from tools.epistemic_action_compiler_ab_test import (
    test_epistemic_action_compiler_ab_evaluation,
)
from tests.test_epistemic_action_compiler import (
    test_epistemic_macros_execution,
    test_non_dilutable_conflict_register_tamper_and_resolution,
    test_epistemic_ontic_wire_gate_blocking,
    test_banned_words_absence as test_epistemic_compiler_banned_words,
)
from tests.test_palantir_ontology_joint_witness_engine import (
    test_canonical_jcs_float_rejection,
    test_nominal_6way_joint_witness_commit,
    test_proposal_to_commit_object_state_drift_rejection,
    test_caplease_semantic_replay_blocked,
    test_cim_narration_poisoning_silent_approval_bypass_rejected,
    test_post_qualification_authority_revocation_blocked,
    test_policy_or_epoch_drift_rejected,
    test_monotonic_subclass_tightening_treasury_harness,
    test_banned_words_absence as test_palantir_ontology_banned_words,
)
from tests.test_eac_typestate_conflict_engine import (
    test_end_to_end_p0_p1_gates,
    test_typestate_target_mismatch_and_invalid_signature,
    test_cryptographic_supervisor_conflict_resolution,
    test_banned_words_absence as test_eac_typestate_banned_words,
)
from tests.test_epistemic_core_bec import (
    test_1000_agent_phase_transition_simulation,
    test_missing_or_fabricated_bose_witness_rejected,
    test_provenance_entropy_synthetic_overload_rejected,
    test_intermediate_phase_transition_blocks_mutation,
    test_banned_words_absence as test_epistemic_core_bec_banned_words,
)
from tests.test_decide_v2_constant_time_snapshot import (
    test_o1_constant_time_codebase_snapshot_index_and_lookup,
    test_decide_v2_five_why_and_two_iteration_convergence,
    test_banned_words_absence as test_decide_v2_banned_words,
)
from tests.test_decide_categorical_epistemic_engine import (
    test_submodular_monotonicity_and_100x_pairwise_coverage,
    test_missed_operator_enforces_current_only_constraint,
    test_cross_ecosystem_brainstorm_gls_diversity_and_pair_decision_schema,
    test_current_missed_next_categorical_contraction_and_ed25519_receipt,
    test_banned_words_absence as test_decide_v3_banned_words,
)
from tests.test_cross_hemisphere_council_decide import (
    test_cross_hemisphere_council_and_3tier_ask_router_hold_and_dominance,
    test_cross_hemisphere_council_developer_answer_unlocks_synthesis,
    test_typed_cross_critique_prevents_tone_sycophancy_arxiv_2609_08016,
    test_current_missed_next_calculus_maxsat_and_nondilutable_register,
    test_banned_words_absence as test_cross_hemisphere_council_banned_words,
)
from tests.test_defense_in_depth_and_intent_outcome import (
    test_anti_disarmament_telemetry_protection,
    test_runtime_startup_hook_lockdown_litellm_vector,
    test_package_manager_step_up_gating,
    test_network_egress_intent_registration,
    test_epistemic_intent_outcome_two_phase_execution,
    test_banned_words_absence as test_defense_in_depth_banned_words,
)
from tools.cross_hemisphere_epistemic_council import (
    test_integrated_tri_partition_architecture,
)
from tools.epistemic_5why_loop import (
    test_epistemic_5why_fts5_merkle_and_conflict_loop,
    test_banned_words_absence as test_epistemic_5why_banned_words,
)
from tools.scitt_ap2_x402_otel_engine import (
    test_scitt_ap2_x402_otel_and_cbom_engine,
    test_banned_words_absence as test_scitt_ap2_x402_banned_words,
)
from benchmarks.stochastic_saga_chaos.run_chaosbench import (
    run_500_episode_chaosbench,
    test_stochastic_saga_chaosbench_500_episodes,
    test_banned_words_absence as test_chaosbench_banned_words,
)
from benchmarks.locomo_context_quality import evaluate_locomo_benchmark
from benchmarks.maseval_integration import run_maseval_comparative_benchmark
from tools.context_ram_and_maseval_harness import (
    test_context_ram_hawkes_and_dynamic_workflows,
)
from tools.phase0_integrity_reset_core import (
    canonical_json_v1,
    test_phase0_integrity_reset_all_blockers,
)
from tools.regulatory_three_tier_and_matrix import (
    generate_regulatory_applicability_matrix,
    test_three_tier_decision_gate_and_applicability_matrix,
)
from tools.smf_frontier_oct2026_upgrades import (
    test_smf_frontier_oct2026_upgrades,
)
from tools.tlaplus_model_conformance_checker import (
    explore_tla_state_space_and_verify_conformance,
)

FIXED_EPOCH = 1760918400  # 2025-10-20T00:00:00Z deterministic build timestamp


def _sanitize_for_canonical_json(val: Any) -> Any:
    if isinstance(val, float):
        return f"{val:.4f}"
    if isinstance(val, dict):
        return {k: _sanitize_for_canonical_json(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_for_canonical_json(x) for x in val]
    return val


def build_and_verify_deterministic_archive(output_dir: Path) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Execute all verification tracks
    test_phase0_integrity_reset_all_blockers()
    test_all_four_structural_cve_fixtures_and_aeib_containment()
    test_three_tier_decision_gate_and_applicability_matrix()
    test_context_ram_hawkes_and_dynamic_workflows()
    test_smf_frontier_oct2026_upgrades()
    test_runtime_boundary_nominal_and_consequential_flow()
    test_runtime_boundary_falsifications_and_uncertainty_latch()
    test_otel_genai_semantic_span_attributes()
    test_evidence_receipt_hash_chain_and_tamper_detection()
    test_human_override_ledger_warrant_validation()
    test_deception_interlock_nominal_and_tripwire_catches()
    test_leviathan_fts5_bounded_cards_and_invariant_retention()
    test_cross_tenant_governor_seven_isolation_properties()
    test_cve_2026_33017_aeib_ast_policy_gate_containment()
    test_cve_2026_33017_aeib_station1_taint_and_authorization_gate()
    test_vibe_coding_missing_auth_and_rls_detection()
    test_gitai_bisect_isolates_breaking_patch()
    test_iaps_agent_honeypot_detection_and_deterrence()
    test_screener_read_only_fast_path()
    test_screener_state_mutation_routing()
    test_daemon_subagent_handback_bounding()
    test_daemon_parent_memory_ceiling_and_packing()
    test_daemon_scoped_forgetting()
    test_local_daemon_banned_words()
    test_hlc_monotonicity_and_causal_ordering()
    test_causal_visibility_fence()
    test_hypergraph_emergent_collusion_sink_convergence()
    test_persist_memory_gate_memmorph_tool_redirect()
    test_hlc_gate_banned_words()
    test_hansard_choke_point_witnessing_and_dag_tip()
    test_hansard_attribution_laundering_detection()
    test_hansard_additive_harms_no_laundering()
    test_defection_probe_initialization_and_validation()
    test_defection_probe_benign_activation()
    test_defection_probe_defection_activation_halt()
    test_defection_probe_sigmoid_numerical_stability()
    test_hansard_defection_banned_words()
    test_sbox_and_field_properties()
    test_linear_layers()
    test_poseidon2_permutation_avalanche_and_non_commutativity()
    test_poseidon2_hash_bytes_and_canonical_json()
    test_poseidon2_merkle_tree_construction_and_padding()
    test_poseidon2_merkle_tree_all_leaves_proof_verification()
    test_poseidon2_proof_serialization_roundtrip()
    test_tampered_leaf_rejected()
    test_tampered_sibling_rejected()
    test_wrong_expected_root_rejected()
    test_invalid_leaf_index_raises()
    test_empty_leaves_raises()
    test_poseidon2_banned_words()
    test_nash_equilibrium_nominal_and_exploit_detection()
    test_nash_equilibrium_matrix_validation()
    test_tee_cvm_lifecycle_allocation_and_read()
    test_tee_cvm_hardware_key_shredding_and_memory_scrubbing()
    test_tee_cvm_remanence_detection_falsification()
    test_wasm_symbolic_path_explorer_clean_and_bounds_check()
    test_wasm_symbolic_path_explorer_violations()
    test_actuarial_multisig_risk_calculation_and_escalation()
    test_actuarial_multisig_signature_verification()
    test_tier3_banned_words()
    test_antigravity_decide_claim_verifier()
    test_five_surviving_principles_engine()
    test_epistemic_action_compiler_ab_evaluation()
    test_epistemic_macros_execution()
    test_non_dilutable_conflict_register_tamper_and_resolution()
    test_epistemic_ontic_wire_gate_blocking()
    test_epistemic_compiler_banned_words()
    test_canonical_jcs_float_rejection()
    test_nominal_6way_joint_witness_commit()
    test_proposal_to_commit_object_state_drift_rejection()
    test_caplease_semantic_replay_blocked()
    test_cim_narration_poisoning_silent_approval_bypass_rejected()
    test_post_qualification_authority_revocation_blocked()
    test_policy_or_epoch_drift_rejected()
    test_monotonic_subclass_tightening_treasury_harness()
    test_palantir_ontology_banned_words()
    test_end_to_end_p0_p1_gates()
    test_typestate_target_mismatch_and_invalid_signature()
    test_cryptographic_supervisor_conflict_resolution()
    test_eac_typestate_banned_words()
    test_1000_agent_phase_transition_simulation()
    test_missing_or_fabricated_bose_witness_rejected()
    test_provenance_entropy_synthetic_overload_rejected()
    test_intermediate_phase_transition_blocks_mutation()
    test_epistemic_core_bec_banned_words()
    test_o1_constant_time_codebase_snapshot_index_and_lookup()
    test_decide_v2_five_why_and_two_iteration_convergence()
    test_decide_v2_banned_words()
    test_submodular_monotonicity_and_100x_pairwise_coverage()
    test_missed_operator_enforces_current_only_constraint()
    test_cross_ecosystem_brainstorm_gls_diversity_and_pair_decision_schema()
    test_current_missed_next_categorical_contraction_and_ed25519_receipt()
    test_decide_v3_banned_words()
    test_cross_hemisphere_council_and_3tier_ask_router_hold_and_dominance()
    test_cross_hemisphere_council_developer_answer_unlocks_synthesis()
    test_typed_cross_critique_prevents_tone_sycophancy_arxiv_2609_08016()
    test_current_missed_next_calculus_maxsat_and_nondilutable_register()
    test_cross_hemisphere_council_banned_words()
    test_integrated_tri_partition_architecture()
    test_anti_disarmament_telemetry_protection()
    test_runtime_startup_hook_lockdown_litellm_vector()
    test_package_manager_step_up_gating()
    test_network_egress_intent_registration()
    test_epistemic_intent_outcome_two_phase_execution()
    test_defense_in_depth_banned_words()
    test_epistemic_5why_fts5_merkle_and_conflict_loop()
    test_epistemic_5why_banned_words()
    test_scitt_ap2_x402_otel_and_cbom_engine()
    test_scitt_ap2_x402_banned_words()
    test_stochastic_saga_chaosbench_500_episodes()
    test_chaosbench_banned_words()
    chaosbench_report = _sanitize_for_canonical_json(
        run_500_episode_chaosbench(episodes=500, seed=42)
    )
    locomo_report = _sanitize_for_canonical_json(evaluate_locomo_benchmark())
    maseval_report = _sanitize_for_canonical_json(run_maseval_comparative_benchmark())
    tla_report = explore_tla_state_space_and_verify_conformance()

    # 2. Generate deterministic, timestamp-free canonical JSON evidence artifacts
    summary_payload = {
        "baseline_version": "v1.0.0-rc.5-preprod",
        "epistemic_status": "locally_reproducible_development_baseline_ready_for_external_reproduction",
        "phase0_blockers_closed": [
            "0.1_canonical_json_caid",
            "0.2_at57b_pure_taint",
            "0.3_at58_escrow_wal",
            "0.4_g3_boot_reverify",
        ],
        "structural_cve_fixtures_verified": [
            "CVE-2026-33017_langflow_build_public_tmp",
            "CVE-2025-53773_vscode_autoapprove_yolo",
            "CVE-2026-77521_maxkb_tainted_shell",
            "CVE-2026-90970_gitlab_gateway_template_escape",
        ],
        "locomo_context_quality": locomo_report,
        "maseval_consequential_mutations": maseval_report,
        "stochastic_saga_chaosbench_500": chaosbench_report,
        "tla_conformance": tla_report,
        "regulatory_matrix": generate_regulatory_applicability_matrix(),
    }

    report_bytes = canonical_json_v1(summary_payload) + b"\n"
    report_path = output_dir / "rc5_canonical_evidence_report.json"
    report_path.write_bytes(report_bytes)

    # 3. Build deterministic tar.gz in memory twice to prove bit-identical reproducibility
    files_to_pack: List[Tuple[str, bytes]] = [
        ("rc5_canonical_evidence_report.json", report_bytes),
    ]
    for rel_file in sorted(
        [
            ".agents/skills/decide/SKILL.md",
            "decide.md",
            "benchmarks/locomo_context_quality.py",
            "benchmarks/maseval_integration.py",
            "benchmarks/stochastic_saga_chaos/run_chaosbench.py",
            "compliance/defense_in_depth.yaml",
            "compliance/defense_in_depth_policy_gate.py",
            "compliance/eac_typestate_conflict_engine.py",
            "docs/architecture/EPISTEMIC_ACTION_COMPILATION_AND_CONFLICT_REGISTER.md",
            "docs/benchmarks/maseval_results.md",
            "docs/compliance/china_agent_regulation_crosswalk.md",
            "docs/compliance/dora-crosswalk.md",
            "docs/compliance/en18286_and_cbom_spec.md",
            "docs/compliance/nist_si_guide_mapping.md",
            "docs/interop/distributed_db_contract.md",
            "docs/interop/rail-mandate-mapping.md",
            "docs/specs/admissibility_and_oo_harness_spec.md",
            "docs/specs/cose_sign1_receipt.md",
            "docs/specs/otel_genai_schema.md",
            "docs/specs/stochastic_acid_formal_proof.md",
            "formal/tlaplus/AEIBStation1And2.tla",
            "formal/tlaplus/TLC_OUTPUT.md",
            "papers/osdi_shared_nothing_agents/manuscript.md",
            "papers/vldb_stochastic_acid/manuscript.md",
            "scripts/verify_research_claims.py",
            "src/actuarial_multisig_gate.py",
            "src/context/__init__.py",
            "src/context/leviathan_context_engine.py",
            "src/deception/__init__.py",
            "src/deception/agent_deception_interlock.py",
            "src/decide_categorical_epistemic_engine.py",
            "src/defection_activation_probe.py",
            "src/epistemic_action_compiler.py",
            "src/epistemic_core.py",
            "src/governance/cross_tenant_sovereign_governor.py",
            "src/hansard_causal_provenance.py",
            "src/hlc_hybrid_logical_clock.py",
            "src/hypergraph_causal_audit.py",
            "src/nash_equilibrium_gate.py",
            "src/observability/__init__.py",
            "src/observability/otel_genai_evidence_chain.py",
            "src/persist_memory_gate.py",
            "src/poseidon2_merkle_tree.py",
            "src/runtime_boundary/__init__.py",
            "src/runtime_boundary/runtime_execution_boundary.py",
            "src/tee_cvm_memory_scrubbing.py",
            "src/wasm_symbolic_path_explorer.py",
            "tests/test_agent_deception_interlock.py",
            "tests/test_cross_hemisphere_council_decide.py",
            "tests/test_cve_2026_33017_langflow_rce.py",
            "tests/test_defense_in_depth_and_intent_outcome.py",
            "tests/test_decide_categorical_epistemic_engine.py",
            "tests/test_decide_v2_constant_time_snapshot.py",
            "tests/test_eac_typestate_conflict_engine.py",
            "tests/test_epistemic_action_compiler.py",
            "tests/test_epistemic_core_bec.py",
            "tests/test_hansard_and_defection_probe.py",
            "tests/test_hlc_hypergraph_and_persist_gate.py",
            "tests/test_leviathan_and_cross_tenant_isolation.py",
            "tests/test_local_system1_leviathan_daemon.py",
            "tests/test_opencode_codemode_hotreload.py",
            "tests/test_otel_genai_evidence_chain.py",
            "tests/test_palantir_ontology_joint_witness_engine.py",
            "tests/test_poseidon2_merkle_tree.py",
            "tests/test_scitt_ap2_mcp_pqc_interop.py",
            "tests/test_tcc_parallel_acid_vs_base.py",
            "tests/test_tier3_post_perfection_matrix.py",
            "tests/test_tool_provenance_and_otel.py",
            "tests/test_runtime_boundary_and_state_machine.py",
            "tests/test_structural_cve_boundary_fixtures.py",
            "tests/test_vibe_coding_and_honeypot.py",
            "tests/test_vibe_coding_and_long_horizon_guard.py",
            "tools/aeib_surviving_principles_engine.py",
            "tools/context_ram_and_maseval_harness.py",
            "tools/cross_hemisphere_council_decide.py",
            "tools/cross_hemisphere_epistemic_council.py",
            "tools/current_missed_next_calculus.py",
            "tools/decide_v2_constant_time_snapshot.py",
            "tools/epistemic_5why_loop.py",
            "tools/epistemic_action_compiler_ab_test.py",
            "tools/epistemic_intent_outcome_engine.py",
            "tools/local_system1_leviathan_daemon.py",
            "tools/palantir_ontology_joint_witness_engine.py",
            "tools/phase0_integrity_reset_core.py",
            "tools/regulatory_three_tier_and_matrix.py",
            "tools/scitt_ap2_x402_otel_engine.py",
            "tools/smf_frontier_oct2026_upgrades.py",
            "tools/tlaplus_model_conformance_checker.py",
            "tools/vibe_coding_and_long_horizon_guard.py",
        ]
    ):
        p = Path(rel_file)
        if p.exists():
            files_to_pack.append((rel_file, p.read_bytes()))

    manifest_lines: List[str] = []
    for arcname, content in files_to_pack:
        h = hashlib.sha256(content).hexdigest()
        manifest_lines.append(f"{h}  {arcname}")
    manifest_bytes = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    files_to_pack.append(("SHA256SUMS.txt", manifest_bytes))

    def _create_deterministic_tar_gz() -> bytes:
        raw_buf = io.BytesIO()
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_buf, mtime=FIXED_EPOCH
        ) as gz:
            with tarfile.open(mode="w", fileobj=gz) as tar:
                for arcname, data in sorted(files_to_pack, key=lambda x: x[0]):
                    info = tarfile.TarInfo(name=arcname)
                    info.size = len(data)
                    info.mtime = FIXED_EPOCH
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(data))
        return raw_buf.getvalue()

    archive_bytes_1 = _create_deterministic_tar_gz()
    archive_bytes_2 = _create_deterministic_tar_gz()
    assert archive_bytes_1 == archive_bytes_2, "Archive generation is not bit-identical!"

    archive_path = output_dir / "aeib_v1.0.0_rc5_preprod_reproducible_bundle.tar.gz"
    archive_path.write_bytes(archive_bytes_1)
    archive_sha256 = hashlib.sha256(archive_bytes_1).hexdigest()

    # 4. Clean-room extraction & SHA256SUMS verification
    with tempfile.TemporaryDirectory() as clean_dir:
        with tarfile.open(archive_path, mode="r:gz") as tar:
            tar.extractall(path=clean_dir, filter="data")
        extracted_manifest = (
            (Path(clean_dir) / "SHA256SUMS.txt").read_text("utf-8").splitlines()
        )
        for line in extracted_manifest:
            if not line.strip():
                continue
            expected_hash, rel_name = line.split("  ", 1)
            actual_hash = hashlib.sha256(
                (Path(clean_dir) / rel_name).read_bytes()
            ).hexdigest()
            assert actual_hash == expected_hash, f"Hash mismatch on {rel_name}"

    return {
        "archive_path": str(archive_path),
        "archive_sha256": archive_sha256,
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "files_verified_in_cleanroom": len(files_to_pack),
    }


def test_deterministic_rc5_archive_builder() -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        res = build_and_verify_deterministic_archive(Path(out_dir))
        assert len(res["archive_sha256"]) == 64
        assert res["files_verified_in_cleanroom"] >= 2


if __name__ == "__main__":
    receipt = build_and_verify_deterministic_archive(Path("output/rc5_reproducible"))
    print(json.dumps(receipt, indent=2))
