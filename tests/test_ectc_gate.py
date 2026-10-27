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
tests/test_ectc_gate.py
================================================================================
Comprehensive verification and falsification suite for the Evidence-Carrying
Termination Certificate (ECTC), TestSuiteHashLock, TaskStateLedger, and
SemanticConvergenceMonitor.
"""

import hashlib
import sys
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataclasses import FrozenInstanceError
from src.jcs_canonicalizer import encode_jcs
from src.evidence_carrying_termination import (
    EvidenceCarryingTerminationCertificate,
    TestSuiteHashLock,
    TestModificationWarrant,
    TaskStateLedger,
    SemanticConvergenceMonitor,
)


@pytest.fixture
def test_keys():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_hex = pub.public_bytes_raw().hex()
    return priv, pub_hex


def test_test_suite_hash_lock_tamper_detection(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    # Create baseline tests
    t1 = tests_dir / "test_auth.py"
    t1.write_text("def test_ok(): assert True\n")
    t2 = tests_dir / "test_billing.py"
    t2.write_text("def test_pay(): assert True\n")

    baseline = TestSuiteHashLock.compute_manifest(tests_dir)
    assert len(baseline) == 2
    assert "test_auth.py" in baseline
    assert "test_billing.py" in baseline

    # 1. Unmodified suite passes
    ok, msg = TestSuiteHashLock.verify_integrity(tests_dir, baseline)
    assert ok is True
    assert msg == "OK_TEST_SUITE_INTEGRITY_PRESERVED"

    # 2. Tampering test content triggers HALT_TEST_TAMPERED
    t1.write_text("def test_ok(): pass\n")  # modified assertion!
    ok_tamper, msg_tamper = TestSuiteHashLock.verify_integrity(tests_dir, baseline)
    assert ok_tamper is False
    assert "HALT_TEST_TAMPERED: TEST_FILE_MUTATED_test_auth.py" in msg_tamper

    # Revert modification
    t1.write_text("def test_ok(): assert True\n")

    # 3. Deleting a test triggers HALT_TEST_TAMPERED
    t2.unlink()
    ok_del, msg_del = TestSuiteHashLock.verify_integrity(tests_dir, baseline)
    assert ok_del is False
    assert "HALT_TEST_TAMPERED: TEST_FILE_DELETED_test_billing.py" in msg_del

    # Restore t2 and add unauthorized test
    t2.write_text("def test_pay(): assert True\n")
    t3 = tests_dir / "test_extra.py"
    t3.write_text("def test_cheat(): assert True\n")
    ok_add, msg_add = TestSuiteHashLock.verify_integrity(tests_dir, baseline)
    assert ok_add is False
    assert "HALT_TEST_TAMPERED: UNEXPECTED_TEST_FILE_ADDED_test_extra.py" in msg_add


def test_test_modification_warrant_authorization(tmp_path, test_keys):
    priv, pub_hex = test_keys
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    t1 = tests_dir / "test_mod.py"
    t1.write_text("def test_old(): assert 1 == 1\n")
    baseline = TestSuiteHashLock.compute_manifest(tests_dir)

    # Legitimate test evolution requires signed warrant
    t1.write_text("def test_new(): assert 2 == 2\n")

    # Unsigned / forged warrant fails
    forged_warrant = TestModificationWarrant(
        warrant_id="w-001",
        authorized_test_paths=("test_mod.py",),
        justification="Update to v2 contract",
        issuer_public_key_hex=pub_hex,
        signature_hex="00" * 64,
    )
    assert forged_warrant.verify_signature() is False
    ok_forged, msg_forged = TestSuiteHashLock.verify_integrity(tests_dir, baseline, forged_warrant)
    assert ok_forged is False
    assert "INVALID_WARRANT_SIGNATURE" in msg_forged

    # Properly signed warrant succeeds
    payload = {
        "warrant_id": "w-002",
        "authorized_test_paths": ["test_mod.py"],
        "justification": "Authorized test evolution",
        "issuer_public_key_hex": pub_hex,
    }
    sig = priv.sign(encode_jcs(payload)).hex()
    valid_warrant = TestModificationWarrant(
        warrant_id="w-002",
        authorized_test_paths=("test_mod.py",),
        justification="Authorized test evolution",
        issuer_public_key_hex=pub_hex,
        signature_hex=sig,
    )
    assert valid_warrant.verify_signature() is True

    ok_auth, msg_auth = TestSuiteHashLock.verify_integrity(tests_dir, baseline, valid_warrant)
    assert ok_auth is True
    assert msg_auth == "OK_TEST_SUITE_INTEGRITY_PRESERVED"


def test_ectc_cryptographic_verification(test_keys):
    priv, pub_hex = test_keys

    cert_data = {
        "task_id": "TASK-2026-001",
        "requirements": ["REQ-01", "REQ-02"],
        "test_suite_digest": "sha256:abc1234",
        "test_run_receipt": {"exit_code": 0, "passed": 12, "failed": 0},
        "artifact_digests": {"src/main.py": "sha256:def5678"},
        "timestamp_epoch_s": 1793080000,
        "nonce": "nonce_xyz",
        "issuer_public_key_hex": pub_hex,
    }
    sig = priv.sign(encode_jcs(cert_data)).hex()

    ectc = EvidenceCarryingTerminationCertificate(
        task_id=cert_data["task_id"],
        requirements=tuple(cert_data["requirements"]),
        test_suite_digest=cert_data["test_suite_digest"],
        test_run_receipt=cert_data["test_run_receipt"],
        artifact_digests=cert_data["artifact_digests"],
        timestamp_epoch_s=cert_data["timestamp_epoch_s"],
        nonce=cert_data["nonce"],
        issuer_public_key_hex=pub_hex,
        signature_hex=sig,
    )

    # 1. Valid certificate verifies
    ok, msg = ectc.verify()
    assert ok is True
    assert msg == "VERIFIED_ECTC_VALID"

    # 2. Tampered signature fails
    ectc_bad_sig = EvidenceCarryingTerminationCertificate(
        task_id=ectc.task_id,
        requirements=ectc.requirements,
        test_suite_digest=ectc.test_suite_digest,
        test_run_receipt=ectc.test_run_receipt,
        artifact_digests=ectc.artifact_digests,
        timestamp_epoch_s=ectc.timestamp_epoch_s,
        nonce=ectc.nonce,
        issuer_public_key_hex=pub_hex,
        signature_hex="ff" * 64,
    )
    ok_sig, msg_sig = ectc_bad_sig.verify()
    assert ok_sig is False
    assert "ERR_INVALID_ECTC_SIGNATURE" in msg_sig

    # 3. Failing test run receipt fails validation
    cert_data_failing = dict(cert_data)
    cert_data_failing["test_run_receipt"] = {"exit_code": 1, "passed": 5, "failed": 2}
    sig_failing = priv.sign(encode_jcs(cert_data_failing)).hex()
    ectc_failing = EvidenceCarryingTerminationCertificate(
        task_id=cert_data_failing["task_id"],
        requirements=tuple(cert_data_failing["requirements"]),
        test_suite_digest=cert_data_failing["test_suite_digest"],
        test_run_receipt=cert_data_failing["test_run_receipt"],
        artifact_digests=cert_data_failing["artifact_digests"],
        timestamp_epoch_s=cert_data_failing["timestamp_epoch_s"],
        nonce=cert_data_failing["nonce"],
        issuer_public_key_hex=pub_hex,
        signature_hex=sig_failing,
    )
    ok_fail, msg_fail = ectc_failing.verify()
    assert ok_fail is False
    assert "ERR_TEST_RECEIPT_NONZERO_EXIT: 1" in msg_fail

    # 4. Zero passed tests fails validation
    cert_data_zero_passed = dict(cert_data)
    cert_data_zero_passed["test_run_receipt"] = {"exit_code": 0, "passed": 0, "failed": 0}
    sig_zero = priv.sign(encode_jcs(cert_data_zero_passed)).hex()
    ectc_zero = EvidenceCarryingTerminationCertificate(
        task_id=cert_data_zero_passed["task_id"],
        requirements=tuple(cert_data_zero_passed["requirements"]),
        test_suite_digest=cert_data_zero_passed["test_suite_digest"],
        test_run_receipt=cert_data_zero_passed["test_run_receipt"],
        artifact_digests=cert_data_zero_passed["artifact_digests"],
        timestamp_epoch_s=cert_data_zero_passed["timestamp_epoch_s"],
        nonce=cert_data_zero_passed["nonce"],
        issuer_public_key_hex=pub_hex,
        signature_hex=sig_zero,
    )
    ok_zero, msg_zero = ectc_zero.verify()
    assert ok_zero is False
    assert msg_zero == "ERR_TEST_RECEIPT_ZERO_TESTS_PASSED"

    # 5. Failed > 0 with exit_code == 0 fails validation
    cert_data_has_failures = dict(cert_data)
    cert_data_has_failures["test_run_receipt"] = {"exit_code": 0, "passed": 10, "failed": 1}
    sig_has_failures = priv.sign(encode_jcs(cert_data_has_failures)).hex()
    ectc_has_failures = EvidenceCarryingTerminationCertificate(
        task_id=cert_data_has_failures["task_id"],
        requirements=tuple(cert_data_has_failures["requirements"]),
        test_suite_digest=cert_data_has_failures["test_suite_digest"],
        test_run_receipt=cert_data_has_failures["test_run_receipt"],
        artifact_digests=cert_data_has_failures["artifact_digests"],
        timestamp_epoch_s=cert_data_has_failures["timestamp_epoch_s"],
        nonce=cert_data_has_failures["nonce"],
        issuer_public_key_hex=pub_hex,
        signature_hex=sig_has_failures,
    )
    ok_has_fail, msg_has_fail = ectc_has_failures.verify()
    assert ok_has_fail is False
    assert msg_has_fail == "ERR_TEST_RECEIPT_FAILURES_DETECTED: 1"

    # 6. Passed == 1 must pass (kills <= 1 mutant)
    cert_data_passed_one = dict(cert_data)
    cert_data_passed_one["test_run_receipt"] = {"exit_code": 0, "passed": 1, "failed": 0}
    sig_passed_one = priv.sign(encode_jcs(cert_data_passed_one)).hex()
    ectc_passed_one = EvidenceCarryingTerminationCertificate(
        task_id=cert_data_passed_one["task_id"],
        requirements=tuple(cert_data_passed_one["requirements"]),
        test_suite_digest=cert_data_passed_one["test_suite_digest"],
        test_run_receipt=cert_data_passed_one["test_run_receipt"],
        artifact_digests=cert_data_passed_one["artifact_digests"],
        timestamp_epoch_s=cert_data_passed_one["timestamp_epoch_s"],
        nonce=cert_data_passed_one["nonce"],
        issuer_public_key_hex=pub_hex,
        signature_hex=sig_passed_one,
    )
    ok_p1, msg_p1 = ectc_passed_one.verify()
    assert ok_p1 is True
    assert msg_p1 == "VERIFIED_ECTC_VALID"

    # 7. Omitted failed key defaults to 0 and passes
    cert_data_no_failed = dict(cert_data)
    cert_data_no_failed["test_run_receipt"] = {"exit_code": 0, "passed": 5}
    sig_no_failed = priv.sign(encode_jcs(cert_data_no_failed)).hex()
    ectc_no_failed = EvidenceCarryingTerminationCertificate(
        task_id=cert_data_no_failed["task_id"],
        requirements=tuple(cert_data_no_failed["requirements"]),
        test_suite_digest=cert_data_no_failed["test_suite_digest"],
        test_run_receipt=cert_data_no_failed["test_run_receipt"],
        artifact_digests=cert_data_no_failed["artifact_digests"],
        timestamp_epoch_s=cert_data_no_failed["timestamp_epoch_s"],
        nonce=cert_data_no_failed["nonce"],
        issuer_public_key_hex=pub_hex,
        signature_hex=sig_no_failed,
    )
    ok_nf, msg_nf = ectc_no_failed.verify()
    assert ok_nf is True
    assert msg_nf == "VERIFIED_ECTC_VALID"


def test_class_test_attributes():
    assert TestModificationWarrant.__test__ is False
    assert TestSuiteHashLock.__test__ is False

    # Verify that EvidenceCarryingTerminationCertificate is frozen
    cert = EvidenceCarryingTerminationCertificate(
        task_id="T1",
        requirements=("R1",),
        test_suite_digest="sha256:00",
        test_run_receipt={"exit_code": 0, "passed": 1, "failed": 0},
        artifact_digests={},
        timestamp_epoch_s=100,
        nonce="n1",
        issuer_public_key_hex="00" * 32,
        signature_hex="00" * 64,
    )
    with pytest.raises(FrozenInstanceError):
        cert.task_id = "T2"  # type: ignore


def test_stopping_as_database_property():
    ledger = TaskStateLedger()

    # 0. Empty ledger halts
    ok0, msg0 = ledger.evaluate_termination_predicate("TASK-100")
    assert ok0 is False
    assert msg0 == "HALT_NO_REQUIREMENTS_REGISTERED"

    # 1. Register incomplete requirements
    ledger.record_requirement("TASK-100", "REQ-1", is_satisfied=False)
    ledger.record_requirement("TASK-100", "REQ-2", is_satisfied=True, ectc_digest="sha256:123")

    ok1, msg1 = ledger.evaluate_termination_predicate("TASK-100")
    assert ok1 is False
    assert msg1 == "HALT_UNSATISFIED_REQUIREMENTS_1_REMAINING"

    # 2. Complete all requirements with valid ECTC digests
    ledger.record_requirement("TASK-100", "REQ-1", is_satisfied=True, ectc_digest="sha256:456")
    ok2, msg2 = ledger.evaluate_termination_predicate("TASK-100")
    assert ok2 is True
    assert msg2 == "TERMINATION_ADMISSIBLE_ALL_REQUIREMENTS_CERTIFIED"

    # 3. Regressing a requirement back to unsatisfied fails closed
    ledger.record_requirement("TASK-100", "REQ-1", is_satisfied=False, ectc_digest="sha256:456")
    ok3, msg3 = ledger.evaluate_termination_predicate("TASK-100")
    assert ok3 is False
    assert msg3 == "HALT_UNSATISFIED_REQUIREMENTS_1_REMAINING"

    # Verify underlying integer encoding in SQLite
    cur = ledger.conn.cursor()
    cur.execute("SELECT is_satisfied FROM task_requirements WHERE requirement_id = 'REQ-1'")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT is_satisfied FROM task_requirements WHERE requirement_id = 'REQ-2'")
    assert cur.fetchone()[0] == 1


def test_semantic_convergence_monitor():
    h = ["hash_1", "hash_2", "hash_3"]

    # Healthy new progress
    ok, msg = SemanticConvergenceMonitor.evaluate_convergence(h, "hash_4")
    assert ok is True
    assert msg == "OK_CONVERGENCE_HEALTHY"

    # Immediate no-op duplicate
    ok_noop, msg_noop = SemanticConvergenceMonitor.evaluate_convergence(h, "hash_3")
    assert ok_noop is False
    assert msg_noop == "HALT_IMMEDIATE_NO_OP_DETECTED"

    # Oscillation cycle (seen twice in history)
    h_cycle = ["hash_a", "hash_b", "hash_a", "hash_c"]
    ok_cyc, msg_cyc = SemanticConvergenceMonitor.evaluate_convergence(h_cycle, "hash_a")
    assert ok_cyc is False
    assert msg_cyc == "HALT_CYCLE_STAGNATION_DETECTED"
