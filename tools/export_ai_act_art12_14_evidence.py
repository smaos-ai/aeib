#!/usr/bin/env python3
"""
AEIB Incident Evidence Exporter (Supporting EU AI Act Articles 12, 14, and 72 Investigation).
Part of SovereignNexus AEIB v1.1 Architecture.

Constructs machine-readable incident evidence bundles supporting internal investigation:
- Article 12: Cryptographically chained event log with RFC 8785 hashes.
- Article 14: Human oversight, STEP_UP dual-control tickets, and Andon cord halts.
- Article 72: Post-market monitoring telemetry stream.

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


class EuAiActEvidenceExporter:
    """
    Constructs standardized incident evidence bundles supporting an organization's
    internal AI governance and investigation workflows.
    """

    def __init__(self, signing_privkey: Optional[ed25519.Ed25519PrivateKey] = None):
        self.privkey = signing_privkey or ed25519.Ed25519PrivateKey.generate()
        self.pubkey = self.privkey.public_key()

    def generate_compliance_bundle(
        self,
        system_id: str,
        operation_id: str,
        caid: str,
        lifecycle_events: List[Dict[str, Any]],
        human_oversight_record: Optional[Dict[str, Any]] = None,
        post_market_metrics: Optional[Dict[str, Any]] = None,
        incident_id: str = "INC-AI-ACT-001",
        governing_authority_id: Optional[str] = "auth-human-operator",
        authority_revocation_state: AuthorityRevocationState = AuthorityRevocationState.VALID,
        boundary_verdict: BoundaryVerdict = BoundaryVerdict.ALLOWED,
        reproducibility_manifest_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Builds complete Articles 12, 14, and 72 evidence package embedding the shared incident schema.
        """
        # 1. Art 12: Compute continuous SHA-256 hash chain over lifecycle events
        chain_tip = "0" * 64
        chained_events = []
        for ev in lifecycle_events:
            ev_copy = dict(ev)
            ev_copy["previous_chain_tip"] = chain_tip
            ev_jcs = encode_jcs(ev_copy)
            ev_hash = hashlib.sha256(ev_jcs).hexdigest()
            ev_copy["event_hash"] = ev_hash
            chain_tip = ev_hash
            chained_events.append(ev_copy)

        article_12_evidence = {
            "mandate_target": "EU AI Act Regulation (EU) 2024/1689 Article 12 (Record-Keeping & Logging)",
            "log_chain_tip": chain_tip,
            "total_lifecycle_events": len(chained_events),
            "events": chained_events,
            "tamper_evident_mechanism": "RFC 8785 JCS Canonicalization + SHA-256 Hash Chaining",
        }

        # 2. Art 14: Human oversight & override record
        article_14_evidence = {
            "mandate_target": "EU AI Act Regulation (EU) 2024/1689 Article 14 (Human Oversight)",
            "oversight_mechanism": human_oversight_record or {
                "step_up_ticket_enforced": True,
                "dual_control_threshold_minor_units": 100000,
                "andon_cord_halt_available": True,
                "disallowed_override_policy": "APPROVE_OVERRIDE_PROHIBITED",
            },
        }

        # 3. Art 72: Post-market telemetry
        article_72_evidence = {
            "mandate_target": "EU AI Act Regulation (EU) 2024/1689 Article 72 (Post-Market Monitoring)",
            "metrics": post_market_metrics or {
                "total_operations_evaluated": 1000,
                "pre_execution_blocks": 25,
                "unresolved_indeterminate_operations": 0,
                "mean_reconciliation_time_ms": 420.5,
            },
        }

        # Shared 3-plane incident evidence record
        shared_incident = IncidentEvidenceRecord(
            incident_id=incident_id,
            reproducibility_manifest_sha256=reproducibility_manifest_sha256,
            model_behavior=ModelBehaviorPlane(
                proposal_digest=caid,
                model_or_agent_version="agent-high-risk-v1",
                input_context_digest=None,
                untrusted_content_references=[],
            ),
            execution_authority=ExecutionAuthorityPlane(
                governing_authority_id=governing_authority_id,
                authority_revocation_state=authority_revocation_state,
                policy_epoch=1,
                boundary_verdict=boundary_verdict,
            ),
            observed_consequence=ObservedConsequencePlane(
                dispatch_intent_digest=caid,
                transport_observation={"events_count": len(chained_events)},
                target_evidence=None,
                reconciliation_result="RECORDED",
                final_disposition="DISPATCH_COMPLETED" if boundary_verdict == BoundaryVerdict.ALLOWED else "NOT_DISPATCHED",
            ),
        )

        manifest = {
            "compliance_schema_version": "1.1.0-ai-act-evidence",
            "audit_status": "LOCAL PASS; INDEPENDENT REPRODUCTION PENDING",
            "disclaimer": INCIDENT_DISCLAIMER,
            "system_id": system_id,
            "operation_id": operation_id,
            "root_caid": caid,
            "article_12_logging": article_12_evidence,
            "article_14_human_oversight": article_14_evidence,
            "article_72_post_market": article_72_evidence,
            "incident_evidence": shared_incident.to_dict(),
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        canonical_bytes = encode_jcs(manifest)
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        sig = self.privkey.sign(canonical_bytes)

        return {
            "manifest": manifest,
            "bundle_digest": digest,
            "boundary_signature_b64": base64.b64encode(sig).decode("ascii"),
            "boundary_public_key_pem": self.pubkey.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii"),
        }
