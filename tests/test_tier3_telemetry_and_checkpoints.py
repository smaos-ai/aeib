"""
tests/test_tier3_telemetry_and_checkpoints.py
Tests verifying Tier 3.2 OpenTelemetry Semantic Telemetry Projection and Tier 3.3 External Witness Checkpoint Anchor:
  1. OpenTelemetry mapping of all 7 AEIB execution phases:
     - PRE_DISPATCH_COMMITTED -> gen_ai.agent.action.pre_commit
     - DISPATCH_AUTHORIZED -> gen_ai.agent.action.dispatch
     - EFFECT_INDETERMINATE -> gen_ai.agent.action.uncertain_transport
     - PROBE_DISPATCHED -> gen_ai.agent.action.reconcile_probe
     - CONFIRMED -> gen_ai.agent.action.confirmed
     - REFUTED -> gen_ai.agent.action.refuted
     - NOT_DISPATCHED -> gen_ai.agent.action.held
  2. W3C traceparent round-trip parsing, generation, and validation:
     - Canonical traceparent parsing and header formatting.
     - Child trace context inheritance and span link continuity.
     - Strict rejection of all-zero identifiers, version 'ff', and invalid formats.
  3. Telemetry isolation verification:
     - Telemetry is outbound observer only.
     - Simulated telemetry exceptions do not alter dispatch decisions or allow unauthorized actions.
  4. Merkle checkpoint calculation and Ed25519 witness signature verification:
     - RFC 6962 binary SHA-256 Merkle root computation (single, paired, odd duplication).
     - RFC 8785 JCS canonicalization and Ed25519 signature verification.
     - Tampered commitments fail signature verification.
  5. Outage simulation and local buffering:
     - Unreachable witness transitions anchor state to ANCHOR_STATE_OUTAGE.
     - Dispatches marked DISPATCH_UNANCHORED_LOCAL_ONLY.
     - Sequence numbers and hash chain continuously linked across buffer.
  6. Outage ceiling breach interlocks:
     - Exceeding max_outage_seconds raises CheckpointOutageCeilingExceededError.
     - Exceeding max_unanchored_batches raises CheckpointOutageCeilingExceededError.
  7. Outage recovery, burst reconciliation, and tamper detection:
     - Burst reconciliation verifies cumulative continuity and signs buffered checkpoints.
     - Emits signed OutageReconciliationReceipt and returns to ANCHOR_STATE_ACTIVE.
     - Interrupted or tampered hash chains raise CheckpointContinuityError.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import importlib.util
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jcs_canonicalizer import encode_jcs

REPO_ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_PATH = REPO_ROOT / "v1.1-roadmap" / "telemetry_correlation_bridge.py"
CHECKPOINT_PATH = REPO_ROOT / "v1.1-roadmap" / "external_checkpoint_anchor.py"

spec_tel = importlib.util.spec_from_file_location("telemetry_correlation_bridge", TELEMETRY_PATH)
assert spec_tel is not None and spec_tel.loader is not None
tel_mod = importlib.util.module_from_spec(spec_tel)
sys.modules["telemetry_correlation_bridge"] = tel_mod
spec_tel.loader.exec_module(tel_mod)

spec_chk = importlib.util.spec_from_file_location("external_checkpoint_anchor", CHECKPOINT_PATH)
assert spec_chk is not None and spec_chk.loader is not None
chk_mod = importlib.util.module_from_spec(spec_chk)
sys.modules["external_checkpoint_anchor"] = chk_mod
spec_chk.loader.exec_module(chk_mod)

ANCHOR_STATE_ACTIVE = chk_mod.ANCHOR_STATE_ACTIVE
ANCHOR_STATE_OUTAGE = chk_mod.ANCHOR_STATE_OUTAGE
DISPATCH_UNANCHORED_LOCAL_ONLY = chk_mod.DISPATCH_UNANCHORED_LOCAL_ONLY
RECONCILE_OUTAGE_BURST = chk_mod.RECONCILE_OUTAGE_BURST
STATUS_ANCHORED = chk_mod.STATUS_ANCHORED
AnchoredCheckpoint = chk_mod.AnchoredCheckpoint
CheckpointCommitment = chk_mod.CheckpointCommitment
CheckpointContinuityError = chk_mod.CheckpointContinuityError
CheckpointOutageCeilingExceededError = chk_mod.CheckpointOutageCeilingExceededError
ExternalWitnessCheckpointAnchor = chk_mod.ExternalWitnessCheckpointAnchor
OutageReconciliationReceipt = chk_mod.OutageReconciliationReceipt
compute_merkle_root = chk_mod.compute_merkle_root

PHASE_EVENT_MAP = tel_mod.PHASE_EVENT_MAP
InvalidTraceparentError = tel_mod.InvalidTraceparentError
SpanContext = tel_mod.SpanContext
TelemetryCorrelationBridge = tel_mod.TelemetryCorrelationBridge
TelemetryIsolationViolationError = tel_mod.TelemetryIsolationViolationError
TraceParent = tel_mod.TraceParent
generate_traceparent = tel_mod.generate_traceparent
parse_traceparent = tel_mod.parse_traceparent


# =========================================================================
# Tier 3.2 Tests: OpenTelemetry Semantic Telemetry Projection
# =========================================================================

def test_all_seven_phases_mapped_to_genai_conventions():
    """Evaluates that all 7 AEIB execution phases map to GenAI semantic conventions."""
    expected_mapping = {
        "PRE_DISPATCH_COMMITTED": "gen_ai.agent.action.pre_commit",
        "DISPATCH_AUTHORIZED": "gen_ai.agent.action.dispatch",
        "EFFECT_INDETERMINATE": "gen_ai.agent.action.uncertain_transport",
        "PROBE_DISPATCHED": "gen_ai.agent.action.reconcile_probe",
        "CONFIRMED": "gen_ai.agent.action.confirmed",
        "REFUTED": "gen_ai.agent.action.refuted",
        "NOT_DISPATCHED": "gen_ai.agent.action.held",
    }

    bridge = TelemetryCorrelationBridge()
    span_ctx = bridge.start_trace(operation_id="op-test-all-phases")

    observed_event_names = []
    for phase, expected_otel_name in expected_mapping.items():
        assert PHASE_EVENT_MAP[phase] == expected_otel_name
        ev = bridge.record_phase_event(
            span_context=span_ctx,
            phase=phase,
            action_caid="caid-" + phase.lower(),
            target_tool="db_transfer",
            extra_attributes={
                "effect_id": f"eff-{phase.lower()}",
                "disposition": phase,
                "retry_safe": (phase in ("EFFECT_INDETERMINATE", "NOT_DISPATCHED")),
            },
        )
        assert ev["name"] == expected_otel_name
        assert ev["attributes"]["gen_ai.system"] == "aeib"
        assert ev["attributes"]["gen_ai.agent.action.phase"] == phase
        assert ev["attributes"]["gen_ai.agent.action.caid"] == "caid-" + phase.lower()
        assert ev["attributes"]["gen_ai.agent.action.tool_name"] == "db_transfer"
        assert ev["attributes"]["aeib.effect_id"] == f"eff-{phase.lower()}"
        assert ev["attributes"]["aeib.disposition"] == phase
        observed_event_names.append(ev["name"])

    assert len(observed_event_names) == 7

    # Export to OTLP dictionary and verify structure
    otlp_dict = bridge.export_spans_otlp_dict()
    assert "resourceSpans" in otlp_dict
    resource_spans = otlp_dict["resourceSpans"]
    assert len(resource_spans) == 1

    scope_spans = resource_spans[0]["scopeSpans"]
    assert len(scope_spans) == 1

    spans = scope_spans[0]["spans"]
    assert len(spans) == 1
    assert spans[0]["traceId"] == span_ctx.trace_id
    assert spans[0]["spanId"] == span_ctx.span_id
    assert len(spans[0]["events"]) == 7

    # Export to JSON
    json_str = bridge.export_spans_json()
    parsed_json = json.loads(json_str)
    assert parsed_json["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["spanId"] == span_ctx.span_id


def test_w3c_traceparent_roundtrip_and_parsing():
    """Evaluates W3C Trace Context parsing, generation, and validation."""
    valid_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    valid_span_id = "00f067aa0ba902b7"
    valid_traceparent = f"00-{valid_trace_id}-{valid_span_id}-01"

    parsed = parse_traceparent(valid_traceparent)
    assert parsed.version == "00"
    assert parsed.trace_id == valid_trace_id
    assert parsed.span_id == valid_span_id
    assert parsed.trace_flags == "01"
    assert parsed.to_header() == valid_traceparent

    generated = generate_traceparent(trace_id=valid_trace_id, span_id=valid_span_id, trace_flags="01")
    assert generated == valid_traceparent

    # Test child span trace continuation
    bridge = TelemetryCorrelationBridge()
    child_ctx = bridge.start_trace(parent_traceparent=valid_traceparent)
    assert child_ctx.trace_id == valid_trace_id
    assert child_ctx.parent_span_id == valid_span_id
    assert child_ctx.span_id != valid_span_id
    assert child_ctx.trace_flags == "01"


def test_w3c_traceparent_invalid_rejections():
    """Evaluates fail-closed rejection of invalid W3C traceparent headers."""
    # Version ff is forbidden
    with pytest.raises(InvalidTraceparentError):
        parse_traceparent("ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")

    # All zeros trace_id is forbidden
    with pytest.raises(InvalidTraceparentError):
        parse_traceparent("00-00000000000000000000000000000000-00f067aa0ba902b7-01")

    # All zeros span_id is forbidden
    with pytest.raises(InvalidTraceparentError):
        parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01")

    # Non-hex characters
    with pytest.raises(InvalidTraceparentError):
        parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e47zz-00f067aa0ba902b7-01")

    # Wrong field count
    with pytest.raises(InvalidTraceparentError):
        parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-01")


def test_telemetry_isolation_assertion():
    """Evaluates that telemetry failures cannot alter gate verdicts or permit unauthorized dispatches."""
    bridge = TelemetryCorrelationBridge()

    # Built-in reference assertion
    assert bridge.assert_telemetry_isolation() is True

    # Custom gate test: unauthorized action must remain rejected even under simulated telemetry failure
    def _strict_firewall_gate(action: Dict[str, Any]) -> Tuple[bool, str]:
        if action.get("role") != "admin_disburser":
            return (False, "NOT_DISPATCHED")
        return (True, "DISPATCH_AUTHORIZED")

    unauth_candidate = {"role": "unauthorized_worker", "amount": 1000}
    assert bridge.assert_telemetry_isolation(gate_fn=_strict_firewall_gate, candidate_action=unauth_candidate) is True

    # Clear bridge
    bridge.clear()
    assert bridge.export_spans_otlp_dict()["resourceSpans"][0]["scopeSpans"][0]["spans"] == []


# =========================================================================
# Tier 3.3 Tests: External Witness Checkpoint Anchor & Outage Resilience
# =========================================================================

def test_merkle_root_computation_and_invariants():
    """Evaluates SHA-256 Merkle root computation over various leaf count configurations."""
    # Empty leaf list produces SHA-256 of empty bytes
    empty_root = compute_merkle_root([])
    assert empty_root == hashlib.sha256(b"").hexdigest()

    # Single leaf produces itself
    leaf_a = hashlib.sha256(b"leaf-A").hexdigest()
    assert compute_merkle_root([leaf_a]) == leaf_a

    # Two leaves produce SHA-256(A + B)
    leaf_b = hashlib.sha256(b"leaf-B").hexdigest()
    expected_pair_root = hashlib.sha256(bytes.fromhex(leaf_a) + bytes.fromhex(leaf_b)).hexdigest()
    assert compute_merkle_root([leaf_a, leaf_b]) == expected_pair_root

    # Three leaves (odd count): duplicates last leaf per RFC 6962
    leaf_c = hashlib.sha256(b"leaf-C").hexdigest()
    parent_ab = hashlib.sha256(bytes.fromhex(leaf_a) + bytes.fromhex(leaf_b)).digest()
    parent_cc = hashlib.sha256(bytes.fromhex(leaf_c) + bytes.fromhex(leaf_c)).digest()
    expected_three_root = hashlib.sha256(parent_ab + parent_cc).hexdigest()
    assert compute_merkle_root([leaf_a, leaf_b, leaf_c]) == expected_three_root

    # Invalid leaf hash format raises ValueError
    with pytest.raises(ValueError):
        compute_merkle_root(["short_hex"])


def test_active_checkpoint_creation_and_signature_verification():
    """Evaluates active checkpoint creation, canonical JCS encoding, and Ed25519 signature verification."""
    witness_key = Ed25519PrivateKey.generate()
    anchor = ExternalWitnessCheckpointAnchor(witness_private_key=witness_key)

    leaf_1 = hashlib.sha256(b"entry-001").hexdigest()
    leaf_2 = hashlib.sha256(b"entry-002").hexdigest()

    checkpoint = anchor.create_checkpoint(leaf_hashes=[leaf_1, leaf_2])

    assert checkpoint.status == STATUS_ANCHORED
    assert checkpoint.commitment.checkpoint_seq == 1
    assert checkpoint.commitment.start_seq == 1
    assert checkpoint.commitment.end_seq == 2
    assert checkpoint.commitment.previous_checkpoint_root == "00" * 32
    assert checkpoint.commitment.merkle_root == compute_merkle_root([leaf_1, leaf_2])

    # Verify signature using public key
    assert checkpoint.verify_signature() is True
    assert checkpoint.verify_signature(witness_key.public_key()) is True

    # Tampered commitment verification fails
    tampered_commitment = CheckpointCommitment(
        checkpoint_seq=1,
        start_seq=1,
        end_seq=999,  # tampered
        merkle_root=checkpoint.commitment.merkle_root,
        previous_checkpoint_root=checkpoint.commitment.previous_checkpoint_root,
        timestamp_utc=checkpoint.commitment.timestamp_utc,
    )
    tampered_cp = AnchoredCheckpoint(
        commitment=tampered_commitment,
        witness_public_key_hex=checkpoint.witness_public_key_hex,
        signature_hex=checkpoint.signature_hex,
        status=STATUS_ANCHORED,
    )
    assert tampered_cp.verify_signature() is False


def test_outage_buffering_and_unanchored_dispatches():
    """Evaluates witness outage window buffering and DISPATCH_UNANCHORED_LOCAL_ONLY status."""
    witness_key = Ed25519PrivateKey.generate()
    anchor = ExternalWitnessCheckpointAnchor(witness_private_key=witness_key)

    # Initial checkpoint in active state
    cp1 = anchor.create_checkpoint(leaf_hashes=[hashlib.sha256(b"batch-1").hexdigest()])
    assert cp1.status == STATUS_ANCHORED
    assert anchor.state == ANCHOR_STATE_ACTIVE

    # Witness becomes unreachable
    anchor.set_witness_availability(False, current_time_epoch=1000.0)
    assert anchor.state == ANCHOR_STATE_OUTAGE

    # Dispatches during outage buffered locally
    cp2 = anchor.create_checkpoint(
        leaf_hashes=[hashlib.sha256(b"batch-2").hexdigest()],
        current_time_epoch=1010.0,
    )
    assert cp2.status == DISPATCH_UNANCHORED_LOCAL_ONLY
    assert cp2.signature_hex == ""
    assert cp2.commitment.checkpoint_seq == 2
    assert cp2.commitment.previous_checkpoint_root == cp1.commitment.merkle_root

    cp3 = anchor.create_checkpoint(
        leaf_hashes=[hashlib.sha256(b"batch-3").hexdigest()],
        current_time_epoch=1020.0,
    )
    assert cp3.status == DISPATCH_UNANCHORED_LOCAL_ONLY
    assert cp3.commitment.checkpoint_seq == 3
    assert cp3.commitment.previous_checkpoint_root == cp2.commitment.merkle_root

    assert len(anchor.unanchored_buffer) == 2


def test_outage_duration_ceiling_breach():
    """Evaluates safety interlock when outage duration exceeds max_outage_seconds."""
    witness_key = Ed25519PrivateKey.generate()
    anchor = ExternalWitnessCheckpointAnchor(
        witness_private_key=witness_key,
        max_outage_seconds=120.0,
    )

    # Trigger outage at t = 1000.0
    anchor.set_witness_availability(False, current_time_epoch=1000.0)

    # At t = 1050.0 (50s elapsed <= 120s): permitted
    anchor.create_checkpoint(
        leaf_hashes=[hashlib.sha256(b"entry").hexdigest()],
        current_time_epoch=1050.0,
    )

    # At t = 1130.0 (130s elapsed > 120s): ceiling breach
    with pytest.raises(CheckpointOutageCeilingExceededError) as exc_info:
        anchor.create_checkpoint(
            leaf_hashes=[hashlib.sha256(b"entry-late").hexdigest()],
            current_time_epoch=1130.0,
        )
    assert "exceeded configured ceiling" in str(exc_info.value)


def test_outage_batch_count_ceiling_breach():
    """Evaluates safety interlock when buffered batch count exceeds max_unanchored_batches."""
    witness_key = Ed25519PrivateKey.generate()
    anchor = ExternalWitnessCheckpointAnchor(
        witness_private_key=witness_key,
        max_unanchored_batches=3,
        max_outage_seconds=1000.0,
    )

    anchor.set_witness_availability(False, current_time_epoch=100.0)

    for i in range(3):
        anchor.create_checkpoint(
            leaf_hashes=[hashlib.sha256(f"batch-{i}".encode()).hexdigest()],
            current_time_epoch=100.0 + i,
        )

    assert len(anchor.unanchored_buffer) == 3

    # Attempting 4th unanchored batch reaches ceiling
    with pytest.raises(CheckpointOutageCeilingExceededError) as exc_info:
        anchor.create_checkpoint(
            leaf_hashes=[hashlib.sha256(b"batch-overflow").hexdigest()],
            current_time_epoch=105.0,
        )
    assert "reached configured ceiling" in str(exc_info.value)


def test_outage_recovery_burst_reconciliation_and_continuity():
    """Evaluates burst reconciliation across outage window and receipt verification."""
    witness_key = Ed25519PrivateKey.generate()
    anchor = ExternalWitnessCheckpointAnchor(
        witness_private_key=witness_key,
        max_outage_seconds=300.0,
    )

    # Phase 1: Pre-outage active checkpoint
    leaf_p1 = hashlib.sha256(b"pre-outage").hexdigest()
    cp_active = anchor.create_checkpoint(leaf_hashes=[leaf_p1], current_time_epoch=100.0)
    assert cp_active.status == STATUS_ANCHORED
    prior_anchored_root = cp_active.commitment.merkle_root

    # Phase 2: Enter outage and buffer 3 unanchored batches
    anchor.set_witness_availability(False, current_time_epoch=110.0)

    unanchored_leaves = [
        [hashlib.sha256(f"outage-batch-{i}-leaf-{j}".encode()).hexdigest() for j in range(2)]
        for i in range(3)
    ]

    for idx, batch in enumerate(unanchored_leaves):
        anchor.create_checkpoint(leaf_hashes=batch, current_time_epoch=110.0 + (idx * 10))

    assert len(anchor.unanchored_buffer) == 3
    assert anchor.state == ANCHOR_STATE_OUTAGE

    # Phase 3: Outage ends, witness resumes connectivity, burst reconciliation executed
    receipt = anchor.reconcile_outage_burst(current_time_epoch=160.0)

    # Verify receipt fields
    assert receipt.action_phase == RECONCILE_OUTAGE_BURST
    assert receipt.start_checkpoint_seq == 2
    assert receipt.end_checkpoint_seq == 4
    assert receipt.reconciled_batch_count == 3
    assert receipt.prior_anchored_root == prior_anchored_root
    assert receipt.outage_duration_seconds == 50.0  # 160.0 - 110.0
    assert receipt.verify_signature() is True
    assert receipt.verify_signature(witness_key.public_key()) is True

    # Verify anchor state returned to active and buffer emptied
    assert anchor.state == ANCHOR_STATE_ACTIVE
    assert len(anchor.unanchored_buffer) == 0

    # Verify all 3 formerly unanchored checkpoints are now signed and anchored
    assert len(anchor.anchored_history) == 4  # 1 pre-outage + 3 burst
    for cp in anchor.anchored_history:
        assert cp.status == STATUS_ANCHORED
        assert cp.verify_signature() is True

    # Phase 4: Subsequent checkpoint anchors cleanly on top of the reconciled chain
    leaf_post = hashlib.sha256(b"post-outage").hexdigest()
    cp_post = anchor.create_checkpoint(leaf_hashes=[leaf_post], current_time_epoch=170.0)
    assert cp_post.status == STATUS_ANCHORED
    assert cp_post.commitment.checkpoint_seq == 5
    assert cp_post.commitment.previous_checkpoint_root == receipt.latest_anchored_root
    assert cp_post.verify_signature() is True


def test_outage_burst_continuity_violation_tamper_detection():
    """Evaluates fail-closed rejection when hash-chain continuity is broken during outage."""
    witness_key = Ed25519PrivateKey.generate()
    anchor = ExternalWitnessCheckpointAnchor(witness_private_key=witness_key)

    anchor.create_checkpoint(leaf_hashes=[hashlib.sha256(b"c0").hexdigest()])
    anchor.set_witness_availability(False, current_time_epoch=10.0)

    anchor.create_checkpoint(leaf_hashes=[hashlib.sha256(b"c1").hexdigest()], current_time_epoch=15.0)
    anchor.create_checkpoint(leaf_hashes=[hashlib.sha256(b"c2").hexdigest()], current_time_epoch=20.0)

    # Tamper with the 2nd buffered checkpoint's previous_checkpoint_root
    bad_commitment = CheckpointCommitment(
        checkpoint_seq=anchor.unanchored_buffer[1].commitment.checkpoint_seq,
        start_seq=anchor.unanchored_buffer[1].commitment.start_seq,
        end_seq=anchor.unanchored_buffer[1].commitment.end_seq,
        merkle_root=anchor.unanchored_buffer[1].commitment.merkle_root,
        previous_checkpoint_root="ff" * 32,  # tampered root
        timestamp_utc=anchor.unanchored_buffer[1].commitment.timestamp_utc,
    )
    anchor.unanchored_buffer[1] = AnchoredCheckpoint(
        commitment=bad_commitment,
        witness_public_key_hex=anchor.witness_public_key_hex,
        signature_hex="",
        status=DISPATCH_UNANCHORED_LOCAL_ONLY,
    )

    # Attempting burst reconciliation must fail closed with CheckpointContinuityError
    with pytest.raises(CheckpointContinuityError) as exc_info:
        anchor.reconcile_outage_burst(current_time_epoch=25.0)
    assert "Hash-chain discontinuity" in str(exc_info.value)
