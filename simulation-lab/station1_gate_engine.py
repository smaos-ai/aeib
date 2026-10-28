# Copyright 2026 SovereignNexus Project
#
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
simulation-lab/station1_gate_engine.py — Station 1 Gatekeeper Engine for Verifiable Agent Fabric.

Implements deterministic evaluation of candidate Acts against:
1. Canonical JSON Schema constraints (additionalProperties: false).
2. Strict path containment (defeating CVE-2025-53110 / CVE-2026-43901).
3. Monotonic taint lattice (TIER_0 <= TIER_1 <= TIER_2).
4. Content-Addressed Action Identifier (CAID) computation via RFC 8785 JCS.
5. Dual-window budget conservation and durable uncertainty handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
ACTION_TYPE_REGEX = re.compile(r"^[a-z]+\.[a-z_]+$")
SHA256_PREFIX_REGEX = re.compile(r"^sha256:[a-f0-9]{64}$")
CURRENCY_REGEX = re.compile(r"^[A-Z]{3}$")


class Disposition(str, Enum):
    DISPATCHED = "DISPATCHED"
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
    NOT_DISPATCHED = "NOT_DISPATCHED"
    REJECTED = "REJECTED"


class TaintTier(str, Enum):
    TIER_0_PINNED = "TIER_0_PINNED"
    TIER_1_REVIEWED = "TIER_1_REVIEWED"
    TIER_2_UNTRUSTED = "TIER_2_UNTRUSTED"


TAINT_ORDER: Dict[str, int] = {
    TaintTier.TIER_0_PINNED.value: 0,
    TaintTier.TIER_1_REVIEWED.value: 1,
    TaintTier.TIER_2_UNTRUSTED.value: 2,
}


ALLOWED_ROOT_KEYS: Set[str] = {
    "act_version",
    "operation_id",
    "idempotency_key",
    "tenant_id",
    "principal",
    "action",
    "constraints",
    "context",
    "signature",
}

ALLOWED_PRINCIPAL_KEYS: Set[str] = {"agent_id", "subject_id", "capability_id"}
ALLOWED_ACTION_KEYS: Set[str] = {"type", "target", "resource", "parameters_digest"}
ALLOWED_CONSTRAINTS_KEYS: Set[str] = {"amount_minor", "currency", "max_per_call_minor", "policy_epoch", "expires_at"}
ALLOWED_CONTEXT_KEYS: Set[str] = {"harness_digest", "taint_tier", "source_trace_id"}
ALLOWED_SIGNATURE_KEYS: Set[str] = {"alg", "key_id", "value"}


def validate_schema_strict(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates payload against act.v1.json schema strictly in Python stdlib,
    enforcing additionalProperties: false and typed format invariants.
    """
    if not isinstance(payload, dict):
        return False, "ERR_SCHEMA_NOT_OBJECT"

    # Enforce root additionalProperties: false
    extra_root = set(payload.keys()) - ALLOWED_ROOT_KEYS
    if extra_root:
        return False, "ERR_SCHEMA_ADDITIONAL_PROPERTY"

    # Check all required root keys
    for req in ALLOWED_ROOT_KEYS:
        if req not in payload:
            return False, f"ERR_SCHEMA_MISSING_REQUIRED_{req.upper()}"

    # act_version
    if payload["act_version"] != "1":
        return False, "ERR_SCHEMA_INVALID_VERSION"

    # operation_id & idempotency_key
    if not isinstance(payload["operation_id"], str) or not UUID_REGEX.match(payload["operation_id"]):
        return False, "ERR_SCHEMA_INVALID_OPERATION_ID"
    if not isinstance(payload["idempotency_key"], str) or not UUID_REGEX.match(payload["idempotency_key"]):
        return False, "ERR_SCHEMA_INVALID_IDEMPOTENCY_KEY"

    # tenant_id
    if not isinstance(payload["tenant_id"], str) or len(payload["tenant_id"]) < 1:
        return False, "ERR_SCHEMA_INVALID_TENANT_ID"

    # principal
    pr = payload["principal"]
    if not isinstance(pr, dict):
        return False, "ERR_SCHEMA_INVALID_PRINCIPAL"
    if set(pr.keys()) - ALLOWED_PRINCIPAL_KEYS:
        return False, "ERR_SCHEMA_ADDITIONAL_PROPERTY"
    for k in ALLOWED_PRINCIPAL_KEYS:
        if not isinstance(pr.get(k), str) or len(pr[k]) < 1:
            return False, f"ERR_SCHEMA_INVALID_PRINCIPAL_{k.upper()}"

    # action
    act = payload["action"]
    if not isinstance(act, dict):
        return False, "ERR_SCHEMA_INVALID_ACTION"
    if set(act.keys()) - ALLOWED_ACTION_KEYS:
        return False, "ERR_SCHEMA_ADDITIONAL_PROPERTY"
    if not isinstance(act.get("type"), str) or not ACTION_TYPE_REGEX.match(act["type"]):
        return False, "ERR_SCHEMA_INVALID_ACTION_TYPE"
    if not isinstance(act.get("target"), str) or len(act["target"]) < 1:
        return False, "ERR_SCHEMA_INVALID_ACTION_TARGET"
    if not isinstance(act.get("resource"), str) or len(act["resource"]) < 1:
        return False, "ERR_SCHEMA_INVALID_ACTION_RESOURCE"
    if not isinstance(act.get("parameters_digest"), str) or not SHA256_PREFIX_REGEX.match(act["parameters_digest"]):
        return False, "ERR_SCHEMA_INVALID_ACTION_PARAMETERS_DIGEST"

    # constraints
    con = payload["constraints"]
    if not isinstance(con, dict):
        return False, "ERR_SCHEMA_INVALID_CONSTRAINTS"
    if set(con.keys()) - ALLOWED_CONSTRAINTS_KEYS:
        return False, "ERR_SCHEMA_ADDITIONAL_PROPERTY"
    if not isinstance(con.get("amount_minor"), int) or con["amount_minor"] < 1:
        return False, "ERR_SCHEMA_INVALID_AMOUNT_MINOR"
    if not isinstance(con.get("currency"), str) or not CURRENCY_REGEX.match(con["currency"]):
        return False, "ERR_SCHEMA_INVALID_CURRENCY"
    if not isinstance(con.get("max_per_call_minor"), int) or con["max_per_call_minor"] < 1:
        return False, "ERR_SCHEMA_INVALID_MAX_PER_CALL"
    if not isinstance(con.get("policy_epoch"), str) or len(con["policy_epoch"]) < 1:
        return False, "ERR_SCHEMA_INVALID_POLICY_EPOCH"
    if not isinstance(con.get("expires_at"), int) or con["expires_at"] < 1700000000:
        return False, "ERR_SCHEMA_INVALID_EXPIRES_AT"

    # context
    ctx = payload["context"]
    if not isinstance(ctx, dict):
        return False, "ERR_SCHEMA_INVALID_CONTEXT"
    if set(ctx.keys()) - ALLOWED_CONTEXT_KEYS:
        return False, "ERR_SCHEMA_ADDITIONAL_PROPERTY"
    if not isinstance(ctx.get("harness_digest"), str) or not SHA256_PREFIX_REGEX.match(ctx["harness_digest"]):
        return False, "ERR_SCHEMA_INVALID_HARNESS_DIGEST"
    if ctx.get("taint_tier") not in TAINT_ORDER:
        return False, "ERR_SCHEMA_INVALID_TAINT_TIER"
    if not isinstance(ctx.get("source_trace_id"), str) or len(ctx["source_trace_id"]) < 1:
        return False, "ERR_SCHEMA_INVALID_SOURCE_TRACE_ID"

    # signature
    sig = payload["signature"]
    if not isinstance(sig, dict):
        return False, "ERR_SCHEMA_INVALID_SIGNATURE"
    if set(sig.keys()) - ALLOWED_SIGNATURE_KEYS:
        return False, "ERR_SCHEMA_ADDITIONAL_PROPERTY"
    if sig.get("alg") not in ("Ed25519", "ML-DSA-65"):
        return False, "ERR_SCHEMA_INVALID_SIGNATURE_ALG"
    if not isinstance(sig.get("key_id"), str) or len(sig["key_id"]) < 1:
        return False, "ERR_SCHEMA_INVALID_KEY_ID"
    if not isinstance(sig.get("value"), str) or len(sig["value"]) < 1:
        return False, "ERR_SCHEMA_INVALID_SIGNATURE_VALUE"

    return True, "OK"


class AEIBStation1Gate:
    """
    Station 1 Pre-Dispatch Gatekeeper:
    The last trustworthy checkpoint before real-world effectuation.
    """

    def __init__(
        self,
        allowed_export_dirs: Optional[List[str]] = None,
        registered_public_keys: Optional[Dict[str, bytes]] = None,
        sprint_budget_ceiling_minor: int = 500_000,
    ):
        self.allowed_export_dirs = [
            str(Path(d).resolve()) for d in (allowed_export_dirs or ["/var/aeib/export", "/tmp/aeib_export"])
        ]
        self.registered_public_keys = registered_public_keys or {}
        self.sprint_budget_ceiling_minor = sprint_budget_ceiling_minor
        self.committed_spend_minor = 0
        self.escrowed_spend_minor = 0
        self.seen_idempotency_keys: Dict[str, Dict[str, Any]] = {}
        self.seen_caids: Set[str] = set()

    def check_path_containment(self, candidate_path: str) -> bool:
        """
        Canonically resolves candidate_path and verifies it resides inside an allowed directory.
        Rejects dot-dot-slash traversal, relative escapes, and unauthorized directory queries.
        Defeats CVE-2025-53110 and CVE-2026-43901.
        """
        try:
            resolved = Path(candidate_path).resolve()
            resolved_str = str(resolved)
            for allowed in self.allowed_export_dirs:
                allowed_path = Path(allowed).resolve()
                if resolved == allowed_path or allowed_path in resolved.parents:
                    return True
            return False
        except Exception:
            return False

    def evaluate_raw_payload(self, raw_bytes: bytes) -> Dict[str, Any]:
        """
        Evaluates a raw byte wire frame against schema, path containment, and budget invariants.
        Returns a structured disposition report.
        """
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except Exception:
            return {
                "disposition": Disposition.NOT_DISPATCHED.value,
                "error_code": "ERR_MALFORMED_JSON",
                "reason": "Wire frame is not valid UTF-8 JSON",
            }

        # Check for path traversal injection in action block or payload
        action_dict = payload.get("action", {})
        if isinstance(action_dict, dict):
            # Check for path traversal attempts like dest_dir or export_path
            for path_key in ("dest_dir", "export_path", "target_path", "file_path"):
                if path_key in action_dict:
                    dest = action_dict[path_key]
                    if not self.check_path_containment(dest):
                        return {
                            "disposition": Disposition.NOT_DISPATCHED.value,
                            "error_code": "ERR_PATH_TRAVERSAL_DENIED",
                            "reason": f"Path traversal rejected: '{dest}' is outside allowed directories",
                        }

        # Strict Schema Validation
        is_valid, err_code = validate_schema_strict(payload)
        if not is_valid:
            return {
                "disposition": Disposition.NOT_DISPATCHED.value,
                "error_code": err_code,
                "reason": f"Schema rejection: {err_code}",
            }

        # Dual-Window Budget Check
        amount_minor = payload["constraints"]["amount_minor"]
        max_per_call = payload["constraints"]["max_per_call_minor"]

        if amount_minor > max_per_call:
            return {
                "disposition": Disposition.NOT_DISPATCHED.value,
                "error_code": "ERR_EXCEEDS_MAX_PER_CALL",
                "reason": f"Amount {amount_minor} exceeds max_per_call {max_per_call}",
            }

        if self.committed_spend_minor + self.escrowed_spend_minor + amount_minor > self.sprint_budget_ceiling_minor:
            return {
                "disposition": Disposition.NOT_DISPATCHED.value,
                "error_code": "ERR_SPRINT_BUDGET_EXCEEDED",
                "reason": "Cumulative spend exceeds sprint ceiling",
            }

        # Monotonic Taint Enforcer
        taint = payload["context"]["taint_tier"]
        if taint == TaintTier.TIER_2_UNTRUSTED.value and amount_minor > 50_000:
            # Untrusted model attempting high-value spend without step-up
            return {
                "disposition": Disposition.NOT_DISPATCHED.value,
                "error_code": "ERR_UNTRUSTED_TAINT_REQUIRES_STEP_UP",
                "reason": "TIER_2_UNTRUSTED cannot execute mutations > 500.00 minor units without step-up",
            }

        # Cryptographic Signature Verification (if key registered)
        key_id = payload["signature"]["key_id"]
        if key_id in self.registered_public_keys:
            pub_raw = self.registered_public_keys[key_id]
            pub_key = Ed25519PublicKey.from_public_bytes(pub_raw)
            sig_val = payload["signature"]["value"]
            try:
                sig_bytes = bytes.fromhex(sig_val)
                # Compute canonical bytes without signature
                payload_copy = dict(payload)
                del payload_copy["signature"]
                canonical_bytes = encode_jcs(payload_copy)
                pub_key.verify(sig_bytes, canonical_bytes)
            except Exception:
                return {
                    "disposition": Disposition.NOT_DISPATCHED.value,
                    "error_code": "ERR_INVALID_SIGNATURE",
                    "reason": "Cryptographic signature verification failed",
                }

        # Idempotency Key Handling
        idem_key = payload["idempotency_key"]
        if idem_key in self.seen_idempotency_keys:
            prior = self.seen_idempotency_keys[idem_key]
            return {
                "disposition": prior["disposition"],
                "caid": prior["caid"],
                "error_code": "IDEMPOTENT_REPLAY",
                "reason": "Idempotency key previously recorded",
                "is_replay": True,
            }

        # Compute CAID over RFC 8785 canonical bytes
        canonical_full_bytes = encode_jcs(payload)
        caid = "sha256:" + hashlib.sha256(canonical_full_bytes).hexdigest()

        # Hold budget in escrow
        self.escrowed_spend_minor += amount_minor
        op_record = {
            "disposition": Disposition.DISPATCHED.value,
            "caid": caid,
            "operation_id": payload["operation_id"],
            "idempotency_key": idem_key,
            "amount_minor": amount_minor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.seen_idempotency_keys[idem_key] = op_record
        self.seen_caids.add(caid)

        return {
            "disposition": Disposition.DISPATCHED.value,
            "caid": caid,
            "operation_id": payload["operation_id"],
            "escrowed_minor": amount_minor,
            "status_code": 200,
            "error_code": None,
        }
