#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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

r"""
probe_coalescer.py - Single-Flight Probe Coalescing & Rate Limiting (Acceptance Tests 11 & 53)

When a post-dispatch transport fault (HTTP 504 / TCP RST) affects an action,
many concurrent workers may simultaneously need the authoritative target disposition.
This module enforces, under the stated model:

  1. Exactly one authoritative probe executes per effect_id (single-flight);
     concurrent callers wait and share the result instead of issuing
     speculative probes.
  2. All callers observe the same shared disposition.
  3. Retry lockout latches fail-closed whenever the disposition is not
     OUTCOME_VERIFIED, blocking speculative re-dispatch across all callers.
  4. Token-bucket rate limiting caps query rate at PROBE_CIRCUIT_BREAKER_LIMIT (50 RPS).
     Rate exhaustion trips ANSI 86 software lockout:
     status = ANSI_86_LOCKOUT, retry_policy = COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED.

Vocabulary mapping (specification term -> repository constant):
  EFFECT_INDETERMINATE -> DISPATCHED_UNCONFIRMED / PROBE_OUTAGE_HOLD
  probe outcomes       -> OUTCOME_VERIFIED, RECONCILIATION_NOT_FOUND,
                          RECONCILIATION_FAILED, ANSI_86_LOCKOUT
"""

import threading
import time
from typing import Callable, Dict, Optional

# Dispositions that mean the external effect was observed as committed.
COMMITTED_DISPOSITIONS = frozenset({"OUTCOME_VERIFIED", "CONFIRMED"})

PROBE_CIRCUIT_BREAKER_LIMIT = 50.0  # Max 50 queries/second


class ProbeCircuitBreakerTripped(RuntimeError):
    """Raised when probe query rate exceeds PROBE_CIRCUIT_BREAKER_LIMIT."""
    disposition = "ANSI_86_LOCKOUT"
    retry_policy = "COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED"

    def __init__(self, message: str = "PROBE_CIRCUIT_BREAKER_LIMIT exceeded (50 RPS): ANSI_86_LOCKOUT engaged."):
        super().__init__(message)


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter for probe query throttling."""

    def __init__(self, rate: float = PROBE_CIRCUIT_BREAKER_LIMIT, capacity: float = PROBE_CIRCUIT_BREAKER_LIMIT):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class ProbeCoalescer:
    """Single-flight resolver: one authoritative probe per effect_id with token-bucket breaker."""

    def __init__(
        self,
        probe_fn: Callable[[str], str],
        max_concurrent_probes: int = 10,
        rate_limit_rps: float = PROBE_CIRCUIT_BREAKER_LIMIT,
        burst_capacity: float = PROBE_CIRCUIT_BREAKER_LIMIT,
    ) -> None:
        if not callable(probe_fn):
            raise TypeError("probe_fn must be callable")
        self._probe_fn = probe_fn
        self._semaphore = threading.Semaphore(max_concurrent_probes)
        self._lock = threading.Lock()
        self._inflight: Dict[str, threading.Event] = {}
        self._results: Dict[str, str] = {}
        self._probe_counts: Dict[str, int] = {}
        self._retry_safe: Dict[str, bool] = {}
        self._rate_limiter = TokenBucketRateLimiter(rate=rate_limit_rps, capacity=burst_capacity)
        self._ansi_86_locked = False

    # -- single-flight resolution ------------------------------------------------
    def resolve(self, effect_id: str) -> str:
        """
        Return the authoritative disposition for effect_id, executing the
        probe exactly once even under concurrent callers. Fail-closed: a
        non-committed disposition latches the retry lockout for every caller.
        Trips ANSI_86_LOCKOUT if rate limit is exceeded.
        """
        if not effect_id:
            raise ValueError("effect_id must be a non-empty string")

        # Check existing ANSI 86 lockout state
        with self._lock:
            if self._ansi_86_locked:
                self._results[effect_id] = "ANSI_86_LOCKOUT"
                self._retry_safe[effect_id] = False
                raise ProbeCircuitBreakerTripped()

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

            # Token-bucket check prior to physical probe dispatch
            if not self._rate_limiter.consume(1.0):
                with self._lock:
                    self._ansi_86_locked = True
                    self._results[effect_id] = "ANSI_86_LOCKOUT"
                    self._retry_safe[effect_id] = False
                    del self._inflight[effect_id]
                    event.set()
                raise ProbeCircuitBreakerTripped(
                    f"PROBE_CIRCUIT_BREAKER_LIMIT exceeded for effect {effect_id}: ANSI_86_LOCKOUT engaged."
                )

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

    # -- observability & control -------------------------------------------------
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

    def is_ansi_86_locked(self) -> bool:
        """Returns True if the circuit breaker has tripped into ANSI 86 lockout."""
        with self._lock:
            return self._ansi_86_locked

    def reset_circuit_breaker(self) -> None:
        """Explicit operator reset of the ANSI 86 lockout."""
        with self._lock:
            self._ansi_86_locked = False
