#!/usr/bin/env python3
"""
Beachhead Enterprise MCP Action Firewall & Control Plane (src/mcp_action_firewall.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model as a default-deny execution control plane
intercepting Agent-to-MCP tool calls:
  1. AEIBReceiptLedger: Durable SQLite-WAL append-only cryptographic receipt ledger
     chained by prev_receipt_caid and signed with an Ed25519 operator key over RFC 8785 JCS.
  2. EffectReconciler: Timeout-is-unknown indeterminate latch blocking blind retries
     until deterministic provider probe reconciliation.
  3. ResearchContextLedger: Content-addressed artifact, line-delta, and decision cache
     eliminating duplicate artifact ingestion.
  4. MCPActionFirewall: Default-deny sidecar integrating signed MCP tool manifests,
     CryptoDelegationGraph, TemporalAuthorityGuard terminal denial latching,
     EffectReconciler, human step-up warrant verification, and AEIBReceiptLedger persistence.
  5. compute_accountable_action_coverage_bps: Enterprise CISO metric with exact integer
     basis-point calculation and conservative Wilson 95% confidence intervals.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.crypto_delegation_graph import (
    CryptoDelegationGraph,
    DelegationToken,
    ScopeBoundary,
)
from src.jcs_canonicalizer import encode_jcs
from src.temporal_authority_guard import (
    IntentScope,
    TemporalAuthorityGuard,
    TemporalIntentEnvelope,
    sha256_caid,
)
from src.wilson_bps_interval import compute_wilson_95_bps

# Alias exported for callers referencing SignedIntent alongside TemporalIntentEnvelope
SignedIntent = TemporalIntentEnvelope


@dataclasses.dataclass(frozen=True)
class ActionExecutionReceipt:
    """Cryptographically chained and signed execution receipt persisted in SQLite-WAL."""

    seq_index: int
    prev_receipt_caid: str
    act_caid: str
    actor_spiffe_id: str
    tool_id: str
    egress_host: str
    decision: str
    status_code: str
    evaluated_at_epoch_sec: int
    receipt_caid: str
    signature_hex: str

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "act_caid": self.act_caid,
            "actor_spiffe_id": self.actor_spiffe_id,
            "decision": self.decision,
            "egress_host": self.egress_host,
            "evaluated_at_epoch_sec": self.evaluated_at_epoch_sec,
            "prev_receipt_caid": self.prev_receipt_caid,
            "seq_index": self.seq_index,
            "status_code": self.status_code,
            "tool_id": self.tool_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        data = self.canonical_payload()
        data["receipt_caid"] = self.receipt_caid
        data["signature_hex"] = self.signature_hex
        return data


class AEIBReceiptLedger:
    """Durable SQLite-WAL append-only action receipt ledger with full hash-chain replay."""

    def __init__(
        self,
        db_path: Union[str, Path],
        operator_private_key: ed25519.Ed25519PrivateKey,
    ) -> None:
        self.db_path = Path(db_path)
        self._operator_private_key = operator_private_key
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=FULL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_receipts (
                seq_index INTEGER PRIMARY KEY,
                prev_receipt_caid TEXT NOT NULL,
                act_caid TEXT NOT NULL,
                actor_spiffe_id TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                egress_host TEXT NOT NULL,
                decision TEXT NOT NULL,
                status_code TEXT NOT NULL,
                evaluated_at_epoch_sec INTEGER NOT NULL,
                receipt_caid TEXT NOT NULL,
                signature_hex TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def append_receipt(
        self,
        act_caid: str,
        actor_spiffe_id: str,
        tool_id: str,
        egress_host: str,
        decision: str,
        status_code: str,
        evaluated_at_epoch_sec: int,
    ) -> ActionExecutionReceipt:
        cursor = self._conn.execute(
            "SELECT seq_index, receipt_caid FROM action_receipts ORDER BY seq_index DESC LIMIT 1"
        )
        last_row = cursor.fetchone()
        if last_row is None:
            seq_index = 0
            prev_receipt_caid = "GENESIS"
        else:
            seq_index = int(last_row[0]) + 1
            prev_receipt_caid = str(last_row[1])

        payload: Dict[str, Any] = {
            "act_caid": act_caid,
            "actor_spiffe_id": actor_spiffe_id,
            "decision": decision,
            "egress_host": egress_host,
            "evaluated_at_epoch_sec": evaluated_at_epoch_sec,
            "prev_receipt_caid": prev_receipt_caid,
            "seq_index": seq_index,
            "status_code": status_code,
            "tool_id": tool_id,
        }
        canonical_bytes = encode_jcs(payload)
        receipt_caid = sha256_caid(canonical_bytes)
        signature_hex = self._operator_private_key.sign(canonical_bytes).hex()

        self._conn.execute(
            """
            INSERT INTO action_receipts (
                seq_index, prev_receipt_caid, act_caid, actor_spiffe_id,
                tool_id, egress_host, decision, status_code,
                evaluated_at_epoch_sec, receipt_caid, signature_hex
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                seq_index,
                prev_receipt_caid,
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                decision,
                status_code,
                evaluated_at_epoch_sec,
                receipt_caid,
                signature_hex,
            ),
        )
        self._conn.commit()

        return ActionExecutionReceipt(
            seq_index=seq_index,
            prev_receipt_caid=prev_receipt_caid,
            act_caid=act_caid,
            actor_spiffe_id=actor_spiffe_id,
            tool_id=tool_id,
            egress_host=egress_host,
            decision=decision,
            status_code=status_code,
            evaluated_at_epoch_sec=evaluated_at_epoch_sec,
            receipt_caid=receipt_caid,
            signature_hex=signature_hex,
        )

    def verify_ledger_and_replay(
        self, operator_public_key: ed25519.Ed25519PublicKey
    ) -> Tuple[bool, str, int]:
        cursor = self._conn.execute(
            """
            SELECT seq_index, prev_receipt_caid, act_caid, actor_spiffe_id,
                   tool_id, egress_host, decision, status_code,
                   evaluated_at_epoch_sec, receipt_caid, signature_hex
            FROM action_receipts
            ORDER BY seq_index ASC
            """
        )
        rows = cursor.fetchall()
        expected_prev_caid = "GENESIS"

        for idx, row in enumerate(rows):
            (
                seq_index,
                prev_receipt_caid,
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                decision,
                status_code,
                evaluated_at_epoch_sec,
                receipt_caid,
                signature_hex,
            ) = row

            if seq_index != idx:
                return False, f"TAMPER_SEQ_INDEX_GAP:{seq_index}!={idx}", idx

            if prev_receipt_caid != expected_prev_caid:
                return (
                    False,
                    f"TAMPER_PREV_CAID_CHAIN_BREAK:{prev_receipt_caid}!={expected_prev_caid}",
                    idx,
                )

            payload: Dict[str, Any] = {
                "act_caid": act_caid,
                "actor_spiffe_id": actor_spiffe_id,
                "decision": decision,
                "egress_host": egress_host,
                "evaluated_at_epoch_sec": evaluated_at_epoch_sec,
                "prev_receipt_caid": prev_receipt_caid,
                "seq_index": seq_index,
                "status_code": status_code,
                "tool_id": tool_id,
            }
            canonical_bytes = encode_jcs(payload)
            recomputed_caid = sha256_caid(canonical_bytes)
            if receipt_caid != recomputed_caid:
                return (
                    False,
                    f"TAMPER_RECEIPT_CAID_MISMATCH:{receipt_caid}!={recomputed_caid}",
                    idx,
                )

            try:
                operator_public_key.verify(
                    bytes.fromhex(signature_hex), canonical_bytes
                )
            except (ValueError, InvalidSignature):
                return False, "TAMPER_INVALID_OPERATOR_SIGNATURE", idx

            expected_prev_caid = receipt_caid

        return True, "LEDGER_REPLAY_VERIFIED", len(rows)

    def close(self) -> None:
        self._conn.close()


class EffectReconciler:
    """Timeout-is-unknown indeterminate latch and provider probe reconciler."""

    def __init__(self) -> None:
        self._states: Dict[str, str] = {}
        self._metadata: Dict[str, Tuple[str, str]] = {}

    def get_effect_state(self, effect_idempotency_caid: str) -> str:
        return self._states.get(effect_idempotency_caid, "NONE")

    def record_timeout_or_indeterminate(
        self,
        effect_idempotency_caid: str,
        tool_id: str,
        actor_spiffe_id: str,
    ) -> str:
        self._states[effect_idempotency_caid] = "EFFECT_INDETERMINATE"
        self._metadata[effect_idempotency_caid] = (tool_id, actor_spiffe_id)
        return "EFFECT_INDETERMINATE"

    def record_committed(
        self,
        effect_idempotency_caid: str,
        tool_id: str,
        actor_spiffe_id: str,
    ) -> str:
        self._states[effect_idempotency_caid] = "CONFIRMED_COMMITTED"
        self._metadata[effect_idempotency_caid] = (tool_id, actor_spiffe_id)
        return "CONFIRMED_COMMITTED"

    def can_dispatch(self, effect_idempotency_caid: str) -> Tuple[bool, str]:
        state = self._states.get(effect_idempotency_caid, "NONE")
        if state == "EFFECT_INDETERMINATE":
            return False, "DENY_INDETERMINATE_EFFECT_PENDING_RECONCILIATION"
        if state == "CONFIRMED_COMMITTED":
            return False, "DENY_ALREADY_COMMITTED_IDEMPOTENT_REPLAY"
        return True, "ALLOW_FRESH_OR_ABORTED_RETRY"

    def reconcile_with_provider_probe(
        self, effect_idempotency_caid: str, provider_status: str
    ) -> str:
        if provider_status not in ("CONFIRMED_COMMITTED", "CONFIRMED_ABORTED"):
            raise ValueError(f"ERR_INVALID_PROVIDER_PROBE_STATUS:{provider_status}")
        self._states[effect_idempotency_caid] = provider_status
        return provider_status


@dataclasses.dataclass(frozen=True)
class ResearchArtifactRecord:
    """Content-addressed research context artifact entry."""

    artifact_caid: str
    raw_text: str
    tags: Tuple[str, ...]
    parent_artifact_caid: str
    cached_decision: str
    line_delta_count: int


class ResearchContextLedger:
    """Content-addressed artifact, line-delta, and decision cache."""

    def __init__(self) -> None:
        self._artifacts: Dict[str, ResearchArtifactRecord] = {}

    def get_artifact(self, artifact_caid: str) -> Optional[ResearchArtifactRecord]:
        return self._artifacts.get(artifact_caid)

    def ingest_artifact(
        self,
        raw_text: str,
        tags: Sequence[str],
        parent_artifact_caid: str = "NONE",
        cached_decision: str = "NONE",
    ) -> Dict[str, Any]:
        artifact_caid = sha256_caid(raw_text)
        existing = self._artifacts.get(artifact_caid)
        if existing is not None:
            return {
                "status": "DUPLICATE_ARTIFACT_SKIPPED",
                "artifact_caid": artifact_caid,
                "cached_decision": existing.cached_decision,
            }

        curr_lines = raw_text.splitlines()
        parent_rec = self._artifacts.get(parent_artifact_caid)
        if parent_artifact_caid != "NONE" and parent_rec is not None:
            parent_lines = set(parent_rec.raw_text.splitlines())
            delta = sum(1 for line in curr_lines if line not in parent_lines)
        else:
            delta = len(curr_lines)

        record = ResearchArtifactRecord(
            artifact_caid=artifact_caid,
            raw_text=raw_text,
            tags=tuple(tags),
            parent_artifact_caid=parent_artifact_caid,
            cached_decision=cached_decision,
            line_delta_count=delta,
        )
        self._artifacts[artifact_caid] = record
        return {
            "status": "INGESTED_NEW_ARTIFACT",
            "artifact_caid": artifact_caid,
            "line_delta_count": delta,
        }


@dataclasses.dataclass(frozen=True)
class SignedToolManifest:
    """Cryptographically verified MCP tool manifest."""

    tool_id: str
    allowed_hosts: Tuple[str, ...]
    irreversible: bool
    max_taint_bps: int
    signature_hex: str
    manifest_caid: str


@dataclasses.dataclass(frozen=True)
class FirewallEvaluationResult:
    """Outcome of MCPActionFirewall evaluation with durable receipt."""

    decision: str
    status_code: str
    act_caid: str
    receipt: ActionExecutionReceipt


class MCPActionFirewall:
    """Default-deny sidecar intercepting Agent-to-MCP tool calls."""

    def __init__(
        self,
        receipt_ledger: AEIBReceiptLedger,
        delegation_graph: CryptoDelegationGraph,
        temporal_guard: TemporalAuthorityGuard,
        effect_reconciler: EffectReconciler,
        human_approver_public_key: ed25519.Ed25519PublicKey,
    ) -> None:
        self.receipt_ledger = receipt_ledger
        self.delegation_graph = delegation_graph
        self.temporal_guard = temporal_guard
        self.effect_reconciler = effect_reconciler
        self.human_approver_public_key = human_approver_public_key
        self._tool_manifests: Dict[str, SignedToolManifest] = {}
        self._terminal_denied_intents: Dict[str, str] = {}

    @staticmethod
    def sign_tool_manifest_payload(
        tool_id: str,
        allowed_hosts: Sequence[str],
        irreversible: bool,
        max_taint_bps: int,
        publisher_private_key: ed25519.Ed25519PrivateKey,
    ) -> str:
        normalized_hosts = tuple(sorted(set(allowed_hosts)))
        payload: Dict[str, Any] = {
            "allowed_hosts": list(normalized_hosts),
            "irreversible": irreversible,
            "max_taint_bps": max_taint_bps,
            "tool_id": tool_id,
        }
        return publisher_private_key.sign(encode_jcs(payload)).hex()

    @staticmethod
    def sign_human_step_up_warrant(
        act_caid: str,
        subject_spiffe_id: str,
        tool_id: str,
        human_private_key: ed25519.Ed25519PrivateKey,
    ) -> str:
        warrant_payload: Dict[str, Any] = {
            "act_caid": act_caid,
            "subject_spiffe_id": subject_spiffe_id,
            "tool_id": tool_id,
        }
        return human_private_key.sign(encode_jcs(warrant_payload)).hex()

    @staticmethod
    def compute_act_caid(
        actor_spiffe_id: str,
        tool_id: str,
        egress_host: str,
        amount_minor: int,
        blast_radius_bps: int,
        context_taint_bps: int,
        intent_caid: str,
        leaf_token_caid: str,
        effect_idempotency_caid: str,
    ) -> str:
        payload: Dict[str, Any] = {
            "actor_spiffe_id": actor_spiffe_id,
            "amount_minor": amount_minor,
            "blast_radius_bps": blast_radius_bps,
            "context_taint_bps": context_taint_bps,
            "effect_idempotency_caid": effect_idempotency_caid,
            "egress_host": egress_host,
            "intent_caid": intent_caid,
            "leaf_token_caid": leaf_token_caid,
            "tool_id": tool_id,
        }
        return sha256_caid(payload)

    def register_signed_tool_manifest(
        self,
        tool_id: str,
        allowed_hosts: Sequence[str],
        irreversible: bool,
        max_taint_bps: int,
        publisher_public_key: ed25519.Ed25519PublicKey,
        signature_hex: str,
    ) -> SignedToolManifest:
        if max_taint_bps < 0 or max_taint_bps > 10000:
            raise ValueError(f"ERR_INVALID_MAX_TAINT_BPS:{max_taint_bps}")

        normalized_hosts = tuple(sorted(set(allowed_hosts)))
        payload: Dict[str, Any] = {
            "allowed_hosts": list(normalized_hosts),
            "irreversible": irreversible,
            "max_taint_bps": max_taint_bps,
            "tool_id": tool_id,
        }
        canonical_bytes = encode_jcs(payload)
        try:
            publisher_public_key.verify(bytes.fromhex(signature_hex), canonical_bytes)
        except (ValueError, InvalidSignature):
            raise ValueError("HALT_INVALID_TOOL_MANIFEST_SIGNATURE")

        manifest = SignedToolManifest(
            tool_id=tool_id,
            allowed_hosts=normalized_hosts,
            irreversible=irreversible,
            max_taint_bps=max_taint_bps,
            signature_hex=signature_hex,
            manifest_caid=sha256_caid(canonical_bytes),
        )
        self._tool_manifests[tool_id] = manifest
        return manifest

    def evaluate_mcp_tool_call(
        self,
        actor_spiffe_id: str,
        tool_id: str,
        egress_host: str,
        amount_minor: int,
        blast_radius_bps: int,
        context_taint_bps: int,
        intent_caid: str,
        leaf_token_caid: str,
        effect_idempotency_caid: str,
        current_time: int,
        human_approval_signature_hex: str = "",
        payment_402_required: bool = False,
        live_preconditions: Optional[Mapping[str, bool]] = None,
    ) -> FirewallEvaluationResult:
        act_caid = self.compute_act_caid(
            actor_spiffe_id=actor_spiffe_id,
            tool_id=tool_id,
            egress_host=egress_host,
            amount_minor=amount_minor,
            blast_radius_bps=blast_radius_bps,
            context_taint_bps=context_taint_bps,
            intent_caid=intent_caid,
            leaf_token_caid=leaf_token_caid,
            effect_idempotency_caid=effect_idempotency_caid,
        )

        # 1. Terminal Denial Latch Check
        if (
            intent_caid in self._terminal_denied_intents
            or self.temporal_guard.get_intent_state(intent_caid) == "DENIED_TERMINAL"
        ):
            return self._record(
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                "DENY",
                "DENY_TERMINAL_PRIOR_INTENT_LATCHED",
                current_time,
            )

        if payment_402_required:
            self._terminal_denied_intents[intent_caid] = "DENY_402_PAYMENT_REQUIRED_TERMINAL"
            return self._record(
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                "DENY",
                "DENY_402_PAYMENT_REQUIRED_TERMINAL",
                current_time,
            )

        if self.temporal_guard.get_intent_state(intent_caid) != "UNREGISTERED":
            t_verdict = self.temporal_guard.evaluate_temporal_dispatch(
                intent_caid=intent_caid,
                current_epoch_sec=current_time,
                live_preconditions=live_preconditions or {},
                requested_host=egress_host,
                requested_tool=tool_id,
                requested_amount_minor=amount_minor,
            )
            if not t_verdict.authorized:
                if t_verdict.state == "DENIED_TERMINAL":
                    self._terminal_denied_intents[intent_caid] = t_verdict.status_code
                return self._record(
                    act_caid,
                    actor_spiffe_id,
                    tool_id,
                    egress_host,
                    "DENY",
                    t_verdict.status_code,
                    current_time,
                )

        # 2. Default-Deny Signed Tool Manifest Check
        manifest = self._tool_manifests.get(tool_id)
        if manifest is None:
            status = f"DENY_UNREGISTERED_MCP_TOOL:{tool_id}"
            self._terminal_denied_intents[intent_caid] = status
            return self._record(
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                "DENY",
                status,
                current_time,
            )

        if egress_host not in manifest.allowed_hosts:
            status = f"DENY_MANIFEST_HOST_FORBIDDEN:{egress_host}"
            self._terminal_denied_intents[intent_caid] = status
            return self._record(
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                "DENY",
                status,
                current_time,
            )

        # 3. Cryptographic Delegation Graph Check
        auth_verdict = self.delegation_graph.evaluate_action(
            actor_spiffe_id=actor_spiffe_id,
            leaf_token_caid=leaf_token_caid,
            action_host=egress_host,
            action_tool=tool_id,
            amount_minor=amount_minor,
            current_time=current_time,
            blast_radius_bps=blast_radius_bps,
        )
        if not auth_verdict.authorized:
            self._terminal_denied_intents[intent_caid] = auth_verdict.reason_code
            return self._record(
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                "DENY",
                auth_verdict.reason_code,
                current_time,
            )

        # 4. EffectReconciler Indeterminate / Duplicate Replay Check
        can_run, reconcile_reason = self.effect_reconciler.can_dispatch(
            effect_idempotency_caid
        )
        if not can_run:
            return self._record(
                act_caid,
                actor_spiffe_id,
                tool_id,
                egress_host,
                "DENY",
                reconcile_reason,
                current_time,
            )

        # 5. Human Step-Up Warrant Verification
        if manifest.irreversible or context_taint_bps > manifest.max_taint_bps:
            if not self._verify_human_warrant(
                act_caid, actor_spiffe_id, tool_id, human_approval_signature_hex
            ):
                return self._record(
                    act_caid,
                    actor_spiffe_id,
                    tool_id,
                    egress_host,
                    "ESCALATE",
                    "ESCALATE_HUMAN_APPROVAL_REQUIRED",
                    current_time,
                )

        # 6. Authorize & Record Committed Effect
        self.effect_reconciler.record_committed(
            effect_idempotency_caid, tool_id, actor_spiffe_id
        )
        return self._record(
            act_caid,
            actor_spiffe_id,
            tool_id,
            egress_host,
            "ALLOW",
            "ALLOW_ACTION_AUTHORIZED",
            current_time,
        )

    def _verify_human_warrant(
        self,
        act_caid: str,
        subject_spiffe_id: str,
        tool_id: str,
        signature_hex: str,
    ) -> bool:
        if not signature_hex:
            return False
        warrant_payload: Dict[str, Any] = {
            "act_caid": act_caid,
            "subject_spiffe_id": subject_spiffe_id,
            "tool_id": tool_id,
        }
        try:
            self.human_approver_public_key.verify(
                bytes.fromhex(signature_hex), encode_jcs(warrant_payload)
            )
        except (ValueError, InvalidSignature):
            return False
        return True

    def _record(
        self,
        act_caid: str,
        actor_spiffe_id: str,
        tool_id: str,
        egress_host: str,
        decision: str,
        status_code: str,
        evaluated_at_epoch_sec: int,
    ) -> FirewallEvaluationResult:
        receipt = self.receipt_ledger.append_receipt(
            act_caid=act_caid,
            actor_spiffe_id=actor_spiffe_id,
            tool_id=tool_id,
            egress_host=egress_host,
            decision=decision,
            status_code=status_code,
            evaluated_at_epoch_sec=evaluated_at_epoch_sec,
        )
        return FirewallEvaluationResult(
            decision=decision,
            status_code=status_code,
            act_caid=act_caid,
            receipt=receipt,
        )


@dataclasses.dataclass(frozen=True)
class ActionAuditSample:
    """Single action audit sample for the Enterprise CISO Accountable Action Coverage metric."""

    action_id: str
    identity_bound: bool
    policy_evaluated: bool
    receipt_recorded: bool
    replay_verified: bool
    reconcilable: bool

    @property
    def is_accountable(self) -> bool:
        return bool(
            self.identity_bound
            and self.policy_evaluated
            and self.receipt_recorded
            and self.replay_verified
            and self.reconcilable
        )


@dataclasses.dataclass(frozen=True)
class AccountableActionCoverageReport:
    """Accountable Action Coverage report with integer basis points and Wilson 95% CI."""

    accountable_count: int
    total_count: int
    coverage_bps: int
    wilson_low_bps: int
    wilson_high_bps: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "accountable_count": self.accountable_count,
            "coverage_bps": self.coverage_bps,
            "total_count": self.total_count,
            "wilson_high_bps": self.wilson_high_bps,
            "wilson_low_bps": self.wilson_low_bps,
        }

    def __getitem__(self, key: str) -> int:
        return self.to_dict()[key]


def compute_accountable_action_coverage_bps(
    samples: Sequence[ActionAuditSample],
) -> AccountableActionCoverageReport:
    """
    Compute the Enterprise CISO Accountable Action Coverage metric in integer basis points.
    An action is accountable iff all 5 predicates (identity_bound, policy_evaluated,
    receipt_recorded, replay_verified, reconcilable) are True.
    """
    total_count = len(samples)
    if total_count == 0:
        return AccountableActionCoverageReport(
            accountable_count=0,
            total_count=0,
            coverage_bps=0,
            wilson_low_bps=0,
            wilson_high_bps=0,
        )

    accountable_count = sum(1 for sample in samples if sample.is_accountable)
    coverage_bps = (accountable_count * 10000) // total_count
    wilson_low_bps, wilson_high_bps = compute_wilson_95_bps(
        accountable_count, total_count
    )
    return AccountableActionCoverageReport(
        accountable_count=accountable_count,
        total_count=total_count,
        coverage_bps=coverage_bps,
        wilson_low_bps=wilson_low_bps,
        wilson_high_bps=wilson_high_bps,
    )
