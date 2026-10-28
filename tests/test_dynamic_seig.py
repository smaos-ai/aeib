#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_dynamic_seig.py
================================================================================
Test & Falsification Suite for Dynamic Self-Evolution Integrity Gate (SEIG v0.1).

Evaluated under the stated model:
- In-flight static AST security filters (forbidden modules, from-imports, method calls, AST nodes).
- Stub detection heuristics (inline True returns, simulated/mock/stub dicts).
- Subprocess dry-run execution with timeout enforcement and error capture.
- Behavioral mutation vector probe (flags mutation survival on corrupted inputs).
- Dataclass immutability and mount_authorized invariant.
- Epistemic linguistic compliance check.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from src.dynamic_seig import (
    DEFAULT_EXECUTION_TIMEOUT_SEC,
    MAX_ERROR_MSG_LEN,
    DynamicSelfEvolutionIntegrityGate,
    SEIGVerdict,
)


# -----------------------------------------------------------------------------
# Test 0: Configuration Constants & Immutability
# -----------------------------------------------------------------------------
def test_0_config_constants_and_immutability() -> None:
    assert DEFAULT_EXECUTION_TIMEOUT_SEC > 0.5
    assert MAX_ERROR_MSG_LEN == int("200")
    gate = DynamicSelfEvolutionIntegrityGate()
    assert gate.timeout_sec == DEFAULT_EXECUTION_TIMEOUT_SEC

    # Default mount_authorized must be strictly False
    v_default = SEIGVerdict(
        verdict="REJECTED",
        halt_code="ERR",
        tool_name="t",
        code_digest="d",
        violations=(),
        dry_run_latency_ms=1.0,
    )
    assert v_default.mount_authorized is False

    with pytest.raises(dataclasses.FrozenInstanceError):
        v_default.mount_authorized = True  # type: ignore


# -----------------------------------------------------------------------------
# Test 1: Positive Control (Clean Deterministic Tool)
# -----------------------------------------------------------------------------
def test_1_positive_control_clean_tool() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=1.5)
    clean_code = """
def compute_sum_squares(n: int = 10) -> int:
    total = sum(i * i for i in range(n))
    return total
"""
    v = gate.audit("compute_sum_squares", clean_code)
    assert v.verdict == "STATIC_AND_DRYRUN_ACCEPTED"
    assert v.halt_code == "OK_SEIG_ACCEPTED"
    assert v.mount_authorized is False
    assert v.tool_name == "compute_sum_squares"
    assert v.code_digest.startswith("sha256:")
    assert len(v.violations) == 0
    assert 0.0 <= v.dry_run_latency_ms < 5000.0


# -----------------------------------------------------------------------------
# Test 2: Syntax Error Rejection
# -----------------------------------------------------------------------------
def test_2_syntax_error_rejection() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=1.0)
    broken_code = "def broken_func(:\n    return 42\n"
    v = gate.audit("broken_func", broken_code)
    assert v.verdict == "REJECTED"
    assert v.halt_code == "HALT_SYNTHESIZED_TOOL_SYNTAX_ERROR"
    assert v.mount_authorized is False
    assert any("SyntaxError" in viol for viol in v.violations)


# -----------------------------------------------------------------------------
# Test 3: Forbidden Imports and Method Calls
# -----------------------------------------------------------------------------
def test_3_forbidden_imports_and_method_calls() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=1.0)

    # 1. Direct forbidden import
    code_subp = "import subprocess\ndef run_cmd():\n    return 'bad'\n"
    v_subp = gate.audit("run_cmd", code_subp)
    assert v_subp.verdict == "REJECTED"
    assert v_subp.halt_code == "HALT_SYNTHESIZED_TOOL_FORBIDDEN_IMPORT"
    assert any("FORBIDDEN_IMPORT:subprocess" in viol for viol in v_subp.violations)
    assert 0.0 <= v_subp.dry_run_latency_ms < 1000.0

    # 2. Forbidden import from
    code_os_sys = "from os import system\ndef run_cmd():\n    return 'bad'\n"
    v_os = gate.audit("run_cmd", code_os_sys)
    assert v_os.verdict == "REJECTED"
    assert v_os.halt_code == "HALT_SYNTHESIZED_TOOL_FORBIDDEN_IMPORT"
    assert any("FORBIDDEN_IMPORT_FROM:os.system" in viol for viol in v_os.violations)

    # 3. Forbidden method call (system, eval, exec, popen)
    code_eval = "def evaluate(obj):\n    return obj.eval('1+1')\n"
    v_eval = gate.audit("evaluate", code_eval)
    assert v_eval.verdict == "REJECTED"
    assert v_eval.halt_code == "HALT_SYNTHESIZED_TOOL_FORBIDDEN_IMPORT"
    assert any("FORBIDDEN_METHOD_CALL:eval" in viol for viol in v_eval.violations)


# -----------------------------------------------------------------------------
# Test 4: Forbidden AST Nodes
# -----------------------------------------------------------------------------
def test_4_forbidden_ast_nodes() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=1.0)

    # 1. Global node
    code_global = "x = 1\ndef modify():\n    global x\n    x = 2\n    return x\n"
    v_global = gate.audit("modify", code_global)
    assert v_global.verdict == "REJECTED"
    assert any("FORBIDDEN_AST_NODE:Global" in viol for viol in v_global.violations)

    # 2. Delete node
    code_del = "def remove_item(d):\n    del d['a']\n    return d\n"
    v_del = gate.audit("remove_item", code_del)
    assert v_del.verdict == "REJECTED"
    assert any("FORBIDDEN_AST_NODE:Delete" in viol for viol in v_del.violations)

    # 3. Nonlocal node
    code_nonlocal = "def outer():\n    y = 1\n    def inner():\n        nonlocal y\n        y = 2\n    return inner()\n"
    v_nonlocal = gate.audit("outer", code_nonlocal)
    assert v_nonlocal.verdict == "REJECTED"
    assert any("FORBIDDEN_AST_NODE:Nonlocal" in viol for viol in v_nonlocal.violations)


# -----------------------------------------------------------------------------
# Test 5: Mock & Stub Heuristics
# -----------------------------------------------------------------------------
def test_5_mock_and_stub_heuristics() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=1.0)

    # 1. Inline True return stub
    code_true = "def check_status():\n    return True\n"
    v_true = gate.audit("check_status", code_true)
    assert v_true.verdict == "REJECTED"
    assert any("HALT_SYNTHESIZED_TOOL_STUB_DETECTED:check_status" in viol for viol in v_true.violations)

    # 2. Simulated dictionary stub
    code_sim = "def get_state():\n    return {'status': 'simulated', 'count': 5}\n"
    v_sim = gate.audit("get_state", code_sim)
    assert v_sim.verdict == "REJECTED"
    assert any("HALT_SYNTHESIZED_TOOL_STUB_DETECTED:get_state" in viol for viol in v_sim.violations)

    # 3. Mock dictionary stub
    code_mock = "def get_result():\n    return {'status': 'mock'}\n"
    v_mock = gate.audit("get_result", code_mock)
    assert v_mock.verdict == "REJECTED"
    assert any("HALT_SYNTHESIZED_TOOL_STUB_DETECTED:get_result" in viol for viol in v_mock.violations)


# -----------------------------------------------------------------------------
# Test 6: Dry-Run Crash and Nonzero Exit
# -----------------------------------------------------------------------------
def test_6_dry_run_crash_and_nonzero_exit() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=1.0)

    # Long error message to test MAX_ERROR_MSG_LEN boundary
    long_err = "X" * 350
    code_crash = f"def faulty():\n    raise RuntimeError('{long_err}')\n"
    v = gate.audit("faulty", code_crash)
    assert v.verdict == "REJECTED"
    assert v.halt_code == "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED"
    assert len(v.violations[0]) <= MAX_ERROR_MSG_LEN
    assert "EXC:" in v.violations[0]


# -----------------------------------------------------------------------------
# Test 7: Dry-Run Execution Timeout
# -----------------------------------------------------------------------------
def test_7_dry_run_execution_timeout() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=0.2)

    code_loop = "def infinite_loop():\n    import time\n    time.sleep(2.0)\n    return 'done'\n"
    v = gate.audit("infinite_loop", code_loop)
    assert v.verdict == "REJECTED"
    assert v.halt_code == "HALT_SYNTHESIZED_TOOL_TIMEOUT"
    assert any("ERR_DRYRUN_TIMEOUT" in viol for viol in v.violations)


# -----------------------------------------------------------------------------
# Test 8: Behavioral Mutation Vector Probe
# -----------------------------------------------------------------------------
def test_8_behavioral_mutation_vector_probe() -> None:
    gate = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=1.5)

    # 1. Initial audit failure immediately returned
    v_bad = gate.verify_against_vectors("bad", "import subprocess\ndef bad(): pass", [], [])
    assert v_bad is not None
    assert v_bad.verdict == "REJECTED"
    assert v_bad.halt_code == "HALT_SYNTHESIZED_TOOL_FORBIDDEN_IMPORT"

    # 2. Valid tool: requires positive integers, raises ValueError on negative or invalid
    clean_tool_code = """
def calculate_discount(price: int, discount_pct: int) -> int:
    if price < 0 or discount_pct < 0 or discount_pct > 100:
        raise ValueError("Invalid price or discount")
    return price - (price * discount_pct // 100)
"""
    pos_vecs = [{"price": 100, "discount_pct": 20}, {"price": 50, "discount_pct": 10}]
    mut_vecs = [{"price": -10, "discount_pct": 20}, {"price": 100, "discount_pct": 150}]

    v_valid = gate.verify_against_vectors(
        tool_name="calculate_discount",
        source_code=clean_tool_code,
        positive_vectors=pos_vecs,
        mutation_vectors=mut_vecs,
    )
    assert v_valid.verdict == "STATIC_AND_DRYRUN_ACCEPTED"
    assert v_valid.halt_code == "OK_SEIG_ACCEPTED"

    # 2b. Positive vector failure emits error to stdout
    code_pos_fail = "def calculate_discount(price: int, discount_pct: int) -> int:\n    if price == 50:\n        raise RuntimeError('pos_fail')\n    return 42\n"
    v_pos_fail = gate.verify_against_vectors(
        tool_name="calculate_discount",
        source_code=code_pos_fail,
        positive_vectors=pos_vecs,
        mutation_vectors=mut_vecs,
    )
    assert v_pos_fail.verdict == "REJECTED"
    assert v_pos_fail.halt_code == "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED"
    assert any("POS_FAIL:pos_fail" in viol for viol in v_pos_fail.violations)

    # 3. Stub tool: blindly returns True or a static dict on mutated inputs
    stub_tool_code = """
def calculate_discount(price: int, discount_pct: int) -> dict:
    if price > 0:
        return {"amount": 80, "status": "ok"}
    return {"amount": 0, "status": "ok"}
"""
    v_stub = gate.verify_against_vectors(
        tool_name="calculate_discount",
        source_code=stub_tool_code,
        positive_vectors=pos_vecs,
        mutation_vectors=mut_vecs,
    )
    assert v_stub.verdict == "REJECTED"
    assert v_stub.halt_code == "HALT_SYNTHESIZED_TOOL_MUTATION_SURVIVED"

    # 4. Tool missing entrypoint in vector probe
    missing_entry_code = "def other_name():\n    return 1\n"
    v_missing = gate.verify_against_vectors(
        tool_name="calculate_discount",
        source_code=missing_entry_code,
        positive_vectors=pos_vecs,
        mutation_vectors=mut_vecs,
    )
    assert v_missing.verdict == "REJECTED"
    assert v_missing.halt_code == "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED"

    # 5. Vector probe timeout (passes dry-run on x=1, hangs in vector probe on x=2)
    gate_short = DynamicSelfEvolutionIntegrityGate(execution_timeout_sec=0.2)
    code_hang = "def hang(x):\n    import time\n    if x == 2:\n        time.sleep(2.0)\n    return x\n"
    v_hang = gate_short.verify_against_vectors("hang", code_hang, [{"x": 1}, {"x": 2}], [{"x": 3}])
    assert v_hang is not None
    assert v_hang.halt_code == "HALT_SYNTHESIZED_TOOL_TIMEOUT"
    assert any("ERR_PROBE_TIMEOUT" in viol for viol in v_hang.violations)

    # 6. Verify ms conversion on AST violation (line 170) and subprocess exception handling (lines 314 & 404)
    import subprocess as _sub
    import time as _time

    orig_pc = _time.perf_counter
    ticks = iter([10.0, 10.5])
    _time.perf_counter = lambda: next(ticks)  # type: ignore[assignment]
    try:
        v_lat = gate.audit("bad_lat", "import subprocess\ndef bad_lat(): pass")
    finally:
        _time.perf_counter = orig_pc  # type: ignore[assignment]
    assert v_lat.dry_run_latency_ms == 500.0

    orig_run = _sub.run
    _sub.run = lambda *a, **kw: (_ for _ in ()).throw(OSError("spawn_err"))  # type: ignore[assignment]
    try:
        dry_exc = gate._run_dry_run("def f(): pass", "f", None)
        vec_exc = gate._run_vector_probe("def f(): pass", "f", [], [])
    finally:
        _sub.run = orig_run  # type: ignore[assignment]
    assert dry_exc["passed"] is False
    assert dry_exc["halt_code"] == "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED"
    assert vec_exc["passed"] is False
    assert vec_exc["halt_code"] == "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED"


# -----------------------------------------------------------------------------
# Test 9: Epistemic Linguistic Compliance (Zero Banned Words)
# -----------------------------------------------------------------------------
def test_9_epistemic_linguistic_compliance() -> None:
    banned_prefixes = [
        "guaran" + "tee",
        "proven univer" + "sally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]

    files_to_check = [
        Path("src/dynamic_seig.py"),
        Path("tests/test_dynamic_seig.py"),
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"File {file_path} must exist"
        content = file_path.read_text(encoding="utf-8")
        for banned in banned_prefixes:
            match = re.search(r"\b" + re.escape(banned), content, re.IGNORECASE)
            assert match is None, (
                f"Epistemic boundary violation: found banned term '{banned}' "
                f"in {file_path}"
            )
