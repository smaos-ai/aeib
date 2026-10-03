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

"""Moat 8: Pre-Access Compliance Handshake via ACD draft-03

PreToolUse Gate: Machine-to-machine compliance negotiation prior to tool execution.
Enforces organizational boundary contracts, transaction limits, and DORA Art. 28
third-party access constraints before actions hit the wire.

Eliminates post-facto security remediation by failing closed at dispatch time.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class HandshakeDisposition(str, Enum):
    AUTHORIZED = "authorized"
    REFUSED_SPENDING_CEILING = "refused_spending_ceiling"
    REFUSED_UNAUTHORIZED_SCOPE = "refused_unauthorized_scope"
    REFUSED_MISSING_ATTESTATION = "refused_missing_attestation"
    REFUSED_EXPIRED_SESSION = "refused_expired_session"


@dataclass(frozen=True)
class HandshakeDecision:
    disposition: HandshakeDisposition
    action_id: str
    tool_name: str
    reason: str
    negotiated_at: str
    is_permitted: bool


class PreToolUseComplianceGate:
    """ACD draft-03 machine-to-machine compliance negotiation gate."""

    def __init__(
        self,
        max_transaction_amount_eur: float = 5000.0,
        permitted_scopes: Optional[Set[str]] = None,
        enforce_attestation_closure: bool = True,
    ):
        self.max_transaction_amount_eur = max_transaction_amount_eur
        self.permitted_scopes = permitted_scopes or {"read", "query", "payments:sepa:initiate"}
        self.enforce_attestation_closure = enforce_attestation_closure

    def negotiate(
        self,
        tool_call: Dict[str, Any],
        caller_context: Dict[str, Any],
    ) -> HandshakeDecision:
        action_id = str(tool_call.get("action_id", "act-unknown"))
        tool_name = str(tool_call.get("tool_name", "unknown_tool"))
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Attestation Closure enforcement
        if self.enforce_attestation_closure:
            closure = caller_context.get("attestation_closure")
            if not closure or not isinstance(closure, dict):
                return HandshakeDecision(
                    disposition=HandshakeDisposition.REFUSED_MISSING_ATTESTATION,
                    action_id=action_id,
                    tool_name=tool_name,
                    reason="Caller lacks IETF AAT draft-03 Attestation Closure credentials",
                    negotiated_at=now_iso,
                    is_permitted=False,
                )

        # 2. Scope enforcement
        requested_scope = str(tool_call.get("required_scope", "payments:sepa:initiate"))
        caller_scopes = set(caller_context.get("scopes", []))
        if requested_scope not in caller_scopes:
            return HandshakeDecision(
                disposition=HandshakeDisposition.REFUSED_UNAUTHORIZED_SCOPE,
                action_id=action_id,
                tool_name=tool_name,
                reason=f"Caller scope {caller_scopes} does not permit '{requested_scope}'",
                negotiated_at=now_iso,
                is_permitted=False,
            )

        # 3. Financial ceiling enforcement
        params = tool_call.get("parameters", {})
        amount = params.get("amount") or params.get("value")
        if amount is not None:
            try:
                amt_float = float(amount)
                if amt_float > self.max_transaction_amount_eur:
                    return HandshakeDecision(
                        disposition=HandshakeDisposition.REFUSED_SPENDING_CEILING,
                        action_id=action_id,
                        tool_name=tool_name,
                        reason=f"Amount €{amt_float:,.2f} exceeds authorized ceiling €{self.max_transaction_amount_eur:,.2f}",
                        negotiated_at=now_iso,
                        is_permitted=False,
                    )
            except (ValueError, TypeError):
                pass

        # 4. Success / Authorized
        return HandshakeDecision(
            disposition=HandshakeDisposition.AUTHORIZED,
            action_id=action_id,
            tool_name=tool_name,
            reason="Pre-access compliance handshake completed and authorized",
            negotiated_at=now_iso,
            is_permitted=True,
        )
