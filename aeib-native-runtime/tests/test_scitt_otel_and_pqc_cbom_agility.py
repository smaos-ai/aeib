#!/usr/bin/env python3
"""
tests/test_scitt_otel_and_pqc_cbom_agility.py — Verification Suite for Directive 2
(IETF SCITT RFC 9942 / RFC 9943 + RFC 9052 COSE_Sign1 + OpenTelemetry GenAI Interop)
and Directive 4 (CNSA 2.0 / RFC 9964 COSE ML-DSA + CycloneDX 1.6 CBOM).

Evaluated under the stated model using real Ed25519 signatures, real SHA-256 / SHAKE-256
digests, real RFC 8785 JCS canonicalization, and real RFC 9162 binary Merkle trees.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.cbom_and_scitt_otel_exporter import (
    COSE_ALG_COMPOSITE_ED25519_ML_DSA_65,
    COSE_ALG_EDDSA,
    COSE_ALG_ESP256,
    COSE_ALG_ML_DSA_44,
    COSE_ALG_ML_DSA_65,
    COSE_ALG_ML_DSA_87,
    COSE_HEADER_RECEIPTS,
    COSE_HEADER_VDP,
    COSE_HEADER_VDS,
    HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG,
    RFC8949CBOR,
    VDP_INCLUSION_PATH,
    VDP_LEAF_INDEX,
    VDP_TREE_SIZE,
    VDS_RFC9162_SHA256,
    COSEAlgorithmRegistry,
    CycloneDX16CBOMGenerator,
    SCITTAnchoredOTelGate,
)
from src.jcs_canonicalizer import encode_jcs

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_CBOM_PATH = REPO_ROOT / "evidence" / "cbom.json"


# ============================================================================
# 1. CycloneDX 1.6 CBOM Generation & Ed25519 JCS Attestation Tests
# ============================================================================


def test_cyclonedx_16_cbom_file_exists_and_verifies_ed25519_jcs() -> None:
    """
    Verifies that `evidence/cbom.json` exists, conforms to CycloneDX 1.6 schema,
    lists `cryptographic-asset` components with `cryptoProperties` for Ed25519 (-8),
    SHA-256, RFC-8785-JCS, RFC-9162-Merkle-Tree, and ML-DSA-65 (-49), and passes
    Ed25519 cryptographic signature verification over RFC 8785 `encode_jcs`.
    """
    generator = CycloneDX16CBOMGenerator()
    written_path = generator.write_cbom_file(EVIDENCE_CBOM_PATH)
    assert written_path.is_file(), "evidence/cbom.json must exist on disk"

    cbom_data = json.loads(written_path.read_text(encoding="utf-8"))
    assert cbom_data["bomFormat"] == "CycloneDX"
    assert cbom_data["specVersion"] == "1.6"
    assert cbom_data["serialNumber"].startswith("urn:uuid:")

    components_by_name = {c["name"]: c for c in cbom_data["components"]}
    for required_name in (
        "Ed25519",
        "SHA-256",
        "SHAKE-256",
        "RFC-8785-JCS",
        "RFC-9162-Merkle-Tree",
        "ML-DSA-65",
        "Composite-ML-DSA-65-Ed25519",
    ):
        assert required_name in components_by_name, f"Missing CBOM asset: {required_name}"
        comp = components_by_name[required_name]
        assert comp["type"] == "cryptographic-asset"
        assert "cryptoProperties" in comp

    # Check Ed25519 (-8) properties
    ed_props = components_by_name["Ed25519"]["cryptoProperties"]["algorithmProperties"]
    assert ed_props["primitive"] == "signature"
    assert ed_props["coseAlgorithmId"] == COSE_ALG_EDDSA
    assert ed_props["implementationLevel"] == "software"
    assert ed_props["classicalSecurityLevel"] == 128

    # Check SHA-256 properties
    sha_props = components_by_name["SHA-256"]["cryptoProperties"]["algorithmProperties"]
    assert sha_props["primitive"] == "hash"
    assert sha_props["parameterSetIdentifier"] == "256"
    assert sha_props["nistQuantumSecurityCategory"] == 1

    # Check ML-DSA-65 (-49) RFC 9964 / CNSA 2.0 properties
    mldsa_props = components_by_name["ML-DSA-65"]["cryptoProperties"]["algorithmProperties"]
    assert mldsa_props["primitive"] == "signature"
    assert mldsa_props["parameterSetIdentifier"] == "65"
    assert mldsa_props["coseAlgorithmId"] == COSE_ALG_ML_DSA_65
    assert mldsa_props["classicalSecurityLevel"] == 192
    assert mldsa_props["nistQuantumSecurityCategory"] == 3
    assert mldsa_props["implementationLevel"] in ("software", "scaffold")

    # Verify Ed25519 signature over RFC 8785 JCS canonical CBOM payload
    verify_res = CycloneDX16CBOMGenerator.verify_cbom_manifest(
        cbom_data,
        expected_public_key=generator.public_key,
    )
    assert verify_res["valid"] is True, f"CBOM verification failed: {verify_res.get('error')}"
    assert verify_res["component_count"] == len(cbom_data["components"])

    # Direct check of encode_jcs digest against attestation_signature
    unsigned_cbom = {k: v for k, v in cbom_data.items() if k != "attestation_signature"}
    expected_jcs_sha256 = hashlib.sha256(encode_jcs(unsigned_cbom)).hexdigest()
    assert cbom_data["attestation_signature"]["payload_jcs_sha256"] == expected_jcs_sha256


def test_cyclonedx_16_cbom_tamper_fails_closed() -> None:
    """
    Verifies that mutating any field in the CycloneDX 1.6 CBOM invalidates the
    RFC 8785 JCS digest and Ed25519 signature.
    """
    generator = CycloneDX16CBOMGenerator()
    cbom_data = generator.build_cbom_dict()

    tampered = copy.deepcopy(cbom_data)
    tampered["components"][0]["cryptoProperties"]["algorithmProperties"][
        "classicalSecurityLevel"
    ] = 64
    res = CycloneDX16CBOMGenerator.verify_cbom_manifest(tampered, generator.public_key)
    assert res["valid"] is False
    assert "mismatch" in (res["error"] or "").lower()

    # Recompute payload_jcs_sha256 without a valid Ed25519 signature
    unsigned_tampered = {k: v for k, v in tampered.items() if k != "attestation_signature"}
    tampered["attestation_signature"]["payload_jcs_sha256"] = hashlib.sha256(
        encode_jcs(unsigned_tampered)
    ).hexdigest()
    res_sig = CycloneDX16CBOMGenerator.verify_cbom_manifest(tampered, generator.public_key)
    assert res_sig["valid"] is False
    assert "invalid ed25519 signature" in (res_sig["error"] or "").lower()


# ============================================================================
# 2. SCITT-Anchored OpenTelemetry GenAI Span Export & Offline Auditor Tests
# ============================================================================


def test_scitt_anchored_otel_gate_multi_operation_offline_verification() -> None:
    """
    Executes 4 tool operations across Station 1 and Station 3, verifying that:
      - Each operation is signed as a binary Tag 18 COSE_Sign1 envelope (alg = -8).
      - The SCITT Transparency Service registers it in the RFC 9162 SHA-256 Merkle tree
        and embeds a binary COSE Receipt into Unprotected Header 394 with Protected
        Header 395 = 1 (VDS_RFC9162_SHA256) and Unprotected Header 396 (VDP inclusion proof).
      - An external auditor (`iFixAi`) holding ONLY the OpenTelemetry GenAI `execute_tool`
        span and the pinned SCITT Merkle root (`expected_merkle_root_hex`) verifies the
        statement offline without reading any host-local `ledger.jsonl`.
    """
    issuer_priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"test-aeib-station-issuer-key").digest()
    )
    ts_priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"test-aeib-scitt-ts-key").digest()
    )

    gate = SCITTAnchoredOTelGate(
        issuer_privkey=issuer_priv,
        ts_privkey=ts_priv,
        issuer_kid="aeib-station:node-alpha",
        service_id="scitt.sovereign-nexus.local",
    )

    operations = [
        ("scada.breaker.trip", "call-001", "station_1_pre_exec", {"breaker_id": "B-101", "cycle": 1}),
        ("scada.breaker.trip", "call-001", "station_3_post_exec", {"breaker_id": "B-101", "settled": True}),
        ("grid.relay.reclose", "call-002", "station_1_pre_exec", {"relay_id": "R-204", "cycle": 2}),
        ("grid.relay.reclose", "call-002", "station_3_post_exec", {"relay_id": "R-204", "settled": True}),
    ]

    for expected_idx, (tool_name, call_id, station_id, claims) in enumerate(operations):
        receipt_payload = {
            "station": station_id,
            "tool_name": tool_name,
            "tool_call_id": call_id,
            "claims": claims,
        }
        otel_span = gate.record_tool_execution_span(
            tool_name=tool_name,
            tool_call_id=call_id,
            receipt_payload=receipt_payload,
            station_id=station_id,
        )

        # Pin the SCITT Merkle root published at registration time
        pinned_root_hex = gate.current_merkle_root_hex
        attrs = otel_span["attributes"]

        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == tool_name
        assert attrs["aeib.crypto.cose_alg"] == COSE_ALG_EDDSA
        assert attrs["aeib.scitt.leaf_index"] == expected_idx
        assert attrs["aeib.scitt.tree_size"] == expected_idx + 1
        assert attrs["aeib.scitt.merkle_root_sha256"] == pinned_root_hex

        # Inspect raw CBOR headers 394, 395, 396 inside the Transparent Statement
        transparent_cbor = base64.b64decode(attrs["aeib.scitt.transparent_statement_b64"])
        outer_tag = RFC8949CBOR.decode(transparent_cbor)
        _, outer_unprotected, _, _ = outer_tag.value
        assert COSE_HEADER_RECEIPTS in outer_unprotected
        embedded_receipt_cbor = outer_unprotected[COSE_HEADER_RECEIPTS][0]
        rcpt_tag = RFC8949CBOR.decode(embedded_receipt_cbor)
        rcpt_prot_bytes, rcpt_unprot, _, _ = rcpt_tag.value
        rcpt_prot = RFC8949CBOR.decode(rcpt_prot_bytes)
        assert rcpt_prot[COSE_HEADER_VDS] == VDS_RFC9162_SHA256
        assert rcpt_unprot[COSE_HEADER_VDP][VDP_TREE_SIZE] == expected_idx + 1
        assert rcpt_unprot[COSE_HEADER_VDP][VDP_LEAF_INDEX] == expected_idx
        assert isinstance(rcpt_unprot[COSE_HEADER_VDP][VDP_INCLUSION_PATH], list)

        # External auditor (`iFixAi`) verifies ONLY the span + pinned SCITT root
        audit_res = SCITTAnchoredOTelGate.verify_otel_span_against_external_scitt_root(
            otel_span=otel_span,
            expected_merkle_root_hex=pinned_root_hex,
            issuer_pubkey=issuer_priv.public_key(),
            ts_pubkey=ts_priv.public_key(),
        )
        assert audit_res["valid"] is True, f"Offline SCITT span audit failed: {audit_res.get('error')}"
        assert audit_res["leaf_index"] == expected_idx
        assert audit_res["tree_size"] == expected_idx + 1
        assert audit_res["merkle_root_sha256"] == pinned_root_hex
        assert audit_res["receipt_payload"] == receipt_payload


def test_scitt_anchored_otel_span_tampering_fails_closed() -> None:
    """
    Verifies that tampering with the span's `merkle_root_sha256`, `transparent_statement_b64`,
    `leaf_index`, or verifying against a mismatched external SCITT root fails closed.
    """
    issuer_priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"tamper-test-issuer-key").digest()
    )
    ts_priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"tamper-test-ts-key").digest()
    )
    wrong_priv = ed25519.Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"tamper-test-wrong-key").digest()
    )

    gate = SCITTAnchoredOTelGate(issuer_privkey=issuer_priv, ts_privkey=ts_priv)
    gate.record_tool_execution_span(
        tool_name="db.transfer",
        tool_call_id="tx-100",
        receipt_payload={"seq": 1, "amount": 500},
    )
    span2 = gate.record_tool_execution_span(
        tool_name="db.transfer",
        tool_call_id="tx-101",
        receipt_payload={"seq": 2, "amount": 900},
    )
    pinned_root = gate.current_merkle_root_hex

    # Case 1: Mismatched external SCITT Merkle root
    wrong_root = hashlib.sha256(b"forged-merkle-root").hexdigest()
    res_wrong_root = SCITTAnchoredOTelGate.verify_otel_span_against_external_scitt_root(
        otel_span=span2,
        expected_merkle_root_hex=wrong_root,
        issuer_pubkey=issuer_priv.public_key(),
        ts_pubkey=ts_priv.public_key(),
    )
    assert res_wrong_root["valid"] is False

    # Case 2: Byte-flip inside `transparent_statement_b64`
    tampered_stmt_span = copy.deepcopy(span2)
    raw_cbor = bytearray(
        base64.b64decode(tampered_stmt_span["attributes"]["aeib.scitt.transparent_statement_b64"])
    )
    raw_cbor[-5] ^= 0xFF
    tampered_b64 = base64.b64encode(bytes(raw_cbor)).decode("ascii")
    tampered_b64url = base64.urlsafe_b64encode(bytes(raw_cbor)).rstrip(b"=").decode("ascii")
    tampered_stmt_span["attributes"]["aeib.scitt.transparent_statement_b64"] = tampered_b64
    tampered_stmt_span["attributes"]["aeib.scitt.receipt_cose_b64url"] = tampered_b64url

    res_tampered_cbor = SCITTAnchoredOTelGate.verify_otel_span_against_external_scitt_root(
        otel_span=tampered_stmt_span,
        expected_merkle_root_hex=pinned_root,
        issuer_pubkey=issuer_priv.public_key(),
        ts_pubkey=ts_priv.public_key(),
    )
    assert res_tampered_cbor["valid"] is False

    # Case 3: Tampered leaf_index in span attributes
    tampered_leaf_span = copy.deepcopy(span2)
    tampered_leaf_span["attributes"]["aeib.scitt.leaf_index"] = 0
    res_tampered_leaf = SCITTAnchoredOTelGate.verify_otel_span_against_external_scitt_root(
        otel_span=tampered_leaf_span,
        expected_merkle_root_hex=pinned_root,
        issuer_pubkey=issuer_priv.public_key(),
        ts_pubkey=ts_priv.public_key(),
    )
    assert res_tampered_leaf["valid"] is False

    # Case 4: Wrong Transparency Service public key
    res_wrong_ts_key = SCITTAnchoredOTelGate.verify_otel_span_against_external_scitt_root(
        otel_span=span2,
        expected_merkle_root_hex=pinned_root,
        issuer_pubkey=issuer_priv.public_key(),
        ts_pubkey=wrong_priv.public_key(),
    )
    assert res_wrong_ts_key["valid"] is False


# ============================================================================
# 3. COSEAlgorithmRegistry & RFC 9964 ML-DSA / Downgrade Rejection Tests
# ============================================================================


def test_cose_algorithm_registry_negotiation_and_downgrade_halt() -> None:
    """
    Verifies official IANA COSE Algorithm IDs:
      - EdDSA = -8
      - ESP256 = -9
      - ML-DSA-44 = -48, ML-DSA-65 = -49, ML-DSA-87 = -50 (RFC 9964)
      - Composite Ed25519 + ML-DSA-65 = -65537
    and confirms fail-closed rejection (`HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG`)
    for unsupported, downgraded, or unactivated algorithms.
    """
    assert COSEAlgorithmRegistry.COSE_ALG_EDDSA == -8
    assert COSEAlgorithmRegistry.COSE_ALG_ESP256 == -9
    assert COSEAlgorithmRegistry.COSE_ALG_ML_DSA_44 == -48
    assert COSEAlgorithmRegistry.COSE_ALG_ML_DSA_65 == -49
    assert COSEAlgorithmRegistry.COSE_ALG_ML_DSA_87 == -50
    assert COSEAlgorithmRegistry.COSE_ALG_COMPOSITE_ED25519_ML_DSA_65 == -65537

    # Active Ed25519 (-8) negotiation succeeds
    ed_desc = COSEAlgorithmRegistry.negotiate_cose_alg(COSE_ALG_EDDSA, require_active_provider=True)
    assert ed_desc.cose_alg_id == -8
    assert ed_desc.parameter_set == "Ed25519"

    # Target PQC profile lookup succeeds when allow_target_pqc_profile=True
    mldsa65_desc = COSEAlgorithmRegistry.negotiate_cose_alg(
        COSE_ALG_ML_DSA_65,
        require_active_provider=True,
        allow_target_pqc_profile=True,
    )
    assert mldsa65_desc.cose_alg_id == -49
    assert mldsa65_desc.nist_quantum_category == 3

    # Downgraded or unknown algorithm IDs must raise HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG
    for invalid_alg in (0, -7, -9, -257, -999999, "EdDSA", None, True):
        with pytest.raises(ValueError, match=HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG):
            COSEAlgorithmRegistry.negotiate_cose_alg(invalid_alg, require_active_provider=True)

    # If no runtime C-lattice provider is installed, requesting live ML-DSA signing halts fail-closed
    runtime_mldsa = COSEAlgorithmRegistry.detect_runtime_mldsa_provider()
    if not runtime_mldsa["available"]:
        for pqc_alg in (
            COSE_ALG_ML_DSA_44,
            COSE_ALG_ML_DSA_65,
            COSE_ALG_ML_DSA_87,
            COSE_ALG_COMPOSITE_ED25519_ML_DSA_65,
        ):
            with pytest.raises(ValueError, match=HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG):
                COSEAlgorithmRegistry.negotiate_cose_alg(
                    pqc_alg,
                    require_active_provider=True,
                    allow_target_pqc_profile=False,
                )

    # Verify composite PQ/T SHAKE-256 + SHA-256 transcript commitment
    transcript = COSEAlgorithmRegistry.compute_composite_pq_t_transcript(
        b'["Signature1",h"a10127",h"",h"7b7d"]'
    )
    assert len(bytes.fromhex(transcript["shake256_64b_hex"])) == 64
    assert len(bytes.fromhex(transcript["composite_transcript_sha256"])) == 32
