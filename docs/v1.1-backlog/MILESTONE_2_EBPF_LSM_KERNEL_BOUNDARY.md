# Milestone 2: Kernel-Native eBPF LSM Interception & Damage Boundaries

**Track:** Track B (`v1.1` Backlog)  
**Status:** Structural Scaffolding & Prototype Controller (`AGENTS.md` §5)  
**Module Alignment:** `ebpf/aeib_sock_filter.c`, `ebpf/agent_warden_lsm.c`, `src/governance_hooks/colibri_rce_check.py`, `tests/test_ebpf_controller.py`  
**Epistemic Notice (`AGENTS.md` §5):** Code in `ebpf/` is classified strictly as structural scaffolding. In standard application test environments and CI without bare-metal root or locked Linux CVM kernels (`CONFIG_BPF_LSM=y`), it does not provide active kernel-level enforcement. It generates policy definitions, BPF bytecode templates, and socket redirection mappings.

---

## 1. Architectural Motivation: Agent-Warden Pattern

Standard userland proxies can be bypassed if an autonomous agent achieves arbitrary code execution (RCE via tool arguments), spawns uninstrumented child processes (`sh`, `curl`, `python -c`), or opens raw sockets bypassing application-layer hooks.

The **Agent-Warden** pattern (informed by empirical USTC research on agent provenance tracking) positions interception at the Linux kernel boundary:
1. **Syscall Hooking:** Attaches to `sys_enter_connect` and `sys_enter_write` to track process-to-socket lineage.
2. **BPF-LSM Socket Redirection:** Traps outbound `connect()` syscalls initiated by designated agent cgroups/PIDs, enforcing redirection to the local AEIB loopback port (`127.0.0.1:8765`) before packets reach host network interfaces.
3. **Emergency Circuit Breaker:** Implements a kernel map kill-switch: if an anomaly or unvetted tool call is detected, the BPF program returns `-EPERM` synchronously, dropping all active agent TCP streams.

---

## 2. Technical Topology & Structural Scaffolding

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        AGENT SANDBOX (CGROUP: /agent)                  │
│  [Autonomous Python / Node Process] -- spawns --> [Subprocess: curl]   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ sys_enter_connect(sock, dest_ip)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     LINUX KERNEL BPF-LSM HOOK                          │
│  ebpf/agent_warden_lsm.c                                               │
│  • Check PID/cgroup against active_agent_map                           │
│  • If kill_switch_active == 1 -> return -EPERM (SYNCHRONOUS HALT)     │
│  • If dest_ip != 127.0.0.1 && port != 8765:                            │
│    Rewrite destination sockaddr to 127.0.0.1:8765 (AEIB Proxy)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Redirected loopback traffic
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               AEIB WIRE BOUNDARY (127.0.0.1:8765)                      │
│  • Evaluates Dead Salmons filter & computes RFC 8785 CAID              │
│  • Enforces EO-1 fsync intent logging before outbound socket release  │
│  • Latches EFFECT_INDETERMINATE on 504/TCP RST and probes target       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Structural Scaffolding Code Assets

1. **BPF Source:** `ebpf/agent_warden_lsm.c`  
   Defines BPF maps (`agent_pid_map`, `circuit_breaker_map`, `egress_allowlist_map`) and the `lsm/socket_connect` program hook.
2. **Verification Controller:** `tests/test_ebpf_controller.py`  
   Evaluates the userland management interface: configuring map values, toggling the emergency kill switch, and verifying that map update policies fail closed upon invalid configurations.
3. **Compliance Boundary:** Evaluated as structural scaffolding. Real-world deployment requires operator kernel privilege and Linux 6.1+ LTS kernels compiled with `CONFIG_BPF_LSM=y`.
