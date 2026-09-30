# AEIB Layer A — eBPF XDP 5-Tuple Packet Quarantine & Telemetry Engine

**Milestone:** Layer A Production-Valid Kernel Primitive ($T_0$ Physical Wire Suppression)  
**Standard Alignment:** Agent Execution Integrity Benchmark (AEIB v0.2.1)  
**Author:** Andrii Leukhin (Independent Researcher, SovereignNexus)  
**Environment Target:** Linux (Kernel 5.8+) with BCC / eBPF tools (`CAP_NET_ADMIN`)  

---

## 🎯 1. Overview & Problem Formulation

In autonomous agent architectures, transport-level dropouts (such as HTTP 504 Gateway Timeouts, TCP RST, or connection drops) routinely trigger unhedged retry loops in LLM ReAct engines. Because userspace middleware cannot guarantee atomicity when the process itself faults or the transport drops asynchronously, the agent re-reasons over an incomplete state and dispatches mutated payloads, resulting in double-spending or corrupted state.

This implementation delivers **Layer A (Kernel & Physical Wire Enforcement)**:
* Userspace governance decisions (e.g., from the AEIB Sidecar Interceptor marking a route as `DISPATCHED_UNCONFIRMED`) write directly to a kernel BPF hash map matching the full **5-tuple** (`saddr`, `sport`, `daddr`, `dport`, `proto`).
* The Linux kernel eXpress Data Path (**XDP**) driver hook inspects incoming and forwarded packets at the earliest possible physical stage ($T_0$), before socket buffers (`sk_buff`) or userspace runtimes are allocated.
* Packets matching the quarantined flow are immediately dropped with `XDP_DROP`, physically freezing unhedged retries at the wire level while emitting high-frequency structured telemetry over a **1 MiB BPF Ringbuf**.
* Non-quarantined flows (such as out-of-band probe sockets on a distinct source port) pass freely (`XDP_PASS`), preventing distributed deadlocks.

---

## 🏛️ 2. The 4 Structural Fixes Applied

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        EBPF KERNEL & USERSPACE STRUCTURAL FIXES                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Network Byte Order Alignment (Userspace <-> BPF Map)                                 │
│    • Applied socket.inet_aton(ip) for saddr/daddr and socket.htons(port) for sport/dport│
│    • Eliminates endianness mismatch on x86/ARM where host byte order broke map lookups.│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. Struct Memory Zero-Initialization                                                   │
│    • Applied ctypes.memset(ctypes.byref(key), 0, ctypes.sizeof(key)) prior to population│
│    • Eliminates uninitialized stack padding bytes corrupting raw BPF hash keys.        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. Dynamic IHL Calculation & Fragment Guards (xdp_drop.c)                              │
│    • Calculated ihl = ip->ihl * 4 dynamically to handle variable IPv4 option headers.  │
│    • Added (ip->frag_off & htons(IP_OFFSET | IP_MF)) check to pass non-initial         │
│      fragments safely without misparsing Layer 4 ports.                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. 1 MiB Ringbuf Capacity & Event Emission                                             │
│    • Expanded BPF_MAP_TYPE_RINGBUF capacity to 1 << 20 (1,048,576 bytes / 256 pages).  │
│    • Prevents telemetry buffer overflows under high-frequency agent retry bursts.       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 3. Architecture & File Structure

```text
ebpf/
├── README.md           # Technical specification, limitations, and verification runbook
├── xdp_drop.c          # Kernel-space XDP packet inspection, drop hook, and Ringbuf emission (C)
└── controller.py       # Userspace Python/BCC manager, 5-tuple coordinator, and CLI
```

### 5-Tuple Schema & Ringbuf Telemetry Contract

```c
struct flow_5tuple {
    __u32 saddr; // Source IPv4 (network byte order)
    __u32 daddr; // Destination IPv4 (network byte order)
    __u16 sport; // Source port (network byte order)
    __u16 dport; // Destination port (network byte order)
    __u8  proto; // IP protocol (IPPROTO_TCP = 6)
}; // 16 bytes (aligned)

struct drop_event {
    __u64 timestamp_ns;      // Kernel boot time in nanoseconds
    struct flow_5tuple flow; // Flow matching the quarantine rule
    __u32 action;            // 1 = XDP_DROP
}; // 32 bytes (aligned)
```

---

## 🧪 4. Linux Verification Runbook (Ubuntu VM / Kernel 5.15+)

### Step 1: Start Controller & Add Quarantine Flow
```bash
sudo python3 ebpf/controller.py --add-flow 10.0.2.15 49210 10.0.2.2 8080 6
```
**Output:**
```json
{"level": "info", "msg": "Quarantine map updated", "src": "10.0.2.15:49210", "dst": "10.0.2.2:8080", "proto": "TCP"}
{"level": "info", "msg": "Polling for drop events (Ctrl+C to exit)..."}
```

### Step 2: Send the Original (Quarantined) Flow
```bash
# In a separate terminal, test sending over the quarantined source port:
nc -p 49210 10.0.2.2 8080
```
**Controller Telemetry Output:**
```json
{"event": "AEIB_XDP_PACKET_DROP", "timestamp_ns": 1717258901234567, "disposition": "DISPATCHED_UNCONFIRMED_QUARANTINE", "flow": {"source": "10.0.2.15:49210", "destination": "10.0.2.2:8080", "protocol": "TCP"}, "action": "XDP_DROP"}
```
*(The `nc` command hangs and times out. The packet was physically suppressed at the driver level before transmission).*

### Step 3: Send the Out-of-Band Probe (Different Source Port)
```bash
# Using probe socket on port 51000:
nc -p 51000 10.0.2.2 8080
```
*(The probe command succeeds immediately. The packet passes with `XDP_PASS`. No drop event is emitted, allowing out-of-band state reconciliation without deadlock).*

---

## 📜 5. AEIB Receipt Integration Spec

To bind this kernel evidence into the `aeib-0.2` schema without breaking signature verification or hash ordering, map the eBPF Ringbuf event into the `transport_evidence` block inside the signed payload view:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "receipt_version": "aeib-0.2",
  "receipt_id": "urn:uuid:8a9b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
  "action_id": "mcp://sess-prd-992/14/call-001/payment.settle",
  "decision": "permit",
  "execution_observation": "tcp_retry_dropped_by_xdp",
  "outcome_verification": "not_confirmed",
  "aeib_extension": {
    "version": "0.1",
    "disposition": "DISPATCHED_UNCONFIRMED",
    "retry_policy": "PROBE_REQUIRED_NO_ORIGINAL_RETRY",
    "dora_binding": {
      "incident_class": null,
      "classification_timestamp_utc": null,
      "classification_status": "PENDING_HUMAN_REVIEW"
    }
  },
  "transport_evidence": {
    "adapter_type": "ebpf_xdp_driver",
    "adapter_version": "0.1",
    "observation": "quarantine_flow_dropped",
    "observed_at_utc": "2026-09-30T07:31:00Z",
    "kernel_telemetry": {
      "timestamp_ns": 1717258901234567,
      "disposition": "DISPATCHED_UNCONFIRMED_QUARANTINE",
      "flow_5tuple": {
        "source": "10.0.2.15:49210",
        "destination": "10.0.2.2:8080",
        "protocol": "TCP"
      },
      "action": "XDP_DROP",
      "ringbuf_discard_count": 0
    }
  },
  "outcome_probe": {
    "adapter_type": "database_ledger",
    "probe_status": "not_yet_attempted",
    "authoritative_source_id": "ledger:payments-prd",
    "expected_payload_hash": "sha256:55aa...",
    "idempotency_key": "c3f9b2..."
  }
}
```

---

## ⚠️ 6. Explicit System Boundaries & Five Known Limitations

1. **No Automatic In-Kernel 504 Detection**: The XDP driver does not parse HTTP response headers. It relies on the userspace AEIB Interceptor (e.g. `src/transport_observer.py`) to detect transport timeouts and populate the BPF quarantine map.
2. **Layer 4 TCP Scope in v0.1**: Filtering is strictly TCP-focused. UDP, ICMP, and raw transport protocols pass through unquarantined in this prototype.
3. **Fragmented Packet Bypass**: Non-initial IP fragments (`IP_OFFSET | IP_MF`) are passed without inspection to avoid incorrect L4 port evaluation.
4. **Kernel Version & Privilege Requirements**: Requires Linux kernel 5.8+ for full BPF Ringbuf support and root / `CAP_NET_ADMIN` capabilities. Will not run natively under macOS (Darwin) or Windows NT.
5. **No L7 Payload Inspection / TLS Decryption**: Operates strictly at Layer 3/4 header boundaries; does not inspect or decrypt encrypted TLS application bodies.
