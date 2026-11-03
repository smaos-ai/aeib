#!/usr/bin/env python3
"""
src/zk_budget_proof_engine.py — Signed Linear-Combination Budget Transcript Scaffold
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

IMPORTANT SECURITY & SOUNDNESS NOTICE (Scaffold / Opt-In Simulation Only):
- This module is a linear mod-r arithmetic transcript scaffold, NOT a sound
  zero-knowledge proof system and NOT a hiding Pedersen commitment scheme:
  1. `_commit_poly` computes a linear integer combination modulo `r` where the
     discrete logs between `G_BASIS` and `H_BLINDING` are publicly known integers.
  2. `verify_budget_proof` checks linear evaluations at `X=2` and `X=challenge_x`
     without enforcing bitness (`b_{i,j} * (1 - b_{i,j}) = 0`) on the verifier side,
     meaning a malicious prover can forge transcripts for negative or out-of-range
     spends that sum to the public delta.
- Consequently, `verify_budget_proof` is quarantined behind `require_simulation_opt_in`
  (`allow_simulation=True` or `AEIB_ALLOW_SIMULATION=1`) and always reports
  `status=SIMULATED_OPT_IN` (never `REAL_EXECUTED`).
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.capability_status import (
    SIMULATED_OPT_IN,
    CapabilityUnavailableError,
    require_simulation_opt_in,
)
from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash


# ============================================================================
# Protocol Constants & Explicit Rejection Codes
# ============================================================================

# Standard BN254 / alt_bn128 scalar field prime r
BN254_SCALAR_FIELD_PRIME: int = 21888242871839275222246405745257275088548364400416034343698204186575808495617

# 64-bit limb representation to enforce non-negative bounded range
NUM_LIMBS: int = 64
MAX_LIMB_VALUE: int = (1 << NUM_LIMBS) - 1

# Explicit rejection codes
HALT_ZK_BALANCE_CONSERVATION_FAILED = "HALT_ZK_BALANCE_CONSERVATION_FAILED"
HALT_ZK_CEILING_BREACH = "HALT_ZK_CEILING_BREACH"
HALT_ZK_NEGATIVE_SPEND_DETECTED = "HALT_ZK_NEGATIVE_SPEND_DETECTED"
HALT_ZK_COMMITMENT_ROOT_MISMATCH = "HALT_ZK_COMMITMENT_ROOT_MISMATCH"
HALT_ZK_PROOF_INVALID = "HALT_ZK_PROOF_INVALID"


# ============================================================================
# Nothing-Up-My-Sleeve (NUMS) Generators over F_r
# ============================================================================

def derive_nums_generators() -> Tuple[List[int], int]:
    """
    Derives deterministic NUMS basis generators (G_0..G_63) and blinding generator H
    in F_r using domain-separated SHA-256 digests.
    """
    r = BN254_SCALAR_FIELD_PRIME
    g_limbs = [
        int(hashlib.sha256(f"AEIB_BN254_NUMS_G_{j}".encode("utf-8")).hexdigest(), 16) % r
        for j in range(NUM_LIMBS)
    ]
    h_blinding = (
        int(hashlib.sha256(b"AEIB_BN254_NUMS_H_BLINDING").hexdigest(), 16) % r
    )
    return g_limbs, h_blinding


G_BASIS, H_BLINDING = derive_nums_generators()


# ============================================================================
# Data Models & Custom Exceptions
# ============================================================================

class ZkCircuitError(ValueError):
    """Raised when an arithmetic circuit invariant is breached during proof generation."""

    def __init__(self, rejection_code: str, message: str):
        super().__init__(f"[{rejection_code}] {message}")
        self.rejection_code = rejection_code
        self.message = message


@dataclass(frozen=True)
class PrivateTransaction:
    """Private transaction witness component: spend amount, salt, and payee identifier."""
    spend_minor: int
    salt: str
    payee: str


@dataclass(frozen=True)
class PrivateWitness:
    """Private witness containing the list of individual transactions."""
    transactions: List[PrivateTransaction]


@dataclass(frozen=True)
class BudgetPublicInputs:
    """Public inputs against which the zero-knowledge proof is evaluated."""
    initial_balance_minor: int
    final_balance_minor: int
    budget_ceiling_minor: int
    commitment_merkle_root: str
    epoch: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget_ceiling_minor": self.budget_ceiling_minor,
            "commitment_merkle_root": self.commitment_merkle_root,
            "epoch": self.epoch,
            "final_balance_minor": self.final_balance_minor,
            "initial_balance_minor": self.initial_balance_minor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BudgetPublicInputs:
        return cls(
            initial_balance_minor=int(data["initial_balance_minor"]),
            final_balance_minor=int(data["final_balance_minor"]),
            budget_ceiling_minor=int(data["budget_ceiling_minor"]),
            commitment_merkle_root=str(data["commitment_merkle_root"]),
            epoch=int(data["epoch"]),
        )


@dataclass(frozen=True)
class ZkVerificationResult:
    """Structured verification outcome with explicit rejection codes and capability status."""
    valid: bool
    rejection_code: Optional[str] = None
    reason: Optional[str] = None
    verification_time_ms: int = 0
    status: str = SIMULATED_OPT_IN

    def __bool__(self) -> bool:
        return self.valid

    def __iter__(self):
        yield self.valid
        yield self.rejection_code


def _reject(
    code: str,
    reason: str,
    t0: float,
    status: str = SIMULATED_OPT_IN,
) -> ZkVerificationResult:
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return ZkVerificationResult(
        valid=False,
        rejection_code=code,
        reason=reason,
        verification_time_ms=elapsed_ms,
        status=status,
    )


@dataclass
class ZkBudgetProof:
    """Non-interactive zero-knowledge proof artifact generated via Fiat-Shamir transcript."""
    public_inputs: BudgetPublicInputs
    leaf_commitments: List[str]
    poly_commitments: Dict[str, Any]
    evaluations: Dict[str, Any]
    aggregate_blinding_eval: int
    slack_blinding_eval: int
    transcript_hash: str
    tenant_public_key_hex: str
    tenant_signature_hex: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aggregate_blinding_eval": self.aggregate_blinding_eval,
            "evaluations": copy.deepcopy(self.evaluations),
            "leaf_commitments": list(self.leaf_commitments),
            "poly_commitments": copy.deepcopy(self.poly_commitments),
            "public_inputs": self.public_inputs.to_dict(),
            "slack_blinding_eval": self.slack_blinding_eval,
            "tenant_public_key_hex": self.tenant_public_key_hex,
            "tenant_signature_hex": self.tenant_signature_hex,
            "transcript_hash": self.transcript_hash,
        }

    def to_jcs_bytes(self) -> bytes:
        return encode_jcs(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ZkBudgetProof:
        return cls(
            public_inputs=BudgetPublicInputs.from_dict(data["public_inputs"]),
            leaf_commitments=list(data["leaf_commitments"]),
            poly_commitments=dict(data["poly_commitments"]),
            evaluations=dict(data["evaluations"]),
            aggregate_blinding_eval=int(data["aggregate_blinding_eval"]),
            slack_blinding_eval=int(data["slack_blinding_eval"]),
            transcript_hash=str(data["transcript_hash"]),
            tenant_public_key_hex=str(data["tenant_public_key_hex"]),
            tenant_signature_hex=str(data["tenant_signature_hex"]),
        )


# ============================================================================
# Engine Implementation
# ============================================================================

class ZkBudgetProofEngine:
    """
    zk-AEIB Arithmetic Circuit & Privacy-Preserving Budget Proof Engine.
    Evaluated under the stated model as a pre-production prototype.
    """

    def __init__(self, tenant_private_key: Optional[Ed25519PrivateKey] = None):
        self._private_key = tenant_private_key or Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        self.field_prime = BN254_SCALAR_FIELD_PRIME

    @property
    def public_key_hex(self) -> str:
        return self._public_key.public_bytes_raw().hex()

    @staticmethod
    def compute_leaf_commitment(salt: str, spend_minor: int, payee: str) -> str:
        """Computes blinded transaction leaf commitment C_i = H(salt || spend_minor || payee)."""
        payload = f"{salt}:{spend_minor}:{payee}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def compute_merkle_root(leaves: Sequence[str]) -> str:
        """
        Computes SHA-256 Merkle root from sequence of leaf hex strings.
        Duplicates the last element when a level has odd cardinality.
        """
        if not leaves:
            return hashlib.sha256(b"EMPTY_ZK_AEIB_TREE").hexdigest()

        current_level = list(leaves)
        while len(current_level) > 1:
            next_level = []
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])
            for i in range(0, len(current_level), 2):
                combined = f"{current_level[i]}:{current_level[i + 1]}".encode("utf-8")
                next_level.append(hashlib.sha256(combined).hexdigest())
            current_level = next_level

        return current_level[0]

    @staticmethod
    def decompose_into_limbs(value: int) -> List[int]:
        """Decomposes an integer into 64 binary limbs (b_0 .. b_63)."""
        if value < 0 or value > MAX_LIMB_VALUE:
            raise ZkCircuitError(
                HALT_ZK_NEGATIVE_SPEND_DETECTED,
                f"Value {value} out of 64-bit limb representation range [0, 2^64 - 1]",
            )
        return [(value >> j) & 1 for j in range(NUM_LIMBS)]

    def _commit_poly(self, coeffs: Sequence[int], rho: int) -> int:
        """Computes blinded Pedersen polynomial commitment com(P, rho) = (rho * H + sum(c_j * G_j)) mod r."""
        r = self.field_prime
        acc = (rho * H_BLINDING) % r
        for c, g in zip(coeffs, G_BASIS):
            acc = (acc + (c % r) * g) % r
        return acc

    def _eval_poly(self, coeffs: Sequence[int], point: int) -> int:
        """Evaluates a polynomial given by coeffs at point mod r using Horner's rule."""
        r = self.field_prime
        acc = 0
        for c in reversed(coeffs):
            acc = (acc * point + c) % r
        return acc

    @staticmethod
    def _sample_blinding(r: int) -> int:
        return secrets.randbelow(r - 1) + 1

    def generate_budget_proof(
        self,
        witness: PrivateWitness,
        public_inputs: BudgetPublicInputs,
    ) -> ZkBudgetProof:
        """
        Generates a non-interactive zero-knowledge budget proof evaluated over F_r.
        Enforces:
        1. Exact Balance Conservation: final_balance = initial_balance - sum(spend_i) mod r
        2. Budget Ceiling Invariant: sum(spend_i) <= budget_ceiling_minor
        3. Non-Negative Spend: each spend_i >= 0 via 64-bit limb decomposition
        4. Commitment Consistency: leaf commitments hash to commitment_merkle_root
        """
        r = self.field_prime

        if not witness.transactions:
            raise ZkCircuitError(
                HALT_ZK_PROOF_INVALID,
                "Cannot generate proof for empty transaction batch",
            )

        # 1. Non-Negative Spend & Limb Decomposition
        spend_limbs: List[List[int]] = []
        leaf_commitments: List[str] = []
        total_spend = 0

        for tx in witness.transactions:
            if tx.spend_minor < 0:
                raise ZkCircuitError(
                    HALT_ZK_NEGATIVE_SPEND_DETECTED,
                    f"Negative spend detected: {tx.spend_minor}",
                )
            if tx.spend_minor > MAX_LIMB_VALUE:
                raise ZkCircuitError(
                    HALT_ZK_NEGATIVE_SPEND_DETECTED,
                    f"Spend exceeds 64-bit maximum: {tx.spend_minor}",
                )

            limbs = self.decompose_into_limbs(tx.spend_minor)
            spend_limbs.append(limbs)
            leaf_commitments.append(
                self.compute_leaf_commitment(tx.salt, tx.spend_minor, tx.payee)
            )
            total_spend += tx.spend_minor

        # 2. Commitment Consistency Check
        computed_root = self.compute_merkle_root(leaf_commitments)
        if computed_root != public_inputs.commitment_merkle_root:
            raise ZkCircuitError(
                HALT_ZK_COMMITMENT_ROOT_MISMATCH,
                f"Witness Merkle root {computed_root} does not match public {public_inputs.commitment_merkle_root}",
            )

        # 3. Exact Balance Conservation Check
        expected_delta = (public_inputs.initial_balance_minor - public_inputs.final_balance_minor) % r
        if (total_spend % r) != expected_delta:
            raise ZkCircuitError(
                HALT_ZK_BALANCE_CONSERVATION_FAILED,
                f"Balance conservation violated: total_spend={total_spend}, expected_delta={expected_delta}",
            )

        # 4. Budget Ceiling Invariant Check
        slack = public_inputs.budget_ceiling_minor - total_spend
        if slack < 0:
            raise ZkCircuitError(
                HALT_ZK_CEILING_BREACH,
                f"Authorized budget ceiling breached: total_spend={total_spend} > ceiling={public_inputs.budget_ceiling_minor}",
            )
        if slack > MAX_LIMB_VALUE:
            raise ZkCircuitError(
                HALT_ZK_CEILING_BREACH,
                f"Slack variable exceeds 64-bit maximum: {slack}",
            )
        slack_limbs = self.decompose_into_limbs(slack)

        # 5. Polynomial Commitments with Independent Blinding Factors
        n_tx = len(witness.transactions)
        rho_b = [self._sample_blinding(r) for _ in range(n_tx)]
        rho_r = [self._sample_blinding(r) for _ in range(n_tx)]
        r_polys = [
            [secrets.randbelow(r) for _ in range(NUM_LIMBS)]
            for _ in range(n_tx)
        ]

        com_b = [self._commit_poly(spend_limbs[i], rho_b[i]) for i in range(n_tx)]
        com_r = [self._commit_poly(r_polys[i], rho_r[i]) for i in range(n_tx)]

        rho_s = self._sample_blinding(r)
        rho_rs = self._sample_blinding(r)
        rs_poly = [secrets.randbelow(r) for _ in range(NUM_LIMBS)]

        com_s = self._commit_poly(slack_limbs, rho_s)
        com_rs = self._commit_poly(rs_poly, rho_rs)

        poly_commitments = {
            "com_b": [str(c) for c in com_b],
            "com_r": [str(c) for c in com_r],
            "com_rs": str(com_rs),
            "com_s": str(com_s),
        }

        # 6. Fiat-Shamir Transcript Generation via RFC 8785 JCS
        transcript_payload = {
            "budget_ceiling_minor": public_inputs.budget_ceiling_minor,
            "commitment_merkle_root": public_inputs.commitment_merkle_root,
            "epoch": public_inputs.epoch,
            "final_balance_minor": public_inputs.final_balance_minor,
            "initial_balance_minor": public_inputs.initial_balance_minor,
            "leaf_commitments": leaf_commitments,
            "poly_commitments": poly_commitments,
        }
        transcript_hash = generate_jcs_payload_hash(transcript_payload)

        # Derive challenges x, y from Fiat-Shamir transcript
        challenge_x = (
            int(hashlib.sha256(f"{transcript_hash}:challenge:x".encode("utf-8")).hexdigest(), 16) % r
        )
        challenge_y = (
            int(hashlib.sha256(f"{transcript_hash}:challenge:y".encode("utf-8")).hexdigest(), 16) % r
        )

        # 7. Blinded Polynomial Evaluations
        # Masked polynomial M_i(X) = (B_i(X) * y + R_i(X)) mod r
        masked_polys: List[List[int]] = []
        v_m_x: List[int] = []
        v_m_2: List[int] = []
        sigma_m: List[int] = []

        for i in range(n_tx):
            m_poly = [
                (spend_limbs[i][j] * challenge_y + r_polys[i][j]) % r
                for j in range(NUM_LIMBS)
            ]
            masked_polys.append(m_poly)
            v_m_x.append(self._eval_poly(m_poly, challenge_x))
            v_m_2.append(self._eval_poly(m_poly, 2))
            sigma_m.append((rho_b[i] * challenge_y + rho_r[i]) % r)

        # Slack masked polynomial M_S(X) = (S(X) * y + R_S(X)) mod r
        ms_poly = [
            (slack_limbs[j] * challenge_y + rs_poly[j]) % r
            for j in range(NUM_LIMBS)
        ]
        v_ms_x = self._eval_poly(ms_poly, challenge_x)
        v_ms_2 = self._eval_poly(ms_poly, 2)
        sigma_ms = (rho_s * challenge_y + rho_rs) % r

        # Aggregate blinding evaluation E_R = sum(R_i(2)) mod r
        aggregate_blinding_eval = sum(self._eval_poly(r_polys[i], 2) for i in range(n_tx)) % r
        slack_blinding_eval = self._eval_poly(rs_poly, 2)

        evaluations = {
            "masked_polys": [[str(coeff) for coeff in p] for p in masked_polys],
            "ms_poly": [str(coeff) for coeff in ms_poly],
            "sigma_m": [str(s) for s in sigma_m],
            "sigma_ms": str(sigma_ms),
            "v_m_2": [str(v) for v in v_m_2],
            "v_m_x": [str(v) for v in v_m_x],
            "v_ms_2": str(v_ms_2),
            "v_ms_x": str(v_ms_x),
        }

        # 8. Ed25519 Tenant Authorization Signature over Transcript
        signature_bytes = self._private_key.sign(transcript_hash.encode("utf-8"))

        return ZkBudgetProof(
            public_inputs=public_inputs,
            leaf_commitments=leaf_commitments,
            poly_commitments=poly_commitments,
            evaluations=evaluations,
            aggregate_blinding_eval=aggregate_blinding_eval,
            slack_blinding_eval=slack_blinding_eval,
            transcript_hash=transcript_hash,
            tenant_public_key_hex=self.public_key_hex,
            tenant_signature_hex=signature_bytes.hex(),
        )

    def verify_budget_proof(
        self,
        public_inputs: BudgetPublicInputs,
        proof: ZkBudgetProof,
        allow_simulation: Optional[bool] = None,
    ) -> ZkVerificationResult:
        """
        Verifies a signed linear-combination budget transcript scaffold.
        NOTE: Because this module checks linear mod-r combinations rather than a
        sound zero-knowledge range/bitness proof, verification requires explicit
        simulation opt-in (`allow_simulation=True` or `AEIB_ALLOW_SIMULATION=1`)
        and reports `status=SIMULATED_OPT_IN`.
        """
        status = require_simulation_opt_in(
            "zk_budget_proof_engine.verify_budget_proof",
            allow_simulation,
            detail="Linear mod-r transcript check is not a sound zero-knowledge proof.",
        )
        t0 = time.perf_counter()
        r = self.field_prime

        # 1. Commitment Merkle Root Consistency
        if proof.public_inputs.commitment_merkle_root != public_inputs.commitment_merkle_root:
            return _reject(HALT_ZK_COMMITMENT_ROOT_MISMATCH, "Proof public commitment root does not match verifier public input", t0, status)

        computed_root = self.compute_merkle_root(proof.leaf_commitments)
        if computed_root != public_inputs.commitment_merkle_root:
            return _reject(HALT_ZK_COMMITMENT_ROOT_MISMATCH, "Leaf commitments do not open to verified public commitment root", t0, status)

        # 2. Public Input Sanity & Invariant Checks
        # Balance delta
        initial_bal = public_inputs.initial_balance_minor
        final_bal = public_inputs.final_balance_minor
        ceiling = public_inputs.budget_ceiling_minor

        delta = initial_bal - final_bal
        if delta < 0:
            return _reject(HALT_ZK_NEGATIVE_SPEND_DETECTED, f"Claimed final balance {final_bal} exceeds initial balance {initial_bal}", t0, status)

        if delta > ceiling:
            return _reject(HALT_ZK_CEILING_BREACH, f"Total delta {delta} exceeds authorized budget ceiling {ceiling}", t0, status)

        slack = ceiling - delta
        if slack < 0 or slack > MAX_LIMB_VALUE:
            return _reject(HALT_ZK_CEILING_BREACH, f"Slack variable out of bounds: {slack}", t0, status)

        # 3. Fiat-Shamir Transcript & Cryptographic Signature Validation
        transcript_payload = {
            "budget_ceiling_minor": public_inputs.budget_ceiling_minor,
            "commitment_merkle_root": public_inputs.commitment_merkle_root,
            "epoch": public_inputs.epoch,
            "final_balance_minor": public_inputs.final_balance_minor,
            "initial_balance_minor": public_inputs.initial_balance_minor,
            "leaf_commitments": proof.leaf_commitments,
            "poly_commitments": proof.poly_commitments,
        }
        recomputed_transcript_hash = generate_jcs_payload_hash(transcript_payload)

        if recomputed_transcript_hash != proof.transcript_hash:
            return _reject(HALT_ZK_PROOF_INVALID, "Fiat-Shamir transcript hash mismatch indicating tampered commitments", t0, status)

        try:
            tenant_pub = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(proof.tenant_public_key_hex)
            )
            tenant_pub.verify(
                bytes.fromhex(proof.tenant_signature_hex),
                proof.transcript_hash.encode("utf-8"),
            )
        except (ValueError, InvalidSignature) as sig_err:
            return _reject(HALT_ZK_PROOF_INVALID, f"Invalid tenant Ed25519 authorization signature: {sig_err}", t0, status)

        # Derive Fiat-Shamir challenges
        challenge_x = (
            int(hashlib.sha256(f"{proof.transcript_hash}:challenge:x".encode("utf-8")).hexdigest(), 16) % r
        )
        challenge_y = (
            int(hashlib.sha256(f"{proof.transcript_hash}:challenge:y".encode("utf-8")).hexdigest(), 16) % r
        )

        # 4. Exact Balance Conservation Algebraic Verification
        # Sum_i(v_M_i(2)) == y * delta + aggregate_blinding_eval mod r
        try:
            v_m_2 = [int(v) for v in proof.evaluations["v_m_2"]]
            sum_v_m_2 = sum(v_m_2) % r
            expected_balance_eval = (challenge_y * (delta % r) + proof.aggregate_blinding_eval) % r
            if sum_v_m_2 != expected_balance_eval:
                return _reject(HALT_ZK_BALANCE_CONSERVATION_FAILED, "Sum of masked spend evaluations does not conserve public balance delta", t0, status)
        except (KeyError, ValueError) as eval_err:
            return _reject(HALT_ZK_PROOF_INVALID, f"Malformed evaluation payload: {eval_err}", t0, status)

        # 5. Budget Ceiling Invariant Verification
        # v_MS(2) == y * slack + slack_blinding_eval mod r
        try:
            v_ms_2 = int(proof.evaluations["v_ms_2"])
            expected_slack_eval = (challenge_y * (slack % r) + proof.slack_blinding_eval) % r
            if v_ms_2 != expected_slack_eval:
                return _reject(HALT_ZK_CEILING_BREACH, "Slack evaluation does not satisfy budget ceiling invariant", t0, status)
        except (KeyError, ValueError) as slack_err:
            return _reject(HALT_ZK_PROOF_INVALID, f"Malformed slack evaluation: {slack_err}", t0, status)

        # 6. Non-Negative Spend via Masked Polynomial Consistency Checks
        try:
            masked_polys = [
                [int(c) for c in p]
                for p in proof.evaluations["masked_polys"]
            ]
            com_b = [int(c) for c in proof.poly_commitments["com_b"]]
            com_r = [int(c) for c in proof.poly_commitments["com_r"]]
            sigma_m = [int(s) for s in proof.evaluations["sigma_m"]]
            v_m_x = [int(v) for v in proof.evaluations["v_m_x"]]

            if not (len(masked_polys) == len(com_b) == len(com_r) == len(sigma_m) == len(v_m_x)):
                return _reject(HALT_ZK_PROOF_INVALID, "Mismatched vector lengths in polynomial evaluations", t0, status)

            for i in range(len(masked_polys)):
                m_poly = masked_polys[i]
                if len(m_poly) != NUM_LIMBS:
                    return _reject(HALT_ZK_NEGATIVE_SPEND_DETECTED, f"Limb polynomial {i} length {len(m_poly)} != {NUM_LIMBS}", t0, status)

                # Horner evaluation at challenge_x must match v_m_x[i]
                recomputed_v_x = self._eval_poly(m_poly, challenge_x)
                if recomputed_v_x != v_m_x[i]:
                    return _reject(HALT_ZK_PROOF_INVALID, f"Evaluation at challenge x inconsistent for transaction {i}", t0, status)

                # Homomorphic commitment check: com(M_i, sigma_m[i]) == com_b[i] * y + com_r[i] mod r
                recomputed_com = self._commit_poly(m_poly, sigma_m[i])
                expected_com = (com_b[i] * challenge_y + com_r[i]) % r
                if recomputed_com != expected_com:
                    return _reject(HALT_ZK_PROOF_INVALID, f"Commitment homomorphism failed for transaction {i}", t0, status)

            # Slack polynomial consistency checks
            ms_poly = [int(c) for c in proof.evaluations["ms_poly"]]
            com_s = int(proof.poly_commitments["com_s"])
            com_rs = int(proof.poly_commitments["com_rs"])
            sigma_ms = int(proof.evaluations["sigma_ms"])
            v_ms_x = int(proof.evaluations["v_ms_x"])

            if len(ms_poly) != NUM_LIMBS:
                return _reject(HALT_ZK_CEILING_BREACH, f"Slack polynomial length {len(ms_poly)} != {NUM_LIMBS}", t0, status)

            if self._eval_poly(ms_poly, challenge_x) != v_ms_x:
                return _reject(HALT_ZK_PROOF_INVALID, "Slack evaluation at challenge x inconsistent", t0, status)

            if self._commit_poly(ms_poly, sigma_ms) != ((com_s * challenge_y + com_rs) % r):
                return _reject(HALT_ZK_PROOF_INVALID, "Slack commitment homomorphism failed", t0, status)

        except (KeyError, ValueError) as limb_err:
            return _reject(HALT_ZK_PROOF_INVALID, f"Failed to verify limb polynomial commitments: {limb_err}", t0, status)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return ZkVerificationResult(
            valid=True,
            rejection_code=None,
            reason="Signed linear-combination budget transcript checked under SIMULATED_OPT_IN (not a sound ZK proof)",
            verification_time_ms=elapsed_ms,
            status=status,
        )
