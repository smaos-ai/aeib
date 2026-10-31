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
tests/test_multi_region_mesh_federation_benchmark.py
================================================================================
Verification Suite for `tools/multi_region_mesh_federation_benchmark.py`.
Evaluates:
1. Multi-region benchmark execution across US-East, US-West, and EU-Central.
2. Latency reduction verification (>= 8000 bps) and local latch durations.
3. Split-brain partition containment and out-of-band probe reconciliation.
4. CLI execution, RFC 8785 JSON report export, and dataclass immutability.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from tools.multi_region_mesh_federation_benchmark import (
    FederationNodeSpec,
    MultiRegionBenchmarkReport,
    MultiRegionFederationBenchmark,
)


def test_1_full_multi_region_benchmark_execution() -> None:
    bench = MultiRegionFederationBenchmark(intents_per_node=10)
    report, telemetry = bench.run_benchmark()

    assert report.total_intents_evaluated == 30
    assert report.status == "INTERNAL PREVIEW COMMISSIONED"
    assert len(report.nodes_participating) == 3
    assert "us-east-1" in report.nodes_participating
    assert "us-west-2" in report.nodes_participating
    assert "eu-central-1" in report.nodes_participating

    # Verify latency reduction is at least 80% (8000 bps)
    assert report.latency_reduction_bps >= 8000
    assert report.mean_local_latch_ms < 15
    assert report.mean_wan_saved_ms > 100

    # Verify partition fault containment & reconciliation
    assert report.partition_contained is True
    assert report.reconciled_after_healing == 1
    assert report.global_merkle_root.startswith("sha256:")
    assert report.report_caid.startswith("sha256:")


def test_2_cli_invocation_and_report_file_export(tmp_path: Path) -> None:
    out_file = tmp_path / "multi_region_report.json"
    cmd = [
        sys.executable,
        "tools/multi_region_mesh_federation_benchmark.py",
        "--intents-per-node",
        "5",
        "--out",
        str(out_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "MULTI-REGION EDGE LATCH FEDERATION BENCHMARK" in res.stdout
    assert out_file.exists()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["report_version"] == "1.0.0"
    assert data["total_intents_evaluated"] == 15
    assert data["partition_contained"] is True
    assert data["reconciled_after_healing"] == 1
    assert data["report_caid"].startswith("sha256:")


def test_3_epistemic_purity_and_zero_mocks() -> None:
    spec = FederationNodeSpec(node_id="n1", region="r1", wan_baseline_ms=100)
    assert spec.wan_baseline_ms == 100

    report = MultiRegionBenchmarkReport(
        report_version="1.0.0",
        report_caid="sha256:rep",
        total_intents_evaluated=10,
        mean_local_latch_ms=2,
        mean_wan_saved_ms=150,
        latency_reduction_bps=9500,
        global_merkle_root="sha256:merkle",
        partition_contained=True,
        reconciled_after_healing=1,
        nodes_participating=("us-east-1", "eu-central-1"),
        status="INTERNAL PREVIEW COMMISSIONED",
        execution_duration_ms=45,
    )
    d = report.to_dict()
    assert d["latency_reduction_bps"] == 9500
    assert d["nodes_participating"] == ["us-east-1", "eu-central-1"]

    with pytest.raises(Exception):
        report.status = "MUTATED"  # type: ignore[misc]
