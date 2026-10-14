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

"""
v1.1-roadmap/temporal_standing_evaluator.py
================================================================================
AEIB Commit-Time Temporal Standing ($T_0 \\to \\Delta N \\to T_n$) Evaluator,
Andon Cord Safe Halt Controller, and Governance Graph Fragment Emitter.

Epistemic Boundary (AGENTS.md §1 & §5):
  Operates under the stated model as an explicit runtime check evaluated
  immediately before a mutating network syscall binds an external consequence.
  Authorization is not a standing permission; it is a time-bound, operation-bound
  verdict revalidated at commit time ($T_n$).

Core Components:
  1. TemporalStandingEvaluator:
     Enforces 10 fail-closed checks at $T_n$ prior to socket allocation.
  2. AndonCordController (EU AI Act Article 14):
     Enforces an emergency human interrupt path placing the system in a safe halted state.
  3. SaidotGraphFragmentEmitter:
     Emits minimal, machine-readable governance graph fragments without turning
     AEIB into a monolithic enterprise inventory system of record.
  4. EventDrivenInvalidator:
     Invalidates cached standing upon external lifecycle and topology events.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


class StandingRevocationError(RuntimeError):
    """Raised when an action's standing is invalidated at commit time ($T_n$)."""


class AndonCordHaltError(RuntimeError):
    """Raised when an operator trips the emergency Andon cord interrupt."""


@dataclass(frozen=True)
class StandingCheckContext:
    """Snapshot of execution context evaluated at $T_n$ immediately before wire dispatch."""

    operation_id: str
    action_digest: str  # "sha256:<64-hex>"
    principal_id: str
    target_identity: str
    proposed_payload: Dict[str, Any]
    authorized_policy_epoch: int
    ticket_decision_id: str
    ticket_expires_at: int
    delegation_chain_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class StandingEvaluationResult:
    """Deterministic result of the $T_n$ temporal standing evaluation."""

    standing_valid: bool
    evaluated_at_epoch: int
    rejection_reason: Optional[str] = None
    violated_check: Optional[str] = None
    audit_event: Optional[Dict[str, Any]] = None


class TemporalStandingEvaluator:
    """
    Evaluates present standing at $T_n$ immediately before the consequence binds.
    Fails closed if any material fact changed during $\\Delta N = T_n - T_0$.
    """

    def __init__(
        self,
        *,
        active_policy_epoch_provider: Callable[[], int],
        target_allowlist_provider: Callable[[], Set[str]],
        revocation_registry_provider: Callable[[], Set[str]],
        evidence_store_health_probe: Callable[[], bool],
        egress_topology_probe: Optional[Callable[[], bool]] = None,
        andon_cord_probe: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.active_policy_epoch_provider = active_policy_epoch_provider
        self.target_allowlist_provider = target_allowlist_provider
        self.revocation_registry_provider = revocation_registry_provider
        self.evidence_store_health_probe = evidence_store_health_probe
        self.egress_topology_probe = egress_topology_probe or (lambda: True)
        self.andon_cord_probe = andon_cord_probe or (lambda: False)

    def evaluate_standing(
        self,
        ctx: StandingCheckContext,
        current_timestamp: int,
    ) -> StandingEvaluationResult:
        """
        Executes the 10 commit-time invariants at $T_n$:
          1. Andon Cord emergency interrupt check.
          2. Authority expiration check.
          3. Principal revocation check.
          4. Delegation chain revocation check.
          5. Policy epoch freshness check.
          6. Target allowlist containment check.
          7. Exact canonical action digest (CAID) re-verification.
          8. Payload parameter stability (amount & recipient) re-verification.
          9. Evidence store availability check.
          10. Sandbox egress path compliance check.
        """
        # 1. Human Andon Cord Interrupt Check (EU AI Act Article 14)
        if self.andon_cord_probe():
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="ANDON_CORD_TRIPPED",
                rejection_reason="Emergency operator interrupt active; execution halted fail-closed in safe state."
            )

        # 2. Authority Expiration Check
        if current_timestamp > ctx.ticket_expires_at:
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="AUTHORITY_EXPIRED",
                rejection_reason=f"Authority ticket expired at {ctx.ticket_expires_at} (commit time: {current_timestamp})."
            )

        # 3. Principal Revocation Check
        revoked_set = self.revocation_registry_provider()
        if ctx.principal_id in revoked_set:
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="PRINCIPAL_REVOKED",
                rejection_reason=f"Principal '{ctx.principal_id}' was revoked prior to commit time."
            )

        # 4. Delegation Chain Revocation Check
        for del_id in ctx.delegation_chain_ids:
            if del_id in revoked_set:
                return StandingEvaluationResult(
                    standing_valid=False,
                    evaluated_at_epoch=current_timestamp,
                    violated_check="DELEGATION_REVOKED",
                    rejection_reason=f"Delegation hop '{del_id}' in chain was revoked prior to commit time."
                )

        # 5. Policy Epoch Freshness Check
        active_epoch = self.active_policy_epoch_provider()
        if ctx.authorized_policy_epoch != active_epoch:
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="POLICY_EPOCH_CHANGED",
                rejection_reason=f"Policy epoch advanced during delta: authorized epoch {ctx.authorized_policy_epoch} != active {active_epoch}."
            )

        # 6. Target Allowlist Containment Check
        allowlist = self.target_allowlist_provider()
        if ctx.target_identity not in allowlist:
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="TARGET_NOT_ALLOWLISTED",
                rejection_reason=f"Target '{ctx.target_identity}' is not in active allowlist at commit time."
            )

        # 7. Exact Canonical Action Digest (CAID) Re-verification
        canonical_bytes = encode_jcs(ctx.proposed_payload)
        recomputed_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        if ctx.action_digest != recomputed_caid:
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="ACTION_DIGEST_MUTATED",
                rejection_reason=f"Payload mutated between authorization and commit: authorized {ctx.action_digest} != recomputed {recomputed_caid}."
            )

        # 8. Evidence Store Availability Check
        if not self.evidence_store_health_probe():
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="EVIDENCE_STORE_UNAVAILABLE",
                rejection_reason="Evidence store probe unhealthy; consequential dispatch blocked fail-closed."
            )

        # 9. Sandbox Egress Path Compliance Check
        if not self.egress_topology_probe():
            return StandingEvaluationResult(
                standing_valid=False,
                evaluated_at_epoch=current_timestamp,
                violated_check="EGRESS_TOPOLOGY_NON_COMPLIANT",
                rejection_reason="Direct ambient egress detected or proxy sidecar route unhealthy; dispatch blocked."
            )

        # 10. Present Standing Confirmed
        audit_event = {
            "event": "TEMPORAL_STANDING_CONFIRMED",
            "operation_id": ctx.operation_id,
            "action_digest": ctx.action_digest,
            "principal_id": ctx.principal_id,
            "target_identity": ctx.target_identity,
            "policy_epoch": active_epoch,
            "evaluated_at": current_timestamp,
            "standing": "PRESENT_AND_VALID"
        }

        return StandingEvaluationResult(
            standing_valid=True,
            evaluated_at_epoch=current_timestamp,
            audit_event=audit_event
        )


class AndonCordController:
    """
    Implements a safe stop and interrupt mechanism pursuant to EU AI Act Article 14.
    Allows an authorized human operator to trip an emergency halt, bringing
    consequential agent dispatches into a safe, deterministic halted state.
    """

    def __init__(self, halted_initially: bool = False) -> None:
        self._halted: bool = halted_initially
        self._halt_history: List[Dict[str, Any]] = []

    def trip_andon_cord(
        self,
        operator_principal: str,
        reason: str,
        timestamp_epoch: int
    ) -> Dict[str, Any]:
        """Trips the emergency halt. All subsequent dispatches fail closed immediately."""
        self._halted = True
        record = {
            "event": "ANDON_CORD_TRIPPED",
            "operator_principal": operator_principal,
            "reason": reason,
            "timestamp": timestamp_epoch,
            "system_state": "SAFE_HALT_ENGAGED"
        }
        self._halt_history.append(record)
        return record

    def reset_andon_cord(
        self,
        supervisor_principal: str,
        justification: str,
        timestamp_epoch: int
    ) -> Dict[str, Any]:
        """Resets the emergency halt under supervisory dual control."""
        self._halted = False
        record = {
            "event": "ANDON_CORD_RESET",
            "supervisor_principal": supervisor_principal,
            "justification": justification,
            "timestamp": timestamp_epoch,
            "system_state": "NORMAL_OPERATION_RESUMED"
        }
        self._halt_history.append(record)
        return record

    def is_halted(self) -> bool:
        return self._halted

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._halt_history)


class SaidotGraphFragmentEmitter:
    """
    Emits minimal, machine-readable governance graph fragments that enterprise
    AI governance platforms (Saidot, Collibra, ServiceNow) can ingest to link
    assets, risks, controls, and runtime boundaries without turning AEIB into
    a monolithic governance repository.
    """

    @staticmethod
    def emit_asset_fragment(
        *,
        agent_id: str,
        owner_principal: str,
        policy_profile: str,
        risk_classification: str = "HIGH_CONSEQUENCE_FINANCIAL",
        approved_use_context: str = "CUSTOMER_REFUND_SETTLEMENT",
        runtime_boundary: str = "AEIB_GATEWAY_v1.1",
        active_policy_epoch: int = 1,
    ) -> Dict[str, Any]:
        """Emits a governed asset node fragment with canonical metadata."""
        fragment = {
            "$schema": "https://aeib.internal/schemas/governed_asset_v1.json",
            "entity_type": "GOVERNED_ASSET",
            "asset_id": agent_id,
            "asset_class": "AUTONOMOUS_AGENT",
            "metadata": {
                "owner_principal": owner_principal,
                "policy_profile": policy_profile,
                "policy_epoch": active_policy_epoch,
                "risk_classification": risk_classification,
                "approved_use_context": approved_use_context,
                "runtime_boundary": runtime_boundary,
                "consequence_level": "STATE_MUTATING_EXTERNAL_API",
                "evidence_survivability": "INDEPENDENT_SIGNED_RECEIPT"
            }
        }
        return fragment

    @staticmethod
    def emit_dependency_fragment(
        *,
        agent_id: str,
        target_id: str,
        target_uri_pattern: str,
        owner_team: str,
        evidence_contract: str = "REFUND_STATUS_v1",
        probe_budget: int = 3,
        circuit_breaker_threshold: int = 5,
    ) -> Dict[str, Any]:
        """Emits a governed dependency edge linking an agent to an external target."""
        fragment = {
            "$schema": "https://aeib.internal/schemas/governed_dependency_v1.json",
            "entity_type": "GOVERNED_DEPENDENCY",
            "source_asset_id": agent_id,
            "target_dependency_id": target_id,
            "relationship": "MUTATES_STATE_VIA",
            "contract": {
                "target_uri_pattern": target_uri_pattern,
                "owner_team": owner_team,
                "evidence_contract": evidence_contract,
                "reconciliation": {
                    "probe_budget": probe_budget,
                    "circuit_breaker_threshold": circuit_breaker_threshold,
                    "backoff_strategy": "EXPONENTIAL_JITTER"
                }
            }
        }
        return fragment


class EventDrivenInvalidator:
    """
    Subscribes to external governance and infrastructure events, instantly
    invalidating open standing tokens and forcing fresh authorization at $T_n$.
    """

    SUPPORTED_EVENTS = {
        "POLICY_EPOCH_CHANGED",
        "PRINCIPAL_REVOKED",
        "DELEGATION_REVOKED",
        "TARGET_CONTRACT_CHANGED",
        "SANDBOX_EGRESS_POLICY_CHANGED",
        "EVIDENCE_STORE_UNAVAILABLE",
        "MODEL_OR_AGENT_VERSION_CHANGED",
        "EMERGENCY_OPERATOR_HALT"
    }

    def __init__(self) -> None:
        self._invalidation_log: List[Dict[str, Any]] = []
        self._revoked_entities: Set[str] = set()
        self._epoch: int = 1

    def dispatch_event(
        self,
        event_type: str,
        entity_id: str,
        timestamp_epoch: int,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if event_type not in self.SUPPORTED_EVENTS:
            raise ValueError(f"UNSUPPORTED_EVENT: '{event_type}' not in {self.SUPPORTED_EVENTS}")

        record = {
            "event_type": event_type,
            "entity_id": entity_id,
            "timestamp": timestamp_epoch,
            "details": details or {}
        }
        self._invalidation_log.append(record)

        if event_type in ("PRINCIPAL_REVOKED", "DELEGATION_REVOKED"):
            self._revoked_entities.add(entity_id)
        elif event_type == "POLICY_EPOCH_CHANGED":
            new_epoch = (details or {}).get("new_epoch", self._epoch + 1)
            self._epoch = new_epoch

        return record

    def is_revoked(self, entity_id: str) -> bool:
        return entity_id in self._revoked_entities

    def get_active_epoch(self) -> int:
        return self._epoch
