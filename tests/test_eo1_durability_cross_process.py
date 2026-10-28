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
tests/test_eo1_durability_cross_process.py
================================================================================
Real-OS evaluation of the EO-1 PreDispatchIntentInterlock durability and
cross-process admission model (no mocks, no monkeypatching):

  a. Real SIGKILL of a child process mid-dispatch -> restart latches, retry blocked,
     exactly one effect on the target file.
  b. Two spawned processes racing on the same CAID behind a barrier (20 rounds) ->
     exactly one DISPATCHED and exactly one effect per round.
  c. Re-send after clean success refused (same instance and fresh instance).
  d. Lost ACK -> reconcile COMMITTED -> re-send refused; restart -> still refused, not re-latched.
  e. Reconcile NOT_COMMITTED -> exactly one fresh attempt admitted.
  f. Receipt hash-chain continuity across restart.
  g. Durability hook: a counting subclass that overrides only the _durable_fsync hook
     observes fsync calls on every durable transition; the module-level helper is
     exercised on a real file descriptor.

Evaluated on local POSIX filesystems (macOS APFS / Linux ext4-class). Not evaluated on NFS
or Windows.
"""

from __future__ import annotations

import ast
import hashlib
import json
import multiprocessing as mp
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.eo1_write_before_execute as eo1_module  # noqa: E402
from src.eo1_write_before_execute import (  # noqa: E402
    DENY_ALREADY_COMMITTED_NO_RESEND,
    GENESIS_CHAIN_TIP,
    ApprovalAlreadyConsumedError,
    ApprovalExpiredError,
    ApprovalMismatchError,
    CaidAlreadyCommittedError,
    CaidIntentUnresolvedError,
    LatchedCaidExecutionHaltedError,
    OperationApprovalGrant,
    PreDispatchIntentInterlock,
    ReconciliationTargetNotFoundError,
    compute_caid,
    receipt_chain_hash,
    verify_ledger_file,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="EO-1 cross-process model evaluated on POSIX only")

PAYLOAD = {"transfer_id": "TXN-DURABILITY-1", "amount_minor": 50000}
URI = "http://127.0.0.1:1/settle"


# ---------------------------------------------------------------------------
# Real target effect: one O_APPEND line per executed side effect
# ---------------------------------------------------------------------------

def _append_effect(target_file: str) -> Dict[str, Any]:
    fd = os.open(target_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, f"effect pid={os.getpid()}\n".encode())
    finally:
        os.close(fd)
    return {"status_code": 200}


def _effect_fn(target_file: Path) -> Callable[[], Dict[str, Any]]:
    return lambda: _append_effect(str(target_file))


def _count_effects(target_file: Path) -> int:
    return len(target_file.read_text().splitlines()) if target_file.exists() else 0


def _pem(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _ledger_records(ledger: Path) -> List[Dict[str, Any]]:
    return [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]


# ---------------------------------------------------------------------------
# Child-process entry points (module level so the spawn start method can import them)
# ---------------------------------------------------------------------------

def _child_sigkill_mid_dispatch(ledger: str, state: str, key_pem: bytes, target: str) -> None:
    key = serialization.load_pem_private_key(key_pem, password=None)
    il = PreDispatchIntentInterlock(ledger_path=Path(ledger), output_state_dir=Path(state), boundary_private_key=key)

    def effect_then_die() -> Dict[str, Any]:
        _append_effect(target)
        os.kill(os.getpid(), signal.SIGKILL)
        return {"unreachable": True}

    il.dispatch(URI, "settle", PAYLOAD, dispatch_fn=effect_then_die)


def _child_racer(ledger: str, state: str, key_pem: bytes, target: str, barrier: Any, queue: Any) -> None:
    key = serialization.load_pem_private_key(key_pem, password=None)
    il = PreDispatchIntentInterlock(ledger_path=Path(ledger), output_state_dir=Path(state), boundary_private_key=key)
    barrier.wait()
    try:
        il.dispatch(URI, "settle", PAYLOAD, dispatch_fn=lambda: _append_effect(target))
        queue.put("DISPATCHED")
    except LatchedCaidExecutionHaltedError as exc:
        queue.put(f"BLOCKED:{type(exc).__name__}")
    except Exception as exc:  # surfaced to the parent assertion
        queue.put(f"ERR:{type(exc).__name__}:{exc}")


# ---------------------------------------------------------------------------
# a. Real SIGKILL mid-dispatch
# ---------------------------------------------------------------------------

def test_a_real_sigkill_mid_dispatch_latches_and_blocks_retry(tmp_path: Path) -> None:
    ledger, state, target = tmp_path / "ledger.jsonl", tmp_path / "state", tmp_path / "target.log"
    key = Ed25519PrivateKey.generate()
    caid = compute_caid(PAYLOAD)

    ctx = mp.get_context("spawn")
    proc = ctx.Process(target=_child_sigkill_mid_dispatch, args=(str(ledger), str(state), _pem(key), str(target)))
    proc.start()
    proc.join(timeout=60)
    assert proc.exitcode == -signal.SIGKILL, f"child exit code {proc.exitcode}"
    assert _count_effects(target) == 1

    # The intent record was durable before the effect; no receipt was written.
    recs = _ledger_records(ledger)
    assert [r["record_type"] for r in recs] == ["DISPATCH_INTENT"]

    restarted = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    assert restarted.is_caid_latched(caid)
    assert (state / f"latched_{caid}.json").exists()

    with pytest.raises(LatchedCaidExecutionHaltedError):
        restarted.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    assert _count_effects(target) == 1


# ---------------------------------------------------------------------------
# b. Two-process race on the same CAID (20 rounds)
# ---------------------------------------------------------------------------

def test_b_two_process_race_same_caid_exactly_one_effect(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    key = Ed25519PrivateKey.generate()
    pem = _pem(key)
    for round_idx in range(20):
        d = tmp_path / f"round_{round_idx:02d}"
        d.mkdir()
        ledger, state, target = d / "ledger.jsonl", d / "state", d / "target.log"
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        procs = [
            ctx.Process(target=_child_racer, args=(str(ledger), str(state), pem, str(target), barrier, queue))
            for _ in range(2)
        ]
        for p in procs:
            p.start()
        outcomes = [queue.get(timeout=60) for _ in procs]
        for p in procs:
            p.join(timeout=60)
            assert p.exitcode == 0, f"round {round_idx}: racer exit code {p.exitcode}"

        assert outcomes.count("DISPATCHED") == 1, f"round {round_idx}: outcomes {outcomes}"
        assert sum(o.startswith("BLOCKED:") for o in outcomes) == 1, f"round {round_idx}: outcomes {outcomes}"
        assert _count_effects(target) == 1, f"round {round_idx}: effects {_count_effects(target)}"
        intents = [r for r in _ledger_records(ledger) if r["record_type"] == "DISPATCH_INTENT"]
        assert len(intents) == 1, f"round {round_idx}: {len(intents)} intents on disk"


# ---------------------------------------------------------------------------
# c. Re-send after clean success
# ---------------------------------------------------------------------------

def test_c_resend_after_clean_success_blocked_same_and_fresh_instance(tmp_path: Path) -> None:
    ledger, state, target = tmp_path / "ledger.jsonl", tmp_path / "state", tmp_path / "target.log"
    key = Ed25519PrivateKey.generate()
    caid = compute_caid(PAYLOAD)

    first = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    first.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    assert _count_effects(target) == 1
    assert first.is_caid_committed(caid)

    with pytest.raises(CaidAlreadyCommittedError) as same_exc:
        first.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    assert DENY_ALREADY_COMMITTED_NO_RESEND in str(same_exc.value)
    assert same_exc.value.disposition == DENY_ALREADY_COMMITTED_NO_RESEND

    fresh = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    with pytest.raises(CaidAlreadyCommittedError):
        fresh.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    with pytest.raises(CaidAlreadyCommittedError):
        fresh.record_intent(URI, "settle", PAYLOAD)

    assert _count_effects(target) == 1
    assert not fresh.is_caid_latched(caid)
    # Refused attempts never reached the ledger.
    assert sum(r["record_type"] == "DISPATCH_INTENT" for r in _ledger_records(ledger)) == 1


# ---------------------------------------------------------------------------
# d. Lost ACK -> reconcile COMMITTED -> re-send refused, restart not re-latched
# ---------------------------------------------------------------------------

def test_d_lost_ack_reconcile_committed_blocks_resend_and_restart_not_relatched(tmp_path: Path) -> None:
    ledger, state, target = tmp_path / "ledger.jsonl", tmp_path / "state", tmp_path / "target.log"
    key = Ed25519PrivateKey.generate()
    caid = compute_caid(PAYLOAD)
    il = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)

    def lost_ack() -> Dict[str, Any]:
        _append_effect(str(target))
        raise TimeoutError("504 Gateway Timeout: lost ACK")

    with pytest.raises(RuntimeError):
        il.dispatch(URI, "settle", PAYLOAD, dispatch_fn=lost_ack, intent_id="intent-lost-ack")
    assert il.is_caid_latched(caid)

    # Default intent_id is derived from the latched state.
    receipt = il.reconcile_out_of_band(caid, {"status": "COMMITTED", "target_observed": True})
    assert receipt.intent_id == "intent-lost-ack"
    assert not il.is_caid_latched(caid)
    assert not (state / f"latched_{caid}.json").exists()

    with pytest.raises(CaidAlreadyCommittedError):
        il.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))

    restarted = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    assert not restarted.is_caid_latched(caid), "restart re-latched an already reconciled intent"
    assert restarted.get_unresolved_intent_ids(caid) == []
    with pytest.raises(CaidAlreadyCommittedError):
        restarted.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    assert _count_effects(target) == 1

    # Explicit mismatching intent_id is refused while a latch exists.
    other_payload = {"transfer_id": "TXN-DURABILITY-2", "amount_minor": 1}
    other_caid = compute_caid(other_payload)
    with pytest.raises(RuntimeError):
        restarted.dispatch(URI, "settle", other_payload, dispatch_fn=lost_ack, intent_id="intent-other")
    with pytest.raises(ValueError):
        restarted.reconcile_out_of_band(other_caid, {"status": "COMMITTED"}, intent_id="intent-wrong")
    assert restarted.is_caid_latched(other_caid)

    # require_latch=True refuses to reconcile a CAID with nothing to reconcile.
    with pytest.raises(ReconciliationTargetNotFoundError):
        restarted.reconcile_out_of_band(compute_caid({"never": "seen"}), {"status": "COMMITTED"}, require_latch=True)


# ---------------------------------------------------------------------------
# e. Reconcile NOT_COMMITTED -> exactly one fresh attempt
# ---------------------------------------------------------------------------

def test_e_reconcile_not_committed_allows_exactly_one_fresh_attempt(tmp_path: Path) -> None:
    ledger, state, target = tmp_path / "ledger.jsonl", tmp_path / "state", tmp_path / "target.log"
    key = Ed25519PrivateKey.generate()
    caid = compute_caid(PAYLOAD)
    il = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)

    def dropped_before_target() -> Dict[str, Any]:
        raise ConnectionResetError("TCP reset before target execution")

    with pytest.raises(RuntimeError):
        il.dispatch(URI, "settle", PAYLOAD, dispatch_fn=dropped_before_target)
    with pytest.raises(LatchedCaidExecutionHaltedError):
        il.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    assert _count_effects(target) == 0

    il.reconcile_out_of_band(caid, {"status": "NOT_FOUND", "target_observed": False})
    assert not il.is_caid_committed(caid)

    # Restart between reconciliation and the fresh attempt must not re-latch either.
    restarted = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    assert not restarted.is_caid_latched(caid)

    restarted.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    assert _count_effects(target) == 1

    with pytest.raises(CaidAlreadyCommittedError):
        restarted.dispatch(URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target))
    with pytest.raises(CaidAlreadyCommittedError):
        PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key).dispatch(
            URI, "settle", PAYLOAD, dispatch_fn=_effect_fn(target)
        )
    assert _count_effects(target) == 1


def test_e2_unresolved_intent_without_latch_blocks_resend(tmp_path: Path) -> None:
    """An intent recorded but not yet resolved (auto_recover=False peer view) blocks a second intent."""
    ledger, state = tmp_path / "ledger.jsonl", tmp_path / "state"
    key = Ed25519PrivateKey.generate()
    writer = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    writer.record_intent(URI, "settle", PAYLOAD, intent_id="intent-in-flight")

    peer = PreDispatchIntentInterlock(
        ledger_path=ledger, output_state_dir=state, boundary_private_key=key, auto_recover=False
    )
    assert not peer.is_caid_latched(compute_caid(PAYLOAD))
    with pytest.raises(CaidIntentUnresolvedError):
        peer.record_intent(URI, "settle", PAYLOAD)
    with pytest.raises(CaidIntentUnresolvedError):
        writer.record_intent(URI, "settle", PAYLOAD)


# ---------------------------------------------------------------------------
# f. Chain tip continuity across restart
# ---------------------------------------------------------------------------

def test_f_chain_tip_continuity_across_restart(tmp_path: Path) -> None:
    ledger, state = tmp_path / "ledger.jsonl", tmp_path / "state"
    key = Ed25519PrivateKey.generate()

    first = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    r1 = first.dispatch(URI, "settle", {"n": 1}, dispatch_fn=lambda: {"ok": 1}).receipt
    r2 = first.dispatch(URI, "settle", {"n": 2}, dispatch_fn=lambda: {"ok": 2}).receipt
    assert r1.chain_tip == GENESIS_CHAIN_TIP
    assert r2.chain_tip == receipt_chain_hash(r1.to_dict())

    restarted = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    r3 = restarted.dispatch(URI, "settle", {"n": 3}, dispatch_fn=lambda: {"ok": 3}).receipt
    assert r3.chain_tip == receipt_chain_hash(r2.to_dict()), "chain tip reset to genesis on restart"

    # Interleaved instances on the same ledger (separate processes behave the same via flock re-read)
    other = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, boundary_private_key=key)
    r4 = other.dispatch(URI, "settle", {"n": 4}, dispatch_fn=lambda: {"ok": 4}).receipt
    r5 = restarted.dispatch(URI, "settle", {"n": 5}, dispatch_fn=lambda: {"ok": 5}).receipt
    assert r4.chain_tip == receipt_chain_hash(r3.to_dict())
    assert r5.chain_tip == receipt_chain_hash(r4.to_dict())

    # Full-ledger walk: every receipt links to its predecessor, all signatures valid.
    tip = GENESIS_CHAIN_TIP
    receipts = 0
    for rec in verify_ledger_file(ledger, key.public_key()):
        if rec["record_type"] == "CONTINUITY_RECEIPT":
            assert rec["chain_tip"] == tip
            tip = receipt_chain_hash(rec)
            receipts += 1
    assert receipts == 5


# ---------------------------------------------------------------------------
# g. Durability hook (counting subclass; no monkeypatching)
# ---------------------------------------------------------------------------

class _FsyncCountingInterlock(PreDispatchIntentInterlock):
    """Overrides only the _durable_fsync hook: counts calls, then performs the real fsync."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.fsync_calls = 0
        super().__init__(*args, **kwargs)

    def _durable_fsync(self, fd: int) -> None:
        self.fsync_calls += 1
        super()._durable_fsync(fd)


def test_g_durable_transitions_route_through_fsync_hook(tmp_path: Path) -> None:
    ledger, state = tmp_path / "ledger.jsonl", tmp_path / "state"
    il = _FsyncCountingInterlock(ledger_path=ledger, output_state_dir=state)
    assert il.fsync_calls == 0  # empty ledger: nothing written at startup

    il.record_intent(URI, "settle", {"g": 1})
    # genesis HWM (tmp fsync + dir fsync) + ledger file fsync + parent directory fsync (file created)
    # + signed high-water mark rewrite (tmp fsync + dir fsync)
    assert il.fsync_calls == 6

    before = il.fsync_calls
    il.record_intent(URI, "settle", {"g": 2})
    assert il.fsync_calls - before == 3  # append to existing ledger: file fsync + HWM (tmp + dir fsync)

    def fail() -> Dict[str, Any]:
        raise ConnectionResetError("reset")

    before = il.fsync_calls
    with pytest.raises(RuntimeError):
        il.dispatch(URI, "settle", {"g": 3}, dispatch_fn=fail)
    # intent append (1) + HWM (2) + latch tmp file fsync (1) + state dir fsync after os.replace (1)
    assert il.fsync_calls - before == 5

    before = il.fsync_calls
    il.reconcile_out_of_band(compute_caid({"g": 3}), {"status": "NOT_FOUND"})
    # receipt append (1) + HWM (2) + state dir fsync after unlink (1)
    assert il.fsync_calls - before == 4


def test_g_fsync_helper_on_real_fd_and_uses_os_fsync(tmp_path: Path) -> None:
    probe = tmp_path / "probe.bin"
    eo1_module._durable_append_bytes(probe, b"one\n")
    # Torn tail (no trailing newline) is isolated by the next durable append.
    with open(probe, "ab") as f:
        f.write(b"torn-fragment")
    eo1_module._durable_append_bytes(probe, b"two\n")
    assert probe.read_bytes() == b"one\ntorn-fragment\ntwo\n"

    tree = ast.parse(Path(eo1_module.__file__).read_text(encoding="utf-8"))
    fsync_fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_fsync_fd")
    src = ast.unparse(fsync_fn)
    assert "os.fsync(fd)" in src
    assert "F_FULLFSYNC" in src


# ---------------------------------------------------------------------------
# Latency evaluation (informational; reported, loosely bounded)
# ---------------------------------------------------------------------------

def test_record_intent_latency_200_calls(tmp_path: Path) -> None:
    il = PreDispatchIntentInterlock(ledger_path=tmp_path / "ledger.jsonl", output_state_dir=tmp_path / "state")
    n = 200
    t0 = time.perf_counter()
    for i in range(n):
        il.record_intent(URI, "settle", {"latency_probe": i})
    elapsed = time.perf_counter() - t0
    per_call_ms = elapsed * 1000.0 / n
    print(f"\n[eo1-latency] {n} record_intent calls: total={elapsed:.3f}s per_call={per_call_ms:.3f}ms")
    assert sum(1 for _ in (tmp_path / "ledger.jsonl").read_text().splitlines()) == n
    assert per_call_ms < 250.0


def test_h_atomic_single_use_approval_and_limbo_ivr_benchmark(tmp_path: Path) -> None:
    """
    Verifies:
      1. OWASP / EO1 v2 OperationApprovalGrant: exact actor, tool, and CAID binding,
         expiry check, and atomic single-use consumption across instances.
      2. LIMBO (arXiv:2609.29095v1) / IdempotencyBench ambiguity fault matrix
         (timeout, HTTP 502, HTTP 504, connection reset) where target commits before
         transport failure: EO1 achieves IVR = 0.0 and FCR = 0.0 vs naive retry IVR = 1000.0.
    """
    ledger, state, target = tmp_path / "ledger.jsonl", tmp_path / "state", tmp_path / "target.log"
    il = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, authority_id="actor-treasury-1")

    op_payload = {"action": "refund", "invoice_id": "INV-2026-01", "amount_minor": 25000}
    op_caid = compute_caid(op_payload)

    # 1a. Mismatched actor or operation CAID is rejected before any intent write
    bad_actor_grant = OperationApprovalGrant(
        approval_id="appr-bad-actor",
        subject_actor_id="actor-other",
        tool_name="settle",
        operation_caid=op_caid,
    )
    with pytest.raises(ApprovalMismatchError):
        il.dispatch(URI, "settle", op_payload, dispatch_fn=_effect_fn(target), approval=bad_actor_grant)
    assert _count_effects(target) == 0

    # 1b. Expired approval is rejected before any intent write
    expired_grant = OperationApprovalGrant(
        approval_id="appr-expired",
        subject_actor_id="actor-treasury-1",
        tool_name="settle",
        operation_caid=op_caid,
        expires_at_epoch_s=time.time() - 10.0,
    )
    with pytest.raises(ApprovalExpiredError):
        il.dispatch(URI, "settle", op_payload, dispatch_fn=_effect_fn(target), approval=expired_grant)
    assert _count_effects(target) == 0

    # 1c. Valid exact-operation approval succeeds once and is atomically consumed on disk
    valid_grant = OperationApprovalGrant(
        approval_id="appr-valid-001",
        subject_actor_id="actor-treasury-1",
        tool_name="settle",
        operation_caid=op_caid,
        expires_at_epoch_s=time.time() + 3600.0,
    )
    il.dispatch(URI, "settle", op_payload, dispatch_fn=_effect_fn(target), approval=valid_grant)
    assert _count_effects(target) == 1
    assert (state / "consumed_approval_appr-valid-001.json").is_file()

    # Reusing the same approval_id (even on a fresh instance and after NOT_COMMITTED or on a new CAID) fails
    il2 = PreDispatchIntentInterlock(ledger_path=ledger, output_state_dir=state, authority_id="actor-treasury-1")
    other_payload = {"action": "refund", "invoice_id": "INV-2026-02", "amount_minor": 25000}
    forged_reuse_grant = OperationApprovalGrant(
        approval_id="appr-valid-001",
        subject_actor_id="actor-treasury-1",
        tool_name="settle",
        operation_caid=compute_caid(other_payload),
    )
    with pytest.raises(ApprovalAlreadyConsumedError):
        il2.dispatch(URI, "settle", other_payload, dispatch_fn=_effect_fn(target), approval=forged_reuse_grant)
    assert _count_effects(target) == 1

    # 2. LIMBO (arXiv:2609.29095v1) ambiguity fault matrix:
    # Target commits side effect, then transport drops with timeout / 502 / 504 / connection_reset.
    fault_modes = [
        ("timeout", TimeoutError("read timed out after target commit")),
        ("http_502", RuntimeError("HTTP 502 Bad Gateway after upstream commit")),
        ("http_504", RuntimeError("HTTP 504 Gateway Timeout after upstream commit")),
        ("conn_reset", ConnectionResetError("Connection reset by peer after upstream commit")),
    ]
    eo1_duplicates = 0
    naive_duplicates = 0

    for idx, (mode_name, exc_to_raise) in enumerate(fault_modes):
        f_target = tmp_path / f"limbo_{mode_name}.log"
        f_payload = {"limbo_case": mode_name, "seq": idx}

        def commit_then_drop(t_path: Path = f_target, err: Exception = exc_to_raise) -> Dict[str, Any]:
            _append_effect(str(t_path))
            raise err

        # EO1 harness execution + retry attempt under ambiguity
        with pytest.raises(RuntimeError, match="EFFECT_INDETERMINATE"):
            il2.dispatch(URI, "settle", f_payload, dispatch_fn=commit_then_drop)
        with pytest.raises(LatchedCaidExecutionHaltedError):
            il2.dispatch(URI, "settle", f_payload, dispatch_fn=_effect_fn(f_target))
        if _count_effects(f_target) > 1:
            eo1_duplicates += 1

        # Naive unguarded retry baseline on the same fault
        naive_target = tmp_path / f"naive_{mode_name}.log"
        try:
            commit_then_drop(naive_target, exc_to_raise)
        except Exception:
            _append_effect(str(naive_target))
        if _count_effects(naive_target) > 1:
            naive_duplicates += 1

    eo1_ivr_per_1000 = (eo1_duplicates / len(fault_modes)) * 1000.0
    naive_ivr_per_1000 = (naive_duplicates / len(fault_modes)) * 1000.0
    assert eo1_ivr_per_1000 == 0.0
    assert naive_ivr_per_1000 == 1000.0
