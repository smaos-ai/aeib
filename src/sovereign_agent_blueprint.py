#!/usr/bin/env python3
# File: src/sovereign_agent_blueprint.py
"""
Sovereign Agent Blueprint Compiler (`SovereignNexus` / `AEIB` v5.0 Artifact).

Evaluated prototype under the stated model unifying the epistemic and ontic planes
into a single compiled, cryptographically signed deployment bundle:
1. Epistemic Proof Layer (`/decide` v5.0):
   - Cross-Hemisphere Council synthesis (US + China + Local open-weight models)
   - RuleTrek statutory/domain dependency graph (`arXiv:2610.19698`)
   - SAKE dual-anchored JCS knowledge tuples (`arXiv:2602.09517`)
   - Non-Dilutable Conflict Register & Retraction Ledger clearance (`arXiv:2610.12360`)
   - Builder-Breaker (`arXiv:2610.14224`) adversarial audit clearance
2. Ontic Sovereign Execution Package (`GoSovem` + `OmniGraph` + `Beads` + `AEIB`):
   - Scoped Ontology subgraph & pinned MCP tool schema CAIDs (`AT63b`)
   - Beads (`steveyegge/beads`) Dolt-versioned graph work-frontier nodes
   - Station 1 & 2 6-Way Joint Commit Witness + TCC Escrow + Visibility-Lag Fence
   - Credential Starvation phantom placeholder bindings & Ring-0 eBPF LSM profile
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_jcs_bytes(obj: Any) -> bytes:
    def _validate(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_BLUEPRINT")
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _validate(v)
        elif isinstance(val, list):
            for item in val:
                _validate(item)

    _validate(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class BeadsWorkFrontierNode:
    issue_id: str
    branch_name: str
    depends_on_ids: Tuple[str, ...]
    status: str  # "READY" | "BLOCKED" | "COMPLETED"


@dataclass(frozen=True)
class EpistemicProofSection:
    decide_version: str
    council_models_consulted: Tuple[str, ...]
    ruletrek_dependency_ids: Tuple[str, ...]
    sake_anchored_fact_hashes: Tuple[str, ...]
    unresolved_conflict_count: int
    retraction_collisions_found: int
    evaluated_pass_hat_8_bps: int
    builder_breaker_disposition: str = "APPROVED_FOR_EXPERIENCE_MD"


@dataclass(frozen=True)
class OnticExecutionManifest:
    blueprint_id: str
    deployment_mode: str                  # "SOVEREIGN_AIR_GAPPED" | "HYBRID_CVM_APPLIANCE"
    ontology_allowed_entities: Tuple[str, ...]
    ontology_allowed_actions: Tuple[str, ...]
    pinned_mcp_tool_schema_caids: Dict[str, str]
    model_routing: Dict[str, str]
    station1_invariants: Dict[str, Any]
    station2_finality: Dict[str, Any]
    ring0_ebpf_containment: Dict[str, Any]
    beads_work_frontier: Tuple[BeadsWorkFrontierNode, ...] = ()


@dataclass(frozen=True)
class CompiledSovereignBlueprint:
    epistemic_proof: EpistemicProofSection
    ontic_manifest: OnticExecutionManifest
    blueprint_caid: str
    architect_signature_b64: str


class SovereignBlueprintCompiler:
    """
    Compiles a verified `/decide` v5.0 architectural decision into a deployable
    Sovereign Agent Blueprint (`agent_blueprint.v1.json`).
    Fails closed if any conflict in the Non-Dilutable Conflict Register is unresolved,
    if any retracted claim is present, or if the Builder-Breaker audit did not pass.
    """

    @staticmethod
    def compile_blueprint(
        epistemic_proof: EpistemicProofSection,
        ontic_manifest: OnticExecutionManifest,
        architect_privkey: Ed25519PrivateKey,
    ) -> CompiledSovereignBlueprint:
        if epistemic_proof.unresolved_conflict_count > 0:
            raise ValueError("HALT_BLUEPRINT_COMPILATION_UNRESOLVED_CONFLICTS_PRESENT")
        if epistemic_proof.retraction_collisions_found > 0:
            raise ValueError("HALT_BLUEPRINT_COMPILATION_RETRACTED_CLAIM_DETECTED")
        if epistemic_proof.evaluated_pass_hat_8_bps < 9000:
            raise ValueError("HALT_BLUEPRINT_COMPILATION_PASS_HAT_8_BELOW_SLO")
        if epistemic_proof.builder_breaker_disposition != "APPROVED_FOR_EXPERIENCE_MD":
            raise ValueError("HALT_BLUEPRINT_COMPILATION_REJECTED_BY_BREAKER")

        core_dict = {
            "epistemic_proof": asdict(epistemic_proof),
            "ontic_manifest": asdict(ontic_manifest),
        }
        raw_bytes = canonical_jcs_bytes(core_dict)
        bp_caid = sha256_prefixed(raw_bytes)
        sig_b64 = base64.b64encode(architect_privkey.sign(raw_bytes)).decode("ascii")

        return CompiledSovereignBlueprint(
            epistemic_proof=epistemic_proof,
            ontic_manifest=ontic_manifest,
            blueprint_caid=bp_caid,
            architect_signature_b64=sig_b64,
        )

    @staticmethod
    def verify_blueprint_before_boot(
        blueprint: CompiledSovereignBlueprint,
        architect_pubkey: Ed25519PublicKey,
    ) -> Tuple[bool, str]:
        if blueprint.epistemic_proof.unresolved_conflict_count != 0:
            return False, "ERR_UNRESOLVED_CONFLICTS"

        core_dict = {
            "epistemic_proof": asdict(blueprint.epistemic_proof),
            "ontic_manifest": asdict(blueprint.ontic_manifest),
        }
        raw_bytes = canonical_jcs_bytes(core_dict)
        if sha256_prefixed(raw_bytes) != blueprint.blueprint_caid:
            return False, "ERR_BLUEPRINT_CAID_MISMATCH"

        try:
            architect_pubkey.verify(
                base64.b64decode(blueprint.architect_signature_b64, validate=True),
                raw_bytes,
            )
        except Exception:
            return False, "ERR_INVALID_ARCHITECT_SIGNATURE"

        return True, "BLUEPRINT_VERIFIED_READY_FOR_STATION1_MOUNT"

    @staticmethod
    def query_ready_beads_nodes(
        blueprint: CompiledSovereignBlueprint,
    ) -> List[BeadsWorkFrontierNode]:
        """
        Mirrors `bd ready` from `steveyegge/beads`: returns work-frontier nodes
        whose upstream dependencies are all marked `COMPLETED`.
        """
        completed_ids = {
            n.issue_id
            for n in blueprint.ontic_manifest.beads_work_frontier
            if n.status == "COMPLETED"
        }
        ready: List[BeadsWorkFrontierNode] = []
        for node in blueprint.ontic_manifest.beads_work_frontier:
            if node.status != "COMPLETED" and all(
                dep in completed_ids for dep in node.depends_on_ids
            ):
                ready.append(node)
        return ready


def run_self_test() -> None:
    arch_priv = Ed25519PrivateKey.generate()

    epistemic = EpistemicProofSection(
        decide_version="v5.0",
        council_models_consulted=(
            "deepseek-v4-pro",
            "qwen-3-max",
            "gemini-4-argon",
            "flint-40b-local",
        ),
        ruletrek_dependency_ids=(
            "R1_TENANT_ISOLATION",
            "R2_TCC_ESCROW",
            "R3_VISIBILITY_FENCE",
        ),
        sake_anchored_fact_hashes=(
            "sha256:sake-genesis-anchor-01",
            "sha256:sake-terminal-anchor-02",
        ),
        unresolved_conflict_count=0,
        retraction_collisions_found=0,
        evaluated_pass_hat_8_bps=9230,
        builder_breaker_disposition="APPROVED_FOR_EXPERIENCE_MD",
    )

    ontic = OnticExecutionManifest(
        blueprint_id="bp-cross-border-treasury-v1",
        deployment_mode="SOVEREIGN_AIR_GAPPED",
        ontology_allowed_entities=("CustomerOrder", "TreasuryAccount"),
        ontology_allowed_actions=("IssueRefund", "VerifySettlement"),
        pinned_mcp_tool_schema_caids={
            "mcp.payments::issue_refund": "sha256:8f9d2c11e4b0",
        },
        model_routing={
            "system1_fast_filter": "local-classifier-33ms",
            "epistemic_ask_detector": "qwen-3-max",
            "ontic_action_proposer": "deepseek-v4-pro",
        },
        station1_invariants={
            "sprint_limit_minor": 2500_00,
            "epoch_limit_minor": 10000_00,
            "require_6way_joint_witness": True,
            "require_sves_rls_binding": True,
            "block_tier2_unpinned_payee": True,
        },
        station2_finality={
            "storage_backend": "SERIALIZABLE_MULTI_AZ_QUORUM",
            "visibility_lag_fence_sec": 5,
            "rail_protocols": ["AP2_V02", "ACP_V1", "X402_V2"],
        },
        ring0_ebpf_containment={
            "tetragon_policy": "aeib-agent-egress-lock",
            "allow_direct_agent_egress": False,
            "protect_control_plane_paths": [
                ".vscode/settings.json",
                ".cursor/mcp.json",
                ".mcp.json",
            ],
        },
        beads_work_frontier=(
            BeadsWorkFrontierNode(
                issue_id="bd-01",
                branch_name="feat/schema-lock",
                depends_on_ids=(),
                status="COMPLETED",
            ),
            BeadsWorkFrontierNode(
                issue_id="bd-02",
                branch_name="feat/tcc-escrow",
                depends_on_ids=("bd-01",),
                status="READY",
            ),
        ),
    )

    compiled = SovereignBlueprintCompiler.compile_blueprint(
        epistemic_proof=epistemic,
        ontic_manifest=ontic,
        architect_privkey=arch_priv,
    )
    ok, code = SovereignBlueprintCompiler.verify_blueprint_before_boot(
        compiled, arch_priv.public_key()
    )
    assert ok and code == "BLUEPRINT_VERIFIED_READY_FOR_STATION1_MOUNT"
    ready_nodes = SovereignBlueprintCompiler.query_ready_beads_nodes(compiled)
    assert len(ready_nodes) == 1 and ready_nodes[0].issue_id == "bd-02"


if __name__ == "__main__":
    run_self_test()
    print("SOVEREIGN AGENT BLUEPRINT COMPILER VERIFIED.")
