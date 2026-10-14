"""
v1.1-roadmap/tier1_durable_executor.py — Tier 1 Core Delivery Candidate.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Implements the Tier 1 Core Delivery Contract:
  1. CandidateAction validation (authority, target, policy epoch, manifest, CAID digest).
  2. Durable DISPATCH_INTENT write-ahead journal with fsync durability acknowledgement.
  3. Persistent, restart-safe single-use authority consumption.
  4. Governed dispatch through execution hook.
  5. Deterministic outcome classification.
  6. Bounded operation-specific reconciliation on ambiguous transport.
  7. Persist resolution and emit RFC 8785 JCS + Ed25519 receipt.

Operates under the stated model: Prohibits in-memory-only ticket assumptions.
Enforces crash-safe recovery, restart-safe ticket consumption, and conservative uncertainty handling.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


class GovernanceHaltError(RuntimeError):
    """Raised when an AEIB wire gate or dispatch precondition fails."""


@dataclass(frozen=True)
class DispatchAuthorityTicket:
    """Cryptographically signed single-use dispatch authority ticket."""

    decision_id: str
    operation_id: str
    principal_id: str
    target_identity: str
    action_digest: str  # "sha256:<64-hex>"
    policy_epoch: int
    manifest_digest: str  # "sha256:<64-hex>"
    expires_at: int
    single_use: bool
    signature_hex: str

    def to_canonical_statement(self) -> Dict[str, Any]:
        return {
            "actionDigest": self.action_digest,
            "decisionId": self.decision_id,
            "expiresAt": self.expires_at,
            "manifestDigest": self.manifest_digest,
            "operationId": self.operation_id,
            "policyEpoch": self.policy_epoch,
            "principalId": self.principal_id,
            "singleUse": self.single_use,
            "targetIdentity": self.target_identity,
        }


class PersistentAuthorityTicketStore:
    """Disk-backed, restart-safe single-use ticket consumption store with fsync durability."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._consumed_decisions: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            if record.get("event") == "TICKET_CONSUMED":
                                self._consumed_decisions.add(record["decision_id"])
                        except json.JSONDecodeError:
                            continue

    def is_consumed(self, decision_id: str) -> bool:
        with self._lock:
            return decision_id in self._consumed_decisions

    def consume_authority(self, decision_id: str, operation_id: str, timestamp_epoch: int) -> bool:
        """Atomically consumes single-use authority with durable write and fsync.

        Returns True if authority was successfully consumed, False if already consumed.
        """
        with self._lock:
            if decision_id in self._consumed_decisions:
                return False

            record = {
                "event": "TICKET_CONSUMED",
                "decision_id": decision_id,
                "operation_id": operation_id,
                "consumed_at": timestamp_epoch,
            }
            line = json.dumps(record, sort_keys=True) + "\n"

            # Durable write with fsync
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            self._consumed_decisions.add(decision_id)
            return True


class DurableDispatchJournal:
    """Append-only write-ahead dispatch intent journal with fsync durability acknowledgement."""

    def __init__(self, journal_path: Path) -> None:
        self.journal_path = journal_path
        self._lock = threading.Lock()

    def persist_intent(
        self,
        *,
        operation_id: str,
        decision_id: str,
        action_caid: str,
        target_identity: str,
        timestamp_epoch: int,
    ) -> None:
        """Persists DISPATCH_INTENT and forces durability acknowledgement via fsync."""
        record = {
            "event": "DISPATCH_INTENT",
            "operation_id": operation_id,
            "decision_id": decision_id,
            "action_caid": action_caid,
            "target_identity": target_identity,
            "timestamp": timestamp_epoch,
            "status": "INTENT_RECORDED",
        }
        self._append_sync(record)

    def mark_dispatch_started(self, operation_id: str, timestamp_epoch: int) -> None:
        record = {
            "event": "DISPATCH_STARTED",
            "operation_id": operation_id,
            "timestamp": timestamp_epoch,
            "status": "DISPATCH_IN_FLIGHT",
        }
        self._append_sync(record)

    def persist_resolution(
        self,
        *,
        operation_id: str,
        disposition: str,
        retry_safe: bool,
        evidence_digest: str,
        timestamp_epoch: int,
    ) -> None:
        record = {
            "event": "DISPATCH_RESOLVED",
            "operation_id": operation_id,
            "disposition": disposition,
            "retry_safe": retry_safe,
            "evidence_digest": evidence_digest,
            "timestamp": timestamp_epoch,
            "status": "RESOLVED",
        }
        self._append_sync(record)

    def _append_sync(self, record: Dict[str, Any]) -> None:
        with self._lock:
            line = json.dumps(record, sort_keys=True) + "\n"
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

    def read_all_events(self) -> List[Dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        events = []
        with open(self.journal_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    def scan_recovery_state(self, operation_id: str) -> str:
        """Analyzes journal events to determine recovery posture for an operation."""
        events = [ev for ev in self.read_all_events() if ev.get("operation_id") == operation_id]
        if not events:
            return "NOT_RECORDED"

        event_types = {ev.get("event") for ev in events}
        if "DISPATCH_RESOLVED" in event_types:
            return "RESOLVED"
        if "DISPATCH_STARTED" in event_types:
            # Crashed during dispatch: outcome unknown, cannot infer target did nothing!
            return "REQUIRES_RECONCILIATION"
        if "DISPATCH_INTENT" in event_types:
            # Crashed after intent, before wire dispatch: conservative abort
            return "ABORTED_PRE_DISPATCH"
        return "UNKNOWN"


class Tier1DurableDispatchExecutor:
    """Executes the Tier 1 Core Delivery Contract with durable intent and persistent tickets."""

    def __init__(
        self,
        *,
        authority_public_key: Ed25519PublicKey,
        ledger_signing_key: Ed25519PrivateKey,
        ticket_store: PersistentAuthorityTicketStore,
        journal: DurableDispatchJournal,
        active_policy_epoch: int,
        pinned_manifest_digest: str,
        probe_reconciler: Optional[Callable[[str, str], Optional[str]]] = None,
    ) -> None:
        self.authority_public_key = authority_public_key
        self.ledger_signing_key = ledger_signing_key
        self.ticket_store = ticket_store
        self.journal = journal
        self.active_policy_epoch = active_policy_epoch
        self.pinned_manifest_digest = pinned_manifest_digest
        self.probe_reconciler = probe_reconciler

    def execute_governed_action(
        self,
        *,
        ticket: DispatchAuthorityTicket,
        candidate_action_payload: Dict[str, Any],
        target_identity: str,
        current_timestamp: int,
        wire_dispatcher: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Runs the 8-step Tier 1 dispatch pipeline."""
        # Step 1: Validate Authority, Target, Policy Epoch, Manifest, Action Digest (CAID)
        canonical_payload_bytes = encode_jcs(candidate_action_payload)
        computed_caid = f"sha256:{hashlib.sha256(canonical_payload_bytes).hexdigest()}"

        if ticket.action_digest != computed_caid:
            raise GovernanceHaltError(
                f"ACTION_DIGEST_MISMATCH: ticket {ticket.action_digest} != computed {computed_caid}"
            )
        if ticket.target_identity != target_identity:
            raise GovernanceHaltError(
                f"TARGET_MISMATCH: ticket target '{ticket.target_identity}' != actual '{target_identity}'"
            )
        if ticket.policy_epoch != self.active_policy_epoch:
            raise GovernanceHaltError(
                f"POLICY_EPOCH_STALE: ticket epoch {ticket.policy_epoch} != active {self.active_policy_epoch}"
            )
        if ticket.manifest_digest != self.pinned_manifest_digest:
            raise GovernanceHaltError(
                f"MANIFEST_DRIFT: ticket manifest {ticket.manifest_digest} != active {self.pinned_manifest_digest}"
            )
        if ticket.expires_at < current_timestamp:
            raise GovernanceHaltError(
                f"TICKET_EXPIRED: ticket expired at {ticket.expires_at} (current: {current_timestamp})"
            )

        # Verify Ed25519 signature of authority ticket
        statement_bytes = encode_jcs(ticket.to_canonical_statement())
        try:
            self.authority_public_key.verify(bytes.fromhex(ticket.signature_hex), statement_bytes)
        except InvalidSignature as e:
            raise GovernanceHaltError("AUTHORITY_SIGNATURE_INVALID: ticket signature rejected") from e

        # Check if already consumed in persistent store before attempting write
        if self.ticket_store.is_consumed(ticket.decision_id):
            raise GovernanceHaltError(
                f"AUTHORITY_ALREADY_CONSUMED: decision_id '{ticket.decision_id}' previously burned"
            )

        # Step 2: Persist DISPATCH_INTENT with fsync durability acknowledgement
        try:
            self.journal.persist_intent(
                operation_id=ticket.operation_id,
                decision_id=ticket.decision_id,
                action_caid=computed_caid,
                target_identity=target_identity,
                timestamp_epoch=current_timestamp,
            )
        except Exception as e:
            # If intent persistence fails -> NO governed dispatch!
            raise GovernanceHaltError(f"INTENT_PERSISTENCE_FAILED: durability write failed: {e}") from e

        # Step 3: Consume single-use dispatch authority
        consumed = self.ticket_store.consume_authority(
            decision_id=ticket.decision_id,
            operation_id=ticket.operation_id,
            timestamp_epoch=current_timestamp,
        )
        if not consumed:
            raise GovernanceHaltError(
                f"CONCURRENT_CONSUMPTION_ABORT: decision_id '{ticket.decision_id}' was consumed concurrently"
            )

        # Step 4: Dispatch through AEIB-governed executor
        self.journal.mark_dispatch_started(ticket.operation_id, current_timestamp)

        raw_outcome: Dict[str, Any]
        try:
            raw_outcome = wire_dispatcher(candidate_action_payload)
        except Exception as wire_err:
            # Transport exception (socket drop, 504, timeout) -> Ambiguous transport outcome
            raw_outcome = {
                "http_status": 504,
                "error": str(wire_err),
                "transport_ambiguity": True,
            }

        # Step 5: Classify outcome
        http_status = raw_outcome.get("http_status", 500)
        transport_ambiguous = raw_outcome.get("transport_ambiguity", False) or http_status in (504, 502, 503)

        final_disposition: str
        retry_safe: bool

        if not transport_ambiguous and http_status == 200:
            final_disposition = "CONFIRMED"
            retry_safe = True
        elif not transport_ambiguous and http_status in (400, 401, 403, 422):
            final_disposition = "REFUSED"
            retry_safe = False
        else:
            # Ambiguous transport outcome: latch to EFFECT_INDETERMINATE with retry_safe: false
            final_disposition = "EFFECT_INDETERMINATE"
            retry_safe = False

            # Step 6: Reconcile ambiguous mutation with bounded operation-specific evidence (ProbeBudget: 1)
            if self.probe_reconciler is not None:
                try:
                    reconciled_state = self.probe_reconciler(ticket.operation_id, computed_caid)
                    if reconciled_state == "CONFIRMED":
                        final_disposition = "CONFIRMED"
                        retry_safe = True
                    elif reconciled_state in ("NOT_FOUND", "ROLLED_BACK"):
                        final_disposition = "REFUTED"
                        retry_safe = False
                except Exception:
                    # Probe error, timeout, or exhaustion: uncertainty strictly preserved
                    pass

        # Step 7: Persist resolution to durable journal
        evidence_digest = f"sha256:{hashlib.sha256(encode_jcs(raw_outcome)).hexdigest()}"
        self.journal.persist_resolution(
            operation_id=ticket.operation_id,
            disposition=final_disposition,
            retry_safe=retry_safe,
            evidence_digest=evidence_digest,
            timestamp_epoch=current_timestamp,
        )

        # Step 8: Emit RFC 8785 canonical signed receipt
        receipt_statement = {
            "actionDigest": computed_caid,
            "decisionId": ticket.decision_id,
            "disposition": final_disposition,
            "operationId": ticket.operation_id,
            "policyEpoch": self.active_policy_epoch,
            "retrySafe": retry_safe,
            "targetIdentity": target_identity,
            "timestamp": current_timestamp,
        }
        receipt_bytes = encode_jcs(receipt_statement)
        receipt_signature_hex = self.ledger_signing_key.sign(receipt_bytes).hex()

        return {
            "disposition": final_disposition,
            "operationId": ticket.operation_id,
            "receipt": receipt_statement,
            "receiptSignatureHex": receipt_signature_hex,
            "retrySafe": retry_safe,
            "status": "RESOLVED",
        }
