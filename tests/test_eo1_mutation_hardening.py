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
tests/test_eo1_mutation_hardening.py
================================================================================
Behavioural tests targeting mutation survivors observed by
tools/mutation_adequacy_gate.py on src/eo1_write_before_execute.py (seed 42).

Real files, real Ed25519 keys, real filesystem conditions; no mocks or monkeypatching.
Each test asserts a specific observable outcome (return value, typed halt reason,
on-disk marker contents, emitted warning) under the stated model.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import logging
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import src.eo1_write_before_execute as eo1
from src.jcs_canonicalizer import encode_jcs
from src.eo1_write_before_execute import (
    DISPOSITION_COMMITTED,
    GENESIS_CHAIN_TIP,
    INTEGRITY_HWM_MALFORMED,
    LedgerIntegrityViolationError,
    OperationApprovalGrant,
    PreDispatchIntentInterlock,
    classify_reconciliation_outcome,
    verify_ledger_file,
)

URI = "http://plc.local/coil/7"
TOOL = "modbus_write"


def _pem(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _seed_ledger(tmp_path: Path, key: Ed25519PrivateKey, payload=None):
    ledger = tmp_path / "ledger.jsonl"
    il = PreDispatchIntentInterlock(ledger, key, output_state_dir=tmp_path / "state")
    rec = il.record_intent(URI, TOOL, payload if payload is not None else {"coil": 7, "value": 1})
    return ledger, il, rec


def _write_signed_hwm(hwm_path: Path, key: Ed25519PrivateKey, statement: dict) -> None:
    sig = base64.b64encode(key.sign(encode_jcs(statement))).decode("ascii")
    doc = dict(statement)
    doc["signature_b64"] = sig
    hwm_path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# Pure helpers: return-value contracts
# ---------------------------------------------------------------------------

def test_classify_non_dict_evidence_is_committed():
    assert classify_reconciliation_outcome("NOT_COMMITTED") == DISPOSITION_COMMITTED
    assert classify_reconciliation_outcome(None) == DISPOSITION_COMMITTED
    assert classify_reconciliation_outcome(["NOT_FOUND"]) == DISPOSITION_COMMITTED


def test_verify_ledger_file_missing_returns_empty_list(tmp_path):
    key = Ed25519PrivateKey.generate()
    result = verify_ledger_file(tmp_path / "absent.jsonl", key.public_key())
    assert result == []
    assert isinstance(result, list)


def test_record_verifies_returns_strict_bool(tmp_path):
    key = Ed25519PrivateKey.generate()
    other = Ed25519PrivateKey.generate()
    _, _, rec = _seed_ledger(tmp_path, key)
    rec_dict = rec.to_dict()
    assert eo1._record_verifies(rec_dict, [key.public_key()]) is True
    assert eo1._record_verifies(rec_dict, [other.public_key()]) is False
    assert eo1._record_verifies(rec_dict, []) is False
    assert eo1._record_verifies({"record_type": "OTHER"}, [key.public_key()]) is False


def test_dataclasses_are_frozen(tmp_path):
    grant = OperationApprovalGrant("a1", "actor", TOOL, "c" * 64)
    with pytest.raises(dataclasses.FrozenInstanceError):
        grant.tool_name = "other"  # type: ignore[misc]
    _, _, rec = _seed_ledger(tmp_path, Ed25519PrivateKey.generate())
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.caid = "0" * 64  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Atomic write: os.replace failure propagates (real filesystem condition)
# ---------------------------------------------------------------------------

def test_atomic_write_replace_failure_propagates_and_cleans_tmp(tmp_path):
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "child").write_text("x", encoding="utf-8")  # non-empty dir: os.replace must fail
    with pytest.raises(OSError):
        eo1._atomic_write_text(target, "payload")
    assert target.is_dir()
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


# ---------------------------------------------------------------------------
# HWM authentication: typed malformed halts
# ---------------------------------------------------------------------------

def test_hwm_wrong_typed_string_field_halts_malformed(tmp_path):
    key = Ed25519PrivateKey.generate()
    ledger, il, _ = _seed_ledger(tmp_path, key)
    doc = json.loads(il.hwm_path.read_text(encoding="utf-8"))
    doc["chain_tip"] = 12345
    il.hwm_path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        PreDispatchIntentInterlock(ledger, key, output_state_dir=tmp_path / "state")
    assert exc.value.reason == INTEGRITY_HWM_MALFORMED


def test_hwm_signature_with_non_base64_chars_halts_malformed(tmp_path):
    key = Ed25519PrivateKey.generate()
    ledger, il, _ = _seed_ledger(tmp_path, key)
    doc = json.loads(il.hwm_path.read_text(encoding="utf-8"))
    sig = doc["signature_b64"]
    doc["signature_b64"] = sig[:8] + "*" + sig[8:]
    il.hwm_path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        PreDispatchIntentInterlock(ledger, key, output_state_dir=tmp_path / "state")
    assert exc.value.reason == INTEGRITY_HWM_MALFORMED


def test_hwm_unknown_signer_warns_in_non_strict_mode(tmp_path, caplog):
    key = Ed25519PrivateKey.generate()
    ledger, _, _ = _seed_ledger(tmp_path, key)
    with caplog.at_level(logging.WARNING):
        il = PreDispatchIntentInterlock(ledger, None, output_state_dir=tmp_path / "state")
    assert il.ledger_integrity_strict is False
    assert any("signed by an unknown key" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# HWM boundary: ledger longer than a genesis HWM (crash between append and HWM rewrite)
# ---------------------------------------------------------------------------

def test_genesis_hwm_with_appended_record_is_accepted_and_latched(tmp_path):
    key = Ed25519PrivateKey.generate()
    ledger, il, rec = _seed_ledger(tmp_path, key)
    _write_signed_hwm(il.hwm_path, key, {
        "chain_tip": GENESIS_CHAIN_TIP,
        "ledger_bytes": 0,
        "ledger_name": ledger.name,
        "ledger_prefix_sha256": hashlib.sha256(b"").hexdigest(),
        "record_count": 0,
        "schema_version": eo1._HWM_SCHEMA_VERSION,
        "seq": 1,
        "signer_public_key_pem": _pem(key),
    })
    restarted = PreDispatchIntentInterlock(ledger, key, output_state_dir=tmp_path / "state")
    assert restarted.is_caid_latched(rec.caid)
    assert restarted.get_unresolved_intent_ids(rec.caid) == [rec.intent_id]


# ---------------------------------------------------------------------------
# Latch state flags
# ---------------------------------------------------------------------------

def test_startup_recovery_state_requires_reconciliation(tmp_path):
    key = Ed25519PrivateKey.generate()
    ledger, _, rec = _seed_ledger(tmp_path, key)
    restarted = PreDispatchIntentInterlock(ledger, key, output_state_dir=tmp_path / "state")
    state = restarted.get_latched_caids()[rec.caid]
    assert state.reconciliation_required is True
    assert state.retry_safe is False


def test_manual_latch_marker_and_reload_flags(tmp_path):
    key = Ed25519PrivateKey.generate()
    ledger = tmp_path / "ledger.jsonl"
    state_dir = tmp_path / "state"
    il = PreDispatchIntentInterlock(ledger, key, output_state_dir=state_dir)
    caid = "ab" * 32
    il.latch_intent(caid, reason="OPERATOR")
    marker = json.loads((state_dir / f"latched_{caid}.json").read_text(encoding="utf-8"))
    assert marker["reconciliation_required"] is True
    assert marker["retry_safe"] is False
    reloaded = PreDispatchIntentInterlock(ledger, key, output_state_dir=state_dir, auto_recover=False)
    state = reloaded.get_latched_caids()[caid]
    assert state.retry_safe is False
    assert state.reconciliation_required is True
