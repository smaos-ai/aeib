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
src/evidence_carrying_termination.py
================================================================================
Evidence-Carrying Termination Certificate (ECTC) & Test Integrity Gate.

Evaluated under the stated model:
Addresses the 2026 Semantic Termination and Reward Hacking frontier:
1. Test-Suite Hash Locking (ImpossibleBench defense, arXiv:2510.20270):
   Captures SHA-256 Merkle digests of all test files pre-execution. Fails closed with
   `HALT_TEST_TAMPERED` if any test file is modified, deleted, or added without an
   explicit Ed25519-signed `TestModificationWarrant`.
2. Stopping as a Database Property (arXiv:2605.01160):
   Loop termination is an SQL predicate evaluated over an auditable SQLite ledger
   (`task_requirements`), rather than an ungrounded model assertion.
3. Evidence-Carrying Termination Certificate (ECTC):
   Binds requirements, task id, test-run receipts, and artifact hashes under an
   RFC 8785 canonical envelope signed by the evaluating oracle.
4. AST / Cycle Convergence Early-Stopping:
   Detects semantic stagnation or oscillation across revision attempts.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs


class HaltTestTamperedError(Exception):
    """Raised when test suite files have been modified without an authorized warrant."""


class HaltTerminationRefusedError(Exception):
    """Raised when an agent attempts to terminate without an admissible certificate."""


@dataclass(frozen=True)
class TestModificationWarrant:
    """Explicit governance authorization required to modify tests under evaluation."""

    __test__ = False

    warrant_id: str
    authorized_test_paths: Tuple[str, ...]
    justification: str
    issuer_public_key_hex: str
    signature_hex: str

    def verify_signature(self) -> bool:
        payload = {
            "warrant_id": self.warrant_id,
            "authorized_test_paths": list(self.authorized_test_paths),
            "justification": self.justification,
            "issuer_public_key_hex": self.issuer_public_key_hex,
        }
        canonical_bytes = encode_jcs(payload)
        pubkey = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(self.issuer_public_key_hex)
        )
        try:
            pubkey.verify(bytes.fromhex(self.signature_hex), canonical_bytes)
            return True
        except InvalidSignature:
            return False


@dataclass(frozen=True)
class EvidenceCarryingTerminationCertificate:
    """Cryptographic certificate required before an agent is permitted to exit."""

    task_id: str
    requirements: Tuple[str, ...]
    test_suite_digest: str
    test_run_receipt: Dict[str, Any]
    artifact_digests: Dict[str, str]
    timestamp_epoch_s: int
    nonce: str
    issuer_public_key_hex: str
    signature_hex: str

    def payload_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "requirements": list(self.requirements),
            "test_suite_digest": self.test_suite_digest,
            "test_run_receipt": self.test_run_receipt,
            "artifact_digests": self.artifact_digests,
            "timestamp_epoch_s": self.timestamp_epoch_s,
            "nonce": self.nonce,
            "issuer_public_key_hex": self.issuer_public_key_hex,
        }

    def verify(self) -> Tuple[bool, str]:
        canonical_bytes = encode_jcs(self.payload_dict())
        try:
            pubkey = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(self.issuer_public_key_hex)
            )
            pubkey.verify(bytes.fromhex(self.signature_hex), canonical_bytes)
        except (InvalidSignature, ValueError) as exc:
            return False, f"ERR_INVALID_ECTC_SIGNATURE: {exc}"

        # Test run receipt validation
        exit_code = self.test_run_receipt.get("exit_code")
        failed = self.test_run_receipt.get("failed", 0)
        passed = self.test_run_receipt.get("passed", 0)

        if exit_code != 0:
            return False, f"ERR_TEST_RECEIPT_NONZERO_EXIT: {exit_code}"
        if failed != 0:
            return False, f"ERR_TEST_RECEIPT_FAILURES_DETECTED: {failed}"
        if passed <= 0:
            return False, "ERR_TEST_RECEIPT_ZERO_TESTS_PASSED"

        return True, "VERIFIED_ECTC_VALID"


class TestSuiteHashLock:
    """Enforces SHA-256 test-suite immutability across agent runs."""

    __test__ = False

    @classmethod
    def compute_manifest(cls, tests_dir: Path) -> Dict[str, str]:
        manifest: Dict[str, str] = {}
        if not tests_dir.exists():
            return manifest

        for root, _, files in sorted(os.walk(tests_dir)):
            for f in sorted(files):
                if f.startswith("test_") and f.endswith(".py"):
                    full_p = Path(root) / f
                    rel_p = str(full_p.relative_to(tests_dir))
                    content = full_p.read_bytes()
                    manifest[rel_p] = hashlib.sha256(content).hexdigest()
        return manifest

    @classmethod
    def compute_manifest_digest(cls, manifest: Dict[str, str]) -> str:
        canonical_bytes = encode_jcs(manifest)
        return hashlib.sha256(canonical_bytes).hexdigest()

    @classmethod
    def verify_integrity(
        cls,
        tests_dir: Path,
        baseline_manifest: Dict[str, str],
        warrant: Optional[TestModificationWarrant] = None,
    ) -> Tuple[bool, str]:
        current = cls.compute_manifest(tests_dir)
        all_keys = sorted(set(baseline_manifest.keys()) | set(current.keys()))

        authorized_paths: Set[str] = set()
        if warrant is not None:
            if not warrant.verify_signature():
                return False, "HALT_TEST_TAMPERED: INVALID_WARRANT_SIGNATURE"
            authorized_paths = set(warrant.authorized_test_paths)

        for k in all_keys:
            if k not in baseline_manifest:
                if k not in authorized_paths:
                    return False, f"HALT_TEST_TAMPERED: UNEXPECTED_TEST_FILE_ADDED_{k}"
            elif k not in current:
                if k not in authorized_paths:
                    return False, f"HALT_TEST_TAMPERED: TEST_FILE_DELETED_{k}"
            elif baseline_manifest[k] != current[k]:
                if k not in authorized_paths:
                    return False, f"HALT_TEST_TAMPERED: TEST_FILE_MUTATED_{k}"

        return True, "OK_TEST_SUITE_INTEGRITY_PRESERVED"


class TaskStateLedger:
    """Stopping as a Database Property: Relational state ledger for termination predicates."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.conn = sqlite3.connect(db_path or ":memory:")
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_requirements (
                    task_id TEXT NOT NULL,
                    requirement_id TEXT NOT NULL,
                    is_satisfied INTEGER NOT NULL DEFAULT 0,
                    ectc_digest TEXT,
                    PRIMARY KEY (task_id, requirement_id)
                )
                """
            )

    def record_requirement(
        self,
        task_id: str,
        requirement_id: str,
        is_satisfied: bool = False,
        ectc_digest: Optional[str] = None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO task_requirements (task_id, requirement_id, is_satisfied, ectc_digest)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(task_id, requirement_id) DO UPDATE SET
                    is_satisfied = excluded.is_satisfied,
                    ectc_digest = excluded.ectc_digest
                """,
                (task_id, requirement_id, 1 if is_satisfied else 0, ectc_digest),
            )

    def evaluate_termination_predicate(self, task_id: str) -> Tuple[bool, str]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM task_requirements
            WHERE task_id = ? AND (is_satisfied = 0 OR ectc_digest IS NULL)
            """,
            (task_id,),
        )
        row = cur.fetchone()
        unsatisfied_count = row[0] if row else 0

        # Also check if total requirements exist
        cur.execute(
            "SELECT COUNT(*) FROM task_requirements WHERE task_id = ?", (task_id,)
        )
        total_row = cur.fetchone()
        total_count = total_row[0] if total_row else 0

        if total_count == 0:
            return False, "HALT_NO_REQUIREMENTS_REGISTERED"

        if unsatisfied_count > 0:
            return False, f"HALT_UNSATISFIED_REQUIREMENTS_{unsatisfied_count}_REMAINING"

        return True, "TERMINATION_ADMISSIBLE_ALL_REQUIREMENTS_CERTIFIED"


class SemanticConvergenceMonitor:
    """Detects cycles and semantic stagnation across iterative agent attempts."""

    @classmethod
    def evaluate_convergence(
        cls, history_hashes: Sequence[str], current_hash: str
    ) -> Tuple[bool, str]:
        # If current hash matches the immediately preceding one: direct no-op
        if history_hashes and history_hashes[-1] == current_hash:
            return False, "HALT_IMMEDIATE_NO_OP_DETECTED"

        # If current hash appears twice in prior history: oscillation cycle
        if history_hashes.count(current_hash) >= 2:
            return False, "HALT_CYCLE_STAGNATION_DETECTED"

        return True, "OK_CONVERGENCE_HEALTHY"
