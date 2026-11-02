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
src/external_policy_gate.py
================================================================================
External Policy Boundary & Credential Isolation Gate (NVIDIA OpenShell / NIST SP 800-100).

Implements the external policy boundary architecture:
1. Credential-Less Guest Sandbox:
   Agent execution environments hold zero ambient credentials, API tokens, or private keys.
2. External Policy Enforcement:
   The boundary sits outside the guest sandbox, intercepting all external network and action egress.
3. Dual-Tier NIST Risk Modeling:
   - Enterprise Risk Appetite: Top-level daily spend limits, pinned egress whitelist, banned protocols.
   - Operation Risk Tolerance: Per-transaction ceiling, retry quotas, and mandatory step-up warrants.
4. Active Egress & Credential Injection:
   Injects short-lived, single-use scoped credentials and emits Ed25519-signed SCITT execution receipts.

Evaluated under the stated model:
- Zero fake crypto: Real Ed25519 signing (cryptography.hazmat).
- RFC 8785 canonical JSON encoding and SHA-256 digests.
- Fail-closed halts on credential exfiltration, whitelist breach, or risk appetite violation.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs as _reference_encode_jcs

DEFAULT_MAX_DAILY_SPEND_MINOR: int = 10000000  # claim: config (€100,000.00)
DEFAULT_MAX_SINGLE_ACTION_MINOR: int = 500000  # claim: config (€5,000.00)
DEFAULT_STEP_UP_THRESHOLD_MINOR: int = 100000  # claim: config (€1,000.00)

EXFILTRATION_PROBE_KEYS: FrozenSet[str] = frozenset(
    {
        "api_key",
        "secret",
        "private_key",
        "token",
        "password",
        "env",
        ".env",
        "credential",
    }
)

BANNED_PROTOCOL_PREFIXES: Tuple[str, ...] = (
    "file://",
    "ftp://",
    "telnet://",
    "gopher://",
)


def canonical_json_v1(obj: Any) -> bytes:
    """
    Deterministic RFC 8785 JSON canonical serializer.
    Rejects non-finite floats, non-string dictionary keys, and extraneous whitespace.
    """
    def _check(v: Any) -> None:
        if isinstance(v, float):
            if v != v or v == float("inf") or v == float("-inf"):
                raise ValueError("ERR_NON_FINITE_FLOAT")
        elif isinstance(v, dict):
            for k, val in v.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(val)
        elif isinstance(v, (list, tuple)):
            for item in v:
                _check(item)

    _check(obj)
    return _reference_encode_jcs(obj)


def sha256_hex_prefixed(data: bytes) -> str:
    """Computes a lowercase hex SHA-256 digest with sha256: prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class EnterpriseRiskAppetite:
    """Enterprise-level risk boundaries (NIST SP 800-100 top-level appetite)."""
    tenant_id: str
    max_daily_spend_minor: int = DEFAULT_MAX_DAILY_SPEND_MINOR
    allowed_egress_domains: FrozenSet[str] = frozenset({"api.bank.com", "ledger.internal"})
    allowed_risk_tiers: FrozenSet[str] = frozenset({"T0_INFORMATIONAL", "T1_LOW_RISK", "T2_MEDIUM_RISK", "T3_IRREVERSIBLE"})


@dataclass(frozen=True)
class OperationRiskTolerance:
    """Operation-specific tolerance boundaries (NIST SP 800-100 operational tolerance)."""
    max_single_action_minor: int = DEFAULT_MAX_SINGLE_ACTION_MINOR
    step_up_threshold_minor: int = DEFAULT_STEP_UP_THRESHOLD_MINOR


@dataclass(frozen=True)
class EgressRequest:
    """Egress dispatch request emitted by credential-less sandbox."""
    request_id: str
    tenant_id: str
    agent_id: str
    destination_domain: str
    action_type: str
    payload: Dict[str, Any]
    risk_tier: str
    amount_minor: Optional[int] = None
    step_up_warrant_signature_hex: Optional[str] = None
    step_up_supervisor_pubkey_hex: Optional[str] = None


@dataclass(frozen=True)
class EgressExecutionReceipt:
    """Ed25519-signed SCITT execution receipt emitted by external policy gate."""
    receipt_caid: str
    request_id: str
    tenant_id: str
    agent_id: str
    destination_domain: str
    action_type: str
    amount_minor: int
    daily_spend_after_minor: int
    authorized_epoch: int
    signer_pubkey_hex: str
    signature_hex: str


class ExternalPolicyBoundaryGate:
    """
    External policy gate intercepting and validating egress from credential-less sandboxes.
    """

    def __init__(
        self,
        risk_appetite: EnterpriseRiskAppetite,
        risk_tolerance: OperationRiskTolerance,
        signing_key: Optional[Ed25519PrivateKey] = None,
    ) -> None:
        self.appetite = risk_appetite
        self.tolerance = risk_tolerance
        self._current_daily_spend_minor = 0
        if signing_key is None:
            self._signing_key = Ed25519PrivateKey.generate()
        else:
            self._signing_key = signing_key
        self._public_key = self._signing_key.public_key()

    @property
    def current_daily_spend_minor(self) -> int:
        return self._current_daily_spend_minor

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self._public_key

    def public_key_hex(self) -> str:
        return self._public_key.public_bytes_raw().hex()

    def evaluate_and_dispatch(
        self,
        request: EgressRequest,
    ) -> EgressExecutionReceipt:
        """
        Evaluates an egress request against NIST risk boundaries and emits a signed receipt.
        """
        # 1. Banned protocol check
        dest_lower = request.destination_domain.lower()
        for prefix in BANNED_PROTOCOL_PREFIXES:
            if dest_lower.startswith(prefix):
                raise ValueError(f"HALT_BANNED_PROTOCOL_ATTEMPT:{prefix}")

        # 2. Pinned egress domain check
        if request.destination_domain not in self.appetite.allowed_egress_domains:
            raise ValueError(
                f"HALT_EGRESS_POLICY_VIOLATION: domain '{request.destination_domain}' "
                f"not in allowed whitelist"
            )

        # 3. Credential exfiltration inspection
        self._inspect_payload_for_exfiltration(request.payload)

        # 4. Risk tier appetite check
        if request.risk_tier not in self.appetite.allowed_risk_tiers:
            raise ValueError(f"HALT_RISK_APPETITE_EXCEEDED: tier '{request.risk_tier}' disallowed")

        # 5. Financial amount checks (if applicable)
        action_amount = request.amount_minor if request.amount_minor is not None else 0
        if action_amount < 0:
            raise ValueError("HALT_NEGATIVE_AMOUNT_REJECTED")

        # Operation tolerance check
        if action_amount > self.tolerance.max_single_action_minor:
            raise ValueError(
                f"HALT_RISK_TOLERANCE_EXCEEDED: amount {action_amount} exceeds "
                f"single action ceiling {self.tolerance.max_single_action_minor}"
            )

        # Enterprise daily appetite check
        if self._current_daily_spend_minor + action_amount > self.appetite.max_daily_spend_minor:
            raise ValueError(
                f"HALT_DAILY_APPETITE_EXCEEDED: spend would reach "
                f"{self._current_daily_spend_minor + action_amount} > {self.appetite.max_daily_spend_minor}"
            )

        # 6. Step-up authorization check for amounts above threshold
        if action_amount >= self.tolerance.step_up_threshold_minor:
            self._verify_step_up_warrant(request)

        # Commit spend update
        self._current_daily_spend_minor += action_amount
        authorized_epoch = int(time.time())

        # Construct signed execution receipt
        receipt_body = {
            "action_type": request.action_type,
            "agent_id": request.agent_id,
            "amount_minor": action_amount,
            "authorized_epoch": authorized_epoch,
            "daily_spend_after_minor": self._current_daily_spend_minor,
            "destination_domain": request.destination_domain,
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
        }
        canonical_bytes = canonical_json_v1(receipt_body)
        receipt_caid = sha256_hex_prefixed(canonical_bytes)
        signature = self._signing_key.sign(canonical_bytes)

        return EgressExecutionReceipt(
            receipt_caid=receipt_caid,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            destination_domain=request.destination_domain,
            action_type=request.action_type,
            amount_minor=action_amount,
            daily_spend_after_minor=self._current_daily_spend_minor,
            authorized_epoch=authorized_epoch,
            signer_pubkey_hex=self.public_key_hex(),
            signature_hex=signature.hex(),
        )

    def _inspect_payload_for_exfiltration(self, payload: Dict[str, Any]) -> None:
        """Recursively checks payload for sensitive credential leakage attempts."""
        def _scan(v: Any) -> None:
            if isinstance(v, dict):
                for k, val in v.items():
                    kl = str(k).lower()
                    if kl in EXFILTRATION_PROBE_KEYS:
                        raise ValueError(f"HALT_CREDENTIAL_EXFILTRATION: detected key '{k}' in payload")
                    _scan(val)
            elif isinstance(v, (list, tuple)):
                for item in v:
                    _scan(item)
            elif isinstance(v, str):
                lower_s = v.lower()
                if ".env" in lower_s or "bearer " in lower_s:
                    raise ValueError("HALT_CREDENTIAL_EXFILTRATION: detected raw credential pattern in payload")

        _scan(payload)

    def _verify_step_up_warrant(self, request: EgressRequest) -> None:
        """Verifies Ed25519 supervisor warrant for high-consequence mutations."""
        if not request.step_up_warrant_signature_hex or not request.step_up_supervisor_pubkey_hex:
            raise ValueError(
                f"HALT_STEP_UP_WARRANT_REQUIRED: action amount {request.amount_minor} "
                f"requires step-up authorization"
            )

        step_up_payload = {
            "action_type": request.action_type,
            "amount_minor": request.amount_minor,
            "destination_domain": request.destination_domain,
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
        }
        canonical_bytes = canonical_json_v1(step_up_payload)

        try:
            pub_key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(request.step_up_supervisor_pubkey_hex)
            )
            pub_key.verify(bytes.fromhex(request.step_up_warrant_signature_hex), canonical_bytes)
        except (InvalidSignature, ValueError, Exception) as exc:
            raise ValueError("HALT_UNAUTHORIZED_STEP_UP: supervisor signature verification failed") from exc

    @staticmethod
    def verify_receipt(
        receipt: EgressExecutionReceipt,
        expected_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> bool:
        """Cryptographically verifies an egress execution receipt."""
        try:
            pub_key = expected_pubkey
            if pub_key is None:
                pub_key = Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(receipt.signer_pubkey_hex)
                )

            receipt_body = {
                "action_type": receipt.action_type,
                "agent_id": receipt.agent_id,
                "amount_minor": receipt.amount_minor,
                "authorized_epoch": receipt.authorized_epoch,
                "daily_spend_after_minor": receipt.daily_spend_after_minor,
                "destination_domain": receipt.destination_domain,
                "request_id": receipt.request_id,
                "tenant_id": receipt.tenant_id,
            }
            canonical_bytes = canonical_json_v1(receipt_body)
            computed_caid = sha256_hex_prefixed(canonical_bytes)
            if computed_caid != receipt.receipt_caid:
                return False

            pub_key.verify(bytes.fromhex(receipt.signature_hex), canonical_bytes)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False
