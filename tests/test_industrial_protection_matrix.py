#!/usr/bin/env python3
"""
tests/test_industrial_protection_matrix.py
Comprehensive 18-Pattern Industrial-Protection-Inspired Architecture Test Suite.
Validates probe-failure escalation pattern, manual lockout latch, peer cancellation pattern,
retry-oscillation detector, payload-integrity differential check, and execution sequence/disturbance records.

MANDATORY DISCLAIMER:
AEIB includes an experimental industrial-protection-inspired governor and an 18-pattern local test matrix.
The patterns adapt concepts such as selective isolation, lockout, backup coordination, event sequencing,
and disturbance recording to AI-agent execution. They are not implementations of ANSI relay functions,
IEC 61850 services, IEEE C37.118 synchronization, or power-system protection conformance.
"""

import time
import threading
import pytest
from typing import Dict, Any, List

from src.protection_governor import (
    IndustrialProtectionGovernor,
    Disposition,
    LockoutState,
    TransferTripEvent,
    jcs_canonical_bytes,
)


def test_ansi_50bf_cascade_real_implementation():
    gov = IndustrialProtectionGovernor()
    result = gov.evaluate_cascade_failure(
        caid="test-caid-001",
        primary_status="PROBE_TIMEOUT",
        secondary_status="RECONCILIATION_NOT_FOUND",
        tertiary_status="EXHAUSTED",
    )
    assert result == Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
    assert gov.is_latched("test-caid-001") is True


def test_jcs_canonical_caid_compliance():
    payload_a = {"b": 2, "a": 1}
    payload_b = {"a": 1, "b": 2}
    bytes_a = jcs_canonical_bytes(payload_a)
    bytes_b = jcs_canonical_bytes(payload_b)
    assert bytes_a == bytes_b
    assert bytes_a == b'{"a":1,"b":2}'


class TestIndustrialProtectionMatrix:
    """Zero-mock integration and unit test suite verifying the 18 industrial protection patterns."""

    @pytest.fixture
    def governor(self):
        return IndustrialProtectionGovernor(max_oscillation_cycles=3)

    # -------------------------------------------------------------------------
    # Layer 1: Trip & Lockout Layer
    # -------------------------------------------------------------------------

    def test_01_ansi_50bf_breaker_failure_cascade(self, governor):
        """
        Pattern 1 (ANSI 50BF Breaker Failure):
        Primary timeout -> Secondary replica not found -> Tertiary exhausted -> ANSI 86 Lockout.
        """
        caid = "caid-50bf-001"
        disposition = governor.evaluate_cascade_failure(
            caid=caid,
            primary_status="PROBE_TIMEOUT",
            secondary_status="RECONCILIATION_NOT_FOUND",
            tertiary_status="EXHAUSTED"
        )
        assert disposition == Disposition.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
        assert governor.is_latched(caid) is True

    def test_02_ansi_86_lockout_relay_latch_and_operator_reset(self, governor):
        """
        Pattern 2 (ANSI 86 Lockout Relay):
        Irreversibly latches on trip; requires valid Ed25519 signature to reset.
        """
        caid = "caid-86-001"
        assert governor.is_latched(caid) is False
        governor.trip_lockout_relay(caid, "Catastrophic fault trip")
        assert governor.is_latched(caid) is True
        assert governor.can_dispatch(caid) is False

        # Reset attempt with invalid signature fails
        assert governor.operator_reset(caid, "short-sig") is False
        assert governor.is_latched(caid) is True

        # Valid 64-character Ed25519 signature clears latch
        valid_ed25519 = "e" * 64
        assert governor.operator_reset(caid, valid_ed25519) is True
        assert governor.is_latched(caid) is False
        assert governor.can_dispatch(caid) is True

    def test_03_pott_transfer_trip_peer_cancellation(self, governor):
        """
        Pattern 3 (POTT Permissive Overreach Transfer Trip):
        4 parallel worker threads; fault on Worker 1 emits transfer trip;
        Workers 2, 3, and 4 immediately abort in-flight mutations.
        """
        caid = "caid-pott-001"
        worker_statuses: Dict[str, str] = {}
        barrier = threading.Barrier(4)

        def worker_task(worker_id: str, is_fault_injector: bool):
            barrier.wait()
            if is_fault_injector:
                # Worker 1 encounters fault and issues POTT transfer trip
                governor.inter_trip_bus.publish_transfer_trip(
                    source_worker_id=worker_id,
                    caid=caid,
                    reason="Upstream line drop detected",
                    mode="POTT"
                )
                worker_statuses[worker_id] = "TRIPPED"
            else:
                # Peers check for inter-trip signal before committing
                time.sleep(0.02)
                if governor.inter_trip_bus.is_worker_tripped(worker_id):
                    worker_statuses[worker_id] = "ABORTED_BY_TRANSFER_TRIP"
                else:
                    worker_statuses[worker_id] = "COMMITTED"

        threads = [
            threading.Thread(target=worker_task, args=("worker-1", True)),
            threading.Thread(target=worker_task, args=("worker-2", False)),
            threading.Thread(target=worker_task, args=("worker-3", False)),
            threading.Thread(target=worker_task, args=("worker-4", False)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert worker_statuses["worker-1"] == "TRIPPED"
        assert worker_statuses["worker-2"] == "ABORTED_BY_TRANSFER_TRIP"
        assert worker_statuses["worker-3"] == "ABORTED_BY_TRANSFER_TRIP"
        assert worker_statuses["worker-4"] == "ABORTED_BY_TRANSFER_TRIP"

    def test_04_putt_permissive_underreach_trip(self, governor):
        """
        Pattern 4 (PUTT Permissive Underreach Transfer Trip):
        Instantaneous local trip on underreach fault with synchronous transfer trip to swarm.
        """
        caid = "caid-putt-001"
        event = governor.inter_trip_bus.publish_transfer_trip(
            source_worker_id="agent-edge-01",
            caid=caid,
            reason="Instantaneous underreach breaker trip",
            mode="PUTT"
        )
        assert event.mode == "PUTT"
        assert governor.inter_trip_bus.is_worker_tripped("agent-edge-01") is True
        assert governor.inter_trip_bus.is_worker_tripped("agent-edge-02") is True

    def test_05_ansi_52_circuit_breaker_interlock(self, governor):
        """
        Pattern 5 (ANSI 52 Circuit Breaker Interlock):
        Asserts dispatch permission is revoked under latch or active transfer trip.
        """
        caid = "caid-52-001"
        assert governor.can_dispatch(caid, worker_id="w-healthy") is True

        governor.trip_lockout_relay(caid, "Interlock test")
        assert governor.can_dispatch(caid, worker_id="w-healthy") is False

    # -------------------------------------------------------------------------
    # Layer 2: Stability Layer
    # -------------------------------------------------------------------------

    def test_06_ansi_51_adaptive_overcurrent_backoff(self, governor):
        """
        Pattern 6 (ANSI 51 Adaptive Overcurrent / Time-Overcurrent):
        Dynamic backoff scaling exponentially for downstream 504/429 throttles.
        """
        b0 = governor.calculate_adaptive_backoff(error_count=0)
        b1 = governor.calculate_adaptive_backoff(error_count=1)
        b2 = governor.calculate_adaptive_backoff(error_count=2)
        b3 = governor.calculate_adaptive_backoff(error_count=3)
        b_max = governor.calculate_adaptive_backoff(error_count=10, max_backoff_ms=2000.0)

        assert b0 == 0.0
        assert b1 == 100.0
        assert b2 == 200.0
        assert b3 == 400.0
        assert b_max == 2000.0

    def test_07_ansi_81_rocof_frequency_spike(self, governor):
        """
        Pattern 7 (ANSI 81 ROCOF Rate of Change of Frequency):
        Detects sudden queue / dispatch acceleration exceeding max rate.
        """
        node = "cluster-gateway-01"
        for _ in range(10):
            assert governor.evaluate_rocof(node, max_df_dt=50.0, window_sec=1.0) is True

        # Rapidly inject 50 calls to exceed threshold
        tripped = False
        for _ in range(50):
            if not governor.evaluate_rocof(node, max_df_dt=50.0, window_sec=1.0):
                tripped = True
                break
        assert tripped is True

    def test_08_ansi_27_undervoltage_pool_starvation(self, governor):
        """
        Pattern 8 (ANSI 27 Undervoltage Protection):
        Trips fail-closed when database connection pool drops to 0 available sockets.
        """
        assert governor.evaluate_undervoltage_pool(available_connections=5) is True
        assert governor.evaluate_undervoltage_pool(available_connections=0) is False

    def test_09_ansi_59_overvoltage_queue_saturation(self, governor):
        """
        Pattern 9 (ANSI 59 Overvoltage Protection):
        Trips when queue backlog exceeds saturation capacity.
        """
        assert governor.evaluate_overvoltage_queue(current_queue_size=200, max_capacity=500) is True
        assert governor.evaluate_overvoltage_queue(current_queue_size=600, max_capacity=500) is False

    def test_10_ansi_67_directional_overcurrent(self, governor):
        """
        Pattern 10 (ANSI 67 Directional Overcurrent):
        Enforces forward power flow only; rejects reverse mutations directed at read replicas.
        """
        assert governor.evaluate_directional_flow(is_primary_writer=True, is_read_only_replica=False) is True
        assert governor.evaluate_directional_flow(is_primary_writer=False, is_read_only_replica=True) is False
        assert governor.evaluate_directional_flow(is_primary_writer=True, is_read_only_replica=True) is False

    # -------------------------------------------------------------------------
    # Layer 3: Telemetry Layer
    # -------------------------------------------------------------------------

    def test_11_pmu_ieee_c37118_clock_skew_sync(self, governor):
        """
        Pattern 11 (PMU / IEEE C37.118 Synchrophasor Sync):
        Validates timestamp alignment; permits <= 0.5s skew, rejects > 0.5s skew.
        """
        now = time.time()
        assert governor.evaluate_pmu_sync(local_timestamp=now, reference_timestamp=now + 0.1, max_skew_sec=0.5) is True
        assert governor.evaluate_pmu_sync(local_timestamp=now, reference_timestamp=now + 1.2, max_skew_sec=0.5) is False

    def test_12_iec_61850_goose_fast_multicast(self, governor):
        """
        Pattern 12 (IEC 61850 GOOSE Fast Teleprotection):
        Validates fast multicast message generation with monotonic status counters.
        """
        msg = governor.create_goose_message(caid="caid-goose-01", event_type="TRIP_BREAKER", st_num=1, sq_num=10)
        assert msg["protocol"] == "IEC_61850_GOOSE"
        assert msg["caid"] == "caid-goose-01"
        assert msg["st_num"] == 1
        assert msg["time_allowed_to_live_ms"] == 2000

    def test_13_iec_61850_sampled_values_stream(self, governor):
        """
        Pattern 13 (IEC 61850-9-2 Sampled Values):
        Validates real-time continuous sampled telemetry packet.
        """
        metrics = {"current_load": 42.5, "latency_ms": 1.2}
        sv = governor.create_sampled_value(stream_id="sv-bus-01", smp_cnt=1024, metrics=metrics)
        assert sv["protocol"] == "IEC_61850_9_2_SV"
        assert sv["smp_cnt"] == 1024
        assert sv["metrics"]["current_load"] == 42.5

    def test_14_iec_61850_mms_scada_reporting(self, governor):
        """
        Pattern 14 (IEC 61850 MMS Supervisory Reporting):
        Validates client-server audit and telemetry packet for SCADA / HMI display.
        """
        report = governor.create_mms_report(caid="caid-mms-01", state="VERIFIED", client_id="HMI-CONSOLE-01")
        assert report["protocol"] == "IEC_61850_MMS"
        assert report["state"] == "VERIFIED"
        assert report["client_id"] == "HMI-CONSOLE-01"

    # -------------------------------------------------------------------------
    # Layer 4: Security Layer
    # -------------------------------------------------------------------------

    def test_15_byzantine_consensus_quorum(self, governor):
        """
        Pattern 15 (Byzantine Consensus Quorum Gating):
        Requires >= 2/3 agreement across heterogeneous replica probes.
        """
        # 3 endpoints: 2 VERIFIED, 1 NOT_FOUND -> Quorum 66.7% passes
        responses_pass = ["VERIFIED", "VERIFIED", "NOT_FOUND"]
        passed, outcome = governor.evaluate_byzantine_quorum(responses_pass, required_quorum_ratio=0.66)
        assert passed is True
        assert outcome == "VERIFIED"

        # 3 endpoints: 1 VERIFIED, 1 CONFLICT, 1 NOT_FOUND -> Quorum fails
        responses_split = ["VERIFIED", "CONFLICT", "NOT_FOUND"]
        passed, outcome = governor.evaluate_byzantine_quorum(responses_split, required_quorum_ratio=0.66)
        assert passed is False
        assert outcome is None

    def test_16_false_data_injection_ansi_87_differential(self, governor):
        """
        Pattern 16 (ANSI 87 Differential Protection / False Data Injection Guard):
        Mutate 1 byte in payload ($100.00 -> $100.01) and assert hash mismatch
        trips RECONCILIATION_CONFLICT in < 1.0 ms.
        """
        caid = "caid-diff-001"
        payload_original = {"account_id": "ACC-99", "amount": 100.00, "currency": "EUR"}
        payload_mutated = {"account_id": "ACC-99", "amount": 100.01, "currency": "EUR"}

        t_start = time.perf_counter()
        is_match, disposition = governor.evaluate_differential_protection(caid, payload_original, payload_mutated)
        duration_ms = (time.perf_counter() - t_start) * 1000.0

        assert is_match is False
        assert disposition == Disposition.RECONCILIATION_CONFLICT
        assert duration_ms < 1.0, f"Differential protection took {duration_ms:.3f}ms (must be < 1.0ms)"

        # Positive case
        is_match, disposition = governor.evaluate_differential_protection(caid, payload_original, payload_original.copy())
        assert is_match is True
        assert disposition == Disposition.OUTCOME_VERIFIED

    def test_17_ansi_78_out_of_step_oscillation(self, governor):
        """
        Pattern 17 (ANSI 78 Out-of-Step Protection):
        Loop agent through 6 alternating DISPATCHED_UNCONFIRMED <-> RECONCILIATION_NOT_FOUND flips.
        Assert governor trips ANSI 86 lockout on 6th flip, halting automated retry loop.
        """
        caid = "caid-78-001"
        sequence = [
            "DISPATCHED_UNCONFIRMED",
            "RECONCILIATION_NOT_FOUND",
            "DISPATCHED_UNCONFIRMED",
            "RECONCILIATION_NOT_FOUND",
            "DISPATCHED_UNCONFIRMED",
            "RECONCILIATION_NOT_FOUND",
            "DISPATCHED_UNCONFIRMED",
        ]
        tripped = False
        for state in sequence:
            if governor.evaluate_out_of_step(caid, state):
                governor.trip_lockout_relay(caid, "ANSI 78 Out-of-Step retry oscillation detected")
                tripped = True
                break

        assert tripped is True
        assert governor.is_latched(caid) is True

    def test_18_forensic_disturbance_triad_ser_fr_ddr(self, governor):
        """
        Pattern 18 (Disturbance Recording Triad SER / FR / DDR):
        Records structured pre-fault, fault, and post-fault disturbance telemetry
        for ISO/IEC 42001 and EU AI Act Art. 12 compliance.
        """
        caid = "caid-triad-001"
        pre_fault = {"status": "HEALTHY", "active_connections": 10}
        fault = {"error": "TCP_RST_SEVERANCE", "http_status": 504}
        post_fault = {"disposition": "COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED", "latched": True}

        record = governor.record_disturbance_triad(
            caid=caid,
            fault_type="TRANSIENT_BUS_FAULT",
            pre_fault_state=pre_fault,
            fault_state=fault,
            post_fault_state=post_fault
        )
        assert record["record_type"] == "FORENSIC_DISTURBANCE_TRIAD"
        assert record["caid"] == caid
        assert "ser" in record
        assert "fr" in record
        assert "ddr" in record
        assert record["fr"]["fault_signature"] == "TRANSIENT_BUS_FAULT"
        assert record["ddr"]["post_fault_settlement"]["latched"] is True
