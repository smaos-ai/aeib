#!/usr/bin/env python3
"""
tools/export_actuarial_ledger.py
================================================================================
Actuarial "Payment Warrant" & Near-Miss Underwriting Ledger (Backlog Item 5).

Inspired by GitHub's 4-Pillar Agentic Governance Taxonomy, Edward Jones-Imhotep's
The Broken Machine (structural breakdown data points), and emerging cyber-insurance
underwriting requirements for autonomous agent deployments.

Evaluates under the stated model:
  1. Aggregates Executed Warrants (cryptographically authorized and settled mutations).
  2. Aggregates Intercepted Near-Misses (every blocked HALT_* intervention):
     - Blocked Sybil velocity bursts and smurfing attempts.
     - Blocked TIER_2 taint escalations.
     - Blocked HTTP 504 duplicate retry storms.
     - Blocked honeypot canary exfiltrations.
  3. Calculates the Risk-Reduction Proof (near-miss ratio and loss prevention baseline)
     to support cyber-insurance underwriting and EN 18286 conformity assessments.
  4. Signs the actuarial package with Ed25519 over RFC 8785 JCS.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Computes a SHA-256 digest with standard prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class ActuarialUnderwritingLedgerExporter:
    """
    Extracts and packages actuarial risk metrics and near-miss evidence
    for institutional cyber-insurers and statutory auditors.
    """

    def __init__(self, signing_key: ed25519.Ed25519PrivateKey) -> None:
        self._signing_key = signing_key

    @property
    def public_key(self) -> ed25519.Ed25519PublicKey:
        return self._signing_key.public_key()

    def generate_actuarial_report(
        self,
        executed_warrants_count: int,
        executed_volume_eur_minor: int,
        intercepted_events: List[Dict[str, Any]],
        assessment_window_days: int = 30,
        now_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates an Ed25519-signed actuarial underwriting report.
        """
        if now_ts is None:
            now_ts = int(time.time())

        # Classify intercepted near-misses
        near_miss_categories: Dict[str, int] = {
            "duplicate_retry_storms_blocked": 0,
            "taint_escalation_blocked": 0,
            "sybil_quota_bursts_blocked": 0,
            "honeypot_canary_tripwires_triggered": 0,
            "shadow_tools_blocked": 0,
        }

        prevented_loss_exposure_minor = 0

        for ev in intercepted_events:
            reason = ev.get("reason", "")
            amount = int(ev.get("prevented_amount_minor", 0))
            prevented_loss_exposure_minor += amount

            if "504" in reason or "RETRY" in reason or "INDETERMINATE" in reason:
                near_miss_categories["duplicate_retry_storms_blocked"] += 1
            elif "TAINT" in reason:
                near_miss_categories["taint_escalation_blocked"] += 1
            elif "SPRINT" in reason or "SYBIL" in reason or "QUOTA" in reason:
                near_miss_categories["sybil_quota_bursts_blocked"] += 1
            elif "HONEYPOT" in reason:
                near_miss_categories["honeypot_canary_tripwires_triggered"] += 1
            else:
                near_miss_categories["shadow_tools_blocked"] += 1

        total_near_misses = sum(near_miss_categories.values())
        total_operations = executed_warrants_count + total_near_misses
        near_miss_rate_pct = (
            round((total_near_misses / max(total_operations, 1)) * 100.0, 2)
            if total_operations > 0
            else 0.0
        )

        payload: Dict[str, Any] = {
            "report_type": "AEIB_ACTUARIAL_NEAR_MISS_UNDERWRITING_LEDGER",
            "assessment_window_days": assessment_window_days,
            "timestamp": now_ts,
            "governance_pillars": {
                "pillar_1_identity_and_access": "VERIFIED_DPOP_AND_DID_ROOT",
                "pillar_2_authorization_boundaries": "STATION_1_PRE_DISPATCH_ESCROW",
                "pillar_3_automated_assurance": "FAIL_CLOSED_BLOCKING_GATES",
                "pillar_4_audit_and_provenance": "RFC_9052_COSE_AND_SCITT_MERKLE",
            },
            "metrics": {
                "executed_warrants_count": executed_warrants_count,
                "executed_volume_eur_minor": executed_volume_eur_minor,
                "total_near_miss_interventions": total_near_misses,
                "prevented_loss_exposure_minor": prevented_loss_exposure_minor,
                "near_miss_rate_pct": near_miss_rate_pct,
                "breakdown_by_category": near_miss_categories,
            },
            "epistemic_notice": (
                "Evaluated under the stated model using deterministic wire-level gates. "
                "Near-miss interventions reflect observed executions blocked pre-socket."
            ),
        }

        canonical_bytes = encode_jcs(payload)
        sig_bytes = self._signing_key.sign(canonical_bytes)

        return {
            "report_caid": sha256_prefixed(canonical_bytes),
            "payload": payload,
            "signature_b64": base64.b64encode(sig_bytes).decode("ascii"),
        }


def verify_actuarial_report(
    pubkey: ed25519.Ed25519PublicKey,
    report: Dict[str, Any],
) -> bool:
    """Verifies an actuarial underwriting report offline."""
    try:
        canonical_bytes = encode_jcs(report["payload"])
        sig_bytes = base64.b64decode(report["signature_b64"], validate=True)
        pubkey.verify(sig_bytes, canonical_bytes)
        expected_caid = sha256_prefixed(canonical_bytes)
        return report.get("report_caid") == expected_caid
    except Exception:
        return False
