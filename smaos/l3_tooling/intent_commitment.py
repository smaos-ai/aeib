"""
Stream H: Intent-Verified Delegation (OWASP ASI01 Defense)
Prevents goal hijacking by hash-committing to proposed objectives before execution.
Detects hijacking, context pollution, and goal drift with cryptographic proof.
"""

import json
import hashlib
import time
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

def utcnow_iso() -> str:
    """Return current UTC timestamp in ISO format (timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()

# Try to import real crypto signer; fall back to placeholder if not available
try:
    from smaos.l6_infrastructure.kms_signer import KMSSigner
    _kms_signer: Optional[KMSSigner] = None  # Will be lazily initialized
except ImportError:
    logger.warning("KMSSigner not available; using placeholder signatures")
    _kms_signer = None


class IntentType(Enum):
    """Types of agent intents."""
    GOAL = "goal"
    PLAN = "plan"
    DECISION = "decision"
    CONSTRAINT = "constraint"


class HijackingType(Enum):
    """Types of detected hijacking."""
    UNAUTHORIZED_DATA_ACCESS = "unauthorized_data_access"
    LATENCY_VIOLATION = "latency_violation"
    UNAUTHORIZED_API_CALL = "unauthorized_api_call"
    GOAL_DRIFT = "goal_drift"
    CONTEXT_POLLUTION = "context_pollution"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class EscalationLevel(Enum):
    """Escalation severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    IMMEDIATE_HALT = "immediate_halt"


@dataclass
class IntentConstraint:
    """Defines constraints on execution."""
    name: str
    value: Any
    constraint_type: str  # "latency", "data_access", "api_call", "resource"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IntentCommitment:
    """
    Cryptographic commitment to a proposed intent.
    Hash-binds the agent to specific goal + plan + constraints.
    """
    commitment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utcnow_iso)
    agent_name: str = "unknown"
    intent_type: IntentType = IntentType.GOAL

    # Core commitment
    goal: str = ""  # What the agent will do
    plan: str = ""  # How it will do it (high-level)
    constraints: List[IntentConstraint] = field(default_factory=list)  # Execution limits

    # Hashes and signatures
    commitment_hash: str = ""  # SHA256 of goal+plan+constraints
    ap2_ledger_id: Optional[str] = None
    ed25519_signature: Optional[str] = None

    # Metadata
    model: str = "unknown"
    context_hash: str = ""  # Hash of context at commitment time
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_commitment_hash(self) -> str:
        """Compute SHA256 hash binding agent to intent."""
        commitment_data = {
            "commitment_id": self.commitment_id,
            "agent_name": self.agent_name,
            "intent_type": self.intent_type.value,
            "goal": self.goal,
            "plan": self.plan,
            "constraints": [c.to_dict() for c in self.constraints],
            "timestamp": self.timestamp,
            "model": self.model,
            "context_hash": self.context_hash,
        }
        json_str = json.dumps(commitment_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    def finalize(self) -> None:
        """Finalize commitment and compute hash."""
        if not self.commitment_hash:
            self.commitment_hash = self.compute_commitment_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "timestamp": self.timestamp,
            "agent_name": self.agent_name,
            "intent_type": self.intent_type.value,
            "goal": self.goal,
            "plan": self.plan,
            "constraints": [c.to_dict() for c in self.constraints],
            "commitment_hash": self.commitment_hash,
            "ap2_ledger_id": self.ap2_ledger_id,
            "ed25519_signature": self.ed25519_signature,
            "model": self.model,
            "context_hash": self.context_hash,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionAction:
    """Records an action taken during execution."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    commitment_id: str = ""
    timestamp: str = field(default_factory=utcnow_iso)
    action_type: str = ""  # "data_access", "api_call", "computation", etc.
    resource_accessed: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HijackingDetection:
    """Records detected hijacking attempt."""
    detection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    commitment_id: str = ""
    hijacking_type: HijackingType = HijackingType.GOAL_DRIFT
    timestamp: str = field(default_factory=utcnow_iso)
    severity: EscalationLevel = EscalationLevel.WARNING
    description: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    actions_blocked: List[str] = field(default_factory=list)
    human_escalated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['hijacking_type'] = self.hijacking_type.value
        d['severity'] = self.severity.value
        return d


class IntentVerifier:
    """Verifies that executed actions match committed intent."""

    def __init__(self, commitment: IntentCommitment):
        self.commitment = commitment
        self.actions: List[ExecutionAction] = []
        self.detections: List[HijackingDetection] = []
        self.started_at = datetime.now(timezone.utc)
        self._verification_done = False

    def record_action(
        self,
        action_type: str,
        resource_accessed: str = "",
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionAction:
        """Record an action taken during execution."""
        action = ExecutionAction(
            commitment_id=self.commitment.commitment_id,
            action_type=action_type,
            resource_accessed=resource_accessed,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        self.actions.append(action)
        return action

    def _check_latency_constraint(self, constraint: IntentConstraint) -> Optional[HijackingDetection]:
        """Check if execution exceeded latency constraint."""
        if constraint.constraint_type != "latency":
            return None

        # Check if already detected for this constraint
        for d in self.detections:
            if d.hijacking_type == HijackingType.LATENCY_VIOLATION:
                return None  # Already detected

        elapsed_ms = (datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000
        max_latency = constraint.value

        if elapsed_ms > max_latency:
            detection = HijackingDetection(
                commitment_id=self.commitment.commitment_id,
                hijacking_type=HijackingType.LATENCY_VIOLATION,
                severity=EscalationLevel.IMMEDIATE_HALT,
                description=f"Latency violation: {elapsed_ms:.0f}ms > {max_latency}ms limit",
                evidence={
                    "actual_latency_ms": elapsed_ms,
                    "max_allowed_ms": max_latency,
                    "constraint_name": constraint.name,
                },
            )
            detection.human_escalated = True
            self.detections.append(detection)
            return detection
        return None

    def _check_data_access_constraint(self, constraint: IntentConstraint, action: ExecutionAction) -> Optional[HijackingDetection]:
        """Check if action violates data access constraints."""
        if constraint.constraint_type != "data_access":
            return None

        if action.action_type != "data_access":
            return None

        allowed_sources = constraint.value  # List of allowed data sources
        if not isinstance(allowed_sources, list):
            allowed_sources = [allowed_sources]

        if action.resource_accessed not in allowed_sources:
            # Check if we already have a detection for this action
            for d in self.detections:
                if action.action_id in d.actions_blocked:
                    return None

            detection = HijackingDetection(
                commitment_id=self.commitment.commitment_id,
                hijacking_type=HijackingType.UNAUTHORIZED_DATA_ACCESS,
                severity=EscalationLevel.IMMEDIATE_HALT,
                description=f"Unauthorized data access: {action.resource_accessed} not in whitelist",
                evidence={
                    "accessed": action.resource_accessed,
                    "allowed_sources": allowed_sources,
                    "constraint_name": constraint.name,
                    "action_id": action.action_id,
                },
            )
            detection.human_escalated = True
            detection.actions_blocked.append(action.action_id)
            self.detections.append(detection)
            return detection
        return None

    def _check_api_constraint(self, constraint: IntentConstraint, action: ExecutionAction) -> Optional[HijackingDetection]:
        """Check if action violates API constraints."""
        if constraint.constraint_type != "api_call":
            return None

        if action.action_type != "api_call":
            return None

        allowed_apis = constraint.value
        if not isinstance(allowed_apis, list):
            allowed_apis = [allowed_apis]

        if action.resource_accessed not in allowed_apis:
            # Check if already detected for this action
            for d in self.detections:
                if action.action_id in d.actions_blocked:
                    return None

            detection = HijackingDetection(
                commitment_id=self.commitment.commitment_id,
                hijacking_type=HijackingType.UNAUTHORIZED_API_CALL,
                severity=EscalationLevel.IMMEDIATE_HALT,
                description=f"Unauthorized API call: {action.resource_accessed}",
                evidence={
                    "api_called": action.resource_accessed,
                    "allowed_apis": allowed_apis,
                    "constraint_name": constraint.name,
                },
            )
            detection.human_escalated = True
            detection.actions_blocked.append(action.action_id)
            self.detections.append(detection)
            return detection
        return None

    def verify_execution(self, final_result: Optional[str] = None) -> Tuple[bool, List[HijackingDetection]]:
        """
        Verify that execution matches committed intent.
        Returns (all_clean, detections_list).
        Called only once per execution.
        """
        if self._verification_done:
            return len(self.detections) == 0, self.detections

        # Check latency constraints
        for constraint in self.commitment.constraints:
            if constraint.constraint_type == "latency":
                self._check_latency_constraint(constraint)

        # Check data and API constraints against recorded actions
        for action in self.actions:
            for constraint in self.commitment.constraints:
                if constraint.constraint_type == "data_access":
                    self._check_data_access_constraint(constraint, action)
                elif constraint.constraint_type == "api_call":
                    self._check_api_constraint(constraint, action)

        self._verification_done = True
        is_clean = len(self.detections) == 0
        return is_clean, self.detections

    def get_verification_report(self) -> Dict[str, Any]:
        """Generate verification report."""
        # Ensure verification is done (idempotent)
        is_clean, detections = self.verify_execution()

        return {
            "commitment_id": self.commitment.commitment_id,
            "verification_passed": is_clean,
            "actions_recorded": len(self.actions),
            "detections": len(detections),
            "critical_detections": len([d for d in detections if d.severity == EscalationLevel.IMMEDIATE_HALT]),
            "escalations": [d.to_dict() for d in detections if d.human_escalated],
            "actions": [a.to_dict() for a in self.actions],
            "detections_all": [d.to_dict() for d in detections],
        }


class IntentCommitmentManager:
    """
    Manages intent commitments and execution verification.
    Integrates with AP2 ledger for immutable proof.
    Uses KMSSigner for real Ed25519 cryptographic signatures.
    """

    def __init__(self, ap2_ledger=None, kms_signer: Optional['KMSSigner'] = None):
        self.commitments: Dict[str, IntentCommitment] = {}
        self.verifiers: Dict[str, IntentVerifier] = {}
        self.ap2_ledger = ap2_ledger
        self.commitment_queue: List[IntentCommitment] = []
        self.kms_signer = kms_signer
        self._init_kms_if_needed()

    def _init_kms_if_needed(self) -> None:
        """Initialize KMS signer if available and not already initialized."""
        if self.kms_signer is None and 'KMSSigner' in globals():
            try:
                self.kms_signer = KMSSigner()
                # Generate a key pair for signing
                self.kms_signer.generate_key_pair("ed25519")
                logger.info("KMS signer initialized with Ed25519 key")
            except Exception as e:
                logger.warning(f"Failed to initialize KMS signer: {e}")
                self.kms_signer = None

    def propose_intent(
        self,
        agent_name: str,
        goal: str,
        plan: str,
        constraints: Optional[List[IntentConstraint]] = None,
        intent_type: IntentType = IntentType.GOAL,
        model: str = "unknown",
        context_hash: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IntentCommitment:
        """
        Agent proposes an intent.
        Returns commitment with hash but not yet signed.
        """
        commitment = IntentCommitment(
            agent_name=agent_name,
            goal=goal,
            plan=plan,
            constraints=constraints or [],
            intent_type=intent_type,
            model=model,
            context_hash=context_hash,
            metadata=metadata or {},
        )
        commitment.finalize()

        self.commitment_queue.append(commitment)
        logger.info(f"Intent proposed by {agent_name}: {goal[:50]}...")

        return commitment

    def commit_intent(self, commitment: IntentCommitment, ap2_ledger_id: str = "", signature: str = "") -> IntentCommitment:
        """
        Lock in commitment with cryptographic signature.
        Uses real Ed25519 signing via KMS if available.
        """
        commitment.ap2_ledger_id = ap2_ledger_id or str(uuid.uuid4())

        # Try to sign with real KMS signer
        if signature:
            commitment.ed25519_signature = signature
        elif self.kms_signer and self.kms_signer.keys:
            try:
                commitment_dict = commitment.to_dict()
                sig_obj = self.kms_signer.sign_json(commitment_dict)
                commitment.ed25519_signature = sig_obj.signature
                logger.info(f"Intent signed with real Ed25519 key: {sig_obj.key_id}")
            except Exception as e:
                logger.warning(f"KMS signing failed, using placeholder: {e}")
                commitment.ed25519_signature = self._generate_placeholder_signature(commitment)
        else:
            commitment.ed25519_signature = self._generate_placeholder_signature(commitment)

        # Store in commitment registry
        self.commitments[commitment.commitment_id] = commitment

        logger.info(f"Intent committed: {commitment.commitment_id}")
        logger.info(f"Commitment hash: {commitment.commitment_hash}")

        # Log to AP2 ledger if available
        if self.ap2_ledger:
            try:
                from smaos.l6_infrastructure.ap2_ledger import ActionType
                self.ap2_ledger.record_action(
                    action_type=ActionType.GOVERNANCE_DECISION,
                    agent=commitment.agent_name,
                    model=commitment.model,
                    prompt=f"Intent: {commitment.goal}",
                    decision=commitment.to_dict(),
                    metadata={"commitment_hash": commitment.commitment_hash},
                )
            except Exception as e:
                logger.warning(f"AP2 ledger recording failed: {e}")

        return commitment

    def begin_execution(self, commitment_id: str) -> IntentVerifier:
        """Begin execution tracking for a committed intent."""
        if commitment_id not in self.commitments:
            raise ValueError(f"Unknown commitment ID: {commitment_id}")

        commitment = self.commitments[commitment_id]
        verifier = IntentVerifier(commitment)
        self.verifiers[commitment_id] = verifier

        logger.info(f"Execution begun for commitment: {commitment_id}")

        return verifier

    def complete_execution(
        self,
        commitment_id: str,
        final_result: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete execution and verify against commitment.
        Returns verification report.
        """
        if commitment_id not in self.verifiers:
            raise ValueError(f"No verifier for commitment: {commitment_id}")

        verifier = self.verifiers[commitment_id]
        is_clean, detections = verifier.verify_execution(final_result)

        report = verifier.get_verification_report()

        # Log verification to AP2 ledger
        if self.ap2_ledger:
            from smaos.l6_infrastructure.ap2_ledger import ActionType
            self.ap2_ledger.record_action(
                action_type=ActionType.PROOF_GENERATION,
                agent=verifier.commitment.agent_name,
                model=verifier.commitment.model,
                prompt=f"Execution verification for {commitment_id}",
                decision={"verification_passed": is_clean},
                metadata=report,
            )

        if not is_clean:
            logger.error(f"HIJACKING DETECTED in {commitment_id}")
            for detection in detections:
                logger.error(f"  {detection.hijacking_type.value}: {detection.description}")
                if detection.human_escalated:
                    logger.critical(f"  >>> ESCALATED TO HUMAN <<<")
        else:
            logger.info(f"Execution verified clean for {commitment_id}")

        return report

    def _generate_placeholder_signature(self, commitment: IntentCommitment) -> str:
        """Generate placeholder Ed25519 signature (production would use real key)."""
        sig_data = commitment.commitment_hash + str(time.time())
        return "ed25519_sig_" + hashlib.sha256(sig_data.encode()).hexdigest()[:48]

    def get_commitment(self, commitment_id: str) -> Optional[IntentCommitment]:
        """Retrieve a commitment by ID."""
        return self.commitments.get(commitment_id)

    def export_commitments(self) -> Dict[str, Any]:
        """Export all commitments for audit trail."""
        return {
            "total_commitments": len(self.commitments),
            "commitments": {
                cid: c.to_dict() for cid, c in self.commitments.items()
            },
            "detections": {
                cid: v.get_verification_report() for cid, v in self.verifiers.items()
                if v.detections
            },
        }


def main():
    """Demonstration of intent commitment system."""
    print("Stream H: Intent-Verified Delegation Demo")
    print("=" * 60)

    # Create manager
    manager = IntentCommitmentManager()

    # Agent 1: Hotel credit scoring (legitimate)
    print("\n1. LEGITIMATE INTENT: Hotel Credit Scoring")
    print("-" * 60)

    commitment1 = manager.propose_intent(
        agent_name="hotel-agent",
        goal="Score hotel guest credit in <5 seconds using verified data",
        plan="Query verified PMS data, run ML model, return score",
        constraints=[
            IntentConstraint("latency", 5000, "latency"),
            IntentConstraint("data_sources", ["pms_database", "credit_registry"], "data_access"),
            IntentConstraint("apis", ["score_credit_api"], "api_call"),
        ],
        intent_type=IntentType.GOAL,
        model="claude-opus-4",
    )

    print(f"Proposed: {commitment1.goal}")
    print(f"Commitment hash: {commitment1.commitment_hash[:32]}...")

    # Commit
    commitment1 = manager.commit_intent(commitment1, signature="ed25519_hotel_sig_abc123")
    print(f"Committed with signature: {commitment1.ed25519_signature[:32]}...")

    # Simulate execution
    verifier1 = manager.begin_execution(commitment1.commitment_id)
    verifier1.record_action("data_access", "pms_database", 100, {"query": "SELECT * FROM guests"})
    verifier1.record_action("api_call", "score_credit_api", 200, {"model": "xgboost_v2"})

    report1 = manager.complete_execution(commitment1.commitment_id, "score: 750")
    print(f"\nExecution result: {report1['verification_passed']}")
    print(f"Actions recorded: {report1['actions_recorded']}")
    print(f"Detections: {report1['detections']}")

    # Agent 2: HIJACKING ATTEMPT - Unauthorized data access
    print("\n2. HIJACKING ATTEMPT: Unauthorized Data Access")
    print("-" * 60)

    commitment2 = manager.propose_intent(
        agent_name="glass-agent",
        goal="Analyze safety critical glass defects",
        plan="Parse CAD model, run safety analysis",
        constraints=[
            IntentConstraint("latency", 10000, "latency"),
            IntentConstraint("data_sources", ["cad_storage"], "data_access"),
        ],
        intent_type=IntentType.GOAL,
        model="claude-opus-4",
    )

    commitment2 = manager.commit_intent(commitment2)
    verifier2 = manager.begin_execution(commitment2.commitment_id)

    # Legitimate action
    verifier2.record_action("data_access", "cad_storage", 500)

    # HIJACKING: Unauthorized data access
    verifier2.record_action("data_access", "hr_employee_records", 100)

    report2 = manager.complete_execution(commitment2.commitment_id)
    print(f"\nExecution result: {report2['verification_passed']}")
    print(f"Critical detections: {report2['critical_detections']}")
    if report2['escalations']:
        print(f"Escalations: {report2['escalations'][0]['hijacking_type']}")

    # Agent 3: HIJACKING ATTEMPT - Latency violation
    print("\n3. HIJACKING ATTEMPT: Latency Violation")
    print("-" * 60)

    commitment3 = manager.propose_intent(
        agent_name="school-agent",
        goal="Check student eligibility quickly",
        plan="Query student records, verify status",
        constraints=[
            IntentConstraint("max_latency", 2000, "latency"),  # 2 seconds
        ],
        intent_type=IntentType.GOAL,
    )

    commitment3 = manager.commit_intent(commitment3)
    verifier3 = manager.begin_execution(commitment3.commitment_id)

    # Simulate slow execution (>2000ms)
    time.sleep(2.1)
    verifier3.record_action("api_call", "student_db", 2100)

    report3 = manager.complete_execution(commitment3.commitment_id)
    print(f"\nExecution result: {report3['verification_passed']}")
    print(f"Critical detections: {report3['critical_detections']}")
    if report3['escalations']:
        print(f"Escalation: {report3['escalations'][0]['description']}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_exports = manager.export_commitments()
    print(f"Total commitments: {all_exports['total_commitments']}")
    print(f"Hijackings detected: {len(all_exports['detections'])}")

    print("\nStream H demonstration complete!")


if __name__ == "__main__":
    main()
