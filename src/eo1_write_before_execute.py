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
src/eo1_write_before_execute.py
================================================================================
AEIB EO-1 Evidence-Before-Effect Pre-Dispatch Intent Interlock.
Evaluated under the stated model. Preserves strict epistemic lock.

Core Invariants:
  1. Wire access is conditioned on an immutable pre-dispatch ledger record.
     Zero network connections or bytes are transmitted if the intent write fails.
  2. If an outbound call is interrupted mid-syscall (e.g. SIGKILL, crash, or wire fault),
     the unfulfilled intent is latched into EFFECT_INDETERMINATE with retry_safe: False.
  3. Subsequent mutations on a latched CAID are halted fail-closed until out-of-band
     reconciliation resolves target-side state.
  4. A CAID with a COMMITTED continuity receipt (clean dispatch success or out-of-band
     reconciliation classified as COMMITTED) is refused for re-send with disposition
     DENY_ALREADY_COMMITTED_NO_RESEND. Reconciliation classified as NOT_COMMITTED
     re-opens the CAID for a fresh attempt.
  5. A CAID with an unresolved DISPATCH_INTENT on disk (in flight in this or another
     process, or orphaned by a crash) is refused with DENY_INTENT_UNRESOLVED_NO_RESEND.

Durability and concurrency model (as configured, evaluated on local POSIX filesystems):
  - Ledger appends use os.open(O_APPEND) + short-write loop + fsync (F_FULLFSYNC on
    darwin when available) before dispatch proceeds; the parent directory is fsynced
    when the ledger file is created.
  - Latch markers are written tmp-file -> fsync -> os.replace -> directory fsync;
    latch removal is followed by a directory fsync.
  - Startup recovery (under the flock) removes orphan temp files ".<target>.<pid>.<tid>.tmp"
    left by a writer killed inside an atomic write, only for targets this interlock writes
    (the HWM, latch and consumed-approval markers), only when the writer pid no longer exists,
    and never through a symlink; the directory is fsynced afterwards and an unlink failure
    halts with ORPHAN_TMP_REAP_FAILED. Counts: ``boot_reaped_tmp_count`` /
    ``boot_reaped_tmp_names`` / ``boot_retained_tmp``.
  - State transitions (record_intent, dispatch latch/receipt, reconcile, latch_intent,
    startup recovery) hold a threading.RLock plus an fcntl.flock(LOCK_EX) on a sibling
    "<ledger>.lock" file, and re-read on-disk ledger + latch state inside the lock.
  - Not evaluated: network filesystems (NFS/SMB flock and fsync semantics differ),
    Windows (no fcntl; the interlock refuses to operate there), storage devices that
    acknowledge flushes without persisting them.

Ledger integrity model (as configured, tested with real files and real Ed25519 keys):
  - Every record read from disk is verified against the trusted boundary public key(s)
    (the interlock's own key plus any ``trusted_public_keys``). Records that fail
    verification are *untrusted* and may only add restrictions: an untrusted
    DISPATCH_INTENT still counts as unresolved, while an untrusted CONTINUITY_RECEIPT
    never resolves an intent, never unlocks a CAID, and taints its CAID with disposition
    HALT_LEDGER_INTEGRITY_VIOLATION until a later trusted receipt for the CAID supersedes it.
  - A signed high-water mark (HWM) is kept in "<ledger>.hwm" and rewritten atomically
    (tmp -> fsync -> os.replace -> directory fsync) after every append. With the default
    ``flush_policy="barrier_then_single_full_flush"`` the ledger append, its directory entry
    and the HWM tmp file are flushed with F_BARRIERFSYNC on darwin (fsync + I/O ordering
    barrier, no device cache flush) and the final directory flush after os.replace is an
    F_FULLFSYNC, which per fcntl(2) asks the drive to flush *all* buffered data; record_intent
    and receipts return only after that flush, so the ledger record and its HWM are both
    flushed before dispatch, as with ``flush_policy="full_flush_every_write"`` (one
    F_FULLFSYNC per step). If the final directory flush cannot issue F_FULLFSYNC, the ledger
    and HWM files are each flushed with the full primitive as a fallback. On non-darwin hosts
    both policies call os.fsync for every step. Not evaluated: actual power-loss testing of
    either policy. It binds record
    count, ledger byte length, SHA-256 of the ledger prefix, receipt chain tip and a
    monotonic sequence number. A ledger shorter than the HWM, or whose prefix does not
    hash to the HWM digest, halts the interlock with LedgerIntegrityViolationError.
  - Limitation (not detectable locally): replacing BOTH the ledger and the HWM with a
    consistent older pair (or deleting both) cannot be distinguished from a genuine older
    state without an external anchor. Operators should anchor ``high_water_mark_digest()``
    / the HWM sequence outside this host (e.g. a transparency log or a peer) and pass the
    last anchored sequence as ``min_hwm_seq`` on restart.
  - When the interlock is constructed without an explicit ``boundary_private_key`` (or
    ``trusted_public_keys``) it holds an ephemeral key and cannot authenticate history
    written by an earlier process; in that configuration a missing HWM, or an HWM signed
    by an unknown key, is logged and enforced restrictively instead of halting.
  - Ledger, HWM, lock and latch files are opened with O_NOFOLLOW and must be regular
    files owned by the current uid; the ledger and state directories must not be
    symlinks and must be owned by the current uid.
"""

from __future__ import annotations

import base64
import errno
import hashlib
import json
import logging
import os
import re
import stat
import sys
import threading
import urllib.request
import urllib.error
from contextlib import ExitStack, contextmanager

try:  # POSIX only; absence makes every locked transition fail closed.
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


class IntentLifecycleState(str, Enum):
    INTENT_COMMITTED = "INTENT_COMMITTED"
    DISPATCH_IN_FLIGHT = "DISPATCH_IN_FLIGHT"
    RECONCILED = "RECONCILED"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"


class PreDispatchLedgerWriteError(RuntimeError):
    """Raised when writing the pre-dispatch intent record to disk fails."""
    pass


class LatchedCaidExecutionHaltedError(RuntimeError):
    """Raised when dispatch on a latched CAID is blocked fail-closed."""
    pass


class IntentVerificationError(ValueError):
    """Raised when cryptographic verification of an intent or receipt fails."""
    pass


# Dispositions recorded in CONTINUITY_RECEIPT.reconciliation_details[DISPOSITION_KEY].
DISPOSITION_KEY = "eo1_effect_disposition"
DISPOSITION_COMMITTED = "COMMITTED"
DISPOSITION_NOT_COMMITTED = "NOT_COMMITTED"

DENY_ALREADY_COMMITTED_NO_RESEND = "DENY_ALREADY_COMMITTED_NO_RESEND"
DENY_INTENT_UNRESOLVED_NO_RESEND = "DENY_INTENT_UNRESOLVED_NO_RESEND"

GENESIS_CHAIN_TIP = hashlib.sha256(b"aeib-eo1-chain-genesis").hexdigest()


class CaidAlreadyCommittedError(LatchedCaidExecutionHaltedError):
    """
    Raised when a CAID already carries a COMMITTED continuity receipt.
    Subclasses LatchedCaidExecutionHaltedError so existing fail-closed handlers still catch it.
    """
    disposition = DENY_ALREADY_COMMITTED_NO_RESEND


class CaidIntentUnresolvedError(LatchedCaidExecutionHaltedError):
    """
    Raised when a CAID has an unresolved DISPATCH_INTENT on disk (in flight elsewhere or orphaned).
    Subclasses LatchedCaidExecutionHaltedError so existing fail-closed handlers still catch it.
    """
    disposition = DENY_INTENT_UNRESOLVED_NO_RESEND


class ReconciliationTargetNotFoundError(ValueError):
    """Raised when reconcile_out_of_band(require_latch=True) finds no latch or unresolved intent."""
    pass


class ApprovalAlreadyConsumedError(LatchedCaidExecutionHaltedError):
    """Raised when a single-use OperationApprovalGrant has already been consumed on disk."""
    pass


class ApprovalMismatchError(LatchedCaidExecutionHaltedError):
    """Raised when an OperationApprovalGrant does not match the actor, tool, or canonical operation CAID."""
    pass


class ApprovalExpiredError(LatchedCaidExecutionHaltedError):
    """Raised when an OperationApprovalGrant has passed its expiration timestamp."""
    pass


HALT_LEDGER_INTEGRITY_VIOLATION = "HALT_LEDGER_INTEGRITY_VIOLATION"

# Reasons carried by LedgerIntegrityViolationError.reason
INTEGRITY_UNTRUSTED_RECEIPT = "UNTRUSTED_RECEIPT"
INTEGRITY_LEDGER_MISSING = "LEDGER_MISSING_BELOW_HWM"
INTEGRITY_LEDGER_TRUNCATED = "LEDGER_TRUNCATED_BELOW_HWM"
INTEGRITY_LEDGER_DIVERGES = "LEDGER_DIVERGES_FROM_HWM"
INTEGRITY_HWM_MISSING = "HWM_MISSING"
INTEGRITY_HWM_MALFORMED = "HWM_MALFORMED"
INTEGRITY_HWM_SIGNATURE_INVALID = "HWM_SIGNATURE_INVALID"
INTEGRITY_HWM_SIGNER_UNTRUSTED = "HWM_SIGNER_UNTRUSTED"
INTEGRITY_HWM_SEQ_REGRESSED = "HWM_SEQ_REGRESSED"
INTEGRITY_ORPHAN_TMP_REAP_FAILED = "ORPHAN_TMP_REAP_FAILED"

# Temp files written by _atomic_write_text: ".<target>.<pid>.<thread id>.tmp".
_ORPHAN_TMP_NAME_RE = re.compile(r"^\.(?P<target>.+)\.(?P<pid>\d+)\.(?P<tid>\d+)\.tmp$")
_LATCH_MARKER_NAME_RE = re.compile(r"^latched_[A-Za-z0-9_\-]+\.json$")
_CONSUMED_MARKER_NAME_RE = re.compile(r"^consumed_approval_[A-Za-z0-9_.:\-]+\.json$")


def _pid_alive(pid: int) -> bool:
    """
    True unless ``pid`` is known not to exist. pid <= 0 (process-group semantics for kill)
    and any probe error other than ESRCH count as alive, so such temp files are retained.
    """
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (OSError, OverflowError, ValueError):
        return True
    return True
INTEGRITY_UNSAFE_PATH = "UNSAFE_PATH"


class LedgerIntegrityViolationError(LatchedCaidExecutionHaltedError):
    """
    Raised (disposition HALT_LEDGER_INTEGRITY_VIOLATION) when on-disk ledger state cannot be
    authenticated: an untrusted receipt for a CAID, a ledger rolled back below its signed
    high-water mark, a tampered high-water mark, or an unsafe (symlinked / foreign-owned) path.
    Subclasses LatchedCaidExecutionHaltedError so existing fail-closed handlers still catch it.
    """
    disposition = HALT_LEDGER_INTEGRITY_VIOLATION

    def __init__(self, reason: str, message: str, caid: Optional[str] = None) -> None:
        super().__init__(f"{HALT_LEDGER_INTEGRITY_VIOLATION}[{reason}]: {message}")
        self.reason = reason
        self.caid = caid


class LedgerPathSecurityError(LedgerIntegrityViolationError):
    """Raised when a ledger / HWM / lock / latch path is a symlink, not regular, or foreign-owned."""

    def __init__(self, message: str) -> None:
        super().__init__(INTEGRITY_UNSAFE_PATH, message)


@dataclass(frozen=True)
class OperationApprovalGrant:
    """
    Single-use, exact-operation approval capability (OWASP Agentic Security / EO1 v2).
    Binds approval_id to exact subject_actor_id, tool_name, and canonical operation_caid,
    and is atomically consumed on disk before DISPATCH_INTENT is recorded.
    """
    approval_id: str
    subject_actor_id: str
    tool_name: str
    operation_caid: str
    expires_at_epoch_s: Optional[float] = None


def compute_caid(payload: Any) -> str:
    """Computes the SHA-256 digest over the RFC 8785 JCS canonical bytes of payload."""
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


# ---------------------------------------------------------------------------
# Reconciliation outcome classification
# ---------------------------------------------------------------------------

_NOT_COMMITTED_TOKENS = frozenset({
    "NOT_COMMITTED",
    "NOT_FOUND",
    "NOT_EXECUTED",
    "ABORTED",
    "REFUTED",
    "RESOLVED_REFUTED",
    "REJECTED",
})
_NOT_COMMITTED_PREFIXES = ("NOT_FOUND", "NOT_COMMITTED", "ABORTED", "RECONCILED_ABORTED")
_OUTCOME_EVIDENCE_KEYS = (
    "target_outcome",
    "outcome",
    "status",
    "target_status",
    "status_enum",
    "state_evaluated",
)


def classify_reconciliation_outcome(
    evidence: Any,
    target_outcome: Optional[str] = None,
) -> str:
    """
    Classifies out-of-band reconciliation evidence as COMMITTED or NOT_COMMITTED.

    Fail-closed under the stated model: NOT_COMMITTED is returned only when the caller
    passes target_outcome="NOT_COMMITTED", or when every recognised outcome field in the
    evidence carries a not-committed token and nothing contradicts it. Anything else
    (unknown, missing, or conflicting evidence) is classified COMMITTED, which blocks re-send.
    """
    if target_outcome is not None:
        norm = str(target_outcome).strip().upper()
        if norm not in (DISPOSITION_COMMITTED, DISPOSITION_NOT_COMMITTED):
            raise ValueError(
                f"target_outcome must be '{DISPOSITION_COMMITTED}' or '{DISPOSITION_NOT_COMMITTED}', got {target_outcome!r}"
            )
        return norm
    if not isinstance(evidence, dict):
        return DISPOSITION_COMMITTED

    explicit = evidence.get(DISPOSITION_KEY)
    if explicit in (DISPOSITION_COMMITTED, DISPOSITION_NOT_COMMITTED):
        return str(explicit)

    saw_not_committed = False
    saw_other = False
    for key in _OUTCOME_EVIDENCE_KEYS:
        value = evidence.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            saw_other = True
            continue
        token = value.strip().upper()
        if token in _NOT_COMMITTED_TOKENS or token.startswith(_NOT_COMMITTED_PREFIXES):
            saw_not_committed = True
        else:
            saw_other = True
    if evidence.get("target_observed") is True:
        saw_other = True
    if saw_not_committed and not saw_other:
        return DISPOSITION_NOT_COMMITTED
    return DISPOSITION_COMMITTED


def receipt_disposition(receipt_dict: Dict[str, Any]) -> str:
    """
    Returns the effect disposition carried by a CONTINUITY_RECEIPT record.
    Receipts without an explicit disposition marker (legacy or direct _emit_receipt calls)
    are treated as COMMITTED (fail-closed: re-send refused).
    """
    details = receipt_dict.get("reconciliation_details")
    if isinstance(details, dict):
        marker = details.get(DISPOSITION_KEY)
        if marker == DISPOSITION_NOT_COMMITTED:
            return DISPOSITION_NOT_COMMITTED
    return DISPOSITION_COMMITTED


def receipt_chain_hash(receipt_dict: Dict[str, Any]) -> str:
    """Recomputes the chain-tip successor hash of a CONTINUITY_RECEIPT record."""
    statement = {
        "caid": receipt_dict["caid"],
        "chain_tip": receipt_dict["chain_tip"],
        "intent_id": receipt_dict["intent_id"],
        "lifecycle_state": receipt_dict["lifecycle_state"],
        "policy_epoch": receipt_dict["policy_epoch"],
        "reconciled_at": receipt_dict["reconciled_at"],
        "reconciliation_details": receipt_dict.get("reconciliation_details", {}),
        "record_type": receipt_dict["record_type"],
        "retry_safe": receipt_dict["retry_safe"],
        "schema_version": receipt_dict["schema_version"],
        "status": receipt_dict["status"],
    }
    return hashlib.sha256(encode_jcs(statement)).hexdigest()


# ---------------------------------------------------------------------------
# Durable filesystem primitives
# ---------------------------------------------------------------------------

_DIR_FSYNC_IGNORED_ERRNOS = frozenset(
    e for e in (getattr(errno, "EINVAL", None), getattr(errno, "ENOTSUP", None), getattr(errno, "EOPNOTSUPP", None))
    if e is not None
)


def _fsync_fd(fd: int) -> bool:
    """
    Flushes fd to stable storage. On darwin, fcntl(F_FULLFSYNC) is attempted first because
    plain fsync() there does not request a device cache flush; falls back to os.fsync.
    Returns True when the platform's full-flush primitive ran (F_FULLFSYNC on darwin,
    os.fsync elsewhere) and False when darwin had to fall back to plain os.fsync.
    """
    if fcntl is not None and sys.platform == "darwin":
        full_fsync = getattr(fcntl, "F_FULLFSYNC", None)
        if full_fsync is not None:
            try:
                fcntl.fcntl(fd, full_fsync)
                return True
            except OSError as exc:
                logger.debug("F_FULLFSYNC failed (%s); falling back to os.fsync", exc)
    os.fsync(fd)
    return sys.platform != "darwin"


# F_BARRIERFSYNC is 85 in the macOS SDK <sys/fcntl.h> ("fsync + issue barrier to drive");
# CPython's fcntl module does not export it, so the SDK value is used when absent.
_F_BARRIERFSYNC = getattr(fcntl, "F_BARRIERFSYNC", 85) if fcntl is not None else None


def _barrier_fsync_fd(fd: int) -> None:
    """
    Ordering flush: on darwin, fcntl(F_BARRIERFSYNC) writes fd's data and metadata to the
    device and orders it before later I/O, without a device cache flush. Callers must follow
    it with a full flush before treating the data as durable. Falls back to the full flush
    (_fsync_fd) when the barrier is rejected; on non-darwin hosts this is os.fsync.
    """
    if _F_BARRIERFSYNC is not None and sys.platform == "darwin":
        try:
            fcntl.fcntl(fd, _F_BARRIERFSYNC)
            return
        except OSError as exc:
            logger.debug("F_BARRIERFSYNC failed (%s); using full flush", exc)
            _fsync_fd(fd)
            return
    os.fsync(fd)


def _fsync_dir(dir_path: Path, fsync_fn: Callable[[int], None] = _fsync_fd) -> None:
    """Flushes a directory entry table so that create/rename/unlink operations persist."""
    fd = os.open(str(dir_path), os.O_RDONLY)
    try:
        try:
            fsync_fn(fd)
        except OSError as exc:
            if exc.errno in _DIR_FSYNC_IGNORED_ERRNOS:
                logger.debug("Directory fsync unsupported on %s: %s", dir_path, exc)
            else:
                raise
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    """Writes every byte of data to fd, looping on short writes."""
    view = memoryview(data)
    written = 0
    while written < len(data):
        n = os.write(fd, view[written:])
        if n <= 0:
            raise OSError(errno.EIO, "os.write returned 0 bytes during durable write")
        written += n


_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


def _current_uid() -> Optional[int]:
    getuid = getattr(os, "getuid", None)
    return getuid() if getuid is not None else None


def _check_safe_directory(dir_path: Path) -> None:
    """Refuses a directory that is a symlink, not a directory, or not owned by the current uid."""
    try:
        st = os.lstat(str(dir_path))
    except FileNotFoundError as exc:
        raise LedgerPathSecurityError(f"Directory {dir_path} does not exist") from exc
    if stat.S_ISLNK(st.st_mode):
        raise LedgerPathSecurityError(f"Directory {dir_path} is a symlink; refused")
    if not stat.S_ISDIR(st.st_mode):
        raise LedgerPathSecurityError(f"{dir_path} is not a directory; refused")
    uid = _current_uid()
    if uid is not None and st.st_uid != uid:
        raise LedgerPathSecurityError(f"Directory {dir_path} is owned by uid {st.st_uid}, not {uid}; refused")


def _open_nofollow(path: Path, flags: int, mode: int = 0o644) -> int:
    """
    Opens path with O_NOFOLLOW and verifies (via fstat on the opened fd) that it is a regular
    file owned by the current uid. Raises LedgerPathSecurityError for symlinks or foreign files;
    FileNotFoundError propagates unchanged.
    """
    try:
        fd = os.open(str(path), flags | _O_NOFOLLOW | _O_CLOEXEC, mode)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise LedgerPathSecurityError(f"{path} is a symlink; refused (O_NOFOLLOW)") from exc
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise LedgerPathSecurityError(f"{path} is not a regular file; refused")
        uid = _current_uid()
        if uid is not None and st.st_uid != uid:
            raise LedgerPathSecurityError(f"{path} is owned by uid {st.st_uid}, not {uid}; refused")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_fd_range(fd: int, offset: int, length: int) -> bytes:
    """Reads exactly up to length bytes from fd starting at offset (loops on short reads)."""
    parts: List[bytes] = []
    remaining = length
    pos = offset
    while remaining > 0:
        chunk = os.pread(fd, remaining, pos)
        if not chunk:
            break
        parts.append(chunk)
        pos += len(chunk)
        remaining -= len(chunk)
    return b"".join(parts)


def _read_file_nofollow(path: Path) -> bytes:
    fd = _open_nofollow(path, os.O_RDONLY)
    try:
        return _read_fd_range(fd, 0, os.fstat(fd).st_size)
    finally:
        os.close(fd)


def _durable_append_bytes(path: Path, data: bytes, fsync_fn: Callable[[int], None] = _fsync_fd) -> None:
    """
    Appends data to path with O_APPEND, loops on short writes and fsyncs before returning.
    If the file does not end in a newline (torn tail left by a crash mid-append), a newline
    is written first so the torn fragment cannot merge with the new record.
    The parent directory is fsynced when the file is created by this call.
    The file is opened with O_NOFOLLOW and must be a regular file owned by the current uid.
    """
    path = Path(path)
    existed = os.path.lexists(str(path))
    fd = _open_nofollow(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        size = os.fstat(fd).st_size
        if size > 0 and os.pread(fd, 1, size - 1) != b"\n":
            data = b"\n" + data
        _write_all(fd, data)
        fsync_fn(fd)
    finally:
        os.close(fd)
    if not existed:
        _fsync_dir(path.parent, fsync_fn)


def _atomic_write_text(
    path: Path,
    text: str,
    fsync_fn: Callable[[int], None] = _fsync_fd,
    dir_fsync_fn: Optional[Callable[[int], None]] = None,
) -> None:
    """
    Writes text to path via tmp file -> fsync -> os.replace -> directory fsync.
    The tmp file is created with O_EXCL | O_NOFOLLOW; os.replace swaps the directory entry
    itself, so a pre-existing symlink at path is replaced rather than followed.
    ``dir_fsync_fn`` (default: ``fsync_fn``) flushes the directory after os.replace.
    """
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = _open_nofollow(tmp, flags, 0o644)
    except FileExistsError:
        # Stale tmp from a crashed writer with the same pid/thread id (or a planted entry).
        os.unlink(tmp)
        fd = _open_nofollow(tmp, flags, 0o644)
    try:
        _write_all(fd, text.encode("utf-8"))
        fsync_fn(fd)
    finally:
        os.close(fd)
    try:
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            logger.warning("Failed to remove temporary latch file %s", tmp)
        raise
    _fsync_dir(path.parent, dir_fsync_fn if dir_fsync_fn is not None else fsync_fn)


def _durable_unlink(path: Path, fsync_fn: Callable[[int], None] = _fsync_fd) -> bool:
    """Unlinks path (if present) and fsyncs its parent directory. Returns True if removed."""
    path = Path(path)
    try:
        os.unlink(path)
    except FileNotFoundError:
        return False
    _fsync_dir(path.parent, fsync_fn)
    return True


# ---------------------------------------------------------------------------
# Incremental ledger view (shared by startup recovery and the interlock)
# ---------------------------------------------------------------------------

class _LedgerView:
    """
    Position-aware fold over ledger records.
    An intent is resolved by any CONTINUITY_RECEIPT appearing *after* it that carries the same
    intent_id or the same caid. Tracks unresolved intents, committed CAIDs and the chain tip.

    Records applied with trusted=False (failed signature verification) may only add
    restrictions: untrusted intents still count as unresolved; untrusted receipts resolve
    nothing, unlock nothing and taint their CAID (``tainted``) until a later trusted receipt
    for the same CAID supersedes them. ``hasher`` / ``record_count`` cover the consumed prefix
    and are compared against the signed high-water mark by the interlock.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.unresolved: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.intent_caid: Dict[str, str] = {}
        self.committed: Dict[str, str] = {}
        self.tainted: Dict[str, str] = {}
        self.untrusted_records: int = 0
        self.chain_tip: str = GENESIS_CHAIN_TIP
        self.offset: int = 0
        self.file_identity: Optional[tuple] = None
        self.record_count: int = 0
        self.hasher = hashlib.sha256()
        self.verified_hwm_seq: Optional[int] = None

    def _advance_chain_tip(self, rec: Dict[str, Any]) -> None:
        try:
            self.chain_tip = receipt_chain_hash(rec)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Malformed CONTINUITY_RECEIPT skipped for chain tip: %s", exc)

    def apply(self, rec: Dict[str, Any], trusted: bool = True) -> None:
        self.record_count += 1
        if not trusted:
            self.untrusted_records += 1
        rtype = rec.get("record_type")
        if rtype == "DISPATCH_INTENT":
            caid = rec.get("caid")
            iid = rec.get("intent_id")
            if not isinstance(caid, str) or not isinstance(iid, str):
                return
            self.unresolved.setdefault(caid, {})[iid] = rec
            self.intent_caid[iid] = caid
        elif rtype == "CONTINUITY_RECEIPT":
            caid = rec.get("caid")
            iid = rec.get("intent_id")
            if not trusted:
                # Fail closed: an unauthenticated receipt never resolves or unlocks anything.
                if isinstance(caid, str):
                    self.tainted[caid] = INTEGRITY_UNTRUSTED_RECEIPT
                self._advance_chain_tip(rec)
                return
            if isinstance(iid, str) and iid in self.intent_caid:
                owner = self.intent_caid.pop(iid)
                bucket = self.unresolved.get(owner)
                if bucket is not None:
                    bucket.pop(iid, None)
                    if not bucket:
                        self.unresolved.pop(owner, None)
            if isinstance(caid, str) and caid in self.unresolved:
                for resolved_iid in self.unresolved.pop(caid):
                    self.intent_caid.pop(resolved_iid, None)
            if isinstance(caid, str):
                self.tainted.pop(caid, None)
            if isinstance(caid, str) and receipt_disposition(rec) == DISPOSITION_COMMITTED:
                self.committed.setdefault(caid, iid if isinstance(iid, str) else "")
            self._advance_chain_tip(rec)

    def unresolved_for(self, caid: str) -> Dict[str, Dict[str, Any]]:
        return dict(self.unresolved.get(caid, {}))


def _iter_ledger_records(raw: bytes, source: Path) -> Iterator[Dict[str, Any]]:
    """Yields decoded dict records from complete ledger lines; undecodable lines are skipped."""
    for line_no, raw_line in enumerate(raw.split(b"\n"), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            # A torn line can only stem from a crash mid-append; durable appends complete
            # (and fsync) before dispatch proceeds, so a torn intent never preceded an effect.
            logger.warning("Skipping undecodable ledger line %d in %s: %s", line_no, source, exc)
            continue
        if isinstance(rec, dict):
            yield rec


@dataclass(frozen=True)
class DispatchIntentRecord:
    record_type: str
    schema_version: str
    intent_id: str
    caid: str
    target_uri: str
    tool_name: str
    policy_epoch: int
    authority_id: str
    timestamp_utc: str
    payload_digest: str
    boundary_signature_b64: str
    boundary_public_key_pem: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authority_id": self.authority_id,
            "boundary_public_key_pem": self.boundary_public_key_pem,
            "boundary_signature_b64": self.boundary_signature_b64,
            "caid": self.caid,
            "intent_id": self.intent_id,
            "payload_digest": self.payload_digest,
            "policy_epoch": self.policy_epoch,
            "record_type": self.record_type,
            "schema_version": self.schema_version,
            "target_uri": self.target_uri,
            "timestamp_utc": self.timestamp_utc,
            "tool_name": self.tool_name,
        }

    def statement_for_signature(self) -> Dict[str, Any]:
        return {
            "authority_id": self.authority_id,
            "caid": self.caid,
            "intent_id": self.intent_id,
            "payload_digest": self.payload_digest,
            "policy_epoch": self.policy_epoch,
            "record_type": self.record_type,
            "schema_version": self.schema_version,
            "target_uri": self.target_uri,
            "timestamp_utc": self.timestamp_utc,
            "tool_name": self.tool_name,
        }


@dataclass(frozen=True)
class ContinuityReceipt:
    record_type: str
    schema_version: str
    intent_id: str
    caid: str
    status: str
    lifecycle_state: str
    retry_safe: bool
    policy_epoch: int
    reconciled_at: str
    chain_tip: str
    boundary_signature_b64: str
    boundary_public_key_pem: str
    reconciliation_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_public_key_pem": self.boundary_public_key_pem,
            "boundary_signature_b64": self.boundary_signature_b64,
            "caid": self.caid,
            "chain_tip": self.chain_tip,
            "intent_id": self.intent_id,
            "lifecycle_state": self.lifecycle_state,
            "policy_epoch": self.policy_epoch,
            "reconciled_at": self.reconciled_at,
            "reconciliation_details": self.reconciliation_details,
            "record_type": self.record_type,
            "retry_safe": self.retry_safe,
            "schema_version": self.schema_version,
            "status": self.status,
        }

    def statement_for_signature(self) -> Dict[str, Any]:
        return {
            "caid": self.caid,
            "chain_tip": self.chain_tip,
            "intent_id": self.intent_id,
            "lifecycle_state": self.lifecycle_state,
            "policy_epoch": self.policy_epoch,
            "reconciled_at": self.reconciled_at,
            "reconciliation_details": self.reconciliation_details,
            "record_type": self.record_type,
            "retry_safe": self.retry_safe,
            "schema_version": self.schema_version,
            "status": self.status,
        }


@dataclass(frozen=True)
class RecoveredIntentState:
    intent_id: str
    caid: str
    target_uri: str
    tool_name: str
    lifecycle_state: IntentLifecycleState
    retry_safe: bool
    reconciliation_required: bool
    latched_at: str
    reproducibility_evidence_sha256: str


@dataclass(frozen=True)
class DispatchResult:
    lifecycle_state: IntentLifecycleState
    caid: str
    receipt: ContinuityReceipt
    response: Dict[str, Any]


def verify_dispatch_intent(
    record_dict: Dict[str, Any],
    public_key: Union[Ed25519PublicKey, str],
    expected_payload: Optional[Any] = None,
) -> bool:
    """Verifies an Ed25519-signed DISPATCH_INTENT record."""
    if isinstance(public_key, str):
        pub = serialization.load_pem_public_key(public_key.encode("utf-8"))
        if not isinstance(pub, Ed25519PublicKey):
            raise IntentVerificationError("Loaded key is not an Ed25519PublicKey")
        public_key = pub

    # Expected payload verification
    if expected_payload is not None:
        computed_caid = compute_caid(expected_payload)
        if computed_caid != record_dict.get("caid"):
            raise IntentVerificationError(
                f"CAID mismatch: record caid '{record_dict.get('caid')}' != computed caid '{computed_caid}'"
            )

    # Reconstruct canonical statement
    statement = {
        "authority_id": record_dict["authority_id"],
        "caid": record_dict["caid"],
        "intent_id": record_dict["intent_id"],
        "payload_digest": record_dict["payload_digest"],
        "policy_epoch": record_dict["policy_epoch"],
        "record_type": record_dict["record_type"],
        "schema_version": record_dict["schema_version"],
        "target_uri": record_dict["target_uri"],
        "timestamp_utc": record_dict["timestamp_utc"],
        "tool_name": record_dict["tool_name"],
    }
    jcs_bytes = encode_jcs(statement)

    sig_b64 = record_dict.get("boundary_signature_b64")
    if not sig_b64:
        raise IntentVerificationError("Missing boundary_signature_b64 in DISPATCH_INTENT")
    try:
        sig_bytes = base64.b64decode(sig_b64)
        public_key.verify(sig_bytes, jcs_bytes)
        return True
    except (InvalidSignature, ValueError) as err:
        raise IntentVerificationError(f"Ed25519 intent signature verification failed: {err}") from err


def verify_continuity_receipt(
    receipt_dict: Dict[str, Any],
    public_key: Union[Ed25519PublicKey, str],
) -> bool:
    """Verifies an Ed25519-signed CONTINUITY_RECEIPT record."""
    if isinstance(public_key, str):
        pub = serialization.load_pem_public_key(public_key.encode("utf-8"))
        if not isinstance(pub, Ed25519PublicKey):
            raise IntentVerificationError("Loaded key is not an Ed25519PublicKey")
        public_key = pub

    statement = {
        "caid": receipt_dict["caid"],
        "chain_tip": receipt_dict["chain_tip"],
        "intent_id": receipt_dict["intent_id"],
        "lifecycle_state": receipt_dict["lifecycle_state"],
        "policy_epoch": receipt_dict["policy_epoch"],
        "reconciled_at": receipt_dict["reconciled_at"],
        "reconciliation_details": receipt_dict.get("reconciliation_details", {}),
        "record_type": receipt_dict["record_type"],
        "retry_safe": receipt_dict["retry_safe"],
        "schema_version": receipt_dict["schema_version"],
        "status": receipt_dict["status"],
    }
    jcs_bytes = encode_jcs(statement)

    sig_b64 = receipt_dict.get("boundary_signature_b64")
    if not sig_b64:
        raise IntentVerificationError("Missing boundary_signature_b64 in CONTINUITY_RECEIPT")
    try:
        sig_bytes = base64.b64decode(sig_b64)
        public_key.verify(sig_bytes, jcs_bytes)
        return True
    except (InvalidSignature, ValueError) as err:
        raise IntentVerificationError(f"Ed25519 continuity receipt signature verification failed: {err}") from err


def verify_ledger_file(
    ledger_path: Path,
    public_key: Union[Ed25519PublicKey, str],
) -> List[Dict[str, Any]]:
    """Verifies every line in the append-only ledger against the trusted public key."""
    ledger_path = Path(ledger_path)
    if not ledger_path.exists():
        return []

    verified_records: List[Dict[str, Any]] = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rec_type = record.get("record_type")
            if rec_type == "DISPATCH_INTENT":
                verify_dispatch_intent(record, public_key)
            elif rec_type == "CONTINUITY_RECEIPT":
                verify_continuity_receipt(record, public_key)
            else:
                raise IntentVerificationError(f"Line {idx}: Unrecognized record_type '{rec_type}'")
            verified_records.append(record)
    return verified_records


def recover_unresolved_intents(
    ledger_path: Path,
    output_state_dir: Path,
    public_key: Optional[Union[Ed25519PublicKey, str]] = None,
    verify_signatures: bool = False,
    fsync_fn: Optional[Callable[[int], None]] = None,
) -> List[RecoveredIntentState]:
    """
    Scans the ledger for DISPATCH_INTENT records lacking a matching CONTINUITY_RECEIPT.
    Latches them into EFFECT_INDETERMINATE and writes latch markers into output_state_dir.

    An intent counts as resolved only by a receipt that appears after it in the ledger and
    carries the same intent_id or the same caid. Latch markers are written durably
    (tmp -> fsync -> os.replace -> directory fsync). Undecodable (torn) lines are skipped.

    Signature handling:
      - verify_signatures=True with public_key: any invalid record raises IntentVerificationError.
      - verify_signatures=False with public_key: invalid records are applied as untrusted
        (an unauthenticated receipt does not resolve its intent, so the intent is latched).
      - public_key=None: records cannot be authenticated; legacy behaviour (all records
        applied). PreDispatchIntentInterlock does not use this mode for its own startup.
    """
    ledger_path = Path(ledger_path)
    output_state_dir = Path(output_state_dir)
    output_state_dir.mkdir(parents=True, exist_ok=True)
    fsync_fn = fsync_fn or _fsync_fd

    if not os.path.lexists(str(ledger_path)):
        return []

    view = _LedgerView()
    for rec in _iter_ledger_records(_read_file_nofollow(ledger_path), ledger_path):
        rtype = rec.get("record_type")
        trusted = True
        if public_key is not None:
            if verify_signatures:
                if rtype == "DISPATCH_INTENT":
                    verify_dispatch_intent(rec, public_key)
                elif rtype == "CONTINUITY_RECEIPT":
                    verify_continuity_receipt(rec, public_key)
            else:
                trusted = _record_verifies(rec, [public_key])
        view.apply(rec, trusted=trusted)

    recovered: List[RecoveredIntentState] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for caid, bucket in view.unresolved.items():
        for intent_id, intent_dict in bucket.items():
            evidence_sha256 = hashlib.sha256(encode_jcs(intent_dict)).hexdigest()

            state = RecoveredIntentState(
                intent_id=intent_id,
                caid=caid,
                target_uri=str(intent_dict.get("target_uri", "unknown")),
                tool_name=str(intent_dict.get("tool_name", "unknown")),
                lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                retry_safe=False,
                reconciliation_required=True,
                latched_at=now_iso,
                reproducibility_evidence_sha256=evidence_sha256,
            )
            recovered.append(state)

            # Persist latch marker to output_state_dir (durable atomic replace)
            latch_file = output_state_dir / f"latched_{caid}.json"
            _atomic_write_text(latch_file, json.dumps(_latch_payload_for(state), indent=2), fsync_fn)

    return recovered


def _latch_payload_for(state: RecoveredIntentState) -> Dict[str, Any]:
    return {
        "caid": state.caid,
        "intent_id": state.intent_id,
        "latched_at": state.latched_at,
        "lifecycle_state": "EFFECT_INDETERMINATE",
        "reconciliation_required": True,
        "retry_safe": False,
        "target_uri": state.target_uri,
        "tool_name": state.tool_name,
    }


def _coerce_public_key(key: Union[Ed25519PublicKey, str]) -> Ed25519PublicKey:
    if isinstance(key, Ed25519PublicKey):
        return key
    pub = serialization.load_pem_public_key(str(key).encode("utf-8"))
    if not isinstance(pub, Ed25519PublicKey):
        raise IntentVerificationError("Loaded key is not an Ed25519PublicKey")
    return pub


def _record_verifies(rec: Dict[str, Any], keys: List[Union[Ed25519PublicKey, str]]) -> bool:
    """Returns True iff rec is a DISPATCH_INTENT / CONTINUITY_RECEIPT whose signature verifies under any key."""
    rtype = rec.get("record_type")
    if rtype == "DISPATCH_INTENT":
        verifier = verify_dispatch_intent
    elif rtype == "CONTINUITY_RECEIPT":
        verifier = verify_continuity_receipt
    else:
        return False
    for key in keys:
        try:
            verifier(rec, key)
            return True
        except (IntentVerificationError, KeyError, TypeError, ValueError, AttributeError):
            continue
    return False


_HWM_SCHEMA_VERSION = "1.0.0-eo1-hwm"
_HWM_SIGNED_FIELDS = (
    "chain_tip",
    "ledger_bytes",
    "ledger_name",
    "ledger_prefix_sha256",
    "record_count",
    "schema_version",
    "seq",
    "signer_public_key_pem",
)

FLUSH_POLICY_BARRIER_THEN_FULL = "barrier_then_single_full_flush"
FLUSH_POLICY_FULL_EVERY_WRITE = "full_flush_every_write"
_FLUSH_POLICIES = frozenset({FLUSH_POLICY_BARRIER_THEN_FULL, FLUSH_POLICY_FULL_EVERY_WRITE})


class PreDispatchIntentInterlock:
    """
    Enforces EO-1 (Evidence-Before-Effect) at the socket boundary.

    State transitions are serialised by a per-instance threading.RLock and, across
    processes sharing the same ledger, by fcntl.flock(LOCK_EX) on "<ledger>.lock".
    On-disk ledger and latch state are re-read inside the lock before every admission
    decision, so instances in different processes observe each other's intents, latches
    and receipts under the stated model (local POSIX filesystem).
    """

    def __init__(
        self,
        ledger_path: Path,
        boundary_private_key: Optional[Ed25519PrivateKey] = None,
        output_state_dir: Optional[Path] = None,
        authority_id: str = "default-authority",
        policy_epoch: int = 1,
        simulate_write_error: bool = False,
        auto_recover: bool = True,
        trusted_public_keys: Optional[List[Union[Ed25519PublicKey, str]]] = None,
        min_hwm_seq: Optional[int] = None,
        flush_policy: str = "barrier_then_single_full_flush",
    ):
        if flush_policy not in _FLUSH_POLICIES:
            raise ValueError(f"flush_policy must be one of {sorted(_FLUSH_POLICIES)}, got {flush_policy!r}")
        self.flush_policy = flush_policy
        # Selects the ordering flush (F_BARRIERFSYNC) inside _durable_fsync; only set, under the
        # interlock lock, for steps that a later full flush in the same append covers.
        self._ordering_only_flush = False
        self._last_flush_was_full = False
        self.ledger_path = Path(ledger_path)
        self.output_state_dir = Path(output_state_dir) if output_state_dir else self.ledger_path.parent / "state"
        # Strict integrity: history can be authenticated only against a stable, caller-supplied key.
        self.ledger_integrity_strict = boundary_private_key is not None or bool(trusted_public_keys)
        self.boundary_private_key = boundary_private_key or Ed25519PrivateKey.generate()
        self.authority_id = authority_id
        self.policy_epoch = policy_epoch
        self.simulate_write_error = simulate_write_error
        # Re-entrant so _emit_receipt can be called both directly and from reconcile/dispatch.
        self._lock = threading.RLock()
        self._flock_depth = 0
        self._lock_path = self.ledger_path.with_name(self.ledger_path.name + ".lock")
        self.hwm_path = self.ledger_path.with_name(self.ledger_path.name + ".hwm")
        self._view = _LedgerView()
        # Restored from the last CONTINUITY_RECEIPT on disk during the initial sync below.
        self._chain_tip: str = GENESIS_CHAIN_TIP
        self._min_hwm_seq = int(min_hwm_seq) if min_hwm_seq is not None else 0
        self._max_hwm_seq_seen = 0
        self._last_hwm: Optional[Dict[str, Any]] = None
        self._integrity_halt: Optional[LedgerIntegrityViolationError] = None
        self._warned_unauthenticated_hwm = False

        own_pub = self.boundary_private_key.public_key()
        pub_bytes = own_pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.boundary_public_key_pem = pub_bytes.decode("utf-8")
        trusted = [own_pub] + [_coerce_public_key(k) for k in (trusted_public_keys or [])]
        # PEM string -> key object; PEM in a record is only a lookup hint, never a trust source.
        self._trusted_keys_by_pem: Dict[str, Ed25519PublicKey] = {}
        for key in trusted:
            pem = key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
            self._trusted_keys_by_pem[pem] = key
        self.output_state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._check_storage_dirs()

        self._latched_intents: Dict[str, RecoveredIntentState] = {}
        # Latches whose marker file could not be persisted; kept in memory fail-closed.
        self._unpersisted_latches: Dict[str, RecoveredIntentState] = {}
        # Orphan temp files of _atomic_write_text removed / kept by startup recovery.
        self.boot_reaped_tmp_count = 0
        self.boot_reaped_tmp_names: List[str] = []
        self.boot_retained_tmp: Dict[str, str] = {}
        if auto_recover:
            self._run_startup_recovery()
        else:
            # Still rebuild chain tip, committed CAIDs and unresolved intents from disk.
            with self._exclusive():
                pass

    # ------------------------------------------------------------------
    # Durability hooks
    # ------------------------------------------------------------------

    def _durable_fsync(self, fd: int) -> None:
        """Single fsync hook used by every durable write of this interlock."""
        if self._ordering_only_flush:
            _barrier_fsync_fd(fd)
            self._last_flush_was_full = False
        else:
            self._last_flush_was_full = _fsync_fd(fd)

    def _fsync_in_mode(self, fd: int, ordering_only: bool) -> None:
        previous = self._ordering_only_flush
        self._ordering_only_flush = ordering_only
        try:
            self._durable_fsync(fd)
        finally:
            self._ordering_only_flush = previous

    def _ordered_durable_fsync(self, fd: int) -> None:
        """Ordering-only flush through the hook; a later full flush must cover it."""
        self._fsync_in_mode(fd, True)

    def _full_durable_fsync(self, fd: int) -> None:
        """Full flush through the hook (F_FULLFSYNC on darwin)."""
        self._fsync_in_mode(fd, False)

    def _full_flush_files_locked(self, *paths: Path) -> None:
        for path in paths:
            fd = _open_nofollow(path, os.O_RDONLY)
            try:
                self._full_durable_fsync(fd)
            finally:
                os.close(fd)

    def _durable_append(self, data: bytes) -> None:
        """
        Appends a ledger record, reads it back into the verified view and rewrites the signed
        high-water mark. Must be called while holding _exclusive(). A genesis HWM is written
        before the first append to an empty ledger so a crash between the append and the HWM
        update leaves "ledger longer than HWM" (accepted) rather than "HWM missing".

        Under FLUSH_POLICY_BARRIER_THEN_FULL the ledger append and the HWM tmp file use the
        ordering flush and the HWM directory flush after os.replace is the full flush, so the
        record and its HWM are both flushed before this method returns.
        """
        if self._last_hwm is None and self._view.offset == 0 and self._ledger_size() == 0:
            self._write_hwm_locked()
        ordered = self.flush_policy == FLUSH_POLICY_BARRIER_THEN_FULL
        _durable_append_bytes(
            self.ledger_path, data, self._ordered_durable_fsync if ordered else self._durable_fsync
        )
        self._sync_ledger_locked()
        self._write_hwm_locked(ordered=ordered)

    def _write_latch_marker(self, caid: str, payload: Dict[str, Any]) -> None:
        latch_file = self.output_state_dir / f"latched_{caid}.json"
        _atomic_write_text(latch_file, json.dumps(payload, indent=2), self._durable_fsync)

    # ------------------------------------------------------------------
    # Path safety, record trust and the signed high-water mark
    # ------------------------------------------------------------------

    def _check_storage_dirs(self) -> None:
        _check_safe_directory(self.ledger_path.parent)
        _check_safe_directory(self.output_state_dir)

    def _ledger_size(self) -> int:
        try:
            st = os.lstat(str(self.ledger_path))
        except FileNotFoundError:
            return 0
        return st.st_size

    def _is_record_trusted(self, rec: Dict[str, Any]) -> bool:
        hint = rec.get("boundary_public_key_pem")
        if isinstance(hint, str) and hint in self._trusted_keys_by_pem:
            return _record_verifies(rec, [self._trusted_keys_by_pem[hint]])
        return _record_verifies(rec, list(self._trusted_keys_by_pem.values()))

    def _halt(self, reason: str, message: str) -> None:
        err = LedgerIntegrityViolationError(reason, f"{message} (ledger={self.ledger_path})")
        self._integrity_halt = err
        logger.error("%s", err)
        raise err

    @staticmethod
    def _hwm_statement(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {k: doc[k] for k in _HWM_SIGNED_FIELDS}

    def _read_hwm_locked(self) -> Optional[Dict[str, Any]]:
        """Reads and authenticates the HWM file; returns None when absent. Halts on tampering."""
        try:
            raw = _read_file_nofollow(self.hwm_path)
        except FileNotFoundError:
            if self._max_hwm_seq_seen > 0:
                # Honest code never deletes the HWM; disappearance while running is tampering.
                self._halt(INTEGRITY_HWM_MISSING, f"Signed high-water mark {self.hwm_path} disappeared")
            return None
        try:
            doc = json.loads(raw.decode("utf-8"))
            if not isinstance(doc, dict):
                raise TypeError("HWM is not a JSON object")
            statement = self._hwm_statement(doc)
            for int_field in ("seq", "record_count", "ledger_bytes"):
                value = statement[int_field]
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise TypeError(f"HWM field {int_field} must be a non-negative integer")
            for str_field in ("ledger_prefix_sha256", "chain_tip", "signer_public_key_pem", "schema_version"):
                if not isinstance(statement[str_field], str):
                    raise TypeError(f"HWM field {str_field} must be a string")
            sig = base64.b64decode(doc["signature_b64"], validate=True)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            self._halt(INTEGRITY_HWM_MALFORMED, f"High-water mark {self.hwm_path} is malformed: {exc}")
        signed_bytes = encode_jcs(statement)
        signer_pem = statement["signer_public_key_pem"]
        trusted_key = self._trusted_keys_by_pem.get(signer_pem)
        try:
            if trusted_key is not None:
                trusted_key.verify(sig, signed_bytes)
            else:
                _coerce_public_key(signer_pem).verify(sig, signed_bytes)
        except (InvalidSignature, IntentVerificationError, ValueError, TypeError) as exc:
            self._halt(INTEGRITY_HWM_SIGNATURE_INVALID, f"High-water mark signature invalid: {exc!r}")
        if trusted_key is None:
            if self.ledger_integrity_strict:
                self._halt(INTEGRITY_HWM_SIGNER_UNTRUSTED, "High-water mark signed by a key outside trusted_public_keys")
            if not self._warned_unauthenticated_hwm:
                logger.warning(
                    "HWM %s signed by an unknown key; ephemeral-key interlock enforces it restrictively only",
                    self.hwm_path,
                )
                self._warned_unauthenticated_hwm = True
        seq = statement["seq"]
        if seq < self._max_hwm_seq_seen or seq < self._min_hwm_seq:
            self._halt(
                INTEGRITY_HWM_SEQ_REGRESSED,
                f"High-water mark seq {seq} is below observed/anchored seq "
                f"{max(self._max_hwm_seq_seen, self._min_hwm_seq)} (older HWM restored)",
            )
        self._max_hwm_seq_seen = seq
        self._last_hwm = statement
        return statement

    def _write_hwm_locked(self, ordered: bool = False) -> None:
        view = self._view
        seq = max(self._max_hwm_seq_seen, self._min_hwm_seq) + 1
        statement = {
            "chain_tip": view.chain_tip,
            "ledger_bytes": view.offset,
            "ledger_name": self.ledger_path.name,
            "ledger_prefix_sha256": view.hasher.hexdigest(),
            "record_count": view.record_count,
            "schema_version": _HWM_SCHEMA_VERSION,
            "seq": seq,
            "signer_public_key_pem": self.boundary_public_key_pem,
        }
        sig_b64 = base64.b64encode(self.boundary_private_key.sign(encode_jcs(statement))).decode("ascii")
        doc = dict(statement)
        doc["signature_b64"] = sig_b64
        text = json.dumps(doc, sort_keys=True)
        if ordered:
            self._last_flush_was_full = False
            _atomic_write_text(self.hwm_path, text, self._ordered_durable_fsync, self._full_durable_fsync)
            if not self._last_flush_was_full:
                # The directory flush could not issue the full primitive: flush the files themselves.
                self._full_flush_files_locked(self.ledger_path, self.hwm_path)
        else:
            _atomic_write_text(self.hwm_path, text, self._durable_fsync)
        self._max_hwm_seq_seen = seq
        self._last_hwm = statement
        view.verified_hwm_seq = seq

    def high_water_mark_digest(self) -> Optional[str]:
        """
        SHA-256 over the RFC 8785 JCS bytes of the current signed HWM statement (None if no HWM).
        Anchor this digest (with its seq) outside the host: local files alone cannot reveal a
        consistent rollback of BOTH the ledger and the HWM.
        """
        with self._exclusive():
            if self._last_hwm is None:
                return None
            return hashlib.sha256(encode_jcs(self._last_hwm)).hexdigest()

    def high_water_mark_seq(self) -> int:
        with self._exclusive():
            return self._max_hwm_seq_seen

    def get_integrity_violations(self) -> Dict[str, str]:
        """CAIDs tainted by untrusted (unauthenticated) receipts, mapped to the violation reason."""
        with self._exclusive():
            return dict(self._view.tainted)

    # ------------------------------------------------------------------
    # Cross-process exclusion and on-disk state sync
    # ------------------------------------------------------------------

    def _acquire_flock(self) -> int:
        if fcntl is None:
            raise OSError(errno.ENOTSUP, "fcntl.flock unavailable on this platform; EO-1 interlock refuses to operate")
        fd = _open_nofollow(self._lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except BaseException:
            os.close(fd)
            raise
        return fd

    @staticmethod
    def _release_flock(fd: int) -> None:
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        """
        Holds the thread lock and the cross-process flock; on outermost entry re-reads the
        ledger and latch directory so admission decisions use current on-disk state.
        A detected ledger integrity violation is sticky: every later entry re-raises it.
        """
        with self._lock:
            if self._flock_depth > 0:
                self._flock_depth += 1
                try:
                    yield
                finally:
                    self._flock_depth -= 1
                return
            if self._integrity_halt is not None:
                raise self._integrity_halt
            fd = self._acquire_flock()
            self._flock_depth = 1
            try:
                self._sync_from_disk_locked()
                yield
            finally:
                self._flock_depth = 0
                self._release_flock(fd)

    def _consume_ledger_bytes(self, data: bytes) -> None:
        view = self._view
        view.hasher.update(data)
        for rec in _iter_ledger_records(data, self.ledger_path):
            view.apply(rec, trusted=self._is_record_trusted(rec))
        view.offset += len(data)

    def _verify_hwm_boundary(self, hwm: Dict[str, Any]) -> None:
        view = self._view
        if (
            view.offset != hwm["ledger_bytes"]
            or view.hasher.hexdigest() != hwm["ledger_prefix_sha256"]
            or view.record_count != hwm["record_count"]
            or view.chain_tip != hwm["chain_tip"]
        ):
            self._halt(
                INTEGRITY_LEDGER_DIVERGES,
                f"Ledger prefix of {hwm['ledger_bytes']} bytes does not match signed HWM seq {hwm['seq']} "
                f"(records {view.record_count} vs {hwm['record_count']})",
            )
        view.verified_hwm_seq = hwm["seq"]

    def _sync_ledger_locked(self) -> None:
        self._check_storage_dirs()
        hwm = self._read_hwm_locked()
        view = self._view
        try:
            fd = _open_nofollow(self.ledger_path, os.O_RDONLY)
        except FileNotFoundError:
            if hwm is not None and hwm["ledger_bytes"] > 0:
                self._halt(INTEGRITY_LEDGER_MISSING, f"Ledger missing but signed HWM seq {hwm['seq']} records {hwm['ledger_bytes']} bytes")
            if view.offset or view.file_identity is not None:
                view.reset()
            self._chain_tip = view.chain_tip
            return
        try:
            st = os.fstat(fd)
            identity = (st.st_dev, st.st_ino)
            if view.file_identity is not None and (identity != view.file_identity or st.st_size < view.offset):
                logger.warning("Ledger %s replaced or truncated; rebuilding view from offset 0", self.ledger_path)
                view.reset()
            view.file_identity = identity
            if hwm is None:
                if st.st_size > 0 and self.ledger_integrity_strict:
                    self._halt(INTEGRITY_HWM_MISSING, f"Non-empty ledger has no signed high-water mark {self.hwm_path}")
            else:
                hwm_bytes = hwm["ledger_bytes"]
                if st.st_size < hwm_bytes:
                    self._halt(
                        INTEGRITY_LEDGER_TRUNCATED,
                        f"Ledger is {st.st_size} bytes, shorter than signed HWM seq {hwm['seq']} ({hwm_bytes} bytes)",
                    )
                if view.offset > hwm_bytes and view.verified_hwm_seq != hwm["seq"]:
                    # HWM boundary lies behind what we already consumed: re-verify from offset 0.
                    view.reset()
                    view.file_identity = identity
            if st.st_size > view.offset:
                chunk = _read_fd_range(fd, view.offset, st.st_size - view.offset)
                last_nl = chunk.rfind(b"\n")
                if last_nl >= 0:
                    complete = chunk[: last_nl + 1]
                    if hwm is not None and view.offset < hwm["ledger_bytes"] <= view.offset + len(complete):
                        split = hwm["ledger_bytes"] - view.offset
                        if complete[split - 1: split] != b"\n":
                            self._halt(INTEGRITY_LEDGER_DIVERGES, "Signed HWM boundary does not fall on a record boundary")
                        self._consume_ledger_bytes(complete[:split])
                        self._verify_hwm_boundary(hwm)
                        self._consume_ledger_bytes(complete[split:])
                    else:
                        self._consume_ledger_bytes(complete)
            if hwm is not None and view.verified_hwm_seq != hwm["seq"]:
                if view.offset == hwm["ledger_bytes"]:
                    self._verify_hwm_boundary(hwm)
                elif view.offset < hwm["ledger_bytes"]:
                    self._halt(INTEGRITY_LEDGER_DIVERGES, "Ledger has no complete record at the signed HWM boundary")
        finally:
            os.close(fd)
        self._chain_tip = view.chain_tip

    def _read_latch_file(self, latch_file: Path) -> Dict[str, Any]:
        data = json.loads(_read_file_nofollow(latch_file).decode("utf-8"))
        if not isinstance(data, dict):
            raise TypeError("latch marker is not a JSON object")
        return data

    def _load_latch_dir_locked(self) -> Dict[str, RecoveredIntentState]:
        latches: Dict[str, RecoveredIntentState] = {}
        for latch_file in sorted(self.output_state_dir.glob("latched_*.json")):
            caid_from_name = latch_file.name[len("latched_"):-len(".json")]
            try:
                data = self._read_latch_file(latch_file)
                caid = data["caid"]
                latches[caid] = RecoveredIntentState(
                    intent_id=data.get("intent_id", f"latched-{caid[:16]}"),
                    caid=caid,
                    target_uri=data.get("target_uri", "unknown"),
                    tool_name=data.get("tool_name", "unknown"),
                    lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                    retry_safe=False,
                    reconciliation_required=True,
                    latched_at=data.get("latched_at", ""),
                    reproducibility_evidence_sha256="",
                )
            except FileNotFoundError:
                continue
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, OSError, LedgerPathSecurityError) as e:
                # Fail-closed: an unreadable / symlinked marker still latches the CAID named in its filename.
                logger.warning("Failed to parse latch %s (%s); latching CAID from filename", latch_file, e)
                latches[caid_from_name] = RecoveredIntentState(
                    intent_id=f"latched-{caid_from_name[:16]}",
                    caid=caid_from_name,
                    target_uri="unknown",
                    tool_name="unknown",
                    lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                    retry_safe=False,
                    reconciliation_required=True,
                    latched_at="",
                    reproducibility_evidence_sha256="",
                )
        return latches

    def _sync_from_disk_locked(self) -> None:
        self._sync_ledger_locked()
        latches = self._load_latch_dir_locked()
        latches.update(self._unpersisted_latches)
        self._latched_intents = latches

    def _owned_tmp_target(self, directory: Path, target: str) -> bool:
        """True when ``target`` names a file this interlock writes via _atomic_write_text in ``directory``."""
        if directory == self.ledger_path.parent and target == self.hwm_path.name:
            return True
        if directory == self.output_state_dir:
            return bool(_LATCH_MARKER_NAME_RE.match(target) or _CONSUMED_MARKER_NAME_RE.match(target))
        return False

    def _reap_orphan_tmp_files_locked(self) -> None:
        """
        Removes temp files left by a writer that died inside _atomic_write_text. Must run under
        _exclusive(). Only names matching ``.<target>.<pid>.<tid>.tmp`` whose target this interlock
        writes are considered; files whose pid is alive (including this process) are retained,
        because recover_unresolved_intents() writes latch markers without the flock. Symlinks and
        non-regular files are never followed or removed. An unlink failure halts (fail closed).
        """
        reaped: List[str] = []
        retained: Dict[str, str] = {}
        directories = [self.ledger_path.parent]
        if self.output_state_dir != self.ledger_path.parent:
            directories.append(self.output_state_dir)
        for directory in directories:
            reaped_here = 0
            for name in sorted(os.listdir(str(directory))):
                m = _ORPHAN_TMP_NAME_RE.match(name)
                if m is None or not self._owned_tmp_target(directory, m.group("target")):
                    continue
                path = directory / name
                if _pid_alive(int(m.group("pid"))):
                    retained[str(path)] = "WRITER_PID_ALIVE"
                    continue
                try:
                    st = os.lstat(str(path))
                except FileNotFoundError:
                    continue
                if not stat.S_ISREG(st.st_mode):
                    retained[str(path)] = "SYMLINK" if stat.S_ISLNK(st.st_mode) else "NOT_REGULAR_FILE"
                    continue
                try:
                    os.unlink(str(path))
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    self._halt(INTEGRITY_ORPHAN_TMP_REAP_FAILED, f"Cannot remove orphan temp file {path}: {exc}")
                reaped.append(str(path))
                reaped_here += 1
            if reaped_here:
                _fsync_dir(directory, self._durable_fsync)
        if reaped:
            logger.warning("Removed %d orphan temp file(s) left by a crashed writer: %s", len(reaped), reaped)
        self.boot_reaped_tmp_count = len(reaped)
        self.boot_reaped_tmp_names = reaped
        self.boot_retained_tmp = retained

    def _run_startup_recovery(self) -> None:
        """
        Latches every DISPATCH_INTENT that no *trusted* receipt resolves. Uses the interlock's
        own signature-verified, HWM-checked view (an unauthenticated receipt cannot hide an intent).
        """
        with self._exclusive():
            self._reap_orphan_tmp_files_locked()
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            recovered: List[RecoveredIntentState] = []
            for caid, bucket in list(self._view.unresolved.items()):
                for intent_id, intent_dict in bucket.items():
                    state = RecoveredIntentState(
                        intent_id=intent_id,
                        caid=caid,
                        target_uri=str(intent_dict.get("target_uri", "unknown")),
                        tool_name=str(intent_dict.get("tool_name", "unknown")),
                        lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                        retry_safe=False,
                        reconciliation_required=True,
                        latched_at=now_iso,
                        reproducibility_evidence_sha256=hashlib.sha256(encode_jcs(intent_dict)).hexdigest(),
                    )
                    recovered.append(state)
                    self._write_latch_marker(caid, _latch_payload_for(state))
            # Reload markers (existing ones plus those just written)
            self._latched_intents = self._load_latch_dir_locked()
            self._latched_intents.update(self._unpersisted_latches)
            for r in recovered:
                self._latched_intents[r.caid] = r

    # ------------------------------------------------------------------
    # Admission checks (fail-closed)
    # ------------------------------------------------------------------

    def _check_not_latched(self, caid: str) -> None:
        if caid in self._latched_intents:
            raise LatchedCaidExecutionHaltedError(
                f"Action CAID {caid} is latched in EFFECT_INDETERMINATE with retry_safe=False. Dispatch refused."
            )

    def _check_not_committed(self, caid: str) -> None:
        if caid in self._view.committed:
            raise CaidAlreadyCommittedError(
                f"{DENY_ALREADY_COMMITTED_NO_RESEND}: Action CAID {caid} already has a COMMITTED continuity "
                f"receipt (intent_id={self._view.committed[caid]!r}). Re-send refused."
            )

    def _check_no_unresolved_intent(self, caid: str) -> None:
        unresolved = self._view.unresolved_for(caid)
        if unresolved:
            raise CaidIntentUnresolvedError(
                f"{DENY_INTENT_UNRESOLVED_NO_RESEND}: Action CAID {caid} has unresolved DISPATCH_INTENT "
                f"{sorted(unresolved)} on disk (in flight or orphaned); treated as EFFECT_INDETERMINATE with "
                f"retry_safe=False. Dispatch refused."
            )

    def _check_not_tainted(self, caid: str) -> None:
        reason = self._view.tainted.get(caid)
        if reason is not None:
            raise LedgerIntegrityViolationError(
                reason,
                f"Action CAID {caid} has an unauthenticated CONTINUITY_RECEIPT on disk (signature does not verify "
                f"against the trusted boundary key); it cannot resolve or unlock the CAID. Dispatch refused.",
                caid=caid,
            )

    def _check_admissible(self, caid: str) -> None:
        """Runs every admission check; must be called while holding _exclusive()."""
        self._check_not_tainted(caid)
        self._check_not_latched(caid)
        self._check_not_committed(caid)
        self._check_no_unresolved_intent(caid)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_caid_latched(self, caid: str) -> bool:
        with self._lock:
            return caid in self._latched_intents

    def get_latched_caids(self) -> Dict[str, RecoveredIntentState]:
        with self._lock:
            return dict(self._latched_intents)

    def is_caid_committed(self, caid: str) -> bool:
        """Re-reads on-disk state and reports whether the CAID has a COMMITTED receipt."""
        with self._exclusive():
            return caid in self._view.committed

    def get_unresolved_intent_ids(self, caid: str) -> List[str]:
        """Re-reads on-disk state and lists unresolved DISPATCH_INTENT ids for the CAID."""
        with self._exclusive():
            return list(self._view.unresolved_for(caid))

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def latch_intent(
        self,
        caid: str,
        reason: str = "MANUAL_LATCH",
        intent_id: Optional[str] = None,
        target_uri: str = "http://unknown",
        tool_name: str = "unknown",
    ) -> RecoveredIntentState:
        """
        Latches a CAID into EFFECT_INDETERMINATE state under the stated model.
        Persists latch marker file to output_state_dir.
        When intent_id is omitted it is derived from the latest unresolved DISPATCH_INTENT
        for the CAID on disk, so a later reconciliation receipt resolves that intent.
        """
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._exclusive():
            if intent_id is None:
                unresolved = self._view.unresolved_for(caid)
                if unresolved:
                    intent_id, rec = list(unresolved.items())[-1]
                    if target_uri == "http://unknown":
                        target_uri = rec.get("target_uri", target_uri)
                    if tool_name == "unknown":
                        tool_name = rec.get("tool_name", tool_name)
            intent_id = intent_id or f"latched-{caid[:16]}"
            latch_state = RecoveredIntentState(
                intent_id=intent_id,
                caid=caid,
                target_uri=target_uri,
                tool_name=tool_name,
                lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                retry_safe=False,
                reconciliation_required=True,
                latched_at=now_iso,
                reproducibility_evidence_sha256="",
            )
            self._latched_intents[caid] = latch_state
            self._write_latch_marker(caid, {
                "caid": caid,
                "intent_id": intent_id,
                "latched_at": now_iso,
                "lifecycle_state": "EFFECT_INDETERMINATE",
                "reason": reason,
                "reconciliation_required": True,
                "retry_safe": False,
                "target_uri": target_uri,
                "tool_name": tool_name,
            })
        return latch_state

    def _consume_approval_locked(
        self,
        approval: OperationApprovalGrant,
        actor_id: str,
        tool_name: str,
        caid: str,
    ) -> None:
        """
        Verifies and atomically consumes a single-use OperationApprovalGrant inside _exclusive().
        """
        if not approval.approval_id or "/" in approval.approval_id or "\\" in approval.approval_id:
            raise ApprovalMismatchError("Invalid approval_id format")
        if approval.subject_actor_id != actor_id:
            raise ApprovalMismatchError(
                f"Approval subject mismatch: grant={approval.subject_actor_id!r} != actor={actor_id!r}"
            )
        if approval.tool_name != tool_name:
            raise ApprovalMismatchError(
                f"Approval tool mismatch: grant={approval.tool_name!r} != tool={tool_name!r}"
            )
        if approval.operation_caid != caid:
            raise ApprovalMismatchError(
                f"Approval operation CAID mismatch: grant={approval.operation_caid!r} != caid={caid!r}"
            )
        now_ts = datetime.now(timezone.utc).timestamp()
        if approval.expires_at_epoch_s is not None and now_ts > approval.expires_at_epoch_s:
            raise ApprovalExpiredError(
                f"Approval {approval.approval_id!r} expired at {approval.expires_at_epoch_s}"
            )
        marker = self.output_state_dir / f"consumed_approval_{approval.approval_id}.json"
        if marker.exists():
            raise ApprovalAlreadyConsumedError(
                f"Approval {approval.approval_id!r} was already consumed; single-use replay refused."
            )
        consumed_payload = {
            "approval_id": approval.approval_id,
            "caid": caid,
            "consumed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "subject_actor_id": actor_id,
            "tool_name": tool_name,
        }
        _atomic_write_text(marker, json.dumps(consumed_payload, indent=2), self._durable_fsync)

    def record_intent(
        self,
        target_uri: str,
        tool_name: str,
        payload: Any,
        intent_id: Optional[str] = None,
        approval: Optional[OperationApprovalGrant] = None,
        actor_id: Optional[str] = None,
    ) -> DispatchIntentRecord:
        """
        Appends and signs an immutable DISPATCH_INTENT record to the ledger.
        Fails closed before any wire access if write fails.
        The record is fsynced (F_FULLFSYNC on darwin when available) before this returns.
        """
        if self.simulate_write_error:
            raise PreDispatchLedgerWriteError(
                "Pre-dispatch ledger write failed: simulated write fault; halted fail-closed before wire access"
            )

        caid = compute_caid(payload)
        with ExitStack() as stack:
            try:
                stack.enter_context(self._exclusive())
            except OSError as exc:
                raise PreDispatchLedgerWriteError(
                    f"Pre-dispatch ledger lock/read failed: {exc}; halted fail-closed before wire access"
                ) from exc

            self._check_admissible(caid)
            if approval is not None:
                effective_actor = actor_id if actor_id is not None else self.authority_id
                self._consume_approval_locked(approval, effective_actor, tool_name, caid)

            now = datetime.now(timezone.utc)
            intent_id = intent_id or (
                "intent-"
                + hashlib.sha256(f"{now.isoformat()}|{os.getpid()}|{os.urandom(16).hex()}".encode()).hexdigest()[:16]
            )
            payload_digest = hashlib.sha256(encode_jcs(payload)).hexdigest()
            now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

            statement = {
                "authority_id": self.authority_id,
                "caid": caid,
                "intent_id": intent_id,
                "payload_digest": payload_digest,
                "policy_epoch": self.policy_epoch,
                "record_type": "DISPATCH_INTENT",
                "schema_version": "1.1.0-eo1-intent",
                "target_uri": target_uri,
                "timestamp_utc": now_iso,
                "tool_name": tool_name,
            }

            jcs_bytes = encode_jcs(statement)
            sig_bytes = self.boundary_private_key.sign(jcs_bytes)
            sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

            record = DispatchIntentRecord(
                record_type="DISPATCH_INTENT",
                schema_version="1.1.0-eo1-intent",
                intent_id=intent_id,
                caid=caid,
                target_uri=target_uri,
                tool_name=tool_name,
                policy_epoch=self.policy_epoch,
                authority_id=self.authority_id,
                timestamp_utc=now_iso,
                payload_digest=payload_digest,
                boundary_signature_b64=sig_b64,
                boundary_public_key_pem=self.boundary_public_key_pem,
            )

            # Durable append to ledger (O_APPEND + short-write loop + fsync)
            try:
                line = json.dumps(record.to_dict()) + "\n"
                self._durable_append(line.encode("utf-8"))
            except Exception as exc:
                raise PreDispatchLedgerWriteError(
                    f"Pre-dispatch ledger write failed: {exc}; halted fail-closed before wire access"
                ) from exc

            return record

    def dispatch(
        self,
        target_uri: str,
        tool_name: str,
        payload: Any,
        dispatch_fn: Optional[Callable[[], Any]] = None,
        intent_id: Optional[str] = None,
        approval: Optional[OperationApprovalGrant] = None,
        actor_id: Optional[str] = None,
    ) -> DispatchResult:
        """
        Executes an outbound action strictly after committing pre-dispatch intent to disk.
        """
        caid = compute_caid(payload)
        intent = self.record_intent(
            target_uri,
            tool_name,
            payload,
            intent_id=intent_id,
            approval=approval,
            actor_id=actor_id,
        )

        # Wire execution
        try:
            if dispatch_fn is not None:
                resp_data = dispatch_fn()
            else:
                req_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    target_uri,
                    data=req_bytes,
                    headers={"Content-Type": "application/json", "X-AEIB-CAID": caid},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    resp_body = resp.read()
                    resp_data = {
                        "status_code": resp.status,
                        "body": resp_body.decode("utf-8", errors="replace"),
                    }

            # On wire success -> emit RECONCILED receipt (disposition COMMITTED: re-send refused)
            receipt = self._emit_receipt(
                intent_id=intent.intent_id,
                caid=caid,
                status="RECONCILED",
                lifecycle_state="RECONCILED",
                retry_safe=False,
                details=resp_data if isinstance(resp_data, dict) else {"result": str(resp_data)},
                disposition=DISPOSITION_COMMITTED,
            )
            return DispatchResult(
                lifecycle_state=IntentLifecycleState.RECONCILED,
                caid=caid,
                receipt=receipt,
                response=resp_data if isinstance(resp_data, dict) else {"result": resp_data},
            )
        except Exception as wire_fault:
            # Wire failure mid-syscall -> latch into EFFECT_INDETERMINATE
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            latch_state = RecoveredIntentState(
                intent_id=intent.intent_id,
                caid=caid,
                target_uri=target_uri,
                tool_name=tool_name,
                lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                retry_safe=False,
                reconciliation_required=True,
                latched_at=now_iso,
                reproducibility_evidence_sha256="",
            )
            latch_payload = {
                "caid": caid,
                "intent_id": intent.intent_id,
                "latched_at": now_iso,
                "lifecycle_state": "EFFECT_INDETERMINATE",
                "reconciliation_required": True,
                "retry_safe": False,
                "target_uri": target_uri,
                "tool_name": tool_name,
                "wire_fault": str(wire_fault),
            }
            with self._lock:
                self._latched_intents[caid] = latch_state
                try:
                    with self._exclusive():
                        self._write_latch_marker(caid, latch_payload)
                        self._unpersisted_latches.pop(caid, None)
                        self._latched_intents[caid] = latch_state
                except (OSError, LedgerIntegrityViolationError) as persist_err:
                    # The unresolved DISPATCH_INTENT on disk still blocks re-send; keep latch in memory.
                    logger.error("Failed to persist latch marker for %s: %s", caid, persist_err)
                    self._unpersisted_latches[caid] = latch_state
                    self._latched_intents[caid] = latch_state
            raise RuntimeError(f"Wire dispatch error; action latched in EFFECT_INDETERMINATE: {wire_fault}") from wire_fault

    def reconcile_out_of_band(
        self,
        caid: str,
        reconciliation_evidence: Dict[str, Any],
        intent_id: Optional[str] = None,
        target_outcome: Optional[str] = None,
        require_latch: bool = False,
    ) -> ContinuityReceipt:
        """
        Clears the indeterminate latch following out-of-band reconciliation and writes receipt.

        - intent_id defaults to the latched intent (or the latest unresolved DISPATCH_INTENT for
          the CAID on disk), so restart recovery does not re-latch the original intent.
        - An explicit intent_id must match the latch or an unresolved intent for the CAID.
        - target_outcome ("COMMITTED" / "NOT_COMMITTED") overrides evidence classification;
          otherwise classify_reconciliation_outcome() is applied (fail-closed to COMMITTED).
          COMMITTED blocks every later re-send of the CAID; NOT_COMMITTED re-opens it.
        - require_latch=True raises ReconciliationTargetNotFoundError when neither a latch nor an
          unresolved intent exists. With the default (False) an orphan receipt is emitted for
          backward compatibility and a warning is logged.
        """
        disposition = classify_reconciliation_outcome(reconciliation_evidence, target_outcome)
        with self._exclusive():
            latch = self._latched_intents.get(caid)
            unresolved = self._view.unresolved_for(caid)
            if latch is None and not unresolved:
                if require_latch:
                    raise ReconciliationTargetNotFoundError(
                        f"No latch or unresolved DISPATCH_INTENT exists for CAID {caid}; nothing to reconcile."
                    )
                logger.warning(
                    "reconcile_out_of_band on CAID %s with no latch or unresolved intent; emitting orphan receipt",
                    caid,
                )
                effective_intent_id = intent_id or f"reconciled-{caid[:16]}"
            else:
                candidates = set(unresolved)
                if latch is not None:
                    candidates.add(latch.intent_id)
                if intent_id is not None:
                    if intent_id not in candidates:
                        raise ValueError(
                            f"intent_id {intent_id!r} does not match the latched/unresolved intents "
                            f"{sorted(candidates)} for CAID {caid}"
                        )
                    effective_intent_id = intent_id
                elif latch is not None and (latch.intent_id in unresolved or not unresolved):
                    effective_intent_id = latch.intent_id
                else:
                    effective_intent_id = list(unresolved)[-1]

            receipt = self._emit_receipt(
                intent_id=effective_intent_id,
                caid=caid,
                status="RECONCILED",
                lifecycle_state="RECONCILED",
                retry_safe=False,
                details=reconciliation_evidence,
                disposition=disposition,
            )
            # Remove in-memory and disk latches (unlink followed by directory fsync)
            self._latched_intents.pop(caid, None)
            self._unpersisted_latches.pop(caid, None)
            _durable_unlink(self.output_state_dir / f"latched_{caid}.json", self._durable_fsync)
            return receipt

    def _emit_receipt(
        self,
        intent_id: str,
        caid: str,
        status: str,
        lifecycle_state: str,
        retry_safe: bool,
        details: Dict[str, Any],
        disposition: Optional[str] = None,
    ) -> ContinuityReceipt:
        if disposition is not None:
            if disposition not in (DISPOSITION_COMMITTED, DISPOSITION_NOT_COMMITTED):
                raise ValueError(f"Unknown effect disposition {disposition!r}")
            details = dict(details)
            details[DISPOSITION_KEY] = disposition

        with self._exclusive():
            # _exclusive() has re-read the ledger, so _chain_tip reflects receipts from any process.
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            statement = {
                "caid": caid,
                "chain_tip": self._chain_tip,
                "intent_id": intent_id,
                "lifecycle_state": lifecycle_state,
                "policy_epoch": self.policy_epoch,
                "reconciled_at": now_iso,
                "reconciliation_details": details,
                "record_type": "CONTINUITY_RECEIPT",
                "retry_safe": retry_safe,
                "schema_version": "1.1.0-eo1-receipt",
                "status": status,
            }
            jcs_bytes = encode_jcs(statement)
            sig_bytes = self.boundary_private_key.sign(jcs_bytes)
            sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

            receipt = ContinuityReceipt(
                record_type="CONTINUITY_RECEIPT",
                schema_version="1.1.0-eo1-receipt",
                intent_id=intent_id,
                caid=caid,
                status=status,
                lifecycle_state=lifecycle_state,
                retry_safe=retry_safe,
                policy_epoch=self.policy_epoch,
                reconciled_at=now_iso,
                chain_tip=self._chain_tip,
                boundary_signature_b64=sig_b64,
                boundary_public_key_pem=self.boundary_public_key_pem,
                reconciliation_details=details,
            )

            # Durable append to ledger (O_APPEND + short-write loop + fsync)
            line = json.dumps(receipt.to_dict()) + "\n"
            self._durable_append(line.encode("utf-8"))

            # Update chain tip only after the receipt is durable
            self._chain_tip = hashlib.sha256(jcs_bytes).hexdigest()

            return receipt
