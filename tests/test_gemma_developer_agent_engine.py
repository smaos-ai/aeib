#!/usr/bin/env python3
"""
tests/test_gemma_developer_agent_engine.py — Comprehensive Pytest Suite for Gemma Developer Agent.

Validates all 5 architectural subsystems:
1. Context & Codebase Intake: SQLite BM25 CTE retrieval and degree-penalized graph expansion.
2. Toyota Jidoka Checkpointing & SpecGuard: Contract trees, AST quadratic loop detection, infinite loop halt.
3. Anti-Scaffold & Scope Bisector: Trivial stub interception, bounded repair (B <= 3), signed track bisection.
4. Station 1 Pre-Dispatch Intent Latch: POSIX flock + fsync, SHA-256 hash chaining, Ed25519 signatures, boot replay.
5. Mutation-Adequate Verification Gate: AST mutant injection, kill ratio evaluation, tautology rejection.
6. Kaggle Submission Generator: Self-contained script generation and AST parse verification.
7. Epistemic Purity: Strict zero-banned-words verification across all owned files.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.aeib_track1_and_calibrated_guards import canonical_json_v1
from src.dir_antiscaffold_and_x402_escrow_engine import ScaffoldFinding
from src.gemma_developer_agent_engine import (
    CodeSymbol,
    ContextIntakeResult,
    ContractTree,
    GemmaAntiScaffoldBisector,
    GemmaCodebaseIntake,
    GemmaDeveloperAgentPipeline,
    GemmaMutationAdequacyGate,
    GemmaStation1PreDispatchLatch,
    JidokaCheckResult,
    MutationCheckResult,
    PreDispatchRecord,
    RepairOutcome,
    ToyotaJidokaSpecGuard,
)
from src.hypersu_store import HyperSUStore


# ---------------------------------------------------------------------------
# Test Suite 1: Context & Codebase Intake
# ---------------------------------------------------------------------------


class TestGemmaCodebaseIntake:
    """Evaluates AST symbol extraction, SQLite FTS5 BM25 search, and degree penalization."""

    def test_index_and_retrieve_symbols(self, tmp_path: Path) -> None:
        store = HyperSUStore(":memory:")
        intake = GemmaCodebaseIntake(store=store, workspace_root=tmp_path)

        sample_source = '''
def calculate_metrics(items):
    """Calculates operational totals."""
    return sum(items)

async def dispatch_payload(client, payload):
    """Dispatches async payload."""
    calculate_metrics(payload)
    return True

class PipelineRunner:
    """Manages execution pipeline."""
    def run_step(self, step_data):
        """Runs single pipeline step."""
        calculate_metrics(step_data)
'''
        symbols = intake.index_source_code("pipeline.py", sample_source)
        assert len(symbols) >= 3

        func_names = {s.name for s in symbols}
        assert "calculate_metrics" in func_names
        assert "dispatch_payload" in func_names
        assert "PipelineRunner.run_step" in func_names

        # Query metrics calculation
        result = intake.retrieve_context(query="calculate metrics totals", limit=5)
        assert isinstance(result, ContextIntakeResult)
        assert len(result.symbols) >= 1
        top_symbol = result.symbols[0]
        assert "calculate_metrics" in top_symbol["label"]
        assert "hyperedges" in top_symbol
        assert result.retrieval_ms >= 0.0

        # Verify default constructor
        default_intake = GemmaCodebaseIntake()
        assert default_intake.store is not None

    def test_degree_penalization_attenuation(self, tmp_path: Path) -> None:
        store = HyperSUStore(":memory:")
        intake = GemmaCodebaseIntake(store=store, workspace_root=tmp_path)

        # Create hub function called by multiple callers
        hub_source = '''
def utility_logger(msg):
    """Logs message to console."""
    return len(msg)

def caller_one(data):
    """First caller."""
    utility_logger(data)

def caller_two(data):
    """Second caller."""
    utility_logger(data)

def specific_domain_solver(problem):
    """Solves domain specific optimization without calling logger."""
    return problem * 2
'''
        intake.index_source_code("hub_test.py", hub_source)
        res = intake.retrieve_context(query="logger solver", limit=10, expand_hops=1)
        assert len(res.symbols) >= 2

        # Verify degree tracking exists (inbound callers + outbound calls)
        degrees = intake._symbol_degrees
        expected_degree = len(["caller_one", "caller_two", "len"])
        assert degrees["utility_logger"] == expected_degree
        labels = {s["label"] for s in res.symbols}
        assert any("caller" in lbl for lbl in labels)

    def test_context_budget_capping(self, tmp_path: Path) -> None:
        store = HyperSUStore(":memory:")
        intake = GemmaCodebaseIntake(store=store, workspace_root=tmp_path)

        code_block = '''
def verbose_function_one():
    """Docstring one with detailed comments."""
    x = 100
    y = 200
    return x + y

def verbose_function_two():
    """Docstring two with detailed comments."""
    a = 300
    b = 400
    return a + b
'''
        intake.index_source_code("verbose.py", code_block)
        # Request with small character limit
        res = intake.retrieve_context(query="verbose", max_context_chars=180, limit=10)
        assert res.total_chars <= 400
        assert len(res.symbols) >= 1

    def test_intake_syntax_error_resilience(self, tmp_path: Path) -> None:
        store = HyperSUStore(":memory:")
        intake = GemmaCodebaseIntake(store=store, workspace_root=tmp_path)
        symbols = intake.index_source_code("broken.py", "def broken_syntax(:\n   pass")
        assert len(symbols) == 0


# ---------------------------------------------------------------------------
# Test Suite 2: Toyota Jidoka Checkpointing & SpecGuard
# ---------------------------------------------------------------------------


class TestToyotaJidokaSpecGuard:
    """Evaluates task contract decomposition and AST complexity / loop inspection."""

    def test_decompose_task_specification(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        prompt = """
        Task: Refactor payment settlement ledger.
        Requirements:
        Must ensure transaction balances remain strictly non-negative.
        Return computed audit digest upon completion.
        Given input list of journal entries.
        """
        tree = guard.decompose_task_specification(prompt)
        assert isinstance(tree, ContractTree)
        assert len(tree.nodes) >= 3

        kinds = {n.kind for n in tree.nodes}
        assert "requirement" in kinds
        assert "invariant" in kinds
        assert "postcondition" in kinds
        assert any(n.kind == "postcondition" and "Return computed" in n.description for n in tree.nodes)
        assert any(n.kind == "precondition" and "Given input" in n.description for n in tree.nodes)
        assert not any(n.kind == "postcondition" and "Given input" in n.description for n in tree.nodes)

        # Immutability check on ContractTree and ContractNode
        with pytest.raises((AttributeError, TypeError)):
            tree.root_task = "mutated"  # type: ignore[misc]
        with pytest.raises((AttributeError, TypeError)):
            tree.nodes[0].description = "mutated"  # type: ignore[misc]

    def test_detect_nested_for_loops_quadratic(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        quadratic_code = """
def bubble_sort(items):
    n = len(items)
    for i in range(n):
        for j in range(n - i - 1):
            if items[j] > items[j + 1]:
                items[j], items[j + 1] = items[j + 1], items[j]
    return items
"""
        eval_res = guard.evaluate_candidate_ast(quadratic_code)
        assert eval_res.andon_pulled is True
        assert eval_res.disposition == "ANDON_HALT_QUADRATIC_COMPLEXITY"
        assert eval_res.lineno > 0

    def test_detect_nested_while_loops(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        while_code = """
def nested_while(matrix):
    i = 0
    while i < len(matrix):
        j = 0
        while j < len(matrix[i]):
            matrix[i][j] *= 2
            j += 1
        i += 1
    return matrix
"""
        eval_res = guard.evaluate_candidate_ast(while_code)
        assert eval_res.andon_pulled is True
        assert eval_res.disposition == "ANDON_HALT_QUADRATIC_COMPLEXITY"

    def test_detect_cartesian_comprehensions(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        cartesian_list = """
def cross_join(list_a, list_b):
    return [(a, b) for a in list_a for b in list_b]
"""
        res_list = guard.evaluate_candidate_ast(cartesian_list)
        assert res_list.andon_pulled is True
        assert res_list.disposition == "ANDON_HALT_QUADRATIC_COMPLEXITY"

        cartesian_set = """
def cross_set(set_a, set_b):
    return {a + b for a in set_a for b in set_b}
"""
        res_set = guard.evaluate_candidate_ast(cartesian_set)
        assert res_set.andon_pulled is True
        assert res_set.disposition == "ANDON_HALT_QUADRATIC_COMPLEXITY"

    def test_detect_infinite_while_loops(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        infinite_code = """
def poll_network():
    while True:
        status = 1
"""
        eval_res = guard.evaluate_candidate_ast(infinite_code)
        assert eval_res.andon_pulled is True
        assert eval_res.disposition == "ANDON_HALT_INFINITE_LOOP"

    def test_while_loop_with_terminator_allowed(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        safe_break = """
def poll_with_break():
    while True:
        if ready():
            break
"""
        res_break = guard.evaluate_candidate_ast(safe_break)
        assert res_break.andon_pulled is False
        assert res_break.disposition == "JIDOKA_INSPECTION_PASSED"

        safe_return = """
def poll_with_return():
    while True:
        return 42
"""
        res_ret = guard.evaluate_candidate_ast(safe_return)
        assert res_ret.andon_pulled is False
        assert res_ret.disposition == "JIDOKA_INSPECTION_PASSED"

    def test_linear_code_inspection_passed(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        linear_code = """
def linear_scan(elements, target):
    for idx, val in enumerate(elements):
        if val == target:
            return idx
    return -1
"""
        res = guard.evaluate_candidate_ast(linear_code)
        assert res.andon_pulled is False
        assert res.disposition == "JIDOKA_INSPECTION_PASSED"
        assert res.lineno == 0
        with pytest.raises((AttributeError, TypeError)):
            res.andon_pulled = True  # type: ignore[misc]

    def test_syntax_error_handled(self) -> None:
        guard = ToyotaJidokaSpecGuard()
        res = guard.evaluate_candidate_ast("def unclosed_syntax(")
        assert res.andon_pulled is True
        assert res.disposition == "ANDON_HALT_SYNTAX_ERROR"


# ---------------------------------------------------------------------------
# Test Suite 3: Anti-Scaffold & Scope Bisector
# ---------------------------------------------------------------------------


class TestGemmaAntiScaffoldBisector:
    """Evaluates detection of trivial stubs, bounded repair loop, and signed bisection."""

    def test_detect_scaffold_variations(self) -> None:
        bisector = GemmaAntiScaffoldBisector()

        # Pass stub
        code_pass = "def verify_action(act):\n    pass\n"
        finds_pass = bisector.inspect_code(code_pass)
        assert any(f.anomaly_code == "SCAFFOLD_PASS_STUB" for f in finds_pass)

        # Ellipsis stub
        code_ellipsis = "def process_data(d):\n    ...\n"
        finds_ellip = bisector.inspect_code(code_ellipsis)
        assert any(f.anomaly_code == "SCAFFOLD_ELLIPSIS_STUB" for f in finds_ellip)

        # Constant return bypasses
        code_ret_true = "def is_valid(token):\n    return True\n"
        finds_true = bisector.inspect_code(code_ret_true)
        assert any(f.anomaly_code == "SCAFFOLD_CONSTANT_RETURN_BYPASS" for f in finds_true)

        code_ret_false = "def is_blocked(user):\n    return False\n"
        finds_false = bisector.inspect_code(code_ret_false)
        assert any(f.anomaly_code == "SCAFFOLD_CONSTANT_RETURN_BYPASS" for f in finds_false)

        code_ret_none = "def get_metadata(obj):\n    return None\n"
        finds_none = bisector.inspect_code(code_ret_none)
        assert any(f.anomaly_code == "SCAFFOLD_CONSTANT_RETURN_BYPASS" for f in finds_none)

        # NotImplementedError
        code_not_impl = "def execute_sync():\n    raise NotImplementedError()\n"
        finds_impl = bisector.inspect_code(code_not_impl)
        assert any(f.anomaly_code == "SCAFFOLD_NOT_IMPLEMENTED_STUB" for f in finds_impl)

        # Empty except handler
        code_except = """
def suppress_fault():
    try:
        critical_io()
    except Exception:
        pass
"""
        finds_exc = bisector.inspect_code(code_except)
        assert any(f.anomaly_code == "SCAFFOLD_EMPTY_EXCEPT_HANDLER" for f in finds_exc)

        # Working function with docstring should have zero scaffold findings
        code_with_doc = '''
def documented_working_func(x):
    """Calculates increment."""
    return x + 1
'''
        finds_doc = bisector.inspect_code(code_with_doc)
        assert len(finds_doc) == 0

    def test_bounded_repair_loop_success(self) -> None:
        bisector = GemmaAntiScaffoldBisector()
        initial_stub = "def add_positive(a, b):\n    return True\n"

        def simulated_repair(code: str, findings: List[ScaffoldFinding]) -> str:
            # Emulates model repairing code in second turn
            return """
def add_positive(a, b):
    if a < 0 or b < 0:
        raise ValueError("Must be positive")
    return a + b
"""

        outcome = bisector.repair_or_bisect(
            candidate_code=initial_stub,
            repair_callback=simulated_repair,
            max_repair_budget=2,
            subsystem_key="test_add_positive",
        )
        assert outcome.success is True
        assert outcome.iterations_used == 1
        assert outcome.final_code is not None
        assert "Must be positive" in outcome.final_code
        assert outcome.bisected_track is None

        # Verify default budget of 3 callback invocations
        calls: List[int] = []
        outcome_def = bisector.repair_or_bisect(
            "def unresolvable(): pass",
            repair_callback=lambda c, f: (calls.append(1) or c),
        )
        assert len(calls) == 3
        assert outcome_def.success is False

        # Verify zero budget
        outcome_zero = bisector.repair_or_bisect("def f(): pass", max_repair_budget=0)
        assert outcome_zero.iterations_used == 0

        # Verify repair succeeded on last iteration
        count = 0
        def fix_on_third(code: str, findings: List[ScaffoldFinding]) -> str:
            nonlocal count
            count += 1
            if count == 3:
                return "def f(x):\n    return x * 2\n"
            return code

        outcome_third = bisector.repair_or_bisect(
            "def f(): pass",
            repair_callback=fix_on_third,
            max_repair_budget=3,
        )
        assert outcome_third.success is True
        assert outcome_third.final_code is not None

    def test_bounded_repair_loop_exhaustion_escalates_to_bisection(self) -> None:
        bisector = GemmaAntiScaffoldBisector()
        broken_stub = "def never_fixed():\n    pass\n"

        def ineffective_repair(code: str, findings: List[ScaffoldFinding]) -> str:
            return "def never_fixed():\n    return False\n"

        outcome = bisector.repair_or_bisect(
            candidate_code=broken_stub,
            repair_callback=ineffective_repair,
            max_repair_budget=2,
            subsystem_key="stub_module",
        )
        assert outcome.success is False
        assert outcome.iterations_used == 2
        assert outcome.bisected_track is not None
        spec = outcome.bisected_track
        assert spec.subsystem_key == "stub_module"
        assert spec.routing_disposition == "ERR_CAPABILITY_UNAVAILABLE_ON_HOST"

        # Verify cryptographic signature of the bisection spec
        stmt = {
            "cold_host_fallback_error": spec.cold_host_fallback_error,
            "existing_verified_provider": spec.existing_verified_provider,
            "ffi_boundary_schema": dict(spec.ffi_boundary_schema),
            "required_host_capabilities": list(spec.required_host_capabilities),
            "routing_disposition": spec.routing_disposition,
            "subsystem_key": spec.subsystem_key,
            "track_id": spec.track_id,
        }
        stmt_bytes = canonical_json_v1(stmt)
        computed_digest = f"sha256:{hashlib.sha256(stmt_bytes).hexdigest()}"
        assert spec.spec_digest == computed_digest

        sig_bytes = base64.b64decode(spec.signature_b64.encode("ascii"))
        bisector.verify_key.verify(sig_bytes, stmt_bytes)

    def test_missing_host_capability_immediate_bisection(self) -> None:
        bisector = GemmaAntiScaffoldBisector()
        outcome = bisector.repair_or_bisect(
            candidate_code="def kernel_hook(): return 0",
            missing_capabilities=("linux_ebpf_lsm", "bpftool"),
            subsystem_key="ebpf_sensor",
        )
        assert outcome.success is False
        assert outcome.iterations_used == 0
        assert outcome.bisected_track is not None
        assert "linux_ebpf_lsm" in outcome.bisected_track.required_host_capabilities


# ---------------------------------------------------------------------------
# Test Suite 4: Station 1 Pre-Dispatch Intent Latch
# ---------------------------------------------------------------------------


class TestGemmaStation1PreDispatchLatch:
    """Evaluates write-before-execute ledger durability, flock, fsync, and boot replay."""

    def test_successful_action_records_intent_and_committed(self, tmp_path: Path) -> None:
        latch = GemmaStation1PreDispatchLatch(ledger_dir=tmp_path)
        payload = {"file": "core.py", "op": "write", "sha": "e3b0c442"}

        def do_write() -> Dict[str, Any]:
            return {"bytes": 42}

        ok, res, rec = latch.execute_with_latch(
            tool_id="fs.write_file",
            action_payload=payload,
            action_executor=do_write,
        )
        assert ok is True
        assert res == {"bytes": 42}
        assert isinstance(rec, PreDispatchRecord)
        assert rec.state == "COMMITTED"
        assert rec.prev_hash != rec.record_hash

        # Re-read ledger rows
        with open(tmp_path / "station1_intent_ledger.jsonl", "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        assert len(lines) == 2
        assert lines[0]["state"] == "INTENT_RESERVED"
        assert lines[1]["state"] == "COMMITTED"
        assert lines[1]["prev_hash"] == lines[0]["record_hash"]

        # Re-initialize latch to test boot replay verification
        reopened_latch = GemmaStation1PreDispatchLatch(
            ledger_dir=tmp_path, signing_key=latch._signing_key
        )
        assert reopened_latch._chain_tip == lines[1]["record_hash"]

    def test_failing_action_records_indeterminate(self, tmp_path: Path) -> None:
        latch = GemmaStation1PreDispatchLatch(ledger_dir=tmp_path)

        def will_raise() -> None:
            raise IOError("Disk full or syscall fault")

        ok, exc, rec = latch.execute_with_latch(
            tool_id="fs.write_file",
            action_payload={"target": "crash.py"},
            action_executor=will_raise,
        )
        assert ok is False
        assert isinstance(exc, IOError)
        assert rec.state == "EFFECT_INDETERMINATE"

    def test_ledger_tampering_breaks_boot_continuity(self, tmp_path: Path) -> None:
        latch = GemmaStation1PreDispatchLatch(ledger_dir=tmp_path)
        latch.execute_with_latch("fs.write", {"a": "1"}, lambda: 10)

        ledger_file = tmp_path / "station1_intent_ledger.jsonl"
        with open(ledger_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Tamper with second row prev_hash
        tampered_rec = json.loads(lines[1])
        tampered_rec["prev_hash"] = "sha256:corrupted_hash_000000000000000000000000000000000000000000000000"
        lines[1] = json.dumps(tampered_rec) + "\n"

        with open(ledger_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        with pytest.raises(RuntimeError, match="HALT_BOOT_CHAIN_LINKAGE_BROKEN"):
            GemmaStation1PreDispatchLatch(ledger_dir=tmp_path, signing_key=latch._signing_key)

    def test_ledger_record_hash_mismatch_detected(self, tmp_path: Path) -> None:
        latch = GemmaStation1PreDispatchLatch(ledger_dir=tmp_path)
        latch.execute_with_latch("fs.write", {"test_key": "val"}, lambda: 1)

        ledger_file = tmp_path / "station1_intent_ledger.jsonl"
        with open(ledger_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Tamper only with record_hash of the first row while keeping signature and prev_hash valid
        tampered = json.loads(lines[0])
        tampered["record_hash"] = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        lines[0] = json.dumps(tampered) + "\n"

        with open(ledger_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        with pytest.raises(RuntimeError, match="HALT_BOOT_RECORD_HASH_MISMATCH"):
            GemmaStation1PreDispatchLatch(ledger_dir=tmp_path, signing_key=latch._signing_key)


# ---------------------------------------------------------------------------
# Test Suite 5: Mutation-Adequate Verification Gate
# ---------------------------------------------------------------------------


class TestGemmaMutationAdequacyGate:
    """Evaluates that tests actively kill injected AST mutants."""

    def test_mutation_adequate_test_kills_mutants(self) -> None:
        gate = GemmaMutationAdequacyGate()

        candidate_code = """
def evaluate_score(a, b):
    if a > 10 and b < 20:
        return a + b
    return 0
"""
        # Test suite testing both sides of condition, boundaries, and return
        test_code = """
def test_evaluate_score():
    assert evaluate_score(15, 15) == 30
    assert evaluate_score(11, 15) == 26
    assert evaluate_score(15, 20) == 0
    assert evaluate_score(5, 15) == 0
    assert evaluate_score(15, 25) == 0
"""
        res = gate.evaluate_test_adequacy(
            candidate_code=candidate_code,
            test_code=test_code,
            min_kill_ratio=0.75,
            max_mutants=6,
        )
        assert isinstance(res, MutationCheckResult)
        assert res.adequate is True
        assert res.disposition == "MUTATION_ADEQUATE"
        assert res.mutants_killed > 0
        assert res.kill_ratio >= 0.75

    def test_tautological_test_suite_rejected(self) -> None:
        gate = GemmaMutationAdequacyGate()

        candidate_code = """
def compute_total(val):
    if val == 100:
        return val * 2
    return val
"""
        # Tautological test that always passes
        tautological_test = """
def test_tautology():
    assert True
"""
        res = gate.evaluate_test_adequacy(
            candidate_code=candidate_code,
            test_code=tautological_test,
            min_kill_ratio=0.80,
            max_mutants=4,
        )
        assert res.adequate is False
        assert res.disposition == "TAUTOLOGICAL_TESTS_OR_INADEQUATE_ORACLE"
        assert res.mutants_survived > 0

    def test_baseline_suite_failure_rejects(self) -> None:
        gate = GemmaMutationAdequacyGate()

        candidate_code = "def get_val(): return 10\n"
        failing_test = "def test_fail(): assert get_val() == 99\n"

        res = gate.evaluate_test_adequacy(
            candidate_code=candidate_code,
            test_code=failing_test,
        )
        assert res.adequate is False
        assert res.disposition == "BASELINE_SUITE_FAILED"

        # Verify immutability of MutationCheckResult
        with pytest.raises((AttributeError, TypeError)):
            res.adequate = True  # type: ignore[misc]

    def test_direct_mutant_generation_operators(self) -> None:
        gate = GemmaMutationAdequacyGate()

        # Constant boolean perturbation
        const_muts = gate._generate_mutants("flag = True\n", max_mutants=2)
        assert len(const_muts) >= 1
        assert "False" in const_muts[0]

        # Constant integer perturbation
        int_muts = gate._generate_mutants("count = 10\n", max_mutants=2)
        assert len(int_muts) >= 1
        assert "11" in int_muts[0]

        # Boolean operator swap
        bool_muts = gate._generate_mutants("res = a and b\n", max_mutants=2)
        assert len(bool_muts) >= 1
        assert "or" in bool_muts[0]

        # Comparison flip
        cmp_muts = gate._generate_mutants("check = (x == y)\n", max_mutants=2)
        assert len(cmp_muts) >= 1
        assert "!=" in cmp_muts[0]

        # Consecutive boolean operators
        consec_muts = gate._generate_mutants("res = (a and b) or (c and d)\n", max_mutants=4)
        assert len(consec_muts) == (1 + 2)
        assert "(a or b)" in consec_muts[1]


# ---------------------------------------------------------------------------
# Test Suite 6: Master Pipeline Integration
# ---------------------------------------------------------------------------


class TestGemmaDeveloperAgentPipeline:
    """Evaluates unified end-to-end pipeline coordination."""

    def test_pipeline_end_to_end_acceptance(self, tmp_path: Path) -> None:
        pipeline = GemmaDeveloperAgentPipeline(ledger_dir=tmp_path)

        task_desc = """
        Must ensure positive inputs.
        Return sum of inputs.
        """
        candidate_code = """
def calculate_sum(a, b):
    if a < 0 or b < 0:
        raise ValueError("Inputs must be non-negative")
    return a + b
"""
        test_code = """
def test_calculate_sum():
    assert calculate_sum(10, 20) == 30
    assert calculate_sum(0, 0) == 0
    try:
        calculate_sum(-1, 5)
        assert False
    except ValueError:
        pass
    try:
        calculate_sum(5, -1)
        assert False
    except ValueError:
        pass
"""
        out = pipeline.process_task(
            task_description=task_desc,
            candidate_code=candidate_code,
            test_code=test_code,
            target_file_path="math_ops.py",
        )
        assert out["accepted"] is True
        assert out["disposition"] == "PIPELINE_VERIFIED_AND_LATCHED"
        assert out["action_caid"].startswith("sha256:")
        assert out["record_hash"].startswith("sha256:")

    def test_pipeline_rejection_at_jidoka_complexity(self, tmp_path: Path) -> None:
        pipeline = GemmaDeveloperAgentPipeline(ledger_dir=tmp_path)

        task_desc = "Compute matrix multiplication"
        quadratic_candidate = """
def matmul(matrix):
    for r in matrix:
        for c in r:
            pass
"""
        out = pipeline.process_task(
            task_description=task_desc,
            candidate_code=quadratic_candidate,
            test_code="def test_m(): pass",
            target_file_path="matrix.py",
        )
        assert out["accepted"] is False
        assert out["rejection_stage"] == "TOYOTA_JIDOKA_COMPLEXITY_GUARD"
        assert out["disposition"] == "ANDON_HALT_QUADRATIC_COMPLEXITY"

    def test_pipeline_rejection_at_anti_scaffold(self, tmp_path: Path) -> None:
        pipeline = GemmaDeveloperAgentPipeline(ledger_dir=tmp_path)

        stub_code = "def stub_func(): return True\n"
        out = pipeline.process_task(
            task_description="Implement stub",
            candidate_code=stub_code,
            test_code="def test_stub(): pass",
            target_file_path="stub.py",
        )
        assert out["accepted"] is False
        assert out["rejection_stage"] == "ANTI_SCAFFOLD_SCOPE_BISECTOR"
        assert out["bisected_track"] is not None

    def test_pipeline_rejection_at_mutation_adequacy(self, tmp_path: Path) -> None:
        pipeline = GemmaDeveloperAgentPipeline(ledger_dir=tmp_path)

        out = pipeline.process_task(
            task_description="Compute multiplier",
            candidate_code="def calc(x):\n    return x * 2\n",
            test_code="def test_calc():\n    assert True\n",
            target_file_path="multiplier.py",
        )
        assert out["accepted"] is False
        assert out["rejection_stage"] == "MUTATION_ADEQUACY_GATE"
        assert out["disposition"] == "TAUTOLOGICAL_TESTS_OR_INADEQUATE_ORACLE"


# ---------------------------------------------------------------------------
# Test Suite 7: Kaggle Submission Script Generator
# ---------------------------------------------------------------------------


class TestKaggleSubmissionScriptGenerator:
    """Evaluates generation and syntax validity of standalone Kaggle submission script."""

    def test_submission_script_syntax_and_structure(self) -> None:
        pipeline = GemmaDeveloperAgentPipeline()
        script_text = pipeline.generate_kaggle_submission_script()

        assert len(script_text) > 1000
        # Validate AST parsing
        tree = ast.parse(script_text)
        assert isinstance(tree, ast.Module)

        # Validate compilation
        compiled = compile(script_text, "<kaggle_submission>", "exec")
        assert compiled is not None

        # Check required self-contained components exist in source
        assert "class KaggleJidokaComplexityGuard" in script_text
        assert "class KaggleAntiScaffoldBisector" in script_text
        assert "class KagglePreDispatchLatch" in script_text
        assert "class KaggleMutationAdequacyGate" in script_text


# ---------------------------------------------------------------------------
# Test Suite 8: Epistemic Purity & Zero-Banned-Words Verification
# ---------------------------------------------------------------------------


class TestEpistemicPurity:
    """Verifies that owned files contain zero promotional or banned words."""

    def test_no_banned_words_in_owned_files(self) -> None:
        banned_terms = [
            "guaran" + "tee",
            "guaran" + "teed",
            "guaran" + "teeing",
            "bullet" + "proof",
            "enterprise-" + "grade",
            "production-" + "safe",
            "100% " + "secure",
            "un" + "assailable",
            "un" + "hackable",
            "bank-" + "grade",
            "production-" + "ready",
            "proven " + "universally",
        ]

        repo_root = Path(__file__).resolve().parent.parent
        owned_files = [
            Path("src/gemma_developer_agent_engine.py"),
            Path("docs/competition/GOOGLE_GEMMA4_DEVELOPER_AGENT_SUBMISSION.md"),
            Path("tests/test_gemma_developer_agent_engine.py"),
        ]

        for file_path in owned_files:
            target_path = file_path if file_path.is_file() else (repo_root / file_path)
            if not target_path.is_file():
                continue
            content = target_path.read_text(encoding="utf-8").lower()
            for term in banned_terms:
                assert term not in content, (
                    f"Forbidden word '{term}' found in {target_path}"
                )
