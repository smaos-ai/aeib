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
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from src.jcs_canonicalizer import encode_jcs
from src.parallel_tracks_abcde_engine import ReproducibleEvidenceBundleBuilder


@dataclass
class StepResult:
    step_id: str
    name: str
    passed: bool
    duration_ms: int
    details: str


DEFAULT_VALIDATION_STEPS: Tuple[Tuple[str, str, List[str]], ...] = (
    (
        "STEP_01_ZONE_BOUNDARY",
        "Zone Boundary Isolation Scanner",
        ["python3", "compliance/check_zone_boundary.py"],
    ),
    (
        "STEP_02_AST_PURITY",
        "Zero-Mock and AST Purity Enforcer",
        ["python3", "compliance/ast_purity.py", "."],
    ),
    (
        "STEP_02B_NO_MOCK",
        "Zero Fake Crypto Verification",
        ["python3", "compliance/no_mock_enforcer.py"],
    ),
    (
        "STEP_03_PQEE_DUAL_VERIFY",
        "FIPS 204 ML-DSA-65 + Ed25519 Dual Verification",
        ["pytest", "tests/test_hybrid_pqc_envelope.py", "-q"],
    ),
    (
        "STEP_04_COMMIT_TIME_BSCR",
        "Commit-Time Consistency Guard (BSC-R)",
        ["pytest", "tests/test_commit_time_state_guard.py", "-q"],
    ),
    (
        "STEP_05_AEIT_TELEMETRY",
        "Agent Execution Integrity Telemetry",
        ["pytest", "tests/test_execution_integrity_telemetry.py", "-q"],
    ),
    (
        "STEP_06_DIRECT_IO_WAL",
        "Rust Direct-I/O WAL & Sector Alignment",
        ["cargo", "test", "-p", "aeib-data-plane", "-q"],
    ),
    (
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
    ),
    (
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
    ),
    (
        "STEP_09_SELECTIVE_DISCLOSURE",
        "Selective Disclosure & Redaction Engine (GDPR/DORA)",
        ["pytest", "tests/test_selective_disclosure_receipt.py", "-q"],
    ),
    (
        "STEP_10_EBV_MODEL_CHECKER",
        "EBV State Machine Formal Model Checker",
        ["python3", "tools/ebv_state_machine_checker.py"],
    ),
    (
        "STEP_11_PREDICTIVE_TRAJECTORY_LATCH",
        "Predictive Trajectory Drift Latch & Adversarial Fuzzing",
        ["pytest", "tests/test_predictive_trajectory_drift_latch.py", "-q"],
    ),
    (
        "STEP_12_ZK_BUDGET_PROOFS",
        "Zero-Knowledge Budget Proof Engine (Pedersen + Schnorr)",
        ["pytest", "tests/test_zk_budget_proof_engine.py", "-q"],
    ),
    (
        "STEP_13_STANDALONE_OFFLINE_VERIFIER",
        "Standalone Zero-Dependency Offline Verifier",
        ["pytest", "tests/test_standalone_offline_verifier.py", "-q"],
    ),
    (
        "STEP_14_BPF_LSM_PROFILE_COMPILER",
        "Tetragon / BPF_LSM Security Profile Compiler",
        ["pytest", "tests/test_bpf_lsm_profile_compiler.py", "-q"],
    ),
    (
        "STEP_15_REPO_INTELLIGENCE_PACKER",
        "SOTA Repo-Intelligence & Radix KV-Cache Packer",
        ["pytest", "tests/test_finalize_repo_intelligence_packer.py", "-q"],
    ),
)


class IndependentValidationRunner:
    """Orchestrates the hermetic clean-room validation flow."""

    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        signing_key: Optional[Ed25519PrivateKey] = None,
        steps_override: Optional[Sequence[Tuple[str, str, List[str]]]] = None,
    ) -> None:
        self.repo_root = repo_root
        self.signing_key = signing_key
        self.steps_spec: Sequence[Tuple[str, str, List[str]]] = (
            steps_override if steps_override is not None else DEFAULT_VALIDATION_STEPS
        )
        self.results: List[StepResult] = []

    def _run_cmd(self, step_id: str, name: str, cmd: List[str]) -> StepResult:
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)
        dur = (time.perf_counter() - t0) * 1000
        passed = (proc.returncode == 0)
        details = proc.stdout.strip() if passed else proc.stderr.strip()
        res = StepResult(
            step_id=step_id,
            name=name,
            passed=passed,
            duration_ms=int(round(dur)),
            details=details[:500] if details else f"exit_code_{proc.returncode}",
        )
        self.results.append(res)
        return res

    def execute_all(self) -> Dict[str, Any]:
        for step_id, name, cmd in self.steps_spec:
            self._run_cmd(step_id, name, cmd)

        all_passed = all(r.passed for r in self.results)
        total_duration_ms = int(sum(r.duration_ms for r in self.results))
        deterministic_outcomes = [
            {"step_id": r.step_id, "passed": bool(r.passed)} for r in self.results
        ]
        deterministic_outcomes_caid = (
            "sha256:" + hashlib.sha256(encode_jcs(deterministic_outcomes)).hexdigest()
        )

        # Generate signed canonical receipt.
        # If no caller key was supplied, record explicitly that the key is ephemeral
        # (run-level integrity only, not pinned authorship).
        key_pinned = self.signing_key is not None
        signing_key = self.signing_key or Ed25519PrivateKey.generate()
        receipt_body = {
            "validation_run": {
                "engine": "AEIB Independent Validation Runner v1.0.0-rc.5",
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_steps": len(self.results),
                "passed_steps": sum(1 for r in self.results if r.passed),
                "all_passed": all_passed,
                "total_duration_ms": total_duration_ms,
                "deterministic_outcomes_caid": deterministic_outcomes_caid,
            },
            "steps": [
                {
                    "step_id": r.step_id,
                    "name": r.name,
                    "passed": bool(r.passed),
                    "duration_ms": int(r.duration_ms),
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
                "key_pinned": key_pinned,
                "key_provenance": (
                    "caller_supplied_signing_key"
                    if key_pinned
                    else "ephemeral_per_run_integrity_only"
                ),
            },
        }

        # Write output receipt
        out_dir = self.repo_root / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "independent_validation_receipt.json"
        out_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

        return receipt


def verify_validation_receipt(
    receipt: Dict[str, Any],
    trusted_public_key_hex: Optional[str] = None,
    allow_ephemeral_key: bool = False,
) -> Tuple[bool, str, bool]:
    """
    Verify an IndependentValidationRunner receipt.
    Fails closed when no trusted_public_key_hex is supplied unless allow_ephemeral_key=True,
    returning (valid, reason, key_pinned).
    """
    if not isinstance(receipt, dict):
        return False, "ERR_RECEIPT_NOT_OBJECT", False
    body = receipt.get("receipt_body")
    env = receipt.get("signature_envelope")
    if not isinstance(body, dict) or not isinstance(env, dict):
        return False, "ERR_MISSING_BODY_OR_ENVELOPE", False
    embedded_hex = env.get("public_key_hex")
    sig_b64 = env.get("signature_b64")
    claimed_hash = env.get("canonical_hash_sha256")
    if not isinstance(embedded_hex, str) or not isinstance(sig_b64, str):
        return False, "ERR_INVALID_ENVELOPE_FIELDS", False

    if trusted_public_key_hex is not None:
        if embedded_hex.lower() != trusted_public_key_hex.lower():
            return False, "ERR_PUBLIC_KEY_MISMATCH", False
        key_pinned = True
    elif allow_ephemeral_key:
        key_pinned = False
    else:
        return False, "ERR_UNPINNED_PUBLIC_KEY_REJECTED", False

    steps = body.get("steps")
    if steps is not None:
        val_run = body.get("validation_run")
        if not isinstance(steps, list) or not isinstance(val_run, dict):
            return False, "ERR_OUTCOMES_CAID_MISMATCH", False
        claimed_outcomes_caid = val_run.get("deterministic_outcomes_caid")
        if not isinstance(claimed_outcomes_caid, str):
            return False, "ERR_OUTCOMES_CAID_MISMATCH", False
        expected_outcomes = []
        for s in steps:
            if (
                not isinstance(s, dict)
                or not isinstance(s.get("step_id"), str)
                or not isinstance(s.get("passed"), bool)
            ):
                return False, "ERR_OUTCOMES_CAID_MISMATCH", False
            expected_outcomes.append({"step_id": s["step_id"], "passed": s["passed"]})
        expected_outcomes_caid = (
            "sha256:" + hashlib.sha256(encode_jcs(expected_outcomes)).hexdigest()
        )
        if claimed_outcomes_caid != expected_outcomes_caid:
            return False, "ERR_OUTCOMES_CAID_MISMATCH", False

    canonical_bytes = encode_jcs(body)
    expected_hash = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
    if claimed_hash != expected_hash:
        return False, "ERR_CANONICAL_HASH_MISMATCH", False

    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(embedded_hex))
        sig = base64.b64decode(sig_b64, validate=True)
        pub.verify(sig, canonical_bytes)
    except (ValueError, InvalidSignature):
        return False, "ERR_SIGNATURE_INVALID", False

    return True, "VERIFIED_PINNED" if key_pinned else "VERIFIED_EPHEMERAL_UNPINNED", key_pinned


def _run_isolated_verifier_cli(
    isolated_verifier: Path,
    tmp_dir: Path,
    cli_args: Sequence[str],
) -> Tuple[int, Dict[str, Any]]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = subprocess.run(
        [sys.executable, "-I", str(isolated_verifier), *cli_args],
        cwd=str(tmp_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    parsed: Dict[str, Any] = {}
    out_str = proc.stdout.strip()
    if out_str:
        parsed = json.loads(out_str)
    return proc.returncode, parsed


def run_external_commission_cleanroom_probe(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    """
    Executes an out-of-tree clean-room external commission verification probe
    (process isolation, not a sandbox: empty PYTHONPATH, isolated -I interpreter, temp cwd).
    """
    verifier_src = repo_root / "tools" / "standalone_offline_verifier.py"

    with tempfile.TemporaryDirectory(prefix="aeib_ext_commission_") as raw_tmp:
        tmp_dir = Path(raw_tmp)
        isolated_verifier = tmp_dir / "standalone_offline_verifier.py"
        shutil.copy2(verifier_src, isolated_verifier)

        # Generate a real Ed25519 keypair and build a signed AEIB receipt
        signing_key = Ed25519PrivateKey.generate()
        pubkey_hex = signing_key.public_key().public_bytes_raw().hex()
        action_payload = {"action": "audit_cleanroom_probe", "amount_cents": 1000, "currency": "USD"}
        action_caid = "sha256:" + hashlib.sha256(encode_jcs(action_payload)).hexdigest()
        unsigned_body = {
            "operation_id": "op-cleanroom-probe-01",
            "disposition": "CONFIRMED",
            "policy_epoch": 1,
            "action_payload": action_payload,
            "action_caid": action_caid,
            "public_key_hex": pubkey_hex,
        }
        sig_b64 = base64.b64encode(signing_key.sign(encode_jcs(unsigned_body))).decode("ascii")
        signed_receipt = {
            **unsigned_body,
            "signature_b64": sig_b64,
        }
        copied_receipt = tmp_dir / "probe_receipt.json"
        copied_receipt.write_text(json.dumps(signed_receipt, indent=2), encoding="utf-8")

        # Probe 1: nominal_pinned_verify
        rc1, out1 = _run_isolated_verifier_cli(
            isolated_verifier,
            tmp_dir,
            [
                "--verify-receipt",
                str(copied_receipt),
                "--public-key",
                pubkey_hex,
                "--json",
            ],
        )
        nominal_pinned_verified = (rc1 == 0) and (out1.get("valid") is True)

        # Probe 2: control_unpinned_rejected
        rc2, out2 = _run_isolated_verifier_cli(
            isolated_verifier,
            tmp_dir,
            ["--verify-receipt", str(copied_receipt), "--json"],
        )
        control_unpinned_rejected = (rc2 != 0) and (out2.get("valid") is False)

        # Probe 3: control_tampered_payload_rejected
        tampered_obj = json.loads(copied_receipt.read_text(encoding="utf-8"))
        tampered_obj["policy_epoch"] = 99
        tampered_path = tmp_dir / "tampered_receipt.json"
        tampered_path.write_text(json.dumps(tampered_obj), encoding="utf-8")
        rc3, out3 = _run_isolated_verifier_cli(
            isolated_verifier,
            tmp_dir,
            [
                "--verify-receipt",
                str(tampered_path),
                "--public-key",
                pubkey_hex,
                "--json",
            ],
        )
        control_tampered_payload_rejected = (rc3 != 0) and (out3.get("valid") is False)

        # Probe 4: control_wrong_pubkey_rejected
        wrong_hex = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
        rc4, out4 = _run_isolated_verifier_cli(
            isolated_verifier,
            tmp_dir,
            [
                "--verify-receipt",
                str(copied_receipt),
                "--public-key",
                wrong_hex,
                "--json",
            ],
        )
        control_wrong_pubkey_rejected = (rc4 != 0) and (out4.get("valid") is False)

    # Probe 5: deterministic_bundle_reproducibility
    sample_artifacts = {
        "manifest.json": {"schema_version": 1, "step_count": 2},
        "outcomes.json": {"all_passed": True, "verified_steps": 2},
    }
    b1, c1 = ReproducibleEvidenceBundleBuilder.build_deterministic_bundle_bytes(sample_artifacts)
    b2, c2 = ReproducibleEvidenceBundleBuilder.build_deterministic_bundle_bytes(sample_artifacts)
    extracted = ReproducibleEvidenceBundleBuilder.verify_and_extract_bundle(b1, c1)
    tampered_bundle = bytearray(b1)
    tampered_bundle[-1] ^= 0x01
    tamper_rejected = False
    try:
        ReproducibleEvidenceBundleBuilder.verify_and_extract_bundle(bytes(tampered_bundle), c1)
    except ValueError:
        tamper_rejected = True

    bundle_reproducible_and_tamper_evident = (
        (b1 == b2)
        and (c1 == c2)
        and (extracted == sample_artifacts)
        and tamper_rejected
    )

    all_probes_held = (
        nominal_pinned_verified
        and control_unpinned_rejected
        and control_tampered_payload_rejected
        and control_wrong_pubkey_rejected
        and bundle_reproducible_and_tamper_evident
    )

    return {
        "all_probes_held": bool(all_probes_held),
        "nominal_pinned_verified": bool(nominal_pinned_verified),
        "control_unpinned_rejected": bool(control_unpinned_rejected),
        "control_tampered_payload_rejected": bool(control_tampered_payload_rejected),
        "control_wrong_pubkey_rejected": bool(control_wrong_pubkey_rejected),
        "bundle_reproducible_and_tamper_evident": bool(bundle_reproducible_and_tamper_evident),
        "bundle_caid": c1,
    }


def main(
    repo_root: Path = REPO_ROOT,
    steps_override: Optional[Sequence[Tuple[str, str, List[str]]]] = None,
) -> None:
    runner = IndependentValidationRunner(repo_root=repo_root, steps_override=steps_override)
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
