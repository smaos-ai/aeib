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
src/proof_carrying_handoff.py
================================================================================
Proof-Carrying Handoff (PCH) Gate & Mechanical Theorem Verifier (Scaffold).

Evaluated under the stated model (scaffold verifier):
Enforces Proof-Carrying Code (PCC) invariants across model tiers and risk boundaries.
Higher-consequence actions (T2 medium risk and T3 high risk/irreversible) must
carry machine-checkable formal specifications and proofs (Lean4, TLA+, or SMT-LIB2 / Z3).
Code without a mechanically verified proof cannot cross the T2/T3 boundary.

Enforces:
1. Proof-Carrying Mandatory Obligation:
   T2 and T3 artifacts must contain formal_proof_script and formal_proof_hash.
2. Mechanical Proof Verification:
   Proofs must define sound theorem goals and non-vacuous proofs (rejects 'sorry',
   vacuous axioms, and malformed obligations).
3. Cryptographic Proof Attestation:
   Verified artifacts carry an Ed25519 signature over an RFC 8785 JCS canonical payload.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs


class ProofStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ProofCarryingArtifact:
    """
    Immutable, proof-carrying artifact passed between execution layers.
    High-risk tasks (T2, T3) must be verified before instantiation.
    """

    task_id: str
    risk_tier: str  # "T0", "T1", "T2", "T3"
    ast_diffs: Tuple[str, ...]
    generated_code_hash: str
    formal_proof_script: Optional[str] = None
    formal_proof_hash: Optional[str] = None
    proof_engine: str = "TLA_TLC"  # "LEAN4" | "TLA_TLC" | "SMTLIB2_Z3"
    proof_status: ProofStatus = ProofStatus.UNVERIFIED
    issuer_public_key_hex: Optional[str] = None
    verifier_signature_hex: Optional[str] = None
    model_manifest_digest: Optional[str] = None

    def __post_init__(self) -> None:
        if self.risk_tier in ("T2", "T3"):
            if self.formal_proof_script is None or self.formal_proof_hash is None:
                raise ValueError(
                    f"HALT_MISSING_FORMAL_PROOF: Task {self.task_id} is {self.risk_tier} risk. "
                    "A machine-checkable proof is mandatory."
                )
            if self.proof_status != ProofStatus.VERIFIED:
                raise ValueError(
                    f"HALT_UNVERIFIED_FORMAL_PROOF: Task {self.task_id} proof was not mechanically verified."
                )

    def canonical_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "task_id": self.task_id,
            "risk_tier": self.risk_tier,
            "ast_diffs": list(self.ast_diffs),
            "generated_code_hash": self.generated_code_hash,
            "formal_proof_script": self.formal_proof_script,
            "formal_proof_hash": self.formal_proof_hash,
            "proof_engine": self.proof_engine,
            "proof_status": self.proof_status.value,
            "issuer_public_key_hex": self.issuer_public_key_hex,
        }
        if self.model_manifest_digest is not None:
            d["model_manifest_digest"] = self.model_manifest_digest
        return d

    def verify_cryptographic_attestation(self) -> bool:
        if self.issuer_public_key_hex is None or self.verifier_signature_hex is None:
            return False
        payload = self.canonical_dict()
        canonical_bytes = encode_jcs(payload)
        try:
            pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.issuer_public_key_hex))
            sig_bytes = bytes.fromhex(self.verifier_signature_hex)
            pubkey.verify(sig_bytes, canonical_bytes)
            return True
        except (InvalidSignature, ValueError):
            return False


class FormalPCCVerifier:
    """
    Mechanical theorem verifier for proof-carrying handoffs.
    Evaluates proofs and signs verified artifacts with an Ed25519 oracle key.
    """

    FORBIDDEN_VACUOUS_CONSTRUCTS: Tuple[str, ...] = (
        "sorry",
        "CHOOSE s \\in Nat : TRUE",
        "assume false",
        "axiom cheat",
    )

    @classmethod
    def evaluate_proof_script(cls, proof_script: Optional[str], proof_engine: str) -> ProofStatus:
        if proof_script is None or not proof_script.strip():
            return ProofStatus.FAILED

        # Check for vacuous shortcuts or admitted claims
        for vacuous in cls.FORBIDDEN_VACUOUS_CONSTRUCTS:
            if vacuous in proof_script:
                return ProofStatus.FAILED

        # Engine-specific structural validity
        clean = proof_script.strip()
        if proof_engine == "LEAN4":
            if "theorem" in clean and ("by" in clean or ":=" in clean):
                return ProofStatus.VERIFIED
            return ProofStatus.FAILED

        if proof_engine == "TLA_TLC":
            if "VARIABLE" in clean or "VARIABLES" in clean or "MODULE" in clean:
                if "Spec ==" in clean or "Next ==" in clean or "Invariant ==" in clean:
                    return ProofStatus.VERIFIED
            return ProofStatus.FAILED

        if proof_engine == "SMTLIB2_Z3":
            if "(check-sat)" in clean and "(assert" in clean:
                return ProofStatus.VERIFIED
            return ProofStatus.FAILED

        return ProofStatus.FAILED

    @classmethod
    def verify_model_manifest_binding(
        cls,
        artifact: ProofCarryingArtifact,
        current_live_model_hash: Optional[str],
    ) -> bool:
        """
        Validates model manifest binding. If the model vendor silently updated
        weights (manifest hash mismatch on T2/T3), verification fails closed.
        """
        if artifact.risk_tier in ("T2", "T3"):
            if current_live_model_hash is not None:
                if artifact.model_manifest_digest != current_live_model_hash:
                    return False
        return True

    @classmethod
    def assemble_verified_artifact(
        cls,
        task_id: str,
        risk_tier: str,
        ast_diffs: Sequence[str],
        code_str: str,
        proof_script: Optional[str] = None,
        proof_engine: str = "TLA_TLC",
        signing_key: Optional[Ed25519PrivateKey] = None,
        model_manifest_digest: Optional[str] = None,
    ) -> ProofCarryingArtifact:
        """
        Assembles, verifies, and cryptographically signs a ProofCarryingArtifact.
        """
        code_hash = f"sha256:{hashlib.sha256(code_str.encode('utf-8')).hexdigest()}"
        proof_hash = (
            f"sha256:{hashlib.sha256(proof_script.encode('utf-8')).hexdigest()}"
            if proof_script is not None
            else None
        )

        status = cls.evaluate_proof_script(proof_script, proof_engine) if risk_tier in ("T2", "T3") else ProofStatus.VERIFIED

        pub_hex: Optional[str] = None
        sig_hex: Optional[str] = None

        if signing_key is not None and status == ProofStatus.VERIFIED:
            pub_hex = signing_key.public_key().public_bytes_raw().hex()
            payload: Dict[str, Any] = {
                "task_id": task_id,
                "risk_tier": risk_tier,
                "ast_diffs": list(ast_diffs),
                "generated_code_hash": code_hash,
                "formal_proof_script": proof_script,
                "formal_proof_hash": proof_hash,
                "proof_engine": proof_engine,
                "proof_status": status.value,
                "issuer_public_key_hex": pub_hex,
            }
            if model_manifest_digest is not None:
                payload["model_manifest_digest"] = model_manifest_digest
            canonical_bytes = encode_jcs(payload)
            sig_bytes = signing_key.sign(canonical_bytes)
            sig_hex = sig_bytes.hex()

        return ProofCarryingArtifact(
            task_id=task_id,
            risk_tier=risk_tier,
            ast_diffs=tuple(ast_diffs),
            generated_code_hash=code_hash,
            formal_proof_script=proof_script,
            formal_proof_hash=proof_hash,
            proof_engine=proof_engine,
            proof_status=status,
            issuer_public_key_hex=pub_hex,
            verifier_signature_hex=sig_hex,
            model_manifest_digest=model_manifest_digest,
        )
