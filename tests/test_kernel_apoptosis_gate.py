#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tests/test_kernel_apoptosis_gate.py
================================================================================
Pytest Falsification Suite for `src/kernel_apoptosis_gate.py` (D2).

Evaluated under the stated model:
Proves that the Homeostatic Membrane triggers Digital Apoptosis on unauthorized
syscalls, blocking unauthorized lateral movement and file writes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.kernel_apoptosis_gate import (
    AgentProcessContext,
    HaltKernelInvariantViolation,
    HomeostaticMembrane,
)


def test_1_allowed_loopback_network_egress() -> None:
    membrane = HomeostaticMembrane()
    ctx = AgentProcessContext(
        pid=1001,
        worktree_path="/tmp/agent_1",
        allowed_network_domains={"127.0.0.1"},
        allowed_file_paths={"/tmp/agent_1"},
    )
    membrane.register_agent(ctx)
    # Loopback network socket connect succeeds
    membrane.simulate_syscall_socket_connect(1001, "127.0.0.1")
    assert len(membrane.apoptosis_log) == 0

    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.pid = 9999  # type: ignore


def test_2_blocked_external_network_triggers_apoptosis() -> None:
    membrane = HomeostaticMembrane()
    ctx = AgentProcessContext(
        pid=1002,
        worktree_path="/tmp/agent_2",
        allowed_network_domains={"127.0.0.1"},
        allowed_file_paths={"/tmp/agent_2"},
    )
    membrane.register_agent(ctx)
    with pytest.raises(HaltKernelInvariantViolation, match="BLOCKED_EGRESS:8.8.8.8"):
        membrane.simulate_syscall_socket_connect(1002, "8.8.8.8")

    assert len(membrane.apoptosis_log) == 1
    assert membrane.apoptosis_log[0]["action"] == "SIGKILL"
    assert membrane.apoptosis_log[0]["pid"] == 1002


def test_3_blocked_file_write_outside_worktree() -> None:
    membrane = HomeostaticMembrane()
    ctx = AgentProcessContext(
        pid=1003,
        worktree_path="/tmp/agent_3",
        allowed_network_domains={"127.0.0.1"},
        allowed_file_paths={"/tmp/agent_3"},
    )
    membrane.register_agent(ctx)

    # Allowed write inside worktree
    membrane.simulate_syscall_file_open(1003, "/tmp/agent_3/output.json", "w")
    assert len(membrane.apoptosis_log) == 0

    # Blocked write outside worktree
    with pytest.raises(HaltKernelInvariantViolation, match="BLOCKED_WRITE:/etc/passwd"):
        membrane.simulate_syscall_file_open(1003, "/etc/passwd", "w")

    assert len(membrane.apoptosis_log) == 1
    assert membrane.apoptosis_log[0]["action"] == "SIGKILL"


def test_4_unregistered_process_rejection() -> None:
    membrane = HomeostaticMembrane()
    with pytest.raises(HaltKernelInvariantViolation, match="HALT_UNREGISTERED_PROCESS_SYSCALL"):
        membrane.simulate_syscall_socket_connect(9999, "127.0.0.1")

    with pytest.raises(HaltKernelInvariantViolation, match="HALT_UNREGISTERED_PROCESS_SYSCALL"):
        membrane.simulate_syscall_file_open(9999, "/tmp/test", "w")


def test_5_ebpf_and_tetragon_artifacts_exist() -> None:
    membrane = HomeostaticMembrane()
    ebpf_code = membrane.get_ebpf_c_code()
    tetragon_policy = membrane.get_tetragon_policy()

    assert "lsm/socket_connect" in ebpf_code
    assert "lsm/file_open" in ebpf_code
    assert "Sigkill" in tetragon_policy
    assert "kernelStackTrace: true" in tetragon_policy


def test_6_epistemic_linguistic_compliance() -> None:
    src_file = Path("src/kernel_apoptosis_gate.py")
    test_file = Path("tests/test_kernel_apoptosis_gate.py")
    banned_patterns = [
        r"\bguaran(?:tee|teed|tees|teeing)\b",
        r"\bproven\s+universally\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100%\s+secure\b",
        r"\bunassailable\b",
        r"\bimmune\b",
        r"\bunhackable\b",
        r"\bbank-grade\b",
        r"\bproduction-ready\b",
    ]

    for fpath in (src_file, test_file):
        text = fpath.read_text(encoding="utf-8")
        for pat in banned_patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            assert len(matches) == 0, f"Banned pattern '{pat}' found in {fpath}: {matches}"
