// SPDX-License-Identifier: Apache-2.0 OR GPL-2.0
/*
 * xdp_drop.c — AEIB Kernel-Space XDP Packet Quarantine Proof-of-Concept (v0.2.1)
 * Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)
 *
 * Implements 5-tuple quarantine and 1 MiB BPF Ringbuf telemetry emission.
 * Incorporates 4 Structural Fixes:
 *   1. Port & IP Byte Order (Network byte order alignment with userspace)
 *   2. Pad Byte Zeroing (Explicit memset and clean 5-tuple key struct)
 *   3. Dynamic IHL calculation & IP fragment guards
 *   4. 1 MiB Ringbuf capacity & telemetry event submission
 */

#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/tcp.h>
#include <uapi/linux/in.h>

#ifndef IP_MF
#define IP_MF 0x2000
#endif
#ifndef IP_OFFSET
#define IP_OFFSET 0x1FFF
#endif

// 5-Tuple flow specification matching userspace Flow5Tuple (16 bytes aligned)
struct flow_5tuple {
    __u32 saddr;
    __u32 daddr;
    __u16 sport;
    __u16 dport;
    __u8  proto;
};

// Ringbuf telemetry event payload (32 bytes aligned)
struct drop_event {
    __u64 timestamp_ns;
    struct flow_5tuple flow;
    __u32 action; // 1 = XDP_DROP
};

// Quarantine BPF Hash Map matching on full 5-tuple
// Value: 1 = DISPATCHED_UNCONFIRMED / Quarantined
BPF_HASH(quarantine_map, struct flow_5tuple, u32);

// Correction 4: 1 MiB Ring buffer for high-frequency telemetry events under agent retry bursts
// In BCC: 256 pages * 4096 = 1,048,576 bytes (1 MiB)
BPF_RINGBUF_OUTPUT(drop_events, 256);

int xdp_drop_quarantined(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    // 1. Boundary check: Verify Ethernet header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != htons(ETH_P_IP))
        return XDP_PASS;

    // 2. Boundary check: Base IPv4 header
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    // Correction 3: Dynamic IHL calculation to handle variable IPv4 option headers
    __u32 ihl = ip->ihl * 4;
    if (ihl < sizeof(struct iphdr))
        return XDP_PASS;

    if ((void *)ip + ihl > data_end)
        return XDP_PASS;

    // Correction 3 Guard: Ignore fragmented packets (cannot parse L4 reliably)
    if (ip->frag_off & htons(IP_OFFSET | IP_MF))
        return XDP_PASS;

    // Only TCP supported in v0.1
    if (ip->protocol != IPPROTO_TCP)
        return XDP_PASS;

    // 3. Boundary check: TCP header
    struct tcphdr *tcp = (void *)ip + ihl;
    if ((void *)(tcp + 1) > data_end)
        return XDP_PASS;

    // Correction 1 & 2: Construct 5-tuple key in network byte order with zeroed memory
    struct flow_5tuple flow;
    __builtin_memset(&flow, 0, sizeof(flow));
    flow.saddr = ip->saddr;
    flow.daddr = ip->daddr;
    flow.sport = tcp->source;
    flow.dport = tcp->dest;
    flow.proto = ip->protocol;

    // 4. Authoritative BPF Map Lookup
    u32 *status = quarantine_map.lookup(&flow);
    if (status && *status == 1) {
        // Correction 4: Emit structured telemetry event to 1 MiB ring buffer
        struct drop_event ev;
        __builtin_memset(&ev, 0, sizeof(ev));
        ev.timestamp_ns = bpf_ktime_get_ns();
        ev.flow = flow;
        ev.action = 1; // XDP_DROP

        drop_events.ringbuf_output(&ev, sizeof(ev), 0);

        bpf_trace_printk("AEIB eBPF XDP_DROP: Flow %x:%d -> %x:%d QUARANTINED\n",
                         ntohl(flow.saddr), ntohs(flow.sport),
                         ntohl(flow.daddr), ntohs(flow.dport));
        return XDP_DROP;
    }

    // Deadlock Prevention: Non-quarantined flows (e.g. probe socket on port 51000) PASS
    return XDP_PASS;
}
