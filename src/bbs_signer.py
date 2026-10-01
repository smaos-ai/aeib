#!/usr/bin/env python3
"""
STAR / SMAOS BBS+ Selectively Redactable Signatures (Reference Demonstration)
Aligned with W3C Data Integrity BBS Cryptosuites v1.0 / BLS12-381.

Resolves the fundamental tension between:
  - GDPR Article 17: Right to Erasure (redacting customer PII, IBAN, Tax ID)
  - EU AI Act Article 12: Mandatory Immutable Audit Logging

Enables a Data Protection Officer (DPO) to selectively blind sensitive fields in an
execution log while producing a cryptographic proof of knowledge of the signature.
Verifiers validate that the unredacted fields and blinded commitments originate
from a validly signed issuer record, returning VERIFIED_REDACTED without failing signature checks.

================================================================================
HONEST BOUNDARIES & CRYPTOGRAPHIC DISCLAIMER (TRUTH-IN-LABELING):
================================================================================
1. ARCHITECTURAL REFERENCE DEMONSTRATION ONLY:
   This module is an architectural proof-of-concept and test-vector demonstration.
   It models the algebraic mechanics of BBS+ selective disclosure over the BLS12-381
   scalar field order.

2. NOT PRODUCTION CRYPTOGRAPHY:
   This implementation uses integer scalar algebra and does NOT implement full
   constant-time elliptic curve pairings or audited side-channel resistance.
   For production deployments, use audited FIPS/Common Criteria libraries such as
   MCL, Hyperledger Ursa, or Mattr BBS Signatures.
================================================================================
"""

import os
import sys
import json
import time
import hashlib
import argparse
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict


# ============================================================================
# 1. MATHEMATICAL SUBSTRATE: BLS12-381 CURVE ORDER & SCALAR ALGEBRA
# ============================================================================

# BLS12-381 curve scalar field order r
BLS12_381_R = 0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001


def scalar_from_bytes(data: bytes) -> int:
    """Derives a non-zero scalar in Fr from arbitrary bytes using RFC 9380 hash style."""
    h = hashlib.sha256(b"BBS_PLUS_SCALAR_DERIVATION_" + data).digest()
    val = int.from_bytes(h, byteorder="big") % BLS12_381_R
    return val if val != 0 else 1


def random_scalar() -> int:
    """Generates a cryptographically secure random non-zero scalar in Fr."""
    while True:
        r = int.from_bytes(os.urandom(32), byteorder="big") % BLS12_381_R
        if r > 0:
            return r


def mod_inv(a: int, m: int = BLS12_381_R) -> int:
    """Computes modular inverse of a modulo m."""
    return pow(a % m, m - 2, m)


class DeterministicRNG:
    """Deterministic PRNG for reproducible test vectors (RFC 6979 style)."""
    def __init__(self, seed: bytes):
        self.counter = 0
        self.seed = seed

    def next_scalar(self) -> int:
        while True:
            self.counter += 1
            h = hashlib.sha256(self.seed + f"_{self.counter}".encode("utf-8")).digest()
            val = int.from_bytes(h, byteorder="big") % BLS12_381_R
            if val > 0:
                return val


# ============================================================================
# 2. GROUP GENERATOR & COMMITMENT ALGEBRA
# ============================================================================

@dataclass(frozen=True)
class GroupPoint:
    """
    Cryptographic group element representation.
    In BLS12-381, maps to G1/G2 curve points with bilinear pairing e(G1, G2).
    Implemented with projective scalar exponentiation and algebraic group invariants:
      P^a * P^b = P^(a+b mod r), (P^a)^b = P^(a*b mod r).
    """
    val: int

    def __post_init__(self):
        object.__setattr__(self, "val", self.val % BLS12_381_R)

    def __mul__(self, other: 'GroupPoint') -> 'GroupPoint':
        if not isinstance(other, GroupPoint):
            raise TypeError("Multiplication only supported between GroupPoints")
        return GroupPoint(val=(self.val + other.val) % BLS12_381_R)

    def pow(self, scalar: int) -> 'GroupPoint':
        """Scalar multiplication: P^scalar."""
        return GroupPoint(val=(self.val * (scalar % BLS12_381_R)) % BLS12_381_R)

    def to_digest(self) -> str:
        """Deterministic digest of group point state."""
        return hashlib.sha256(self.val.to_bytes(32, byteorder="big")).hexdigest()

    def to_hex(self) -> str:
        return hex(self.val)

    @classmethod
    def from_hex(cls, h: str) -> 'GroupPoint':
        return cls(val=int(h, 16))


class BBSGenerators:
    """Generators g1, g2, h0, h_1 ... h_L derived deterministically from domain seed."""
    def __init__(self, message_count: int, seed: bytes = b"SMAOS_BBS_PLUS_GENERATORS_V1"):
        self.seed = seed
        self.message_count = message_count
        self.g1 = GroupPoint(val=scalar_from_bytes(seed + b"_g1"))
        self.g2 = GroupPoint(val=scalar_from_bytes(seed + b"_g2"))
        self.h0 = GroupPoint(val=scalar_from_bytes(seed + b"_h0"))
        self.h_vec: List[GroupPoint] = []
        for i in range(message_count):
            h_i = GroupPoint(val=scalar_from_bytes(seed + f"_h_{i}".encode("utf-8")))
            self.h_vec.append(h_i)


# ============================================================================
# 3. KEY PAIRS & SIGNATURE DATA MODELS
# ============================================================================

@dataclass
class BBSPlusPublicKey:
    w: GroupPoint  # w = g2^x
    generators: BBSGenerators
    message_count: int
    key_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "w_digest": self.w.to_digest(),
            "message_count": self.message_count,
            "curve": "BLS12-381",
            "cryptosuite": "bbs-2023-v1.0"
        }

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "w_val": self.w.to_hex(),
            "w_digest": self.w.to_digest(),
            "message_count": self.message_count,
            "curve": "BLS12-381",
            "cryptosuite": "bbs-2023-v1.0"
        }

    @classmethod
    def from_manifest(cls, data: Dict[str, Any], seed: bytes = b"SMAOS_BBS_PLUS_GENERATORS_V1") -> 'BBSPlusPublicKey':
        gens = BBSGenerators(message_count=data["message_count"], seed=seed)
        w = GroupPoint.from_hex(data["w_val"])
        return cls(w=w, generators=gens, message_count=data["message_count"], key_id=data["key_id"])


@dataclass
class BBSPlusPrivateKey:
    x: int  # scalar in Fr
    public_key: BBSPlusPublicKey


@dataclass
class BBSPlusSignature:
    A: GroupPoint
    e: int
    s: int
    message_hashes: List[int]
    signature_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "A": self.A.to_digest(),
            "e": hex(self.e),
            "s": hex(self.s),
            "signature_digest": self.signature_digest
        }

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "A_val": self.A.to_hex(),
            "A_digest": self.A.to_digest(),
            "e_hex": hex(self.e),
            "s_hex": hex(self.s),
            "message_hashes_hex": [hex(m) for m in self.message_hashes],
            "signature_digest": self.signature_digest
        }

    @classmethod
    def from_manifest(cls, data: Dict[str, Any]) -> 'BBSPlusSignature':
        A = GroupPoint.from_hex(data["A_val"])
        e = int(data["e_hex"], 16)
        s = int(data["s_hex"], 16)
        m_hashes = [int(m, 16) for m in data["message_hashes_hex"]]
        return cls(A=A, e=e, s=s, message_hashes=m_hashes, signature_digest=data["signature_digest"])


@dataclass
class BBSPlusProof:
    """Zero-knowledge proof of signature and selective disclosure."""
    A_prime: GroupPoint
    A_bar: GroupPoint
    d: GroupPoint
    c: int  # Challenge hash
    hat_r1: int
    hat_r2: int
    hat_e: int
    hat_s_prime: int
    hat_hidden_messages: Dict[int, int]  # index -> hat scalar
    disclosed_messages: Dict[int, str]   # index -> plaintext message
    redacted_field_names: List[str]
    status: str = "GENERATED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "c": hex(self.c),
            "hat_r1": hex(self.hat_r1),
            "hat_e": hex(self.hat_e),
            "A_prime": self.A_prime.to_digest(),
            "A_bar": self.A_bar.to_digest(),
            "d": self.d.to_digest(),
            "disclosed_messages": self.disclosed_messages,
            "redacted_field_names": self.redacted_field_names
        }

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "A_prime_val": self.A_prime.to_hex(),
            "A_bar_val": self.A_bar.to_hex(),
            "d_val": self.d.to_hex(),
            "c_hex": hex(self.c),
            "hat_r1_hex": hex(self.hat_r1),
            "hat_r2_hex": hex(self.hat_r2),
            "hat_e_hex": hex(self.hat_e),
            "hat_s_prime_hex": hex(self.hat_s_prime),
            "hat_hidden_messages_hex": {str(k): hex(v) for k, v in self.hat_hidden_messages.items()},
            "disclosed_messages": {str(k): v for k, v in self.disclosed_messages.items()},
            "redacted_field_names": self.redacted_field_names
        }

    @classmethod
    def from_manifest(cls, data: Dict[str, Any]) -> 'BBSPlusProof':
        A_prime = GroupPoint.from_hex(data["A_prime_val"])
        A_bar = GroupPoint.from_hex(data["A_bar_val"])
        d = GroupPoint.from_hex(data["d_val"])
        c = int(data["c_hex"], 16)
        hat_r1 = int(data["hat_r1_hex"], 16)
        hat_r2 = int(data["hat_r2_hex"], 16)
        hat_e = int(data["hat_e_hex"], 16)
        hat_s_prime = int(data["hat_s_prime_hex"], 16)
        hat_hidden = {int(k): int(v, 16) for k, v in data["hat_hidden_messages_hex"].items()}
        disclosed = {int(k): v for k, v in data["disclosed_messages"].items()}
        return cls(
            A_prime=A_prime,
            A_bar=A_bar,
            d=d,
            c=c,
            hat_r1=hat_r1,
            hat_r2=hat_r2,
            hat_e=hat_e,
            hat_s_prime=hat_s_prime,
            hat_hidden_messages=hat_hidden,
            disclosed_messages=disclosed,
            redacted_field_names=data["redacted_field_names"],
            status=data.get("status", "VERIFIED_REDACTED")
        )


# ============================================================================
# 4. BBS+ CORE ENGINE (SIGNING & ZERO-KNOWLEDGE SELECTIVE PROOFS)
# ============================================================================

class BBSPlusEngine:
    """
    BBS+ Engine implementing vector signing, verification, and selective disclosure.
    """

    @staticmethod
    def generate_keypair(
        message_count: int,
        key_id: str = "cro-bbs-key-01",
        rng: Optional[DeterministicRNG] = None
    ) -> Tuple[BBSPlusPrivateKey, BBSPlusPublicKey]:
        """Generates a BBS+ keypair for signing message vectors of length `message_count`."""
        x = rng.next_scalar() if rng else random_scalar()
        gens = BBSGenerators(message_count=message_count)
        w = gens.g2.pow(x)
        pub = BBSPlusPublicKey(w=w, generators=gens, message_count=message_count, key_id=key_id)
        priv = BBSPlusPrivateKey(x=x, public_key=pub)
        return priv, pub

    @staticmethod
    def sign_messages(
        priv_key: BBSPlusPrivateKey,
        messages: List[str],
        rng: Optional[DeterministicRNG] = None
    ) -> BBSPlusSignature:
        """
        Signs a vector of string messages:
          m_i = scalar_from_bytes(messages[i])
          e, s = random scalars
          B = g1 * h0^s * prod(h_i^m_i)
          A = B^(1 / (x + e))
        """
        if len(messages) != priv_key.public_key.message_count:
            raise ValueError(f"Message count {len(messages)} != expected {priv_key.public_key.message_count}")

        gens = priv_key.public_key.generators
        m_scalars = [scalar_from_bytes(m.encode("utf-8")) for m in messages]

        e = rng.next_scalar() if rng else random_scalar()
        s = rng.next_scalar() if rng else random_scalar()

        # Compute B = g1 * h0^s * prod(h_i^m_i)
        B = gens.g1.pow(1) * gens.h0.pow(s)
        for i, m_val in enumerate(m_scalars):
            B = B * gens.h_vec[i].pow(m_val)

        # Compute A = B^(1 / (x + e))
        exp_inv = mod_inv(priv_key.x + e, BLS12_381_R)
        A = B.pow(exp_inv)

        sig_digest = hashlib.sha256(
            f"{A.to_digest()}:{e}:{s}".encode("utf-8")
        ).hexdigest()

        return BBSPlusSignature(
            A=A,
            e=e,
            s=s,
            message_hashes=m_scalars,
            signature_digest=sig_digest
        )

    @staticmethod
    def verify_full_signature(pub_key: BBSPlusPublicKey, signature: BBSPlusSignature, messages: List[str]) -> bool:
        """Verifies a full BBS+ signature against all disclosed messages."""
        if len(messages) != pub_key.message_count:
            return False

        gens = pub_key.generators
        m_scalars = [scalar_from_bytes(m.encode("utf-8")) for m in messages]

        # Reconstruct B = g1 * h0^s * prod(h_i^m_i)
        B = gens.g1.pow(1) * gens.h0.pow(signature.s)
        for i, m_val in enumerate(m_scalars):
            B = B * gens.h_vec[i].pow(m_val)

        # Bilinear pairing check: e(A, w * g2^e) == e(B, g2)
        # In scalar exponent domain: A.val * (w.val + g2.val * e) == B.val * g2.val mod r
        lhs_exp = (signature.A.val * (pub_key.w.val + (gens.g2.val * signature.e) % BLS12_381_R)) % BLS12_381_R
        rhs_exp = (B.val * gens.g2.val) % BLS12_381_R

        return lhs_exp == rhs_exp

    @staticmethod
    def create_selective_proof(
        pub_key: BBSPlusPublicKey,
        signature: BBSPlusSignature,
        messages: List[str],
        field_names: List[str],
        disclosed_indices: Set[int],
        rng: Optional[DeterministicRNG] = None
    ) -> BBSPlusProof:
        """
        Creates a Zero-Knowledge Selective Disclosure Proof:
          - Messages at indices in `disclosed_indices` are disclosed in plaintext.
          - Messages outside `disclosed_indices` (redacted PII / IBAN) are cryptographically blinded.
        """
        gens = pub_key.generators
        m_scalars = [scalar_from_bytes(m.encode("utf-8")) for m in messages]
        hidden_indices = sorted(list(set(range(len(messages))) - disclosed_indices))

        # Randomize signature with blinding factors r1, r2
        r1 = rng.next_scalar() if rng else random_scalar()
        r2 = rng.next_scalar() if rng else random_scalar()

        A_prime = signature.A.pow(r1)
        x_val = (pub_key.w.val * mod_inv(gens.g2.val)) % BLS12_381_R
        A_bar = A_prime.pow(x_val)

        s_prime = (signature.s * r1 - r2) % BLS12_381_R
        hidden_m_primes = {j: (m_scalars[j] * r1) % BLS12_381_R for j in hidden_indices}

        # d = g1^r1 * h0^r2 * prod_{j in hidden}(h_j^m'_j)
        d = gens.g1.pow(r1) * gens.h0.pow(r2)
        for j in hidden_indices:
            d = d * gens.h_vec[j].pow(hidden_m_primes[j])

        # Zero-Knowledge Schnorr Commitments
        t_r1 = rng.next_scalar() if rng else random_scalar()
        t_r2 = rng.next_scalar() if rng else random_scalar()
        t_e = rng.next_scalar() if rng else random_scalar()
        t_s_prime = rng.next_scalar() if rng else random_scalar()
        t_hidden_m = {j: (rng.next_scalar() if rng else random_scalar()) for j in hidden_indices}

        # C1 = g1^t_r1 * h0^t_r2 * prod_{j in hidden}(h_j^t_m_j)
        C1 = gens.g1.pow(t_r1) * gens.h0.pow(t_r2)
        for j in hidden_indices:
            C1 = C1 * gens.h_vec[j].pow(t_hidden_m[j])

        # hD = prod_{i in disclosed}(h_i^m_i)
        hD = GroupPoint(val=0)
        for i in disclosed_indices:
            hD = hD * gens.h_vec[i].pow(m_scalars[i])

        # C2 = A_prime^(-t_e) * h0^t_s_prime * hD^t_r1
        C2 = A_prime.pow(-t_e) * gens.h0.pow(t_s_prime) * hD.pow(t_r1)

        # Fiat-Shamir challenge hash
        challenge_preimage = (
            f"{A_prime.to_digest()}:{A_bar.to_digest()}:{d.to_digest()}:"
            f"{C1.to_digest()}:{C2.to_digest()}:"
            f"{sorted(list(disclosed_indices))}"
        ).encode("utf-8")
        c = scalar_from_bytes(challenge_preimage)

        # Responses
        hat_r1 = (t_r1 + c * r1) % BLS12_381_R
        hat_r2 = (t_r2 + c * r2) % BLS12_381_R
        hat_e = (t_e + c * signature.e) % BLS12_381_R
        hat_s_prime = (t_s_prime + c * s_prime) % BLS12_381_R
        hat_hidden_m = {j: (t_hidden_m[j] + c * hidden_m_primes[j]) % BLS12_381_R for j in hidden_indices}

        disclosed_dict = {i: messages[i] for i in disclosed_indices}
        redacted_fields = [field_names[j] for j in hidden_indices]

        return BBSPlusProof(
            A_prime=A_prime,
            A_bar=A_bar,
            d=d,
            c=c,
            hat_r1=hat_r1,
            hat_r2=hat_r2,
            hat_e=hat_e,
            hat_s_prime=hat_s_prime,
            hat_hidden_messages=hat_hidden_m,
            disclosed_messages=disclosed_dict,
            redacted_field_names=redacted_fields,
            status="VERIFIED_REDACTED"
        )

    @staticmethod
    def verify_selective_proof(
        pub_key: BBSPlusPublicKey,
        proof: BBSPlusProof,
        field_names: List[str]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verifies a BBS+ Zero-Knowledge Selective Disclosure Proof:
          1. Validates bilinear pairing e(A_prime, w) == e(A_bar, g2).
          2. Reconstructs commitments C1_rec, C2_rec.
          3. Matches Fiat-Shamir challenge hash c.
        """
        if proof.A_prime.val == 0:
            return False, "INVALID_IDENTITY_ELEMENT", {}

        gens = pub_key.generators

        # 1. Pairing Check: e(A_prime, w) == e(A_bar, g2)
        lhs_pairing = (proof.A_prime.val * pub_key.w.val) % BLS12_381_R
        rhs_pairing = (proof.A_bar.val * gens.g2.val) % BLS12_381_R
        if lhs_pairing != rhs_pairing:
            return False, "PAIRING_CHECK_FAILED", {}

        disclosed_indices = set(proof.disclosed_messages.keys())
        hidden_indices = sorted(list(set(range(pub_key.message_count)) - disclosed_indices))

        # 2. Reconstruct C1 = g1^hat_r1 * h0^hat_r2 * prod_{j in hidden}(h_j^hat_m_j) * d^(-c)
        C1_rec = gens.g1.pow(proof.hat_r1) * gens.h0.pow(proof.hat_r2)
        for j in hidden_indices:
            if j not in proof.hat_hidden_messages:
                return False, "MISSING_HIDDEN_MESSAGE_RESPONSE", {}
            C1_rec = C1_rec * gens.h_vec[j].pow(proof.hat_hidden_messages[j])
        C1_rec = C1_rec * proof.d.pow(-proof.c)

        # 3. Reconstruct C2 = A_prime^(-hat_e) * h0^hat_s_prime * hD^hat_r1 * (A_bar * d^(-1))^(-c)
        hD = GroupPoint(val=0)
        for i in disclosed_indices:
            m_scalar_i = scalar_from_bytes(proof.disclosed_messages[i].encode("utf-8"))
            hD = hD * gens.h_vec[i].pow(m_scalar_i)

        diff_A_bar_d = proof.A_bar * proof.d.pow(-1)
        C2_rec = proof.A_prime.pow(-proof.hat_e) * gens.h0.pow(proof.hat_s_prime) * hD.pow(proof.hat_r1) * diff_A_bar_d.pow(-proof.c)

        # 4. Recompute Fiat-Shamir challenge hash
        challenge_preimage = (
            f"{proof.A_prime.to_digest()}:{proof.A_bar.to_digest()}:{proof.d.to_digest()}:"
            f"{C1_rec.to_digest()}:{C2_rec.to_digest()}:"
            f"{sorted(list(disclosed_indices))}"
        ).encode("utf-8")
        c_rec = scalar_from_bytes(challenge_preimage)

        if c_rec != proof.c:
            return False, "CHALLENGE_VERIFICATION_FAILED_OR_TAMPERED", {}

        audit_meta = {
            "disclosed_fields": {field_names[i]: proof.disclosed_messages[i] for i in disclosed_indices if i < len(field_names)},
            "redacted_fields": proof.redacted_field_names,
            "gdpr_art17_erased_count": len(proof.redacted_field_names),
            "ai_act_art12_log_preserved": True,
            "pairing_invariant_verified": True,
            "zero_knowledge_proof_valid": True
        }

        return True, "VERIFIED_REDACTED", audit_meta


# ============================================================================
# 5. SOVEREIGN AUDIT LOG RECONCILIATION DATA MODEL
# ============================================================================

class SovereignAuditLogEntry:
    """
    Standard schema for SMAOS Execution Audit Trail (EU AI Act Art 12).
    Designates fields subject to GDPR Art 17 Right to Erasure.
    """
    FIELDS = [
        "event_id",
        "timestamp_iso",
        "agent_id",
        "tool_name",
        "user_full_name",   # PII
        "user_iban",        # PII
        "user_tax_id",      # PII
        "credit_limit_eur",
        "policy_verdict",
        "boundary_hash"
    ]

    SENSITIVE_PII_FIELDS = {
        "user_full_name",
        "user_iban",
        "user_tax_id"
    }

    def __init__(self, data: Dict[str, str]):
        for f in self.FIELDS:
            if f not in data:
                raise ValueError(f"Missing required audit field: {f}")
        self.data = data

    def to_message_vector(self) -> List[str]:
        return [self.data[f] for f in self.FIELDS]

    @classmethod
    def get_field_names(cls) -> List[str]:
        return cls.FIELDS

    @classmethod
    def get_non_pii_indices(cls) -> Set[int]:
        return {i for i, f in enumerate(cls.FIELDS) if f not in cls.SENSITIVE_PII_FIELDS}


# ============================================================================
# 6. TEST VECTOR MANIFEST GENERATION & VERIFICATION
# ============================================================================

def generate_test_vector_manifest(output_path: str):
    """Generates a deterministic test vector manifest for conformance testing."""
    rng = DeterministicRNG(seed=b"SMAOS_BBS_PLUS_CONFORMANCE_V1_SEED")
    field_names = SovereignAuditLogEntry.get_field_names()

    priv_key, pub_key = BBSPlusEngine.generate_keypair(
        message_count=len(field_names),
        key_id="example-bank-cro-bbs-01",
        rng=rng
    )

    log_data = {
        "event_id": "EVT-2026-9901",
        "timestamp_iso": "2026-09-12T22:00:00Z",
        "agent_id": "SMAOS-LOAN-OFFICER-01",
        "tool_name": "credit_facility_underwrite",
        "user_full_name": "Jane Doe",
        "user_iban": "XX00EXAMPLE0000000000001",
        "user_tax_id": "TAX-EXAMPLE-001",
        "credit_limit_eur": "1850000",
        "policy_verdict": "APPROVED_CONDITIONAL_JIDOKA",
        "boundary_hash": "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890"
    }

    entry = SovereignAuditLogEntry(log_data)
    messages = entry.to_message_vector()

    # 1. Full signature
    sig = BBSPlusEngine.sign_messages(priv_key, messages, rng=rng)

    # 2. Selective proof (PII blinded)
    disclosed_indices = SovereignAuditLogEntry.get_non_pii_indices()
    proof = BBSPlusEngine.create_selective_proof(
        pub_key=pub_key,
        signature=sig,
        messages=messages,
        field_names=field_names,
        disclosed_indices=disclosed_indices,
        rng=rng
    )

    # 3. Tampered disclosed field
    tampered_proof_msg = BBSPlusProof.from_manifest(proof.to_manifest())
    credit_idx = field_names.index("credit_limit_eur")
    tampered_proof_msg.disclosed_messages[credit_idx] = "9999999"

    # 4. Tampered scalar hat_e
    tampered_proof_scalar = BBSPlusProof.from_manifest(proof.to_manifest())
    tampered_proof_scalar.hat_e = (tampered_proof_scalar.hat_e + 1) % BLS12_381_R

    # 5. Wrong public key
    rng_wrong = DeterministicRNG(seed=b"SMAOS_BBS_PLUS_WRONG_KEY_SEED")
    _, wrong_pub_key = BBSPlusEngine.generate_keypair(
        message_count=len(field_names),
        key_id="adversary-bbs-01",
        rng=rng_wrong
    )

    manifest = {
        "manifest_version": "1.0.0",
        "standard": "W3C Data Integrity BBS Cryptosuites v1.0 / BLS12-381 Scalar Field",
        "description": "Deterministic test vectors for BBS+ Selectively Redactable Signatures (GDPR Art 17 vs AI Act Art 12)",
        "curve_parameters": {
            "curve": "BLS12-381",
            "scalar_field_order_r": hex(BLS12_381_R),
            "message_count": len(field_names),
            "field_names": field_names
        },
        "issuer_public_key": pub_key.to_manifest(),
        "original_log_entry": log_data,
        "test_vectors": [
            {
                "vector_id": "VEC-01-FULL-SIGNATURE",
                "description": "Valid 10-message vector signed with genuine private key",
                "signature": sig.to_manifest(),
                "expected_verified": True
            },
            {
                "vector_id": "VEC-02-SELECTIVE-REDACTION-GDPR-ART17",
                "description": "Selective disclosure proof blinding 3 customer PII fields (Name, IBAN, Tax ID)",
                "redacted_fields": list(SovereignAuditLogEntry.SENSITIVE_PII_FIELDS),
                "proof": proof.to_manifest(),
                "expected_status": "VERIFIED_REDACTED",
                "expected_verified": True,
                "expected_gdpr_art17_erased_count": 3,
                "expected_ai_act_art12_log_preserved": True
            },
            {
                "vector_id": "VEC-03-TAMPERED-DISCLOSED-FIELD",
                "description": "Adversary alters disclosed credit_limit_eur from 1850000 to 9999999",
                "proof": tampered_proof_msg.to_manifest(),
                "expected_status": "CHALLENGE_VERIFICATION_FAILED_OR_TAMPERED",
                "expected_verified": False
            },
            {
                "vector_id": "VEC-04-TAMPERED-PROOF-SCALAR",
                "description": "Adversary manipulates response scalar hat_e",
                "proof": tampered_proof_scalar.to_manifest(),
                "expected_status": "CHALLENGE_VERIFICATION_FAILED_OR_TAMPERED",
                "expected_verified": False
            },
            {
                "vector_id": "VEC-05-WRONG-ISSUER-PUBLIC-KEY",
                "description": "Proof verified against adversary public key",
                "wrong_public_key": wrong_pub_key.to_manifest(),
                "proof": proof.to_manifest(),
                "expected_status": "PAIRING_CHECK_FAILED",
                "expected_verified": False
            }
        ]
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"✅ Generated deterministic test vector manifest at {output_path}")


def verify_test_vector_manifest(manifest_path: str) -> bool:
    """Verifies all test vectors within a manifest file."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    field_names = manifest["curve_parameters"]["field_names"]
    pub_key = BBSPlusPublicKey.from_manifest(manifest["issuer_public_key"])
    log_entry = SovereignAuditLogEntry(manifest["original_log_entry"])
    messages = log_entry.to_message_vector()

    all_passed = True
    for vec in manifest["test_vectors"]:
        v_id = vec["vector_id"]
        if v_id == "VEC-01-FULL-SIGNATURE":
            sig = BBSPlusSignature.from_manifest(vec["signature"])
            res = BBSPlusEngine.verify_full_signature(pub_key, sig, messages)
            if res != vec["expected_verified"]:
                print(f"❌ {v_id} failed: expected {vec['expected_verified']}, got {res}")
                all_passed = False
            else:
                print(f"  [+] {v_id}: PASSED")

        elif v_id in ("VEC-02-SELECTIVE-REDACTION-GDPR-ART17", "VEC-03-TAMPERED-DISCLOSED-FIELD", "VEC-04-TAMPERED-PROOF-SCALAR"):
            proof = BBSPlusProof.from_manifest(vec["proof"])
            is_valid, status, meta = BBSPlusEngine.verify_selective_proof(pub_key, proof, field_names)
            if is_valid != vec["expected_verified"] or status != vec["expected_status"]:
                print(f"❌ {v_id} failed: expected ({vec['expected_verified']}, {vec['expected_status']}), got ({is_valid}, {status})")
                all_passed = False
            else:
                if vec.get("expected_gdpr_art17_erased_count"):
                    assert meta["gdpr_art17_erased_count"] == vec["expected_gdpr_art17_erased_count"]
                print(f"  [+] {v_id}: PASSED ({status})")

        elif v_id == "VEC-05-WRONG-ISSUER-PUBLIC-KEY":
            wrong_pub = BBSPlusPublicKey.from_manifest(vec["wrong_public_key"])
            proof = BBSPlusProof.from_manifest(vec["proof"])
            is_valid, status, _ = BBSPlusEngine.verify_selective_proof(wrong_pub, proof, field_names)
            if is_valid != vec["expected_verified"] or status != vec["expected_status"]:
                print(f"❌ {v_id} failed: expected ({vec['expected_verified']}, {vec['expected_status']}), got ({is_valid}, {status})")
                all_passed = False
            else:
                print(f"  [+] {v_id}: PASSED ({status})")

    return all_passed


# ============================================================================
# 7. SELF-TEST & CLI
# ============================================================================

def self_test():
    """Validates BBS+ signing, full verification, selective disclosure, and tamper detection."""
    print("[*] Testing BBS+ Selectively Redactable Signatures (GDPR Art 17 vs AI Act Art 12)...")
    
    field_names = SovereignAuditLogEntry.get_field_names()
    priv_key, pub_key = BBSPlusEngine.generate_keypair(message_count=len(field_names), key_id="example-bank-cro-bbs-01")

    log_data = {
        "event_id": "EVT-2026-9901",
        "timestamp_iso": "2026-09-12T22:00:00Z",
        "agent_id": "SMAOS-LOAN-OFFICER-01",
        "tool_name": "credit_facility_underwrite",
        "user_full_name": "Jane Doe",
        "user_iban": "XX00EXAMPLE0000000000001",
        "user_tax_id": "TAX-EXAMPLE-001",
        "credit_limit_eur": "1850000",
        "policy_verdict": "APPROVED_CONDITIONAL_JIDOKA",
        "boundary_hash": "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890"
    }

    entry = SovereignAuditLogEntry(log_data)
    messages = entry.to_message_vector()

    # 1. Sign full record
    sig = BBSPlusEngine.sign_messages(priv_key, messages)
    assert BBSPlusEngine.verify_full_signature(pub_key, sig, messages), "Full signature verification failed!"
    print("  [+] Full BBS+ signature verified successfully.")

    # 2. DPO invokes GDPR Article 17 (Right to Erasure) on customer PII
    disclosed_indices = SovereignAuditLogEntry.get_non_pii_indices()
    proof = BBSPlusEngine.create_selective_proof(
        pub_key=pub_key,
        signature=sig,
        messages=messages,
        field_names=field_names,
        disclosed_indices=disclosed_indices
    )
    print(f"  [+] Created selective disclosure proof. Redacted: {proof.redacted_field_names}")

    # 3. Verifier checks proof without seeing Jane Doe, IBAN, or Tax ID
    is_valid, status, audit_meta = BBSPlusEngine.verify_selective_proof(pub_key, proof, field_names)
    assert is_valid, f"Selective proof failed: {status}"
    assert status == "VERIFIED_REDACTED"
    assert "Jane Doe" not in str(proof.disclosed_messages)
    assert "XX00EXAMPLE0000000000001" not in str(proof.disclosed_messages)
    print("  [+] Selective proof verification succeeded: VERIFIED_REDACTED.")

    # 4. Tampering detection: Altering a disclosed field
    import copy
    tampered_proof = copy.deepcopy(proof)
    tampered_proof.disclosed_messages[0] = "EVT-MALICIOUS-TAMPER"
    is_tampered_valid, status_tampered, _ = BBSPlusEngine.verify_selective_proof(pub_key, tampered_proof, field_names)
    assert not is_tampered_valid, "Tampering was not detected!"
    print(f"  [+] Tampering successfully detected and rejected: {status_tampered}")

    print("✅ BBS+ Selectively Redactable Signatures self-test passed!")


def main():
    parser = argparse.ArgumentParser(description="BBS+ Selectively Redactable Signatures Reference Engine")
    parser.add_argument("--generate-manifest", help="Generate deterministic test vector manifest to path", default=None)
    parser.add_argument("--verify-manifest", help="Verify deterministic test vector manifest from path", default=None)
    args = parser.parse_args()

    if args.generate_manifest:
        generate_test_vector_manifest(args.generate_manifest)
        return

    if args.verify_manifest:
        ok = verify_test_vector_manifest(args.verify_manifest)
        if not ok:
            sys.exit(1)
        print("✅ All manifest test vectors verified successfully!")
        return

    self_test()


if __name__ == "__main__":
    main()
