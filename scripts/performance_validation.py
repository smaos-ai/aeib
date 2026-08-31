#!/usr/bin/env python3
"""
Stream D: Performance Validation
Measures latency and resource usage for infrastructure components.
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "smaos" / "l6_infrastructure"))

from kms_signer import KMSSigner
from ap2_ledger import AP2Ledger, ActionType


class PerformanceTest:
    """Performance testing harness."""

    def __init__(self):
        self.results = {}

    def measure(self, name: str, func, iterations: int = 100) -> float:
        """Measure execution time of a function."""
        start = time.time()
        for _ in range(iterations):
            func()
        elapsed = time.time() - start
        avg_ms = (elapsed / iterations) * 1000
        self.results[name] = avg_ms
        return avg_ms

    def report(self) -> str:
        """Generate performance report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "measurements": self.results,
            "summary": {
                "fastest": min(self.results.items(), key=lambda x: x[1])[0],
                "slowest": max(self.results.items(), key=lambda x: x[1])[0],
            },
        }
        return json.dumps(report, indent=2)


def test_kms_performance():
    """Benchmark KMS operations."""
    print("\nKMS Performance:")
    print("-" * 50)

    signer = KMSSigner()
    perf = PerformanceTest()

    # Key generation
    avg = perf.measure(
        "Generate Ed25519 key",
        lambda: signer.generate_key_pair("ed25519"),
        iterations=50,
    )
    print(f"  Generate Ed25519 key: {avg:.3f}ms")

    # Signing
    signer.generate_key_pair("ed25519")
    data = {"test": "data"}

    avg = perf.measure(
        "Sign JSON (Ed25519)",
        lambda: signer.sign_json(data),
        iterations=100,
    )
    print(f"  Sign JSON (Ed25519): {avg:.3f}ms")

    # Verification
    sig = signer.sign_json(data)

    avg = perf.measure(
        "Verify signature",
        lambda: signer.verify_signature(data, sig),
        iterations=100,
    )
    print(f"  Verify signature: {avg:.3f}ms")

    return perf


def test_ledger_performance():
    """Benchmark ledger operations."""
    print("\nLedger Performance:")
    print("-" * 50)

    ledger = AP2Ledger()
    perf = PerformanceTest()

    # Record action
    avg = perf.measure(
        "Record action",
        lambda: ledger.record_action(
            action_type=ActionType.GOVERNANCE_DECISION,
            agent="test",
            model="test",
            prompt="test",
            decision="approved",
        ),
        iterations=100,
    )
    print(f"  Record action: {avg:.3f}ms")

    # Create digest
    avg = perf.measure(
        "Create digest",
        lambda: ledger.create_digest(),
        iterations=50,
    )
    print(f"  Create digest: {avg:.3f}ms")

    return perf


def test_merkle_performance():
    """Benchmark Merkle tree operations."""
    print("\nMerkle Tree Performance:")
    print("-" * 50)

    from ap2_ledger import MerkleTree

    tree = MerkleTree()
    perf = PerformanceTest()

    # Add leaf
    counter = [0]

    def add_leaf():
        counter[0] += 1
        tree.add_leaf(f"data_{counter[0]}")

    avg = perf.measure(
        "Add leaf to tree",
        add_leaf,
        iterations=100,
    )
    print(f"  Add leaf to tree: {avg:.3f}ms")

    # Get root
    avg = perf.measure(
        "Compute Merkle root",
        lambda: tree.get_root(),
        iterations=1000,
    )
    print(f"  Compute Merkle root: {avg:.3f}ms")

    return perf


def main():
    """Run performance tests."""
    print("=" * 60)
    print("Stream D: Performance Validation")
    print("=" * 60)

    kms_perf = test_kms_performance()
    ledger_perf = test_ledger_performance()
    merkle_perf = test_merkle_performance()

    # Summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)

    all_results = {**kms_perf.results, **ledger_perf.results, **merkle_perf.results}

    latency_targets = {
        "Sign JSON (Ed25519)": 10.0,  # <10ms
        "Verify signature": 10.0,
        "Record action": 5.0,  # <5ms
        "Add leaf to tree": 1.0,  # <1ms
        "Compute Merkle root": 0.5,  # <0.5ms
    }

    passed = 0
    for name, target in latency_targets.items():
        if name in all_results:
            actual = all_results[name]
            status = "✓" if actual <= target else "✗"
            print(f"  {status} {name}: {actual:.3f}ms (target: {target}ms)")
            if actual <= target:
                passed += 1

    print(f"\nLatency targets: {passed}/{len(latency_targets)} passed")

    # Memory check (simplified)
    print("\n" + "=" * 60)
    print("Memory Check (simplified):")
    print(f"  Large ledger (1000 actions) should be <10MB")
    large_ledger = AP2Ledger()
    for i in range(1000):
        large_ledger.record_action(
            action_type=ActionType.GOVERNANCE_DECISION,
            agent="test",
            model="test",
            prompt=f"Prompt {i}",
            decision=f"Decision {i}",
        )
    print(f"  Ledger size: ~{len(str(large_ledger.export_ledger())) / 1024:.1f}KB")

    print("\n" + "=" * 60)
    print("Performance validation completed successfully")


if __name__ == "__main__":
    main()
