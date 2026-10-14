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
governed_financial_action_boundary.py
================================================================================
AEIB Governed Financial Action Boundary: Customer Refund & Payment Gateway.

Operates under the stated model as a narrow, verifiable execution boundary
positioned between autonomous AI agents and high-consequence financial APIs.

Implements the 7 Core Controls (The P0 Core):
  1. Exact Action Authorization:
     Evaluates exact canonical action, principal, target URI, and policy epoch.
  2. Durable Dispatch Intent (EO-1 Evidence-Before-Effect):
     Persists intent to write-ahead journal with os.fsync before socket dispatch.
  3. Single-Use Dispatch Authority:
     Burns authorization ticket upon use to prevent replay or concurrent reuse.
  4. Governed Executor:
     Dispatches strictly the authorized canonical payload to payment endpoints.
  5. Uncertain-Outcome Classification:
     Explicitly latches EFFECT_INDETERMINATE on transport faults (504, TCP RST).
  6. Bounded Operation-Specific Reconciliation:
     Resolves ambiguity using authenticated target status under strict ProbeBudget.
  7. Verifiable Operation-Bound Receipt:
     Mints RFC 8785 JCS payload with Ed25519 signature for offline verification.
"""

import os
import sys
import json
import time
import uuid
import struct
import socket
import hashlib
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Add repository root to path for JCS canonicalizer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs


# ------------------------------------------------------------------------------
# Epistemic Constants & Dispositions
# ------------------------------------------------------------------------------
DISPOSITION_ALLOW = "ALLOW"
DISPOSITION_DENY = "DENY"
DISPOSITION_STEP_UP = "STEP_UP"
DISPOSITION_CONFIRMED = "CONFIRMED"
DISPOSITION_REFUTED = "REFUTED"
DISPOSITION_EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
DISPOSITION_RECONCILIATION_CONFLICT = "RECONCILIATION_CONFLICT"
DISPOSITION_PRESERVED_UNCERTAINTY = "PRESERVED_UNCERTAINTY"

# Ephemeral reasoning keys stripped by the Dead Salmons filter
EPHEMERAL_REASONING_KEYS = {
    "_reasoning",
    "chain_of_thought",
    "thought",
    "rationale",
    "explanation",
    "cot",
    "internal_monologue"
}


# ------------------------------------------------------------------------------
# Data Models: CandidateAction, Ticket, Journal Entries
# ------------------------------------------------------------------------------
@dataclass
class FinancialCandidateAction:
    """
    Structured action proposal submitted by an agent for financial execution.
    """
    action_id: str
    principal: str
    target_uri: str
    operation_type: str  # e.g., "customer_refund", "payment_transfer"
    parameters: Dict[str, Any]
    policy_epoch: int
    source_epoch: int
    delegation_token: Optional[str] = None
    max_amount_cents_limit: int = 500000  # Default limit: 5,000.00 EUR

    def extract_canonical_payload(self) -> Dict[str, Any]:
        """
        Applies Dead Salmons filter to remove ephemeral thoughts and returns
        the exact canonical dictionary subject to cryptographic binding.
        """
        cleaned_params = {}
        for k, v in self.parameters.items():
            if k not in EPHEMERAL_REASONING_KEYS:
                cleaned_params[k] = v

        return {
            "action_id": self.action_id,
            "principal": self.principal,
            "target_uri": self.target_uri,
            "operation_type": self.operation_type,
            "parameters": cleaned_params,
            "policy_epoch": self.policy_epoch,
            "source_epoch": self.source_epoch
        }

    def compute_caid(self) -> str:
        """
        Derives the Content-Addressed Action Identifier (CAID) via RFC 8785 JCS + SHA-256.
        """
        canonical_dict = self.extract_canonical_payload()
        canonical_bytes = encode_jcs(canonical_dict)
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        return f"caid:sha256:{digest}"


@dataclass
class DispatchAuthorizationTicket:
    """
    Cryptographic single-use token issued upon passing standing and policy evaluation.
    """
    ticket_id: str
    caid: str
    principal: str
    target_uri: str
    policy_epoch: int
    issued_at: float
    expires_at: float
    consumed: bool = False
    signature_hex: str = ""

    def to_signable_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "caid": self.caid,
            "principal": self.principal,
            "target_uri": self.target_uri,
            "policy_epoch": self.policy_epoch,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at
        }


@dataclass
class FinancialContinuityReceipt:
    """
    Operation-bound verifiable execution receipt with Ed25519 signature.
    """
    receipt_version: str
    action_id: str
    caid: str
    ticket_id: str
    principal: str
    target_uri: str
    operation_id: str
    disposition: str
    retry_safe: bool
    reconciliation_attempts: int
    downstream_commit_count: int
    chain_tip: str
    timestamp_utc: str
    signature_hex: str = ""
    public_key_pem: str = ""

    def to_unsigned_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("signature_hex", None)
        d.pop("public_key_pem", None)
        return d


# ------------------------------------------------------------------------------
# Target Service Simulator (Realistic Bank / Payment Gateway)
# ------------------------------------------------------------------------------
class ExternalPaymentLedger:
    """
    Authoritative database owned by the payment processor / banking primary.
    Tracks actual committed mutations and provides independent status verification.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.records: Dict[str, Dict[str, Any]] = {}
        self.commit_counts: Dict[str, int] = {}

    def commit(self, operation_id: str, idempotency_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            count = self.commit_counts.get(operation_id, 0) + 1
            self.commit_counts[operation_id] = count
            rec = {
                "operation_id": operation_id,
                "idempotency_key": idempotency_key,
                "payload": payload,
                "status": "SETTLED",
                "commit_count": count,
                "settled_at": datetime.now(timezone.utc).isoformat()
            }
            self.records[operation_id] = rec
            return rec

    def probe(self, operation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.records.get(operation_id)

    def get_commit_count(self, operation_id: str) -> int:
        with self._lock:
            return self.commit_counts.get(operation_id, 0)


class RealisticPaymentSimulator:
    """
    Simulates target financial API with granular fault injection:
      - Clean execution
      - HTTP 504 Gateway Timeout post-commit
      - TCP RST socket disconnect post-commit
      - Unreadable/corrupt response post-commit
      - Target rejection (e.g. invalid account / insufficient funds)
      - Conflicting idempotency record
      - Status endpoint outage
    """
    DISPATCH_NORMAL_SUCCESS = "NORMAL_SUCCESS"
    DISPATCH_NORMAL_REJECTION = "NORMAL_REJECTION"
    DISPATCH_HTTP_504 = "HTTP_504"
    DISPATCH_TCP_RST = "TCP_RST"
    DISPATCH_TIMEOUT = "TIMEOUT"
    DISPATCH_MALFORMED = "MALFORMED"

    PROBE_NORMAL = "PROBE_NORMAL"
    PROBE_NOT_FOUND = "PROBE_NOT_FOUND"
    PROBE_CONFLICT = "PROBE_CONFLICT"
    PROBE_OUTAGE = "PROBE_OUTAGE"

    def __init__(self, ledger: Optional[ExternalPaymentLedger] = None):
        self.ledger = ledger or ExternalPaymentLedger()
        self.dispatch_mode = self.DISPATCH_NORMAL_SUCCESS
        self.probe_mode = self.PROBE_NORMAL
        self.probe_delay_seconds = 0.0

    def set_dispatch_mode(self, mode: str):
        self.dispatch_mode = mode

    def set_probe_mode(self, mode: str):
        self.probe_mode = mode

    def dispatch_payment(
        self,
        operation_id: str,
        idempotency_key: str,
        payload: Dict[str, Any]
    ) -> Tuple[int, Optional[Dict[str, Any]], str]:
        """
        Simulates dispatching mutating HTTP POST /v1/payments/refunds.
        Returns: (http_status, parsed_body_or_none, transport_fault_label)
        """
        if self.dispatch_mode == self.DISPATCH_NORMAL_REJECTION:
            return (
                422,
                {"status": "REJECTED", "reason": "REFUND_EXCEEDS_ORIGINAL_CHARGE", "operation_id": operation_id},
                "NONE"
            )

        # Mutating operations commit to authoritative ledger
        rec = self.ledger.commit(operation_id, idempotency_key, payload)

        if self.dispatch_mode == self.DISPATCH_HTTP_504:
            return (504, None, "HTTP_504_GATEWAY_TIMEOUT")

        if self.dispatch_mode == self.DISPATCH_TCP_RST:
            return (0, None, "TCP_CONNECTION_RESET_BY_PEER")

        if self.dispatch_mode == self.DISPATCH_TIMEOUT:
            return (0, None, "SOCKET_READ_TIMEOUT")

        if self.dispatch_mode == self.DISPATCH_MALFORMED:
            return (200, None, "MALFORMED_NON_JSON_RESPONSE")

        # Nominal Success
        return (
            200,
            {
                "status": "CONFIRMED",
                "operation_id": operation_id,
                "transaction_id": f"tx_bank_{operation_id[:8]}",
                "commit_count": rec["commit_count"],
                "settled_at": rec["settled_at"]
            },
            "NONE"
        )

    def probe_reconciliation(
        self,
        operation_id: str,
        idempotency_key: str
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Queries out-of-band authenticated status endpoint:
        GET /v1/payments/refunds/{operation_id}/status
        """
        if self.probe_delay_seconds > 0:
            time.sleep(self.probe_delay_seconds)

        if self.probe_mode == self.PROBE_OUTAGE:
            return (503, {"status": "SERVICE_UNAVAILABLE", "reason": "status_oracle_offline"})

        if self.probe_mode == self.PROBE_CONFLICT:
            return (409, {
                "status": "CONFLICT",
                "operation_id": operation_id,
                "reason": "DUPLICATE_IDEMPOTENCY_MISMATCH"
            })

        if self.probe_mode == self.PROBE_NOT_FOUND:
            return (404, {
                "status": "NOT_FOUND",
                "operation_id": operation_id,
                "commit_count": 0
            })

        rec = self.ledger.probe(operation_id)
        if rec:
            return (200, {
                "status": "COMMITTED",
                "operation_id": operation_id,
                "commit_count": rec["commit_count"],
                "details": rec
            })
        else:
            return (404, {
                "status": "NOT_FOUND",
                "operation_id": operation_id,
                "commit_count": 0
            })


# ------------------------------------------------------------------------------
# Durable Dispatch Journal (EO-1: Evidence-Before-Effect)
# ------------------------------------------------------------------------------
class DurableDispatchJournal:
    """
    Append-only write-ahead log committed with os.fsync before socket dispatch.
    Ensures recovery from mid-syscall process termination.
    """
    def __init__(self, journal_path: Path):
        self.journal_path = journal_path
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            line = json.dumps(entry) + "\n"
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

    def read_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self.journal_path.exists():
                return []
            entries = []
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            continue
            return entries


# ------------------------------------------------------------------------------
# Persistent Single-Use Ticket Store
# ------------------------------------------------------------------------------
class PersistentSingleUseTicketStore:
    """
    Guarantees tickets are consumed once-and-only-once across restart boundaries.
    """
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._consumed_tickets: Set[str] = set()
        self._issued_tickets: Dict[str, DispatchAuthorizationTicket] = {}
        self._load()

    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rec = json.loads(line)
                            if rec.get("status") == "CONSUMED":
                                self._consumed_tickets.add(rec["ticket_id"])
                        except Exception:
                            continue

    def register_issued_ticket(self, ticket: DispatchAuthorizationTicket) -> None:
        with self._lock:
            self._issued_tickets[ticket.ticket_id] = ticket

    def burn_ticket(self, ticket_id: str, caid: str) -> Tuple[bool, str]:
        """
        Atomically burns ticket to prevent replay.
        Fails closed if ticket is already consumed, missing, or CAID mismatched.
        """
        with self._lock:
            if ticket_id in self._consumed_tickets:
                return False, f"TICKET_ALREADY_BURNED: ticket '{ticket_id}' has already been consumed."

            ticket = self._issued_tickets.get(ticket_id)
            if not ticket:
                return False, f"TICKET_NOT_FOUND: ticket '{ticket_id}' was never issued."

            if ticket.caid != caid:
                return False, f"TICKET_CAID_MISMATCH: ticket CAID '{ticket.caid}' does not match action CAID '{caid}'."

            now = time.time()
            if now > ticket.expires_at:
                return False, f"TICKET_EXPIRED: ticket expired at {ticket.expires_at} (current time: {now})."

            self._consumed_tickets.add(ticket_id)
            ticket.consumed = True

            # Persist burn record with fsync
            with open(self.storage_path, "a", encoding="utf-8") as f:
                record = {
                    "ticket_id": ticket_id,
                    "caid": caid,
                    "status": "CONSUMED",
                    "burned_at": now
                }
                f.write(json.dumps(record) + "\n")
                f.flush()
                os.fsync(f.fileno())

            return True, "TICKET_BURNED"


# ------------------------------------------------------------------------------
# The Governed Financial Action Boundary (P0 Core)
# ------------------------------------------------------------------------------
class GovernedFinancialActionBoundary:
    """
    The narrow runtime boundary governing high-consequence financial dispatches.
    Enforces all 7 P0 core controls.
    """
    def __init__(
        self,
        base_dir: Path,
        active_policy_epoch: int = 1,
        allowed_targets: Optional[Set[str]] = None,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        probe_budget: int = 1
    ):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_policy_epoch = active_policy_epoch
        self.allowed_targets = allowed_targets or {
            "https://api.bank.internal/v1/payments/refunds",
            "https://api.bank.internal/v1/payments/transfers"
        }
        self.probe_budget = probe_budget

        # Real cryptographic keypair
        self.signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.signing_key.public_key()
        self.public_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")

        # Persistence engines
        self.journal = DurableDispatchJournal(self.base_dir / "intent_journal.jsonl")
        self.ticket_store = PersistentSingleUseTicketStore(self.base_dir / "ticket_store.jsonl")

        # Continuous hash chain tip
        self._chain_tip_file = self.base_dir / "chain_tip.txt"
        self._chain_tip = self._load_chain_tip()
        self._chain_lock = threading.Lock()

    def _load_chain_tip(self) -> str:
        if self._chain_tip_file.exists():
            return self._chain_tip_file.read_text(encoding="utf-8").strip()
        # Initial Genesis Hash
        return "sha256:" + hashlib.sha256(b"AEIB_GENESIS_FINANCIAL_BOUNDARY_v1.0").hexdigest()

    def _advance_chain_tip(self, event_bytes: bytes) -> str:
        with self._chain_lock:
            prev = self._chain_tip.encode("utf-8")
            new_tip = "sha256:" + hashlib.sha256(prev + event_bytes).hexdigest()
            self._chain_tip = new_tip
            with open(self._chain_tip_file, "w", encoding="utf-8") as f:
                f.write(new_tip)
                f.flush()
                os.fsync(f.fileno())
            return new_tip

    # --------------------------------------------------------------------------
    # Control 1: Exact Action Authorization
    # --------------------------------------------------------------------------
    def authorize_action(
        self,
        candidate: FinancialCandidateAction
    ) -> Tuple[bool, str, Optional[DispatchAuthorizationTicket]]:
        """
        Evaluates exact canonical action, principal, target, and policy epoch.
        Fails closed on any policy mismatch, target violation, or amount breach.
        """
        # 1. Target allowlist check
        if candidate.target_uri not in self.allowed_targets:
            return False, f"TARGET_NOT_ALLOWED: Target URI '{candidate.target_uri}' is not in policy allowlist.", None

        # 2. Policy epoch freshness check
        if candidate.policy_epoch != self.active_policy_epoch:
            return (
                False,
                f"STALE_POLICY_EPOCH: Candidate epoch {candidate.policy_epoch} != active epoch {self.active_policy_epoch}.",
                None
            )

        # 3. Numeric spend ceiling check
        amount_cents = candidate.parameters.get("amount_cents", 0)
        if not isinstance(amount_cents, (int, float)) or amount_cents < 0:
            return False, "INVALID_AMOUNT: Amount must be non-negative numeric.", None

        if amount_cents > candidate.max_amount_cents_limit:
            return (
                False,
                f"STEP_UP: Amount {amount_cents} cents exceeds automated limit {candidate.max_amount_cents_limit}; requires dual control.",
                None
            )

        # 4. Canonical CAID computation (applies Dead Salmons filter)
        caid = candidate.compute_caid()

        # 5. Mint single-use DispatchAuthorizationTicket
        now = time.time()
        ticket_id = f"ticket_auth_{uuid.uuid4().hex[:12]}"
        ticket = DispatchAuthorizationTicket(
            ticket_id=ticket_id,
            caid=caid,
            principal=candidate.principal,
            target_uri=candidate.target_uri,
            policy_epoch=candidate.policy_epoch,
            issued_at=now,
            expires_at=now + 300.0,  # 5-minute validity window
            consumed=False
        )

        # Sign ticket canonical bytes with boundary Ed25519 private key
        ticket_signable = ticket.to_signable_dict()
        ticket_bytes = encode_jcs(ticket_signable)
        sig = self.signing_key.sign(ticket_bytes)
        ticket.signature_hex = sig.hex()

        self.ticket_store.register_issued_ticket(ticket)
        return True, "AUTHORIZED", ticket

    # --------------------------------------------------------------------------
    # Full Lifecycle Execution (Controls 2 - 7)
    # --------------------------------------------------------------------------
    def execute_governed_action(
        self,
        candidate: FinancialCandidateAction,
        ticket: DispatchAuthorizationTicket,
        payment_service: RealisticPaymentSimulator,
        crash_point: Optional[str] = None
    ) -> FinancialContinuityReceipt:
        """
        Coordinates the complete crash-safe financial execution lifecycle:
          - Validates & burns authority ticket (Control 3)
          - Persists durable intent with os.fsync (Control 2: EO-1)
          - Governed dispatch to payment service (Control 4)
          - State machine classification & EFFECT_INDETERMINATE latching (Control 5)
          - Bounded out-of-band reconciliation under ProbeBudget (Control 6)
          - Operation-bound receipt issuance with Ed25519 signature (Control 7)
        """
        caid = candidate.compute_caid()
        operation_id = candidate.parameters.get("operation_id") or candidate.action_id
        idempotency_key = candidate.parameters.get("idempotency_key") or f"idem_{operation_id}"

        # Crash Point 1: Crash before single-use ticket burn or intent
        if crash_point == "BEFORE_INTENT":
            raise SystemExit("SIMULATED_PROCESS_CRASH: Process crashed before durable intent persistence.")

        # Control 3: Burn Single-Use Dispatch Authority
        burned, burn_msg = self.ticket_store.burn_ticket(ticket.ticket_id, caid)
        if not burned:
            receipt = self._mint_receipt(
                candidate=candidate,
                ticket=ticket,
                operation_id=operation_id,
                disposition=DISPOSITION_DENY,
                retry_safe=False,
                reconciliation_attempts=0,
                downstream_commit_count=0
            )
            return receipt

        # Control 2: Durable Dispatch Intent (EO-1)
        intent_entry = {
            "event_type": "DISPATCH_INTENT",
            "action_id": candidate.action_id,
            "caid": caid,
            "ticket_id": ticket.ticket_id,
            "operation_id": operation_id,
            "idempotency_key": idempotency_key,
            "target_uri": candidate.target_uri,
            "payload": candidate.extract_canonical_payload(),
            "status": "INTENT_COMMITTED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.journal.append(intent_entry)

        # Crash Point 2: Crash after intent persistence, before network dispatch
        if crash_point == "AFTER_INTENT_BEFORE_DISPATCH":
            raise SystemExit("SIMULATED_PROCESS_CRASH: Process crashed after intent persistence but before dispatch.")

        # Control 4: Governed Executor (Dispatches exact canonical payload)
        http_status, resp_data, transport_fault = payment_service.dispatch_payment(
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            payload=candidate.extract_canonical_payload()
        )

        # Crash Point 3: Crash during/immediately after socket write before outcome processing
        if crash_point == "DURING_DISPATCH":
            raise SystemExit("SIMULATED_PROCESS_CRASH: Process crashed during dispatch transport.")

        # Control 5: Uncertain-Outcome Classification
        reconciliation_attempts = 0
        final_disposition = DISPOSITION_ALLOW
        retry_safe = False
        downstream_commits = 0

        if transport_fault != "NONE" or http_status in (504, 502, 503, 0):
            # Ambiguous transport fault -> Latch EFFECT_INDETERMINATE with retry_safe: False
            final_disposition = DISPOSITION_EFFECT_INDETERMINATE
            retry_safe = False

            # Control 6: Bounded Operation-Specific Reconciliation
            if self.probe_budget > 0:
                reconciliation_attempts += 1
                probe_status, probe_data = payment_service.probe_reconciliation(
                    operation_id=operation_id,
                    idempotency_key=idempotency_key
                )

                if probe_status == 200 and probe_data.get("status") == "COMMITTED":
                    # Reconciled to CONFIRMED
                    final_disposition = DISPOSITION_CONFIRMED
                    downstream_commits = probe_data.get("commit_count", 1)
                    retry_safe = False
                elif probe_status == 404:
                    # Target explicitly confirmed zero external mutation occurred
                    final_disposition = DISPOSITION_REFUTED
                    downstream_commits = 0
                    retry_safe = True  # Safe to propose a fresh attempt under new action ID
                elif probe_status == 409:
                    # Contradictory evidence detected on target
                    final_disposition = DISPOSITION_RECONCILIATION_CONFLICT
                    downstream_commits = probe_data.get("commit_count", 1)
                    retry_safe = False
                else:
                    # Reconciliation failed or timed out -> Preserve uncertainty fail-closed
                    final_disposition = DISPOSITION_PRESERVED_UNCERTAINTY
                    downstream_commits = probe_data.get("commit_count", 0)
                    retry_safe = False
        elif http_status == 200:
            final_disposition = DISPOSITION_CONFIRMED
            retry_safe = False
            downstream_commits = resp_data.get("commit_count", 1) if resp_data else 1
        elif http_status in (400, 422):
            final_disposition = DISPOSITION_DENY
            retry_safe = False
            downstream_commits = 0
        else:
            final_disposition = DISPOSITION_PRESERVED_UNCERTAINTY
            retry_safe = False

        # Crash Point 4: Crash after target effect, before outcome receipt persistence
        if crash_point == "AFTER_EFFECT_BEFORE_RECEIPT":
            raise SystemExit("SIMULATED_PROCESS_CRASH: Process crashed after target effect before receipt persistence.")

        # Control 7: Verifiable Operation-Bound Receipt
        receipt = self._mint_receipt(
            candidate=candidate,
            ticket=ticket,
            operation_id=operation_id,
            disposition=final_disposition,
            retry_safe=retry_safe,
            reconciliation_attempts=reconciliation_attempts,
            downstream_commit_count=downstream_commits
        )

        # Log completion event to journal
        completion_entry = {
            "event_type": "LIFECYCLE_COMPLETED",
            "action_id": candidate.action_id,
            "operation_id": operation_id,
            "disposition": final_disposition,
            "retry_safe": retry_safe,
            "downstream_commit_count": downstream_commits,
            "receipt_chain_tip": receipt.chain_tip,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.journal.append(completion_entry)

        return receipt

    def _mint_receipt(
        self,
        candidate: FinancialCandidateAction,
        ticket: DispatchAuthorizationTicket,
        operation_id: str,
        disposition: str,
        retry_safe: bool,
        reconciliation_attempts: int,
        downstream_commit_count: int
    ) -> FinancialContinuityReceipt:
        """
        Creates, signs, and hash-chains the RFC 8785 verifiable receipt.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        caid = candidate.compute_caid()

        # Advance hash chain with event binding
        chain_event_bytes = encode_jcs({
            "action_id": candidate.action_id,
            "caid": caid,
            "operation_id": operation_id,
            "disposition": disposition,
            "timestamp_utc": now_iso
        })
        chain_tip = self._advance_chain_tip(chain_event_bytes)

        # Build complete unsigned receipt
        unsigned_receipt = {
            "receipt_version": "v1.0.0-financial-boundary",
            "action_id": candidate.action_id,
            "caid": caid,
            "ticket_id": ticket.ticket_id,
            "principal": candidate.principal,
            "target_uri": candidate.target_uri,
            "operation_id": operation_id,
            "disposition": disposition,
            "retry_safe": retry_safe,
            "reconciliation_attempts": reconciliation_attempts,
            "downstream_commit_count": downstream_commit_count,
            "chain_tip": chain_tip,
            "timestamp_utc": now_iso
        }

        # Canonical RFC 8785 JCS bytes
        receipt_bytes = encode_jcs(unsigned_receipt)

        # Ed25519 digital signature directly over canonical receipt bytes
        sig = self.signing_key.sign(receipt_bytes)

        return FinancialContinuityReceipt(
            receipt_version="v1.0.0-financial-boundary",
            action_id=candidate.action_id,
            caid=caid,
            ticket_id=ticket.ticket_id,
            principal=candidate.principal,
            target_uri=candidate.target_uri,
            operation_id=operation_id,
            disposition=disposition,
            retry_safe=retry_safe,
            reconciliation_attempts=reconciliation_attempts,
            downstream_commit_count=downstream_commit_count,
            chain_tip=chain_tip,
            timestamp_utc=now_iso,
            signature_hex=sig.hex(),
            public_key_pem=self.public_key_pem
        )

    # --------------------------------------------------------------------------
    # Crash Recovery & Startup Re-Synchronization
    # --------------------------------------------------------------------------
    def recover_from_crash(
        self,
        payment_service: RealisticPaymentSimulator
    ) -> List[Dict[str, Any]]:
        """
        Evaluates unacknowledged intent entries in the write-ahead journal.
        If an intent was persisted without a matching completion receipt,
        initiates out-of-band reconciliation to settle state without blind retry.
        """
        entries = self.journal.read_all()
        intents: Dict[str, Dict[str, Any]] = {}
        completed: Set[str] = set()

        for e in entries:
            evt_type = e.get("event_type")
            action_id = e.get("action_id")
            if evt_type == "DISPATCH_INTENT":
                intents[action_id] = e
            elif evt_type == "LIFECYCLE_COMPLETED":
                completed.add(action_id)

        recovery_resolutions = []
        for action_id, intent in intents.items():
            if action_id not in completed:
                # Incomplete operation detected -> execute authoritative reconciliation probe
                operation_id = intent["operation_id"]
                idempotency_key = intent["idempotency_key"]

                probe_status, probe_data = payment_service.probe_reconciliation(
                    operation_id=operation_id,
                    idempotency_key=idempotency_key
                )

                if probe_status == 200 and probe_data.get("status") == "COMMITTED":
                    resolved_disp = DISPOSITION_CONFIRMED
                    downstream_commits = probe_data.get("commit_count", 1)
                elif probe_status == 404:
                    resolved_disp = DISPOSITION_REFUTED
                    downstream_commits = 0
                else:
                    resolved_disp = DISPOSITION_PRESERVED_UNCERTAINTY
                    downstream_commits = probe_data.get("commit_count", 0)

                resolution = {
                    "action_id": action_id,
                    "operation_id": operation_id,
                    "status": "RECOVERED",
                    "disposition": resolved_disp,
                    "downstream_commit_count": downstream_commits,
                    "reconciled_at": datetime.now(timezone.utc).isoformat()
                }
                recovery_resolutions.append(resolution)

                # Persist recovery completion
                self.journal.append({
                    "event_type": "LIFECYCLE_COMPLETED",
                    "action_id": action_id,
                    "operation_id": operation_id,
                    "disposition": resolved_disp,
                    "retry_safe": False,
                    "downstream_commit_count": downstream_commits,
                    "recovered": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

        return recovery_resolutions


# ------------------------------------------------------------------------------
# Standalone Offline Verifier
# ------------------------------------------------------------------------------
class FinancialReceiptOfflineVerifier:
    """
    Independent zero-egress offline verifier.
    Enforces byte-for-byte RFC 8785 JCS verification and strict Ed25519 signature validation.
    """
    @staticmethod
    def verify_receipt(receipt: FinancialContinuityReceipt) -> Tuple[bool, Optional[str]]:
        try:
            pub_key = serialization.load_pem_public_key(receipt.public_key_pem.encode("utf-8"))
            if not isinstance(pub_key, ed25519.Ed25519PublicKey):
                return False, "INVALID_KEY_TYPE: Expected Ed25519 public key."

            # Reconstruct exact unsigned canonical bytes
            unsigned_dict = receipt.to_unsigned_dict()
            canonical_bytes = encode_jcs(unsigned_dict)

            # Re-verify Ed25519 digital signature directly over canonical receipt bytes
            signature_bytes = bytes.fromhex(receipt.signature_hex)
            pub_key.verify(signature_bytes, canonical_bytes)
            return True, None
        except Exception as e:
            return False, f"VERIFICATION_FAILED: {str(e)}"
