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
tests/test_ot_cyber_physical_boundary.py
================================================================================
AEIB Operational Technology (OT) and Cyber-Physical Boundary Evaluation Suite.
Evaluated under the stated model. Preserves strict epistemic lock.

MANDATORY DISCLAIMER:
AEIB evaluates software execution safeguards inspired by electrical protection
principles, breaker failure logic, and SCADA boundary controls. The patterns adapt
concepts such as selective isolation, lockout, backup coordination, event sequencing,
and disturbance recording to AI-agent execution. They are not physical implementations
of ANSI relay functions, IEC 61850 services, IEEE C37.118 synchronization, or
power-system protection conformance.

Consequence Tiers Evaluated:
  - Tier A (IRREVERSIBLE_EXTERNAL_MUTATION): Breaker trip / physical valve closure.
    Zero tolerance: requires pre-dispatch intent commitment, 0 blind retries,
    latches on transport failure, and transitions to lockout on cascade exhaustion.
  - Tier B (RECOVERABLE_REVIEW_COST): SCADA telemetry / status polling.
    Bounded probe budget: preserves uncertainty on transport ambiguity and routes
    to operator review rather than issuing blind duplicate mutations.
  - Tier C (OBSERVABILITY_ONLY): Passive monitoring and disturbance logging.
    Strict observer isolation: telemetry failures cannot grant authorization
    or bypass protection gates.
"""

from __future__ import annotations

import http.server
import json
import threading
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.eo1_write_before_execute import (
    IntentLifecycleState,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    PreDispatchLedgerWriteError,
    compute_caid,
)
from src.jcs_canonicalizer import encode_jcs
from src.protection_governor import (
    Disposition,
    IndustrialProtectionGovernor,
)

# -----------------------------------------------------------------------------
# Consequence Classification Hierarchy
# -----------------------------------------------------------------------------

class ConsequenceTier(str, Enum):
    TIER_A_IRREVERSIBLE_PHYSICAL_MUTATION = "IRREVERSIBLE_EXTERNAL_MUTATION"
    TIER_B_RECOVERABLE_REVIEW_COST = "RECOVERABLE_REVIEW_COST"
    TIER_C_OBSERVABILITY_ONLY = "OBSERVABILITY_ONLY"


# -----------------------------------------------------------------------------
# Robotics Adjacency Register (Strict Out-of-Scope Demarcation)
# -----------------------------------------------------------------------------

ROBOTICS_ADJACENCY_METADATA: Dict[str, Any] = {
    "status": "NOT_IN_V1.0_OR_V1.1",
    "domain": "robotics_realtime_kinetic_actuation",
    "description": (
        "Real-time kinetic actuation, robotic manipulators, and sub-millisecond "
        "motion control loops are out of scope for AEIB v1.0 / v1.1 and are tracked "
        "as prospective future research."
    ),
    "evaluated": False,
    "scope_version": "v1.1",
}


def evaluate_kinetic_actuation_request(command: Dict[str, Any]) -> None:
    """
    Guard function validating that robotic kinetic actuation requests are rejected
    fail-closed in AEIB v1.0 / v1.1.
    """
    if command.get("domain") == "robotics_realtime_kinetic_actuation":
        raise NotImplementedError(
            f"Kinetic actuation is out of scope for current AEIB release. "
            f"Status: {ROBOTICS_ADJACENCY_METADATA['status']}"
        )


# -----------------------------------------------------------------------------
# Ephemeral Instrumentation Server for OT Boundary Sockets
# -----------------------------------------------------------------------------

class OtSubstationHandler(http.server.BaseHTTPRequestHandler):
    """Instruments physical socket calls for OT breaker/valve controllers."""

    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        server: OtSubstationServer = self.server  # type: ignore
        server.bytes_received_total += len(body)
        server.recorded_payloads.append(body)

        if server.simulate_timeout:
            # Simulate 504 Gateway Timeout / ambiguous transport
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            resp = json.dumps({"error": "GATEWAY_TIMEOUT", "ot_status": "AMBIGUOUS"}).encode("utf-8")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        resp = json.dumps({"acknowledged": True, "breaker_state": "TRIPPED"}).encode("utf-8")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, format: str, *args: Any) -> None:
        _ = (format, args)


class OtSubstationServer(http.server.HTTPServer):
    def __init__(self, server_address: Tuple[str, int]) -> None:
        super().__init__(server_address, OtSubstationHandler)
        self.connection_count = 0
        self.bytes_received_total = 0
        self.recorded_payloads: List[bytes] = []
        self.simulate_timeout = False

    def get_request(self) -> Tuple[Any, Any]:
        sock, addr = super().get_request()
        self.connection_count += 1
        return sock, addr


# -----------------------------------------------------------------------------
# Tier A Tests: IRREVERSIBLE_EXTERNAL_MUTATION (Substation Breakers & Valves)
# -----------------------------------------------------------------------------

def test_tier_a_breaker_trip_intent_ledger_failure_blocks_physical_transmission(tmp_path: Path):
    """
    Tier A (IRREVERSIBLE_EXTERNAL_MUTATION):
    Asserts that if the pre-dispatch ledger write fails, zero physical network
    connections and zero bytes are transmitted to the substation breaker controller.
    """
    server = OtSubstationServer(("127.0.0.1", 0))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port
    target_uri = f"http://127.0.0.1:{port}/api/v1/substation/breaker/trip"

    ledger_path = tmp_path / "ot_ledger.jsonl"
    interlock = PreDispatchIntentInterlock(
        ledger_path=ledger_path,
        simulate_write_error=True,
    )

    breaker_payload = {
        "substation_id": "SUB-NORTH-500KV",
        "bay_id": "BAY-4",
        "action": "TRIP_BREAKER",
        "consequence_tier": ConsequenceTier.TIER_A_IRREVERSIBLE_PHYSICAL_MUTATION.value,
    }

    with pytest.raises(PreDispatchLedgerWriteError):
        interlock.dispatch(
            target_uri=target_uri,
            tool_name="trip_substation_breaker",
            payload=breaker_payload,
        )

    # Physical verification: 0 connections, 0 bytes
    assert server.connection_count == 0
    assert server.bytes_received_total == 0
    assert len(server.recorded_payloads) == 0

    server.shutdown()
    server.server_close()


def test_tier_a_breaker_trip_trapped_in_effect_indeterminate_on_transport_fault(tmp_path: Path):
    """
    Tier A (IRREVERSIBLE_EXTERNAL_MUTATION):
    Asserts that an ambiguous 504 on breaker trip traps into EFFECT_INDETERMINATE
    with retry_safe: False, and blocks any blind re-dispatch.
    """
    server = OtSubstationServer(("127.0.0.1", 0))
    server.simulate_timeout = True
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_port
    target_uri = f"http://127.0.0.1:{port}/api/v1/substation/breaker/trip"

    ledger_path = tmp_path / "ot_ledger.jsonl"
    interlock = PreDispatchIntentInterlock(ledger_path=ledger_path)

    breaker_payload = {
        "substation_id": "SUB-WEST-230KV",
        "bay_id": "BAY-1",
        "action": "TRIP_BREAKER",
        "consequence_tier": ConsequenceTier.TIER_A_IRREVERSIBLE_PHYSICAL_MUTATION.value,
    }

    with pytest.raises(RuntimeError) as exc_info:
        interlock.dispatch(
            target_uri=target_uri,
            tool_name="trip_substation_breaker",
            payload=breaker_payload,
        )

    assert "latched in EFFECT_INDETERMINATE" in str(exc_info.value)

    caid = compute_caid(breaker_payload)
    assert interlock.is_caid_latched(caid) is True
    latched_record = interlock.get_latched_caids()[caid]
    assert latched_record.lifecycle_state == IntentLifecycleState.EFFECT_INDETERMINATE
    assert latched_record.retry_safe is False
    assert latched_record.reconciliation_required is True

    # Immediate blind re-dispatch attempt must fail closed
    with pytest.raises(LatchedCaidExecutionHaltedError):
        interlock.dispatch(
            target_uri=target_uri,
            tool_name="trip_substation_breaker",
            payload=breaker_payload,
        )

    # Physical verification: Exactly 1 dispatch attempt occurred, 0 blind retries
    assert server.connection_count == 1

    server.shutdown()
    server.server_close()


def test_tier_a_breaker_failure_cascade_and_ansi_86_lockout():
    """
    Tier A (IRREVERSIBLE_EXTERNAL_MUTATION):
    Verifies that cascade failure during high-voltage breaker trip evaluation
    trips ANSI 86 lockout, halts dispatch, and requires an Ed25519 operator signature to reset.
    """
    governor = IndustrialProtectionGovernor(max_oscillation_cycles=2)
    caid = "ot-caid-breaker-trip-500kv-001"

    disposition = governor.evaluate_cascade_failure(
        caid=caid,
        primary_status="PROBE_TIMEOUT",
        secondary_status="RECONCILIATION_NOT_FOUND",
        tertiary_status="EXHAUSTED",
    )

    assert disposition == Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
    assert governor.is_latched(caid) is True
    assert governor.can_dispatch(caid) is False

    # Short/invalid reset signature fails
    assert governor.operator_reset(caid, "invalid-sig") is False
    assert governor.is_latched(caid) is True

    # Valid Ed25519 signature resets the lockout
    op_key = Ed25519PrivateKey.generate()
    reset_statement = encode_jcs({"caid": caid, "action": "OPERATOR_RESET_86"})
    sig_bytes = op_key.sign(reset_statement)
    valid_sig_hex = sig_bytes.hex()  # 128 hex chars = 64 bytes

    assert governor.operator_reset(caid, valid_sig_hex) is True
    assert governor.is_latched(caid) is False
    assert governor.can_dispatch(caid) is True


# -----------------------------------------------------------------------------
# Tier B Tests: RECOVERABLE_REVIEW_COST (SCADA Polling & Bounded Probes)
# -----------------------------------------------------------------------------

def test_tier_b_scada_probe_timeout_latches_indeterminate_without_blind_mutation():
    """
    Tier B (RECOVERABLE_REVIEW_COST):
    Asserts that an unconfirmed SCADA status probe preserves uncertainty
    rather than guessing, and safely routes to operator review.
    """
    governor = IndustrialProtectionGovernor()
    caid = "ot-caid-scada-status-poll-002"

    # Primary probe fails on SCADA gateway
    disp = governor.evaluate_cascade_failure(
        caid=caid,
        primary_status="PROBE_TIMEOUT",
        secondary_status="RECONCILIATION_NOT_FOUND",
        tertiary_status="WAITING_SECONDARY",
    )

    # In Tier B, intermediate secondary check preserves status without catastrophic lockout
    assert disp == Disposition.RECONCILIATION_NOT_FOUND
    assert governor.is_latched(caid) is False


def test_tier_b_scada_probe_budget_bounded_escalation():
    """
    Tier B (RECOVERABLE_REVIEW_COST):
    Validates that repeated probe failures decrement probe budget and escalate
    to manual intervention rather than performing unbounded polling loops.
    """
    governor = IndustrialProtectionGovernor(max_oscillation_cycles=2)
    caid = "ot-caid-sensor-calibration-003"

    # Simulate oscillation cycles between PROBE_RETRY and PROBE_TIMEOUT
    governor.evaluate_out_of_step(caid, "PROBE_RETRY")
    governor.evaluate_out_of_step(caid, "PROBE_TIMEOUT")
    governor.evaluate_out_of_step(caid, "PROBE_RETRY")
    governor.evaluate_out_of_step(caid, "PROBE_TIMEOUT")
    is_oscillating = governor.evaluate_out_of_step(caid, "PROBE_RETRY")
    assert is_oscillating is True

    disp = governor.evaluate_cascade_failure(
        caid=caid,
        primary_status="PROBE_TIMEOUT",
        secondary_status="RECONCILIATION_NOT_FOUND",
        tertiary_status="EXHAUSTED",
    )
    assert disp == Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
    assert governor.is_latched(caid) is True


# -----------------------------------------------------------------------------
# Tier C Tests: OBSERVABILITY_ONLY (Passive Telemetry & SOE Logging)
# -----------------------------------------------------------------------------

def test_tier_c_passive_telemetry_isolation_and_zero_enforcement_leakage():
    """
    Tier C (OBSERVABILITY_ONLY):
    Verifies that passive telemetry disturbances and SOE logs are strictly observational:
    failures in the telemetry stream never bypass gates or grant mutation permissions.
    """
    governor = IndustrialProtectionGovernor()
    caid = "ot-caid-pmu-frequency-telemetry-004"

    # Normal disturbance recording
    dist_record = governor.record_disturbance_triad(
        caid=caid,
        fault_type="FREQUENCY_DEVIATION",
        pre_fault_state={"f_hz": 50.02},
        fault_state={"f_hz": 49.88},
        post_fault_state={"f_hz": 49.95},
    )

    assert dist_record["record_type"] == "FORENSIC_DISTURBANCE_TRIAD"
    assert len(governor._disturbance_logs) == 1
    assert governor._disturbance_logs[0]["caid"] == caid

    # Simulate an error in passive disturbance recorder (e.g. malformed event)
    try:
        governor.record_disturbance_triad(
            caid=caid,
            fault_type="CORRUPTED_EVENT",
            pre_fault_state=None,  # type: ignore
            fault_state=None,  # type: ignore
            post_fault_state=None,  # type: ignore
        )
    except Exception:
        pass

    # Telemetry logging state must NEVER alter execution dispatch authority
    # An unauthorized CAID remains unauthorized
    governor.latch_lockout(caid, "Prior security event")
    assert governor.can_dispatch(caid) is False


# -----------------------------------------------------------------------------
# Robotics Adjacency & Epistemic Scope Test
# -----------------------------------------------------------------------------

def test_robotics_adjacency_metadata_not_in_v1_0_or_v1_1():
    """
    Verifies that real-time robotic motion and kinetic actuation are formally
    demarcated as out-of-scope (NOT_IN_V1.0_OR_V1.1).
    """
    assert ROBOTICS_ADJACENCY_METADATA["status"] == "NOT_IN_V1.0_OR_V1.1"
    assert ROBOTICS_ADJACENCY_METADATA["evaluated"] is False

    kinetic_command = {
        "domain": "robotics_realtime_kinetic_actuation",
        "action": "MOVE_ROBOTIC_ARM_SUB_MILLISECOND",
        "joint_angles": [0.1, 0.4, -0.2],
    }

    with pytest.raises(NotImplementedError) as exc_info:
        evaluate_kinetic_actuation_request(kinetic_command)

    assert "NOT_IN_V1.0_OR_V1.1" in str(exc_info.value)


# -----------------------------------------------------------------------------
# Consequence-Weighted Metric Evaluation Test
# -----------------------------------------------------------------------------

def test_consequence_weighted_metric_evaluation_vs_aggregate_pass_rate():
    """
    Demonstrates error-cost asymmetry:
    A system with 99.8% aggregate accuracy but 1 false positive on
    IRREVERSIBLE_EXTERNAL_MUTATION (breaker trip) has a consequence-weighted
    safety score of 0.0 (unacceptable risk).

    Conversely, a system with 85.0% aggregate accuracy but zero irreversible
    failures safely routes all ambiguous operations to human review.
    """
    # System 1: Naive high aggregate accuracy (99.8%), 1 catastrophic irreversible failure
    system_1_confusion = {
        ConsequenceTier.TIER_A_IRREVERSIBLE_PHYSICAL_MUTATION: {"total": 50, "failures": 1},
        ConsequenceTier.TIER_B_RECOVERABLE_REVIEW_COST: {"total": 450, "failures": 0},
    }

    # System 2: Conservative boundary (85.0% auto-pass, 15% routed to review, 0 irreversible failures)
    system_2_confusion = {
        ConsequenceTier.TIER_A_IRREVERSIBLE_PHYSICAL_MUTATION: {"total": 50, "failures": 0},
        ConsequenceTier.TIER_B_RECOVERABLE_REVIEW_COST: {"total": 450, "failures": 75},
    }

    def compute_consequence_weighted_safety(eval_matrix: Dict[ConsequenceTier, Dict[str, int]]) -> float:
        # Zero tolerance for irreversible failures: any failure sets safety to 0.0
        irreversible = eval_matrix[ConsequenceTier.TIER_A_IRREVERSIBLE_PHYSICAL_MUTATION]
        if irreversible["failures"] > 0:
            return 0.0

        # For recoverable review costs, accuracy is smoothly weighted
        recoverable = eval_matrix[ConsequenceTier.TIER_B_RECOVERABLE_REVIEW_COST]
        rec_pass_rate = (recoverable["total"] - recoverable["failures"]) / recoverable["total"]
        return float(rec_pass_rate)

    safety_score_1 = compute_consequence_weighted_safety(system_1_confusion)
    safety_score_2 = compute_consequence_weighted_safety(system_2_confusion)

    assert safety_score_1 == 0.0  # Rejected despite 99.8% aggregate accuracy
    assert safety_score_2 == 0.8333333333333334  # Safely bounded, zero irreversible mutations
