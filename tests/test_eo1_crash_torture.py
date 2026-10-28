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
tests/test_eo1_crash_torture.py
================================================================================
EO-1 crash-consistency torture harness under process death (real SIGKILL, real files,
real Ed25519 keys; no mocks, no monkeypatching).

A child interpreter loops over record_intent / dispatch (effect + COMMITTED receipt) /
dispatch-with-wire-fault (latch) on one ledger with a stable boundary key and prints
"ACK_INTENT <caid>" only after record_intent has returned (and, for dispatch, before
the effect). The parent SIGKILLs it at a seeded random time, captures the on-disk crash
state, opens a fresh interlock (auto_recover=True) and classifies the kill:

  (a) clean recovery;
  (b) integrity halt on an honest crash (availability failure);
  (c) acknowledged intent missing after recovery (durability failure);
  (d) a CAID with an intent on disk that is admitted again, or an effect executed twice
      (safety failure);
  (o) a temp file of a dead writer still present after recovery (orphan not reaped).

Scope: process death only. Power loss / device cache loss is not simulated here, so the
F_BARRIERFSYNC + single F_FULLFSYNC ordering argument is not evaluated by this harness.
The pytest run is small (40 kills); scratch/crash_torture/run_torture.py runs N >= 300.
"""

from __future__ import annotations

import json
import math
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.eo1_write_before_execute as eo1  # noqa: E402
from src.eo1_write_before_execute import (  # noqa: E402
    LatchedCaidExecutionHaltedError,
    LedgerIntegrityViolationError,
    PreDispatchIntentInterlock,
    compute_caid,
)

URI = "local://crash-torture"
TOOL = "t"

CHILD_SRC = r"""
import os, sys, random
import signal, stat
repo, d, gen, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
kill_at, kill_when = int(sys.argv[5]), sys.argv[6]
sys.path.insert(0, repo)
from cryptography.hazmat.primitives import serialization
from src.eo1_write_before_execute import PreDispatchIntentInterlock, LedgerIntegrityViolationError, compute_caid

def out(line):
    os.write(1, (line + "\n").encode("utf-8"))

class KillAtFlush(PreDispatchIntentInterlock):
    # Real SIGKILL of this process at the kill_at-th durable flush after READY (before or after it).
    armed = False
    flushes = 0

    def _durable_fsync(self, fd):
        if not self.armed:
            return super()._durable_fsync(fd)
        self.flushes += 1
        if self.flushes == kill_at:
            st = os.fstat(fd)
            if stat.S_ISDIR(st.st_mode):
                kind = "dir"
            elif os.path.exists(os.path.join(d, "ledger.jsonl")) and st.st_ino == os.stat(os.path.join(d, "ledger.jsonl")).st_ino:
                kind = "ledger"
            else:
                kind = "tmp_file"
            out("KILLPOINT %s %s ordering=%s" % (kill_when, kind, self._ordering_only_flush))
            if kill_when == "before":
                os.kill(os.getpid(), signal.SIGKILL)
            super()._durable_fsync(fd)
            os.kill(os.getpid(), signal.SIGKILL)
        return super()._durable_fsync(fd)

with open(os.path.join(d, "key.pem"), "rb") as fh:
    key = serialization.load_pem_private_key(fh.read(), None)
try:
    il = KillAtFlush(
        ledger_path=os.path.join(d, "ledger.jsonl"), boundary_private_key=key,
        output_state_dir=os.path.join(d, "state"), auto_recover=True)
except LedgerIntegrityViolationError as exc:
    out("HALT_STARTUP " + exc.reason)
    sys.exit(3)
out("READY")
il.armed = kill_at > 0
rng = random.Random(seed * 1000003 + gen)
effects = os.path.join(d, "effects.log")
URI, TOOL = "__URI__", "__TOOL__"

def effect(caid):
    fd = os.open(effects, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, (caid + "\n").encode("utf-8"))
    finally:
        os.close(fd)

i = 0
try:
    while True:
        payload = {"gen": gen, "i": i}
        caid = compute_caid(payload)
        out("TRY " + str(gen) + " " + str(i))
        i += 1
        op = rng.random()
        if op < 0.25:
            il.record_intent(URI, TOOL, payload)
            out("ACK_INTENT " + caid)
        elif op < 0.75:
            def ok(c=caid):
                out("ACK_INTENT " + c)
                effect(c)
                return {"ok": True}
            il.dispatch(URI, TOOL, payload, dispatch_fn=ok)
            out("ACK_COMMIT " + caid)
        else:
            def cut(c=caid):
                out("ACK_INTENT " + c)
                raise ConnectionError("wire cut")
            try:
                il.dispatch(URI, TOOL, payload, dispatch_fn=cut)
            except RuntimeError:
                out("ACK_LATCH " + caid)
except LedgerIntegrityViolationError as exc:
    out("HALT_RUNTIME " + exc.reason)
    sys.exit(4)
""".replace("__URI__", URI).replace("__TOOL__", TOOL)


def wilson(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """Wilson score 95% interval for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _ledger_records(raw: bytes) -> List[Dict[str, Any]]:
    recs = []
    for line in raw.split(b"\n"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(rec, dict):
            recs.append(rec)
    return recs


def dead_writer_tmp_files(d: Path) -> List[str]:
    """Temp files named like _atomic_write_text output whose writer pid no longer exists."""
    out = []
    for directory in (d, d / "state"):
        if not directory.is_dir():
            continue
        for name in os.listdir(directory):
            m = eo1._ORPHAN_TMP_NAME_RE.match(name)
            if m and not eo1._pid_alive(int(m.group("pid"))):
                out.append(str(directory / name))
    return sorted(out)


def disk_crash_state(d: Path) -> Dict[str, Any]:
    """Classifies where the kill landed, from on-disk evidence only (captured before recovery)."""
    ledger = d / "ledger.jsonl"
    hwm = d / "ledger.jsonl.hwm"
    raw = ledger.read_bytes() if ledger.exists() else b""
    hwm_bytes: Optional[int] = None
    if hwm.exists():
        try:
            hwm_bytes = int(json.loads(hwm.read_text(encoding="utf-8"))["ledger_bytes"])
        except (ValueError, KeyError, TypeError):
            hwm_bytes = -1
    tmp_hwm = sorted(p.name for p in d.glob(".ledger.jsonl.hwm.*.tmp"))
    torn_tail = bool(raw) and not raw.endswith(b"\n")
    if hwm_bytes is None:
        point = "no_hwm"
    elif torn_tail:
        point = "inside_ledger_write_torn_tail"
    elif len(raw) > hwm_bytes:
        point = "between_ledger_fsync_and_hwm_replace"
    elif len(raw) == hwm_bytes:
        point = "after_hwm_replace_or_outside_append"
    else:
        point = "ledger_shorter_than_hwm"
    return {
        "point": point,
        "ledger_bytes": len(raw),
        "hwm_ledger_bytes": hwm_bytes,
        "hwm_tmp_files_present": len(tmp_hwm),
        "torn_tail": torn_tail,
        "orphan_tmp_before_recovery": len(dead_writer_tmp_files(d)),
    }


def _payload_caids(acks_by_gen: Dict[int, int]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for gen, last_try in acks_by_gen.items():
        for i in range(last_try + 1):
            p = {"gen": gen, "i": i}
            out[compute_caid(p)] = p
    return out


class TortureRun:
    """One ledger directory; repeated spawn -> seeded SIGKILL -> fresh-interlock recovery check."""

    def __init__(self, d: Path, key: Ed25519PrivateKey, seed: int, max_delay_s: float, pre_ready_kill_prob: float):
        self.d = d
        self.key = key
        self.seed = seed
        self.rng = random.Random(seed)
        self.max_delay_s = max_delay_s
        self.pre_ready_kill_prob = pre_ready_kill_prob
        self.acked_intents: Set[str] = set()
        self.committed_acked: Set[str] = set()
        self.last_try: Dict[int, int] = {}
        self.gen = 0
        self.halted = False
        (d / "state").mkdir(parents=True, exist_ok=True)
        (d / "key.pem").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )

    def _spawn(self, kill_at: int = 0, kill_when: str = "none") -> subprocess.Popen:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.Popen(
            [sys.executable, "-c", CHILD_SRC, str(REPO_ROOT), str(self.d), str(self.gen), str(self.seed),
             str(kill_at), kill_when],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=str(self.d),
        )

    def kill_once(self, kill_at: int = 0, kill_when: str = "none") -> Dict[str, Any]:
        """Random-time SIGKILL by the parent, or (kill_at > 0) self-SIGKILL at the kill_at-th flush."""
        gen = self.gen
        self.gen += 1
        proc = self._spawn(kill_at, kill_when)
        pre_ready = kill_at == 0 and self.rng.random() < self.pre_ready_kill_prob
        delay = self.rng.uniform(0.0, self.max_delay_s)
        lines: List[str] = []
        if kill_at > 0:
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.kill(proc.pid, signal.SIGKILL)
        elif pre_ready:
            time.sleep(delay * 3)
        else:
            first = proc.stdout.readline().decode("utf-8", "replace").strip()
            lines.append(first)
            if first == "READY":
                time.sleep(delay)
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)
        proc.wait()
        lines += proc.stdout.read().decode("utf-8", "replace").splitlines()
        proc.stdout.close()
        child_halt = next((ln for ln in lines if ln.startswith("HALT_")), None)
        for ln in lines:
            parts = ln.split()
            if not parts:
                continue
            if parts[0] == "ACK_INTENT":
                self.acked_intents.add(parts[1])
            elif parts[0] == "ACK_COMMIT":
                self.committed_acked.add(parts[1])
            elif parts[0] == "TRY":
                self.last_try[int(parts[1])] = int(parts[2])
        crash = disk_crash_state(self.d)
        crash["gen"] = gen
        crash["killed_before_ready"] = pre_ready
        crash["last_child_line"] = lines[-1] if lines else ""
        crash["killpoint"] = next((ln for ln in lines if ln.startswith("KILLPOINT")), None)
        crash["exit_code"] = proc.returncode
        crash["acked_this_gen"] = sum(1 for ln in lines if ln.startswith("ACK_INTENT"))
        result = self.check(crash)
        if child_halt is not None:
            result["classes"].add("b")
            result["details"].append({"class": "b", "child": child_halt})
        if "b" in result["classes"]:
            self.halted = True
        return result

    def _fresh(self) -> PreDispatchIntentInterlock:
        return PreDispatchIntentInterlock(
            ledger_path=self.d / "ledger.jsonl",
            boundary_private_key=self.key,
            output_state_dir=self.d / "state",
            auto_recover=True,
        )

    def check(self, crash: Dict[str, Any], full: bool = False) -> Dict[str, Any]:
        classes: Set[str] = set()
        details: List[Dict[str, Any]] = []
        try:
            il = self._fresh()
        except LedgerIntegrityViolationError as exc:
            classes.add("b")
            details.append({"class": "b", "reason": exc.reason, "message": str(exc)})
            return {"crash": crash, "classes": classes, "details": details}
        crash["reaped_tmp"] = il.boot_reaped_tmp_count
        leftover = dead_writer_tmp_files(self.d)
        if leftover:
            classes.add("o")
            details.append({"class": "o", "orphan_tmp_after_recovery": leftover})
        recs = _ledger_records((self.d / "ledger.jsonl").read_bytes()) if (self.d / "ledger.jsonl").exists() else []
        intent_caids = {r.get("caid") for r in recs if r.get("record_type") == "DISPATCH_INTENT"}
        missing = sorted(self.acked_intents - intent_caids)
        if missing:
            classes.add("c")
            details.append({"class": "c", "missing_caids": missing})
        effects_file = self.d / "effects.log"
        if effects_file.exists():
            eff = [ln for ln in effects_file.read_text(encoding="utf-8").splitlines() if ln]
            dups = sorted({c for c in eff if eff.count(c) > 1})
            if dups:
                classes.add("d")
                details.append({"class": "d", "duplicate_effects": dups})
        payloads = _payload_caids(self.last_try)
        if full:
            probe = sorted(c for c in intent_caids if c in payloads)
        else:
            latest = crash["gen"]
            recent = [c for c in intent_caids if c in payloads and payloads[c]["gen"] >= latest - 1]
            older = sorted(c for c in intent_caids if c in payloads and c not in recent)
            probe = sorted(recent) + self.rng.sample(older, min(8, len(older)))
        unknown = sorted(c for c in intent_caids if c not in payloads)
        if unknown:
            classes.add("c")
            details.append({"class": "c", "intent_caids_without_known_payload": unknown})
        for caid in probe:
            try:
                il.record_intent(URI, TOOL, payloads[caid])
            except LatchedCaidExecutionHaltedError:
                continue
            classes.add("d")
            details.append({"class": "d", "readmitted_caid": caid, "payload": payloads[caid]})
        crash["probed_caids"] = len(probe)
        return {"crash": crash, "classes": classes, "details": details}


def run_torture(base: Path, total_kills: int, kills_per_run: int, seed: int,
                max_delay_s: float = 0.25, pre_ready_kill_prob: float = 0.15,
                flush_sweep: int = 0) -> Dict[str, Any]:
    """
    Runs the harness and returns per-class counts, Wilson 95% intervals and every bad case.
    flush_sweep=N first adds 2*N deterministic kills (before/after each of flush 1..N after
    READY, one ledger directory per flush index), then total_kills random-time kills.
    """
    rng = random.Random(seed)
    kills: List[Dict[str, Any]] = []
    run_idx = 0
    started = time.perf_counter()
    for n in range(1, flush_sweep + 1):
        d = base / f"sweep{n:03d}"
        d.mkdir(parents=True)
        run = TortureRun(d, Ed25519PrivateKey.generate(), rng.randrange(1 << 30), max_delay_s, 0.0)
        for when in ("before", "after"):
            res = run.kill_once(kill_at=n, kill_when=when)
            res["run"] = f"sweep{n}"
            kills.append(res)
            if run.halted:
                break
        run_idx += 1
    total_kills += len(kills)
    while len(kills) < total_kills:
        d = base / f"run{run_idx:03d}"
        d.mkdir(parents=True)
        run = TortureRun(d, Ed25519PrivateKey.generate(), rng.randrange(1 << 30), max_delay_s, pre_ready_kill_prob)
        for _ in range(min(kills_per_run, total_kills - len(kills))):  # random-time kills
            res = run.kill_once()
            res["run"] = run_idx
            kills.append(res)
            if run.halted:
                break
        if not run.halted:
            final = run.check({"gen": run.gen, "point": "end_of_run_full_probe"}, full=True)
            if final["classes"]:
                final["run"] = run_idx
                final["end_of_run"] = True
                kills[-1]["classes"] |= final["classes"]
                kills[-1]["details"] += final["details"]
        run_idx += 1
    n = len(kills)
    report: Dict[str, Any] = {"kills": n, "runs": run_idx, "seed": seed, "elapsed_s": round(time.perf_counter() - started, 1)}
    for cls in ("b", "c", "d", "o"):
        k = sum(1 for r in kills if cls in r["classes"])
        report[cls] = {"count": k, "wilson95": [round(x, 4) for x in wilson(k, n)]}
    k_clean = sum(1 for r in kills if not r["classes"])
    report["a"] = {"count": k_clean, "wilson95": [round(x, 4) for x in wilson(k_clean, n)]}
    hist: Dict[str, int] = {}
    for r in kills:
        hist[r["crash"]["point"]] = hist.get(r["crash"]["point"], 0) + 1
    report["crash_point_histogram"] = hist
    report["kills_with_stale_hwm_tmp"] = sum(1 for r in kills if r["crash"].get("hwm_tmp_files_present"))
    report["kills_with_orphan_tmp_before_recovery"] = sum(
        1 for r in kills if r["crash"].get("orphan_tmp_before_recovery"))
    report["orphan_tmp_before_recovery_total"] = sum(
        r["crash"].get("orphan_tmp_before_recovery", 0) for r in kills)
    report["orphan_tmp_reaped_total"] = sum(r["crash"].get("reaped_tmp", 0) for r in kills)
    report["kills_before_ready"] = sum(1 for r in kills if r["crash"].get("killed_before_ready"))
    kp: Dict[str, int] = {}
    for r in kills:
        if r["crash"].get("killpoint"):
            kp[r["crash"]["killpoint"]] = kp.get(r["crash"]["killpoint"], 0) + 1
    report["deterministic_killpoints"] = kp
    report["bad_cases"] = [
        {"run": r["run"], "crash": r["crash"], "classes": sorted(r["classes"]), "details": r["details"]}
        for r in kills if r["classes"]
    ]
    return report


# ---------------------------------------------------------------------------
# Small pytest version (40 kills)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="needs POSIX SIGKILL")
def test_crash_torture_44_kills_no_bad_outcomes(tmp_path: Path) -> None:
    # 2 x 12 deterministic flush-point kills + 20 random-time kills.
    report = run_torture(tmp_path, total_kills=20, kills_per_run=20, seed=20261026, flush_sweep=12)
    assert report["kills"] == 44
    assert report["bad_cases"] == [], json.dumps(report["bad_cases"], indent=1, default=str)[:4000]
    assert report["a"]["count"] == 44
    assert report["o"]["count"] == 0  # no orphan temp file survives any recovery
    kp = report["deterministic_killpoints"]
    assert sum(kp.values()) == 24
    # The sweep must reach the window between the ledger flush and the HWM replace, and the
    # window between os.replace and the directory flush.
    assert any(k.startswith("KILLPOINT after ledger") for k in kp)
    assert any(k.startswith("KILLPOINT before dir") for k in kp)
    assert report["crash_point_histogram"].get("between_ledger_fsync_and_hwm_replace", 0) >= 1


def test_wilson_interval_reference_values() -> None:
    lo, hi = wilson(0, 300)
    assert abs(lo) < 1e-12 and 0.0126 < hi < 0.0127
    lo, hi = wilson(5, 10)
    assert 0.2365 < lo < 0.2366 and 0.7634 < hi < 0.7635


def test_disk_crash_state_classifies_real_states(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    il = PreDispatchIntentInterlock(tmp_path / "ledger.jsonl", key, tmp_path / "state")
    assert disk_crash_state(tmp_path)["point"] == "no_hwm"
    il.record_intent(URI, TOOL, {"n": 0})
    assert disk_crash_state(tmp_path)["point"] == "after_hwm_replace_or_outside_append"
    ledger = tmp_path / "ledger.jsonl"
    line = ledger.read_bytes()
    with open(ledger, "ab") as fh:
        fh.write(line)  # complete record beyond the HWM (state left by a kill before the HWM replace)
    assert disk_crash_state(tmp_path)["point"] == "between_ledger_fsync_and_hwm_replace"
    with open(ledger, "ab") as fh:
        fh.write(line[: len(line) // 2])
    st = disk_crash_state(tmp_path)
    assert st["point"] == "inside_ledger_write_torn_tail" and st["torn_tail"] is True
