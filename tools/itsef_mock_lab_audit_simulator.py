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
tools/itsef_mock_lab_audit_simulator.py
================================================================================
Third-Party ITSEF Laboratory Evaluation Sign-Off & Mock Audit Simulator.

Simulates an accredited Common Criteria Information Technology Security Evaluation
Facility (ITSEF) laboratory performing an independent audit of the AEIB v1.1
Common Criteria EAL4+ Submission Pack:
1. Submission Pack Merkle Integrity Verification:
   - Recomputes SHA-256 digests of all 6 formal evaluation artifacts.
   - Reconstructs and validates the binary submission Merkle root.
2. Independent Evaluator Test Execution (ATE_IND.2):
   - Executes 05_INDEPENDENT_TEST_RUNNER_ATE_IND_2.py in an isolated subprocess.
3. Formal CEM Work Unit Conformance Assessment:
   - Validates all 11 ISO/IEC 18045 CEM work units.
4. Multi-Cloud Hardware Security Module (Cloud HSM) Remote Quorum Sign-Off:
   - Executes an M-of-N (3-of-5) threshold quorum authorization across simulated
     independent evaluation authorities (TÜV, CEA, SGS, ANSSI, BSI).
5. Emits an RFC 8785 sealed evaluation verdict:
   output/itsef_evaluation_lab_signoff_verdict.json.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.cloud_hsm_remote_quorum import (
    QUORUM_STATUS_ESTABLISHED,
    CloudHsmEnclaveNode,
    CloudHsmRemoteQuorumCoordinator,
    QuorumAuthorizationReceipt,
)
from src.jcs_canonicalizer import encode_jcs

DEFAULT_PACK_DIR: Path = _REPO_ROOT / "dist" / "common_criteria_eal4_submission_pack"
DEFAULT_OUTPUT_FILE: Path = _REPO_ROOT / "output" / "itsef_evaluation_lab_signoff_verdict.json"

VERDICT_CONFORMANCE_VERIFIED: str = "ACCREDITED_CONFORMANCE_VERIFIED"
STATUS_INTERNAL_PREVIEW: str = "INTERNAL PREVIEW COMMISSIONED"
TARGET_TOE: str = "SovereignNexus AEIB v1.1"
TARGET_EAL: str = "EAL4+ (ALC_FLR.2 + AVA_VAN.4)"


def sha256_jcs_caid(payload: Any) -> str:
    """Computes deterministic SHA-256 CAID digest over RFC 8785 canonical bytes."""
    raw = payload if isinstance(payload, bytes) else encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class ItsefLabVerdict:
    """Accredited ITSEF Laboratory Evaluation Sign-off Verdict."""

    verdict_id: str
    lab_identifier: str
    evaluation_target: str
    assurance_level: str
    status: str
    submission_manifest_caid: str
    submission_merkle_root: str
    ate_ind_test_verdict: str
    cem_work_units_passed: int
    cem_work_units_total: int
    cem_compliance_score_bps: int
    hsm_quorum_status: str
    hsm_quorum_receipt_caid: str
    overall_evaluation_verdict: str
    created_epoch_ms: int
    verdict_caid: str

    def __post_init__(self) -> None:
        if not isinstance(self.verdict_id, str) or not self.verdict_id.strip():
            raise ValueError("ERR_INVALID_VERDICT_ID")
        if not isinstance(self.lab_identifier, str) or not self.lab_identifier.strip():
            raise ValueError("ERR_INVALID_LAB_IDENTIFIER")
        if self.evaluation_target != TARGET_TOE:
            raise ValueError(f"ERR_INVALID_TOE: {self.evaluation_target}")
        if self.assurance_level != TARGET_EAL:
            raise ValueError(f"ERR_INVALID_ASSURANCE_LEVEL: {self.assurance_level}")
        if self.status != STATUS_INTERNAL_PREVIEW:
            raise ValueError(f"ERR_INVALID_STATUS: {self.status}")
        if not self.submission_manifest_caid.startswith("sha256:"):
            raise ValueError("ERR_INVALID_MANIFEST_CAID")
        if not self.submission_merkle_root.startswith("sha256:"):
            raise ValueError("ERR_INVALID_MERKLE_ROOT")
        if self.ate_ind_test_verdict != "PASS_VERIFIED":
            raise ValueError(f"ERR_INVALID_ATE_IND_VERDICT: {self.ate_ind_test_verdict}")
        if type(self.cem_work_units_passed) is not int or self.cem_work_units_passed < 0:
            raise ValueError("ERR_INVALID_WORK_UNITS_PASSED")
        if type(self.cem_work_units_total) is not int or self.cem_work_units_total <= 0:
            raise ValueError("ERR_INVALID_WORK_UNITS_TOTAL")
        if type(self.cem_compliance_score_bps) is not int or self.cem_compliance_score_bps < 0:
            raise ValueError("ERR_INVALID_COMPLIANCE_SCORE_BPS")
        if self.hsm_quorum_status != QUORUM_STATUS_ESTABLISHED:
            raise ValueError(f"ERR_INVALID_QUORUM_STATUS: {self.hsm_quorum_status}")
        if not self.hsm_quorum_receipt_caid.startswith("sha256:"):
            raise ValueError("ERR_INVALID_QUORUM_RECEIPT_CAID")
        if self.overall_evaluation_verdict != VERDICT_CONFORMANCE_VERIFIED:
            raise ValueError(f"ERR_INVALID_OVERALL_VERDICT: {self.overall_evaluation_verdict}")
        if type(self.created_epoch_ms) is not int or self.created_epoch_ms <= 0:
            raise ValueError("ERR_INVALID_CREATED_EPOCH_MS")
        if not self.verdict_caid.startswith("sha256:"):
            raise ValueError("ERR_INVALID_VERDICT_CAID")


class ItsefMockLabAuditSimulator:
    """Simulates an accredited ITSEF evaluation lab performing EAL4+ sign-off."""

    def __init__(
        self,
        pack_dir: Optional[Path] = None,
        output_file: Optional[Path] = None,
        lab_identifier: str = "ITSEF-ACCREDITED-SIMULATOR-LAB-01",
    ) -> None:
        self.pack_dir = pack_dir or DEFAULT_PACK_DIR
        self.output_file = output_file or DEFAULT_OUTPUT_FILE
        self.lab_identifier = lab_identifier

    def verify_submission_pack_integrity(self) -> Dict[str, Any]:
        """Validates all file hashes and Merkle tree root of the submission pack."""
        manifest_path = self.pack_dir / "SUBMISSION_MANIFEST.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"ERR_MANIFEST_NOT_FOUND: {manifest_path}")

        raw_bytes = manifest_path.read_bytes()
        manifest_dict = json.loads(raw_bytes.decode("utf-8"))

        documents = manifest_dict.get("documents", {})
        if len(documents) < 6:
            raise ValueError(f"ERR_INSUFFICIENT_DOCUMENTS: {len(documents)} < 6")

        leaf_hashes: List[bytes] = []
        for filename in sorted(documents.keys()):
            doc_meta = documents[filename]
            doc_file = self.pack_dir / filename
            if not doc_file.exists():
                raise FileNotFoundError(f"ERR_DOCUMENT_FILE_MISSING: {filename}")

            file_bytes = doc_file.read_bytes()
            computed_sha = f"sha256:{hashlib.sha256(file_bytes).hexdigest()}"
            expected_sha = doc_meta.get("sha256")
            if computed_sha != expected_sha:
                raise ValueError(f"ERR_FILE_DIGEST_MISMATCH: {filename} {computed_sha} != {expected_sha}")

            leaf_hashes.append(hashlib.sha256(file_bytes).digest())

        # Compute Merkle tree root
        current_layer = leaf_hashes
        while len(current_layer) > 1:
            next_layer = []
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i + 1] if i + 1 < len(current_layer) else left
                parent = hashlib.sha256(left + right).digest()
                next_layer.append(parent)
            current_layer = next_layer

        recomputed_root = f"sha256:{current_layer[0].hex()}"
        expected_root = manifest_dict.get("submission_merkle_root")
        if recomputed_root != expected_root:
            raise ValueError(f"ERR_MERKLE_ROOT_MISMATCH: {recomputed_root} != {expected_root}")

        # Compute manifest CAID
        unsealed = dict(manifest_dict)
        unsealed.pop("manifest_caid", None)
        computed_manifest_caid = sha256_jcs_caid(unsealed)
        expected_manifest_caid = manifest_dict.get("manifest_caid")
        if computed_manifest_caid != expected_manifest_caid:
            raise ValueError(f"ERR_MANIFEST_CAID_MISMATCH: {computed_manifest_caid} != {expected_manifest_caid}")

        return {
            "valid": True,
            "manifest_caid": computed_manifest_caid,
            "submission_merkle_root": recomputed_root,
            "documents_count": len(documents),
        }

    def execute_independent_evaluator_harness(self) -> Dict[str, Any]:
        """Runs the standalone ATE_IND.2 evaluator harness in an isolated subprocess."""
        runner_path = self.pack_dir / "05_INDEPENDENT_TEST_RUNNER_ATE_IND_2.py"
        if not runner_path.exists():
            raise FileNotFoundError(f"ERR_ATE_IND_RUNNER_MISSING: {runner_path}")

        proc = subprocess.run(
            [sys.executable, str(runner_path)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )

        if proc.returncode != 0:
            raise RuntimeError(f"ERR_ATE_IND_EXECUTION_FAILED (code {proc.returncode}):\n{proc.stderr}")

        if "CONFORMANCE_EVALUATION_COMPLETE" not in proc.stdout:
            raise RuntimeError("ERR_ATE_IND_VERDICT_NOT_FOUND_IN_OUTPUT")

        return {
            "verdict": "PASS_VERIFIED",
            "returncode": proc.returncode,
            "stdout_summary": "CONFORMANCE_EVALUATION_COMPLETE",
        }

    def evaluate_cem_work_units(self) -> Dict[str, Any]:
        """Evaluates all 11 formal ISO/IEC 18045 CEM work units."""
        from tools.itsef_cem_evaluation_runner import ITSEFCEMEvaluationRunner

        cem_runner = ITSEFCEMEvaluationRunner(pack_dir=self.pack_dir)
        report, telemetry = cem_runner.run_evaluation_audit()

        if report.compliance_score_bps < 10000:
            raise ValueError(f"ERR_CEM_COMPLIANCE_INCOMPLETE: {report.compliance_score_bps} < 10000 bps")

        return {
            "passed_count": report.work_units_conforming_count,
            "total_count": report.work_units_evaluated_count,
            "compliance_score_bps": report.compliance_score_bps,
            "etr_caid": report.etr_caid,
        }

    def execute_hsm_quorum_signoff(
        self,
        submission_digest_hex: str,
        cluster_epoch_id: int = 1,
        now_ms: Optional[int] = None,
    ) -> QuorumAuthorizationReceipt:
        """Executes multi-cloud HSM remote quorum authorization for the audit sign-off."""
        nodes = [
            CloudHsmEnclaveNode("auditor-tuv-rheinland", "SOFTHSM_PKCS11", "ECDSA_P256_SHA256"),
            CloudHsmEnclaveNode("auditor-cea-leti", "GCP_CLOUD_KMS", "ECDSA_P256_SHA256"),
            CloudHsmEnclaveNode("auditor-sgs-brightsight", "AWS_KMS", "ED25519"),
            CloudHsmEnclaveNode("auditor-anssi-observer", "AZURE_KEY_VAULT", "ED25519"),
            CloudHsmEnclaveNode("auditor-bsi-validator", "APPLE_SECURE_ENCLAVE", "ECDSA_P256_SHA256"),
        ]

        coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=cluster_epoch_id)
        current_time = now_ms if now_ms is not None else int(time.time() * 1000)

        for node in nodes:
            coordinator.register_node_record(node.to_record(current_time))

        action_type = "ITSEF_EAL4_EVALUATION_SIGNOFF"
        payload = {
            "action": action_type,
            "submission_digest_hex": submission_digest_hex,
            "cluster_epoch_id": cluster_epoch_id,
        }
        digest_hex = sha256_jcs_caid(payload).split("sha256:")[1]

        # 3 independent evaluation authorities provide signed authorization shares
        shares = [
            nodes[0].sign_share(action_type, digest_hex, cluster_epoch_id, nonce="nonce-tuv-01", signed_at_epoch_ms=current_time),
            nodes[1].sign_share(action_type, digest_hex, cluster_epoch_id, nonce="nonce-cea-01", signed_at_epoch_ms=current_time),
            nodes[2].sign_share(action_type, digest_hex, cluster_epoch_id, nonce="nonce-sgs-01", signed_at_epoch_ms=current_time),
        ]

        receipt = coordinator.evaluate_quorum(
            action_type=action_type,
            payload=payload,
            shares=shares,
            cluster_epoch_id=cluster_epoch_id,
            evaluation_time_ms=current_time,
        )

        if receipt.quorum_status != QUORUM_STATUS_ESTABLISHED:
            raise RuntimeError(f"ERR_HSM_QUORUM_FAILED: {receipt.quorum_status}")

        return receipt

    def run_simulation(self, cluster_epoch_id: int = 1, current_time_ms: Optional[int] = None) -> Tuple[ItsefLabVerdict, Dict[str, Any]]:
        """Executes full ITSEF laboratory independent evaluation simulation."""
        now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)

        # 1. Integrity check
        pack_integrity = self.verify_submission_pack_integrity()

        # 2. Independent test execution
        ate_result = self.execute_independent_evaluator_harness()

        # 3. Formal CEM audit
        cem_result = self.evaluate_cem_work_units()

        # 4. HSM Quorum sign-off
        merkle_root_hex = pack_integrity["submission_merkle_root"].split("sha256:")[1]
        quorum_receipt = self.execute_hsm_quorum_signoff(merkle_root_hex, cluster_epoch_id=cluster_epoch_id, now_ms=now_ms)

        verdict_id = f"verdict-itsef-eal4-{cluster_epoch_id}-{now_ms}"

        unsealed_verdict: Dict[str, Any] = {
            "assurance_level": TARGET_EAL,
            "ate_ind_test_verdict": ate_result["verdict"],
            "cem_compliance_score_bps": cem_result["compliance_score_bps"],
            "cem_work_units_passed": cem_result["passed_count"],
            "cem_work_units_total": cem_result["total_count"],
            "created_epoch_ms": now_ms,
            "evaluation_target": TARGET_TOE,
            "hsm_quorum_receipt_caid": quorum_receipt.receipt_caid,
            "hsm_quorum_status": quorum_receipt.quorum_status,
            "lab_identifier": self.lab_identifier,
            "overall_evaluation_verdict": VERDICT_CONFORMANCE_VERIFIED,
            "status": STATUS_INTERNAL_PREVIEW,
            "submission_manifest_caid": pack_integrity["manifest_caid"],
            "submission_merkle_root": pack_integrity["submission_merkle_root"],
            "verdict_id": verdict_id,
        }

        verdict_caid = sha256_jcs_caid(unsealed_verdict)

        verdict = ItsefLabVerdict(
            verdict_id=verdict_id,
            lab_identifier=self.lab_identifier,
            evaluation_target=TARGET_TOE,
            assurance_level=TARGET_EAL,
            status=STATUS_INTERNAL_PREVIEW,
            submission_manifest_caid=pack_integrity["manifest_caid"],
            submission_merkle_root=pack_integrity["submission_merkle_root"],
            ate_ind_test_verdict=ate_result["verdict"],
            cem_work_units_passed=cem_result["passed_count"],
            cem_work_units_total=cem_result["total_count"],
            cem_compliance_score_bps=cem_result["compliance_score_bps"],
            hsm_quorum_status=quorum_receipt.quorum_status,
            hsm_quorum_receipt_caid=quorum_receipt.receipt_caid,
            overall_evaluation_verdict=VERDICT_CONFORMANCE_VERIFIED,
            created_epoch_ms=now_ms,
            verdict_caid=verdict_caid,
        )

        full_dossier = {
            "verdict": asdict(verdict),
            "pack_integrity": pack_integrity,
            "ate_ind_execution": ate_result,
            "cem_evaluation": cem_result,
            "hsm_quorum_authorization": asdict(quorum_receipt),
            "dossier_caid": verdict_caid,
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        canonical_bytes = encode_jcs(full_dossier)
        self.output_file.write_bytes(canonical_bytes)

        return verdict, full_dossier

    def verify_verdict_file(self, verdict_path: Optional[Path] = None) -> bool:
        """Verifies the cryptographic and structural integrity of an existing verdict file."""
        target_path = verdict_path or self.output_file
        if not target_path.exists():
            return False

        try:
            raw_bytes = target_path.read_bytes()
            dossier = json.loads(raw_bytes.decode("utf-8"))

            verdict_dict = dossier.get("verdict")
            if not isinstance(verdict_dict, dict):
                return False

            expected_caid = verdict_dict.get("verdict_caid")
            unsealed = dict(verdict_dict)
            unsealed.pop("verdict_caid", None)
            computed_caid = sha256_jcs_caid(unsealed)

            if computed_caid != expected_caid:
                return False
            if dossier.get("dossier_caid") != expected_caid:
                return False

            # Verify values
            if verdict_dict.get("status") != STATUS_INTERNAL_PREVIEW:
                return False
            if verdict_dict.get("overall_evaluation_verdict") != VERDICT_CONFORMANCE_VERIFIED:
                return False
            if verdict_dict.get("cem_compliance_score_bps") != 10000:
                return False
            if verdict_dict.get("hsm_quorum_status") != QUORUM_STATUS_ESTABLISHED:
                return False

            return True
        except Exception:
            return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Third-Party ITSEF Laboratory Evaluation Sign-Off Simulator")
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR, help="Path to CC EAL4+ Submission Pack")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE, help="Path to write verdict dossier JSON")
    parser.add_argument("--cluster-epoch-id", type=int, default=1, help="Cluster epoch ID for HSM quorum")
    parser.add_argument("--verify", action="store_true", help="Verify existing evaluation verdict file")

    args = parser.parse_args()
    simulator = ItsefMockLabAuditSimulator(pack_dir=args.pack_dir, output_file=args.output)

    if args.verify:
        is_valid = simulator.verify_verdict_file()
        if is_valid:
            print(f"[✓] ITSEF Evaluation Lab Verdict Integrity Verified: {args.output}")
            return 0
        else:
            print(f"[✗] ITSEF Evaluation Lab Verdict Integrity Check FAILED: {args.output}", file=sys.stderr)
            return 1

    print("================================================================================")
    print("  THIRD-PARTY ITSEF LABORATORY INDEPENDENT EVALUATION SIGN-OFF SIMULATOR")
    print(f"  Status: {STATUS_INTERNAL_PREVIEW}")
    print(f"  Target: {TARGET_TOE} ({TARGET_EAL})")
    print("================================================================================")

    verdict, dossier = simulator.run_simulation(cluster_epoch_id=args.cluster_epoch_id)
    print(f"  [✓] Submission Pack Merkle Integrity: {verdict.submission_merkle_root}")
    print(f"  [✓] Independent Test Harness (ATE_IND.2): {verdict.ate_ind_test_verdict}")
    print(f"  [✓] CEM Work Units Conformance: {verdict.cem_work_units_passed}/{verdict.cem_work_units_total} (10,000 bps)")
    print(f"  [✓] Multi-Cloud HSM Remote Quorum: {verdict.hsm_quorum_status} (3-of-5 threshold)")
    print("--------------------------------------------------------------------------------")
    print(f"  OVERALL EVALUATION VERDICT: {verdict.overall_evaluation_verdict}")
    print(f"  Verdict CAID: {verdict.verdict_caid}")
    print(f"  Output Dossier: {args.output}")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
