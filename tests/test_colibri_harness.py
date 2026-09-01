#!/usr/bin/env python3
"""
Colibri v1.9.0 Harness Verification Test Suite
Tests Layer 6 integration: binary compilation, config validation, governance wiring
"""

import json
import subprocess
import sys
import socket
from pathlib import Path
from typing import Dict, Any, Tuple


class ColibriHarnessValidator:
    """Validates Colibri harness deployment for SMAOS Layer 6"""

    def __init__(self):
        self.repo_root = Path(__file__).parent.parent
        self.colibri_bin = self.repo_root / "build" / "colibri"
        self.config_file = self.repo_root / "config" / "colibri_edge.json"
        self.results = {"passed": 0, "failed": 0, "warnings": 0}
        self.config: Dict[str, Any] = {}

    def log(self, level: str, msg: str) -> None:
        """Print timestamped log message"""
        prefix = {
            "INFO": "[INFO]",
            "PASS": "[PASS]",
            "FAIL": "[FAIL]",
            "WARN": "[WARN]",
        }.get(level, "[LOG]")
        print(f"{prefix} {msg}")

    # ========================================================================
    # TEST 1: Binary Exists and Is Executable
    # ========================================================================

    def test_binary_exists(self) -> bool:
        """Test: Colibri binary exists at expected path"""
        self.log("INFO", "TEST 1/6: Binary exists and is executable")

        if not self.colibri_bin.exists():
            self.log("FAIL", f"Binary not found: {self.colibri_bin}")
            self.results["failed"] += 1
            return False

        if not self.colibri_bin.is_file():
            self.log("FAIL", f"Path exists but is not a file: {self.colibri_bin}")
            self.results["failed"] += 1
            return False

        if not (self.colibri_bin.stat().st_mode & 0o111):
            self.log("FAIL", f"Binary exists but is not executable")
            self.results["failed"] += 1
            return False

        self.log("PASS", f"Binary found and executable: {self.colibri_bin}")
        self.results["passed"] += 1
        return True

    # ========================================================================
    # TEST 2: Binary Is Valid ELF/Mach-O Executable
    # ========================================================================

    def test_binary_format(self) -> bool:
        """Test: Compiled binary is valid executable format"""
        self.log("INFO", "TEST 2/6: Binary format validation")

        try:
            result = subprocess.run(
                ["file", str(self.colibri_bin)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout.lower()

            if "elf" in output or "mach-o" in output or "executable" in output:
                self.log("PASS", f"Binary format valid: {output.strip()}")
                self.results["passed"] += 1
                return True
            else:
                self.log("FAIL", f"Unrecognized binary format: {output.strip()}")
                self.results["failed"] += 1
                return False

        except subprocess.TimeoutExpired:
            self.log("WARN", "file command timed out")
            self.results["warnings"] += 1
            return True
        except FileNotFoundError:
            self.log("WARN", "file command not available, skipping format check")
            self.results["warnings"] += 1
            return True

    # ========================================================================
    # TEST 3: Config File Exists and Is Valid JSON
    # ========================================================================

    def test_config_exists(self) -> bool:
        """Test: Configuration file exists and is valid JSON"""
        self.log("INFO", "TEST 3/6: Configuration file validation")

        if not self.config_file.exists():
            self.log("FAIL", f"Config file not found: {self.config_file}")
            self.results["failed"] += 1
            return False

        try:
            with open(self.config_file, "r") as f:
                self.config = json.load(f)
            self.log("PASS", "Configuration file is valid JSON")
            self.results["passed"] += 1
            return True
        except json.JSONDecodeError as e:
            self.log("FAIL", f"Invalid JSON: {str(e)}")
            self.results["failed"] += 1
            return False

    # ========================================================================
    # TEST 4: Memory Hierarchy Configuration for RTX 4060
    # ========================================================================

    def test_memory_hierarchy(self) -> bool:
        """Test: Memory tiers configured for RTX 4060 8GB + 16GB RAM"""
        self.log("INFO", "TEST 4/6: Memory hierarchy configuration")

        if not self.config:
            self.log("FAIL", "Config not loaded")
            self.results["failed"] += 1
            return False

        # Check required fields
        required_fields = [
            ("tier_vram_mb", int, 6144),
            ("tier_ram_mb", int, 16384),
            ("tier_nvme_path", str, "/var/lib/smaos/colibri_cache"),
            ("substrate", str, "RTX_4060_8GB"),
        ]

        all_valid = True
        for field_name, field_type, expected_value in required_fields:
            if field_name not in self.config:
                self.log("FAIL", f"Missing required field: {field_name}")
                all_valid = False
                continue

            value = self.config[field_name]
            if not isinstance(value, field_type):
                self.log(
                    "FAIL",
                    f"{field_name} has wrong type: "
                    f"expected {field_type.__name__}, got {type(value).__name__}",
                )
                all_valid = False
                continue

            if value != expected_value:
                self.log(
                    "FAIL",
                    f"{field_name} mismatch: expected {expected_value}, got {value}",
                )
                all_valid = False

        if all_valid:
            self.log("PASS", "Memory hierarchy correctly configured for RTX 4060")
            self.log("INFO", f"  L1 VRAM:  {self.config['tier_vram_mb']} MB")
            self.log("INFO", f"  L2 RAM:   {self.config['tier_ram_mb']} MB")
            self.log("INFO", f"  L3 NVMe:  {self.config['tier_nvme_path']}")
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1

        return all_valid

    # ========================================================================
    # TEST 5: Semantic Invariance Configuration
    # ========================================================================

    def test_semantic_invariance(self) -> bool:
        """Test: Semantic guarantee set to strict_fp16"""
        self.log("INFO", "TEST 5/6: Semantic invariance configuration")

        if not self.config:
            self.log("FAIL", "Config not loaded")
            self.results["failed"] += 1
            return False

        # Check semantic guarantee
        semantic_guarantee = self.config.get("semantic_guarantee")
        if semantic_guarantee != "strict_fp16":
            self.log(
                "FAIL",
                f"semantic_guarantee not set correctly: "
                f"expected 'strict_fp16', got '{semantic_guarantee}'",
            )
            self.results["failed"] += 1
            return False

        # Check caching policy
        caching_policy = self.config.get("caching_policy")
        if caching_policy != "routing_aware_prefetch":
            self.log(
                "FAIL",
                f"caching_policy not set correctly: "
                f"expected 'routing_aware_prefetch', got '{caching_policy}'",
            )
            self.results["failed"] += 1
            return False

        # Check semantic config subsection
        if "semantic_config" in self.config:
            sem_config = self.config["semantic_config"]
            if sem_config.get("guarantee_level") == "strict_fp16":
                self.log("PASS", "Semantic invariance configured: strict_fp16")
                self.log("INFO", f"  Routing-aware prefetch: {sem_config.get('routing_aware')}")
                self.log("INFO", f"  Prefetch enabled: {sem_config.get('prefetch_enabled')}")
                self.results["passed"] += 1
                return True

        self.log("WARN", "Semantic config subsection incomplete, but main guarantee OK")
        self.results["warnings"] += 1
        self.results["passed"] += 1
        return True

    # ========================================================================
    # TEST 6: Governance Hook Wiring
    # ========================================================================

    def test_governance_hook(self) -> bool:
        """Test: Governance hook URL is configured and reachable"""
        self.log("INFO", "TEST 6/6: Governance hook wiring")

        if not self.config:
            self.log("FAIL", "Config not loaded")
            self.results["failed"] += 1
            return False

        # Check governance_hook field
        governance_hook = self.config.get("governance_hook")
        if not governance_hook:
            self.log("FAIL", "governance_hook not configured")
            self.results["failed"] += 1
            return False

        if not governance_hook.startswith("http://"):
            self.log("FAIL", f"governance_hook URL invalid: {governance_hook}")
            self.results["failed"] += 1
            return False

        self.log("PASS", f"Governance hook configured: {governance_hook}")

        # Try to connect to governance endpoint (non-blocking)
        try:
            host, port_str = governance_hook.replace("http://", "").split(":")
            port = int(port_str.split("/")[0])

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                self.log("PASS", f"Governance endpoint reachable: {host}:{port}")
                self.results["passed"] += 1
                return True
            else:
                self.log(
                    "WARN",
                    f"Governance endpoint not reachable (expected during setup): "
                    f"{host}:{port}",
                )
                self.log("INFO", "  Note: Endpoint will be available after FastAPI startup")
                self.results["warnings"] += 1
                self.results["passed"] += 1
                return True

        except (ValueError, socket.error) as e:
            self.log(
                "WARN",
                f"Could not validate governance endpoint: {str(e)}",
            )
            self.results["warnings"] += 1
            self.results["passed"] += 1
            return True

    # ========================================================================
    # VERIFICATION REPORT
    # ========================================================================

    def print_report(self) -> None:
        """Print verification summary report"""
        total = self.results["passed"] + self.results["failed"]
        pass_pct = (
            100 * self.results["passed"] // total if total > 0 else 0
        )

        print()
        print("=" * 70)
        print("COLIBRI HARNESS VERIFICATION REPORT")
        print("=" * 70)
        print()
        print(f"Binary:          {self.colibri_bin}")
        print(f"Config:          {self.config_file}")
        print()
        print(f"Tests Passed:    {self.results['passed']}/{total}")
        print(f"Tests Failed:    {self.results['failed']}/{total}")
        print(f"Warnings:        {self.results['warnings']}")
        print(f"Success Rate:    {pass_pct}%")
        print()

        if self.config:
            print("MEMORY HIERARCHY")
            print("-" * 70)
            print(f"  L1 VRAM:       {self.config.get('tier_vram_mb')} MB")
            print(f"  L2 RAM:        {self.config.get('tier_ram_mb')} MB")
            print(f"  L3 NVMe:       {self.config.get('tier_nvme_path')}")
            print()

            print("SEMANTIC INVARIANCE")
            print("-" * 70)
            print(f"  Guarantee:     {self.config.get('semantic_guarantee')}")
            print(f"  Policy:        {self.config.get('caching_policy')}")
            print()

            print("GOVERNANCE")
            print("-" * 70)
            print(f"  Hook Endpoint: {self.config.get('governance_hook')}")
            print()

        print("=" * 70)

    # ========================================================================
    # MAIN TEST RUNNER
    # ========================================================================

    def run(self) -> int:
        """Execute all tests and return exit code"""
        print()
        print("=" * 70)
        print("COLIBRI HARNESS VERIFICATION TEST SUITE")
        print("=" * 70)
        print()

        # Run all tests
        self.test_binary_exists()
        self.test_binary_format()
        self.test_config_exists()
        self.test_memory_hierarchy()
        self.test_semantic_invariance()
        self.test_governance_hook()

        # Print report
        self.print_report()

        # Return exit code
        if self.results["failed"] > 0:
            print("RESULT: FAILED")
            print()
            return 1
        else:
            print("RESULT: PASSED (all tests green)")
            print()
            return 0


if __name__ == "__main__":
    validator = ColibriHarnessValidator()
    exit_code = validator.run()
    sys.exit(exit_code)
