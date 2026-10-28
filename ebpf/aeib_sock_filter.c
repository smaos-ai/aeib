// SPDX-License-Identifier: GPL-2.0
// aeib_sock_filter.c — eBPF Kernel Socket State Transition Scaffolding (L7a Transport)
//
// Structural scaffolding for observing TCP socket state transitions at the kernel level.
// Per AGENTS.md §5, this module is architectural scaffolding: it does not claim live
// kernel enforcement without an active BPF subsystem deployment and a user-space loader.
//
// L7a scope: this program only *observes* wire facts. Disposition derivation
// (DISPATCHED_UNCONFIRMED, retry_safe, latching) stays at L7c in the AEIB engine.

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_endian.h>

// TCP states (include/net/tcp_states.h), 1-based as defined by the kernel.
#define TCP_ESTABLISHED 1
#define TCP_SYN_SENT    2
#define TCP_SYN_RECV    3
#define TCP_FIN_WAIT1   4
#define TCP_FIN_WAIT2   5
#define TCP_TIME_WAIT   6
#define TCP_CLOSE       7
#define TCP_CLOSE_WAIT  8
#define TCP_LAST_ACK    9
#define TCP_LISTEN      10
#define TCP_CLOSING     11

// L7a wire-fault classification emitted with each teardown observation.
// 0 is a non-fault: userspace MUST NOT map it to DISPATCHED_UNCONFIRMED.
#define AEIB_WIRE_GRACEFUL_FIN_ACK 0 // FIN-ACK handshake completed (or TIME_WAIT expiry)
#define AEIB_WIRE_TCP_RST          1 // abortive severance: teardown with no FIN exchange
#define AEIB_WIRE_TIMEOUT          2 // unacknowledged teardown abandoned during FIN_WAIT

struct wire_fault_event {
    __u32 pid;
    __u32 saddr;
    __u32 daddr;
    __u16 sport;
    __u16 dport;
    __u8 old_state;
    __u8 new_state;
    __u8 fault_type; // AEIB_WIRE_GRACEFUL_FIN_ACK | AEIB_WIRE_TCP_RST | AEIB_WIRE_TIMEOUT
    __u8 fin_ack_seen; // 1 when the FIN-ACK handshake was observed before teardown
};

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 18);
} fault_events SEC(".maps");

// Disambiguates how a socket reached TCP_CLOSE using the state it left.
//
// Graceful (FIN-ACK) completions:
//   LAST_ACK  -> CLOSE : passive close finished, our FIN was acknowledged
//   TIME_WAIT -> CLOSE : normal TIME_WAIT expiry after a completed handshake
// Unconfirmed mid-flight drops:
//   ESTABLISHED / CLOSE_WAIT / SYN_* -> CLOSE : no FIN exchange at all
//                                           -> TCP_RST (abortive severance)
//   FIN_WAIT1 / FIN_WAIT2 / CLOSING  -> CLOSE : socket left FIN_WAIT without
//                                           reaching TIME_WAIT
//                                           -> TIMEOUT (unacknowledged teardown)
static __always_inline __u8 aeib_classify_teardown(__u8 old_state, __u8 *fin_ack_seen)
{
    // Graceful: passive close completed after our FIN was acknowledged, or a
    // normal TIME_WAIT expiry following a completed FIN-ACK handshake.
    if (old_state == TCP_LAST_ACK || old_state == TCP_TIME_WAIT) {
        *fin_ack_seen = 1;
        return AEIB_WIRE_GRACEFUL_FIN_ACK;
    }

    // Unconfirmed teardown during FIN_WAIT: our FIN left the socket but the
    // handshake never reached TIME_WAIT.
    if (old_state == TCP_FIN_WAIT2 || old_state == TCP_CLOSING) {
        *fin_ack_seen = 1;
        return AEIB_WIRE_TIMEOUT;
    }
    if (old_state == TCP_FIN_WAIT1) {
        // FIN transmitted, ACK never observed before the socket was reaped.
        *fin_ack_seen = 0;
        return AEIB_WIRE_TIMEOUT;
    }

    // Data-transfer state torn down with no FIN exchange: TCP_RST or an
    // equivalent abortive socket teardown (mid-flight drop).
    *fin_ack_seen = 0;
    return AEIB_WIRE_TCP_RST;
}

SEC("fentry/tcp_set_state")
int BPF_PROG(aeib_tcp_set_state, struct sock *sk, int state)
{
    __u8 old_state = BPF_CORE_READ(sk, __sk_common.skc_state);
    __u8 new_state = state;
    __u8 fin_ack_seen = 0;
    __u8 fault_type;

    // Only mid-flight teardown is in scope; listening sockets carry no payload.
    if (new_state != TCP_CLOSE || old_state == TCP_CLOSE || old_state == TCP_LISTEN)
        return 0;

    fault_type = aeib_classify_teardown(old_state, &fin_ack_seen);

    struct wire_fault_event *event = bpf_ringbuf_reserve(&fault_events, sizeof(*event), 0);
    if (!event)
        return 0;

    // Filter for IPv4 sockets (AF_INET = 2). IPv6 addresses require separate
    // in6_addr extraction and are out of scope for this IPv4 observer.
    __u16 family = BPF_CORE_READ(sk, __sk_common.skc_family);
    if (family != 2)
        return 0;

    // Softirq Caveat: When tcp_set_state is called in softirq context (e.g.,
    // handling an asynchronous incoming TCP RST packet), bpf_get_current_pid_tgid()
    // reflects the currently interrupted task rather than the socket owner.
    // Production process attribution requires socket cookie or cgroup ID tracking.
    __u64 pid_tgid = bpf_get_current_pid_tgid();
    event->pid = (__u32)(pid_tgid >> 32);

    // Extract IPv4 addresses and ports with endian conversion for dport
    event->saddr = BPF_CORE_READ(sk, __sk_common.skc_rcv_saddr);
    event->daddr = BPF_CORE_READ(sk, __sk_common.skc_daddr);
    event->sport = BPF_CORE_READ(sk, __sk_common.skc_num);
    event->dport = bpf_ntohs(BPF_CORE_READ(sk, __sk_common.skc_dport));

    event->old_state = old_state;
    event->new_state = new_state;
    event->fault_type = fault_type;
    event->fin_ack_seen = fin_ack_seen;
    bpf_ringbuf_submit(event, 0);
    return 0;
}

char _license[] SEC("license") = "GPL";
