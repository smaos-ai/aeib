#!/usr/bin/env python3
"""
FreeToken Benchmarking Script
Measures throughput (tok/s) vs Ollama baseline
Target: 39.3 tok/s on 8GB GPU (3-4x faster than Ollama ~22 tok/s)
"""

import time
import requests
import json
import statistics
from typing import List

FREETOKEN_URL = "http://localhost:8001"
OLLAMA_URL = "http://localhost:11434"

test_prompts = [
    "What is a credit score and how does it impact financial decisions?",
    "Explain the regulatory requirements for AI systems in financial services.",
    "Describe the steps involved in processing a hotel booking request.",
    "What are the security considerations for biometric access control systems?",
    "How can machine learning improve workplace safety monitoring?",
]


def benchmark_freetoken(num_runs: int = 5) -> dict:
    """Benchmark FreeToken inference speed"""
    print(f"\n🚀 Benchmarking FreeToken ({num_runs} runs)...")
    latencies = []
    throughputs = []
    tokens_list = []

    for i, prompt in enumerate(test_prompts[:num_runs]):
        try:
            response = requests.post(
                f"{FREETOKEN_URL}/api/generate",
                json={"prompt": prompt, "max_tokens": 128, "temperature": 0.7},
                timeout=60,
            )
            data = response.json()

            latency_ms = data["latency_ms"]
            throughput = data["throughput_tps"]
            tokens = data["tokens"]

            latencies.append(latency_ms)
            throughputs.append(throughput)
            tokens_list.append(tokens)

            print(
                f"  Run {i + 1}: {tokens} tokens in {latency_ms:.0f}ms = {throughput:.1f} tok/s"
            )
        except Exception as e:
            print(f"  ❌ Run {i + 1} failed: {e}")
            return None

    avg_latency = statistics.mean(latencies)
    avg_throughput = statistics.mean(throughputs)
    p99_latency = sorted(latencies)[-1] if latencies else 0

    return {
        "service": "FreeToken",
        "avg_latency_ms": avg_latency,
        "p99_latency_ms": p99_latency,
        "avg_throughput_tps": avg_throughput,
        "total_tokens": sum(tokens_list),
        "status": "healthy" if avg_throughput > 30 else "warn" if avg_throughput > 15 else "fail",
    }


def benchmark_ollama(num_runs: int = 5) -> dict:
    """Benchmark Ollama inference speed (baseline)"""
    print(f"\n🏛️  Benchmarking Ollama ({num_runs} runs)...")
    latencies = []
    throughputs = []
    tokens_list = []

    for i, prompt in enumerate(test_prompts[:num_runs]):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": "qwen2.5-coder:14b", "prompt": prompt, "stream": False},
                timeout=120,
            )
            data = response.json()

            # Extract tokens and latency from Ollama response
            eval_count = data.get("eval_count", 0)
            eval_duration = data.get("eval_duration", 0)
            latency_ms = eval_duration / 1_000_000  # Convert nanoseconds to ms
            throughput = eval_count / (eval_duration / 1_000_000_000) if eval_duration > 0 else 0

            latencies.append(latency_ms)
            throughputs.append(throughput)
            tokens_list.append(eval_count)

            print(
                f"  Run {i + 1}: {eval_count} tokens in {latency_ms:.0f}ms = {throughput:.1f} tok/s"
            )
        except Exception as e:
            print(f"  ⚠️  Ollama not available: {e}")
            return None

    avg_latency = statistics.mean(latencies) if latencies else 0
    avg_throughput = statistics.mean(throughputs) if throughputs else 0
    p99_latency = sorted(latencies)[-1] if latencies else 0

    return {
        "service": "Ollama",
        "avg_latency_ms": avg_latency,
        "p99_latency_ms": p99_latency,
        "avg_throughput_tps": avg_throughput,
        "total_tokens": sum(tokens_list),
        "status": "baseline",
    }


def compare_benchmarks(freetoken: dict, ollama: dict) -> None:
    """Compare FreeToken vs Ollama performance"""
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS: FreeToken vs Ollama")
    print("=" * 70)

    if freetoken:
        print(f"\n🚀 FreeToken:")
        print(f"   Throughput: {freetoken['avg_throughput_tps']:.1f} tok/s")
        print(f"   Avg Latency: {freetoken['avg_latency_ms']:.0f}ms")
        print(f"   P99 Latency: {freetoken['p99_latency_ms']:.0f}ms")
        print(f"   Total Tokens: {freetoken['total_tokens']}")

    if ollama:
        print(f"\n🏛️  Ollama:")
        print(f"   Throughput: {ollama['avg_throughput_tps']:.1f} tok/s")
        print(f"   Avg Latency: {ollama['avg_latency_ms']:.0f}ms")
        print(f"   P99 Latency: {ollama['p99_latency_ms']:.0f}ms")
        print(f"   Total Tokens: {ollama['total_tokens']}")

    if freetoken and ollama and ollama["avg_throughput_tps"] > 0:
        speedup = freetoken["avg_throughput_tps"] / ollama["avg_throughput_tps"]
        print(f"\n📊 FreeToken is {speedup:.1f}x faster than Ollama")
        if speedup >= 3.0:
            print("   ✅ TARGET MET: 3-4x speedup achieved!")
        else:
            print("   ⚠️  Below target (3-4x). Optimization needed.")

    print("=" * 70)


if __name__ == "__main__":
    print("\n🔬 SMAOS Phase 1 Infrastructure Benchmarking")
    print("Testing FreeToken vs Ollama for hotel pilot inference requirements\n")

    freetoken_result = benchmark_freetoken(num_runs=3)
    ollama_result = benchmark_ollama(num_runs=3)

    compare_benchmarks(freetoken_result, ollama_result)

    # Save results to JSON
    results = {"freetoken": freetoken_result, "ollama": ollama_result, "timestamp": time.time()}
    with open("benchmark-results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n✅ Benchmark results saved to benchmark-results.json")
