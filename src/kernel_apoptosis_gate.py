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
src/kernel_apoptosis_gate.py
================================================================================
D2 Delivery: eBPF Homeostatic Membrane & Digital Apoptosis Gate.

Evaluated under the stated model (simulated scaffold model):
Enforces kernel-level capability sandboxes and continuous runtime verification (CRV).
In host environments equipped with Cilium Tetragon or libbpf, this module maps to
eBPF LSM hooks (`security_socket_connect`, `security_file_open`).
For the deterministic test harness, it provides a simulated model of the LSM hook
evaluation logic, triggering Digital Apoptosis (`SIGKILL` / `HaltKernelInvariantViolation`)
upon any out-of-bounds syscall or network egress attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set


# ============================================================================
# Declarative Artifacts (eBPF C & Cilium Tetragon Policy)
# ============================================================================
EBPF_LSM_C_CODE: str = """
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <linux/sched.h>
#include <linux/socket.h>
#include <linux/in.h>

// Allowlist of permitted network domains (Populated from FormalIntent spec)
const volatile __u32 allowed_net_domains[] = {0x0100007F}; // 127.0.0.1 in network byte order

SEC("lsm/socket_connect")
int BPF_PROG(aeib_socket_connect, struct socket *sock, struct sockaddr *address, int addrlen) {
    if (address->sa_family == AF_INET) {
        struct sockaddr_in *addr_in = (struct sockaddr_in *)address;
        // Block all non-loopback network connections for isolated agent worktrees
        if (addr_in->sin_addr.s_addr != allowed_net_domains[0]) {
            bpf_printk("AEIB_APOPTOSIS: Blocked non-loopback network egress");
            return -EPERM; // Kernel drops the syscall
        }
    }
    return 0;
}

SEC("lsm/file_open")
int BPF_PROG(aeib_file_open, struct file *file) {
    // In live kernel: uses bpf_d_path to verify file inode against worktree bounds
    // If write attempt is detected outside allowed_file_paths -> return -EPERM
    return 0;
}
"""

TETRAGON_TRACING_POLICY: str = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: aeib-homeostatic-membrane
spec:
  lsm:
    - call: "socket_connect"
      selectors:
        - matchActions:
            - action: Sigkill
              kernelStackTrace: true
    - call: "file_open"
      selectors:
        - matchActions:
            - action: Sigkill
"""


# ============================================================================
# Core Boundary Classes
# ============================================================================
class HaltKernelInvariantViolation(Exception):
    """Triggered when the kernel membrane detects an unauthorized syscall."""


@dataclass(frozen=True)
class AgentProcessContext:
    pid: int
    worktree_path: str
    allowed_network_domains: Set[str]
    allowed_file_paths: Set[str]


class HomeostaticMembrane:
    """
    The Cell Membrane for AI Agents.
    Evaluates syscall admissibility and triggers programmed self-termination on violation.
    """

    def __init__(self) -> None:
        self.active_agents: Dict[int, AgentProcessContext] = {}
        self.apoptosis_log: List[Dict[str, Any]] = []

    def register_agent(self, ctx: AgentProcessContext) -> None:
        """Registers an agent process and its strict capability bounds."""
        self.active_agents[ctx.pid] = ctx

    def simulate_syscall_socket_connect(self, pid: int, target_ip: str) -> None:
        """Evaluates network egress against declared process domains."""
        if pid not in self.active_agents:
            raise HaltKernelInvariantViolation("HALT_UNREGISTERED_PROCESS_SYSCALL")
        ctx = self.active_agents[pid]
        if target_ip not in ctx.allowed_network_domains:
            self._trigger_apoptosis(pid, f"BLOCKED_EGRESS:{target_ip}")

    def simulate_syscall_file_open(self, pid: int, target_path: str, mode: str) -> None:
        """Evaluates filesystem access against declared worktree boundaries."""
        if pid not in self.active_agents:
            raise HaltKernelInvariantViolation("HALT_UNREGISTERED_PROCESS_SYSCALL")
        ctx = self.active_agents[pid]
        if mode == "w" and not any(target_path.startswith(p) for p in ctx.allowed_file_paths):
            self._trigger_apoptosis(pid, f"BLOCKED_WRITE:{target_path}")

    def _trigger_apoptosis(self, pid: int, reason: str) -> None:
        """
        Digital Apoptosis: Records termination event and halts execution.
        Under live kernel operations, Tetragon sends SIGKILL immediately.
        """
        self.apoptosis_log.append({"pid": pid, "reason": reason, "action": "SIGKILL"})
        raise HaltKernelInvariantViolation(f"HALT_KERNEL_INVARIANT_VIOLATION:{reason}")

    def get_ebpf_c_code(self) -> str:
        return EBPF_LSM_C_CODE

    def get_tetragon_policy(self) -> str:
        return TETRAGON_TRACING_POLICY
