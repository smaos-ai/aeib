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
tests/test_macp_primitives.py
================================================================================
Comprehensive unit test suite for standalone macp package.
Covers Gaps 1-6 with zero external mock objects.
"""

import json
from pathlib import Path
import pytest

from macp.backpressure import BackpressureLimiter
from macp.bft import BFTProvenanceValidator, SemanticValidationError
from macp.consensus import QuorumConsensusResolver
from macp.coordinator import HardenedCoordinator
from macp.idempotency import IdempotentTaskDispatcher, encode_jcs
from macp.resilience import CircuitBreaker, HeartbeatLeaseTracker


def test_circuit_breaker_cooldown_and_tripping():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout_sec=1.0)
    assert not cb.is_open(now=100.0)

    # 1st failure: still closed
    tripped = cb.record_failure(now=100.0)
    assert not tripped
    assert not cb.is_open(now=100.5)

    # 2nd failure: trips open
    tripped = cb.record_failure(now=101.0)
    assert tripped
    assert cb.is_open(now=101.5)

    # Cooldown expires: resets closed
    assert not cb.is_open(now=102.5)

    # Success resets failure counter
    cb.record_failure(now=103.0)
    cb.record_success()
    assert cb.failures == 0


def test_heartbeat_lease_expiry():
    tracker = HeartbeatLeaseTracker(default_lease_sec=1.0)
    tracker.record_heartbeat("task-01", now=10.0)
    assert tracker.check_alive("task-01", now=10.5)
    assert not tracker.check_alive("task-01", now=11.5)
    assert not tracker.check_alive("unknown-task", now=10.5)


def test_idempotent_task_dispatch_and_collision(tmp_path: Path):
    dispatcher = IdempotentTaskDispatcher(state_dir=tmp_path)
    spec_a = {"task": "verify", "priority": 1}
    spec_b = {"task": "verify", "priority": 2}

    # First dispatch: reserves task
    is_cached, cached_val = dispatcher.check_or_reserve_task("task-100", "aeib-verifier", spec_a)
    assert is_cached is False
    assert cached_val is None

    # Record completed handback
    result_payload = {"status": "COMPLETED", "summary_for_orchestrator": "Done"}
    dispatcher.record_completed_result("task-100", result_payload)

    # Duplicate dispatch with identical spec: returns cached result
    is_cached_dup, cached_dup_val = dispatcher.check_or_reserve_task("task-100", "aeib-verifier", spec_a)
    assert is_cached_dup is True
    assert cached_dup_val["status"] == "COMPLETED"

    # Collision with mutated spec: raises ValueError
    with pytest.raises(ValueError, match="Idempotency key collision"):
        dispatcher.check_or_reserve_task("task-100", "aeib-verifier", spec_b)


def test_bft_provenance_validation(tmp_path: Path):
    sample_file = tmp_path / "evidence.txt"
    sample_file.write_text("line 1: authorized\nline 2: settled\nline 3: confirmed\n", encoding="utf-8")

    # Valid finding
    valid_finding = {
        "claim": "Transfer settled",
        "source": "evidence.txt:2",
        "anchor_token": "settled",
    }
    BFTProvenanceValidator.verify_finding(tmp_path, valid_finding)

    # Non-existent file
    with pytest.raises(SemanticValidationError, match="Fabricated source file does not exist"):
        BFTProvenanceValidator.verify_finding(tmp_path, {"claim": "X", "source": "ghost.txt:1"})

    # Out of range line
    with pytest.raises(SemanticValidationError, match="out of range"):
        BFTProvenanceValidator.verify_finding(tmp_path, {"claim": "X", "source": "evidence.txt:99"})

    # Missing anchor token
    with pytest.raises(SemanticValidationError, match="Anchor token 'unseen_token' not found"):
        BFTProvenanceValidator.verify_finding(
            tmp_path,
            {"claim": "X", "source": "evidence.txt:1", "anchor_token": "unseen_token"},
        )


def test_quorum_consensus_resolution():
    # 2-of-3 agreement
    f1 = [{"claim": "Pass", "source": "a.txt:1"}]
    f2 = [{"claim": "Fail", "source": "b.txt:1"}]
    r1 = {"status": "COMPLETED", "verified_findings": f1}
    r2 = {"status": "COMPLETED", "verified_findings": f1}
    r3 = {"status": "FAILED", "verified_findings": f2}

    resolved = QuorumConsensusResolver.resolve([r1, r2, r3])
    assert resolved["status"] == "COMPLETED"
    assert resolved["consensus_quorum"] == "2/3"

    # 3-way split tie
    r4 = {"status": "INDETERMINATE", "verified_findings": [{"claim": "Split", "source": "c.txt:1"}]}
    split = QuorumConsensusResolver.resolve([r1, r3, r4])
    assert split["status"] == "INDETERMINATE"
    assert split["reason"] == "NO_CONSENSUS_QUORUM"


def test_backpressure_and_fsync_ledger(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    limiter = BackpressureLimiter(max_concurrent=2, ledger_path=ledger)

    with limiter.throttle():
        rec = limiter.record_telemetry("task-01", "COMPLETED", "Done quickly", b'{"status":"COMPLETED"}')
        assert rec["task_id"] == "task-01"
        assert rec["status"] == "COMPLETED"

    assert ledger.exists()
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["task_id"] == "task-01"
    assert parsed["result_sha256"].startswith("sha256:")


def test_full_coordinator_integration(tmp_path: Path):
    coord = HardenedCoordinator(state_dir=tmp_path, repo_root=tmp_path, max_concurrent=2)

    sample_doc = tmp_path / "guide.md"
    sample_doc.write_text("# Guide\nDistributed systems require explicit primitives.\n", encoding="utf-8")

    handback_json = json.dumps({
        "status": "COMPLETED",
        "scope_reviewed": [str(sample_doc)],
        "verified_findings": [
            {
                "claim": "Explicit primitives required",
                "source": f"{sample_doc.name}:2",
                "anchor_token": "primitives",
            }
        ],
        "not_established": [],
        "summary_for_orchestrator": "Observed guidance documentation.",
    })

    def mock_worker(task_id, spec):
        return handback_json

    # Test initial dispatch
    res = coord.dispatch_task("aeib-researcher", "task-guidance", {"doc": "guide"}, mock_worker)
    assert res["status"] == "COMPLETED"

    # Test duplicate dispatch returns cached without calling worker
    def fail_worker(task_id, spec):
        raise AssertionError("Worker must not be called on duplicate dispatch")

    cached_res = coord.dispatch_task("aeib-researcher", "task-guidance", {"doc": "guide"}, fail_worker)
    assert cached_res["status"] == "COMPLETED"
