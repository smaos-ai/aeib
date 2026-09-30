// SPDX-License-Identifier: GPL-2.0
// AEIB eBPF XDP Quarantine: 5-tuple flow isolation with ringbuf telemetry

#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>  // FIX 1: endian helpers
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>

// 5-tuple flow key (aligned for BPF map)
struct flow_5tuple {
    __u32 saddr;
    __u32 daddr;
    __u16 sport; // network byte order
    __u16 dport; // network byte order
    __u8  proto;
    __u8  pad[3]; // explicit 3-byte padding for 64-bit alignment
};

// Quarantine map: 5-tuple → disposition code
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, struct flow_5tuple);
    __type(value, __u32);
} quarantine_map SEC(".maps");

// Ringbuf for structured drop events
struct drop_event {
    struct flow_5tuple flow;
    __u64 timestamp_ns;
    __u32 disposition_code; // 1 = DISPATCHED_UNCONFIRMED_QUARANTINE
};

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);
} events SEC(".maps");

SEC("xdp")
int xdp_drop_func(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    // Ethernet header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    // Only IPv4
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    // IP header - FIX 2: verifier-safe pointer derivation
    struct iphdr *iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS;

    // FIX 4: reject malformed IHL
    if (iph->ihl < 5)
        return XDP_PASS;

    // FIX 3: drop all fragments (conservative)
    if (iph->frag_off & bpf_htons(0x3FFF))
        return XDP_PASS;

    struct flow_5tuple flow = {};
    flow.saddr = iph->saddr;
    flow.daddr = iph->daddr;
    flow.proto = iph->protocol;

    // TCP/UDP header - FIX 2: derive from iph, not from data
    if (iph->protocol == IPPROTO_TCP) {
        struct tcphdr *tcph = (void *)iph + (iph->ihl * 4);
        if ((void *)(tcph + 1) > data_end)
            return XDP_PASS;
        flow.sport = tcph->source;
        flow.dport = tcph->dest;
    } else if (iph->protocol == IPPROTO_UDP) {
        struct udphdr *udph = (void *)iph + (iph->ihl * 4);
        if ((void *)(udph + 1) > data_end)
            return XDP_PASS;
        flow.sport = udph->source;
        flow.dport = udph->dest;
    } else {
        return XDP_PASS; // non-TCP/UDP: pass
    }

    // Check quarantine map
    __u32 *disp = bpf_map_lookup_elem(&quarantine_map, &flow);
    if (disp) {
        // Emit ringbuf event
        struct drop_event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);
        if (e) {
            e->flow = flow;
            e->timestamp_ns = bpf_ktime_get_ns();
            e->disposition_code = *disp;
            bpf_ringbuf_submit(e, 0);
        }
        return XDP_DROP;
    }

    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
