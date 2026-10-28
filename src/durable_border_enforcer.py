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
src/durable_border_enforcer.py
================================================================================
Durable Execution Boundary Enforcer: Cross-Process File Locking, WAL Nonce Burning,
A2A #1857 Task Escort, and Crash-Resilient Indeterminate Holding.

Enforces Manifesto Law #1 & Defect Remediations F4, F5, F6:
1. Cross-process isolation via POSIX `fcntl.flock(LOCK_EX)`.
2. Durable append-only write-ahead ledger with `F_FULLFSYNC` (macOS) / `os.fsync`.
3. Nonce burning is persistent across process restarts (prevents replay attacks).
4. `DISPATCHED_UNCONFIRMED` escrow state is persistent across restarts (prevents blind retries).
5. Wraps pure decision predicates in `src/border_policy.py`.
"""

from __future__ import annotations

import errno
import json
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Set, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.border_policy import (
    BorderVerdict,
    CancelledAtState,
    PolicyManifest,
    SignedHumanActionWarrant,
    TaintTier,
    TaskEscortState,
    canonical_json_v1,
    compute_action_caid,
    evaluate_action_admissibility,
)


def _fsync_fd(fd: int) -> None:
    """Invokes Darwin F_FULLFSYNC when available, falling back to os.fsync."""
    if sys.platform == "darwin" and fcntl is not None:
        try:
            fcntl.fcntl(fd, 51)  # F_FULLFSYNC
            return
        except (OSError, AttributeError):
            pass
    os.fsync(fd)


def _fsync_dir(dir_path: Path) -> None:
    """Fsyncs directory fd to persist directory entry creations."""
    try:
        dfd = os.open(str(dir_path), os.O_RDONLY)
        try:
            _fsync_fd(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


def _durable_append_line(file_path: Path, raw_line: bytes) -> None:
    """Durable append loop with short write handling and full fsync."""
    is_new = not file_path.exists()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(str(file_path), flags, 0o600)
    try:
        total = 0
        while total < len(raw_line):
            written = os.write(fd, raw_line[total:])
            if written == 0:
                raise OSError("Zero bytes written during durable append")
            total += written
        _fsync_fd(fd)
    finally:
        os.close(fd)

    if is_new:
        _fsync_dir(file_path.parent)


class DurableBorderEnforcer:
    """
    Durable Default-Deny Border Gate + A2A #1857 Task Escort.
    Coordinates pure evaluation predicates with durable on-disk state.
    """

    def __init__(
        self,
        policy: PolicyManifest,
        ledger_dir: Path,
        human_pub_key: Ed25519PublicKey,
        gate_private_key: Optional[Ed25519PrivateKey] = None,
    ) -> None:
        self.policy = policy
        self.ledger_dir = Path(ledger_dir)
        self.human_pub_key = human_pub_key
        self.gate_private_key = gate_private_key or Ed25519PrivateKey.generate()

        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.ledger_dir / ".border.lock"
        self._nonce_ledger_path = self.ledger_dir / "nonce_burns.jsonl"
        self._escrow_ledger_path = self.ledger_dir / "escrow_states.jsonl"

        self._thread_lock = threading.RLock()
        self._flock_depth = 0
        self._burned_nonces_cache: Set[str] = set()
        self._escrow_state_cache: Dict[str, Tuple[TaskEscortState, CancelledAtState]] = {}

        # Initial state sync from durable ledger
        with self._exclusive():
            pass

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        """Provides in-process thread safety and cross-process fcntl.flock exclusion."""
        with self._thread_lock:
            flock_fd: Optional[int] = None
            if self._flock_depth == 0:
                if fcntl is None:
                    raise OSError(errno.ENOTSUP, "fcntl.flock unavailable; border enforcer refuses to operate")
                fd = os.open(str(self._lock_path), os.O_RDWR | os.O_CREAT, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                    flock_fd = fd
                except BaseException:
                    os.close(fd)
                    raise
            self._flock_depth += 1
            try:
                self._sync_on_disk_state()
                yield
            finally:
                self._flock_depth -= 1
                if self._flock_depth == 0 and flock_fd is not None:
                    try:
                        fcntl.flock(flock_fd, fcntl.LOCK_UN)
                    finally:
                        os.close(flock_fd)

    def _sync_on_disk_state(self) -> None:
        """Reads ledger files to reconstruct burned nonces and active escrow states."""
        # 1. Nonce burns
        if self._nonce_ledger_path.exists():
            with open(self._nonce_ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        nonce = rec.get("nonce")
                        if isinstance(nonce, str):
                            self._burned_nonces_cache.add(nonce)
                    except json.JSONDecodeError:
                        continue

        # 2. Escrow states
        if self._escrow_ledger_path.exists():
            with open(self._escrow_ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        caid = rec.get("action_caid")
                        estate = rec.get("escort_state")
                        cstate = rec.get("cancelled_at")
                        if isinstance(caid, str) and isinstance(estate, str) and isinstance(cstate, str):
                            self._escrow_state_cache[caid] = (
                                TaskEscortState(estate),
                                CancelledAtState(cstate),
                            )
                    except (json.JSONDecodeError, ValueError):
                        continue

    def burn_nonce_durable(self, nonce: str, warrant_id: str, action_caid: str, now_ns: int) -> None:
        """Persists a burned nonce to the WAL ledger with immediate fsync."""
        rec = {
            "action_caid": action_caid,
            "burned_at_ns": now_ns,
            "nonce": nonce,
            "warrant_id": warrant_id,
        }
        line_bytes = canonical_json_v1(rec) + b"\n"
        _durable_append_line(self._nonce_ledger_path, line_bytes)
        self._burned_nonces_cache.add(nonce)

    def persist_escrow_state(
        self,
        action_caid: str,
        escort_state: TaskEscortState,
        cancelled_at: CancelledAtState,
        now_ns: int,
    ) -> None:
        """Persists an action's escort state to the escrow ledger with immediate fsync."""
        rec = {
            "action_caid": action_caid,
            "cancelled_at": cancelled_at.value,
            "escort_state": escort_state.value,
            "updated_at_ns": now_ns,
        }
        line_bytes = canonical_json_v1(rec) + b"\n"
        _durable_append_line(self._escrow_ledger_path, line_bytes)
        self._escrow_state_cache[action_caid] = (escort_state, cancelled_at)

    def evaluate_and_escort(
        self,
        action_name: str,
        args: Dict[str, Any],
        now_ns: int,
        dispatch_fn: Callable[[], Dict[str, Any]],
        warrant: Optional[SignedHumanActionWarrant] = None,
        taint_tier: int = int(TaintTier.TIER_0_SYSTEM),
        simulated_cancel_at: CancelledAtState = CancelledAtState.NONE,
    ) -> BorderVerdict:
        """
        Coordinates boundary admission, durable nonce burning, task execution,
        and A2A #1857 failure escort.
        """
        caid = compute_action_caid(action_name, args, self.policy.tenant_id, self.policy.agent_id)

        with self._exclusive():
            # 1. A2A #1857 Idempotency & Post-Cancel State Check from durable ledger
            existing = self._escrow_state_cache.get(caid)
            if existing is not None:
                existing_escort, existing_cancel = existing
                if existing_escort == TaskEscortState.DISPATCHED_UNCONFIRMED:
                    return BorderVerdict(
                        allowed=False,
                        reason_code="HALT_A2A_DISPATCHED_UNCONFIRMED_NO_BLIND_RETRY",
                        action_caid=caid,
                        escort_state=TaskEscortState.DISPATCHED_UNCONFIRMED,
                        cancelled_at_state=existing_cancel,
                    )
                if existing_escort == TaskEscortState.COMMITTED:
                    return BorderVerdict(
                        allowed=False,
                        reason_code="DENY_A2A_ALREADY_COMMITTED_IDEMPOTENT_BLOCK",
                        action_caid=caid,
                        escort_state=TaskEscortState.COMMITTED,
                        cancelled_at_state=CancelledAtState.NONE,
                    )

            # 2. Evaluate pure admissibility predicates
            verdict = evaluate_action_admissibility(
                action_name=action_name,
                args=args,
                policy=self.policy,
                now_ns=now_ns,
                warrant=warrant,
                taint_tier=taint_tier,
                burned_nonces=frozenset(self._burned_nonces_cache),
                human_pub_key=self.human_pub_key,
                action_caid=caid,
            )
            if not verdict.allowed:
                return verdict

            # 3. A2A #1857 Before-Start Cancellation is clean and safe
            if simulated_cancel_at == CancelledAtState.BEFORE_START:
                self.persist_escrow_state(
                    caid,
                    TaskEscortState.CANCELLED_CLEAN_BEFORE_START,
                    CancelledAtState.BEFORE_START,
                    now_ns,
                )
                return BorderVerdict(
                    allowed=False,
                    reason_code="CANCELLED_CLEAN_BEFORE_START",
                    action_caid=caid,
                    escort_state=TaskEscortState.CANCELLED_CLEAN_BEFORE_START,
                    cancelled_at_state=CancelledAtState.BEFORE_START,
                )

            # 4. Burn warrant nonce on disk BEFORE dispatch
            if warrant is not None:
                self.burn_nonce_durable(warrant.nonce, warrant.warrant_id, caid, now_ns)

            # 5. Handle simulated mid-call or post-call cancellation
            if simulated_cancel_at in (CancelledAtState.MID_TOOL_CALL, CancelledAtState.POST_TOOL_CALL):
                self.persist_escrow_state(
                    caid,
                    TaskEscortState.DISPATCHED_UNCONFIRMED,
                    simulated_cancel_at,
                    now_ns,
                )
                return BorderVerdict(
                    allowed=False,
                    reason_code="HALT_A2A_CANCELLED_MID_CALL_ESCROW_LOCKED",
                    action_caid=caid,
                    escort_state=TaskEscortState.DISPATCHED_UNCONFIRMED,
                    cancelled_at_state=simulated_cancel_at,
                )

            # 6. Execute dispatch function; catch failures and freeze state
            try:
                dispatch_fn()
            except Exception:
                self.persist_escrow_state(
                    caid,
                    TaskEscortState.DISPATCHED_UNCONFIRMED,
                    CancelledAtState.MID_TOOL_CALL,
                    now_ns,
                )
                return BorderVerdict(
                    allowed=False,
                    reason_code="HALT_TRANSPORT_DROP_DISPATCHED_UNCONFIRMED",
                    action_caid=caid,
                    escort_state=TaskEscortState.DISPATCHED_UNCONFIRMED,
                    cancelled_at_state=CancelledAtState.MID_TOOL_CALL,
                )

            # 7. Clean commit
            self.persist_escrow_state(
                caid,
                TaskEscortState.COMMITTED,
                CancelledAtState.NONE,
                now_ns,
            )
            return BorderVerdict(
                allowed=True,
                reason_code="OK_COMMITTED",
                action_caid=caid,
                escort_state=TaskEscortState.COMMITTED,
                cancelled_at_state=CancelledAtState.NONE,
            )
