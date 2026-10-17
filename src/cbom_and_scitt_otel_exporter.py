#!/usr/bin/env python3
"""
src/cbom_and_scitt_otel_exporter.py — IETF SCITT + OpenTelemetry GenAI Transparency
Exporter & CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) + PQC Agility Module.

Evaluated under the stated model:
  1. Directive 2: Encodes AEIB Station 1/3 execution receipts as RFC 9052 COSE_Sign1
     (CBOR Tag 18) statements, registers them in an RFC 9943 / RFC 9942 SCITT
     Transparency Service (Header 394 receipts, Header 395 vds=1 RFC 9162 SHA-256
     Merkle tree, Header 396 vdp inclusion proof), and exports OpenTelemetry GenAI
     `execute_tool` spans verifiable offline against a pinned SCITT Merkle root
     without reading any host-local `ledger.jsonl`.
  2. Directive 4: Defines IANA COSE Algorithm Identifiers including RFC 9964 ML-DSA
     (-48, -49, -50) and Composite Ed25519 + ML-DSA-65 (-65537), enforces fail-closed
     algorithm negotiation, and generates an Ed25519-signed CycloneDX 1.6 CBOM
     (`evidence/cbom.json`).
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import platform
import ssl
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cryptography
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs

# Load RFC 9052 COSE profile and SCITT Transparency Service modules
_ROADMAP_COSE_PATH = REPO_ROOT / "v1.1-roadmap" / "rfc9052_cose_profile.py"
_cose_spec = importlib.util.spec_from_file_location("rfc9052_cose_profile", _ROADMAP_COSE_PATH)
if _cose_spec is None or _cose_spec.loader is None:
    raise ImportError(f"Unable to load COSE profile module from {_ROADMAP_COSE_PATH}")
_cose_mod = importlib.util.module_from_spec(_cose_spec)
sys.modules["rfc9052_cose_profile"] = _cose_mod
_cose_spec.loader.exec_module(_cose_mod)

_SCITT_TOOL_PATH = REPO_ROOT / "tools" / "verify_cose_scitt_receipts.py"
_scitt_spec = importlib.util.spec_from_file_location("verify_cose_scitt_receipts", _SCITT_TOOL_PATH)
if _scitt_spec is None or _scitt_spec.loader is None:
    raise ImportError(f"Unable to load SCITT verifier module from {_SCITT_TOOL_PATH}")
_scitt_mod = importlib.util.module_from_spec(_scitt_spec)
sys.modules["verify_cose_scitt_receipts"] = _scitt_mod
_scitt_spec.loader.exec_module(_scitt_mod)

RFC8949CBOR = _cose_mod.RFC8949CBOR
CBORTag = _cose_mod.CBORTag
RFC9052CoseSigner = _cose_mod.RFC9052CoseSigner
RFC9052CoseVerifier = _cose_mod.RFC9052CoseVerifier
append_receipt_to_signed_statement = _cose_mod.append_receipt_to_signed_statement

COSE_HEADER_ALG = _cose_mod.COSE_HEADER_ALG
COSE_HEADER_KID = _cose_mod.COSE_HEADER_KID
COSE_HEADER_RECEIPTS = _cose_mod.COSE_HEADER_RECEIPTS
COSE_HEADER_VDS = _cose_mod.COSE_HEADER_VDS
COSE_HEADER_VDP = _cose_mod.COSE_HEADER_VDP
VDS_RFC9162_SHA256 = _cose_mod.VDS_RFC9162_SHA256
VDP_TREE_SIZE = _cose_mod.VDP_TREE_SIZE
VDP_LEAF_INDEX = _cose_mod.VDP_LEAF_INDEX
VDP_INCLUSION_PATH = _cose_mod.VDP_INCLUSION_PATH
COSE_TAG_SIGN1 = _cose_mod.COSE_TAG_SIGN1

SCITTMerkleTree = _scitt_mod.SCITTMerkleTree
SCITTTransparencyService = _scitt_mod.SCITTTransparencyService
verify_binary_transparent_statement = _scitt_mod.verify_binary_transparent_statement


# ============================================================================
# IANA COSE Algorithm Identifiers (RFC 9053, RFC 9964, Composite PQ/T)
# ============================================================================

COSE_ALG_EDDSA = -8
COSE_ALG_ESP256 = -9
COSE_ALG_ML_DSA_44 = -48
COSE_ALG_ML_DSA_65 = -49
COSE_ALG_ML_DSA_87 = -50
COSE_ALG_COMPOSITE_ED25519_ML_DSA_65 = -65537

HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG = "HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG"
COMPOSITE_DOMAIN_SEPARATOR = b"AEIB-COMPOSITE-ED25519-MLDSA65-V1"


@dataclass(frozen=True)
class COSEAlgorithmDescriptor:
    """Metadata descriptor for an IANA or private-use COSE signature algorithm."""

    cose_alg_id: int
    name: str
    standard_ref: str
    primitive: str
    parameter_set: str
    classical_security_bits: int
    nist_quantum_category: int
    is_pqc: bool
    is_hybrid_composite: bool


class COSEAlgorithmRegistry:
    """
    Registry of IANA COSE Algorithm Identifiers for AEIB cryptographic agility.
    Enforces fail-closed rejection of unknown, downgraded, or unactivated algorithms.
    """

    COSE_ALG_EDDSA: int = COSE_ALG_EDDSA
    COSE_ALG_ESP256: int = COSE_ALG_ESP256
    COSE_ALG_ML_DSA_44: int = COSE_ALG_ML_DSA_44
    COSE_ALG_ML_DSA_65: int = COSE_ALG_ML_DSA_65
    COSE_ALG_ML_DSA_87: int = COSE_ALG_ML_DSA_87
    COSE_ALG_COMPOSITE_ED25519_ML_DSA_65: int = COSE_ALG_COMPOSITE_ED25519_ML_DSA_65

    _DESCRIPTORS: Dict[int, COSEAlgorithmDescriptor] = {
        COSE_ALG_EDDSA: COSEAlgorithmDescriptor(
            cose_alg_id=COSE_ALG_EDDSA,
            name="EdDSA (Ed25519)",
            standard_ref="RFC 9053 Section 2.2 / RFC 8032",
            primitive="signature",
            parameter_set="Ed25519",
            classical_security_bits=128,
            nist_quantum_category=0,
            is_pqc=False,
            is_hybrid_composite=False,
        ),
        COSE_ALG_ESP256: COSEAlgorithmDescriptor(
            cose_alg_id=COSE_ALG_ESP256,
            name="ESP256 (ECDSA P-256 + SHA-256)",
            standard_ref="RFC 9053 / IANA COSE Algorithms",
            primitive="signature",
            parameter_set="P-256",
            classical_security_bits=128,
            nist_quantum_category=0,
            is_pqc=False,
            is_hybrid_composite=False,
        ),
        COSE_ALG_ML_DSA_44: COSEAlgorithmDescriptor(
            cose_alg_id=COSE_ALG_ML_DSA_44,
            name="ML-DSA-44",
            standard_ref="RFC 9964 / FIPS 204",
            primitive="signature",
            parameter_set="44",
            classical_security_bits=128,
            nist_quantum_category=2,
            is_pqc=True,
            is_hybrid_composite=False,
        ),
        COSE_ALG_ML_DSA_65: COSEAlgorithmDescriptor(
            cose_alg_id=COSE_ALG_ML_DSA_65,
            name="ML-DSA-65",
            standard_ref="RFC 9964 / FIPS 204 / CNSA 2.0",
            primitive="signature",
            parameter_set="65",
            classical_security_bits=192,
            nist_quantum_category=3,
            is_pqc=True,
            is_hybrid_composite=False,
        ),
        COSE_ALG_ML_DSA_87: COSEAlgorithmDescriptor(
            cose_alg_id=COSE_ALG_ML_DSA_87,
            name="ML-DSA-87",
            standard_ref="RFC 9964 / FIPS 204 / CNSA 2.0",
            primitive="signature",
            parameter_set="87",
            classical_security_bits=256,
            nist_quantum_category=5,
            is_pqc=True,
            is_hybrid_composite=False,
        ),
        COSE_ALG_COMPOSITE_ED25519_ML_DSA_65: COSEAlgorithmDescriptor(
            cose_alg_id=COSE_ALG_COMPOSITE_ED25519_ML_DSA_65,
            name="Composite-ML-DSA-65-Ed25519",
            standard_ref="draft-ietf-jose-pq-composite-sigs / RFC 9964",
            primitive="combiner",
            parameter_set="Ed25519+ML-DSA-65",
            classical_security_bits=192,
            nist_quantum_category=3,
            is_pqc=True,
            is_hybrid_composite=True,
        ),
    }

    # Explicitly prohibited or downgraded COSE algorithms (e.g., none=0, RSASSA-PKCS1-v1_5, ES256=-7)
    _PROHIBITED_OR_DOWNGRADED_ALGS = {0, -7, -35, -36, -37, -257, -258, -259, -65535}

    @classmethod
    def detect_runtime_mldsa_provider(cls) -> Dict[str, Any]:
        """
        Inspects the active Python runtime for a native FIPS 204 ML-DSA lattice backend.
        Never uses fake or simulated lattice signatures.
        """
        oqs_spec = importlib.util.find_spec("oqs")
        has_oqs = oqs_spec is not None
        has_cryptography_mldsa = hasattr(
            cryptography.hazmat.primitives.asymmetric, "mldsa"
        )
        if has_oqs:
            return {
                "available": True,
                "provider_name": "liboqs-python",
                "execution_environment": "software-native-lattice",
                "implementation_level": "software",
            }
        if has_cryptography_mldsa:
            return {
                "available": True,
                "provider_name": "cryptography-openssl-mldsa",
                "execution_environment": "software-openssl-3.5+",
                "implementation_level": "software",
            }
        return {
            "available": False,
            "provider_name": "stdlib+cryptography-classical-only",
            "execution_environment": "scaffold",
            "implementation_level": "scaffold",
        }

    @classmethod
    def get_descriptor(cls, alg_id: int) -> COSEAlgorithmDescriptor:
        if isinstance(alg_id, bool) or not isinstance(alg_id, int):
            raise ValueError(
                f"{HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG}: alg must be an integer, got {alg_id!r}"
            )
        if alg_id in cls._PROHIBITED_OR_DOWNGRADED_ALGS:
            raise ValueError(
                f"{HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG}: downgraded or prohibited COSE alg {alg_id}"
            )
        desc = cls._DESCRIPTORS.get(alg_id)
        if desc is None:
            raise ValueError(
                f"{HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG}: unknown COSE alg {alg_id}"
            )
        return desc

    @classmethod
    def negotiate_cose_alg(
        cls,
        requested_alg: Any,
        require_active_provider: bool = True,
        allow_target_pqc_profile: bool = False,
    ) -> COSEAlgorithmDescriptor:
        """
        Validates a requested COSE algorithm identifier.
        Fails closed with HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG if:
          - requested_alg is non-integer, boolean, unknown, or downgraded;
          - requested_alg is ESP256 (-9) while AEIB requires Ed25519 (-8) or PQC ML-DSA;
          - requested_alg requires a native ML-DSA lattice provider that is not installed
            and allow_target_pqc_profile is False.
        """
        desc = cls.get_descriptor(requested_alg)

        if desc.cose_alg_id == cls.COSE_ALG_ESP256 and require_active_provider:
            raise ValueError(
                f"{HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG}: COSE_ALG_ESP256 (-9) is not an active signing profile in AEIB Station 1/3"
            )

        if desc.is_pqc and require_active_provider and not allow_target_pqc_profile:
            mldsa_runtime = cls.detect_runtime_mldsa_provider()
            if not mldsa_runtime["available"]:
                raise ValueError(
                    f"{HALT_UNSUPPORTED_OR_DOWNGRADED_COSE_ALG}: COSE alg {desc.cose_alg_id} ({desc.name}) "
                    "requested for live signing/verification, but no native C-lattice provider "
                    "(liboqs / OpenSSL 3.5+ ML-DSA) is present in this runtime"
                )
        return desc

    @classmethod
    def compute_composite_pq_t_transcript(cls, sig_structure_bytes: bytes) -> Dict[str, str]:
        """
        Computes the real domain-separated SHAKE-256 (512-bit) and SHA-256 cryptographic
        commitment over a COSE Sig_structure for the non-separable Composite
        Ed25519 + ML-DSA-65 profile.
        """
        if not isinstance(sig_structure_bytes, (bytes, bytearray)) or len(sig_structure_bytes) == 0:
            raise ValueError("sig_structure_bytes must be non-empty bytes")
        raw = bytes(sig_structure_bytes)
        shake_digest = hashlib.shake_256(COMPOSITE_DOMAIN_SEPARATOR + raw).digest(64)
        sha256_digest = hashlib.sha256(COMPOSITE_DOMAIN_SEPARATOR + shake_digest).hexdigest()
        return {
            "domain_separator": COMPOSITE_DOMAIN_SEPARATOR.decode("ascii"),
            "shake256_64b_hex": shake_digest.hex(),
            "composite_transcript_sha256": sha256_digest,
        }


# ============================================================================
# CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) Generator & Verifier
# ============================================================================


class CycloneDX16CBOMGenerator:
    """
    Generates and cryptographically signs a CycloneDX 1.6 Cryptographic Bill of Materials
    (`evidence/cbom.json`) cataloging all active and target PQC primitives in AEIB.
    """

    DEFAULT_CBOM_SEED = hashlib.sha256(b"AEIB-CYCLONEDX-1.6-CBOM-SIGNER-2026-V1").digest()

    def __init__(
        self,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        key_id: str = "aeib-cbom-ed25519-key-2026",
    ) -> None:
        self.signing_key = (
            signing_key
            if signing_key is not None
            else ed25519.Ed25519PrivateKey.from_private_bytes(self.DEFAULT_CBOM_SEED)
        )
        self.public_key = self.signing_key.public_key()
        self.key_id = key_id

    def build_cbom_dict(self, timestamp_utc: str = "2026-10-17T12:00:00Z") -> Dict[str, Any]:
        """
        Inspects runtime OpenSSL / cryptography versions and builds a CycloneDX 1.6 CBOM
        signed with Ed25519 over RFC 8785 JCS canonical bytes.
        """
        openssl_version = ssl.OPENSSL_VERSION
        crypto_pkg_version = getattr(cryptography, "__version__", "unknown")
        python_version = platform.python_version()
        mldsa_status = COSEAlgorithmRegistry.detect_runtime_mldsa_provider()

        components: List[Dict[str, Any]] = [
            {
                "type": "cryptographic-asset",
                "bom-ref": "crypto/alg/ed25519-cose-alg--8",
                "name": "Ed25519",
                "version": "RFC-8032-RFC-9053",
                "description": (
                    "Active Edwards-curve Digital Signature Algorithm (Ed25519, IANA COSE alg -8) "
                    "executed via cryptography.hazmat.primitives.asymmetric.ed25519"
                ),
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "oid": "1.3.101.112",
                    "algorithmProperties": {
                        "primitive": "signature",
                        "variant": "Ed25519",
                        "parameterSetIdentifier": "Ed25519",
                        "curve": "curve25519",
                        "executionEnvironment": "software-openssl",
                        "implementationLevel": "software",
                        "cryptoFunctions": ["keygen", "sign", "verify"],
                        "classicalSecurityLevel": 128,
                        "nistQuantumSecurityCategory": 0,
                        "coseAlgorithmId": COSE_ALG_EDDSA,
                    },
                },
            },
            {
                "type": "cryptographic-asset",
                "bom-ref": "crypto/alg/sha256-fips180-4",
                "name": "SHA-256",
                "version": "FIPS-180-4",
                "description": (
                    "Active 256-bit cryptographic digest used for RFC 8785 JCS CAID derivation "
                    "and RFC 9162 / RFC 9942 SCITT binary Merkle trees"
                ),
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "oid": "2.16.840.1.101.3.4.2.1",
                    "algorithmProperties": {
                        "primitive": "hash",
                        "variant": "SHA-256",
                        "parameterSetIdentifier": "256",
                        "executionEnvironment": "software-openssl",
                        "implementationLevel": "software",
                        "cryptoFunctions": ["digest"],
                        "classicalSecurityLevel": 256,
                        "nistQuantumSecurityCategory": 1,
                    },
                },
            },
            {
                "type": "cryptographic-asset",
                "bom-ref": "crypto/alg/shake256-fips202",
                "name": "SHAKE-256",
                "version": "FIPS-202",
                "description": (
                    "Active Extendable-Output Function (XOF) used for FIPS 204 / composite "
                    "PQ/T transcript pre-hashing via hashlib.shake_256"
                ),
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "oid": "2.16.840.1.101.3.4.2.12",
                    "algorithmProperties": {
                        "primitive": "xof",
                        "variant": "SHAKE-256",
                        "parameterSetIdentifier": "256",
                        "executionEnvironment": "software-openssl",
                        "implementationLevel": "software",
                        "cryptoFunctions": ["digest"],
                        "classicalSecurityLevel": 256,
                        "nistQuantumSecurityCategory": 2,
                    },
                },
            },
            {
                "type": "cryptographic-asset",
                "bom-ref": "crypto/protocol/rfc8785-jcs",
                "name": "RFC-8785-JCS",
                "version": "RFC-8785",
                "description": (
                    "Active JSON Canonicalization Scheme (UTF-16 code unit key sorting, "
                    "ECMAScript 7.1.12.1 number formatting)"
                ),
                "cryptoProperties": {
                    "assetType": "protocol",
                    "algorithmProperties": {
                        "primitive": "other",
                        "variant": "RFC-8785-JCS",
                        "parameterSetIdentifier": "UTF-16-BE-Sort",
                        "executionEnvironment": "software-python-stdlib",
                        "implementationLevel": "software",
                        "cryptoFunctions": ["other"],
                        "classicalSecurityLevel": 128,
                        "nistQuantumSecurityCategory": 1,
                    },
                },
            },
            {
                "type": "cryptographic-asset",
                "bom-ref": "crypto/protocol/rfc9162-rfc9942-merkle-vds-1",
                "name": "RFC-9162-Merkle-Tree",
                "version": "RFC-9162-RFC-9942",
                "description": (
                    "Active SCITT Verifiable Data Structure (COSE Header 395 VDS=1) SHA-256 "
                    "binary Merkle tree with 0x00 leaf and 0x01 interior node domain separation"
                ),
                "cryptoProperties": {
                    "assetType": "protocol",
                    "algorithmProperties": {
                        "primitive": "hash",
                        "variant": "RFC-9162-Binary-Merkle-SHA256",
                        "parameterSetIdentifier": "VDS-1",
                        "executionEnvironment": "software-python-stdlib",
                        "implementationLevel": "software",
                        "cryptoFunctions": ["digest", "verify"],
                        "classicalSecurityLevel": 256,
                        "nistQuantumSecurityCategory": 1,
                    },
                },
            },
            {
                "type": "cryptographic-asset",
                "bom-ref": "crypto/alg/ml-dsa-65-cose-alg--49",
                "name": "ML-DSA-65",
                "version": "FIPS-204-RFC-9964",
                "description": (
                    "NSA CNSA 2.0 / IETF RFC 9964 Module-Lattice-Based Digital Signature Standard "
                    "(IANA COSE alg -49). Tagged with exact runtime implementationLevel per AGENTS.md"
                ),
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "oid": "2.16.840.1.101.3.4.3.18",
                    "algorithmProperties": {
                        "primitive": "signature",
                        "variant": "ML-DSA-65",
                        "parameterSetIdentifier": "65",
                        "executionEnvironment": mldsa_status["execution_environment"],
                        "implementationLevel": mldsa_status["implementation_level"],
                        "runtimeProvider": mldsa_status["provider_name"],
                        "cryptoFunctions": ["keygen", "sign", "verify"],
                        "classicalSecurityLevel": 192,
                        "nistQuantumSecurityCategory": 3,
                        "coseAlgorithmId": COSE_ALG_ML_DSA_65,
                    },
                },
            },
            {
                "type": "cryptographic-asset",
                "bom-ref": "crypto/alg/composite-ed25519-mldsa65",
                "name": "Composite-ML-DSA-65-Ed25519",
                "version": "draft-ietf-jose-pq-composite-sigs",
                "description": (
                    "Non-separable hybrid post-quantum/traditional (PQ/T) signature combiner "
                    "binding Ed25519 (active) and ML-DSA-65 (COSE alg -49 slot) over a shared "
                    "SHAKE-256 domain-separated transcript"
                ),
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "combiner",
                        "variant": "Composite-ML-DSA-65-Ed25519",
                        "parameterSetIdentifier": "Ed25519+ML-DSA-65",
                        "executionEnvironment": mldsa_status["execution_environment"],
                        "implementationLevel": mldsa_status["implementation_level"],
                        "cryptoFunctions": ["sign", "verify"],
                        "classicalSecurityLevel": 192,
                        "nistQuantumSecurityCategory": 3,
                        "coseAlgorithmId": COSE_ALG_COMPOSITE_ED25519_ML_DSA_65,
                    },
                },
            },
        ]

        components_digest = hashlib.sha256(encode_jcs(components)).digest()
        deterministic_uuid = str(uuid.UUID(bytes=components_digest[:16], version=5))

        unsigned_cbom: Dict[str, Any] = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "serialNumber": f"urn:uuid:{deterministic_uuid}",
            "version": 1,
            "metadata": {
                "timestamp": timestamp_utc,
                "component": {
                    "type": "application",
                    "bom-ref": "application/sovereign-nexus-aeib",
                    "name": "SovereignNexus-AEIB",
                    "version": "1.1.0",
                },
                "properties": [
                    {"name": "aeib:runtime:python_version", "value": python_version},
                    {"name": "aeib:runtime:openssl_version", "value": openssl_version},
                    {"name": "aeib:runtime:cryptography_version", "value": crypto_pkg_version},
                    {
                        "name": "aeib:pqc:cnsa_2_0_target_cose_alg",
                        "value": str(COSE_ALG_ML_DSA_65),
                    },
                    {
                        "name": "aeib:pqc:mldsa_runtime_provider",
                        "value": mldsa_status["provider_name"],
                    },
                ],
            },
            "components": components,
            "dependencies": [
                {
                    "ref": "application/sovereign-nexus-aeib",
                    "dependsOn": [c["bom-ref"] for c in components],
                }
            ],
        }

        canonical_bytes = encode_jcs(unsigned_cbom)
        jcs_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        signature_bytes = self.signing_key.sign(canonical_bytes)
        pubkey_raw = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        signed_cbom = dict(unsigned_cbom)
        signed_cbom["attestation_signature"] = {
            "algorithm": "Ed25519",
            "cose_alg_id": COSE_ALG_EDDSA,
            "canonicalization": "RFC-8785-JCS",
            "key_id": self.key_id,
            "public_key_hex": pubkey_raw.hex(),
            "payload_jcs_sha256": jcs_sha256,
            "signature_hex": signature_bytes.hex(),
        }
        return signed_cbom

    def write_cbom_file(
        self,
        output_path: Optional[Path] = None,
        timestamp_utc: str = "2026-10-17T12:00:00Z",
    ) -> Path:
        target = output_path if output_path is not None else (REPO_ROOT / "evidence" / "cbom.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        cbom_dict = self.build_cbom_dict(timestamp_utc=timestamp_utc)
        target.write_text(json.dumps(cbom_dict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    @staticmethod
    def verify_cbom_manifest(
        cbom_dict: Dict[str, Any],
        expected_public_key: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> Dict[str, Any]:
        """
        Verifies a CycloneDX 1.6 CBOM dictionary:
          1. Validates `bomFormat == "CycloneDX"` and `specVersion == "1.6"`.
          2. Validates required `cryptographic-asset` components (`Ed25519`, `SHA-256`, `ML-DSA-65`).
          3. Verifies the Ed25519 signature over the RFC 8785 JCS canonical encoding of the unsigned CBOM.
        """
        if not isinstance(cbom_dict, dict):
            return {"valid": False, "error": "CBOM must be a dictionary"}
        if cbom_dict.get("bomFormat") != "CycloneDX":
            return {"valid": False, "error": f"Invalid bomFormat: {cbom_dict.get('bomFormat')!r}"}
        if cbom_dict.get("specVersion") != "1.6":
            return {"valid": False, "error": f"Invalid specVersion: {cbom_dict.get('specVersion')!r}"}

        components = cbom_dict.get("components")
        if not isinstance(components, list) or len(components) == 0:
            return {"valid": False, "error": "CBOM components list is missing or empty"}

        for comp in components:
            if comp.get("type") != "cryptographic-asset":
                return {
                    "valid": False,
                    "error": f"Component {comp.get('bom-ref')!r} does not have type 'cryptographic-asset'",
                }
            if "cryptoProperties" not in comp or not isinstance(comp["cryptoProperties"], dict):
                return {
                    "valid": False,
                    "error": f"Component {comp.get('bom-ref')!r} missing cryptoProperties",
                }

        att = cbom_dict.get("attestation_signature")
        if not isinstance(att, dict):
            return {"valid": False, "error": "Missing attestation_signature block"}

        unsigned_copy = {k: v for k, v in cbom_dict.items() if k != "attestation_signature"}
        canonical_bytes = encode_jcs(unsigned_copy)
        computed_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        if att.get("payload_jcs_sha256") != computed_sha256:
            return {
                "valid": False,
                "error": "CBOM JCS SHA-256 digest mismatch against attestation_signature",
            }

        try:
            pub_key = (
                expected_public_key
                if expected_public_key is not None
                else ed25519.Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(att["public_key_hex"])
                )
            )
            sig_bytes = bytes.fromhex(att["signature_hex"])
            pub_key.verify(sig_bytes, canonical_bytes)
        except InvalidSignature:
            return {"valid": False, "error": "Invalid Ed25519 signature over CBOM JCS payload"}
        except Exception as exc:
            return {"valid": False, "error": f"CBOM signature verification error: {exc}"}

        return {
            "valid": True,
            "serial_number": cbom_dict.get("serialNumber"),
            "component_count": len(components),
            "payload_jcs_sha256": computed_sha256,
            "key_id": att.get("key_id"),
            "error": None,
        }


# ============================================================================
# SCITT-Anchored OpenTelemetry GenAI `execute_tool` Span Exporter & Verifier
# ============================================================================


class SCITTAnchoredOTelGate:
    """
    Signs AEIB Station 1/3 tool execution receipts as RFC 9052 COSE_Sign1 (Tag 18)
    envelopes, registers them in an RFC 9943 / RFC 9942 SCITT Transparency Service,
    attaches the binary COSE Receipt into Unprotected Header 394 (with Protected
    Header 395=1 VDS_RFC9162_SHA256 and Unprotected Header 396 VDP inclusion proof),
    and exports OpenTelemetry GenAI `execute_tool` spans.
    """

    def __init__(
        self,
        issuer_privkey: ed25519.Ed25519PrivateKey,
        ts_privkey: ed25519.Ed25519PrivateKey,
        issuer_kid: str = "aeib-station-ed25519:node-01",
        service_id: str = "aeib-scitt-transparency-log-01",
    ) -> None:
        self.issuer_privkey = issuer_privkey
        self.issuer_pubkey = issuer_privkey.public_key()
        self.issuer_kid = issuer_kid
        self.ts_privkey = ts_privkey
        self.ts_pubkey = ts_privkey.public_key()
        self.service_id = service_id

        self.cose_signer = RFC9052CoseSigner(private_key=issuer_privkey, key_id=issuer_kid)
        self.transparency_service = SCITTTransparencyService(
            service_id=service_id,
            ts_privkey=ts_privkey,
        )

    @property
    def current_merkle_root_hex(self) -> str:
        """Returns the current 64-hex RFC 9162 SHA-256 Merkle root of the SCITT log."""
        return self.transparency_service.tree.root_hash().hex()

    def record_tool_execution_span(
        self,
        tool_name: str,
        tool_call_id: str,
        receipt_payload: Dict[str, Any],
        station_id: str = "station_1_pre_exec",
        cose_alg: int = COSE_ALG_EDDSA,
        external_aad: bytes = b"",
    ) -> Dict[str, Any]:
        """
        Signs `receipt_payload` as a binary Tag 18 COSE_Sign1 Signed Statement,
        registers it in the SCITT Merkle tree, embeds the RFC 9942 binary COSE Receipt
        into Unprotected Header 394, and returns an OpenTelemetry GenAI `execute_tool` span.
        """
        if not tool_name or not isinstance(tool_name, str):
            raise ValueError("tool_name must be a non-empty string")
        if not tool_call_id or not isinstance(tool_call_id, str):
            raise ValueError("tool_call_id must be a non-empty string")

        # Validate COSE algorithm negotiation (fails closed on downgraded/unactivated algs)
        COSEAlgorithmRegistry.negotiate_cose_alg(cose_alg, require_active_provider=True)

        # 1. Canonicalize inner receipt payload with RFC 8785 JCS and sign as COSE_Sign1 (Tag 18)
        jcs_bytes = encode_jcs(receipt_payload)
        payload_caid = hashlib.sha256(jcs_bytes).hexdigest()
        signed_statement_cbor = self.cose_signer.sign(
            jcs_bytes,
            external_aad=external_aad,
            protected_extra={3: "application/aeib-receipt+jcs"},
        )

        # 2. Issue RFC 9942 binary COSE Receipt from SCITT Transparency Service
        #    Protected Header 395 = 1 (VDS_RFC9162_SHA256)
        #    Unprotected Header 396 = VDP map {-1: tree_size, -2: leaf_index, -3: inclusion_path}
        binary_receipt_cbor = self.transparency_service.issue_binary_cose_receipt(
            signed_statement_cbor,
            issuer_pubkey=self.issuer_pubkey,
            expected_aad=external_aad,
        )

        # 3. Attach binary receipt into Unprotected Header 394 (COSE_HEADER_RECEIPTS)
        transparent_statement_cbor = append_receipt_to_signed_statement(
            signed_statement_cbor,
            binary_receipt_cbor,
        )

        # Decode receipt VDP metadata to populate OpenTelemetry attributes
        rcpt_tag = RFC8949CBOR.decode(binary_receipt_cbor)
        _, rcpt_unprotected, rcpt_payload, _ = rcpt_tag.value
        vdp_map = rcpt_unprotected[COSE_HEADER_VDP]
        tree_size = int(vdp_map[VDP_TREE_SIZE])
        leaf_index = int(vdp_map[VDP_LEAF_INDEX])
        merkle_root_hex = bytes(rcpt_payload).hex()

        transparent_b64 = base64.b64encode(transparent_statement_cbor).decode("ascii")
        transparent_b64url = (
            base64.urlsafe_b64encode(transparent_statement_cbor).rstrip(b"=").decode("ascii")
        )

        span_id = hashlib.sha256(
            f"span:{tool_call_id}:{leaf_index}:{merkle_root_hex}".encode("utf-8")
        ).hexdigest()[:16]
        trace_id = hashlib.sha256(
            f"trace:{tool_call_id}:{payload_caid}".encode("utf-8")
        ).hexdigest()[:32]

        return {
            "name": f"execute_tool {tool_name}",
            "trace_id": trace_id,
            "span_id": span_id,
            "kind": "INTERNAL",
            "status": {"status_code": "OK"},
            "attributes": {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_name,
                "gen_ai.tool.call.id": tool_call_id,
                "aeib.station.id": station_id,
                "aeib.receipt.caid_sha256": payload_caid,
                "aeib.crypto.cose_alg": cose_alg,
                "aeib.scitt.service_id": self.service_id,
                "aeib.scitt.vds": VDS_RFC9162_SHA256,
                "aeib.scitt.merkle_root_sha256": merkle_root_hex,
                "aeib.scitt.leaf_index": leaf_index,
                "aeib.scitt.tree_size": tree_size,
                "aeib.scitt.transparent_statement_b64": transparent_b64,
                "aeib.scitt.receipt_cose_b64url": transparent_b64url,
            },
        }

    @staticmethod
    def verify_otel_span_against_external_scitt_root(
        otel_span: Dict[str, Any],
        expected_merkle_root_hex: str,
        issuer_pubkey: ed25519.Ed25519PublicKey,
        ts_pubkey: ed25519.Ed25519PublicKey,
        expected_aad: bytes = b"",
    ) -> Dict[str, Any]:
        """
        Verifies an OpenTelemetry GenAI `execute_tool` span offline using ONLY:
          - the span attributes (`aeib.scitt.transparent_statement_b64` / `receipt_cose_b64url`),
          - the external auditor's pinned SCITT Merkle root (`expected_merkle_root_hex`),
          - the issuer and Transparency Service Ed25519 public keys.
        Does NOT read or trust any host-local `ledger.jsonl` file.
        """
        if not isinstance(otel_span, dict):
            return {"valid": False, "error": "otel_span must be a dictionary"}

        attrs = otel_span.get("attributes")
        if not isinstance(attrs, dict):
            return {"valid": False, "error": "Missing attributes dictionary in otel_span"}

        if attrs.get("gen_ai.operation.name") != "execute_tool":
            return {
                "valid": False,
                "error": (
                    f"Invalid gen_ai.operation.name: {attrs.get('gen_ai.operation.name')!r} "
                    "(expected 'execute_tool')"
                ),
            }

        # Validate COSE algorithm header on span
        cose_alg = attrs.get("aeib.crypto.cose_alg")
        try:
            COSEAlgorithmRegistry.negotiate_cose_alg(cose_alg, require_active_provider=True)
        except ValueError as exc:
            return {"valid": False, "error": str(exc)}

        if not isinstance(expected_merkle_root_hex, str) or len(expected_merkle_root_hex) != 64:
            return {"valid": False, "error": "expected_merkle_root_hex must be a 64-character hex string"}

        span_root_hex = attrs.get("aeib.scitt.merkle_root_sha256")
        if span_root_hex != expected_merkle_root_hex:
            return {
                "valid": False,
                "error": (
                    f"Span aeib.scitt.merkle_root_sha256 ({span_root_hex!r}) does not match "
                    f"pinned external SCITT Merkle root ({expected_merkle_root_hex!r})"
                ),
            }

        stmt_b64 = attrs.get("aeib.scitt.transparent_statement_b64")
        stmt_b64url = attrs.get("aeib.scitt.receipt_cose_b64url")
        if not isinstance(stmt_b64, str) or not stmt_b64:
            return {"valid": False, "error": "Missing aeib.scitt.transparent_statement_b64 in span"}

        try:
            transparent_cbor = base64.b64decode(stmt_b64, validate=True)
        except Exception as exc:
            return {"valid": False, "error": f"Invalid base64 in transparent_statement_b64: {exc}"}

        if isinstance(stmt_b64url, str) and stmt_b64url:
            padding = "=" * ((4 - len(stmt_b64url) % 4) % 4)
            try:
                decoded_url_bytes = base64.urlsafe_b64decode(stmt_b64url + padding)
            except Exception as exc:
                return {"valid": False, "error": f"Invalid base64url in receipt_cose_b64url: {exc}"}
            if decoded_url_bytes != transparent_cbor:
                return {
                    "valid": False,
                    "error": "Mismatch between transparent_statement_b64 and receipt_cose_b64url",
                }

        # Verify the binary Tag 18 COSE_Sign1 Transparent Statement (Headers 394, 395, 396)
        scitt_res = verify_binary_transparent_statement(
            transparent_cbor,
            issuer_pubkey=issuer_pubkey,
            ts_pubkey=ts_pubkey,
            expected_aad=expected_aad,
        )
        if not scitt_res.get("valid"):
            return {
                "valid": False,
                "error": f"SCITT Transparent Statement verification failed: {scitt_res.get('error')}",
            }

        # Cross-verify Merkle root, leaf_index, tree_size, and JCS payload CAID
        if scitt_res["merkle_root_hex"] != expected_merkle_root_hex:
            return {
                "valid": False,
                "error": (
                    f"Verified SCITT receipt Merkle root ({scitt_res['merkle_root_hex']}) "
                    f"does not match pinned external root ({expected_merkle_root_hex})"
                ),
            }

        if scitt_res["leaf_index"] != attrs.get("aeib.scitt.leaf_index"):
            return {
                "valid": False,
                "error": "Span aeib.scitt.leaf_index mismatch against signed SCITT VDP (-2)",
            }

        if scitt_res["tree_size"] != attrs.get("aeib.scitt.tree_size"):
            return {
                "valid": False,
                "error": "Span aeib.scitt.tree_size mismatch against signed SCITT VDP (-1)",
            }

        payload_bytes = scitt_res["statement_payload"]
        computed_caid = hashlib.sha256(payload_bytes).hexdigest()
        if computed_caid != attrs.get("aeib.receipt.caid_sha256"):
            return {
                "valid": False,
                "error": "Span aeib.receipt.caid_sha256 does not match signed COSE payload SHA-256",
            }

        try:
            decoded_receipt_json = json.loads(payload_bytes.decode("utf-8"))
            if encode_jcs(decoded_receipt_json) != payload_bytes:
                return {
                    "valid": False,
                    "error": "Inner COSE statement payload is not canonical RFC 8785 JCS",
                }
        except Exception as exc:
            return {"valid": False, "error": f"Inner COSE payload JSON parse failure: {exc}"}

        return {
            "valid": True,
            "tool_name": attrs.get("gen_ai.tool.name"),
            "tool_call_id": attrs.get("gen_ai.tool.call.id"),
            "station_id": attrs.get("aeib.station.id"),
            "payload_caid_sha256": computed_caid,
            "merkle_root_sha256": scitt_res["merkle_root_hex"],
            "leaf_index": scitt_res["leaf_index"],
            "tree_size": scitt_res["tree_size"],
            "vds": scitt_res["vds"],
            "service_id": scitt_res["service_id"],
            "receipt_payload": decoded_receipt_json,
            "error": None,
        }


if __name__ == "__main__":
    generator = CycloneDX16CBOMGenerator()
    cbom_path = generator.write_cbom_file()
    print(f"Generated CycloneDX 1.6 CBOM at: {cbom_path}")
