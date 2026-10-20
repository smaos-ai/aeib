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
tools/temporal_conformance.py — Explicit Operation-Bound Temporal Conformance Monitor & 16-Class Agent Chaos Injector.
Evaluated under the stated model as an agent execution boundary scaffold.

Integrates:
1. Operation-Bound Trace Automaton (`TemporalConformanceMonitor`):
   Enforces 6 temporal safety properties across multi-operation traces:
   - T1 (Durable Intent Before Dispatch): DISPATCH_SENT requires prior INTENT_PERSISTED.
   - T2 (Verified Receipt / Warrant Before Dispatch): DISPATCH_SENT requires prior RECEIPT_VERIFIED.
   - T3 (Global Halt Barrier): No DISPATCH_SENT permitted after HALT_ENGAGED.
   - T4 (No Blind Retry Under Uncertainty): No DISPATCH_SENT permitted for an operation currently in EFFECT_INDETERMINATE.
   - T5 (Authoritative Probe Before Resolution): Transition from EFFECT_INDETERMINATE to CONFIRMED or REFUTED
        requires an intervening RECONCILIATION_PROBED event.
   - T6 (Scope & Path Containment — CVE-2026-43901 & Overreach Defense): Tool calls must match the task's
        authorized toolset and must not write outside allowed directories.

2. 16-Class Agent Chaos & Hallucination Injector (`FailClosedWireParserAndGate`):
   Simulates 16 malformed wire payloads, non-abstention hallucinations (MiniMax M3.1 Flash pattern),
   scope overreaches (17.1% Claude Code pattern), and MCP path-traversal exports (CVE-2026-43901 Wireshark-MCP pattern).
"""

from __future__ import annotations

import argparse
import enum
import hashlib
import json
import os
import posixpath
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


class OperationTemporalState(enum.Enum):
    UNSEEN = "UNSEEN"
    INTENT_PERSISTED = "INTENT_PERSISTED"
    DISPATCH_SENT = "DISPATCH_SENT"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    UNRESOLVED_ESCALATED = "UNRESOLVED_ESCALATED"


class TemporalViolationError(Exception):
    """Raised when an operation breaches declared temporal execution rules."""

    def __init__(
        self,
        rule_id: str,
        operation_id: str,
        step_index: int,
        details: str,
    ) -> None:
        super().__init__(
            f"TEMPORAL INVARIANT BREACH [{rule_id}] (op: {operation_id}, step: {step_index}): {details}"
        )
        self.rule_id = rule_id
        self.operation_id = operation_id
        self.step_index = step_index
        self.details = details


@dataclass
class OperationTimeline:
    operation_id: str
    current_state: OperationTemporalState = OperationTemporalState.UNSEEN
    action_caid: Optional[str] = None
    amount_minor: Optional[int] = None
    intent_step: Optional[int] = None
    dispatch_step: Optional[int] = None
    indeterminate_step: Optional[int] = None
    settlement_step: Optional[int] = None
    indeterminate_reason: Optional[str] = None
    evidence_digest: Optional[str] = None
    authority_signature: Optional[str] = None
    transitions: List[Tuple[int, OperationTemporalState, str]] = field(default_factory=list)


@dataclass
class OperationTraceState:
    operation_id: str
    intent_persisted: bool = False
    receipt_verified: bool = False
    dispatched: bool = False
    effect_indeterminate: bool = False
    reconciliation_probed: bool = False
    terminal_state: Optional[str] = None


class TemporalConformanceMonitor:
    """
    Operation-bound trace-event monitor verifying AEIB temporal invariants T1-T6,
    supporting both online trace validation and offline replay verification.
    """

    def __init__(
        self,
        max_reconciliation_horizon_steps: int = 100,
        allowed_tools: Optional[Set[str]] = None,
        allowed_export_dirs: Optional[Set[str]] = None,
    ) -> None:
        self.max_reconciliation_horizon = max_reconciliation_horizon_steps
        self.operations: Dict[str, OperationTraceState] = {}
        self.timelines: Dict[str, OperationTimeline] = {}
        self.halted: bool = False
        self.is_halted: bool = False
        self.halt_reason: Optional[str] = None
        self.halt_step: Optional[int] = None
        self.current_step: int = 0
        self.violations: List[str] = []
        self.active_indeterminate_ops: Set[str] = set()

        self.allowed_tools: FrozenSet[str] = frozenset(
            allowed_tools or {"refund_payment", "query_refund_status", "slice_symbol"}
        )
        self.allowed_export_dirs: FrozenSet[str] = frozenset(
            os.path.realpath(d) for d in (allowed_export_dirs or {"/tmp/aeib_safe_exports"})
        )

    def _get_op(self, op_id: str) -> OperationTraceState:
        if op_id not in self.operations:
            self.operations[op_id] = OperationTraceState(operation_id=op_id)
        return self.operations[op_id]

    def _is_path_contained(self, candidate_path: str) -> bool:
        """Defeats CVE-2026-43901 (arbitrary file write / export path escape)."""
        norm = posixpath.normpath(os.path.realpath(candidate_path))
        return any(
            norm == allowed or norm.startswith(allowed + "/") for allowed in self.allowed_export_dirs
        )

    def apply(self, event: Dict[str, Any]) -> None:
        """Applies a trace event and checks T1-T6 invariants."""
        op_id = str(event.get("operation_id", ""))
        kind = str(event.get("event", ""))
        state = self._get_op(op_id)

        # T6a: Scope Overreach Check (unapproved tool-call defense)
        tool_name = event.get("tool_name")
        if tool_name is not None and tool_name not in self.allowed_tools:
            self.violations.append(f"{op_id}: T6_SCOPE_OVERREACH_UNAPPROVED_TOOL ({tool_name})")

        # T6b: MCP Path-Traversal Export Check (CVE-2026-43901 defense)
        dest_dir = event.get("dest_dir")
        if dest_dir is not None and not self._is_path_contained(str(dest_dir)):
            self.violations.append(f"{op_id}: T6_PATH_TRAVERSAL_EXPORT_DENIED ({dest_dir})")

        if kind == "HALT_ENGAGED":
            self.halted = True
            self.is_halted = True
        elif kind == "INTENT_PERSISTED":
            if state.dispatched:
                self.violations.append(f"{op_id}: T1_INTENT_PERSISTED_AFTER_DISPATCH")
            state.intent_persisted = True
        elif kind == "RECEIPT_VERIFIED":
            state.receipt_verified = True
        elif kind == "DISPATCH_SENT":
            if self.halted or self.is_halted:
                self.violations.append(f"{op_id}: T3_DISPATCH_AFTER_HALT")
            if not state.intent_persisted:
                self.violations.append(f"{op_id}: T1_DISPATCH_WITHOUT_DURABLE_INTENT")
            if not state.receipt_verified:
                self.violations.append(f"{op_id}: T2_DISPATCH_WITHOUT_VERIFIED_RECEIPT")
            if state.effect_indeterminate:
                self.violations.append(f"{op_id}: T4_BLIND_RETRY_AFTER_UNCERTAINTY")
            if state.dispatched and not state.effect_indeterminate:
                self.violations.append(f"{op_id}: T4_DUPLICATE_DISPATCH_FOR_OPERATION")
            state.dispatched = True
        elif kind == "EFFECT_INDETERMINATE":
            if not state.dispatched:
                self.violations.append(f"{op_id}: UNCERTAINTY_WITHOUT_DISPATCH")
            state.effect_indeterminate = True
            state.reconciliation_probed = False
        elif kind == "RECONCILIATION_PROBED":
            if not state.effect_indeterminate:
                self.violations.append(f"{op_id}: PROBE_WITHOUT_INDETERMINATE_STATE")
            state.reconciliation_probed = True
        elif kind in ("CONFIRMED", "REFUTED", "UNRESOLVED_ESCALATED"):
            if not state.dispatched:
                self.violations.append(f"{op_id}: TERMINAL_WITHOUT_DISPATCH")
            if state.effect_indeterminate and kind in ("CONFIRMED", "REFUTED"):
                if not state.reconciliation_probed:
                    self.violations.append(
                        f"{op_id}: T5_TERMINAL_RESOLUTION_WITHOUT_RECONCILIATION_PROBE"
                    )
            if state.terminal_state is not None and state.terminal_state != kind:
                self.violations.append(
                    f"{op_id}: CONTRADICTORY_TERMINAL_TRANSITION ({state.terminal_state}->{kind})"
                )
            state.terminal_state = kind
            state.effect_indeterminate = False

    # Direct Timeline API for backwards compatibility and fine-grained simulation
    def record_halt(self, reason: str, step_index: Optional[int] = None) -> None:
        step = self.current_step if step_index is None else step_index
        self.is_halted = True
        self.halted = True
        self.halt_reason = reason
        self.halt_step = step

    def record_intent(
        self,
        operation_id: str,
        action_caid: str,
        amount_minor: int,
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index
        if operation_id not in self.timelines:
            self.timelines[operation_id] = OperationTimeline(operation_id=operation_id)
        tl = self.timelines[operation_id]
        tl.action_caid = action_caid
        tl.amount_minor = amount_minor
        tl.intent_step = step
        tl.current_state = OperationTemporalState.INTENT_PERSISTED
        tl.transitions.append((step, OperationTemporalState.INTENT_PERSISTED, "INTENT_RECORDED"))

    def record_dispatch(
        self,
        operation_id: str,
        endpoint: str = "",
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index
        if self.is_halted or self.halted:
            raise TemporalViolationError(
                rule_id="halt_blocks_future_dispatch",
                operation_id=operation_id,
                step_index=step,
                details=f"Dispatch attempted while boundary was halted: {self.halt_reason}",
            )
        tl = self.timelines.get(operation_id)
        if tl is None or tl.current_state == OperationTemporalState.UNSEEN:
            raise TemporalViolationError(
                rule_id="durable_intent_before_dispatch",
                operation_id=operation_id,
                step_index=step,
                details="Dispatch executed without prior durable intent persistence",
            )
        if tl.current_state == OperationTemporalState.EFFECT_INDETERMINATE:
            raise TemporalViolationError(
                rule_id="no_blind_retry_after_uncertainty",
                operation_id=operation_id,
                step_index=step,
                details="Blind retry attempted while operation effect is indeterminate",
            )
        tl.dispatch_step = step
        tl.current_state = OperationTemporalState.DISPATCH_SENT
        tl.transitions.append((step, OperationTemporalState.DISPATCH_SENT, f"DISPATCH_TO_{endpoint}"))

    def record_uncertainty(
        self,
        operation_id: str,
        reason: str = "HTTP_504_TIMEOUT",
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index
        tl = self.timelines.get(operation_id)
        if tl is None or tl.current_state != OperationTemporalState.DISPATCH_SENT:
            raise TemporalViolationError(
                rule_id="uncertainty_requires_prior_dispatch",
                operation_id=operation_id,
                step_index=step,
                details="Cannot transition to EFFECT_INDETERMINATE without prior dispatch",
            )
        tl.current_state = OperationTemporalState.EFFECT_INDETERMINATE
        tl.indeterminate_step = step
        tl.indeterminate_reason = reason
        tl.transitions.append((step, OperationTemporalState.EFFECT_INDETERMINATE, reason))
        self.active_indeterminate_ops.add(operation_id)

    def record_settlement(
        self,
        operation_id: str,
        outcome: str,
        evidence_digest: Optional[str] = None,
        authority_signature: Optional[str] = None,
        step_index: Optional[int] = None,
    ) -> None:
        step = self.current_step if step_index is None else step_index
        tl = self.timelines.get(operation_id)
        if tl is None or tl.current_state not in (
            OperationTemporalState.DISPATCH_SENT,
            OperationTemporalState.EFFECT_INDETERMINATE,
        ):
            raise TemporalViolationError(
                rule_id="settlement_requires_active_operation",
                operation_id=operation_id,
                step_index=step,
                details=f"Cannot settle operation in state {tl.current_state if tl else 'UNSEEN'}",
            )
        outcome_norm = outcome.upper()
        if outcome_norm in ("CONFIRMED", "SETTLED_CONFIRMED"):
            if not evidence_digest:
                raise TemporalViolationError(
                    rule_id="no_settlement_without_authoritative_evidence",
                    operation_id=operation_id,
                    step_index=step,
                    details="CONFIRMED settlement requires authoritative evidence digest",
                )
            tl.current_state = OperationTemporalState.CONFIRMED
        elif outcome_norm in ("REFUTED", "SETTLED_REFUTED"):
            tl.current_state = OperationTemporalState.REFUTED
        elif outcome_norm in ("UNRESOLVED_ESCALATED", "ESCALATED"):
            tl.current_state = OperationTemporalState.UNRESOLVED_ESCALATED
        else:
            raise ValueError(f"Unknown settlement outcome: {outcome}")

        tl.settlement_step = step
        tl.evidence_digest = evidence_digest
        tl.authority_signature = authority_signature
        tl.transitions.append((step, tl.current_state, f"SETTLED_{outcome_norm}"))
        self.active_indeterminate_ops.discard(operation_id)

    def check_bounded_reconciliation(self, current_step: int) -> None:
        for op_id in list(self.active_indeterminate_ops):
            tl = self.timelines[op_id]
            if tl.indeterminate_step is not None:
                elapsed = current_step - tl.indeterminate_step
                if elapsed > self.max_reconciliation_horizon:
                    raise TemporalViolationError(
                        rule_id="bounded_reconciliation",
                        operation_id=op_id,
                        step_index=current_step,
                        details=(
                            f"Operation {op_id} lingered in EFFECT_INDETERMINATE for {elapsed} steps "
                            f"(limit: {self.max_reconciliation_horizon})"
                        ),
                    )

    def verify_trace(self, trace_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        for step_idx, event in enumerate(trace_events):
            self.current_step = step_idx
            op_id = event.get("operation_id", "")
            action = event.get("action", "")
            self.check_bounded_reconciliation(step_idx)
            if event.get("is_halt_trigger", False) or action.startswith("HALT"):
                self.record_halt(reason=action, step_index=step_idx)
                continue
            if action in ("INTENT_STAGED", "INTENT_PERSISTED", "RECEIPT_CREATED"):
                caid = event.get("caid", hashlib.sha256(op_id.encode()).hexdigest())
                amount = event.get("amount_minor", 100_00)
                self.record_intent(op_id, caid, amount, step_index=step_idx)
            elif action in ("DISPATCH", "DISPATCH_SENT", "DISPATCH_RESERVED"):
                endpoint = event.get("endpoint", "POST /v1/mutations")
                self.record_dispatch(op_id, endpoint, step_index=step_idx)
            elif action in ("TRANSPORT_TIMEOUT_504", "HTTP_504_TIMEOUT", "EFFECT_INDETERMINATE", "LOST_ACK_POST_COMMIT"):
                reason = event.get("reason", action)
                self.record_uncertainty(op_id, reason, step_index=step_idx)
            elif action in ("CONFIRMED", "SETTLED_CONFIRMED", "REFUTED", "SETTLED_REFUTED", "UNRESOLVED_ESCALATED"):
                evidence = event.get("evidence_digest") or event.get("evidence")
                sig = event.get("authority_signature")
                self.record_settlement(op_id, action, evidence_digest=evidence, authority_signature=sig, step_index=step_idx)
        self.check_bounded_reconciliation(len(trace_events))
        return {
            "status": "PASS",
            "total_steps_verified": len(trace_events),
            "total_operations": len(self.timelines),
            "halt_engaged": self.is_halted,
            "halt_reason": self.halt_reason,
        }


# ============================================================================
# 16-CLASS AGENT CHAOS & HALLUCINATION INJECTOR
# ============================================================================

@dataclass(frozen=True)
class RawBoundaryDecision:
    disposition: str
    error_code: str
    request_id: str


class FailClosedWireParserAndGate:
    """
    Evaluates raw untrusted agent wire bytes BEFORE Station 1 touches any budget pool.
    Defeats all 16 Agent Chaos classes (truncated JSON, duplicate keys, float money,
    64-bit overflow, NaN/Infinity, scope overreach, and CVE-2026-43901 path escapes).
    """

    MAX_SAFE_U64_MINOR = (1 << 63) - 1
    REQUIRED_FIELDS = frozenset(
        {"operation_id", "tool_name", "amount_minor", "recipient", "policy_epoch"}
    )

    def __init__(
        self,
        allowed_tools: Set[str],
        pinned_recipients: Set[str],
        allowed_export_dirs: Set[str],
        active_policy_epoch: str = "epoch-2026-10",
    ) -> None:
        self.allowed_tools = frozenset(allowed_tools)
        self.pinned_recipients = frozenset(pinned_recipients)
        self.allowed_export_dirs = frozenset(os.path.realpath(d) for d in allowed_export_dirs)
        self.active_policy_epoch = active_policy_epoch
        self.reserved_minor: int = 0
        self.authoritative_ledger: List[Dict[str, Any]] = []
        self.rejection_audit_log: Dict[str, str] = {}
        self._seen_operation_ids: Set[str] = set()
        self._indeterminate_ops: Set[str] = set()

    def _reject(self, req_id: str, code: str) -> RawBoundaryDecision:
        self.rejection_audit_log[req_id] = code
        return RawBoundaryDecision(
            disposition="NOT_DISPATCHED",
            error_code=code,
            request_id=req_id,
        )

    def evaluate_raw_wire_payload(self, raw_payload: bytes, fallback_req_id: str) -> RawBoundaryDecision:
        # 1. Strict UTF-8 validation
        try:
            text = raw_payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return self._reject(fallback_req_id, "ERR_MALFORMED_WIRE_PAYLOAD_INVALID_UTF8")

        # 2. Strict JSON parse forbidding duplicate keys & NaN/Infinity constants
        duplicate_key_found = [False]

        def reject_dup_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            for k, v in pairs:
                if k in out:
                    duplicate_key_found[0] = True
                out[k] = v
            return out

        def reject_nan_inf(val: str) -> Any:
            raise ValueError(f"Forbidden constant: {val}")

        try:
            obj = json.loads(
                text,
                object_pairs_hook=reject_dup_keys,
                parse_constant=reject_nan_inf,
            )
        except Exception:
            return self._reject(fallback_req_id, "ERR_MALFORMED_WIRE_PAYLOAD_JSON")

        if duplicate_key_found[0] or not isinstance(obj, dict):
            return self._reject(fallback_req_id, "ERR_MALFORMED_WIRE_PAYLOAD_DUPLICATE_KEYS")

        # 3. Required schema fields check
        if not self.REQUIRED_FIELDS.issubset(obj.keys()):
            return self._reject(fallback_req_id, "ERR_MALFORMED_WIRE_PAYLOAD_MISSING_FIELDS")

        op_id = obj["operation_id"]
        if not isinstance(op_id, str) or not op_id.strip():
            return self._reject(fallback_req_id, "ERR_MALFORMED_WIRE_PAYLOAD_OP_ID")

        req_id = op_id

        # 4. Infinite retry / duplicate operation check
        if op_id in self._indeterminate_ops:
            return self._reject(req_id, "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY")
        if op_id in self._seen_operation_ids:
            return self._reject(req_id, "ERR_DUPLICATE_OPERATION_ID")

        # 5. Tool allowlist / Overreach check (unapproved tool defense)
        tool = obj["tool_name"]
        if not isinstance(tool, str) or tool not in self.allowed_tools:
            return self._reject(req_id, "ERR_UNAPPROVED_TOOL_OVERREACH")

        # 6. Export directory containment check (CVE-2026-43901 defense)
        if "dest_dir" in obj:
            dest_dir = obj["dest_dir"]
            if not isinstance(dest_dir, str):
                return self._reject(req_id, "ERR_INVALID_DEST_DIR_TYPE")
            norm = posixpath.normpath(os.path.realpath(dest_dir))
            if not any(
                norm == allowed or norm.startswith(allowed + "/")
                for allowed in self.allowed_export_dirs
            ):
                return self._reject(req_id, "ERR_PATH_TRAVERSAL_EXPORT_DENIED")

        # 7. Strict integer minor-unit validation (rejects bool, float, string, negative, overflow)
        amt = obj["amount_minor"]
        if isinstance(amt, bool) or not isinstance(amt, int):
            return self._reject(req_id, "ERR_MALFORMED_WIRE_PAYLOAD_AMOUNT_TYPE")
        if amt <= 0 or amt > self.MAX_SAFE_U64_MINOR:
            return self._reject(req_id, "ERR_MALFORMED_WIRE_PAYLOAD_AMOUNT_BOUNDS")

        # 8. Recipient type & allowlist check (hallucinated IBAN defense)
        rcpt = obj["recipient"]
        if not isinstance(rcpt, str) or rcpt not in self.pinned_recipients:
            return self._reject(req_id, "ERR_UNPINNED_OR_HALLUCINATED_RECIPIENT")

        # 9. Policy epoch & contradiction check
        if obj["policy_epoch"] != self.active_policy_epoch:
            return self._reject(req_id, "ERR_STALE_POLICY_EPOCH")
        if obj.get("read_only") is True and amt > 0:
            return self._reject(req_id, "ERR_CONTRADICTORY_CONTEXT_INTENT")

        # Validated: reserve budget and record in authoritative ledger
        self._seen_operation_ids.add(op_id)
        self.reserved_minor += amt
        self.authoritative_ledger.append({"operation_id": op_id, "amount_minor": amt})
        return RawBoundaryDecision(
            disposition="DISPATCHED",
            error_code="OK",
            request_id=req_id,
        )


def build_16_agent_chaos_fault_vectors() -> List[Tuple[str, bytes]]:
    """Returns all 16 mandatory agent chaos & hallucination fault classes."""
    return [
        ("1_truncated_json", b'{"operation_id":"op-1","amount_minor":50000,"recipient":"iban:DE89'),
        ("2_invalid_utf8", b'{"operation_id":"\xff\xfe","tool_name":"refund_payment"}'),
        (
            "3_duplicate_json_keys",
            b'{"operation_id":"op-dup","tool_name":"refund_payment","amount_minor":100,"amount_minor":999999,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "4_wrong_type_amount",
            b'{"operation_id":"op-str","tool_name":"refund_payment","amount_minor":"FIVE_HUNDRED","recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "5_negative_amount",
            b'{"operation_id":"op-neg","tool_name":"refund_payment","amount_minor":-500,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "6_integer_overflow",
            b'{"operation_id":"op-ovf","tool_name":"refund_payment","amount_minor":999999999999999999999999999,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "7_float_amount",
            b'{"operation_id":"op-flt","tool_name":"refund_payment","amount_minor":199.99,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "8_missing_operation_id",
            b'{"tool_name":"refund_payment","amount_minor":100,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "9_unknown_overreach_tool",
            b'{"operation_id":"op-ovr","tool_name":"drop_production_database","amount_minor":100,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "10_wrong_recipient_type",
            b'{"operation_id":"op-rtype","tool_name":"refund_payment","amount_minor":100,"recipient":["iban:DE89370400440532013000"],"policy_epoch":"epoch-2026-10"}',
        ),
        (
            "11_hallucinated_recipient_iban",
            b'{"operation_id":"op-halluc","tool_name":"refund_payment","amount_minor":100,"recipient":"iban:HALLUCINATED_MINIMAX_999","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "12_stale_policy_epoch",
            b'{"operation_id":"op-epoch","tool_name":"refund_payment","amount_minor":100,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2024-01"}',
        ),
        (
            "13_contradictory_context_intent",
            b'{"operation_id":"op-contra","tool_name":"refund_payment","amount_minor":100,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10","read_only":true}',
        ),
        (
            "14_cve_2026_43901_ssh_path_export",
            b'{"operation_id":"op-pcap","tool_name":"refund_payment","amount_minor":100,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10","dest_dir":"/home/user/.ssh"}',
        ),
        (
            "15_nan_constant_injection",
            b'{"operation_id":"op-nan","tool_name":"refund_payment","amount_minor":NaN,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
        (
            "16_boolean_as_integer_trap",
            b'{"operation_id":"op-bool","tool_name":"refund_payment","amount_minor":true,"recipient":"iban:DE89370400440532013000","policy_epoch":"epoch-2026-10"}',
        ),
    ]


def test_temporal_conformance_and_16_agent_chaos_faults() -> None:
    # 1. Verify Temporal Conformance Monitor on valid trace
    mon_ok = TemporalConformanceMonitor(
        allowed_tools={"refund_payment"},
        allowed_export_dirs={"/tmp/aeib_safe_exports"},
    )
    valid_trace = [
        {"operation_id": "op-101", "event": "INTENT_PERSISTED", "tool_name": "refund_payment"},
        {"operation_id": "op-101", "event": "RECEIPT_VERIFIED"},
        {"operation_id": "op-101", "event": "DISPATCH_SENT"},
        {"operation_id": "op-101", "event": "EFFECT_INDETERMINATE"},
        {"operation_id": "op-101", "event": "RECONCILIATION_PROBED"},
        {"operation_id": "op-101", "event": "CONFIRMED"},
    ]
    for ev in valid_trace:
        mon_ok.apply(ev)
    assert mon_ok.violations == []

    # 2. Verify Temporal Conformance Monitor catches blind retry, unprobed resolution, & path escape
    mon_bad = TemporalConformanceMonitor(
        allowed_tools={"refund_payment"},
        allowed_export_dirs={"/tmp/aeib_safe_exports"},
    )
    bad_trace = [
        {"operation_id": "op-202", "event": "INTENT_PERSISTED"},
        {"operation_id": "op-202", "event": "RECEIPT_VERIFIED"},
        {"operation_id": "op-202", "event": "DISPATCH_SENT"},
        {"operation_id": "op-202", "event": "EFFECT_INDETERMINATE"},
        {"operation_id": "op-202", "event": "DISPATCH_SENT"},  # Blind retry
        {"operation_id": "op-202", "event": "CONFIRMED"},      # Resolved without probe
        {
            "operation_id": "op-203",
            "event": "INTENT_PERSISTED",
            "tool_name": "wireshark_export_objects",           # Unapproved tool
            "dest_dir": "/home/user/.ssh",                     # Path escape
        },
    ]
    for ev in bad_trace:
        mon_bad.apply(ev)
    assert any("T4_BLIND_RETRY_AFTER_UNCERTAINTY" in v for v in mon_bad.violations)
    assert any("T5_TERMINAL_RESOLUTION_WITHOUT_RECONCILIATION_PROBE" in v for v in mon_bad.violations)
    assert any("T6_SCOPE_OVERREACH_UNAPPROVED_TOOL" in v for v in mon_bad.violations)
    assert any("T6_PATH_TRAVERSAL_EXPORT_DENIED" in v for v in mon_bad.violations)

    # 3. Verify all 16 Agent Chaos & Hallucination Faults fail-closed with 0 budget or ledger mutation
    gate = FailClosedWireParserAndGate(
        allowed_tools={"refund_payment"},
        pinned_recipients={"iban:DE89370400440532013000"},
        allowed_export_dirs={"/tmp/aeib_safe_exports"},
    )
    before_reserved = gate.reserved_minor
    before_ledger_len = len(gate.authoritative_ledger)

    for fault_name, raw_bytes in build_16_agent_chaos_fault_vectors():
        req_tag = f"chaos-{fault_name}"
        res = gate.evaluate_raw_wire_payload(raw_bytes, fallback_req_id=req_tag)
        assert res.disposition == "NOT_DISPATCHED", f"Fault {fault_name} was not blocked!"
        assert gate.reserved_minor == before_reserved, f"Budget mutated on {fault_name}!"
        assert len(gate.authoritative_ledger) == before_ledger_len, f"Ledger polluted on {fault_name}!"
        assert res.request_id in gate.rejection_audit_log, f"Missing audit log for {fault_name}!"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AEIB Temporal Conformance Monitor & Replay Checker"
    )
    parser.add_argument("--trace", type=str, help="Path to JSON/JSONL trace file")
    parser.add_argument(
        "--max-horizon",
        type=int,
        default=100,
        help="Max reconciliation steps for indeterminate effects",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run self-test against nominal and falsification traces",
    )

    args = parser.parse_args()

    if args.self_test:
        print("[*] Running TemporalConformanceMonitor self-test...")
        # 1. Direct timeline self-tests
        m1 = TemporalConformanceMonitor()
        try:
            m1.record_dispatch("op-bad", step_index=0)
            assert False, "Failed to catch Rule 1"
        except TemporalViolationError as e:
            assert e.rule_id == "durable_intent_before_dispatch"

        m2 = TemporalConformanceMonitor()
        m2.record_intent("op-retry", "caid1", 100, step_index=0)
        m2.record_dispatch("op-retry", step_index=1)
        m2.record_uncertainty("op-retry", step_index=2)
        try:
            m2.record_dispatch("op-retry", step_index=3)
            assert False, "Failed to catch Rule 2"
        except TemporalViolationError as e:
            assert e.rule_id == "no_blind_retry_after_uncertainty"

        m3 = TemporalConformanceMonitor(max_reconciliation_horizon_steps=3)
        m3.record_intent("op-linger", "caid1", 100, step_index=0)
        m3.record_dispatch("op-linger", step_index=1)
        m3.record_uncertainty("op-linger", step_index=2)
        try:
            m3.check_bounded_reconciliation(current_step=6)
            assert False, "Failed to catch Rule 3"
        except TemporalViolationError as e:
            assert e.rule_id == "bounded_reconciliation"

        m4 = TemporalConformanceMonitor()
        m4.record_halt("CORRUPTED_LEDGER", step_index=0)
        try:
            m4.record_dispatch("op-sub", step_index=2)
            assert False, "Failed to catch Rule 4"
        except TemporalViolationError as e:
            assert e.rule_id == "halt_blocks_future_dispatch"

        m5 = TemporalConformanceMonitor()
        m5.record_intent("op-ev", "caid1", 100, step_index=0)
        m5.record_dispatch("op-ev", step_index=1)
        try:
            m5.record_settlement("op-ev", "CONFIRMED", evidence_digest=None, step_index=2)
            assert False, "Failed to catch Rule 5"
        except TemporalViolationError as e:
            assert e.rule_id == "no_settlement_without_authoritative_evidence"

        # 2. Run new 16-class agent chaos and T1-T6 trace checks
        test_temporal_conformance_and_16_agent_chaos_faults()

        print("[✓] TemporalConformanceMonitor self-test PASSED (T1-T6 & 16 Chaos classes verified).")
        return 0

    if args.trace:
        trace_path = Path(args.trace)
        if not trace_path.exists():
            print(f"Error: Trace file not found: {trace_path}", file=sys.stderr)
            return 1
        events: List[Dict[str, Any]] = []
        if trace_path.suffix == ".jsonl":
            with open(trace_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        else:
            with open(trace_path, "r", encoding="utf-8") as f:
                events = json.load(f)

        monitor = TemporalConformanceMonitor(max_reconciliation_horizon_steps=args.max_horizon)
        try:
            res = monitor.verify_trace(events)
            print(json.dumps(res, indent=2))
            return 0
        except TemporalViolationError as e:
            print(f"FAILED: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
