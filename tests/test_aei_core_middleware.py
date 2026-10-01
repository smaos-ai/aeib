#!/usr/bin/env python3
"""
tests/test_aei_core_middleware.py — Empirical Validation of aei_core_middleware

Validates the two required empirical control objectives:
1. Duplicate Mutation Guard: Proves an ambiguous 504 drop during a tool call halts
   the loop and prevents duplicate dispatch after an out-of-band probe confirms execution.
2. Signature & Hash Tamper Detection: Proves modifying a single byte in the canonical
   payload string invalidates the signature check and halts verification.
"""

import pytest
import copy
from cryptography.exceptions import InvalidSignature
from src.aei_core_middleware import (
    AeiCoreMiddleware,
    TransportDropException,
    DuplicateExecutionBlockedError,
    verify_disposition_receipt
)


class MockLedgerServer:
    """Simulates an external downstream ledger with idempotency support."""
    def __init__(self):
        self.committed_records = {}
        self.mutation_count = 0

    def dispatch_payment(self, idempotency_key: str, amount: float, simulate_drop_after_commit: bool = False):
        if idempotency_key in self.committed_records:
            # Idempotent response if gateway catches it
            return {"status": "SUCCESS", "idempotent_replay": True}

        # Commit mutation on server
        self.mutation_count += 1
        record = {
            "tx_id": f"tx_{self.mutation_count:04d}",
            "idempotency_key": idempotency_key,
            "amount": amount,
            "status": "COMMITTED"
        }
        self.committed_records[idempotency_key] = record

        # Transport drop occurs after commit but before 200 OK reaches client
        if simulate_drop_after_commit:
            raise TransportDropException(status_code=504, message="HTTP 504 Gateway Timeout")

        return {"status": "SUCCESS", "tx_id": record["tx_id"]}

    def oob_probe(self, idempotency_key: str):
        """Out-of-band authoritative read endpoint."""
        return self.committed_records.get(idempotency_key, None)


def test_1_duplicate_mutation_guard():
    """
    Test 1: Proving that an ambiguous 504 drop during a tool call halts the loop
    and prevents duplicate payload dispatch after the probe confirms prior execution.
    """
    server = MockLedgerServer()
    middleware = AeiCoreMiddleware()

    action_id = "agent_call_debit_001"
    idempotency_key = "idem_key_payment_9981"
    amount = 50000.00

    # Simulation: Agent executes mutating action
    # Downstream server commits, but transport drops with HTTP 504
    with pytest.raises(DuplicateExecutionBlockedError) as exc_info:
        middleware.execute_with_guard(
            action_id=action_id,
            idempotency_key=idempotency_key,
            tool_dispatch_fn=lambda: server.dispatch_payment(
                idempotency_key=idempotency_key,
                amount=amount,
                simulate_drop_after_commit=True
            ),
            out_of_band_probe_fn=server.oob_probe
        )

    receipt = exc_info.value.receipt

    # Assertions on fail-closed state
    assert receipt["disposition"] == "OUTCOME_VERIFIED"
    assert receipt["retry_permitted"] is False
    assert receipt["probe_performed"] is True
    assert receipt["probe_result"] == "COMMITTED"
    assert receipt["wire_status"] == "HTTP_504_DROP"

    # Verify that the downstream server mutated exactly ONCE and duplicate was blocked
    assert server.mutation_count == 1
    assert idempotency_key in server.committed_records

    # Confirm the receipt emitted during blocking is cryptographically valid
    assert verify_disposition_receipt(receipt) is True

    # If agent attempted to blindly re-dispatch, middleware would again prevent duplicate
    # by detecting prior execution or enforcing no-retry
    with pytest.raises(DuplicateExecutionBlockedError):
        middleware.execute_with_guard(
            action_id=action_id,
            idempotency_key=idempotency_key,
            tool_dispatch_fn=lambda: server.dispatch_payment(
                idempotency_key=idempotency_key,
                amount=amount,
                simulate_drop_after_commit=True
            ),
            out_of_band_probe_fn=server.oob_probe
        )

    # Mutation count remains strictly 1
    assert server.mutation_count == 1


def test_2_signature_and_hash_tamper_detection():
    """
    Test 2: Proving that modifying a single byte in the canonical payload string
    invalidates the signature check and halts verification.
    """
    server = MockLedgerServer()
    middleware = AeiCoreMiddleware()

    action_id = "agent_call_check_002"
    idempotency_key = "idem_key_check_1122"

    # Execute nominal tool call
    _, receipt = middleware.execute_with_guard(
        action_id=action_id,
        idempotency_key=idempotency_key,
        tool_dispatch_fn=lambda: server.dispatch_payment(
            idempotency_key=idempotency_key,
            amount=100.0,
            simulate_drop_after_commit=False
        ),
        out_of_band_probe_fn=server.oob_probe
    )

    receipt_dict = receipt.to_dict()

    # 1. Untampered receipt MUST pass verification
    assert verify_disposition_receipt(receipt_dict) is True

    # 2. Tamper Test A: Modify a single character in the canonical_payload
    # e.g., attempt to tamper retry_permitted from false to true
    tampered_receipt_a = copy.deepcopy(receipt_dict)
    original_payload = tampered_receipt_a["canonical_payload"]
    assert '"retry_permitted":false' in original_payload

    # Flip 'false' to 'true ' (keeping length) or alter 1 byte
    tampered_payload_a = original_payload.replace('"retry_permitted":false', '"retry_permitted":true')
    tampered_receipt_a["canonical_payload"] = tampered_payload_a

    # Must fail verification due to hash mismatch or signature invalidity
    with pytest.raises((ValueError, InvalidSignature)):
        verify_disposition_receipt(tampered_receipt_a)

    # 3. Tamper Test B: Modify a single byte of action_id inside canonical payload
    tampered_receipt_b = copy.deepcopy(receipt_dict)
    payload_b = tampered_receipt_b["canonical_payload"]
    # Change first character of action_id from 'a' to 'b'
    tampered_payload_b = payload_b.replace('"action_id":"agent_call_check_002"', '"action_id":"bgent_call_check_002"')
    tampered_receipt_b["canonical_payload"] = tampered_payload_b

    with pytest.raises((ValueError, InvalidSignature)):
        verify_disposition_receipt(tampered_receipt_b)

    # 4. Tamper Test C: Modify the declared payload_hash to match the tampered payload,
    # then the signature check must fail directly
    tampered_receipt_c = copy.deepcopy(tampered_receipt_a)
    import hashlib
    from src.aei_core_middleware import jcs_canonicalize
    import json
    new_hash = hashlib.sha256(jcs_canonicalize(json.loads(tampered_payload_a))).hexdigest()
    tampered_receipt_c["payload_hash"] = f"sha256:{new_hash}"

    with pytest.raises(InvalidSignature):
        verify_disposition_receipt(tampered_receipt_c)

    # 5. Tamper Test D: Alter 1 hex character in the Ed25519 signature
    tampered_receipt_d = copy.deepcopy(receipt_dict)
    sig = list(tampered_receipt_d["signature"])
    sig[0] = 'f' if sig[0] != 'f' else '0'
    tampered_receipt_d["signature"] = "".join(sig)

    with pytest.raises(InvalidSignature):
        verify_disposition_receipt(tampered_receipt_d)
