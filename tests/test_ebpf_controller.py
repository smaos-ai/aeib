#!/usr/bin/env python3
r"""
test_ebpf_controller.py
Unit tests for ebpf/controller.py and ebpf/xdp_drop.c integrity.
Verifies IP serialization, quarantine map operations, simulation mode,
and existence of valid kernel XDP C source files.
"""

import os
import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ebpf.controller import (
    XdpQuarantineController,
    ip_to_u32,
    u32_to_ip,
    XDP_SOURCE_FILE,
)


class TestEbpfController(unittest.TestCase):
    """Verifies eBPF XDP controller logic and XDP source integrity."""

    def setUp(self):
        self.controller = XdpQuarantineController(iface="lo", force_simulate=True)

    def tearDown(self):
        self.controller.detach()

    def test_ip_to_u32_and_roundtrip(self):
        """Converts between string IP and 32-bit unsigned integers accurately."""
        test_ips = ["127.0.0.1", "127.0.0.2", "10.0.0.1", "192.168.1.254", "255.255.255.255"]
        for ip in test_ips:
            u32_val = ip_to_u32(ip)
            self.assertIsInstance(u32_val, int)
            self.assertGreaterEqual(u32_val, 0)
            self.assertLessEqual(u32_val, 0xFFFFFFFF)
            reconstructed = u32_to_ip(u32_val)
            self.assertEqual(reconstructed, ip)

    def test_add_and_query_quarantine(self):
        """Adding target IP marks it quarantined with status 1."""
        target_ip = "127.0.0.2"
        self.assertFalse(self.controller.is_quarantined(target_ip))

        self.controller.add_quarantine(target_ip)
        self.assertTrue(self.controller.is_quarantined(target_ip))

        entries = self.controller.list_quarantine()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0], (target_ip, 1))

    def test_remove_quarantine(self):
        """Removing IP clears quarantine status; unknown IP returns False."""
        target_ip = "10.10.10.10"
        self.controller.add_quarantine(target_ip)
        self.assertTrue(self.controller.is_quarantined(target_ip))

        # Successful removal
        removed = self.controller.remove_quarantine(target_ip)
        self.assertTrue(removed)
        self.assertFalse(self.controller.is_quarantined(target_ip))

        # Repeat removal returns False
        removed_again = self.controller.remove_quarantine(target_ip)
        self.assertFalse(removed_again)

    def test_clear_all_quarantine(self):
        """Clearing map removes all entries."""
        for i in range(1, 5):
            self.controller.add_quarantine(f"192.168.10.{i}")

        self.assertEqual(len(self.controller.list_quarantine()), 4)
        self.controller.clear_all()
        self.assertEqual(len(self.controller.list_quarantine()), 0)

    def test_xdp_source_c_file_exists_and_valid(self):
        """Validates that xdp_drop.c exists and contains required symbols."""
        self.assertTrue(XDP_SOURCE_FILE.exists(), f"XDP source file missing at {XDP_SOURCE_FILE}")
        content = XDP_SOURCE_FILE.read_text(encoding="utf-8")

        self.assertIn("BPF_HASH(quarantine_map, u32, u32);", content)
        self.assertIn("int xdp_drop_quarantined(struct xdp_md *ctx)", content)
        self.assertIn("XDP_DROP", content)
        self.assertIn("XDP_PASS", content)


if __name__ == "__main__":
    unittest.main()
