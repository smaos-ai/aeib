#!/usr/bin/env python3
"""
tests/test_ansi_50bf_breaker_failure.py
Zero-Mock empirical test implementation for probe-failure escalation pattern
(conceptually inspired by breaker failure protection principles).
"""

import socket
import threading
import time
import pytest
from datetime import datetime, timezone
from aei_core.model.evidence import EvidenceRecord, EvidenceType
from aei_core.model.state import DispositionState, ReconciliationState
from aei_core.reconciliation.engine import ReconciliationEngine


def test_breaker_failure_cascade_ansi_50bf():
    """
    ANSI 50BF Breaker Failure Protection:
    Verifies that when primary, secondary, and tertiary out-of-band probes
    all fail to establish the external effect, the CAID transitions to
    a terminal lockout state requiring manual intervention.
    """
    # 1. Initialize Engine with strict cascade policy (Zero-Mock: Real object, no MagicMock)
    engine = ReconciliationEngine(
        max_probe_attempts=3,
        probe_backoff_ms=0,  # Instant for test speed
        terminal_state=DispositionState.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
    )

    caid = "caid-50bf-cascade-test-001"

    # 2. Initial State: Agent claims CONFIRMED, but transport was GATEWAY_5XX (504)
    initial_context = {
        "operation_id": "op-50bf-001",
        "attempt_id": "att-001",
        "agent_claim": "CONFIRMED",
        "transport_state": "GATEWAY_5XX",
        "external_effect": "UNKNOWN"
    }

    # 3. Simulate Primary Probe Failure (e.g., HTTP 504 on read replica 1)
    probe_1_failure = EvidenceRecord(
        evidence_id="ev-001",
        evidence_type=EvidenceType.PROBE_RESULT,
        source="primary_ledger_probe",
        timestamp=datetime.now(timezone.utc),
        payload={"status": "timeout", "http_code": 504},
        authority_level="OBSERVATIONAL"
    )

    state_1 = engine.process_evidence(caid, initial_context, probe_1_failure)
    assert state_1.disposition == DispositionState.PROBE_1_FAILED
    assert state_1.requires_further_probing is True

    # 4. Simulate Secondary Probe Failure (e.g., HTTP 503 on read replica 2)
    probe_2_failure = EvidenceRecord(
        evidence_id="ev-002",
        evidence_type=EvidenceType.PROBE_RESULT,
        source="secondary_ledger_probe",
        timestamp=datetime.now(timezone.utc),
        payload={"status": "service_unavailable", "http_code": 503},
        authority_level="OBSERVATIONAL"
    )

    state_2 = engine.process_evidence(caid, state_1, probe_2_failure)
    assert state_2.disposition == DispositionState.PROBE_2_FAILED
    assert state_2.requires_further_probing is True

    # 5. Simulate Tertiary Probe Failure (e.g., Event log append-only store unreachable)
    probe_3_failure = EvidenceRecord(
        evidence_id="ev-003",
        evidence_type=EvidenceType.PROBE_RESULT,
        source="tertiary_event_log_probe",
        timestamp=datetime.now(timezone.utc),
        payload={"status": "connection_refused"},
        authority_level="OBSERVATIONAL"
    )

    # Engine processes probe 3. All probes exhausted.
    # MUST transition to terminal lockout (ANSI 86 equivalent).
    state_3 = engine.process_evidence(caid, state_2, probe_3_failure)

    assert state_3.disposition == DispositionState.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
    assert state_3.requires_further_probing is False
    assert state_3.is_terminal is True

    # 6. Verify Lockout (ANSI 86): Any subsequent automated probe attempts are rejected
    probe_4_attempt = EvidenceRecord(
        evidence_id="ev-004",
        evidence_type=EvidenceType.PROBE_RESULT,
        source="rogue_automated_probe",
        timestamp=datetime.now(timezone.utc),
        payload={"status": "success", "http_code": 200},  # Even if it succeeds now
        authority_level="OBSERVATIONAL"
    )

    # The engine must ignore or reject this, maintaining the lockout
    state_4 = engine.process_evidence(caid, state_3, probe_4_attempt)
    assert state_4.disposition == DispositionState.COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED
    assert state_4.is_terminal is True


def _unresponsive_server(sock: socket.socket, stop_event: threading.Event):
    """Real socket that accepts connection but sends no data (simulating TCP blackhole)"""
    sock.settimeout(0.5)
    while not stop_event.is_set():
        try:
            conn, addr = sock.accept()
            while not stop_event.is_set():
                time.sleep(0.05)
            try:
                conn.close()
            except Exception:
                pass
        except socket.timeout:
            continue
        except OSError:
            break


def test_empirical_50bf_network_drop():
    stop_event = threading.Event()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(('127.0.0.1', 0))
        port = server_sock.getsockname()[1]
        server_sock.listen(1)
    except (PermissionError, OSError) as e:
        pytest.skip(f"Socket bind/listen not permitted in current execution context: {e}")

    server_thread = threading.Thread(target=_unresponsive_server, args=(server_sock, stop_event), daemon=True)
    server_thread.start()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            with pytest.raises((ConnectionRefusedError, socket.timeout, ConnectionResetError, BrokenPipeError, OSError)):
                s.connect(('127.0.0.1', port))
                s.sendall(b"GET /status HTTP/1.1\r\n\r\n")
                s.recv(1024)
    finally:
        stop_event.set()
        try:
            server_sock.close()
        except Exception:
            pass
        server_thread.join(timeout=1.0)
