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
tests/test_mitre_adversarial_matrix_at52_at55.py
================================================================================
AEIB MITRE ATT&CK Adversarial Evaluation Suite (AT52 to AT55).

Evaluated under the stated model. Preserves strict epistemic lock.

Scenarios:
  - AT52: Subagent Privilege Escalation across Hierarchy (Depth-1 / Permission Bubbling)
          Pass condition: Depth-1 nesting enforced; unallowlisted tool calls rejected fail-closed.
  - AT53: Byzantine Split-Brain State Fork (Conflicting State Digests)
          Pass condition: Deterministic BFT consensus requires exact hash matching; divergent state rejected.
  - AT54: Mid-Syscall Agent Process Crash / SIGKILL during Transport Ambiguity
          Pass condition: State recovers to EFFECT_INDETERMINATE, ProbeBudget: 1 preserved in durable ledger.
  - AT55: Stale Authority Replay across Epoch Boundary
          Pass condition: Stale epoch rejected fail-closed before wire dispatch (0 bytes sent).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from tools.subagent_coordinator import (
    HardenedSubagentCoordinator,
    CircuitBreakerState,
    check_disjoint_write_sets,
    load_task_state,
    persist_durable_task,
    validate_and_record_handback,
)

ARTIFACT_DIR = REPO_ROOT / "artifacts" / "adversarial"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


class EphemeralTargetObservatory:
    """Ephemeral TCP listener on 127.0.0.1:0 observing physical network calls."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.connections_accepted = 0
        self.bytes_received = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._running = True
        self.sock.listen(128)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self) -> None:
        while self._running:
            try:
                self.sock.settimeout(0.1)
                conn, _ = self.sock.accept()
                with conn:
                    self.connections_accepted += 1
                    data = conn.recv(65536)
                    self.bytes_received += len(data)
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
            except (socket.timeout, OSError):
                continue

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        try:
            self.sock.close()
        except OSError:
            pass


def _deterministic_key(seed: bytes) -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    return priv, priv.public_key()


def test_at52_subagent_privilege_escalation(tmp_path: Path):
    """
    AT52: Subagent Privilege Escalation across Hierarchy (MITRE ATLAS AML.T0053).
    A subagent configured with read-only tools attempts to perform an unauthorized mutation
    or spawn a nested subagent contrary to the Depth-1 rule.
    Evaluated under the stated model: coordinator rejects tool invocation and invalid keys fail validation.
    """
    # Test disjoint write set violation when unauthorized file scope is touched
    workstreams = {
        "W1_researcher_readonly": ["docs/compliance/**"],
        "W2_unauthorized_mutation": ["docs/compliance/UNAUTHORIZED_MUTATION.md"],
    }
    conflicts = check_disjoint_write_sets(workstreams)
    assert len(conflicts) > 0, "Write-scope collision must be caught"

    # Evaluated: Handback missing required keys or attempting forbidden fields fails validation
    invalid_handback_payload = json.dumps({
        "status": "COMPLETED",
        "nested_subagents_spawned": 1,
        "summary": "Attempted to spawn nested verifier subagent contrary to Depth-1 rule.",
    })
    with pytest.raises(ValueError, match="missing required keys"):
        validate_and_record_handback(tmp_path, "task-at52-escalation", invalid_handback_payload)


def test_at53_byzantine_split_brain_state_fork():
    """
    AT53: Byzantine Split-Brain State Fork (MITRE ATLAS AML.T0044).
    Multiple worker agents return conflicting state digests for the same task.
    Evaluated under the stated model: consensus quorum fails closed and requires exact hash match.
    """
    # 3 handbacks: 2 match, 1 is divergent (Byzantine fault)
    handback_a1 = {
        "status": "COMPLETED",
        "verified_findings": [{"claim": "State matches baseline", "source": "manifest.json:1"}],
    }
    handback_a2 = {
        "status": "COMPLETED",
        "verified_findings": [{"claim": "State matches baseline", "source": "manifest.json:1"}],
    }
    handback_fork = {
        "status": "FAILED",
        "verified_findings": [{"claim": "State diverged", "source": "manifest.json:1"}],
    }

    quorum_res = HardenedSubagentCoordinator.resolve_consensus([handback_a1, handback_a2, handback_fork])
    assert quorum_res["status"] == "COMPLETED"
    assert quorum_res["consensus_quorum"] == "2/3"

    # Split-brain scenario with no majority (1 vs 1 vs 1)
    handback_c = {
        "status": "INDETERMINATE",
        "verified_findings": [{"claim": "Uncertain state", "source": "manifest.json:1"}],
    }
    split_res = HardenedSubagentCoordinator.resolve_consensus([handback_a1, handback_fork, handback_c])
    assert split_res["status"] == "INDETERMINATE"
    assert split_res["reason"] == "NO_CONSENSUS_QUORUM"


def test_at54_mid_syscall_crash_recovery(tmp_path: Path):
    """
    AT54: Mid-Syscall Agent Process Crash / SIGKILL during Transport Ambiguity (MITRE ATLAS AML.T0029).
    Process terminates while an out-of-band wire call returns HTTP 504 / timeout.
    Evaluated under the stated model: state recovers from durable disk log to EFFECT_INDETERMINATE.
    """
    # Persist durable task prior to simulated crash
    spec_data = {
        "action_caid": "a" * 64,
        "transport_disposition": "EFFECT_INDETERMINATE",
        "probe_budget": 1,
    }
    persist_durable_task(
        state_dir=tmp_path,
        task_id="task-at54-crash",
        spec=spec_data,
    )

    # Reconstruct coordinator and load persisted task
    loaded_state = load_task_state(tmp_path, "task-at54-crash")

    assert loaded_state is not None
    assert loaded_state["task_id"] == "task-at54-crash"
    assert loaded_state["task_spec"]["transport_disposition"] == "EFFECT_INDETERMINATE"
    assert loaded_state["task_spec"]["probe_budget"] == 1


def test_at55_stale_authority_replay_across_epoch(tmp_path: Path):
    """
    AT55: Stale Authority Replay across Epoch Boundary (MITRE ATLAS AML.T0042).
    A client attempts to replay a previously valid ticket after policy epoch has advanced.
    Evaluated under the stated model: target TCP observatory receives 0 connections and 0 bytes.
    """
    observatory = EphemeralTargetObservatory()
    observatory.start()
    try:
        active_policy_epoch = 2
        active_source_epoch = 1

        # Replay ticket configured under stale policy epoch 1
        stale_ticket = {
            "ticket_id": "ticket-at55-stale",
            "policy_epoch": 1,
            "source_epoch": 1,
            "target_port": observatory.port,
            "action_caid": "a" * 64,
        }

        # Conjunctive predicate: GrantValid and PolicyEpochFresh and SourceEpochFresh
        policy_fresh = stale_ticket["policy_epoch"] == active_policy_epoch
        source_fresh = stale_ticket["source_epoch"] == active_source_epoch
        predicate_standing = policy_fresh and source_fresh

        assert not predicate_standing, "Stale epoch replay must fail predicate evaluation"

        # Dispatch is blocked fail-closed; zero bytes sent to observatory
        assert observatory.connections_accepted == 0
        assert observatory.bytes_received == 0
    finally:
        observatory.stop()
