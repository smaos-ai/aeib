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

r"""
test_process_trace_guard.py — Acceptance Test for Process-Oracle Guard (SINGED Defense / AT50)
Verifies detection and fail-closed blocking of functional counterfeits.
"""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.process_trace_guard import (
    ProcessTraceGuard,
    ProcessTrace,
    ProcessExecutionEvent,
    compute_process_trace_digest,
    FunctionalCounterfeitError,
)


class TestProcessTraceGuard:
    def setup_method(self):
        self.guard = ProcessTraceGuard(
            allowed_executables={"/usr/bin/python3", "/app/bin/runner"},
            allowed_socket_targets={"api.internal.bank.cz:443"},
        )

    def test_benign_trace_passes_inspection(self):
        trace = ProcessTrace(
            process_id=1024,
            executable_path="/usr/bin/python3",
            command_line="python3 script.py",
            events=[
                ProcessExecutionEvent(event_type="connect", target="api.internal.bank.cz:443"),
            ],
        )
        digest = self.guard.verify_or_halt(trace)
        assert digest.startswith("sha256:")

    def test_unauthorized_secondary_fork_fails_closed(self):
        # Functional counterfeit: benign answer produced, but forks curl to exfiltrate
        trace = ProcessTrace(
            process_id=1024,
            executable_path="/usr/bin/python3",
            command_line="python3 script.py",
            events=[
                ProcessExecutionEvent(event_type="connect", target="api.internal.bank.cz:443"),
                ProcessExecutionEvent(event_type="fork", target="/usr/bin/curl"),
            ],
        )
        with pytest.raises(FunctionalCounterfeitError) as exc_info:
            self.guard.verify_or_halt(trace)

        assert "SINGED_FUNCTIONAL_COUNTERFEIT_DETECTED" in str(exc_info.value)
        assert "Forbidden secondary subprocess" in str(exc_info.value)

    def test_forbidden_loopback_socket_fails_closed(self):
        trace = ProcessTrace(
            process_id=1024,
            executable_path="/usr/bin/python3",
            command_line="python3 script.py",
            events=[
                ProcessExecutionEvent(event_type="connect", target="127.0.0.1:9090"),
            ],
        )
        with pytest.raises(FunctionalCounterfeitError) as exc_info:
            self.guard.verify_or_halt(trace)

        assert "Forbidden network socket connection" in str(exc_info.value)

    def test_unauthorized_primary_binary_fails_closed(self):
        trace = ProcessTrace(
            process_id=2048,
            executable_path="/usr/bin/bash",
            command_line="bash script.sh",
            events=[],
        )
        with pytest.raises(FunctionalCounterfeitError) as exc_info:
            self.guard.verify_or_halt(trace)
        assert "Unauthorized executable binary" in str(exc_info.value)

    def test_unauthorized_secondary_execve_fails_closed(self):
        trace = ProcessTrace(
            process_id=1024,
            executable_path="/usr/bin/python3",
            command_line="python3 script.py",
            events=[
                ProcessExecutionEvent(event_type="execve", target="/bin/sh"),
            ],
        )
        with pytest.raises(FunctionalCounterfeitError) as exc_info:
            self.guard.verify_or_halt(trace)
        assert "Forbidden secondary subprocess fork: /bin/sh" in str(exc_info.value)

    def test_defaults_and_event_serialization(self):
        # 1. ProcessTraceGuard defaults
        default_guard = ProcessTraceGuard()
        assert "/usr/bin/python3" in default_guard.allowed_executables
        assert "/usr/local/bin/smaos" in default_guard.allowed_executables
        assert "api.internal.bank.cz:443" in default_guard.allowed_socket_targets

        # 2. ProcessExecutionEvent defaults and to_dict
        ev_default = ProcessExecutionEvent("fork", "/usr/bin/python3")
        assert ev_default.timestamp_ns == 0
        assert ev_default.to_dict() == {
            "event_type": "fork",
            "target": "/usr/bin/python3",
            "timestamp_ns": 0,
        }

        # 3. Custom FunctionalCounterfeitError code and detail
        err = FunctionalCounterfeitError("custom detail", violation_type="CUSTOM_VIOLATION")
        assert err.code == "CUSTOM_VIOLATION"
        assert err.detail == "custom detail"

    def test_to_canonical_dict_sorting_invariance(self):
        ev1 = ProcessExecutionEvent(event_type="fork", target="/usr/bin/python3")
        ev2 = ProcessExecutionEvent(event_type="connect", target="api.internal.bank.cz:443")
        trace_unsorted = ProcessTrace(1, "/usr/bin/python3", "cmd", events=[ev1, ev2])
        d = trace_unsorted.to_canonical_dict()
        assert d["events"][0]["event_type"] == "connect"
        assert d["events"][1]["event_type"] == "fork"
