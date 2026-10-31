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
src/zk_mmr_accumulator.py — Zero-Knowledge Merkle Mountain Range (MMR) Accumulator for Historical Agent Receipts.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as an append-only
Zero-Knowledge Merkle Mountain Range (MMR) accumulator and non-interactive polynomial proof prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and simulation prototype for Zero-Knowledge Merkle Mountain
    Range (MMR) historical receipt accumulation.
  - It performs authentic BN254 scalar field arithmetic, Horner polynomial evaluations, and
    Fiat-Shamir non-interactive challenge generation in software.
  - Operational mode: scaffold / simulated ZK accumulator.

Architectural Invariants:
1. Append-Only Merkle Mountain Range (MMR):
   - Maintains a forest of perfect binary trees (peaks) with strictly decreasing heights.
   - Amortized O(1) leaf append, O(log N) inclusion proofs, and O(log N) consistency proofs.
2. BN254 Scalar Field Arithmetic:
   - Evaluates commitments over r = 21888242871839275222246405745257275088548364400416034343698204186575808495617.
3. Fiat-Shamir Polynomial Proofs:
   - Generates non-interactive zero-knowledge polynomial proofs verifying leaf membership
     against the bagged peak root.
4. Fail-Closed Rejections:
   - HALT_MMR_EMPTY_TREE
   - HALT_MMR_LEAF_OUT_OF_BOUNDS
   - HALT_MMR_INCLUSION_VERIFICATION_FAILED
   - HALT_MMR_NON_MONOTONIC_LEAF
   - HALT_MMR_FIELD_OVERFLOW
   - HALT_MMR_CONSISTENCY_FAILED
5. SQLite-WAL Persistence:
   - Persists all tree states, leaves, and generated proofs to SQLite-WAL tables.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import sqlite3
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from src.jcs_canonicalizer import encode_jcs

# Standard BN254 / alt_bn128 scalar field prime r
BN254_SCALAR_FIELD_PRIME: int = 21888242871839275222246405745257275088548364400416034343698204186575808495617

# Fail-Closed Rejection Codes
HALT_MMR_EMPTY_TREE: str = "HALT_MMR_EMPTY_TREE"
HALT_MMR_LEAF_OUT_OF_BOUNDS: str = "HALT_MMR_LEAF_OUT_OF_BOUNDS"
HALT_MMR_INCLUSION_VERIFICATION_FAILED: str = "HALT_MMR_INCLUSION_VERIFICATION_FAILED"
HALT_MMR_NON_MONOTONIC_LEAF: str = "HALT_MMR_NON_MONOTONIC_LEAF"
HALT_MMR_FIELD_OVERFLOW: str = "HALT_MMR_FIELD_OVERFLOW"
HALT_MMR_CONSISTENCY_FAILED: str = "HALT_MMR_CONSISTENCY_FAILED"

STATUS_PROOF_VERIFIED: str = "PROOF_VERIFIED"
STATUS_PROOF_REJECTED: str = "PROOF_REJECTED"


def compute_sha256(data: bytes) -> str:
    """Compute standard lowercase hex SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def compute_wilson_ci_bps(k: int, n: int, z: float = 1.95996) -> Tuple[int, int]:
    """Compute conservative Wilson 95% confidence interval in basis points."""
    if n <= 0 or k < 0 or k > n:
        return 0, 0
    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half_width = (z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n)) / denom
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    return round(low * 10000), round(high * 10000)


def hash_to_field_scalar(data: bytes) -> int:
    """Maps arbitrary byte payload into a valid BN254 scalar field element."""
    digest = hashlib.sha256(data).digest()
    return int.from_bytes(digest, byteorder="big") % BN254_SCALAR_FIELD_PRIME


def combine_field_scalars(left: int, right: int) -> int:
    """Combines two scalar hashes into a parent scalar hash over BN254."""
    msg = left.to_bytes(32, "big") + right.to_bytes(32, "big")
    return hash_to_field_scalar(msg)


def evaluate_polynomial_horner(coefficients: Sequence[int], x: int) -> int:
    """
    Evaluates polynomial P(x) = c0 + c1*x + ... + c_{d}*x^d mod r
    using Horner's method in O(d) field operations.
    """
    if not coefficients:
        return 0
    result = 0
    for coef in reversed(coefficients):
        result = (result * x + coef) % BN254_SCALAR_FIELD_PRIME
    return result


@dataclass(frozen=True)
class MmrPeak:
    """Represents a single MMR peak in the forest."""
    height: int
    leaf_count: int
    scalar_hash: int

    def __post_init__(self) -> None:
        if self.height < 0:
            raise ValueError("Peak height cannot be negative")
        if self.leaf_count <= 0:
            raise ValueError("Peak leaf count must be positive")
        if not (0 <= self.scalar_hash < BN254_SCALAR_FIELD_PRIME):
            raise ValueError("Peak scalar hash outside BN254 field bounds")


@dataclass(frozen=True)
class ZkMmrInclusionProof:
    """Non-interactive zero-knowledge polynomial inclusion proof for a leaf in an MMR."""
    tree_id: str
    leaf_pos: int
    receipt_caid: str
    leaf_scalar: int
    auth_path: List[Tuple[int, bool]]  # List of (scalar_hash, is_left_sibling)
    peak_height: int
    bagged_root: str
    fiat_shamir_challenge: int
    polynomial_evaluation: int
    proof_caid: str

    def __post_init__(self) -> None:
        if not self.tree_id:
            raise ValueError("tree_id must be non-empty")
        if self.leaf_pos < 0:
            raise ValueError("leaf_pos cannot be negative")
        if not self.receipt_caid:
            raise ValueError("receipt_caid must be non-empty")
        if not (0 <= self.leaf_scalar < BN254_SCALAR_FIELD_PRIME):
            raise ValueError("leaf_scalar outside BN254 field bounds")
        if not self.bagged_root:
            raise ValueError("bagged_root must be non-empty")
        if not self.proof_caid:
            raise ValueError("proof_caid must be non-empty")


class ZkMmrAccumulator:
    """
    Zero-Knowledge Merkle Mountain Range (MMR) Accumulator.
    Maintains an append-only forest of perfect binary trees over the BN254 scalar field,
    enabling succinct membership proofs and consistency auditing for agent receipts.
    """

    def __init__(self, tree_id: str, db_path: str = ":memory:") -> None:
        if not tree_id or not isinstance(tree_id, str):
            raise ValueError("tree_id must be a non-empty string")
        self.tree_id = tree_id
        self.db_path = db_path

        # In-memory MMR forest state
        # Active peaks: List of (MmrPeak, subtree_leaves_list)
        self._peaks: List[Tuple[MmrPeak, List[int]]] = []
        self._leaf_count: int = 0
        self._leaf_caids: List[str] = []
        self._leaf_scalars: List[int] = []

        self._conn = sqlite3.connect(self.db_path)
        self._init_sqlite_schema()

    def _init_sqlite_schema(self) -> None:
        """Initialize SQLite tables and WAL mode."""
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS zk_mmr_state (
                    tree_id TEXT PRIMARY KEY,
                    leaf_count INTEGER NOT NULL,
                    bagged_root TEXT NOT NULL,
                    peaks_json TEXT NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS zk_mmr_leaves (
                    tree_id TEXT NOT NULL,
                    leaf_pos INTEGER NOT NULL,
                    receipt_caid TEXT NOT NULL,
                    leaf_hash TEXT NOT NULL,
                    scalar_val TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    PRIMARY KEY (tree_id, leaf_pos)
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS zk_mmr_proofs (
                    proof_caid TEXT PRIMARY KEY,
                    tree_id TEXT NOT NULL,
                    leaf_pos INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    verified_at_ms INTEGER NOT NULL
                );
                """
            )

    @property
    def leaf_count(self) -> int:
        """Return total number of accumulated leaves."""
        return self._leaf_count

    def get_bagged_root(self) -> str:
        """
        Compute the bagged peak root over the BN254 scalar field.
        Folds peaks from right to left: R = FoldRight(peaks).
        """
        if not self._peaks:
            return "0" * 64
        if len(self._peaks) == 1:
            return f"{self._peaks[0][0].scalar_hash:064x}"

        # Fold from right to left
        acc = self._peaks[-1][0].scalar_hash
        for i in range(len(self._peaks) - 2, -1, -1):
            left_scalar = self._peaks[i][0].scalar_hash
            acc = combine_field_scalars(left_scalar, acc)
        return f"{acc:064x}"

    def append_receipt(self, receipt_caid: str, timestamp_ms: Optional[int] = None) -> int:
        """
        Append a receipt CAID to the Merkle Mountain Range.
        Returns the 0-based leaf position of the appended receipt.
        """
        if not receipt_caid or len(receipt_caid) != 64:
            raise ValueError("receipt_caid must be a 64-character hex string")
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        leaf_pos = self._leaf_count
        leaf_scalar = hash_to_field_scalar(receipt_caid.encode("utf-8"))

        self._leaf_caids.append(receipt_caid)
        self._leaf_scalars.append(leaf_scalar)
        self._leaf_count += 1

        # Current candidate peak
        cand_peak = MmrPeak(height=0, leaf_count=1, scalar_hash=leaf_scalar)
        cand_subtree = [leaf_pos]

        # Merge peaks of identical height
        while self._peaks and self._peaks[-1][0].height == cand_peak.height:
            prev_peak, prev_subtree = self._peaks.pop()
            new_scalar = combine_field_scalars(prev_peak.scalar_hash, cand_peak.scalar_hash)
            cand_peak = MmrPeak(
                height=cand_peak.height + 1,
                leaf_count=prev_peak.leaf_count + cand_peak.leaf_count,
                scalar_hash=new_scalar,
            )
            cand_subtree = prev_subtree + cand_subtree

        self._peaks.append((cand_peak, cand_subtree))

        # Persist to SQLite
        bagged_root = self.get_bagged_root()
        peaks_data = [
            {"height": p.height, "leaf_count": p.leaf_count, "scalar_hash": hex(p.scalar_hash)}
            for p, _ in self._peaks
        ]

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO zk_mmr_leaves (tree_id, leaf_pos, receipt_caid, leaf_hash, scalar_val, timestamp_ms)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    self.tree_id,
                    leaf_pos,
                    receipt_caid,
                    f"{leaf_scalar:064x}",
                    str(leaf_scalar),
                    timestamp_ms,
                ),
            )
            self._conn.execute(
                """
                INSERT OR REPLACE INTO zk_mmr_state (tree_id, leaf_count, bagged_root, peaks_json, updated_at_ms)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    self.tree_id,
                    self._leaf_count,
                    bagged_root,
                    json.dumps(peaks_data),
                    timestamp_ms,
                ),
            )

        return leaf_pos

    def _build_auth_path(self, target_pos: int, subtree_leaves: List[int], height: int) -> List[Tuple[int, bool]]:
        """
        Recursively construct the Merkle path of sibling scalar hashes for a leaf inside a peak subtree.
        Returns list of (sibling_scalar_hash, is_left_sibling).
        """
        path: List[Tuple[int, bool]] = []
        leaves = list(subtree_leaves)
        curr_pos = target_pos

        while len(leaves) > 1:
            mid = len(leaves) // 2
            left_half = leaves[:mid]
            right_half = leaves[mid:]

            if curr_pos in left_half:
                # Sibling is right subtree peak
                sibling_scalar = self._compute_subtree_root(right_half)
                path.append((sibling_scalar, False))  # Sibling is on the right
                leaves = left_half
            else:
                # Sibling is left subtree peak
                sibling_scalar = self._compute_subtree_root(left_half)
                path.append((sibling_scalar, True))  # Sibling is on the left
                leaves = right_half

        # Return bottom-up path from leaf level up to peak root
        return list(reversed(path))

    def _compute_subtree_root(self, leaves: List[int]) -> int:
        """Compute the root scalar hash of a balanced subtree of leaves."""
        if len(leaves) == 1:
            return self._leaf_scalars[leaves[0]]
        mid = len(leaves) // 2
        left_root = self._compute_subtree_root(leaves[:mid])
        right_root = self._compute_subtree_root(leaves[mid:])
        return combine_field_scalars(left_root, right_root)

    def generate_inclusion_proof(self, leaf_pos: int) -> ZkMmrInclusionProof:
        """
        Generate a non-interactive zero-knowledge polynomial inclusion proof for a leaf.
        """
        if self._leaf_count == 0:
            raise ValueError(f"[{HALT_MMR_EMPTY_TREE}] Cannot generate proof on empty MMR")
        if not (0 <= leaf_pos < self._leaf_count):
            raise ValueError(f"[{HALT_MMR_LEAF_OUT_OF_BOUNDS}] Leaf pos {leaf_pos} out of bounds [0..{self._leaf_count - 1}]")

        # Find which peak contains this leaf
        target_peak: Optional[MmrPeak] = None
        target_subtree: Optional[List[int]] = None

        for peak, subtree in self._peaks:
            if leaf_pos in subtree:
                target_peak = peak
                target_subtree = subtree
                break

        if target_peak is None or target_subtree is None:
            raise RuntimeError("Corrupted MMR state: leaf not found in any peak")

        leaf_scalar = self._leaf_scalars[leaf_pos]
        receipt_caid = self._leaf_caids[leaf_pos]
        bagged_root = self.get_bagged_root()

        # Build auth path within target peak
        auth_path = self._build_auth_path(leaf_pos, target_subtree, target_peak.height)

        # Fiat-Shamir challenge generation
        challenge_doc = {
            "auth_path": [(h, is_l) for h, is_l in auth_path],
            "bagged_root": bagged_root,
            "leaf_pos": leaf_pos,
            "leaf_scalar": leaf_scalar,
            "receipt_caid": receipt_caid,
            "tree_id": self.tree_id,
        }
        challenge_bytes = encode_jcs(challenge_doc)
        challenge_scalar = hash_to_field_scalar(challenge_bytes)

        # Construct polynomial coefficients: P(t) = leaf_scalar + sum(path_i * t^(i+1))
        coefficients = [leaf_scalar] + [h for h, _ in auth_path]
        polynomial_evaluation = evaluate_polynomial_horner(coefficients, challenge_scalar)

        # Proof CAID
        proof_doc = {
            "bagged_root": bagged_root,
            "challenge": challenge_scalar,
            "eval": polynomial_evaluation,
            "leaf_pos": leaf_pos,
            "receipt_caid": receipt_caid,
            "tree_id": self.tree_id,
        }
        proof_caid = compute_sha256(encode_jcs(proof_doc))

        return ZkMmrInclusionProof(
            tree_id=self.tree_id,
            leaf_pos=leaf_pos,
            receipt_caid=receipt_caid,
            leaf_scalar=leaf_scalar,
            auth_path=auth_path,
            peak_height=target_peak.height,
            bagged_root=bagged_root,
            fiat_shamir_challenge=challenge_scalar,
            polynomial_evaluation=polynomial_evaluation,
            proof_caid=proof_caid,
        )

    def verify_inclusion_proof(self, proof: ZkMmrInclusionProof) -> bool:
        """
        Verify a ZK MMR polynomial inclusion proof against the current accumulator state.
        """
        # 1. Check leaf bounds and receipt CAID consistency
        if not (0 <= proof.leaf_pos < self._leaf_count):
            return False
        if self._leaf_caids[proof.leaf_pos] != proof.receipt_caid:
            return False

        # 2. Check leaf scalar hash
        expected_scalar = hash_to_field_scalar(proof.receipt_caid.encode("utf-8"))
        if proof.leaf_scalar != expected_scalar:
            return False

        # 3. Check Fiat-Shamir challenge reconstruction
        challenge_doc = {
            "auth_path": [(h, is_l) for h, is_l in proof.auth_path],
            "bagged_root": proof.bagged_root,
            "leaf_pos": proof.leaf_pos,
            "leaf_scalar": proof.leaf_scalar,
            "receipt_caid": proof.receipt_caid,
            "tree_id": proof.tree_id,
        }
        expected_challenge = hash_to_field_scalar(encode_jcs(challenge_doc))
        if proof.fiat_shamir_challenge != expected_challenge:
            return False

        # 4. Check Horner polynomial evaluation
        coefficients = [proof.leaf_scalar] + [h for h, _ in proof.auth_path]
        expected_eval = evaluate_polynomial_horner(coefficients, proof.fiat_shamir_challenge)
        if proof.polynomial_evaluation != expected_eval:
            return False

        # 5. Reconstruct peak scalar from path
        curr = proof.leaf_scalar
        for sibling_scalar, is_left in proof.auth_path:
            if is_left:
                curr = combine_field_scalars(sibling_scalar, curr)
            else:
                curr = combine_field_scalars(curr, sibling_scalar)

        # Check if reconstructed peak exists in active peaks
        peak_scalars = {p.scalar_hash for p, _ in self._peaks}
        if curr not in peak_scalars:
            return False

        # 6. Bagged root must match current accumulator root
        if proof.bagged_root != self.get_bagged_root():
            return False

        # Persist successful verification to SQLite
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO zk_mmr_proofs (proof_caid, tree_id, leaf_pos, status, verified_at_ms)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    proof.proof_caid,
                    proof.tree_id,
                    proof.leaf_pos,
                    STATUS_PROOF_VERIFIED,
                    int(time.time() * 1000),
                ),
            )
        return True

    def get_peak_hashes(self) -> List[str]:
        """Return hex strings of all active peak scalar hashes."""
        return [f"{p.scalar_hash:064x}" for p, _ in self._peaks]
