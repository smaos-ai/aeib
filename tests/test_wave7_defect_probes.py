#!/usr/bin/env python3
# File: tests/test_wave7_defect_probes.py
"""Red-team probes for defects found in the pasted Wave 7 drafts.
F1 traversal, F4 compare-0/1, F5 no-op reproducer (fixed in pasted round 2);
F6 modify-and-rehash forgery, F7 bool-as-int, F8 symlink redirect (fixed here)."""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.wave7_steward_sphinx_and_escalation import (
    ShadowWorkflowAndIncidentEmitter,
    SphinxCognitiveDebtGate,
    StewardInvariantCoreGuard,
    StewardReflectionProposal,
    sha256_jcs_caid,
)


def test_probe_F1_traversal_through_shell_prefix() -> None:
    v = StewardInvariantCoreGuard(30).evaluate_reflection(
        StewardReflectionProposal("p", "docs/notes/../../src/jcs_canonicalizer.py", 3, 20, "x"))
    assert v.allowed is False


def test_probe_F4_compare_boundary_one_is_challenged() -> None:
    ch = SphinxCognitiveDebtGate.extract_ast_challenge(
        "def g(t):\n    if t >= 1:\n        return 'HALT_LATE'\n")
    assert 1 in ch.expected_integer_constants


def test_probe_F6_valid_looking_rehashed_notice_rejected() -> None:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes_raw().hex()
    n = ShadowWorkflowAndIncidentEmitter.emit_incident_notice(
        "INC-9", "SEV_2_HIGH", "HALT_X", 40, "sha256:" + "cd" * 32, ["EU_MSA_FR"], key)
    forged = dict(n)
    forged["halt_reason_code"] = "HALT_SOMETHING_ELSE"
    forged["severity_tier"] = "SEV_3_MEDIUM"
    body = {k: forged[k] for k in ShadowWorkflowAndIncidentEmitter._SIGNED_FIELDS}
    forged["notification_caid"] = sha256_jcs_caid(body)
    assert ShadowWorkflowAndIncidentEmitter.verify_incident_notice(forged, pub) is False


def test_probe_F7_bool_is_not_an_int_layer_or_drawdown() -> None:
    g = StewardInvariantCoreGuard(30)
    assert g.evaluate_reflection(
        StewardReflectionProposal("p", "docs/notes/a.md", True, 10, "x")).allowed is False
    assert g.evaluate_reflection(
        StewardReflectionProposal("p", "docs/notes/a.md", 3, True, "x")).allowed is False


def test_probe_F8_symlink_in_shell_pointing_at_core(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs" / "notes").mkdir(parents=True)
    os.symlink(tmp_path / "src", tmp_path / "docs" / "notes" / "s")
    v = StewardInvariantCoreGuard(30, repo_root=str(tmp_path)).evaluate_reflection(
        StewardReflectionProposal("p", "docs/notes/s/jcs_canonicalizer.py", 3, 10, "x"))
    assert v.allowed is False
