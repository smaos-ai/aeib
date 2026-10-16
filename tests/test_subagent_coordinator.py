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
tests/test_subagent_coordinator.py
================================================================================
Comprehensive test suite for Antigravity subagent coordinator, disjoint conflict gate,
durable task persistence, and frozen JSON hand-back validation.
"""

import json
from pathlib import Path
import pytest

from tools.subagent_coordinator import (
    CircuitBreakerState,
    HardenedSubagentCoordinator,
    check_disjoint_write_sets,
    load_task_state,
    persist_durable_task,
    validate_and_record_handback,
)


def test_disjoint_write_sets_no_conflicts():
    workstreams = {
        "W1_regulatory": ["docs/compliance/**", "docs/commercial/**"],
        "W2_threat": ["docs/security/**", "docs/PEER_EXECUTIVE_BRIEFING.md"],
    }
    conflicts = check_disjoint_write_sets(workstreams)
    assert conflicts == []


def test_disjoint_write_sets_exact_collision():
    workstreams = {
        "W1_agent": ["src/module.py", "docs/a.md"],
        "W2_agent": ["src/module.py", "docs/b.md"],
    }
    conflicts = check_disjoint_write_sets(workstreams)
    assert len(conflicts) == 1
    assert "collision on 'src/module.py'" in conflicts[0]


def test_disjoint_write_sets_prefix_overlap():
    workstreams = {
        "W1_broad": ["docs/**"],
        "W2_narrow": ["docs/compliance/**"],
    }
    conflicts = check_disjoint_write_sets(workstreams)
    assert len(conflicts) == 1
    assert "overlap between" in conflicts[0]


def test_persist_durable_task(tmp_path: Path):
    task_id = "test-task-42"
    spec = {"agent": "aeib-verifier", "command": "zone_boundary"}
    task_path = persist_durable_task(tmp_path, task_id, spec)

    assert task_path.exists()
    assert task_path.name == f"{task_id}.task.json"
    loaded = json.loads(task_path.read_text(encoding="utf-8"))
    for k, v in spec.items():
        assert loaded[k] == v
    assert loaded["task_id"] == task_id
    assert loaded["status"] == "DISPATCHED"


def test_validate_and_record_handback_success(tmp_path: Path):
    task_id = "test-task-101"
    valid_handback = json.dumps({
        "status": "COMPLETED",
        "scope_reviewed": ["docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md"],
        "verified_findings": [
            {
                "claim": "EN 18286 provides presumption of conformity under Article 40",
                "source": "docs/compliance/EN_18286_AND_REGULATORY_APPLICABILITY_DOSSIER.md:15",
                "date": "2026-10-16",
            }
        ],
        "not_established": [],
        "summary_for_orchestrator": "Verified CEN-CENELEC EN 18286 regulatory crosswalk.",
    })

    telemetry = validate_and_record_handback(tmp_path, task_id, valid_handback)
    assert telemetry["task_id"] == task_id
    assert telemetry["status"] == "COMPLETED"
    assert telemetry["scope_count"] == 1
    assert telemetry["findings_count"] == 1

    # Verify result file written
    res_file = tmp_path / f"{task_id}.result.json"
    assert res_file.exists()

    # Verify telemetry ledger appended
    ledger_file = tmp_path / "subagent_observability.jsonl"
    assert ledger_file.exists()
    lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_validate_handback_strips_markdown_fences(tmp_path: Path):
    task_id = "test-task-fence"
    fenced_handback = """```json
{
  "status": "INDETERMINATE",
  "scope_reviewed": ["docs/gap.md"],
  "verified_findings": [],
  "not_established": ["external audit sign-off pending"],
  "summary_for_orchestrator": "Audit pending external confirmation."
}
```"""
    telemetry = validate_and_record_handback(tmp_path, task_id, fenced_handback)
    assert telemetry["status"] == "INDETERMINATE"


def test_validate_handback_missing_keys_raises(tmp_path: Path):
    task_id = "test-task-missing"
    bad_payload = json.dumps({"status": "COMPLETED"})
    with pytest.raises(ValueError, match="missing required keys"):
        validate_and_record_handback(tmp_path, task_id, bad_payload)


def test_validate_handback_invalid_status_raises(tmp_path: Path):
    task_id = "test-task-bad-status"
    bad_payload = json.dumps({
        "status": "UNKNOWN_STATUS",
        "scope_reviewed": [],
        "verified_findings": [],
        "not_established": [],
        "summary_for_orchestrator": "Test",
    })
    with pytest.raises(ValueError, match="Invalid status"):
        validate_and_record_handback(tmp_path, task_id, bad_payload)


def test_validate_handback_word_limit_exceeded_raises(tmp_path: Path):
    task_id = "test-task-wordy"
    verbose_summary = "word " * 251
    bad_payload = json.dumps({
        "status": "COMPLETED",
        "scope_reviewed": [],
        "verified_findings": [],
        "not_established": [],
        "summary_for_orchestrator": verbose_summary,
    })
    with pytest.raises(ValueError, match="Summary exceeds 250-word limit"):
        validate_and_record_handback(tmp_path, task_id, bad_payload)


def test_load_task_state(tmp_path: Path):
    task_id = "test-task-load"
    spec = {"agent": "aeib-researcher", "target": "DORA"}
    persist_durable_task(tmp_path, task_id, spec)

    state = load_task_state(tmp_path, task_id)
    assert state["task_id"] == task_id
    for k, v in spec.items():
        assert state["task_spec"][k] == v
    assert state["is_completed"] is False

    valid_handback = json.dumps({
        "status": "COMPLETED",
        "scope_reviewed": ["docs/DORA.md"],
        "verified_findings": [],
        "not_established": [],
        "summary_for_orchestrator": "Done",
    })
    validate_and_record_handback(tmp_path, task_id, valid_handback)

    updated_state = load_task_state(tmp_path, task_id)
    assert updated_state["is_completed"] is True
    assert updated_state["result"]["status"] == "COMPLETED"


def test_circuit_breaker_transitions():
    cb = CircuitBreakerState(failure_threshold=2, reset_timeout_sec=1.0)
    assert not cb.is_open(now=100.0)

    # 1st failure: still closed
    tripped = cb.record_failure(now=100.0)
    assert not tripped
    assert not cb.is_open(now=100.5)

    # 2nd failure: trips open
    tripped = cb.record_failure(now=101.0)
    assert tripped
    assert cb.is_open(now=101.5)

    # After cooldown: resets half-open/closed
    assert not cb.is_open(now=102.5)

    # Success resets counter
    cb.record_failure(now=103.0)
    cb.record_success()
    assert cb.failures == 0


def test_hardened_coordinator_idempotency_and_backpressure(tmp_path: Path):
    coord = HardenedSubagentCoordinator(state_dir=tmp_path, repo_root=Path("."), max_concurrent=2)

    valid_payload = json.dumps({
        "status": "COMPLETED",
        "scope_reviewed": ["ROADMAP.md"],
        "verified_findings": [{"claim": "Roadmap active", "source": "ROADMAP.md:1", "date": "2026-10-16"}],
        "not_established": [],
        "summary_for_orchestrator": "Verified roadmap.",
    })

    # Dispatch 1
    call_count = [0]
    def worker(tid, spec):
        call_count[0] += 1
        return valid_payload

    res1 = coord.dispatch_idempotent_task("aeib-researcher", "task-x", {"action": "check"}, worker)
    assert res1["status"] == "COMPLETED"
    assert call_count[0] == 1

    # Dispatch 2: exact same task_id & spec -> must return cached result without calling worker!
    res2 = coord.dispatch_idempotent_task("aeib-researcher", "task-x", {"action": "check"}, worker)
    assert res2["status"] == "COMPLETED"
    assert call_count[0] == 1, "Duplicate dispatch must not re-execute worker"


def test_semantic_validator_catches_hallucinations(tmp_path: Path):
    from tools.semantic_validator import SemanticValidationError, validate_handback_semantics

    # Non-existent file
    bad_handback = {
        "verified_findings": [{"claim": "Fabricated", "source": "non_existent_file.py:10"}],
    }
    with pytest.raises(SemanticValidationError, match="Fabricated source file does not exist"):
        validate_handback_semantics(tmp_path, bad_handback)

    # File exists but line out of range
    sample_file = tmp_path / "sample.py"
    sample_file.write_text("line1\nline2\n", encoding="utf-8")

    out_of_range_handback = {
        "verified_findings": [{"claim": "Line out of range", "source": "sample.py:99"}],
    }
    with pytest.raises(SemanticValidationError, match="out of range"):
        validate_handback_semantics(tmp_path, out_of_range_handback)

    # Valid file and line
    good_handback = {
        "verified_findings": [{"claim": "Found line1", "source": "sample.py:1"}],
    }
    assert validate_handback_semantics(tmp_path, good_handback) is True


def test_consensus_quorum_resolution():
    # 2-of-3 quorum consensus
    res_a1 = {"status": "COMPLETED", "verified_findings": [{"claim": "Approved", "source": "a.py:1"}]}
    res_a2 = {"status": "COMPLETED", "verified_findings": [{"claim": "Approved", "source": "a.py:1"}]}
    res_b = {"status": "FAILED", "verified_findings": [{"claim": "Rejected", "source": "a.py:1"}]}

    quorum_res = HardenedSubagentCoordinator.resolve_consensus([res_a1, res_a2, res_b])
    assert quorum_res["status"] == "COMPLETED"
    assert quorum_res["consensus_quorum"] == "2/3"

    # Conflicting split (1 vs 1 vs 1)
    res_c = {"status": "INDETERMINATE", "verified_findings": [{"claim": "Unknown", "source": "a.py:1"}]}
    split_res = HardenedSubagentCoordinator.resolve_consensus([res_a1, res_b, res_c])
    assert split_res["status"] == "INDETERMINATE"
    assert split_res["reason"] == "NO_CONSENSUS_QUORUM"

