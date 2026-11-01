#!/usr/bin/env python3
"""
Verification and Falsification Suite for `src/cognitive_step_router.py`.
Evaluated against real on-disk repository modules (`SovereignCognitiveStepRouter.from_disk_repo`)
with zero hardcoded token floors or synthetic repo strings.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from src.cognitive_step_router import (
    DEFAULT_MINIMUM_MUTATION_SCORE_BPS,
    ArchitecturalSpecContract,
    SovereignCognitiveStepRouter,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

REAL_DISK_MODULES: Tuple[str, ...] = (
    "src/jcs_canonicalizer.py",
    "src/temporal_authority_guard.py",
    "src/crypto_delegation_graph.py",
    "src/mcp_action_firewall.py",
    "src/specification_invariant_compiler.py",
    "src/adversarial_mutation_verifier.py",
    "src/evidence_sufficiency_and_lean_gate.py",
    "src/scitt_proof_aggregation_reconciler.py",
    "src/sovereign_token_decree.py",
    "src/hypergraph_blast_radius.py",
)


def _disk_router(**kwargs: Any) -> SovereignCognitiveStepRouter:
    return SovereignCognitiveStepRouter.from_disk_repo(
        repo_root=REPO_ROOT,
        relative_paths=REAL_DISK_MODULES,
        **kwargs,
    )


def test_1_high_risk_auth_task_on_real_disk_uses_opus_only_for_step2() -> None:
    router = _disk_router()
    assert router.mutation_verifier.minimum_score_bps == DEFAULT_MINIMUM_MUTATION_SCORE_BPS

    def coder_gen(
        contract: ArchitecturalSpecContract, attempt: int, feedback: Optional[str]
    ) -> str:
        return (
            "def verify_ttl(exp: int, now: int) -> bool:\n"
            "    if exp > now:\n"
            "        return True\n"
            "    return False\n"
        )

    def strong_oracle(ns: Dict[str, Any]) -> None:
        fn = ns["verify_ttl"]
        assert fn(101, 100) is True
        assert fn(100, 100) is False
        assert fn(99, 100) is False

    result = router.execute_5_step_development_flow(
        task_id="task_auth_ttl",
        target_file="src/temporal_authority_guard.py",
        required_function_name="verify_ttl",
        allowed_imports=(),
        max_lines_changed=20,
        coder_generator_fn=coder_gen,
        test_oracle_fn=strong_oracle,
        check_oracle_non_vacuity=True,
    )

    expected_in_bytes = len(
        (REPO_ROOT / "src/temporal_authority_guard.py").read_bytes()
    )
    assert result.final_status == "COMMITTED"
    assert result.opus_invocations == 1
    assert result.fast_coder_invocations == 1
    assert result.zero_cost_kernel_steps == 3
    assert result.mutation_score_bps == 10000
    assert result.total_cost_nano_usd == 14_978_700
    assert result.monolithic_opus_baseline_nano_usd == 5_841_825_000
    assert result.cost_savings_bps == 9974
    assert result.trajectory_caid.startswith("sha256:")

    assert [r.step_number for r in result.step_records] == [1, 2, 3, 4, 5]
    assert result.step_records[0].input_bytes == expected_in_bytes
    assert result.step_records[0].output_bytes == 2397
    assert result.step_records[0].verdict_code == "SCOPED_BLAST_3000_BPS"
    assert result.step_records[1].input_bytes == 2397
    assert result.step_records[1].output_bytes == 314
    assert result.step_records[1].input_tokens == 600
    assert result.step_records[1].output_tokens == 79
    assert result.step_records[1].step_cost_nano_usd == 14_925_000
    assert result.step_records[2].input_bytes == 314
    assert result.step_records[2].output_bytes == 99
    assert result.step_records[2].input_tokens == 79
    assert result.step_records[2].output_tokens == 25
    assert result.step_records[2].step_cost_nano_usd == 53_700
    assert result.step_records[3].output_bytes == 0

    for rec in result.step_records:
        d = rec.to_dict()
        assert d["step_number"] == rec.step_number
        if rec.step_number in (1, 4, 5):
            assert rec.actor_tier == "TIER_0_DETERMINISTIC_KERNEL"
            assert rec.input_tokens == 0
            assert rec.output_tokens == 0
            assert rec.step_cost_nano_usd == 0

    # Verify dynamic sensitivity: smaller repo slice produces a smaller baseline cost (never hardcoded!)
    small_router = SovereignCognitiveStepRouter.from_disk_repo(
        repo_root=REPO_ROOT,
        relative_paths=("src/jcs_canonicalizer.py", "src/temporal_authority_guard.py"),
    )
    small_res = small_router.execute_5_step_development_flow(
        task_id="task_auth_small",
        target_file="src/temporal_authority_guard.py",
        required_function_name="verify_ttl",
        allowed_imports=(),
        max_lines_changed=20,
        coder_generator_fn=coder_gen,
        test_oracle_fn=strong_oracle,
    )
    assert small_res.monolithic_opus_baseline_nano_usd < result.monolithic_opus_baseline_nano_usd


def test_2_low_risk_leaf_task_on_real_disk_uses_zero_opus_calls() -> None:
    router = _disk_router()

    def coder_gen(
        contract: ArchitecturalSpecContract, attempt: int, feedback: Optional[str]
    ) -> str:
        return (
            "def clamp_width(w: int, limit: int) -> bool:\n"
            "    if w <= limit:\n"
            "        return True\n"
            "    return False\n"
        )

    def leaf_oracle(ns: Dict[str, Any]) -> None:
        fn = ns["clamp_width"]
        assert fn(49, 50) is True
        assert fn(50, 50) is True
        assert fn(51, 50) is False

    result = router.execute_5_step_development_flow(
        task_id="task_leaf",
        target_file="src/hypergraph_blast_radius.py",
        required_function_name="clamp_width",
        allowed_imports=(),
        max_lines_changed=20,
        coder_generator_fn=coder_gen,
        test_oracle_fn=leaf_oracle,
    )

    assert result.final_status == "COMMITTED"
    assert result.opus_invocations == 0
    assert result.total_cost_nano_usd == 170_700
    assert result.monolithic_opus_baseline_nano_usd == 6_088_200_000
    assert result.cost_savings_bps == 9999
    assert result.step_records[1].actor_tier == "TIER_1_FAST_PLANNER"

    # Also verify DeepSeek-R1 architect configuration on high-risk path
    ds_router = _disk_router(high_tier_architect="TIER_3_DEEPSEEK_R1_ARCHITECT")
    res_ds = ds_router.execute_5_step_development_flow(
        task_id="task_ds_arch",
        target_file="src/hypergraph_blast_radius.py",
        required_function_name="clamp_width",
        allowed_imports=(),
        max_lines_changed=20,
        coder_generator_fn=coder_gen,
        test_oracle_fn=leaf_oracle,
        force_opus_architect=True,
    )
    assert res_ds.final_status == "COMMITTED"
    assert res_ds.step_records[1].actor_tier == "TIER_3_DEEPSEEK_R1_ARCHITECT"
    assert res_ds.step_records[1].step_cost_nano_usd == 432_600
    assert res_ds.opus_invocations == 0
    with pytest.raises(Exception):
        res_ds.opus_invocations = 99  # type: ignore[misc]
    with pytest.raises(Exception):
        res_ds.step_records[0].step_number = 99  # type: ignore[misc]


def test_3_fast_coder_violating_opus_contract_is_blocked_at_step_4_for_zero_tokens() -> None:
    router = _disk_router()

    def rogue_coder(
        contract: ArchitecturalSpecContract, attempt: int, feedback: Optional[str]
    ) -> str:
        return (
            "import urllib.request\n"
            "def verify_ttl(exp: int, now: int) -> bool:\n"
            "    return exp > now\n"
        )

    result = router.execute_5_step_development_flow(
        task_id="task_rogue_import",
        target_file="src/temporal_authority_guard.py",
        required_function_name="verify_ttl",
        allowed_imports=(),
        max_lines_changed=20,
        coder_generator_fn=rogue_coder,
        test_oracle_fn=lambda ns: None,
    )

    assert result.final_status == "HALT_CONTRACT_VIOLATION"
    assert result.mutation_score_bps == 0
    assert result.step_records[-1].step_number == 4
    assert "HALT_CONTRACT_UNAPPROVED_IMPORT:urllib" in result.step_records[-1].verdict_code

    contract = ArchitecturalSpecContract(
        task_id="t1",
        architect_tier="TIER_3_OPUS_ARCHITECT",
        allowed_files=("src/temporal_authority_guard.py",),
        allowed_imports=("math",),
        required_function_name="verify_ttl",
        max_lines_changed=3,
        invariant_summary="strict",
        contract_caid="sha256:00",
    )
    ok_f, r_f = router.verify_code_obeys_architect_contract(
        contract, "src/other.py", "def verify_ttl(): return True\n"
    )
    assert ok_f is False and "HALT_CONTRACT_FILE_VIOLATION" in r_f

    ok_l, r_l = router.verify_code_obeys_architect_contract(
        contract,
        "src/temporal_authority_guard.py",
        "def verify_ttl():\n    a = 1\n    b = 2\n    return a + b\n",
    )
    assert ok_l is False and "HALT_CONTRACT_LINE_BUDGET_EXCEEDED" in r_l

    ok_a, r_a = router.verify_code_obeys_architect_contract(
        contract,
        "src/temporal_authority_guard.py",
        "import time\ndef verify_ttl():\n    time.sleep(10)\n",
    )
    assert ok_a is False and "HALT_DEFERRED_SLEEP_BLOCKED" in r_a

    ok_fi, r_fi = router.verify_code_obeys_architect_contract(
        contract,
        "src/temporal_authority_guard.py",
        "from socket import socket\ndef verify_ttl(): return True\n",
    )
    assert ok_fi is False and "HALT_CONTRACT_UNAPPROVED_IMPORT:socket" in r_fi

    ok_fn, r_fn = router.verify_code_obeys_architect_contract(
        contract,
        "src/temporal_authority_guard.py",
        "import math\ndef wrong_name(): return True\n",
    )
    assert ok_fn is False and "HALT_CONTRACT_MISSING_REQUIRED_FUNCTION:verify_ttl" in r_fn


def test_4_monotonic_contract_refinement_and_speculative_branches_and_repair_loop() -> None:
    router = _disk_router(max_repair_attempts=1)

    contract = ArchitecturalSpecContract(
        task_id="t_mutiny",
        architect_tier="TIER_3_OPUS_ARCHITECT",
        allowed_files=("src/hypergraph_blast_radius.py",),
        allowed_imports=(),
        required_function_name="clamp_width",
        max_lines_changed=10,
        invariant_summary="strict",
        contract_caid="sha256:11",
        secondary_stdlib_allowlist=("math",),
    )
    ok_np, msg_np, am_np = router.reconcile_contract_import_request(contract, "numpy")
    assert ok_np is False
    assert msg_np == "HALT_MUTINY_FORBIDDEN_CAPABILITY_ESCALATION:numpy"
    assert am_np is None
    with pytest.raises(Exception):
        contract.max_lines_changed = 99  # type: ignore[misc]

    ok_dec, msg_dec, am_dec = router.reconcile_contract_import_request(contract, "decimal")
    assert ok_dec is False
    assert msg_dec == "HALT_MUTINY_NOT_IN_ARCHITECT_ENVELOPE:decimal"
    assert am_dec is None

    def speculative_coder(
        c: ArchitecturalSpecContract, branch_idx: int, feedback: Optional[str]
    ) -> str:
        if branch_idx == 1:
            return "def clamp_width(w: int, limit: int) -> bool:\n    return False\n"
        return (
            "import math\n"
            "def clamp_width(w: int, limit: int) -> bool:\n"
            "    if w <= limit:\n"
            "        return True\n"
            "    return False\n"
        )

    def leaf_oracle(ns: Dict[str, Any]) -> None:
        fn = ns["clamp_width"]
        assert fn(49, 50) is True
        assert fn(50, 50) is True
        assert fn(51, 50) is False

    res_spec = router.execute_5_step_development_flow(
        task_id="task_speculative_math",
        target_file="src/hypergraph_blast_radius.py",
        required_function_name="clamp_width",
        allowed_imports=(),
        secondary_stdlib_allowlist=("math",),
        max_lines_changed=10,
        coder_generator_fn=speculative_coder,
        test_oracle_fn=leaf_oracle,
        speculative_branches=2,
    )
    assert res_spec.final_status == "COMMITTED"
    assert res_spec.fast_coder_invocations == 2
    assert res_spec.mutation_score_bps == 10000

    def always_weak_coder(
        c: ArchitecturalSpecContract, attempt: int, feedback: Optional[str]
    ) -> str:
        return (
            "def clamp_width(w: int, limit: int) -> bool:\n"
            "    if w <= limit and limit > 0:\n"
            "        return True\n"
            "    return False\n"
        )

    res_lockout = router.execute_5_step_development_flow(
        task_id="task_lockout",
        target_file="src/hypergraph_blast_radius.py",
        required_function_name="clamp_width",
        allowed_imports=(),
        max_lines_changed=10,
        coder_generator_fn=always_weak_coder,
        test_oracle_fn=leaf_oracle,
    )
    assert res_lockout.final_status == "HALT_ANSI_86_LOCKOUT"
    assert res_lockout.fast_coder_invocations == 2
    assert res_lockout.step_records[3].step_number == 4
    assert res_lockout.step_records[3].input_bytes == 0
    assert res_lockout.step_records[3].output_bytes == 0
    assert res_lockout.step_records[4].input_bytes > res_lockout.step_records[2].input_bytes

    r_zero_rep = _disk_router(max_repair_attempts=0)
    assert r_zero_rep.max_repair_attempts == 0


def test_5_step1_anti_poisoning_meta_oracle_and_validation_guards() -> None:
    router = _disk_router()

    def vacuous_oracle(ns: Dict[str, Any]) -> None:
        assert ns["verify_ttl"](100, 100) is not None

    res_vacuous = router.execute_5_step_development_flow(
        task_id="task_vacuous_test",
        target_file="src/temporal_authority_guard.py",
        required_function_name="verify_ttl",
        allowed_imports=(),
        max_lines_changed=20,
        coder_generator_fn=lambda c, a, f: "def verify_ttl(exp, now): return True\n",
        test_oracle_fn=vacuous_oracle,
        check_oracle_non_vacuity=True,
    )
    assert res_vacuous.final_status == "HALT_VACUOUS_TEST_ORACLE"
    assert res_vacuous.opus_invocations == 0
    assert res_vacuous.fast_coder_invocations == 0
    assert res_vacuous.total_cost_nano_usd == 0
    assert res_vacuous.mutation_score_bps == 0
    assert len(res_vacuous.step_records) == 1
    assert res_vacuous.step_records[0].step_number == 1
    assert "HALT_VACUOUS_TEST_ORACLE_AT_STEP_1" in res_vacuous.step_records[0].verdict_code

    ok_one, msg_one = router.audit_test_oracle_non_vacuity(
        "verify_ttl",
        lambda ns: None
        if ns["verify_ttl"](1, 1) == 1
        else (_ for _ in ()).throw(AssertionError()),
    )
    assert ok_one is True and msg_one == "OK_ORACLE_DISCRIMINATING"

    assert router.estimate_tokens("") == 0
    assert router.estimate_tokens("a") == 1
    assert router.estimate_tokens("abcd") == 1
    assert router.estimate_tokens("abcde") == 2
    assert router.compute_step_cost_nano_usd("TIER_0_DETERMINISTIC_KERNEL", 1000, 1000) == 0
    assert router.compute_step_cost_nano_usd("TIER_1_FAST_PLANNER", 1000, 1000) == 750_000
    assert router.compute_step_cost_nano_usd("TIER_2_FAST_CODER", 1000, 1000) == 1_500_000
    assert router.compute_step_cost_nano_usd("TIER_3_DEEPSEEK_R1_ARCHITECT", 1000, 1000) == 2_740_000
    assert router.compute_step_cost_nano_usd("TIER_3_OPUS_ARCHITECT", 1000, 1000) == 90_000_000

    import inspect
    from src.cognitive_step_router import DEFAULT_MINIMUM_MUTATION_SCORE_BPS

    # Verify exact 9000 bps configuration threshold (kills CONST_PERTURB line 53)
    assert DEFAULT_MINIMUM_MUTATION_SCORE_BPS == 9 * 1000
    assert (
        inspect.signature(SovereignCognitiveStepRouter.__init__)
        .parameters["minimum_mutation_score_bps"]
        .default
        == 9 * 1000
    )
    assert _disk_router().mutation_verifier.minimum_score_bps == 9 * 1000

    with pytest.raises(ValueError, match="ERR_EMPTY_REPO_SOURCES"):
        SovereignCognitiveStepRouter(repo_sources={})
    with pytest.raises(ValueError, match="ERR_INVALID_BLAST_RADIUS_THRESHOLD"):
        _disk_router(blast_radius_opus_threshold_bps=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_BLAST_RADIUS_THRESHOLD"):
        _disk_router(blast_radius_opus_threshold_bps=10001)
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_REPAIR_ATTEMPTS"):
        _disk_router(max_repair_attempts=-1)
    with pytest.raises(ValueError, match="ERR_UNKNOWN_ARCHITECT_TIER"):
        _disk_router(high_tier_architect="UNKNOWN")
    with pytest.raises(ValueError, match="ERR_INVALID_SPECULATIVE_BRANCHES"):
        router.execute_5_step_development_flow(
            task_id="bad_spec",
            target_file="src/hypergraph_blast_radius.py",
            required_function_name="clamp_width",
            allowed_imports=(),
            max_lines_changed=10,
            coder_generator_fn=lambda c, a, f: "",
            test_oracle_fn=lambda ns: None,
            speculative_branches=0,
        )
