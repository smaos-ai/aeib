"""
Unit and falsification tests for DORA Art. 17 and EU AI Act Art. 12/14/72 evidence exporters.
Zero-mock Ed25519 cryptography, strict RFC 8785 JCS canonicalization.
"""

import json
import base64
import pytest
from cryptography.hazmat.primitives import serialization

from tools.export_dora_art17_evidence import DoraArt17Exporter
from tools.export_ai_act_art12_14_evidence import EuAiActEvidenceExporter
from src.jcs_canonicalizer import encode_jcs


def test_dora_art17_exporter_happy_path_and_falsification():
    exporter = DoraArt17Exporter()
    bundle = exporter.generate_incident_package(
        incident_id="INC-2026-TEST-01",
        operation_id="op-test-101",
        caid="a" * 64,
        fault_type="HTTP_504_GATEWAY_TIMEOUT",
        detection_timestamp_utc="2026-10-16T04:00:00Z",
        classification_timestamp_utc="2026-10-16T04:02:00Z",
        resolved_timestamp_utc="2026-10-16T04:05:00Z",
        financial_impact_minor_units=50000,
        currency="EUR",
    )

    package = bundle["package"]
    assert package["dora_schema_version"] == "1.1.0-dora-art17"
    assert package["incident_id"] == "INC-2026-TEST-01"
    assert package["timeline"]["initial_notification_deadline_utc"] == "2026-10-16T08:02:00Z"
    assert package["incident_candidate"]["financial_exposure"] == "50000 EUR"

    # Verify Ed25519 signature over canonical RFC 8785 package
    pubkey = serialization.load_pem_public_key(bundle["boundary_public_key_pem"].encode("ascii"))
    sig = base64.b64decode(bundle["boundary_signature_b64"])
    pubkey.verify(sig, encode_jcs(package))

    # Falsification: tampered impact estimate fails signature verification
    tampered_package = dict(package)
    tampered_package["incident_candidate"] = dict(package["incident_candidate"])
    tampered_package["incident_candidate"]["financial_exposure"] = "0 EUR"
    with pytest.raises(Exception):
        pubkey.verify(sig, encode_jcs(tampered_package))


def test_eu_ai_act_exporter_hash_chain_and_falsification():
    exporter = EuAiActEvidenceExporter()
    events = [
        {"phase": "PRE_DISPATCH_COMMITTED", "timestamp": "2026-10-16T04:00:00Z"},
        {"phase": "DISPATCH_AUTHORIZED", "timestamp": "2026-10-16T04:00:01Z"},
        {"phase": "EFFECT_INDETERMINATE", "timestamp": "2026-10-16T04:00:05Z"},
        {"phase": "RECONCILED_CONFIRMED", "timestamp": "2026-10-16T04:00:08Z"},
    ]

    bundle = exporter.generate_compliance_bundle(
        system_id="system-audit-01",
        operation_id="op-test-202",
        caid="b" * 64,
        lifecycle_events=events,
    )

    manifest = bundle["manifest"]
    assert manifest["compliance_schema_version"] == "1.1.0-ai-act-evidence"
    assert manifest["article_12_logging"]["total_lifecycle_events"] == 4

    # Verify hash chain continuity in Art 12 events
    chained_events = manifest["article_12_logging"]["events"]
    assert chained_events[0]["previous_chain_tip"] == "0" * 64
    for i in range(1, len(chained_events)):
        assert chained_events[i]["previous_chain_tip"] == chained_events[i - 1]["event_hash"]

    # Verify Ed25519 signature
    pubkey = serialization.load_pem_public_key(bundle["boundary_public_key_pem"].encode("ascii"))
    sig = base64.b64decode(bundle["boundary_signature_b64"])
    pubkey.verify(sig, encode_jcs(manifest))

    # Falsification: altered event breaks verification
    tampered_manifest = dict(manifest)
    tampered_manifest["article_12_logging"] = dict(manifest["article_12_logging"])
    tampered_manifest["article_12_logging"]["total_lifecycle_events"] = 99
    with pytest.raises(Exception):
        pubkey.verify(sig, encode_jcs(tampered_manifest))
