"""
Verification & Falsification Suite for Toyota Jidoka + Volvo Safety
Divide-and-Conquer Binary Checkpoint Pair-Monitor (`src/toyota_volvo_dac_checkpoint_monitor.py`).
"""

from __future__ import annotations

from pathlib import Path
import math
from typing import List, Tuple

import pytest

from src.eo1_write_before_execute import PreDispatchIntentInterlock
from src.hypersu_store import HyperSUStore
from src.toyota_volvo_dac_checkpoint_monitor import (
    AlgorithmicHorizonExperimentHarness,
    BinaryCheckpointBisector,
    DataStructureComplexityTaxonomy,
    DivideAndConquerContractTree,
    GovernedJidokaAssemblyLine,
    HorizonCandidateProposal,
    JidokaStationPairMonitor,
    LexusYetContradictionStandardizer,
    MultiPerspectiveCriticAndBuyVsBuildAdvisor,
    ProblemToEvidenceProtocolV1,
    SafeRefundGatewayWorkflow,
    SpecGuardContractAuditor,
    StationContract,
    _compile_candidate_callable,
    compute_ast_cleanliness_metrics,
    run_five_policy_jidoka_benchmark,
    run_jidoka_dac_vs_posthoc_benchmark,
)


def _pair_sum_contract() -> StationContract:
    """Station contract: find whether any two distinct elements in `nums` sum to `target`."""

    def _build_scaling_input(n: int) -> Tuple[list[int], int]:
        return (list(range(n)), -1)

    return StationContract(
        station_id="station-pair-sum",
        function_name="has_pair_sum",
        expected_arg_count=2,
        max_cyclomatic_complexity=6,
        max_nesting_depth=2,
        max_scaling_exponent=1.35,
        held_out_cases=(
            (([2, 7, 11, 15], 9), True),
            (([3, 2, 4], 6), True),
            (([1, 5, 9], 20), False),
            (([4, 4], 8), True),
            (([4], 8), False),
        ),
        scaling_input_builder=_build_scaling_input,
    )


def test_divide_and_conquer_tree_balanced_decomposition() -> None:
    """Verifies that K stations decompose into a balanced binary tree of depth ceil(log2 K) + 1."""
    stations = [
        StationContract(
            station_id=f"s-{i}",
            function_name=f"fn_{i}",
            expected_arg_count=1,
            max_cyclomatic_complexity=5,
            max_nesting_depth=2,
            max_scaling_exponent=1.25,
            held_out_cases=(((1,), 2),),
        )
        for i in range(16)
    ]
    root = DivideAndConquerContractTree.build(stations)
    depth = DivideAndConquerContractTree.tree_depth(root)
    assert not root.is_leaf
    assert len(root.subtree_station_ids) == len(stations)
    assert depth == int(math.log2(len(stations))) + 1


def test_jidoka_station_andon_halts_on_spaghetti_and_quadratic_then_releases_clean_refactor() -> None:
    """
    Tests the Toyota Jidoka + Volvo Active Safety station workflow:
      - Attempt 1: Deeply nested spaghetti code -> halted by `ANDON_HALT_NEEDS_IN_STATION_REFACTOR`.
      - Attempt 2: Flat Nesting but O(N^2) double-loop -> halted by `ANDON_HALT_QUADRATIC_COMPLEXITY`.
      - Attempt 3: Refactored O(N) hash-set implementation -> passes all 4 gates on first release
        with 100% mutant kill rate (`STATION_CLEAN_FIRST_WRITE_RELEASED`).
    """
    contract = _pair_sum_contract()
    monitor = JidokaStationPairMonitor()

    # Attempt 1: Deeply nested (>2 levels) messy implementation
    spaghetti_src = """
def has_pair_sum(nums, target):
    for i in range(len(nums)):
        if i >= 0:
            for j in range(len(nums)):
                if i != j:
                    if nums[i] + nums[j] == target:
                        return True
    return False
"""

    # Attempt 2: Nesting reduced via generator comprehension (depth == 2), still O(N^2) quadratic work
    quadratic_src = """
def has_pair_sum(nums, target):
    n = len(nums)
    for i in range(n):
        if any(nums[i] + nums[j] == target for j in range(i + 1, n)):
            return True
    return False
"""

    # Attempt 3: Clean O(N) single-pass hash-set implementation
    clean_linear_src = """
def has_pair_sum(nums, target):
    seen = set()
    for x in nums:
        if target - x in seen:
            return True
        seen.add(x)
    return False
"""

    final_receipt, history = monitor.execute_station_with_andon_refactor_loop(
        contract, [spaghetti_src, quadratic_src, clean_linear_src]
    )

    assert len(history) == 3
    assert not history[0].passed
    assert history[0].andon_status == "ANDON_HALT_NEEDS_IN_STATION_REFACTOR"
    assert history[0].max_nesting_depth > contract.max_nesting_depth

    assert not history[1].passed
    assert history[1].andon_status == "ANDON_HALT_QUADRATIC_COMPLEXITY"
    assert history[1].empirical_scaling_exponent > contract.max_scaling_exponent

    assert final_receipt.passed
    assert final_receipt.andon_status == "STATION_CLEAN_FIRST_WRITE_RELEASED"
    assert final_receipt.empirical_scaling_exponent <= contract.max_scaling_exponent
    assert final_receipt.held_out_cases_passed == final_receipt.held_out_cases_total
    assert final_receipt.mutants_killed == final_receipt.mutants_total
    assert final_receipt.mutants_total > 0


def test_falsification_stub_and_weak_oracle_rejected() -> None:
    """
    Falsification vectors:
      1. Stub implementation (`pass` / wrong signature) is halted at Gate 1.
      2. Weak oracle where a mutated operator (`+` -> `-`) still satisfies trivial
         zero-input test cases (`0 + 0 == 0`) is halted at Gate 4b (`ANDON_HALT_WEAK_ORACLE_SURVIVING_MUTANT`).
    """
    monitor = JidokaStationPairMonitor()
    contract = _pair_sum_contract()

    stub_receipt = monitor.inspect_station_write(
        contract,
        "def has_pair_sum(nums, target):\n    pass\n",
    )
    assert not stub_receipt.passed
    assert stub_receipt.andon_status == "ANDON_HALT_SIGNATURE_OR_STUB_DEFECT"

    ellipsis_receipt = monitor.inspect_station_write(
        contract,
        "def has_pair_sum(nums, target):\n    ...\n",
    )
    assert not ellipsis_receipt.passed
    assert ellipsis_receipt.andon_status == "ANDON_HALT_SIGNATURE_OR_STUB_DEFECT"
    assert compute_ast_cleanliness_metrics("def f(x):\n    42\n", "f")[4] is False

    syntax_receipt = monitor.inspect_station_write(contract, "def broken(:\n")
    assert not syntax_receipt.passed
    assert syntax_receipt.mutants_killed == 0

    forbidden_receipt = monitor.inspect_station_write(
        contract,
        "def has_pair_sum(nums, target):\n    return eval('False')\n",
    )
    assert not forbidden_receipt.passed
    assert forbidden_receipt.mutants_killed == 0

    rounded_rcpt = monitor._build_receipt(contract, True, "OK", 1, 1, 1.123456, 5, 1, 1, 1)
    assert rounded_rcpt.empirical_scaling_exponent == 1.1235

    with pytest.raises(ValueError):
        _compile_candidate_callable("x = 1\n", "missing_fn")

    # Weak oracle contract that only tests (0, 0) -> 0, allowing `a + b` vs `a - b` mutant to survive
    weak_contract = StationContract(
        station_id="station-weak-oracle",
        function_name="combine_offset",
        expected_arg_count=2,
        max_cyclomatic_complexity=4,
        max_nesting_depth=2,
        max_scaling_exponent=1.25,
        held_out_cases=(((0, 0), 0),),
    )
    weak_receipt = monitor.inspect_station_write(
        weak_contract,
        "def combine_offset(a, b):\n    return a + b\n",
    )
    assert not weak_receipt.passed
    assert weak_receipt.andon_status == "ANDON_HALT_WEAK_ORACLE_SURVIVING_MUTANT"
    assert weak_receipt.mutants_killed < weak_receipt.mutants_total


def test_binary_checkpoint_bisector_logarithmic_fault_isolation() -> None:
    """
    Verifies that BinaryCheckpointBisector isolates the exact first failing station
    across K = 64 stages in <= ceil(log2 64) + 1 = 7 probes instead of linear scanning.
    """
    total_stages = 64
    for injected_fault in (0, 1, 19, 31, 48, 63):
        receipt = BinaryCheckpointBisector.bisect_first_faulty_station(
            total_stations=total_stages,
            checkpoint_ok=lambda idx, f=injected_fault: idx < f,
        )
        assert receipt.faulty_station_index == injected_fault
        assert receipt.probes_executed <= int(math.ceil(math.log2(total_stages))) + 1

    healthy_receipt = BinaryCheckpointBisector.bisect_first_faulty_station(
        total_stations=total_stages,
        checkpoint_ok=lambda _idx: True,
    )
    assert healthy_receipt.faulty_station_index is None
    assert healthy_receipt.probes_executed == 1


def test_jidoka_dac_vs_posthoc_benchmark_scaling() -> None:
    """Verifies the empirical benchmark across K in {8, 16, 32, 64}."""
    rows = run_jidoka_dac_vs_posthoc_benchmark((8, 16, 32, 64))
    assert len(rows) == 4
    for row in rows:
        assert row.jidoka_wasted_downstream_stations == 0
        assert row.posthoc_wasted_downstream_stations > 0
        assert row.linear_isolation_probes == row.fault_injected_at_station + 1
        assert row.binary_bisection_probes < row.linear_isolation_probes
        assert row.binary_bisection_probes <= int(math.ceil(math.log2(row.num_stations))) + 1


def test_specguard_contract_auditor_rejects_contradictory_and_vacuous_contracts() -> None:
    """
    Tests `SpecGuardContractAuditor` (arXiv:2610.09159v1 & arXiv:2610.10604v1):
      - Contradictory contract where the same input `(2, 3)` maps to `5` and `6`
        is rejected with `SPEC_CONFLICT_CONTRADICTORY_EXAMPLES`.
      - Vacuous contract with only 1 input point is rejected with
        `SPEC_VACUOUS_INSUFFICIENT_COVERAGE`.
    """
    contradictory = StationContract(
        station_id="st-conflict",
        function_name="add_vals",
        expected_arg_count=2,
        max_cyclomatic_complexity=4,
        max_nesting_depth=2,
        max_scaling_exponent=1.25,
        held_out_cases=(((2, 3), 5), ((2, 3), 6)),
    )
    res_conflict = SpecGuardContractAuditor.audit_contract(contradictory)
    assert not res_conflict.valid
    assert res_conflict.status_code == "SPEC_CONFLICT_CONTRADICTORY_EXAMPLES"

    vacuous = StationContract(
        station_id="st-vacuous",
        function_name="add_vals",
        expected_arg_count=2,
        max_cyclomatic_complexity=4,
        max_nesting_depth=2,
        max_scaling_exponent=1.25,
        held_out_cases=(((2, 3), 5),),
    )
    res_vacuous = SpecGuardContractAuditor.audit_contract(vacuous)
    assert not res_vacuous.valid
    assert res_vacuous.status_code == "SPEC_VACUOUS_INSUFFICIENT_COVERAGE"


def test_multi_perspective_critic_buy_vs_build_and_constant_time_o1_advisory() -> None:
    """
    Tests `MultiPerspectiveCriticAndBuyVsBuildAdvisor`:
      - Flags reinvented BM25/FTS logic with `BUY_OR_REUSE_EXISTING_SOLUTION`.
      - Flags `x in [1, 2, 3]` inside a loop with `UPGRADE_TO_O1_CONSTANT_TIME_LOOKUP`.
      - Remains strictly `ADVISORY_ONLY_VERIFIER_IS_AUTHORITATIVE`.
    """
    fts_contract = StationContract(
        station_id="station-custom-bm25",
        function_name="custom_bm25_search",
        expected_arg_count=1,
        max_cyclomatic_complexity=5,
        max_nesting_depth=2,
        max_scaling_exponent=1.25,
        held_out_cases=(([1, 2], 1), ([3, 4], 0)),
    )
    linear_in_loop_src = """
def custom_bm25_search(items):
    hits = 0
    for x in items:
        if x in [1, 2, 5, 9]:
            hits += 1
    return hits
"""
    report = MultiPerspectiveCriticAndBuyVsBuildAdvisor.critique_station(
        fts_contract, linear_in_loop_src
    )
    assert report.authority_role == "ADVISORY_ONLY_VERIFIER_IS_AUTHORITATIVE"
    assert report.buy_vs_build_verdict == "BUY_OR_REUSE_EXISTING_SOLUTION"
    assert report.recommended_existing_component is not None
    assert "FTS5" in report.recommended_existing_component
    assert report.constant_time_o1_verdict == "UPGRADE_TO_O1_CONSTANT_TIME_LOOKUP"


def test_governed_jidoka_assembly_line_eo1_commit_hypersu_trace_and_bounded_human_escalation(
    tmp_path: Path,
) -> None:
    """
    Tests `GovernedJidokaAssemblyLine` integrating real `PreDispatchIntentInterlock`
    and real `HyperSUStore`:
      - Attempt 1 fails Andon (nested spaghetti) -> trace written to disk & ingested into
        `HyperSUStore` with verified SHA-256 provenance.
      - Attempt 2 passes all 4 gates -> committed via `EO1` (`COMMITTED`).
      - Always-failing candidate exhausts `max_rework_attempts` -> escalates to
        `HUMAN_ESCALATION_REQUIRED` without committing to `EO1`.
    """
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "jidoka_eo1.jsonl",
        output_state_dir=tmp_path / "jidoka_latches",
    )
    store = HyperSUStore(tmp_path / "jidoka_memory.sqlite")
    line = GovernedJidokaAssemblyLine(
        workspace_root=tmp_path,
        interlock=interlock,
        memory_store=store,
        max_rework_attempts=2,
    )
    contract = _pair_sum_contract()

    def _adaptive_builder(_c: StationContract, attempt: int, _feedback: List[str]) -> str:
        if attempt == 1:
            return (
                "def has_pair_sum(nums, target):\n"
                "    for i in range(len(nums)):\n"
                "        if i >= 0:\n"
                "            for j in range(len(nums)):\n"
                "                if i != j:\n"
                "                    if nums[i] + nums[j] == target:\n"
                "                        return True\n"
                "    return False\n"
            )
        return (
            "def has_pair_sum(nums, target):\n"
            "    seen = set()\n"
            "    for x in nums:\n"
            "        if target - x in seen:\n"
            "            return True\n"
            "        seen.add(x)\n"
            "    return False\n"
        )

    outcome = line.run_station(contract, _adaptive_builder)
    assert outcome.committed is True
    assert outcome.lifecycle_state == "COMMITTED"
    assert not outcome.human_escalation_required
    assert outcome.attempts_used == 2
    assert outcome.eo1_caid is not None
    assert interlock.is_caid_committed(outcome.eo1_caid)
    assert len(outcome.hypersu_failure_fact_ids) == 1
    prov = store.verify_fact_provenance(outcome.hypersu_failure_fact_ids[0], tmp_path)
    assert prov.valid is True

    # Bounded rework exhaustion -> HUMAN_ESCALATION_REQUIRED
    contract_fail = StationContract(
        station_id="station-unresolvable",
        function_name="has_pair_sum",
        expected_arg_count=2,
        max_cyclomatic_complexity=6,
        max_nesting_depth=2,
        max_scaling_exponent=1.35,
        held_out_cases=contract.held_out_cases,
    )
    outcome_escalated = line.run_station(
        contract_fail,
        lambda _c, _a, _f: "def has_pair_sum(nums, target):\n    pass\n",
    )
    assert outcome_escalated.committed is False
    assert outcome_escalated.human_escalation_required is True
    assert outcome_escalated.lifecycle_state == "HUMAN_ESCALATION_REQUIRED"
    assert outcome_escalated.eo1_caid is None
    store.close()


def test_algorithmic_horizon_experiment_selects_o1_hash_over_on2_and_disqualifies_non_equivalent_cheat() -> None:
    """
    Tests `DataStructureComplexityTaxonomy` and `AlgorithmicHorizonExperimentHarness`:
      - Verifies 6 taxonomy tiers covering O(1), O(log N), O(N), O(N log N), SQLite FTS5, and HyperSU.
      - Runs an autonomous horizon tournament comparing 3 diverse learning-path candidates
        against an unoptimized O(N^2) reference implementation:
          1. Fast O(1) cheat that violates behavioral equivalence on held-out inputs -> disqualified
             by `AQUEDUCT_DIFFERENTIAL_EQUIVALENCE_MISMATCH`.
          2. Naive nested-scan candidate -> disqualified by `JIDOKA_GATE_REJECTED:ANDON_HALT_QUADRATIC_COMPLEXITY`.
          3. Systems O(1) hash-indexed (`set`) candidate -> passes equivalence and all 4 Jidoka gates,
             achieving >15x operation reduction at N=128 over the O(N^2) reference.
    """
    assert len(DataStructureComplexityTaxonomy.TIERS) == 6
    contract = _pair_sum_contract()

    reference_quadratic_src = (
        "def has_pair_sum(nums, target):\n"
        "    n = len(nums)\n"
        "    for i in range(n):\n"
        "        if any(nums[i] + nums[j] == target for j in range(i + 1, n)):\n"
        "            return True\n"
        "    return False\n"
    )

    proposals = (
        HorizonCandidateProposal(
            candidate_id="cand_fast_cheat",
            learning_path_background="PATH_SHORTCUT_HEURISTIC",
            claimed_taxonomy_tier="TIER_1_O1_HASH_OR_DIRECT_INDEX",
            source_code=(
                "def has_pair_sum(nums, target):\n"
                "    return len(nums) > 1 and (nums[0] + nums[1] == target)\n"
            ),
        ),
        HorizonCandidateProposal(
            candidate_id="cand_nested_quadratic",
            learning_path_background="PATH_BRUTE_FORCE_PAIRWISE",
            claimed_taxonomy_tier="TIER_3_ON_SINGLE_PASS_STREAMING",
            source_code=reference_quadratic_src,
        ),
        HorizonCandidateProposal(
            candidate_id="cand_n2_divergent_cheat",
            learning_path_background="PATH_SCALE_CONDITIONAL_CHEAT",
            claimed_taxonomy_tier="TIER_1_O1_HASH_OR_DIRECT_INDEX",
            source_code=(
                "def has_pair_sum(nums, target):\n"
                "    if len(nums) == 128:\n"
                "        return True\n"
                "    seen = set()\n"
                "    for x in nums:\n"
                "        if target - x in seen:\n"
                "            return True\n"
                "        seen.add(x)\n"
                "    return False\n"
            ),
        ),
        HorizonCandidateProposal(
            candidate_id="cand_systems_o1_hash",
            learning_path_background="PATH_SYSTEMS_CONSTANT_TIME_HASH",
            claimed_taxonomy_tier="TIER_1_O1_HASH_OR_DIRECT_INDEX",
            source_code=(
                "def has_pair_sum(nums, target):\n"
                "    seen = set()\n"
                "    for x in nums:\n"
                "        if target - x in seen:\n"
                "            return True\n"
                "        seen.add(x)\n"
                "    return False\n"
            ),
        ),
    )

    harness = AlgorithmicHorizonExperimentHarness()
    report = harness.evaluate_stage_candidates(
        contract=contract,
        reference_source=reference_quadratic_src,
        proposals=proposals,
        scales=(64, 128),
    )

    assert report.winning_candidate_id == "cand_systems_o1_hash"
    assert report.winning_learning_path == "PATH_SYSTEMS_CONSTANT_TIME_HASH"
    assert report.winning_ast_mechanism == "AST_MECHANISM_O1_HASH_INDEXED"
    assert report.winning_operations_at_n2 == 128
    assert report.reference_operations_at_n2 == 8256
    assert report.winning_operations_at_n2 < report.reference_operations_at_n2
    assert report.stage_work_speedup_factor > 15.0
    with pytest.raises(Exception):
        report.winning_candidate_id = "mutated"  # type: ignore[misc]

    by_id = {c.candidate_id: c for c in report.evaluated_candidates}
    assert by_id["cand_fast_cheat"].behaviorally_equivalent_to_reference is False
    assert (
        by_id["cand_fast_cheat"].disqualification_reason
        == "AQUEDUCT_DIFFERENTIAL_EQUIVALENCE_MISMATCH"
    )
    assert by_id["cand_nested_quadratic"].jidoka_passed is False
    assert (
        by_id["cand_nested_quadratic"].disqualification_reason
        == "JIDOKA_GATE_REJECTED:ANDON_HALT_QUADRATIC_COMPLEXITY"
    )
    assert by_id["cand_systems_o1_hash"].behaviorally_equivalent_to_reference is True
    assert by_id["cand_systems_o1_hash"].jidoka_passed is True


def test_five_policy_jidoka_benchmark_defect_escape_comparison() -> None:
    """
    Tests `run_five_policy_jidoka_benchmark` across the 5 policies:
      - `baseline_generate_then_review` escapes all injected defects and contaminates downstream units.
      - `critic_only` and `verifier_only` catch partial subsets but allow defects to escape.
      - `test_first_jidoka` and `full_jidoka` catch all 6 injected defects with 0 escaped defects
        and 0 downstream contaminated units.
    """
    rows = {r.policy_name: r for r in run_five_policy_jidoka_benchmark()}

    baseline = rows["baseline_generate_then_review"]
    critic_only = rows["critic_only"]
    verifier_only = rows["verifier_only"]
    full_jidoka = rows["full_jidoka"]

    assert baseline.escaped_defects == baseline.injected_defects
    assert baseline.downstream_contaminated_units > 0

    assert 0 < critic_only.caught_defects < critic_only.injected_defects
    assert critic_only.escaped_defects > 0

    assert 0 < verifier_only.caught_defects < verifier_only.injected_defects
    assert verifier_only.caught_defects == 3
    assert verifier_only.escaped_defects > 0

    assert full_jidoka.escaped_defects == 0
    assert full_jidoka.caught_defects == full_jidoka.injected_defects
    assert full_jidoka.downstream_contaminated_units == 0
    assert full_jidoka.human_escalations_triggered >= 2
    with pytest.raises(Exception):
        full_jidoka.escaped_defects = 99  # type: ignore[misc]


def test_problem_to_evidence_protocol_and_safe_refund_gateway_workflow(tmp_path: Path) -> None:
    """
    Tests `LexusYetContradictionStandardizer`, `ProblemToEvidenceProtocolV1`, and
    `SafeRefundGatewayWorkflow` (Commercial Wedge #1 + #2):
      - Verifies the 3 Lexus 'Yet' Pareto contradiction standards.
      - Executes the 11-step Safe Refund Workflow over real `PreDispatchIntentInterlock`
        and `HyperSUStore` under a simulated HTTP 504 timeout after downstream bank commit.
      - Confirms `EFFECT_INDETERMINATE` latch blocks blind retry, out-of-band reconciliation
        settles the state, post-reconciliation replay is refused, and actual refund side
        effects equal 1 (0 duplicates).
      - Validates the exported `PEP v1` bundle and falsifies a bundle with injected duplicate effects.
    """
    assert len(LexusYetContradictionStandardizer.AXES) == 3

    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "refund_eo1.jsonl",
        output_state_dir=tmp_path / "refund_latches",
    )
    store = HyperSUStore(tmp_path / "refund_memory.sqlite")
    workflow = SafeRefundGatewayWorkflow(
        workspace_root=tmp_path,
        interlock=interlock,
        memory_store=store,
    )

    receipt = workflow.execute_safe_refund_under_timeout(
        order_id="ORD-12345",
        amount_cents=25000,
        currency="EUR",
    )

    assert receipt.timeout_latched_indeterminate is True
    assert receipt.blind_retry_blocked is True
    assert receipt.reconciled_as_committed is True
    assert receipt.post_reconcile_replay_blocked is True
    assert receipt.actual_refund_side_effects == 1
    assert receipt.pep_bundle.eo1["duplicate_effects"] == 0
    assert receipt.pep_bundle.status == "VERIFIED_LOCAL_RESULT"

    valid, reasons = ProblemToEvidenceProtocolV1.validate_bundle(receipt.pep_bundle)
    assert valid is True
    assert reasons == ()

    # Validate default 0 fallback when 'ambiguous_outcomes' key is omitted from eo1 dict
    sparse_eo1_bundle = ProblemToEvidenceProtocolV1.build_bundle(
        task_id="pep-sparse-eo1",
        human_outcome="Test default 0 fallback on omitted ambiguous_outcomes",
        constraints=("0 duplicates",),
        evidence_sources=receipt.pep_bundle.evidence_sources,
        plan_digest=receipt.pep_bundle.plan_digest,
        experiments=receipt.pep_bundle.experiments,
        verification=receipt.pep_bundle.verification,
        eo1_metrics={"duplicate_effects": 0},
        deliverable_kind="research_witness",
        deliverable_digest=receipt.pep_bundle.deliverable["digest"],
        reproduction_command="pytest",
        status="VERIFIED_LOCAL_RESULT",
    )
    sparse_valid, sparse_reasons = ProblemToEvidenceProtocolV1.validate_bundle(sparse_eo1_bundle)
    assert sparse_valid is True
    assert sparse_reasons == ()

    # Falsification: a PEP bundle reporting a duplicate effect or failed verifier must be rejected
    bad_bundle = ProblemToEvidenceProtocolV1.build_bundle(
        task_id="pep-bad-01",
        human_outcome="Test invalid bundle rejection",
        constraints=("0 duplicates",),
        evidence_sources=receipt.pep_bundle.evidence_sources,
        plan_digest=receipt.pep_bundle.plan_digest,
        experiments=receipt.pep_bundle.experiments,
        verification={
            "compiler": "PASS",
            "domain_verifier": "FAIL",
            "property_tests": "PASS",
            "static_analysis": "PASS",
            "tests": "PASS",
        },
        eo1_metrics={
            "ambiguous_outcomes": 1,
            "consequential_actions": 2,
            "duplicate_effects": 1,
            "escalations": 0,
        },
        deliverable_kind="research_witness",
        deliverable_digest=receipt.pep_bundle.deliverable["digest"],
        reproduction_command="pytest",
        status="VERIFIED_LOCAL_RESULT",
    )
    bad_valid, bad_reasons = ProblemToEvidenceProtocolV1.validate_bundle(bad_bundle)
    assert bad_valid is False
    assert "PEP_DUPLICATE_EFFECT_DETECTED" in bad_reasons
    assert "PEP_VERIFICATION_GATE_NOT_PASSED:domain_verifier" in bad_reasons
    assert "PEP_UNRESOLVED_AMBIGUOUS_OUTCOME" in bad_reasons
    store.close()



