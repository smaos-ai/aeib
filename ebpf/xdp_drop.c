// SPDX-License-Identifier: Apache-2.0 OR GPL-2.0
/*
 * xdp_drop.c — AEIB Kernel-Space XDP Packet Quarantine Proof-of-Concept
 * Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)
 *
 * Driver-level ($T_0$) packet suppression hook.
 * Inspects incoming/routed IPv4 packets, extracts the destination IPv4 address,
 * looks up the destination in the quarantine BPF hash map, and physically drops
 * packets (XDP_DROP) if the target route is marked DISPATCHED_UNCONFIRMED (status == 1).
 */

#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/in.h>

// BPF Hash Map storing quarantined target IPv4 addresses
// Key: u32 (IPv4 destination address in network byte order)
// Value: u32 (1 = DISPATCHED_UNCONFIRMED / Quarantined, triggers XDP_DROP)
BPF_HASH(quarantine_map, u32, u32);

int xdp_drop_quarantined(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    // 1. Boundary check: Verify Ethernet header fits within packet bounds
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    // Filter non-IPv4 traffic (pass ARP, IPv6, VLAN, etc.)
    if (eth->h_proto != htons(ETH_P_IP))
        return XDP_PASS;

    // 2. Boundary check: Verify IPv4 header fits within packet bounds
    struct iphdr *iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS;

    u32 dst_ip = iph->daddr;

    // 3. Authoritative BPF Map Lookup
    u32 *status = quarantine_map.lookup(&dst_ip);
    if (status && *status == 1) {
        bpf_trace_printk("AEIB eBPF XDP_DROP: Target IP %x QUARANTINED (status=1)\n", dst_ip);
        return XDP_DROP;
    }

    return XDP_PASS;
}
