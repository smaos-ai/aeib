#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
benchmarks/iphone_notary_latency_benchmark.py
================================================================================
Empirical Latency and Throughput Benchmark for Apple Silicon Notary Components.

Evaluated under the stated model (A18 Pro Secure Enclave + Mac M3 Pro verifier).
Adheres to strict epistemic constraints:
  - Measures across 3 payload sizes (Small: ~150B, Medium: ~1.5KB, Large: ~15KB).
  - All latencies reported in integer microseconds (us).
  - All summary rates reported in integer basis points (bps) or integer ops/sec.
  - Zero floats in RFC 8785 JCS canonical digests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    sha256_jcs_caid,
)
from src.iphone_rpc_client import IPhoneNotaryRPCClient
from src.jcs_canonicalizer import encode_jcs


def _generate_p256_keypair() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return priv, pub_bytes.hex()


def _percentile_us(samples_ns: List[int], p: float) -> int:
    """Calculates percentile in integer microseconds."""
    if not samples_ns:
        return 0
    s = sorted(samples_ns)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    val_ns = int(s[f] + (k - f) * (s[c] - s[f]))
    return val_ns // 1000


def benchmark_jcs_and_verification(
    trials_per_size: int = 1000,
) -> Dict[str, Any]:
    """Measures JCS canonicalization and NIST P-256 verification latency across 3 input sizes."""
    priv, pub_hex = _generate_p256_keypair()

    sizes = [
        ("small_200B", "T3_WIRE_TRANSFER", 100_000, "https://internal/vault/small"),
        ("medium_2KB", "T3_BATCH_ESCROW", 5_000_000, "https://internal/vault/medium/" + "x" * 1800),
        ("large_20KB", "T3_GLOBAL_SETTLEMENT", 50_000_000, "https://internal/vault/large/" + "y" * 19800),
    ]

    results: Dict[str, Any] = {}

    for size_label, action_prefix, amount, target_resource in sizes:
        proposal = T3ActionProposal(
            action_type=f"{action_prefix}_{size_label}",
            amount_minor=amount,
            attempt_fence=1,
            expires_at_epoch_sec=2000000000,
            intent_caid=f"caid_{size_label}",
            operation_id=f"op_{size_label}",
            target_resource=target_resource,
        )
        canonical_bytes = proposal.to_canonical_jcs_bytes()
        sig_der = priv.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))

        warrant = EnclaveSignedWarrant(
            canonical_payload_utf8=canonical_bytes.decode("utf-8"),
            payload_sha256_caid=sha256_jcs_caid(canonical_bytes),
            public_key_x963_hex=pub_hex,
            signature_der_hex=sig_der.hex(),
            algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
        )

        # 1. Benchmark JCS serialization
        jcs_latencies_ns: List[int] = []
        for _ in range(trials_per_size):
            t0 = time.perf_counter_ns()
            _ = proposal.to_canonical_jcs_bytes()
            t1 = time.perf_counter_ns()
            jcs_latencies_ns.append(t1 - t0)

        # 2. Benchmark P-256 verification
        verify_latencies_ns: List[int] = []
        for _ in range(trials_per_size):
            t0 = time.perf_counter_ns()
            verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
                expected_proposal=proposal,
                warrant=warrant,
                pinned_enclave_pubkey_x963_hex=pub_hex,
                current_epoch_sec=1900000000,
            )
            t1 = time.perf_counter_ns()
            if not verdict.latch_released:
                raise RuntimeError(f"Verification benchmark failed on size {size_label}")
            verify_latencies_ns.append(t1 - t0)

        results[size_label] = {
            "payload_bytes": len(canonical_bytes),
            "jcs_median_us": _percentile_us(jcs_latencies_ns, 0.50),
            "jcs_p95_us": _percentile_us(jcs_latencies_ns, 0.95),
            "jcs_p99_us": _percentile_us(jcs_latencies_ns, 0.99),
            "p256_verify_median_us": _percentile_us(verify_latencies_ns, 0.50),
            "p256_verify_p95_us": _percentile_us(verify_latencies_ns, 0.95),
            "p256_verify_p99_us": _percentile_us(verify_latencies_ns, 0.99),
        }

    return results


def benchmark_loopback_rpc_throughput(rounds: int = 50) -> Dict[str, Any]:
    """Measures local HTTP loopback warrant round-trip latency."""
    priv, pub_hex = _generate_p256_keypair()

    class LoopbackHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/approve":
                length = int(self.headers.get("Content-Length", 0))
                payload = self.rfile.read(length)
                caid = sha256_jcs_caid(payload)
                sig = priv.sign(payload, ec.ECDSA(hashes.SHA256()))
                resp = json.dumps({
                    "canonical_payload_utf8": payload.decode("utf-8"),
                    "payload_sha256_caid": caid,
                    "public_key_x963_hex": pub_hex,
                    "signature_der_hex": sig.hex(),
                    "algorithm": "ECDSA_P256_SHA256_SECURE_ENCLAVE",
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), LoopbackHandler)
    port = server.server_port
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()

    rpc_client = IPhoneNotaryRPCClient(
        iphone_host="127.0.0.1",
        port=port,
        pinned_enclave_pubkey_x963_hex=pub_hex,
    )

    proposal = T3ActionProposal(
        action_type="T3_LOOPBACK_BENCH",
        amount_minor=50000,
        attempt_fence=1,
        expires_at_epoch_sec=2000000000,
        intent_caid="caid_loopback",
        operation_id="op_loopback",
        target_resource="https://internal/loopback",
    )

    latencies_ns: List[int] = []
    success_count = 0

    for _ in range(rounds):
        t0 = time.perf_counter_ns()
        verdict = rpc_client.request_faceid_warrant(
            proposal=proposal,
            timeout_sec=5,
            current_epoch_sec=1900000000,
        )
        t1 = time.perf_counter_ns()
        if verdict.latch_released:
            success_count += 1
            latencies_ns.append(t1 - t0)

    server.shutdown()
    server.server_close()

    success_bps = (success_count * 10000) // rounds
    return {
        "trials": rounds,
        "success_count": success_count,
        "success_rate_bps": success_bps,
        "loopback_roundtrip_median_us": _percentile_us(latencies_ns, 0.50),
        "loopback_roundtrip_p95_us": _percentile_us(latencies_ns, 0.95),
    }


def run_benchmark(trials_per_size: int = 500, loopback_rounds: int = 50) -> Dict[str, Any]:
    print("Running cryptographic and JCS latency benchmarks across 3 input sizes...")
    crypto_bench = benchmark_jcs_and_verification(trials_per_size=trials_per_size)

    print("Running HTTP loopback RPC round-trip benchmark...")
    loopback_bench = benchmark_loopback_rpc_throughput(rounds=loopback_rounds)

    summary: Dict[str, Any] = {
        "benchmark_name": "apple_silicon_notary_latency_v1",
        "crypto_and_jcs": crypto_bench,
        "loopback_rpc": loopback_bench,
    }

    summary_canonical_bytes = encode_jcs(summary)
    run_digest = hashlib.sha256(summary_canonical_bytes).hexdigest()
    summary["run_digest_sha256"] = run_digest

    return summary


def run_all_benchmarks(trials: int = 500, loopback_rounds: int = 50, trials_per_size: Optional[int] = None) -> Dict[str, Any]:
    """Compatibility runner for test suites and programmatic benchmarks."""
    t = trials_per_size if trials_per_size is not None else trials
    return run_benchmark(trials_per_size=t, loopback_rounds=loopback_rounds)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Apple Silicon Notary Latency Benchmark")
    parser.add_argument("--trials", type=int, default=500, help="Trials per size for crypto benchmarks")
    parser.add_argument("--loopback-rounds", type=int, default=50, help="Rounds for RPC loopback benchmark")
    parser.add_argument("--json", action="store_true", help="Print raw JCS JSON output")
    args = parser.parse_args(argv)

    summary = run_benchmark(trials_per_size=args.trials, loopback_rounds=args.loopback_rounds)

    if args.json:
        print(encode_jcs(summary).decode("utf-8"))
        return 0

    print("\n" + "=" * 80)
    print("  APPLE SILICON NOTARY LATENCY & THROUGHPUT BENCHMARK RESULTS")
    print("=" * 80)
    print(f"  Run Digest (SHA-256): {summary['run_digest_sha256']}")
    print("-" * 80)
    print(f"  {'Payload Size':<16} | {'Bytes':<8} | {'JCS Med (us)':<12} | {'JCS p95':<8} | {'P-256 Med (us)':<14} | {'P-256 p95':<10}")
    print("-" * 80)
    for size, data in summary["crypto_and_jcs"].items():
        print(
            f"  {size:<16} | {data['payload_bytes']:<8} | "
            f"{data['jcs_median_us']:<12} | {data['jcs_p95_us']:<8} | "
            f"{data['p256_verify_median_us']:<14} | {data['p256_verify_p95_us']:<10}"
        )
    print("-" * 80)
    loop = summary["loopback_rpc"]
    print(
        f"  Loopback RPC ({loop['trials']} trials): Success = {loop['success_rate_bps']} bps | "
        f"Median = {loop['loopback_roundtrip_median_us']} us | p95 = {loop['loopback_roundtrip_p95_us']} us"
    )
    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
