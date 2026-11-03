#!/usr/bin/env python3
"""
SovereignNexus Compact State Baton Exporter (tools/export_state_baton.py).

Evaluated under the stated model to emit a compact (<300 token) RFC 8785 canonical
state handoff capsule (state/STATE_BATON.json) for cross-session continuity without
context-window bloat.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


def build_state_baton(
    directive: str,
    repo_root: Path = _REPO_ROOT,
) -> Dict[str, Any]:
    """Build compact deterministic state baton with git HEAD and verified modules."""
    head_res = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    head_sha = head_res.stdout.strip() if head_res.returncode == 0 else "unknown"

    branch_res = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    branch_name = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"

    core_modules: List[str] = [
        "src/temporal_authority_guard.py",
        "src/crypto_delegation_graph.py",
        "src/temporal_graph_router.py",
        "src/sovereign_token_decree.py",
        "src/token_decree_dispatch_interlock.py",
        "src/autonomous_pr_webhook_dispatcher.py",
        "src/hypergraph_blast_radius.py",
        "src/substrate_cube_interlock.py",
        "src/a2a_trajectory_interlock.py",
        "tools/pre_push_integrity_gate.py",
        "src/adversarial_mutation_verifier.py",
        "src/evidence_sufficiency_and_lean_gate.py",
        "src/figma_mcp_connector.py",
        "src/headless_browser_sidecar.py",
        "src/kiro_1000pr_and_cube_wal_simulator.py",
        "src/kagent_crd_adapter.py",
        "src/cognitive_step_router.py",
        "src/specification_invariant_compiler.py",
        "src/mcp_action_firewall.py",
        "src/anti_hardcode_spec_gate.py",
        "src/cognitive_friction_gate.py",
        "src/live_killchain_attestor.py",
        "src/temporal_model_bound_token.py",
        "src/accuracy_cascade_router.py",
        "src/anti_gravity_context_cart.py",
        "src/anti_scaffold_falsifier.py",
        "src/apoptosis_sentinel.py",
        "src/bpf_lsm_profile_compiler.py",
        "src/jcs_canonicalizer.py",
        "src/visual_regression_gate.py",
        "src/seatbelt_sandbox.py",
        "src/package_install_gate.py",
        "src/slop_filter.py",
        "src/scaffold_detector.py",
        "src/truth_compass.py",
        "src/eo1_effect_key.py",
        "src/border_policy.py",
        "src/commit_time_state_guard.py",
        "src/constraint_compiler.py",
        "src/perception_fast_path_router.py",
        "src/biometric_hitl_gate.py",
        "src/semantic_scion_compiler.py",
        "src/multi_tenant_governor.py",
        "src/autonomous_night_cycle_runner.py",
        "src/package_provenance_egress_guard.py",
        "src/sqlite_probe_adapter.py",
        "src/research_mcp_adapter.py",
        "src/bbs_plus_redactable.py",
        "src/behavioral_assurance_gate.py",
        "src/counterfeit_execution_tracker.py",
        "src/deterministic_graph_executor.py",
        "src/dir_antiscaffold_and_x402_escrow_engine.py",
        "src/dynamic_tool_registry.py",
        "src/epistemic_bisector.py",
        "src/epistemic_handoff.py",
        "src/epistemic_intent_compiler.py",
        "src/external_policy_gate.py",
        "src/jidoka_ui_pipeline.py",
        "src/kernel_apoptosis_gate.py",
        "src/mcp_schema_pinning.py",
        "src/process_trace_guard.py",
        "src/rssi_harness_evolver.py",
        "src/sovereign_moat_upgrades.py",
        "src/stateful_hitl.py",
        "src/subexponential_concurrency_gate.py",
        "src/unitboost_merge_operator.py",
        "src/inverse_lifecycle_referee.py",
        "src/lajolla_covering_verifier.py",
        "src/protected_path_egress_policy.py",
        "src/proof_carrying_handoff.py",
        "src/evidence_registry_client.py",
        "src/pre_tool_use_chain.py",
        "src/variant_evidence_pipeline.py",
        "src/distributed_agentgateway_reconciler.py",
        "src/harness_router.py",
        "src/human_translation_compiler.py",
        "src/deepseek_idempotency_reconciler.py",
        "src/hypersu_fts.py",
        "src/kagent_helm_generator.py",
        "src/lexus_nvh_and_thermal_governor.py",
        "src/incident_replay_digital_twin.py",
        "src/industrial_dev_flow_engine.py",
        "src/tpm_pcr_attestation.py",
        "src/sema_auto_swarm_simulator.py",
        "src/pap_adapter.py",
        "src/reality/merkle_sync.py",
        "src/reality/git_oracle.py",
        "src/reality/pointer_bus.py",
        "src/reality/passport_compiler.py",
        "src/reality/memory_poisoning_guard.py",
        "src/reality/hunger_credit_ledger.py",
    ]
    present_modules = [m for m in core_modules if (repo_root / m).is_file()]

    baton_core: Dict[str, Any] = {
        "active_branch": branch_name,
        "directive": directive,
        "head_commit": head_sha,
        "status_label": "INTERNAL_PREVIEW_COMMISSIONED",
        "verified_module_count": len(present_modules),
        "verified_modules": present_modules,
    }
    canonical_bytes = encode_jcs(baton_core)
    baton_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
    baton_full = dict(baton_core)
    baton_full["baton_caid"] = baton_caid
    baton_full["serialized_byte_length"] = len(encode_jcs(baton_full))
    return baton_full


def main() -> None:
    parser = argparse.ArgumentParser(description="Export compact RFC 8785 STATE_BATON.json")
    parser.add_argument(
        "--directive",
        type=str,
        default="Temporal Authority, Delegation DAG & Token Decree verified",
        help="Summary directive for the state baton.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="state/STATE_BATON.json",
        help="Output path relative to repo root.",
    )
    args = parser.parse_args()

    baton = build_state_baton(directive=args.directive, repo_root=_REPO_ROOT)
    out_path = _REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_bytes = encode_jcs(baton)
    out_path.write_bytes(out_bytes + b"\n")
    print(
        f"[state-baton] path={args.out} bytes={len(out_bytes)} caid={baton['baton_caid']}"
    )


if __name__ == "__main__":
    main()
