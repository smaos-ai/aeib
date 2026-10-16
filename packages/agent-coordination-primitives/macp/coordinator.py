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
macp.coordinator
================================================================================
Unified Hardened Subagent Coordinator.
Composes Gaps 1-6 into a single resilient multi-agent execution pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from macp.backpressure import BackpressureLimiter
from macp.bft import BFTProvenanceValidator
from macp.consensus import QuorumConsensusResolver
from macp.idempotency import IdempotentTaskDispatcher
from macp.resilience import CircuitBreaker, HeartbeatLeaseTracker

REQUIRED_HANDBACK_KEYS = {
    "status",
    "scope_reviewed",
    "verified_findings",
    "not_established",
    "summary_for_orchestrator",
}
VALID_STATUSES = {"COMPLETED", "INDETERMINATE", "FAILED"}


class HardenedCoordinator:
    """Coordinates parallel leaf subagents with distributed-systems resilience invariants."""

    def __init__(
        self,
        state_dir: Path,
        repo_root: Path = Path("."),
        max_concurrent: int = 4,
        heartbeat_timeout_sec: float = 90.0,
        breaker_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.repo_root = Path(repo_root)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.heartbeat_timeout_sec = heartbeat_timeout_sec
        self.heartbeats = HeartbeatLeaseTracker(default_lease_sec=heartbeat_timeout_sec)
        self.dispatcher = IdempotentTaskDispatcher(self.state_dir)
        self.backpressure = BackpressureLimiter(
            max_concurrent=max_concurrent,
            ledger_path=self.state_dir / "subagent_observability.jsonl",
        )

        configs = breaker_configs or {
            "aeib-researcher": {"failure_threshold": 3, "reset_timeout_sec": 600.0},
            "aeib-verifier": {"failure_threshold": 5, "reset_timeout_sec": 300.0},
        }
        self.breakers: Dict[str, CircuitBreaker] = {
            prof: CircuitBreaker(cfg["failure_threshold"], cfg["reset_timeout_sec"])
            for prof, cfg in configs.items()
        }

    def dispatch_task(
        self,
        profile: str,
        task_id: str,
        spec: Dict[str, Any],
        worker_fn: Callable[[str, Dict[str, Any]], str],
    ) -> Dict[str, Any]:
        """Dispatches an idempotent task with circuit breaker, backpressure, and BFT verification."""
        # Gap 3: Idempotency check before execution
        is_cached, cached_val = self.dispatcher.check_or_reserve_task(task_id, profile, spec)
        if is_cached and cached_val is not None:
            return cached_val

        # Gap 2: Circuit breaker check
        breaker = self.breakers.setdefault(profile, CircuitBreaker(3, 300.0))
        if breaker.is_open():
            return {
                "status": "FAILED",
                "reason": f"CIRCUIT_BREAKER_OPEN:{profile}",
                "idempotency_key": task_id,
            }

        # Gap 6: Concurrency backpressure throttle
        with self.backpressure.throttle():
            self.heartbeats.record_heartbeat(task_id)
            try:
                raw_output = worker_fn(task_id, spec)

                # Gap 1: Heartbeat verification
                if not self.heartbeats.check_alive(task_id, timeout_sec=self.heartbeat_timeout_sec):
                    breaker.record_failure()
                    indeterminate_handback = {
                        "status": "INDETERMINATE",
                        "reason": "HEARTBEAT_TIMEOUT",
                        "idempotency_key": task_id,
                    }
                    self.dispatcher.record_completed_result(task_id, indeterminate_handback)
                    return indeterminate_handback

                validated = self.validate_and_record_handback(task_id, raw_output)
                if validated.get("status") == "FAILED":
                    breaker.record_failure()
                else:
                    breaker.record_success()
                return validated
            except Exception as exc:
                breaker.record_failure()
                err_handback = {
                    "status": "FAILED",
                    "reason": str(exc),
                    "idempotency_key": task_id,
                }
                return err_handback

    def validate_and_record_handback(self, task_id: str, raw_handback_str: str) -> Dict[str, Any]:
        """Validates JSON schema, word limits, and BFT provenance before storing on disk."""
        cleaned = raw_handback_str.strip()
        if cleaned.startswith("```"):
            lines = [ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        payload: Dict[str, Any] = json.loads(cleaned)
        missing = REQUIRED_HANDBACK_KEYS - set(payload.keys())
        if missing:
            raise ValueError(f"Subagent handback missing required keys: {sorted(missing)}")
        if payload["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {payload['status']}")

        summary_words = len(str(payload.get("summary_for_orchestrator", "")).split())
        if summary_words > 250:
            raise ValueError(f"Summary exceeds 250-word limit ({summary_words} words)")

        # Gap 4: Zero-LLM BFT Provenance verification
        BFTProvenanceValidator.validate_handback(self.repo_root, payload)

        # Gap 3: Persist completed result
        raw_bytes = self.dispatcher.record_completed_result(task_id, payload)

        # Gap 6: Record fsync'd telemetry
        self.backpressure.record_telemetry(
            task_id=task_id,
            status=payload["status"],
            summary=payload.get("summary_for_orchestrator", ""),
            raw_result_bytes=raw_bytes,
            extra={
                "scope_count": len(payload.get("scope_reviewed", [])),
                "findings_count": len(payload.get("verified_findings", [])),
            },
        )
        return payload

    @staticmethod
    def resolve_consensus(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Gap 5: Resolves 2-of-3 quorum consensus over agent findings."""
        return QuorumConsensusResolver.resolve(results)
