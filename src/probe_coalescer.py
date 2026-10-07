#!/usr/bin/env python3
r"""
probe_coalescer.py - Single-Flight Probe Coalescing (Acceptance Test 11)

When a post-dispatch transport fault (HTTP 504 / TCP RST) affects one
effect_id, many concurrent workers may simultaneously need the authoritative
disposition. This module enforces, under the stated model:

  1. Exactly one authoritative probe executes per effect_id (single-flight);
     concurrent callers wait and share the result instead of issuing
     speculative probes.
  2. All callers observe the same shared disposition.
  3. Retry lockout latches fail-closed whenever the disposition is not
     OUTCOME_VERIFIED, blocking speculative re-dispatch across all callers.

Vocabulary mapping (specification term -> repository constant):
  EFFECT_INDETERMINATE -> DISPATCHED_UNCONFIRMED / PROBE_OUTAGE_HOLD
  probe outcomes       -> OUTCOME_VERIFIED, RECONCILIATION_NOT_FOUND,
                          RECONCILIATION_FAILED (SQLiteOutcomeProbeAdapter)

This is a concurrency control primitive; it does not itself contact any
external system - the probe function is supplied by the caller.
"""

import threading
from typing import Callable, Dict, Optional

# Dispositions that mean the external effect was observed as committed.
COMMITTED_DISPOSITIONS = frozenset({"OUTCOME_VERIFIED", "CONFIRMED"})


class ProbeCoalescer:
    """Single-flight resolver: one authoritative probe per effect_id."""

    def __init__(self, probe_fn: Callable[[str], str], max_concurrent_probes: int = 10) -> None:
        if not callable(probe_fn):
            raise TypeError("probe_fn must be callable")
        self._probe_fn = probe_fn
        self._semaphore = threading.Semaphore(max_concurrent_probes)
        self._lock = threading.Lock()
        self._inflight: Dict[str, threading.Event] = {}
        self._results: Dict[str, str] = {}
        self._probe_counts: Dict[str, int] = {}
        self._retry_safe: Dict[str, bool] = {}

    # -- single-flight resolution ------------------------------------------------
    def resolve(self, effect_id: str) -> str:
        """
        Return the authoritative disposition for effect_id, executing the
        probe exactly once even under concurrent callers. Fail-closed: a
        non-committed disposition latches the retry lockout for every caller.
        """
        if not effect_id:
            raise ValueError("effect_id must be a non-empty string")
        while True:
            with self._lock:
                if effect_id in self._results:
                    return self._results[effect_id]
                event = self._inflight.get(effect_id)
                if event is None:
                    event = threading.Event()
                    self._inflight[effect_id] = event
                    leader = True
                else:
                    leader = False

            if not leader:
                event.wait()
                continue  # re-check under the lock (result or leadership)

            try:
                with self._semaphore:
                    result = self._probe_fn(effect_id)
            except BaseException:
                with self._lock:
                    del self._inflight[effect_id]
                    event.set()
                raise

            if not isinstance(result, str) or not result:
                with self._lock:
                    del self._inflight[effect_id]
                    event.set()
                raise ValueError(f"probe returned a non-disposition: {result!r}")

            with self._lock:
                self._results[effect_id] = result
                self._probe_counts[effect_id] = (
                    self._probe_counts.get(effect_id, 0) + 1
                )
                # Fail-closed lockout: only a committed observation leaves
                # retry open; everything else latches retry_safe = False.
                self._retry_safe[effect_id] = result in COMMITTED_DISPOSITIONS
                del self._inflight[effect_id]
                event.set()
            return result

    # -- observability -----------------------------------------------------------
    def probe_count(self, effect_id: str) -> int:
        """Number of probe executions so far for this effect_id."""
        with self._lock:
            return self._probe_counts.get(effect_id, 0)

    def disposition(self, effect_id: str) -> Optional[str]:
        """Shared disposition, or None if no probe has completed."""
        with self._lock:
            return self._results.get(effect_id)

    def is_retry_safe(self, effect_id: str) -> bool:
        """
        Fail-closed: an unknown or unresolved effect is never retry-safe;
        after resolution, only a committed observation re-opens retry.
        """
        with self._lock:
            return self._retry_safe.get(effect_id, False)
