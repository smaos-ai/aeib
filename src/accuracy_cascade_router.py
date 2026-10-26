#!/usr/bin/env python3
"""
src/accuracy_cascade_router.py — Oracle-sovereign, calibrated cost-aware cascade router (prototype).

Design (grounded, see docs in module tests):
- CRE-Router (Moslem et al., ADAPT/Trinity College Dublin & Huawei, arXiv:2606.27457):
  per-cluster cost-adjusted error  Score = Error + lambda * Cost_norm, plus QE escalation.
- Agent-as-a-Router / ACRouter (arXiv:2606.22902): Context -> Action -> Feedback loop with
  verifier + memory; routing statistics come from execution-grounded feedback.
- Conformal Arbitrage (Overman & Bayati, Stanford, arXiv:2506.00911): finite-sample
  distribution-free Conformal Risk Control bound R_hat = (losses + 1) / (n + 1) over a
  sliding window + consecutive-failure breaker to detect non-stationary model drift.
- UTBoost (Yu, Zhu, He, Kang, CUHK & UIUC, arXiv:2506.09289): boolean "tests pass" is
  vulnerable to weak-suite test overfitting; AcceptanceOracle enforces an optional
  mutation-adequacy floor (`min_mutation_kill_bps`).

Corrections applied versus the pasted drafts:
1. Acceptance is decided by the task oracle, never by the router or a formatter/AST check alone.
2. No benchmark constants (e.g. "0.53 / 0.58") are used as live accuracy. Accuracy per
   (task_cluster, model) is read from a routing ledger and summarised by the Wilson 95%
   lower bound plus a sliding-window Conformal Risk Control upper bound. Cold-start
   clusters (n < min_samples) fail closed to the strong route (with deterministic,
   oracle-gated T0/T1 calibration exploration while the Wilson upper bound admits the floor).
3. Objective is constrained: min E[cost] s.t. LB(P(verified | m, c)) >= accuracy_floor,
   recent conformal risk <= 1 - accuracy_floor, and boundary-violation tolerance is zero
   (T3 => strong adjudication + human approval).
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
BPS_SCALE = 10000

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


def _validate_counts(count: int, trials: int) -> None:
    if count < 0 or count > trials:
        raise ValueError("ERR_INVALID_COUNTS")


def wilson_lower_bound(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    """Wilson score interval lower bound; 0.0 when there are no trials (fail closed)."""
    if trials <= 0:
        return 0.0
    _validate_counts(successes, trials)
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
    _validate_counts(successes, trials)
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    centre = p + z2 / (2.0 * trials)
    margin = z * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))
    return min(1.0, (centre + margin) / denom)


def conformal_risk_upper_bound(losses: int, trials: int) -> float:
    """
    Finite-sample distribution-free Conformal Risk Control upper bound (arXiv:2506.00911):
        R_hat = (losses + 1) / (trials + 1)
    Returns 1.0 when trials <= 0 (fail closed).
    """
    if trials <= 0:
        return 1.0
    _validate_counts(losses, trials)
    return (losses + 1.0) / (trials + 1.0)


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
    consecutive_failures: int = 0
    total_cost_usd: float = 0.0
    latencies: List[int] = field(default_factory=list)
    recent_verified: List[bool] = field(default_factory=list)


class RoutingLedger:
    def __init__(self) -> None:
        self._stats: Dict[Tuple[str, str], ClusterStats] = {}

    def record(self, entry: LedgerEntry) -> None:
        if entry.cost_usd < 0 or entry.latency_ms < 0:
            raise ValueError("ERR_NEGATIVE_COST_OR_LATENCY")
        s = self._stats.setdefault((entry.task_cluster, entry.model), ClusterStats())
        s.trials += 1
        is_verified = entry.verified
        s.verified += int(is_verified)
        s.false_accepts += int(entry.oracle_passed and entry.regression_detected)
        s.escalations += int(entry.escalated)
        s.consecutive_failures = 0 if is_verified else (s.consecutive_failures + 1)
        s.total_cost_usd += entry.cost_usd
        s.latencies.append(entry.latency_ms)
        s.recent_verified.append(is_verified)

    def stats(self, cluster: str, model: str) -> ClusterStats:
        return self._stats.get((cluster, model), ClusterStats())

    def accuracy_lower_bound(self, cluster: str, model: str) -> float:
        s = self.stats(cluster, model)
        return wilson_lower_bound(s.verified, s.trials)

    def recent_conformal_risk_ub(self, cluster: str, model: str, window: int = 20) -> float:
        if window <= 0:
            raise ValueError("ERR_INVALID_WINDOW")
        s = self.stats(cluster, model)
        recent = s.recent_verified[-window:]
        losses = len(recent) - sum(int(v) for v in recent)
        return conformal_risk_upper_bound(losses, len(recent))

    def calibration_report(self, cluster: str, model: str) -> Dict[str, object]:
        s = self.stats(cluster, model)
        lat = sorted(s.latencies)

        def pct(q: float) -> Optional[int]:
            if not lat:
                return None
            return lat[int(math.ceil(q * len(lat))) - 1]

        return {
            "task_cluster": cluster,
            "model": model,
            "trials": s.trials,
            "accuracy_bps": (s.verified * BPS_SCALE) // s.trials if s.trials else 0,
            "accuracy_wilson_lb_bps": int(self.accuracy_lower_bound(cluster, model) * BPS_SCALE),
            "false_accept_rate_bps": (s.false_accepts * BPS_SCALE) // s.trials if s.trials else 0,
            "escalation_rate_bps": (s.escalations * BPS_SCALE) // s.trials if s.trials else 0,
            "consecutive_failures": s.consecutive_failures,
            "cost_per_verified_change_usd": (
                round(s.total_cost_usd / s.verified, 6) if s.verified else None
            ),
            "latency_p50_ms": pct(0.50),
            "latency_p95_ms": pct(0.95),
        }


# ------------------------------------------------------------------------------
# Router (constrained objective + Conformal Risk Control drift breaker)
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
    Chooses the cheapest model whose calibrated Wilson lower bound meets the accuracy floor
    and whose sliding-window Conformal Risk Control upper bound and consecutive-failure count
    have not tripped. Ties/penalties use Score = (1 - LB) + lambda * Cost_norm.
    The router never accepts code.
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
        max_consecutive_failures: int = 3,
        drift_window: int = 20,
    ) -> None:
        if not 0.0 < accuracy_floor <= 1.0:
            raise ValueError("ERR_ACCURACY_FLOOR_OUT_OF_RANGE")
        if (
            lambda_cost < 0.0
            or min_samples < 1
            or not 0 <= exploration_bps <= BPS_SCALE
            or max_consecutive_failures < 1
            or drift_window < 1
        ):
            raise ValueError("ERR_INVALID_ROUTER_PARAMS")
        self.exploration_bps = exploration_bps
        self.max_exploration_trials = max_exploration_trials
        self.max_consecutive_failures = max_consecutive_failures
        self.drift_window = drift_window
        self.ledger = ledger
        self.cheap = cheap_model
        self.strong = strong_model
        self.accuracy_floor = accuracy_floor
        self.lambda_cost = lambda_cost
        self.min_samples = min_samples

    def _explore(self, task_id: str) -> bool:
        h = int.from_bytes(hashlib.sha256(task_id.encode("utf-8")).digest()[:4], "big")
        return (h % BPS_SCALE) < self.exploration_bps

    def _drift_tripped(self, cluster: str, cheap_stats: ClusterStats) -> bool:
        if cheap_stats.consecutive_failures >= self.max_consecutive_failures:
            return True
        if len(cheap_stats.recent_verified) >= self.drift_window:
            recent_ub = self.ledger.recent_conformal_risk_ub(cluster, self.cheap, self.drift_window)
            max_risk = (1.0 - self.accuracy_floor) + (1.0 / (self.drift_window + 1.0))
            if recent_ub > max_risk:
                return True
        return False

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

        if calibrated and self._drift_tripped(task.task_cluster, cheap_stats):
            return RouteDecision(
                self.strong, "DRIFT_OR_CONFORMAL_RISK_TRIP_TO_STRONG",
                strong_cost, strong_lb, task.risk_tier == "T2", False,
            )

        if calibrated and cheap_lb >= self.accuracy_floor:
            strong_stats = self.ledger.stats(task.task_cluster, self.strong)
            cheap_err = 1.0 - (cheap_stats.verified / cheap_stats.trials)
            strong_err = (
                1.0 - (strong_stats.verified / strong_stats.trials)
                if strong_stats.trials
                else 1.0
            )
            max_cost = max(cheap_cost, strong_cost) or 1.0
            cheap_score = cheap_err + self.lambda_cost * cheap_cost / max_cost
            strong_score = strong_err + self.lambda_cost * strong_cost / max_cost
            if cheap_score <= strong_score:
                return RouteDecision(
                    self.cheap, "CHEAP_LB_MEETS_FLOOR_AND_SCORE",
                    cheap_cost, cheap_lb, task.risk_tier == "T2", True,
                )

        # Oracle-gated calibration exploration (T0/T1 only, deterministic per task_id).
        still_plausible = (not calibrated) or (
            wilson_upper_bound(cheap_stats.verified, cheap_stats.trials) >= self.accuracy_floor
        )
        if (
            task.risk_tier in ("T0", "T1")
            and cheap_stats.trials < self.max_exploration_trials
            and cheap_stats.consecutive_failures < self.max_consecutive_failures
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
# Sovereign acceptance oracle (with UTBoost mutation-adequacy floor)
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
        cls,
        risk_tier: str,
        evidence: Mapping[str, bool],
        produced_by: str,
        reviewed_by: str = "",
        mutation_kill_ratio_bps: Optional[int] = None,
        min_mutation_kill_bps: int = 0,
    ) -> OracleVerdict:
        if not 0 <= min_mutation_kill_bps <= BPS_SCALE:
            raise ValueError("ERR_INVALID_MUTATION_FLOOR")
        req = cls.required_checks(risk_tier)
        missing = list(c for c in req if c not in evidence)
        failed = list(c for c in req if c in evidence and evidence[c] is not True)
        if risk_tier in ("T2", "T3") and evidence.get("independent_diff_only_review") is True:
            if not reviewed_by or reviewed_by == produced_by:
                failed.append("self_review_not_independent")
        if min_mutation_kill_bps > 0:
            if mutation_kill_ratio_bps is None:
                missing.append("mutation_kill_ratio_bps")
            elif mutation_kill_ratio_bps < min_mutation_kill_bps:
                failed.append("mutation_adequacy_below_floor")
        if missing:
            return OracleVerdict(False, "REJECT_MISSING_EVIDENCE", tuple(missing), tuple(failed))
        if failed:
            return OracleVerdict(False, "REJECT_FAILED_CHECKS", tuple(missing), tuple(failed))
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
        half = max_evidence_chars // 2
        evidence = evidence[:half] + "\n...[truncated]...\n" + evidence[-half:]
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
