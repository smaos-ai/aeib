#!/usr/bin/env python3
r"""
test_ebpf_controller.py
Unit tests for ebpf/controller.py and ebpf/xdp_drop.c integrity.
Verifies 5-tuple flow serialization, zero-initialization, quarantine operations,
simulation mode, and structural fixes in kernel XDP C source files.
"""

import os
import sys
import ctypes
import unittest
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ebpf.controller import (
    XdpQuarantineController,
    Flow5Tuple,
    DropEvent,
    format_ip,
    proto_name,
    XDP_SOURCE_FILE,
)


class TestEbpfController(unittest.TestCase):
    """Verifies eBPF XDP 5-tuple controller logic and XDP source integrity."""

    def setUp(self):
        self.controller = XdpQuarantineController(iface="lo", force_simulate=True)

    def tearDown(self):
        self.controller.detach()

    def test_struct_sizes_contract(self):
        """Validates that Flow5Tuple is 16 bytes and DropEvent is 32 bytes."""
        self.assertEqual(ctypes.sizeof(Flow5Tuple), 16)
        self.assertEqual(ctypes.sizeof(DropEvent), 32)

    def test_build_flow_key_network_order_and_zero_init(self):
        """Verifies network byte order and zeroed memory (Correction 1 & 2)."""
        key = self.controller.build_flow_key(
            src_ip="10.0.2.15",
            src_port=49210,
            dst_ip="10.0.2.2",
            dst_port=8080,
            proto=6,
        )
        self.assertEqual(ctypes.sizeof(key), 16)
        raw_bytes = bytes(key)
        self.assertEqual(len(raw_bytes), 16)

        # Byte 0-3: 10.0.2.15 in network order -> 0x0a, 0x00, 0x02, 0x0f
        self.assertEqual(list(raw_bytes[:4]), [10, 0, 2, 15])
        # Byte 4-7: 10.0.2.2 in network order -> 0x0a, 0x00, 0x02, 0x02
        self.assertEqual(list(raw_bytes[4:8]), [10, 0, 2, 2])
        # Byte 12: proto = 6
        self.assertEqual(raw_bytes[12], 6)
        # Byte 13, 14, 15: explicit zero padding (Correction 2)
        self.assertEqual(list(raw_bytes[13:]), [0, 0, 0])

    def test_add_and_query_quarantine_flow(self):
        """Adding target 5-tuple marks it quarantined with status 1."""
        self.assertFalse(self.controller.is_flow_quarantined("10.0.2.15", 49210, "10.0.2.2", 8080, 6))

        self.controller.add_flow("10.0.2.15", 49210, "10.0.2.2", 8080, 6)
        self.assertTrue(self.controller.is_flow_quarantined("10.0.2.15", 49210, "10.0.2.2", 8080, 6))

        # Different source port (probe socket) is NOT quarantined (Deadlock Prevention)
        self.assertFalse(self.controller.is_flow_quarantined("10.0.2.15", 51000, "10.0.2.2", 8080, 6))

        entries = self.controller.list_quarantine()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "10.0.2.15:49210")
        self.assertEqual(entries[0]["destination"], "10.0.2.2:8080")
        self.assertEqual(entries[0]["protocol"], "TCP")
        self.assertEqual(entries[0]["status"], 1)

    def test_remove_quarantine_flow(self):
        """Removing flow clears quarantine; unknown flow returns False."""
        self.controller.add_flow("192.168.1.10", 3000, "192.168.1.20", 5432, 6)
        self.assertTrue(self.controller.is_flow_quarantined("192.168.1.10", 3000, "192.168.1.20", 5432, 6))

        # Successful removal
        removed = self.controller.remove_flow("192.168.1.10", 3000, "192.168.1.20", 5432, 6)
        self.assertTrue(removed)
        self.assertFalse(self.controller.is_flow_quarantined("192.168.1.10", 3000, "192.168.1.20", 5432, 6))

        # Repeat removal returns False
        removed_again = self.controller.remove_flow("192.168.1.10", 3000, "192.168.1.20", 5432, 6)
        self.assertFalse(removed_again)

    def test_clear_all_quarantine(self):
        """Clearing map removes all entries."""
        for port in range(8001, 8005):
            self.controller.add_flow("10.0.0.1", port, "10.0.0.2", 8080, 6)

        self.assertEqual(len(self.controller.list_quarantine()), 4)
        self.controller.clear_all()
        self.assertEqual(len(self.controller.list_quarantine()), 0)

    def test_xdp_source_c_file_structural_fixes(self):
        """Validates that xdp_drop.c contains the 4 Structural Fixes."""
        self.assertTrue(XDP_SOURCE_FILE.exists(), f"XDP source file missing at {XDP_SOURCE_FILE}")
        content = XDP_SOURCE_FILE.read_text(encoding="utf-8")

        # Correction 1 & 2: 5-tuple struct and hash map
        self.assertIn("struct flow_5tuple", content)
        self.assertIn("BPF_HASH(quarantine_map, struct flow_5tuple, u32);", content)

        # Correction 3: Dynamic IHL calculation & Fragment guards
        self.assertIn("ip->ihl * 4", content)
        self.assertIn("IP_OFFSET | IP_MF", content)

        # Correction 4: 1 MiB Ringbuf output definition (256 pages)
        self.assertIn("BPF_RINGBUF_OUTPUT(drop_events, 256);", content)
        self.assertIn("ringbuf_output", content)
        self.assertIn("XDP_DROP", content)
        self.assertIn("XDP_PASS", content)


if __name__ == "__main__":
    unittest.main()
