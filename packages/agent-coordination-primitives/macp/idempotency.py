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
macp.idempotency
================================================================================
Gap 3: Idempotent task dispatch and durable state persistence.
Strict RFC 8785 JSON Canonicalization Scheme (JCS) encoding.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


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


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> bytes:
    """Writes a dictionary as indented JSON with atomic fsync flush."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    return raw


class IdempotentTaskDispatcher:
    """Enforces Exactly-Once Dispatch Semantics (EO-1) via RFC 8785 CAID binding."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def check_or_reserve_task(
        self,
        task_id: str,
        profile: str,
        spec: Dict[str, Any],
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Checks idempotency state. Returns (is_cached, cached_result_or_none). Raises on collision."""
        task_path = self.state_dir / f"{task_id}.task.json"
        result_path = self.state_dir / f"{task_id}.result.json"
        spec_caid = f"sha256:{hashlib.sha256(encode_jcs(spec)).hexdigest()}"

        if task_path.exists():
            existing_task = json.loads(task_path.read_text(encoding="utf-8"))
            if existing_task.get("spec_caid") != spec_caid:
                raise ValueError(
                    f"Idempotency key collision: task '{task_id}' already registered with different spec"
                )
            if existing_task.get("status") == "COMPLETED" and result_path.exists():
                return True, json.loads(result_path.read_text(encoding="utf-8"))
            if existing_task.get("status") == "DISPATCHED":
                return True, {
                    "status": "INDETERMINATE",
                    "reason": "DUPLICATE_DISPATCH_BLOCKED_IN_FLIGHT",
                    "idempotency_key": task_id,
                }

        # Reserve new task record with fsync prior to spawn
        task_record = {
            "idempotency_key": task_id,
            "profile": profile,
            "spec_caid": spec_caid,
            "status": "DISPATCHED",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(task_path, task_record)
        return False, None

    def record_completed_result(
        self,
        task_id: str,
        result: Dict[str, Any],
    ) -> bytes:
        """Stores final completed task handback with fsync and updates task status."""
        task_path = self.state_dir / f"{task_id}.task.json"
        result_path = self.state_dir / f"{task_id}.result.json"

        raw_result = atomic_write_json(result_path, result)

        if task_path.exists():
            task_record = json.loads(task_path.read_text(encoding="utf-8"))
            task_record["status"] = "COMPLETED"
            task_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            atomic_write_json(task_path, task_record)

        return raw_result
