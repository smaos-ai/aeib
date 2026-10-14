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
action_intelligence_brief.py
================================================================================
AEIB Action Intelligence Brief & Human Resolution Authority Adapter.

Implements the decision-ready workflow pattern inspired by operational narrative
intelligence paradigms, adapted under strict epistemic and cryptographic bounds:
  - Generates structured, permission-aware Action Intelligence Briefs when a
    governed consequential action enters an uncertain or indeterminate state
    (EFFECT_INDETERMINATE) and exhausts its bounded ProbeBudget.
  - Generates Slack Block Kit interactive message cards linking directly to
    verifiable receipts and RFC 8785 canonical hashes.
  - Verifies incoming Slack interaction webhook HMAC-SHA256 signatures with
    replay prevention (300-second maximum age).
  - Enforces Human Resolution Authority bounds: a human operator cannot override
    evidence or declare an unverified mutation successful; they may approve only
    policy-defined next steps (ESCALATE, REQUEST_ADDITIONAL_RECONCILIATION, or
    MARK_TARGET_FAILED_IF_EVIDENCE_SUPPORTS_IT).
  - Enforces single-use ticket burn and expiry, with optional step-up
    authentication challenge parameters consistent with RFC 9470 concepts.
  - Confines LLM translation strictly to read-only presentation; the model
    cannot evaluate policy, authorize actions, or classify external effects.
"""

import os
import sys
import json
import time
import uuid
import hmac
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Add repository root to path for JCS canonicalizer and boundary imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs

try:
    from v1_1_roadmap.governed_financial_action_boundary import (
        FinancialCandidateAction,
        FinancialContinuityReceipt,
        DISPOSITION_EFFECT_INDETERMINATE,
        DISPOSITION_RECONCILIATION_CONFLICT,
        DISPOSITION_PRESERVED_UNCERTAINTY,
        DISPOSITION_CONFIRMED,
        DISPOSITION_REFUTED
    )
except ImportError:
    from governed_financial_action_boundary import (
        FinancialCandidateAction,
        FinancialContinuityReceipt,
        DISPOSITION_EFFECT_INDETERMINATE,
        DISPOSITION_RECONCILIATION_CONFLICT,
        DISPOSITION_PRESERVED_UNCERTAINTY,
        DISPOSITION_CONFIRMED,
        DISPOSITION_REFUTED
    )


# ------------------------------------------------------------------------------
# Epistemic Constants & Boundaries
# ------------------------------------------------------------------------------
PRIORITY_P1 = "P1"  # Ambiguous / unresolved financial mutation
PRIORITY_P2 = "P2"  # Probe budget exhaustion / target oracle outage
PRIORITY_P3 = "P3"  # Policy step-up threshold exceeded
PRIORITY_P4 = "P4"  # Informational observation

# Allowed next steps for Human Resolution Authority
DECISION_ESCALATE = "ESCALATE"
DECISION_MARK_TARGET_FAILED = "MARK_TARGET_FAILED_IF_EVIDENCE_SUPPORTS_IT"
DECISION_REQUEST_ADDITIONAL_RECONCILIATION = "REQUEST_ADDITIONAL_RECONCILIATION"

ALLOWED_RESOLUTION_STEPS: Set[str] = {
    DECISION_ESCALATE,
    DECISION_MARK_TARGET_FAILED,
    DECISION_REQUEST_ADDITIONAL_RECONCILIATION
}

# Explicitly prohibited actions that a human cannot authorize regardless of UI interaction
PROHIBITED_DECLARE_SUCCESS = "DECLARE_SUCCESS_WITHOUT_TARGET_EVIDENCE"
PROHIBITED_RETRY_BLINDLY = "RETRY_BLINDLY"
PROHIBITED_CHANGE_POLICY = "CHANGE_POLICY"
PROHIBITED_GRANT_NEW_AUTHORITY = "GRANT_NEW_FINANCIAL_AUTHORITY"

PROHIBITED_RESOLUTION_STEPS: Set[str] = {
    PROHIBITED_DECLARE_SUCCESS,
    PROHIBITED_RETRY_BLINDLY,
    PROHIBITED_CHANGE_POLICY,
    PROHIBITED_GRANT_NEW_AUTHORITY
}

BANNED_WORDS = [
    "guaranteed",
    "proven universally",
    "bulletproof",
    "enterprise-grade",
    "production-safe",
    "100% secure"
]

NON_AUTHORITATIVE_DISCLAIMER = (
    "Notice: This explanation is an automated summary of structured operation "
    "evidence under the stated model. It is not an authorization, policy evaluation, "
    "or verified target claim."
)


# ------------------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------------------
class ProhibitedDecisionError(Exception):
    """Raised when an operator or component attempts an explicitly prohibited resolution step."""
    pass


class TicketAlreadyBurnedError(Exception):
    """Raised when a single-use resolution authority ticket is presented for reuse."""
    pass


class TicketExpiredError(Exception):
    """Raised when a resolution authority ticket has expired."""
    pass


class InvalidSignatureError(Exception):
    """Raised when cryptographic signature verification fails."""
    pass


class StepUpAuthenticationRequiredError(Exception):
    """Raised when step-up authentication is missing or insufficient per RFC 9470 concepts."""
    pass


# ------------------------------------------------------------------------------
# Data Models
# ------------------------------------------------------------------------------
@dataclass
class HumanResolutionAuthority:
    """
    Policy-bound, single-use, time-limited cryptographic approval token
    permitting an authorized operator to execute a policy-defined next step.
    """
    ticket_id: str
    operation_id: str
    approver_principal: str
    decision: str
    issued_at: float
    expires_at: float
    step_up_context: Optional[Dict[str, Any]] = None
    consumed: bool = False
    signature_hex: str = ""

    def to_signable_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "operation_id": self.operation_id,
            "approver_principal": self.approver_principal,
            "decision": self.decision,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "step_up_context": self.step_up_context or {}
        }

    def sign(self, signing_key: ed25519.Ed25519PrivateKey) -> None:
        signable_bytes = encode_jcs(self.to_signable_dict())
        sig = signing_key.sign(signable_bytes)
        self.signature_hex = sig.hex()

    def verify(self, public_key: ed25519.Ed25519PublicKey) -> bool:
        if not self.signature_hex:
            return False
        try:
            signable_bytes = encode_jcs(self.to_signable_dict())
            sig_bytes = bytes.fromhex(self.signature_hex)
            public_key.verify(sig_bytes, signable_bytes)
            return True
        except Exception:
            return False


@dataclass
class ActionIntelligenceBrief:
    """
    Decision-ready brief synthesizing structured operation evidence,
    transport observations, and bounded resolution options.
    """
    brief_id: str
    priority: str
    operation_id: str
    action_id: str
    caid: str
    principal: str
    target_uri: str
    what_was_authorized: Dict[str, Any]
    what_happened_externally: Dict[str, Any]
    what_aeib_did: List[str]
    evidence_links: Dict[str, Any]
    permitted_next_steps: List[str] = field(default_factory=lambda: sorted(list(ALLOWED_RESOLUTION_STEPS)))
    prohibited_next_steps: List[str] = field(default_factory=lambda: sorted(list(PROHIBITED_RESOLUTION_STEPS)))
    human_resolution_authority: Optional[HumanResolutionAuthority] = None
    llm_summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.human_resolution_authority:
            d["human_resolution_authority"] = self.human_resolution_authority.to_signable_dict()
            d["human_resolution_authority"]["consumed"] = self.human_resolution_authority.consumed
            d["human_resolution_authority"]["signature_hex"] = self.human_resolution_authority.signature_hex
        return d


# ------------------------------------------------------------------------------
# Brief Generator
# ------------------------------------------------------------------------------
class ActionIntelligenceBriefGenerator:
    """
    Constructs an ActionIntelligenceBrief from candidate action and boundary receipt.
    """
    @staticmethod
    def generate_brief(
        candidate: FinancialCandidateAction,
        receipt: FinancialContinuityReceipt,
        transport_outcome: str,
        http_status: int,
        target_reconciliation_status: str,
        probes_executed: int,
        policy_version: str = "finance_v7"
    ) -> ActionIntelligenceBrief:
        # Determine risk priority based on disposition and outcome
        if receipt.disposition in (
            DISPOSITION_EFFECT_INDETERMINATE,
            DISPOSITION_RECONCILIATION_CONFLICT,
            DISPOSITION_PRESERVED_UNCERTAINTY
        ):
            priority = PRIORITY_P1
        elif target_reconciliation_status == "OUTAGE" or probes_executed > 0:
            priority = PRIORITY_P2
        else:
            priority = PRIORITY_P3

        brief_id = f"brief_{uuid.uuid4().hex[:12]}"
        operation_id = candidate.parameters.get("operation_id") or candidate.action_id
        amount_cents = int(candidate.parameters.get("amount_cents", 0))
        currency = str(candidate.parameters.get("currency", "EUR"))

        amount_formatted = f"{amount_cents / 100:.2f} {currency}"
        action_summary = f"{candidate.operation_type} ({amount_formatted})"

        what_authorized = {
            "action_summary": action_summary,
            "amount_cents": amount_cents,
            "currency": currency,
            "policy_version": policy_version,
            "policy_epoch": candidate.policy_epoch
        }

        what_happened = {
            "transport_outcome": transport_outcome,
            "http_status": http_status,
            "target_reconciliation_status": target_reconciliation_status,
            "probes_executed": probes_executed
        }

        # Deterministic AEIB actions log
        aeib_actions = [
            "Persisted dispatch intent to write-ahead journal before socket dispatch",
            "Burned single-use authorization ticket to prevent replay or concurrent reuse",
            "Evaluated transport outcome and latched EFFECT_INDETERMINATE fail-closed",
            f"Executed {probes_executed} authenticated reconciliation check(s) under ProbeBudget: 1"
        ]
        if target_reconciliation_status == "INCONCLUSIVE" or receipt.disposition == DISPOSITION_PRESERVED_UNCERTAINTY:
            aeib_actions.append("Reconciliation was inconclusive; preserved uncertainty without blind retry")

        auth_hash = hashlib.sha256(receipt.ticket_id.encode("utf-8")).hexdigest()
        intent_hash = hashlib.sha256(candidate.compute_caid().encode("utf-8")).hexdigest()

        evidence_links = {
            "authorization_receipt_sha256": auth_hash,
            "dispatch_intent_receipt_sha256": intent_hash,
            "chain_tip": receipt.chain_tip,
            "public_key_pem": receipt.public_key_pem,
            "timestamp_utc": receipt.timestamp_utc
        }

        return ActionIntelligenceBrief(
            brief_id=brief_id,
            priority=priority,
            operation_id=operation_id,
            action_id=candidate.action_id,
            caid=candidate.compute_caid(),
            principal=candidate.principal,
            target_uri=candidate.target_uri,
            what_was_authorized=what_authorized,
            what_happened_externally=what_happened,
            what_aeib_did=aeib_actions,
            evidence_links=evidence_links,
            permitted_next_steps=sorted(list(ALLOWED_RESOLUTION_STEPS)),
            prohibited_next_steps=sorted(list(PROHIBITED_RESOLUTION_STEPS))
        )


# ------------------------------------------------------------------------------
# Slack Block Kit Adapter & Webhook Request Verifier
# ------------------------------------------------------------------------------
class SlackBlockKitAdapter:
    """
    Renders ActionIntelligenceBriefs into Slack Block Kit payloads and
    verifies inbound Slack interactive webhook requests using HMAC-SHA256.
    """
    @staticmethod
    def format_slack_block_kit(
        brief: ActionIntelligenceBrief,
        evidence_base_url: str = "https://aeib.internal/evidence"
    ) -> Dict[str, Any]:
        """
        Renders a Block Kit message card.
        Includes action buttons strictly for permitted options:
          - [View Evidence]
          - [Escalate]
          - [Request Additional Check]
        Explicitly excludes any 'Approve Release' or 'Mark Failed' buttons
        unless backed by authorized target evidence.
        """
        header_text = f"🚨 [{brief.priority} — RESOLUTION REQUIRED] Ambiguous Agent Mutation"
        operation_text = f"*Operation ID:* `{brief.operation_id}`\n*Action ID:* `{brief.action_id}`"
        authorized_text = (
            f"*WHAT WAS AUTHORIZED:*\n"
            f"• *Action:* {brief.what_was_authorized.get('action_summary')}\n"
            f"• *Target:* `{brief.target_uri}`\n"
            f"• *Policy:* `{brief.what_was_authorized.get('policy_version')}` (Epoch {brief.what_was_authorized.get('policy_epoch')})"
        )
        external_text = (
            f"*WHAT HAPPENED EXTERNALLY:*\n"
            f"• *Transport Outcome:* `{brief.what_happened_externally.get('transport_outcome')}` (HTTP {brief.what_happened_externally.get('http_status')})\n"
            f"• *Reconciliation Status:* `{brief.what_happened_externally.get('target_reconciliation_status')}` "
            f"({brief.what_happened_externally.get('probes_executed')} probe executed)"
        )
        aeib_did_lines = "\n".join([f"• {act}" for act in brief.what_aeib_did])
        aeib_text = f"*WHAT AEIB DID:*\n{aeib_did_lines}"

        evidence_url = f"{evidence_base_url}/{brief.operation_id}"
        evidence_text = (
            f"*EVIDENCE ATTACHED:*\n"
            f"• *Receipt Tip:* `{brief.evidence_links.get('chain_tip')[:24]}...`\n"
            f"• *Intent Digest:* `{brief.evidence_links.get('dispatch_intent_receipt_sha256')[:24]}...`\n"
            f"• *Timestamp:* `{brief.evidence_links.get('timestamp_utc')}`"
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text,
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": operation_text
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": authorized_text
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": external_text
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": aeib_text
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": evidence_text
                }
            },
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": f"aeib_resolution_actions_{brief.operation_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Evidence",
                            "emoji": True
                        },
                        "url": evidence_url,
                        "action_id": "action_view_evidence"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Escalate to L2",
                            "emoji": True
                        },
                        "style": "danger",
                        "value": json.dumps({"operation_id": brief.operation_id, "action": DECISION_ESCALATE}),
                        "action_id": "action_escalate_l2"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Request Additional Check",
                            "emoji": True
                        },
                        "value": json.dumps({"operation_id": brief.operation_id, "action": DECISION_REQUEST_ADDITIONAL_RECONCILIATION}),
                        "action_id": "action_request_recheck"
                    }
                ]
            }
        ]

        return {
            "text": f"🚨 [{brief.priority}] Ambiguous Agent Mutation — Operation {brief.operation_id}",
            "blocks": blocks
        }

    @staticmethod
    def verify_slack_request(
        headers: Dict[str, str],
        raw_body: bytes,
        signing_secret: str,
        max_age_seconds: int = 300,
        current_time: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Cryptographically verifies Slack webhook request signatures according to
        Slack API standards (HMAC-SHA256 over 'v0:{timestamp}:{raw_body}').
        Rejects requests older than max_age_seconds to prevent replay attacks.
        """
        # Look up headers case-insensitively
        norm_headers = {k.lower(): v for k, v in headers.items()}
        timestamp_str = norm_headers.get("x-slack-request-timestamp")
        signature = norm_headers.get("x-slack-signature")

        if not timestamp_str or not signature:
            return False, "MISSING_SLACK_HEADERS: Missing X-Slack-Request-Timestamp or X-Slack-Signature."

        try:
            req_timestamp = int(timestamp_str)
        except ValueError:
            return False, "INVALID_TIMESTAMP: X-Slack-Request-Timestamp must be an integer."

        now = current_time if current_time is not None else time.time()
        if abs(now - req_timestamp) > max_age_seconds:
            return False, f"REPLAY_OR_EXPIRED: Timestamp {req_timestamp} deviates from current time {now} by > {max_age_seconds}s."

        sig_basestring = f"v0:{req_timestamp}:".encode("utf-8") + raw_body
        expected_sig = "v0=" + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, signature):
            return False, "INVALID_SIGNATURE: HMAC verification failed."

        return True, "VERIFIED"


# ------------------------------------------------------------------------------
# Human Resolution Authority Manager
# ------------------------------------------------------------------------------
class HumanResolutionAuthorityManager:
    """
    Manages issuance, cryptographic validation, and single-use consumption
    of HumanResolutionAuthority tokens.
    """
    def __init__(
        self,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        storage_path: Optional[Path] = None
    ):
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.signing_key.public_key()
        self.public_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")
        self.storage_path = storage_path
        self._consumed_tickets: Set[str] = set()

    def issue_authority(
        self,
        operation_id: str,
        approver_principal: str,
        decision: str,
        validity_seconds: float = 300.0,
        step_up_acr: Optional[str] = None
    ) -> HumanResolutionAuthority:
        """
        Issues a single-use HumanResolutionAuthority token.
        Fails closed if the proposed decision is in PROHIBITED_RESOLUTION_STEPS.
        """
        if decision in PROHIBITED_RESOLUTION_STEPS:
            raise ProhibitedDecisionError(
                f"PROHIBITED_ACTION: Decision '{decision}' is strictly prohibited. "
                f"A human operator cannot override evidence or grant unverified success."
            )

        if decision not in ALLOWED_RESOLUTION_STEPS:
            raise ValueError(
                f"UNRECOGNIZED_DECISION: Decision '{decision}' is not in policy-allowed set: {ALLOWED_RESOLUTION_STEPS}."
            )

        now = time.time()
        ticket_id = f"hra_{uuid.uuid4().hex[:12]}"

        step_up_context = None
        if step_up_acr:
            step_up_context = {
                "acr_values": step_up_acr,
                "auth_time": now
            }

        ticket = HumanResolutionAuthority(
            ticket_id=ticket_id,
            operation_id=operation_id,
            approver_principal=approver_principal,
            decision=decision,
            issued_at=now,
            expires_at=now + validity_seconds,
            step_up_context=step_up_context,
            consumed=False
        )

        ticket.sign(self.signing_key)
        return ticket

    def consume_authority(
        self,
        ticket: HumanResolutionAuthority,
        target_evidence_supports_failure: bool = False,
        current_time: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Consumes the resolution authority token once-and-only-once.
        Enforces:
          - Replay prevention (ticket not already consumed)
          - Expiration check
          - Cryptographic signature check
          - Target evidence requirement for failure marking
        """
        now = current_time if current_time is not None else time.time()

        if ticket.ticket_id in self._consumed_tickets or ticket.consumed:
            raise TicketAlreadyBurnedError(
                f"TICKET_ALREADY_BURNED: Ticket '{ticket.ticket_id}' has already been consumed."
            )

        if now > ticket.expires_at:
            raise TicketExpiredError(
                f"TICKET_EXPIRED: Ticket '{ticket.ticket_id}' expired at {ticket.expires_at} (current time: {now})."
            )

        if not ticket.verify(self.public_key):
            raise InvalidSignatureError(
                f"INVALID_SIGNATURE: Ticket '{ticket.ticket_id}' signature failed cryptographic verification."
            )

        # Enforce target evidence rule for MARK_TARGET_FAILED
        if ticket.decision == DECISION_MARK_TARGET_FAILED and not target_evidence_supports_failure:
            raise ProhibitedDecisionError(
                "CANNOT_MARK_FAILED_WITHOUT_EVIDENCE: Marking a target failed requires authenticated "
                "target-side status confirmation (e.g. 404 NOT_FOUND or explicit target reversal). "
                "A human decision is not an evidence override."
            )

        ticket.consumed = True
        self._consumed_tickets.add(ticket.ticket_id)

        return True, "AUTHORITY_CONSUMED_SUCCESSFULLY"


# ------------------------------------------------------------------------------
# LLM Explainer (Strictly Non-Authoritative Presentation Layer)
# ------------------------------------------------------------------------------
class LLMExplainer:
    """
    Renders structured ActionIntelligenceBriefs into human-readable prose.

    Epistemic Boundary:
      - The explainer is strictly read-only presentation.
      - It has NO access to authority, state modification, or policy gates.
      - It cannot classify external effects or resolve EFFECT_INDETERMINATE.
      - It enforces that all outputs carry an explicit non-authoritative disclaimer
        and zero banned words.
    """
    @staticmethod
    def explain(brief: ActionIntelligenceBrief) -> Dict[str, Any]:
        what_auth = brief.what_was_authorized
        what_ext = brief.what_happened_externally

        text = (
            f"Operational Case Summary for Operation {brief.operation_id}:\n"
            f"An agent principal ('{brief.principal}') requested a consequential {what_auth.get('action_summary')} "
            f"under policy {what_auth.get('policy_version')} (Epoch {what_auth.get('policy_epoch')}).\n"
            f"Following dispatch, an ambiguous transport event occurred ({what_ext.get('transport_outcome')}, "
            f"HTTP status {what_ext.get('http_status')}). AEIB classified the external outcome as unresolved "
            f"(EFFECT_INDETERMINATE), recorded the intent before dispatch, and blocked blind retries.\n"
            f"An authenticated reconciliation probe was conducted ({what_ext.get('probes_executed')} probe(s)), "
            f"yielding status '{what_ext.get('target_reconciliation_status')}'.\n"
            f"Permitted operator actions: {', '.join(brief.permitted_next_steps)}."
        )

        # Epistemic self-check: verify zero banned words
        for banned in BANNED_WORDS:
            if banned in text.lower():
                text = text.replace(banned, "[redacted_epistemic_violation]")

        return {
            "text": text,
            "disclaimer": NON_AUTHORITATIVE_DISCLAIMER,
            "is_authoritative": False
        }
