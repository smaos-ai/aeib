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
process_trace_guard.py — Caller-Supplied Process-Trace Allowlist Validator (AT50)
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.4.1

Motivated by "Functional Counterfeits" described in the SINGED benchmark
(Sept 2026, 7,549 audited trials): situations where an agent yields byte-for-byte
correct task answers while executing unauthorized secondary actions along its
trajectory (unapproved loopback sockets, unvetted forks, background exfiltration).

Under the stated model:
  Valid(A) <=> Target_Commit_Confirmed AND NOT Forbidden_Side_Effects

Computes ProcessTraceDigest = SHA256(JCS(trace)) for binding into the Extended
CAID, and checks execve/fork/connect events against an explicit allowlist.

SCOPE (honest label, 2026-10-26 audit): this module VALIDATES a ``ProcessTrace``
object that the CALLER constructs and passes in. It has NO capture mechanism —
no kernel hooks, no eBPF, no ptrace/auditd/ETW integration — so it cannot detect
events that the caller omits or fabricates. It is not a kernel lineage guard;
its verdict is only as complete as the trace it is given.
"""

import hashlib
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass, field

try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs


class FunctionalCounterfeitError(RuntimeError):
    """Raised when an agent executes unauthorized side-effects along its trajectory."""
    def __init__(self, detail: str, violation_type: str = "SINGED_FUNCTIONAL_COUNTERFEIT_DETECTED"):
        self.code = violation_type
        self.detail = detail
        super().__init__(f"{violation_type}: {detail}")


@dataclass
class ProcessExecutionEvent:
    event_type: str  # "execve", "connect", "fork"
    target: str      # binary path or "host:port"
    timestamp_ns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "target": self.target,
            "timestamp_ns": self.timestamp_ns,
        }


@dataclass
class ProcessTrace:
    process_id: int
    executable_path: str
    command_line: str
    events: List[ProcessExecutionEvent] = field(default_factory=list)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "executable_path": self.executable_path,
            "command_line": self.command_line,
            "events": [
                {
                    "event_type": ev.event_type,
                    "target": ev.target,
                }
                for ev in sorted(self.events, key=lambda e: (e.event_type, e.target))
            ],
        }


def compute_process_trace_digest(trace: ProcessTrace) -> str:
    """Computes deterministic SHA256(JCS(trace))."""
    canonical_bytes = encode_jcs(trace.to_canonical_dict())
    return f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"


class ProcessTraceGuard:
    """
    Allowlist validator for a caller-supplied ProcessTrace. Flags executables,
    forks and socket targets in the supplied trace that are not allowlisted.
    It does not observe the running system; omitted events are invisible to it.
    """

    def __init__(
        self,
        allowed_executables: Optional[Set[str]] = None,
        allowed_socket_targets: Optional[Set[str]] = None,
    ):
        self.allowed_executables = set(allowed_executables or {
            "/usr/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/smaos",
            "/app/bin/runner"
        })
        self.allowed_socket_targets = set(allowed_socket_targets or {
            "api.internal.bank.cz:443",
            "settlement.core.net:443"
        })

    def audit_trace(self, trace: ProcessTrace) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates the caller-supplied trace against approved boundaries.
        Returns (is_valid, disposition, telemetry). "TRACE_VERIFIED" means the
        supplied events matched the allowlist, not that the trace is complete.
        """
        digest = compute_process_trace_digest(trace)
        telemetry = {
            "trace_digest": digest,
            "executable": trace.executable_path,
            "event_count": len(trace.events),
            "violations": [],
        }

        # Check primary binary
        if trace.executable_path not in self.allowed_executables:
            msg = f"Unauthorized executable binary: {trace.executable_path}"
            telemetry["violations"].append(msg)
            return False, "SINGED_FUNCTIONAL_COUNTERFEIT_DETECTED", telemetry

        # Check secondary events
        for event in trace.events:
            if event.event_type in ("execve", "fork"):
                if event.target not in self.allowed_executables:
                    msg = f"Forbidden secondary subprocess fork: {event.target}"
                    telemetry["violations"].append(msg)
                    return False, "SINGED_FUNCTIONAL_COUNTERFEIT_DETECTED", telemetry
            elif event.event_type == "connect":
                if event.target not in self.allowed_socket_targets:
                    msg = f"Forbidden network socket connection: {event.target}"
                    telemetry["violations"].append(msg)
                    return False, "SINGED_FUNCTIONAL_COUNTERFEIT_DETECTED", telemetry

        return True, "TRACE_VERIFIED", telemetry

    def verify_or_halt(self, trace: ProcessTrace) -> str:
        """Enforces fail-closed halt if forbidden side effects are detected."""
        valid, disposition, telemetry = self.audit_trace(trace)
        if not valid:
            reasons = "; ".join(telemetry["violations"])
            raise FunctionalCounterfeitError(
                f"Execution failed process-oracle inspection: {reasons}",
                violation_type=disposition
            )
        return telemetry["trace_digest"]
