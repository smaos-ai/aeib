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
benchmarks/eo1_real_duplicate_benchmark.py
================================================================================
Duplicate-side-effect benchmark that drives the REAL
src/eo1_write_before_execute.PreDispatchIntentInterlock against a REAL local
effect target (stdlib ThreadingHTTPServer on 127.0.0.1 that appends one line to
an effects file per committed effect). Effects are counted by reading that file;
nothing in the metric path is simulated.

Unlike benchmarks/aeib_execution_integrity/run_episodes.py (a self-contained
simulation), every A2 dispatch here goes through the interlock's ledger, flock,
fsync, latch and recovery code paths, and F4/F5 use real OS processes.

Fault schedule (balanced, seeded shuffle via random.Random(seed)); fault naming is
aligned where possible with Table 2 of arXiv:2609.29095v1 (LIMBO):
  F1 timeout after server commit (ack lost)     ~ LIMBO timeout_post
  F2 timeout before commit (not executed)       ~ LIMBO timeout_pre
  F3 HTTP 500 after commit                      ~ LIMBO http500_post
  F4 client SIGKILL mid-dispatch, then restart  (client-side crash; no LIMBO row)
  F5 concurrent duplicate submission, 2 procs   (client-side; loosely related to
                                                  LIMBO duplicate_delivery, which is
                                                  transport-side redelivery)
  F6 clean success, same-process re-issue, then restart + re-issue (no LIMBO row)
  F7 timeout after server commit (as F1) AND the target's read-back endpoint never answers
     within the probe timeout (no LIMBO row; exercises A3's UNKNOWN path)
  F8 regenerated retry (no LIMBO row; after ACRFence, arXiv:2603.20625): timeout after server
     commit (as F1), then a crash/restore (new client + interlock instance over the same
     ledger; A3/A4 run their reconcile pass on the pre-crash CAID first), then the agent
     re-issues the call with a changed memo, a new client_request_id UUID and reordered
     optional fields (same recipient, amount, currency, business reference `key`)
  F9 late commit (LIMBO timeout_late): the target holds the first write past the client
     timeout; while it is still in flight a read-back answers NOT_APPLIED; the write then
     commits after a seeded delay of factor x client timeout, factor in F9_LATE_FACTORS
     (0.6: before the client timeout, i.e. before any reconcile pass; 1.3: after a single
     reconcile pass and its retry; 2.4 / 4.2: after the second / third spaced probe of A4N3).
     A fenced write (attempt < fence) is refused at commit time instead.
Faults F1-F4 and the F7/F8/F9 write fault apply only to the first write the target sees for an
intent; the F7 read-back hold applies to every read-back of that intent.

Arms:
  A0 naive retry loop (1 + 3 retries on transport/5xx error, no key, no ledger)
  A1 per-process in-memory idempotency key (random per process) + same retry loop;
     also suppresses same-process re-issue of an acknowledged intent
  A2 real EO1 PreDispatchIntentInterlock (no retry; wire faults latch the CAID)
  A3 A2 + src/eo1_reconciliation_adapter.Eo1ReconciliationAdapter: after each intent's
     scenario, one reconcile pass reads the target's CAID read-back endpoint
     (GET /readback?caid=...) and settles the latch through EO1's reconcile_out_of_band;
     an intent settled NOT_COMMITTED is re-submitted once through EO1.
  A4 A3 with the CAID derived by src/eo1_effect_key (schema-declared identity fields: op, key,
     recipient, amount_minor, currency) instead of the full-payload CAID that A2/A3 use. The
     interlock is handed the effect-key preimage as its payload; the raw tool call is what
     dispatch_fn sends.
  A3 and A4 settle NOT_APPLIED with the explicit UNSAFE opt-in
     trust_not_applied_without_fence=True (basis "unsafe_trust_not_applied").
  A4N3 A4 (unsafe opt-in) with not_applied_confirmations=3 and probe spacing 0.7 x / 1.4 x the
     client timeout.
  A4D A4 with the adapter's fail-closed default: NOT_APPLIED without a fence or deadline stays
     latched (reason NOT_APPLIED_UNFENCED); no retry.
  A5 A4 + attempt fencing: every write carries X-AEIB-Attempt = count_dispatch_attempts + 1; a
     NOT_APPLIED read is settled only after POST /fence?caid=..&below=n is acked (the target
     then refuses in-flight writes with attempt < n). Fence failure -> stays latched.

Every arm sends the same JSON tool-call body (tool_call_payload); the target counts effects by
its business reference `key`. EO1 arms (A2, A3, A4) send the CAID as the X-AEIB-CAID header so
the target can index effects by it. The target's own idempotency-key handling is OFF by default (--target-idempotency off),
so A1's key only matters when the target honours it (--target-idempotency on); the CAID
header is used only for read-back, never for de-duplication.

Usage:
  python3 benchmarks/eo1_real_duplicate_benchmark.py --n 300 --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import random
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eo1_effect_key import (  # noqa: E402
    EffectClass,
    EffectKeySchema,
    EffectKeySchemaRegistry,
    IdentityField,
    resolve_dispatch_key,
)
from src.eo1_reconciliation_adapter import (  # noqa: E402
    Eo1ReconciliationAdapter,
    FenceOutcome,
    FenceRequest,
    ReadBackOutcome,
    ReadBackRequest,
    count_dispatch_attempts,
)
from src.eo1_write_before_execute import (  # noqa: E402
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    PreDispatchLedgerWriteError,
    compute_caid,
)

FAULTS = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9")
ARMS = ("A0", "A1", "A2", "A3", "A4", "A4N3", "A4D", "A5")
EO1_ARMS = ("A2", "A3", "A4", "A4N3", "A4D", "A5")
RECONCILING_ARMS = ("A3", "A4", "A4N3", "A4D", "A5")
EFFECT_KEY_ARMS = ("A4", "A4N3", "A4D", "A5")
ARM_LABELS = {
    "A0": "naive retry (<=3 retries)",
    "A1": "in-memory idempotency key",
    "A2": "EO1 PreDispatchIntentInterlock",
    "A3": "EO1 + read-back reconciler (unsafe opt-in)",
    "A4": "EO1 + reconciler + effect-key CAID (unsafe opt-in)",
    "A4N3": "A4 unsafe opt-in, 3 spaced NOT_APPLIED confirmations",
    "A4D": "A4 fail-closed default (no fence)",
    "A5": "A4 + attempt fencing",
}
# Basis on which each reconciling arm may settle a NOT_APPLIED read (recorded in receipts).
ARM_NOT_APPLIED_BASIS = {
    "A3": "unsafe_trust_not_applied",
    "A4": "unsafe_trust_not_applied",
    "A4N3": "unsafe_trust_not_applied (3 confirmations)",
    "A4D": "none (stays latched: NOT_APPLIED_UNFENCED)",
    "A5": "fence",
}
LIMBO_ALIGNMENT = {
    "F1": "timeout_post",
    "F2": "timeout_pre",
    "F3": "http500_post",
    "F4": "none (client SIGKILL + restart)",
    "F5": "none (2-process concurrent submit; cf. duplicate_delivery)",
    "F6": "none (re-issue + restart after clean success)",
    "F7": "none (timeout_post + read-back timeout)",
    "F8": "none (timeout_post + restore + regenerated retry; cf. ACRFence arXiv:2603.20625)",
    "F9": "timeout_late (in flight at read-back, commits late)",
}
MAX_RETRIES = 3
TOOL_NAME = "effect_target.append"
WILSON_Z = 1.959963984540054  # two-sided 95% normal quantile
RECONCILE_MAX_PROBE_ATTEMPTS = 3
RECONCILE_BACKOFF_INITIAL_S = 0.05
REQUEST_ID_NAMESPACE = uuid.UUID("6b0f3c52-8c1e-4a57-9d0e-3f1b2a4c5d6e")
F8_REGENERATED_VARIANT = 1
F9_LATE_FACTORS = (0.6, 1.3, 2.4, 4.2)  # late-commit delay as a multiple of the client timeout
A4N3_CONFIRMATIONS = 3
A4N3_SPACING_FACTOR = 0.7  # first probe gap = 0.7 x client timeout, then doubling

# A4's effect-key schema for the benchmark tool. effect_class "irreversible": the target's
# append is not de-duplicated (target idempotency off by default). Taxonomy: arXiv:2604.23283.
EFFECT_KEY_SCHEMA = EffectKeySchema(
    tool=TOOL_NAME,
    schema_id="effect_target.append.effect",
    schema_version="1",
    identity_fields=(
        IdentityField("op", "exact_nfc"),
        IdentityField("key", "exact_nfc"),
        IdentityField("recipient", "casefold_nfc"),
        IdentityField("amount_minor", "minor_units"),
        IdentityField("currency", "currency_iso4217"),
    ),
    effect_class=EffectClass.IRREVERSIBLE,
)
EFFECT_KEY_REGISTRY = EffectKeySchemaRegistry([EFFECT_KEY_SCHEMA])


class BenchmarkHarnessError(RuntimeError):
    """Raised when the harness itself fails (worker crash, missing signal); never swallowed."""


class TargetHTTPError(RuntimeError):
    """Non-2xx response from the effect target."""


# ---------------------------------------------------------------------------
# Real effect target
# ---------------------------------------------------------------------------


class EffectTarget:
    """Local HTTP effect target. Each committed effect is one appended JSON line."""

    def __init__(self, root: Path, idempotency: bool, fault_sleep_s: float, race_window_s: float):
        self.effects_path = root / "effects.jsonl"
        self.effects_path.touch()
        self.idempotency = idempotency
        self.fault_sleep_s = fault_sleep_s
        self.race_window_s = race_window_s
        self._lock = threading.Lock()
        self._attempts: Counter = Counter()
        self._seen_idem: set = set()
        self._applied_caids: set = set()
        self.readback_hold: set = set()  # CAIDs whose read-back never answers in time (F7)
        self.readback_requests: Counter = Counter()
        self.fences: Dict[str, int] = {}  # caid -> refuse writes with attempt < value
        self.fenced_refusals: Counter = Counter()  # key -> writes refused by a fence
        self.fence_requests: Counter = Counter()  # caid -> fence calls
        self.client_timeout_s = fault_sleep_s / 2.5
        self._writes_in_flight = 0
        self._idle = threading.Condition(self._lock)
        self.plan: Dict[str, Dict[str, Any]] = {}
        self.f4_reached: Dict[str, threading.Event] = {}
        self.f4_release: Dict[str, threading.Event] = {}
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # -- lifecycle --
    def start(self) -> int:
        target = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, fmt: str, *args: Any) -> None:  # silence stderr
                return None

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                attempt_hdr = self.headers.get("X-AEIB-Attempt")
                parsed = urlparse(self.path)
                if parsed.path == "/fence":
                    q = parse_qs(parsed.query)
                    target.handle_fence(self, q.get("caid", [""])[0], int(q.get("below", ["0"])[0]))
                    return
                target.handle(self, str(body.get("key", "")), self.headers.get("X-Idempotency-Key"),
                              self.headers.get("X-AEIB-CAID"),
                              int(attempt_hdr) if attempt_hdr is not None else None)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != "/readback":
                    target._respond(self, 404, {"error": "not found"})
                    return
                target.handle_readback(self, parse_qs(parsed.query).get("caid", [""])[0])

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return int(self._server.server_address[1])

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

    # -- effect commit --
    def _commit(self, key: str, attempt: int, idem: Optional[str], caid: Optional[str] = None,
                attempt_token: Optional[int] = None) -> bool:
        with self._lock:
            if self.idempotency and idem and idem in self._seen_idem:
                return False
            if caid and caid in self.fences and (attempt_token or 0) < self.fences[caid]:
                self.fenced_refusals[key] += 1
                return False
            line = json.dumps({"key": key, "attempt": attempt, "caid": caid, "t": time.time()}) + "\n"
            fd = os.open(str(self.effects_path), os.O_WRONLY | os.O_APPEND)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
            if idem:
                self._seen_idem.add(idem)
            if caid:
                self._applied_caids.add(caid)
            return True

    @staticmethod
    def _respond(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        try:
            handler.send_response(status)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # client already gone (timed out or killed); the commit decision stands

    def handle(self, handler: BaseHTTPRequestHandler, key: str, idem: Optional[str],
               caid: Optional[str] = None, attempt_token: Optional[int] = None) -> None:
        with self._lock:
            self._writes_in_flight += 1
        try:
            self._handle_write(handler, key, idem, caid, attempt_token)
        finally:
            with self._lock:
                self._writes_in_flight -= 1
                self._idle.notify_all()

    def wait_writes_drained(self, timeout_s: float) -> None:
        """Blocks until no write is in flight (late commits included); effects are counted after this."""
        deadline = time.monotonic() + timeout_s
        with self._lock:
            while self._writes_in_flight > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BenchmarkHarnessError(f"{self._writes_in_flight} target writes still in flight")
                self._idle.wait(remaining)

    def _handle_write(self, handler: BaseHTTPRequestHandler, key: str, idem: Optional[str],
                      caid: Optional[str], attempt_token: Optional[int]) -> None:
        with self._lock:
            self._attempts[key] += 1
            attempt = self._attempts[key]
        plan = self.plan.get(key, {})
        fault = plan.get("fault")
        first = attempt == 1

        if fault == "F2" and first:
            time.sleep(self.fault_sleep_s)
            return  # not executed, no response
        if fault == "F9" and first:
            delay = float(plan["late_commit_factor"]) * self.client_timeout_s
            time.sleep(delay)  # in flight: read-back answers NOT_APPLIED meanwhile
            applied = self._commit(key, attempt, idem, caid, attempt_token)
            time.sleep(max(0.0, self.fault_sleep_s - delay))
            self._respond(handler, 200 if applied else 409, {"committed": applied})
            return
        if fault == "F4" and first:
            if plan.get("commit_before_kill"):
                self._commit(key, attempt, idem, caid, attempt_token)
            self.f4_reached[key].set()
            self.f4_release[key].wait(timeout=60.0)
            self._respond(handler, 200, {"committed": bool(plan.get("commit_before_kill"))})
            return
        if fault == "F5":
            time.sleep(self.race_window_s)
        applied = self._commit(key, attempt, idem, caid, attempt_token)
        if fault in ("F1", "F7", "F8") and first:
            time.sleep(self.fault_sleep_s)
            self._respond(handler, 200, {"committed": applied})
            return
        if fault == "F3" and first:
            self._respond(handler, 500, {"error": "internal", "committed": applied})
            return
        self._respond(handler, 200, {"committed": applied, "replayed": not applied})

    def handle_readback(self, handler: BaseHTTPRequestHandler, caid: str) -> None:
        """Read-back by CAID: {"caid", "applied"}; F7 CAIDs are held past the probe timeout."""
        with self._lock:
            self.readback_requests[caid] += 1
            applied = caid in self._applied_caids
            hold = caid in self.readback_hold
        if hold:
            time.sleep(self.fault_sleep_s)
            return  # no answer within the probe timeout
        self._respond(handler, 200, {"caid": caid, "applied": applied})

    def handle_fence(self, handler: BaseHTTPRequestHandler, caid: str, below: int) -> None:
        """Atomic check-and-fence: refuse later commits of attempts < below; report whether applied."""
        with self._lock:
            self.fence_requests[caid] += 1
            self.fences[caid] = max(self.fences.get(caid, 0), below)
            applied = caid in self._applied_caids
        self._respond(handler, 200, {"caid": caid, "fenced": True, "below": below, "applied": applied})

    def effect_counts(self) -> Counter:
        counts: Counter = Counter()
        with open(self.effects_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    counts[json.loads(line)["key"]] += 1
        return counts


# ---------------------------------------------------------------------------
# Client arms
# ---------------------------------------------------------------------------


def tool_call_payload(key: str, variant: int = 0) -> Dict[str, Any]:
    """
    The JSON tool call every arm sends. Identity (op, key = business reference, recipient,
    amount_minor, currency) depends only on `key`; the incidental fields depend on `variant`.
    Variant 0 is the original call; variant F8_REGENERATED_VARIANT is the regenerated retry
    (changed memo, new client_request_id, reordered optional object members and list items).
    Deterministic per (key, variant) so subprocess workers rebuild the same call; the
    client_request_id is a UUIDv5 so runs are reproducible, and it differs between variants.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    regenerated = variant == F8_REGENERATED_VARIANT
    payload: Dict[str, Any] = {
        "op": "append_effect",
        "key": key,
        "recipient": f"acct-{digest[2:6].hex()}",
        "amount_minor": 1000 + int.from_bytes(digest[:2], "big") % 9000,
        "currency": "EUR",
        "memo": (f"Re-sending settlement for {key} after restart" if regenerated
                 else f"Settlement for {key}"),
        "client_request_id": str(uuid.uuid5(REQUEST_ID_NAMESPACE, f"{key}|v{variant}")),
    }
    if regenerated:
        payload["tags"] = ["eo1", "benchmark"]
        payload["options"] = {"notify": True, "priority": "normal"}
    else:
        payload["options"] = {"priority": "normal", "notify": True}
        payload["tags"] = ["benchmark", "eo1"]
    return payload


def post_effect(port: int, key: str, timeout_s: float, idem: Optional[str] = None,
                caid: Optional[str] = None, body: Optional[Dict[str, Any]] = None,
                attempt: Optional[int] = None) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout_s)
    try:
        headers = {"Content-Type": "application/json"}
        if idem:
            headers["X-Idempotency-Key"] = idem
        if caid:
            headers["X-AEIB-CAID"] = caid
        if attempt is not None:
            headers["X-AEIB-Attempt"] = str(attempt)
        doc = body if body is not None else tool_call_payload(key)
        conn.request("POST", "/effect", body=json.dumps(doc).encode("utf-8"), headers=headers)
        resp = conn.getresponse()
        body = resp.read()
        if not 200 <= resp.status < 300:
            raise TargetHTTPError(f"HTTP {resp.status}")
        return {"status_code": resp.status, "body": body.decode("utf-8", errors="replace")}
    finally:
        conn.close()


TRANSPORT_ERRORS = (OSError, http.client.HTTPException, TargetHTTPError)


class NaiveRetryClient:
    """A0: retry up to MAX_RETRIES times on any transport error or 5xx; no key, no ledger."""

    def __init__(self, port: int, timeout_s: float, **_: Any):
        self.port, self.timeout_s = port, timeout_s

    def submit(self, key: str, variant: int = 0) -> str:
        body = tool_call_payload(key, variant)
        for _attempt in range(1 + MAX_RETRIES):
            try:
                post_effect(self.port, key, self.timeout_s, body=body)
                return "SUCCESS"
            except TRANSPORT_ERRORS:
                continue
        return "FAILED"


class InMemoryKeyClient:
    """A1: random per-process idempotency key held in memory; same retry loop as A0."""

    def __init__(self, port: int, timeout_s: float, **_: Any):
        self.port, self.timeout_s = port, timeout_s
        self._keys: Dict[str, str] = {}
        self._done: set = set()

    def submit(self, key: str, variant: int = 0) -> str:
        if key in self._done:
            return "SKIPPED_LOCAL_DUPLICATE"
        idem = self._keys.setdefault(key, uuid.uuid4().hex)
        body = tool_call_payload(key, variant)
        for _attempt in range(1 + MAX_RETRIES):
            try:
                post_effect(self.port, key, self.timeout_s, idem=idem, body=body)
                self._done.add(key)
                return "SUCCESS"
            except TRANSPORT_ERRORS:
                continue
        return "FAILED"


def arm_interlock_payload(arm: str, key: str, variant: int = 0) -> Dict[str, Any]:
    """Payload handed to PreDispatchIntentInterlock: raw tool call (A2/A3) or effect-key preimage (A4)."""
    raw = tool_call_payload(key, variant)
    if arm in EFFECT_KEY_ARMS:
        return resolve_dispatch_key(TOOL_NAME, raw, EFFECT_KEY_REGISTRY).interlock_payload
    return raw


def arm_caid(arm: str, key: str, variant: int = 0) -> str:
    """The CAID the interlock computes for this arm's call (compute_caid over the interlock payload)."""
    return compute_caid(arm_interlock_payload(arm, key, variant))


def load_or_create_boundary_key(ledger_dir: Path) -> Ed25519PrivateKey:
    """
    One stable Ed25519 boundary key per arm ledger, shared by every client process and the
    finalize probe. Without it each interlock instance holds an ephemeral key and treats records
    signed by other instances as untrusted (restrictive mode), which would latch everything.
    The key file lives only in the benchmark's temporary directory (mode 0600).
    """
    key_path = ledger_dir / "boundary_ed25519.pem"
    if not key_path.exists():
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        try:
            fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            try:
                os.write(fd, pem)
                os.fsync(fd)
            finally:
                os.close(fd)
    loaded = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise BenchmarkHarnessError(f"{key_path} is not an Ed25519 private key")
    return loaded


class Eo1InterlockClient:
    """A2: real PreDispatchIntentInterlock; no retry, wire faults latch EFFECT_INDETERMINATE."""

    arm = "A2"
    attempt_tokens = False

    def __init__(self, port: int, timeout_s: float, ledger_dir: str, auto_recover: bool = True, **_: Any):
        self.port, self.timeout_s = port, timeout_s
        ledger_dir_p = Path(ledger_dir)
        self.interlock = PreDispatchIntentInterlock(
            ledger_path=ledger_dir_p / "eo1_ledger.jsonl",
            output_state_dir=ledger_dir_p / "state",
            boundary_private_key=load_or_create_boundary_key(ledger_dir_p),
            authority_id="eo1-real-duplicate-benchmark",
            auto_recover=auto_recover,
        )

    def submit(self, key: str, variant: int = 0) -> str:
        uri = f"http://127.0.0.1:{self.port}/effect"
        body = tool_call_payload(key, variant)
        interlock_payload = arm_interlock_payload(self.arm, key, variant)
        caid = compute_caid(interlock_payload)
        attempt = count_dispatch_attempts(self.interlock, caid) + 1 if self.attempt_tokens else None
        try:
            self.interlock.dispatch(
                uri, TOOL_NAME, interlock_payload,
                dispatch_fn=lambda: post_effect(self.port, key, self.timeout_s, caid=caid, body=body,
                                                attempt=attempt),
            )
            return "SUCCESS"
        except LatchedCaidExecutionHaltedError:
            return "REFUSED"
        except PreDispatchLedgerWriteError:
            return "FAILED_CLOSED_NO_SEND"
        except RuntimeError:
            return "INDETERMINATE"


class HttpCaidReadBackProbe:
    """
    ReadBackProbe for the local effect target: GET /readback?caid=<caid>. Returns APPLIED /
    NOT_APPLIED only on a 200 answer that echoes the CAID; any other HTTP status is UNKNOWN.
    Transport errors (including the probe timeout) propagate; the adapter records them and
    treats the read as UNKNOWN.
    """

    def __init__(self, port: int, timeout_s: float):
        self.port, self.timeout_s = port, timeout_s
        self.issued = 0

    def __call__(self, request: ReadBackRequest) -> ReadBackOutcome:
        self.issued += 1
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.timeout_s)
        try:
            conn.request("GET", f"/readback?caid={request.caid}")
            resp = conn.getresponse()
            body = resp.read()
        finally:
            conn.close()
        if resp.status != 200:
            return ReadBackOutcome.UNKNOWN
        doc = json.loads(body)
        if doc.get("caid") != request.caid or not isinstance(doc.get("applied"), bool):
            return ReadBackOutcome.UNKNOWN
        return ReadBackOutcome.APPLIED if doc["applied"] else ReadBackOutcome.NOT_APPLIED


class HttpAttemptFenceProbe:
    """
    FenceProbe for the local effect target: POST /fence?caid=..&below=n. FENCED_NOT_APPLIED /
    APPLIED only on a 200 answer that echoes the CAID with fenced=true; anything else is FAILED.
    Transport errors propagate; the adapter records them as FAILED (CAID stays latched).
    """

    def __init__(self, port: int, timeout_s: float):
        self.port, self.timeout_s = port, timeout_s
        self.issued = 0

    def __call__(self, request: FenceRequest) -> FenceOutcome:
        self.issued += 1
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.timeout_s)
        try:
            conn.request("POST", f"/fence?caid={request.caid}&below={request.below_attempt}", body=b"",
                         headers={"Content-Length": "0"})
            resp = conn.getresponse()
            body = resp.read()
        finally:
            conn.close()
        if resp.status != 200:
            return FenceOutcome.FAILED
        doc = json.loads(body)
        if doc.get("caid") != request.caid or doc.get("fenced") is not True or doc.get("below") != request.below_attempt:
            return FenceOutcome.FAILED
        return FenceOutcome.APPLIED if doc.get("applied") is True else FenceOutcome.FENCED_NOT_APPLIED


class Eo1ReconcilingClient(Eo1InterlockClient):
    """A3: A2 plus Eo1ReconciliationAdapter over the target's CAID read-back endpoint (unsafe opt-in)."""

    arm = "A3"

    def adapter_kwargs(self) -> Dict[str, Any]:
        return {"max_probe_attempts": RECONCILE_MAX_PROBE_ATTEMPTS,
                "backoff_initial_s": RECONCILE_BACKOFF_INITIAL_S,
                "trust_not_applied_without_fence": True}

    def __init__(self, port: int, timeout_s: float, ledger_dir: str, auto_recover: bool = True, **_: Any):
        super().__init__(port=port, timeout_s=timeout_s, ledger_dir=ledger_dir, auto_recover=auto_recover)
        self.probe = HttpCaidReadBackProbe(port, timeout_s)
        kwargs = self.adapter_kwargs()
        self.fence_probe = kwargs.get("fence")
        self.adapter = Eo1ReconciliationAdapter(
            self.interlock, self.probe, probe_id="effect_target.readback", **kwargs)

    def reconcile_and_retry(self, key: str, variant: int = 0) -> Dict[str, Any]:
        """One reconcile pass for this call's CAID; a NOT_COMMITTED settlement is re-submitted once."""
        caid = arm_caid(self.arm, key, variant)
        before = self.probe.issued
        fences_before = self.fence_probe.issued if self.fence_probe is not None else 0
        t0 = time.perf_counter()
        report = self.adapter.reconcile_pending(caids=[caid])
        reconcile_ms = (time.perf_counter() - t0) * 1000.0
        statuses = [s.status.value for s in report.settlements]
        retry_outcome = None
        if report.not_committed:
            retry_outcome = self.submit(key, variant)
        return {
            "statuses": statuses,
            "probes": self.probe.issued - before,
            "fences": (self.fence_probe.issued if self.fence_probe is not None else 0) - fences_before,
            "reconcile_ms": reconcile_ms,
            "total_ms": (time.perf_counter() - t0) * 1000.0,
            "retry_outcome": retry_outcome,
        }


class Eo1EffectKeyReconcilingClient(Eo1ReconcilingClient):
    """A4: A3 with the CAID derived from src/eo1_effect_key (EFFECT_KEY_SCHEMA) instead of the full payload."""

    arm = "A4"


class Eo1ConfirmingClient(Eo1EffectKeyReconcilingClient):
    """A4N3: A4 (unsafe opt-in) requiring 3 consecutive NOT_APPLIED reads, spaced 0.7x / 1.4x timeout."""

    arm = "A4N3"

    def adapter_kwargs(self) -> Dict[str, Any]:
        return {"max_probe_attempts": A4N3_CONFIRMATIONS,
                "not_applied_confirmations": A4N3_CONFIRMATIONS,
                "backoff_initial_s": A4N3_SPACING_FACTOR * self.timeout_s,
                "backoff_factor": 2.0,
                "backoff_max_s": 10.0,
                "trust_not_applied_without_fence": True}


class Eo1FailClosedClient(Eo1EffectKeyReconcilingClient):
    """A4D: A4 with the adapter's fail-closed default (NOT_APPLIED without fence stays latched)."""

    arm = "A4D"

    def adapter_kwargs(self) -> Dict[str, Any]:
        return {"max_probe_attempts": RECONCILE_MAX_PROBE_ATTEMPTS,
                "backoff_initial_s": RECONCILE_BACKOFF_INITIAL_S}


class Eo1FencedClient(Eo1EffectKeyReconcilingClient):
    """A5: A4 + attempt tokens on every write + FenceProbe before any NOT_COMMITTED settlement."""

    arm = "A5"
    attempt_tokens = True

    def adapter_kwargs(self) -> Dict[str, Any]:
        return {"max_probe_attempts": RECONCILE_MAX_PROBE_ATTEMPTS,
                "backoff_initial_s": RECONCILE_BACKOFF_INITIAL_S,
                "fence": HttpAttemptFenceProbe(self.port, self.timeout_s)}


CLIENTS = {"A0": NaiveRetryClient, "A1": InMemoryKeyClient, "A2": Eo1InterlockClient, "A3": Eo1ReconcilingClient,
           "A4": Eo1EffectKeyReconcilingClient, "A4N3": Eo1ConfirmingClient, "A4D": Eo1FailClosedClient,
           "A5": Eo1FencedClient}


def make_client(arm: str, port: int, timeout_s: float, ledger_dir: str, auto_recover: bool = True) -> Any:
    return CLIENTS[arm](port=port, timeout_s=timeout_s, ledger_dir=ledger_dir, auto_recover=auto_recover)


# ---------------------------------------------------------------------------
# Subprocess worker (real OS process for F4 / F5)
# ---------------------------------------------------------------------------


def worker_main(spec_json: str) -> int:
    spec = json.loads(spec_json)
    client = make_client(spec["arm"], spec["port"], spec["timeout_s"], spec["ledger_dir"],
                         auto_recover=spec.get("auto_recover", True))
    sys.stdout.write("READY\n")
    sys.stdout.flush()
    if spec.get("barrier"):
        sys.stdin.readline()
    t0 = time.perf_counter()
    outcome = client.submit(spec["key"])
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    sys.stdout.write(json.dumps({"outcome": outcome, "elapsed_ms": elapsed_ms}) + "\n")
    sys.stdout.flush()
    return 0


def _spawn_worker(spec: Dict[str, Any], stdin_pipe: bool) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker", json.dumps(spec)],
        cwd=str(ROOT), env=env, text=True,
        stdin=subprocess.PIPE if stdin_pipe else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _read_ready(proc: subprocess.Popen) -> None:
    line = proc.stdout.readline() if proc.stdout else ""
    if line.strip() != "READY":
        _, err = proc.communicate(timeout=30)
        raise BenchmarkHarnessError(f"worker failed before READY: {line!r} {err[-800:]}")


def _finish_worker(proc: subprocess.Popen) -> Dict[str, Any]:
    out, err = proc.communicate(timeout=60)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if proc.returncode != 0 or not lines:
        raise BenchmarkHarnessError(f"worker rc={proc.returncode} stderr={err[-800:]}")
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# Scenario runners
# ---------------------------------------------------------------------------


@dataclass
class IntentRecord:
    idx: int
    arm: str
    fault: str
    key: str
    variant: Dict[str, Any] = field(default_factory=dict)
    outcomes: List[str] = field(default_factory=list)
    latency_ms: Optional[float] = None
    effects: int = 0
    indeterminate: bool = False
    reconcile_statuses: List[str] = field(default_factory=list)
    reconcile_probes: int = 0
    reconcile_ms: Optional[float] = None
    submitted_variants: List[int] = field(default_factory=lambda: [0])
    fenced_refusals: int = 0
    fence_calls: int = 0


def build_schedule(n: int, seed: int) -> List[Tuple[str, Dict[str, Any]]]:
    rng = random.Random(seed)
    faults = [FAULTS[i % len(FAULTS)] for i in range(n)]
    rng.shuffle(faults)
    schedule = []
    for f in faults:
        if f == "F4":
            variant = {"commit_before_kill": rng.random() < 0.5}
        elif f == "F9":
            variant = {"late_commit_factor": rng.choice(F9_LATE_FACTORS)}
        else:
            variant = {}
        schedule.append((f, variant))
    return schedule


class Harness:
    def __init__(self, workdir: Path, n: int, seed: int, timeout_s: float, target_idempotency: bool):
        self.workdir = workdir
        self.n, self.seed, self.timeout_s = n, seed, timeout_s
        self.target = EffectTarget(workdir, target_idempotency, fault_sleep_s=timeout_s * 2.5,
                                   race_window_s=0.03)
        self.port = 0

    def _timed(self, fn: Any, *args: Any) -> Tuple[Any, float]:
        t0 = time.perf_counter()
        out = fn(*args)
        return out, (time.perf_counter() - t0) * 1000.0

    def _spec(self, arm: str, key: str, ledger_dir: str, **extra: Any) -> Dict[str, Any]:
        spec = {"arm": arm, "port": self.port, "timeout_s": self.timeout_s, "key": key, "ledger_dir": ledger_dir}
        spec.update(extra)
        return spec

    def run_f4(self, rec: IntentRecord, ledger_dir: str) -> None:
        reached, release = threading.Event(), threading.Event()
        self.target.f4_reached[rec.key], self.target.f4_release[rec.key] = reached, release
        proc = _spawn_worker(self._spec(rec.arm, rec.key, ledger_dir), stdin_pipe=False)
        try:
            if not reached.wait(timeout=60.0):
                raise BenchmarkHarnessError(f"F4 worker for {rec.key} never reached target")
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=30)
            if proc.returncode != -signal.SIGKILL:
                raise BenchmarkHarnessError(f"F4 worker rc={proc.returncode}, expected SIGKILL")
        finally:
            release.set()
            if proc.poll() is None:
                proc.kill()
            for stream in (proc.stdout, proc.stderr):
                if stream:
                    stream.close()
        rec.outcomes.append("KILLED")
        restart = _spawn_worker(self._spec(rec.arm, rec.key, ledger_dir, auto_recover=True), stdin_pipe=False)
        result = _finish_worker(restart)
        rec.outcomes.append(result["outcome"])
        rec.latency_ms = result["elapsed_ms"]

    def run_f5(self, rec: IntentRecord, ledger_dir: str) -> None:
        procs = [_spawn_worker(self._spec(rec.arm, rec.key, ledger_dir, auto_recover=False, barrier=True),
                               stdin_pipe=True) for _ in range(2)]
        for p in procs:
            _read_ready(p)
        for p in procs:
            p.stdin.write("GO\n")
            p.stdin.flush()
        results = [_finish_worker(p) for p in procs]
        rec.outcomes.extend(r["outcome"] for r in results)
        rec.latency_ms = max(r["elapsed_ms"] for r in results)

    def _apply_reconcile(self, rec: IntentRecord, recon: Dict[str, Any]) -> None:
        rec.reconcile_statuses.extend(recon["statuses"])
        rec.reconcile_probes += recon["probes"]
        rec.fence_calls += recon["fences"]
        rec.reconcile_ms = (rec.reconcile_ms or 0.0) + recon["reconcile_ms"]
        if recon["retry_outcome"] is not None:
            rec.outcomes.append("RETRY_" + recon["retry_outcome"])
        rec.latency_ms = (rec.latency_ms or 0.0) + recon["total_ms"]

    def run_f8(self, rec: IntentRecord, client: Any, ledger_dir: str) -> Any:
        """
        F8 regenerated retry: original call (target commits, ack lost) -> crash/restore (new client
        and interlock over the same ledger; A3/A4 reconcile the pre-crash CAID on startup) -> the
        agent re-issues a regenerated call (variant F8_REGENERATED_VARIANT). Returns the restarted
        client so the post-scenario reconcile pass runs on post-restore state.
        """
        outcome, total = self._timed(client.submit, rec.key, 0)
        rec.outcomes.append(outcome)
        rec.latency_ms = total
        restarted = make_client(rec.arm, self.port, self.timeout_s, ledger_dir)
        if rec.arm in RECONCILING_ARMS:
            self._apply_reconcile(rec, restarted.reconcile_and_retry(rec.key, 0))
        outcome, ms = self._timed(restarted.submit, rec.key, F8_REGENERATED_VARIANT)
        rec.outcomes.append(outcome)
        rec.latency_ms = (rec.latency_ms or 0.0) + ms
        rec.submitted_variants = [0, F8_REGENERATED_VARIANT]
        return restarted

    def run_arm(self, arm: str, schedule: List[Tuple[str, Dict[str, Any]]]) -> List[IntentRecord]:
        ledger_dir = self.workdir / f"ledger_{arm}"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        client = make_client(arm, self.port, self.timeout_s, str(ledger_dir))
        records: List[IntentRecord] = []
        for idx, (fault, variant) in enumerate(schedule):
            key = f"{arm}-s{self.seed}-i{idx}"
            rec = IntentRecord(idx=idx, arm=arm, fault=fault, key=key, variant=dict(variant))
            self.target.plan[key] = {"fault": fault, **variant}
            if fault == "F7":
                with self.target._lock:
                    self.target.readback_hold.add(arm_caid(arm, key))
            post_client = client
            if fault in ("F1", "F2", "F3", "F7", "F9"):
                outcome, ms = self._timed(client.submit, key)
                rec.outcomes.append(outcome)
                rec.latency_ms = ms
            elif fault == "F4":
                self.run_f4(rec, str(ledger_dir))
            elif fault == "F5":
                self.run_f5(rec, str(ledger_dir))
            elif fault == "F8":
                post_client = self.run_f8(rec, client, str(ledger_dir))
            else:  # F6: clean success, same-process re-issue, restart, re-issue
                total = 0.0
                for c in (client, client, make_client(arm, self.port, self.timeout_s, str(ledger_dir))):
                    outcome, ms = self._timed(c.submit, key)
                    rec.outcomes.append(outcome)
                    total += ms
                rec.latency_ms = total
            if arm in RECONCILING_ARMS:
                # Latency = scenario submits + reconcile pass(es) + any single NOT_COMMITTED retry.
                self._apply_reconcile(rec, post_client.reconcile_and_retry(key, rec.submitted_variants[-1]))
            records.append(rec)
        return records

    def finalize(self, records: List[IntentRecord]) -> None:
        # Late commits (F9) and held writes may still be in flight after the last scenario.
        self.target.wait_writes_drained(timeout_s=120.0)
        counts = self.target.effect_counts()
        for rec in records:
            rec.effects = counts.get(rec.key, 0)
            rec.fenced_refusals = self.target.fenced_refusals.get(rec.key, 0)
        for arm in ARMS:
            arm_recs = [r for r in records if r.arm == arm]
            if arm not in EO1_ARMS or not arm_recs:
                continue
            ledger_dir = self.workdir / f"ledger_{arm}"
            probe = PreDispatchIntentInterlock(
                ledger_path=ledger_dir / "eo1_ledger.jsonl", output_state_dir=ledger_dir / "state",
                boundary_private_key=load_or_create_boundary_key(ledger_dir),
                authority_id="eo1-real-duplicate-benchmark-probe", auto_recover=False,
            )
            latched = probe.get_latched_caids()
            for rec in arm_recs:
                caids = {arm_caid(arm, rec.key, v) for v in rec.submitted_variants}
                rec.indeterminate = any(c in latched or bool(probe.get_unresolved_intent_ids(c)) for c in caids)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def wilson_ci(k: int, n: int, z: float = WILSON_Z) -> Optional[Tuple[float, float]]:
    if n <= 0:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100.0 * len(ordered)))
    return ordered[rank - 1]


def summarize(records: List[IntentRecord], subset_label: str = "all") -> Dict[str, Any]:
    n = len(records)
    dup_effects = sum(max(0, r.effects - 1) for r in records)
    dup_intents = sum(1 for r in records if r.effects > 1)
    indet = [r for r in records if r.indeterminate]
    lost = sum(1 for r in records if r.effects == 0 and not r.indeterminate)
    overclaim = sum(1 for r in records if r.effects > 1 and "SUCCESS" in r.outcomes)
    lat = [r.latency_ms for r in records if r.latency_ms is not None]
    rlat = [r.reconcile_ms for r in records if r.reconcile_ms is not None and r.reconcile_statuses]
    ci = wilson_ci(dup_intents, n)
    return {
        "subset": subset_label,
        "total_intents": n,
        "actual_effects": sum(r.effects for r in records),
        "duplicate_effects": dup_effects,
        "intents_with_duplicate": dup_intents,
        "duplicate_rate": (dup_intents / n) if n else None,
        "duplicate_rate_wilson95": list(ci) if ci else None,
        "lost_effects_unflagged": lost,
        "indeterminate_intents": len(indet),
        "indeterminate_effect_applied": sum(1 for r in indet if r.effects >= 1),
        "indeterminate_effect_absent": sum(1 for r in indet if r.effects == 0),
        "refused_submissions": sum(r.outcomes.count("REFUSED") for r in records),
        "overclaim_success_with_duplicate": overclaim,
        "reconcile_probes": sum(r.reconcile_probes for r in records),
        "reconcile_settled_committed": sum(r.reconcile_statuses.count("SETTLED_COMMITTED") for r in records),
        "reconcile_settled_not_committed": sum(r.reconcile_statuses.count("SETTLED_NOT_COMMITTED") for r in records),
        "reconcile_left_latched": sum(r.reconcile_statuses.count("LATCHED_UNKNOWN") for r in records),
        "reconcile_left_unfenced": sum(r.reconcile_statuses.count("LATCHED_NOT_APPLIED_UNFENCED") for r in records),
        "reconcile_fence_failed": sum(r.reconcile_statuses.count("LATCHED_FENCE_FAILED") for r in records),
        "fenced_write_refusals": sum(r.fenced_refusals for r in records),
        "fence_calls": sum(r.fence_calls for r in records),
        "reconcile_ms_p50": percentile(rlat, 50),
        "reconcile_ms_p95": percentile(rlat, 95),
        "latency_ms_p50": percentile(lat, 50),
        "latency_ms_p95": percentile(lat, 95),
        "latency_samples": len(lat),
    }


def added_latency(records: List[IntentRecord], arm: str) -> Dict[str, Optional[float]]:
    base = {r.idx: r.latency_ms for r in records if r.arm == "A0" and r.latency_ms is not None}
    diffs = [r.latency_ms - base[r.idx] for r in records
             if r.arm == arm and r.latency_ms is not None and r.idx in base]
    clean = [r.latency_ms - base[r.idx] for r in records
             if r.arm == arm and r.fault == "F6" and r.latency_ms is not None and r.idx in base]
    return {
        "added_vs_A0_ms_p50": percentile(diffs, 50),
        "added_vs_A0_ms_p95": percentile(diffs, 95),
        "added_vs_A0_clean_path_F6_ms_p50": percentile(clean, 50),
    }


def run_benchmark(n: int = 300, seed: int = 42, timeout_s: float = 0.35,
                  target_idempotency: bool = False, arms: Tuple[str, ...] = ARMS) -> Dict[str, Any]:
    schedule = build_schedule(n, seed)
    t_start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="eo1_real_dup_") as tmp:
        harness = Harness(Path(tmp), n, seed, timeout_s, target_idempotency)
        harness.port = harness.target.start()
        try:
            records: List[IntentRecord] = []
            for arm in arms:
                records.extend(harness.run_arm(arm, schedule))
            harness.finalize(records)
        finally:
            harness.target.stop()
    wall_s = time.perf_counter() - t_start
    per_arm = {}
    for arm in arms:
        arm_recs = [r for r in records if r.arm == arm]
        summary = summarize(arm_recs)
        summary.update(added_latency(records, arm))
        summary["per_fault"] = {f: summarize([r for r in arm_recs if r.fault == f], f) for f in FAULTS}
        per_arm[arm] = summary
    return {
        "benchmark": "eo1_real_duplicate_benchmark",
        "config": {"n": n, "seed": seed, "client_timeout_s": timeout_s, "max_retries_A0_A1": MAX_RETRIES,
                   "target_idempotency": target_idempotency, "arms": list(arms),
                   "a3_reconcile": {"max_probe_attempts": RECONCILE_MAX_PROBE_ATTEMPTS,
                                    "backoff_initial_s": RECONCILE_BACKOFF_INITIAL_S,
                                    "probe_timeout_s": timeout_s,
                                    "not_committed_retries": 1},
                   "fault_counts": dict(Counter(f for f, _ in schedule)),
                   "limbo_alignment_arXiv_2609_29095v1": LIMBO_ALIGNMENT,
                   "f8_regenerated_fields": sorted(
                       k for k in tool_call_payload("probe", 0)
                       if tool_call_payload("probe", 0)[k] != tool_call_payload("probe", F8_REGENERATED_VARIANT)[k]),
                   "f9_late_commit_factors_x_client_timeout": list(F9_LATE_FACTORS),
                   "a4n3": {"not_applied_confirmations": A4N3_CONFIRMATIONS,
                            "probe_spacing_s": [A4N3_SPACING_FACTOR * timeout_s, 2 * A4N3_SPACING_FACTOR * timeout_s]},
                   "not_applied_basis_per_arm": ARM_NOT_APPLIED_BASIS,
                   "a4_effect_key_schema": EFFECT_KEY_SCHEMA.descriptor(),
                   "a4_effect_key_schema_digest": EFFECT_KEY_SCHEMA.digest(),
                   "python": sys.version.split()[0], "platform": sys.platform},
        "wall_clock_s": wall_s,
        "arms": per_arm,
        "intents": [asdict(r) for r in records],
    }


def _fmt(v: Any, digits: int = 1) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def render_markdown(result: Dict[str, Any]) -> str:
    cfg = result["config"]
    lines = [
        f"EO1 real duplicate benchmark: N={cfg['n']} seed={cfg['seed']} "
        f"timeout={cfg['client_timeout_s']}s target_idempotency={'on' if cfg['target_idempotency'] else 'off'} "
        f"wall={result['wall_clock_s']:.1f}s",
        "",
        "| Arm | Intents | Effects | Dup effects | Dup rate [Wilson 95%] | Lost (unflagged) | "
        "INDETERMINATE (applied/absent) | Refused | Reconcile probes | p50/p95 latency ms | "
        "added vs A0 p50/p95 ms |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, s in result["arms"].items():
        ci = s["duplicate_rate_wilson95"]
        ci_txt = f"[{ci[0]*100:.1f}, {ci[1]*100:.1f}]" if ci else "n/a"
        lines.append(
            f"| {arm} {ARM_LABELS[arm]} | {s['total_intents']} | {s['actual_effects']} | {s['duplicate_effects']} | "
            f"{_fmt(s['duplicate_rate'] * 100 if s['duplicate_rate'] is not None else None)}% {ci_txt} | "
            f"{s['lost_effects_unflagged']} | {s['indeterminate_intents']} "
            f"({s['indeterminate_effect_applied']}/{s['indeterminate_effect_absent']}) | {s['refused_submissions']} | "
            f"{s['reconcile_probes']} | "
            f"{_fmt(s['latency_ms_p50'])}/{_fmt(s['latency_ms_p95'])} | "
            f"{_fmt(s['added_vs_A0_ms_p50'])}/{_fmt(s['added_vs_A0_ms_p95'])} |"
        )
    lines += ["", "Per fault: dup effects [Wilson 95% dup-intent rate] / effects / lost / residual INDETERMINATE "
              "/ reconcile probes (n per cell):", "",
              "| Fault (LIMBO row) | " + " | ".join(result["arms"].keys()) + " |",
              "|---|" + "---|" * len(result["arms"])]
    for f in FAULTS:
        cells = []
        for arm, s in result["arms"].items():
            pf = s["per_fault"][f]
            ci = pf["duplicate_rate_wilson95"]
            ci_txt = f"[{ci[0]*100:.0f},{ci[1]*100:.0f}]%" if ci else "n/a"
            cells.append(f"dup {pf['duplicate_effects']} {ci_txt} / eff {pf['actual_effects']} / "
                         f"lost {pf['lost_effects_unflagged']} / indet {pf['indeterminate_intents']} / "
                         f"probes {pf['reconcile_probes']} (n {pf['total_intents']})")
        lines.append(f"| {f} ({LIMBO_ALIGNMENT[f]}) | " + " | ".join(cells) + " |")
    for arm in RECONCILING_ARMS:
        if arm not in result["arms"]:
            continue
        s = result["arms"][arm]
        lines += ["", f"{arm} reconcile (NOT_APPLIED basis: {ARM_NOT_APPLIED_BASIS[arm]}): settled COMMITTED "
                      f"{s['reconcile_settled_committed']}, NOT_COMMITTED {s['reconcile_settled_not_committed']} "
                      f"(each re-submitted once), left latched UNKNOWN {s['reconcile_left_latched']}, "
                      f"NOT_APPLIED_UNFENCED {s['reconcile_left_unfenced']}, fence failed "
                      f"{s['reconcile_fence_failed']}; fence calls {s['fence_calls']}, fenced write refusals "
                      f"{s['fenced_write_refusals']}; reconcile pass p50/p95 "
                      f"{_fmt(s['reconcile_ms_p50'])}/{_fmt(s['reconcile_ms_p95'])} ms"]
    lines += ["", "F8 regenerated retry (fields changed: "
              + ", ".join(cfg.get("f8_regenerated_fields", [])) + "):", "",
              "| Arm | n | Intents with duplicate | Dup effects | Dup-intent rate [Wilson 95%] | Effects | Refused |",
              "|---|---|---|---|---|---|---|"]
    for arm, s in result["arms"].items():
        pf = s["per_fault"]["F8"]
        ci = pf["duplicate_rate_wilson95"]
        rate = pf["duplicate_rate"]
        ci_txt = f"[{ci[0]*100:.1f}, {ci[1]*100:.1f}]" if ci else "n/a"
        lines.append(
            f"| {arm} {ARM_LABELS[arm]} | {pf['total_intents']} | {pf['intents_with_duplicate']} | "
            f"{pf['duplicate_effects']} | {_fmt(rate * 100 if rate is not None else None)}% "
            f"{ci_txt} | {pf['actual_effects']} | {pf['refused_submissions']} |")
    lines += ["", "F9 late commit (LIMBO timeout_late; read-back answers NOT_APPLIED while the write is in flight):", "",
              "| Arm | NOT_APPLIED basis | n | Intents with duplicate | Dup-intent rate [Wilson 95%] | Effects | "
              "Lost (unflagged) | Residual INDETERMINATE | Fenced write refusals |",
              "|---|---|---|---|---|---|---|---|---|"]
    for arm, s in result["arms"].items():
        pf = s["per_fault"]["F9"]
        ci = pf["duplicate_rate_wilson95"]
        rate = pf["duplicate_rate"]
        ci_txt = f"[{ci[0]*100:.1f}, {ci[1]*100:.1f}]" if ci else "n/a"
        lines.append(
            f"| {arm} | {ARM_NOT_APPLIED_BASIS.get(arm, 'n/a (no reconciler)')} | {pf['total_intents']} | "
            f"{pf['intents_with_duplicate']} | {_fmt(rate * 100 if rate is not None else None)}% {ci_txt} | "
            f"{pf['actual_effects']} | {pf['lost_effects_unflagged']} | {pf['indeterminate_intents']} | "
            f"{pf['fenced_write_refusals']} |")
    by_factor: Dict[str, Dict[float, List[int]]] = {}
    for r in result.get("intents", []):
        if r["fault"] == "F9":
            cell = by_factor.setdefault(r["arm"], {}).setdefault(r["variant"]["late_commit_factor"], [0, 0])
            cell[0] += 1 if r["effects"] > 1 else 0
            cell[1] += 1
    if by_factor:
        lines += ["", "F9 duplicate intents by late-commit factor (x client timeout), dup/n:", "",
                  "| Arm | " + " | ".join(str(f) for f in F9_LATE_FACTORS) + " |",
                  "|---|" + "---|" * len(F9_LATE_FACTORS)]
        for arm in result["arms"]:
            cells = by_factor.get(arm, {})
            lines.append(f"| {arm} | " + " | ".join(
                f"{cells[f][0]}/{cells[f][1]}" if f in cells else "0/0" for f in F9_LATE_FACTORS) + " |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--client-timeout", type=float, default=0.35)
    ap.add_argument("--target-idempotency", choices=("off", "on"), default="off")
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--worker", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker:
        return worker_main(args.worker)
    result = run_benchmark(args.n, args.seed, args.client_timeout, args.target_idempotency == "on")
    tag = f"seed{args.seed}_n{args.n}_idem{args.target_idempotency}"
    out_json = Path(args.out_json or f"/tmp/eo1_real_duplicate_benchmark_{tag}.json")
    out_md = Path(args.out_md or f"/tmp/eo1_real_duplicate_benchmark_{tag}.md")
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md = render_markdown(result)
    out_md.write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    sys.stdout.write(f"\nJSON: {out_json}\nMarkdown: {out_md}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
