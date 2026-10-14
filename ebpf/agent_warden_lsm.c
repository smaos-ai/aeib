// SPDX-License-Identifier: GPL-2.0
// agent_warden_lsm.c — Linux BPF-LSM Agent-Warden Kernel Boundary Scaffolding
//
// Epistemic Boundary (AGENTS.md §5):
//   This module provides structural scaffolding and prototype BPF-LSM hooks
//   evaluated for environments where CONFIG_BPF_LSM=y and operator privileges
//   are available. In application testing or non-root environments, this file
//   serves as a prototype specification and bytecode compilation target, not
//   a live kernel guarantee.
//
// Operational Capabilities (under the stated model):
//   1. Tracks process-to-socket lineage for designated agent cgroups/PIDs.
//   2. Implements synchronous circuit-breaker kill switch: drops agent egress
//      with -EPERM when triggered via circuit_breaker_map.
//   3. Restricts agent socket connect calls to local AEIB proxy loopback interface
//      (127.0.0.1:8765), denying ambient outbound TCP egress fail-closed.

#include <linux/bpf.h>
#include <linux/capability.h>
#include <linux/errno.h>
#include <linux/in.h>
#include <linux/socket.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_endian.h>

#define AGENT_WARDEN_DISPOSITION_ALLOWED 0
#define AGENT_WARDEN_DISPOSITION_DENIED  1

#define HOOK_SOCKET_CONNECT 1

// Event record forwarded to userspace ring buffer for audit and telemetry
struct warden_event {
    __u32 pid;
    __u32 tgid;
    __u32 uid;
    __u32 hook_id;
    __u32 disposition;
    __u32 dest_ip;
    __u16 dest_port;
    __u16 reason_code;
    char comm[16];
};

// Map 1: Active monitored agent PIDs
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32); // PID
    __type(value, __u8); // 1 = monitored agent process
} agent_pid_map SEC(".maps");

// Map 2: Emergency circuit breaker kill switch
// key 0 -> 1 = emergency trip (drop all agent egress synchronously), 0 = normal
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u32);
} circuit_breaker_map SEC(".maps");

// Map 3: Out-of-band audit ring buffer for warden telemetry
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 18); // 256 KB
} warden_events SEC(".maps");

// Helper: emit event to userland ring buffer
static __always_inline void emit_warden_event(
    __u32 pid,
    __u32 tgid,
    __u32 uid,
    __u32 disposition,
    __u32 dest_ip,
    __u16 dest_port,
    __u16 reason_code
) {
    struct warden_event *evt = bpf_ringbuf_reserve(&warden_events, sizeof(*evt), 0);
    if (!evt)
        return;

    evt->pid = pid;
    evt->tgid = tgid;
    evt->uid = uid;
    evt->hook_id = HOOK_SOCKET_CONNECT;
    evt->disposition = disposition;
    evt->dest_ip = dest_ip;
    evt->dest_port = dest_port;
    evt->reason_code = reason_code;
    bpf_get_current_comm(&evt->comm, sizeof(evt->comm));

    bpf_ringbuf_submit(evt, 0);
}

// ─────────────────────────────────────────────────────────────────────────────
// BPF-LSM HOOK: socket_connect
// ─────────────────────────────────────────────────────────────────────────────
SEC("lsm/socket_connect")
int BPF_PROG(agent_warden_connect, struct socket *sock, struct sockaddr *address, int addrlen)
{
    __u64 pid_tgid = bpf_get_current_pid_tgid();
    __u32 pid = (__u32)(pid_tgid >> 32);
    __u32 tgid = (__u32)pid_tgid;
    __u32 uid = bpf_get_current_uid_gid();

    // 1. Check if current process is tracked in agent_pid_map
    __u8 *is_agent = bpf_map_lookup_elem(&agent_pid_map, &pid);
    if (!is_agent) {
        // Also check TGID for multi-threaded / child processes
        is_agent = bpf_map_lookup_elem(&agent_pid_map, &tgid);
    }

    // Unmonitored non-agent processes proceed normally
    if (!is_agent || *is_agent == 0) {
        return 0;
    }

    // 2. Evaluate Circuit Breaker Kill Switch
    __u32 zero = 0;
    __u32 *tripped = bpf_map_lookup_elem(&circuit_breaker_map, &zero);
    if (tripped && *tripped == 1) {
        emit_warden_event(pid, tgid, uid, AGENT_WARDEN_DISPOSITION_DENIED, 0, 0, 101); // 101 = CIRCUIT_BREAKER_TRIPPED
        return -EPERM;
    }

    // 3. Inspect target sockaddr (IPv4 support in prototype scaffold)
    if (address->sa_family == AF_INET) {
        struct sockaddr_in *in = (struct sockaddr_in *)address;
        __u32 daddr = in->sin_addr.s_addr;
        __u16 dport = bpf_ntohs(in->sin_port);

        // 127.0.0.1 in network byte order: 0x0100007f
        __u32 loopback_ip = 0x0100007f;
        __u16 aeib_proxy_port = 8765;

        // If target is local AEIB gateway, permit connection
        if (daddr == loopback_ip && dport == aeib_proxy_port) {
            emit_warden_event(pid, tgid, uid, AGENT_WARDEN_DISPOSITION_ALLOWED, daddr, dport, 200);
            return 0;
        }

        // Ambient external egress attempted by agent: deny fail-closed
        emit_warden_event(pid, tgid, uid, AGENT_WARDEN_DISPOSITION_DENIED, daddr, dport, 403);
        return -EPERM;
    }

    // Non-IPv4 address families for agent denied fail-closed under strict model
    emit_warden_event(pid, tgid, uid, AGENT_WARDEN_DISPOSITION_DENIED, 0, 0, 400);
    return -EPERM;
}

char _license[] SEC("license") = "GPL";
