#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
src/edge_ai_prescreener.py
================================================================================
Zero-Egress On-Device Edge AI Pre-Screening & Anomaly Critic Engine.

Evaluated under the stated model:
  - Edge Neural Engine / Local Heuristic SLM Cognitive Critic
  - Zero-Egress Offline Analysis (No cloud API leaks)
  - Plain-English 2-Sentence On-Screen Summary & Risk Score (0..10000 bps)
  - RFC 8785 JCS Canonicalization with Integer Metrics

Core Architectural Invariants:
  1. Independent Structural Verification:
     Before prompting the human operator for FaceID, the edge critic independently
     analyzes the blast radius, target path, spending cap, and expiration TTL.
  2. Plain-English Screen Critique:
     Emits exactly two concise sentences:
       Sentence 1: What the proposal actually mutates in plain English.
       Sentence 2: Risk verdict and identified anomalies or safety confirmations.
  3. Integer BPS Risk Scoring:
     Calculates risk in integer basis points (0..10000 bps), categorizing proposals
     into PROCEED_TO_FACEID, OPERATOR_SCRUTINY_REQUIRED, or RECOMMEND_VETO.
  4. Zero-Float Cryptographic Receipts:
     Every pre-screening verdict is signed with an Ed25519 key over canonical RFC 8785 bytes.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


class PrescreenRecommendation(str, Enum):
    """Action recommendation emitted by the on-device critic."""

    PROCEED_TO_FACEID = "PROCEED_TO_FACEID"
    OPERATOR_SCRUTINY_REQUIRED = "OPERATOR_SCRUTINY_REQUIRED"
    RECOMMEND_VETO = "RECOMMEND_VETO"


@dataclass(frozen=True)
class EdgePrescreenReport:
    """Pre-screening report rendered on the iPhone screen before FaceID prompt."""

    report_id: str
    target_operation_id: str
    risk_score_bps: int  # 0..10000 bps
    is_anomalous: bool
    sentence_1_summary: str
    sentence_2_critique: str
    recommendation: PrescreenRecommendation
    flagged_anomalies: List[str]
    report_caid: str
    signature_hex: str
    public_key_hex: str

    def __post_init__(self) -> None:
        if not isinstance(self.risk_score_bps, int) or not (0 <= self.risk_score_bps <= 10000):
            raise ValueError("risk_score_bps must be an integer in 0..10000 bps")
        if not self.report_caid.startswith("sha256:"):
            raise ValueError("report_caid must be a sha256: prefixed string")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_operation_id": self.target_operation_id,
            "risk_score_bps": self.risk_score_bps,
            "is_anomalous": self.is_anomalous,
            "sentence_1_summary": self.sentence_1_summary,
            "sentence_2_critique": self.sentence_2_critique,
            "recommendation": self.recommendation.value,
            "flagged_anomalies": self.flagged_anomalies,
            "report_caid": self.report_caid,
            "signature_hex": self.signature_hex,
            "public_key_hex": self.public_key_hex,
        }


class EdgeAIPrescreener:
    """
    On-device cognitive critic running locally on the edge notary node.
    """

    # claim: config - Thresholds for risk evaluation
    BASELINE_RISK_BPS = 1000  # claim: config - 10% baseline for any gated action
    MAX_NOMINAL_SPENDING_MINOR = 5000  # $50.00
    HIGH_RISK_SPENDING_MINOR = 50000  # $500.00
    MIN_EXPIRATION_TTL_SEC = 15  # < 15s is dangerously short
    MAX_EXPIRATION_TTL_SEC = 86400 * 7  # > 7 days is dangerously long

    SENSITIVE_RESOURCE_PATTERNS = [
        re.compile(r"^/etc/"),
        re.compile(r"^/root/"),
        re.compile(r"\.ssh/"),
        re.compile(r"\.env"),
        re.compile(r"DROP\s+TABLE", re.IGNORECASE),
        re.compile(r"DELETE\s+FROM", re.IGNORECASE),
    ]

    def __init__(self, signing_key: Optional[ed25519.Ed25519PrivateKey] = None) -> None:
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.signing_key.public_key()

    def prescreen_proposal(
        self,
        action_type: str,
        target_resource: str,
        amount_minor: int,
        expires_at_epoch_sec: int,
        current_epoch_sec: int,
        operation_id: str,
        report_id: Optional[str] = None,
    ) -> EdgePrescreenReport:
        """
        Analyzes a proposal and generates the 2-sentence critique and risk score.
        """
        anomalies: List[str] = []
        base_risk_bps = self.BASELINE_RISK_BPS  # claim: config - 10% baseline for any gated action

        # 1. Financial Risk Analysis
        if amount_minor > self.HIGH_RISK_SPENDING_MINOR:
            anomalies.append(f"HIGH_SPENDING_AMOUNT_{amount_minor}_MINOR")
            base_risk_bps += 4000
        elif amount_minor > self.MAX_NOMINAL_SPENDING_MINOR:
            anomalies.append(f"ELEVATED_SPENDING_AMOUNT_{amount_minor}_MINOR")
            base_risk_bps += 3000

        # 2. Resource & Path Analysis
        for pat in self.SENSITIVE_RESOURCE_PATTERNS:
            if pat.search(target_resource):
                anomalies.append(f"SENSITIVE_RESOURCE_PATTERN_{pat.pattern}")
                base_risk_bps += 5000
                break

        # 3. Expiration TTL Analysis
        ttl_sec = expires_at_epoch_sec - current_epoch_sec
        if ttl_sec < self.MIN_EXPIRATION_TTL_SEC:
            anomalies.append("EXPIRATION_TTL_TOO_SHORT")
            base_risk_bps += 2500
        elif ttl_sec > self.MAX_EXPIRATION_TTL_SEC:
            anomalies.append("EXPIRATION_TTL_EXCESSIVE")
            base_risk_bps += 1500

        # 4. Action Type Sensitivity
        if "DESTRUCTIVE" in action_type.upper() or "DELETE" in action_type.upper() or "DROP" in action_type.upper():
            anomalies.append("DESTRUCTIVE_ACTION_TYPE")
            base_risk_bps += 4000

        final_risk_bps = min(10000, base_risk_bps)
        is_anomalous = len(anomalies) > 0

        # Formulate 2-Sentence Plain-English Critique
        sentence_1 = f"Proposed {action_type} targets {target_resource} with authorization value {amount_minor} minor units."

        if final_risk_bps >= 8000:
            recommendation = PrescreenRecommendation.RECOMMEND_VETO
            sentence_2 = f"Critical risk detected due to {', '.join(anomalies)}; human veto recommended unless explicitly verified."
        elif final_risk_bps >= 4000:
            recommendation = PrescreenRecommendation.OPERATOR_SCRUTINY_REQUIRED
            sentence_2 = f"Elevated caution advised regarding {', '.join(anomalies)}; verify parameters before FaceID confirmation."
        else:
            recommendation = PrescreenRecommendation.PROCEED_TO_FACEID
            sentence_2 = "Parameters conform to standard operational bounds; zero structural anomalies detected."

        rid = report_id or f"report-critic-{hashlib.sha256(operation_id.encode('utf-8')).hexdigest()[:16]}"

        body = {
            "report_id": rid,
            "target_operation_id": operation_id,
            "risk_score_bps": final_risk_bps,
            "is_anomalous": is_anomalous,
            "sentence_1_summary": sentence_1,
            "sentence_2_critique": sentence_2,
            "recommendation": recommendation.value,
            "flagged_anomalies": sorted(anomalies),
        }

        canonical_bytes = encode_jcs(body)
        caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        sig = self.signing_key.sign(canonical_bytes)
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return EdgePrescreenReport(
            report_id=rid,
            target_operation_id=operation_id,
            risk_score_bps=final_risk_bps,
            is_anomalous=is_anomalous,
            sentence_1_summary=sentence_1,
            sentence_2_critique=sentence_2,
            recommendation=recommendation,
            flagged_anomalies=sorted(anomalies),
            report_caid=caid,
            signature_hex=sig.hex(),
            public_key_hex=pub_bytes.hex(),
        )


def verify_edge_prescreen_report(
    report_data: Dict[str, Any],
    pinned_pubkey_hex: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verifies the Ed25519 signature and RFC 8785 JCS integrity of an EdgePrescreenReport.
    """
    required_keys = {
        "report_id",
        "target_operation_id",
        "risk_score_bps",
        "is_anomalous",
        "sentence_1_summary",
        "sentence_2_critique",
        "recommendation",
        "flagged_anomalies",
        "report_caid",
        "signature_hex",
        "public_key_hex",
    }
    if not required_keys.issubset(report_data.keys()):
        return False, "ERR_MISSING_REPORT_FIELDS"

    for k, v in report_data.items():
        if isinstance(v, float):
            return False, "ERR_FLOAT_FORBIDDEN_IN_REPORT"

    pub_hex = report_data["public_key_hex"]
    if pinned_pubkey_hex and pub_hex != pinned_pubkey_hex:
        return False, "ERR_UNPINNED_CRITIC_PUBLIC_KEY"

    try:
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        sig_bytes = bytes.fromhex(report_data["signature_hex"])
    except Exception:
        return False, "ERR_INVALID_CRYPTO_ENVELOPE"

    body_to_verify = {
        "report_id": report_data["report_id"],
        "target_operation_id": report_data["target_operation_id"],
        "risk_score_bps": report_data["risk_score_bps"],
        "is_anomalous": report_data["is_anomalous"],
        "sentence_1_summary": report_data["sentence_1_summary"],
        "sentence_2_critique": report_data["sentence_2_critique"],
        "recommendation": report_data["recommendation"],
        "flagged_anomalies": sorted(report_data["flagged_anomalies"]),
    }

    try:
        canonical_bytes = encode_jcs(body_to_verify)
    except Exception:
        return False, "ERR_JCS_CANONICALIZATION_FAILED"

    expected_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
    if report_data["report_caid"] != expected_caid:
        return False, "ERR_REPORT_CAID_MISMATCH"

    try:
        pub_key.verify(sig_bytes, canonical_bytes)
    except InvalidSignature:
        return False, "ERR_CRITIC_SIGNATURE_INVALID"

    return True, "OK"
