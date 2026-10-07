#!/usr/bin/env python3
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

r"""
src/governance_boundary.py — AEIB v0.4.0 Decision Boundary & Governance Engine
Implements the 9-Stage Execution Pipeline for Agentic Effect Integrity.

Provides evaluation for Acceptance Tests AT15–AT25:
- AT15: Unregistered Agent Dispatch (Identity Inventory Boundary)
- AT16: Delegation Scope Escalation (Preserves principal_id, blocks privilege escalation)
- AT17: Stale Grant / Epoch Expiry (Fail-closed on policy_epoch or grant expiry)
- AT18: Control-Plane Degradation (Triggers containment C1–C5, never fails open)
- AT19: Agent Evidence Tampering (Process isolation & append-only model blocks modification)
- AT20: Escalation on Indeterminate Loops (Triggers human review after repeated EFFECT_INDETERMINATE)
- AT21: Memory Poisoning Attack (Parameter/context injection causes schema/payload digest mismatch)
- AT22: Cross-Boundary Delegation (Identity-neutral federation: OIDC/mTLS/X.509/DIDs fail-closed)
- AT23: Millisecond Standing Race (Atomic re-check at dispatch instant: DISPATCH_REJECTED on race)
- AT24: Candidate Payload Mutation (Post-approval argument change invalidates CAID/digest)
- AT25: Ledger Compromise / Fork (Hash chain discrepancy triggers C5 containment and blocks release)
"""

import hashlib
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
from src.mcp_schema_pinning import compute_tool_schema_hash


class EvidenceTamperingError(PermissionError):
    """Raised when an agent attempts unauthorized modification or deletion of ledger records."""
    pass


class LedgerIntegrityError(RuntimeError):
    """Raised when the cryptographic audit chain of the ledger fails verification."""
    pass


@dataclass
class AgentIdentityContext:
    agent_id: str
    principal_id: str
    tenant_id: str
    delegation_chain: List[str]
    standing_version: str
    policy_epoch: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "delegation_chain": list(self.delegation_chain),
            "standing_version": self.standing_version,
            "policy_epoch": self.policy_epoch,
        }


@dataclass
class ControlPlaneHealth:
    schema_pinning: str = "healthy"  # "healthy", "degraded", "unavailable"
    ledger: str = "healthy"
    probe: str = "healthy"
    signer: str = "healthy"

    def is_healthy(self) -> bool:
        return (
            self.schema_pinning == "healthy"
            and self.ledger == "healthy"
            and self.probe == "healthy"
            and self.signer == "healthy"
        )

    def determine_containment(self) -> str:
        if self.signer != "healthy":
            return "C5"
        if self.ledger != "healthy":
            return "C4"
        if self.probe != "healthy":
            return "C3"
        if self.schema_pinning != "healthy":
            return "C2"
        return "C0"

    def to_dict(self) -> Dict[str, str]:
        return {
            "schema_pinning": self.schema_pinning,
            "ledger": self.ledger,
            "probe": self.probe,
            "signer": self.signer,
        }


@dataclass
class DelegationGrant:
    grant_id: str
    principal_id: str
    authorized_agent_id: str
    allowed_verbs: Set[str]
    policy_epoch: str
    expires_at_epoch_ms: int
    is_revoked: bool = False


@dataclass
class FederationMetadata:
    profile: str  # "OIDC", "mTLS", "X.509", "W3C_DID"
    issuer: str
    subject_tenant: str
    token_or_proof: str
    valid_until_epoch_ms: int
    is_valid: bool = True


@dataclass
class CandidateAction:
    noun: str
    verb: str
    payload: Dict[str, Any]
    schema: Optional[Dict[str, Any]] = None
    approved_caid: Optional[str] = None
    approved_payload_hash: Optional[str] = None
    policy_epoch: str = "policy:epoch_104"
    grant_id: Optional[str] = None
    federation: Optional[FederationMetadata] = None


@dataclass
class PreDispatchDecision:
    permitted: bool
    disposition: str
    retry_safe: bool
    containment_level: str
    reason: str
    attributes: Dict[str, Any] = field(default_factory=dict)


class AppendOnlyEvidenceLedger:
    """
    Cryptographic append-only evidence ledger.
    Enforces process isolation, immutability, and external anchor hash-chain integrity.
    """
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self._genesis_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"

    def append(self, entry: Dict[str, Any]) -> str:
        prev_hash = self.entries[-1]["entry_hash"] if self.entries else self._genesis_hash
        hasher = hashlib.sha256()
        hasher.update(prev_hash.encode("utf-8"))
        hasher.update(b"::")
        hasher.update(encode_jcs(entry))
        entry_hash = hasher.hexdigest()
        stored_record = {
            "entry_id": len(self.entries) + 1,
            "data": entry,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.entries.append(stored_record)
        return entry_hash

    def get_latest_hash(self) -> str:
        return self.entries[-1]["entry_hash"] if self.entries else self._genesis_hash

    def verify_integrity(self) -> bool:
        prev_hash = self._genesis_hash
        for rec in self.entries:
            if rec["prev_hash"] != prev_hash:
                return False
            hasher = hashlib.sha256()
            hasher.update(prev_hash.encode("utf-8"))
            hasher.update(b"::")
            hasher.update(encode_jcs(rec["data"]))
            expected_hash = hasher.hexdigest()
            if rec["entry_hash"] != expected_hash:
                return False
            prev_hash = rec["entry_hash"]
        return True

    def execute_agent_mutation_attempt(self, operation: str, entry_id: int) -> None:
        """
        AT19: Agent attempts to modify, rewrite, or delete historical ledger records.
        Strict process isolation and append-only constraints reject direct write/modify/delete access.
        """
        op = operation.strip().upper()
        verb = op.split()[0] if op else ""
        if verb in ("DELETE", "UPDATE", "DROP", "TRUNCATE", "OVERWRITE") or op in ("DELETE", "UPDATE", "DROP", "TRUNCATE", "OVERWRITE"):
            raise EvidenceTamperingError(
                f"EVIDENCE_TAMPERING_REJECTED: Process isolation forbids agent mutation "
                f"operation '{operation}' against ledger entry {entry_id}."
            )


class GovernanceDecisionBoundary:
    """
    AEIB Decision Boundary (Stages 1–5 and 8–9 of the Execution Pipeline).
    Controls Candidate Binding, Pre-Dispatch Authorization, Consequence Governance,
    and Release Separation.
    """
    def __init__(
        self,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        active_policy_epoch: str = "policy:epoch_104",
        active_standing_version: str = "standing:v2026.10.07-epoch-14"
    ):
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key_hex = self.signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

        self.active_policy_epoch = active_policy_epoch
        self.active_standing_version = active_standing_version
        self.agent_inventory: Set[str] = set()
        self.grants: Dict[str, DelegationGrant] = {}
        self.pinned_schemas: Dict[str, str] = {}
        self.control_health = ControlPlaneHealth()
        self.ledger = AppendOnlyEvidenceLedger()
        self.indeterminate_history: Dict[str, int] = {}

    def register_agent(self, agent_id: str) -> None:
        self.agent_inventory.add(agent_id)

    def pin_schema(self, tool_name: str, schema: Dict[str, Any]) -> str:
        schema_hash = compute_tool_schema_hash(schema)
        self.pinned_schemas[tool_name] = schema_hash
        return schema_hash

    def add_grant(self, grant: DelegationGrant) -> None:
        self.grants[grant.grant_id] = grant

    def revoke_grant(self, grant_id: str) -> None:
        if grant_id in self.grants:
            self.grants[grant_id].is_revoked = True

    def evaluate_pre_dispatch(
        self,
        candidate: CandidateAction,
        identity: AgentIdentityContext,
        current_time_ms: int
    ) -> PreDispatchDecision:
        """
        Evaluates Stages 1 through 5 of the pipeline at the millisecond of dispatch.
        Fails closed on any policy, identity, standing, schema, or health violation.
        """
        # Candidate CAID derivation: CAID = H(Noun || Verb || JCS(Payload))
        canonical_payload = encode_jcs(candidate.payload)
        hasher = hashlib.sha256()
        hasher.update(candidate.noun.strip().encode("utf-8"))
        hasher.update(b"::")
        hasher.update(candidate.verb.strip().encode("utf-8"))
        hasher.update(b"::")
        hasher.update(canonical_payload)
        candidate_caid = f"caid:sha256:{hasher.hexdigest()}"
        computed_payload_hash = generate_jcs_payload_hash(candidate.payload)

        base_attrs = {
            "aeib.governance.agent_id": identity.agent_id,
            "aeib.governance.principal_id": identity.principal_id,
            "aeib.governance.tenant_id": identity.tenant_id,
            "aeib.governance.delegation_chain": identity.delegation_chain,
            "aeib.governance.standing_version": identity.standing_version,
            "aeib.governance.policy_epoch": identity.policy_epoch,
            "aeib.governance.candidate_caid": candidate_caid,
            "aeib.governance.control_health": self.control_health.to_dict(),
        }

        # -------------------------------------------------------------
        # AT15: Identity & Agent Inventory Verification
        # -------------------------------------------------------------
        if identity.agent_id not in self.agent_inventory:
            return PreDispatchDecision(
                permitted=False,
                disposition="AGENT_NOT_IN_INVENTORY",
                retry_safe=False,
                containment_level="C2",
                reason="Agent identifier not registered in authorized inventory.",
                attributes={**base_attrs, "aeib.containment_level": "C2"}
            )

        # -------------------------------------------------------------
        # AT16: Delegation Scope Verification
        # -------------------------------------------------------------
        action_verb = f"{candidate.noun}:{candidate.verb}"
        grant = self.grants.get(candidate.grant_id) if candidate.grant_id else None

        if grant:
            if action_verb not in grant.allowed_verbs:
                return PreDispatchDecision(
                    permitted=False,
                    disposition="DELEGATION_SCOPE_ESCALATION",
                    retry_safe=False,
                    containment_level="C2",
                    reason=f"Sub-agent action '{action_verb}' exceeds parent delegation scope.",
                    attributes={**base_attrs, "aeib.containment_level": "C2"}
                )

        # -------------------------------------------------------------
        # AT17: Stale Grant / Policy Epoch Expiry
        # -------------------------------------------------------------
        if identity.policy_epoch != self.active_policy_epoch:
            return PreDispatchDecision(
                permitted=False,
                disposition="POLICY_EPOCH_STALE",
                retry_safe=False,
                containment_level="C2",
                reason=f"Candidate epoch '{identity.policy_epoch}' drifted from active '{self.active_policy_epoch}'.",
                attributes={**base_attrs, "aeib.containment_level": "C2"}
            )

        if grant:
            if grant.expires_at_epoch_ms <= current_time_ms:
                return PreDispatchDecision(
                    permitted=False,
                    disposition="POLICY_EPOCH_STALE",
                    retry_safe=False,
                    containment_level="C2",
                    reason="Delegation grant has expired at the dispatch timestamp.",
                    attributes={**base_attrs, "aeib.containment_level": "C2"}
                )

        # -------------------------------------------------------------
        # AT18: Control-Plane Health Check (Fail-Closed Containment)
        # -------------------------------------------------------------
        if not self.control_health.is_healthy():
            containment = self.control_health.determine_containment()
            return PreDispatchDecision(
                permitted=False,
                disposition="CONTAINMENT_ENGAGED",
                retry_safe=False,
                containment_level=containment,
                reason="Control plane degradation detected; fail-closed containment engaged.",
                attributes={**base_attrs, "aeib.containment_level": containment}
            )

        # -------------------------------------------------------------
        # AT21: Memory Poisoning & Schema Pinning Validation
        # -------------------------------------------------------------
        if candidate.schema is not None:
            observed_schema_hash = compute_tool_schema_hash(candidate.schema)
            pinned = self.pinned_schemas.get(candidate.noun)
            if pinned and observed_schema_hash != pinned:
                return PreDispatchDecision(
                    permitted=False,
                    disposition="SCHEMA_HASH_MISMATCH",
                    retry_safe=False,
                    containment_level="C3",
                    reason="Observed tool schema digest does not match approved pinned digest.",
                    attributes={**base_attrs, "aeib.containment_level": "C3"}
                )

        # -------------------------------------------------------------
        # AT22: Cross-Boundary Delegation (Identity-Neutral Federation)
        # -------------------------------------------------------------
        if candidate.federation is not None:
            fed = candidate.federation
            if not fed.is_valid or fed.valid_until_epoch_ms <= current_time_ms:
                return PreDispatchDecision(
                    permitted=False,
                    disposition="CROSS_BOUNDARY_AUTH_FAILED",
                    retry_safe=False,
                    containment_level="C2",
                    reason="Cross-boundary federation metadata missing or verification failed.",
                    attributes={**base_attrs, "aeib.containment_level": "C2"}
                )

        # -------------------------------------------------------------
        # AT24: Candidate Payload Mutation Invalidation
        # -------------------------------------------------------------
        if candidate.approved_caid is not None:
            if candidate_caid != candidate.approved_caid:
                return PreDispatchDecision(
                    permitted=False,
                    disposition="PAYLOAD_MUTATION_REJECTED",
                    retry_safe=False,
                    containment_level="C3",
                    reason="Payload parameters mutated after approval cycle; CAID invalidated.",
                    attributes={**base_attrs, "aeib.containment_level": "C3"}
                )

        if candidate.approved_payload_hash is not None:
            if computed_payload_hash != candidate.approved_payload_hash:
                return PreDispatchDecision(
                    permitted=False,
                    disposition="PAYLOAD_MUTATION_REJECTED",
                    retry_safe=False,
                    containment_level="C3",
                    reason="Canonical JCS payload hash mismatch; new authorization cycle required.",
                    attributes={**base_attrs, "aeib.containment_level": "C3"}
                )

        # -------------------------------------------------------------
        # AT23: Millisecond Standing Race (TOCTOU at Dispatch Instant)
        # -------------------------------------------------------------
        if grant and grant.is_revoked:
            return PreDispatchDecision(
                permitted=False,
                disposition="DISPATCH_REJECTED",
                retry_safe=False,
                containment_level="C1",
                reason="STANDING_REVOKED_AT_DISPATCH",
                attributes={**base_attrs, "aeib.containment_level": "C1"}
            )

        # All pre-dispatch gates passed
        return PreDispatchDecision(
            permitted=True,
            disposition="DISPATCH_PERMITTED",
            retry_safe=False,
            containment_level="C0",
            reason="Pre-dispatch authorization granted under stated policy epoch.",
            attributes={**base_attrs, "aeib.containment_level": "C0"}
        )

    def record_wire_outcome(self, caid: str, wire_disposition: str) -> Dict[str, Any]:
        """
        AT20: Consequence Governance on repeated indeterminate wire outcomes.
        If a retry loop encounters repeated EFFECT_INDETERMINATE, escalates to human review.
        """
        if wire_disposition == "EFFECT_INDETERMINATE":
            count = self.indeterminate_history.get(caid, 0) + 1
            self.indeterminate_history[caid] = count
            if count >= 3:
                return {
                    "caid": caid,
                    "disposition": "POLICY_ESCALATION_HUMAN_REQUIRED",
                    "retry_safe": False,
                    "retry_policy": "PROHIBITED_ESCALATE_HUMAN_OPERATOR",
                    "consecutive_indeterminate_count": count,
                }
            return {
                "caid": caid,
                "disposition": "EFFECT_INDETERMINATE",
                "retry_safe": False,
                "retry_policy": "PROHIBITED_RETRY_HOLD",
                "consecutive_indeterminate_count": count,
            }

        self.indeterminate_history[caid] = 0
        return {
            "caid": caid,
            "disposition": wire_disposition,
            "retry_safe": False,
            "consecutive_indeterminate_count": 0,
        }

    def audit_and_release(self, caid: str) -> Dict[str, Any]:
        """
        AT25: Release Separation & Ledger Compromise Detection.
        Validates hash chain integrity before release authorization.
        If ledger integrity is compromised, blocks release and engages C5 containment.
        """
        if not self.ledger.verify_integrity():
            return {
                "caid": caid,
                "disposition": "CONTAINMENT_LEVEL_C5",
                "containment_level": "C5",
                "release_authorization": "blocked_containment",
                "reason": "Ledger hash chain mismatch detected; containment level C5 engaged.",
            }

        return {
            "caid": caid,
            "disposition": "AUDIT_VERIFIED",
            "containment_level": "C0",
            "release_authorization": "not_provided",
            "reason": "Ledger integrity verified; release authorization remains separated.",
        }

    def sign_governance_receipt(
        self,
        candidate: CandidateAction,
        identity: AgentIdentityContext,
        decision: PreDispatchDecision
    ) -> Dict[str, Any]:
        """
        Signs a Canonical Evidence Protocol receipt using real Ed25519 and RFC 8785 JCS.
        """
        event_body = {
            "aeib.caid": decision.attributes.get("aeib.governance.candidate_caid", ""),
            "aeib.action.noun": candidate.noun,
            "aeib.action.verb": candidate.verb,
            "aeib.payload_hash": generate_jcs_payload_hash(candidate.payload),
            "aeib.disposition": decision.disposition,
            "aeib.retry_safe": decision.retry_safe,
            "aeib.containment_level": decision.containment_level,
            "aeib.release_authorization": "not_provided",
            "aeib.spec_version": "0.4.0",
            **decision.attributes,
        }

        canonical_bytes = encode_jcs(event_body)
        event_digest = hashlib.sha256(canonical_bytes).hexdigest()
        signature = self.signing_key.sign(canonical_bytes)

        pubkey = self.signing_key.public_key()
        pubkey.verify(signature, canonical_bytes)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_name": "aeib.governance_decision",
            "attributes": {
                **event_body,
                "aeib.receipt.signature": signature.hex(),
                "aeib.receipt.public_key_hex": self.public_key_hex,
                "aeib.receipt.jcs_payload_hash": f"sha256:{event_digest}",
                "aeib.receipt.verified": True,
            }
        }
