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
src/ebpf_agent_guard_controller.py
================================================================================
eBPF LSM Inode & Model Weight Attestation Controller.
Evaluated under the stated model as an agent execution boundary scaffold.

Provides boundary control for:
  1. Process binary execution allowlisting via inode and SHA-256 digests (bprm_check_security).
  2. Model weight (.safetensors / .gguf) attestation against signed manifests before mmap.
  3. Strict W^X memory protection enforcement (denying simultaneous PROT_WRITE | PROT_EXEC).
  4. Dynamic memory protection escalation prevention (file_mprotect PROT_EXEC check).
  5. Cgroup-scoped socket connect filtering on untrusted taint tiers (socket_connect).

Honest Platform Boundary (In-Memory Policy Evaluator Scaffold):
  - This module is an in-memory Python policy evaluator scaffold (`is_kernel_bpf_active=False`,
    `operational_status=SIMULATED_OPT_IN`).
  - It does NOT attach kernel `BPF_LSM` programs or open `/sys/fs/bpf/smaos_policy`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.capability_status import SIMULATED_OPT_IN
from src.jcs_canonicalizer import encode_jcs


PROT_NONE = 0x0
PROT_READ = 0x1
PROT_WRITE = 0x2
PROT_EXEC = 0x4

EVENT_TYPE_BINARY_BLOCKED = "BINARY_EXECUTION_BLOCKED"
EVENT_TYPE_WEIGHT_TAMPERED = "WEIGHT_TAMPERING_DETECTED"
EVENT_TYPE_WX_VIOLATION = "WX_MEMORY_PROTECTION_VIOLATION"
EVENT_TYPE_PROT_EXEC_VIOLATION = "PROT_EXEC_PROMOTION_VIOLATION"
EVENT_TYPE_SOCKET_BLOCKED = "SOCKET_CONNECT_BLOCKED_TAINT"


@dataclass
class ModelWeightManifestEntry:
    model_name: str
    file_path: str
    expected_sha256: str
    expected_inode: Optional[int] = None
    file_size_bytes: int = 0
    model_type: str = "GGUF"  # GGUF | SAFETENSORS
    signed_by: str = "cro-ed25519-master-key"


@dataclass
class AllowedBinaryEntry:
    binary_name: str
    file_path: str
    expected_sha256: str
    expected_inode: Optional[int] = None
    permissions_mask: int = PROT_READ | PROT_EXEC


@dataclass
class AgentGuardSecurityEvent:
    event_id: str
    event_type: str
    target_path: str
    target_inode: Optional[int]
    observed_digest: Optional[str]
    expected_digest: Optional[str]
    pid: int
    comm: str
    timestamp_iso: str
    verdict: str  # ALLOW | DENY
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EbpfAgentGuardController:
    """
    Controller and clean-room evaluation engine for eBPF LSM boundary rules.
    """

    def __init__(self, bpf_pin_path: str = "/sys/fs/bpf/smaos_policy") -> None:
        self.bpf_pin_path = bpf_pin_path
        self.allowed_binaries: Dict[str, AllowedBinaryEntry] = {}
        self.model_weights: Dict[str, ModelWeightManifestEntry] = {}
        self.ringbuffer_events: List[AgentGuardSecurityEvent] = []
        self.is_kernel_bpf_active = False
        self.operational_status = SIMULATED_OPT_IN

    def register_allowed_binary(
        self,
        binary_name: str,
        file_path: str,
        sha256_digest: Optional[str] = None,
    ) -> AllowedBinaryEntry:
        abs_path = os.path.abspath(file_path)
        inode = None
        digest = sha256_digest

        if os.path.exists(abs_path):
            stat_res = os.stat(abs_path)
            inode = stat_res.st_ino
            if digest is None:
                with open(abs_path, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()

        entry = AllowedBinaryEntry(
            binary_name=binary_name,
            file_path=abs_path,
            expected_sha256=digest or "UNKNOWN",
            expected_inode=inode,
        )
        self.allowed_binaries[abs_path] = entry
        return entry

    def register_model_weight(
        self,
        model_name: str,
        file_path: str,
        expected_sha256: str,
        model_type: str = "GGUF",
        signed_by: str = "cro-ed25519-master-key",
    ) -> ModelWeightManifestEntry:
        abs_path = os.path.abspath(file_path)
        inode = None
        size_bytes = 0

        if os.path.exists(abs_path):
            stat_res = os.stat(abs_path)
            inode = stat_res.st_ino
            size_bytes = stat_res.st_size

        entry = ModelWeightManifestEntry(
            model_name=model_name,
            file_path=abs_path,
            expected_sha256=expected_sha256.lower(),
            expected_inode=inode,
            file_size_bytes=size_bytes,
            model_type=model_type,
            signed_by=signed_by,
        )
        self.model_weights[abs_path] = entry
        return entry

    def attest_binary_execution(
        self,
        binary_path: str,
        pid: int = 1001,
        comm: str = "smaos-runner",
    ) -> Tuple[bool, str, Optional[AgentGuardSecurityEvent]]:
        """LSM Hook: bprm_check_security"""
        abs_path = os.path.abspath(binary_path)
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        event_id = f"EVT-BPRM-{int(time.time()*1000)}"

        if abs_path not in self.allowed_binaries:
            event = AgentGuardSecurityEvent(
                event_id=event_id,
                event_type=EVENT_TYPE_BINARY_BLOCKED,
                target_path=abs_path,
                target_inode=os.stat(abs_path).st_ino if os.path.exists(abs_path) else None,
                observed_digest=None,
                expected_digest=None,
                pid=pid,
                comm=comm,
                timestamp_iso=timestamp_iso,
                verdict="DENY",
                reason=f"Binary {abs_path} not present in allowed_binaries map (EPERM)",
            )
            self.ringbuffer_events.append(event)
            return False, "DENY_UNAUTHORIZED_BINARY", event

        entry = self.allowed_binaries[abs_path]
        if os.path.exists(abs_path):
            with open(abs_path, "rb") as f:
                current_digest = hashlib.sha256(f.read()).hexdigest()
            if current_digest.lower() != entry.expected_sha256.lower():
                event = AgentGuardSecurityEvent(
                    event_id=event_id,
                    event_type=EVENT_TYPE_BINARY_BLOCKED,
                    target_path=abs_path,
                    target_inode=os.stat(abs_path).st_ino,
                    observed_digest=current_digest,
                    expected_digest=entry.expected_sha256,
                    pid=pid,
                    comm=comm,
                    timestamp_iso=timestamp_iso,
                    verdict="DENY",
                    reason="Binary SHA-256 digest tampered or replaced (EPERM)",
                )
                self.ringbuffer_events.append(event)
                return False, "DENY_BINARY_INTEGRITY_FAILED", event

        return True, "ALLOW_EXECUTION", None

    def attest_model_weight_mmap(
        self,
        weight_file_path: str,
        prot_flags: int = PROT_READ,
        pid: int = 1001,
        comm: str = "rapid-mlx",
    ) -> Tuple[bool, str, Optional[AgentGuardSecurityEvent]]:
        """LSM Hook: mmap_file"""
        abs_path = os.path.abspath(weight_file_path)
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        event_id = f"EVT-MMAP-{int(time.time()*1000)}"

        # 1. Check W^X invariant: simultaneous WRITE and EXEC is strictly prohibited
        if (prot_flags & PROT_WRITE) and (prot_flags & PROT_EXEC):
            event = AgentGuardSecurityEvent(
                event_id=event_id,
                event_type=EVENT_TYPE_WX_VIOLATION,
                target_path=abs_path,
                target_inode=None,
                observed_digest=None,
                expected_digest=None,
                pid=pid,
                comm=comm,
                timestamp_iso=timestamp_iso,
                verdict="DENY",
                reason="Simultaneous PROT_WRITE and PROT_EXEC requested (EACCES)",
            )
            self.ringbuffer_events.append(event)
            return False, "DENY_WX_VIOLATION", event

        # 2. Check if file is a registered model weight
        if abs_path not in self.model_weights:
            if any(abs_path.endswith(ext) for ext in [".safetensors", ".gguf", ".bin", ".pt"]):
                event = AgentGuardSecurityEvent(
                    event_id=event_id,
                    event_type=EVENT_TYPE_WEIGHT_TAMPERED,
                    target_path=abs_path,
                    target_inode=os.stat(abs_path).st_ino if os.path.exists(abs_path) else None,
                    observed_digest=None,
                    expected_digest=None,
                    pid=pid,
                    comm=comm,
                    timestamp_iso=timestamp_iso,
                    verdict="DENY",
                    reason="Unregistered model weights rejected by guard (EACCES)",
                )
                self.ringbuffer_events.append(event)
                return False, "DENY_UNREGISTERED_MODEL_WEIGHT", event
            return True, "ALLOW_UNMONITORED_MMAP", None

        manifest_entry = self.model_weights[abs_path]
        if not os.path.exists(abs_path):
            return False, "FILE_NOT_FOUND", None

        stat_res = os.stat(abs_path)
        with open(abs_path, "rb") as f:
            actual_digest = hashlib.sha256(f.read()).hexdigest()

        if actual_digest.lower() != manifest_entry.expected_sha256.lower():
            event = AgentGuardSecurityEvent(
                event_id=event_id,
                event_type=EVENT_TYPE_WEIGHT_TAMPERED,
                target_path=abs_path,
                target_inode=stat_res.st_ino,
                observed_digest=actual_digest,
                expected_digest=manifest_entry.expected_sha256,
                pid=pid,
                comm=comm,
                timestamp_iso=timestamp_iso,
                verdict="DENY",
                reason=f"Model weight digest mismatch: observed {actual_digest[:16]}... vs expected {manifest_entry.expected_sha256[:16]}...",
            )
            self.ringbuffer_events.append(event)
            return False, "DENY_WEIGHT_TAMPERING_DETECTED", event

        return True, "ALLOW_WEIGHT_MMAP", None

    def attest_memory_protection_escalation(
        self,
        target_name: str,
        new_prot: int,
        pid: int = 1001,
        comm: str = "rapid-mlx",
    ) -> Tuple[bool, str, Optional[AgentGuardSecurityEvent]]:
        """LSM Hook: file_mprotect"""
        if new_prot & PROT_EXEC:
            event = AgentGuardSecurityEvent(
                event_id=f"EVT-MPROT-{int(time.time()*1000)}",
                event_type=EVENT_TYPE_PROT_EXEC_VIOLATION,
                target_path=target_name,
                target_inode=None,
                observed_digest=None,
                expected_digest=None,
                pid=pid,
                comm=comm,
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
                verdict="DENY",
                reason="Attempted to escalate mapped model weight memory to PROT_EXEC (EPERM)",
            )
            self.ringbuffer_events.append(event)
            return False, "DENY_PROT_EXEC_VIOLATION", event

        return True, "ALLOW_MPROTECT", None

    def attest_socket_connect(
        self,
        dest_ip: str,
        dest_port: int,
        taint_tier: int = 0,
        pid: int = 1001,
        comm: str = "agent-runtime",
    ) -> Tuple[bool, str, Optional[AgentGuardSecurityEvent]]:
        """LSM Hook: socket_connect"""
        # TIER_2_UNTRUSTED_EXTERNAL processes are prohibited from direct external network connect
        if taint_tier >= 2:
            event = AgentGuardSecurityEvent(
                event_id=f"EVT-SOCK-{int(time.time()*1000)}",
                event_type=EVENT_TYPE_SOCKET_BLOCKED,
                target_path=f"{dest_ip}:{dest_port}",
                target_inode=None,
                observed_digest=None,
                expected_digest=None,
                pid=pid,
                comm=comm,
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
                verdict="DENY",
                reason="Untrusted external taint tier prohibited from direct socket connect (ENETUNREACH)",
            )
            self.ringbuffer_events.append(event)
            return False, "DENY_TAINTED_EGRESS_BLOCKED", event

        return True, "ALLOW_SOCKET_CONNECT", None

    def get_ringbuffer_events(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.ringbuffer_events]

    def clear_events(self) -> None:
        self.ringbuffer_events.clear()


def run_self_test() -> None:
    """Executes self-test of EbpfAgentGuardController."""
    ctrl = EbpfAgentGuardController()

    # 1. Test binary allowlisting
    ctrl.register_allowed_binary("python_bin", sys.executable)
    ok, reason, _ = ctrl.attest_binary_execution(sys.executable)
    assert ok is True

    bad_ok, bad_reason, _ = ctrl.attest_binary_execution("/usr/bin/unauthorized_agent_exploit")
    assert bad_ok is False
    assert bad_reason == "DENY_UNAUTHORIZED_BINARY"

    # 2. Test W^X violation
    wx_ok, wx_reason, _ = ctrl.attest_model_weight_mmap(
        "model.safetensors", prot_flags=PROT_WRITE | PROT_EXEC
    )
    assert wx_ok is False
    assert wx_reason == "DENY_WX_VIOLATION"

    # 3. Test memory protection escalation
    mp_ok, mp_reason, _ = ctrl.attest_memory_protection_escalation("mapped_page", PROT_EXEC)
    assert mp_ok is False
    assert mp_reason == "DENY_PROT_EXEC_VIOLATION"

    # 4. Test tainted socket connect blocking
    sock_ok, sock_reason, _ = ctrl.attest_socket_connect("198.51.100.1", 443, taint_tier=2)
    assert sock_ok is False
    assert sock_reason == "DENY_TAINTED_EGRESS_BLOCKED"

    print("[✓] EbpfAgentGuardController: Self-test passed (BPRM, W^X, MProtect, and Socket Taint verified).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="eBPF LSM Agent Guard Controller")
    parser.add_argument("--self-test", action="store_true", help="Execute self-test")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        sys.exit(0)
    else:
        parser.print_help()
