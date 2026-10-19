#!/usr/bin/env python3
"""
tests/test_contextcart_20_tasks.py
================================================================================
Empirical Test Suite for ContextCart-MCP 20-Task Benchmark & CLI Distribution.

Evaluates under the stated model:
  1. Executes run_20_task_empirical_benchmark.py and asserts:
     - Exactly 20 tasks evaluated.
     - Every task returned bounded output <= 1,500 tokens.
     - p50 token reduction >= 75%, p90 token reduction >= 85%.
     - Content-addressed evidence files created on disk with valid SHA-256 matching manifest.
     - Latency per task <= 100 ms.
  2. Tests @sovereignnexus/context-governor-mcp CLI executable via
     node contextcart-mcp/bin/context-governor-mcp.js --help.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_contextcart_20_task_empirical_benchmark() -> None:
    """
    Executes the 20-task empirical benchmark script and verifies distribution
    statistics, token boundaries, and cryptographic content addressing.
    """
    benchmark_script = (
        REPO_ROOT
        / "contextcart-mcp"
        / "benchmarks"
        / "run_20_task_empirical_benchmark.py"
    )
    assert benchmark_script.is_file(), f"Benchmark script missing: {benchmark_script}"

    output_json = REPO_ROOT / "evidence" / "contextcart_20_task_benchmark_results.json"

    # Execute benchmark runner
    cmd = [
        sys.executable,
        str(benchmark_script),
        "--runs",
        "1",
        "--output-json",
        str(output_json),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"Benchmark runner failed:\n{proc.stderr}\n{proc.stdout}"
    assert output_json.is_file(), f"Output JSON not created: {output_json}"

    # Parse results manifest
    report = json.loads(output_json.read_text(encoding="utf-8"))
    summary = report["summary"]
    tasks = report["tasks"]

    # Assertion 1: Exactly 20 tasks evaluated
    assert len(tasks) == 20, f"Expected 20 tasks, observed {len(tasks)}"
    assert summary["total_tasks"] == 20

    # Assertion 2: Every task returned bounded output <= 1,500 tokens
    for t in tasks:
        assert (
            t["bounded_tokens"] <= 1500
        ), f"Task {t['task_id']} exceeded 1,500 token limit: {t['bounded_tokens']} tokens"

    # Assertion 3: p50 reduction >= 75%, p90 reduction >= 85%
    p50_val = summary["p50_reduction_pct"]
    p90_val = summary["p90_reduction_pct"]
    assert (
        p50_val >= 75.0
    ), f"Observed p50 reduction {p50_val}% is below 75.0% threshold"
    assert (
        p90_val >= 85.0
    ), f"Observed p90 reduction {p90_val}% is below 85.0% threshold"

    # Assertion 4: Content-addressed evidence files on disk with matching SHA-256
    for t in tasks:
        ev_file = Path(t["evidence_path"])
        assert (
            ev_file.is_file()
        ), f"Evidence file not found on disk: {ev_file} for task {t['task_id']}"

        raw_bytes = ev_file.read_bytes()
        assert (
            len(raw_bytes) == t["evidence_bytes"]
        ), f"Byte count mismatch for {t['task_id']}: {len(raw_bytes)} != {t['evidence_bytes']}"

        calculated_sha = hashlib.sha256(raw_bytes).hexdigest()
        assert (
            calculated_sha == t["sha256"]
        ), f"SHA-256 digest mismatch for {t['task_id']}: {calculated_sha} != {t['sha256']}"
        assert (
            t["evidence_id"] == f"sha256:{calculated_sha}"
        ), f"Evidence ID format mismatch for {t['task_id']}"

    # Assertion 5: Latency per task <= 100 ms
    for t in tasks:
        assert (
            t["latency_ms"] <= 100.0
        ), f"Latency for {t['task_id']} exceeded 100ms threshold: {t['latency_ms']} ms"

    # Assertion 6: Modeled API cost savings evaluated
    modeled_cost = summary["modeled_api_cost_savings"]
    assert modeled_cost["input_rate_per_million_usd"] == 3.00
    assert modeled_cost["output_rate_per_million_usd"] == 15.00
    assert modeled_cost["direct_input_savings_usd"] > 0.0
    assert modeled_cost["team_annual_input_savings_usd"] > 0.0


def test_context_governor_mcp_cli_help() -> None:
    """
    Tests the Node-based @sovereignnexus/context-governor-mcp CLI executable
    via `node contextcart-mcp/bin/context-governor-mcp.js --help`.
    """
    cli_script = (
        REPO_ROOT
        / "contextcart-mcp"
        / "bin"
        / "context-governor-mcp.js"
    )
    assert cli_script.is_file(), f"CLI executable missing: {cli_script}"

    cmd = ["node", str(cli_script), "--help"]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"CLI --help invocation failed:\n{proc.stderr}\n{proc.stdout}"
    assert "CONTEXT GOVERNOR MCP" in proc.stdout
    assert "@sovereignnexus/context-governor-mcp" in proc.stdout
    assert "Commands:" in proc.stdout
    assert "init" in proc.stdout
    assert "scan" in proc.stdout
    assert "audit" in proc.stdout
