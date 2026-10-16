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

"""
macp.resilience
================================================================================
Gap 1: Heartbeat lease-timeout management.
Gap 2: Per-profile circuit breaker state machine.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional


class CircuitBreaker:
    """Per-profile circuit breaker that prevents cascading subagent tool failures."""

    def __init__(self, failure_threshold: int = 3, reset_timeout_sec: float = 300.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_sec = reset_timeout_sec
        self.failures = 0
        self.opened_at: Optional[float] = None
        self._lock = threading.Lock()

    def is_open(self, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            if self.opened_at is None:
                return False
            if (now - self.opened_at) >= self.reset_timeout_sec:
                # Cooldown period expired: reset to closed state
                self.opened_at = None
                self.failures = 0
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None

    def record_failure(self, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = now
                return True
            return False


class HeartbeatLeaseTracker:
    """Gap 1: Heartbeat and lease-timeout detection for active worker subagents."""

    def __init__(self, default_lease_sec: float = 90.0) -> None:
        self.default_lease_sec = default_lease_sec
        self._heartbeats: Dict[str, float] = {}
        self._lock = threading.Lock()

    def record_heartbeat(self, task_id: str, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._heartbeats[task_id] = now

    def check_alive(self, task_id: str, timeout_sec: Optional[float] = None, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        limit = self.default_lease_sec if timeout_sec is None else timeout_sec
        with self._lock:
            last = self._heartbeats.get(task_id)
            if last is None:
                return False
            return (now - last) <= limit

    def clear(self, task_id: str) -> None:
        with self._lock:
            self._heartbeats.pop(task_id, None)
