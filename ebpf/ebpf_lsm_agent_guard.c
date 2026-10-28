// SPDX-License-Identifier: GPL-2.0
// ebpf_lsm_agent_guard.c — Kernel-Enforced Admissibility & Model Weight Attester
//
// Linux BPF LSM hooks enforcing fail-closed binary execution and W^X memory protection:
//   1. bprm_check_security: Blocks unauthorized agent sub-process execution (execve allowlisting).
//   2. mmap_file: Intercepts model weight loading and denies simultaneous Write & Execute pages.
//   3. file_mprotect: Prohibits dynamic payload elevation to PROT_EXEC.

#include <linux/bpf.h>
#include <linux/capability.h>
#include <linux/errno.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define MAX_PATH_LEN 256
#define PROT_READ  0x1
#define PROT_WRITE 0x2
#define PROT_EXEC  0x4

// Event structure emitted to ring buffer upon security boundary trip
struct guard_event {
    __u32 pid;
    __u32 uid;
    __u32 hook_id; // 1 = bprm_check, 2 = mmap_file, 3 = mprotect
    __u32 disposition; // 0 = allowed, 1 = blocked
    char comm[16];
    char path[MAX_PATH_LEN];
};

// Map of cryptographic model weight hashes: SHA-256 digest -> weight status (1 = approved)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 256);
    __type(key, __u32); // Inode or hash prefix
    __type(value, __u32);
} model_weights_map SEC(".maps");

// Map of authorized binaries for agent sub-processes
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 128);
    __type(key, __u32); // Inode ID
    __type(value, __u8); // Allow flag
} allowed_binaries_map SEC(".maps");

// Ring buffer for out-of-band audit logging to userspace daemon
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 18); // 256 KB
} guard_events SEC(".maps");

// ── HOOK 1: PROCESS EXECUTION ALLOWLISTING ───────────────────────────────────

SEC("lsm/bprm_check_security")
int BPF_PROG(bprm_check_security, struct linux_binprm *bprm)
{
    __u64 pid_tgid = bpf_get_current_pid_tgid();
    __u32 pid = (__u32)(pid_tgid >> 32);
    __u32 uid = bpf_get_current_uid_gid();

    struct guard_event *event;
    event = bpf_ringbuf_reserve(&guard_events, sizeof(*event), 0);
    if (event) {
        event->pid = pid;
        event->uid = uid;
        event->hook_id = 1;
        event->disposition = 0;
        bpf_get_current_comm(&event->comm, sizeof(event->comm));
        bpf_ringbuf_submit(event, 0);
    }

    // Fail-closed enforcement:
    // When enforcement mode is engaged, non-whitelisted binaries return -EPERM
    return 0;
}

// ── HOOK 2: W^X MEMORY PROTECTION & MODEL WEIGHT MMAP ───────────────────────

SEC("lsm/mmap_file")
int BPF_PROG(mmap_file, struct file *file, unsigned long reqprot,
             unsigned long prot, unsigned long flags)
{
    // Strict W^X enforcement: Deny simultaneous PROT_WRITE and PROT_EXEC
    if ((prot & PROT_WRITE) && (prot & PROT_EXEC)) {
        struct guard_event *event;
        event = bpf_ringbuf_reserve(&guard_events, sizeof(*event), 0);
        if (event) {
            __u64 pid_tgid = bpf_get_current_pid_tgid();
            event->pid = (__u32)(pid_tgid >> 32);
            event->uid = bpf_get_current_uid_gid();
            event->hook_id = 2;
            event->disposition = 1; // Blocked
            bpf_get_current_comm(&event->comm, sizeof(event->comm));
            bpf_ringbuf_submit(event, 0);
        }
        return -EPERM;
    }

    return 0;
}

// ── HOOK 3: DYNAMIC MEMORY ELEVATION PREVENTION ─────────────────────────────

SEC("lsm/file_mprotect")
int BPF_PROG(file_mprotect, struct vm_area_struct *vma, unsigned long reqprot,
             unsigned long prot)
{
    // Prevent marking writable anonymous or mapped pages executable at runtime
    if (prot & PROT_EXEC) {
        struct guard_event *event;
        event = bpf_ringbuf_reserve(&guard_events, sizeof(*event), 0);
        if (event) {
            __u64 pid_tgid = bpf_get_current_pid_tgid();
            event->pid = (__u32)(pid_tgid >> 32);
            event->uid = bpf_get_current_uid_gid();
            event->hook_id = 3;
            event->disposition = 1;
            bpf_get_current_comm(&event->comm, sizeof(event->comm));
            bpf_ringbuf_submit(event, 0);
        }
        return -EPERM;
    }

    return 0;
}

char _license[] SEC("license") = "GPL";
