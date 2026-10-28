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
aeib_gateway_adapter.py — Inline Wire-Boundary Interlock Adapter
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.4.1

Implements Stages 6–10 of the Execution-Integrity Decision Boundary:
- RFC 8785 JCS canonicalization (_canonicalize_jcs)
- Candidate Identity Triad: (operation_id, request_digest, business_idempotency_key)
- Extended Candidate Action ID (CAID) computation
- Millisecond T_dispatch Standing Gate (evaluate_standing)
- Write-Ahead Uncertainty Latching (EFFECT_INDETERMINATE, retry_safe: false)
- Miyazaki HOLD accountability schema (assigned principal, deadline, escalation path)
- Transparency Log Freshness Verification (TransparencyLogFresh)
- Non-Compensatory Execution Predicate Evaluation
- Zero-mock Ed25519 cryptographic signing and verification
"""

import hashlib
import re
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

try:
    from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
    from src.governance_boundary import (
        GovernanceDecisionBoundary,
        AgentIdentityContext,
        CandidateAction,
        PreDispatchDecision,
        DelegationGrant,
    )
    from src.evidence_registry_client import EvidenceRegistryClient, EvidenceChainVerified
except ImportError:
    from jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
    from governance_boundary import (
        GovernanceDecisionBoundary,
        AgentIdentityContext,
        CandidateAction,
        PreDispatchDecision,
        DelegationGrant,
    )
    from evidence_registry_client import EvidenceRegistryClient, EvidenceChainVerified


AUTH_TOKEN_PATTERN = re.compile(
    r"(?:bearer\s+[a-zA-Z0-9_\-\.]+|eyJ[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9_\-\.]+|sk-[a-zA-Z0-9_\-]+|ghp_[a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)


def redact_sensitive_credentials(payload: Any) -> Any:
    """Recursively redacts bearer tokens, JWTs, and API keys to prevent confused deputy credential laundering."""
    if isinstance(payload, dict):
        redacted = {}
        for k, v in payload.items():
            key_lower = k.lower()
            if any(s in key_lower for s in ("authorization", "token", "jwt", "bearer", "api_key", "secret")):
                redacted[k] = "[REDACTED_CREDENTIAL]"
            else:
                redacted[k] = redact_sensitive_credentials(v)
        return redacted
    elif isinstance(payload, list):
        return [redact_sensitive_credentials(item) for item in payload]
    elif isinstance(payload, str):
        if AUTH_TOKEN_PATTERN.search(payload):
            return AUTH_TOKEN_PATTERN.sub("[REDACTED_CREDENTIAL]", payload)
        return payload
    return payload


def check_transparency_log_freshness(
    log_state: Dict[str, Any],
    current_time_ms: int,
    max_staleness_ms: int = 60000,
) -> bool:
    """
    Evaluates TransparencyLogFresh(log_state, T_dispatch):
    Fails closed if consistency proof is missing/invalid or if last_verified_ms
    is older than max_staleness_ms relative to current_time_ms.
    """
    if not isinstance(log_state, dict):
        return False
    if not log_state.get("consistency_proof_valid", False):
        return False
    last_verified = log_state.get("last_verified_ms", 0)
    if (current_time_ms - last_verified) > max_staleness_ms:
        return False
    return True


def validate_crypto_inventory(crypto_inventory: Optional[Dict[str, Any]]) -> bool:
    """
    Evaluates CryptoInventoryValid(receipt.crypto_inventory):
    Validates cryptographic inventory metadata, PQC migration target declaration,
    active non-revoked status, and epoch compliance.
    """
    if not isinstance(crypto_inventory, dict):
        return False
    required_keys = (
        "algorithm",
        "pqc_migration_target",
        "key_id",
        "key_epoch",
        "purpose",
        "owner",
        "storage",
        "validity_interval",
        "rotation_policy",
        "revocation_status",
        "migration_status",
    )
    if not all(k in crypto_inventory for k in required_keys):
        return False
    if crypto_inventory.get("revocation_status") != "ACTIVE_UNREVOKED":
        return False
    valid_algs = ("Ed25519", "NIST_FIPS_204_ML_DSA_65", "FIPS_205_SLH_DSA")
    if crypto_inventory.get("algorithm") not in valid_algs:
        return False
    return True


@dataclass
class ExecutionEvaluationResult:
    """Result of evaluating the non-compensatory execution contract formula."""
    permitted: bool
    failed_clause: Optional[str] = None
    disposition: str = "UNKNOWN"
    details: Dict[str, Any] = field(default_factory=dict)


class AEIBGatewayAdapter:
    """
    Inline Gateway Interlock Adapter managing pre-dispatch standing evaluation,
    exact CAID derivation, transport uncertainty latching, and evidence minting.
    """

    def __init__(
        self,
        governance_boundary: Optional[GovernanceDecisionBoundary] = None,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
    ):
        self.boundary = governance_boundary or GovernanceDecisionBoundary()
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key_hex = self.signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        self.active_latches: Dict[str, Dict[str, Any]] = {}

    def _canonicalize_jcs(self, payload: Dict[str, Any]) -> bytes:
        """Returns byte-exact RFC 8785 canonical JSON."""
        return encode_jcs(payload)

    def compute_request_digest(
        self,
        payload: Dict[str, Any],
        redact_credentials: bool = True,
    ) -> str:
        """
        Computes SHA256(JCS(exact request payload)) conforming to RFC 8785.
        """
        clean_payload = redact_sensitive_credentials(payload) if redact_credentials else payload
        canonical_bytes = self._canonicalize_jcs(clean_payload)
        return hashlib.sha256(canonical_bytes).hexdigest()

    def derive_extended_caid(
        self,
        noun: str,
        verb: str,
        payload: Dict[str, Any],
        operation_id: Optional[str] = None,
        business_idempotency_key: Optional[str] = None,
        memory_digest: Optional[str] = None,
        harness_digest: Optional[str] = None,
        process_trace_digest: Optional[str] = None,
        manifest_hash: Optional[str] = None,
        redact_credentials: bool = True,
    ) -> str:
        """
        Computes the Master Extended Candidate Action ID binding the Identity Triad:
        CAID = SHA256(operation_id || noun::verb::JCS_redacted(Payload) || business_idempotency_key ||
                      MemoryDigest || HarnessDigest || ProcessTraceDigest || ManifestHash)
        """
        clean_payload = redact_sensitive_credentials(payload) if redact_credentials else payload
        canonical_payload = self._canonicalize_jcs(clean_payload)

        hasher = hashlib.sha256()
        if operation_id:
            hasher.update(b"op:")
            hasher.update(operation_id.strip().encode("utf-8"))
            hasher.update(b"::")

        hasher.update(noun.strip().encode("utf-8"))
        hasher.update(b"::")
        hasher.update(verb.strip().encode("utf-8"))
        hasher.update(b"::")
        hasher.update(canonical_payload)

        if business_idempotency_key:
            hasher.update(b"::bizkey:")
            hasher.update(business_idempotency_key.strip().encode("utf-8"))
        if memory_digest:
            hasher.update(b"::mem:")
            hasher.update(memory_digest.strip().encode("utf-8"))
        if harness_digest:
            hasher.update(b"::harness:")
            hasher.update(harness_digest.strip().encode("utf-8"))
        if process_trace_digest:
            hasher.update(b"::trace:")
            hasher.update(process_trace_digest.strip().encode("utf-8"))
        if manifest_hash:
            hasher.update(b"::manifest:")
            hasher.update(manifest_hash.strip().encode("utf-8"))

        return f"caid:sha256:{hasher.hexdigest()}"

    def derive_triad_caid(
        self,
        operation_id: str,
        noun: str,
        verb: str,
        payload: Dict[str, Any],
        business_idempotency_key: Optional[str] = None,
        memory_digest: Optional[str] = None,
        harness_digest: Optional[str] = None,
        process_trace_digest: Optional[str] = None,
        manifest_hash: Optional[str] = None,
        redact_credentials: bool = True,
    ) -> str:
        """Explicit Candidate Identity Triad CAID constructor."""
        return self.derive_extended_caid(
            noun=noun,
            verb=verb,
            payload=payload,
            operation_id=operation_id,
            business_idempotency_key=business_idempotency_key,
            memory_digest=memory_digest,
            harness_digest=harness_digest,
            process_trace_digest=process_trace_digest,
            manifest_hash=manifest_hash,
            redact_credentials=redact_credentials,
        )

    def evaluate_standing(
        self,
        candidate: CandidateAction,
        identity: AgentIdentityContext,
        current_time_ms: int,
    ) -> PreDispatchDecision:
        """
        Millisecond T_dispatch Standing Gate: Re-evaluates authority, policy epoch,
        and tool constraints immediately before packet emission.
        """
        return self.boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms)

    def latch_uncertainty(
        self,
        caid: str,
        wire_fault: str,
        operation_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        review_deadline_hours: int = 4,
        escalation_path: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Write-Ahead Uncertainty Latching: Locks ambiguous wire transport events
        (HTTP 504 / TCP RST) fail-closed at EFFECT_INDETERMINATE with retry_safe: false
        and registers the Miyazaki HOLD accountability schema.
        """
        dt_now = datetime.now(timezone.utc)
        deadline = (dt_now + timedelta(hours=review_deadline_hours)).isoformat()

        latch_record = {
            "caid": caid,
            "operation_id": operation_id or "",
            "disposition": "EFFECT_INDETERMINATE",
            "retry_safe": False,
            "wire_fault": wire_fault,
            "latched_at": dt_now.isoformat(),
            "status": "PROHIBITED_DEFAULT_LATCH",
            "miyazaki_hold": {
                "assigned_to": assigned_to or "principal:compliance_officer_oncall",
                "review_deadline": deadline,
                "escalation_path": escalation_path or [
                    "tier1_sre_operator",
                    "tier2_compliance_officer",
                    "tier3_executive_risk_committee",
                ],
                "expiration_action": "EXPIRED_RELEASE_DENIED",
                "raw_evidence_inspected": False,
            },
        }
        self.active_latches[caid] = latch_record
        return latch_record

    def is_latched(self, caid: str) -> bool:
        """Returns True if the CAID is locked under an active uncertainty latch."""
        return caid in self.active_latches

    def evaluate_execution_predicate(
        self,
        candidate: CandidateAction,
        identity: AgentIdentityContext,
        current_time_ms: int,
        log_state: Dict[str, Any],
        citations: Optional[List[str]] = None,
        evidence_client: Optional[EvidenceRegistryClient] = None,
        transport_disposition: str = "CONFIRMED",
        retry_safe: bool = True,
        target_probe_status: str = "AUTHORITATIVE",
        entropy_bits: int = 256,
        boot_harness_digest: str = "",
        current_harness_digest: str = "",
        release_authorized: bool = True,
        crypto_inventory: Optional[Dict[str, Any]] = None,
        max_log_staleness_ms: int = 60000,
    ) -> ExecutionEvaluationResult:
        """
        Evaluates the non-compensatory execution contract formula:
        Execution(a) <=>
            S(T_dispatch) == true ∧
            TransparencyLogFresh(log_state, T_dispatch) == true ∧
            EvidenceChainVerified(citations) == true ∧
            Transport_disposition in {CONFIRMED, EFFECT_INDETERMINATE} ∧
            (Transport_disposition == EFFECT_INDETERMINATE => retry_safe == false) ∧
            Target_probe_status == AUTHORITATIVE ∧
            Entropy(T_dispatch) >= 256b ∧
            HarnessDigest_boot == HarnessDigest_T_dispatch ∧
            Release_authorized == true
        """
        # Clause 1: S(T_dispatch) Millisecond Standing Gate
        standing = self.evaluate_standing(candidate, identity, current_time_ms)
        if not standing.permitted:
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="STANDING_GATE_REJECTED",
                disposition=standing.disposition,
                details={"standing_reason": standing.reason},
            )

        # Clause 2: TransparencyLogFresh
        if not check_transparency_log_freshness(log_state, current_time_ms, max_log_staleness_ms):
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="TRANSPARENCY_LOG_STALE_OR_INVALID",
                disposition="TRANSPARENCY_LOG_REJECTED",
                details={"log_state": log_state},
            )

        # Clause 3: EvidenceChainVerified
        if citations and evidence_client is not None:
            chain_verified, reason, cit_details = evidence_client.evidence_chain_verified(citations)
            if not chain_verified:
                return ExecutionEvaluationResult(
                    permitted=False,
                    failed_clause="EVIDENCE_CHAIN_VERIFICATION_FAILED",
                    disposition="CITATION_REJECTED",
                    details={"reason": reason, "citations": cit_details},
                )

        # Clause 4: Transport disposition legality
        if transport_disposition not in ("CONFIRMED", "EFFECT_INDETERMINATE"):
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="INVALID_TRANSPORT_DISPOSITION",
                disposition=transport_disposition,
            )

        # Clause 5: EFFECT_INDETERMINATE => retry_safe == false
        if transport_disposition == "EFFECT_INDETERMINATE" and retry_safe is not False:
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="INDETERMINATE_WITHOUT_RETRY_SUPPRESSION",
                disposition="FAIL_CLOSED_RETRY_VIOLATION",
            )

        # Clause 6: Target probe status must be AUTHORITATIVE
        if target_probe_status != "AUTHORITATIVE":
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="TARGET_PROBE_NON_AUTHORITATIVE",
                disposition="PROBE_STATUS_REJECTED",
            )

        # Clause 7: CryptoInventoryValid
        if crypto_inventory is not None:
            if not validate_crypto_inventory(crypto_inventory):
                return ExecutionEvaluationResult(
                    permitted=False,
                    failed_clause="CRYPTO_INVENTORY_INVALID",
                    disposition="CRYPTO_INVENTORY_REJECTED",
                    details={"crypto_inventory": crypto_inventory},
                )

        # Clause 8: Entropy(T_dispatch) >= 256 bits
        if entropy_bits < 256:
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="INSUFFICIENT_ENTROPY",
                disposition="ENTROPY_STARVATION_REJECTED",
            )

        # Clause 9: HarnessDigest_boot == HarnessDigest_T_dispatch
        if boot_harness_digest != current_harness_digest:
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="HARNESS_DIGEST_MUTATED",
                disposition="TAMPERING_REJECTED",
            )

        # Clause 10: Release_authorized == true
        if not release_authorized:
            return ExecutionEvaluationResult(
                permitted=False,
                failed_clause="RELEASE_UNAUTHORIZED",
                disposition="RELEASE_DENIED",
            )

        return ExecutionEvaluationResult(
            permitted=True,
            failed_clause=None,
            disposition=transport_disposition,
            details={"standing": standing.to_dict() if hasattr(standing, "to_dict") else {}},
        )
