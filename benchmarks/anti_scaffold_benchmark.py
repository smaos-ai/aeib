"""
benchmarks/anti_scaffold_benchmark.py — Empirical benchmark for Anti-Scaffold Falsification Engine.

Under the stated model, this benchmark executes live physical measurements of:
1. Prior-art AST linter throughput across sample modules.
2. Cryptographic track spec bisection and RFC 8785 Ed25519 signing latency.
3. Live experiment oracle multi-seed/multi-scale execution and variance verification.
4. Differential mutation trap kill ratio on candidate verifiers.

Zero hardcoded metric constants; all numbers are calculated from runtime executions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from typing import Any, Dict, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.anti_scaffold_falsifier import (
    DifferentialMutationFalsifier,
    DynamicExperimentSpec,
    LiveExperimentOracle,
    MutationTestCase,
    PreFlightScopeDecoupler,
    PriorArtLinter,
    ScopeTier,
)
from src.jcs_canonicalizer import encode_jcs


def run_benchmark() -> Dict[str, Any]:
    """Execute live physical benchmarks and record elapsed nanoseconds and counts."""
    # 1. Benchmark PriorArtLinter
    sample_code = """
import hashlib

def example_search(query: str, records: list) -> list:
    results = []
    for item in records:
        if query in item["text"]:
            results.append(item)
    return results

def example_hash(data: bytes) -> str:
    h = 0x12345678
    for b in data:
        h = ((h << 3) ^ (h >> 2)) & 0xffffffff
    return hex(h)
"""
    t0_lint = time.perf_counter_ns()
    lint_iterations = 200
    total_findings = 0
    for _ in range(lint_iterations):
        findings = PriorArtLinter.lint_source(sample_code, "bench_sample.py")
        total_findings += len(findings)
    t1_lint = time.perf_counter_ns()
    lint_elapsed_ns = max(1, t1_lint - t0_lint)
    avg_lint_us = (lint_elapsed_ns / lint_iterations) / 1000.0

    # 2. Benchmark PreFlightScopeDecoupler signing & verification
    key = Ed25519PrivateKey.generate()
    decoupler = PreFlightScopeDecoupler(signing_key=key)
    t0_spec = time.perf_counter_ns()
    spec_iterations = 100
    valid_sig_count = 0
    for i in range(spec_iterations):
        spec = decoupler.create_parallel_track_spec(
            track_id=f"TRACK-{i}",
            subsystem_name="BenchmarkSubsystem",
            scope_tier=ScopeTier.TIER_2_PARALLEL_WORKTREE,
            target_worktree_branch="feat/bench",
            boundary_protocol_name="BenchProtocol",
            acceptance_criteria=["Zero mock calls", "Kill ratio >= 9000 bps"],
            target_mutation_kill_bps=9000,
        )
        if spec.verify_signature():
            valid_sig_count += 1
    t1_spec = time.perf_counter_ns()
    spec_elapsed_ns = max(1, t1_spec - t0_spec)
    avg_spec_us = (spec_elapsed_ns / spec_iterations) / 1000.0

    # 3. Benchmark LiveExperimentOracle
    def dynamic_workload(seed: int, scale: int) -> int:
        acc = seed
        for step in range(scale):
            acc = (acc * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return acc

    dyn_spec = DynamicExperimentSpec(
        experiment_name="bench_dynamic_workload",
        target_callable=dynamic_workload,
        seeds=(10, 20, 30),
        scales=(64, 256, 1024),
        declared_effect_profile="CPU_DETERMINISTIC",
    )
    t0_dyn = time.perf_counter_ns()
    dyn_verdict = LiveExperimentOracle.evaluate_dynamic_execution(dyn_spec)
    t1_dyn = time.perf_counter_ns()
    dyn_elapsed_ns = max(1, t1_dyn - t0_dyn)

    # 4. Benchmark DifferentialMutationFalsifier
    nominal_payload = {"amount_minor": 10000, "basis_points": 5000, "caid": "bench_caid"}
    nominal_sig = key.sign(encode_jcs(nominal_payload)).hex()
    pubkey_bytes = key.public_key().public_bytes_raw()

    def robust_verifier(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        payload = data.get("payload")
        sig_hex = data.get("sig")
        pk_hex = data.get("pubkey", pubkey_bytes.hex())
        if not payload or not sig_hex or not pk_hex:
            return False
        bps = payload.get("basis_points")
        if bps is None or bps < 0 or bps > 10000:
            return False
        try:
            sig = bytes.fromhex(sig_hex)
            pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk_hex))
            pk.verify(sig, encode_jcs(payload))
            return True
        except Exception:
            return False

    mutants = DifferentialMutationFalsifier.generate_standard_mutants(
        nominal_payload=nominal_payload,
        nominal_signature_hex=nominal_sig,
    )
    augmented_mutants = [
        MutationTestCase(
            mutation_id=m.mutation_id,
            mutation_class=m.mutation_class,
            mutated_input={"payload": m.mutated_input["payload"], "sig": m.mutated_input["sig"], "pubkey": pubkey_bytes.hex()},
            description=m.description,
        )
        for m in mutants
    ]

    t0_mut = time.perf_counter_ns()
    mut_verdict = DifferentialMutationFalsifier.evaluate_verifier(
        verifier_name="BenchVerifier",
        verifier_callable=robust_verifier,
        nominal_valid_input={"payload": nominal_payload, "sig": nominal_sig, "pubkey": pubkey_bytes.hex()},
        adversarial_mutants=augmented_mutants,
    )
    t1_mut = time.perf_counter_ns()
    mut_elapsed_ns = max(1, t1_mut - t0_mut)

    results = {
        "linter": {
            "iterations": lint_iterations,
            "total_findings": total_findings,
            "elapsed_ns": lint_elapsed_ns,
            "avg_latency_micros": avg_lint_us,
        },
        "scope_decoupler": {
            "iterations": spec_iterations,
            "valid_signatures": valid_sig_count,
            "elapsed_ns": spec_elapsed_ns,
            "avg_latency_micros": avg_spec_us,
        },
        "live_oracle": {
            "runs_evaluated": len(dyn_verdict.runs),
            "distinct_digests": dyn_verdict.distinct_digest_count,
            "is_valid": dyn_verdict.is_valid,
            "total_elapsed_ns": dyn_elapsed_ns,
        },
        "mutation_falsifier": {
            "mutations_tested": mut_verdict.mutations_tested,
            "mutations_killed": mut_verdict.mutations_killed,
            "kill_ratio_bps": mut_verdict.mutation_kill_bps,
            "is_adequate": mut_verdict.is_adequate,
            "elapsed_ns": mut_elapsed_ns,
        },
    }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Empirical Anti-Scaffold Benchmark")
    parser.add_argument("--json-out", type=str, default="reports/anti_scaffold_benchmark_report.json")
    args = parser.parse_args()

    results = run_benchmark()
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Benchmark completed. Results written to {out_path}")


if __name__ == "__main__":
    main()
