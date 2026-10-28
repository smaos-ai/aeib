#!/usr/bin/env python3
# File: tests/test_wave7_steward_sphinx_and_escalation.py
"""Boundary and behaviour suite for src/wave7_steward_sphinx_and_escalation.py.
Zero-mock: real temp directories, real subprocess pytest runs, real Ed25519 keys."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.wave7_steward_sphinx_and_escalation import (
    BlockerEscalationPacket,
    NonPenalizedBlockerEscalationGate,
    ShadowWorkflowAndIncidentEmitter,
    SphinxCognitiveDebtGate,
    StewardInvariantCoreGuard,
    StewardReflectionProposal,
    compute_tests_manifest_digest,
    sha256_jcs_caid,
)

BUNDLE = "sha256:" + "ab" * 32


def _p(path: str, layer: int = 3, dd: int = 10) -> StewardReflectionProposal:
    return StewardReflectionProposal("p", path, layer, dd, "note")


# ----------------------------------------------------------------- caid helper
def test_sha256_jcs_caid_inputs_and_float_rejection() -> None:
    assert sha256_jcs_caid(b"abc") == sha256_jcs_caid("abc")
    assert sha256_jcs_caid({"b": 2, "a": 1}) == sha256_jcs_caid({"a": 1, "b": 2})
    for bad in ({"f": 1.5}, [1, [2.0]], (0.5,)):
        with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_IN_JCS"):
            sha256_jcs_caid(bad)


# --------------------------------------------------------------------- steward
def test_steward_constructor_bounds() -> None:
    assert StewardInvariantCoreGuard().hard_max_drawdown_cap_bps == 30
    assert StewardInvariantCoreGuard(1).hard_max_drawdown_cap_bps == 1
    assert StewardInvariantCoreGuard(5000).hard_max_drawdown_cap_bps == 5000
    for bad in (0, 5001, True, -1):
        with pytest.raises(ValueError, match="ERR_INVALID_DRAWDOWN_CAP_BPS"):
            StewardInvariantCoreGuard(bad)  # type: ignore[arg-type]


def test_steward_layer_and_drawdown_boundaries() -> None:
    g = StewardInvariantCoreGuard(30)
    for bad_layer in (0, 8, True):
        v = g.evaluate_reflection(_p("docs/notes/a.md", layer=bad_layer))
        assert (v.allowed, v.zone_classification, v.reason_code) == (
            False, "INVALID_LAYER", "HALT_STEWARD_MEMORY_LAYER_OUT_OF_RANGE")
    for layer, dd in ((1, 0), (7, 30)):
        v = g.evaluate_reflection(_p("memory/reflective_layer_1.json", layer, dd))
        assert (v.allowed, v.zone_classification, v.reason_code) == (
            True, "REFLECTIVE_SHELL", "OK_STEWARD_SHELL_EVOLUTION_AUTHORIZED")
        assert v.receipt_caid.startswith("sha256:")
    for bad_dd in (-1, 31, True):
        v = g.evaluate_reflection(_p("docs/notes/a.md", dd=bad_dd))
        assert (v.allowed, v.zone_classification, v.reason_code) == (
            False, "INVARIANT_CORE", "HALT_STEWARD_RISK_CAP_BREACH")


def test_steward_core_prefixes_case_folding_and_unclassified() -> None:
    g = StewardInvariantCoreGuard(30)
    for prefix in StewardInvariantCoreGuard.IMMUTABLE_CORE_PREFIXES:
        v = g.evaluate_reflection(_p(f"{prefix}x"))
        assert v.allowed is False and v.zone_classification == "INVARIANT_CORE"
        assert v.reason_code == f"HALT_INVARIANT_CORE_IMMUTABLE:{prefix}x"
    v_case = g.evaluate_reflection(_p("SRC/JCS_Canonicalizer.py"))
    assert v_case.reason_code == "HALT_INVARIANT_CORE_IMMUTABLE:SRC/JCS_Canonicalizer.py"
    v_unc = g.evaluate_reflection(_p("scripts/deploy.sh"))
    assert (v_unc.allowed, v_unc.zone_classification, v_unc.reason_code) == (
        False, "UNCLASSIFIED_PATH", "HALT_PATH_OUTSIDE_REFLECTIVE_SHELL:scripts/deploy.sh")
    # Shell prefixes are case-sensitive: a case variant is not in the shell.
    assert g.evaluate_reflection(_p("Docs/notes/a.md")).zone_classification == "UNCLASSIFIED_PATH"


def test_steward_path_canonicalization_rejections() -> None:
    g = StewardInvariantCoreGuard(30)
    cases = {
        "docs/notes/../../src/jcs_canonicalizer.py": "HALT_NON_CANONICAL_REFLECTION_PATH",
        "docs/notes/./a.md": "HALT_NON_CANONICAL_REFLECTION_PATH",
        "docs//notes/a.md": "HALT_NON_CANONICAL_REFLECTION_PATH",
        "docs/notes/": "HALT_NON_CANONICAL_REFLECTION_PATH",
        "../outside.py": "HALT_PATH_TRAVERSAL_IN_REFLECTION_TARGET",
        "..": "HALT_PATH_TRAVERSAL_IN_REFLECTION_TARGET",
        "": "HALT_ABSOLUTE_OR_EMPTY_REFLECTION_PATH",
        "/etc/passwd": "HALT_ABSOLUTE_OR_EMPTY_REFLECTION_PATH",
        "docs/notes/a\x00.md": "HALT_ABSOLUTE_OR_EMPTY_REFLECTION_PATH",
        "docs\\notes\\a.md": "HALT_BACKSLASH_PATH_SEPARATOR_FORBIDDEN",
    }
    for path, code in cases.items():
        v = g.evaluate_reflection(_p(path))
        assert (v.allowed, v.zone_classification, v.reason_code) == (False, "INVARIANT_CORE", code), path
    v_none = g.evaluate_reflection(_p(None))  # type: ignore[arg-type]
    assert v_none.reason_code == "HALT_ABSOLUTE_OR_EMPTY_REFLECTION_PATH"


def test_steward_symlink_redirect_out_of_shell_is_blocked(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "jcs_canonicalizer.py").write_text("# core\n")
    (tmp_path / "docs" / "notes").mkdir(parents=True)
    os.symlink(tmp_path / "src", tmp_path / "docs" / "notes" / "link")
    g = StewardInvariantCoreGuard(30, repo_root=str(tmp_path))
    v = g.evaluate_reflection(_p("docs/notes/link/jcs_canonicalizer.py"))
    assert (v.allowed, v.reason_code) == (False, "HALT_SYMLINK_REDIRECT_IN_REFLECTION_TARGET")
    assert g.evaluate_reflection(_p("docs/notes/real.md")).allowed is True
    # Without repo_root the lexical policy alone cannot see the symlink (documented residual).
    assert StewardInvariantCoreGuard(30).evaluate_reflection(
        _p("docs/notes/link/jcs_canonicalizer.py")).allowed is True


# ------------------------------------------------------------------ escalation
FAILING = "def test_fails():\n    assert -5 >= 0\n"
PASSING = "def test_passes():\n    assert 1 == 1\n"
SLOW = "import time\n\ndef test_slow():\n    time.sleep(10)\n"


def _project(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(FAILING + "\n\n" + PASSING + "\n\n" + SLOW)
    return tmp_path


def _packet(**over: str) -> BlockerEscalationPacket:
    base = dict(
        task_id="t1", spec_caid="sha256:spec", failing_test_id="tests/test_x.py::test_fails",
        contradiction_kind="CONTRADICTORY_SPEC", minimal_reproducer_code="assert -5 >= 0\n",
        observed_assertion_error="AssertionError: -5 >= 0",
    )
    base.update(over)
    return BlockerEscalationPacket(**base)


def test_escalation_constructor_validation(tmp_path: Path) -> None:
    for bad in ("", "sha256:xyz", "md5:" + "a" * 64):
        with pytest.raises(ValueError, match="ERR_INVALID_BASELINE_MANIFEST_DIGEST"):
            NonPenalizedBlockerEscalationGate(str(tmp_path), bad)
    for bad_t in (0, -1, True):
        with pytest.raises(ValueError, match="ERR_INVALID_TEST_TIMEOUT"):
            NonPenalizedBlockerEscalationGate(str(tmp_path), BUNDLE, bad_t)  # type: ignore[arg-type]
    assert NonPenalizedBlockerEscalationGate(str(tmp_path), BUNDLE).test_timeout_s == 60


def test_escalation_accepts_real_failing_test_and_rejects_others(tmp_path: Path) -> None:
    root = _project(tmp_path)
    baseline = compute_tests_manifest_digest(str(root / "tests"))
    gate = NonPenalizedBlockerEscalationGate(str(root), baseline, test_timeout_s=30)

    for kind in sorted(NonPenalizedBlockerEscalationGate.VALID_KINDS):
        ok = gate.evaluate_escalation(_packet(contradiction_kind=kind))
        assert (ok.terminal_disposition, ok.agent_penalized) == ("ESCALATED_CLEANLY_NO_PENALTY", False)

    expected = {
        "HALT_INVALID_CONTRADICTION_KIND": _packet(contradiction_kind="LAZY"),
        "HALT_EMPTY_ASSERTION_EVIDENCE": _packet(observed_assertion_error="  "),
        "HALT_INVALID_REPRODUCER_SYNTAX": _packet(minimal_reproducer_code="def b(:\n"),
        "HALT_EMPTY_REPRODUCER_AST": _packet(minimal_reproducer_code="# c\n"),
        "HALT_REPRODUCER_LACKS_ASSERT_OR_RAISE": _packet(minimal_reproducer_code="x = 1\n"),
        "HALT_INVALID_FAILING_TEST_ID": _packet(failing_test_id="tests/test_x.py::t; rm -rf /"),
        "HALT_NAMED_TEST_DID_NOT_FAIL:exit_0": _packet(failing_test_id="tests/test_x.py::test_passes"),
        "HALT_NAMED_TEST_DID_NOT_FAIL:exit_4": _packet(failing_test_id="tests/test_x.py::test_missing"),
    }
    for code, pkt in expected.items():
        v = gate.evaluate_escalation(pkt)
        assert (v.terminal_disposition, v.agent_penalized) == (code, True), code
        assert v.escalation_receipt_caid.startswith("sha256:")
    raise_ok = gate.evaluate_escalation(_packet(minimal_reproducer_code="raise ValueError('x')\n"))
    assert raise_ok.agent_penalized is False


def test_escalation_timeout_and_test_tamper(tmp_path: Path) -> None:
    root = _project(tmp_path)
    baseline = compute_tests_manifest_digest(str(root / "tests"))
    fast = NonPenalizedBlockerEscalationGate(str(root), baseline, test_timeout_s=2)
    v_to = fast.evaluate_escalation(_packet(failing_test_id="tests/test_x.py::test_slow"))
    assert (v_to.terminal_disposition, v_to.agent_penalized) == ("HALT_FAILING_TEST_TIMEOUT", True)

    (root / "tests" / "test_x.py").write_text(PASSING)  # agent edits the test
    v_t = fast.evaluate_escalation(_packet())
    assert (v_t.terminal_disposition, v_t.agent_penalized) == (
        "HALT_REWARD_HACKING_TEST_TAMPER_DURING_ESCALATION", True)


def test_tests_manifest_digest_detects_changes_and_refuses_symlinks(tmp_path: Path) -> None:
    root = _project(tmp_path)
    d1 = compute_tests_manifest_digest(str(root / "tests"))
    (root / "tests" / "__pycache__").mkdir()
    (root / "tests" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    (root / "tests" / "stale.pyc").write_bytes(b"\x01")
    assert compute_tests_manifest_digest(str(root / "tests")) == d1
    (root / "tests" / "new_test.py").write_text("x = 1\n")
    assert compute_tests_manifest_digest(str(root / "tests")) != d1
    os.symlink(root / "tests" / "new_test.py", root / "tests" / "link.py")
    with pytest.raises(ValueError, match="ERR_SYMLINK_IN_TESTS_MANIFEST"):
        compute_tests_manifest_digest(str(root / "tests"))
    with pytest.raises(ValueError, match="ERR_TESTS_ROOT_NOT_A_DIRECTORY"):
        compute_tests_manifest_digest(str(root / "missing"))
    os.symlink(root / "tests", root / "tests_link")
    with pytest.raises(ValueError, match="ERR_TESTS_ROOT_NOT_A_DIRECTORY"):
        compute_tests_manifest_digest(str(root / "tests_link"))


# ---------------------------------------------------------------------- sphinx
def test_sphinx_extraction_rules() -> None:
    src = (
        "FLAG = True\nZERO = 0\nONE = 1\nNEG = -1\n"
        "def check(val: int) -> str:\n"
        "    if val > 50000 or val < -5 or val == 0:\n"
        "        return 'HALT_WIRE_CAP'\n"
        "    return 'OK_PASS'\n"
        "async def later(turn):\n"
        "    if turn >= 1:\n"
        "        return 'HALT_LATE'\n"
    )
    ch = SphinxCognitiveDebtGate.extract_ast_challenge(src)
    assert ch.expected_function_names == ("check", "later")
    assert ch.expected_halt_codes == ("HALT_LATE", "HALT_WIRE_CAP")
    assert ch.expected_integer_constants == (-5, -1, 0, 1, 50000)
    only_assign = SphinxCognitiveDebtGate.extract_ast_challenge("A = 0\nB = 1\nC = 2\n")
    assert only_assign.expected_integer_constants == (2,)


def test_sphinx_attestation_branches() -> None:
    code = "def f(v):\n    if v > 50000:\n        return 'HALT_CAP'\n    return 'OK'\n"
    ch = SphinxCognitiveDebtGate.extract_ast_challenge(code)
    verify = SphinxCognitiveDebtGate.verify_reviewer_attestation
    assert verify(code, ["g"], ["HALT_CAP"], [50000])[:2] == (False, "HALT_COGNITIVE_DEBT_FUNCTION_MISMATCH")
    assert verify(code, ["f"], ["HALT_X"], [50000])[:2] == (False, "HALT_COGNITIVE_DEBT_HALT_CODE_MISMATCH")
    assert verify(code, ["f"], ["HALT_CAP"], [10000])[:2] == (False, "HALT_COGNITIVE_DEBT_CONSTANT_MISMATCH")
    assert verify(code, ["f", "f"], ["HALT_CAP"], [50000]) == (True, "OK_REVIEWER_ATTESTATION_MATCHES_AST", ch.challenge_caid)


# -------------------------------------------------------------------- incident
def _notice(key: Ed25519PrivateKey, **over):
    args = dict(incident_id="INC-1", severity_tier="SEV_1_CRITICAL",
                halt_reason_code="HALT_T3_SHARED_L3_CACHE_CO_TENANT_FORBIDDEN",
                containment_latency_us=18, evidence_bundle_caid=BUNDLE,
                jurisdictions=["US_X", "EU_MSA_DE", "US_X"])
    args.update(over)
    return ShadowWorkflowAndIncidentEmitter.emit_incident_notice(signing_key=key, **args)


def test_shadow_record() -> None:
    rec = ShadowWorkflowAndIncidentEmitter.record_shadow_exception("wf", "a", "b", "note")
    assert (rec.workflow_id, rec.last_known_sop_node, rec.observed_shadow_action, rec.operator_note) == ("wf", "a", "b", "note")
    assert rec.candidate_caid == sha256_jcs_caid(
        {"last_known_sop_node": "a", "observed_shadow_action": "b", "operator_note": "note", "workflow_id": "wf"})


def test_incident_emit_validation() -> None:
    key = Ed25519PrivateKey.generate()
    n = _notice(key, containment_latency_us=0)
    assert n["jurisdictions_notified"] == ["EU_MSA_DE", "US_X"]
    assert n["action_taken"] == "FAIL_CLOSED_KERNEL_OR_HOOK_VETO"
    assert n["containment_latency_us"] == 0
    bad = [
        dict(severity_tier="SEV_9_FAKE"), dict(containment_latency_us=-1),
        dict(containment_latency_us=True), dict(halt_reason_code="OK_X"),
        dict(halt_reason_code=5), dict(incident_id="  "), dict(incident_id=7),
        dict(evidence_bundle_caid="sha256:short"), dict(evidence_bundle_caid=3),
        dict(jurisdictions=[]), dict(jurisdictions=[""]),
    ]
    for over in bad:
        with pytest.raises(ValueError, match="ERR_INVALID_INCIDENT_NOTICE_FIELDS"):
            _notice(key, **over)


def test_incident_verify_signature_pinning_and_forgery() -> None:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes_raw().hex()
    n = _notice(key)
    verify = ShadowWorkflowAndIncidentEmitter.verify_incident_notice
    assert verify(n, pub) is True

    # Modify a field that still satisfies all invariants and recompute the CAID:
    # an unkeyed hash check would accept this; the signature check must not.
    forged = dict(n)
    forged["containment_latency_us"] = 5
    body = {k: forged[k] for k in ShadowWorkflowAndIncidentEmitter._SIGNED_FIELDS}
    forged["notification_caid"] = sha256_jcs_caid(body)
    assert verify(forged, pub) is False

    attacker = Ed25519PrivateKey.generate()
    assert verify(_notice(attacker), pub) is False          # unpinned issuer
    assert verify(n, attacker.public_key().public_bytes_raw().hex()) is False

    stale_caid = dict(n)
    stale_caid["notification_caid"] = "sha256:" + "00" * 32
    assert verify(stale_caid, pub) is False
    extra = dict(n)
    extra["note"] = "x"
    assert verify(extra, pub) is False
    missing = dict(n)
    del missing["signature_hex"]
    assert verify(missing, pub) is False
    bad_sig = dict(n)
    bad_sig["signature_hex"] = "zz"
    assert verify(bad_sig, pub) is False
    for field, value in (("severity_tier", "SEV_9"), ("action_taken", "ALLOW"),
                         ("jurisdictions_notified", ["US_X", "EU_MSA_DE"]),
                         ("jurisdictions_notified", [1]), ("containment_latency_us", -2)):
        tampered = dict(n)
        tampered[field] = value
        assert verify(tampered, pub) is False, field


def test_escalation_verdict_is_frozen_and_child_output_is_not_leaked(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    import dataclasses

    root = _project(tmp_path)
    gate = NonPenalizedBlockerEscalationGate(
        str(root), compute_tests_manifest_digest(str(root / "tests")), test_timeout_s=30)
    capfd.readouterr()
    v = gate.evaluate_escalation(_packet())
    out, err = capfd.readouterr()
    # The untrusted child pytest run must not write into the harness's own stdout/stderr.
    assert "test_fails" not in out and "failed" not in out and "failed" not in err
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.agent_penalized = False  # type: ignore[misc]
