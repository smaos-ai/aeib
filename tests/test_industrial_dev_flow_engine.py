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
tests/test_industrial_dev_flow_engine.py
================================================================================
Verification of the Industrial Dev-Flow Commissioning Engine (real Ed25519,
real files on disk, zero mocks).

Regression tests R1-R4 (test_11..test_14) fail on the previous version of the
module, where any key could clear a lockout, evidence arguments defaulted to
passing values, test hashes were self-reported by the caller, and a clearance
signed for one task could be replayed against another.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.industrial_dev_flow_engine import (
    FiveWhysDecompositionDAG,
    IndustrialDevFlowGovernor,
    TaskSpec,
    TripReasonCode,
    lockout_clearance_message,
)
from src.jcs_canonicalizer import encode_jcs

TEST_SRC = b"def test_ok():\n    assert 1 + 1 == 2\n"


def _pub_hex(key: ed25519.Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    ).hex()


@pytest.fixture
def operator() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
def gov(operator) -> IndustrialDevFlowGovernor:
    return IndustrialDevFlowGovernor(operator_public_keys_hex=(_pub_hex(operator),))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_bytes(TEST_SRC)
    return tmp_path


def _spec(task_id: str = "task_x", editable=("src/x.py",)) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        description="Implement x",
        editable_files=editable,
        pinned_test_hashes={"tests/test_x.py": "sha256:" + hashlib.sha256(TEST_SRC).hexdigest()},
    )


GOOD = {"src/x.py": "def f(a: int) -> int:\n    if a < 0:\n        raise ValueError('neg')\n    return a + 1\n"}
BAD = {"src/x.py": "def f(a):\n    pass\n"}


def _evaluate(gov, repo, files=GOOD, spec=None, bps=9500, passed=True):
    return gov.evaluate_candidate(
        spec=spec or _spec(),
        candidate_files=files,
        baseline_files={"src/x.py": ""},
        repo_root=repo,
        mutation_kill_ratio_bps=bps,
        execution_passed=passed,
    )


def _latch(gov, repo, spec):
    for _ in range(3):
        _evaluate(gov, repo, files=BAD, spec=spec)
    assert gov.is_locked_out(spec.task_id) is True


def test_1_task_spec_poka_yoke_validation():
    spec = _spec()
    assert spec.task_id == "task_x"
    assert spec.domain_floor_min_cardinality == 4
    assert spec.required_boundary_values == (-1, 0, 1, 2)
    base = dict(description="d", editable_files=("src/x.py",), pinned_test_hashes={})
    assert TaskSpec(task_id="t2", required_boundary_values=(0, 2), **base).required_boundary_values == (0, 2)
    with pytest.raises(ValueError, match="ERR_INVALID_TASK_ID"):
        TaskSpec(task_id="", **base)
    with pytest.raises(ValueError, match="ERR_INVALID_DESCRIPTION"):
        TaskSpec(task_id="t", description="", editable_files=("a",), pinned_test_hashes={})
    with pytest.raises(ValueError, match="ERR_EMPTY_SCOPE"):
        TaskSpec(task_id="t", description="d", editable_files=(), pinned_test_hashes={})
    with pytest.raises(ValueError, match="ERR_INVALID_BOUNDARY_VALUES"):
        TaskSpec(task_id="t", required_boundary_values=(1,), **base)
    with pytest.raises(ValueError, match="ERR_MISSING_BOUNDARY"):
        TaskSpec(task_id="t", required_boundary_values=(-1, 1, 3), **base)
    for bad_floor in (0, -1, "four"):
        with pytest.raises(ValueError, match="ERR_INVALID_DOMAIN_FLOOR"):
            TaskSpec(task_id="t", domain_floor_min_cardinality=bad_floor, **base)


def test_2_five_whys_decomposition_dag():
    dag = FiveWhysDecompositionDAG()
    dag.add_node("w1", 1, "Payment failed with 504")
    dag.add_node("w2", 2, "Ledger did not ack in 5s", ("w1",))
    dag.add_node("w3", 3, "Retry used fresh UUID", ("w2",))
    dag.add_node("w4", 4, "No pre-dispatch intent latch", ("w3",))
    dag.add_node("w5", 5, "EO-1 interlock missing in pipeline", ("w4",))
    assert dag.is_acyclic() is True
    assert len(dag.nodes) == 5
    assert dag.nodes["w1"].verified is False
    assert dag.nodes["w5"].why_level == 5
    with pytest.raises(ValueError, match="ERR_INVALID_WHY_LEVEL"):
        dag.add_node("x", 6, "too deep")
    with pytest.raises(ValueError, match="ERR_DUPLICATE_NODE_ID"):
        dag.add_node("w1", 1, "dup")
    with pytest.raises(ValueError, match="ERR_UNRESOLVED_DEPENDENCY"):
        dag.add_node("orphan", 2, "o", ("missing",))


def test_3_scope_violation_trips_immediately(gov, repo):
    files = dict(GOOD, **{"src/unauthorized.py": "def g():\n    return 1\n"})
    v = _evaluate(gov, repo, files=files)
    assert v.approved is False
    assert v.trip_code == TripReasonCode.TRIP_SCOPE_VIOLATION.value
    assert "src/unauthorized.py" in v.disposition


def test_4_test_file_modified_on_disk_trips(gov, repo):
    (repo / "tests" / "test_x.py").write_bytes(b"def test_ok():\n    assert True\n")
    v = _evaluate(gov, repo)
    assert v.approved is False
    assert v.trip_code == TripReasonCode.TRIP_TEST_TAMPER_DETECTED.value
    assert "tests/test_x.py" in v.disposition


def test_5_ast_scaffold_and_syntax_error_trip(gov, repo):
    v = _evaluate(gov, repo, files=BAD)
    assert v.trip_code == TripReasonCode.TRIP_SCAFFOLD_DETECTED.value
    v = _evaluate(gov, repo, files={"src/x.py": "class MockSink:\n    def log(self):\n        return 1\n"})
    assert v.trip_code == TripReasonCode.TRIP_SCAFFOLD_DETECTED.value
    assert "SCAFFOLD_TEST_DOUBLE_IN_PRODUCTION" in v.disposition
    v = _evaluate(gov, repo, files={"src/x.py": "def broken(\n"})
    assert v.trip_code == TripReasonCode.TRIP_ANSI_86_LOCKOUT.value  # third failure latches


def test_6_syntax_error_and_mutation_threshold(gov, repo):
    v = _evaluate(gov, repo, files={"src/x.py": "def broken(\n"}, spec=_spec("t_syn"))
    assert v.trip_code == TripReasonCode.TRIP_SYNTAX_ERROR.value
    v = _evaluate(gov, repo, bps=8999, spec=_spec("t_mut"))
    assert v.trip_code == TripReasonCode.TRIP_MUTATION_INADEQUATE.value
    assert "8999bps" in v.disposition
    v = _evaluate(gov, repo, bps=9000, spec=_spec("t_mut_ok"))
    assert v.approved is True


def test_7_ansi_86_lockout_and_pinned_operator_reset(gov, repo, operator):
    spec = _spec("t_86")
    v1 = _evaluate(gov, repo, files=BAD, spec=spec)
    v2 = _evaluate(gov, repo, files=BAD, spec=spec)
    assert (v1.attempt_count, v1.lockout_latched) == (1, False)
    assert (v2.attempt_count, v2.lockout_latched) == (2, False)
    v3 = _evaluate(gov, repo, files=BAD, spec=spec)
    assert (v3.attempt_count, v3.lockout_latched) == (3, True)
    assert v3.trip_code == TripReasonCode.TRIP_ANSI_86_LOCKOUT.value
    v4 = _evaluate(gov, repo, files=GOOD, spec=spec)
    assert v4.approved is False and v4.disposition == "REJECTED_LOCKED_OUT"
    assert v4.mutation_kill_ratio_bps == 0 and v4.lockout_latched is True

    sig = operator.sign(lockout_clearance_message("t_86", "n1")).hex()
    tampered = sig[:-2] + ("00" if sig[-2:] != "00" else "ff")
    assert gov.operator_clear_lockout("t_86", "n1", tampered, _pub_hex(operator)) is False
    assert gov.is_locked_out("t_86") is True
    assert gov.operator_clear_lockout("t_86", "n1", sig, _pub_hex(operator)) is True
    assert gov.is_locked_out("t_86") is False
    assert _evaluate(gov, repo, files=GOOD, spec=spec).attempt_count == 1


def test_8_nominal_commissioning_and_signed_verdict(gov, repo):
    v = _evaluate(gov, repo)
    assert v.approved is True
    assert v.disposition == "COMMISSIONED_VERIFIED_OUTCOME"
    assert v.trip_code is None and v.lockout_latched is False
    assert v.mutation_kill_ratio_bps == 9500
    expected = encode_jcs({
        "approved": True, "disposition": "COMMISSIONED_VERIFIED_OUTCOME",
        "lockout_latched": False, "mutation_kill_ratio_bps": 9500,
        "task_id": "task_x", "trip_code": "NONE",
    })
    assert v.deterministic_outcome_caid == "sha256:" + hashlib.sha256(expected).hexdigest()
    pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(v.authority_public_key_hex))
    pub.verify(bytes.fromhex(v.provenance_signature_hex), expected)
    cd = v.to_canonical_dict()
    assert (cd["approved"], cd["task_id"], cd["trip_code"]) == (True, "task_x", "NONE")


def test_9_dag_cycle_detection():
    dag = FiveWhysDecompositionDAG()
    dag.add_node("n1", 1, "a")
    dag.add_node("n2", 2, "b", ("n1",))
    dag.nodes["n1"] = type(dag.nodes["n1"])(
        node_id="n1", why_level=1, hypothesis_or_action="a", dependencies=("n2",), verified=False
    )
    assert dag.is_acyclic() is False


def test_10_execution_failure_and_custom_authority_key(operator, repo):
    key = ed25519.Ed25519PrivateKey.generate()
    gov = IndustrialDevFlowGovernor(key, operator_public_keys_hex=(_pub_hex(operator),))
    assert gov.authority_public_key_hex == _pub_hex(key)
    v = _evaluate(gov, repo, passed=False)
    assert v.approved is False
    assert v.trip_code == TripReasonCode.TRIP_EXECUTION_FAILURE.value
    assert v.mutation_kill_ratio_bps == 0
    assert gov.operator_clear_lockout("task_x", "n", "00" * 64, _pub_hex(operator)) is False


def test_11_r1_unpinned_key_cannot_clear_lockout(gov, repo, operator):
    spec = _spec("t_r1")
    _latch(gov, repo, spec)
    attacker = ed25519.Ed25519PrivateKey.generate()
    sig = attacker.sign(lockout_clearance_message("t_r1", "n1")).hex()
    assert gov.operator_clear_lockout("t_r1", "n1", sig, _pub_hex(attacker)) is False
    assert gov.is_locked_out("t_r1") is True
    with pytest.raises(ValueError, match="ERR_NO_PINNED_OPERATOR_KEYS"):
        IndustrialDevFlowGovernor(operator_public_keys_hex=())
    with pytest.raises(ValueError, match="ERR_INVALID_OPERATOR_KEY"):
        IndustrialDevFlowGovernor(operator_public_keys_hex=("ab",))


def test_12_r2_evidence_arguments_are_required_and_typed(gov, repo):
    with pytest.raises(TypeError):
        gov.evaluate_candidate(spec=_spec(), candidate_files=GOOD, baseline_files={}, repo_root=repo)
    for bps in (True, -1, 10001, 9500.0):
        with pytest.raises(ValueError, match="ERR_INVALID_MUTATION_BPS"):
            _evaluate(gov, repo, bps=bps)
    with pytest.raises(ValueError, match="ERR_INVALID_EXECUTION_PASSED"):
        _evaluate(gov, repo, passed=1)


def test_13_r3_missing_or_escaping_test_path_trips(gov, repo):
    spec = TaskSpec(task_id="t_r3", description="d", editable_files=("src/x.py",),
                    pinned_test_hashes={"../outside.py": "00" * 32})
    assert _evaluate(gov, repo, spec=spec).trip_code == TripReasonCode.TRIP_TEST_TAMPER_DETECTED.value
    (repo / "tests" / "test_x.py").unlink()
    assert _evaluate(gov, repo, spec=_spec("t_r3b")).trip_code == \
        TripReasonCode.TRIP_TEST_TAMPER_DETECTED.value


def test_14_r4_clearance_is_bound_to_task_and_single_use(gov, repo, operator):
    a, b = _spec("t_a"), _spec("t_b")
    _latch(gov, repo, a)
    _latch(gov, repo, b)
    sig_a = operator.sign(lockout_clearance_message("t_a", "n1")).hex()
    assert gov.operator_clear_lockout("t_b", "n1", sig_a, _pub_hex(operator)) is False
    assert gov.operator_clear_lockout("t_a", "n1", sig_a, _pub_hex(operator)) is True
    _latch(gov, repo, a)
    assert gov.operator_clear_lockout("t_a", "n1", sig_a, _pub_hex(operator)) is False  # replay
    with pytest.raises(ValueError, match="ERR_INVALID_CLEARANCE_NONCE"):
        lockout_clearance_message("t_a", "")
    with pytest.raises(ValueError, match="ERR_INVALID_TASK_ID"):
        lockout_clearance_message("", "n")
