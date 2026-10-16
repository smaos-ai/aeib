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
Deterministic coordinator for Antigravity IDE subagents:
1. Checks disjoint file write-sets before spawning (Conflict Gate).
2. Persists task spec to disk with fsync before execution (Durable Workflow).
3. Validates bounded JSON hand-back contracts and logs telemetry.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

REQUIRED_HANDBACK_KEYS = {
    "status",
    "scope_reviewed",
    "verified_findings",
    "not_established",
    "summary_for_orchestrator",
}

VALID_STATUSES = {"COMPLETED", "INDETERMINATE", "FAILED"}


def check_disjoint_write_sets(workstreams: Dict[str, List[str]]) -> List[str]:
    """Returns a list of conflicting file paths/globs across parallel workstreams."""
    seen: Dict[str, str] = {}
    conflicts: List[str] = []

    for ws_name, globs in workstreams.items():
        for g in globs:
            # Normalize trailing slashes
            norm_g = g.rstrip("/")
            if norm_g in seen:
                conflicts.append(f"Write collision on '{g}' between {seen[norm_g]} and {ws_name}")
            else:
                # Check for prefix containment (e.g. docs/** vs docs/compliance/**)
                for existing_g, existing_owner in seen.items():
                    if norm_g.startswith(existing_g.rstrip("*")) or existing_g.startswith(norm_g.rstrip("*")):
                        conflicts.append(
                            f"Write overlap between '{existing_g}' ({existing_owner}) and '{g}' ({ws_name})"
                        )
                seen[norm_g] = ws_name

    return conflicts


def persist_durable_task(state_dir: Path, task_id: str, spec: Dict[str, Any]) -> Path:
    """Writes task intent to disk with fsync before spawning a subagent."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    task_path = state_dir / f"{task_id}.task.json"
    raw = json.dumps(spec, sort_keys=True, indent=2).encode("utf-8")

    fd = os.open(str(task_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)

    return task_path


def validate_and_record_handback(
    state_dir: Path,
    task_id: str,
    handback_json_str: str,
) -> Dict[str, Any]:
    """Validates subagent JSON output against the frozen hand-back contract."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    cleaned = handback_json_str.strip()
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        payload: Dict[str, Any] = json.loads(cleaned)
    except Exception as exc:
        raise ValueError(f"Failed to parse subagent hand-back as JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Subagent hand-back must be a JSON object, got {type(payload).__name__}")

    missing = REQUIRED_HANDBACK_KEYS - set(payload.keys())
    if missing:
        raise ValueError(f"Subagent hand-back missing required keys: {sorted(missing)}")

    status = payload.get("status")
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: '{status}'. Expected one of {sorted(VALID_STATUSES)}")

    if not isinstance(payload.get("scope_reviewed"), list):
        raise ValueError("Field 'scope_reviewed' must be a list of file paths or URLs")

    if not isinstance(payload.get("verified_findings"), list):
        raise ValueError("Field 'verified_findings' must be a list of finding objects")

    if not isinstance(payload.get("not_established"), list):
        raise ValueError("Field 'not_established' must be a list of unproven claims or gaps")

    summary_text = str(payload.get("summary_for_orchestrator", "")).strip()
    summary_words = len(summary_text.split())
    if summary_words > 250:
        raise ValueError(f"Summary exceeds 250-word limit ({summary_words} words)")

    # Write durable result with fsync
    result_path = state_dir / f"{task_id}.result.json"
    raw_res = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")

    fd = os.open(str(result_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, raw_res)
        os.fsync(fd)
    finally:
        os.close(fd)

    telemetry_entry = {
        "task_id": task_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scope_count": len(payload.get("scope_reviewed", [])),
        "findings_count": len(payload.get("verified_findings", [])),
        "summary_words": summary_words,
        "result_sha256": f"sha256:{hashlib.sha256(raw_res).hexdigest()}",
    }

    ledger_path = state_dir / "subagent_observability.jsonl"
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


if __name__ == "__main__":
    # Self-test CLI mode
    tmp = Path("artifacts/subagent_runtime")
    tmp.mkdir(parents=True, exist_ok=True)

    conflicts = check_disjoint_write_sets(
        {"W1": ["docs/compliance/a.md"], "W2": ["docs/security/b.md"]}
    )
    assert not conflicts, f"Unexpected conflicts: {conflicts}"

    persist_durable_task(tmp, "task-001", {"agent": "aeib-researcher", "depth": 1})

    sample_out = json.dumps({
        "status": "COMPLETED",
        "scope_reviewed": ["docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md"],
        "verified_findings": [
            {
                "claim": "EN 18286 approved in July 2026 under CEN/CLC/JTC 21",
                "source": "docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md:1",
                "date": "2026-10-16",
            }
        ],
        "not_established": [],
        "summary_for_orchestrator": "Verified EN 18286 regulatory crosswalk and zero banned words.",
    })

    rec = validate_and_record_handback(tmp, "task-001", sample_out)
    print(f"[OK] VALIDATED_SUBAGENT_RECEIPT: {json.dumps(rec)}")
