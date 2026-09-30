#!/usr/bin/env python3
r"""
controller.py — Userspace eBPF XDP 5-Tuple Quarantine Controller & Telemetry Engine
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB v0.2.1)

Enforces driver-level packet suppression ($T_0$) with 4 Structural Fixes:
  1. Port & IP Byte Order (Network byte order alignment with userspace)
  2. Struct Memory Zero-Initialization (ctypes.memset / zeroed pad[3])
  3. Dynamic IHL Calculation & IP Fragment Guards (with verifier-safe pointer math)
  4. Ringbuf Telemetry Event Stream (libbpf CO-RE ringbuf events)
"""

import os
import sys
import time
import socket
import struct
import ctypes
import argparse
import platform
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Any

# Path to the accompanying XDP C program
XDP_SOURCE_FILE = Path(__file__).resolve().parent / "xdp_drop.c"

# Detect BCC availability and platform
PLATFORM_IS_LINUX = (platform.system() == "Linux")
try:
    from bcc import BPF
    BCC_AVAILABLE = True
except (ImportError, Exception):
    BCC_AVAILABLE = False


class Flow5Tuple(ctypes.Structure):
    """
    5-Tuple flow specification (16 bytes aligned).
    Explicitly zero-initialized to eliminate undefined padding bits.
    """
    _fields_ = [
        ("saddr", ctypes.c_uint32),
        ("daddr", ctypes.c_uint32),
        ("sport", ctypes.c_uint16),
        ("dport", ctypes.c_uint16),
        ("proto", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 3),
    ]


class DropEvent(ctypes.Structure):
    """
    Ringbuf telemetry event payload (32 bytes aligned).
    Emitted by xdp_drop.c on XDP_DROP action.
    """
    _fields_ = [
        ("flow", Flow5Tuple),
        ("timestamp_ns", ctypes.c_uint64),
        ("disposition_code", ctypes.c_uint32),
    ]


# Protocol constants
TCP = 6
UDP = 17
ICMP = 1


def _normalize_proto(proto: Any) -> int:
    """Normalizes protocol representation (integer or string like 'TCP')."""
    if isinstance(proto, str):
        p_up = proto.upper().strip()
        if p_up == "TCP":
            return 6
        elif p_up == "UDP":
            return 17
        elif p_up == "ICMP":
            return 1
        return int(proto)
    return int(proto)


def ip_to_u32(ip: str) -> int:
    """Converts dot-decimal IPv4 string to 32-bit unsigned integer in network byte order."""
    return struct.unpack("=I", socket.inet_aton(ip.strip()))[0]


def flow_key_bytes(key: Flow5Tuple) -> bytes:
    """Returns raw byte representation of 5-tuple key for map hashing."""
    return bytes(key)


def format_ip(u32_val: int) -> str:
    """Converts 32-bit integer in network byte order to dot-decimal IPv4 string."""
    return socket.inet_ntoa(struct.pack("=I", u32_val))


def proto_name(proto: int) -> str:
    """Converts protocol number to human-readable protocol string."""
    if proto == 6:
        return "TCP"
    elif proto == 17:
        return "UDP"
    elif proto == 1:
        return "ICMP"
    return str(proto)


class SimulatedBpfMap:
    """Fallback in-memory BPF map simulator for macOS Darwin and test environments."""

    def __init__(self):
        self._map: Dict[bytes, Tuple[Flow5Tuple, int]] = {}

    def __setitem__(self, key, value):
        k_bytes = flow_key_bytes(key)
        v = value.value if hasattr(value, "value") else int(value)
        # Store a copy of key struct
        stored_key = Flow5Tuple()
        ctypes.memmove(ctypes.byref(stored_key), ctypes.byref(key), ctypes.sizeof(key))
        self._map[k_bytes] = (stored_key, v)

    def __getitem__(self, key):
        k_bytes = flow_key_bytes(key)
        if k_bytes in self._map:
            _, val = self._map[k_bytes]
            return ctypes.c_uint32(val)
        raise KeyError("Key not found in simulated BPF map")

    def __delitem__(self, key):
        k_bytes = flow_key_bytes(key)
        if k_bytes in self._map:
            del self._map[k_bytes]
        else:
            raise KeyError("Key not found in simulated BPF map")

    def __contains__(self, key):
        k_bytes = flow_key_bytes(key)
        return k_bytes in self._map

    def items(self):
        for k_bytes, (k_struct, v) in self._map.items():
            yield k_struct, ctypes.c_uint32(v)

    def clear(self):
        self._map.clear()

    def __len__(self):
        return len(self._map)


class XdpQuarantineController:
    """
    Manages the lifecycle of the XDP 5-tuple quarantine program and Ringbuf telemetry.
    """

    def __init__(self, iface: str = "lo", source_file: Optional[Path] = None, force_simulate: bool = False):
        self.iface = iface
        self.source_file = source_file or XDP_SOURCE_FILE
        self.force_simulate = force_simulate
        self.is_simulated = force_simulate or (not PLATFORM_IS_LINUX) or (not BCC_AVAILABLE)

        self._bpf = None
        self._quarantine_map = None

        if self.is_simulated:
            self._quarantine_map = SimulatedBpfMap()
        else:
            self._init_bcc()

        self.quarantine_map = self._quarantine_map

    def _init_bcc(self):
        """Compiles and loads the XDP C program into the Linux kernel via BCC."""
        if not self.source_file.exists():
            raise FileNotFoundError(f"XDP source file not found at {self.source_file}")

        c_code = self.source_file.read_text(encoding="utf-8")
        self._bpf = BPF(text=c_code)
        fn = self._bpf.load_func("xdp_drop_func", BPF.XDP)
        self._bpf.attach_xdp(self.iface, fn, 0)
        self._quarantine_map = self._bpf["quarantine_map"]
        self.quarantine_map = self._quarantine_map

    def detach(self):
        """Removes the XDP program from the network interface."""
        if self._bpf and not self.is_simulated:
            try:
                self._bpf.remove_xdp(self.iface, 0)
            except Exception:
                pass

    def build_flow_key(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> Flow5Tuple:
        """
        Builds a zero-initialized Flow5Tuple struct in network byte order.
        Addresses Correction 1 (Network Byte Order) & Correction 2 (Pad Byte Zeroing).
        """
        proto_num = _normalize_proto(proto)
        key = Flow5Tuple(
            saddr=ip_to_u32(src_ip),
            daddr=ip_to_u32(dst_ip),
            sport=socket.htons(int(src_port)),
            dport=socket.htons(int(dst_port)),
            proto=int(proto_num),
            pad=(ctypes.c_uint8 * 3)(0, 0, 0),
        )
        return key

    def add_flow(
        self,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        proto: Any = 6,
        disposition: int = 1,
    ) -> None:
        """
        Quarantines a 5-tuple flow in the BPF map with status = disposition (default 1 = DISPATCHED_UNCONFIRMED).
        XDP physically drops matching packets at the driver layer ($T_0$).
        """
        key = self.build_flow_key(src_ip, src_port, dst_ip, dst_port, proto)
        val = ctypes.c_uint32(int(disposition))
        self.quarantine_map[key] = val

    def add(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6, disposition: int = 1) -> None:
        """Convenience alias for add_flow."""
        self.add_flow(src_ip, src_port, dst_ip, dst_port, proto, disposition)

    def remove_flow(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> bool:
        """Removes 5-tuple flow from quarantine map, restoring normal traffic flow."""
        key = self.build_flow_key(src_ip, src_port, dst_ip, dst_port, proto)
        try:
            del self.quarantine_map[key]
            return True
        except (KeyError, Exception):
            return False

    def remove(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> bool:
        """Convenience alias for remove_flow."""
        return self.remove_flow(src_ip, src_port, dst_ip, dst_port, proto)

    def is_quarantined(self, saddr: str, sport: int, daddr: str, dport: int, proto: Any = 6) -> bool:
        """
        Prove that quarantine is scoped to exact 5-tuple, not just destination IP.
        Checks if 5-tuple exists in the quarantine BPF map.
        """
        proto_num = _normalize_proto(proto)
        key = Flow5Tuple(
            saddr=ip_to_u32(saddr),
            daddr=ip_to_u32(daddr),
            sport=socket.htons(int(sport)),
            dport=socket.htons(int(dport)),
            proto=int(proto_num),
            pad=(ctypes.c_uint8 * 3)(),
        )
        return key in self.quarantine_map

    def is_flow_quarantined(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> bool:
        """Direct alias for is_quarantined conforming to AEIB test specification."""
        return self.is_quarantined(src_ip, src_port, dst_ip, dst_port, proto)

    def list_quarantine(self) -> List[Dict[str, Any]]:
        """Returns list of all active quarantined flows."""
        flows = []
        for k, v in self.quarantine_map.items():
            s_ip = format_ip(k.saddr)
            d_ip = format_ip(k.daddr)
            s_port = socket.ntohs(k.sport)
            d_port = socket.ntohs(k.dport)
            p_str = proto_name(k.proto)
            val_num = v.value if hasattr(v, "value") else int(v)
            flows.append({
                "source": f"{s_ip}:{s_port}",
                "destination": f"{d_ip}:{d_port}",
                "protocol": p_str,
                "status": val_num,
            })
        return flows

    def clear_all(self) -> None:
        """Flushes all entries from the quarantine map."""
        if hasattr(self.quarantine_map, "clear"):
            self.quarantine_map.clear()
        else:
            keys = [k for k, _ in self.quarantine_map.items()]
            for k in keys:
                del self.quarantine_map[k]

    def poll_events(self, timeout_sec: Optional[float] = None, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        Polls 256 KiB Ring buffer for high-frequency drop telemetry events.
        Emits structured JSON events matching AEIB evidence requirements.
        If timeout_sec is specified (> 0), polls for that duration then returns.
        """
        def default_callback(event_dict):
            print(json.dumps(event_dict))
            sys.stdout.flush()

        cb = callback or default_callback
        start_time = time.time()

        if self.is_simulated or not self._bpf:
            timeout_desc = f"{timeout_sec}s" if timeout_sec and timeout_sec > 0 else "indefinite"
            print(json.dumps({"level": "info", "msg": f"Polling for drop events (simulation mode, timeout={timeout_desc})..."}))
            sys.stdout.flush()
            try:
                while True:
                    if timeout_sec and timeout_sec > 0:
                        if time.time() - start_time >= timeout_sec:
                            break
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
            return

        def _handle_ringbuf_event(cpu, data, size):
            event = ctypes.cast(data, ctypes.POINTER(DropEvent)).contents
            s_ip = format_ip(event.flow.saddr)
            d_ip = format_ip(event.flow.daddr)
            s_port = socket.ntohs(event.flow.sport)
            d_port = socket.ntohs(event.flow.dport)
            p_str = proto_name(event.flow.proto)

            event_dict = {
                "event": "AEIB_XDP_PACKET_DROP",
                "timestamp_ns": int(event.timestamp_ns),
                "disposition": "DISPATCHED_UNCONFIRMED_QUARANTINE" if event.disposition_code == 1 else str(event.disposition_code),
                "disposition_code": int(event.disposition_code),
                "flow": {
                    "source": f"{s_ip}:{s_port}",
                    "destination": f"{d_ip}:{d_port}",
                    "protocol": p_str,
                },
                "action": "XDP_DROP",
            }
            cb(event_dict)

        self._bpf["events"].open_ring_buffer(_handle_ringbuf_event)
        timeout_desc = f"{timeout_sec}s" if timeout_sec and timeout_sec > 0 else "Ctrl+C to exit"
        print(json.dumps({"level": "info", "msg": f"Polling ringbuf events (timeout={timeout_desc})..."}))
        sys.stdout.flush()
        try:
            while True:
                if timeout_sec and timeout_sec > 0:
                    if time.time() - start_time >= timeout_sec:
                        break
                self._bpf.ring_buffer_poll(timeout=100)
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="AEIB eBPF XDP 5-Tuple Quarantine Controller — Physical wire suppression at T_0"
    )
    parser.add_argument("--iface", default="lo", help="Network interface to attach XDP to (default: lo)")
    parser.add_argument(
        "--add-flow",
        nargs="+",
        metavar="FLOW_PARAM",
        help="Quarantine a 5-tuple flow: SRC_IP SRC_PORT DST_IP DST_PORT PROTO [DISPOSITION]",
    )
    parser.add_argument(
        "--remove-flow",
        nargs=5,
        metavar=("SRC_IP", "SRC_PORT", "DST_IP", "DST_PORT", "PROTO"),
        help="Remove 5-tuple flow from quarantine",
    )
    parser.add_argument("--list", action="store_true", help="List all quarantined flows")
    parser.add_argument("--clear", action="store_true", help="Clear all quarantined flows")
    parser.add_argument("--listen", action="store_true", help="Keep attached and stream ringbuf telemetry events")
    parser.add_argument(
        "--poll",
        type=float,
        nargs="?",
        const=0.0,
        default=None,
        metavar="SECONDS",
        help="Poll ringbuf telemetry events (optional timeout in seconds; 0 or omitted for indefinite)",
    )
    parser.add_argument("--simulate", action="store_true", help="Force userspace simulation mode")

    args = parser.parse_args()

    # Display schema contract structure if no operational arguments provided
    if not (args.add_flow or args.remove_flow or args.list or args.clear or args.listen or (args.poll is not None)):
        print("[!] Displaying compiled 5-Tuple schema contract structure:")
        print(f"    Key struct size: {ctypes.sizeof(Flow5Tuple)} bytes (saddr, daddr, sport, dport, proto, pad[3])")
        print(f"    Event struct size: {ctypes.sizeof(DropEvent)} bytes (Ringbuf telemetry payload)")
        print("\nUse --help for CLI execution options, or --add-flow to quarantine a route.\n")
        return

    controller = XdpQuarantineController(
        iface=args.iface,
        force_simulate=args.simulate,
    )

    try:
        if args.add_flow:
            if len(args.add_flow) == 5:
                s_ip, s_port, d_ip, d_port, proto = args.add_flow
                disp = 1
            elif len(args.add_flow) >= 6:
                s_ip, s_port, d_ip, d_port, proto = args.add_flow[:5]
                disp = int(args.add_flow[5])
            else:
                parser.error("--add-flow requires 5 or 6 arguments: SRC_IP SRC_PORT DST_IP DST_PORT PROTO [DISPOSITION]")

            controller.add_flow(s_ip, int(s_port), d_ip, int(d_port), proto, int(disp))
            p_str = proto_name(_normalize_proto(proto))
            print(json.dumps({
                "level": "info",
                "msg": "Quarantine map updated",
                "src": f"{s_ip}:{s_port}",
                "dst": f"{d_ip}:{d_port}",
                "proto": p_str,
                "disposition": disp,
            }))
            sys.stdout.flush()
            if args.poll is not None or args.listen:
                timeout = args.poll if args.poll is not None else 0.0
                controller.poll_events(timeout_sec=timeout)

        elif args.remove_flow:
            s_ip, s_port, d_ip, d_port, proto = args.remove_flow
            removed = controller.remove_flow(s_ip, int(s_port), d_ip, int(d_port), proto)
            p_str = proto_name(_normalize_proto(proto))
            if removed:
                print(json.dumps({
                    "level": "info",
                    "msg": "Quarantine flow removed",
                    "src": f"{s_ip}:{s_port}",
                    "dst": f"{d_ip}:{d_port}",
                    "proto": p_str,
                }))
            else:
                print(json.dumps({
                    "level": "warn",
                    "msg": "Flow not found in quarantine map",
                    "src": f"{s_ip}:{s_port}",
                    "dst": f"{d_ip}:{d_port}",
                    "proto": p_str,
                }))

        elif args.clear:
            controller.clear_all()
            print(json.dumps({"level": "info", "msg": "Quarantine map cleared"}))

        elif args.list:
            entries = controller.list_quarantine()
            print(f"\n--- Current 5-Tuple Quarantine Map ({len(entries)} entries) ---")
            if not entries:
                print("  (Empty — normal traffic allowed)")
            for item in entries:
                print(f"  • {item['source']} -> {item['destination']} [{item['protocol']}] => XDP_DROP (status={item['status']})")
            print("----------------------------------------------------------------\n")

        elif args.poll is not None:
            controller.poll_events(timeout_sec=args.poll)

        elif args.listen:
            controller.poll_events()

    finally:
        if not args.add_flow and not args.listen and (args.poll is None):
            controller.detach()


if __name__ == "__main__":
    main()
