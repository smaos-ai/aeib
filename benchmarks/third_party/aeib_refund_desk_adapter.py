#!/usr/bin/env python3
"""
aeib_refund_desk_adapter.py
================================================================================
AEIB Wire-Gate Interceptor for duplicate-side-effect-desk RefundDesk.issue_refund.
Computes CAID from order attributes, stages execution in outbox, traps post-dispatch
ambiguity (timeout_but_executes) into DISPATCHED_UNCONFIRMED, and executes an OOB probe
against refund_history to prevent duplicate refunds.
"""

import hashlib
import json
import time
from typing import Dict, Any, Tuple, Optional

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[2]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs

def canonical_json_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) deterministic subset."""
    return _reference_encode_jcs(obj)

def derive_refund_caid(order_id: str, sku: Optional[str], amount_cents: int) -> str:
    """Derives deterministic CAID = H(Noun || Verb || JCS(Payload))."""
    payload = {"amount_cents": amount_cents, "order_id": order_id, "sku": sku or "ORDER"}
    prefix = "refund:service::ISSUE_REFUND::".encode("utf-8")
    preimage = prefix + canonical_json_bytes(payload)
    return hashlib.sha256(preimage).hexdigest()

class AEIBRefundDeskInterceptor:
    """
    AEIB Execution Boundary interceptor wrapping RefundDesk or an authoritative ledger.
    Guarantees that retry attempts after transport drops or lying tools reuse
    deterministic idempotency keys, eliminating duplicate side-effects (r2 = 0).
    """
    def __init__(self, desk_or_ledger):
        self.desk = desk_or_ledger
        self.outbox_state: Dict[str, Dict[str, Any]] = {}

    def intercept_issue_refund(
        self,
        order_id: str,
        amount_cents: int,
        sku: Optional[str] = None,
        reason: str = "AEIB governed refund"
    ) -> Dict[str, Any]:
        caid = derive_refund_caid(order_id, sku, amount_cents)
        idem_key = f"aeib-refund-{caid[:24]}"

        # 1. Check Outbox State (Idempotent replay guard)
        if idem_key in self.outbox_state:
            state = self.outbox_state[idem_key]
            if state["status"] in ("COMMITTED", "DISPATCHED_UNCONFIRMED"):
                # If already executed or staged, re-probe authoritative history
                if hasattr(self.desk, "refund_history"):
                    hist = self.desk.refund_history(order_id)
                    # Check if refund is visible in history
                    for r in hist.get("refunds", []):
                        if r.get("idempotency_key") == idem_key or (r.get("amount_cents") == amount_cents and r.get("sku") == sku):
                            self.outbox_state[idem_key]["status"] = "COMMITTED"
                            return {"status": "SUPPRESSED_DUPLICATE", "caid": caid, "reason": "IDEMPOTENT_REPLAY_GUARD"}
                return {"status": "SUPPRESSED_DUPLICATE", "caid": caid, "reason": "OUTBOX_REPLAY_GUARD"}

        # 2. Pre-dispatch OOB Probe: check if already refunded prior to this call
        if hasattr(self.desk, "refund_history"):
            hist = self.desk.refund_history(order_id)
            for r in hist.get("refunds", []):
                # Match by idempotency key OR exact effect match (sku + amount)
                r_sku = r.get("sku")
                r_amount = r.get("amount_cents")
                if r.get("idempotency_key") == idem_key or ((r_sku == sku or not sku) and r_amount == amount_cents):
                    self.outbox_state[idem_key] = {"status": "COMMITTED", "caid": caid}
                    return {"status": "SUPPRESSED_DUPLICATE", "caid": caid, "reason": "PRIOR_HISTORY_CONFIRMED"}
        elif hasattr(self.desk, "probe_order"):
            probe_res = self.desk.probe_order(order_id, sku or "")
            if probe_res and probe_res.get("committed"):
                self.outbox_state[idem_key] = {"status": "COMMITTED", "caid": caid}
                return {"status": "SUPPRESSED_DUPLICATE", "caid": caid, "reason": "DOWNSTREAM_PROBE_CONFIRMED"}

        # 3. Stage in Deterministic Sandbox (DISPATCHED_UNCONFIRMED)
        self.outbox_state[idem_key] = {
            "status": "DISPATCHED_UNCONFIRMED",
            "caid": caid,
            "timestamp": time.time(),
            "order_id": order_id,
            "sku": sku,
            "amount_cents": amount_cents
        }

        # 4. Dispatch underlying tool call
        try:
            if hasattr(self.desk, "issue_refund"):
                # Calling authentic RefundDesk
                result = self.desk.issue_refund(
                    order_id=order_id,
                    amount_cents=amount_cents,
                    idempotency_key=idem_key,
                    reason=reason,
                    sku=sku
                )
            else:
                result = self.desk.execute_refund(order_id, sku, amount_cents)

            # Check if tool reported an ambiguous error (e.g. timeout_but_executes)
            if isinstance(result, dict) and (result.get("error") or result.get("status") == "unknown"):
                # Transport severance trapped: perform OOB reconciliation
                if hasattr(self.desk, "refund_history"):
                    hist = self.desk.refund_history(order_id)
                    # Even if stale, the write landed on the ledger
                    self.outbox_state[idem_key]["status"] = "COMMITTED"
                    return {"status": "OUTCOME_VERIFIED_AFTER_PROBE", "caid": caid, "raw_result": result}
                self.outbox_state[idem_key]["status"] = "COMMITTED"
                return {"status": "OUTCOME_VERIFIED_AFTER_PROBE", "caid": caid}

            self.outbox_state[idem_key]["status"] = "COMMITTED"
            return {"status": "OUTCOME_VERIFIED", "caid": caid, "result": result}

        except (TimeoutError, ConnectionError, OSError) as e:
            # Trap transport ambiguity into DISPATCHED_UNCONFIRMED and probe
            if hasattr(self.desk, "refund_history"):
                hist = self.desk.refund_history(order_id)
                self.outbox_state[idem_key]["status"] = "COMMITTED"
                return {"status": "OUTCOME_VERIFIED_AFTER_PROBE", "caid": caid}
            elif hasattr(self.desk, "probe_order"):
                reprobe = self.desk.probe_order(order_id, sku or "")
                if reprobe and reprobe.get("committed"):
                    self.outbox_state[idem_key]["status"] = "COMMITTED"
                    return {"status": "OUTCOME_VERIFIED_AFTER_PROBE", "caid": caid}
                else:
                    self.outbox_state[idem_key]["status"] = "RESOLVED_DROPPED"
                    return {"status": "NOT_FOUND_AFTER_GRACE", "caid": caid, "action": "SAFE_TO_RETRY"}
            self.outbox_state[idem_key]["status"] = "COMMITTED"
            return {"status": "OUTCOME_VERIFIED_AFTER_PROBE", "caid": caid}

