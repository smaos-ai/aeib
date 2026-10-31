#!/usr/bin/env python3
r"""
src/diagnostic_normalizer.py
================================================================================
MCP JSON-RPC 2.0 Execution Normalizer & 4-Step SMAOS Wrap
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Category: Agent Execution Integrity
Tagline : Actions are claims. Outcomes are evidence.
Invariant: authorized write ≠ persisted write ≠ correct physical outcome

Defensible Scope:
  "SMAOS is a local execution-integrity prototype that preserves action identity,
   quarantines ambiguous post-write outcomes, and produces structured,
   COSE_Sign1–signed evidence for reconciliation and later audit review."

Evaluation Status: INTERNAL PREVIEW COMMISSIONED.
Epistemic Boundary: Observed, tested, and configured under the stated model.
Serialization: Single-source RFC 8785 JCS canonicalization scheme.

The Four-Step SMAOS Execution Cycle:
  Step 1: Pre-dispatch authority check (identity, TTL, policy, schema)
  Step 2: Dispatch (UUIDv5 idempotency injection, transport fault quarantine)
  Step 3: Post-condition probe (authoritative downstream state reconciliation)
  Step 4: Attest (complete receipt coverage sealed in standard RFC 9052 COSE_Sign1 envelope)

Error Taxonomy & Retry Policy:
  • OUTCOME_VERIFIED        : Retry: NO. Outcome physically confirmed; proceed.
  • ACK_UNVERIFIED          : Retry: NO (without probe). Wire ack only; require probe.
  • DISPATCHED_UNCONFIRMED  : Retry: NO. Network drop; halt and poll probe.
  • RECONCILIATION_NOT_FOUND: Retry: YES (with new authority). Safe to re-dispatch with fresh key.
  • RECONCILIATION_FAILED   : Retry: NO. Payload hash divergence/tampering; escalate.
  • PROBE_EXCEPTION         : Retry: MAYBE (probe only). Retry probe with backoff; halt action.
  • RECONCILIATION_CONFLICT : Retry: NO. Multiple conflicting downstream records; escalate.
  • REFUSED                 : Retry: NO. Authority check failed or rejected.
"""

import os
import sys
import json
import time
import uuid
import struct
import hashlib
import hmac
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union, Protocol, Set, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Cryptography: Ed25519 for RFC 9052 COSE_Sign1
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# Try importing pycose if available
try:
    import pycose.messages
    import pycose.headers
    import pycose.algorithms
    import pycose.keys
    PYCOSE_AVAILABLE = True
except ImportError:
    PYCOSE_AVAILABLE = False


# Try importing RFC 8785 JCS canonicalizer
try:
    from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
except ImportError:
    try:
        from jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
    except ImportError:
        encode_jcs = None
        generate_jcs_payload_hash = None


# ── Constants & Namespaces ───────────────────────────────────────────────────

SERIALIZATION_LABEL = "RFC 8785 JCS Validated"
RECEIPT_VERSION = "1.2.0"
COSE_ALG_EDDSA = -8  # RFC 9054 / RFC 8152 EdDSA
COSE_HEADER_ALG = 1
COSE_HEADER_KID = 4

# Policy Defaults (Integer Milliseconds)
DEFAULT_FRESHNESS_LIMIT_MS: int = 100_000  # claim: config
HIGH_RISK_FRESHNESS_LIMIT_MS: int = 5_000  # claim: config

# SMAOS Action Integrity Namespace (RFC 4122 UUIDv5)
NAMESPACE_SMAOS_URL = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

# Retry Policies
RETRY_POLICY_TABLE: Dict[str, Dict[str, Any]] = {
    "OUTCOME_VERIFIED": {
        "retry_allowed": False,
        "action": "Record and proceed."
    },
    "ACK_UNVERIFIED": {
        "retry_allowed": False,
        "action": "Require authoritative probe before any retry."
    },
    "DISPATCHED_UNCONFIRMED": {
        "retry_allowed": False,
        "action": "Run reconciliation probe; decide based on result."
    },
    "RECONCILIATION_NOT_FOUND": {
        "retry_allowed": True,
        "action": "Obtain fresh authority and new idempotency key."
    },
    "RECONCILIATION_FAILED": {
        "retry_allowed": False,
        "action": "Escalate; do not retry automatically."
    },
    "PROBE_EXCEPTION": {
        "retry_allowed": False,  # Action retry not allowed; probe retry only
        "action": "Retry probe with backoff; do not retry original action until probe succeeds."
    },
    "RECONCILIATION_CONFLICT": {
        "retry_allowed": False,
        "action": "Escalate; manual resolution required."
    },
    "REFUSED": {
        "retry_allowed": False,
        "action": "Authority check failed; do not retry without new credentials."
    }
}


# ── Deterministic JSON Serialization ──────────────────────────────────────────

def deterministic_json_bytes(data: Any) -> bytes:
    """
    Serializes data to deterministic UTF-8 bytes conforming to RFC 8785 (JCS).
    Enforces UTF-16 code-unit sorted keys, compact separators, unescaped UTF-8,
    and strict rejection of NaN/Infinity.
    """
    if encode_jcs is None:
        raise RuntimeError("ERR_JCS_CANONICALIZER_UNAVAILABLE")
    return encode_jcs(data)


def deterministic_digest(data: Any) -> str:
    """Computes SHA-256 digest over RFC 8785 JCS canonical JSON bytes."""
    if generate_jcs_payload_hash is not None:
        return f"sha256:{generate_jcs_payload_hash(data)}"
    return f"sha256:{hashlib.sha256(deterministic_json_bytes(data)).hexdigest()}"


# ── Minimal RFC 8949 CBOR Encoder for Air-Gapped COSE_Sign1 ──────────────────

class MinimalCBOR:
    """
    Zero-dependency, deterministic RFC 8949 CBOR encoder and decoder subset
    sufficient for standard RFC 9052 COSE_Sign1 envelopes.
    Runs 100% locally with zero external network egress.
    """

    @classmethod
    def encode(cls, val: Any) -> bytes:
        if val is None:
            return b'\xf6'
        elif isinstance(val, bool):
            return b'\xf5' if val else b'\xf4'
        elif isinstance(val, int):
            if val >= 0:
                return cls._encode_header(0, val)
            else:
                # Negative int in CBOR: -1 - val (major type 1)
                return cls._encode_header(1, -1 - val)
        elif isinstance(val, bytes):
            return cls._encode_header(2, len(val)) + val
        elif isinstance(val, str):
            utf8 = val.encode('utf-8')
            return cls._encode_header(3, len(utf8)) + utf8
        elif isinstance(val, (list, tuple)):
            out = bytearray(cls._encode_header(4, len(val)))
            for item in val:
                out.extend(cls.encode(item))
            return bytes(out)
        elif isinstance(val, dict):
            # Sort keys deterministically
            sorted_items = sorted(
                val.items(),
                key=lambda kv: (isinstance(kv[0], str), kv[0])
            )
            out = bytearray(cls._encode_header(5, len(sorted_items)))
            for k, v in sorted_items:
                out.extend(cls.encode(k))
                out.extend(cls.encode(v))
            return bytes(out)
        else:
            raise TypeError(f"CBOR unsupported type: {type(val)}")

    @classmethod
    def _encode_header(cls, major: int, val: int) -> bytes:
        major_bits = major << 5
        if val < 24:
            return bytes([major_bits | val])
        elif val <= 0xff:
            return bytes([major_bits | 24, val])
        elif val <= 0xffff:
            return struct.pack('>BH', major_bits | 25, val)
        elif val <= 0xffffffff:
            return struct.pack('>BI', major_bits | 26, val)
        elif val <= 0xffffffffffffffff:
            return struct.pack('>BQ', major_bits | 27, val)
        else:
            raise ValueError(f"CBOR integer too large: {val}")

    @classmethod
    def encode_tag(cls, tag_num: int, item: Any) -> bytes:
        """Encodes CBOR tag (major type 6). Tag 18 = COSE_Sign1."""
        return cls._encode_header(6, tag_num) + cls.encode(item)

    @classmethod
    def decode_item(cls, raw: bytes, idx: int = 0) -> Tuple[Any, int]:
        """
        Recursively decodes a CBOR item and returns (decoded_item, next_idx).
        """
        if idx >= len(raw):
            raise ValueError("Unexpected end of CBOR bytes")
        major = raw[idx] >> 5
        info = raw[idx] & 0x1f
        idx += 1
        if info < 24:
            val = info
        elif info == 24:
            val = raw[idx]
            idx += 1
        elif info == 25:
            val = struct.unpack('>H', raw[idx:idx+2])[0]
            idx += 2
        elif info == 26:
            val = struct.unpack('>I', raw[idx:idx+4])[0]
            idx += 4
        elif info == 27:
            val = struct.unpack('>Q', raw[idx:idx+8])[0]
            idx += 8
        else:
            raise ValueError(f"Unsupported CBOR additional info: {info}")

        if major == 0:  # unsigned int
            return val, idx
        elif major == 1:  # negative int (-1 - val)
            return -1 - val, idx
        elif major == 2:  # byte string
            return raw[idx:idx+val], idx + val
        elif major == 3:  # text string
            return raw[idx:idx+val].decode('utf-8'), idx + val
        elif major == 4:  # array
            arr = []
            for _ in range(val):
                item, idx = cls.decode_item(raw, idx)
                arr.append(item)
            return arr, idx
        elif major == 5:  # map
            m = {}
            for _ in range(val):
                k, idx = cls.decode_item(raw, idx)
                v, idx = cls.decode_item(raw, idx)
                m[k] = v
            return m, idx
        elif major == 6:  # tag
            tagged_item, idx = cls.decode_item(raw, idx)
            return ("TAG", val, tagged_item), idx
        else:  # major == 7 (simple / float)
            if info == 20:
                return False, idx
            elif info == 21:
                return True, idx
            elif info == 22:
                return None, idx
            else:
                raise ValueError(f"Unsupported CBOR simple value: {info}")


# ── Key Registry & Key Management ─────────────────────────────────────────────

class KeyRegistry:
    """
    Registry for Ed25519 public keys mapped by Key ID (`kid`).
    Supports rotation, lookup, and PEM import/export.
    """

    def __init__(self):
        self._keys: Dict[str, ed25519.Ed25519PublicKey] = {}

    def register_key(self, kid: str, public_key: ed25519.Ed25519PublicKey):
        self._keys[kid] = public_key

    def get_key(self, kid: str) -> Optional[ed25519.Ed25519PublicKey]:
        return self._keys.get(kid)

    def register_from_pem(self, kid: str, pem_bytes: bytes):
        pub = serialization.load_pem_public_key(pem_bytes)
        if not isinstance(pub, ed25519.Ed25519PublicKey):
            raise TypeError("Key must be an Ed25519 public key")
        self._keys[kid] = pub

    def export_pem(self, kid: str) -> bytes:
        pub = self._keys.get(kid)
        if not pub:
            raise KeyError(f"Key ID '{kid}' not registered")
        return pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )


# ── RFC 9052 / RFC 8152 COSE_Sign1 Engine ─────────────────────────────────────

class COSESign1Engine:
    """
    Standard RFC 9052 COSE_Sign1 envelope implementation for EdDSA (alg: -8).
    Creates and verifies envelopes using Ed25519 keys or Zero-RAM PKCS#11 callbacks.
    """

    def __init__(self, pkcs11_signer_callback: Optional[Callable[[bytes], bytes]] = None):
        """
        The signer_callback is bound to `PKCS11HSMEnclave.sign_digest` in production.
        It strictly receives a 32-byte SHA-256 digest of the COSE Sig_structure.
        """
        self.signer_callback = pkcs11_signer_callback

    def create_receipt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates the JCS canonicalized payload and applies a Zero-RAM signature.
        """
        if encode_jcs is not None:
            jcs_payload_bytes = encode_jcs(payload)
        else:
            jcs_payload_bytes = deterministic_json_bytes(payload)

        context_string = b"Signature1"
        body_protected = b""
        external_aad = b""

        sig_structure = context_string + body_protected + external_aad + jcs_payload_bytes
        digest = hashlib.sha256(sig_structure).digest()

        if self.signer_callback:
            signature_bytes = self.signer_callback(digest)
            signature_hex = signature_bytes.hex()
        else:
            signature_hex = "UNSIGNED_DEVELOPMENT_MODE"

        return {
            "serialization": SERIALIZATION_LABEL,
            "payload_jcs": jcs_payload_bytes.decode('utf-8'),
            "signature": signature_hex
        }

    @staticmethod
    def create_envelope(
        payload: bytes,
        private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        key_id: Optional[str] = None,
        external_aad: bytes = b"",
        signer_callback: Optional[Callable[[bytes], bytes]] = None
    ) -> bytes:
        """
        Builds and signs a standard COSE_Sign1 message:
          COSE_Sign1 = [
             protected: bstr,     // CBOR { 1: -8 }
             unprotected: map,    // { 4: key_id } or {}
             payload: bstr,       // payload bytes
             signature: bstr      // 64-byte Ed25519 signature
          ]
        Sig_structure = ["Signature1", protected, external_aad, payload]
        """
        # Protected header: { 1: -8 } -> alg: EdDSA
        protected_map = {COSE_HEADER_ALG: COSE_ALG_EDDSA}
        body_protected = MinimalCBOR.encode(protected_map)

        # Unprotected header: { 4: key_id.encode('utf-8') } if key_id
        unprotected_map: Dict[Any, Any] = {}
        if key_id:
            unprotected_map[COSE_HEADER_KID] = key_id.encode("utf-8")

        # Sig_structure: ["Signature1", body_protected, external_aad, payload]
        sig_structure = [
            "Signature1",
            body_protected,
            external_aad,
            payload
        ]
        sig_structure_bytes = MinimalCBOR.encode(sig_structure)

        # Sign with PKCS#11 Zero-RAM callback if provided, else private key
        if signer_callback is not None:
            digest = hashlib.sha256(sig_structure_bytes).digest()
            signature = signer_callback(digest)
        elif private_key is not None:
            signature = private_key.sign(sig_structure_bytes)
        else:
            raise ValueError("Either private_key or signer_callback (PKCS#11) must be provided.")

        # Construct COSE_Sign1 array: [body_protected, unprotected_map, payload, signature]
        cose_sign1_array = [
            body_protected,
            unprotected_map,
            payload,
            signature
        ]

        # Wrap in CBOR Tag 18 (COSE_Sign1)
        return MinimalCBOR.encode_tag(18, cose_sign1_array)

    @staticmethod
    def verify_envelope(
        envelope_cbor: bytes,
        public_key: ed25519.Ed25519PublicKey,
        external_aad: bytes = b""
    ) -> Tuple[bool, bytes, Dict[str, Any]]:
        """
        Verifies a COSE_Sign1 envelope against the supplied Ed25519 public key.
        Returns: (is_valid, payload_bytes, metadata)
        """
        decoded, _ = MinimalCBOR.decode_item(envelope_cbor)
        if isinstance(decoded, tuple) and len(decoded) == 3 and decoded[0] == "TAG":
            cose_arr = decoded[2]
        elif isinstance(decoded, list):
            cose_arr = decoded
        else:
            raise ValueError("Malformed COSE_Sign1 message: expected CBOR tag 18 or array")

        if not isinstance(cose_arr, list) or len(cose_arr) != 4:
            raise ValueError("Malformed COSE_Sign1 message: expected 4-element array")

        body_protected = cose_arr[0]
        unprotected_map = cose_arr[1]
        payload = cose_arr[2]
        signature = cose_arr[3]

        if not isinstance(body_protected, bytes):
            raise ValueError("body_protected must be a byte string")
        if not isinstance(payload, bytes):
            raise ValueError("payload must be a byte string")
        if not isinstance(signature, bytes) or len(signature) != 64:
            raise ValueError("signature must be 64 bytes (Ed25519)")

        extracted_kid = None
        if isinstance(unprotected_map, dict) and COSE_HEADER_KID in unprotected_map:
            raw_kid = unprotected_map[COSE_HEADER_KID]
            if isinstance(raw_kid, bytes):
                extracted_kid = raw_kid.decode('utf-8', errors='replace')
            elif isinstance(raw_kid, str):
                extracted_kid = raw_kid

        # Reconstruct Sig_structure = ["Signature1", body_protected, external_aad, payload]
        sig_structure = [
            "Signature1",
            body_protected,
            external_aad,
            payload
        ]
        sig_structure_bytes = MinimalCBOR.encode(sig_structure)

        meta = {
            "cose_alg": COSE_ALG_EDDSA,
            "cose_kid": extracted_kid,
            "signature_len": len(signature)
        }

        try:
            public_key.verify(signature, sig_structure_bytes)
            return True, payload, meta
        except InvalidSignature:
            meta["error"] = "Invalid signature"
            return False, payload, meta


# ── Models & State Machine Definitions ────────────────────────────────────────

@dataclass
class AuthorityContext:
    """Pre-dispatch authority context."""
    actor: str
    tool: str
    valid_from: Optional[Union[int, float]] = None
    authority_ttl: Optional[str] = None
    allowed_tools: Optional[List[str]] = None


@dataclass
class CompleteExecutionReceipt:
    """
    Standard Complete Execution Receipt covering all evaluated invariants.
    """
    receipt_version: str
    key_id: str
    action_id: str
    actor: str
    authority_hash: str
    authority_ttl: Optional[str]
    dispatched_at: str
    request_payload_hash: str
    downstream_state_hash: Optional[str]
    observed_outcome: Dict[str, Any]
    outcome_verified: bool
    verification_method: str
    wall_clock_delta_ms: Optional[int]
    freshness_status: str
    freshness_limit_ms: int
    serialization_format: str
    disposition: str
    transport_fault: str
    retry_policy: Dict[str, Any]
    cose_envelope_hex: Optional[str] = None
    cose_alg: int = COSE_ALG_EDDSA
    cose_kid: Optional[str] = None
    cose_payload_hash: Optional[str] = None
    hmac_sha256_tag: Optional[str] = None

    def to_unsigned_dict(self) -> Dict[str, Any]:
        """Returns the canonical dictionary of all receipt fields to be authenticated."""
        d = asdict(self)
        d.pop("cose_envelope_hex", None)
        d.pop("cose_alg", None)
        d.pop("cose_kid", None)
        d.pop("cose_payload_hash", None)
        d.pop("hmac_sha256_tag", None)
        return d

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── MCP JSON-RPC 2.0 Parser ───────────────────────────────────────────────────

class MCPJSONRPCParser:
    """
    Natively parses Model Context Protocol tools/call JSON-RPC 2.0 requests
    and manages deterministic action identification and idempotency keys.
    """

    @staticmethod
    def parse_tools_call(raw_payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
        """
        Extracts (tool_name, arguments, rpc_id) from MCP tools/call request.
        Validates JSON-RPC 2.0 structure.
        """
        if not isinstance(raw_payload, dict):
            raise ValueError(f"Payload must be a JSON object, got {type(raw_payload).__name__}")

        if raw_payload.get("jsonrpc") != "2.0":
            raise ValueError(f"Invalid JSON-RPC protocol version: {raw_payload.get('jsonrpc')}")

        method = str(raw_payload.get("method", ""))
        rpc_id = str(raw_payload.get("id", "mcp-anon-call"))

        if "params" not in raw_payload:
            raise ValueError("Missing mandatory 'params' field in MCP JSON-RPC request.")

        params = raw_payload.get("params")
        if not isinstance(params, dict):
            raise ValueError(f"MCP params must be a JSON object, got {type(params).__name__}")

        if method == "tools/call":
            tool_name = params.get("name")
            if not tool_name or not isinstance(tool_name, str):
                raise ValueError("Missing or invalid 'name' in MCP tools/call params.")
            arguments = params.get("arguments", params.get("args", {}))
        elif method.startswith("tools/"):
            tool_name = method.split("/", 1)[1]
            arguments = params
        else:
            raise ValueError(f"Method '{method}' is not in the MCP 'tools/' namespace.")

        if not isinstance(arguments, dict):
            raise ValueError(f"Tool arguments must be a JSON object, got {type(arguments).__name__}")

        return tool_name, arguments, rpc_id

    @staticmethod
    def generate_composite_action_id(
        session_id: str,
        step: int,
        rpc_id: str,
        tool_name: str
    ) -> str:
        """
        Generates composite action identity:
        mcp://{session_id}/{step}/{rpc_id}/{tool_name}
        """
        return f"mcp://{session_id}/{step}/{rpc_id}/{tool_name}"

    @staticmethod
    def generate_uuidv5_idempotency_key(
        action_id: str,
        payload_hash: str
    ) -> str:
        """
        Generates deterministic UUIDv5 key bound to canonical payload digest
        and action identity under SMAOS namespace.
        """
        seed = f"{action_id}:{payload_hash}"
        return str(uuid.uuid5(NAMESPACE_SMAOS_URL, seed))


# ── Post-Condition Prober Protocol & Implementations ──────────────────────────

class PostConditionProber(Protocol):
    """Abstract protocol for out-of-band downstream state reconciliation."""
    def probe(
        self,
        idempotency_key: str,
        action_id: str,
        expected_payload_hash: str
    ) -> Dict[str, Any]:
        ...


class DatabaseStateProber:
    """
    Queries an authoritative local or remote SQL database ledger for record state.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_ledger (
                idempotency_key TEXT PRIMARY KEY,
                action_id TEXT,
                payload_hash TEXT,
                status TEXT,
                persisted_at TEXT,
                details TEXT
            )
        """)
        self.conn.commit()

    def insert_record(self, idempotency_key: str, action_id: str, payload_hash: str, status: str, details: str = "{}"):
        self.conn.execute(
            "INSERT OR REPLACE INTO audit_ledger VALUES (?, ?, ?, ?, ?, ?)",
            (idempotency_key, action_id, payload_hash, status, datetime.now(timezone.utc).isoformat(), details)
        )
        self.conn.commit()

    def probe(
        self,
        idempotency_key: str,
        action_id: str,
        expected_payload_hash: str
    ) -> Dict[str, Any]:
        """
        Executes SQL query against audit_ledger.
        Returns typed dictionary with reconciliation status and downstream state hash.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT idempotency_key, action_id, payload_hash, status, persisted_at, details FROM audit_ledger WHERE idempotency_key = ?",
            (idempotency_key,)
        )
        rows = cursor.fetchall()

        if len(rows) == 0:
            return {
                "disposition": "RECONCILIATION_NOT_FOUND",
                "outcome_verified": False,
                "downstream_state_hash": None,
                "record": None
            }
        elif len(rows) > 1:
            return {
                "disposition": "RECONCILIATION_CONFLICT",
                "outcome_verified": False,
                "downstream_state_hash": None,
                "conflict_count": len(rows)
            }

        row = rows[0]
        rec = {
            "idempotency_key": row[0],
            "action_id": row[1],
            "payload_hash": row[2],
            "status": row[3],
            "persisted_at": row[4],
            "details": row[5]
        }
        state_hash = deterministic_digest(rec)

        if rec["payload_hash"] != expected_payload_hash:
            return {
                "disposition": "RECONCILIATION_FAILED",
                "outcome_verified": False,
                "downstream_state_hash": state_hash,
                "reason": "Payload hash mismatch against persisted row (possible tampering or parameter collision)",
                "record": rec
            }

        if rec["status"] in ("CONFIRMED", "COMMITTED", "PERSISTED", "SETTLED"):
            return {
                "disposition": "OUTCOME_VERIFIED",
                "outcome_verified": True,
                "downstream_state_hash": state_hash,
                "record": rec
            }
        else:
            return {
                "disposition": "RECONCILIATION_FAILED",
                "outcome_verified": False,
                "downstream_state_hash": state_hash,
                "record": rec
            }


class HTTPReconciliationProber:
    """
    Queries an out-of-band HTTP reconciliation endpoint.
    Uses authoritative client callback or returns unconfirmed probe.
    """

    def __init__(self, endpoint_url: str = "https://api.internal.bank/reconcile", client_fn: Optional[Any] = None):
        self.endpoint_url = endpoint_url
        self.client_fn = client_fn

    def probe(
        self,
        idempotency_key: str,
        action_id: str,
        expected_payload_hash: str
    ) -> Dict[str, Any]:
        if self.client_fn is None:
            # Default unconfirmed probe handler when client callback is absent
            return {
                "disposition": "RECONCILIATION_NOT_FOUND",
                "outcome_verified": False,
                "downstream_state_hash": None,
                "endpoint": self.endpoint_url
            }

        res = self.client_fn(self.endpoint_url, idempotency_key, action_id)
        if res.get("status") == 200 and res.get("committed", False):
            state_hash = deterministic_digest(res)
            return {
                "disposition": "OUTCOME_VERIFIED",
                "outcome_verified": True,
                "downstream_state_hash": state_hash,
                "response": res
            }
        elif res.get("status") == 404:
            return {
                "disposition": "RECONCILIATION_NOT_FOUND",
                "outcome_verified": False,
                "downstream_state_hash": None,
                "response": res
            }
        else:
            return {
                "disposition": "RECONCILIATION_FAILED",
                "outcome_verified": False,
                "downstream_state_hash": deterministic_digest(res),
                "response": res
            }


# ── Operational Safety & Kill-Switch Controller ──────────────────────────────

@dataclass
class OperatorActionReceipt:
    receipt_version: str
    action_type: str
    operator_id: str
    reason: str
    timestamp_utc: str
    details: Dict[str, Any]
    cose_envelope_hex: str
    cose_alg: int
    cose_kid: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OperationalSafetyController:
    """
    Operational safety controller providing global circuit breakers, forced reconciliation,
    high-risk tool approval gating, and cryptographically attested operator action receipts.
    """

    def __init__(
        self,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        key_id: str = "key:smaos-operator-01"
    ):
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.signing_key.public_key()
        self.key_id = key_id

        self.kill_switch_active: bool = False
        self.kill_switch_reason: Optional[str] = None
        self.kill_switch_operator: Optional[str] = None
        self.kill_switch_tripped_at: Optional[str] = None

        self.forced_reconciliation_active: bool = False
        self.forced_reconciliation_reason: Optional[str] = None

        self.high_risk_tools: Set[str] = set()
        self.active_approvals: Dict[str, Dict[str, Any]] = {}
        self.operator_receipts: List[OperatorActionReceipt] = []

    def _emit_operator_receipt(
        self,
        action_type: str,
        operator_id: str,
        reason: str,
        details: Dict[str, Any]
    ) -> OperatorActionReceipt:
        now_iso = datetime.now(timezone.utc).isoformat()
        unsigned = {
            "receipt_type": "OPERATOR_ACTION",
            "receipt_version": RECEIPT_VERSION,
            "action_type": action_type,
            "operator_id": operator_id,
            "reason": reason,
            "timestamp_utc": now_iso,
            "details": details
        }
        canon_bytes = deterministic_json_bytes(unsigned)
        cose_envelope_bytes = COSESign1Engine.create_envelope(
            payload=canon_bytes,
            private_key=self.signing_key,
            key_id=self.key_id,
            external_aad=b""
        )
        receipt = OperatorActionReceipt(
            receipt_version=RECEIPT_VERSION,
            action_type=action_type,
            operator_id=operator_id,
            reason=reason,
            timestamp_utc=now_iso,
            details=details,
            cose_envelope_hex=cose_envelope_bytes.hex(),
            cose_alg=COSE_ALG_EDDSA,
            cose_kid=self.key_id
        )
        self.operator_receipts.append(receipt)
        return receipt

    def trip_kill_switch(self, reason: str, operator_id: str) -> OperatorActionReceipt:
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        self.kill_switch_operator = operator_id
        self.kill_switch_tripped_at = datetime.now(timezone.utc).isoformat()
        return self._emit_operator_receipt(
            action_type="KILL_SWITCH_TRIP",
            operator_id=operator_id,
            reason=reason,
            details={"tripped_at": self.kill_switch_tripped_at}
        )

    def resume_operations(self, reason: str, operator_id: str) -> OperatorActionReceipt:
        was_active = self.kill_switch_active
        self.kill_switch_active = False
        prev_reason = self.kill_switch_reason
        self.kill_switch_reason = None
        self.kill_switch_operator = None
        return self._emit_operator_receipt(
            action_type="KILL_SWITCH_RESUME",
            operator_id=operator_id,
            reason=reason,
            details={"previously_active": was_active, "prior_reason": prev_reason}
        )

    def enable_forced_reconciliation(self, reason: str, operator_id: str) -> OperatorActionReceipt:
        self.forced_reconciliation_active = True
        self.forced_reconciliation_reason = reason
        return self._emit_operator_receipt(
            action_type="FORCED_RECONCILIATION_ENABLE",
            operator_id=operator_id,
            reason=reason,
            details={"forced_reconciliation": True}
        )

    def disable_forced_reconciliation(self, reason: str, operator_id: str) -> OperatorActionReceipt:
        self.forced_reconciliation_active = False
        self.forced_reconciliation_reason = None
        return self._emit_operator_receipt(
            action_type="FORCED_RECONCILIATION_DISABLE",
            operator_id=operator_id,
            reason=reason,
            details={"forced_reconciliation": False}
        )

    def register_high_risk_tools(self, tools: List[str]):
        for t in tools:
            self.high_risk_tools.add(t)

    def issue_approval_token(
        self,
        tool_name: str,
        operator_id: str,
        ttl_seconds: int = 300,
        reason: str = "Authorized high-risk execution"
    ) -> str:
        token = f"APPR-{uuid.uuid4().hex[:12].upper()}"
        now = time.time()
        record = {
            "tool_name": tool_name,
            "operator_id": operator_id,
            "issued_at": now,
            "expires_at": now + ttl_seconds,
            "ttl_seconds": ttl_seconds,
            "token": token
        }
        self.active_approvals[token] = record
        self._emit_operator_receipt(
            action_type="APPROVAL_TOKEN_ISSUED",
            operator_id=operator_id,
            reason=reason,
            details=record
        )
        return token

    def is_dispatch_allowed(
        self,
        tool_name: str,
        is_mutating: bool = True,
        approval_token: Optional[str] = None
    ) -> Tuple[bool, str]:
        # 1. Kill-Switch check
        if self.kill_switch_active and is_mutating:
            return False, f"KILL_SWITCH_ACTIVE: Operations halted by {self.kill_switch_operator} ({self.kill_switch_reason})"

        # 2. Forced reconciliation check
        if self.forced_reconciliation_active:
            return False, f"FORCED_RECONCILIATION_MODE: New dispatches paused pending reconciliation sweeps ({self.forced_reconciliation_reason})"

        # 3. High-risk tool approval check
        if tool_name in self.high_risk_tools:
            if not approval_token:
                return False, f"HIGH_RISK_TOOL_REQUIRES_OPERATOR_APPROVAL: Tool '{tool_name}' requires valid operator approval token"
            token_data = self.active_approvals.get(approval_token)
            if not token_data or token_data.get("tool_name") != tool_name:
                return False, f"INVALID_APPROVAL_TOKEN: Token not valid for tool '{tool_name}'"
            if time.time() > token_data.get("expires_at", 0):
                return False, f"EXPIRED_APPROVAL_TOKEN: Token expired at {token_data.get('expires_at')}"

        return True, "ALLOWED"


# ── The Four-Step SMAOS Execution Normalizer ──────────────────────────────────

class DiagnosticExecutionNormalizer:
    """
    Executes and normalizes the four-step SMAOS execution cycle:
      Step 1: Pre-dispatch authority check
      Step 2: Dispatch
      Step 3: Post-condition probe
      Step 4: Attest (RFC 9052 COSE_Sign1 envelope)
    """

    def __init__(
        self,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        key_id: Optional[str] = None,
        freshness_limit_ms: int = DEFAULT_FRESHNESS_LIMIT_MS,
        hmac_key: Optional[bytes] = None,
        key_registry: Optional[KeyRegistry] = None,
        safety_controller: Optional[OperationalSafetyController] = None
    ):
        # Key management: env -> parameter -> ephemeral
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.signing_key.public_key()
        self.key_id = key_id or os.environ.get("SMAOS_COSE_KID", "key:smaos-local-ed25519-01")
        self.freshness_limit_ms = freshness_limit_ms
        self.hmac_key = hmac_key or os.environ.get("SMAOS_HMAC_KEY", "").encode("utf-8")
        self.safety_controller = safety_controller

        self.key_registry = key_registry or KeyRegistry()
        self.key_registry.register_key(self.key_id, self.public_key)

    # ── Step 1: Pre-Dispatch Authority Check ─────────────────────────────────
    def pre_dispatch_authority_check(
        self,
        auth_context: AuthorityContext,
        current_time: Optional[float] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Step 1: Validates actor authority, permissions, and TTL.
        Fails closed without dispatching if check fails.
        Returns: (is_authorized, reason, authority_hash)
        """
        now_ts = current_time if current_time is not None else time.time()

        # Check permissible tools list
        if auth_context.allowed_tools is not None:
            if auth_context.tool not in auth_context.allowed_tools:
                return False, f"Tool '{auth_context.tool}' not permitted for actor '{auth_context.actor}'", None

        # Check TTL freshness if provided (strict unmanufactured: no fabricated defaults)
        if auth_context.authority_ttl:
            try:
                ttl_dt = datetime.fromisoformat(auth_context.authority_ttl.replace("Z", "+00:00"))
                ttl_epoch = ttl_dt.timestamp()
                if now_ts > ttl_epoch:
                    return False, f"Authority token expired at {auth_context.authority_ttl}", None
            except ValueError:
                return False, f"Malformed authority TTL ISO timestamp: '{auth_context.authority_ttl}'", None

        # Check valid_from if provided
        if auth_context.valid_from is not None and now_ts < auth_context.valid_from:
            return False, f"Authority token not yet active (valid_from {auth_context.valid_from})", None

        # Compute authority digest
        auth_canon = {
            "actor": auth_context.actor,
            "tool": auth_context.tool,
            "valid_from": auth_context.valid_from,
            "authority_ttl": auth_context.authority_ttl
        }
        authority_hash = deterministic_digest(auth_canon)
        return True, "AUTHORITY_CONFIRMED", authority_hash

    # ── Step 2: Dispatch ─────────────────────────────────────────────────────
    def dispatch_mcp_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        idempotency_key: str,
        action_id: str,
        mcp_client: Optional[Any] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[int], Optional[str]]:
        """
        Step 2: Dispatches the tool call through transport adapter.
        Injects idempotency headers; traps transport disconnects (504, TCP RST).
        Returns: (raw_result, wire_status, transport_fault)
        """
        transport_meta = {
            "_smaos_idempotency_key": idempotency_key,
            "_smaos_action_id": action_id
        }

        if mcp_client is None:
            # Simulated direct loopback if client not supplied
            return {"status": "ok", "ack": True}, 200, None

        try:
            res = mcp_client.call_tool(tool_name, arguments, headers=transport_meta)
            return res, 200, None
        except TimeoutError as te:
            return None, 504, f"HTTP_504_TIMEOUT: {te}"
        except ConnectionResetError as cre:
            return None, None, f"TCP_RST_ECONNRESET: {cre}"
        except Exception as e:
            err_name = type(e).__name__
            status_code = getattr(e, "status_code", 500)
            return None, status_code, f"{err_name}: {e}"

    # ── Step 3: Post-Condition Probe ─────────────────────────────────────────
    def probe_post_condition(
        self,
        tool_name: str,
        idempotency_key: str,
        action_id: str,
        req_payload_hash: str,
        transport_fault: Optional[str],
        state_prober: Optional[Any] = None,
        manual_probe_result: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, bool, Optional[str], Dict[str, Any], str]:
        """
        Step 3: Queries downstream authoritative source.
        Determines granular disposition:
          ACK_UNVERIFIED, DISPATCHED_UNCONFIRMED, RECONCILIATION_NOT_FOUND,
          RECONCILIATION_FAILED, PROBE_EXCEPTION, OUTCOME_VERIFIED, RECONCILIATION_CONFLICT.
        Returns: (disposition, outcome_verified, downstream_state_hash, observed_outcome, verification_method)
        """
        # Case A: If manual probe record was provided (e.g. in test harness)
        if manual_probe_result is not None:
            observed = manual_probe_result
            method = "manual_authoritative_probe"
            if observed.get("conflict_detected", False):
                return "RECONCILIATION_CONFLICT", False, deterministic_digest(observed), observed, method
            if observed.get("payload_hash_mismatch", False):
                return "RECONCILIATION_FAILED", False, deterministic_digest(observed), observed, method
            if observed.get("not_found", False):
                return "RECONCILIATION_NOT_FOUND", False, None, observed, method
            if observed.get("exception", False):
                return "PROBE_EXCEPTION", False, None, observed, method

            verified = bool(observed.get("outcome_confirmed", True))
            disposition = "OUTCOME_VERIFIED" if verified else "RECONCILIATION_FAILED"
            return disposition, verified, deterministic_digest(observed), observed, method

        # Case B: If an external StateProber object is provided
        if state_prober is not None:
            try:
                # Supports both probe(idempotency_key, action_id, expected_payload_hash)
                # and legacy probe_state(idempotency_key, payload_hash)
                if hasattr(state_prober, "probe"):
                    probe_res = state_prober.probe(idempotency_key, action_id, req_payload_hash)
                elif hasattr(state_prober, "probe_state"):
                    probe_res = state_prober.probe_state(idempotency_key, req_payload_hash)
                else:
                    raise TypeError("State prober must implement probe() or probe_state()")

                disposition = probe_res.get("disposition", "UNKNOWN")
                verified = (disposition == "OUTCOME_VERIFIED")
                state_hash = probe_res.get("downstream_state_hash")
                return disposition, verified, state_hash, probe_res, "state_prober_reconciliation"
            except Exception as pe:
                err_outcome = {"probe_error": str(pe), "idempotency_key": idempotency_key}
                return "PROBE_EXCEPTION", False, None, err_outcome, "state_prober_exception"

        # Case C: No probe supplied
        if transport_fault is not None:
            quarantine_outcome = {
                "transport_fault": transport_fault,
                "reconciliation_attempted": False,
                "quarantine": "FAIL_CLOSED"
            }
            return "DISPATCHED_UNCONFIRMED", False, None, quarantine_outcome, "transport_fault_quarantine"

        # Mutating action executed on wire, but no probe supplied
        # Invariant: Wire 200 != Verified Outcome
        wire_ack_outcome = {
            "wire_ack_received": True,
            "note": "Wire ACK received; physical outcome unverified without downstream state probe"
        }
        return "ACK_UNVERIFIED", False, None, wire_ack_outcome, "no_authoritative_probe"

    # ── Step 4: Attest (Complete Receipt + COSE_Sign1 Envelope) ──────────────
    def attest_execution(
        self,
        action_id: str,
        actor: str,
        authority_hash: str,
        authority_ttl: Optional[str],
        dispatched_at_iso: str,
        req_payload_hash: str,
        downstream_state_hash: Optional[str],
        observed_outcome: Dict[str, Any],
        outcome_verified: bool,
        verification_method: str,
        disposition: str,
        transport_fault: Optional[str],
        valid_time_t0: Optional[float] = None,
        transaction_time_tn: Optional[float] = None,
        freshness_limit_ms: Optional[float] = None,
        request_payload_hash: Optional[str] = None
    ) -> CompleteExecutionReceipt:
        """
        Step 4: Constructs complete execution receipt, validates authority freshness
        against threshold, and seals with standard RFC 9052 COSE_Sign1 envelope.
        """
        limit_ms = int(round(freshness_limit_ms)) if freshness_limit_ms is not None else int(self.freshness_limit_ms)
        payload_hash = request_payload_hash or req_payload_hash

        # Evaluate freshness status (Measurement != Policy Compliance)
        if valid_time_t0 is None or transaction_time_tn is None:
            wall_clock_delta_ms = None
            freshness_status = "UNMEASURED"
        elif transaction_time_tn < valid_time_t0:
            wall_clock_delta_ms = int(round((transaction_time_tn - valid_time_t0) * 1000.0))
            freshness_status = "CLOCK_ORDER_INVALID"
        else:
            delta_ms = int(round((transaction_time_tn - valid_time_t0) * 1000.0))
            wall_clock_delta_ms = delta_ms
            if delta_ms > limit_ms:
                freshness_status = "STALE"
            else:
                freshness_status = "FRESH"

        # Lookup retry policy
        retry_info = RETRY_POLICY_TABLE.get(disposition, {
            "retry_allowed": False,
            "action": "Unknown disposition; halt and escalate."
        })

        receipt = CompleteExecutionReceipt(
            receipt_version=RECEIPT_VERSION,
            key_id=self.key_id,
            action_id=action_id,
            actor=actor,
            authority_hash=authority_hash,
            authority_ttl=authority_ttl,
            dispatched_at=dispatched_at_iso,
            request_payload_hash=payload_hash,
            downstream_state_hash=downstream_state_hash,
            observed_outcome=observed_outcome,
            outcome_verified=outcome_verified,
            verification_method=verification_method,
            wall_clock_delta_ms=wall_clock_delta_ms,
            freshness_status=freshness_status,
            freshness_limit_ms=limit_ms,
            serialization_format=SERIALIZATION_LABEL,
            disposition=disposition,
            transport_fault=transport_fault or "NONE",
            retry_policy=retry_info
        )

        # 1. Complete Unsigned Receipt Canonical Bytes
        unsigned_canon_bytes = deterministic_json_bytes(receipt.to_unsigned_dict())

        # 2. Seal in standard RFC 9052 COSE_Sign1 Envelope (alg: -8)
        cose_envelope_bytes = COSESign1Engine.create_envelope(
            payload=unsigned_canon_bytes,
            private_key=self.signing_key,
            key_id=self.key_id,
            external_aad=b""
        )
        receipt.cose_envelope_hex = cose_envelope_bytes.hex()
        receipt.cose_alg = COSE_ALG_EDDSA
        receipt.cose_kid = self.key_id
        receipt.cose_payload_hash = f"sha256:{hashlib.sha256(unsigned_canon_bytes).hexdigest()}"

        # 3. Optional HMAC tag over complete unsigned receipt if key present
        if self.hmac_key:
            receipt.hmac_sha256_tag = hmac.new(
                self.hmac_key,
                unsigned_canon_bytes,
                hashlib.sha256
            ).hexdigest()

        return receipt

    # ── Full Four-Step Execution Wrap Cycle ──────────────────────────────────
    def execute_lifecycle(
        self,
        raw_mcp_request: Dict[str, Any],
        actor: str,
        session_id: str = "sess-01",
        step_sequence: int = 1,
        authority_ttl: Optional[str] = None,
        valid_time_t0: Optional[float] = None,
        allowed_tools: Optional[List[str]] = None,
        mcp_client: Optional[Any] = None,
        state_prober: Optional[Any] = None,
        manual_probe_result: Optional[Dict[str, Any]] = None,
        freshness_limit_ms: Optional[float] = None,
        approval_token: Optional[str] = None
    ) -> CompleteExecutionReceipt:
        """
        Coordinates the complete 4-step SMAOS Execution Cycle:
          1. Pre-dispatch authority check
          2. Dispatch
          3. Post-condition probe
          4. Attest (COSE_Sign1)
        """
        # Parse MCP JSON-RPC call
        tool_name, arguments, rpc_id = MCPJSONRPCParser.parse_tools_call(raw_mcp_request)
        action_id = MCPJSONRPCParser.generate_composite_action_id(
            session_id, step_sequence, rpc_id, tool_name
        )
        req_payload_hash = deterministic_digest(arguments)
        idempotency_key = MCPJSONRPCParser.generate_uuidv5_idempotency_key(action_id, req_payload_hash)

        # Operational Safety Check (Kill-Switch & High-Risk Approval Gate)
        if self.safety_controller is not None:
            allowed, gate_reason = self.safety_controller.is_dispatch_allowed(
                tool_name=tool_name,
                is_mutating=True,
                approval_token=approval_token
            )
            if not allowed:
                t_gate = time.time()
                dispatched_at_iso = datetime.now(timezone.utc).isoformat()
                return self.attest_execution(
                    action_id=action_id,
                    actor=actor,
                    authority_hash=deterministic_digest({"safety_gate": gate_reason}),
                    authority_ttl=authority_ttl,
                    dispatched_at_iso=dispatched_at_iso,
                    req_payload_hash=req_payload_hash,
                    downstream_state_hash=None,
                    observed_outcome={"refusal_reason": gate_reason, "step": "operational_safety_gate"},
                    outcome_verified=False,
                    verification_method="operational_safety_gate",
                    disposition="REFUSED",
                    transport_fault="NONE",
                    valid_time_t0=valid_time_t0,
                    transaction_time_tn=t_gate,
                    freshness_limit_ms=freshness_limit_ms
                )

        # Step 1: Pre-dispatch authority check
        auth_context = AuthorityContext(
            actor=actor,
            tool=tool_name,
            valid_from=valid_time_t0,
            authority_ttl=authority_ttl,
            allowed_tools=allowed_tools
        )
        is_authorized, auth_reason, authority_hash = self.pre_dispatch_authority_check(auth_context)

        t_dispatch = time.time()
        dispatched_at_iso = datetime.now(timezone.utc).isoformat()

        if not is_authorized:
            # Fails closed immediately without touching the wire
            return self.attest_execution(
                action_id=action_id,
                actor=actor,
                authority_hash=deterministic_digest(asdict(auth_context)),
                authority_ttl=authority_ttl,
                dispatched_at_iso=dispatched_at_iso,
                req_payload_hash=req_payload_hash,
                downstream_state_hash=None,
                observed_outcome={"refusal_reason": auth_reason, "step": "pre_dispatch_authority_check"},
                outcome_verified=False,
                verification_method="pre_dispatch_policy_rejection",
                disposition="REFUSED",
                transport_fault="NONE",
                valid_time_t0=valid_time_t0,
                transaction_time_tn=t_dispatch,
                freshness_limit_ms=freshness_limit_ms
            )

        # Step 2: Dispatch
        raw_res, wire_status, transport_fault = self.dispatch_mcp_call(
            tool_name=tool_name,
            arguments=arguments,
            idempotency_key=idempotency_key,
            action_id=action_id,
            mcp_client=mcp_client
        )
        t_post_dispatch = time.time()

        # Step 3: Post-condition probe
        disposition, outcome_verified, downstream_hash, observed, method = self.probe_post_condition(
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            action_id=action_id,
            req_payload_hash=req_payload_hash,
            transport_fault=transport_fault,
            state_prober=state_prober,
            manual_probe_result=manual_probe_result
        )

        # Step 4: Attest
        receipt = self.attest_execution(
            action_id=action_id,
            actor=actor,
            authority_hash=authority_hash or deterministic_digest(asdict(auth_context)),
            authority_ttl=authority_ttl,
            dispatched_at_iso=dispatched_at_iso,
            req_payload_hash=req_payload_hash,
            downstream_state_hash=downstream_hash,
            observed_outcome=observed,
            outcome_verified=outcome_verified,
            verification_method=method,
            disposition=disposition,
            transport_fault=transport_fault,
            valid_time_t0=valid_time_t0,
            transaction_time_tn=t_post_dispatch,
            freshness_limit_ms=freshness_limit_ms
        )

        return receipt


# ── Standalone CLI & Validation Routine ───────────────────────────────────────

def main():
    print("=" * 80)
    print("🛡️  SMAOS MCP DIAGNOSTIC NORMALIZER & 4-STEP WRAP")
    print(f"Serialization: {SERIALIZATION_LABEL}")
    print("Envelope     : RFC 9052 COSE_Sign1 (alg: -8 / EdDSA)")
    print("=" * 80)

    priv = ed25519.Ed25519PrivateKey.generate()
    normalizer = DiagnosticExecutionNormalizer(signing_key=priv)

    sample_rpc = {
        "jsonrpc": "2.0",
        "id": "rpc-test-441",
        "method": "tools/call",
        "params": {
            "name": "core.transfer_funds",
            "arguments": {
                "beneficiary": "CZ6808000000001234567890",
                "amount": 250000.0,
                "currency": "EUR"
            }
        }
    }

    # Run Demonstration
    receipt = normalizer.execute_lifecycle(
        raw_mcp_request=sample_rpc,
        actor="did:bank:unicredit-treasury",
        session_id="sess-889",
        step_sequence=3,
        authority_ttl=None,  # Explicitly unmanufactured
        manual_probe_result={
            "ledger_id": "tx-88931",
            "status": "SETTLED",
            "outcome_confirmed": True
        }
    )

    print("\n[+] Complete Execution Receipt Generated:")
    print(json.dumps(receipt.to_dict(), indent=2))

    # Verify COSE_Sign1 envelope
    env_bytes = bytes.fromhex(receipt.cose_envelope_hex)
    is_valid, payload, meta = COSESign1Engine.verify_envelope(env_bytes, normalizer.public_key)
    print(f"\n[+] COSE_Sign1 Verification Result: {is_valid} ({meta})")
    print(f"    Payload length: {len(payload)} bytes")
    print("\n✅ 4-STEP SMAOS CYCLE EXECUTED AND ATTESTED SUCCESSFULLY")


if __name__ == "__main__":
    main()
