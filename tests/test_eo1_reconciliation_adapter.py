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
tests/test_eo1_reconciliation_adapter.py
================================================================================
Evaluates src/eo1_reconciliation_adapter.Eo1ReconciliationAdapter against the REAL
PreDispatchIntentInterlock (real ledger, fsync, flock, Ed25519 receipts) and a REAL local
HTTP target (stdlib ThreadingHTTPServer on 127.0.0.1) that records effects by CAID and
exposes a read-back endpoint. No unittest.mock is used. Probe sleeps are injected (a manual
clock), so the adapter performs no real sleeps; the target's own response holds are real.

The target lives in this file (not benchmarks/) so the mutation gate's shadow root, which
copies only src/ and tests/, can run this module.
"""

from __future__ import annotations

import dataclasses
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eo1_reconciliation_adapter import (  # noqa: E402
    BASIS_DEADLINE,
    BASIS_FENCE,
    BASIS_FENCE_OBSERVED_APPLIED,
    BASIS_READ_BACK_APPLIED,
    BASIS_UNSAFE_TRUST,
    REASON_DEADLINE_NOT_ELAPSED,
    REASON_FENCE_FAILED,
    REASON_NOT_APPLIED_UNFENCED,
    RECONCILER_ID,
    DeadlineContract,
    Eo1ReconciliationAdapter,
    FenceOutcome,
    FenceRequest,
    ReadBackOutcome,
    ReadBackRequest,
    ReconcileReport,
    SettlementStatus,
    _coerce_fence,
    _coerce_outcome,
    count_dispatch_attempts,
    intent_dispatched_at,
)
from src.eo1_write_before_execute import (  # noqa: E402
    DISPOSITION_KEY,
    CaidAlreadyCommittedError,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
    verify_continuity_receipt,
)

CLIENT_TIMEOUT_S = 0.2
HOLD_S = 0.6
LATE_COMMIT_S = 0.5  # late commit lands after the read-back (~0.2 s) and after the retry
TOOL = "effect_target.append"


# ---------------------------------------------------------------------------
# Real local HTTP effect target with CAID read-back
# ---------------------------------------------------------------------------


class CaidTarget:
    """
    Write: POST /effect (X-AEIB-CAID, optional X-AEIB-Attempt). Read-back: GET /readback?caid=...
    Fence: POST /fence?caid=..&below=n -> refuses any write for caid with attempt < n (checked at
    commit time) and reports, atomically, whether the effect was already applied.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.effects: Dict[str, int] = {}
        self.write_mode: Dict[str, str] = {}  # caid -> "ack_lost" | "pre_timeout" | "late" (first write only)
        self.readback_mode: Dict[str, str] = {}  # caid -> "hold" | "error503"
        self.fence_mode: Dict[str, str] = {}  # caid -> "unsupported" | "hold"
        self.fences: Dict[str, int] = {}
        self.fenced_refusals: Dict[str, int] = {}
        self.late_done: Dict[str, threading.Event] = {}
        self.writes_seen: Dict[str, int] = {}
        self.readbacks: List[str] = []
        self.fence_requests: List[Dict[str, Any]] = []
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

            def _commit(self, caid: str, attempt: int) -> bool:
                with target.lock:
                    if attempt < target.fences.get(caid, 0):
                        target.fenced_refusals[caid] = target.fenced_refusals.get(caid, 0) + 1
                        return False
                    target.effects[caid] = target.effects.get(caid, 0) + 1
                    return True

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/fence":
                    self._fence(parse_qs(parsed.query))
                    return
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                caid = self.headers.get("X-AEIB-CAID", "")
                attempt = int(self.headers.get("X-AEIB-Attempt", "0"))
                with target.lock:
                    target.writes_seen[caid] = target.writes_seen.get(caid, 0) + 1
                    first = target.writes_seen[caid] == 1
                mode = target.write_mode.get(caid) if first else None
                if mode == "pre_timeout":
                    time.sleep(HOLD_S)
                    return
                if mode == "late":
                    time.sleep(LATE_COMMIT_S)  # still in flight while read-back says NOT_APPLIED
                    applied = self._commit(caid, attempt)
                    target.late_done.setdefault(caid, threading.Event()).set()
                    self._send(200, {"committed": applied})
                    return
                applied = self._commit(caid, attempt)
                if mode == "ack_lost":
                    time.sleep(HOLD_S)
                self._send(200 if applied else 409, {"committed": applied})

            def _fence(self, query: Dict[str, List[str]]) -> None:
                caid = query.get("caid", [""])[0]
                below = int(query.get("below", ["0"])[0])
                mode = target.fence_mode.get(caid)
                with target.lock:
                    target.fence_requests.append({"caid": caid, "below": below})
                if mode == "unsupported":
                    self._send(404, {"error": "fence not supported"})
                    return
                if mode == "hold":
                    time.sleep(HOLD_S)
                    return
                with target.lock:
                    target.fences[caid] = max(target.fences.get(caid, 0), below)
                    applied = target.effects.get(caid, 0) > 0
                self._send(200, {"caid": caid, "fenced": True, "below": below, "applied": applied})

            def do_GET(self) -> None:  # noqa: N802
                caid = parse_qs(urlparse(self.path).query).get("caid", [""])[0]
                with target.lock:
                    target.readbacks.append(caid)
                    applied = target.effects.get(caid, 0) > 0
                mode = target.readback_mode.get(caid)
                if mode == "hold":
                    time.sleep(HOLD_S)
                    return
                if mode == "error503":
                    self._send(503, {"error": "unavailable"})
                    return
                self._send(200, {"caid": caid, "applied": applied})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def uri(self) -> str:
        return f"http://127.0.0.1:{self.port}/effect"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def http_fence_probe(port: int):
    """Real HTTP fence probe: FENCED_NOT_APPLIED / APPLIED on a 200 echo, FAILED otherwise; errors propagate."""

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


def http_readback_probe(port: int):
    """Real HTTP read-back probe; transport errors propagate (the adapter treats them as UNKNOWN)."""

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


class ManualClock:
    """Injected monotonic clock; sleep() advances it instead of blocking."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: List[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class SequenceProbe:
    """Returns scripted outcomes in order (last one repeats) and records every request."""

    def __init__(self, outcomes: List[Any]) -> None:
        self.outcomes = list(outcomes)
        self.requests: List[ReadBackRequest] = []

    def __call__(self, request: ReadBackRequest) -> Any:
        self.requests.append(request)
        idx = min(len(self.requests) - 1, len(self.outcomes) - 1)
        item = self.outcomes[idx]
        if isinstance(item, BaseException):
            raise item
        return item


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def target():
    t = CaidTarget()
    yield t
    t.stop()


@pytest.fixture()
def key():
    return Ed25519PrivateKey.generate()


def make_interlock(tmp_path: Path, key: Ed25519PrivateKey, auto_recover: bool = True) -> PreDispatchIntentInterlock:
    return PreDispatchIntentInterlock(
        ledger_path=tmp_path / "ledger.jsonl",
        output_state_dir=tmp_path / "state",
        boundary_private_key=key,
        authority_id="eo1-reconcile-test",
        auto_recover=auto_recover,
    )


def payload_for(name: str) -> Dict[str, Any]:
    return {"op": "append_effect", "key": name}


def send(interlock: PreDispatchIntentInterlock, target: CaidTarget, name: str, attempt_token: bool = False) -> str:
    payload = payload_for(name)
    caid = compute_caid(payload)
    headers = {"Content-Type": "application/json", "X-AEIB-CAID": caid}
    if attempt_token:
        headers["X-AEIB-Attempt"] = str(count_dispatch_attempts(interlock, caid) + 1)

    def wire() -> Dict[str, Any]:
        req = urllib.request.Request(
            target.uri, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=CLIENT_TIMEOUT_S) as resp:
            return {"status_code": resp.status}

    try:
        interlock.dispatch(target.uri, TOOL, payload, dispatch_fn=wire)
        return "SUCCESS"
    except LatchedCaidExecutionHaltedError:
        return "REFUSED"
    except RuntimeError:
        return "INDETERMINATE"


def latch_with_fault(interlock, target, name: str, mode: str, attempt_token: bool = False) -> str:
    caid = compute_caid(payload_for(name))
    target.write_mode[caid] = mode
    assert send(interlock, target, name, attempt_token) == "INDETERMINATE"
    assert interlock.is_caid_latched(caid)
    return caid


def ledger_receipts(tmp_path: Path, caid: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for line in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["record_type"] == "CONTINUITY_RECEIPT" and (caid is None or rec["caid"] == caid):
            out.append(rec)
    return out


def adapter_for(interlock, probe, clock: Optional[ManualClock] = None, **kw: Any) -> Eo1ReconciliationAdapter:
    clock = clock or ManualClock()
    return Eo1ReconciliationAdapter(interlock, probe, clock=clock.clock, sleep=clock.sleep, **kw)


# ---------------------------------------------------------------------------
# APPLIED / NOT_APPLIED / UNKNOWN through real HTTP + real interlock
# ---------------------------------------------------------------------------


def test_applied_settles_committed_and_blocks_resend(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "applied", "ack_lost")
    assert target.effects[caid] == 1
    adapter = adapter_for(il, http_readback_probe(target.port), probe_id="http-readback")

    report = adapter.reconcile_pending()

    assert len(report.settlements) == 1
    s = report.settlements[0]
    assert s.status == SettlementStatus.SETTLED_COMMITTED
    assert s.read_back == ReadBackOutcome.APPLIED
    assert s.probe_attempts == 1 and s.total_probe_attempts == 1 and s.probe_errors == []
    assert report.committed == [s] and report.not_committed == [] and report.still_latched == []
    assert report.probes_issued == 1
    rec = ledger_receipts(tmp_path, caid)
    assert len(rec) == 1
    assert verify_continuity_receipt(rec[0], key.public_key()) is True
    details = rec[0]["reconciliation_details"]
    assert details[DISPOSITION_KEY] == "COMMITTED"
    assert details["reconciler"] == RECONCILER_ID
    assert details["read_back_outcome"] == "APPLIED"
    assert details["probe_id"] == "http-readback"
    assert details["probe_attempts"] == 1
    assert details["settlement_basis"] == BASIS_READ_BACK_APPLIED and s.basis == BASIS_READ_BACK_APPLIED
    assert details["target_uri"] == target.uri and details["tool_name"] == TOOL
    assert s.receipt is not None and s.receipt.intent_id == rec[0]["intent_id"]
    assert not il.is_caid_latched(caid) and il.is_caid_committed(caid)
    with pytest.raises(CaidAlreadyCommittedError):
        il.dispatch(target.uri, TOOL, payload_for("applied"), dispatch_fn=lambda: {"x": 1})
    assert send(il, target, "applied") == "REFUSED"
    assert target.effects[caid] == 1
    assert target.writes_seen[caid] == 1


def test_not_applied_with_unsafe_opt_in_settles_not_committed_and_allows_one_fresh_attempt(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "absent", "pre_timeout")
    assert target.effects.get(caid, 0) == 0
    adapter = adapter_for(il, http_readback_probe(target.port), trust_not_applied_without_fence=True)

    report = adapter.reconcile_pending()

    s = report.settlements[0]
    assert s.status == SettlementStatus.SETTLED_NOT_COMMITTED
    assert s.read_back == ReadBackOutcome.NOT_APPLIED
    assert s.basis == BASIS_UNSAFE_TRUST and s.reason is None and s.fence is None
    assert report.not_committed == [s] and report.committed == []
    rec = ledger_receipts(tmp_path, caid)
    assert len(rec) == 1 and rec[0]["reconciliation_details"][DISPOSITION_KEY] == "NOT_COMMITTED"
    assert rec[0]["reconciliation_details"]["settlement_basis"] == BASIS_UNSAFE_TRUST
    assert "fence_outcome" not in rec[0]["reconciliation_details"]
    assert verify_continuity_receipt(rec[0], key.public_key()) is True
    assert not il.is_caid_latched(caid) and not il.is_caid_committed(caid)
    assert send(il, target, "absent") == "SUCCESS"
    assert target.effects[caid] == 1
    assert send(il, target, "absent") == "REFUSED"
    assert target.effects[caid] == 1
    assert adapter.reconcile_pending().settlements == []


def test_unknown_stays_latched_with_bounded_backoff_and_no_receipt(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "unknown", "ack_lost")
    target.readback_mode[caid] = "error503"
    clock = ManualClock()
    adapter = adapter_for(il, http_readback_probe(target.port), clock=clock, max_probe_attempts=3,
                          backoff_initial_s=0.05, backoff_factor=2.0, backoff_max_s=1.0)

    report = adapter.reconcile_pending()

    s = report.settlements[0]
    assert s.status == SettlementStatus.LATCHED_UNKNOWN
    assert s.read_back == ReadBackOutcome.UNKNOWN and s.receipt is None
    assert s.probe_attempts == 3 and adapter.attempts_for(s.intent_id) == 3
    assert clock.sleeps == pytest.approx([0.05, 0.1])
    assert s.elapsed_ms == 150
    assert report.still_latched == [s] and report.probes_issued == 3
    assert target.readbacks.count(caid) == 3
    assert ledger_receipts(tmp_path, caid) == []
    assert il.is_caid_latched(caid)
    assert send(il, target, "unknown") == "REFUSED"
    assert target.effects[caid] == 1


def test_probe_timeout_stays_latched_not_duplicated(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "rb-timeout", "ack_lost")
    target.readback_mode[caid] = "hold"
    adapter = adapter_for(il, http_readback_probe(target.port), max_probe_attempts=2)

    s = adapter.reconcile_pending().settlements[0]

    assert s.status == SettlementStatus.LATCHED_UNKNOWN
    assert len(s.probe_errors) == 2
    assert all(("timed out" in e.lower()) or ("timeout" in e.lower()) for e in s.probe_errors)
    assert il.is_caid_latched(caid) and ledger_receipts(tmp_path, caid) == []
    assert send(il, target, "rb-timeout") == "REFUSED"
    assert target.effects[caid] == 1 and target.writes_seen[caid] == 1


# ---------------------------------------------------------------------------
# Restart / concurrency idempotency
# ---------------------------------------------------------------------------


def test_restart_mid_reconcile_is_idempotent(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    a = latch_with_fault(il, target, "r-a", "ack_lost")
    b = latch_with_fault(il, target, "r-b", "pre_timeout")
    c = latch_with_fault(il, target, "r-c", "ack_lost")
    http_probe = http_readback_probe(target.port)

    # Pass 1 settles only A, then the "process" dies while probing B (BaseException escapes).
    first = adapter_for(il, http_probe).reconcile_pending(caids=[a])
    assert [x.caid for x in first.settlements] == [a]
    crash = SequenceProbe([KeyboardInterrupt("killed mid-probe")])
    with pytest.raises(KeyboardInterrupt):
        adapter_for(il, crash).reconcile_pending(caids=[b])
    assert il.is_caid_latched(b) and ledger_receipts(tmp_path, b) == []

    # Restart: fresh interlock (startup recovery) + fresh adapter on the same ledger.
    il2 = make_interlock(tmp_path, key, auto_recover=True)
    assert not il2.is_caid_latched(a) and il2.is_caid_latched(b) and il2.is_caid_latched(c)
    seen: List[str] = []

    def recording_probe(req: ReadBackRequest) -> ReadBackOutcome:
        seen.append(req.caid)
        return http_probe(req)

    second = adapter_for(il2, recording_probe, fence=http_fence_probe(target.port)).reconcile_pending()
    assert a not in seen and sorted(seen) == sorted([b, c])
    status = {x.caid: x.status for x in second.settlements}
    assert status == {b: SettlementStatus.SETTLED_NOT_COMMITTED, c: SettlementStatus.SETTLED_COMMITTED}
    assert {x.caid: x.basis for x in second.settlements} == {b: BASIS_FENCE, c: BASIS_READ_BACK_APPLIED}
    for caid in (a, b, c):
        assert len(ledger_receipts(tmp_path, caid)) == 1
    third = adapter_for(make_interlock(tmp_path, key), recording_probe).reconcile_pending()
    assert third.settlements == [] and len(seen) == 2


def test_concurrent_settlement_writes_one_receipt(tmp_path, key, target):
    il_a = make_interlock(tmp_path, key)
    caid = latch_with_fault(il_a, target, "race", "ack_lost")
    il_b = make_interlock(tmp_path, key, auto_recover=False)
    probe = http_readback_probe(target.port)
    adapter_b = adapter_for(il_b, probe)
    stale_latch = adapter_b.pending_latched()[caid]

    assert adapter_for(il_a, probe).reconcile_pending().committed[0].caid == caid
    late = adapter_b.settle(stale_latch)

    assert late.status == SettlementStatus.ALREADY_RESOLVED and late.receipt is None
    assert late.read_back == ReadBackOutcome.APPLIED
    assert len(ledger_receipts(tmp_path, caid)) == 1


def test_caids_filter_and_unlatched_unresolved_skipped(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    a = latch_with_fault(il, target, "f-a", "ack_lost")
    b = latch_with_fault(il, target, "f-b", "ack_lost")
    # An unresolved intent with no latch (possibly in flight elsewhere) must not be scanned.
    inflight = il.record_intent(target.uri, TOOL, payload_for("f-inflight"))
    probe = SequenceProbe([ReadBackOutcome.APPLIED])
    report = adapter_for(il, probe).reconcile_pending(caids=[b])
    assert [s.caid for s in report.settlements] == [b]
    assert il.is_caid_latched(a) and not il.is_caid_latched(b)
    rest = adapter_for(il, probe).reconcile_pending()
    assert [s.caid for s in rest.settlements] == [a]
    assert inflight.caid not in [r.caid for r in probe.requests]
    assert il.get_unresolved_intent_ids(inflight.caid) == [inflight.intent_id]


# ---------------------------------------------------------------------------
# Probe loop semantics (scripted probe, real interlock)
# ---------------------------------------------------------------------------


def test_unknown_then_applied_retries_and_records_attempts(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "retry", "ack_lost")
    probe = SequenceProbe([ConnectionResetError("reset"), "unknown", "APPLIED"])
    clock = ManualClock()
    s = adapter_for(il, probe, clock=clock, max_probe_attempts=3).reconcile_pending().settlements[0]
    assert s.status == SettlementStatus.SETTLED_COMMITTED
    assert s.probe_attempts == 3
    assert s.probe_errors == ["ConnectionResetError: reset"]
    assert [r.attempt for r in probe.requests] == [1, 2, 3]
    assert all(r.caid == caid and r.tool_name == TOOL and r.target_uri == target.uri for r in probe.requests)
    assert ledger_receipts(tmp_path, caid)[0]["reconciliation_details"]["probe_errors"] == ["ConnectionResetError: reset"]
    assert len(clock.sleeps) == 2


def test_not_applied_confirmations_require_consecutive_reads(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "confirm", "pre_timeout")
    probe = SequenceProbe(["NOT_APPLIED", "UNKNOWN", "NOT_APPLIED", "NOT_APPLIED"])
    s = adapter_for(il, probe, max_probe_attempts=4, not_applied_confirmations=2,
                    trust_not_applied_without_fence=True).reconcile_pending().settlements[0]
    assert s.status == SettlementStatus.SETTLED_NOT_COMMITTED and s.probe_attempts == 4

    il2 = make_interlock(tmp_path / "b", key)
    latch_with_fault(il2, target, "confirm-short", "pre_timeout")
    probe2 = SequenceProbe(["NOT_APPLIED", "UNKNOWN", "NOT_APPLIED"])
    s2 = adapter_for(il2, probe2, max_probe_attempts=3, not_applied_confirmations=2).reconcile_pending().settlements[0]
    assert s2.status == SettlementStatus.LATCHED_UNKNOWN and s2.probe_attempts == 3

    il3 = make_interlock(tmp_path / "c", key)
    latch_with_fault(il3, target, "confirm-applied", "pre_timeout")
    probe3 = SequenceProbe(["NOT_APPLIED", "APPLIED"])
    s3 = adapter_for(il3, probe3, max_probe_attempts=3, not_applied_confirmations=2).reconcile_pending().settlements[0]
    assert s3.status == SettlementStatus.SETTLED_COMMITTED and s3.probe_attempts == 2


def test_lifetime_probe_cap_across_passes(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "cap", "ack_lost")
    probe = SequenceProbe([ReadBackOutcome.UNKNOWN])
    adapter = adapter_for(il, probe, max_probe_attempts=3, max_total_probes_per_intent=2)
    first = adapter.reconcile_pending().settlements[0]
    assert first.probe_attempts == 2 and first.total_probe_attempts == 2
    second = adapter.reconcile_pending().settlements[0]
    assert second.status == SettlementStatus.LATCHED_UNKNOWN
    assert second.probe_attempts == 0 and len(probe.requests) == 2


def test_backoff_is_capped(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "backoff", "ack_lost")
    clock = ManualClock()
    adapter = adapter_for(il, SequenceProbe(["UNKNOWN"]), clock=clock, max_probe_attempts=4,
                          backoff_initial_s=0.5, backoff_factor=3.0, backoff_max_s=1.0)
    s = adapter.reconcile_pending().settlements[0]
    assert clock.sleeps == pytest.approx([0.5, 1.0, 1.0])
    assert s.elapsed_ms == 2500


def test_default_parameters():
    probe = SequenceProbe(["UNKNOWN"])
    adapter = Eo1ReconciliationAdapter(None, probe)  # type: ignore[arg-type]
    assert adapter.max_probe_attempts == 3
    assert adapter.not_applied_confirmations == 1
    assert adapter.max_total_probes_per_intent is None
    assert adapter.backoff_initial_s == 0.05 and adapter.backoff_factor == 2.0 and adapter.backoff_max_s == 1.0
    assert adapter._backoff_delay(0) == pytest.approx(adapter.backoff_initial_s)
    assert adapter._backoff_delay(1) == pytest.approx(adapter.backoff_initial_s * adapter.backoff_factor)
    assert adapter._backoff_delay(10) == pytest.approx(adapter.backoff_max_s)
    assert adapter.probe_id == "readback"


@pytest.mark.parametrize("kwargs", [
    {"max_probe_attempts": 0},
    {"not_applied_confirmations": 0},
    {"max_probe_attempts": 2, "not_applied_confirmations": 3},
    {"backoff_initial_s": -0.1},
    {"backoff_max_s": -1.0},
    {"backoff_factor": 0.5},
    {"max_total_probes_per_intent": 0},
])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        Eo1ReconciliationAdapter(None, SequenceProbe(["UNKNOWN"]), **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("kwargs", [
    {"max_probe_attempts": 1},
    {"max_probe_attempts": 2, "not_applied_confirmations": 2},
    {"backoff_initial_s": 0.0, "backoff_max_s": 0.0, "backoff_factor": 1.0},
    {"max_total_probes_per_intent": 1},
])
def test_boundary_configuration_accepted(kwargs):
    Eo1ReconciliationAdapter(None, SequenceProbe(["UNKNOWN"]), **kwargs)  # type: ignore[arg-type]


def test_coerce_outcome():
    assert _coerce_outcome(ReadBackOutcome.NOT_APPLIED) is ReadBackOutcome.NOT_APPLIED
    assert _coerce_outcome(" applied ") is ReadBackOutcome.APPLIED
    assert _coerce_outcome("not_applied") is ReadBackOutcome.NOT_APPLIED
    assert _coerce_outcome("maybe") is ReadBackOutcome.UNKNOWN
    assert _coerce_outcome(True) is ReadBackOutcome.UNKNOWN
    assert _coerce_outcome(None) is ReadBackOutcome.UNKNOWN


def test_empty_report_properties():
    r = ReconcileReport()
    assert r.probes_issued == 0 and r.committed == [] and r.not_committed == [] and r.still_latched == []


def test_probe_request_and_settlement_are_immutable(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "frozen", "ack_lost")
    probe = SequenceProbe(["APPLIED"])
    s = adapter_for(il, probe).reconcile_pending().settlements[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        probe.requests[0].caid = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.status = SettlementStatus.LATCHED_UNKNOWN  # type: ignore[misc]


def test_long_probe_error_is_truncated(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "longerr", "ack_lost")
    s = adapter_for(il, SequenceProbe([OSError("x" * 500)]), max_probe_attempts=1).reconcile_pending().settlements[0]
    assert len(s.probe_errors[0]) == 200 and s.probe_errors[0].startswith("OSError: xxx")


def test_socket_timeout_class_is_reported(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "sockto", "ack_lost")
    s = adapter_for(il, SequenceProbe([socket.timeout("timed out")]), max_probe_attempts=1).reconcile_pending().settlements[0]
    assert s.status == SettlementStatus.LATCHED_UNKNOWN
    assert s.probe_errors[0].endswith("timed out")


# ---------------------------------------------------------------------------
# Fail-closed NOT_APPLIED default, late commit, attempt fencing, deadline
# (LIMBO arXiv:2609.29095 Prop. 1; MCP #3394 row C)
# ---------------------------------------------------------------------------


def test_default_not_applied_stays_latched_unfenced(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "unfenced", "pre_timeout")
    report = adapter_for(il, http_readback_probe(target.port)).reconcile_pending()
    s = report.settlements[0]
    assert s.status == SettlementStatus.LATCHED_NOT_APPLIED_UNFENCED
    assert s.read_back == ReadBackOutcome.NOT_APPLIED
    assert s.reason == REASON_NOT_APPLIED_UNFENCED and s.basis is None and s.receipt is None
    assert report.unfenced == [s] and report.still_latched == [s] and report.not_committed == []
    assert ledger_receipts(tmp_path, caid) == []
    assert il.is_caid_latched(caid)
    assert send(il, target, "unfenced") == "REFUSED"
    assert target.effects.get(caid, 0) == 0


def test_late_commit_with_unsafe_opt_in_duplicates(tmp_path, key, target):
    """Falsification: in flight + read-back NOT_APPLIED + opt-in retry + late commit = duplicate."""
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "late-dup", "late")
    s = adapter_for(il, http_readback_probe(target.port), trust_not_applied_without_fence=True).reconcile_pending().settlements[0]
    assert s.status == SettlementStatus.SETTLED_NOT_COMMITTED and s.basis == BASIS_UNSAFE_TRUST
    assert send(il, target, "late-dup") == "SUCCESS"
    assert target.late_done.setdefault(caid, threading.Event()).wait(5.0)
    assert target.effects[caid] == 2


def test_late_commit_is_refused_after_fence(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "late-fenced", "late", attempt_token=True)
    assert count_dispatch_attempts(il, caid) == 1
    report = adapter_for(il, http_readback_probe(target.port), fence=http_fence_probe(target.port)).reconcile_pending()
    s = report.settlements[0]
    assert s.status == SettlementStatus.SETTLED_NOT_COMMITTED
    assert s.basis == BASIS_FENCE and s.fence == FenceOutcome.FENCED_NOT_APPLIED and s.fence_below_attempt == 2
    assert target.fence_requests == [{"caid": caid, "below": 2}]
    details = ledger_receipts(tmp_path, caid)[0]["reconciliation_details"]
    assert details["settlement_basis"] == BASIS_FENCE
    assert details["fence_outcome"] == "FENCED_NOT_APPLIED" and details["fence_below_attempt"] == 2
    assert send(il, target, "late-fenced", attempt_token=True) == "SUCCESS"
    assert count_dispatch_attempts(il, caid) == 2
    assert target.late_done.setdefault(caid, threading.Event()).wait(5.0)
    assert target.effects[caid] == 1
    assert target.fenced_refusals[caid] == 1


def test_fence_observes_late_commit_and_settles_committed(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "fence-sees", "ack_lost", attempt_token=True)
    # Read-back said NOT_APPLIED (stale), but the effect is present when the fence is installed.
    report = adapter_for(il, SequenceProbe([ReadBackOutcome.NOT_APPLIED]), fence=http_fence_probe(target.port)).reconcile_pending()
    s = report.settlements[0]
    assert s.status == SettlementStatus.SETTLED_COMMITTED
    assert s.basis == BASIS_FENCE_OBSERVED_APPLIED and s.fence == FenceOutcome.APPLIED
    assert ledger_receipts(tmp_path, caid)[0]["reconciliation_details"][DISPOSITION_KEY] == "COMMITTED"
    assert il.is_caid_committed(caid)
    assert send(il, target, "fence-sees", attempt_token=True) == "REFUSED"
    assert target.effects[caid] == 1


@pytest.mark.parametrize("mode", ["unsupported", "hold"])
def test_fence_unsupported_or_timeout_stays_latched(tmp_path, key, target, mode):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, f"fence-{mode}", "pre_timeout")
    target.fence_mode[caid] = mode
    report = adapter_for(il, http_readback_probe(target.port), fence=http_fence_probe(target.port),
                         trust_not_applied_without_fence=True).reconcile_pending()
    s = report.settlements[0]
    assert s.status == SettlementStatus.LATCHED_FENCE_FAILED and s.reason == REASON_FENCE_FAILED
    assert s.fence == FenceOutcome.FAILED and s.receipt is None
    assert report.fence_failed == [s] and report.still_latched == [s]
    if mode == "hold":
        assert any(e.startswith("fence ") for e in s.probe_errors)
    else:
        assert s.probe_errors == []
    assert il.is_caid_latched(caid) and ledger_receipts(tmp_path, caid) == []
    assert send(il, target, f"fence-{mode}") == "REFUSED"


def test_fence_failure_falls_back_to_elapsed_deadline(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "fence-deadline", "pre_timeout")
    target.fence_mode[caid] = "unsupported"
    s = adapter_for(il, http_readback_probe(target.port), fence=http_fence_probe(target.port),
                    deadline=DeadlineContract(not_after_s=2.0, clock_skew_margin_s=1.0),
                    wall_clock=lambda: time.time() + 60.0).reconcile_pending().settlements[0]
    assert s.status == SettlementStatus.SETTLED_NOT_COMMITTED and s.basis == BASIS_DEADLINE
    assert s.fence == FenceOutcome.FAILED
    assert ledger_receipts(tmp_path, caid)[0]["reconciliation_details"]["fence_outcome"] == "FAILED"


def test_deadline_basis_boundaries(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "deadline", "pre_timeout")
    intent_id = il.get_unresolved_intent_ids(caid)[0]
    dispatched = intent_dispatched_at(il, intent_id)
    assert dispatched is not None and abs(dispatched - time.time()) < 5.0
    contract = DeadlineContract(not_after_s=2.0, clock_skew_margin_s=0.5)
    bound = dispatched + 1.0 + 2.0 + 0.5
    early = adapter_for(il, SequenceProbe(["NOT_APPLIED"]), deadline=contract,
                        wall_clock=lambda: bound - 0.01).reconcile_pending().settlements[0]
    assert early.status == SettlementStatus.LATCHED_NOT_APPLIED_UNFENCED
    assert early.reason == REASON_DEADLINE_NOT_ELAPSED
    opt_in = adapter_for(il, SequenceProbe(["NOT_APPLIED"]), deadline=contract, trust_not_applied_without_fence=True,
                         wall_clock=lambda: bound - 0.01).settle(il.get_latched_caids()[caid])
    assert opt_in.basis == BASIS_UNSAFE_TRUST
    il2 = make_interlock(tmp_path / "b", key)
    caid2 = latch_with_fault(il2, target, "deadline-2", "pre_timeout")
    d2 = intent_dispatched_at(il2, il2.get_unresolved_intent_ids(caid2)[0])
    on_time = adapter_for(il2, SequenceProbe(["NOT_APPLIED"]), deadline=contract,
                          wall_clock=lambda: d2 + 3.5).reconcile_pending().settlements[0]
    assert on_time.status == SettlementStatus.SETTLED_NOT_COMMITTED and on_time.basis == BASIS_DEADLINE


def test_deadline_without_intent_record_is_not_a_basis(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "deadline-orphan", "pre_timeout")
    latch = il.get_latched_caids()[caid]
    orphan = type(latch)(**{**latch.__dict__, "intent_id": "intent-not-in-ledger"})
    s = adapter_for(il, SequenceProbe(["NOT_APPLIED"]), deadline=DeadlineContract(1.0, 0.0),
                    wall_clock=lambda: time.time() + 1e6).settle(orphan)
    assert s.status == SettlementStatus.LATCHED_NOT_APPLIED_UNFENCED
    assert s.reason == REASON_DEADLINE_NOT_ELAPSED


@pytest.mark.parametrize("kwargs", [{"not_after_s": 0.0}, {"not_after_s": 1.0, "clock_skew_margin_s": -0.1}])
def test_deadline_contract_validation(kwargs):
    with pytest.raises(ValueError):
        DeadlineContract(**kwargs)
    assert DeadlineContract(0.001, 0.0).clock_skew_margin_s == 0.0
    assert DeadlineContract(1.0).clock_skew_margin_s == 1.0


def test_fence_exception_and_custom_attempt_counter(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "fence-raise", "pre_timeout")
    seen: List[FenceRequest] = []

    def raising_fence(req: FenceRequest) -> FenceOutcome:
        seen.append(req)
        raise ConnectionRefusedError("no fence endpoint")

    s = adapter_for(il, SequenceProbe(["NOT_APPLIED"]), fence=raising_fence,
                    attempt_counter=lambda _il, _caid: 6).reconcile_pending().settlements[0]
    assert s.status == SettlementStatus.LATCHED_FENCE_FAILED
    assert s.probe_errors == ["fence ConnectionRefusedError: no fence endpoint"]
    assert seen[0].below_attempt == 7 and s.fence_below_attempt == 7
    assert seen[0].tool_name == TOOL and seen[0].target_uri == target.uri


def test_fence_string_outcomes_are_coerced(tmp_path, key, target):
    il = make_interlock(tmp_path, key)
    latch_with_fault(il, target, "fence-str", "pre_timeout")
    s = adapter_for(il, SequenceProbe(["NOT_APPLIED"]), fence=lambda req: " fenced_not_applied ").reconcile_pending().settlements[0]
    assert s.basis == BASIS_FENCE
    il2 = make_interlock(tmp_path / "b", key)
    latch_with_fault(il2, target, "fence-junk", "pre_timeout")
    s2 = adapter_for(il2, SequenceProbe(["NOT_APPLIED"]), fence=lambda req: "maybe").reconcile_pending().settlements[0]
    assert s2.status == SettlementStatus.LATCHED_FENCE_FAILED


def test_coerce_fence():
    assert _coerce_fence(FenceOutcome.APPLIED) is FenceOutcome.APPLIED
    assert _coerce_fence("applied") is FenceOutcome.APPLIED
    assert _coerce_fence("FENCED_NOT_APPLIED") is FenceOutcome.FENCED_NOT_APPLIED
    assert _coerce_fence("nope") is FenceOutcome.FAILED
    assert _coerce_fence(1) is FenceOutcome.FAILED
    assert _coerce_fence(None) is FenceOutcome.FAILED


class _LedgerOnly:
    def __init__(self, path: Path) -> None:
        self.ledger_path = path


def test_ledger_helpers_on_raw_files(tmp_path):
    missing = _LedgerOnly(tmp_path / "absent.jsonl")
    assert count_dispatch_attempts(missing, "c1") == 0
    assert intent_dispatched_at(missing, "i1") is None
    path = tmp_path / "ledger.jsonl"
    lines = [
        json.dumps({"record_type": "DISPATCH_INTENT", "caid": "c1", "intent_id": "i1", "timestamp_utc": "2026-01-02T03:04:05Z"}),
        "{torn",
        json.dumps({"record_type": "CONTINUITY_RECEIPT", "caid": "c1", "intent_id": "i1"}),
        json.dumps({"record_type": "DISPATCH_INTENT", "caid": "c1", "intent_id": "i2", "timestamp_utc": "bad"}),
        json.dumps({"record_type": "DISPATCH_INTENT", "caid": "c2", "intent_id": "i3", "timestamp_utc": "2026-01-02T03:04:06Z"}),
        json.dumps(["not", "a", "dict"]),
        "\xff",
    ]
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8") + b"\xff\xfe\n")
    il = _LedgerOnly(path)
    assert count_dispatch_attempts(il, "c1") == 2
    assert count_dispatch_attempts(il, "c2") == 1
    assert count_dispatch_attempts(il, "c3") == 0
    assert intent_dispatched_at(il, "i1") == 1767323045.0
    assert intent_dispatched_at(il, "i2") is None
    assert intent_dispatched_at(il, "i3") == 1767323046.0
    assert intent_dispatched_at(il, "i9") is None


def test_deadline_contract_is_immutable_and_elapsed_returns_bool(tmp_path, key, target):
    contract = DeadlineContract(2.0, 0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.not_after_s = 0.0  # type: ignore[misc]
    il = make_interlock(tmp_path, key)
    caid = latch_with_fault(il, target, "deadline-bool", "pre_timeout")
    latch = il.get_latched_caids()[caid]
    orphan = type(latch)(**{**latch.__dict__, "intent_id": "intent-not-in-ledger"})
    late_wall = adapter_for(il, SequenceProbe(["NOT_APPLIED"]), deadline=contract, wall_clock=lambda: time.time() + 1e6)
    assert late_wall._deadline_elapsed(latch) is True
    assert late_wall._deadline_elapsed(orphan) is False
    assert adapter_for(il, SequenceProbe(["NOT_APPLIED"]))._deadline_elapsed(latch) is False


def test_fence_and_readback_requests_are_immutable() -> None:
    """A probe/fence implementation must not be able to rewrite the CAID or the attempt floor it
    was asked to enforce (kills the `frozen=True` mutant on FenceRequest)."""
    fence = FenceRequest(caid="sha256:" + "a" * 64, intent_id="i1", target_uri="https://t.local/x",
                         tool_name="ledger.transfer", below_attempt=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fence.below_attempt = 0  # type: ignore[misc]
    rb = ReadBackRequest(caid="sha256:" + "b" * 64, intent_id="i2", target_uri="https://t.local/x",
                         tool_name="ledger.transfer", attempt=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rb.caid = "sha256:" + "c" * 64  # type: ignore[misc]
    assert fence.below_attempt == 2 and rb.caid == "sha256:" + "b" * 64
