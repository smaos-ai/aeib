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
tests/test_ebpf_lsm_agent_guard.py
================================================================================
Verification suite for eBPF LSM Agent Guard Controller.
Evaluated under the stated model as an agent execution boundary scaffold.
"""

import os
import subprocess
import sys
import tempfile
import pytest

from src.ebpf_agent_guard_controller import (
    EbpfAgentGuardController,
    PROT_READ,
    PROT_WRITE,
    PROT_EXEC,
)


def test_ebpf_lsm_bprm_allowlisting_and_rejection():
    ctrl = EbpfAgentGuardController()
    ctrl.register_allowed_binary("python_bin", sys.executable)

    # Allowed binary executes cleanly
    ok, reason, evt = ctrl.attest_binary_execution(sys.executable)
    assert ok is True
    assert reason == "ALLOW_EXECUTION"
    assert evt is None

    # Unregistered binary fails closed with EPERM
    unauth_bin = "/opt/unauthorized_agent_exploit_bin"
    ok, reason, evt = ctrl.attest_binary_execution(unauth_bin)
    assert ok is False
    assert reason == "DENY_UNAUTHORIZED_BINARY"
    assert evt is not None
    assert evt.verdict == "DENY"


def test_ebpf_lsm_model_weight_attestation_and_tampering(tmp_path):
    ctrl = EbpfAgentGuardController()

    weight_file = tmp_path / "model.gguf"
    weight_file.write_bytes(b"GGUF_VALID_MODEL_WEIGHTS_42_BYTES_PADDING")

    # Register genuine weight digest
    manifest = ctrl.register_model_weight(
        model_name="test-llm",
        file_path=str(weight_file),
        expected_sha256="fake_initial",
    )
    # Update expected to actual sha256
    import hashlib
    actual_hash = hashlib.sha256(weight_file.read_bytes()).hexdigest()
    manifest.expected_sha256 = actual_hash

    # 1. Nominal mmap: passes
    ok, reason, _ = ctrl.attest_model_weight_mmap(str(weight_file), prot_flags=PROT_READ)
    assert ok is True
    assert reason == "ALLOW_WEIGHT_MMAP"

    # 2. Tampered file: fails closed
    weight_file.write_bytes(b"GGUF_TAMPERED_BACKDOORED_WEIGHTS_OFFSET")
    ok, reason, evt = ctrl.attest_model_weight_mmap(str(weight_file), prot_flags=PROT_READ)
    assert ok is False
    assert reason == "DENY_WEIGHT_TAMPERING_DETECTED"
    assert evt.verdict == "DENY"


def test_ebpf_lsm_wx_violation_and_mprotect_escalation():
    ctrl = EbpfAgentGuardController()

    # W^X violation on mmap: write and exec together is denied
    ok, reason, evt = ctrl.attest_model_weight_mmap(
        "model.safetensors", prot_flags=PROT_WRITE | PROT_EXEC
    )
    assert ok is False
    assert reason == "DENY_WX_VIOLATION"

    # Dynamic promotion to PROT_EXEC is denied
    ok, reason, evt = ctrl.attest_memory_protection_escalation("anon_tensor_page", PROT_EXEC)
    assert ok is False
    assert reason == "DENY_PROT_EXEC_VIOLATION"


def test_ebpf_lsm_socket_connect_taint_isolation():
    ctrl = EbpfAgentGuardController()

    # Trusted process: allowed
    ok, reason, _ = ctrl.attest_socket_connect("10.0.0.1", 443, taint_tier=0)
    assert ok is True

    # Untrusted external process: blocked fail-closed (ENETUNREACH)
    ok, reason, evt = ctrl.attest_socket_connect("198.51.100.1", 443, taint_tier=2)
    assert ok is False
    assert reason == "DENY_TAINTED_EGRESS_BLOCKED"
    assert evt.verdict == "DENY"


def test_ebpf_lsm_controller_cli_self_test():
    proc = subprocess.run(
        [sys.executable, "src/ebpf_agent_guard_controller.py", "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Self-test passed" in proc.stdout
