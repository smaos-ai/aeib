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
tools/independent_validation_runner.py — Hermetic Independent Validation Flow.

Executes a complete, unified verification battery for independent reviewers:
1. Static AST purity & Zone Boundary Isolation (Zero Zone 1 -> Zone 2 leakage, zero mocks).
2. FIPS 204 ML-DSA-65 & Ed25519 PQEE Dual Verification (require_both_valid).
3. Commit-Time Consistency Guard (BSC-R, Wesley Shu arXiv:2609.37475).
4. Agent Execution Integrity Telemetry (AEIT, descriptive metrics).
5. Native Rust Direct-I/O WAL sector alignment and recovery.
6. Industrial Protection Matrix & ANSI 50BF Breaker Cascade.
7. Deterministic 500-Episode Fault Simulation Benchmark.
Emits an RFC 8785 canonical, Ed25519-signed independent validation receipt.
"""

import base64
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from src.jcs_canonicalizer import encode_jcs


@dataclass
class StepResult:
    step_id: str
    name: str
    passed: bool
    duration_ms: float
    details: str


class IndependentValidationRunner:
    """Orchestrates the hermetic clean-room validation flow."""

    def __init__(self, repo_root: Path = REPO_ROOT) -> None:
        self.repo_root = repo_root
        self.results: List[StepResult] = []

    def _run_cmd(self, step_id: str, name: str, cmd: List[str]) -> StepResult:
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)
        dur = (time.perf_counter() - t0) * 1000.0
        passed = (proc.returncode == 0)
        details = proc.stdout.strip() if passed else proc.stderr.strip()
        res = StepResult(
            step_id=step_id,
            name=name,
            passed=passed,
            duration_ms=round(dur, 2),
            details=details[:500] if details else f"exit_code_{proc.returncode}",
        )
        self.results.append(res)
        return res

    def execute_all(self) -> Dict[str, Any]:
        # Step 1: Zone Boundary Check
        self._run_cmd(
            "STEP_01_ZONE_BOUNDARY",
            "Zone Boundary Isolation Scanner",
            ["python3", "compliance/check_zone_boundary.py"],
        )

        # Step 2: AST Purity & Zero-Mock Enforcer
        self._run_cmd(
            "STEP_02_AST_PURITY",
            "Zero-Mock and AST Purity Enforcer",
            ["python3", "compliance/ast_purity.py", "."],
        )
        self._run_cmd(
            "STEP_02B_NO_MOCK",
            "Zero Fake Crypto Verification",
            ["python3", "compliance/no_mock_enforcer.py"],
        )

        # Step 3: FIPS 204 ML-DSA-65 & Ed25519 PQEE Dual Verification
        self._run_cmd(
            "STEP_03_PQEE_DUAL_VERIFY",
            "FIPS 204 ML-DSA-65 + Ed25519 Dual Verification",
            ["pytest", "tests/test_hybrid_pqc_envelope.py", "-q"],
        )

        # Step 4: Commit-Time Consistency Guard (BSC-R)
        self._run_cmd(
            "STEP_04_COMMIT_TIME_BSCR",
            "Commit-Time Consistency Guard (BSC-R)",
            ["pytest", "tests/test_commit_time_state_guard.py", "-q"],
        )

        # Step 5: Execution Integrity Telemetry (AEIT)
        self._run_cmd(
            "STEP_05_AEIT_TELEMETRY",
            "Agent Execution Integrity Telemetry",
            ["pytest", "tests/test_execution_integrity_telemetry.py", "-q"],
        )

        # Step 6: Native Rust Data-Plane Direct-I/O WAL
        self._run_cmd(
            "STEP_06_DIRECT_IO_WAL",
            "Rust Direct-I/O WAL & Sector Alignment",
            ["cargo", "test", "-p", "aeib-data-plane", "-q"],
        )

        # Step 7: Core Industrial Matrix & Breaker Cascade
        self._run_cmd(
            "STEP_07_INDUSTRIAL_MATRIX",
            "Industrial Protection Matrix & 50BF Breaker Cascade",
            [
                "pytest",
                "tests/test_industrial_protection_matrix.py",
                "tests/test_ansi_50bf_breaker_failure.py",
                "tests/test_saga_compensation.py",
                "tests/test_falsifiability_matrix.py",
                "-q",
            ],
        )

        # Step 8: Deterministic 500-Episode Simulation Benchmark
        self._run_cmd(
            "STEP_08_DST_BENCHMARK",
            "Deterministic 500-Episode Execution Integrity Benchmark",
            [
                "python3",
                "benchmarks/aeib_execution_integrity/run_episodes.py",
                "--episodes",
                "500",
                "--seed",
                "42",
            ],
        )

        all_passed = all(r.passed for r in self.results)
        total_duration = sum(r.duration_ms for r in self.results)

        # Generate signed canonical receipt
        signing_key = Ed25519PrivateKey.generate()
        receipt_body = {
            "validation_run": {
                "engine": "AEIB Independent Validation Runner v1.0.0-rc.5",
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_steps": len(self.results),
                "passed_steps": sum(1 for r in self.results if r.passed),
                "all_passed": all_passed,
                "total_duration_ms": round(total_duration, 2),
            },
            "steps": [
                {
                    "step_id": r.step_id,
                    "name": r.name,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                }
                for r in self.results
            ],
        }

        canonical_receipt_bytes = encode_jcs(receipt_body)
        signature = signing_key.sign(canonical_receipt_bytes)
        pub_key_bytes = signing_key.public_key().public_bytes_raw()

        receipt = {
            "receipt_body": receipt_body,
            "signature_envelope": {
                "algorithm": "Ed25519",
                "public_key_hex": pub_key_bytes.hex(),
                "signature_b64": base64.b64encode(signature).decode("ascii"),
                "canonical_hash_sha256": f"sha256:{hashlib.sha256(canonical_receipt_bytes).hexdigest()}",
            },
        }

        # Write output receipt
        out_dir = self.repo_root / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "independent_validation_receipt.json"
        out_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

        return receipt


def main():
    runner = IndependentValidationRunner()
    print("=" * 80)
    print("  AEIB INDEPENDENT VALIDATION FLOW RUNNER")
    print("=" * 80)
    receipt = runner.execute_all()

    for step in receipt["receipt_body"]["steps"]:
        status = "PASSED" if step["passed"] else "FAILED"
        print(f"[{status}] {step['step_id']:<26} {step['name']:<50} ({step['duration_ms']} ms)")

    print("-" * 80)
    summary = receipt["receipt_body"]["validation_run"]
    print(
        f"Validation Result: {'ALL_PASSED' if summary['all_passed'] else 'FAILURES_DETECTED'} "
        f"({summary['passed_steps']}/{summary['total_steps']} steps passed in {summary['total_duration_ms']} ms)"
    )
    print(f"Signed Receipt written to: output/independent_validation_receipt.json")
    print(f"Statement SHA-256: {receipt['signature_envelope']['canonical_hash_sha256']}")
    print("=" * 80)

    if not summary["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
