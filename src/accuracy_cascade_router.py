#!/usr/bin/env python3
"""
src/accuracy_cascade_router.py — Oracle-sovereign, calibrated cost-aware cascade router (prototype).

Design (grounded, see docs in module tests):
- CRE-Router (Moslem et al., ADAPT/Trinity College Dublin & Huawei, arXiv:2606.27457):
  per-cluster cost-adjusted error  Score = Error + lambda * Cost_norm, plus QE escalation.
- Agent-as-a-Router / ACRouter (arXiv:2606.22902): Context -> Action -> Feedback loop with
  verifier + memory; routing statistics come from execution-grounded feedback.

Corrections applied versus the pasted drafts:
1. Acceptance is decided by the task oracle, never by the router or a formatter/AST check alone.
2. No benchmark constants (e.g. "0.53 / 0.58") are used as live accuracy. Accuracy per
   (task_cluster, model) is read from a routing ledger and summarised by the Wilson 95%
   lower bound. Cold-start clusters (n < min_samples) fail closed to the strong route.
3. Objective is constrained: min E[cost] s.t. LB(P(verified | m, c)) >= accuracy_floor,
   and boundary-violation tolerance is zero (T3 => strong adjudication + human approval).
4. Final acceptance is bounded by the oracle, risk policy and human approval; a stronger
   model raises the probability of an oracle-passing repair but does not make it correct.

Epistemic notice: prototype, evaluated under the stated model. No outbound network calls.
"""

from __future__ import annotations

import hashlib
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs

RISK_TIERS = ("T0", "T1", "T2", "T3")
MAX_REPAIR_ATTEMPTS = 3  # AGENTS.md: bounded repair loop B <= 3

BASE_ORACLE_CHECKS: Tuple[str, ...] = (
    "diff_applies_cleanly",
    "syntax_valid",
    "allowed_imports_only",
    "no_stub_signals",
    "contract_tests_pass",
    "property_tests_pass",
    "regression_tests_pass",
    "no_unnecessary_public_api_change",
    "no_scope_expansion",
)
T2_ORACLE_CHECKS: Tuple[str, ...] = (
    "independent_diff_only_review",
    "blast_radius_updated",
    "provenance_recorded",
)
T3_ORACLE_CHECKS: Tuple[str, ...] = (
    "strong_model_adjudication",
    "exact_human_approval",
    "irreversible_action_idempotent",
    "reconciliation_path_defined",
)


def jcs_digest(payload: object) -> str:
    return "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()


def wilson_lower_bound(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    """Wilson score interval lower bound; 0.0 when there are no trials (fail closed)."""
    if trials <= 0:
        return 0.0
    if successes < 0 or successes > trials:
        raise ValueError("ERR_INVALID_COUNTS")
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    centre = p + z2 / (2.0 * trials)
    margin = z * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))
    return max(0.0, (centre - margin) / denom)


def wilson_upper_bound(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    """Wilson score interval upper bound; 1.0 when there are no trials."""
    if trials <= 0:
        return 1.0
    if successes < 0 or successes > trials:
        raise ValueError("ERR_INVALID_COUNTS")
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    centre = p + z2 / (2.0 * trials)
    margin = z * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))
    return min(1.0, (centre + margin) / denom)


# ------------------------------------------------------------------------------
# Calibration ledger (execution-grounded feedback memory)
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerEntry:
    task_cluster: str
    model: str
    oracle_passed: bool
    regression_detected: bool
    cost_usd: float
    latency_ms: int
    escalated: bool = False
    human_approved: bool = False

    @property
    def verified(self) -> bool:
        return self.oracle_passed and not self.regression_detected


@dataclass
class ClusterStats:
    trials: int = 0
    verified: int = 0
    false_accepts: int = 0  # oracle passed but regression detected later
    escalations: int = 0
    total_cost_usd: float = 0.0
    latencies: List[int] = field(default_factory=list)


class RoutingLedger:
    def __init__(self) -> None:
        self._stats: Dict[Tuple[str, str], ClusterStats] = {}

    def record(self, entry: LedgerEntry) -> None:
        if entry.cost_usd < 0 or entry.latency_ms < 0:
            raise ValueError("ERR_NEGATIVE_COST_OR_LATENCY")
        s = self._stats.setdefault((entry.task_cluster, entry.model), ClusterStats())
        s.trials += 1
        s.verified += int(entry.verified)
        s.false_accepts += int(entry.oracle_passed and entry.regression_detected)
        s.escalations += int(entry.escalated)
        s.total_cost_usd += entry.cost_usd
        s.latencies.append(entry.latency_ms)

    def stats(self, cluster: str, model: str) -> ClusterStats:
        return self._stats.get((cluster, model), ClusterStats())

    def accuracy_lower_bound(self, cluster: str, model: str) -> float:
        s = self.stats(cluster, model)
        return wilson_lower_bound(s.verified, s.trials)

    def calibration_report(self, cluster: str, model: str) -> Dict[str, object]:
        s = self.stats(cluster, model)
        lat = sorted(s.latencies)

        def pct(q: float) -> Optional[int]:
            if not lat:
                return None
            return lat[min(len(lat) - 1, int(math.ceil(q * len(lat))) - 1)]

        return {
            "task_cluster": cluster,
            "model": model,
            "trials": s.trials,
            "accuracy_bps": (s.verified * 10000) // s.trials if s.trials else 0,
            "accuracy_wilson_lb_bps": int(self.accuracy_lower_bound(cluster, model) * 10000),
            "false_accept_rate_bps": (s.false_accepts * 10000) // s.trials if s.trials else 0,
            "escalation_rate_bps": (s.escalations * 10000) // s.trials if s.trials else 0,
            "cost_per_verified_change_usd": (
                round(s.total_cost_usd / s.verified, 6) if s.verified else None
            ),
            "latency_p50_ms": pct(0.50),
            "latency_p95_ms": pct(0.95),
        }


# ------------------------------------------------------------------------------
# Router (constrained objective)
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CodingTask:
    task_id: str
    task_cluster: str
    risk_tier: str
    no_change_required: bool
    estimated_cost_usd: Mapping[str, float]  # per model id, operator-supplied estimate


@dataclass(frozen=True)
class RouteDecision:
    model: str
    reason: str
    estimated_cost_usd: float
    accuracy_lower_bound: float
    requires_human_approval: bool
    escalation_allowed: bool


class AccuracyCascadeRouter:
    """
    Chooses the cheapest model whose calibrated Wilson lower bound meets the accuracy floor.
    Ties/penalties use Score = (1 - LB) + lambda * Cost_norm. The router never accepts code.
    """

    def __init__(
        self,
        ledger: RoutingLedger,
        cheap_model: str,
        strong_model: str,
        accuracy_floor: float,
        lambda_cost: float = 0.05,
        min_samples: int = 30,
        exploration_bps: int = 0,
        max_exploration_trials: int = 300,
    ) -> None:
        if not 0.0 < accuracy_floor <= 1.0:
            raise ValueError("ERR_ACCURACY_FLOOR_OUT_OF_RANGE")
        if lambda_cost < 0.0 or min_samples < 1 or not 0 <= exploration_bps <= 10000:
            raise ValueError("ERR_INVALID_ROUTER_PARAMS")
        self.exploration_bps = exploration_bps
        self.max_exploration_trials = max_exploration_trials
        self.ledger = ledger
        self.cheap = cheap_model
        self.strong = strong_model
        self.accuracy_floor = accuracy_floor
        self.lambda_cost = lambda_cost
        self.min_samples = min_samples

    def _explore(self, task_id: str) -> bool:
        h = int.from_bytes(hashlib.sha256(task_id.encode("utf-8")).digest()[:4], "big")
        return (h % 10000) < self.exploration_bps

    def route(self, task: CodingTask) -> RouteDecision:
        if task.risk_tier not in RISK_TIERS:
            raise ValueError(f"ERR_UNKNOWN_RISK_TIER:{task.risk_tier}")
        if task.no_change_required:
            return RouteDecision("none", "HALT_NO_CHANGE_REQUIRED", 0.0, 0.0, False, False)
        for m in (self.cheap, self.strong):
            if m not in task.estimated_cost_usd or task.estimated_cost_usd[m] < 0:
                raise ValueError(f"ERR_MISSING_COST_ESTIMATE:{m}")

        strong_lb = self.ledger.accuracy_lower_bound(task.task_cluster, self.strong)
        strong_cost = task.estimated_cost_usd[self.strong]

        if task.risk_tier == "T3":
            return RouteDecision(
                self.strong, "T3_REQUIRES_STRONG_ADJUDICATION_AND_HUMAN",
                strong_cost, strong_lb, True, False,
            )

        cheap_stats = self.ledger.stats(task.task_cluster, self.cheap)
        cheap_cost = task.estimated_cost_usd[self.cheap]
        cheap_lb = self.ledger.accuracy_lower_bound(task.task_cluster, self.cheap)
        calibrated = cheap_stats.trials >= self.min_samples

        if calibrated:
            max_cost = max(cheap_cost, strong_cost) or 1.0
            cheap_score = (1.0 - cheap_lb) + self.lambda_cost * cheap_cost / max_cost
            strong_score = (1.0 - strong_lb) + self.lambda_cost * strong_cost / max_cost
            if cheap_lb >= self.accuracy_floor and cheap_score <= strong_score:
                return RouteDecision(
                    self.cheap, "CHEAP_LB_MEETS_FLOOR_AND_SCORE",
                    cheap_cost, cheap_lb, task.risk_tier == "T2", True,
                )

        # Oracle-gated calibration exploration (T0/T1 only, deterministic per task_id).
        # Observed in benchmarks/cascade_router_sim.py: stopping exploration at min_samples
        # froze a cheap model out (LB at n=30 sits far below its true rate). Exploration
        # therefore continues while the Wilson upper bound still admits the floor, capped
        # by max_exploration_trials.
        still_plausible = (not calibrated) or (
            wilson_upper_bound(cheap_stats.verified, cheap_stats.trials) >= self.accuracy_floor
        )
        if (
            task.risk_tier in ("T0", "T1")
            and cheap_stats.trials < self.max_exploration_trials
            and still_plausible
            and self._explore(task.task_id)
        ):
            return RouteDecision(
                self.cheap, "CALIBRATION_EXPLORATION_ORACLE_GATED",
                cheap_cost, cheap_lb, False, True,
            )

        reason = "FLOOR_OR_SCORE_PREFERS_STRONG" if calibrated else "COLD_START_INSUFFICIENT_CALIBRATION_FAIL_CLOSED"
        return RouteDecision(
            self.strong, reason, strong_cost, strong_lb, task.risk_tier == "T2", False,
        )


# ------------------------------------------------------------------------------
# Sovereign acceptance oracle
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class OracleVerdict:
    accepted: bool
    reason: str
    missing_checks: Tuple[str, ...]
    failed_checks: Tuple[str, ...]


class AcceptanceOracle:
    """Fail-closed: a check that is absent from evidence counts as a failure."""

    @staticmethod
    def required_checks(risk_tier: str) -> Tuple[str, ...]:
        if risk_tier not in RISK_TIERS:
            raise ValueError(f"ERR_UNKNOWN_RISK_TIER:{risk_tier}")
        req = list(BASE_ORACLE_CHECKS)
        if risk_tier in ("T2", "T3"):
            req += T2_ORACLE_CHECKS
        if risk_tier == "T3":
            req += T3_ORACLE_CHECKS
        return tuple(req)

    @classmethod
    def evaluate(
        cls, risk_tier: str, evidence: Mapping[str, bool], produced_by: str, reviewed_by: str = ""
    ) -> OracleVerdict:
        req = cls.required_checks(risk_tier)
        missing = tuple(c for c in req if c not in evidence)
        failed = tuple(c for c in req if c in evidence and evidence[c] is not True)
        if risk_tier in ("T2", "T3") and evidence.get("independent_diff_only_review") is True:
            if not reviewed_by or reviewed_by == produced_by:
                failed = failed + ("self_review_not_independent",)
        if missing:
            return OracleVerdict(False, "REJECT_MISSING_EVIDENCE", missing, failed)
        if failed:
            return OracleVerdict(False, "REJECT_FAILED_CHECKS", missing, failed)
        return OracleVerdict(True, "ACCEPT_ORACLE_PASSED", (), ())


def run_check_out_of_process(cmd: Sequence[str], cwd: str, timeout_s: int = 300) -> bool:
    """
    Executes one oracle command in a separate interpreter/process with a minimal env and
    timeout. Process isolation, not a sandbox. Returns True only on exit code 0.
    """
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": "0"}
    with tempfile.TemporaryDirectory() as home:
        env["HOME"] = home
        try:
            proc = subprocess.run(
                list(cmd), cwd=cwd, env=env, capture_output=True, timeout=timeout_s, check=False
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    return proc.returncode == 0


# ------------------------------------------------------------------------------
# Escalation packet (failed slice only, append-only suffix)
# ------------------------------------------------------------------------------


def build_escalation_packet(
    task: Mapping[str, object],
    contract: Mapping[str, object],
    failed_candidate_diff: str,
    verdict: OracleVerdict,
    failing_output: str,
    affected_symbols: Sequence[str],
    reverse_callers: Sequence[str],
    constraints: Sequence[str],
    attempt: int,
    max_input_tokens: int = 20000,
    max_output_tokens: int = 4000,
    max_evidence_chars: int = 4000,
) -> Dict[str, object]:
    if verdict.accepted:
        raise ValueError("ERR_ESCALATION_OF_ACCEPTED_CANDIDATE")
    if attempt > MAX_REPAIR_ATTEMPTS:
        raise RuntimeError("HALT_REPAIR_BUDGET_EXHAUSTED_ESCALATE_TO_HUMAN")
    if not reverse_callers and not affected_symbols:
        raise ValueError("ERR_EMPTY_SLICE_REFUSING_FULL_REPO_ESCALATION")
    evidence = failing_output
    truncated = len(evidence) > max_evidence_chars
    if truncated:
        evidence = evidence[: max_evidence_chars // 2] + "\n...[truncated]...\n" + evidence[-max_evidence_chars // 2 :]
    return {
        "escalation_version": "1",
        "original_task_digest": jcs_digest(dict(task)),
        "contract_digest": jcs_digest(dict(contract)),
        "failed_candidate_digest": "sha256:" + hashlib.sha256(failed_candidate_diff.encode()).hexdigest(),
        "failed_checks": sorted(set(verdict.failed_checks) | set(verdict.missing_checks)),
        "failing_test_output": evidence,
        "failing_output_truncated": truncated,
        "failing_output_digest": "sha256:" + hashlib.sha256(failing_output.encode()).hexdigest(),
        "affected_symbols": sorted(affected_symbols),
        "reverse_callers": sorted(reverse_callers),
        "constraints": list(constraints),
        "repair_budget": {
            "attempt": attempt,
            "max_attempts": MAX_REPAIR_ATTEMPTS,
            "max_input_tokens": max_input_tokens,
            "max_output_tokens": max_output_tokens,
        },
    }
