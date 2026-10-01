#!/usr/bin/env python3
"""
tests/test_aei_adversarial.py — Adversarial Stress Testing of aei_core_middleware

Evaluates four adversarial and high-risk operational failure modes:
1. Retry storms under post-commit loss (N=50 parallel/burst attempts)
2. Idempotency-key drift across agent re-prompting cycles
3. Evidence tampering, byte-level modifications, and signature hash mismatches
4. Probe failures, database timeouts, and reconciliation network outages
"""

import pytest
import concurrent.futures
import copy
from typing import Dict, Any, Optional
from cryptography.exceptions import InvalidSignature
from src.aei_core_middleware import (
    AeiCoreMiddleware,
    aei_guard,
    TransportDropException,
    DuplicateExecutionBlockedError,
    IdempotencyKeyDriftError,
    ProbeOutageError,
    verify_disposition_receipt
)


class AdversarialServer:
    """Stateful mock server for adversarial evaluation."""
    def __init__(self):
        self.ledger: Dict[str, Dict[str, Any]] = {}
        self.mutation_counter = 0

    def mutate(self, idempotency_key: str, amount: float, drop_wire: bool = False):
        if idempotency_key in self.ledger:
            # Idempotent response
            return {"status": "SUCCESS", "tx_id": self.ledger[idempotency_key]["tx_id"], "duplicate": False}

        # Server commits state
        self.mutation_counter += 1
        record = {
            "tx_id": f"tx_{self.mutation_counter}",
            "idempotency_key": idempotency_key,
            "amount": amount
        }
        self.ledger[idempotency_key] = record

        if drop_wire:
            raise TransportDropException(status_code=504, message="HTTP 504 Gateway Timeout")

        return {"status": "SUCCESS", "tx_id": record["tx_id"], "duplicate": False}

    def probe(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        return self.ledger.get(idempotency_key)


# =============================================================================
# 1. RETRY STORMS UNDER POST-COMMIT LOSS (N=50)
# =============================================================================

def test_adversarial_retry_storm_post_commit():
    """
    Simulates an agent or orchestration framework firing a storm of 50 retry
    attempts following an ambiguous 504 timeout where the server committed.
    """
    server = AdversarialServer()
    middleware = AeiCoreMiddleware()

    action_id = "act_storm_001"
    idempotency_key = "idem_storm_key_001"
    amount = 1000.00
    N_RETRIES = 50

    # Initial attempt commits on server, but connection drops with 504
    with pytest.raises(DuplicateExecutionBlockedError):
        middleware.execute_with_guard(
            action_id=action_id,
            idempotency_key=idempotency_key,
            tool_dispatch_fn=lambda: server.mutate(idempotency_key, amount, drop_wire=True),
            out_of_band_probe_fn=server.probe
        )

    assert server.mutation_counter == 1

    # Simulate storm of N_RETRIES rapid re-dispatch attempts by agent loop
    blocked_count = 0
    for _ in range(N_RETRIES - 1):
        try:
            middleware.execute_with_guard(
                action_id=action_id,
                idempotency_key=idempotency_key,
                tool_dispatch_fn=lambda: server.mutate(idempotency_key, amount, drop_wire=True),
                out_of_band_probe_fn=server.probe
            )
        except DuplicateExecutionBlockedError:
            blocked_count += 1

    # Invariant: 100% of storm retries (49/49) must be intercepted before wire dispatch
    assert blocked_count == 49
    assert server.mutation_counter == 1


# =============================================================================
# 2. IDEMPOTENCY-KEY DRIFT ACROSS AGENT RE-PROMPTING
# =============================================================================

def test_adversarial_idempotency_key_drift():
    """
    Simulates agent semantic drift: after an initial drop on action_id 'act_drift_10',
    the agent loop re-prompts and generates a drifted key 'idem_key_v2'.
    Without guard, the server would commit a duplicate transaction.
    """
    server = AdversarialServer()
    middleware = AeiCoreMiddleware()

    action_id = "act_drift_10"
    original_key = "idem_stable_v1"
    drifted_key = "idem_drifted_v2"
    amount = 2500.00

    # 1. First dispatch: Drops after commit with original_key
    with pytest.raises(DuplicateExecutionBlockedError):
        middleware.execute_with_guard(
            action_id=action_id,
            idempotency_key=original_key,
            tool_dispatch_fn=lambda: server.mutate(original_key, amount, drop_wire=True),
            out_of_band_probe_fn=server.probe
        )

    assert server.mutation_counter == 1
    assert original_key in server.ledger

    # 2. Re-dispatch attempt: Agent re-prompts and generates drifted_key for the same action_id
    with pytest.raises(IdempotencyKeyDriftError) as exc_info:
        middleware.execute_with_guard(
            action_id=action_id,
            idempotency_key=drifted_key,  # Drifted key!
            tool_dispatch_fn=lambda: server.mutate(drifted_key, amount, drop_wire=False),
            out_of_band_probe_fn=server.probe
        )

    err = exc_info.value
    assert err.action_id == action_id
    assert err.original_key == original_key
    assert err.drifted_key == drifted_key

    # Invariant: The drifted request NEVER reached server. Ledger has exactly 1 entry.
    assert server.mutation_counter == 1
    assert drifted_key not in server.ledger


# =============================================================================
# 3. EVIDENCE TAMPERING AND HASH MISMATCHES
# =============================================================================

def test_adversarial_evidence_tampering():
    """
    Tests resistance against multi-vector receipt and evidence tampering.
    """
    server = AdversarialServer()
    middleware = AeiCoreMiddleware()

    _, receipt = middleware.execute_with_guard(
        action_id="act_tamper_test",
        idempotency_key="idem_tamper_key",
        tool_dispatch_fn=lambda: server.mutate("idem_tamper_key", 500.0, drop_wire=False),
        out_of_band_probe_fn=server.probe
    )

    base_dict = receipt.to_dict()
    assert verify_disposition_receipt(base_dict) is True

    # Vector A: Flip single byte in disposition from 'CONFIRMED' to 'MODIFIED'
    tampered_a = copy.deepcopy(base_dict)
    tampered_a["canonical_payload"] = tampered_a["canonical_payload"].replace(
        '"disposition":"CONFIRMED"',
        '"disposition":"MODIFIED"'
    )
    with pytest.raises((ValueError, InvalidSignature)):
        verify_disposition_receipt(tampered_a)

    # Vector B: Tamper action_id
    tampered_b = copy.deepcopy(base_dict)
    tampered_b["canonical_payload"] = tampered_b["canonical_payload"].replace(
        '"action_id":"act_tamper_test"',
        '"action_id":"act_forged_test"'
    )
    with pytest.raises((ValueError, InvalidSignature)):
        verify_disposition_receipt(tampered_b)

    # Vector C: Forge payload_hash to match tampered payload (signature must catch it)
    tampered_c = copy.deepcopy(tampered_a)
    import hashlib
    import json
    from src.aei_core_middleware import jcs_canonicalize
    forged_hash = hashlib.sha256(jcs_canonicalize(json.loads(tampered_c["canonical_payload"]))).hexdigest()
    tampered_c["payload_hash"] = f"sha256:{forged_hash}"

    with pytest.raises(InvalidSignature):
        verify_disposition_receipt(tampered_c)

    # Vector D: Tamper signature bits
    tampered_d = copy.deepcopy(base_dict)
    sig_chars = list(tampered_d["signature"])
    sig_chars[10] = '0' if sig_chars[10] != '0' else '1'
    tampered_d["signature"] = "".join(sig_chars)

    with pytest.raises(InvalidSignature):
        verify_disposition_receipt(tampered_d)


# =============================================================================
# 4. PROBE FAILURES AND RECONCILIATION OUTAGES (FAIL-CLOSED)
# =============================================================================

def test_adversarial_probe_failures_and_outages():
    """
    Evaluates system behavior when the out-of-band probe itself fails
    (e.g., database connection timeout, replica partition, or DNS failure).
    System must fail closed: hold at PROBE_OUTAGE_HOLD with retry_permitted=False.
    """
    server = AdversarialServer()
    middleware = AeiCoreMiddleware()

    action_id = "act_outage_01"
    idempotency_key = "idem_outage_key_01"

    def broken_probe(key: str):
        raise ConnectionError("FATAL: Out-of-band database probe timed out (reconciliation outage)")

    # Action commits on server, wire drops with 504, and then OOB probe ALSO fails
    with pytest.raises(ProbeOutageError) as exc_info:
        middleware.execute_with_guard(
            action_id=action_id,
            idempotency_key=idempotency_key,
            tool_dispatch_fn=lambda: server.mutate(idempotency_key, 750.0, drop_wire=True),
            out_of_band_probe_fn=broken_probe
        )

    receipt = exc_info.value.receipt
    assert receipt["disposition"] == "PROBE_OUTAGE_HOLD"
    assert receipt["retry_permitted"] is False
    assert "PROBE_UNAVAILABLE" in receipt["probe_result"]

    # Invariant: Receipt emitted during probe outage is still cryptographically signed
    assert verify_disposition_receipt(receipt) is True

    # Subsequent re-dispatch attempt is immediately blocked because retry_permitted is False
    with pytest.raises(DuplicateExecutionBlockedError):
        middleware.execute_with_guard(
            action_id=action_id,
            idempotency_key=idempotency_key,
            tool_dispatch_fn=lambda: server.mutate(idempotency_key, 750.0, drop_wire=False),
            out_of_band_probe_fn=broken_probe
        )

    # Server was committed only once; speculative blind retries were completely prevented
    assert server.mutation_counter == 1


# =============================================================================
# 5. DECORATOR INTEGRATION BENCHMARK WITH MOCK AGENT
# =============================================================================

def test_decorator_agent_integration_and_duplicate_suppression():
    """
    Tests @aei_guard decorator on a standard tool call within an agent loop.
    Demonstrates baseline (unprotected) vs. guarded duplicate mutation count.
    """
    server = AdversarialServer()

    # Define tool wrapped with @aei_guard
    @aei_guard(probe_fn=server.probe)
    def transfer_tool(amount: float, idempotency_key: str, action_id: str, drop: bool = False):
        return server.mutate(idempotency_key=idempotency_key, amount=amount, drop_wire=drop)

    # Simulation: Agent executes mutating tool, network drops 504 post-commit
    with pytest.raises(DuplicateExecutionBlockedError) as exc_info:
        transfer_tool(
            amount=5000.0,
            idempotency_key="agent_tool_key_100",
            action_id="agent_turn_1",
            drop=True
        )

    assert server.mutation_counter == 1
    receipt = exc_info.value.receipt
    assert receipt["disposition"] == "OUTCOME_VERIFIED"
    assert receipt["retry_permitted"] is False

    # Second turn of agent loop blindly retrying the same tool call
    with pytest.raises(DuplicateExecutionBlockedError):
        transfer_tool(
            amount=5000.0,
            idempotency_key="agent_tool_key_100",
            action_id="agent_turn_1",
            drop=False
        )

    # Guard completely prevented duplicate execution
    assert server.mutation_counter == 1
