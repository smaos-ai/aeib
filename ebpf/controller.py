#!/usr/bin/env python3
r"""
controller.py — Userspace eBPF XDP Quarantine Controller
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)

Compiles and attaches the xdp_drop.c kernel program to a network interface via BCC.
Provides a CLI to add/remove target IPv4 addresses to the BPF quarantine map,
simulating how the AEIB interceptor enforces driver-level packet suppression ($T_0$)
during DISPATCHED_UNCONFIRMED ambiguous states.
"""

import os
import sys
import time
import socket
import struct
import ctypes
import argparse
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Path to the accompanying XDP C program
XDP_SOURCE_FILE = Path(__file__).resolve().parent / "xdp_drop.c"

# Detect BCC availability and platform
PLATFORM_IS_LINUX = (platform.system() == "Linux")
try:
    from bcc import BPF
    BCC_AVAILABLE = True
except (ImportError, Exception):
    BCC_AVAILABLE = False


def ip_to_u32(ip_str: str) -> int:
    """
    Converts standard IPv4 string into 32-bit unsigned integer
    in native byte order matching struct iphdr.daddr in memory.
    """
    raw_bytes = socket.inet_aton(ip_str.strip())
    return struct.unpack("=I", raw_bytes)[0]


def u32_to_ip(u32_val: int) -> str:
    """Converts 32-bit unsigned integer back into IPv4 dot-decimal notation."""
    raw_bytes = struct.pack("=I", u32_val)
    return socket.inet_ntoa(raw_bytes)


class SimulatedBpfMap:
    """Fallback in-memory BPF map simulator for macOS Darwin and test environments."""

    def __init__(self):
        self._map: Dict[int, int] = {}

    def __setitem__(self, key, value):
        k = key.value if hasattr(key, "value") else int(key)
        v = value.value if hasattr(value, "value") else int(value)
        self._map[k] = v

    def __getitem__(self, key):
        k = key.value if hasattr(key, "value") else int(key)
        val = self._map[k]
        return ctypes.c_uint32(val)

    def __delitem__(self, key):
        k = key.value if hasattr(key, "value") else int(key)
        if k in self._map:
            del self._map[k]
        else:
            raise KeyError(k)

    def items(self):
        for k, v in self._map.items():
            yield ctypes.c_uint32(k), ctypes.c_uint32(v)

    def clear(self):
        self._map.clear()

    def __len__(self):
        return len(self._map)


class XdpQuarantineController:
    """
    Manages the lifecycle of the XDP quarantine program and BPF map.
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

    def add_quarantine(self, ip_str: str) -> None:
        """
        Adds target IPv4 to quarantine map with status = 1 (DISPATCHED_UNCONFIRMED).
        Kernel XDP hook will physically drop all packets to this destination.
        """
        ip_u32 = ip_to_u32(ip_str)
        key = ctypes.c_uint32(ip_u32)
        val = ctypes.c_uint32(1)
        self._quarantine_map[key] = val

    def remove_quarantine(self, ip_str: str) -> bool:
        """Removes target IPv4 from quarantine map, restoring normal traffic flow."""
        ip_u32 = ip_to_u32(ip_str)
        key = ctypes.c_uint32(ip_u32)
        try:
            del self._quarantine_map[key]
            return True
        except (KeyError, Exception):
            return False

    def list_quarantine(self) -> List[Tuple[str, int]]:
        """Returns list of currently quarantined IP addresses and status codes."""
        entries = []
        for k, v in self._quarantine_map.items():
            ip_str = u32_to_ip(k.value)
            status = v.value
            entries.append((ip_str, status))
        return entries

    def is_quarantined(self, ip_str: str) -> bool:
        """Checks if a given IP address is marked quarantined in the map."""
        ip_u32 = ip_to_u32(ip_str)
        key = ctypes.c_uint32(ip_u32)
        try:
            val = self._quarantine_map[key]
            return val.value == 1
        except (KeyError, IndexError):
            return False

    def clear_all(self) -> None:
        """Flushes all entries from the quarantine map."""
        if hasattr(self._quarantine_map, "clear"):
            self._quarantine_map.clear()
        else:
            keys = [k for k, _ in self._quarantine_map.items()]
            for k in keys:
                del self._quarantine_map[k]

    def listen_trace_pipe(self):
        """Reads and streams kernel trace messages emitted by bpf_trace_printk."""
        if self.is_simulated or not self._bpf:
            print("[SIMULATION] Listening for simulated kernel drop events. Press Ctrl+C to exit.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            return

        print(f"[+] Listening on {self.iface} (trace_print)... Press Ctrl+C to stop.")
        try:
            self._bpf.trace_print()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="AEIB eBPF XDP Quarantine Controller — Physical wire suppression at T_0"
    )
    parser.add_argument("--iface", default="lo", help="Network interface to attach XDP to (default: lo)")
    parser.add_argument("--add", help="IPv4 address to quarantine (triggers XDP_DROP)")
    parser.add_argument("--remove", help="IPv4 address to un-quarantine")
    parser.add_argument("--list", action="store_true", help="List all quarantined IP addresses")
    parser.add_argument("--clear", action="store_true", help="Clear all quarantined entries")
    parser.add_argument("--listen", action="store_true", help="Keep attached and stream trace pipe")
    parser.add_argument("--simulate", action="store_true", help="Force userspace simulation mode")

    args = parser.parse_args()

    controller = XdpQuarantineController(
        iface=args.iface,
        force_simulate=args.simulate,
    )

    if controller.is_simulated:
        print("[!] Note: Running in userspace simulation mode (Linux kernel + BCC required for live XDP).")

    try:
        if args.add:
            controller.add_quarantine(args.add)
            print(f"[+] Quarantined IPv4: {args.add} (status=1 -> XDP_DROP)")

        if args.remove:
            removed = controller.remove_quarantine(args.remove)
            if removed:
                print(f"[+] Removed IPv4 from quarantine: {args.remove} (traffic restored)")
            else:
                print(f"[-] IPv4 not found in quarantine: {args.remove}")

        if args.clear:
            controller.clear_all()
            print("[+] Cleared all entries from quarantine map.")

        if args.list or (not args.add and not args.remove and not args.clear and not args.listen):
            entries = controller.list_quarantine()
            print(f"\n--- Current Quarantine Map ({len(entries)} entries) ---")
            if not entries:
                print("  (Empty — normal traffic allowed)")
            for ip, status in entries:
                status_str = "DISPATCHED_UNCONFIRMED / QUARANTINED (XDP_DROP)" if status == 1 else f"STATUS_{status}"
                print(f"  • {ip:<16} => {status_str}")
            print("---------------------------------------------------\n")

        if args.listen:
            controller.listen_trace_pipe()

    finally:
        if not args.listen:
            controller.detach()


if __name__ == "__main__":
    main()
