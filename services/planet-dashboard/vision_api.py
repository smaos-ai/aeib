#!/usr/bin/env python3
"""
VisionAPI — Decision Support Layer for Governance
Embeds cryptographic governance into app decision flows.
Covenant-aligned: fail-closed gates, cryptographic audit, 1%/99% settlement.
Human Gate Policy Engine: fail-closed pre-execution checks before AP2 ledger charge.
Integrates MongeGapGovernor drift detection (PSI > 0.25 auto-engages, requires human approval).
"""

from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone
import hashlib
import json
import uuid
from abc import ABC, abstractmethod


# ═══════════════════════════════════════════════════════════
# 1. RISK LEVEL CLASSIFICATION
# ═══════════════════════════════════════════════════════════

class RiskLevel(Enum):
    """Risk Level Classification for Human Gate Policy"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @staticmethod
    def from_blast_radius(radius: float) -> 'RiskLevel':
        """Classify risk level from blast radius (0.0-1.0)"""
        if radius < 0.25:
            return RiskLevel.LOW
        elif radius < 0.5:
            return RiskLevel.MEDIUM
        elif radius < 0.75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def requires_approval(self) -> bool:
        """Check if this risk level requires human approval"""
        return self in (RiskLevel.HIGH, RiskLevel.CRITICAL)


# ═══════════════════════════════════════════════════════════
# 2. HUMAN GATE POLICY
# ═══════════════════════════════════════════════════════════

@dataclass
class HumanGatePolicy:
    """Policy defining approval requirements per risk level"""
    policy_id: str = "default-human-gate"
    requires_approval_for: List[RiskLevel] = None
    ap2_charge_enabled: bool = True
    psi_drift_threshold: float = 0.25  # PSI > 0.25 auto-engages gate
    max_concurrent_approvals: int = 10
    approval_timeout_secs: int = 3600

    def __post_init__(self):
        if self.requires_approval_for is None:
            self.requires_approval_for = [RiskLevel.HIGH, RiskLevel.CRITICAL]

    def needs_approval(self, risk_level: RiskLevel) -> bool:
        """Check if approval is required for given risk level"""
        return risk_level in self.requires_approval_for


# ═══════════════════════════════════════════════════════════
# 3. MERKLE PROOF & GOVERNANCE STRUCTURES
# ═══════════════════════════════════════════════════════════

@dataclass
class HumanGateProof:
    """Signed proof returned when gate passes"""
    merkle_root: str
    timestamp: str
    decision_id: str
    approved_by: Optional[str] = None  # Human approver ID if human approval
    auto_approved: bool = False  # Whether auto-approved due to low risk


@dataclass
class GovernRequest:
    """Govern request for AP2 ledger charge"""
    request_id: str
    action: str
    blast_radius: float  # 0.0-1.0
    user_id: str
    app_id: str
    human_approved: bool
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class PreExecuteCheckResult:
    """Result of pre-execution check"""
    allowed: bool
    charge_amount: int  # AP2 ledger charge (0 if blocked)
    proof: Optional[HumanGateProof] = None
    error: Optional[str] = None
    reason: str = ""

    def to_dict(self):
        """Convert to dict for JSON serialization"""
        return {
            "allowed": self.allowed,
            "charge_amount": self.charge_amount,
            "blocked": not self.allowed,
            "proof": asdict(self.proof) if self.proof else None,
            "error": self.error,
            "reason": self.reason
        }


# ═══════════════════════════════════════════════════════════
# 4. MONGE GAP GOVERNOR — DRIFT DETECTION
# ═══════════════════════════════════════════════════════════

@dataclass
class MongeGapResult:
    """Result of causal intervention experiment measuring generalization gap"""
    experiment_id: str
    hypothesis: str
    baseline_mean: float
    intervention_mean: float
    predicted_effect: float
    actual_effect: float
    gap_score: float
    breach_condition: bool
    timestamp: str


class MongeGapGovernor:
    """
    Stateful monitor for drift detection using Population Stability Index (PSI).
    Measures distributional shift between baseline and current distributions.
    PSI > 0.25 indicates significant drift and triggers human gate auto-engagement.
    """

    def __init__(self, circuit_breaker_threshold: int = 3):
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.breach_history: List[MongeGapResult] = []

    def compute_psi(self, baseline: List[float], current: List[float]) -> float:
        """
        Compute Population Stability Index (PSI) for drift detection.
        PSI measures distributional shift between baseline and current values.
        PSI > 0.25 indicates significant drift and should trigger human gate.

        Formula:
        PSI = |mean_current - mean_baseline| / std_baseline
            + 0.5 * (std_current - std_baseline)^2 / std_baseline^2
        """
        if not baseline or not current:
            return 0.0

        baseline_mean = sum(baseline) / len(baseline)
        baseline_std = (
            (sum((v - baseline_mean) ** 2 for v in baseline) / len(baseline)) ** 0.5
        )
        baseline_std = max(baseline_std, 0.001)  # Avoid division by zero

        current_mean = sum(current) / len(current)
        current_std = (
            (sum((v - current_mean) ** 2 for v in current) / len(current)) ** 0.5
        )
        current_std = max(current_std, 0.001)

        psi = (
            abs((current_mean - baseline_mean) / baseline_std)
            + 0.5 * ((current_std - baseline_std) / baseline_std) ** 2
        )
        return min(psi, 1.0)  # Clamp to [0, 1]

    def check_drift_detection(
        self, baseline_values: List[float], current_values: List[float], policy: HumanGatePolicy
    ) -> bool:
        """
        Check if drift detection should auto-engage human gate.
        Returns True if PSI > policy.psi_drift_threshold.
        """
        if not baseline_values or not current_values:
            return False

        psi = self.compute_psi(baseline_values, current_values)
        triggers_gate = psi > policy.psi_drift_threshold
        return triggers_gate

    def evaluate_experiment(
        self, baseline: List[float], current: List[float], hypothesis: str = "model_drift"
    ) -> MongeGapResult:
        """Evaluate experiment and return MongeGapResult"""
        baseline_mean = sum(baseline) / len(baseline) if baseline else 0.0
        current_mean = sum(current) / len(current) if current else 0.0
        actual_effect = current_mean - baseline_mean

        baseline_std = (
            (sum((v - baseline_mean) ** 2 for v in baseline) / len(baseline)) ** 0.5
            if baseline
            else 0.1
        )
        predicted_effect = max(baseline_std, 0.1)

        max_effect = max(abs(actual_effect), abs(predicted_effect), 0.01)
        gap_score = abs(actual_effect - predicted_effect) / max_effect
        breach_condition = gap_score > 0.15

        return MongeGapResult(
            experiment_id=str(uuid.uuid4()),
            hypothesis=hypothesis,
            baseline_mean=baseline_mean,
            intervention_mean=current_mean,
            predicted_effect=predicted_effect,
            actual_effect=actual_effect,
            gap_score=min(gap_score, 1.0),
            breach_condition=breach_condition,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# ═══════════════════════════════════════════════════════════
# 5. VISION API — MAIN DECISION ENGINE
# ═══════════════════════════════════════════════════════════

class VisionAPI:
    """
    VisionAPI — Decision Support Layer for Governance
    Implements fail-closed gates with cryptographic audit.
    Code flow:
    1. Receive govern request with human_approved flag
    2. Run pre_execute_check(risk_level, human_approved, psi_drift)
    3. If gate fails → return {"charge_amount": 0, "blocked": true, "reason": "[GATE_NAME]"}
    4. If gate passes → run AP2 charge + return Merkle proof
    """

    def __init__(self, policy: Optional[HumanGatePolicy] = None):
        self.policy = policy or HumanGatePolicy()
        self.decisions: Dict[str, PreExecuteCheckResult] = {}
        self.audit_trail: List[Tuple[str, str]] = []  # (decision_id, merkle_proof)
        self.merkle_root = "0"
        self.drift_detector = MongeGapGovernor()
        self.pending_approvals: Dict[str, GovernRequest] = {}

    def pre_execute_check(
        self, request: GovernRequest, psi_drift: Optional[float] = None
    ) -> PreExecuteCheckResult:
        """
        Pre-execution check with Human Gate Policy.
        Fail-closed: returns zero charge + error if not approved.

        Flow:
        1. Compute risk level from blast radius
        2. Check if PSI drift auto-engages gate
        3. Check if human approval is required
        4. If required and not approved, return error with zero charge
        5. If approved or low risk, compute Merkle proof and return charge authorization

        Returns:
            PreExecuteCheckResult with allowed flag, charge_amount, and Merkle proof
        """
        # Step 1: Classify risk level
        risk_level = RiskLevel.from_blast_radius(request.blast_radius)

        # Step 2: Check if PSI drift should auto-engage gate
        drift_gate_triggered = False
        if psi_drift is not None and psi_drift > self.policy.psi_drift_threshold:
            drift_gate_triggered = True
            # PSI drift auto-requires approval
            if not request.human_approved:
                return PreExecuteCheckResult(
                    allowed=False,
                    charge_amount=0,
                    error="DriftGateRequired",
                    reason=f"Model drift detected (PSI={psi_drift:.3f} > {self.policy.psi_drift_threshold}). "
                    f"High-risk action requires human approval.",
                )

        # Step 3: Check if approval is required for this risk level
        approval_required = self.policy.needs_approval(risk_level)

        # Step 4: Fail-closed gate: if approval required but not granted, block
        if approval_required and not request.human_approved:
            return PreExecuteCheckResult(
                allowed=False,
                charge_amount=0,
                error="HumanGateRequired",
                reason=f"Request requires human approval for risk level {risk_level.name}",
            )

        # Step 5: Gate passes: generate signed proof
        merkle_proof = self._compute_govern_merkle(request)
        self._update_merkle_root(merkle_proof)

        now = datetime.now(timezone.utc).isoformat()
        proof = HumanGateProof(
            merkle_root=self.merkle_root,
            timestamp=now,
            decision_id=request.request_id,
            approved_by=request.user_id if request.human_approved else None,
            auto_approved=not request.human_approved and not approval_required,
        )

        # Store in audit trail
        self.audit_trail.append((request.request_id, merkle_proof))

        # Compute AP2 charge
        charge_amount = 100 if self.policy.ap2_charge_enabled else 0

        result = PreExecuteCheckResult(
            allowed=True,
            charge_amount=charge_amount,
            proof=proof,
            error=None,
            reason=f"Approved (risk: {risk_level.name})",
        )

        self.decisions[request.request_id] = result
        return result

    def check_drift_auto_gates(
        self, baseline_values: List[float], current_values: List[float]
    ) -> bool:
        """
        Check if drift detection should auto-engage human gate.
        Returns True if PSI > policy.psi_drift_threshold.
        """
        return self.drift_detector.check_drift_detection(
            baseline_values, current_values, self.policy
        )

    def compute_psi(self, baseline: List[float], current: List[float]) -> float:
        """Compute Population Stability Index for drift detection"""
        return self.drift_detector.compute_psi(baseline, current)

    def _compute_govern_merkle(self, request: GovernRequest) -> str:
        """Generate Merkle proof for a govern request"""
        hasher = hashlib.sha256()
        hasher.update(request.request_id.encode())
        hasher.update(request.action.encode())
        hasher.update(str(request.blast_radius).encode())
        hasher.update(request.user_id.encode())
        hasher.update(request.app_id.encode())
        hasher.update(str(request.human_approved).encode())
        return hasher.hexdigest()

    def _update_merkle_root(self, new_proof: str) -> None:
        """Update cumulative Merkle root by hashing current root with new proof"""
        hasher = hashlib.sha256()
        hasher.update(self.merkle_root.encode())
        hasher.update(new_proof.encode())
        self.merkle_root = hasher.hexdigest()

    def export_audit_trail(self) -> str:
        """Export decision history as audit trail (for compliance + transparency)"""
        output = "DECISION AUDIT TRAIL\n"
        output += "===================\n\n"

        for decision_id, merkle_proof in self.audit_trail:
            output += f"Decision ID: {decision_id}\n"
            output += f"Merkle Proof: {merkle_proof}\n"
            if decision_id in self.decisions:
                result = self.decisions[decision_id]
                output += f"Allowed: {result.allowed}\n"
                output += f"Charge: {result.charge_amount}\n"
            output += "\n"

        return output

    def get_audit_trail(self) -> List[Tuple[str, str]]:
        """Get audit trail (human-verifiable, cryptographically signed)"""
        return self.audit_trail.copy()


# ═══════════════════════════════════════════════════════════
# 6. TESTS
# ═══════════════════════════════════════════════════════════

def test_risk_level_classification():
    """Test: RiskLevel classification from blast radius"""
    assert RiskLevel.from_blast_radius(0.1) == RiskLevel.LOW
    assert RiskLevel.from_blast_radius(0.3) == RiskLevel.MEDIUM
    assert RiskLevel.from_blast_radius(0.6) == RiskLevel.HIGH
    assert RiskLevel.from_blast_radius(0.9) == RiskLevel.CRITICAL
    print("[PASS] test_risk_level_classification")


def test_risk_level_requires_approval():
    """Test: RiskLevel approval requirement"""
    assert not RiskLevel.LOW.requires_approval()
    assert not RiskLevel.MEDIUM.requires_approval()
    assert RiskLevel.HIGH.requires_approval()
    assert RiskLevel.CRITICAL.requires_approval()
    print("[PASS] test_risk_level_requires_approval")


def test_low_risk_auto_approved():
    """Test: Low-risk action auto-approved without gate (zero approval required)"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-001",
        action="read_data",
        blast_radius=0.1,  # LOW risk
        user_id="user-1",
        app_id="app-1",
        human_approved=False,  # Not explicitly approved
    )

    result = api.pre_execute_check(request)
    assert result.allowed is True
    assert result.charge_amount == 100
    assert result.proof is not None
    assert result.proof.auto_approved is True
    assert result.error is None
    print("[PASS] test_low_risk_auto_approved")


def test_high_risk_blocked_without_approval():
    """Test: High-risk action blocked without approval (zero charge)"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-002",
        action="execute_system",
        blast_radius=0.8,  # HIGH risk
        user_id="user-2",
        app_id="app-2",
        human_approved=False,  # NOT approved
    )

    result = api.pre_execute_check(request)
    assert result.allowed is False
    assert result.charge_amount == 0  # ZERO charge on rejection
    assert result.proof is None
    assert result.error == "HumanGateRequired"
    assert "human approval" in result.reason.lower()
    print("[PASS] test_high_risk_blocked_without_approval")


def test_high_risk_approved_allowed():
    """Test: High-risk action allowed with human approval"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-003",
        action="execute_system",
        blast_radius=0.8,  # HIGH risk
        user_id="admin-1",
        app_id="app-3",
        human_approved=True,  # APPROVED
    )

    result = api.pre_execute_check(request)
    assert result.allowed is True
    assert result.charge_amount == 100
    assert result.proof is not None
    assert result.proof.approved_by == "admin-1"
    assert result.proof.auto_approved is False  # Human-approved, not auto
    print("[PASS] test_high_risk_approved_allowed")


def test_critical_risk_without_approval():
    """Test: Critical-risk action blocked without approval"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-004",
        action="delete_critical_data",
        blast_radius=0.95,  # CRITICAL risk
        user_id="user-4",
        app_id="app-4",
        human_approved=False,
    )

    result = api.pre_execute_check(request)
    assert result.allowed is False
    assert result.charge_amount == 0
    assert result.proof is None
    assert "CRITICAL" in result.reason
    print("[PASS] test_critical_risk_without_approval")


def test_psi_drift_triggers_gate():
    """Test: PSI drift > 0.25 auto-engages human gate"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-005",
        action="model_inference",
        blast_radius=0.4,  # MEDIUM risk
        user_id="user-5",
        app_id="app-5",
        human_approved=False,  # Not approved by human
    )

    # Simulate high PSI drift (> 0.25 threshold)
    psi_drift = 0.3

    result = api.pre_execute_check(request, psi_drift=psi_drift)
    assert result.allowed is False
    assert result.charge_amount == 0
    assert result.error == "DriftGateRequired"
    assert "drift" in result.reason.lower()
    print("[PASS] test_psi_drift_triggers_gate")


def test_psi_drift_overridden_by_human_approval():
    """Test: PSI drift gate can be overridden with human approval"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-006",
        action="model_inference",
        blast_radius=0.4,  # MEDIUM risk
        user_id="admin-2",
        app_id="app-6",
        human_approved=True,  # APPROVED by human
    )

    # Simulate high PSI drift (> 0.25 threshold)
    psi_drift = 0.3

    result = api.pre_execute_check(request, psi_drift=psi_drift)
    assert result.allowed is True
    assert result.charge_amount == 100
    assert result.proof is not None
    assert result.proof.approved_by == "admin-2"
    print("[PASS] test_psi_drift_overridden_by_human_approval")


def test_merkle_proof_generation():
    """Test: Merkle proof generation and accumulation"""
    api = VisionAPI()
    initial_root = api.merkle_root

    request1 = GovernRequest(
        request_id="req-1",
        action="action1",
        blast_radius=0.1,
        user_id="user-1",
        app_id="app-1",
        human_approved=False,
    )

    result1 = api.pre_execute_check(request1)
    root_after_1 = api.merkle_root

    assert initial_root != root_after_1
    assert result1.proof is not None
    assert result1.proof.merkle_root == root_after_1

    request2 = GovernRequest(
        request_id="req-2",
        action="action2",
        blast_radius=0.2,
        user_id="user-2",
        app_id="app-2",
        human_approved=False,
    )

    result2 = api.pre_execute_check(request2)
    root_after_2 = api.merkle_root

    assert root_after_1 != root_after_2
    print("[PASS] test_merkle_proof_generation")


def test_merkle_proof_deterministic():
    """Test: Same request produces same Merkle proof"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-det",
        action="action",
        blast_radius=0.1,
        user_id="user",
        app_id="app",
        human_approved=True,
    )

    proof1 = api._compute_govern_merkle(request)
    proof2 = api._compute_govern_merkle(request)
    assert proof1 == proof2
    print("[PASS] test_merkle_proof_deterministic")


def test_drift_detection_no_drift():
    """Test: PSI drift detection with stable distribution"""
    api = VisionAPI()
    baseline = [100.0, 101.0, 99.0, 100.0, 101.0]
    current = [100.05, 101.05, 99.05, 100.05, 101.05]  # <0.1% shift

    triggers_gate = api.check_drift_auto_gates(baseline, current)
    assert triggers_gate is False
    print("[PASS] test_drift_detection_no_drift")


def test_drift_detection_significant_drift():
    """Test: PSI drift detection with significant shift triggers gate"""
    api = VisionAPI()
    baseline = [100.0, 100.0, 100.0, 100.0, 100.0]
    current = [80.0, 80.0, 80.0, 80.0, 80.0]  # 20% shift

    triggers_gate = api.check_drift_auto_gates(baseline, current)
    assert triggers_gate is True
    print("[PASS] test_drift_detection_significant_drift")


def test_psi_computation():
    """Test: PSI computation"""
    api = VisionAPI()
    baseline = [10.0, 11.0, 12.0, 13.0, 14.0]
    shifted = [20.0, 21.0, 22.0, 23.0, 24.0]  # Shifted by 10

    psi = api.compute_psi(baseline, shifted)
    assert psi > 0.0
    assert psi > 0.25  # High drift
    print("[PASS] test_psi_computation")


def test_custom_policy_overrides():
    """Test: Custom policy overrides default"""
    custom_policy = HumanGatePolicy(
        policy_id="custom",
        psi_drift_threshold=0.5,
        ap2_charge_enabled=False,
    )

    api = VisionAPI(policy=custom_policy)
    request = GovernRequest(
        request_id="req-custom",
        action="read",
        blast_radius=0.1,
        user_id="user",
        app_id="app",
        human_approved=False,
    )

    result = api.pre_execute_check(request)
    assert result.allowed is True
    assert result.charge_amount == 0  # No charge due to disabled AP2
    print("[PASS] test_custom_policy_overrides")


def test_audit_trail_export():
    """Test: Audit trail export"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-audit",
        action="read",
        blast_radius=0.1,
        user_id="user",
        app_id="app",
        human_approved=False,
    )

    api.pre_execute_check(request)
    trail = api.export_audit_trail()
    assert "req-audit" in trail
    assert "DECISION AUDIT TRAIL" in trail
    print("[PASS] test_audit_trail_export")


def test_pre_execute_check_result_to_dict():
    """Test: PreExecuteCheckResult serialization to dict"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-dict",
        action="read",
        blast_radius=0.1,
        user_id="user",
        app_id="app",
        human_approved=False,
    )

    result = api.pre_execute_check(request)
    result_dict = result.to_dict()
    assert result_dict["allowed"] is True
    assert result_dict["blocked"] is False
    assert result_dict["charge_amount"] == 100
    assert result_dict["proof"] is not None
    print("[PASS] test_pre_execute_check_result_to_dict")


def test_blocked_result_to_dict():
    """Test: Blocked PreExecuteCheckResult serialization"""
    api = VisionAPI()
    request = GovernRequest(
        request_id="req-blocked",
        action="execute_system",
        blast_radius=0.8,
        user_id="user",
        app_id="app",
        human_approved=False,
    )

    result = api.pre_execute_check(request)
    result_dict = result.to_dict()
    assert result_dict["allowed"] is False
    assert result_dict["blocked"] is True
    assert result_dict["charge_amount"] == 0
    assert result_dict["proof"] is None
    assert result_dict["error"] == "HumanGateRequired"
    print("[PASS] test_blocked_result_to_dict")


# ═══════════════════════════════════════════════════════════
# 7. TEST RUNNER
# ═══════════════════════════════════════════════════════════

def run_all_tests():
    """Run all tests"""
    tests = [
        test_risk_level_classification,
        test_risk_level_requires_approval,
        test_low_risk_auto_approved,
        test_high_risk_blocked_without_approval,
        test_high_risk_approved_allowed,
        test_critical_risk_without_approval,
        test_psi_drift_triggers_gate,
        test_psi_drift_overridden_by_human_approval,
        test_merkle_proof_generation,
        test_merkle_proof_deterministic,
        test_drift_detection_no_drift,
        test_drift_detection_significant_drift,
        test_psi_computation,
        test_custom_policy_overrides,
        test_audit_trail_export,
        test_pre_execute_check_result_to_dict,
        test_blocked_result_to_dict,
    ]

    print("=" * 70)
    print("VISION API — HUMAN GATE POLICY TEST SUITE")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
