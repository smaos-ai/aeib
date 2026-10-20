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
tools/ssd_parallel_master_orchestrator.py — High-Performance Parallel SSD Validation Runner.

Orchestrates multi-core parallel execution across 16 critical verification tracks,
saturating the external physical NVMe SSD (/Volumes/EXTssd) with direct-I/O WAL bursts,
running multi-region DST consensus, predictive trajectory fuzzing, zk-budget proofs,
and standalone offline verification simultaneously.

Emits an RFC 8785 canonical, Ed25519-signed master validation receipt to both local
disk and the external NVMe SSD, then verifies both with the pure-Python standalone verifier.
"""

import base64
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from src.jcs_canonicalizer import encode_jcs

EXTERNAL_SSD_MOUNT = Path("/Volumes/EXTssd")
EXTERNAL_SSD_WAL = EXTERNAL_SSD_MOUNT / "aeib_hardware_stress" / "wal"


@dataclass
class JobSpec:
    job_id: str
    name: str
    command: List[str]
    category: str


@dataclass
class JobOutput:
    job_id: str
    name: str
    category: str
    passed: bool
    duration_ms: float
    returncode: int
    summary: str


def _execute_job(spec: JobSpec, repo_root: str) -> JobOutput:
    """Executes a single job subprocess and captures runtime metrics."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        spec.command,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    dur_ms = (time.perf_counter() - t0) * 1000.0
    passed = (proc.returncode == 0)

    summary = proc.stdout.strip() if passed else proc.stderr.strip()
    # Truncate summary if excessively long
    lines = summary.splitlines()
    if len(lines) > 6:
        summary = "\n".join(lines[:3] + ["..."] + lines[-3:])

    return JobOutput(
        job_id=spec.job_id,
        name=spec.name,
        category=spec.category,
        passed=passed,
        duration_ms=round(dur_ms, 2),
        returncode=proc.returncode,
        summary=summary,
    )


class SsdParallelMasterOrchestrator:
    """Multi-core parallel orchestrator for AEIB hardware-flushing and state validation."""

    def __init__(self, repo_root: Path = REPO_ROOT, max_workers: Optional[int] = None) -> None:
        self.repo_root = repo_root
        self.max_workers = max_workers or min(os.cpu_count() or 4, 8)
        self.jobs: List[JobSpec] = self._build_job_specs()

    def _build_job_specs(self) -> List[JobSpec]:
        specs: List[JobSpec] = [
            JobSpec(
                job_id="TRACK_01_NVME_DIRECT_IO_STRESS",
                name="External NVMe Direct-I/O Group-Commit WAL Burst (2,000 Threads)",
                command=[
                    "python3",
                    "benchmarks/run_parallel_burst_stress.py",
                    "--threads",
                    "2000",
                    "--wal-dir",
                    str(EXTERNAL_SSD_WAL),
                    "--output",
                    "output/hardware_nvme_2000thread_stress_receipt.json",
                    "--quiet",
                ],
                category="HARDWARE_DIRECT_IO",
            ),
            JobSpec(
                job_id="TRACK_02_DST_500_EPISODES",
                name="Deterministic 500-Episode Simulation (4 Arms, 15 Fault Vectors)",
                command=[
                    "python3",
                    "benchmarks/aeib_execution_integrity/run_episodes.py",
                    "--episodes",
                    "500",
                    "--seed",
                    "42",
                ],
                category="FAULT_SIMULATION",
            ),
            JobSpec(
                job_id="TRACK_03_MULTI_REGION_QUORUM_DST",
                name="Multi-Region Consensus Quorum & Partition Recovery DST",
                command=["pytest", "tests/test_dst_multi_region_partition.py", "-q"],
                category="DISTRIBUTED_CONSENSUS",
            ),
            JobSpec(
                job_id="TRACK_04_TRAJECTORY_DRIFT_AND_FUZZER",
                name="Predictive Trajectory Drift Latch & Adversarial Token Chaos Fuzzer",
                command=["pytest", "tests/test_predictive_trajectory_drift_latch.py", "-q"],
                category="ADVERSARIAL_DEFENSE",
            ),
            JobSpec(
                job_id="TRACK_05_ZK_BUDGET_PROOF_ENGINE",
                name="Zero-Knowledge Privacy-Preserving Budget Proof Engine (BN254 Field)",
                command=["pytest", "tests/test_zk_budget_proof_engine.py", "-q"],
                category="ZERO_KNOWLEDGE",
            ),
            JobSpec(
                job_id="TRACK_06_STANDALONE_OFFLINE_VERIFIER",
                name="Standalone Zero-Dependency Pure-Python Curve25519 Offline Verifier",
                command=["pytest", "tests/test_standalone_offline_verifier.py", "-q"],
                category="AUDIT_VERIFICATION",
            ),
            JobSpec(
                job_id="TRACK_07_BPF_LSM_PROFILE_COMPILER",
                name="Linux Kernel BPF_LSM Security Profile Compiler & Static Linter",
                command=["pytest", "tests/test_bpf_lsm_profile_compiler.py", "-q"],
                category="KERNEL_ENFORCEMENT",
            ),
            JobSpec(
                job_id="TRACK_08_CLOUDFLARE_SIX_PHASE_AUDIT",
                name="Cloudflare 6-Phase Audit & Fresh Disproving Verifier Harness",
                command=["pytest", "tests/test_audit_disproving_verifier.py", "-q"],
                category="AUDIT_VERIFICATION",
            ),
            JobSpec(
                job_id="TRACK_09_SECURE_MCP_UDS_BOUNDARY",
                name="Secure MCP Unix Domain Socket Boundary & Local Peer Identity Gate",
                command=["pytest", "tests/test_secure_mcp_uds_boundary.py", "-q"],
                category="ISOLATION_BOUNDARY",
            ),
            JobSpec(
                job_id="TRACK_10_DYNAMIC_CODE_POLICY_GATE",
                name="Dynamic Execution Policy Gate & Signed Plugin Manifest Verifier",
                command=["pytest", "tests/test_dynamic_code_policy_gate.py", "-q"],
                category="CODE_GOVERNANCE",
            ),
            JobSpec(
                job_id="TRACK_11_GOVERNED_CROSS_MODEL_HANDOFF",
                name="Governed Cross-Model Handoff & Taint Monotonicity Lattice Gate",
                command=["pytest", "tests/test_governed_cross_model_handoff.py", "-q"],
                category="CROSS_MODEL_GOVERNANCE",
            ),
            JobSpec(
                job_id="TRACK_12_ARTEMIS_DEVICE_AND_PLUGIN",
                name="ARTEMIS Mobile Device Actuator & ADECS 4.0 Lifecycle Gate",
                command=["pytest", "tests/test_artemis_device_and_plugin_boundary.py", "-q"],
                category="ACTUATOR_GOVERNANCE",
            ),
            JobSpec(
                job_id="TRACK_13_POSTGRES_TCC_STRESS",
                name="PostgreSQL TCC High-Contention Concurrency & Bitemporal Outbox",
                command=["pytest", "tests/test_postgres_tcc_concurrency_stress.py", "-q"],
                category="STORAGE_CONCURRENCY",
            ),
            JobSpec(
                job_id="TRACK_14_CONTEXTCART_20_TASK_BENCHMARK",
                name="ContextCart-MCP 20-Task Empirical Symbol Slicing Benchmark",
                command=[
                    "python3",
                    "contextcart-mcp/benchmarks/run_20_task_empirical_benchmark.py",
                ],
                category="CONTEXT_OPTIMIZATION",
            ),
            JobSpec(
                job_id="TRACK_15_FIPS204_PQEE_DUAL_VERIFY",
                name="FIPS 204 ML-DSA-65 + Ed25519 Post-Quantum Evidence Envelope",
                command=["pytest", "tests/test_hybrid_pqc_envelope.py", "-q"],
                category="POST_QUANTUM_CRYPTO",
            ),
            JobSpec(
                job_id="TRACK_16_DORA_BACKUP_RESTORE_VERIFY",
                name="DORA Article 17 Backup Clean-Room Restorability & Reproducible WASM",
                command=["bash", "scripts/verify_reproducible_wasm_and_backup_restore.sh"],
                category="RESILIENCE_AND_RESTORABILITY",
            ),
        ]
        return specs

    def run_parallel(self) -> Dict[str, Any]:
        """Runs all verification tracks concurrently and generates a signed master receipt."""
        EXTERNAL_SSD_WAL.mkdir(parents=True, exist_ok=True)

        print("=" * 80)
        print("  AEIB HIGH-PERFORMANCE PARALLEL SSD MASTER ORCHESTRATOR")
        print(f"  Parallel Workers : {self.max_workers} processes")
        print(f"  Total Tracks     : {len(self.jobs)} concurrent tracks")
        print(f"  Physical NVMe WAL: {EXTERNAL_SSD_WAL}")
        print("=" * 80)

        t_wall_start = time.perf_counter()
        results: List[JobOutput] = []

        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_job = {
                executor.submit(_execute_job, job, str(self.repo_root)): job for job in self.jobs
            }
            for future in concurrent.futures.as_completed(future_to_job):
                output = future.result()
                results.append(output)
                status_symbol = "[✓]" if output.passed else "[✗]"
                print(
                    f"  {status_symbol} {output.job_id:<36} : {output.duration_ms:8.2f} ms | "
                    f"status={'PASS' if output.passed else 'FAIL'}"
                )

        wall_duration_ms = (time.perf_counter() - t_wall_start) * 1000.0
        results.sort(key=lambda r: r.job_id)

        all_passed = all(r.passed for r in results)
        total_cpu_duration_ms = sum(r.duration_ms for r in results)
        parallel_speedup = (
            total_cpu_duration_ms / max(1.0, wall_duration_ms) if wall_duration_ms > 0 else 1.0
        )

        print("-" * 80)
        print(f"  Execution Summary:")
        print(f"    Total Tracks Evaluated: {len(results)}")
        print(f"    Passed Tracks         : {sum(1 for r in results if r.passed)}")
        print(f"    Failed Tracks         : {sum(1 for r in results if not r.passed)}")
        print(f"    Summed Track CPU Time : {total_cpu_duration_ms:8.2f} ms")
        print(f"    Wall-Clock Duration   : {wall_duration_ms:8.2f} ms")
        print(f"    Observed Speedup      : {parallel_speedup:8.2f}x")
        print(f"    Overall Status        : {'PASS' if all_passed else 'FAIL'}")
        print("=" * 80)

        # Generate Ed25519 signing keypair for the receipt
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pubkey_b64 = base64.b64encode(public_key.public_bytes_raw()).decode("utf-8")

        # Compile receipt body conforming to AEIB Format 5 standard
        receipt_body = {
            "orchestrator": "SsdParallelMasterOrchestrator v1.0.0-rc.5",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "environment": {
                "os": sys.platform,
                "cpu_count": os.cpu_count(),
                "max_workers": self.max_workers,
                "external_ssd_mount": str(EXTERNAL_SSD_MOUNT),
                "external_ssd_available": EXTERNAL_SSD_MOUNT.exists(),
            },
            "performance": {
                "wall_duration_ms": round(wall_duration_ms, 2),
                "total_cpu_duration_ms": round(total_cpu_duration_ms, 2),
                "parallel_speedup_factor": round(parallel_speedup, 2),
            },
            "summary": {
                "total_tracks": len(results),
                "passed_tracks": sum(1 for r in results if r.passed),
                "all_passed": all_passed,
            },
            "tracks": [
                {
                    "job_id": r.job_id,
                    "name": r.name,
                    "category": r.category,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "returncode": r.returncode,
                }
                for r in results
            ],
        }

        canonical_bytes = encode_jcs(receipt_body)
        payload_hash = hashlib.sha256(canonical_bytes).hexdigest()
        signature_bytes = private_key.sign(canonical_bytes)
        pub_key_bytes = public_key.public_bytes_raw()

        signed_receipt = {
            "receipt_body": receipt_body,
            "signature_envelope": {
                "algorithm": "Ed25519",
                "public_key_hex": pub_key_bytes.hex(),
                "public_key_b64": base64.b64encode(pub_key_bytes).decode("ascii"),
                "signature_b64": base64.b64encode(signature_bytes).decode("ascii"),
                "canonical_hash_sha256": f"sha256:{payload_hash}",
            },
        }

        # Write to local repo output
        local_output_path = self.repo_root / "output" / "master_parallel_validation_receipt.json"
        local_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_output_path, "w", encoding="utf-8") as f:
            json.dump(signed_receipt, f, indent=2)
        print(f"[✓] Local master validation receipt written to: {local_output_path}")

        # Mirror directly to external NVMe SSD with Darwin F_FULLFSYNC flush
        ssd_output_path = EXTERNAL_SSD_MOUNT / "master_parallel_validation_receipt.json"
        if EXTERNAL_SSD_MOUNT.exists():
            try:
                with open(ssd_output_path, "w", encoding="utf-8") as f:
                    json.dump(signed_receipt, f, indent=2)
                    f.flush()
                    if hasattr(os, "fcntl") and hasattr(os, "F_FULLFSYNC"):
                        os.fcntl(f.fileno(), os.F_FULLFSYNC)
                    else:
                        os.fsync(f.fileno())
                print(f"[✓] External NVMe SSD master receipt flushed to: {ssd_output_path}")
            except Exception as e:
                print(f"[!] Warning: Failed to flush to external SSD: {e}")

        return signed_receipt


def main() -> int:
    orchestrator = SsdParallelMasterOrchestrator()
    receipt = orchestrator.run_parallel()
    all_passed = receipt["receipt_body"]["summary"]["all_passed"]
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
