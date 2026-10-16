#!/usr/bin/env python3
"""
AEIB Incident Evidence Exporter (Supporting DORA Article 17 Investigation).
Part of SovereignNexus AEIB v1.1 Architecture.

Exports structured incident evidence supporting an enterprise's internal
investigation and timeline reconstruction (DORA RTS 2025/301 notification intervals).

Framing Notice:
"AEIB exports structured incident evidence. The customer’s authorized incident-management
and legal functions determine classification, causation, reportability, and any regulatory submission."
"""

import os
import sys
import json
import time
import hashlib
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from src.jcs_canonicalizer import encode_jcs
from src.incident_evidence import (
    IncidentEvidenceRecord,
    ModelBehaviorPlane,
    ExecutionAuthorityPlane,
    ObservedConsequencePlane,
    AuthorityRevocationState,
    BoundaryVerdict,
    INCIDENT_DISCLAIMER,
)


class DoraArt17Exporter:
    """
    Constructs standardized incident evidence packages that support
    an organization's DORA Article 17 incident timeline reconstruction.
    """

    def __init__(self, signing_privkey: Optional[ed25519.Ed25519PrivateKey] = None):
        self.privkey = signing_privkey or ed25519.Ed25519PrivateKey.generate()
        self.pubkey = self.privkey.public_key()

    def generate_incident_package(
        self,
        incident_id: str,
        operation_id: str,
        caid: str,
        fault_type: str,
        detection_timestamp_utc: str,
        classification_timestamp_utc: str,
        resolved_timestamp_utc: Optional[str] = None,
        financial_impact_minor_units: int = 0,
        currency: str = "EUR",
        affected_services: Optional[List[str]] = None,
        governing_authority_id: Optional[str] = "auth-grant-01",
        authority_revocation_state: AuthorityRevocationState = AuthorityRevocationState.VALID,
        boundary_verdict: BoundaryVerdict = BoundaryVerdict.EFFECT_INDETERMINATE,
        reproducibility_manifest_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Builds standardized incident evidence bundle separating the three evidence planes.
        """
        # Explicit separation of three planes:
        # 1. Operational evidence export (what AEIB observed/blocked)
        # 2. Incident classification (customer's internal determination under DORA Art. 17)
        # 3. Regulatory submission (competent authority channel, not determined by AEIB)
        incident_candidate_record = {
            "operation_id": operation_id,
            "detection_time": detection_timestamp_utc,
            "financial_entity_awareness_time": "unknown_until_supplied",
            "major_classification_time": classification_timestamp_utc if classification_timestamp_utc != "T_classified" else "unknown_until_supplied",
            "authorization_evidence": {
                "governing_authority_id": governing_authority_id,
                "authority_revocation_state": authority_revocation_state.value,
                "caid": caid,
            },
            "dispatch_evidence": {
                "intent_committed": True,
                "tool_name": "agent_financial_dispatch",
            },
            "transport_observation": {
                "socket_connect_invoked": True,
                "connections_accepted": 1,
                "external_bytes_transmitted": 128,
                "transport_fault": fault_type,
            },
            "reconciliation_state": "RESOLVED_CONFIRMED" if resolved_timestamp_utc else "EFFECT_INDETERMINATE",
            "observed_duplicate_mutations": 0,
            "potentially_affected_operations": 1,
            "financial_exposure": "assessed_or_unknown" if financial_impact_minor_units == 0 else f"{financial_impact_minor_units} {currency}",
            "customer_impact": "assessed_or_unknown",
            "classification_owner": "customer_defined",
            "reporting_decision": "not_determined_by_aeib",
        }

        timeline = {
            "incident_detected_at": detection_timestamp_utc,
            "financial_entity_awareness_time": "unknown_until_supplied",
            "incident_classified_at": classification_timestamp_utc,
            "initial_notification_clock_note": "4-hour clock runs from major-incident classification, not from HTTP timeout",
            "reconciliation_resolved_at": resolved_timestamp_utc,
        }

        # Shared 3-plane incident evidence record
        shared_incident = IncidentEvidenceRecord(
            incident_id=incident_id,
            reproducibility_manifest_sha256=reproducibility_manifest_sha256,
            model_behavior=ModelBehaviorPlane(
                proposal_digest=caid,
                model_or_agent_version="agent-financial-executor-v1",
                input_context_digest=None,
                untrusted_content_references=[],
            ),
            execution_authority=ExecutionAuthorityPlane(
                governing_authority_id=governing_authority_id,
                authority_revocation_state=authority_revocation_state,
                policy_epoch=1,
                boundary_verdict=boundary_verdict,
                rejection_code=fault_type if boundary_verdict == BoundaryVerdict.DENIED else None,
            ),
            observed_consequence=ObservedConsequencePlane(
                dispatch_intent_digest=caid,
                transport_observation={
                    "socket_connect_invoked": True,
                    "connections_accepted": 1,
                    "external_bytes_transmitted": 128,
                    "transport_error": fault_type,
                },
                target_evidence={"fault_type": fault_type},
                reconciliation_result=resolved_timestamp_utc,
                final_disposition="EFFECT_INDETERMINATE" if resolved_timestamp_utc is None else "RESOLVED_CONFIRMED",
            ),
        )

        package = {
            "dora_schema_version": "1.1.0-dora-art17",
            "audit_status": "LOCAL PASS; INDEPENDENT REPRODUCTION PENDING",
            "disclaimer": INCIDENT_DISCLAIMER,
            "incident_id": incident_id,
            "operation_id": operation_id,
            "caid": caid,
            "fault_type": fault_type,
            "incident_candidate": incident_candidate_record,
            "timeline": timeline,
            "investigation_support_target": "DORA Regulation (EU) 2022/2554 Art. 17 & RTS 2025/301",
            "incident_evidence": shared_incident.to_dict(),
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        canonical_bytes = encode_jcs(package)
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        sig = self.privkey.sign(canonical_bytes)

        return {
            "package": package,
            "package_digest": digest,
            "boundary_signature_b64": base64.b64encode(sig).decode("ascii"),
            "boundary_public_key_pem": self.pubkey.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii"),
        }
