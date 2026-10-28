#!/usr/bin/env python3
"""
benchmarks/undobench_100_trial_effect_key.py
================================================================================
UndoBench-style lost-ack port with synthetic payloads; not the official UndoBench
harness; in-memory target.

Reference scenario: the lost-acknowledgment fault study in "UndoBench: Separating Task
Competence from Recovery Capability in Tool-Using AI Agents" (arXiv:2610.05622) and the
regenerated-retry problem described by ACRFence (arXiv:2603.20625). This file does not
reproduce either paper's harness, agents or payloads; it is a seeded port that drives the
repository's real ``PreDispatchIntentInterlock`` against a deterministic in-memory target.

Trial families (100 trials, seed 42 by default):
  * F8 "reworded retry" (50): attempt 1 commits at the target, then the ACK is lost
    (ConnectionResetError). Attempt 2 re-issues the same effect (same tenant, recipient,
    amount_minor, currency, business_ref) with reworded memo text, a fresh
    client_request_id and reordered optional fields.
  * DISTINCT "follow-up intent" (50): a first effect (its ACK lost or delivered, chosen by
    the seeded RNG) followed by a genuinely different second effect (different
    business_ref; amount equal or different, chosen by the RNG). The second effect is
    expected to execute.

Arms:
  * A0 naive retry: no interlock; every attempt goes to the target.
  * A2 interlock keyed by the full-payload ``compute_caid`` (raw tool arguments).
  * A4 interlock keyed by the effect-key CAID (``resolve_dispatch_key`` with a registry
    schema for the tool; unknown tools raise ``UnknownToolSchemaError`` before dispatch).
  * A5 A4 + ``Eo1ReconciliationAdapter`` settling EFFECT_INDETERMINATE latches via a
    read-back probe on the target before attempt 2.

Measured per arm (counted from target state and interlock outcomes, never assumed):
  duplicate effects on F8 (business references with > 1 applied effect, of 50), with a
  Wilson 95% interval computed in integer basis points; distinct follow-ups completed (of
  50); false merges (distinct follow-ups refused by the interlock); residual
  EFFECT_INDETERMINATE latches at the end of the run.

Predictions (tested, not assumed; reported as held / failed):
  A0 F8 duplicates > 0; A2 F8 duplicates > 0; A4 F8 duplicates == 0; A4 false merges == 0.

Limits: payloads are synthetic and generated from a seeded ``random.Random``; the target
is an in-memory counter, not a payment system; the interlock ledger lives in a temp dir.
The run digest covers only the integer/string summary (interlock intent ids and
timestamps are not part of it).
"""

from __future__ import annotations

import argparse
import hashlib
import random
import sys
import tempfile
from dataclasses import dataclass, field
from fractions import Fraction
from math import isqrt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from src.eo1_effect_key import (  # noqa: E402
    EffectClass,
    EffectKeySchema,
    EffectKeySchemaRegistry,
    IdentityField,
    resolve_dispatch_key,
)
from src.eo1_reconciliation_adapter import (  # noqa: E402
    Eo1ReconciliationAdapter,
    FenceOutcome,
    FenceRequest,
    ReadBackOutcome,
    ReadBackRequest,
)
from src.eo1_write_before_execute import (  # noqa: E402
    CaidAlreadyCommittedError,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
)
from src.jcs_canonicalizer import encode_jcs  # noqa: E402
from src.strict_json_ingress import loads_strict  # noqa: E402

LABEL = "UndoBench-style lost-ack port with synthetic payloads; not the official UndoBench harness; in-memory target"
SOURCE_PAPERS = ("arXiv:2610.05622", "arXiv:2603.20625")
TARGET_URI = "https://payments.target.local/api/v1/transfers"
TOOL_NAME = "payments.create_transfer"

ARM_NAIVE = "A0_naive_retry"
ARM_FULL_PAYLOAD = "A2_interlock_full_payload_caid"
ARM_EFFECT_KEY = "A4_interlock_effect_key_caid"
ARM_EFFECT_KEY_RECONCILED = "A5_effect_key_plus_readback_reconciler"
ARMS = (ARM_NAIVE, ARM_FULL_PAYLOAD, ARM_EFFECT_KEY, ARM_EFFECT_KEY_RECONCILED)

FAMILY_F8 = "F8_reworded_retry"
FAMILY_DISTINCT = "DISTINCT_follow_up"

FAULT_LOST_ACK = "LOST_ACK_AFTER_COMMIT"
FAULT_NONE = "NOMINAL"

# Wilson z = 1.96 expressed as z^2 = 38416 / 10000 (exact rational, no floats).
_Z2_NUM = 38416
_Z2_DEN = 10000
_BPS = 10000
_SQRT_SCALE = 10 ** 12

MEMO_TEMPLATES = (
    "Payment for invoice {ref}",
    "Settling {ref} as agreed",
    "Transfer re: {ref}",
    "Invoice {ref} - monthly services",
    "Re-sending payment for {ref}",
    "As discussed, paying {ref}",
)
TAG_POOL = ("ap", "vendor", "q4", "recurring", "ops", "approved")


def payments_schema() -> EffectKeySchema:
    """Identity = tenant, recipient, amount_minor, currency, business_ref; memo/ids/tags are incidental."""
    return EffectKeySchema(
        tool=TOOL_NAME,
        schema_id="payments.create_transfer.effect.v1",
        schema_version="1",
        identity_fields=(
            IdentityField("tenant_id", "exact_nfc"),
            IdentityField("recipient_account", "exact_nfc"),
            IdentityField("amount_minor", "minor_units"),
            IdentityField("currency", "currency_iso4217"),
            IdentityField("business_ref", "exact_nfc"),
        ),
        effect_class=EffectClass.IRREVERSIBLE,
    )


def build_registry() -> EffectKeySchemaRegistry:
    return EffectKeySchemaRegistry([payments_schema()], allow_full_payload_fallback=False)


# ---------------------------------------------------------------------------
# Deterministic in-memory target
# ---------------------------------------------------------------------------


class InMemoryPaymentsTarget:
    """
    Counts applied side effects per (tenant_id, business_ref). Not idempotent by itself:
    every call that reaches ``execute`` applies an effect. A fault plan keyed by
    client_request_id makes a call commit and then raise ConnectionResetError (lost ACK).
    ``readback_probe`` answers by the idempotency token (the arm's CAID) that accompanied
    each applied call.
    """

    def __init__(self, fault_by_request_id: Dict[str, str]) -> None:
        self.fault_by_request_id = dict(fault_by_request_id)
        self.effects_by_ref: Dict[Tuple[str, str], int] = {}
        self.applied_tokens: Dict[str, Tuple[str, str]] = {}
        self.calls = 0

    def execute(self, payload: Dict[str, Any], token: Optional[str]) -> Dict[str, Any]:
        self.calls += 1
        ref = (str(payload["tenant_id"]), str(payload["business_ref"]))
        self.effects_by_ref[ref] = self.effects_by_ref.get(ref, 0) + 1
        if token is not None:
            self.applied_tokens[token] = ref
        if self.fault_by_request_id.get(str(payload["client_request_id"])) == FAULT_LOST_ACK:
            raise ConnectionResetError("post-commit lost acknowledgment (synthetic)")
        return {"status": "APPLIED", "business_ref": ref[1]}

    def readback_probe(self, req: ReadBackRequest) -> ReadBackOutcome:
        return ReadBackOutcome.APPLIED if req.caid in self.applied_tokens else ReadBackOutcome.NOT_APPLIED

    def fence_probe(self, req: FenceRequest) -> FenceOutcome:
        return FenceOutcome.APPLIED if req.caid in self.applied_tokens else FenceOutcome.FENCED_NOT_APPLIED

    def effect_count(self, tenant_id: str, business_ref: str) -> int:
        return self.effects_by_ref.get((tenant_id, business_ref), 0)


# ---------------------------------------------------------------------------
# Seeded trial schedule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Trial:
    index: int
    family: str
    first: Dict[str, Any]
    second: Dict[str, Any]
    first_fault: str


def _request_id(rng: random.Random) -> str:
    return f"req-{rng.getrandbits(64):016x}"


def _payload(rng: random.Random, tenant: str, recipient: str, amount: int, currency: str, ref: str,
             request_id: str, memo_idx: int, tags: List[str], key_order_reversed: bool) -> Dict[str, Any]:
    items: List[Tuple[str, Any]] = [
        ("tenant_id", tenant),
        ("recipient_account", recipient),
        ("amount_minor", amount),
        ("currency", currency),
        ("business_ref", ref),
        ("memo", MEMO_TEMPLATES[memo_idx].format(ref=ref)),
        ("client_request_id", request_id),
        ("tags", list(tags)),
        ("requested_by", "agent-%d" % rng.randrange(1, 4)),
    ]
    if key_order_reversed:
        items.reverse()
    return dict(items)


def build_schedule(seed: int = 42, n_f8: int = 50, n_distinct: int = 50) -> List[Trial]:
    rng = random.Random(seed)
    trials: List[Trial] = []
    for i in range(n_f8 + n_distinct):
        family = FAMILY_F8 if i < n_f8 else FAMILY_DISTINCT
        tenant = f"tenant-{rng.randrange(1, 6):02d}"
        recipient = f"acct-{rng.randrange(10_000, 99_999)}"
        amount = rng.randrange(100, 500_000)
        currency = rng.choice(("EUR", "USD", "GBP"))
        ref = f"INV-2026-{i:04d}"
        tags = rng.sample(TAG_POOL, 3)
        memo1 = rng.randrange(len(MEMO_TEMPLATES))
        first = _payload(rng, tenant, recipient, amount, currency, ref, _request_id(rng), memo1, tags, False)
        if family == FAMILY_F8:
            memo2 = (memo1 + 1 + rng.randrange(len(MEMO_TEMPLATES) - 1)) % len(MEMO_TEMPLATES)
            second = _payload(rng, tenant, recipient, amount, currency, ref, _request_id(rng), memo2,
                              list(reversed(tags)), True)
            first_fault = FAULT_LOST_ACK
        else:
            second_amount = amount if rng.random() < 0.5 else rng.randrange(100, 500_000)
            ref2 = f"INV-2026-{i:04d}-B"
            memo2 = rng.randrange(len(MEMO_TEMPLATES))
            second = _payload(rng, tenant, recipient, second_amount, currency, ref2, _request_id(rng), memo2,
                              rng.sample(TAG_POOL, 3), rng.random() < 0.5)
            first_fault = FAULT_LOST_ACK if rng.random() < 0.5 else FAULT_NONE
        trials.append(Trial(index=i, family=family, first=first, second=second, first_fault=first_fault))
    return trials


_REQUIRED_TRIAL_KEYS = ("family", "first", "second", "first_fault")
_REQUIRED_PAYLOAD_STR_KEYS = ("tenant_id", "recipient_account", "currency", "business_ref", "client_request_id")


def _validate_trial_payload(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
    for k in _REQUIRED_PAYLOAD_STR_KEYS:
        val = obj.get(k)
        if not isinstance(val, str) or not val.strip():
            raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
    amt = obj.get("amount_minor")
    if isinstance(amt, bool) or not isinstance(amt, int) or amt <= 0:
        raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
    return dict(obj)


def load_trials_from_jsonl(path: Path) -> List[Trial]:
    """Load and strictly validate an external JSONL file of UndoBench-style trials."""
    if not path.is_file():
        raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW") from exc
    trials: List[Trial] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = loads_strict(line, integers_only=True)
        except Exception as exc:
            raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW") from exc
        if not isinstance(row, dict):
            raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
        for req_key in _REQUIRED_TRIAL_KEYS:
            if req_key not in row:
                raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
        family = row["family"]
        if family not in (FAMILY_F8, FAMILY_DISTINCT):
            raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
        first_fault = row["first_fault"]
        if first_fault not in (FAULT_LOST_ACK, FAULT_NONE):
            raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
        first = _validate_trial_payload(row["first"])
        second = _validate_trial_payload(row["second"])
        trials.append(Trial(
            index=len(trials),
            family=family,
            first=first,
            second=second,
            first_fault=first_fault,
        ))
    if not trials:
        raise ValueError("ERR_INVALID_UNDOBENCH_JSONL_ROW")
    return trials


# ---------------------------------------------------------------------------
# Arm drivers
# ---------------------------------------------------------------------------

OUTCOME_EXECUTED = "EXECUTED"
OUTCOME_LOST_ACK = "LOST_ACK"
OUTCOME_REFUSED_LATCHED = "REFUSED_LATCHED"
OUTCOME_REFUSED_COMMITTED = "REFUSED_ALREADY_COMMITTED"


def _new_interlock(base: Path, authority_id: str) -> PreDispatchIntentInterlock:
    return PreDispatchIntentInterlock(
        ledger_path=base / "ledger.jsonl",
        output_state_dir=base / "state",
        boundary_private_key=Ed25519PrivateKey.generate(),
        authority_id=authority_id,
    )


def dispatch_effect_keyed(interlock: PreDispatchIntentInterlock, target: InMemoryPaymentsTarget,
                          registry: EffectKeySchemaRegistry, tool: str, payload: Dict[str, Any]) -> str:
    """
    A4 dispatch path. ``resolve_dispatch_key`` raises UnknownToolSchemaError for a tool without a
    schema, before any ledger write or target call. The interlock CAID equals the effect CAID
    because the effect-key preimage is passed as the interlock payload; the raw arguments go to
    the target with that CAID as the idempotency token. Returns the CAID.
    """
    resolution = resolve_dispatch_key(tool, payload, registry)
    caid = resolution.caid
    interlock.dispatch(TARGET_URI, tool, resolution.interlock_payload,
                       dispatch_fn=lambda: target.execute(payload, caid))
    return caid


def _attempt(arm: str, interlock: Optional[PreDispatchIntentInterlock], target: InMemoryPaymentsTarget,
             registry: EffectKeySchemaRegistry, payload: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    if arm == ARM_NAIVE:
        try:
            target.execute(payload, None)
            return OUTCOME_EXECUTED, None
        except ConnectionResetError:
            return OUTCOME_LOST_ACK, None
    if interlock is None:
        raise ValueError(f"arm {arm!r} requires an interlock")
    try:
        if arm == ARM_FULL_PAYLOAD:
            caid = compute_caid(payload)
            interlock.dispatch(TARGET_URI, TOOL_NAME, payload,
                               dispatch_fn=lambda: target.execute(payload, caid))
        else:
            caid = resolve_dispatch_key(TOOL_NAME, payload, registry).caid
            dispatch_effect_keyed(interlock, target, registry, TOOL_NAME, payload)
        return OUTCOME_EXECUTED, caid
    except CaidAlreadyCommittedError:
        return OUTCOME_REFUSED_COMMITTED, caid
    except LatchedCaidExecutionHaltedError:
        return OUTCOME_REFUSED_LATCHED, caid
    except RuntimeError as exc:
        if isinstance(exc.__cause__, ConnectionResetError):
            return OUTCOME_LOST_ACK, caid
        raise


@dataclass
class ArmResult:
    arm: str
    f8_trials: int = 0
    f8_duplicates: int = 0
    f8_second_refused: int = 0
    distinct_trials: int = 0
    distinct_completed: int = 0
    false_merges: int = 0
    residual_indeterminate: int = 0
    reconciler_settled_committed: int = 0
    reconciler_settled_not_committed: int = 0
    reconciler_still_latched: int = 0
    target_calls: int = 0
    outcomes: Dict[str, int] = field(default_factory=dict)

    def bump(self, outcome: str) -> None:
        self.outcomes[outcome] = self.outcomes.get(outcome, 0) + 1


def run_arm(arm: str, trials: List[Trial], workdir: Path) -> ArmResult:
    fault_plan = {str(t.first["client_request_id"]): t.first_fault for t in trials}
    target = InMemoryPaymentsTarget(fault_plan)
    registry = build_registry()
    interlock = None if arm == ARM_NAIVE else _new_interlock(workdir / arm, f"undobench-port-{arm}")
    adapter = None
    if arm == ARM_EFFECT_KEY_RECONCILED and interlock is not None:
        adapter = Eo1ReconciliationAdapter(interlock, target.readback_probe, fence=target.fence_probe,
                                           clock=lambda: 0.0, sleep=lambda _s: None)
    res = ArmResult(arm=arm)
    for t in trials:
        out1, caid1 = _attempt(arm, interlock, target, registry, t.first)
        res.bump(out1)
        if adapter is not None and out1 == OUTCOME_LOST_ACK and caid1 is not None:
            report = adapter.reconcile_pending(caids=[caid1])
            res.reconciler_settled_committed += len(report.committed)
            res.reconciler_settled_not_committed += len(report.not_committed)
            res.reconciler_still_latched += len(report.still_latched)
        out2, _ = _attempt(arm, interlock, target, registry, t.second)
        res.bump(out2)
        if t.family == FAMILY_F8:
            res.f8_trials += 1
            if target.effect_count(t.first["tenant_id"], t.first["business_ref"]) > 1:
                res.f8_duplicates += 1
            if out2 in (OUTCOME_REFUSED_LATCHED, OUTCOME_REFUSED_COMMITTED):
                res.f8_second_refused += 1
        else:
            res.distinct_trials += 1
            if out2 in (OUTCOME_REFUSED_LATCHED, OUTCOME_REFUSED_COMMITTED):
                res.false_merges += 1
            elif target.effect_count(t.second["tenant_id"], t.second["business_ref"]) == 1:
                res.distinct_completed += 1
    if interlock is not None:
        res.residual_indeterminate = len(interlock.get_latched_caids())
    res.target_calls = target.calls
    return res


# ---------------------------------------------------------------------------
# Statistics (integers only)
# ---------------------------------------------------------------------------


def _sqrt_fraction_bounds(x: Fraction) -> Tuple[Fraction, Fraction]:
    """Floor / ceil rational bounds on sqrt(x) at 1/_SQRT_SCALE resolution."""
    scaled = x * _SQRT_SCALE * _SQRT_SCALE
    lo = isqrt(scaled.numerator // scaled.denominator)
    hi = lo if lo * lo * scaled.denominator == scaled.numerator else lo + 1
    return Fraction(lo, _SQRT_SCALE), Fraction(hi, _SQRT_SCALE)


def wilson_interval_bps(k: int, n: int) -> Tuple[int, int]:
    """Wilson 95% score interval for k/n in integer basis points (outward-rounded, clamped)."""
    if n <= 0 or k < 0 or k > n:
        raise ValueError("wilson_interval_bps requires 0 <= k <= n and n > 0")
    z2 = Fraction(_Z2_NUM, _Z2_DEN)
    denom = n + z2
    center = (k + z2 / 2) / denom
    radicand = z2 * (Fraction(k * (n - k), n) + z2 / 4)
    _, sqrt_hi = _sqrt_fraction_bounds(radicand)
    half = sqrt_hi / denom
    lo = (center - half) * _BPS
    hi = (center + half) * _BPS
    lo_bps = max(0, lo.numerator // lo.denominator)
    hi_bps = min(_BPS, -((-hi.numerator) // hi.denominator))
    return int(lo_bps), int(hi_bps)


def rate_bps(k: int, n: int) -> int:
    return (k * _BPS) // n if n else 0


# ---------------------------------------------------------------------------
# Run + report
# ---------------------------------------------------------------------------


def _arm_summary(res: ArmResult) -> Dict[str, Any]:
    lo, hi = wilson_interval_bps(res.f8_duplicates, res.f8_trials)
    return {
        "arm": res.arm,
        "f8_trials": res.f8_trials,
        "f8_duplicate_effects": res.f8_duplicates,
        "f8_duplicate_rate_bps": rate_bps(res.f8_duplicates, res.f8_trials),
        "f8_duplicate_wilson95_bps": [lo, hi],
        "f8_second_attempt_refused": res.f8_second_refused,
        "distinct_trials": res.distinct_trials,
        "distinct_completed": res.distinct_completed,
        "false_merges": res.false_merges,
        "residual_effect_indeterminate": res.residual_indeterminate,
        "reconciler_settled_committed": res.reconciler_settled_committed,
        "reconciler_settled_not_committed": res.reconciler_settled_not_committed,
        "reconciler_still_latched": res.reconciler_still_latched,
        "target_calls": res.target_calls,
        "attempt_outcomes": dict(sorted(res.outcomes.items())),
    }


def _predictions(arms: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
    return {
        "A0_f8_duplicates_gt_0": arms[ARM_NAIVE]["f8_duplicate_effects"] > 0,
        "A2_f8_duplicates_gt_0": arms[ARM_FULL_PAYLOAD]["f8_duplicate_effects"] > 0,
        "A4_f8_duplicates_eq_0": arms[ARM_EFFECT_KEY]["f8_duplicate_effects"] == 0,
        "A4_false_merges_eq_0": arms[ARM_EFFECT_KEY]["false_merges"] == 0,
    }


def probe_unknown_tool_fail_closed(workdir: Path) -> Dict[str, Any]:
    """A4 with a tool that has no schema: count ledger records and target calls after the refusal."""
    from src.eo1_effect_key import UnknownToolSchemaError

    target = InMemoryPaymentsTarget({})
    interlock = _new_interlock(workdir / "unknown_tool_probe", "undobench-port-unknown-tool")
    payload = build_schedule(seed=0, n_f8=1, n_distinct=0)[0].first
    refused = False
    try:
        dispatch_effect_keyed(interlock, target, build_registry(), "payments.unregistered_tool", payload)
    except UnknownToolSchemaError:
        refused = True
    ledger = interlock.ledger_path
    ledger_lines = len([ln for ln in ledger.read_bytes().split(b"\n") if ln.strip()]) if ledger.exists() else 0
    return {"refused_unknown_tool": refused, "target_calls": target.calls, "ledger_records": ledger_lines}


def run_benchmark(seed: int = 42, n_f8: int = 50, n_distinct: int = 50,
                  workdir: Optional[Path] = None,
                  trials: Optional[List[Trial]] = None) -> Dict[str, Any]:
    if trials is None:
        active_trials = build_schedule(seed=seed, n_f8=n_f8, n_distinct=n_distinct)
    else:
        active_trials = list(trials)
        n_f8 = sum(1 for t in active_trials if t.family == FAMILY_F8)
        n_distinct = sum(1 for t in active_trials if t.family == FAMILY_DISTINCT)
    with tempfile.TemporaryDirectory(prefix="undobench100-") as tmp:
        base = Path(workdir) if workdir is not None else Path(tmp)
        arms = {arm: _arm_summary(run_arm(arm, active_trials, base)) for arm in ARMS}
        unknown = probe_unknown_tool_fail_closed(base)
    schedule_digest = hashlib.sha256(encode_jcs([
        {"family": t.family, "first": t.first, "first_fault": t.first_fault, "second": t.second} for t in active_trials
    ])).hexdigest()
    summary: Dict[str, Any] = {
        "label": LABEL,
        "source_papers": list(SOURCE_PAPERS),
        "seed": seed,
        "trials": {"F8_reworded_retry": n_f8, "DISTINCT_follow_up": n_distinct},
        "schedule_digest_sha256": schedule_digest,
        "arms": arms,
        "predictions_held": _predictions(arms) if n_f8 and n_distinct else {},
        "unknown_tool_probe_A4": unknown,
    }
    summary["run_digest_sha256"] = hashlib.sha256(encode_jcs(summary)).hexdigest()
    return summary


def _fmt_bps(bps: int) -> str:
    return f"{bps / 100:.2f}%"


def render_table(summary: Dict[str, Any]) -> str:
    lines = [
        summary["label"],
        f"seed={summary['seed']}  F8={summary['trials']['F8_reworded_retry']}  "
        f"DISTINCT={summary['trials']['DISTINCT_follow_up']}",
        "",
        f"{'arm':<40} {'F8 dupes':>9} {'dupe rate':>9} {'Wilson95':>17} {'distinct ok':>11} "
        f"{'false merges':>12} {'resid INDET':>11}",
    ]
    for arm in ARMS:
        a = summary["arms"][arm]
        lo, hi = a["f8_duplicate_wilson95_bps"]
        lines.append(
            f"{arm:<40} {a['f8_duplicate_effects']:>4}/{a['f8_trials']:<4} {_fmt_bps(a['f8_duplicate_rate_bps']):>9} "
            f"{'[' + _fmt_bps(lo) + ', ' + _fmt_bps(hi) + ']':>17} "
            f"{str(a['distinct_completed']) + '/' + str(a['distinct_trials']):>11} "
            f"{a['false_merges']:>12} {a['residual_effect_indeterminate']:>11}"
        )
    a5 = summary["arms"][ARM_EFFECT_KEY_RECONCILED]
    lines += [
        "",
        f"A5 reconciler: settled_committed={a5['reconciler_settled_committed']} "
        f"settled_not_committed={a5['reconciler_settled_not_committed']} "
        f"still_latched={a5['reconciler_still_latched']}",
        f"A4 unknown-tool probe: {summary['unknown_tool_probe_A4']}",
        "Predictions: " + ", ".join(
            f"{name}={'held' if ok else 'FAILED'}" for name, ok in summary["predictions_held"].items()),
        f"schedule_digest_sha256={summary['schedule_digest_sha256']}",
        f"run_digest_sha256={summary['run_digest_sha256']}",
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=LABEL)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--f8", type=int, default=50)
    parser.add_argument("--distinct", type=int, default=50)
    parser.add_argument("--jsonl-in", type=str, default=None, help="load trials from an external JSONL file")
    parser.add_argument("--json", action="store_true", help="print the JCS summary instead of the table")
    args = parser.parse_args(argv)
    loaded_trials = load_trials_from_jsonl(Path(args.jsonl_in)) if args.jsonl_in else None
    summary = run_benchmark(seed=args.seed, n_f8=args.f8, n_distinct=args.distinct, trials=loaded_trials)
    if args.json:
        print(encode_jcs(summary).decode("utf-8"))
    else:
        print(render_table(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
