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

"""
tools/subagent_coordinator.py
================================================================================
Hardened Antigravity Subagent Coordinator (Gaps 1-6 closed):
- Gap 1: Heartbeat & lease-timeout detection
- Gap 2: Per-profile circuit breakers with automatic cooldown
- Gap 3: Idempotent task dispatch (EO-1 disk persistence prior to spawn)
- Gap 4: Deterministic BFT provenance validation (via semantic_validator.py)
- Gap 5: 2-of-3 quorum consensus with INDETERMINATE fallback
- Gap 6: BoundedSemaphore backpressure throttling
"""

from __future__ import annotations

import collections
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from tools.semantic_validator import SemanticValidationError, validate_handback_semantics

REQUIRED_HANDBACK_KEYS = {
    "status",
    "scope_reviewed",
    "verified_findings",
    "not_established",
    "summary_for_orchestrator",
}
VALID_STATUSES = {"COMPLETED", "INDETERMINATE", "FAILED"}


def encode_jcs(obj: Any) -> bytes:
    """Strict RFC 8785 JSON Canonicalization Scheme (JCS)."""
    if obj is None:
        return b"null"
    if isinstance(obj, bool):
        return b"true" if obj else b"false"
    if isinstance(obj, int):
        return str(obj).encode("utf-8")
    if isinstance(obj, float):
        if obj != obj or obj == float("inf") or obj == float("-inf"):
            raise ValueError(f"JCS does not support non-finite float {obj}")
        if obj.is_integer():
            return str(int(obj)).encode("utf-8")
        return f"{obj:.16g}".encode("utf-8")
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if isinstance(obj, list):
        items = [encode_jcs(x) for x in obj]
        return b"[" + b",".join(items) + b"]"
    if isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=lambda k: k.encode("utf-16-be"))
        parts = []
        for k in sorted_keys:
            encoded_k = json.dumps(k, ensure_ascii=False).encode("utf-8")
            encoded_v = encode_jcs(obj[k])
            parts.append(encoded_k + b":" + encoded_v)
        return b"{" + b",".join(parts) + b"}"
    raise TypeError(f"Type {type(obj)} not serializable in RFC 8785 JCS")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    return raw


# -----------------------------------------------------------------------------
# Gap 2: Circuit Breaker State Machine
# -----------------------------------------------------------------------------

class CircuitBreakerState:
    def __init__(self, failure_threshold: int, reset_timeout_sec: float) -> None:
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
                # Half-open reset after cooldown window
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


# -----------------------------------------------------------------------------
# Hardened Subagent Coordinator
# -----------------------------------------------------------------------------

class HardenedSubagentCoordinator:
    def __init__(
        self,
        state_dir: Path,
        repo_root: Path = Path("."),
        max_concurrent: int = 4,
        heartbeat_timeout_sec: float = 90.0,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.repo_root = Path(repo_root)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.semaphore = threading.BoundedSemaphore(max_concurrent)
        self.heartbeat_timeout_sec = heartbeat_timeout_sec
        self.breakers: Dict[str, CircuitBreakerState] = {
            "aeib-researcher": CircuitBreakerState(failure_threshold=3, reset_timeout_sec=600.0),
            "aeib-verifier": CircuitBreakerState(failure_threshold=5, reset_timeout_sec=300.0),
        }
        self._heartbeats: Dict[str, float] = {}

    def record_heartbeat(self, task_id: str, now: Optional[float] = None) -> None:
        self._heartbeats[task_id] = time.monotonic() if now is None else now

    def check_heartbeat_alive(self, task_id: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        last = self._heartbeats.get(task_id)
        if last is None:
            return False
        return (now - last) <= self.heartbeat_timeout_sec

    def dispatch_idempotent_task(
        self,
        profile: str,
        task_id: str,
        spec: Dict[str, Any],
        worker_fn: Callable[[str, Dict[str, Any]], str],
    ) -> Dict[str, Any]:
        """Enforces Circuit Breaker (Gap 2), Idempotency (Gap 3), Backpressure (Gap 6), Heartbeat (Gap 1), and BFT Validation (Gap 4)."""
        task_path = self.state_dir / f"{task_id}.task.json"
        result_path = self.state_dir / f"{task_id}.result.json"
        spec_caid = f"sha256:{hashlib.sha256(encode_jcs(spec)).hexdigest()}"

        # Gap 3: Idempotency check before spawning
        if task_path.exists():
            existing_task = json.loads(task_path.read_text(encoding="utf-8"))
            if existing_task.get("spec_caid") != spec_caid:
                raise ValueError(f"Idempotency key collision with mutated spec for {task_id}")
            if existing_task.get("status") == "COMPLETED" and result_path.exists():
                return json.loads(result_path.read_text(encoding="utf-8"))
            if existing_task.get("status") == "DISPATCHED":
                return {
                    "status": "INDETERMINATE",
                    "reason": "DUPLICATE_DISPATCH_BLOCKED_IN_FLIGHT",
                    "idempotency_key": task_id,
                }

        # Gap 2: Circuit breaker check
        breaker = self.breakers.setdefault(profile, CircuitBreakerState(3, 300.0))
        if breaker.is_open():
            return {
                "status": "FAILED",
                "reason": f"CIRCUIT_BREAKER_OPEN:{profile}",
                "idempotency_key": task_id,
            }

        # Gap 6: Acquire bounded semaphore for backpressure
        self.semaphore.acquire()
        try:
            task_record = {
                "idempotency_key": task_id,
                "profile": profile,
                "spec_caid": spec_caid,
                "status": "DISPATCHED",
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_write_json(task_path, task_record)
            self.record_heartbeat(task_id)

            raw_output = worker_fn(task_id, spec)

            if not self.check_heartbeat_alive(task_id):
                breaker.record_failure()
                task_record["status"] = "INDETERMINATE"
                _atomic_write_json(task_path, task_record)
                return {
                    "status": "INDETERMINATE",
                    "reason": "HEARTBEAT_TIMEOUT",
                    "idempotency_key": task_id,
                }

            validated = self.validate_and_record_handback(task_id, raw_output)
            if validated.get("status") == "FAILED":
                breaker.record_failure()
            else:
                breaker.record_success()
                task_record["status"] = "COMPLETED"
                _atomic_write_json(task_path, task_record)
            return validated
        except Exception as exc:
            breaker.record_failure()
            return {
                "status": "FAILED",
                "reason": str(exc),
                "idempotency_key": task_id,
            }
        finally:
            self.semaphore.release()

    def validate_and_record_handback(self, task_id: str, handback_json_str: str) -> Dict[str, Any]:
        cleaned = handback_json_str.strip()
        if cleaned.startswith("```"):
            lines = [ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        payload: Dict[str, Any] = json.loads(cleaned)
        missing = REQUIRED_HANDBACK_KEYS - set(payload.keys())
        if missing:
            raise ValueError(f"Subagent hand-back missing required keys: {sorted(missing)}")
        if payload["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {payload['status']}")

        summary_words = len(str(payload.get("summary_for_orchestrator", "")).split())
        if summary_words > 250:
            raise ValueError(f"Summary exceeds 250-word limit ({summary_words} words)")

        # Gap 4: Deterministic BFT provenance verification
        validate_handback_semantics(self.repo_root, payload)

        result_path = self.state_dir / f"{task_id}.result.json"
        raw_res = _atomic_write_json(result_path, payload)

        telemetry_entry = {
            "task_id": task_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "status": payload["status"],
            "scope_count": len(payload.get("scope_reviewed", [])),
            "findings_count": len(payload.get("verified_findings", [])),
            "summary_words": summary_words,
            "result_sha256": f"sha256:{hashlib.sha256(raw_res).hexdigest()}",
        }
        ledger_path = self.state_dir / "subagent_observability.jsonl"
        lfd = os.open(str(ledger_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(lfd, (json.dumps(telemetry_entry, sort_keys=True) + "\n").encode("utf-8"))
            os.fsync(lfd)
        finally:
            os.close(lfd)
        return payload

    @staticmethod
    def resolve_consensus(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Gap 5: 2-of-3 quorum consensus over canonicalized findings; latches INDETERMINATE on split."""
        if not results:
            return {"status": "INDETERMINATE", "reason": "empty_results"}
        canonical_map: Dict[str, Dict[str, Any]] = {}
        counts: Counter[str] = Counter()
        for r in results:
            key = hashlib.sha256(encode_jcs(r.get("verified_findings", []))).hexdigest()
            canonical_map[key] = r
            counts[key] += 1

        top_key, top_count = counts.most_common(1)[0]
        quorum = (len(results) // 2) + 1
        if top_count >= quorum:
            winner = dict(canonical_map[top_key])
            winner["consensus_quorum"] = f"{top_count}/{len(results)}"
            return winner

        return {
            "status": "INDETERMINATE",
            "reason": "NO_CONSENSUS_QUORUM",
            "conflicting_results": results,
        }


# -----------------------------------------------------------------------------
# Backwards-Compatible Functional API for Existing Scripts & Tests
# -----------------------------------------------------------------------------

def check_disjoint_write_sets(workstreams: Dict[str, List[str]]) -> List[str]:
    """Returns a list of conflicting file paths/globs across parallel workstreams."""
    seen: Dict[str, str] = {}
    conflicts: List[str] = []

    for ws_name, globs in workstreams.items():
        for g in globs:
            norm_g = g.rstrip("/")
            if norm_g in seen:
                conflicts.append(f"Write collision on '{g}' between {seen[norm_g]} and {ws_name}")
            else:
                for existing_g, existing_owner in seen.items():
                    if norm_g.startswith(existing_g.rstrip("*")) or existing_g.startswith(norm_g.rstrip("*")):
                        conflicts.append(
                            f"Write overlap between '{existing_g}' ({existing_owner}) and '{g}' ({ws_name})"
                        )
                seen[norm_g] = ws_name

    return conflicts


def persist_durable_task(
    state_dir: Path,
    task_id: str,
    spec: Dict[str, Any],
) -> Path:
    """Writes task intent to disk with fsync before spawning a subagent."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    task_path = state_dir / f"{task_id}.task.json"
    spec_caid = f"sha256:{hashlib.sha256(encode_jcs(spec)).hexdigest()}"

    persisted_spec = dict(spec)
    persisted_spec["task_id"] = task_id
    persisted_spec["spec_caid"] = spec_caid
    persisted_spec["status"] = "DISPATCHED"
    persisted_spec["dispatched_at"] = datetime.now(timezone.utc).isoformat()

    _atomic_write_json(task_path, persisted_spec)
    return task_path


def validate_and_record_handback(
    state_dir: Path,
    task_id: str,
    handback_json_str: str,
    repo_root: Path = Path("."),
    verify_semantic_evidence: bool = False,
) -> Dict[str, Any]:
    """Functional wrapper for validate_and_record_handback."""
    coord = HardenedSubagentCoordinator(state_dir=state_dir, repo_root=repo_root)
    if verify_semantic_evidence:
        return coord.validate_and_record_handback(task_id, handback_json_str)

    # If verify_semantic_evidence is False, do standard schema validation without provenance check
    cleaned = handback_json_str.strip()
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    payload: Dict[str, Any] = json.loads(cleaned)
    missing = REQUIRED_HANDBACK_KEYS - set(payload.keys())
    if missing:
        raise ValueError(f"Subagent hand-back missing required keys: {sorted(missing)}")
    if payload["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {payload['status']}")

    summary_words = len(str(payload.get("summary_for_orchestrator", "")).split())
    if summary_words > 250:
        raise ValueError(f"Summary exceeds 250-word limit ({summary_words} words)")

    result_path = Path(state_dir) / f"{task_id}.result.json"
    raw_res = _atomic_write_json(result_path, payload)

    telemetry_entry = {
        "task_id": task_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": payload["status"],
        "scope_count": len(payload.get("scope_reviewed", [])),
        "findings_count": len(payload.get("verified_findings", [])),
        "summary_words": summary_words,
        "result_sha256": f"sha256:{hashlib.sha256(raw_res).hexdigest()}",
    }
    ledger_path = Path(state_dir) / "subagent_observability.jsonl"
    lfd = os.open(str(ledger_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(lfd, (json.dumps(telemetry_entry, sort_keys=True) + "\n").encode("utf-8"))
        os.fsync(lfd)
    finally:
        os.close(lfd)
    return telemetry_entry


def load_task_state(state_dir: Path, task_id: str) -> Dict[str, Any]:
    """Loads a durable task specification and its result if available."""
    state_dir = Path(state_dir)
    task_path = state_dir / f"{task_id}.task.json"
    result_path = state_dir / f"{task_id}.result.json"

    if not task_path.exists():
        raise FileNotFoundError(f"Task spec not found for task_id '{task_id}'")

    task_spec = json.loads(task_path.read_text(encoding="utf-8"))
    result_data = None
    if result_path.exists():
        result_data = json.loads(result_path.read_text(encoding="utf-8"))

    return {
        "task_id": task_id,
        "task_spec": task_spec,
        "result": result_data,
        "is_completed": result_data is not None,
    }


def evaluate_consensus(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Functional alias for consensus resolution."""
    return HardenedSubagentCoordinator.resolve_consensus(results)
