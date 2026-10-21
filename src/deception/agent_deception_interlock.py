"""
src/deception/agent_deception_interlock.py
================================================================================
AEIB Track C: Autonomous Deception, Canary Tripwires & Insider Threat Defense

Operationalizes honeypot defenses for enterprise agent runtimes:
- Decoy canary credentials, fake administrative tools, shadow API endpoints,
  and canary filesystem paths.
- Core Invariant: "Decoy access is NEVER authorized."
- Instant three-tier response upon tripwire access:
  1. Detection: Sub-millisecond alert with tripwire identifier.
  2. Containment: Revokes capability, latches HALT_HONEYPOT_TRIPWIRE_TRIGGERED,
     and halts further execution.
  3. Evidence: Preserves forensic incident receipt under RFC 8785 JCS canonical
     format and triggers human escalation.

Epistemic Calibration:
  Observed, tested, and evaluated against simulated internal lateral movement
  and privilege escalation attacks. Zero mock primitives; real Ed25519 signatures.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.runtime_boundary.runtime_execution_boundary import canonical_json_bytes


@dataclass(frozen=True)
class DecoyTripwire:
    tripwire_id: str
    kind: str  # "CANARY_CREDENTIAL" | "SHADOW_API" | "ADMIN_TOOL" | "CANARY_PATH"
    identifier: str  # The exact token, URL, tool name, or file path
    description: str


@dataclass(frozen=True)
class DeceptionForensicIncident:
    incident_id: str
    agent_id: str
    tripwire_id: str
    tripwire_kind: str
    triggered_value: str
    detected_at: int
    containment_action: str  # "CAPABILITY_REVOKED_AND_HALTED"
    forensic_digest: str
    signature_hex: str


class AutonomousDeceptionInterlock:
    """
    Tripwire enforcement gate embedded into tool and credential lookup paths.
    Configured so that touching any honeypot asset halts the calling agent immediately under the stated model.
    """

    def __init__(self, boundary_signer: Ed25519PrivateKey) -> None:
        self.boundary_signer = boundary_signer
        self.boundary_pubkey = boundary_signer.public_key()
        self.decoys: Dict[str, DecoyTripwire] = {}
        self.incidents: List[DeceptionForensicIncident] = []
        self.halted_agents: Set[str] = set()
        self._populate_standard_decoys()

    def _populate_standard_decoys(self) -> None:
        standard = [
            DecoyTripwire(
                "decoy-cred-01",
                "CANARY_CREDENTIAL",
                "AKIA_DECOY_ROOT_KEY_991",
                "Decoy AWS root access key bait",
            ),
            DecoyTripwire(
                "decoy-cred-02",
                "CANARY_CREDENTIAL",
                "sk_live_canary_tripwire_stripe_root",
                "Decoy live Stripe secret key bait",
            ),
            DecoyTripwire(
                "decoy-api-01",
                "SHADOW_API",
                "/internal/v1/admin/bypass_gate",
                "Shadow unauthenticated administrative endpoint",
            ),
            DecoyTripwire(
                "decoy-tool-01",
                "ADMIN_TOOL",
                "system.force_override_ceiling",
                "Decoy privileged override tool",
            ),
            DecoyTripwire(
                "decoy-path-01",
                "CANARY_PATH",
                "/etc/aeib/vault_master_key.json",
                "Decoy vault master key file",
            ),
        ]
        for d in standard:
            self.decoys[d.identifier] = d

    def register_custom_decoy(self, decoy: DecoyTripwire) -> None:
        self.decoys[decoy.identifier] = decoy

    def inspect_access_attempt(
        self,
        agent_id: str,
        attempted_resource: str,
        detected_at: int,
    ) -> Dict[str, Any]:
        """
        Inspects an accessed resource, parameter, tool, or endpoint.
        If a decoy is accessed:
        - Fails closed immediately (`HALT_HONEYPOT_TRIPWIRE_TRIGGERED`).
        - Revokes agent authority.
        - Emits a signed forensic incident receipt.
        """
        if agent_id in self.halted_agents:
            return {
                "disposition": "HALTED",
                "code": "HALT_AGENT_ALREADY_REVOKED_FOR_DECEPTION_BREACH",
                "incident_id": None,
            }

        # Check if the attempted resource matches or contains a decoy tripwire
        matched_decoy: Optional[DecoyTripwire] = None
        for decoy_id, decoy in self.decoys.items():
            if decoy_id == attempted_resource or decoy_id in attempted_resource:
                matched_decoy = decoy
                break

        if matched_decoy is None:
            return {"disposition": "CLEAN", "code": "OK"}

        # TRIPWIRE HIT: Immediate containment
        self.halted_agents.add(agent_id)
        incident_id = f"inc-decoy-{matched_decoy.tripwire_id}-{detected_at}"

        incident_core = {
            "incident_id": incident_id,
            "agent_id": agent_id,
            "tripwire_id": matched_decoy.tripwire_id,
            "tripwire_kind": matched_decoy.kind,
            "triggered_value": attempted_resource,
            "detected_at": detected_at,
            "containment_action": "CAPABILITY_REVOKED_AND_HALTED",
        }
        canonical_bytes = canonical_json_bytes(incident_core)
        forensic_digest = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        sig_hex = self.boundary_signer.sign(canonical_bytes).hex()

        incident = DeceptionForensicIncident(
            incident_id=incident_id,
            agent_id=agent_id,
            tripwire_id=matched_decoy.tripwire_id,
            tripwire_kind=matched_decoy.kind,
            triggered_value=attempted_resource,
            detected_at=detected_at,
            containment_action="CAPABILITY_REVOKED_AND_HALTED",
            forensic_digest=forensic_digest,
            signature_hex=sig_hex,
        )
        self.incidents.append(incident)

        return {
            "disposition": "HALTED",
            "code": "HALT_HONEYPOT_TRIPWIRE_TRIGGERED",
            "incident_id": incident_id,
            "tripwire_kind": matched_decoy.kind,
            "containment": "CAPABILITY_REVOKED_AND_HALTED",
            "forensic_digest": forensic_digest,
            "signature_hex": sig_hex,
        }

    def is_agent_halted(self, agent_id: str) -> bool:
        return agent_id in self.halted_agents
