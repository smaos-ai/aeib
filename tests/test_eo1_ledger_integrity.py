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
tests/test_eo1_ledger_integrity.py
================================================================================
EO-1 ledger integrity under on-disk tampering (real files, real Ed25519 keys,
local dispatch_fn side-effect counters; no mocks).

Evaluated under the stated model:
  - forged / edited receipts never unlock a CAID (HALT_LEDGER_INTEGRITY_VIOLATION),
  - rollback below the signed high-water mark halts the interlock,
  - symlinked ledger / HWM / state paths are refused (O_NOFOLLOW + lstat checks),
  - a clean restart with the same key has no false positive,
  - the documented limitation: a consistent rollback of BOTH ledger and HWM is only
    detected when an externally anchored HWM sequence is supplied (min_hwm_seq).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import src.eo1_write_before_execute as eo1
from src.eo1_write_before_execute import (
    HALT_LEDGER_INTEGRITY_VIOLATION,
    INTEGRITY_HWM_MISSING,
    INTEGRITY_HWM_SEQ_REGRESSED,
    INTEGRITY_HWM_SIGNATURE_INVALID,
    INTEGRITY_HWM_SIGNER_UNTRUSTED,
    INTEGRITY_LEDGER_DIVERGES,
    INTEGRITY_LEDGER_MISSING,
    INTEGRITY_LEDGER_TRUNCATED,
    INTEGRITY_UNTRUSTED_RECEIPT,
    CaidAlreadyCommittedError,
    LatchedCaidExecutionHaltedError,
    LedgerIntegrityViolationError,
    LedgerPathSecurityError,
    PreDispatchIntentInterlock,
    compute_caid,
    recover_unresolved_intents,
)

URI = "local://effect"
TOOL = "settle"
PAY: Dict[str, Any] = {"op": "transfer", "amount_minor": 100, "to": "acct-1"}


class _Target:
    """Counts real side effects (one appended line per effect) in a local file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def ok(self) -> Dict[str, Any]:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("effect\n")
        return {"ok": 1}

    def fail(self) -> Dict[str, Any]:
        self.ok()  # the target commits, then the transport drops (ambiguous outcome)
        raise ConnectionResetError("wire cut after target commit")

    def count(self) -> int:
        if not self.path.exists():
            return 0
        return len(self.path.read_text(encoding="utf-8").splitlines())


@pytest.fixture()
def env(tmp_path: Path):
    key = Ed25519PrivateKey.generate()
    ledger = tmp_path / "ledger.jsonl"
    state = tmp_path / "state"
    target = _Target(tmp_path / "target.log")

    def make(**kw: Any) -> PreDispatchIntentInterlock:
        kw.setdefault("boundary_private_key", key)
        return PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, **kw)

    return {"key": key, "ledger": ledger, "state": state, "target": target, "make": make, "tmp": tmp_path}


def _latch_once(env: Dict[str, Any]) -> None:
    with pytest.raises(RuntimeError):
        env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].fail)


def _lines(ledger: Path) -> List[str]:
    return ledger.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# 1. Forged / edited receipts
# ---------------------------------------------------------------------------

def test_forged_unsigned_not_committed_receipt_with_deleted_latch_stays_blocked(env) -> None:
    _latch_once(env)
    assert env["target"].count() == 1
    for f in env["state"].glob("latched_*.json"):
        f.unlink()
    intent = json.loads(_lines(env["ledger"])[0])
    forged = {
        "record_type": "CONTINUITY_RECEIPT",
        "caid": intent["caid"],
        "intent_id": intent["intent_id"],
        "reconciliation_details": {eo1.DISPOSITION_KEY: eo1.DISPOSITION_NOT_COMMITTED},
    }
    with open(env["ledger"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(forged) + "\n")

    il = env["make"]()
    caid = compute_caid(PAY)
    assert il.get_integrity_violations() == {caid: INTEGRITY_UNTRUSTED_RECEIPT}
    # Startup recovery re-latched the intent: the forged receipt resolved nothing.
    assert il.is_caid_latched(caid)
    assert il.get_unresolved_intent_ids(caid) == [intent["intent_id"]]
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    assert exc.value.disposition == HALT_LEDGER_INTEGRITY_VIOLATION
    assert exc.value.reason == INTEGRITY_UNTRUSTED_RECEIPT
    assert exc.value.caid == caid
    assert isinstance(exc.value, LatchedCaidExecutionHaltedError)
    assert env["target"].count() == 1


def test_edited_receipt_signature_blocks_with_integrity_error(env) -> None:
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    lines = _lines(env["ledger"])
    rec = json.loads(lines[-1])
    sig = bytearray(base64.b64decode(rec["boundary_signature_b64"]))
    sig[0] ^= 0x01
    rec["boundary_signature_b64"] = base64.b64encode(bytes(sig)).decode("ascii")
    lines[-1] = json.dumps(rec)
    # Same byte length keeps the HWM length check satisfied; the prefix digest still differs.
    env["ledger"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"]()
    assert exc.value.reason == INTEGRITY_LEDGER_DIVERGES
    assert env["target"].count() == 1


def test_edited_receipt_disposition_without_hwm_still_blocked_per_caid(env) -> None:
    """Even if the HWM is also removed (ephemeral-key reader), an edited receipt never unlocks."""
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    lines = _lines(env["ledger"])
    rec = json.loads(lines[-1])
    rec["reconciliation_details"][eo1.DISPOSITION_KEY] = eo1.DISPOSITION_NOT_COMMITTED
    lines[-1] = json.dumps(rec)
    env["ledger"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    (env["ledger"].with_name("ledger.jsonl.hwm")).unlink()

    # Ephemeral key: cannot authenticate history; HWM absence is tolerated but receipts stay untrusted.
    il = PreDispatchIntentInterlock(ledger_path=env["ledger"], output_state_dir=env["state"])
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    assert exc.value.reason == INTEGRITY_UNTRUSTED_RECEIPT

    # Stable key with HWM deleted: strict mode halts the whole interlock.
    with pytest.raises(LedgerIntegrityViolationError) as exc2:
        env["make"]()
    assert exc2.value.reason == INTEGRITY_HWM_MISSING
    assert env["target"].count() == 1


def test_trusted_reconcile_supersedes_untrusted_receipt(env) -> None:
    """Operator recovery path: a later receipt signed by the trusted key clears the taint."""
    _latch_once(env)
    other = Ed25519PrivateKey.generate()
    intent = json.loads(_lines(env["ledger"])[0])
    forged = {
        "record_type": "CONTINUITY_RECEIPT", "caid": intent["caid"], "intent_id": intent["intent_id"],
        "schema_version": "1.1.0-eo1-receipt", "status": "RECONCILED", "lifecycle_state": "RECONCILED",
        "retry_safe": False, "policy_epoch": 1, "reconciled_at": "2026-01-01T00:00:00Z",
        "chain_tip": eo1.GENESIS_CHAIN_TIP,
        "reconciliation_details": {eo1.DISPOSITION_KEY: eo1.DISPOSITION_NOT_COMMITTED},
    }
    forged["boundary_signature_b64"] = base64.b64encode(
        other.sign(eo1.encode_jcs({k: forged[k] for k in sorted(forged)}))
    ).decode("ascii")
    with open(env["ledger"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(forged) + "\n")
    il = env["make"]()
    caid = compute_caid(PAY)
    assert caid in il.get_integrity_violations()
    il.reconcile_out_of_band(caid, {"status": "NOT_FOUND"}, target_outcome="NOT_COMMITTED")
    assert il.get_integrity_violations() == {}
    il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    assert env["target"].count() == 2
    with pytest.raises(CaidAlreadyCommittedError):
        env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    assert env["target"].count() == 2


def test_trusted_public_keys_accept_rotated_signer(env) -> None:
    old_key = env["key"]
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    new_key = Ed25519PrivateKey.generate()
    il = env["make"](boundary_private_key=new_key, trusted_public_keys=[old_key.public_key()])
    assert il.get_integrity_violations() == {}
    with pytest.raises(CaidAlreadyCommittedError):
        il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    # Without the old key in the trust set, the old HWM signer is untrusted -> halt.
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"](boundary_private_key=Ed25519PrivateKey.generate())
    assert exc.value.reason == INTEGRITY_HWM_SIGNER_UNTRUSTED
    assert env["target"].count() == 1


def test_recover_unresolved_intents_with_key_ignores_forged_receipt(env) -> None:
    _latch_once(env)
    intent = json.loads(_lines(env["ledger"])[0])
    with open(env["ledger"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"record_type": "CONTINUITY_RECEIPT", "caid": intent["caid"],
                             "intent_id": intent["intent_id"]}) + "\n")
    out = env["tmp"] / "recovered_state"
    rec = recover_unresolved_intents(env["ledger"], out, public_key=env["key"].public_key())
    assert [r.intent_id for r in rec] == [intent["intent_id"]]
    # Legacy unauthenticated mode (no key) is unchanged: the receipt resolves the intent.
    assert recover_unresolved_intents(env["ledger"], env["tmp"] / "legacy_state") == []


# ---------------------------------------------------------------------------
# 2. Rollback against the signed high-water mark
# ---------------------------------------------------------------------------

def test_truncated_ledger_halts(env) -> None:
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    lines = env["ledger"].read_bytes().splitlines(keepends=True)
    env["ledger"].write_bytes(b"".join(lines[:-2]))
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"]()
    assert exc.value.reason == INTEGRITY_LEDGER_TRUNCATED
    assert env["target"].count() == 1


def test_truncated_while_running_halts_and_is_sticky(env) -> None:
    il = env["make"]()
    il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    env["ledger"].write_bytes(b"")
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    assert exc.value.reason == INTEGRITY_LEDGER_TRUNCATED
    # Sticky: other CAIDs are refused too until a fresh, consistent instance is built.
    with pytest.raises(LedgerIntegrityViolationError):
        il.dispatch(URI, TOOL, {"other": 1}, dispatch_fn=env["target"].ok)
    assert env["target"].count() == 1


def test_deleted_ledger_halts(env) -> None:
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    env["ledger"].unlink()
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"]()
    assert exc.value.reason == INTEGRITY_LEDGER_MISSING


def test_older_ledger_copy_restored_halts(env) -> None:
    env["make"]().dispatch(URI, TOOL, {"first": 1}, dispatch_fn=env["target"].ok)
    snap = env["tmp"] / "old_ledger.jsonl"
    shutil.copy(env["ledger"], snap)
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    shutil.copy(snap, env["ledger"])
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"]()
    assert exc.value.reason == INTEGRITY_LEDGER_TRUNCATED
    assert env["target"].count() == 2


def test_same_length_rewrite_of_prefix_halts(env) -> None:
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    raw = bytearray(env["ledger"].read_bytes())
    idx = raw.index(b'"settle"') + 1
    raw[idx] = ord("S")
    env["ledger"].write_bytes(bytes(raw))
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"]()
    assert exc.value.reason == INTEGRITY_LEDGER_DIVERGES


def test_older_hwm_restored_while_running_halts(env) -> None:
    il = env["make"]()
    il.dispatch(URI, TOOL, {"first": 1}, dispatch_fn=env["target"].ok)
    hwm = env["ledger"].with_name("ledger.jsonl.hwm")
    old_hwm = hwm.read_bytes()
    il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    hwm.write_bytes(old_hwm)
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        il.dispatch(URI, TOOL, {"third": 1}, dispatch_fn=env["target"].ok)
    assert exc.value.reason == INTEGRITY_HWM_SEQ_REGRESSED


def test_tampered_hwm_fields_halt(env) -> None:
    env["make"]().dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    hwm = env["ledger"].with_name("ledger.jsonl.hwm")
    doc = json.loads(hwm.read_text(encoding="utf-8"))
    doc["record_count"] = 0
    doc["ledger_bytes"] = 0
    hwm.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"]()
    assert exc.value.reason == INTEGRITY_HWM_SIGNATURE_INVALID


def test_consistent_rollback_of_both_files_needs_external_anchor(env) -> None:
    """Documents the limitation: local files alone cannot reveal a consistent older pair."""
    env["make"]().dispatch(URI, TOOL, {"first": 1}, dispatch_fn=env["target"].ok)
    hwm = env["ledger"].with_name("ledger.jsonl.hwm")
    snap_l, snap_h = env["tmp"] / "l.bak", env["tmp"] / "h.bak"
    shutil.copy(env["ledger"], snap_l)
    shutil.copy(hwm, snap_h)
    il = env["make"]()
    il.dispatch(URI, TOOL, PAY, dispatch_fn=env["target"].ok)
    anchored_seq = il.high_water_mark_seq()
    anchored_digest = il.high_water_mark_digest()
    assert isinstance(anchored_digest, str) and len(anchored_digest) == 64
    shutil.copy(snap_l, env["ledger"])
    shutil.copy(snap_h, hwm)
    # With the externally anchored seq, the consistent rollback is detected.
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        env["make"](min_hwm_seq=anchored_seq)
    assert exc.value.reason == INTEGRITY_HWM_SEQ_REGRESSED
    # Without an anchor the older pair verifies (limitation, stated in the module docstring).
    unanchored = env["make"]()
    assert unanchored.high_water_mark_seq() < anchored_seq


# ---------------------------------------------------------------------------
# 3. Symlink / ownership refusal
# ---------------------------------------------------------------------------

def test_symlinked_ledger_path_refused(tmp_path: Path) -> None:
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    redirect = other_dir / "redirect.jsonl"
    redirect.write_text("")
    work = tmp_path / "work"
    work.mkdir()
    ledger = work / "ledger.jsonl"
    os.symlink(redirect, ledger)
    with pytest.raises(LedgerPathSecurityError):
        PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=work / "state",
                                   boundary_private_key=Ed25519PrivateKey.generate())
    assert redirect.stat().st_size == 0


def test_symlinked_hwm_and_state_dir_refused(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    ledger = tmp_path / "ledger.jsonl"
    il = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=tmp_path / "state", boundary_private_key=key)
    il.dispatch(URI, TOOL, PAY, dispatch_fn=lambda: {"ok": 1})
    hwm = ledger.with_name("ledger.jsonl.hwm")
    real_hwm = tmp_path / "hwm.real"
    os.replace(hwm, real_hwm)
    os.symlink(real_hwm, hwm)
    with pytest.raises(LedgerPathSecurityError):
        PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=tmp_path / "state", boundary_private_key=key)

    real_state = tmp_path / "real_state"
    real_state.mkdir()
    os.symlink(real_state, tmp_path / "state_link")
    with pytest.raises(LedgerPathSecurityError):
        PreDispatchIntentInterlock(ledger_path=tmp_path / "l2.jsonl", output_state_dir=tmp_path / "state_link",
                                   boundary_private_key=key)


def test_symlinked_latch_marker_still_latches(env) -> None:
    other_caid = compute_caid({"x": "latched-by-name"})
    decoy = env["tmp"] / "decoy.json"
    decoy.write_text(json.dumps({"caid": "something-else"}))
    env["state"].mkdir(parents=True, exist_ok=True)
    os.symlink(decoy, env["state"] / f"latched_{other_caid}.json")
    il = env["make"]()
    assert il.is_caid_latched(other_caid)
    with pytest.raises(LatchedCaidExecutionHaltedError):
        il.dispatch(URI, TOOL, {"x": "latched-by-name"}, dispatch_fn=env["target"].ok)
    assert env["target"].count() == 0


# ---------------------------------------------------------------------------
# 4. No false positive on clean restart; latency
# ---------------------------------------------------------------------------

def test_clean_restart_has_no_false_positive(env) -> None:
    il = env["make"]()
    il.dispatch(URI, TOOL, {"a": 1}, dispatch_fn=env["target"].ok)
    with pytest.raises(RuntimeError):
        il.dispatch(URI, TOOL, {"b": 1}, dispatch_fn=env["target"].fail)
    seq_before = il.high_water_mark_seq()
    del il

    restarted = env["make"]()
    assert restarted.get_integrity_violations() == {}
    assert restarted.high_water_mark_seq() == seq_before
    with pytest.raises(CaidAlreadyCommittedError):
        restarted.dispatch(URI, TOOL, {"a": 1}, dispatch_fn=env["target"].ok)
    with pytest.raises(LatchedCaidExecutionHaltedError):
        restarted.dispatch(URI, TOOL, {"b": 1}, dispatch_fn=env["target"].ok)
    restarted.reconcile_out_of_band(compute_caid({"b": 1}), {"status": "NOT_FOUND"})
    restarted.dispatch(URI, TOOL, {"b": 1}, dispatch_fn=env["target"].ok)
    restarted.dispatch(URI, TOOL, {"c": 1}, dispatch_fn=env["target"].ok)
    assert env["target"].count() == 4

    again = env["make"]()
    assert again.get_integrity_violations() == {}
    assert again.high_water_mark_seq() > seq_before


def test_torn_tail_after_hwm_is_accepted(env) -> None:
    """Crash mid-append leaves bytes beyond the HWM; that is not a rollback."""
    env["make"]().dispatch(URI, TOOL, {"a": 1}, dispatch_fn=env["target"].ok)
    with open(env["ledger"], "ab") as fh:
        fh.write(b'{"record_type": "DISPATCH_INT')
    il = env["make"]()
    il.dispatch(URI, TOOL, {"b": 1}, dispatch_fn=env["target"].ok)
    assert env["make"]().get_integrity_violations() == {}
    assert env["target"].count() == 2


def test_record_intent_latency_200(env, capsys) -> None:
    il = env["make"]()
    samples: List[float] = []
    for i in range(200):
        t0 = time.perf_counter()
        il.record_intent(URI, TOOL, {"n": i})
        samples.append(time.perf_counter() - t0)
    assert len(samples) == 200
    # genesis HWM (seq 1) + one HWM per appended intent
    assert il.high_water_mark_seq() == 201
    assert env["make"](auto_recover=False).get_integrity_violations() == {}
    ordered = sorted(samples)
    with capsys.disabled():
        print(
            f"\n[eo1 record_intent x200] mean_ms={statistics.mean(samples) * 1e3:.3f} "
            f"p50_ms={ordered[99] * 1e3:.3f} p99_ms={ordered[197] * 1e3:.3f}"
        )
