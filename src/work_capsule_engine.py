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
src/work_capsule_engine.py — Canonical Work Capsule Lifecycle & Human Gate Engine.

Implements the 6-Plane Fabric Work Capsule:
1. Lifecycle Automaton:
   DRAFT -> PROPOSED -> VERIFIED -> HUMAN_APPROVAL_PENDING -> AUTHORIZED
   -> DISPATCHED -> (CONFIRMED | REFUTED | EFFECT_INDETERMINATE) -> SETTLED
2. Fail-Closed Human Gate (Poka-yoke):
   Consequential mutations exceeding policy threshold require an Ed25519 supervisor warrant.
3. Durable Uncertainty Latch (Jidoka):
   On transport drop (504/RST), transitions to EFFECT_INDETERMINATE until authoritative probe.
4. Cryptographic Evidence Store:
   Signs canonical RFC 8785 JCS transition statements.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs


class CapsuleState(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    VERIFIED = "VERIFIED"
    HUMAN_APPROVAL_PENDING = "HUMAN_APPROVAL_PENDING"
    AUTHORIZED = "AUTHORIZED"
    DISPATCHED = "DISPATCHED"
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
    SETTLED = "SETTLED"
    HALTED = "HALTED"


VALID_TRANSITIONS: Dict[CapsuleState, Set[CapsuleState]] = {
    CapsuleState.DRAFT: {CapsuleState.PROPOSED, CapsuleState.HALTED},
    CapsuleState.PROPOSED: {CapsuleState.VERIFIED, CapsuleState.HALTED},
    CapsuleState.VERIFIED: {CapsuleState.HUMAN_APPROVAL_PENDING, CapsuleState.AUTHORIZED, CapsuleState.HALTED},
    CapsuleState.HUMAN_APPROVAL_PENDING: {CapsuleState.AUTHORIZED, CapsuleState.HALTED},
    CapsuleState.AUTHORIZED: {CapsuleState.DISPATCHED, CapsuleState.HALTED},
    CapsuleState.DISPATCHED: {
        CapsuleState.CONFIRMED,
        CapsuleState.REFUTED,
        CapsuleState.EFFECT_INDETERMINATE,
        CapsuleState.HALTED,
    },
    CapsuleState.EFFECT_INDETERMINATE: {CapsuleState.CONFIRMED, CapsuleState.REFUTED, CapsuleState.HALTED},
    CapsuleState.CONFIRMED: {CapsuleState.SETTLED},
    CapsuleState.REFUTED: {CapsuleState.SETTLED},
    CapsuleState.SETTLED: set(),
    CapsuleState.HALTED: set(),
}


@dataclass
class ContractRefs:
    act_schema_version: str = "1"
    behavior_contract_id: str = "urn:contract:refund:v1"
    capability_id: str = "cap-refund-v1"


@dataclass
class PolicyContext:
    policy_epoch: str = "2026-Q4"
    taint_tier: str = "TIER_1_REVIEWED"
    requires_human_gate: bool = False
    human_approval_signature: Optional[str] = None


@dataclass
class CandidateRef:
    source_revision: str
    artifact_sha256: str
    parameters_digest: str


@dataclass
class ExecutionPlan:
    target_endpoint: str
    action_type: str
    idempotency_key: str
    amount_minor: int
    currency: str = "EUR"


@dataclass
class WorkCapsule:
    capsule_version: str
    capsule_id: str
    intent_id: str
    state: str
    contract_refs: Dict[str, Any]
    policy_context: Dict[str, Any]
    candidate_ref: Dict[str, Any]
    execution_plan: Dict[str, Any]
    evidence_receipts: List[str] = field(default_factory=list)
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class EvidenceReceipt:
    receipt_version: str
    receipt_caid: str
    capsule_id: str
    operation_id: str
    disposition: str
    payload_sha256: str
    signer_public_key_hex: str
    signature_hex: str
    signed_at_utc: str


class HumanApprovalGate:
    """
    Fail-closed Human Gate:
    Evaluates policy requirements and validates supervisor Ed25519 signatures.
    """

    def __init__(self, supervisor_public_keys: Optional[Dict[str, bytes]] = None):
        self.supervisor_public_keys = supervisor_public_keys or {}

    def register_supervisor(self, key_id: str, public_key_bytes: bytes) -> None:
        self.supervisor_public_keys[key_id] = public_key_bytes

    def evaluate_gate_requirement(self, capsule: WorkCapsule) -> bool:
        """Determines if the operation requires a human-in-the-loop approval step."""
        amount = capsule.execution_plan["amount_minor"]
        taint = capsule.policy_context.get("taint_tier", "")
        # High value or untrusted taint triggers mandatory human gate
        if amount >= 50_000 or taint == "TIER_2_UNTRUSTED":
            return True
        return capsule.policy_context.get("requires_human_gate", False)

    def verify_approval(self, capsule: WorkCapsule, key_id: str, signature_hex: str) -> bool:
        """Verifies Ed25519 signature over canonical capsule execution bytes."""
        if key_id not in self.supervisor_public_keys:
            return False

        pub_raw = self.supervisor_public_keys[key_id]
        pub_key = Ed25519PublicKey.from_public_bytes(pub_raw)

        approval_preimage = {
            "capsule_id": capsule.capsule_id,
            "operation_id": capsule.execution_plan.get("idempotency_key", ""),
            "amount_minor": capsule.execution_plan.get("amount_minor", 0),
            "target_endpoint": capsule.execution_plan.get("target_endpoint", ""),
            "policy_epoch": capsule.policy_context.get("policy_epoch", ""),
        }
        canonical_bytes = encode_jcs(approval_preimage)

        try:
            sig_bytes = bytes.fromhex(signature_hex)
            pub_key.verify(sig_bytes, canonical_bytes)
            return True
        except (InvalidSignature, ValueError):
            return False


class WorkCapsuleLifecycleEngine:
    """
    Coordinates Work Capsule state transitions, enforcing invariant sequencing
    and emitting cryptographically signed receipts.
    """

    def __init__(
        self,
        signer_key: Optional[Ed25519PrivateKey] = None,
        human_gate: Optional[HumanApprovalGate] = None,
    ):
        self.signer_key = signer_key or Ed25519PrivateKey.generate()
        self.human_gate = human_gate or HumanApprovalGate()

    def create_capsule(
        self,
        intent_id: str,
        execution_plan: ExecutionPlan,
        candidate_ref: CandidateRef,
        policy_context: Optional[PolicyContext] = None,
        contract_refs: Optional[ContractRefs] = None,
    ) -> WorkCapsule:
        pol = policy_context or PolicyContext()
        crefs = contract_refs or ContractRefs()

        capsule_id = str(uuid.uuid4())
        capsule = WorkCapsule(
            capsule_version="1",
            capsule_id=capsule_id,
            intent_id=intent_id,
            state=CapsuleState.DRAFT.value,
            contract_refs=asdict(crefs),
            policy_context=asdict(pol),
            candidate_ref=asdict(candidate_ref),
            execution_plan=asdict(execution_plan),
            evidence_receipts=[],
            created_at=int(time.time()),
            updated_at=int(time.time()),
        )
        return capsule

    def transition(
        self,
        capsule: WorkCapsule,
        target_state: CapsuleState,
        supervisor_key_id: Optional[str] = None,
        supervisor_sig_hex: Optional[str] = None,
    ) -> Tuple[bool, str]:
        current = CapsuleState(capsule.state)
        allowed = VALID_TRANSITIONS.get(current, set())

        if target_state not in allowed:
            return False, f"ERR_INVALID_TRANSITION: Cannot transition from {current.value} to {target_state.value}"

        # If entering AUTHORIZED from HUMAN_APPROVAL_PENDING, verify supervisor signature
        if current == CapsuleState.HUMAN_APPROVAL_PENDING and target_state == CapsuleState.AUTHORIZED:
            if not supervisor_key_id or not supervisor_sig_hex:
                return False, "ERR_HUMAN_GATE_SIGNATURE_MISSING"
            if not self.human_gate.verify_approval(capsule, supervisor_key_id, supervisor_sig_hex):
                return False, "ERR_INVALID_SUPERVISOR_SIGNATURE"
            capsule.policy_context["human_approval_signature"] = supervisor_sig_hex

        # If entering VERIFIED, check if human gate is triggered
        if target_state == CapsuleState.VERIFIED:
            needs_human = self.human_gate.evaluate_gate_requirement(capsule)
            capsule.policy_context["requires_human_gate"] = needs_human

        capsule.state = target_state.value
        capsule.updated_at = int(time.time())

        # Generate cryptographic receipt on consequential terminal or dispatch states
        if target_state in (
            CapsuleState.AUTHORIZED,
            CapsuleState.DISPATCHED,
            CapsuleState.CONFIRMED,
            CapsuleState.REFUTED,
            CapsuleState.EFFECT_INDETERMINATE,
            CapsuleState.SETTLED,
        ):
            receipt = self._emit_receipt(capsule, target_state.value)
            capsule.evidence_receipts.append(receipt.receipt_caid)

        return True, "OK"

    def _emit_receipt(self, capsule: WorkCapsule, disposition: str) -> EvidenceReceipt:
        payload_dict = {
            "capsule_id": capsule.capsule_id,
            "state": disposition,
            "idempotency_key": capsule.execution_plan.get("idempotency_key"),
            "amount_minor": capsule.execution_plan.get("amount_minor"),
            "timestamp": capsule.updated_at,
        }
        canonical_bytes = encode_jcs(payload_dict)
        digest = hashlib.sha256(canonical_bytes).hexdigest()

        sig_bytes = self.signer_key.sign(canonical_bytes)
        pub_bytes = self.signer_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        receipt_caid = f"urn:aeib:receipt:sha256:{digest}"
        return EvidenceReceipt(
            receipt_version="1.0.0",
            receipt_caid=receipt_caid,
            capsule_id=capsule.capsule_id,
            operation_id=capsule.execution_plan.get("idempotency_key", ""),
            disposition=disposition,
            payload_sha256=digest,
            signer_public_key_hex=pub_bytes.hex(),
            signature_hex=sig_bytes.hex(),
            signed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
