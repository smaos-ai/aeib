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
src/border_policy.py
================================================================================
Pure Predicate Engine for Default-Deny Border Policy, Bell-LaPadula Taint Lattice,
Payment Invariant Enforcement, and Warrant Verification.

Preserves strict epistemic lock and zero side-effects:
- Pure functions only; zero filesystem I/O, zero network, zero global state.
- RFC 8785 canonical JSON sorting and SHA-256 digest computation.
- Real Ed25519 asymmetric signature verification (zero fake crypto).
- Bell-LaPadula no-write-up: untrusted context (TIER_2) can never authorize
  mutations or payment-shaped parameters (even draft_payment).
- Cross-border payment limit checks apply uniformly across all payment-shaped actions.
- A2A #1857 cancel-state transition logic.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Dict, FrozenSet, Optional, Set

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


class TaintTier(IntEnum):
    TIER_0_SYSTEM = 0
    TIER_1_INTERNAL = 1
    TIER_2_UNTRUSTED_EXTERNAL = 2


class CancelledAtState(str, Enum):
    NONE = "none"
    BEFORE_START = "before_start"
    MID_TOOL_CALL = "mid_tool_call"
    POST_TOOL_CALL = "post_tool_call"


class TaskEscortState(str, Enum):
    READY = "READY"
    COMMITTED = "COMMITTED"
    DISPATCHED_UNCONFIRMED = "DISPATCHED_UNCONFIRMED"
    CANCELLED_CLEAN_BEFORE_START = "CANCELLED_CLEAN_BEFORE_START"


PAYMENT_SHAPED_KEYS: FrozenSet[str] = frozenset({
    "amount_minor",
    "currency",
    "recipient_id",
    "iban",
    "destination_account",
    "payee",
})


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
        elif isinstance(v, list):
            for item in v:
                _check(item)

    _check(obj)
    return _reference_encode_jcs(obj)


def sha256_hex_prefixed(data: bytes) -> str:
    """Computes a lowercase hex SHA-256 digest with sha256: prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def is_payment_shaped(args: Dict[str, Any]) -> bool:
    """Returns True if the arguments contain any financial or payment-routing key."""
    return bool(PAYMENT_SHAPED_KEYS & set(args.keys()))


def compute_action_caid(
    action_name: str,
    args: Dict[str, Any],
    tenant_id: str,
    agent_id: str,
) -> str:
    """
    Computes the content-addressed action identifier (CAID) over canonical RFC 8785 JCS.
    """
    payload = {
        "action_name": str(action_name),
        "agent_id": str(agent_id),
        "args": args,
        "tenant_id": str(tenant_id),
    }
    return sha256_hex_prefixed(canonical_json_v1(payload))


@dataclass(frozen=True)
class SignedHumanActionWarrant:
    warrant_id: str
    nonce: str
    tenant_id: str
    action_name: str
    action_caid: str
    expires_at_ns: int
    signature_b64: str

    def unsigned_dict(self) -> Dict[str, Any]:
        return {
            "action_caid": self.action_caid,
            "action_name": self.action_name,
            "expires_at_ns": self.expires_at_ns,
            "mandate_id": self.warrant_id,
            "nonce": self.nonce,
            "tenant_id": self.tenant_id,
        }

    def unsigned_bytes(self) -> bytes:
        return canonical_json_v1(self.unsigned_dict())

    def verify(self, public_key: Ed25519PublicKey) -> bool:
        if not self.signature_b64:
            return False
        try:
            raw_sig = base64.b64decode(self.signature_b64)
            public_key.verify(raw_sig, self.unsigned_bytes())
            return True
        except Exception:
            return False


def issue_human_warrant(
    warrant_id: str,
    nonce: str,
    tenant_id: str,
    action_name: str,
    action_caid: str,
    expires_at_ns: int,
    human_priv_key: Ed25519PrivateKey,
) -> SignedHumanActionWarrant:
    """Issues a cryptographically signed human authorization warrant."""
    unsigned = canonical_json_v1({
        "action_caid": action_caid,
        "action_name": action_name,
        "expires_at_ns": expires_at_ns,
        "mandate_id": warrant_id,
        "nonce": nonce,
        "tenant_id": tenant_id,
    })
    sig_b64 = base64.b64encode(human_priv_key.sign(unsigned)).decode("ascii")
    return SignedHumanActionWarrant(
        warrant_id=warrant_id,
        nonce=nonce,
        tenant_id=tenant_id,
        action_name=action_name,
        action_caid=action_caid,
        expires_at_ns=expires_at_ns,
        signature_b64=sig_b64,
    )


@dataclass(frozen=True)
class PolicyManifest:
    policy_version: str
    tenant_id: str
    agent_id: str
    allowed: FrozenSet[str]
    forbidden_without_human: FrozenSet[str]
    forbidden_always: FrozenSet[str]
    max_amount_minor_units: int
    allowed_currencies: FrozenSet[str]
    pinned_recipients: FrozenSet[str]


@dataclass(frozen=True)
class BorderVerdict:
    allowed: bool
    reason_code: str
    action_caid: str
    escort_state: TaskEscortState
    cancelled_at_state: CancelledAtState


def evaluate_taint_lattice(
    action_name: str,
    args: Dict[str, Any],
    policy: PolicyManifest,
    taint_tier: int,
) -> Optional[str]:
    """
    Bell-LaPadula no-write-up predicate.
    Untrusted external context (tier >= 2) can NEVER authorize mutating actions,
    payment-shaped parameters (even draft_payment), or unlisted capabilities.
    """
    mutating = (
        action_name in policy.forbidden_without_human
        or is_payment_shaped(args)
        or action_name not in policy.allowed
    )
    if mutating and taint_tier >= int(TaintTier.TIER_2_UNTRUSTED_EXTERNAL):
        return "HALT_UNTRUSTED_CONTEXT_CANNOT_AUTHORIZE_MUTATION"
    return None


def evaluate_payment_limits(
    action_name: str,
    args: Dict[str, Any],
    policy: PolicyManifest,
) -> Optional[str]:
    """
    Evaluates currency, amount, and recipient pinning across ALL payment-shaped actions
    (both draft_payment and execute_payment).
    """
    if not is_payment_shaped(args):
        return None

    amt = args.get("amount_minor")
    if isinstance(amt, bool) or not isinstance(amt, int) or amt <= 0 or amt > policy.max_amount_minor_units:
        return "HALT_PAYMENT_AMOUNT_OUT_OF_BOUNDS"

    curr = args.get("currency")
    if not isinstance(curr, str) or curr not in policy.allowed_currencies:
        return "HALT_PAYMENT_CURRENCY_NOT_ALLOWED"

    recip = args.get("recipient_id")
    if not isinstance(recip, str) or recip not in policy.pinned_recipients:
        return "HALT_PAYMENT_RECIPIENT_NOT_PINNED"

    return None


def evaluate_action_admissibility(
    action_name: str,
    args: Dict[str, Any],
    policy: PolicyManifest,
    now_ns: int,
    warrant: Optional[SignedHumanActionWarrant] = None,
    taint_tier: int = int(TaintTier.TIER_0_SYSTEM),
    burned_nonces: Optional[FrozenSet[str]] = None,
    human_pub_key: Optional[Ed25519PublicKey] = None,
    action_caid: Optional[str] = None,
) -> BorderVerdict:
    """
    Pure mathematical decision function for border admissibility.
    Evaluates policy constraints, taint bounds, payment invariants, and cryptographic warrants.
    """
    caid = action_caid or compute_action_caid(action_name, args, policy.tenant_id, policy.agent_id)

    # 1. forbidden_always check (absolute fail-closed)
    if action_name in policy.forbidden_always:
        return BorderVerdict(
            allowed=False,
            reason_code=f"HALT_FORBIDDEN_ALWAYS_CAPABILITY:{action_name}",
            action_caid=caid,
            escort_state=TaskEscortState.READY,
            cancelled_at_state=CancelledAtState.BEFORE_START,
        )

    # 2. Bell-LaPadula taint lattice check
    taint_err = evaluate_taint_lattice(action_name, args, policy, taint_tier)
    if taint_err is not None:
        return BorderVerdict(
            allowed=False,
            reason_code=taint_err,
            action_caid=caid,
            escort_state=TaskEscortState.READY,
            cancelled_at_state=CancelledAtState.BEFORE_START,
        )

    # 3. Cross-border payment limits check (applies to both draft and execute)
    limit_err = evaluate_payment_limits(action_name, args, policy)
    if limit_err is not None:
        return BorderVerdict(
            allowed=False,
            reason_code=limit_err,
            action_caid=caid,
            escort_state=TaskEscortState.READY,
            cancelled_at_state=CancelledAtState.BEFORE_START,
        )

    # 4. forbidden_without_human check (requires valid, unburned human warrant)
    if action_name in policy.forbidden_without_human:
        if warrant is None:
            return BorderVerdict(
                allowed=False,
                reason_code=f"HALT_HUMAN_WARRANT_REQUIRED:{action_name}",
                action_caid=caid,
                escort_state=TaskEscortState.READY,
                cancelled_at_state=CancelledAtState.BEFORE_START,
            )

        if burned_nonces and warrant.nonce in burned_nonces:
            return BorderVerdict(
                allowed=False,
                reason_code=f"HALT_WARRANT_NONCE_ALREADY_BURNED:{warrant.nonce}",
                action_caid=caid,
                escort_state=TaskEscortState.READY,
                cancelled_at_state=CancelledAtState.BEFORE_START,
            )

        if (
            warrant.action_caid != caid
            or warrant.action_name != action_name
            or warrant.tenant_id != policy.tenant_id
            or now_ns > warrant.expires_at_ns
        ):
            return BorderVerdict(
                allowed=False,
                reason_code="HALT_WARRANT_BINDING_OR_EXPIRY_INVALID",
                action_caid=caid,
                escort_state=TaskEscortState.READY,
                cancelled_at_state=CancelledAtState.BEFORE_START,
            )

        if human_pub_key is None or not warrant.verify(human_pub_key):
            return BorderVerdict(
                allowed=False,
                reason_code="HALT_WARRANT_SIGNATURE_INVALID",
                action_caid=caid,
                escort_state=TaskEscortState.READY,
                cancelled_at_state=CancelledAtState.BEFORE_START,
            )

    # 5. Default-Deny check: anything not explicitly listed in allowed is denied
    elif action_name not in policy.allowed:
        return BorderVerdict(
            allowed=False,
            reason_code=f"DENY_DEFAULT_BORDER_POLICY:{action_name}",
            action_caid=caid,
            escort_state=TaskEscortState.READY,
            cancelled_at_state=CancelledAtState.BEFORE_START,
        )

    # 6. Admissible
    return BorderVerdict(
        allowed=True,
        reason_code="OK_ADMISSIBLE",
        action_caid=caid,
        escort_state=TaskEscortState.READY,
        cancelled_at_state=CancelledAtState.NONE,
    )
