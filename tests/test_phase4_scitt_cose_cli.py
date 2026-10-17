"""
tests/test_phase4_scitt_cose_cli.py — Phase 4 Verification Suite for IETF SCITT (RFC 9942 / RFC 9943)
and RFC 9052 COSE Transparent Statement CLI (`tools/verify_cose_scitt_receipts.py`).

Evaluated under the stated model:
- SCITTMerkleTree inclusion proofs across 1, 4, and 7 leaves with RFC 9162 0x00/0x01 domain separation
- SCITTTransparencyService registration policy enforcement and COSE_Sign1 receipt issuance
- verify_transparent_statement positive and falsification paths
- CLI execution via subprocess (--self-test and --envelope / --public-key / --aad)
"""

from __future__ import annotations

import base64
import copy
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from tools.verify_cose_scitt_receipts import (
    RFC8949CBOR,
    RFC9052CoseSigner,
    SCITTMerkleTree,
    SCITTTransparencyService,
    load_public_key,
    verify_transparent_statement,
)


def _derive_keypair(seed_label: str) -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(seed_label.encode("utf-8")).digest()
    )
    return priv, priv.public_key()


@pytest.mark.parametrize("num_leaves", [1, 4, 7])
def test_scitt_merkle_tree_inclusion_proofs_and_domain_separation(num_leaves: int) -> None:
    """
    Evaluates SCITTMerkleTree across 1, 4, and 7 leaves with explicit 0x00 leaf
    and 0x01 internal node domain separation under the stated model.
    """
    tree = SCITTMerkleTree()
    statements = [f"statement-payload-{i}".encode("utf-8") for i in range(num_leaves)]

    for idx, stmt in enumerate(statements):
        assigned_idx = tree.add_leaf(stmt)
        assert assigned_idx == idx

    root = tree.root_hash()
    root_hex = root.hex()
    assert len(root) == 32

    if num_leaves == 1:
        # RFC 9162 domain separation: single leaf root equals SHA-256(0x00 || leaf_bytes)
        expected_single = hashlib.sha256(b"\x00" + statements[0]).digest()
        assert root == expected_single
        raw_unprefixed = hashlib.sha256(statements[0]).digest()
        assert root != raw_unprefixed

    if num_leaves == 4:
        # Explicit 4-leaf manual check with 0x00 leaf and 0x01 node prefixes
        leaf_hashes = [hashlib.sha256(b"\x00" + s).digest() for s in statements]
        n01 = hashlib.sha256(b"\x01" + leaf_hashes[0] + leaf_hashes[1]).digest()
        n23 = hashlib.sha256(b"\x01" + leaf_hashes[2] + leaf_hashes[3]).digest()
        expected_root_4 = hashlib.sha256(b"\x01" + n01 + n23).digest()
        assert root == expected_root_4

    for idx, stmt in enumerate(statements):
        proof = tree.inclusion_proof(idx)
        assert proof["leaf_index"] == idx
        assert proof["tree_size"] == num_leaves
        assert proof["root_hash_hex"] == root_hex
        assert SCITTMerkleTree.verify_inclusion_proof(stmt, proof, root_hex) is True
        # Wrong statement bytes must fail verification
        assert SCITTMerkleTree.verify_inclusion_proof(stmt + b"-tampered", proof, root_hex) is False


def test_scitt_transparent_statement_positive_path() -> None:
    """
    Tests end-to-end SCITTTransparencyService registration and offline
    verify_transparent_statement validation.
    """
    issuer_priv, issuer_pub = _derive_keypair("phase4-scitt-issuer-positive")
    ts_priv, ts_pub = _derive_keypair("phase4-scitt-ts-positive")

    issuer_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:gatekeeper-alpha")
    ts = SCITTTransparencyService(service_id="scitt.aeib.local", ts_privkey=ts_priv)
    aad = b"aeib-zone1-context"

    bundle_list = []
    for i in range(3):
        statement_claim = {
            "caid": hashlib.sha256(f"claim-{i}".encode("utf-8")).hexdigest(),
            "disposition": "ALLOW",
            "step": i,
        }
        stmt_cbor, _ = issuer_signer.sign_receipt(statement_claim, external_aad=aad)
        bundle = ts.register_signed_statement(stmt_cbor, issuer_pubkey=issuer_pub, expected_aad=aad)
        bundle_list.append(bundle)

        result = verify_transparent_statement(
            bundle,
            issuer_pubkey=issuer_pub,
            ts_pubkey=ts_pub,
            expected_aad=aad,
        )
        assert result["valid"] is True
        assert result["error"] is None
        assert result["service_id"] == "scitt.aeib.local"
        assert result["leaf_index"] == i
        assert result["tree_size"] == i + 1
        assert result["issuer_kid"] == "issuer:gatekeeper-alpha"
        assert result["ts_kid"] == "scitt-ts:scitt.aeib.local"


def test_scitt_falsification_unverified_or_tampered_cose_rejected_on_registration() -> None:
    """
    Falsification 1: Unverified or tampered COSE_Sign1 Signed Statement must be
    rejected by SCITTTransparencyService.register_signed_statement with ValueError.
    """
    issuer_priv, issuer_pub = _derive_keypair("phase4-scitt-issuer-reg")
    wrong_priv, _ = _derive_keypair("phase4-scitt-wrong-issuer-reg")
    ts_priv, _ = _derive_keypair("phase4-scitt-ts-reg")

    ts = SCITTTransparencyService(service_id="scitt.aeib.local", ts_privkey=ts_priv)

    # Signed by wrong issuer key
    wrong_signer = RFC9052CoseSigner(private_key=wrong_priv, key_id="issuer:wrong")
    bad_stmt_cbor, _ = wrong_signer.sign_receipt({"caid": "00" * 32, "disposition": "ALLOW"})

    with pytest.raises(ValueError, match="SCITT Registration Policy rejected Signed Statement"):
        ts.register_signed_statement(bad_stmt_cbor, issuer_pubkey=issuer_pub)

    # Tampered signature byte in valid statement
    valid_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:valid")
    valid_stmt_cbor, _ = valid_signer.sign_receipt({"caid": "11" * 32, "disposition": "ALLOW"})
    tampered_cbor = bytearray(valid_stmt_cbor)
    tampered_cbor[-1] ^= 0xFF

    with pytest.raises(ValueError, match="SCITT Registration Policy rejected Signed Statement"):
        ts.register_signed_statement(bytes(tampered_cbor), issuer_pubkey=issuer_pub)

    assert ts.tree.tree_size == 0


def test_scitt_falsification_tampered_audit_path_rejected_offline() -> None:
    """
    Falsification 2: Tampered Merkle audit_path sibling hash must be rejected offline
    even if re-signed or modified in the receipt/bundle.
    """
    issuer_priv, issuer_pub = _derive_keypair("phase4-scitt-issuer-audit")
    ts_priv, ts_pub = _derive_keypair("phase4-scitt-ts-audit")

    issuer_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:audit")
    ts = SCITTTransparencyService(service_id="scitt.aeib.local", ts_privkey=ts_priv)

    for i in range(4):
        stmt, _ = issuer_signer.sign_receipt({"seq": i, "disposition": "ALLOW"})
        bundle = ts.register_signed_statement(stmt, issuer_pubkey=issuer_pub)

    # Case A: Tamper with bundle["inclusion_proof"]["audit_path"][0] directly
    tampered_bundle = copy.deepcopy(bundle)
    orig_sibling = bytes.fromhex(tampered_bundle["inclusion_proof"]["audit_path"][0])
    flipped_sibling = (int.from_bytes(orig_sibling, "big") ^ 1).to_bytes(32, "big").hex()
    tampered_bundle["inclusion_proof"]["audit_path"][0] = flipped_sibling

    res_a = verify_transparent_statement(tampered_bundle, issuer_pubkey=issuer_pub, ts_pubkey=ts_pub)
    assert res_a["valid"] is False

    # Case B: Re-sign receipt with corrupted sibling hash so TS signature passes but Merkle math fails
    corrupted_claims = {
        "service_id": ts.service_id,
        "leaf_index": tampered_bundle["inclusion_proof"]["leaf_index"],
        "tree_size": tampered_bundle["inclusion_proof"]["tree_size"],
        "audit_path": tampered_bundle["inclusion_proof"]["audit_path"],
        "merkle_root_hex": tampered_bundle["merkle_root_hex"],
        "statement_sha256": hashlib.sha256(
            base64.b64decode(tampered_bundle["signed_statement_b64"])
        ).hexdigest(),
    }
    ts_signer = RFC9052CoseSigner(private_key=ts_priv, key_id=ts.ts_kid)
    forged_receipt = ts_signer.sign(encode_jcs(corrupted_claims))
    tampered_bundle["cose_receipt_b64"] = base64.b64encode(forged_receipt).decode("ascii")

    res_b = verify_transparent_statement(tampered_bundle, issuer_pubkey=issuer_pub, ts_pubkey=ts_pub)
    assert res_b["valid"] is False
    assert "Merkle inclusion proof verification failed" in res_b["error"]


def test_scitt_falsification_tampered_leaf_index_rejected_offline() -> None:
    """
    Falsification 3: Tampered leaf_index must be rejected offline.
    """
    issuer_priv, issuer_pub = _derive_keypair("phase4-scitt-issuer-leafidx")
    ts_priv, ts_pub = _derive_keypair("phase4-scitt-ts-leafidx")

    issuer_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:leafidx")
    ts = SCITTTransparencyService(service_id="scitt.aeib.local", ts_privkey=ts_priv)

    bundles = []
    for i in range(4):
        stmt, _ = issuer_signer.sign_receipt({"seq": i, "disposition": "ALLOW"})
        bundles.append(ts.register_signed_statement(stmt, issuer_pubkey=issuer_pub))

    target = copy.deepcopy(bundles[3])
    # Flip leaf_index from 3 to 2 and re-sign receipt with TS key to test Merkle path rejection
    target["inclusion_proof"]["leaf_index"] = 2
    corrupted_claims = {
        "service_id": ts.service_id,
        "leaf_index": 2,
        "tree_size": target["inclusion_proof"]["tree_size"],
        "audit_path": target["inclusion_proof"]["audit_path"],
        "merkle_root_hex": target["merkle_root_hex"],
        "statement_sha256": hashlib.sha256(
            base64.b64decode(target["signed_statement_b64"])
        ).hexdigest(),
    }
    ts_signer = RFC9052CoseSigner(private_key=ts_priv, key_id=ts.ts_kid)
    target["cose_receipt_b64"] = base64.b64encode(
        ts_signer.sign(encode_jcs(corrupted_claims))
    ).decode("ascii")

    res = verify_transparent_statement(target, issuer_pubkey=issuer_pub, ts_pubkey=ts_pub)
    assert res["valid"] is False
    assert "Merkle inclusion proof verification failed" in res["error"]


def test_scitt_falsification_wrong_ts_pubkey_rejected_offline() -> None:
    """
    Falsification 4: Wrong Transparency Service public key must be rejected offline.
    """
    issuer_priv, issuer_pub = _derive_keypair("phase4-scitt-issuer-wrongts")
    ts_priv, _ = _derive_keypair("phase4-scitt-ts-real")
    _, wrong_ts_pub = _derive_keypair("phase4-scitt-ts-wrong")

    issuer_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:wrongts")
    ts = SCITTTransparencyService(service_id="scitt.aeib.local", ts_privkey=ts_priv)

    stmt, _ = issuer_signer.sign_receipt({"seq": 0, "disposition": "ALLOW"})
    bundle = ts.register_signed_statement(stmt, issuer_pubkey=issuer_pub)

    res = verify_transparent_statement(bundle, issuer_pubkey=issuer_pub, ts_pubkey=wrong_ts_pub)
    assert res["valid"] is False
    assert "Transparency Service COSE Receipt verification failed" in res["error"]


def test_scitt_falsification_tampered_signed_statement_after_receipt_issuance() -> None:
    """
    Falsification 5: Tampered Signed Statement bytes after receipt issuance (even if validly
    signed by the same issuer) must be rejected offline by statement_sha256 and Merkle binding.
    """
    issuer_priv, issuer_pub = _derive_keypair("phase4-scitt-issuer-post")
    ts_priv, ts_pub = _derive_keypair("phase4-scitt-ts-post")

    issuer_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:post")
    ts = SCITTTransparencyService(service_id="scitt.aeib.local", ts_privkey=ts_priv)

    stmt_original, _ = issuer_signer.sign_receipt({"seq": 0, "disposition": "ALLOW"})
    stmt_substituted, _ = issuer_signer.sign_receipt({"seq": 0, "disposition": "DENY"})

    bundle = ts.register_signed_statement(stmt_original, issuer_pubkey=issuer_pub)
    tampered_bundle = copy.deepcopy(bundle)
    tampered_bundle["signed_statement_b64"] = base64.b64encode(stmt_substituted).decode("ascii")

    res = verify_transparent_statement(tampered_bundle, issuer_pubkey=issuer_pub, ts_pubkey=ts_pub)
    assert res["valid"] is False
    assert "Statement SHA-256 mismatch" in res["error"]


def test_cli_self_test_and_envelope_verification_subprocess(tmp_path: Path) -> None:
    """
    Tests CLI execution of `tools/verify_cose_scitt_receipts.py` via subprocess.run
    for both `--self-test` and `--envelope` / `--public-key` / `--aad`.
    """
    cli_script = REPO_ROOT / "tools" / "verify_cose_scitt_receipts.py"

    # 1. --self-test mode
    self_test_proc = subprocess.run(
        [sys.executable, str(cli_script), "--self-test"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert self_test_proc.returncode == 0, self_test_proc.stderr
    assert "Self-Test PASSED" in self_test_proc.stdout

    # 2. --envelope / --public-key / --aad mode
    priv, pub = _derive_keypair("phase4-cli-subprocess-key")
    signer = RFC9052CoseSigner(private_key=priv, key_id="cli-test-key")
    aad = b"cli-external-aad"
    envelope_bytes, caid = signer.sign_receipt(
        {"caid": "ab" * 32, "disposition": "ALLOW"},
        external_aad=aad,
    )

    envelope_file = tmp_path / "sample_receipt.cose"
    envelope_file.write_bytes(envelope_bytes)

    pem_bytes = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pubkey_file = tmp_path / "issuer_pub.pem"
    pubkey_file.write_bytes(pem_bytes)

    # Also verify load_public_key helper directly
    loaded_pub = load_public_key(str(pubkey_file))
    assert (
        loaded_pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        == pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )

    env_proc = subprocess.run(
        [
            sys.executable,
            str(cli_script),
            "--envelope",
            str(envelope_file),
            "--public-key",
            str(pubkey_file),
            "--aad",
            aad.hex(),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert env_proc.returncode == 0, env_proc.stderr
    assert "Receipt Verification SUCCESSFUL" in env_proc.stdout
    assert "cli-test-key" in env_proc.stdout
