#!/usr/bin/env python3
"""
Unit and regression test suite for AutonomousPRWebhookDispatcher.
Evaluated under the stated model with zero mocks, real HMAC, and real Ed25519 signatures.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import re
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.autonomous_pr_webhook_dispatcher import (
    AutonomousPRDispatchReceipt,
    AutonomousPRMergeWarrant,
    AutonomousPRWebhookDispatcher,
)
from src.hypergraph_blast_radius import HypergraphBlastRadiusGovernor
from src.jcs_canonicalizer import encode_jcs


def _sample_repo_sources() -> Dict[str, str]:
    return {
        "src/leaf_module.py": "def helper(): return 1\n",
        "src/mid_module.py": "import src.leaf_module\ndef mid(): return src.leaf_module.helper()\n",
        "src/core_engine.py": "import src.mid_module\ndef run(): return src.mid_module.mid()\n",
        "src/another_dep.py": "import src.mid_module\ndef run2(): return src.mid_module.mid()\n",
    }


def test_1_webhook_hmac_signature_verification() -> None:
    dispatcher = AutonomousPRWebhookDispatcher(webhook_secret="super-secret-token")
    payload = {"action": "opened", "pull_request": {"number": 101, "title": "Test PR"}}
    raw_bytes = encode_jcs(payload)

    computed_sig = "sha256=" + hmac.new(b"super-secret-token", raw_bytes, hashlib.sha256).hexdigest()
    assert dispatcher.verify_webhook_signature(raw_bytes, computed_sig) is True

    # Bad secret
    wrong_sig = "sha256=" + hmac.new(b"wrong-token", raw_bytes, hashlib.sha256).hexdigest()
    assert dispatcher.verify_webhook_signature(raw_bytes, wrong_sig) is False

    # Malformed header
    assert dispatcher.verify_webhook_signature(raw_bytes, "invalid-header") is False


def test_2_low_blast_radius_auto_merge_dispatch() -> None:
    # Set up governor with known repo sources
    sources = _sample_repo_sources()
    gov = HypergraphBlastRadiusGovernor(repo_sources=sources, max_auto_merge_radius_bps=3000)
    dispatcher = AutonomousPRWebhookDispatcher(governor=gov, webhook_secret="secret")

    # Change to a leaf or non-imported file (core_engine is top-level, has 0 dependents)
    event_payload = {
        "action": "opened",
        "pull_request": {
            "number": 102,
            "title": "fix: update core docstring",
            "body": "CAID: sha256:" + "a" * 64,
            "files": [{"filename": "src/core_engine.py"}],
            "additions": 10,
            "deletions": 5,
        },
    }
    raw_bytes = encode_jcs(event_payload)
    sig_header = "sha256=" + hmac.new(b"secret", raw_bytes, hashlib.sha256).hexdigest()

    receipt = dispatcher.dispatch_pr_event(event_payload, signature_header=sig_header)

    assert receipt.admissible is True
    assert receipt.verdict_action == "AUTO_MERGE"
    assert receipt.warrant is not None
    assert receipt.warrant.pr_id == "PR-102"
    assert receipt.warrant.blast_radius_bps <= 3000

    # Verify warrant
    valid, reason = dispatcher.verify_merge_warrant(receipt.warrant)
    assert valid is True
    assert reason == "OK"


def test_3_high_fan_in_human_escalation() -> None:
    sources = _sample_repo_sources()
    gov = HypergraphBlastRadiusGovernor(repo_sources=sources, max_auto_merge_radius_bps=1000)
    dispatcher = AutonomousPRWebhookDispatcher(governor=gov)

    # leaf_module is depended on by mid_module, core_engine, another_dep (3/4 = 7500 bps blast radius!)
    event_payload = {
        "action": "synchronize",
        "pull_request": {
            "number": 103,
            "title": "refactor: change leaf API",
            "body": "Refactoring helper signature.",
            "files": [{"filename": "src/leaf_module.py"}],
            "additions": 15,
            "deletions": 10,
        },
    }

    receipt = dispatcher.dispatch_pr_event(event_payload)

    assert receipt.admissible is False
    assert receipt.verdict_action == "HUMAN_ESCALATE"
    assert receipt.blast_radius_bps > 1000
    assert receipt.warrant is None


def test_4_line_count_exceeded_scope_creep_halt() -> None:
    gov = HypergraphBlastRadiusGovernor(repo_sources=_sample_repo_sources(), max_lines_changed=50)
    dispatcher = AutonomousPRWebhookDispatcher(governor=gov)

    event_payload = {
        "action": "opened",
        "pull_request": {
            "number": 104,
            "title": "massive refactor",
            "body": "Modifying too many lines.",
            "files": [{"filename": "src/core_engine.py"}],
            "additions": 400,
            "deletions": 200,
        },
    }

    receipt = dispatcher.dispatch_pr_event(event_payload)
    assert receipt.admissible is False
    assert receipt.verdict_action == "HALT_SCOPE_CREEP"
    assert receipt.warrant is None


def test_5_tampered_warrant_and_boundary_checks() -> None:
    gov = HypergraphBlastRadiusGovernor(repo_sources=_sample_repo_sources(), max_auto_merge_radius_bps=3000)
    dispatcher = AutonomousPRWebhookDispatcher(governor=gov)

    event_payload = {
        "action": "opened",
        "pull_request": {
            "number": 105,
            "title": "minor tweak",
            "files": [{"filename": "src/core_engine.py"}],
            "additions": 2,
            "deletions": 1,
        },
    }
    receipt = dispatcher.dispatch_pr_event(event_payload)
    warrant = receipt.warrant
    assert warrant is not None

    # 1. Non-integer blast radius
    bad_warrant_bool = dataclasses.replace(warrant, blast_radius_bps=False)  # type: ignore
    valid, err = dispatcher.verify_merge_warrant(bad_warrant_bool)
    assert valid is False
    assert err == "ERR_NON_INTEGER_BLAST_RADIUS"

    # 2. Exceeds auto merge threshold
    bad_warrant_exceeds = dataclasses.replace(warrant, blast_radius_bps=5000)
    valid, err = dispatcher.verify_merge_warrant(bad_warrant_exceeds)
    assert valid is False
    assert err == "ERR_BLAST_RADIUS_EXCEEDS_AUTO_MERGE_THRESHOLD"

    # 3. Invalid warrant action
    bad_warrant_action = dataclasses.replace(warrant, action="HUMAN_ESCALATE")
    valid, err = dispatcher.verify_merge_warrant(bad_warrant_action)
    assert valid is False
    assert err == "ERR_INVALID_WARRANT_ACTION"

    # 4. Forged warrant caid
    bad_warrant_caid = dataclasses.replace(warrant, warrant_caid="sha256:" + "0" * 64)
    valid, err = dispatcher.verify_merge_warrant(bad_warrant_caid)
    assert valid is False
    assert err == "ERR_WARRANT_CAID_MISMATCH"


def test_6_forged_key_signature_rejection() -> None:
    dispatcher = AutonomousPRWebhookDispatcher()
    event_payload = {
        "action": "opened",
        "pull_request": {
            "number": 106,
            "title": "small change",
            "files": [{"filename": "src/core_engine.py"}],
            "additions": 1,
            "deletions": 1,
        },
    }
    receipt = dispatcher.dispatch_pr_event(event_payload)
    warrant = receipt.warrant
    assert warrant is not None

    # Corrupt signature
    corrupted_sig = "ff" * 64
    forged_warrant = dataclasses.replace(warrant, signature_hex=corrupted_sig)
    valid, err = dispatcher.verify_merge_warrant(forged_warrant)
    assert valid is False
    assert "ERR_CRYPTOGRAPHIC_VERIFICATION_FAILED" in err


def test_7_receipt_serialization_and_immutability() -> None:
    dispatcher = AutonomousPRWebhookDispatcher()
    event_payload = {
        "action": "opened",
        "pull_request": {
            "number": 107,
            "title": "tweak",
            "files": [{"filename": "src/core_engine.py"}],
            "additions": 1,
            "deletions": 1,
        },
    }
    receipt = dispatcher.dispatch_pr_event(event_payload)
    r_dict = receipt.to_dict()
    assert "receipt_caid" in r_dict
    assert "warrant" in r_dict
    assert r_dict["pr_id"] == "PR-107"

    # Immutability check
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.admissible = False  # type: ignore


def test_9_comprehensive_edge_cases_and_intent_caid_parsing() -> None:
    dispatcher = AutonomousPRWebhookDispatcher(webhook_secret="sec")

    # 1. Missing pull_request object raises ValueError
    with pytest.raises(ValueError, match="ERR_MISSING_PULL_REQUEST_OBJECT"):
        dispatcher.extract_pr_spec({"action": "opened"})

    # 2. Empty signature header returns False
    assert dispatcher.verify_webhook_signature(b"{}", "") is False

    # 3. Intent-CAID header extraction in PR body
    exact_71_caid = "sha256:" + "b" * 64
    payload_intent_caid = {
        "action": "opened",
        "pull_request": {
            "number": 201,
            "title": "intent test",
            "body": f"Some text\nIntent-CAID: {exact_71_caid}\nMore text",
            "files": ["src/core_engine.py"],
            "additions": 5,
            "deletions": 2,
        },
    }
    _, spec = dispatcher.extract_pr_spec(payload_intent_caid)
    assert spec.intent_caid == exact_71_caid

    # 4. Short CAID (e.g. 70 chars) falls back to synthetic digest
    short_caid = "sha256:" + "b" * 63
    payload_short = {
        "action": "opened",
        "pull_request": {
            "number": 202,
            "title": "fallback title",
            "body": f"Intent-CAID: {short_caid}",
            "files": ["src/core_engine.py"],
        },
    }
    _, spec_short = dispatcher.extract_pr_spec(payload_short)
    assert spec_short.intent_caid != short_caid
    assert spec_short.intent_caid.startswith("sha256:")

    # 5. warrant.to_dict() and frozen immutability
    receipt = dispatcher.dispatch_pr_event({
        "action": "opened",
        "pull_request": {
            "number": 203,
            "title": "auto",
            "files": [{"filename": "src/core_engine.py"}],
            "additions": 1,
            "deletions": 1,
        },
    })
    assert receipt.warrant is not None
    w_dict = receipt.warrant.to_dict()
    assert w_dict["pr_id"] == "PR-203"
    assert "warrant_caid" in w_dict
    assert "signature_hex" in w_dict

    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.warrant.action = "HALT"  # type: ignore


def test_8_epistemic_purity_no_banned_words() -> None:
    banned_terms = [
        r"\bguarant[e]e\b",
        r"\bguarant[e]ed\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100% [s]ecure\b",
    ]
    files_to_scan = [
        Path("src/autonomous_pr_webhook_dispatcher.py"),
        Path("tests/test_autonomous_pr_webhook_dispatcher.py"),
    ]

    for fpath in files_to_scan:
        content = fpath.read_text(encoding="utf-8")
        for pat in banned_terms:
            matches = re.findall(pat, content, re.IGNORECASE)
            assert not matches, f"Banned pattern '{pat}' found in {fpath}: {matches}"
