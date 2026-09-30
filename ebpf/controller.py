#!/usr/bin/env python3
r"""
controller.py — Userspace eBPF XDP 5-Tuple Quarantine Controller & Telemetry Engine
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB v0.2.1)

Enforces driver-level packet suppression ($T_0$) with 4 Structural Fixes:
  1. Port & IP Byte Order (Network byte order alignment with userspace)
  2. Struct Memory Zero-Initialization (ctypes.memset preventing undefined padding bytes)
  3. Dynamic IHL Calculation & IP Fragment Guards
  4. 1 MiB Ringbuf Capacity & High-Frequency Telemetry Event Stream
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
from typing import Dict, List, Optional, Tuple, Callable

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
    ]


class DropEvent(ctypes.Structure):
    """
    Ringbuf telemetry event payload (32 bytes aligned).
    Emitted by xdp_drop.c on XDP_DROP action.
    """
    _fields_ = [
        ("timestamp_ns", ctypes.c_uint64),
        ("flow", Flow5Tuple),
        ("action", ctypes.c_uint32),
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

    def _init_bcc(self):
        """Compiles and loads the XDP C program into the Linux kernel via BCC."""
        if not self.source_file.exists():
            raise FileNotFoundError(f"XDP source file not found at {self.source_file}")

        c_code = self.source_file.read_text(encoding="utf-8")
        self._bpf = BPF(text=c_code)
        fn = self._bpf.load_func("xdp_drop_quarantined", BPF.XDP)
        self._bpf.attach_xdp(self.iface, fn, 0)
        self._quarantine_map = self._bpf["quarantine_map"]

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
        key = Flow5Tuple()
        # Correction 2: Explicit zero-initialization of memory
        ctypes.memset(ctypes.byref(key), 0, ctypes.sizeof(key))

        # Correction 1: Explicit network byte order packing
        key.saddr = struct.unpack("=I", socket.inet_aton(src_ip.strip()))[0]
        key.daddr = struct.unpack("=I", socket.inet_aton(dst_ip.strip()))[0]
        key.sport = socket.htons(int(src_port))
        key.dport = socket.htons(int(dst_port))
        key.proto = int(proto_num)
        return key

    def add_flow(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> None:
        """
        Quarantines a 5-tuple flow in the BPF map with status = 1 (DISPATCHED_UNCONFIRMED).
        XDP will physically drop matching packets at the driver layer ($T_0$).
        """
        key = self.build_flow_key(src_ip, src_port, dst_ip, dst_port, proto)
        val = ctypes.c_uint32(1)
        self._quarantine_map[key] = val

    def add(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> None:
        """Convenience alias for add_flow."""
        self.add_flow(src_ip, src_port, dst_ip, dst_port, proto)

    def remove_flow(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> bool:
        """Removes 5-tuple flow from quarantine map, restoring normal traffic flow."""
        key = self.build_flow_key(src_ip, src_port, dst_ip, dst_port, proto)
        try:
            del self._quarantine_map[key]
            return True
        except (KeyError, Exception):
            return False

    def remove(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> bool:
        """Convenience alias for remove_flow."""
        return self.remove_flow(src_ip, src_port, dst_ip, dst_port, proto)

    def is_flow_quarantined(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> bool:
        """Checks if a given 5-tuple flow is currently quarantined."""
        key = self.build_flow_key(src_ip, src_port, dst_ip, dst_port, proto)
        try:
            val = self._quarantine_map[key]
            return val.value == 1
        except (KeyError, IndexError):
            return False

    def is_quarantined(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: Any = 6) -> bool:
        """
        Checks if a given 5-tuple flow is currently quarantined.
        Direct alias for is_flow_quarantined conforming to AEIB test specification.
        """
        return self.is_flow_quarantined(src_ip, src_port, dst_ip, dst_port, proto)

    def list_quarantine(self) -> List[Dict[str, Any]]:
        """Returns list of all active quarantined flows."""
        flows = []
        for k, v in self._quarantine_map.items():
            s_ip = format_ip(k.saddr)
            d_ip = format_ip(k.daddr)
            s_port = socket.ntohs(k.sport)
            d_port = socket.ntohs(k.dport)
            p_str = proto_name(k.proto)
            flows.append({
                "source": f"{s_ip}:{s_port}",
                "destination": f"{d_ip}:{d_port}",
                "protocol": p_str,
                "status": v.value,
            })
        return flows

    def clear_all(self) -> None:
        """Flushes all entries from the quarantine map."""
        if hasattr(self._quarantine_map, "clear"):
            self._quarantine_map.clear()
        else:
            keys = [k for k, _ in self._quarantine_map.items()]
            for k in keys:
                del self._quarantine_map[k]

    def poll_events(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        Correction 4: Polls 1 MiB Ring buffer for high-frequency drop telemetry events.
        Emits structured JSON events matching AEIB evidence requirements.
        """
        def default_callback(event_dict):
            print(json.dumps(event_dict))
            sys.stdout.flush()

        cb = callback or default_callback

        if self.is_simulated or not self._bpf:
            print(json.dumps({"level": "info", "msg": "Polling for drop events (Ctrl+C to exit)..."}))
            sys.stdout.flush()
            try:
                while True:
                    time.sleep(0.5)
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
                "disposition": "DISPATCHED_UNCONFIRMED_QUARANTINE",
                "flow": {
                    "source": f"{s_ip}:{s_port}",
                    "destination": f"{d_ip}:{d_port}",
                    "protocol": p_str,
                },
                "action": "XDP_DROP",
            }
            cb(event_dict)

        self._bpf["drop_events"].open_ring_buffer(_handle_ringbuf_event)
        print(json.dumps({"level": "info", "msg": "Polling for drop events (Ctrl+C to exit)..."}))
        sys.stdout.flush()
        try:
            while True:
                self._bpf.ring_buffer_poll()
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="AEIB eBPF XDP 5-Tuple Quarantine Controller — Physical wire suppression at T_0"
    )
    parser.add_argument("--iface", default="lo", help="Network interface to attach XDP to (default: lo)")
    parser.add_argument(
        "--add-flow",
        nargs=5,
        metavar=("SRC_IP", "SRC_PORT", "DST_IP", "DST_PORT", "PROTO"),
        help="Quarantine a 5-tuple flow (triggers XDP_DROP)",
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
    parser.add_argument("--simulate", action="store_true", help="Force userspace simulation mode")

    args = parser.parse_args()

    # Display schema contract structure if no operational arguments provided
    if not (args.add_flow or args.remove_flow or args.list or args.clear or args.listen):
        print("[!] Displaying compiled 5-Tuple schema contract structure:")
        print(f"    Key struct size: {ctypes.sizeof(Flow5Tuple)} bytes (saddr, daddr, sport, dport, proto)")
        print(f"    Event struct size: {ctypes.sizeof(DropEvent)} bytes (Ringbuf telemetry payload)")
        print("\nUse --help for CLI execution options, or --add-flow to quarantine a route.\n")
        return

    controller = XdpQuarantineController(
        iface=args.iface,
        force_simulate=args.simulate,
    )

    try:
        if args.add_flow:
            s_ip, s_port, d_ip, d_port, proto = args.add_flow
            controller.add_flow(s_ip, int(s_port), d_ip, int(d_port), int(proto))
            p_str = proto_name(int(proto))
            print(json.dumps({
                "level": "info",
                "msg": "Quarantine map updated",
                "src": f"{s_ip}:{s_port}",
                "dst": f"{d_ip}:{d_port}",
                "proto": p_str,
            }))
            sys.stdout.flush()
            # If add-flow is called without detach, immediately poll events
            controller.poll_events()

        elif args.remove_flow:
            s_ip, s_port, d_ip, d_port, proto = args.remove_flow
            removed = controller.remove_flow(s_ip, int(s_port), d_ip, int(d_port), int(proto))
            p_str = proto_name(int(proto))
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

        elif args.listen:
            controller.poll_events()

    finally:
        if not args.add_flow and not args.listen:
            controller.detach()


if __name__ == "__main__":
    main()
