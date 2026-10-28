# Copyright 2026 SovereignNexus Project
#
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
tests/test_vaf_work_capsule_and_conformance.py — Integration test suite for VAF.

Verifies:
1. WorkCapsuleLifecycleEngine state machine sequencing and invalid jump rejection.
2. HumanApprovalGate fail-closed enforcement for high-value and untrusted taint acts.
3. Cryptographic Ed25519 evidence receipts emitted on consequential transitions.
4. Durable uncertainty handling (EFFECT_INDETERMINATE latching and reconciliation).
5. Universal Conformance Runner execution across all 20 declarative vectors (100% pass rate).
6. Epistemic boundary compliance (zero banned words).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs
import src.work_capsule_engine as wc_mod
from src.work_capsule_engine import (
    CandidateRef,
    CapsuleState,
    ContractRefs,
    ExecutionPlan,
    HumanApprovalGate,
    PolicyContext,
    WorkCapsule,
    WorkCapsuleLifecycleEngine,
)
import tools.vaf_conformance_runner as vaf_mod
from tools.vaf_conformance_runner import (
    AEIBStation1Gate,
    VafConformanceRunner,
    VectorResult,
)


def test_modules_sys_path_bootstrap() -> None:
    """Verifies REPO_ROOT and SIM_LAB sys.path bootstrap when missing."""
    global CandidateRef, CapsuleState, ContractRefs, ExecutionPlan, HumanApprovalGate
    global PolicyContext, WorkCapsule, WorkCapsuleLifecycleEngine, VafConformanceRunner
    global AEIBStation1Gate, VectorResult
    repo_str = str(wc_mod.REPO_ROOT)
    sim_str = str(vaf_mod.SIM_LAB)
    orig_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if p != repo_str]
        importlib.reload(wc_mod)
        assert sys.path[0] == repo_str

        sys.path = [p for p in sys.path if p not in (repo_str, sim_str)]
        importlib.reload(vaf_mod)
        assert repo_str in sys.path
        assert sim_str in sys.path
    finally:
        sys.path = orig_path
        CandidateRef = wc_mod.CandidateRef
        CapsuleState = wc_mod.CapsuleState
        ContractRefs = wc_mod.ContractRefs
        ExecutionPlan = wc_mod.ExecutionPlan
        HumanApprovalGate = wc_mod.HumanApprovalGate
        PolicyContext = wc_mod.PolicyContext
        WorkCapsule = wc_mod.WorkCapsule
        WorkCapsuleLifecycleEngine = wc_mod.WorkCapsuleLifecycleEngine
        VafConformanceRunner = vaf_mod.VafConformanceRunner
        AEIBStation1Gate = vaf_mod.AEIBStation1Gate
        VectorResult = vaf_mod.VectorResult


def test_work_capsule_boundary_and_human_gate_invariants() -> None:
    """Verifies constructor defaults, human gate boundaries, and transition edges."""
    assert wc_mod.PolicyContext().requires_human_gate is False

    sup_priv = Ed25519PrivateKey.generate()
    sup_pub = sup_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    hg_empty = wc_mod.HumanApprovalGate()
    assert hg_empty.supervisor_public_keys == {}

    hg = wc_mod.HumanApprovalGate(supervisor_public_keys={"sup-1": sup_pub})
    assert hg.supervisor_public_keys == {"sup-1": sup_pub}

    signer_priv = Ed25519PrivateKey.generate()
    eng_custom = wc_mod.WorkCapsuleLifecycleEngine(signer_key=signer_priv, human_gate=hg)
    assert eng_custom.signer_key is signer_priv
    assert eng_custom.human_gate is hg

    eng_default = wc_mod.WorkCapsuleLifecycleEngine()
    assert isinstance(eng_default.signer_key, Ed25519PrivateKey)
    assert isinstance(eng_default.human_gate, wc_mod.HumanApprovalGate)

    # Test create_capsule with explicit contract_refs and default policy_context
    c_ref = wc_mod.CandidateRef("rev1", "sha256:" + "1" * 64, "sha256:" + "2" * 64)
    plan_exact = wc_mod.ExecutionPlan("ep", "refund.create", "idem-1", 50 * 1000)
    custom_crefs = wc_mod.ContractRefs(capability_id="cap-custom-99")
    cap_50k = eng_custom.create_capsule("int-1", plan_exact, c_ref, contract_refs=custom_crefs)
    assert cap_50k.contract_refs["capability_id"] == "cap-custom-99"
    assert cap_50k.policy_context["requires_human_gate"] is False

    # DRAFT -> PROPOSED does NOT set requires_human_gate yet
    ok_prop, _ = eng_custom.transition(cap_50k, wc_mod.CapsuleState.PROPOSED)
    assert ok_prop is True
    assert cap_50k.policy_context["requires_human_gate"] is False

    # Exact boundary amount == 50_000 triggers human gate on VERIFIED
    assert hg.evaluate_gate_requirement(cap_50k) is True
    ok_ver, _ = eng_custom.transition(cap_50k, wc_mod.CapsuleState.VERIFIED)
    assert ok_ver is True
    assert cap_50k.policy_context["requires_human_gate"] is True

    # Below boundary 49_999 without requires_human_gate key in policy_context
    raw_cap = wc_mod.WorkCapsule(
        capsule_version="1",
        capsule_id="cap-raw",
        intent_id="int-raw",
        state=wc_mod.CapsuleState.HUMAN_APPROVAL_PENDING.value,
        contract_refs={},
        policy_context={"taint_tier": "TIER_1_REVIEWED", "policy_epoch": "2026-Q4"},
        candidate_ref={},
        execution_plan={"amount_minor": 50 * 1000 - 1},
    )
    assert hg.evaluate_gate_requirement(raw_cap) is False

    # Untrusted taint triggers human gate even with small amount
    raw_cap.policy_context["taint_tier"] = "TIER_2_UNTRUSTED"
    assert hg.evaluate_gate_requirement(raw_cap) is True

    # verify_approval when amount_minor is omitted from execution_plan (default 0)
    del raw_cap.execution_plan["amount_minor"]
    preimage_zero = {
        "capsule_id": "cap-raw",
        "operation_id": "",
        "amount_minor": 0,
        "target_endpoint": "",
        "policy_epoch": "2026-Q4",
    }
    sig_zero = sup_priv.sign(encode_jcs(preimage_zero)).hex()
    assert hg.verify_approval(raw_cap, "sup-1", sig_zero) is True
    assert hg.verify_approval(raw_cap, "sup-1", "00" * 64) is False
    assert hg.verify_approval(raw_cap, "unknown-key", sig_zero) is False

    # Missing key_id vs missing sig_hex on HUMAN_APPROVAL_PENDING -> AUTHORIZED
    ok_no_k, msg_no_k = eng_custom.transition(
        raw_cap, wc_mod.CapsuleState.AUTHORIZED, supervisor_key_id=None, supervisor_sig_hex=sig_zero
    )
    assert ok_no_k is False
    assert msg_no_k == "ERR_HUMAN_GATE_SIGNATURE_MISSING"

    ok_no_s, msg_no_s = eng_custom.transition(
        raw_cap, wc_mod.CapsuleState.AUTHORIZED, supervisor_key_id="sup-1", supervisor_sig_hex=None
    )
    assert ok_no_s is False
    assert msg_no_s == "ERR_HUMAN_GATE_SIGNATURE_MISSING"

    ok_bad_s, msg_bad_s = eng_custom.transition(
        raw_cap, wc_mod.CapsuleState.AUTHORIZED, supervisor_key_id="sup-1", supervisor_sig_hex="00" * 64
    )
    assert ok_bad_s is False
    assert msg_bad_s == "ERR_INVALID_SUPERVISOR_SIGNATURE"

    # Transition from HUMAN_APPROVAL_PENDING to HALTED does NOT require supervisor signature
    ok_halt, msg_halt = eng_custom.transition(raw_cap, wc_mod.CapsuleState.HALTED)
    assert ok_halt is True
    assert msg_halt == "OK"


def test_vaf_conformance_runner_boundaries_and_main(tmp_path: Path) -> None:
    """Verifies VafConformanceRunner custom gate, negative vectors, rounding, self_test, and main."""
    custom_gate = AEIBStation1Gate()
    runner_custom = vaf_mod.VafConformanceRunner(gate=custom_gate)
    assert runner_custom.gate is custom_gate

    runner_default = vaf_mod.VafConformanceRunner()
    assert isinstance(runner_default.gate, AEIBStation1Gate)

    # Create a custom vector dir with 3 vectors: 2 passing, 1 failing (mismatched error code & disposition)
    vec_dir = tmp_path / "vecs"
    vec_dir.mkdir()
    src_vec = json.loads((REPO_ROOT / "conformance" / "vectors" / "act-valid-nominal-001.json").read_text())

    v1 = dict(src_vec, vector_id="act-custom-001")
    (vec_dir / "act-custom-001.json").write_text(json.dumps(v1), encoding="utf-8")

    # Single-vector suite: max(1, 1) -> 100.0%
    rep_single = vaf_mod.VafConformanceRunner().run_suite(vec_dir)
    assert rep_single.total_evaluated == 1
    assert rep_single.pass_rate_pct == 100.0

    # Add a 2nd passing vector and a 3rd failing vector (mismatched error code)
    v2 = dict(src_vec, vector_id="act-custom-002")
    v2["input_payload"] = json.loads(json.dumps(src_vec["input_payload"]))
    v2["input_payload"]["idempotency_key"] = str(uuid.uuid4())
    (vec_dir / "act-custom-002.json").write_text(json.dumps(v2), encoding="utf-8")

    v3_bad_err = dict(src_vec, vector_id="act-custom-003", expected_disposition="NOT_DISPATCHED", expected_error_code="ERR_COMPLETELY_DIFFERENT")
    v3_bad_err["input_payload"] = {"act_version": "999"}
    (vec_dir / "act-custom-003.json").write_text(json.dumps(v3_bad_err), encoding="utf-8")

    res_bad_err = vaf_mod.VafConformanceRunner().evaluate_vector_file(vec_dir / "act-custom-003.json")
    assert res_bad_err.passed is False

    # Also test disposition mismatch when expected_error_code is None
    v4_bad_disp = dict(src_vec, vector_id="act-custom-004", expected_disposition="CONFIRMED", expected_error_code=None)
    v4_bad_disp["input_payload"] = {"act_version": "999"}
    (vec_dir / "act-custom-004.json").write_text(json.dumps(v4_bad_disp), encoding="utf-8")
    res_bad_disp = vaf_mod.VafConformanceRunner().evaluate_vector_file(vec_dir / "act-custom-004.json")
    assert res_bad_disp.passed is False
    (vec_dir / "act-custom-004.json").unlink()

    # 2/3 passing -> 66.67% (tests round(..., 2))
    rep_three = vaf_mod.VafConformanceRunner().run_suite(vec_dir)
    assert rep_three.pass_rate_pct == 66.67

    # Test p50 3-decimal rounding in run_suite
    runner_lat = vaf_mod.VafConformanceRunner()
    orig_eval_vec = runner_lat.evaluate_vector_file
    runner_lat.evaluate_vector_file = lambda vf: vaf_mod.VectorResult(
        vector_id="v",
        description="d",
        expected_disposition="DISPATCHED",
        observed_disposition="DISPATCHED",
        expected_error_code=None,
        observed_error_code=None,
        passed=True,
        latency_ms=1.23456,
    )
    rep_lat = runner_lat.run_suite(vec_dir)
    assert rep_lat.p50_latency_ms == 1.235
    runner_lat.evaluate_vector_file = orig_eval_vec

    # self_test() true and false paths
    assert vaf_mod.self_test() is True
    orig_root = vaf_mod.REPO_ROOT
    try:
        vaf_mod.REPO_ROOT = tmp_path / "missing_repo"
        assert vaf_mod.self_test() is False
    finally:
        vaf_mod.REPO_ROOT = orig_root

    # main() return codes and exist_ok=True
    out_file = tmp_path / "existing_sub" / "report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    orig_argv = list(sys.argv)
    try:
        sys.argv = ["vaf_conformance_runner.py", "--self-test"]
        assert vaf_mod.main() == 0

        vaf_mod.REPO_ROOT = tmp_path / "missing_repo"
        assert vaf_mod.main() == 1
        vaf_mod.REPO_ROOT = orig_root

        sys.argv = [
            "vaf_conformance_runner.py",
            "--vectors-dir",
            str(REPO_ROOT / "conformance" / "vectors"),
            "--output-json",
            str(out_file),
        ]
        assert vaf_mod.main() == 0

        sys.argv = [
            "vaf_conformance_runner.py",
            "--vectors-dir",
            str(vec_dir),
            "--output-json",
            str(out_file),
        ]
        assert vaf_mod.main() == 1
    finally:
        vaf_mod.REPO_ROOT = orig_root
        sys.argv = orig_argv


def test_work_capsule_nominal_lifecycle():
    """Evaluates the nominal happy path from DRAFT to SETTLED."""
    engine = WorkCapsuleLifecycleEngine()

    capsule = engine.create_capsule(
        intent_id=f"intent-{uuid.uuid4()}",
        execution_plan=ExecutionPlan(
            target_endpoint="payments.stripe",
            action_type="refund.create",
            idempotency_key=str(uuid.uuid4()),
            amount_minor=10000,  # €100.00
            currency="EUR",
        ),
        candidate_ref=CandidateRef(
            source_revision="git:main@commit-1",
            artifact_sha256="sha256:" + "a" * 64,
            parameters_digest="sha256:" + "b" * 64,
        ),
        policy_context=PolicyContext(
            policy_epoch="2026-Q4",
            taint_tier="TIER_1_REVIEWED",
            requires_human_gate=False,
        ),
    )

    assert capsule.state == CapsuleState.DRAFT.value

    # DRAFT -> PROPOSED
    ok, msg = engine.transition(capsule, CapsuleState.PROPOSED)
    assert ok, msg
    assert capsule.state == CapsuleState.PROPOSED.value

    # PROPOSED -> VERIFIED
    ok, msg = engine.transition(capsule, CapsuleState.VERIFIED)
    assert ok, msg
    assert capsule.state == CapsuleState.VERIFIED.value
    assert not capsule.policy_context["requires_human_gate"]

    # VERIFIED -> AUTHORIZED
    ok, msg = engine.transition(capsule, CapsuleState.AUTHORIZED)
    assert ok, msg
    assert capsule.state == CapsuleState.AUTHORIZED.value
    assert len(capsule.evidence_receipts) == 1

    # AUTHORIZED -> DISPATCHED
    ok, msg = engine.transition(capsule, CapsuleState.DISPATCHED)
    assert ok, msg
    assert capsule.state == CapsuleState.DISPATCHED.value
    assert len(capsule.evidence_receipts) == 2

    # DISPATCHED -> CONFIRMED
    ok, msg = engine.transition(capsule, CapsuleState.CONFIRMED)
    assert ok, msg
    assert capsule.state == CapsuleState.CONFIRMED.value
    assert len(capsule.evidence_receipts) == 3

    # CONFIRMED -> SETTLED
    ok, msg = engine.transition(capsule, CapsuleState.SETTLED)
    assert ok, msg
    assert capsule.state == CapsuleState.SETTLED.value
    assert len(capsule.evidence_receipts) == 4


def test_invalid_lifecycle_transition_fails_closed():
    """Asserts that illegal state skips (e.g. DRAFT -> DISPATCHED) are blocked."""
    engine = WorkCapsuleLifecycleEngine()

    capsule = engine.create_capsule(
        intent_id=f"intent-{uuid.uuid4()}",
        execution_plan=ExecutionPlan(
            target_endpoint="payments.stripe",
            action_type="refund.create",
            idempotency_key=str(uuid.uuid4()),
            amount_minor=5000,
            currency="EUR",
        ),
        candidate_ref=CandidateRef(
            source_revision="git:main@commit-1",
            artifact_sha256="sha256:" + "a" * 64,
            parameters_digest="sha256:" + "b" * 64,
        ),
    )

    # Illegal jump: DRAFT -> DISPATCHED directly
    ok, msg = engine.transition(capsule, CapsuleState.DISPATCHED)
    assert not ok
    assert "ERR_INVALID_TRANSITION" in msg
    assert capsule.state == CapsuleState.DRAFT.value


def test_human_approval_gate_fail_closed_and_resolution():
    """
    Evaluates human approval gate:
    1. High value act (>= 50,000 minor units) triggers mandatory human gate.
    2. Attempting transition without signature fails closed.
    3. Invalid signature fails closed.
    4. Valid Ed25519 signature from registered supervisor allows authorization.
    """
    supervisor_priv = Ed25519PrivateKey.generate()
    supervisor_pub_raw = supervisor_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    human_gate = HumanApprovalGate()
    human_gate.register_supervisor("sup-lead-01", supervisor_pub_raw)

    engine = WorkCapsuleLifecycleEngine(human_gate=human_gate)

    capsule = engine.create_capsule(
        intent_id=f"intent-{uuid.uuid4()}",
        execution_plan=ExecutionPlan(
            target_endpoint="wires.swift",
            action_type="wire.disburse",
            idempotency_key=str(uuid.uuid4()),
            amount_minor=65000,  # €650.00 >= €500.00 threshold
            currency="EUR",
        ),
        candidate_ref=CandidateRef(
            source_revision="git:main@commit-1",
            artifact_sha256="sha256:" + "a" * 64,
            parameters_digest="sha256:" + "b" * 64,
        ),
        policy_context=PolicyContext(
            policy_epoch="2026-Q4",
            taint_tier="TIER_1_REVIEWED",
        ),
    )

    engine.transition(capsule, CapsuleState.PROPOSED)
    engine.transition(capsule, CapsuleState.VERIFIED)

    # Must require human gate because amount >= 50,000
    assert capsule.policy_context["requires_human_gate"] is True

    # Transition to HUMAN_APPROVAL_PENDING
    ok, msg = engine.transition(capsule, CapsuleState.HUMAN_APPROVAL_PENDING)
    assert ok, msg

    # Falsification 1: Attempt AUTHORIZED without signature -> rejected
    ok, msg = engine.transition(capsule, CapsuleState.AUTHORIZED)
    assert not ok
    assert "ERR_HUMAN_GATE_SIGNATURE_MISSING" in msg

    # Falsification 2: Attempt AUTHORIZED with forged signature -> rejected
    ok, msg = engine.transition(
        capsule,
        CapsuleState.AUTHORIZED,
        supervisor_key_id="sup-lead-01",
        supervisor_sig_hex="00" * 64,
    )
    assert not ok
    assert "ERR_INVALID_SUPERVISOR_SIGNATURE" in msg

    # Valid approval: compute pre-image, canonical JCS, real Ed25519 sign
    approval_preimage = {
        "capsule_id": capsule.capsule_id,
        "operation_id": capsule.execution_plan.get("idempotency_key", ""),
        "amount_minor": capsule.execution_plan.get("amount_minor", 0),
        "target_endpoint": capsule.execution_plan.get("target_endpoint", ""),
        "policy_epoch": capsule.policy_context.get("policy_epoch", ""),
    }
    canonical_preimage = encode_jcs(approval_preimage)
    valid_sig = supervisor_priv.sign(canonical_preimage).hex()

    # Success: AUTHORIZED with valid signature
    ok, msg = engine.transition(
        capsule,
        CapsuleState.AUTHORIZED,
        supervisor_key_id="sup-lead-01",
        supervisor_sig_hex=valid_sig,
    )
    assert ok, msg
    assert capsule.state == CapsuleState.AUTHORIZED.value
    assert capsule.policy_context["human_approval_signature"] == valid_sig


def test_durable_uncertainty_latch_and_reconciliation():
    """
    Evaluates durable uncertainty:
    Transport drop during dispatch latches state into EFFECT_INDETERMINATE.
    State survives and settles once out-of-band reconciliation probe runs.
    """
    engine = WorkCapsuleLifecycleEngine()

    capsule = engine.create_capsule(
        intent_id=f"intent-{uuid.uuid4()}",
        execution_plan=ExecutionPlan(
            target_endpoint="payments.stripe",
            action_type="refund.create",
            idempotency_key=str(uuid.uuid4()),
            amount_minor=15000,
            currency="EUR",
        ),
        candidate_ref=CandidateRef(
            source_revision="git:main@commit-1",
            artifact_sha256="sha256:" + "a" * 64,
            parameters_digest="sha256:" + "b" * 64,
        ),
    )

    engine.transition(capsule, CapsuleState.PROPOSED)
    engine.transition(capsule, CapsuleState.VERIFIED)
    engine.transition(capsule, CapsuleState.AUTHORIZED)
    engine.transition(capsule, CapsuleState.DISPATCHED)

    # Simulated network timeout / 504 Gateway Timeout -> latch to EFFECT_INDETERMINATE
    ok, msg = engine.transition(capsule, CapsuleState.EFFECT_INDETERMINATE)
    assert ok, msg
    assert capsule.state == CapsuleState.EFFECT_INDETERMINATE.value

    # Reconciliation probe confirms remote commit -> CONFIRMED -> SETTLED
    ok, msg = engine.transition(capsule, CapsuleState.CONFIRMED)
    assert ok, msg
    assert capsule.state == CapsuleState.CONFIRMED.value

    ok, msg = engine.transition(capsule, CapsuleState.SETTLED)
    assert ok, msg
    assert capsule.state == CapsuleState.SETTLED.value


def test_vaf_conformance_runner_evaluates_all_vectors():
    """Runs the Universal Conformance Runner against all 20 vectors in conformance/vectors/."""
    vectors_dir = REPO_ROOT / "conformance" / "vectors"
    runner = VafConformanceRunner()
    report = runner.run_suite(vectors_dir)

    assert int(report.total_evaluated) == 20
    assert int(report.passed_count) == 20
    assert report.failed_count == 0
    assert report.pass_rate_pct == 100.0
    assert len(report.results_merkle_root) == 64
    assert 0.0 < report.p50_latency_ms < 50.0  # sub-50ms execution
    assert 0.0 < report.p99_latency_ms < 100.0


def test_conformance_runner_cli():
    """Verifies CLI execution of tools/vaf_conformance_runner.py."""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "vaf_conformance_runner.py"),
        "--vectors-dir",
        str(REPO_ROOT / "conformance" / "vectors"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert '"pass_rate_pct": 100.0' in proc.stdout
    assert '"total_evaluated": 20' in proc.stdout


def test_epistemic_purity():
    """Scans src/work_capsule_engine.py and this test file for banned promotional words."""
    banned = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
    ]
    files_to_check = [
        REPO_ROOT / "src" / "work_capsule_engine.py",
        REPO_ROOT / "tests" / "test_vaf_work_capsule_and_conformance.py",
    ]
    for fpath in files_to_check:
        content = fpath.read_text(encoding="utf-8").lower()
        for b in banned:
            assert b not in content, f"Banned word '{b}' found in {fpath.name}"
