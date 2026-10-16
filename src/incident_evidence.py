"""
AEIB Shared Incident Evidence Specification & Validation Module.
Part of SovereignNexus AEIB v1.1 Architecture.

Enforces strict separation of three evidence planes:
1. Untrusted CandidateAction proposal (model_behavior)
2. Authorization / standing evaluation (execution_authority)
3. Observed transport and reconciliation outcome (observed_consequence)

Enforces explicit enums and fail-closed validation for the four incident disclosure fields:
- governing_authority_id: string_or_null
- authority_revocation_state: VALID | EXPIRED | REVOKED | SUPERSEDED | UNKNOWN
- boundary_verdict: ALLOWED | DENIED | HELD | ESCALATED | NOT_EVALUATED | EFFECT_INDETERMINATE
- reproducibility_manifest_sha256: string_or_null

Mandatory Framing Disclaimer:
"AEIB exports structured incident evidence. The customer’s authorized incident-management
and legal functions determine classification, causation, reportability, and any regulatory submission."
"""

import re
import json
import time
import hashlib
import base64
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Real RFC 8785 JCS canonicalizer
from src.jcs_canonicalizer import encode_jcs


INCIDENT_DISCLAIMER = (
    "AEIB exports structured incident evidence. The customer’s authorized incident-management "
    "and legal functions determine classification, causation, reportability, and any regulatory submission."
)


class AuthorityRevocationState(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


class BoundaryVerdict(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    HELD = "HELD"
    ESCALATED = "ESCALATED"
    NOT_EVALUATED = "NOT_EVALUATED"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"


HEX_64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
INCIDENT_ID_PATTERN = re.compile(r"^INC-[a-zA-Z0-9_-]+$")


@dataclass
class ModelBehaviorPlane:
    proposal_digest: str
    model_or_agent_version: str
    input_context_digest: Optional[str] = None
    untrusted_content_references: List[Dict[str, Any]] = field(default_factory=list)

    def validate(self) -> None:
        if not self.proposal_digest or not HEX_64_PATTERN.match(self.proposal_digest):
            raise ValueError(f"Invalid proposal_digest: must be 64-char lowercase hex string, got {self.proposal_digest}")
        if not self.model_or_agent_version or not self.model_or_agent_version.strip():
            raise ValueError("model_or_agent_version cannot be empty")
        if self.input_context_digest is not None and not HEX_64_PATTERN.match(self.input_context_digest):
            raise ValueError(f"Invalid input_context_digest: {self.input_context_digest}")


@dataclass
class ExecutionAuthorityPlane:
    governing_authority_id: Optional[str]
    authority_revocation_state: AuthorityRevocationState
    policy_epoch: int
    boundary_verdict: BoundaryVerdict
    delegation_chain_digest: Optional[str] = None
    rejection_code: Optional[str] = None

    def validate(self) -> None:
        if not isinstance(self.authority_revocation_state, AuthorityRevocationState):
            try:
                self.authority_revocation_state = AuthorityRevocationState(str(self.authority_revocation_state))
            except ValueError:
                raise ValueError(
                    f"Invalid authority_revocation_state '{self.authority_revocation_state}'. "
                    f"Must be one of {[e.value for e in AuthorityRevocationState]}; fail-closed."
                )

        if not isinstance(self.boundary_verdict, BoundaryVerdict):
            try:
                self.boundary_verdict = BoundaryVerdict(str(self.boundary_verdict))
            except ValueError:
                raise ValueError(
                    f"Invalid boundary_verdict '{self.boundary_verdict}'. "
                    f"Must be one of {[e.value for e in BoundaryVerdict]}; fail-closed."
                )

        if not isinstance(self.policy_epoch, int) or self.policy_epoch < 0:
            raise ValueError(f"policy_epoch must be non-negative integer, got {self.policy_epoch}")

        if self.delegation_chain_digest is not None and not HEX_64_PATTERN.match(self.delegation_chain_digest):
            raise ValueError(f"Invalid delegation_chain_digest: {self.delegation_chain_digest}")


@dataclass
class ObservedConsequencePlane:
    dispatch_intent_digest: Optional[str] = None
    transport_observation: Optional[Dict[str, Any]] = None
    target_evidence: Optional[Dict[str, Any]] = None
    reconciliation_result: Optional[str] = None
    final_disposition: str = "NOT_DISPATCHED"

    def validate(self) -> None:
        if self.dispatch_intent_digest is not None and not HEX_64_PATTERN.match(self.dispatch_intent_digest):
            raise ValueError(f"Invalid dispatch_intent_digest: {self.dispatch_intent_digest}")
        if not self.final_disposition or not self.final_disposition.strip():
            raise ValueError("final_disposition cannot be empty")


@dataclass
class IncidentEvidenceRecord:
    incident_id: str
    model_behavior: ModelBehaviorPlane
    execution_authority: ExecutionAuthorityPlane
    observed_consequence: ObservedConsequencePlane
    reproducibility_manifest_sha256: Optional[str] = None
    schema_version: str = "1.1.0-incident-evidence"
    disclaimer: str = INCIDENT_DISCLAIMER
    exported_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def validate(self) -> None:
        if not self.incident_id or not INCIDENT_ID_PATTERN.match(self.incident_id):
            raise ValueError(f"Invalid incident_id: must match ^INC-[a-zA-Z0-9_-]+$, got {self.incident_id}")
        if self.schema_version != "1.1.0-incident-evidence":
            raise ValueError(f"Invalid schema_version: must be 1.1.0-incident-evidence, got {self.schema_version}")
        if self.disclaimer != INCIDENT_DISCLAIMER:
            raise ValueError("Disclaimer modified or missing mandatory legal framing statement")
        if self.reproducibility_manifest_sha256 is not None and not HEX_64_PATTERN.match(self.reproducibility_manifest_sha256):
            raise ValueError(f"Invalid reproducibility_manifest_sha256: {self.reproducibility_manifest_sha256}")

        self.model_behavior.validate()
        self.execution_authority.validate()
        self.observed_consequence.validate()

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "incident_id": self.incident_id,
            "schema_version": self.schema_version,
            "disclaimer": self.disclaimer,
            "reproducibility_manifest_sha256": self.reproducibility_manifest_sha256,
            "exported_at": self.exported_at,
            "model_behavior": {
                "proposal_digest": self.model_behavior.proposal_digest,
                "model_or_agent_version": self.model_behavior.model_or_agent_version,
                "input_context_digest": self.model_behavior.input_context_digest,
                "untrusted_content_references": self.model_behavior.untrusted_content_references,
            },
            "execution_authority": {
                "governing_authority_id": self.execution_authority.governing_authority_id,
                "authority_revocation_state": self.execution_authority.authority_revocation_state.value,
                "policy_epoch": self.execution_authority.policy_epoch,
                "delegation_chain_digest": self.execution_authority.delegation_chain_digest,
                "boundary_verdict": self.execution_authority.boundary_verdict.value,
                "rejection_code": self.execution_authority.rejection_code,
            },
            "observed_consequence": {
                "dispatch_intent_digest": self.observed_consequence.dispatch_intent_digest,
                "transport_observation": self.observed_consequence.transport_observation,
                "target_evidence": self.observed_consequence.target_evidence,
                "reconciliation_result": self.observed_consequence.reconciliation_result,
                "final_disposition": self.observed_consequence.final_disposition,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentEvidenceRecord":
        if not isinstance(data, dict):
            raise ValueError("Input data must be a dictionary")

        # Verify planes exist separately
        for plane_name in ("model_behavior", "execution_authority", "observed_consequence"):
            if plane_name not in data or not isinstance(data[plane_name], dict):
                raise ValueError(f"Missing or invalid evidence plane: {plane_name}; fail-closed.")

        mb_data = data["model_behavior"]
        ea_data = data["execution_authority"]
        oc_data = data["observed_consequence"]

        # Parse authority revocation state enum strictly
        raw_rev_state = ea_data.get("authority_revocation_state")
        try:
            rev_state = AuthorityRevocationState(raw_rev_state)
        except (ValueError, TypeError):
            raise ValueError(
                f"Unknown or invalid authority_revocation_state '{raw_rev_state}'. "
                f"Must be one of {[e.value for e in AuthorityRevocationState]}; fail-closed."
            )

        # Parse boundary verdict enum strictly
        raw_verdict = ea_data.get("boundary_verdict")
        try:
            verdict = BoundaryVerdict(raw_verdict)
        except (ValueError, TypeError):
            raise ValueError(
                f"Unknown or invalid boundary_verdict '{raw_verdict}'. "
                f"Must be one of {[e.value for e in BoundaryVerdict]}; fail-closed."
            )

        model_behavior = ModelBehaviorPlane(
            proposal_digest=mb_data.get("proposal_digest", ""),
            model_or_agent_version=mb_data.get("model_or_agent_version", ""),
            input_context_digest=mb_data.get("input_context_digest"),
            untrusted_content_references=mb_data.get("untrusted_content_references", []),
        )

        execution_authority = ExecutionAuthorityPlane(
            governing_authority_id=ea_data.get("governing_authority_id"),
            authority_revocation_state=rev_state,
            policy_epoch=ea_data.get("policy_epoch", 0),
            delegation_chain_digest=ea_data.get("delegation_chain_digest"),
            boundary_verdict=verdict,
            rejection_code=ea_data.get("rejection_code"),
        )

        observed_consequence = ObservedConsequencePlane(
            dispatch_intent_digest=oc_data.get("dispatch_intent_digest"),
            transport_observation=oc_data.get("transport_observation"),
            target_evidence=oc_data.get("target_evidence"),
            reconciliation_result=oc_data.get("reconciliation_result"),
            final_disposition=oc_data.get("final_disposition", "NOT_DISPATCHED"),
        )

        record = cls(
            incident_id=data.get("incident_id", ""),
            schema_version=data.get("schema_version", "1.1.0-incident-evidence"),
            disclaimer=data.get("disclaimer", INCIDENT_DISCLAIMER),
            reproducibility_manifest_sha256=data.get("reproducibility_manifest_sha256"),
            exported_at=data.get("exported_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            model_behavior=model_behavior,
            execution_authority=execution_authority,
            observed_consequence=observed_consequence,
        )
        record.validate()
        return record


def sign_incident_evidence(
    record: IncidentEvidenceRecord, privkey: ed25519.Ed25519PrivateKey
) -> Dict[str, Any]:
    """
    Canonicalizes the incident record via RFC 8785 JCS, computes SHA-256 digest,
    and signs it with the boundary Ed25519 private key.
    """
    record_dict = record.to_dict()
    canonical_bytes = encode_jcs(record_dict)
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    sig = privkey.sign(canonical_bytes)

    pubkey = privkey.public_key()
    pubkey_pem = pubkey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    return {
        "incident_evidence": record_dict,
        "evidence_digest": digest,
        "boundary_signature_b64": base64.b64encode(sig).decode("ascii"),
        "boundary_public_key_pem": pubkey_pem,
    }


def verify_signed_incident_evidence(bundle: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Clean-room offline verifier for signed incident evidence bundles.
    """
    if not isinstance(bundle, dict):
        return False, "Bundle must be a dict"

    record_dict = bundle.get("incident_evidence")
    if not record_dict:
        return False, "Missing incident_evidence in bundle"

    # Strict schema validation
    try:
        record = IncidentEvidenceRecord.from_dict(record_dict)
    except Exception as e:
        return False, f"Schema validation failed: {e}"

    # Recompute RFC 8785 canonical digest
    canonical_bytes = encode_jcs(record_dict)
    recomputed_digest = hashlib.sha256(canonical_bytes).hexdigest()
    if recomputed_digest != bundle.get("evidence_digest"):
        return False, f"Digest mismatch: {recomputed_digest} != {bundle.get('evidence_digest')}"

    # Verify signature
    pubkey_pem = bundle.get("boundary_public_key_pem")
    sig_b64 = bundle.get("boundary_signature_b64")
    if not pubkey_pem or not sig_b64:
        return False, "Missing boundary_public_key_pem or boundary_signature_b64"

    try:
        pubkey = serialization.load_pem_public_key(pubkey_pem.encode("ascii"))
        sig = base64.b64decode(sig_b64)
        pubkey.verify(sig, canonical_bytes)
    except Exception as e:
        return False, f"Ed25519 signature verification failed: {e}"

    return True, None
