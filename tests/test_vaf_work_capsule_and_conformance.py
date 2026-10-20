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
from src.work_capsule_engine import (
    CandidateRef,
    CapsuleState,
    ContractRefs,
    ExecutionPlan,
    HumanApprovalGate,
    PolicyContext,
    WorkCapsuleLifecycleEngine,
)
from tools.vaf_conformance_runner import VafConformanceRunner


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

    assert report.total_evaluated == 20
    assert report.passed_count == 20
    assert report.failed_count == 0
    assert report.pass_rate_pct == 100.0
    assert len(report.results_merkle_root) == 64
    assert report.p50_latency_ms < 50.0  # sub-50ms execution
    assert report.p99_latency_ms < 100.0


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
