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
tests/test_eo1_orphan_reaper.py
================================================================================
Startup reaping of orphan ``.<target>.<pid>.<tid>.tmp`` files left by a writer killed inside
_atomic_write_text (real files, real child processes, real SIGKILL; no mocks):

  - a child SIGKILLed while flushing the HWM temp file / a latch-marker temp file leaves the
    temp file; a fresh interlock removes it and reports the count and names;
  - look-alike names, names for targets this interlock does not write, and temp files in the
    wrong directory are untouched;
  - a temp file whose pid is alive (this test process) is retained;
  - a symlink or directory with a matching name is retained and never followed;
  - a clean restart removes nothing; an unlink failure halts with ORPHAN_TMP_REAP_FAILED;
  - the directory is fsynced after reaping (counted through the _durable_fsync hook).
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, List

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.eo1_write_before_execute as eo1  # noqa: E402
from src.eo1_write_before_execute import (  # noqa: E402
    INTEGRITY_ORPHAN_TMP_REAP_FAILED,
    LedgerIntegrityViolationError,
    PreDispatchIntentInterlock,
)

URI = "local://orphan-reaper"

CHILD_SRC = r"""
import os, sys, signal, stat
repo, d, mode = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, repo)
from cryptography.hazmat.primitives import serialization
from src.eo1_write_before_execute import PreDispatchIntentInterlock

state = os.path.join(d, "state")

def tmp_inodes(directory, prefix):
    out = set()
    for name in os.listdir(directory):
        if name.startswith(prefix) and name.endswith(".tmp"):
            out.add(os.lstat(os.path.join(directory, name)).st_ino)
    return out

class KillInTmpFlush(PreDispatchIntentInterlock):
    armed = False
    def _durable_fsync(self, fd):
        if self.armed:
            ino = os.fstat(fd).st_ino
            if mode == "hwm" and ino in tmp_inodes(d, ".ledger.jsonl.hwm."):
                os.kill(os.getpid(), signal.SIGKILL)
            if mode == "latch" and ino in tmp_inodes(state, ".latched_"):
                os.kill(os.getpid(), signal.SIGKILL)
        return super()._durable_fsync(fd)

with open(os.path.join(d, "key.pem"), "rb") as fh:
    key = serialization.load_pem_private_key(fh.read(), None)
il = KillInTmpFlush(ledger_path=os.path.join(d, "ledger.jsonl"), boundary_private_key=key, output_state_dir=state)
il.record_intent("local://orphan-reaper", "t", {"warm": 1})
il.armed = True
if mode == "hwm":
    il.record_intent("local://orphan-reaper", "t", {"n": 1})
else:
    def cut():
        raise ConnectionError("wire cut")
    il.dispatch("local://orphan-reaper", "t", {"n": 2}, dispatch_fn=cut)
sys.exit(7)  # not reached when the kill fires
"""


def _key_dir(tmp_path: Path) -> Ed25519PrivateKey:
    key = Ed25519PrivateKey.generate()
    (tmp_path / "state").mkdir(exist_ok=True)
    (tmp_path / "key.pem").write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return key


def _make(tmp_path: Path, key: Ed25519PrivateKey, cls=PreDispatchIntentInterlock, **kw: Any):
    return cls(ledger_path=tmp_path / "ledger.jsonl", boundary_private_key=key, output_state_dir=tmp_path / "state", **kw)


def _spawn_and_reap() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"], env={"PATH": os.environ.get("PATH", "")})
    p.wait(timeout=60)
    assert not eo1._pid_alive(p.pid)
    return p.pid


def _kill_child(tmp_path: Path, mode: str) -> int:
    p = subprocess.Popen(
        [sys.executable, "-c", CHILD_SRC, str(REPO_ROOT), str(tmp_path), mode],
        env={"PATH": os.environ.get("PATH", "")},
        cwd=str(tmp_path),
        stderr=subprocess.DEVNULL,
    )
    rc = p.wait(timeout=120)
    assert rc == -9, f"child was expected to die by SIGKILL, rc={rc}"
    return p.pid


def _tmp_names(directory: Path) -> List[str]:
    return sorted(n for n in os.listdir(directory) if eo1._ORPHAN_TMP_NAME_RE.match(n))


# ---------------------------------------------------------------------------
# Real SIGKILL mid-append
# ---------------------------------------------------------------------------

def test_sigkill_during_hwm_tmp_flush_leaves_orphan_and_restart_reaps_it(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    pid = _kill_child(tmp_path, "hwm")
    left = _tmp_names(tmp_path)
    assert left and all(f".{pid}." in n and n.startswith(".ledger.jsonl.hwm.") for n in left)
    il = _make(tmp_path, key)
    assert il.boot_reaped_tmp_count == len(left) == 1
    assert il.boot_reaped_tmp_names == [str(tmp_path / left[0])]
    assert _tmp_names(tmp_path) == []
    # The intent whose HWM write was interrupted is on disk and latched (not re-admitted).
    il2 = _make(tmp_path, key)
    assert il2.boot_reaped_tmp_count == 0


def test_sigkill_during_latch_tmp_flush_leaves_orphan_and_restart_reaps_it(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    pid = _kill_child(tmp_path, "latch")
    state = tmp_path / "state"
    left = _tmp_names(state)
    assert left and all(n.startswith(".latched_") and f".{pid}." in n for n in left)
    il = _make(tmp_path, key)
    assert il.boot_reaped_tmp_count == 1
    assert il.boot_reaped_tmp_names == [str(state / left[0])]
    assert _tmp_names(state) == [] or all(f".{os.getpid()}." in n for n in _tmp_names(state))
    caid = eo1.compute_caid({"n": 2})
    assert il.is_caid_latched(caid)


# ---------------------------------------------------------------------------
# What must never be removed
# ---------------------------------------------------------------------------

def test_lookalikes_foreign_targets_and_wrong_directory_untouched(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    _make(tmp_path, key).record_intent(URI, "t", {"n": 0})
    dead = _spawn_and_reap()
    state = tmp_path / "state"
    untouched = [
        tmp_path / ".foo.1.2.tmp",
        tmp_path / ".hwm.x.tmp",
        tmp_path / f".ledger.jsonl.hwm.abc.{dead}.tmp",
        tmp_path / f".other.jsonl.hwm.{dead}.1.tmp",
        tmp_path / f".ledger.jsonl.{dead}.1.tmp",
        tmp_path / f".latched_{'a' * 64}.json.{dead}.1.tmp",       # latch name in the ledger dir
        state / f".ledger.jsonl.hwm.{dead}.1.tmp",                  # HWM name in the state dir
        state / f".notes.json.{dead}.1.tmp",
        state / f"latched_{'b' * 64}.json.{dead}.1.tmp",            # no leading dot
        state / f".latched_../x.json.{dead}.1.tmp".replace("/", "_"),
    ]
    for p in untouched:
        p.write_text("keep", encoding="utf-8")
    genuine = state / f".latched_{'c' * 64}.json.{dead}.77.tmp"
    genuine.write_text("partial", encoding="utf-8")
    il = _make(tmp_path, key)
    assert il.boot_reaped_tmp_names == [str(genuine)]
    assert not genuine.exists()
    for p in untouched:
        assert p.read_text(encoding="utf-8") == "keep", p.name


def test_tmp_of_live_pid_is_retained(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    _make(tmp_path, key).record_intent(URI, "t", {"n": 0})
    live = tmp_path / f".ledger.jsonl.hwm.{os.getpid()}.12345.tmp"
    live.write_text("in progress", encoding="utf-8")
    il = _make(tmp_path, key)
    assert il.boot_reaped_tmp_count == 0
    assert live.read_text(encoding="utf-8") == "in progress"
    assert il.boot_retained_tmp == {str(live): "WRITER_PID_ALIVE"}


def test_symlink_and_directory_with_matching_name_are_retained(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    _make(tmp_path, key).record_intent(URI, "t", {"n": 0})
    dead = _spawn_and_reap()
    outside = tmp_path / "outside.txt"
    outside.write_text("victim", encoding="utf-8")
    link = tmp_path / f".ledger.jsonl.hwm.{dead}.1.tmp"
    os.symlink(outside, link)
    as_dir = tmp_path / "state" / f".latched_{'d' * 64}.json.{dead}.2.tmp"
    as_dir.mkdir()
    il = _make(tmp_path, key)
    assert il.boot_reaped_tmp_count == 0
    assert os.path.islink(link) and outside.read_text(encoding="utf-8") == "victim"
    assert as_dir.is_dir()
    assert il.boot_retained_tmp == {str(link): "SYMLINK", str(as_dir): "NOT_REGULAR_FILE"}


def test_clean_restart_reaps_nothing(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    il = _make(tmp_path, key)
    il.record_intent(URI, "t", {"n": 0})
    il2 = _make(tmp_path, key)
    assert (il2.boot_reaped_tmp_count, il2.boot_reaped_tmp_names, il2.boot_retained_tmp) == (0, [], {})


def test_no_reaping_without_auto_recover(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    _make(tmp_path, key).record_intent(URI, "t", {"n": 0})
    orphan = tmp_path / f".ledger.jsonl.hwm.{_spawn_and_reap()}.1.tmp"
    orphan.write_text("x", encoding="utf-8")
    il = _make(tmp_path, key, auto_recover=False)
    assert il.boot_reaped_tmp_count == 0 and orphan.exists()
    il2 = _make(tmp_path, key)
    assert il2.boot_reaped_tmp_count == 1 and not orphan.exists()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores directory write permission")
def test_unlink_failure_halts_fail_closed(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    _make(tmp_path, key).record_intent(URI, "t", {"n": 0})
    state = tmp_path / "state"
    orphan = state / f".latched_{'e' * 64}.json.{_spawn_and_reap()}.1.tmp"
    orphan.write_text("x", encoding="utf-8")
    os.chmod(state, 0o500)
    try:
        with pytest.raises(LedgerIntegrityViolationError) as exc:
            _make(tmp_path, key)
        assert exc.value.reason == INTEGRITY_ORPHAN_TMP_REAP_FAILED
    finally:
        os.chmod(state, 0o700)
    assert orphan.exists()


class _CountingInterlock(PreDispatchIntentInterlock):
    def __init__(self, *a: Any, **kw: Any) -> None:
        self.dir_fsyncs: List[int] = []
        super().__init__(*a, **kw)

    def _durable_fsync(self, fd: int) -> None:
        st = os.fstat(fd)
        if stat.S_ISDIR(st.st_mode):
            self.dir_fsyncs.append(st.st_ino)
        super()._durable_fsync(fd)


def test_directory_fsynced_once_per_directory_after_reaping(tmp_path: Path) -> None:
    key = _key_dir(tmp_path)
    _make(tmp_path, key).record_intent(URI, "t", {"n": 0})
    clean = _make(tmp_path, key, cls=_CountingInterlock)
    baseline = list(clean.dir_fsyncs)  # latch-marker rewrite for the unresolved intent
    dead = _spawn_and_reap()
    (tmp_path / f".ledger.jsonl.hwm.{dead}.1.tmp").write_text("x", encoding="utf-8")
    (tmp_path / f".ledger.jsonl.hwm.{dead}.2.tmp").write_text("x", encoding="utf-8")
    (tmp_path / "state" / f".consumed_approval_ap-1.json.{dead}.3.tmp").write_text("x", encoding="utf-8")
    il = _make(tmp_path, key, cls=_CountingInterlock)
    assert il.boot_reaped_tmp_count == 3
    assert sorted(il.dir_fsyncs) == sorted(baseline + [os.stat(tmp_path).st_ino, os.stat(tmp_path / "state").st_ino])


def test_pid_alive_probe_on_real_processes() -> None:
    assert eo1._pid_alive(os.getpid()) is True
    assert eo1._pid_alive(_spawn_and_reap()) is False
    assert eo1._pid_alive(0) is True
    assert eo1._pid_alive(-5) is True
    assert eo1._pid_alive(2 ** 40) is True
