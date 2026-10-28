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
src/eo1_reconciliation_adapter.py
================================================================================
Read-back reconciliation adapter for the EO1 PreDispatchIntentInterlock (prototype,
evaluated under the stated model).

EO1 latches every interrupted dispatch into EFFECT_INDETERMINATE with retry_safe=False and
refuses re-send until out-of-band reconciliation settles the target-side state. This adapter
automates that step for targets that expose a read-back path:

  - It scans the CAIDs the interlock currently has latched (re-read from disk under the
    interlock's flock via a public query) and, for each, calls a target-specific
    ``ReadBackProbe`` with the CAID (the idempotency token carried on the wire).
  - APPLIED      -> ``reconcile_out_of_band(..., target_outcome="COMMITTED")``: the CAID is
                    committed and every later re-send is refused by EO1.
  - NOT_APPLIED  -> settles NOT_COMMITTED (EO1 re-opens the CAID for one fresh attempt; the
                    adapter never re-sends by itself) ONLY on one of these bases, recorded in
                    the receipt as ``settlement_basis``:
                      "fence"     a FenceProbe acked an attempt fence for the CAID: the target
                                  will refuse every still-in-flight write with a lower attempt;
                      "deadline"  a server-enforced not-after deadline (DeadlineContract) for
                                  the attempt has elapsed, plus a clock-skew margin;
                      "unsafe_trust_not_applied"  explicit opt-in
                                  ``trust_not_applied_without_fence=True``.
                    Otherwise the CAID stays latched with reason NOT_APPLIED_UNFENCED (default).
                    A fence that observes the effect (late commit landed) settles COMMITTED.
  - UNKNOWN      -> nothing is written; the CAID stays latched (the adapter never guesses).

Why the fail-closed default: LIMBO (arXiv:2609.29095) Proposition 1 states that no
verification-only policy is exactly-once under late commits without a known bound on in-flight
time; MCP conformance issue #3394 row C classifies "in flight + read-back not found" as UNKNOWN,
not safe to retry. A read-back NOT_APPLIED cannot exclude a write that is still being processed.

Every settled outcome is recorded through EO1's own signed CONTINUITY_RECEIPT path
(``reconcile_out_of_band``), so the receipt is Ed25519-signed by the interlock's boundary key
and chained into the ledger. Probe calls are bounded (``max_probe_attempts``) with
exponential backoff; the clock and sleep functions are injectable.

Requirements on the target (documented, not enforced here): the write request must carry the
CAID (EO1's default urllib path sends it as the ``X-AEIB-CAID`` header) and the target must
answer a read-back query keyed by that CAID. Fencing additionally needs the write to carry an
attempt token (CAID + attempt number, ``count_dispatch_attempts(...) + 1``) and a target-side
fence that checks-and-fences atomically. Deadlines need the target to enforce a not-after time.
All three need target cooperation; tools without them remain EFFECT_INDETERMINATE by design.

Limitations (stated):
  - With the unsafe opt-in, a target that applies an in-flight request after answering
    NOT_APPLIED (late commit, LIMBO ``timeout_late``) can produce a duplicate on the fresh
    attempt. ``not_applied_confirmations`` > 1 narrows but does not close that window.
  - A fence is only as good as the target's enforcement of it; a lying target defeats it.
  - Only latched CAIDs are scanned. An unresolved DISPATCH_INTENT without a latch may still be
    in flight in another process and is skipped.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from src.eo1_write_before_execute import (
    DISPOSITION_COMMITTED,
    DISPOSITION_NOT_COMMITTED,
    ContinuityReceipt,
    PreDispatchIntentInterlock,
    ReconciliationTargetNotFoundError,
)

logger = logging.getLogger(__name__)

RECONCILER_ID = "eo1_reconciliation_adapter"
RECONCILER_SCHEMA_VERSION = "1.1.0-eo1-readback-reconcile-basis"


class ReadBackOutcome(str, Enum):
    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    UNKNOWN = "UNKNOWN"


class SettlementStatus(str, Enum):
    SETTLED_COMMITTED = "SETTLED_COMMITTED"
    SETTLED_NOT_COMMITTED = "SETTLED_NOT_COMMITTED"
    LATCHED_UNKNOWN = "LATCHED_UNKNOWN"
    LATCHED_FENCE_FAILED = "LATCHED_FENCE_FAILED"
    LATCHED_NOT_APPLIED_UNFENCED = "LATCHED_NOT_APPLIED_UNFENCED"
    ALREADY_RESOLVED = "ALREADY_RESOLVED"


# Recorded in the receipt evidence as "settlement_basis".
BASIS_READ_BACK_APPLIED = "read_back_applied"
BASIS_FENCE = "fence"
BASIS_FENCE_OBSERVED_APPLIED = "fence_observed_applied"
BASIS_DEADLINE = "deadline"
BASIS_UNSAFE_TRUST = "unsafe_trust_not_applied"

# Reason codes for NOT_APPLIED reads that leave the CAID latched.
REASON_NOT_APPLIED_UNFENCED = "NOT_APPLIED_UNFENCED"
REASON_FENCE_FAILED = "NOT_APPLIED_FENCE_FAILED"
REASON_DEADLINE_NOT_ELAPSED = "NOT_APPLIED_DEADLINE_NOT_ELAPSED"


@dataclass(frozen=True)
class DeadlineContract:
    """
    Server-enforced not-after bound: the target refuses (never applies) a write older than
    ``not_after_s`` seconds after its dispatch. A NOT_APPLIED read may settle once
    ``not_after_s + clock_skew_margin_s`` (+1 s for the ledger's whole-second timestamps) have
    elapsed since the attempt's DISPATCH_INTENT timestamp.
    """

    not_after_s: float
    clock_skew_margin_s: float = 1.0

    def __post_init__(self) -> None:
        if self.not_after_s <= 0 or self.clock_skew_margin_s < 0:
            raise ValueError("not_after_s must be > 0 and clock_skew_margin_s >= 0")


class FenceOutcome(str, Enum):
    """Target answer to an attempt fence."""

    FENCED_NOT_APPLIED = "FENCED_NOT_APPLIED"  # fence installed; effect still absent at fence time
    APPLIED = "APPLIED"  # effect observed at fence time (e.g. a late commit landed after read-back)
    FAILED = "FAILED"  # fence unsupported, refused, malformed or timed out


@dataclass(frozen=True)
class ReadBackRequest:
    """What a probe receives: the CAID is the idempotency token the target must index by."""

    caid: str
    intent_id: str
    target_uri: str
    tool_name: str
    attempt: int


@dataclass(frozen=True)
class FenceRequest:
    """Ask the target to refuse every still-in-flight write for ``caid`` whose attempt < below_attempt."""

    caid: str
    intent_id: str
    target_uri: str
    tool_name: str
    below_attempt: int


class ReadBackProbe(Protocol):
    """Target-specific read-back: returns APPLIED / NOT_APPLIED / UNKNOWN for a CAID."""

    def __call__(self, request: ReadBackRequest) -> ReadBackOutcome: ...


class FenceProbe(Protocol):
    """Target-specific attempt fence; must check-and-fence atomically on the target side."""

    def __call__(self, request: FenceRequest) -> FenceOutcome: ...


@dataclass(frozen=True)
class IntentSettlement:
    caid: str
    intent_id: str
    status: SettlementStatus
    read_back: ReadBackOutcome
    probe_attempts: int
    total_probe_attempts: int
    probe_errors: List[str]
    elapsed_ms: int
    receipt: Optional[ContinuityReceipt] = None
    fence: Optional[FenceOutcome] = None
    fence_below_attempt: Optional[int] = None
    basis: Optional[str] = None
    reason: Optional[str] = None


_LATCHED_STATUSES = frozenset({
    SettlementStatus.LATCHED_UNKNOWN,
    SettlementStatus.LATCHED_FENCE_FAILED,
    SettlementStatus.LATCHED_NOT_APPLIED_UNFENCED,
})


@dataclass
class ReconcileReport:
    settlements: List[IntentSettlement] = field(default_factory=list)

    def _by(self, status: SettlementStatus) -> List[IntentSettlement]:
        return [s for s in self.settlements if s.status == status]

    @property
    def committed(self) -> List[IntentSettlement]:
        return self._by(SettlementStatus.SETTLED_COMMITTED)

    @property
    def not_committed(self) -> List[IntentSettlement]:
        return self._by(SettlementStatus.SETTLED_NOT_COMMITTED)

    @property
    def still_latched(self) -> List[IntentSettlement]:
        return [s for s in self.settlements if s.status in _LATCHED_STATUSES]

    @property
    def fence_failed(self) -> List[IntentSettlement]:
        return self._by(SettlementStatus.LATCHED_FENCE_FAILED)

    @property
    def unfenced(self) -> List[IntentSettlement]:
        return self._by(SettlementStatus.LATCHED_NOT_APPLIED_UNFENCED)

    @property
    def probes_issued(self) -> int:
        return sum(s.probe_attempts for s in self.settlements)


def _coerce_outcome(value: Any) -> ReadBackOutcome:
    """Maps a probe return value onto ReadBackOutcome; anything unrecognised is UNKNOWN."""
    if isinstance(value, ReadBackOutcome):
        return value
    if isinstance(value, str):
        try:
            return ReadBackOutcome(value.strip().upper())
        except ValueError:
            return ReadBackOutcome.UNKNOWN
    return ReadBackOutcome.UNKNOWN


def _coerce_fence(value: Any) -> FenceOutcome:
    """Maps a fence return value onto FenceOutcome; anything unrecognised is FAILED."""
    if isinstance(value, FenceOutcome):
        return value
    if isinstance(value, str):
        try:
            return FenceOutcome(value.strip().upper())
        except ValueError:
            return FenceOutcome.FAILED
    return FenceOutcome.FAILED


def count_dispatch_attempts(interlock: PreDispatchIntentInterlock, caid: str) -> int:
    """
    Number of DISPATCH_INTENT records for ``caid`` in the interlock's ledger file. Every record
    counts, signed or not, so the count can only over-estimate (a higher fence is the safe side).
    Undecodable (torn) lines are skipped. Dispatchers that send an attempt token use
    ``count_dispatch_attempts(...) + 1`` for the next attempt; the fence uses the same value.
    """
    path = Path(interlock.ledger_path)
    if not path.exists():
        return 0
    count = 0
    for raw in path.read_bytes().split(b"\n"):
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(rec, dict) and rec.get("record_type") == "DISPATCH_INTENT" and rec.get("caid") == caid:
            count += 1
    return count


def intent_dispatched_at(interlock: PreDispatchIntentInterlock, intent_id: str) -> Optional[float]:
    """Epoch seconds of the DISPATCH_INTENT ``timestamp_utc`` for intent_id, or None if absent/unparseable."""
    path = Path(interlock.ledger_path)
    if not path.exists():
        return None
    found: Optional[float] = None
    for raw in path.read_bytes().split(b"\n"):
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(rec, dict) and rec.get("record_type") == "DISPATCH_INTENT" and rec.get("intent_id") == intent_id:
            try:
                found = datetime.strptime(str(rec.get("timestamp_utc")), "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc).timestamp()
            except ValueError:
                return None
    return found


class Eo1ReconciliationAdapter:
    """
    Settles latched EFFECT_INDETERMINATE intents through EO1's public reconcile path.

    Args:
        interlock: the PreDispatchIntentInterlock that owns the ledger.
        probe: target-specific ReadBackProbe.
        max_probe_attempts: probe calls per intent per pass (>= 1). UNKNOWN results and probe
            exceptions are retried up to this bound; after it the intent stays latched.
        backoff_initial_s / backoff_factor / backoff_max_s: sleep between probe attempts.
        not_applied_confirmations: consecutive NOT_APPLIED reads required before settling
            NOT_COMMITTED (>= 1). Any APPLIED read settles COMMITTED.
        max_total_probes_per_intent: optional lifetime cap per intent across passes within
            this adapter instance; once reached the intent is left latched without probing.
        fence: optional FenceProbe; on NOT_APPLIED the adapter asks the target to fence every
            attempt <= count_dispatch_attempts(caid) before settling NOT_COMMITTED.
        deadline: optional DeadlineContract (server-enforced not-after bound).
        trust_not_applied_without_fence: UNSAFE explicit opt-in; settles NOT_APPLIED without a
            fence or deadline (duplicates under late commits; LIMBO Prop. 1).
        attempt_counter: maps (interlock, caid) to attempts recorded so far.
        clock: monotonic seconds; sleep: blocking sleep; wall_clock: epoch seconds (deadline).
    """

    def __init__(
        self,
        interlock: PreDispatchIntentInterlock,
        probe: ReadBackProbe,
        max_probe_attempts: int = 3,
        backoff_initial_s: float = 0.05,
        backoff_factor: float = 2.0,
        backoff_max_s: float = 1.0,
        not_applied_confirmations: int = 1,
        max_total_probes_per_intent: Optional[int] = None,
        probe_id: str = "readback",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        fence: Optional[FenceProbe] = None,
        deadline: Optional[DeadlineContract] = None,
        trust_not_applied_without_fence: bool = False,
        attempt_counter: Callable[[PreDispatchIntentInterlock, str], int] = count_dispatch_attempts,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        if max_probe_attempts < 1:
            raise ValueError("max_probe_attempts must be >= 1")
        if not_applied_confirmations < 1:
            raise ValueError("not_applied_confirmations must be >= 1")
        if not_applied_confirmations > max_probe_attempts:
            raise ValueError("not_applied_confirmations cannot exceed max_probe_attempts")
        if backoff_initial_s < 0 or backoff_max_s < 0 or backoff_factor < 1:
            raise ValueError("backoff values must be non-negative and backoff_factor >= 1")
        if max_total_probes_per_intent is not None and max_total_probes_per_intent < 1:
            raise ValueError("max_total_probes_per_intent must be >= 1 when set")
        self.interlock = interlock
        self.probe = probe
        self.max_probe_attempts = max_probe_attempts
        self.backoff_initial_s = backoff_initial_s
        self.backoff_factor = backoff_factor
        self.backoff_max_s = backoff_max_s
        self.not_applied_confirmations = not_applied_confirmations
        self.max_total_probes_per_intent = max_total_probes_per_intent
        self.probe_id = probe_id
        self._clock = clock
        self._sleep = sleep
        self._attempts: Dict[str, int] = {}
        self.fence = fence
        self.deadline = deadline
        self.trust_not_applied_without_fence = trust_not_applied_without_fence
        self._attempt_counter = attempt_counter
        self._wall_clock = wall_clock

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def attempts_for(self, intent_id: str) -> int:
        """Probe calls issued so far for intent_id by this adapter instance."""
        return self._attempts.get(intent_id, 0)

    def pending_latched(self) -> Dict[str, Any]:
        """
        Latched CAIDs after re-reading on-disk ledger and latch state. ``get_unresolved_intent_ids``
        is a public query that re-syncs the interlock under its flock; ``get_latched_caids`` alone
        reads only the in-memory view.
        """
        self.interlock.get_unresolved_intent_ids("")
        return self.interlock.get_latched_caids()

    # ------------------------------------------------------------------
    # Probe loop
    # ------------------------------------------------------------------

    def _backoff_delay(self, attempt_index: int) -> float:
        delay = self.backoff_initial_s * (self.backoff_factor ** attempt_index)
        return min(delay, self.backoff_max_s)

    def _probe_with_retries(self, latch: Any) -> tuple:
        errors: List[str] = []
        attempts = 0
        not_applied_streak = 0
        while attempts < self.max_probe_attempts:
            if (
                self.max_total_probes_per_intent is not None
                and self.attempts_for(latch.intent_id) >= self.max_total_probes_per_intent
            ):
                break
            if attempts > 0:
                self._sleep(self._backoff_delay(attempts - 1))
            attempts += 1
            self._attempts[latch.intent_id] = self.attempts_for(latch.intent_id) + 1
            request = ReadBackRequest(
                caid=latch.caid,
                intent_id=latch.intent_id,
                target_uri=latch.target_uri,
                tool_name=latch.tool_name,
                attempt=self.attempts_for(latch.intent_id),
            )
            try:
                read = _coerce_outcome(self.probe(request))
            except Exception as exc:  # fail closed: a failing probe never settles anything
                errors.append(f"{type(exc).__name__}: {exc}"[:200])
                read = ReadBackOutcome.UNKNOWN
            if read == ReadBackOutcome.APPLIED:
                return ReadBackOutcome.APPLIED, attempts, errors
            if read == ReadBackOutcome.NOT_APPLIED:
                not_applied_streak += 1
                if not_applied_streak >= self.not_applied_confirmations:
                    return ReadBackOutcome.NOT_APPLIED, attempts, errors
            else:
                not_applied_streak = 0
        return ReadBackOutcome.UNKNOWN, attempts, errors

    # ------------------------------------------------------------------
    # Settlement
    # ------------------------------------------------------------------

    def _deadline_elapsed(self, latch: Any) -> bool:
        if self.deadline is None:
            return False
        dispatched = intent_dispatched_at(self.interlock, latch.intent_id)
        if dispatched is None:
            return False
        bound = dispatched + 1.0 + self.deadline.not_after_s + self.deadline.clock_skew_margin_s
        return self._wall_clock() >= bound

    def _try_fence(self, latch: Any, errors: List[str]) -> tuple:
        below = self._attempt_counter(self.interlock, latch.caid) + 1
        request = FenceRequest(
            caid=latch.caid,
            intent_id=latch.intent_id,
            target_uri=latch.target_uri,
            tool_name=latch.tool_name,
            below_attempt=below,
        )
        try:
            outcome = _coerce_fence(self.fence(request))  # type: ignore[misc]
        except Exception as exc:  # fail closed: a failing fence never re-opens the CAID
            errors.append(f"fence {type(exc).__name__}: {exc}"[:200])
            outcome = FenceOutcome.FAILED
        return outcome, below

    def settle(self, latch: Any) -> IntentSettlement:
        """Probes one latched intent and settles it through reconcile_out_of_band."""
        t0 = self._clock()
        read, attempts, errors = self._probe_with_retries(latch)
        fence_outcome: Optional[FenceOutcome] = None
        fence_below: Optional[int] = None
        basis: Optional[str] = None
        reason: Optional[str] = None
        disposition = DISPOSITION_COMMITTED

        if read == ReadBackOutcome.APPLIED:
            basis = BASIS_READ_BACK_APPLIED
        elif read == ReadBackOutcome.NOT_APPLIED:
            disposition = DISPOSITION_NOT_COMMITTED
            if self.fence is not None:
                fence_outcome, fence_below = self._try_fence(latch, errors)
                if fence_outcome == FenceOutcome.FENCED_NOT_APPLIED:
                    basis = BASIS_FENCE
                elif fence_outcome == FenceOutcome.APPLIED:
                    basis, disposition = BASIS_FENCE_OBSERVED_APPLIED, DISPOSITION_COMMITTED
                elif self._deadline_elapsed(latch):
                    basis = BASIS_DEADLINE
                else:
                    reason = REASON_FENCE_FAILED
            elif self._deadline_elapsed(latch):
                basis = BASIS_DEADLINE
            elif self.trust_not_applied_without_fence:
                basis = BASIS_UNSAFE_TRUST
            elif self.deadline is not None:
                reason = REASON_DEADLINE_NOT_ELAPSED
            else:
                reason = REASON_NOT_APPLIED_UNFENCED
        elapsed_ms = int(round((self._clock() - t0) * 1000))

        def _result(status: SettlementStatus, receipt: Optional[ContinuityReceipt] = None) -> IntentSettlement:
            return IntentSettlement(
                caid=latch.caid,
                intent_id=latch.intent_id,
                status=status,
                read_back=read,
                probe_attempts=attempts,
                total_probe_attempts=self.attempts_for(latch.intent_id),
                probe_errors=list(errors),
                elapsed_ms=elapsed_ms,
                receipt=receipt,
                fence=fence_outcome,
                fence_below_attempt=fence_below,
                basis=basis,
                reason=reason,
            )

        if read == ReadBackOutcome.UNKNOWN:
            return _result(SettlementStatus.LATCHED_UNKNOWN)
        if reason == REASON_FENCE_FAILED:
            return _result(SettlementStatus.LATCHED_FENCE_FAILED)
        if reason is not None:
            return _result(SettlementStatus.LATCHED_NOT_APPLIED_UNFENCED)

        evidence = {
            "reconciler": RECONCILER_ID,
            "reconciler_schema_version": RECONCILER_SCHEMA_VERSION,
            "probe_id": self.probe_id,
            "read_back_outcome": read.value,
            "settlement_basis": basis,
            "probe_attempts": attempts,
            "total_probe_attempts": self.attempts_for(latch.intent_id),
            "probe_errors": list(errors),
            "elapsed_ms": elapsed_ms,
            "target_uri": latch.target_uri,
            "tool_name": latch.tool_name,
        }
        if fence_outcome is not None:
            evidence["fence_outcome"] = fence_outcome.value
            evidence["fence_below_attempt"] = fence_below
        try:
            receipt = self.interlock.reconcile_out_of_band(
                latch.caid,
                evidence,
                intent_id=latch.intent_id,
                target_outcome=disposition,
                require_latch=True,
            )
        except (ReconciliationTargetNotFoundError, ValueError) as exc:
            # Another process settled this intent between scan and reconcile: no second receipt.
            logger.info("Intent %s for CAID %s already resolved: %s", latch.intent_id, latch.caid, exc)
            return _result(SettlementStatus.ALREADY_RESOLVED)
        status = (
            SettlementStatus.SETTLED_COMMITTED
            if disposition == DISPOSITION_COMMITTED
            else SettlementStatus.SETTLED_NOT_COMMITTED
        )
        return _result(status, receipt)

    def reconcile_pending(self, caids: Optional[Iterable[str]] = None) -> ReconcileReport:
        """
        One reconciliation pass over latched CAIDs (optionally restricted to ``caids``).
        Idempotent across restarts: a settled intent has a receipt on disk and is no longer
        latched, so a later pass (in this or a new process) does not probe or settle it again.
        """
        wanted = set(caids) if caids is not None else None
        report = ReconcileReport()
        for caid, latch in sorted(self.pending_latched().items()):
            if wanted is not None and caid not in wanted:
                continue
            report.settlements.append(self.settle(latch))
        return report
