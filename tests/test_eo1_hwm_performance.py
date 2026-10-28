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
tests/test_eo1_hwm_performance.py
================================================================================
Real-file tests for the EO-1 high-water-mark flush policies (no mocks, no monkeypatching):

  - Default policy "barrier_then_single_full_flush": per append to an existing ledger the
    ledger fd and the HWM tmp fd get the ordering flush and the directory gets the single
    full flush, issued last (after os.replace).
  - "full_flush_every_write": every step gets the full flush (legacy behaviour).
  - Fallback: when the directory flush cannot report a full flush, the ledger and HWM files
    are flushed with the full primitive before the append returns.
  - Detection is unchanged under the default policy: the HWM is rewritten after every
    append, and truncation / older-HWM restore / divergence still halt.

The recording subclasses override only the _durable_fsync hook (as in
tests/test_eo1_durability_cross_process.py) and still perform the real syscalls; one
subclass performs a real os.fsync on directory fds instead of the full primitive to
exercise the fallback branch. Power loss is not simulated here.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, List, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.eo1_write_before_execute as eo1  # noqa: E402
from src.eo1_write_before_execute import (  # noqa: E402
    FLUSH_POLICY_BARRIER_THEN_FULL,
    FLUSH_POLICY_FULL_EVERY_WRITE,
    INTEGRITY_HWM_SEQ_REGRESSED,
    INTEGRITY_LEDGER_DIVERGES,
    INTEGRITY_LEDGER_TRUNCATED,
    LedgerIntegrityViolationError,
    PreDispatchIntentInterlock,
)

URI = "local://hwm-perf"

Call = Tuple[int, bool, bool]  # (st_ino, is_directory, ordering_only)


class _RecordingInterlock(PreDispatchIntentInterlock):
    """Records (inode, is_dir, ordering_only) for every hook call, then performs the real flush."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.calls: List[Call] = []
        super().__init__(*args, **kwargs)

    def _durable_fsync(self, fd: int) -> None:
        st = os.fstat(fd)
        self.calls.append((st.st_ino, stat.S_ISDIR(st.st_mode), self._ordering_only_flush))
        super()._durable_fsync(fd)


class _NoFullDirFlushInterlock(_RecordingInterlock):
    """Directory full flushes run plain os.fsync and report 'not full' (FS without F_FULLFSYNC on dirs)."""

    def _durable_fsync(self, fd: int) -> None:
        st = os.fstat(fd)
        if stat.S_ISDIR(st.st_mode) and not self._ordering_only_flush:
            self.calls.append((st.st_ino, True, False))
            os.fsync(fd)
            self._last_flush_was_full = False
            return
        super()._durable_fsync(fd)


def _make(cls, tmp_path: Path, key: Ed25519PrivateKey, **kwargs: Any):
    return cls(
        ledger_path=tmp_path / "ledger.jsonl",
        boundary_private_key=key,
        output_state_dir=tmp_path / "state",
        **kwargs,
    )


def _inodes(il: PreDispatchIntentInterlock) -> Tuple[int, int, int]:
    return (
        os.stat(il.ledger_path).st_ino,
        os.stat(il.hwm_path).st_ino,
        os.stat(il.ledger_path.parent).st_ino,
    )


def _hwm_doc(il: PreDispatchIntentInterlock) -> dict:
    return json.loads(il.hwm_path.read_text(encoding="utf-8"))


def _ledger_records(il: PreDispatchIntentInterlock) -> int:
    return sum(1 for line in il.ledger_path.read_bytes().splitlines() if line.strip())


# ---------------------------------------------------------------------------
# Policy selection
# ---------------------------------------------------------------------------

def test_default_policy_is_barrier_then_single_full_flush(tmp_path: Path) -> None:
    il = _make(PreDispatchIntentInterlock, tmp_path, Ed25519PrivateKey.generate())
    assert il.flush_policy == FLUSH_POLICY_BARRIER_THEN_FULL == "barrier_then_single_full_flush"
    assert FLUSH_POLICY_FULL_EVERY_WRITE == "full_flush_every_write"


def test_unknown_flush_policy_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="flush_policy"):
        _make(PreDispatchIntentInterlock, tmp_path, Ed25519PrivateKey.generate(), flush_policy="every_other_write")


# ---------------------------------------------------------------------------
# Flush sequence per append
# ---------------------------------------------------------------------------

def test_default_policy_orders_then_single_full_flush_last(tmp_path: Path) -> None:
    il = _make(_RecordingInterlock, tmp_path, Ed25519PrivateKey.generate())
    il.record_intent(URI, "t", {"n": 0})
    il.calls.clear()
    il.record_intent(URI, "t", {"n": 1})
    ledger_ino, hwm_ino, dir_ino = _inodes(il)
    assert il.calls == [
        (ledger_ino, False, True),   # ledger append: ordering flush
        (hwm_ino, False, True),      # HWM tmp file (renamed onto hwm_path): ordering flush
        (dir_ino, True, False),      # directory after os.replace: the single full flush
    ]
    assert il._ordering_only_flush is False  # mode restored after the append
    assert il._last_flush_was_full is True


def test_full_every_write_policy_uses_full_flush_for_every_step(tmp_path: Path) -> None:
    il = _make(_RecordingInterlock, tmp_path, Ed25519PrivateKey.generate(), flush_policy=FLUSH_POLICY_FULL_EVERY_WRITE)
    il.record_intent(URI, "t", {"n": 0})
    il.calls.clear()
    il.record_intent(URI, "t", {"n": 1})
    ledger_ino, hwm_ino, dir_ino = _inodes(il)
    assert il.calls == [(ledger_ino, False, False), (hwm_ino, False, False), (dir_ino, True, False)]


def test_first_append_genesis_hwm_is_full_and_new_ledger_dir_entry_is_ordered(tmp_path: Path) -> None:
    il = _make(_RecordingInterlock, tmp_path, Ed25519PrivateKey.generate())
    il.record_intent(URI, "t", {"n": 0})
    ledger_ino, hwm_ino, dir_ino = _inodes(il)
    modes = [(is_dir, ordering) for (_ino, is_dir, ordering) in il.calls]
    assert modes == [
        (False, False), (True, False),   # genesis HWM: full tmp + full dir
        (False, True), (True, True),     # ledger created: ordering file + ordering dir entry
        (False, True), (True, False),    # HWM rewrite: ordering tmp, full dir flush last
    ]
    assert il.calls[2][0] == ledger_ino and il.calls[4][0] == hwm_ino and il.calls[5][0] == dir_ino


def test_receipt_append_also_ends_with_full_flush(tmp_path: Path) -> None:
    il = _make(_RecordingInterlock, tmp_path, Ed25519PrivateKey.generate())
    intent = il.record_intent(URI, "t", {"n": 0})
    il.calls.clear()
    il.reconcile_out_of_band(intent.caid, {"status": "OBSERVED"}, target_outcome="COMMITTED")
    assert il.calls, "receipt append must flush"
    assert il.calls[-1][1:] == (True, False)
    assert il._last_flush_was_full is True


def test_fallback_full_flushes_files_when_dir_flush_not_full(tmp_path: Path) -> None:
    il = _make(_NoFullDirFlushInterlock, tmp_path, Ed25519PrivateKey.generate())
    il.record_intent(URI, "t", {"n": 0})
    il.calls.clear()
    il.record_intent(URI, "t", {"n": 1})
    ledger_ino, hwm_ino, dir_ino = _inodes(il)
    assert il.calls == [
        (ledger_ino, False, True),
        (hwm_ino, False, True),
        (dir_ino, True, False),      # reported not full
        (ledger_ino, False, False),  # fallback: full flush of the ledger file
        (hwm_ino, False, False),     # fallback: full flush of the HWM file
    ]


def test_no_fallback_under_full_every_write_policy(tmp_path: Path) -> None:
    il = _make(_NoFullDirFlushInterlock, tmp_path, Ed25519PrivateKey.generate(), flush_policy=FLUSH_POLICY_FULL_EVERY_WRITE)
    il.record_intent(URI, "t", {"n": 0})
    il.calls.clear()
    il.record_intent(URI, "t", {"n": 1})
    assert len(il.calls) == 3


# ---------------------------------------------------------------------------
# Module helpers on real descriptors
# ---------------------------------------------------------------------------

def test_fsync_helpers_on_real_file(tmp_path: Path) -> None:
    path = tmp_path / "f.bin"
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        os.write(fd, b"x" * 64)
        assert eo1._fsync_fd(fd) is True
        assert eo1._barrier_fsync_fd(fd) is None
    finally:
        os.close(fd)
    assert path.read_bytes() == b"x" * 64


def test_barrier_helper_does_not_swallow_unflushable_fd() -> None:
    r, w = os.pipe()
    try:
        with pytest.raises(OSError):
            eo1._barrier_fsync_fd(w)
    finally:
        os.close(r)
        os.close(w)


# ---------------------------------------------------------------------------
# Detection unchanged under the default policy
# ---------------------------------------------------------------------------

def test_hwm_covers_every_append_under_default_policy(tmp_path: Path) -> None:
    il = _make(PreDispatchIntentInterlock, tmp_path, Ed25519PrivateKey.generate())
    for i in range(5):
        intent = il.record_intent(URI, "t", {"n": i})
        doc = _hwm_doc(il)
        assert doc["record_count"] == _ledger_records(il)
        assert doc["ledger_bytes"] == il.ledger_path.stat().st_size
        il.reconcile_out_of_band(intent.caid, {"status": "OBSERVED"}, target_outcome="COMMITTED")
        doc = _hwm_doc(il)
        assert doc["record_count"] == _ledger_records(il)
        assert doc["ledger_bytes"] == il.ledger_path.stat().st_size


def test_truncation_after_intent_detected_on_restart(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    il = _make(PreDispatchIntentInterlock, tmp_path, key)
    il.record_intent(URI, "t", {"n": 0})
    il.record_intent(URI, "t", {"n": 1})
    raw = il.ledger_path.read_bytes()
    lines = raw.splitlines(keepends=True)
    il.ledger_path.write_bytes(b"".join(lines[:-1]))  # drop the last (dispatched) intent
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        _make(PreDispatchIntentInterlock, tmp_path, key)
    assert exc.value.reason == INTEGRITY_LEDGER_TRUNCATED


def test_older_hwm_restored_while_running_halts_under_default_policy(tmp_path: Path) -> None:
    il = _make(PreDispatchIntentInterlock, tmp_path, Ed25519PrivateKey.generate())
    il.record_intent(URI, "t", {"n": 0})
    old = il.hwm_path.read_bytes()
    il.record_intent(URI, "t", {"n": 1})
    il.hwm_path.write_bytes(old)
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        il.record_intent(URI, "t", {"n": 2})
    assert exc.value.reason == INTEGRITY_HWM_SEQ_REGRESSED


def test_edited_prefix_detected_on_restart_under_default_policy(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    il = _make(PreDispatchIntentInterlock, tmp_path, key)
    il.record_intent(URI, "t", {"n": 0})
    il.record_intent(URI, "t", {"n": 1})
    raw = bytearray(il.ledger_path.read_bytes())
    idx = raw.index(b'"t"')
    raw[idx + 1:idx + 2] = b"u"  # same length, different bytes
    il.ledger_path.write_bytes(bytes(raw))
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        _make(PreDispatchIntentInterlock, tmp_path, key)
    assert exc.value.reason == INTEGRITY_LEDGER_DIVERGES


def test_policies_share_on_disk_format_across_restart(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    il = _make(PreDispatchIntentInterlock, tmp_path, key)
    il.record_intent(URI, "t", {"n": 0})
    seq = il.high_water_mark_seq()
    il2 = _make(PreDispatchIntentInterlock, tmp_path, key, flush_policy=FLUSH_POLICY_FULL_EVERY_WRITE, min_hwm_seq=seq)
    il2.record_intent(URI, "t", {"n": 1})
    assert il2.high_water_mark_seq() == seq + 1
    il3 = _make(PreDispatchIntentInterlock, tmp_path, key, min_hwm_seq=seq + 1)
    assert il3.high_water_mark_seq() == seq + 1
    assert _hwm_doc(il3)["record_count"] == 2


# ---------------------------------------------------------------------------
# Adjacent module behaviour exercised by the same append path (mutation-gate survivors)
# ---------------------------------------------------------------------------

def test_hwm_deleted_at_seq_one_while_running_halts(tmp_path: Path) -> None:
    il = _make(PreDispatchIntentInterlock, tmp_path, Ed25519PrivateKey.generate())
    with il._exclusive():
        il._write_hwm_locked()  # genesis HWM on an empty ledger: seq 1
    assert il.high_water_mark_seq() == 1
    il.hwm_path.unlink()
    with pytest.raises(LedgerIntegrityViolationError) as exc:
        il.record_intent(URI, "t", {"n": 0})
    assert exc.value.reason == eo1.INTEGRITY_HWM_MISSING


def test_foreign_signed_tail_record_counted_untrusted_once(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    ours = _make(PreDispatchIntentInterlock, tmp_path / "a", Ed25519PrivateKey.generate())
    ours.record_intent(URI, "t", {"n": 0})
    foreign = _make(PreDispatchIntentInterlock, tmp_path / "b", Ed25519PrivateKey.generate())
    foreign.record_intent(URI, "t", {"n": 99})
    with open(ours.ledger_path, "ab") as fh:
        fh.write(foreign.ledger_path.read_bytes())
    with ours._exclusive():
        assert ours._view.untrusted_records == 1
        assert ours._view.record_count == 2


def test_default_policy_epoch_and_reconcile_fields(tmp_path: Path) -> None:
    il = _make(PreDispatchIntentInterlock, tmp_path, Ed25519PrivateKey.generate())
    intent = il.record_intent(URI, "t", {"n": 0})
    assert intent.policy_epoch == 1
    latch = il.latch_intent(intent.caid)
    assert latch.reconciliation_required is True
    receipt = il.reconcile_out_of_band(intent.caid, {"status": "NOT_FOUND"}, target_outcome="NOT_COMMITTED")
    assert receipt.retry_safe is False
    statement = receipt.statement_for_signature()
    assert statement["caid"] == intent.caid and statement["retry_safe"] is False
