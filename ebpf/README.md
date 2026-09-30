# AEIB Layer A — eBPF XDP Driver-Level Packet Quarantine Proof-of-Concept

**Milestone:** Layer A Research Prototype ($T_0$ Physical Wire Suppression)  
**Standard Alignment:** Agent Execution Integrity Benchmark (AEIB v0.2.1)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Environment Target:** Linux (Kernel 4.18+) with BCC / eBPF tools (`CAP_NET_ADMIN`)  

---

## 🎯 1. Overview & Scientific Motivation

In autonomous agent architectures, transport-level dropouts (such as HTTP 504 Gateway Timeouts, TCP RST, or connection drops) routinely trigger unhedged retry loops in LLM ReAct engines. Because userspace middleware cannot guarantee atomicity when the process itself faults or the transport drops asynchronously, the agent re-reasons over an incomplete state and dispatches mutated payloads, resulting in double-spending or corrupted state.

This isolated proof-of-concept demonstrates **Layer A (Kernel & Physical Wire Enforcement)**:
* Userspace governance decisions (e.g., from the AEIB Sidecar Interceptor marking a route as `DISPATCHED_UNCONFIRMED`) write directly to a kernel BPF hash map.
* The Linux kernel eXpress Data Path (**XDP**) driver hook inspects incoming and forwarded packets at the earliest possible physical stage ($T_0$), before socket buffers (`sk_buff`) or userspace runtimes are allocated.
* Packets destined for the quarantined target are immediately dropped with `XDP_DROP`, physically freezing unhedged retries at the wire level until out-of-band reconciliation completes.

---

## 🏛️ 2. Architecture & File Structure

```text
ebpf/
├── README.md           # Technical specification, limitations, and verification runbook
├── xdp_drop.c          # Kernel-space XDP packet inspection and drop hook (C)
└── controller.py       # Userspace Python/BCC manager, map coordinator, and CLI
```

### BPF Map Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| **Key** | `__u32` | Target IPv4 destination address in network byte order (`iph->daddr`) |
| **Value** | `__u32` | Quarantine status (`1` = `DISPATCHED_UNCONFIRMED` / Quarantined $\to$ `XDP_DROP`) |

---

## ⚙️ 3. Component Details

### Kernel Program (`xdp_drop.c`)
* Parses Ethernet frame (`struct ethhdr`) and filters non-IPv4 traffic (`ETH_P_IP`).
* Verifies IPv4 packet boundaries (`struct iphdr`).
* Extracts `iph->daddr` and performs a zero-copy lookup in `quarantine_map`.
* If `status == 1`: logs a kernel debug trace via `bpf_trace_printk` and returns `XDP_DROP`.
* Otherwise: returns `XDP_PASS` for normal protocol stack processing.

### Userspace Controller (`controller.py`)
* Compiles `xdp_drop.c` using the BPF Compiler Collection (BCC) and attaches the XDP program to the chosen interface (`lo`, `veth1`, or `eth0`).
* Populates and manages the kernel `quarantine_map` via `bpf()` syscalls.
* Handles clean detachment on exit (`SIGINT`).
* Includes a built-in simulation fallback mode for development and testing on non-Linux platforms (e.g. macOS Darwin).

---

## 🧪 4. Linux Verification Runbook

> [!NOTE]
> eBPF XDP programs require a Linux kernel (4.18+) with root or `CAP_NET_ADMIN` capabilities. Under macOS Darwin, `controller.py` automatically runs in userspace simulation mode.

### Prerequisites (Ubuntu / Debian Linux)
```bash
sudo apt-get update
sudo apt-get install -y bpfcc-tools linux-headers-$(uname -r) python3-bpfcc python3
```

### Step 1: Attach to Loopback & Quarantine Target IP
```bash
# Attach XDP hook to loopback and quarantine target address 127.0.0.2
sudo python3 controller.py --iface lo --add 127.0.0.2
```

### Step 2: Verify Kernel-Level Packet Suppression
```bash
# In a separate terminal, test reachability:
ping -c 3 127.0.0.2

# Expected output: 100% packet loss (silently dropped at XDP driver layer)
# --- 127.0.0.2 ping statistics ---
# 3 packets transmitted, 0 received, 100% packet loss
```

### Step 3: Inspect Kernel Trace Messages
```bash
sudo cat /sys/kernel/debug/tracing/trace_pipe

# Expected output:
# <...>-1234 [001] .... 1234.567890: bpf_trace_printk: AEIB eBPF XDP_DROP: Target IP 200007f QUARANTINED (status=1)
```

### Step 4: Remove Target from Quarantine
```bash
sudo python3 controller.py --iface lo --remove 127.0.0.2

# Normal traffic is immediately restored:
ping -c 3 127.0.0.2
# 3 packets transmitted, 3 received, 0% packet loss
```

---

## ⚠️ 5. Honest Technical Framing & Explicit Boundaries

To maintain scientific credibility and prevent overclaiming:

1. **Isolated Layer 3 Proof-of-Concept**: This implementation matches strictly on IPv4 destination address (`__u32`). It does not inspect TCP sequence numbers, TLS SNI, or Layer 7 HTTP/JSON-RPC bodies.
2. **Decoupled from Receipt Generation**: This module proves kernel-level drop mechanics. It does not generate or verify Ed25519 receipts directly; in the target 3-layer architecture, userspace components (such as `src/transport_observer.py`) instruct the BPF map upon detecting ambiguous wire states.
3. **OS Specificity**: Native XDP execution requires Linux. Darwin (macOS) and Windows NT do not provide XDP driver infrastructure.
