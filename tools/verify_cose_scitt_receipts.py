#!/usr/bin/env python3
"""
AEIB RFC 9052 COSE_Sign1 & IETF SCITT (RFC 9942 / RFC 9943) Transparency Receipt Verifier.
Part of SovereignNexus AEIB v1.1 Architecture.

Evaluated under the stated model:
- RFC 9052 COSE_Sign1 CBOR envelopes (Tag 18)
- Exact Ed25519 signature over canonical Sig_structure
- RFC 8785 JCS inner receipt payload integrity
- RFC 9162 / RFC 9942 SHA-256 binary Merkle tree inclusion proofs with domain separation
- RFC 9943 SCITT Transparency Service registration and offline Transparent Statement verification
- External AAD binding (e.g. Merkle checkpoint root)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ROADMAP_COSE_PATH = REPO_ROOT / "v1.1-roadmap" / "rfc9052_cose_profile.py"
cose_spec = importlib.util.spec_from_file_location("rfc9052_cose_profile", ROADMAP_COSE_PATH)
if cose_spec is None or cose_spec.loader is None:
    raise ImportError(f"Cannot load {ROADMAP_COSE_PATH}")
cose_mod = importlib.util.module_from_spec(cose_spec)
sys.modules["rfc9052_cose_profile"] = cose_mod
cose_spec.loader.exec_module(cose_mod)

RFC8949CBOR = cose_mod.RFC8949CBOR
RFC9052CoseVerifier = cose_mod.RFC9052CoseVerifier
RFC9052CoseSigner = cose_mod.RFC9052CoseSigner

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs


LEAF_DOMAIN_PREFIX = b"\x00"
NODE_DOMAIN_PREFIX = b"\x01"


class SCITTMerkleTree:
    """
    Pure Python SHA-256 binary Merkle tree implementing RFC 9162 / RFC 9942
    domain separation under the stated model:
      - Leaf hash: SHA-256(0x00 || statement_cbor)
      - Internal node hash: SHA-256(0x01 || left_hash || right_hash)
    """

    def __init__(self) -> None:
        self._leaf_hashes: List[bytes] = []

    @staticmethod
    def hash_leaf(statement_cbor: bytes) -> bytes:
        if not isinstance(statement_cbor, (bytes, bytearray)):
            raise TypeError("statement_cbor must be bytes")
        return hashlib.sha256(LEAF_DOMAIN_PREFIX + bytes(statement_cbor)).digest()

    @staticmethod
    def hash_children(left: bytes, right: bytes) -> bytes:
        return hashlib.sha256(NODE_DOMAIN_PREFIX + left + right).digest()

    @property
    def tree_size(self) -> int:
        return len(self._leaf_hashes)

    def add_leaf(self, statement_cbor: bytes) -> int:
        """Appends a signed statement CBOR byte string and returns its 0-based leaf_index."""
        leaf_hash = self.hash_leaf(statement_cbor)
        idx = len(self._leaf_hashes)
        self._leaf_hashes.append(leaf_hash)
        return idx

    @classmethod
    def _mth(cls, leaves: List[bytes]) -> bytes:
        n = len(leaves)
        if n == 0:
            return hashlib.sha256(b"").digest()
        if n == 1:
            return leaves[0]
        k = 1 << ((n - 1).bit_length() - 1)
        left = cls._mth(leaves[:k])
        right = cls._mth(leaves[k:])
        return cls.hash_children(left, right)

    def root_hash(self) -> bytes:
        """Computes the RFC 9162 Merkle Tree Hash (MTH) over all current leaves."""
        return self._mth(self._leaf_hashes)

    @classmethod
    def _path(cls, m: int, leaves: List[bytes]) -> List[bytes]:
        n = len(leaves)
        if n == 1 and m == 0:
            return []
        k = 1 << ((n - 1).bit_length() - 1)
        if m < k:
            return cls._path(m, leaves[:k]) + [cls._mth(leaves[k:])]
        return cls._path(m - k, leaves[k:]) + [cls._mth(leaves[:k])]

    def inclusion_proof(self, leaf_index: int) -> Dict[str, Any]:
        """
        Generates an RFC 9942 / RFC 9162 inclusion proof for leaf_index across the current tree.
        """
        n = len(self._leaf_hashes)
        if leaf_index < 0 or leaf_index >= n:
            raise ValueError(f"leaf_index {leaf_index} out of bounds for tree_size {n}")
        audit_hashes = self._path(leaf_index, self._leaf_hashes)
        return {
            "leaf_index": leaf_index,
            "tree_size": n,
            "audit_path": [h.hex() for h in audit_hashes],
            "root_hash_hex": self.root_hash().hex(),
        }

    @classmethod
    def verify_inclusion_proof(
        cls,
        statement_cbor: bytes,
        proof: Dict[str, Any],
        expected_root_hex: str,
    ) -> bool:
        """
        Offline verification of an RFC 9162 / RFC 9942 SHA-256 Merkle inclusion proof.
        Evaluated fail-closed under the stated model.
        """
        if not isinstance(proof, dict) or not isinstance(expected_root_hex, str):
            return False
        leaf_index = proof.get("leaf_index")
        tree_size = proof.get("tree_size")
        audit_path = proof.get("audit_path")
        proof_root_hex = proof.get("root_hash_hex")

        if (
            not isinstance(leaf_index, int)
            or isinstance(leaf_index, bool)
            or not isinstance(tree_size, int)
            or isinstance(tree_size, bool)
            or not isinstance(audit_path, list)
        ):
            return False

        if leaf_index < 0 or tree_size <= 0 or leaf_index >= tree_size:
            return False

        try:
            expected_root = bytes.fromhex(expected_root_hex)
            if len(expected_root) != 32:
                return False
            if proof_root_hex is not None:
                if bytes.fromhex(proof_root_hex) != expected_root:
                    return False
        except Exception:
            return False

        # Reconstruct top-down split direction steps per RFC 9162 Section 2.1.3
        steps_is_right_sibling: List[bool] = []
        m = leaf_index
        n = tree_size
        while n > 1:
            k = 1 << ((n - 1).bit_length() - 1)
            if m < k:
                steps_is_right_sibling.append(True)
                n = k
            else:
                steps_is_right_sibling.append(False)
                m = m - k
                n = n - k

        if len(audit_path) != len(steps_is_right_sibling):
            return False

        current_hash = cls.hash_leaf(statement_cbor)
        for sibling_hex, is_right_sibling in zip(
            audit_path, reversed(steps_is_right_sibling)
        ):
            if not isinstance(sibling_hex, str):
                return False
            try:
                sibling_bytes = bytes.fromhex(sibling_hex)
            except ValueError:
                return False
            if len(sibling_bytes) != 32:
                return False
            if is_right_sibling:
                current_hash = cls.hash_children(current_hash, sibling_bytes)
            else:
                current_hash = cls.hash_children(sibling_bytes, current_hash)

        return current_hash == expected_root


class SCITTTransparencyService:
    """
    Prototype IETF SCITT (RFC 9943) Transparency Service issuing RFC 9942 COSE Receipts
    over an append-only SHA-256 Merkle tree.
    """

    def __init__(self, service_id: str, ts_privkey: ed25519.Ed25519PrivateKey) -> None:
        if not service_id:
            raise ValueError("service_id must be a non-empty string")
        self.service_id = service_id
        self.ts_privkey = ts_privkey
        self.ts_kid = f"scitt-ts:{service_id}"
        self.tree = SCITTMerkleTree()
        self._signer = RFC9052CoseSigner(private_key=ts_privkey, key_id=self.ts_kid)

    def register_signed_statement(
        self,
        signed_statement_cbor: bytes,
        issuer_pubkey: ed25519.Ed25519PublicKey,
        expected_aad: bytes = b"",
    ) -> Dict[str, Any]:
        """
        Verifies an incoming COSE_Sign1 Signed Statement against the Registration Policy,
        appends it to the SCITT Merkle tree, and issues a signed COSE_Sign1 Receipt.
        Fails closed with ValueError if the incoming statement is invalid.
        """
        stmt_res = RFC9052CoseVerifier.verify(
            signed_statement_cbor,
            issuer_pubkey,
            expected_external_aad=expected_aad,
        )
        if not stmt_res.valid:
            raise ValueError(
                f"SCITT Registration Policy rejected Signed Statement: {stmt_res.error}"
            )

        leaf_index = self.tree.add_leaf(signed_statement_cbor)
        proof = self.tree.inclusion_proof(leaf_index)
        statement_sha256 = hashlib.sha256(signed_statement_cbor).hexdigest()

        receipt_claims = {
            "service_id": self.service_id,
            "leaf_index": proof["leaf_index"],
            "tree_size": proof["tree_size"],
            "audit_path": proof["audit_path"],
            "merkle_root_hex": proof["root_hash_hex"],
            "statement_sha256": statement_sha256,
        }
        receipt_payload_bytes = encode_jcs(receipt_claims)
        cose_receipt_bytes = self._signer.sign(
            receipt_payload_bytes,
            external_aad=expected_aad,
        )

        return {
            "signed_statement_b64": base64.b64encode(signed_statement_cbor).decode("ascii"),
            "cose_receipt_b64": base64.b64encode(cose_receipt_bytes).decode("ascii"),
            "inclusion_proof": proof,
            "merkle_root_hex": proof["root_hash_hex"],
            "issuer_kid": stmt_res.kid,
            "ts_kid": self.ts_kid,
        }


def verify_transparent_statement(
    bundle: Dict[str, Any],
    issuer_pubkey: ed25519.Ed25519PublicKey,
    ts_pubkey: ed25519.Ed25519PublicKey,
    expected_aad: bytes = b"",
) -> Dict[str, Any]:
    """
    Offline verification of an IETF SCITT Transparent Statement bundle:
      1. Issuer COSE_Sign1 signature over the Signed Statement;
      2. Transparency Service COSE_Sign1 signature over the COSE Receipt;
      3. Statement SHA-256 binding between the receipt and the statement;
      4. RFC 9162 / RFC 9942 SHA-256 Merkle inclusion path up to the signed merkle_root_hex.
    """
    try:
        signed_statement_cbor = base64.b64decode(bundle["signed_statement_b64"])
        cose_receipt_bytes = base64.b64decode(bundle["cose_receipt_b64"])
    except Exception as exc:
        return {"valid": False, "error": f"Malformed base64 in bundle: {exc}"}

    # 1. Verify Issuer COSE_Sign1 signature over the Signed Statement
    stmt_res = RFC9052CoseVerifier.verify(
        signed_statement_cbor,
        issuer_pubkey,
        expected_external_aad=expected_aad,
    )
    if not stmt_res.valid:
        return {
            "valid": False,
            "error": f"Issuer Signed Statement verification failed: {stmt_res.error}",
        }

    # 2. Verify Transparency Service COSE_Sign1 signature over the COSE Receipt
    rcpt_res = RFC9052CoseVerifier.verify(
        cose_receipt_bytes,
        ts_pubkey,
        expected_external_aad=expected_aad,
    )
    if not rcpt_res.valid:
        return {
            "valid": False,
            "error": f"Transparency Service COSE Receipt verification failed: {rcpt_res.error}",
        }

    try:
        receipt_claims = json.loads(rcpt_res.payload.decode("utf-8"))
        if encode_jcs(receipt_claims) != rcpt_res.payload:
            return {
                "valid": False,
                "error": "COSE Receipt payload is not RFC 8785 JCS canonical",
            }
    except Exception as exc:
        return {"valid": False, "error": f"Malformed COSE Receipt JSON payload: {exc}"}

    # 3. Verify Statement SHA-256 binding
    actual_stmt_sha256 = hashlib.sha256(signed_statement_cbor).hexdigest()
    if receipt_claims.get("statement_sha256") != actual_stmt_sha256:
        return {
            "valid": False,
            "error": "Statement SHA-256 mismatch between Signed Statement and COSE Receipt",
        }

    # 4. Cross-check bundle metadata against signed receipt claims and verify Merkle inclusion proof
    signed_root_hex = receipt_claims.get("merkle_root_hex")
    if not isinstance(signed_root_hex, str):
        return {"valid": False, "error": "Missing merkle_root_hex in COSE Receipt"}

    bundle_root_hex = bundle.get("merkle_root_hex")
    if bundle_root_hex is not None and bundle_root_hex != signed_root_hex:
        return {
            "valid": False,
            "error": "Bundle merkle_root_hex does not match signed COSE Receipt merkle_root_hex",
        }

    signed_proof = {
        "leaf_index": receipt_claims.get("leaf_index"),
        "tree_size": receipt_claims.get("tree_size"),
        "audit_path": receipt_claims.get("audit_path"),
        "root_hash_hex": signed_root_hex,
    }
    bundle_proof = bundle.get("inclusion_proof")
    if bundle_proof is not None and bundle_proof != signed_proof:
        return {
            "valid": False,
            "error": "Bundle inclusion_proof does not match signed COSE Receipt claims",
        }

    if not SCITTMerkleTree.verify_inclusion_proof(
        signed_statement_cbor,
        signed_proof,
        signed_root_hex,
    ):
        return {
            "valid": False,
            "error": "RFC 9942 / RFC 9162 Merkle inclusion proof verification failed",
        }

    return {
        "valid": True,
        "service_id": receipt_claims.get("service_id"),
        "leaf_index": signed_proof["leaf_index"],
        "tree_size": signed_proof["tree_size"],
        "merkle_root_hex": signed_root_hex,
        "statement_sha256": actual_stmt_sha256,
        "issuer_kid": stmt_res.kid,
        "ts_kid": rcpt_res.kid,
        "statement_payload": stmt_res.payload,
        "error": None,
    }


def load_public_key(pubkey_str: str) -> ed25519.Ed25519PublicKey:
    path = Path(pubkey_str)
    if path.exists():
        data = path.read_bytes()
        try:
            return serialization.load_pem_public_key(data)
        except Exception:
            return ed25519.Ed25519PublicKey.from_public_bytes(data)
    try:
        raw_bytes = bytes.fromhex(pubkey_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
    except ValueError:
        pass
    try:
        raw_bytes = base64.b64decode(pubkey_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
    except Exception:
        pass
    raise ValueError(f"Unable to parse public key from: {pubkey_str}")


def run_self_test() -> int:
    """
    Runs a deterministic 4-leaf SCITT Transparency Service and offline verification
    demonstration under the stated model.
    """
    issuer_priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"aeib-scitt-self-test-issuer-key").digest()
    )
    issuer_pub = issuer_priv.public_key()
    ts_priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"aeib-scitt-self-test-ts-key").digest()
    )
    ts_pub = ts_priv.public_key()

    issuer_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:aeib-gatekeeper-01")
    ts_service = SCITTTransparencyService(
        service_id="scitt.sovereignnexus.internal",
        ts_privkey=ts_priv,
    )
    aad = b"aeib-scitt-v1.1-domain"

    statements: List[bytes] = []
    bundles: List[Dict[str, Any]] = []
    for idx in range(4):
        claim = {
            "caid": hashlib.sha256(f"episode-{idx}".encode("utf-8")).hexdigest(),
            "disposition": "ALLOW",
            "sequence": idx,
        }
        stmt_cbor, _ = issuer_signer.sign_receipt(claim, external_aad=aad)
        statements.append(stmt_cbor)
        bundle = ts_service.register_signed_statement(
            stmt_cbor,
            issuer_pubkey=issuer_pub,
            expected_aad=aad,
        )
        bundles.append(bundle)

    # Verify each bundle at its issuance checkpoint and against the final 4-leaf tree
    final_root_hex = ts_service.tree.root_hash().hex()
    for idx, bundle in enumerate(bundles):
        res = verify_transparent_statement(
            bundle,
            issuer_pubkey=issuer_pub,
            ts_pubkey=ts_pub,
            expected_aad=aad,
        )
        if not res["valid"]:
            print(f"[-] SCITT self-test failed at leaf {idx}: {res['error']}", file=sys.stderr)
            return 1

        full_proof = ts_service.tree.inclusion_proof(idx)
        if not SCITTMerkleTree.verify_inclusion_proof(
            statements[idx], full_proof, final_root_hex
        ):
            print(f"[-] SCITT 4-leaf inclusion proof failed at leaf {idx}", file=sys.stderr)
            return 1

    print("[✓] IETF SCITT (RFC 9942 / RFC 9943) & RFC 9052 COSE Self-Test PASSED")
    print(f"    - Service ID        : {ts_service.service_id}")
    print(f"    - Tree Size         : {ts_service.tree.tree_size} leaves")
    print(f"    - Final Merkle Root : {final_root_hex}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEIB RFC 9052 COSE_Sign1 & IETF SCITT Receipt Verifier"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run end-to-end 4-leaf IETF SCITT & RFC 9052 COSE self-test",
    )
    parser.add_argument(
        "--envelope",
        help="Path to COSE_Sign1 CBOR binary envelope (.cose)",
    )
    parser.add_argument(
        "--public-key",
        help="Path to Ed25519 public key PEM or raw bytes",
    )
    parser.add_argument(
        "--aad",
        default="",
        help="Optional external AAD (hex string or utf-8)",
    )

    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_self_test())

    if not args.envelope or not args.public_key:
        parser.error("the following arguments are required: --envelope, --public-key (unless --self-test is set)")

    envelope_path = Path(args.envelope)
    if not envelope_path.exists():
        print(f"[-] Envelope file not found: {args.envelope}", file=sys.stderr)
        sys.exit(1)

    envelope_bytes = envelope_path.read_bytes()
    pubkey = load_public_key(args.public_key)

    aad_bytes = b""
    if args.aad:
        try:
            aad_bytes = bytes.fromhex(args.aad)
        except ValueError:
            aad_bytes = args.aad.encode("utf-8")

    verifier = RFC9052CoseVerifier()
    res = verifier.verify(envelope_bytes, pubkey, expected_external_aad=aad_bytes)

    if not res.valid:
        print(f"[-] COSE_Sign1 Verification FAILED: {res.error}", file=sys.stderr)
        sys.exit(1)

    print("[✓] RFC 9052 COSE_Sign1 Receipt Verification SUCCESSFUL")
    print(f"    - Algorithm         : {res.alg} (EdDSA)")
    print(f"    - Key ID            : {res.kid}")
    print(f"    - Payload Bytes     : {len(res.payload)}")
    print(f"    - Protected Headers : {res.protected_headers}")
    print(f"    - Unprotected Headers: {res.unprotected_headers}")

    try:
        inner_json = json.loads(res.payload.decode("utf-8"))
        print("    - Inner Payload CAID: " + inner_json.get("caid", "N/A"))
        print("    - Inner Disposition : " + inner_json.get("disposition", "N/A"))
    except Exception:
        pass


if __name__ == "__main__":
    main()

