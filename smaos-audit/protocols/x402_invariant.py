#!/usr/bin/env python3
"""
protocols/x402_invariant.py — Moat 11: The x402 Settlement Invariant Engine
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Features:
  1. Prevents autonomous agents from double-paying on dropped wires by strictly
     differentiating HTTP 402 Payment Required from 402 upstream_timeout.
  2. Catches dropped payment wires and forces normative UNKNOWN disposition.
  3. Halts autonomous re-signing loops to protect enterprise treasury wallets.

Zero external dependencies (pure Python standard library).
"""

from typing import Any, Dict, Optional


class X402InvariantEngine:
    """
    Prevents autonomous agents from double-paying on dropped wires 
    by strictly differentiating HTTP 402 Payment Required from 
    402 upstream_timeout.
    """

    def __init__(self):
        self.prevented_double_spends = 0
        self.protected_cents = 0

    @staticmethod
    def evaluate_response(status_code: int, headers: Dict[str, str], body: str) -> str:
        """
        Evaluates an HTTP 402 response and enforces the wire drop invariant.
        """
        if status_code != 402:
            return "PROCEED_WITH_STANDARD_LOGIC"
        
        # Normalize header keys to lowercase
        h_lower = {k.lower(): v for k, v in headers.items()}
        error_type = (h_lower.get("x-error-type") or h_lower.get("x-payment-error") or "").lower()
        body_lower = body.lower()
        
        # The Catastrophe Check: Upstream Gateway Drop
        if (
            "upstream_timeout" in error_type
            or "upstream_timeout" in body_lower
            or "gateway timeout" in body_lower
            or "connection reset" in body_lower
        ):
            # The wire dropped. The agent MUST NOT re-sign or retry payment.
            return "UNKNOWN" 
        
        # Legitimate payment request (requires signature/authorization)
        if "x-payment-proof" in h_lower or "x-payment-amount" in h_lower or "invoice" in body_lower:
            # Requires human/system policy payment approval
            return "REFUSED"
            
        # Ambiguous 402. Default to fail-closed epistemic safety.
        return "UNKNOWN"

    def record_interception(self, amount_cents: int = 0) -> None:
        self.prevented_double_spends += 1
        self.protected_cents += amount_cents
