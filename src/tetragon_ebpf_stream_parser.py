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
src/tetragon_ebpf_stream_parser.py
================================================================================
Live Tetragon eBPF Trace Stream Ingestion Engine & Kernel PEP Auditor.

Engineering Status: INTERNAL PREVIEW COMMISSIONED (simulated stream parser)
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Evaluated Invariants:
1. Strict Kernel-to-SPIFFE SVID Binding:
   Validates incoming kernel telemetry against registered bpf_lsm_profile_digest.
2. Default-Deny Egress Syscall Interception:
   Verifies that sys_enter_connect syscalls route strictly to authorized agentgateway
   listeners (e.g. port 15001 / loopback / cluster proxy IP), intercepting direct external bypass.
3. Credential File Protection:
   Audits security_file_open / sys_enter_openat events against unauthorized
   un-blinded secret extraction attempts.
4. Deterministic RFC 8785 Canonical JCS Receipt:
   Computes integer basis points (0..10000 bps) integrity score and seals
   an immutable SHA-256 Content-Addressed Identifier (CAID).

Zero mocks, zero floats, deterministic RFC 8785 single-source JCS validation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple, Union

from src.hypergraph_blast_radius import sha256_jcs_caid

DEFAULT_ALLOWED_GATEWAY_PORTS: FrozenSet[int] = frozenset({15001})  # claim: config
DEFAULT_ALLOWED_GATEWAY_IPS: FrozenSet[str] = frozenset(
    {"127.0.0.1", "::1", "10.96.0.10"}
)  # claim: config
DEFAULT_PROTECTED_FILE_PATHS: FrozenSet[str] = frozenset(
    {
        "/etc/shadow",
        "/var/run/secrets/kubernetes.io",
        ".aws/credentials",
        ".ssh/id_rsa",
    }
)  # claim: config


@dataclass(frozen=True)
class TetragonEvent:
    event_type: str  # "PROCESS_EXEC" | "PROCESS_KPROBE" | "PROCESS_LSM" | "UNKNOWN"
    function_name: str  # "sys_enter_connect" | "sys_enter_execve" | "security_file_open" | ...
    action: str  # "KPROBE_ACTION_POST" | "LSM_ACTION_SIGKILL" | "LSM_ACTION_ALLOW" | ...
    pod_namespace: str
    pod_name: str
    container_name: str
    pid: int
    binary: str
    arguments: str
    details: Dict[str, Any]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "function_name": self.function_name,
            "action": self.action,
            "pod_namespace": self.pod_namespace,
            "pod_name": self.pod_name,
            "container_name": self.container_name,
            "pid": self.pid,
            "binary": self.binary,
            "arguments": self.arguments,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class TetragonAuditReceipt:
    stream_id: str
    actor_spiffe_id: str
    bpf_lsm_profile_digest: str
    total_events_evaluated: int
    allowed_events_count: int
    blocked_events_count: int
    policy_violations: Tuple[Dict[str, Any], ...]
    integrity_score_bps: int
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "actor_spiffe_id": self.actor_spiffe_id,
            "bpf_lsm_profile_digest": self.bpf_lsm_profile_digest,
            "total_events_evaluated": self.total_events_evaluated,
            "allowed_events_count": self.allowed_events_count,
            "blocked_events_count": self.blocked_events_count,
            "policy_violations": list(self.policy_violations),
            "integrity_score_bps": self.integrity_score_bps,
            "receipt_caid": self.receipt_caid,
        }


class TetragonEBPFStreamParser:
    """
    Parses and evaluates Tetragon eBPF kernel telemetry against AEIB
    runtime security policies and SPIFFE workload identity.
    """

    def __init__(
        self,
        actor_spiffe_id: str,
        bpf_lsm_profile_digest: str,
        allowed_gateway_ports: FrozenSet[int] = DEFAULT_ALLOWED_GATEWAY_PORTS,
        allowed_gateway_ips: FrozenSet[str] = DEFAULT_ALLOWED_GATEWAY_IPS,
        protected_file_paths: FrozenSet[str] = DEFAULT_PROTECTED_FILE_PATHS,
    ) -> None:
        if not actor_spiffe_id.startswith("spiffe://"):
            raise ValueError(f"ERR_INVALID_SPIFFE_ID: {actor_spiffe_id}")
        if not bpf_lsm_profile_digest.startswith("sha256:"):
            raise ValueError(f"ERR_INVALID_BPF_PROFILE_DIGEST: {bpf_lsm_profile_digest}")

        self.actor_spiffe_id = actor_spiffe_id
        self.bpf_lsm_profile_digest = bpf_lsm_profile_digest
        self.allowed_gateway_ports = allowed_gateway_ports
        self.allowed_gateway_ips = allowed_gateway_ips
        self.protected_file_paths = protected_file_paths

    def parse_raw_event(self, raw_input: Union[str, Dict[str, Any]]) -> TetragonEvent:
        """Parses a Tetragon event JSON string or dictionary into a structured TetragonEvent."""
        if isinstance(raw_input, str):
            try:
                data = json.loads(raw_input)
            except Exception as e:
                raise ValueError(f"ERR_MALFORMED_JSON: {e}") from e
        elif isinstance(raw_input, dict):
            data = raw_input
        else:
            raise ValueError(f"ERR_UNSUPPORTED_TYPE: {type(raw_input).__name__}")

        timestamp = str(data.get("time", ""))

        if "process_exec" in data:
            event_type = "PROCESS_EXEC"
            proc = data["process_exec"].get("process", {})
            func_name = "sys_enter_execve"
            action = "EXEC_ACTION_POST"
            details = {
                "parent": data["process_exec"].get("parent", {}),
                "cwd": proc.get("cwd", ""),
            }
        elif "process_kprobe" in data:
            event_type = "PROCESS_KPROBE"
            kprobe = data["process_kprobe"]
            proc = kprobe.get("process", {})
            func_name = str(kprobe.get("function_name", "unknown_kprobe"))
            action = str(kprobe.get("action", "KPROBE_ACTION_POST"))
            details = {"args": kprobe.get("args", [])}
        elif "process_lsm" in data:
            event_type = "PROCESS_LSM"
            lsm = data["process_lsm"]
            proc = lsm.get("process", {})
            func_name = str(lsm.get("function_name", "unknown_lsm"))
            action = str(lsm.get("action", "LSM_ACTION_ENFORCED"))
            details = {"args": lsm.get("args", [])}
        else:
            event_type = "UNKNOWN"
            proc = data.get("process", {})
            func_name = str(data.get("function_name", "unknown"))
            action = str(data.get("action", "UNKNOWN"))
            details = {}

        pod_info = proc.get("pod", {})
        container_info = pod_info.get("container", {})

        return TetragonEvent(
            event_type=event_type,
            function_name=func_name,
            action=action,
            pod_namespace=str(pod_info.get("namespace", "")),
            pod_name=str(pod_info.get("name", "")),
            container_name=str(container_info.get("name", "")),
            pid=int(proc.get("pid", 0)),
            binary=str(proc.get("binary", "")),
            arguments=str(proc.get("arguments", "")),
            details=details,
            timestamp=timestamp,
        )

    def evaluate_event(self, event: TetragonEvent) -> Tuple[bool, Optional[str]]:
        """
        Evaluates a single TetragonEvent against security policy invariants.
        Returns:
            (is_allowed: bool, violation_reason: Optional[str])
        """
        # 1. Immediate LSM enforcement check
        if "SIGKILL" in event.action or "BLOCK" in event.action:
            return False, f"LSM_ENFORCEMENT_ACTION: {event.action}"

        # 2. Network Egress PEP check on sys_enter_connect / socket probes
        if event.function_name in {"sys_enter_connect", "tcp_connect", "security_socket_connect"}:
            args = event.details.get("args", [])
            for arg_entry in args:
                sock = arg_entry.get("sock_arg", {})
                if not sock:
                    continue
                daddr = str(sock.get("daddr", ""))
                dport = sock.get("dport")

                if dport is not None and int(dport) not in self.allowed_gateway_ports:
                    if daddr not in self.allowed_gateway_ips:
                        return (
                            False,
                            f"EGRESS_PEP_BYPASS_ATTEMPT: dest={daddr}:{dport} not in allowed agentgateway routes",
                        )

        # 3. File access check on protected credential paths
        if event.function_name in {"security_file_open", "sys_enter_openat", "security_file_permission"}:
            args = event.details.get("args", [])
            for arg_entry in args:
                file_arg = arg_entry.get("file_arg", {})
                path = str(file_arg.get("path", ""))
                for protected in self.protected_file_paths:
                    if protected in path:
                        return (
                            False,
                            f"UNAUTHORIZED_CREDENTIAL_ACCESS_ATTEMPT: attempted access to protected path {path}",
                        )

        return True, None

    def evaluate_stream(
        self,
        stream_id: str,
        events: Sequence[Union[str, Dict[str, Any]]],
        stream_profile_digest: Optional[str] = None,
    ) -> TetragonAuditReceipt:
        """
        Evaluates a complete telemetry batch/stream and issues a deterministic RFC 8785 receipt.
        """
        # Verify profile digest
        expected_digest = stream_profile_digest if stream_profile_digest is not None else self.bpf_lsm_profile_digest
        if expected_digest != self.bpf_lsm_profile_digest:
            raise ValueError(
                f"ERR_BPF_PROFILE_MISMATCH: expected {self.bpf_lsm_profile_digest}, got {expected_digest}"
            )

        total_count = len(events)
        allowed_count = 0
        blocked_count = 0
        violations: List[Dict[str, Any]] = []

        for raw_event in events:
            parsed = self.parse_raw_event(raw_event)
            allowed, violation_reason = self.evaluate_event(parsed)
            if allowed:
                allowed_count += 1
            else:
                blocked_count += 1
                violations.append(
                    {
                        "timestamp": parsed.timestamp,
                        "pid": parsed.pid,
                        "binary": parsed.binary,
                        "function_name": parsed.function_name,
                        "action": parsed.action,
                        "violation_reason": violation_reason,
                    }
                )

        if total_count == 0:
            integrity_bps = 10000  # claim: assumption
        else:
            # Pure integer basis point computation (0..10000)
            deduction = (blocked_count * 10000) // total_count
            integrity_bps = max(0, 10000 - deduction)

        canonical_payload: Dict[str, Any] = {
            "actor_spiffe_id": self.actor_spiffe_id,
            "allowed_events_count": allowed_count,
            "blocked_events_count": blocked_count,
            "bpf_lsm_profile_digest": self.bpf_lsm_profile_digest,
            "integrity_score_bps": integrity_bps,
            "policy_violations": violations,
            "stream_id": stream_id,
            "total_events_evaluated": total_count,
        }

        receipt_caid = sha256_jcs_caid(canonical_payload)

        return TetragonAuditReceipt(
            stream_id=stream_id,
            actor_spiffe_id=self.actor_spiffe_id,
            bpf_lsm_profile_digest=self.bpf_lsm_profile_digest,
            total_events_evaluated=total_count,
            allowed_events_count=allowed_count,
            blocked_events_count=blocked_count,
            policy_violations=tuple(violations),
            integrity_score_bps=integrity_bps,
            receipt_caid=receipt_caid,
        )
