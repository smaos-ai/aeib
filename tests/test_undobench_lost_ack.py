"""Counterfactual paired lost-acknowledgment benchmark & test (`arXiv:2610.05622`, UndoBench).

Models UndoBench's frozen lost-acknowledgment fault study ("UndoBench: Separating Task
Competence from Recovery Capability in Tool-Using AI Agents", Sah et al., arXiv:2610.05622v1)
across three execution arms using the real `PreDispatchIntentInterlock` and
`Eo1ReconciliationAdapter`:

  1. Arm 1 (`NAIVE_RETRY`): Retries immediately on lost ACK without read-back or intent
     latching. Produces duplicate external mutations on every post-commit lost-ACK trial
     (16/30 = 53.33% duplicate rate when 16 of 30 trials experience post-commit lost ACK).
  2. Arm 2 (`EO1_LATCH_ONLY`): Records intent before dispatch and latches `EFFECT_INDETERMINATE`
     on lost ACK, refusing blind retries (`LatchedCaidExecutionHaltedError`) -> 0 duplicates.
  3. Arm 3 (`EO1_PLUS_FENCED_RECONCILER`): Settles `EFFECT_INDETERMINATE` via
     `Eo1ReconciliationAdapter` (`FenceOutcome.APPLIED` -> `COMMITTED`;
     `FenceOutcome.FENCED_NOT_APPLIED` -> `NOT_COMMITTED` + single retry) -> 0 duplicates and
     30/30 intents applied exactly once.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.eo1_reconciliation_adapter import (
    Eo1ReconciliationAdapter,
    FenceOutcome,
    FenceRequest,
    ReadBackOutcome,
    ReadBackRequest,
    SettlementStatus,
)
from src.eo1_write_before_execute import (
    CaidAlreadyCommittedError,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
)

TARGET_URI = "https://enterprise.target.local/api/v1/ledger/transfer"
TOOL_NAME = "ledger.transfer_funds"


class DeterministicLostAckTarget:
    """In-memory state oracle recording exact external side-effect counts per CAID."""

    def __init__(self, fault_by_caid: Dict[str, str]) -> None:
        self.fault_by_caid = dict(fault_by_caid)
        self.effects_by_caid: Dict[str, int] = {}
        self.fenced_caids: Dict[str, int] = {}
        self._fault_triggered: set[str] = set()

    def execute_call(self, caid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        fault = self.fault_by_caid.get(caid, "NOMINAL_OK")
        if caid not in self._fault_triggered:
            self._fault_triggered.add(caid)
            if fault == "APPLIED_LOST_ACK":
                # Mutation commits on target, then connection drops before ACK reaches caller
                self.effects_by_caid[caid] = self.effects_by_caid.get(caid, 0) + 1
                raise ConnectionResetError("Simulated post-commit lost acknowledgment")
            if fault == "DROPPED_BEFORE_COMMIT":
                # Request dropped in flight before target mutates state
                raise TimeoutError("Simulated pre-commit transport drop")

        self.effects_by_caid[caid] = self.effects_by_caid.get(caid, 0) + 1
        return {"status": "APPLIED", "caid": caid, "amount_minor": payload["amount_minor"]}

    def fence_probe(self, req: FenceRequest) -> FenceOutcome:
        self.fenced_caids[req.caid] = req.below_attempt
        if self.effects_by_caid.get(req.caid, 0) > 0:
            return FenceOutcome.APPLIED
        return FenceOutcome.FENCED_NOT_APPLIED

    def readback_probe(self, req: ReadBackRequest) -> ReadBackOutcome:
        if self.effects_by_caid.get(req.caid, 0) > 0:
            return ReadBackOutcome.APPLIED
        return ReadBackOutcome.NOT_APPLIED


def _build_30_trial_schedule() -> List[ tuple[Dict[str, Any], str, str] ]:
    """Build 30 paired trials: 16 APPLIED_LOST_ACK (53.33%), 8 DROPPED_BEFORE_COMMIT, 6 NOMINAL_OK."""
    trials: List[tuple[Dict[str, Any], str, str]] = []
    for i in range(30):
        payload = {
            "account_id": f"acct_{i:03d}",
            "amount_minor": 1000 + i * 25,
            "currency": "USD",
            "invoice_id": f"inv_2026_{i:03d}",
        }
        caid = compute_caid(payload)
        if i < 16:
            fault = "APPLIED_LOST_ACK"
        elif i < 24:
            fault = "DROPPED_BEFORE_COMMIT"
        else:
            fault = "NOMINAL_OK"
        trials.append((payload, caid, fault))
    return trials


def test_undobench_paired_lost_ack_counterfactual_arms(tmp_path: Path) -> None:
    trials = _build_30_trial_schedule()
    fault_map = {caid: fault for _, caid, fault in trials}

    # -------------------------------------------------------------------------
    # Arm 1: Naive Retry (no pre-dispatch interlock, blind retry on lost ACK)
    # -------------------------------------------------------------------------
    target_naive = DeterministicLostAckTarget(fault_map)
    for payload, caid, _ in trials:
        try:
            target_naive.execute_call(caid, payload)
        except (ConnectionResetError, TimeoutError):
            # Naive retry re-sends on exception without state reconciliation
            target_naive.execute_call(caid, payload)

    naive_duplicates = sum(1 for c in target_naive.effects_by_caid.values() if c > 1)
    assert naive_duplicates == 16
    assert len(trials) == 30

    # -------------------------------------------------------------------------
    # Arm 2: EO1 Write-Before-Execute Only (latches EFFECT_INDETERMINATE, blocks retry)
    # -------------------------------------------------------------------------
    target_eo1 = DeterministicLostAckTarget(fault_map)
    interlock_eo1 = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "eo1_only" / "ledger.jsonl",
        output_state_dir=tmp_path / "eo1_only" / "state",
        boundary_private_key=Ed25519PrivateKey.generate(),
        authority_id="undobench-eo1-only",
    )
    latched_refusals = 0
    for payload, caid, _ in trials:
        try:
            interlock_eo1.dispatch(
                TARGET_URI,
                TOOL_NAME,
                payload,
                dispatch_fn=lambda c=caid, p=payload: target_eo1.execute_call(c, p),
            )
        except RuntimeError:
            # Blind retry attempt must be halted by the EFFECT_INDETERMINATE latch
            try:
                interlock_eo1.dispatch(
                    TARGET_URI,
                    TOOL_NAME,
                    payload,
                    dispatch_fn=lambda c=caid, p=payload: target_eo1.execute_call(c, p),
                )
            except LatchedCaidExecutionHaltedError:
                latched_refusals += 1

    eo1_duplicates = sum(1 for c in target_eo1.effects_by_caid.values() if c > 1)
    assert eo1_duplicates == 0
    assert latched_refusals == 24

    # -------------------------------------------------------------------------
    # Arm 3: EO1 + Fenced Read-Back Reconciler (settles & retries only NOT_APPLIED)
    # -------------------------------------------------------------------------
    target_reconciled = DeterministicLostAckTarget(fault_map)
    interlock_rec = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "eo1_reconciled" / "ledger.jsonl",
        output_state_dir=tmp_path / "eo1_reconciled" / "state",
        boundary_private_key=Ed25519PrivateKey.generate(),
        authority_id="undobench-eo1-reconciled",
    )

    for payload, caid, _ in trials:
        try:
            interlock_rec.dispatch(
                TARGET_URI,
                TOOL_NAME,
                payload,
                dispatch_fn=lambda c=caid, p=payload: target_reconciled.execute_call(c, p),
            )
        except RuntimeError:
            pass

    reconciler = Eo1ReconciliationAdapter(
        interlock_rec,
        target_reconciled.readback_probe,
        fence=target_reconciled.fence_probe,
        clock=lambda: 100.0,
        sleep=lambda _: None,
    )
    report = reconciler.reconcile_pending()
    assert len(report.settlements) == 24

    settled_committed = sum(
        1 for s in report.settlements if s.status == SettlementStatus.SETTLED_COMMITTED
    )
    settled_not_committed = sum(
        1 for s in report.settlements if s.status == SettlementStatus.SETTLED_NOT_COMMITTED
    )
    assert settled_committed == 16
    assert settled_not_committed == 8
    assert len(report.committed) == 16
    assert len(report.not_committed) == 8

    # Now retry all 24 faulted trials through EO1:
    # - The 16 APPLIED_LOST_ACK trials are already SETTLED_COMMITTED -> raise CaidAlreadyCommittedError
    # - The 8 DROPPED_BEFORE_COMMIT trials are SETTLED_NOT_COMMITTED -> execute once and succeed
    already_committed_blocks = 0
    recovered_executions = 0
    for payload, caid, fault in trials:
        if fault == "NOMINAL_OK":
            continue
        try:
            interlock_rec.dispatch(
                TARGET_URI,
                TOOL_NAME,
                payload,
                dispatch_fn=lambda c=caid, p=payload: target_reconciled.execute_call(c, p),
            )
            recovered_executions += 1
        except CaidAlreadyCommittedError:
            already_committed_blocks += 1

    assert already_committed_blocks == 16
    assert recovered_executions == 8

    # Every single one of the 30 trials applied its effect to the target exactly once (0 duplicates, 0 lost)
    reconciled_duplicates = sum(1 for c in target_reconciled.effects_by_caid.values() if c > 1)
    reconciled_exactly_once = sum(1 for c in target_reconciled.effects_by_caid.values() if c == 1)
    assert reconciled_duplicates == 0
    assert reconciled_exactly_once == 30
    assert interlock_rec.get_latched_caids() == {}
