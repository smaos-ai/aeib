// SPDX-License-Identifier: GPL-2.0
// ebpf_agent_guard.c — AEIB Kernel-Level Socket & LSM Guard Prototype
//
// ARCHITECTURAL SCAFFOLDING NOTICE (AGENTS.md Section 5 — SCAFFOLD_ONLY):
// This file in `ebpf/` is currently structural scaffolding (SCAFFOLD_ONLY).
// It defines the BPF map schemas and LSM/cgroup socket hook signatures for a
// Linux kernel deployment, but does NOT claim live kernel/hardware enforcement
// on non-Linux hosts or unprivileged userspace runtimes. Primary deterministic
// enforcement is performed in userspace by AEIB Station 1–3 interlocks.
//
// Hook Design (Structural Scaffolding):
//   1. cgroup/connect4: Inspects outbound IPv4 connect() attempts from agent
//      processes, permitting only connections directed to the local AEIB
//      Station 2 sidecar loopback port.
//   2. lsm/bprm_check_security: Evaluates child binary execve() calls against
//      pinned inode allowlists.
//   3. lsm/mmap_file: Enforces W^X memory protection on model weight pages.

#include <linux/bpf.h>
#include <linux/errno.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define PROT_READ  0x1
#define PROT_WRITE 0x2
#define PROT_EXEC  0x4

// Structural scaffold telemetry event emitted to userspace audit ring buffer
struct aeib_guard_scaffold_event {
    __u32 pid;
    __u32 uid;
    __u32 hook_id;      // 1 = connect4, 2 = bprm_check, 3 = mmap_file
    __u32 disposition;  // 0 = observed_allowed, 1 = observed_blocked
    __u16 dst_port;
    __u16 reserved;
    char comm[16];
};

// Pinned Station 2 loopback port configuration map (key 0 -> allowed port)
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u16);
} station2_loopback_port_map SEC(".maps");

// Ring buffer for structural telemetry export
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 16);
} aeib_guard_ringbuf SEC(".maps");

SEC("lsm/mmap_file")
int BPF_PROG(aeib_scaffold_mmap_wx_guard, struct file *file,
             unsigned long reqprot, unsigned long prot, unsigned long flags)
{
    if ((prot & PROT_WRITE) && (prot & PROT_EXEC)) {
        struct aeib_guard_scaffold_event *evt;
        evt = bpf_ringbuf_reserve(&aeib_guard_ringbuf, sizeof(*evt), 0);
        if (evt) {
            __u64 pid_tgid = bpf_get_current_pid_tgid();
            evt->pid = (__u32)(pid_tgid >> 32);
            evt->uid = (__u32)bpf_get_current_uid_gid();
            evt->hook_id = 3;
            evt->disposition = 1;
            evt->dst_port = 0;
            evt->reserved = 0;
            bpf_get_current_comm(&evt->comm, sizeof(evt->comm));
            bpf_ringbuf_submit(evt, 0);
        }
        return -EPERM;
    }
    return 0;
}

char _license[] SEC("license") = "GPL";
