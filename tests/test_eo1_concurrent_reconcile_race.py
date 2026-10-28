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
tests/test_eo1_concurrent_reconcile_race.py
================================================================================
Multi-process race probe for src/eo1_reconciliation_adapter.Eo1ReconciliationAdapter.

Claim under test (pasted, unverified): "the state check (CONFIRMED vs EFFECT_INDETERMINATE)
and the execution branch have a TOCTOU race if two workers poll an indeterminate latch
simultaneously". The EO1 ledger is an append-only JSONL file serialised by fcntl.flock on
"<ledger>.lock" (no SQLite), so the probe exercises that real path.

Setup per round: one ledger dir, N_INTENTS intents latched EFFECT_INDETERMINATE through the
real PreDispatchIntentInterlock.dispatch: for even indices the target applied the write and
the acknowledgement was then lost (ConnectionResetError raised after the real HTTP 200); for
odd indices the connection failed before the write was sent. The target is a real stdlib
ThreadingHTTPServer on 127.0.0.1 in the pytest process that counts effects per CAID and is
shared by every worker process.

Race: 2-4 separate OS processes (subprocess, own interpreter, own interlock instance on the
same ledger) are released together by a stdin GO line. Each runs one reconcile pass and the
single re-submit of every intent it settled NOT_COMMITTED. Workers differ by schedule:
  w0  scans inside the pass (reconcile_pending), re-submits after the pass;
  w1  snapshots the latches BEFORE the barrier and settles that stale snapshot in a seeded
      shuffled order, re-submitting each NOT_COMMITTED immediately (the stale check -> act
      window the claim describes);
  w2  scans after the barrier, re-submits immediately after each settlement;
  w3  stale snapshot, re-submits after the pass.
Re-submitted writes (attempt >= 2) are held by the target for RESUBMIT_HOLD_S before commit,
which widens the window where a re-submit is in flight while other workers still settle.

Measured per basis: duplicate effects per CAID (> 1), original intents with more than one
CONTINUITY_RECEIPT (double settlement) or conflicting dispositions, ledger integrity after
the round (fresh strict interlock re-reads ledger + signed HWM, every record verifies, the
receipt hash chain is linear), worker exceptions, ALREADY_RESOLVED count (evidence that the
workers really contended).

Sensitivity control: the same harness with a check-then-act worker that bypasses the
interlock (read-back, second barrier, direct write) must produce duplicates, so the effect
counter and barrier can detect a TOCTOU when one exists.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from src.eo1_reconciliation_adapter import (  # noqa: E402
    Eo1ReconciliationAdapter,
    FenceOutcome,
    FenceRequest,
    ReadBackOutcome,
    ReadBackRequest,
    ReconcileReport,
    SettlementStatus,
    count_dispatch_attempts,
)
from src.eo1_write_before_execute import (  # noqa: E402
    DISPOSITION_KEY,
    GENESIS_CHAIN_TIP,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
    receipt_chain_hash,
    verify_ledger_file,
)

N_INTENTS = 20
PROCESS_COUNTS = (2, 3, 4, 2, 3, 4)  # one round each; the round index also varies the jitter seed
SEED = 42
CLIENT_TIMEOUT_S = 2.0
RESUBMIT_HOLD_S = 0.05
JITTER_S = 0.02
WORKER_TIMEOUT_S = 60
TOOL = "effect_target.append"
AUTHORITY = "eo1-concurrent-reconcile-race"


# ---------------------------------------------------------------------------
# Shared real HTTP effect target (lives in the pytest process)
# ---------------------------------------------------------------------------


class SharedEffectTarget:
    """
    POST /effect (X-AEIB-CAID, X-AEIB-Attempt): commits one effect unless a fence refuses the
    attempt (checked at commit time). Writes with attempt >= 2 are held RESUBMIT_HOLD_S first.
    GET /readback?caid=..: {"applied": bool}. POST /fence?caid=..&below=n: installs the fence and
    reports, atomically under the same lock, whether the effect is already applied.
    """

    def __init__(self, resubmit_hold_s: float = RESUBMIT_HOLD_S) -> None:
        self.lock = threading.Lock()
        self.effects: Dict[str, int] = {}
        self.fences: Dict[str, int] = {}
        self.fenced_refusals: Dict[str, int] = {}
        target = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, fmt: str, *args: Any) -> None:
                return None

            def _send(self, status: int, payload: Dict[str, Any]) -> None:
                data = json.dumps(payload).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                if parsed.path == "/fence":
                    query = parse_qs(parsed.query)
                    caid = query.get("caid", [""])[0]
                    below = int(query.get("below", ["0"])[0])
                    with target.lock:
                        target.fences[caid] = max(target.fences.get(caid, 0), below)
                        applied = target.effects.get(caid, 0) > 0
                    self._send(200, {"caid": caid, "fenced": True, "below": below, "applied": applied})
                    return
                caid = self.headers.get("X-AEIB-CAID", "")
                attempt = int(self.headers.get("X-AEIB-Attempt", "0"))
                if attempt >= 2:
                    time.sleep(resubmit_hold_s)
                with target.lock:
                    if attempt < target.fences.get(caid, 0):
                        target.fenced_refusals[caid] = target.fenced_refusals.get(caid, 0) + 1
                        committed = False
                    else:
                        target.effects[caid] = target.effects.get(caid, 0) + 1
                        committed = True
                self._send(200 if committed else 409, {"committed": committed})

            def do_GET(self) -> None:  # noqa: N802
                caid = parse_qs(urlparse(self.path).query).get("caid", [""])[0]
                with target.lock:
                    applied = target.effects.get(caid, 0) > 0
                self._send(200, {"caid": caid, "applied": applied})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def snapshot(self) -> Dict[str, int]:
        with self.lock:
            return dict(self.effects)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


# ---------------------------------------------------------------------------
# HTTP client helpers (used by the pytest process and by workers)
# ---------------------------------------------------------------------------


def effect_uri(port: int) -> str:
    return f"http://127.0.0.1:{port}/effect"


def post_effect(port: int, payload: Dict[str, Any], attempt: int) -> Dict[str, Any]:
    caid = compute_caid(payload)
    req = urllib.request.Request(
        effect_uri(port), data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "X-AEIB-CAID": caid, "X-AEIB-Attempt": str(attempt)},
    )
    with urllib.request.urlopen(req, timeout=CLIENT_TIMEOUT_S) as resp:
        return {"status_code": resp.status}


def readback_probe(port: int):
    def probe(request: ReadBackRequest) -> ReadBackOutcome:
        url = f"http://127.0.0.1:{port}/readback?caid={request.caid}"
        try:
            with urllib.request.urlopen(url, timeout=CLIENT_TIMEOUT_S) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError:
            return ReadBackOutcome.UNKNOWN
        if body.get("caid") != request.caid:
            return ReadBackOutcome.UNKNOWN
        return ReadBackOutcome.APPLIED if body.get("applied") is True else ReadBackOutcome.NOT_APPLIED

    return probe


def fence_probe(port: int):
    def fence(request: FenceRequest) -> FenceOutcome:
        url = f"http://127.0.0.1:{port}/fence?caid={request.caid}&below={request.below_attempt}"
        req = urllib.request.Request(url, data=b"", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=CLIENT_TIMEOUT_S) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError:
            return FenceOutcome.FAILED
        if body.get("caid") != request.caid or body.get("fenced") is not True:
            return FenceOutcome.FAILED
        return FenceOutcome.APPLIED if body.get("applied") is True else FenceOutcome.FENCED_NOT_APPLIED

    return fence


def payload_for(name: str) -> Dict[str, Any]:
    return {"op": "append_effect", "key": name}


def make_interlock(ledger_dir: Path, key: Ed25519PrivateKey, auto_recover: bool) -> PreDispatchIntentInterlock:
    return PreDispatchIntentInterlock(
        ledger_path=ledger_dir / "ledger.jsonl",
        output_state_dir=ledger_dir / "state",
        boundary_private_key=key,
        authority_id=AUTHORITY,
        auto_recover=auto_recover,
    )


def resubmit(il: PreDispatchIntentInterlock, port: int, payload: Dict[str, Any]) -> str:
    """The single fresh attempt after a NOT_COMMITTED settlement, through EO1 admission."""
    attempt = count_dispatch_attempts(il, compute_caid(payload)) + 1
    try:
        il.dispatch(effect_uri(port), TOOL, payload, dispatch_fn=lambda: post_effect(port, payload, attempt))
        return "SUCCESS"
    except LatchedCaidExecutionHaltedError:
        return "REFUSED"
    except RuntimeError:
        return "INDETERMINATE"


# ---------------------------------------------------------------------------
# Worker process
# ---------------------------------------------------------------------------


def _wait_line(expected: str) -> None:
    line = sys.stdin.readline().strip()
    if line != expected:
        raise RuntimeError(f"barrier expected {expected!r}, got {line!r}")


def worker_main(spec: Dict[str, Any]) -> Dict[str, Any]:
    ledger_dir = Path(spec["ledger_dir"])
    key = Ed25519PrivateKey.from_private_bytes(Path(spec["key_path"]).read_bytes())
    port = int(spec["port"])
    basis = spec["basis"]
    payloads = {compute_caid(payload_for(k)): payload_for(k) for k in spec["keys"]}
    rng = random.Random(f"{spec['seed']}:{spec['round']}:{spec['worker']}")
    il = make_interlock(ledger_dir, key, auto_recover=False)
    errors: List[str] = []
    out: Dict[str, Any] = {"worker": spec["worker"], "settlements": [], "resubmits": [], "errors": errors}

    if basis == "check_then_act":
        reads = {caid: readback_probe(port)(ReadBackRequest(caid, "", effect_uri(port), TOOL, 1)) for caid in sorted(payloads)}
        print("READY", flush=True)
        _wait_line("GO")
        print("READ", flush=True)
        _wait_line("GO2")
        writes = 0
        for caid, read in sorted(reads.items()):
            if read == ReadBackOutcome.NOT_APPLIED:
                post_effect(port, payloads[caid], attempt=0)
                writes += 1
        out["direct_writes"] = writes
        return out

    kwargs: Dict[str, Any] = {}
    if basis == "fence":
        kwargs["fence"] = fence_probe(port)
    elif basis == "unsafe":
        kwargs["trust_not_applied_without_fence"] = True
    else:
        raise ValueError(f"unknown basis {basis!r}")
    adapter = Eo1ReconciliationAdapter(
        il, readback_probe(port), max_probe_attempts=3, backoff_initial_s=0.01, backoff_max_s=0.05,
        probe_id=f"race-w{spec['worker']}", **kwargs,
    )
    stale = adapter.pending_latched() if spec["stale_snapshot"] else None
    out["stale_snapshot_size"] = None if stale is None else len(stale)
    print("READY", flush=True)
    _wait_line("GO")
    time.sleep(rng.uniform(0.0, JITTER_S))

    report = ReconcileReport()
    inline: List[Dict[str, Any]] = []

    def _settle_one(latch: Any) -> None:
        s = adapter.settle(latch)
        report.settlements.append(s)
        if spec["inline_resubmit"] and s.status == SettlementStatus.SETTLED_NOT_COMMITTED:
            # Re-submit immediately so it is in flight while other workers still settle.
            inline.append({"caid": s.caid, "outcome": resubmit(il, port, payloads[s.caid])})

    if stale is None:
        try:
            if spec["inline_resubmit"]:
                for _caid, latch in sorted(adapter.pending_latched().items()):
                    _settle_one(latch)
            else:
                report = adapter.reconcile_pending()
        except Exception as exc:  # recorded and asserted empty by the parent
            errors.append(f"reconcile {type(exc).__name__}: {exc}"[:300])
    else:
        order = sorted(stale.items())
        rng.shuffle(order)
        for _caid, latch in order:
            try:
                _settle_one(latch)
            except Exception as exc:
                errors.append(f"settle {type(exc).__name__}: {exc}"[:300])
    for s in report.settlements:
        out["settlements"].append({"caid": s.caid, "intent_id": s.intent_id, "status": s.status.value, "basis": s.basis})
    out["resubmits"].extend(inline)
    if not spec["inline_resubmit"]:
        for s in report.not_committed:
            try:
                out["resubmits"].append({"caid": s.caid, "outcome": resubmit(il, port, payloads[s.caid])})
            except Exception as exc:
                errors.append(f"resubmit {type(exc).__name__}: {exc}"[:300])
    return out


# ---------------------------------------------------------------------------
# Round driver (pytest process)
# ---------------------------------------------------------------------------


def _spawn(spec: Dict[str, Any]) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker", json.dumps(spec)],
        cwd=str(ROOT), env=env, text=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _expect(proc: subprocess.Popen, token: str) -> None:
    line = proc.stdout.readline() if proc.stdout else ""
    if line.strip() != token:
        _, err = proc.communicate(timeout=WORKER_TIMEOUT_S)
        raise AssertionError(f"worker sent {line!r} instead of {token!r}; stderr={err[-1200:]}")


def _release(procs: List[subprocess.Popen], token: str) -> None:
    for p in procs:
        assert p.stdin is not None
        p.stdin.write(token + "\n")
    for p in procs:
        assert p.stdin is not None
        p.stdin.flush()


def latch_round(ledger_dir: Path, key: Ed25519PrivateKey, target: SharedEffectTarget, keys: List[str]) -> List[str]:
    """Latches every key EFFECT_INDETERMINATE: even index applied-then-ack-lost, odd index never sent."""
    il = make_interlock(ledger_dir, key, auto_recover=True)
    caids = []
    for idx, name in enumerate(keys):
        payload = payload_for(name)
        caid = compute_caid(payload)
        attempt = count_dispatch_attempts(il, caid) + 1

        def wire(applied: bool = idx % 2 == 0, p: Dict[str, Any] = payload, a: int = attempt) -> Dict[str, Any]:
            if applied:
                post_effect(target.port, p, a)
                raise ConnectionResetError("acknowledgement lost after the target applied the write")
            raise ConnectionRefusedError("connection failed before the write was sent")

        try:
            il.dispatch(effect_uri(target.port), TOOL, payload, dispatch_fn=wire)
        except RuntimeError:
            pass
        assert il.is_caid_latched(caid)
        caids.append(caid)
    assert len(il.get_latched_caids()) == len(keys)
    return caids


def ledger_records(ledger_dir: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in (ledger_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def integrity_ok(ledger_dir: Path, key: Ed25519PrivateKey) -> List[str]:
    """Empty list when the ledger passes every check; otherwise the failures."""
    problems: List[str] = []
    try:
        fresh = make_interlock(ledger_dir, key, auto_recover=False)  # strict: HWM + signatures re-checked
        if fresh.get_integrity_violations():
            problems.append(f"tainted: {fresh.get_integrity_violations()}")
    except Exception as exc:
        problems.append(f"fresh interlock {type(exc).__name__}: {exc}")
    records = ledger_records(ledger_dir)
    try:
        if len(verify_ledger_file(ledger_dir / "ledger.jsonl", key.public_key())) != len(records):
            problems.append("verify_ledger_file count mismatch")
    except Exception as exc:
        problems.append(f"verify_ledger_file {type(exc).__name__}: {exc}")
    tip = GENESIS_CHAIN_TIP
    for rec in records:
        if rec["record_type"] != "CONTINUITY_RECEIPT":
            continue
        if rec["chain_tip"] != tip:
            problems.append(f"receipt chain fork at intent {rec['intent_id']}")
        tip = receipt_chain_hash(rec)
    return problems


def run_round(tmp_path: Path, key: Ed25519PrivateKey, key_path: Path, target: SharedEffectTarget,
              basis: str, round_idx: int, n_procs: int) -> Dict[str, Any]:
    ledger_dir = tmp_path / f"{basis}-r{round_idx}"
    ledger_dir.mkdir()
    keys = [f"{basis}-r{round_idx}-k{i}" for i in range(N_INTENTS)]
    caids = latch_round(ledger_dir, key, target, keys)
    applied_half = {c for i, c in enumerate(caids) if i % 2 == 0}
    original_intents = {rec["caid"]: rec["intent_id"] for rec in ledger_records(ledger_dir)
                        if rec["record_type"] == "DISPATCH_INTENT"}

    procs = []
    for w in range(n_procs):
        spec = {"ledger_dir": str(ledger_dir), "key_path": str(key_path), "port": target.port, "basis": basis,
                "keys": keys, "seed": SEED, "round": round_idx, "worker": w, "stale_snapshot": w % 2 == 1,
                "inline_resubmit": w in (1, 2)}
        procs.append(_spawn(spec))
    for p in procs:
        _expect(p, "READY")
    _release(procs, "GO")
    if basis == "check_then_act":
        for p in procs:
            _expect(p, "READ")
        _release(procs, "GO2")
    results, worker_errors = [], []
    for p in procs:
        out, err = p.communicate(timeout=WORKER_TIMEOUT_S)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        if p.returncode != 0 or not lines:
            worker_errors.append(f"rc={p.returncode} stderr={err[-800:]}")
            continue
        res = json.loads(lines[-1])
        worker_errors.extend(res["errors"])
        results.append(res)

    effects = target.snapshot()
    round_effects = {c: effects.get(c, 0) for c in caids}
    receipts_by_intent: Dict[str, List[str]] = {}
    for rec in ledger_records(ledger_dir):
        if rec["record_type"] == "CONTINUITY_RECEIPT":
            receipts_by_intent.setdefault(rec["intent_id"], []).append(rec["reconciliation_details"].get(DISPOSITION_KEY))
    orig_receipts = {c: receipts_by_intent.get(iid, []) for c, iid in original_intents.items()}
    statuses = Counter(s["status"] for r in results for s in r["settlements"])
    resubmits = Counter(x["outcome"] for r in results for x in r["resubmits"])
    final = make_interlock(ledger_dir, key, auto_recover=False)
    still_latched = sum(1 for c in final.get_latched_caids() if c in round_effects)

    # Drain: one sequential pass (same basis) settles whatever the race left latched.
    drained = dict(round_effects)
    latched_after_drain = still_latched
    if basis != "check_then_act":
        kwargs: Dict[str, Any] = ({"fence": fence_probe(target.port)} if basis == "fence"
                                  else {"trust_not_applied_without_fence": True})
        drain = Eo1ReconciliationAdapter(final, readback_probe(target.port), backoff_initial_s=0.01, **kwargs)
        payloads = {compute_caid(payload_for(k)): payload_for(k) for k in keys}
        for s in drain.reconcile_pending().not_committed:
            resubmit(final, target.port, payloads[s.caid])
        after = target.snapshot()
        drained = {c: after.get(c, 0) for c in caids}
        latched_after_drain = sum(1 for c in make_interlock(ledger_dir, key, False).get_latched_caids() if c in drained)
    return {
        "basis": basis,
        "round": round_idx,
        "processes": n_procs,
        "intents": len(caids),
        "duplicate_caids": sum(1 for n in round_effects.values() if n > 1),
        "excess_effects": sum(n - 1 for n in round_effects.values() if n > 1),
        "applied_exactly_once": sum(1 for n in round_effects.values() if n == 1),
        "applied_half_effects": sorted({round_effects[c] for c in applied_half}),
        "double_settled_intents": sum(1 for v in orig_receipts.values() if len(v) > 1),
        "conflicting_settlements": sum(1 for v in orig_receipts.values() if len(set(v)) > 1),
        "unsettled_original_intents": sum(1 for v in orig_receipts.values() if len(v) == 0),
        "statuses": dict(statuses),
        "resubmits": dict(resubmits),
        "fenced_refusals": sum(target.fenced_refusals.get(c, 0) for c in caids),
        "still_latched_after": still_latched,
        "duplicate_caids_after_drain": sum(1 for n in drained.values() if n > 1),
        "applied_exactly_once_after_drain": sum(1 for n in drained.values() if n == 1),
        "still_latched_after_drain": latched_after_drain,
        "direct_writes": sum(r.get("direct_writes", 0) for r in results),
        "integrity_problems": integrity_ok(ledger_dir, key),
        "worker_errors": worker_errors,
    }


def _key_file(tmp_path: Path, key: Ed25519PrivateKey) -> Path:
    path = tmp_path / "boundary_key.bin"
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(raw)
    return path


def _summarise(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    keys = ("duplicate_caids", "excess_effects", "double_settled_intents", "conflicting_settlements",
            "unsettled_original_intents", "fenced_refusals", "still_latched_after", "applied_exactly_once",
            "duplicate_caids_after_drain", "applied_exactly_once_after_drain", "still_latched_after_drain",
            "direct_writes")
    summary = {k: sum(r[k] for r in rounds) for k in keys}
    summary["rounds"] = len(rounds)
    summary["processes"] = [r["processes"] for r in rounds]
    summary["intents"] = sum(r["intents"] for r in rounds)
    summary["already_resolved"] = sum(r["statuses"].get(SettlementStatus.ALREADY_RESOLVED.value, 0) for r in rounds)
    summary["worker_errors"] = sum(len(r["worker_errors"]) for r in rounds)
    summary["integrity_problems"] = sum(len(r["integrity_problems"]) for r in rounds)
    return summary


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def shared_target():
    t = SharedEffectTarget()
    yield t
    t.stop()


@pytest.mark.parametrize("basis", ["fence", "unsafe"])
def test_concurrent_reconcilers_produce_no_duplicate_or_double_settlement(tmp_path, shared_target, basis):
    key = Ed25519PrivateKey.generate()
    key_path = _key_file(tmp_path, key)
    rounds = [run_round(tmp_path, key, key_path, shared_target, basis, i, n) for i, n in enumerate(PROCESS_COUNTS)]
    summary = _summarise(rounds)
    print(f"\nEO1_CONCURRENT_RECONCILE basis={basis} summary={json.dumps(summary, sort_keys=True)}")
    for r in rounds:
        print(f"  round={r['round']} procs={r['processes']} statuses={r['statuses']} resubmits={r['resubmits']} "
              f"dup={r['duplicate_caids']} double={r['double_settled_intents']} latched_after={r['still_latched_after']}")

    for r in rounds:
        assert r["worker_errors"] == [], r["worker_errors"]
        assert r["integrity_problems"] == [], r["integrity_problems"]
        assert r["duplicate_caids"] == 0 and r["excess_effects"] == 0, r
        assert r["double_settled_intents"] == 0 and r["conflicting_settlements"] == 0, r
        assert r["unsettled_original_intents"] == 0, r
        assert r["applied_half_effects"] == [1], r  # applied-then-ack-lost writes are never re-applied
        assert r["direct_writes"] == 0
        # Fail-closed liveness: whatever the race left latched settles in one sequential pass.
        assert r["duplicate_caids_after_drain"] == 0, r
        assert r["applied_exactly_once_after_drain"] == N_INTENTS and r["still_latched_after_drain"] == 0, r
    # The probe must actually contend: stale-snapshot workers hit intents settled by another process.
    assert summary["already_resolved"] >= 1, summary


def test_check_then_act_control_detects_duplicates(tmp_path, shared_target):
    """Sensitivity control: bypassing the interlock (read-back then write) duplicates under the same harness."""
    key = Ed25519PrivateKey.generate()
    key_path = _key_file(tmp_path, key)
    n_procs = 3
    r = run_round(tmp_path, key, key_path, shared_target, "check_then_act", 0, n_procs)
    print(f"\nEO1_CONCURRENT_RECONCILE basis=check_then_act summary={json.dumps(_summarise([r]), sort_keys=True)}")
    not_applied = N_INTENTS // 2
    assert r["worker_errors"] == [] and r["integrity_problems"] == []
    assert r["direct_writes"] == n_procs * not_applied
    assert r["duplicate_caids"] == not_applied
    assert r["excess_effects"] == (n_procs - 1) * not_applied


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        print(json.dumps(worker_main(json.loads(sys.argv[2]))), flush=True)
        sys.exit(0)
    sys.exit(pytest.main([__file__, "-q", "-s"]))
