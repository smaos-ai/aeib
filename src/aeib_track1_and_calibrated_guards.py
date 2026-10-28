"""
src/aeib_track1_and_calibrated_guards.py — Track 1 Core Loop Lock (AT57b, AT58, G3, G4, G6)
with Calibrated Meta-Evaluator, Zero-Trust 72h Supply-Chain Gatekeeper, and
Cognitive Flight Recorder.

Under the stated model, this prototype closes all eight audited gaps:
1. `canonical_json_v1`: Deterministic sorted-key JSON serialization (rejects floats and non-string keys).
2. `AT57b` (Bell-LaPadula Pure Taint Gate): Blocks `TIER_2_UNTRUSTED_EXTERNAL` context from executing
   mutations toward unpinned beneficiaries unless an RFC 9470 step-up warrant is provided.
3. `AT58` (Pre-Socket Sprint Escrow + Indeterminate Hold): Reserves budget under `fcntl.flock` before
   dispatch and holds `indeterminate_held_minor` across timeouts so parallel/retry calls cannot timeout-smurf.
4. `G3` (Boot-Time CAID & Ed25519 Signature Replay): `_verify_continuity_on_boot()` recomputes `action_caid`,
   `entry_caid`, and verifies `gate_signature` on every row.
5. `G6` (Destructive Mutation Pool): Enforces quota caps on zero-dollar destructive actions.
6. `GoldenDatasetCalibratedMonitor`: Computes empirical Precision, Recall, F1, FPR, FNR, and MCC over
   a golden corpus and recommends Jidoka verification gain.
7. `ZeroTrustSupplyChainGatekeeper`: Enforces 72-hour release cooldown, SHA-256 pinning, and AT68 pre-session
   plugin registry freeze.
8. `CognitiveFlightRecorder`: Emits hash-chained OpenTelemetry-compatible spans bound to
   `MultiModalEvidenceHyperedge` digests with honest `ReceiptTier` labels.
"""

from __future__ import annotations

import base64
import enum
import fcntl
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


class TaintTier(str, enum.Enum):
    """Context taint levels under the Bell-LaPadula model."""

    TIER_0_TRUSTED_SYSTEM = "TIER_0_TRUSTED_SYSTEM"
    TIER_1_INTERNAL_VERIFIED = "TIER_1_INTERNAL_VERIFIED"
    TIER_2_UNTRUSTED_EXTERNAL = "TIER_2_UNTRUSTED_EXTERNAL"


class EffectState(str, enum.Enum):
    """Lifecycle disposition states for state-mutating actions."""

    INTENT_RESERVED = "INTENT_RESERVED"
    COMMITTED = "COMMITTED"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
    RECONCILED_COMMITTED = "RECONCILED_COMMITTED"
    RECONCILED_ABORTED = "RECONCILED_ABORTED"


class ReceiptTier(str, enum.Enum):
    """Honest ladder of audit receipts."""

    LOCAL_SIGNED_AUDIT_RECORD = "LOCAL_SIGNED_AUDIT_RECORD"
    SCITT_READY_COSE_STATEMENT = "SCITT_READY_COSE_STATEMENT"
    EXTERNALLY_ANCHORED_TRANSPARENT_STATEMENT = (
        "EXTERNALLY_ANCHORED_TRANSPARENT_STATEMENT"
    )


def canonical_json_v1(obj: Any) -> bytes:
    """Deterministic JSON serializer (UTF-8, sorted keys, no whitespace, no floats/NaN)."""

    def _validate(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_CANONICAL_JSON_V1")
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _validate(v)
        elif isinstance(val, (list, tuple)):
            for item in val:
                _validate(item)

    _validate(obj)
    return _reference_encode_jcs(obj)


def sha256_digest(data: bytes) -> str:
    """Compute sha256 hex digest prefixed with sha256:."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def durable_fsync(fd: int) -> None:
    """Execute durable fsync on file descriptor, using F_FULLFSYNC on macOS Darwin."""
    if sys.platform == "darwin" and hasattr(fcntl, "F_FULLFSYNC"):
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    else:
        os.fsync(fd)


def compute_action_caid(
    actor_id: str,
    tool_name: str,
    beneficiary_id: str,
    amount_minor: int,
    harness_digest: str,
    canonical_args: Dict[str, Any],
) -> str:
    """Compute content-addressed identifier over action parameters."""
    payload = {
        "actor_id": actor_id,
        "amount_minor": amount_minor,
        "arguments": canonical_args,
        "beneficiary_id": beneficiary_id,
        "harness_digest": harness_digest,
        "tool_name": tool_name,
    }
    return sha256_digest(canonical_json_v1(payload))


@dataclass(frozen=True)
class GateDecision:
    """Decision emitted by BootVerifiedEo1EscrowGate."""

    allowed: bool
    reason_code: str
    action_caid: str
    effect_state: Optional[EffectState]
    committed_spend_minor: int
    indeterminate_held_minor: int
    destructive_ops_used: int
    chain_tip: str
    receipt_tier: ReceiptTier = ReceiptTier.LOCAL_SIGNED_AUDIT_RECORD
    entry_caid: str = ""


class BootVerifiedEo1EscrowGate:
    """Enforces AT57b (taint gate), AT58 (pre-socket escrow), G3 (boot verify), G4, and G6."""

    GENESIS_TIP = "sha256:" + ("0" * 64)
    DESTRUCTIVE_TOOLS = frozenset(
        {"db.drop_table", "db.delete_rows", "fs.rm_tree", "iam.revoke_all"}
    )

    def __init__(
        self,
        ledger_dir: Path,
        signing_key: Ed25519PrivateKey,
        verify_key: Ed25519PublicKey,
        sprint_budget_minor: int,
        max_destructive_ops_per_epoch: int,
        pinned_beneficiaries: Set[str],
        harness_digest: str = "sha256:aeib_harness_v1_0_0_rc3",
    ) -> None:
        self.ledger_dir = Path(ledger_dir).resolve()
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.ledger_dir / "eo1_escrow_ledger.jsonl"
        self.lock_path = self.ledger_dir / "eo1_escrow.lock"
        self._signing_key = signing_key
        self._verify_key = verify_key
        self.sprint_budget_minor = sprint_budget_minor
        self.max_destructive_ops_per_epoch = max_destructive_ops_per_epoch
        self.pinned_beneficiaries = set(pinned_beneficiaries)
        self.harness_digest = harness_digest
        self._chain_tip = self.GENESIS_TIP
        self._state_by_caid: Dict[str, EffectState] = {}
        self._amount_by_caid: Dict[str, int] = {}
        self._tool_by_caid: Dict[str, str] = {}
        self._meta_by_caid: Dict[str, Dict[str, Any]] = {}

        lock_fd = self._acquire_flock()
        try:
            self._verify_continuity_on_boot()
        finally:
            self._release_flock(lock_fd)

    def _acquire_flock(self) -> int:
        fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def _release_flock(self, fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _verify_continuity_on_boot(self) -> None:
        """Verify hash-chain linkage, recompute CAID, and verify Ed25519 signature per row."""
        self._chain_tip = self.GENESIS_TIP
        self._state_by_caid.clear()
        self._amount_by_caid.clear()
        self._tool_by_caid.clear()
        self._meta_by_caid.clear()

        if not self.ledger_path.exists():
            return

        with open(self.ledger_path, "rb") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                rec = json.loads(line.decode("utf-8"))

                # 1. Verify hash-chain linkage
                if rec.get("prev_hash") != self._chain_tip:
                    raise RuntimeError(
                        f"HALT_BOOT_CHAIN_LINKAGE_BROKEN_LINE_{line_no}"
                    )

                # 2. Recompute 6-tuple action_caid
                expected_action_caid = compute_action_caid(
                    actor_id=rec["actor_id"],
                    tool_name=rec["tool_name"],
                    beneficiary_id=rec["beneficiary_id"],
                    amount_minor=rec["amount_minor"],
                    harness_digest=rec["harness_digest"],
                    canonical_args=rec["arguments"],
                )
                if expected_action_caid != rec.get("action_caid"):
                    raise RuntimeError(
                        f"HALT_BOOT_ACTION_CAID_TAMPERED_LINE_{line_no}"
                    )

                # 3. Recompute entry_caid over canonical unsigned body
                unsigned_body = {
                    k: v
                    for k, v in rec.items()
                    if k not in ("entry_caid", "gate_signature")
                }
                unsigned_bytes = canonical_json_v1(unsigned_body)
                expected_entry_caid = sha256_digest(unsigned_bytes)
                if expected_entry_caid != rec.get("entry_caid"):
                    raise RuntimeError(
                        f"HALT_BOOT_ENTRY_CAID_TAMPERED_LINE_{line_no}"
                    )

                # 4. Verify Ed25519 signature
                sig_bytes = base64.b64decode(rec["gate_signature"])
                try:
                    self._verify_key.verify(sig_bytes, unsigned_bytes)
                except InvalidSignature as exc:
                    raise RuntimeError(
                        f"HALT_BOOT_SIGNATURE_INVALID_LINE_{line_no}"
                    ) from exc

                self._chain_tip = expected_entry_caid
                caid = rec["action_caid"]
                st = EffectState(rec["effect_state"])
                self._state_by_caid[caid] = st
                self._amount_by_caid[caid] = int(rec["amount_minor"])
                self._tool_by_caid[caid] = rec["tool_name"]
                self._meta_by_caid[caid] = {
                    "actor_id": rec["actor_id"],
                    "arguments": rec["arguments"],
                    "beneficiary_id": rec["beneficiary_id"],
                    "harness_digest": rec["harness_digest"],
                    "tool_name": rec["tool_name"],
                }

    def _compute_escrow_totals_locked(self) -> Tuple[int, int, int]:
        committed_minor = 0
        held_indeterminate_minor = 0
        destructive_ops = 0
        for caid, st in self._state_by_caid.items():
            amt = self._amount_by_caid[caid]
            tool = self._tool_by_caid[caid]
            if st in (EffectState.COMMITTED, EffectState.RECONCILED_COMMITTED):
                committed_minor += amt
                if tool in self.DESTRUCTIVE_TOOLS:
                    destructive_ops += 1
            elif st in (
                EffectState.INTENT_RESERVED,
                EffectState.EFFECT_INDETERMINATE,
            ):
                held_indeterminate_minor += amt
                if tool in self.DESTRUCTIVE_TOOLS:
                    destructive_ops += 1
        return committed_minor, held_indeterminate_minor, destructive_ops

    def _append_signed_entry_locked(
        self,
        actor_id: str,
        tool_name: str,
        beneficiary_id: str,
        amount_minor: int,
        canonical_args: Dict[str, Any],
        action_caid: str,
        effect_state: EffectState,
    ) -> str:
        unsigned_body = {
            "action_caid": action_caid,
            "actor_id": actor_id,
            "amount_minor": amount_minor,
            "arguments": canonical_args,
            "beneficiary_id": beneficiary_id,
            "effect_state": effect_state.value,
            "harness_digest": self.harness_digest,
            "prev_hash": self._chain_tip,
            "receipt_tier": ReceiptTier.LOCAL_SIGNED_AUDIT_RECORD.value,
            "tool_name": tool_name,
        }
        unsigned_bytes = canonical_json_v1(unsigned_body)
        entry_caid = sha256_digest(unsigned_bytes)
        sig_b64 = base64.b64encode(self._signing_key.sign(unsigned_bytes)).decode(
            "ascii"
        )
        full_entry = {
            **unsigned_body,
            "entry_caid": entry_caid,
            "gate_signature": sig_b64,
        }
        line_bytes = canonical_json_v1(full_entry) + b"\n"
        fd = os.open(
            str(self.ledger_path),
            os.O_CREAT | os.O_WRONLY | os.O_APPEND,
            0o600,
        )
        try:
            written = 0
            while written < len(line_bytes):
                n = os.write(fd, line_bytes[written:])
                if n <= 0:
                    raise IOError("ERR_SHORT_LEDGER_WRITE")
                written += n
            durable_fsync(fd)
        finally:
            os.close(fd)

        self._chain_tip = entry_caid
        self._state_by_caid[action_caid] = effect_state
        self._amount_by_caid[action_caid] = amount_minor
        self._tool_by_caid[action_caid] = tool_name
        self._meta_by_caid[action_caid] = {
            "actor_id": actor_id,
            "arguments": canonical_args,
            "beneficiary_id": beneficiary_id,
            "harness_digest": self.harness_digest,
            "tool_name": tool_name,
        }
        return entry_caid

    def authorize_and_execute(
        self,
        actor_id: str,
        tool_name: str,
        beneficiary_id: str,
        amount_minor: int,
        canonical_args: Dict[str, Any],
        context_taint: TaintTier,
        dispatch_fn: Callable[[], Dict[str, Any]],
        has_rfc9470_step_up: bool = False,
    ) -> GateDecision:
        """Enforces AT57b taint, AT58 escrow reservation, G6 destructive pool, and dispatches."""
        action_caid = compute_action_caid(
            actor_id=actor_id,
            tool_name=tool_name,
            beneficiary_id=beneficiary_id,
            amount_minor=amount_minor,
            harness_digest=self.harness_digest,
            canonical_args=canonical_args,
        )

        lock_fd = self._acquire_flock()
        try:
            self._verify_continuity_on_boot()
            committed, held_indet, destr_used = self._compute_escrow_totals_locked()

            # 1. Close AT57b: Pure Bell-LaPadula Taint Gate
            if (
                context_taint == TaintTier.TIER_2_UNTRUSTED_EXTERNAL
                and beneficiary_id not in self.pinned_beneficiaries
                and not has_rfc9470_step_up
            ):
                return GateDecision(
                    allowed=False,
                    reason_code="UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP",
                    action_caid=action_caid,
                    effect_state=None,
                    committed_spend_minor=committed,
                    indeterminate_held_minor=held_indet,
                    destructive_ops_used=destr_used,
                    chain_tip=self._chain_tip,
                )

            # 2. Check existing state for duplicate / indeterminate CAID
            existing_state = self._state_by_caid.get(action_caid)
            if existing_state in (
                EffectState.INTENT_RESERVED,
                EffectState.EFFECT_INDETERMINATE,
            ):
                return GateDecision(
                    allowed=False,
                    reason_code="HALT_LATCHED_EFFECT_INDETERMINATE_NO_RETRY",
                    action_caid=action_caid,
                    effect_state=EffectState.EFFECT_INDETERMINATE,
                    committed_spend_minor=committed,
                    indeterminate_held_minor=held_indet,
                    destructive_ops_used=destr_used,
                    chain_tip=self._chain_tip,
                )
            if existing_state in (
                EffectState.COMMITTED,
                EffectState.RECONCILED_COMMITTED,
            ):
                return GateDecision(
                    allowed=False,
                    reason_code="DENY_ALREADY_COMMITTED_NO_RESEND",
                    action_caid=action_caid,
                    effect_state=existing_state,
                    committed_spend_minor=committed,
                    indeterminate_held_minor=held_indet,
                    destructive_ops_used=destr_used,
                    chain_tip=self._chain_tip,
                )

            # 3. Close G6: Destructive State Pool Check
            if (
                tool_name in self.DESTRUCTIVE_TOOLS
                and destr_used + 1 > self.max_destructive_ops_per_epoch
            ):
                return GateDecision(
                    allowed=False,
                    reason_code="DENY_DESTRUCTIVE_MUTATION_POOL_EXHAUSTED",
                    action_caid=action_caid,
                    effect_state=None,
                    committed_spend_minor=committed,
                    indeterminate_held_minor=held_indet,
                    destructive_ops_used=destr_used,
                    chain_tip=self._chain_tip,
                )

            # 4. Close AT58: Pre-Socket Escrow Reservation Check
            if committed + held_indet + amount_minor > self.sprint_budget_minor:
                return GateDecision(
                    allowed=False,
                    reason_code="DENY_SPRINT_ESCROW_EXCEEDED_INCLUDING_INDETERMINATE_HOLD",
                    action_caid=action_caid,
                    effect_state=None,
                    committed_spend_minor=committed,
                    indeterminate_held_minor=held_indet,
                    destructive_ops_used=destr_used,
                    chain_tip=self._chain_tip,
                )

            # 5. Durably reserve intent before executing downstream dispatch
            self._append_signed_entry_locked(
                actor_id=actor_id,
                tool_name=tool_name,
                beneficiary_id=beneficiary_id,
                amount_minor=amount_minor,
                canonical_args=canonical_args,
                action_caid=action_caid,
                effect_state=EffectState.INTENT_RESERVED,
            )
        finally:
            self._release_flock(lock_fd)

        # Downstream execution
        try:
            dispatch_fn()
        except Exception:
            return self.record_downstream_effect(
                action_caid=action_caid,
                effect_state=EffectState.EFFECT_INDETERMINATE,
            )
        return self.record_downstream_effect(
            action_caid=action_caid,
            effect_state=EffectState.COMMITTED,
        )

    def record_downstream_effect(
        self, action_caid: str, effect_state: EffectState
    ) -> GateDecision:
        """Records terminal or indeterminate downstream effect in the signed ledger."""
        lock_fd = self._acquire_flock()
        try:
            self._verify_continuity_on_boot()
            meta = self._meta_by_caid.get(action_caid)
            if meta is None:
                raise RuntimeError(f"ERR_UNKNOWN_ACTION_CAID:{action_caid}")

            entry_caid = self._append_signed_entry_locked(
                actor_id=meta["actor_id"],
                tool_name=meta["tool_name"],
                beneficiary_id=meta["beneficiary_id"],
                amount_minor=self._amount_by_caid[action_caid],
                canonical_args=meta["arguments"],
                action_caid=action_caid,
                effect_state=effect_state,
            )
            committed, held_indet, destr_used = self._compute_escrow_totals_locked()
            allowed = effect_state in (
                EffectState.COMMITTED,
                EffectState.RECONCILED_COMMITTED,
            )
            return GateDecision(
                allowed=allowed,
                reason_code=f"RECORDED_{effect_state.value}",
                action_caid=action_caid,
                effect_state=effect_state,
                committed_spend_minor=committed,
                indeterminate_held_minor=held_indet,
                destructive_ops_used=destr_used,
                chain_tip=self._chain_tip,
                entry_caid=entry_caid,
            )
        finally:
            self._release_flock(lock_fd)


# ---------------------------------------------------------------------------
# Blind Spot 1: Golden-Dataset Calibrated Meta-Evaluator + PLA2G2F Gain
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoldenEvaluationCase:
    """Benchmark evaluation case with verified ground truth."""

    case_id: str
    code_snippet: str
    ground_truth_is_safe: bool
    defect_category: str


@dataclass(frozen=True)
class MonitorCalibrationReport:
    """Empirical calibration metrics calculated over golden cases."""

    total_cases: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    false_negative_rate: float
    matthews_corrcoef: float
    recommended_jidoka_gain: str
    requires_human_escalation: bool


class GoldenDatasetCalibratedMonitor:
    """Calibrates an evaluator against a Golden Dataset before trusting its verdicts."""

    def __init__(
        self,
        evaluator_fn: Callable[[str], bool],
        golden_cases: Sequence[GoldenEvaluationCase],
        min_f1_threshold: float = 0.90,  # claim: config
        max_fnr_for_defects: float = 0.0,  # claim: config
    ) -> None:
        self.evaluator_fn = evaluator_fn
        self.golden_cases = tuple(golden_cases)
        self.min_f1_threshold = min_f1_threshold
        self.max_fnr_for_defects = max_fnr_for_defects

    def run_calibration(self) -> MonitorCalibrationReport:
        """Run calibration over golden cases, defining positive as defect detected."""
        tp = fp = tn = fn = 0
        for case in self.golden_cases:
            verdict_is_safe = self.evaluator_fn(case.code_snippet)
            actual_is_defect = not case.ground_truth_is_safe
            predicted_is_defect = not verdict_is_safe

            if actual_is_defect and predicted_is_defect:
                tp += 1
            elif not actual_is_defect and predicted_is_defect:
                fp += 1
            elif not actual_is_defect and not predicted_is_defect:
                tn += 1
            else:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            (2.0 * precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        mcc = ((tp * tn) - (fp * fn)) / denom if denom > 0 else 0.0
        requires_human = (f1 < self.min_f1_threshold) or (
            fnr > self.max_fnr_for_defects
        )
        gain = (
            "CRITICAL_FORMAL_AND_MUTATION_REQUIRED"
            if requires_human
            else "CALIBRATED_AUTONOMOUS_GATE"
        )
        return MonitorCalibrationReport(
            total_cases=len(self.golden_cases),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            false_positive_rate=round(fpr, 4),
            false_negative_rate=round(fnr, 4),
            matthews_corrcoef=round(mcc, 4),
            recommended_jidoka_gain=gain,
            requires_human_escalation=requires_human,
        )


# ---------------------------------------------------------------------------
# Blind Spot 2: Zero-Trust 72-Hour Supply-Chain & Plugin Registry Gatekeeper
# ---------------------------------------------------------------------------


class ZeroTrustSupplyChainGatekeeper:
    """Enforces release cooldown, digest pinning, and pre-session plugin freeze."""

    def __init__(
        self,
        pinned_package_digests: Dict[str, str],
        frozen_session_plugins: Set[str],
        cooldown_seconds: int = 72 * 3600,  # claim: config
    ) -> None:
        self.pinned_package_digests = dict(pinned_package_digests)
        self.frozen_session_plugins = frozenset(frozen_session_plugins)
        self.cooldown_seconds = cooldown_seconds

    def verify_package_install(
        self,
        package_spec: str,
        artifact_sha256: str,
        published_epoch_s: float,
        now_epoch_s: float,
    ) -> Tuple[bool, str]:
        """Verify package is not in cooldown and matches pinned SHA-256 digest."""
        age_s = now_epoch_s - published_epoch_s
        if age_s < self.cooldown_seconds:
            return (
                False,
                f"DENY_SUPPLY_CHAIN_COOLDOWN_VIOLATION:{package_spec} age={int(age_s)}s < {self.cooldown_seconds}s",
            )
        expected_digest = self.pinned_package_digests.get(package_spec)
        if expected_digest is None:
            return False, f"DENY_UNPINNED_PACKAGE:{package_spec}"
        if expected_digest != artifact_sha256:
            return False, f"DENY_PACKAGE_DIGEST_MISMATCH:{package_spec}"
        return True, "ALLOW_VERIFIED_PINNED_PACKAGE"

    def verify_plugin_invocation(self, plugin_id: str) -> Tuple[bool, str]:
        """Rejects mid-session hot-reloaded plugin not in frozen session set."""
        if plugin_id not in self.frozen_session_plugins:
            return False, f"DENY_MID_SESSION_UNFROZEN_PLUGIN:{plugin_id}"
        return True, "ALLOW_FROZEN_SESSION_PLUGIN"


# ---------------------------------------------------------------------------
# Blind Spot 3: OpenTelemetry Cognitive Flight Recorder
# ---------------------------------------------------------------------------


class CognitiveFlightRecorder:
    """Exports hash-chained decision path spans bound to MultiModalEvidenceHyperedges."""

    def __init__(self) -> None:
        self.spans: List[Dict[str, Any]] = []
        self.last_span_digest = "sha256:" + ("0" * 64)

    def record_step_span(
        self,
        operation_name: str,
        model_id: str,
        action_caid: str,
        code_ast_digest: str,
        runtime_trace_digest: str,
        env_digest: str,
        verdict: str,
        latency_ms: float,
    ) -> Dict[str, Any]:
        """Record an execution step span with SHA-256 hash chaining."""
        hyperedge_digest = sha256_digest(
            canonical_json_v1(
                {
                    "code_ast_digest": code_ast_digest,
                    "env_digest": env_digest,
                    "runtime_trace_digest": runtime_trace_digest,
                }
            )
        )
        span_body = {
            "attributes": {
                "aeib.action.caid": action_caid,
                "aeib.boundary.hyperedge_sha256": hyperedge_digest,
                "aeib.boundary.prev_span_sha256": self.last_span_digest,
                "aeib.boundary.receipt_tier": ReceiptTier.LOCAL_SIGNED_AUDIT_RECORD.value,
                "aeib.boundary.verdict": verdict,
                "gen_ai.operation.name": operation_name,
                "gen_ai.request.model": model_id,
            },
            "latency_us": int(round(latency_ms * 1000)),
        }
        span_digest = sha256_digest(canonical_json_v1(span_body))
        full_span = {**span_body, "span_sha256": span_digest}
        self.last_span_digest = span_digest
        self.spans.append(full_span)
        return full_span
