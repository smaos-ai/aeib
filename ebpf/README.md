# AEIB eBPF L7a Kernel Socket Interceptor

This directory contains `aeib_sock_filter.c`, the eBPF program responsible for **Stage 1** of the AEIB 3-Stage Verification Stack: trapping raw socket resets at the Linux kernel boundary.

## Compilation Instructions (TRL 7-9)

To compile the eBPF filter into a loadable BPF object, you must have `clang`, `llvm`, and `bpftool` installed on a Linux host (or cross-compiled from a macOS/Windows environment targeting Linux).

```bash
# 1. Generate the vmlinux.h header from the target kernel
bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h

# 2. Compile the eBPF C code to BPF bytecode using clang
clang -g -O2 -target bpf -D__TARGET_ARCH_x86 -I. -c aeib_sock_filter.c -o aeib_sock_filter.o

# 3. (Optional) Inspect the generated BPF bytecode
llvm-objdump -S aeib_sock_filter.o
```

## Wire Fault Classification (L7a observation only)

Teardown observations are classified from the TCP state the socket *left*, so a
graceful FIN-ACK closure is classified as `fault_type 0` rather than as a
mid-flight drop:

| `fault_type` | Meaning | Transition basis |
|---|---|---|
| `0` `AEIB_WIRE_GRACEFUL_FIN_ACK` | Not a fault — FIN-ACK handshake completed | `LAST_ACK -> CLOSE`, `TIME_WAIT -> CLOSE` |
| `1` `AEIB_WIRE_TCP_RST` | Abortive severance, no FIN exchange observed | `ESTABLISHED/CLOSE_WAIT/SYN_* -> CLOSE` |
| `2` `AEIB_WIRE_TIMEOUT` | Unacknowledged teardown during `FIN_WAIT` | `FIN_WAIT1/FIN_WAIT2/CLOSING -> CLOSE` |

`fin_ack_seen` records whether the FIN exchange had been observed before the
telemetry event. The program only reports wire facts: disposition derivation
(`DISPATCHED_UNCONFIRMED`, `retry_safe`, latch state) is performed at L7c
inside the AEIB engine, not in the kernel.

Per `AGENTS.md` §5 this directory remains architectural scaffolding until it is
loaded into a kernel with an active BPF subsystem and a user-space loader.

## Loader Integration
The compiled `aeib_sock_filter.o` can be loaded into the kernel via Python using the `bcc` or `cilium/ebpf` (Go) libraries. The AEIB engine reads from the `fault_events` BPF ring buffer to deterministically map socket faults to `DISPATCHED_UNCONFIRMED` (events with `fault_type != 0`).
