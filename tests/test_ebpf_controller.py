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

try:
    from ebpf.controller import (
        XdpQuarantineController,
        Flow5Tuple,
        DropEvent,
        ip_to_u32,
        format_ip,
        proto_name,
        TCP,
        UDP,
        ICMP,
        XDP_SOURCE_FILE,
    )
except ImportError:
    from controller import (
        XdpQuarantineController,
        Flow5Tuple,
        DropEvent,
        ip_to_u32,
        format_ip,
        proto_name,
        TCP,
        UDP,
        ICMP,
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
        self.assertFalse(self.controller.is_quarantined("10.0.2.15", 49210, "10.0.2.2", 8080, 6))

        self.controller.add_flow("10.0.2.15", 49210, "10.0.2.2", 8080, 6, 1)
        self.assertTrue(self.controller.is_quarantined("10.0.2.15", 49210, "10.0.2.2", 8080, 6))

        # Different source port (probe socket) is NOT quarantined (Deadlock Prevention)
        self.assertFalse(self.controller.is_quarantined("10.0.2.15", 51000, "10.0.2.2", 8080, 6))

        entries = self.controller.list_quarantine()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "10.0.2.15:49210")
        self.assertEqual(entries[0]["destination"], "10.0.2.2:8080")
        self.assertEqual(entries[0]["protocol"], "TCP")
        self.assertEqual(entries[0]["status"], 1)

    def test_remove_quarantine_flow(self):
        """Removing flow clears quarantine; unknown flow returns False."""
        self.controller.add_flow("192.168.1.10", 3000, "192.168.1.20", 5432, 6)
        self.assertTrue(self.controller.is_quarantined("192.168.1.10", 3000, "192.168.1.20", 5432, 6))

        # Successful removal
        removed = self.controller.remove_flow("192.168.1.10", 3000, "192.168.1.20", 5432, 6)
        self.assertTrue(removed)
        self.assertFalse(self.controller.is_quarantined("192.168.1.10", 3000, "192.168.1.20", 5432, 6))

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
        """Validates that xdp_drop.c contains the 4 C Structural Fixes."""
        self.assertTrue(XDP_SOURCE_FILE.exists(), f"XDP source file missing at {XDP_SOURCE_FILE}")
        content = XDP_SOURCE_FILE.read_text(encoding="utf-8")

        # FIX 1: Endian helpers
        self.assertIn("bpf/bpf_endian.h", content)

        # 5-tuple struct and quarantine map with pad[3]
        self.assertIn("struct flow_5tuple", content)
        self.assertIn("pad[3]", content)
        self.assertIn("quarantine_map", content)

        # FIX 2: Verifier-safe pointer derivation
        self.assertIn("struct iphdr *iph = (void *)(eth + 1);", content)
        self.assertIn("(void *)iph + (iph->ihl * 4)", content)

        # FIX 3: Conservative fragment drop guard
        self.assertIn("0x3FFF", content)

        # FIX 4: Reject malformed IHL
        self.assertIn("iph->ihl < 5", content)

        # Ringbuf events map and handler
        self.assertIn("events SEC(\".maps\");", content)
        self.assertIn("xdp_drop_func", content)
        self.assertIn("bpf_ringbuf_reserve", content)
        self.assertIn("bpf_ringbuf_submit", content)
        self.assertIn("XDP_DROP", content)
        self.assertIn("XDP_PASS", content)

    def test_quarantine_5tuple_probe_isolation(self):
        """
        Proof of Fix: Adding key {127.0.0.1:49210 -> 127.0.0.1:8080, TCP} makes
        is_quarantined(127.0.0.1, 49210, 127.0.0.1, 8080, TCP) == True while
        is_quarantined(127.0.0.1, 51000, 127.0.0.1, 8080, TCP) == False.
        """
        self.controller.add("127.0.0.1", 49210, "127.0.0.1", 8080, TCP)
        self.assertTrue(self.controller.is_quarantined("127.0.0.1", 49210, "127.0.0.1", 8080, TCP))
        self.assertFalse(self.controller.is_quarantined("127.0.0.1", 51000, "127.0.0.1", 8080, TCP))

        # Also verifies string protocol alias 'TCP'
        self.assertTrue(self.controller.is_quarantined("127.0.0.1", 49210, "127.0.0.1", 8080, "TCP"))
        self.assertFalse(self.controller.is_quarantined("127.0.0.1", 51000, "127.0.0.1", 8080, "TCP"))


def test_5tuple_isolation():
    """Prove that quarantine is scoped to exact 5-tuple, not just destination IP."""
    c = XdpQuarantineController(iface='lo', force_simulate=True)
    
    # Quarantine a specific flow
    c.add_flow('127.0.0.1', 49210, '127.0.0.1', 8080, 6, 1)
    
    # Same 5-tuple → quarantined
    assert c.is_quarantined('127.0.0.1', 49210, '127.0.0.1', 8080, 6) is True, \
        "Exact 5-tuple should be quarantined"
    
    # Different source port → NOT quarantined (probe should pass)
    assert c.is_quarantined('127.0.0.1', 51000, '127.0.0.1', 8080, 6) is False, \
        "Different source port should NOT be quarantined"
    
    # Different destination port → NOT quarantined
    assert c.is_quarantined('127.0.0.1', 49210, '127.0.0.1', 8081, 6) is False, \
        "Different destination port should NOT be quarantined"
    
    # Different protocol → NOT quarantined
    assert c.is_quarantined('127.0.0.1', 49210, '127.0.0.1', 8080, 17) is False, \
        "Different protocol should NOT be quarantined"


def test_add_remove_flow():
    """Prove add and remove lifecycle."""
    c = XdpQuarantineController(iface='lo', force_simulate=True)
    c.add_flow('192.168.1.10', 3000, '192.168.1.20', 5432, 6, 1)
    assert c.is_quarantined('192.168.1.10', 3000, '192.168.1.20', 5432, 6) is True
    assert c.remove_flow('192.168.1.10', 3000, '192.168.1.20', 5432, 6) is True
    assert c.is_quarantined('192.168.1.10', 3000, '192.168.1.20', 5432, 6) is False


if __name__ == "__main__":
    unittest.main()
