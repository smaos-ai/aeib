"""
Unit and fail-closed tests for AEIB Shared Incident Evidence Schema v1.1.
Verifies the four incident fields, explicit enums, 3 separated evidence planes,
and fail-closed behavior on missing, invalid, or unknown fields.
Zero-mock Ed25519 cryptography and strict RFC 8785 canonicalization.
"""

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.incident_evidence import (
    IncidentEvidenceRecord,
    ModelBehaviorPlane,
    ExecutionAuthorityPlane,
    ObservedConsequencePlane,
    AuthorityRevocationState,
    BoundaryVerdict,
    INCIDENT_DISCLAIMER,
    sign_incident_evidence,
    verify_signed_incident_evidence,
)


def _valid_record() -> IncidentEvidenceRecord:
    return IncidentEvidenceRecord(
        incident_id="INC-2026-TEST-01",
        reproducibility_manifest_sha256="a" * 64,
        model_behavior=ModelBehaviorPlane(
            proposal_digest="b" * 64,
            model_or_agent_version="agent-model-v1.0",
            input_context_digest="c" * 64,
            untrusted_content_references=[{"source": "rag_kb", "reference_id": "doc-99"}],
        ),
        execution_authority=ExecutionAuthorityPlane(
            governing_authority_id="grant-root-01",
            authority_revocation_state=AuthorityRevocationState.VALID,
            policy_epoch=1,
            delegation_chain_digest="d" * 64,
            boundary_verdict=BoundaryVerdict.DENIED,
            rejection_code="POLICY_EPOCH_STALE",
        ),
        observed_consequence=ObservedConsequencePlane(
            dispatch_intent_digest="e" * 64,
            transport_observation={"connections_accepted": 0, "external_bytes_transmitted": 0},
            target_evidence=None,
            reconciliation_result=None,
            final_disposition="NOT_DISPATCHED",
        ),
    )


def test_incident_evidence_valid_roundtrip_and_signature():
    record = _valid_record()
    record.validate()
    d = record.to_dict()

    # Confirm 4 incident fields are present
    ea = d["execution_authority"]
    assert ea["governing_authority_id"] == "grant-root-01"
    assert ea["authority_revocation_state"] == "VALID"
    assert ea["boundary_verdict"] == "DENIED"
    assert d["reproducibility_manifest_sha256"] == "a" * 64

    # Confirm 3 planes are strictly separated
    assert "model_behavior" in d
    assert "execution_authority" in d
    assert "observed_consequence" in d

    # Confirm disclaimer
    assert d["disclaimer"] == INCIDENT_DISCLAIMER

    # Roundtrip from dict
    restored = IncidentEvidenceRecord.from_dict(d)
    assert restored.incident_id == record.incident_id
    assert restored.execution_authority.boundary_verdict == BoundaryVerdict.DENIED

    # Sign and verify
    privkey = ed25519.Ed25519PrivateKey.generate()
    bundle = sign_incident_evidence(record, privkey)

    valid, err = verify_signed_incident_evidence(bundle)
    assert valid is True
    assert err is None


def test_fail_closed_on_free_text_authority_revocation_state():
    d = _valid_record().to_dict()
    d["execution_authority"]["authority_revocation_state"] = "PENDING_INVESTIGATION"

    with pytest.raises(ValueError, match="authority_revocation_state"):
        IncidentEvidenceRecord.from_dict(d)


def test_fail_closed_on_free_text_boundary_verdict():
    d = _valid_record().to_dict()
    d["execution_authority"]["boundary_verdict"] = "MAYBE_ALLOWED"

    with pytest.raises(ValueError, match="boundary_verdict"):
        IncidentEvidenceRecord.from_dict(d)


def test_fail_closed_on_missing_evidence_plane():
    d = _valid_record().to_dict()
    del d["observed_consequence"]

    with pytest.raises(ValueError, match="Missing or invalid evidence plane: observed_consequence"):
        IncidentEvidenceRecord.from_dict(d)


def test_fail_closed_on_altered_disclaimer():
    d = _valid_record().to_dict()
    d["disclaimer"] = "AEIB automates all compliance submissions."

    with pytest.raises(ValueError, match="Disclaimer modified or missing mandatory legal framing statement"):
        IncidentEvidenceRecord.from_dict(d)


def test_fail_closed_on_invalid_hex_digest():
    d = _valid_record().to_dict()
    d["model_behavior"]["proposal_digest"] = "not-a-hex-digest"

    with pytest.raises(ValueError, match="proposal_digest"):
        IncidentEvidenceRecord.from_dict(d)


def test_fail_closed_on_negative_epoch():
    d = _valid_record().to_dict()
    d["execution_authority"]["policy_epoch"] = -1

    with pytest.raises(ValueError, match="policy_epoch must be non-negative integer"):
        IncidentEvidenceRecord.from_dict(d)


def test_falsification_tampered_bundle_signature():
    record = _valid_record()
    privkey = ed25519.Ed25519PrivateKey.generate()
    bundle = sign_incident_evidence(record, privkey)

    # Tamper payload
    bundle["incident_evidence"]["execution_authority"]["policy_epoch"] = 999
    valid, err = verify_signed_incident_evidence(bundle)
    assert valid is False
    assert "Digest mismatch" in err or "signature verification failed" in err
