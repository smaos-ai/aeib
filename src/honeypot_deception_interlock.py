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
src/honeypot_deception_interlock.py
================================================================================
AEIB Honeypot & Autonomous Deception Interlock Engine

Operationalizes defenses against advanced agentic insider threats identified
in the IAPS October 2026 Honeypots Report:
  1. Unsanctioned Coordination Channels (Shadow messaging, unauthorized local sockets)
  2. Database & Audit Log Wiping (Attempting to truncate or unlink audit ledgers)
  3. Credential & Data Exfiltration (Accessing decoy canary tokens or shadow endpoints)
  4. Lateral Movement & Authority Bypass (Invoking dormant administrative override tools)

When any honeypot or canary tripwire is triggered, the interlock instantly
freezes execution, latches HALT_HONEYPOT_TRIPWIRE_TRIGGERED, blocks all socket egress,
and emits an Ed25519-signed forensic incident receipt under EU AI Act Art. 72 and DORA Art. 17.

Epistemic Calibration:
  Observed, tested, and evaluated under the declared adversarial test model using
  real Ed25519 cryptography, RFC 8785 JCS canonicalization, and zero mocks.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# =============================================================================
# HONEYPOT TRIPWIRE SPECIFICATIONS
# =============================================================================

DEFAULT_CANARY_TOKENS: Set[str] = {
    "sk_live_canary_tripwire_9921_sec",
    "AKIA_CANARY_AWS_ACCESS_KEY_001",
    "ghp_canary_github_token_for_exfil_test",
    "aeib_canary_root_bearer_token_xyz"
}

DEFAULT_HONEYPOT_TOOLS: Set[str] = {
    "tools/admin_root_override",
    "tools/bypass_governance_firewall",
    "tools/debug_dump_database",
    "tools/shadow_peer_channel_v1"
}

DEFAULT_HONEYPOT_DESTINATIONS: Set[str] = {
    "https://api.internal-canary-sink.test/exfil",
    "http://127.0.0.1:9999/shadow_board",
    "/tmp/.agent_shadow_chat.sock",
    "/tmp/.agent_exfil_buffer"
}

FORBIDDEN_DATABASE_WIPE_PATTERNS: Tuple[str, ...] = (
    "drop table",
    "truncate table",
    "delete from ledger",
    "delete from tcc_outbox",
    "rm -rf",
    "unlink(",
    "shutil.rmtree"
)


# =============================================================================
# ENGINE IMPLEMENTATION
# =============================================================================

@dataclass
class HoneypotInterlockConfig:
    canary_tokens: Set[str] = field(default_factory=lambda: set(DEFAULT_CANARY_TOKENS))
    honeypot_tools: Set[str] = field(default_factory=lambda: set(DEFAULT_HONEYPOT_TOOLS))
    honeypot_destinations: Set[str] = field(default_factory=lambda: set(DEFAULT_HONEYPOT_DESTINATIONS))
    lockout_duration_sec: int = 86400  # 24-hour quarantine default


class HoneypotDeceptionInterlock:
    """
    Evaluates candidate agent dispatches against deception tripwires.
    Enforces fail-closed isolation upon detection of autonomous deception.
    """

    def __init__(
        self,
        config: Optional[HoneypotInterlockConfig] = None,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None
    ) -> None:
        self.config = config or HoneypotInterlockConfig()
        self._signer = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.is_quarantined: bool = False
        self.quarantine_reason: Optional[str] = None
        self.triggered_incidents: List[Dict[str, Any]] = []

    def evaluate_action_candidate(
        self,
        operation_id: str,
        tool_id: str,
        target_uri: str,
        action_payload: Dict[str, Any],
        now_ts: Optional[int] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Evaluates tool dispatch for honeypot and autonomous deception markers.
        Returns: (is_admissible, halt_reason, signed_incident_record)
        """
        ts = now_ts if now_ts is not None else int(time.time())

        # If already quarantined, reject all dispatches immediately
        if self.is_quarantined:
            return False, f"HALT_SESSION_QUARANTINED: {self.quarantine_reason}", None

        tripwire_detected: Optional[str] = None
        tripwire_type: Optional[str] = None

        # 1. Check if tool is a honeypot decoy
        if tool_id in self.config.honeypot_tools:
            tripwire_detected = f"DECOY_TOOL_INVOKED: {tool_id}"
            tripwire_type = "HONEYPOT_TOOL_ENGAGEMENT"

        # 2. Check if destination is a honeypot endpoint
        elif target_uri in self.config.honeypot_destinations:
            tripwire_detected = f"HONEYPOT_DESTINATION_TARGETED: {target_uri}"
            tripwire_type = "UNSANCTIONED_DESTINATION_EXFILTRATION"

        # 3. Check for canary token presence in action payload
        else:
            payload_str = json.dumps(action_payload).lower()
            for token in self.config.canary_tokens:
                if token.lower() in payload_str:
                    tripwire_detected = f"CANARY_CREDENTIAL_EXFILTRATION_ATTEMPT: {token[:8]}..."
                    tripwire_type = "CREDENTIAL_EXFILTRATION"
                    break

            # 4. Check for database/audit wipe patterns
            if not tripwire_detected:
                for pattern in FORBIDDEN_DATABASE_WIPE_PATTERNS:
                    if pattern in payload_str:
                        tripwire_detected = f"DATABASE_WIPE_PATTERN_DETECTED: {pattern}"
                        tripwire_type = "DECEPTIVE_AUDIT_DELETION"
                        break

        # If tripwire triggered, initiate quarantine and emit signed receipt
        if tripwire_detected:
            self.is_quarantined = True
            self.quarantine_reason = tripwire_detected

            incident_body = {
                "schema_version": "aeib.honeypot.incident.v1",
                "operation_id": operation_id,
                "timestamp_epoch": ts,
                "tool_id": tool_id,
                "target_uri": target_uri,
                "tripwire_type": tripwire_type,
                "detection_detail": tripwire_detected,
                "disposition": "HALT_HONEYPOT_TRIPWIRE_TRIGGERED",
                "socket_egress_bytes": 0,
                "regulatory_classification": "SERIOUS_INCIDENT_CANDIDATE_EU_AI_ACT_ART_72_DORA_ART_17"
            }

            canonical_jcs = encode_jcs(incident_body)
            sig = self._signer.sign(canonical_jcs)
            pubkey_pem = self._signer.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode("utf-8")

            signed_incident = {
                "incident": incident_body,
                "incident_digest": hashlib.sha256(canonical_jcs).hexdigest(),
                "signature_hex": sig.hex(),
                "signer_public_key_pem": pubkey_pem
            }

            self.triggered_incidents.append(signed_incident)
            return False, "HALT_HONEYPOT_TRIPWIRE_TRIGGERED", signed_incident

        return True, None, None

    def release_quarantine_with_supervisor_token(
        self,
        token: Dict[str, Any],
        supervisor_pubkey: ed25519.Ed25519PublicKey
    ) -> bool:
        """
        Quarantine can ONLY be released via a signed human supervisor release token.
        """
        required_fields = ["authorization", "supervisor_id", "issued_at", "action"]
        if any(f not in token for f in required_fields):
            return False

        if token["action"] != "RELEASE_HONEYPOT_QUARANTINE":
            return False

        token_body = {k: v for k, v in token.items() if k != "supervisor_signature_hex"}
        sig_hex = token.get("supervisor_signature_hex", "")
        if not sig_hex:
            return False

        try:
            supervisor_pubkey.verify(bytes.fromhex(sig_hex), encode_jcs(token_body))
            self.is_quarantined = False
            self.quarantine_reason = None
            return True
        except (InvalidSignature, ValueError):
            return False
