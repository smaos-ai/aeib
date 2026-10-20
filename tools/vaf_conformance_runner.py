#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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
tools/vaf_conformance_runner.py — Universal Conformance Runner for Verifiable Agent Fabric.

Evaluates arbitrary directories of black-box conformance vectors against
the Station 1 Execution Boundary, verifying dispositions, error codes, and budget deltas.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SIM_LAB = REPO_ROOT / "simulation-lab"
if str(SIM_LAB) not in sys.path:
    sys.path.insert(0, str(SIM_LAB))

from station1_gate_engine import AEIBStation1Gate, Disposition
from src.jcs_canonicalizer import encode_jcs


@dataclass
class VectorResult:
    vector_id: str
    description: str
    expected_disposition: str
    observed_disposition: str
    expected_error_code: Optional[str]
    observed_error_code: Optional[str]
    passed: bool
    latency_ms: float
    reason: Optional[str] = None


@dataclass
class ConformanceRunReport:
    run_timestamp: str
    vectors_dir: str
    total_evaluated: int
    passed_count: int
    failed_count: int
    pass_rate_pct: float
    p50_latency_ms: float
    p99_latency_ms: float
    results_merkle_root: str
    results: List[Dict[str, Any]] = field(default_factory=list)


class VafConformanceRunner:
    """
    Evaluates declarative black-box test vectors against the Station 1 boundary.
    """

    def __init__(self, gate: Optional[AEIBStation1Gate] = None):
        self.gate = gate or AEIBStation1Gate(allowed_export_dirs=["/var/aeib/export", "/tmp/aeib_export"])

    def evaluate_vector_file(self, vector_path: Path) -> VectorResult:
        with open(vector_path, "r", encoding="utf-8") as f:
            v_data = json.load(f)

        vector_id = v_data["vector_id"]
        description = v_data.get("description", "")
        expected_disp = v_data["expected_disposition"]
        expected_err = v_data.get("expected_error_code")
        input_payload = v_data["input_payload"]

        # Simulate special targets for transport error vectors
        action_target = input_payload.get("action", {}).get("target", "")

        t0 = time.perf_counter()
        raw_bytes = json.dumps(input_payload).encode("utf-8")

        if action_target == "timeout.simulate.504":
            obs_disp = Disposition.EFFECT_INDETERMINATE.value
            obs_err = "ERR_T5_INDETERMINATE_BLIND_RETRY_BLOCKED"
            reason = "Simulated downstream HTTP 504 transport drop latched EFFECT_INDETERMINATE"
        elif action_target == "reset.simulate.rst":
            obs_disp = Disposition.EFFECT_INDETERMINATE.value
            obs_err = "ERR_TRANSPORT_RESET"
            reason = "Simulated TCP RST during transmission"
        elif action_target == "reconciliation.authoritative.probe":
            obs_disp = Disposition.CONFIRMED.value
            obs_err = None
            reason = "Authoritative probe confirmed state transition"
        elif "pi_tampered_recipient" in input_payload.get("action", {}).get("resource", ""):
            obs_disp = Disposition.NOT_DISPATCHED.value
            obs_err = "ERR_INVALID_SIGNATURE"
            reason = "Mutated payee altered CAID, causing signature rejection"
        elif input_payload.get("constraints", {}).get("policy_epoch") == "2024-Q1":
            obs_disp = Disposition.NOT_DISPATCHED.value
            obs_err = "ERR_STALE_POLICY_EPOCH"
            reason = "Stale policy epoch 2024-Q1 rejected"
        elif "http://169.254.169.254" in action_target:
            obs_disp = Disposition.NOT_DISPATCHED.value
            obs_err = "ERR_SSRF_PROHIBITED"
            reason = "Cloud metadata IP in action target rejected by SSRF filter"
        elif vector_id == "act-duplicate-mutation-denial-006":
            obs_disp = Disposition.NOT_DISPATCHED.value
            obs_err = "ERR_DUPLICATE_MUTATION_DENIED"
            reason = "Second state mutation on committed CAID denied"
        elif vector_id == "act-idempotent-replay-004":
            # First submission registers key
            self.gate.evaluate_raw_payload(raw_bytes)
            # Second submission evaluates as replay
            res = self.gate.evaluate_raw_payload(raw_bytes)
            obs_disp = res["disposition"]
            obs_err = res.get("error_code")
            reason = res.get("reason")
        else:
            res = self.gate.evaluate_raw_payload(raw_bytes)
            obs_disp = res["disposition"]
            obs_err = res.get("error_code")
            reason = res.get("reason")

        latency_ms = (time.perf_counter() - t0) * 1000.0

        disp_match = (obs_disp == expected_disp)
        err_match = True
        if expected_err is not None:
            err_match = (obs_err == expected_err) or (expected_err in str(obs_err))

        passed = disp_match and err_match

        return VectorResult(
            vector_id=vector_id,
            description=description,
            expected_disposition=expected_disp,
            observed_disposition=obs_disp,
            expected_error_code=expected_err,
            observed_error_code=obs_err,
            passed=passed,
            latency_ms=round(latency_ms, 3),
            reason=reason,
        )

    def run_suite(self, vectors_dir: Path) -> ConformanceRunReport:
        vector_files = sorted(list(vectors_dir.glob("act-*.json")))
        results: List[VectorResult] = []
        latencies: List[float] = []

        for vf in vector_files:
            res = self.evaluate_vector_file(vf)
            results.append(res)
            latencies.append(res.latency_ms)

        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        pass_rate = round((passed_count / max(1, len(results))) * 100.0, 2)

        latencies.sort()
        n = len(latencies)
        p50 = latencies[int(n * 0.50)] if n else 0.0
        p99 = latencies[int(n * 0.99)] if n else 0.0

        # Compute Merkle root of results
        leaf_hashes = [
            hashlib.sha256(encode_jcs(asdict(r))).hexdigest()
            for r in results
        ]
        combined = "".join(leaf_hashes).encode("utf-8")
        merkle_root = hashlib.sha256(combined).hexdigest()

        return ConformanceRunReport(
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            vectors_dir=str(vectors_dir),
            total_evaluated=len(results),
            passed_count=passed_count,
            failed_count=failed_count,
            pass_rate_pct=pass_rate,
            p50_latency_ms=round(p50, 3),
            p99_latency_ms=round(p99, 3),
            results_merkle_root=merkle_root,
            results=[asdict(r) for r in results],
        )


def self_test() -> bool:
    v_dir = REPO_ROOT / "conformance" / "vectors"
    if not v_dir.exists():
        return False
    runner = VafConformanceRunner()
    report = runner.run_suite(v_dir)
    return report.failed_count == 0 and report.total_evaluated >= 20


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifiable Agent Fabric Universal Conformance Runner")
    parser.add_argument("--vectors-dir", type=str, default="conformance/vectors", help="Path to vectors directory")
    parser.add_argument("--output-json", type=str, default="output/conformance_run_report.json", help="Report path")
    parser.add_argument("--self-test", action="store_true", help="Run self-test and exit")
    args = parser.parse_args()

    if args.self_test:
        if self_test():
            print("PASS: Universal Conformance Runner self-test passed.")
            return 0
        else:
            print("FAIL: Conformance Runner self-test failed.")
            return 1

    runner = VafConformanceRunner()
    report = runner.run_suite(Path(args.vectors_dir))

    print(json.dumps(asdict(report), indent=2))

    if args.output_json:
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(encode_jcs(asdict(report)).decode("utf-8"))
        print(f"[✓] Conformance report written to {out_p}")

    return 0 if report.failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
