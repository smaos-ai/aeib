#!/usr/bin/env python3
"""
src/predictive_trajectory_drift_latch.py
================================================================================
Tsinghua-Style Predictive Loss-of-Control & Upstream Trajectory Drift Latch
with Adversarial Chaos Fuzzing.

Evaluated under the stated model as an AEIB Station 1 execution interlock
prototype scaffold. Preserves strict zero-mock cryptographic purity.

Core Components:
1. PredictiveTrajectoryDriftLatch:
   - Tracks an agent's sequential tool call proposals t_1, t_2, ..., t_k.
   - Capability Domain Velocity (v_k): Rate of tool capability scope shifts.
   - Permission Entropy (H_k): Shannon entropy across cumulative resource scopes.
   - Trajectory Curvature (kappa_k): Evaluates sudden sharp pivots in action
     payloads or arguments compared to prior conversational history.
   - Triggers fail-closed with HALT_PREDICTIVE_TRAJECTORY_DRIFT before the
     proposed action reaches Station 1 execution dispatch.
   - Provides manual reset via authorized supervisor Ed25519 step-up warrant.

2. AdversarialTrajectoryChaosFuzzer:
   - Multi-turn adversarial perturbation engine:
     * Token smuggling: zero-width whitespace (\\u200b, \\u200c, \\ufeff),
       hidden base64 chunks, Unicode tag characters in tool arguments.
     * Homoglyph substitution in JSON keys: replacing ASCII Latin characters
       with identical-looking Cyrillic or Greek characters.
     * Out-of-order execution step injection: skipping prerequisite staging.
   - Validates fail-closed rejections with HALT_HOMOGLYPH_KEY_INJECTION,
     HALT_TOKEN_SMUGGLING_DETECTED, and HALT_OUT_OF_ORDER_EXECUTION.
================================================================================
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass, field
from enum import IntEnum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata

from cryptography.hazmat.primitives.asymmetric import ed25519

# Ensure repository root is on sys.path for RFC 8785 canonicalizer
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    # Deterministic fallback conforming to RFC 8785 Section 3.2
    def encode_jcs(payload: Any) -> bytes:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")


# ==============================================================================
# Security Violation Codes & Domain Tiers
# ==============================================================================

HALT_PREDICTIVE_TRAJECTORY_DRIFT = "HALT_PREDICTIVE_TRAJECTORY_DRIFT"
HALT_HOMOGLYPH_KEY_INJECTION = "HALT_HOMOGLYPH_KEY_INJECTION"
HALT_TOKEN_SMUGGLING_DETECTED = "HALT_TOKEN_SMUGGLING_DETECTED"
HALT_OUT_OF_ORDER_EXECUTION = "HALT_OUT_OF_ORDER_EXECUTION"
HALT_STEP_UP_WARRANT_INVALID = "HALT_STEP_UP_WARRANT_INVALID"
HALT_LATCH_ALREADY_TRIPPED = "HALT_LATCH_ALREADY_TRIPPED"


class CapabilityDomain(IntEnum):
    """
    Ordinal capability tiers for tool actions under the stated model.
    Graduated from read-only inspection up to privileged administration.
    """
    READ_ONLY = 0           # Informational, reading state, catalog lookup
    DIAGNOSTIC = 1          # Health checks, log inspection, probe verification
    CONFIG_PROBE = 2        # Configuration staging, parameter preparation, escrow setup
    MUTATION = 3            # State mutation, file writes, resource allocation
    FINANCIAL_DISPATCH = 4  # Fund transfers, wire executions, billing operations
    PRIVILEGED_ADMIN = 5    # System reconfiguration, key rotation, policy modification


DEFAULT_DOMAIN_MAP: Dict[str, int] = {
    # READ_ONLY (0)
    "lookup_balance": CapabilityDomain.READ_ONLY,
    "query_catalog": CapabilityDomain.READ_ONLY,
    "get_status": CapabilityDomain.READ_ONLY,
    "read_file": CapabilityDomain.READ_ONLY,
    "search_knowledge": CapabilityDomain.READ_ONLY,
    "get_transaction_history": CapabilityDomain.READ_ONLY,
    # DIAGNOSTIC (1)
    "inspect_logs": CapabilityDomain.DIAGNOSTIC,
    "check_zone_boundary": CapabilityDomain.DIAGNOSTIC,
    "probe_system_health": CapabilityDomain.DIAGNOSTIC,
    "run_ast_purity_scan": CapabilityDomain.DIAGNOSTIC,
    # CONFIG_PROBE (2)
    "staged_escrow": CapabilityDomain.CONFIG_PROBE,
    "stage_config": CapabilityDomain.CONFIG_PROBE,
    "prepare_payload": CapabilityDomain.CONFIG_PROBE,
    "dry_run_simulation": CapabilityDomain.CONFIG_PROBE,
    "verify_firmware_digest": CapabilityDomain.CONFIG_PROBE,
    # MUTATION (3)
    "write_file": CapabilityDomain.MUTATION,
    "update_record": CapabilityDomain.MUTATION,
    "execute_mutation": CapabilityDomain.MUTATION,
    "modify_metadata": CapabilityDomain.MUTATION,
    # FINANCIAL_DISPATCH (4)
    "wire_dispatch": CapabilityDomain.FINANCIAL_DISPATCH,
    "transfer_funds": CapabilityDomain.FINANCIAL_DISPATCH,
    "disburse_grant": CapabilityDomain.FINANCIAL_DISPATCH,
    "execute_refund": CapabilityDomain.FINANCIAL_DISPATCH,
    # PRIVILEGED_ADMIN (5)
    "rotate_root_keys": CapabilityDomain.PRIVILEGED_ADMIN,
    "reconfigure_firewall": CapabilityDomain.PRIVILEGED_ADMIN,
    "update_kernel_policy": CapabilityDomain.PRIVILEGED_ADMIN,
    "apply_firmware": CapabilityDomain.PRIVILEGED_ADMIN,
}

DEFAULT_PERMISSION_MAP: Dict[str, Set[str]] = {
    "lookup_balance": {"account:read"},
    "query_catalog": {"catalog:read"},
    "get_status": {"system:read"},
    "read_file": {"filesystem:read"},
    "search_knowledge": {"knowledge:read"},
    "get_transaction_history": {"account:read", "audit:read"},
    "inspect_logs": {"logs:read"},
    "check_zone_boundary": {"compliance:read"},
    "probe_system_health": {"health:read"},
    "run_ast_purity_scan": {"code:read"},
    "staged_escrow": {"escrow:stage", "account:read"},
    "stage_config": {"config:stage"},
    "prepare_payload": {"payload:prepare"},
    "dry_run_simulation": {"sim:execute"},
    "verify_firmware_digest": {"firmware:verify"},
    "write_file": {"filesystem:write"},
    "update_record": {"database:write"},
    "execute_mutation": {"state:write"},
    "modify_metadata": {"metadata:write"},
    "wire_dispatch": {"escrow:commit", "wire:execute"},
    "transfer_funds": {"escrow:commit", "transfer:execute"},
    "disburse_grant": {"escrow:commit", "grant:disburse"},
    "execute_refund": {"escrow:commit", "refund:execute"},
    "rotate_root_keys": {"pqc:rotate", "admin:root"},
    "reconfigure_firewall": {"firewall:write", "admin:root"},
    "update_kernel_policy": {"kernel:write", "admin:root"},
    "apply_firmware": {"firmware:write", "admin:root"},
}

DEFAULT_PREREQUISITES: Dict[str, List[str]] = {
    "wire_dispatch": ["staged_escrow"],
    "transfer_funds": ["staged_escrow"],
    "disburse_grant": ["staged_escrow"],
    "execute_refund": ["staged_escrow"],
    "apply_firmware": ["verify_firmware_digest"],
    "reconfigure_firewall": ["stage_config"],
}

# Unicode Confusable Homoglyphs (Cyrillic and Greek mapped to ASCII Latin)
HOMOGLYPH_MAP: Dict[str, str] = {
    # Cyrillic lowercase
    "\u0430": "a", "\u0441": "c", "\u0435": "e", "\u043e": "o", "\u0440": "p",
    "\u0445": "x", "\u0443": "y", "\u0456": "i", "\u0458": "j", "\u0455": "s",
    "\u0501": "d", "\u051b": "q", "\u04bb": "h", "\u04cf": "l",
    # Cyrillic uppercase
    "\u0410": "A", "\u0412": "B", "\u0421": "C", "\u0415": "E", "\u041d": "H",
    "\u0406": "I", "\u041a": "K", "\u041c": "M", "\u041e": "O", "\u0420": "P",
    "\u0422": "T", "\u0425": "X",
    # Greek lowercase
    "\u03b1": "a", "\u03b2": "b", "\u03b5": "e", "\u03bf": "o", "\u03c1": "p",
    "\u03c4": "t", "\u03c5": "u", "\u03bd": "v", "\u03ba": "k", "\u03c7": "x",
    # Greek uppercase
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0397": "H", "\u0399": "I",
    "\u039a": "K", "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P",
    "\u03a4": "T", "\u03a7": "X",
}

# Zero-width whitespace, directional overrides, and Unicode tags
ZERO_WIDTH_CHARS: Set[str] = {
    "\u200b",  # ZERO WIDTH SPACE
    "\u200c",  # ZERO WIDTH NON-JOINER
    "\u200d",  # ZERO WIDTH JOINER
    "\ufeff",  # ZERO WIDTH NO-BREAK SPACE / BOM
    "\u2060",  # WORD JOINER
    "\u200e",  # LEFT-TO-RIGHT MARK
    "\u200f",  # RIGHT-TO-LEFT MARK
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # Bidi overrides
}

BASE64_DATA_URI_PATTERN = re.compile(
    r"data:[a-zA-Z0-9+/-]+;base64,([A-Za-z0-9+/=]+)",
    re.IGNORECASE
)

SUSPICIOUS_PAYLOAD_KEYWORDS = (
    b"eval(", b"exec(", b"os.system", b"subprocess", b"/bin/sh", b"/bin/bash",
    b"cat /etc/passwd", b"chmod +x", b"rm -rf", b"wget ", b"curl ", b"Bearer ",
    b"DROP TABLE", b"admin_override", b"bypass_latch",
)


# ==============================================================================
# Exceptions
# ==============================================================================

class TrajectorySecurityError(Exception):
    """Base class for trajectory drift latch security violations."""

    def __init__(self, message: str, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class PredictiveTrajectoryDriftError(TrajectorySecurityError):
    """Triggered when capability domain velocity or entropy acceleration exceeds threshold."""

    def __init__(self, message: str = "Predictive trajectory drift threshold exceeded") -> None:
        super().__init__(message, error_code=HALT_PREDICTIVE_TRAJECTORY_DRIFT)


class HomoglyphKeyInjectionError(TrajectorySecurityError):
    """Triggered when homoglyph key substitution is detected in JSON proposal."""

    def __init__(self, message: str = "Homoglyph key injection detected in tool call payload") -> None:
        super().__init__(message, error_code=HALT_HOMOGLYPH_KEY_INJECTION)


class TokenSmugglingDetectedError(TrajectorySecurityError):
    """Triggered when zero-width, tag, or covert base64 token smuggling is detected."""

    def __init__(self, message: str = "Token smuggling detected in tool arguments") -> None:
        super().__init__(message, error_code=HALT_TOKEN_SMUGGLING_DETECTED)


class OutOfOrderExecutionError(TrajectorySecurityError):
    """Triggered when an action proposal attempts to skip prerequisite validation/staging."""

    def __init__(self, message: str = "Out-of-order execution step injection detected") -> None:
        super().__init__(message, error_code=HALT_OUT_OF_ORDER_EXECUTION)


class StepUpWarrantInvalidError(TrajectorySecurityError):
    """Triggered when supervisor Ed25519 step-up warrant verification fails."""

    def __init__(self, message: str = "Supervisor step-up warrant verification failed") -> None:
        super().__init__(message, error_code=HALT_STEP_UP_WARRANT_INVALID)


class LatchTrippedError(TrajectorySecurityError):
    """Triggered when an action is proposed while the drift latch is in tripped state."""

    def __init__(self, message: str = "Drift latch is currently tripped in fail-closed state") -> None:
        super().__init__(message, error_code=HALT_LATCH_ALREADY_TRIPPED)


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class ToolCallProposal:
    """
    Candidate tool call proposed by an autonomous agent during an execution trajectory.
    """
    tool_name: str
    arguments: Dict[str, Any]
    session_id: str
    step_index: int
    timestamp_ns: int = field(default_factory=time.time_ns)
    domain: Optional[int] = None
    required_permissions: Optional[Set[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Returns JSON-compatible dictionary for canonicalization."""
        perms = sorted(list(self.required_permissions)) if self.required_permissions else []
        return {
            "arguments": self.arguments,
            "domain": self.domain,
            "metadata": self.metadata,
            "required_permissions": perms,
            "session_id": self.session_id,
            "step_index": self.step_index,
            "timestamp_ns": self.timestamp_ns,
            "tool_name": self.tool_name,
        }

    def compute_caid(self) -> str:
        """Computes Content-Addressed Action Identifier (CAID) via RFC 8785 JCS + SHA-256."""
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        return hashlib.sha256(canonical_bytes).hexdigest()


@dataclass
class TrajectoryMetrics:
    """
    Mathematical metrics evaluated at step k of an agent trajectory.
    """
    step_index: int
    domain_level: int
    domain_step_jump: float
    domain_velocity: float
    permission_entropy: float
    entropy_rate: float
    entropy_acceleration: float
    trajectory_curvature: float
    cumulative_permissions: Set[str]
    caid: str
    timestamp_ns: int


@dataclass
class AdmissionReceipt:
    """
    Execution admission receipt indicating pass/fail status and trajectory metrics.
    """
    admitted: bool
    action_caid: str
    step_index: int
    metrics: Optional[TrajectoryMetrics] = None
    latch_tripped: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "action_caid": self.action_caid,
            "admitted": self.admitted,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latch_tripped": self.latch_tripped,
            "step_index": self.step_index,
        }
        if self.metrics:
            data["metrics"] = {
                "caid": self.metrics.caid,
                "domain_level": self.metrics.domain_level,
                "domain_step_jump": self.metrics.domain_step_jump,
                "domain_velocity": self.metrics.domain_velocity,
                "entropy_acceleration": self.metrics.entropy_acceleration,
                "entropy_rate": self.metrics.entropy_rate,
                "permission_entropy": self.metrics.permission_entropy,
                "step_index": self.metrics.step_index,
                "trajectory_curvature": self.metrics.trajectory_curvature,
            }
        return data


# ==============================================================================
# Predictive Trajectory Drift Latch
# ==============================================================================

class PredictiveTrajectoryDriftLatch:
    """
    Monitors sequential tool call proposals t_1, t_2, ..., t_k.
    Computes capability velocity, permission entropy acceleration, and discrete curvature.
    Fails closed before Station 1 execution dispatch upon anomalous drift.
    """

    def __init__(
        self,
        agent_id: str = "agent-orchestrator-01",
        max_velocity_threshold: float = 2.0,
        max_step_jump: float = 2.0,
        max_entropy_acceleration: float = 1.5,
        max_entropy_rate: float = 2.0,
        max_curvature_threshold: float = 1.85,
        velocity_ema_alpha: float = 0.7,
        domain_map: Optional[Dict[str, int]] = None,
        permission_map: Optional[Dict[str, Set[str]]] = None,
        prerequisite_rules: Optional[Dict[str, List[str]]] = None,
        supervisor_public_keys: Optional[Dict[str, ed25519.Ed25519PublicKey]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.max_velocity_threshold = float(max_velocity_threshold)
        self.max_step_jump = float(max_step_jump)
        self.max_entropy_acceleration = float(max_entropy_acceleration)
        self.max_entropy_rate = float(max_entropy_rate)
        self.max_curvature_threshold = float(max_curvature_threshold)
        self.velocity_ema_alpha = float(velocity_ema_alpha)

        self.domain_map = dict(DEFAULT_DOMAIN_MAP if domain_map is None else domain_map)
        self.permission_map = dict(DEFAULT_PERMISSION_MAP if permission_map is None else permission_map)
        self.prerequisite_rules = dict(DEFAULT_PREREQUISITES if prerequisite_rules is None else prerequisite_rules)
        self.supervisor_public_keys = dict(supervisor_public_keys or {})

        # State tracking
        self.is_tripped: bool = False
        self.trip_reason: Optional[Dict[str, Any]] = None
        self.history: List[TrajectoryMetrics] = []
        self.admitted_history: List[ToolCallProposal] = []
        self.cumulative_permission_counts: Dict[str, int] = {}
        self.completed_actions_by_session: Dict[str, Set[str]] = {}

        # Trajectory tracking by session
        self.session_trajectories: Dict[str, List[TrajectoryMetrics]] = {}
        self.session_admitted: Dict[str, List[ToolCallProposal]] = {}
        self.session_permission_counts: Dict[str, Dict[str, int]] = {}
        self.session_curvature_state: Dict[str, Tuple[Optional[List[float]], Optional[List[float]]]] = {}

    # --------------------------------------------------------------------------
    # Static Inspection Helpers
    # --------------------------------------------------------------------------

    @classmethod
    def inspect_homoglyph_keys(cls, obj: Any, path: str = "") -> None:
        """
        Recursively scans all dictionary keys. Detects confusable Unicode
        substitutions replacing standard ASCII identifiers.
        """
        if isinstance(obj, dict):
            for key, val in obj.items():
                current_path = f"{path}.{key}" if path else key
                if not isinstance(key, str):
                    continue

                # Check for non-ASCII characters in key
                has_non_ascii = any(ord(c) > 127 for c in key)
                if has_non_ascii:
                    # Check for homoglyph substitution
                    for char in key:
                        if char in HOMOGLYPH_MAP:
                            mapped = HOMOGLYPH_MAP[char]
                            raise HomoglyphKeyInjectionError(
                                f"Homoglyph character U+{ord(char):04X} ('{char}') detected in key "
                                f"'{key}' at '{current_path}' (maps to ASCII '{mapped}')"
                            )
                        # General confusable non-ASCII check for tool keys
                        if ord(char) > 127 and (
                            unicodedata.category(char).startswith("L") or
                            unicodedata.category(char).startswith("N")
                        ):
                            raise HomoglyphKeyInjectionError(
                                f"Non-ASCII identifier character U+{ord(char):04X} detected in key '{key}' at '{current_path}'"
                            )

                cls.inspect_homoglyph_keys(val, current_path)
        elif isinstance(obj, (list, tuple)):
            for idx, item in enumerate(obj):
                cls.inspect_homoglyph_keys(item, f"{path}[{idx}]")

    @classmethod
    def inspect_token_smuggling(cls, obj: Any, path: str = "") -> None:
        """
        Recursively scans string arguments for zero-width characters,
        Unicode tags (U+E0001 - U+E007F), and covert base64 chunks.
        """
        if isinstance(obj, str):
            # 1. Zero-width whitespace and bidi overrides
            for char in obj:
                if char in ZERO_WIDTH_CHARS:
                    raise TokenSmugglingDetectedError(
                        f"Zero-width character U+{ord(char):04X} detected at '{path}'"
                    )
                # 2. Unicode tag block (U+E0001 - U+E007F)
                if 0xE0001 <= ord(char) <= 0xE007F:
                    raise TokenSmugglingDetectedError(
                        f"Unicode tag smuggling character U+{ord(char):04X} detected at '{path}'"
                    )

            # 3. Base64 data URI smuggling
            for match in BASE64_DATA_URI_PATTERN.finditer(obj):
                encoded = match.group(1)
                try:
                    decoded = base64.b64decode(encoded, validate=True)
                    for kw in SUSPICIOUS_PAYLOAD_KEYWORDS:
                        if kw in decoded:
                            raise TokenSmugglingDetectedError(
                                f"Covert base64 payload containing prohibited token detected at '{path}'"
                            )
                except Exception as e:
                    if isinstance(e, TokenSmugglingDetectedError):
                        raise
                    # Ignore invalid base64 in data URI

            # 4. Standalone covert base64 blocks with suspicious decoded keywords
            if len(obj) >= 20 and not obj.startswith("sha256:") and not obj.startswith("ed25519:"):
                # Scan substrings matching base64 pattern of at least 20 chars
                b64_candidates = re.findall(r"\b[A-Za-z0-9+/]{20,}={0,2}\b", obj)
                for cand in b64_candidates:
                    try:
                        decoded = base64.b64decode(cand, validate=True)
                        for kw in SUSPICIOUS_PAYLOAD_KEYWORDS:
                            if kw in decoded:
                                raise TokenSmugglingDetectedError(
                                    f"Embedded covert base64 chunk with prohibited payload detected at '{path}'"
                                )
                    except Exception:
                        pass

        elif isinstance(obj, dict):
            for k, v in obj.items():
                cls.inspect_token_smuggling(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, (list, tuple)):
            for idx, item in enumerate(obj):
                cls.inspect_token_smuggling(item, f"{path}[{idx}]")

    # --------------------------------------------------------------------------
    # Metric Calculation Helpers
    # --------------------------------------------------------------------------

    def _resolve_domain(self, proposal: ToolCallProposal) -> int:
        """Determines ordinal capability tier for tool action."""
        if proposal.domain is not None:
            return int(proposal.domain)
        if proposal.tool_name in self.domain_map:
            return int(self.domain_map[proposal.tool_name])

        # Heuristic fallback based on action prefix
        name = proposal.tool_name.lower()
        if any(name.startswith(p) for p in ("read", "get", "lookup", "query", "search", "list", "fetch")):
            return CapabilityDomain.READ_ONLY
        if any(name.startswith(p) for p in ("check", "inspect", "probe", "scan", "audit", "verify")):
            return CapabilityDomain.DIAGNOSTIC
        if any(name.startswith(p) for p in ("stage", "prepare", "dry_run", "plan", "simulate")):
            return CapabilityDomain.CONFIG_PROBE
        if any(name.startswith(p) for p in ("write", "update", "modify", "insert", "delete", "set")):
            return CapabilityDomain.MUTATION
        if any(name.startswith(p) for p in ("wire", "transfer", "disburse", "pay", "refund", "execute_payment")):
            return CapabilityDomain.FINANCIAL_DISPATCH
        if any(name.startswith(p) for p in ("rotate", "admin", "reconfigure", "reboot", "shutdown", "root")):
            return CapabilityDomain.PRIVILEGED_ADMIN

        return CapabilityDomain.MUTATION

    def _resolve_permissions(self, proposal: ToolCallProposal) -> Set[str]:
        """Resolves resource scopes/permissions invoked by proposal."""
        if proposal.required_permissions:
            return set(proposal.required_permissions)
        if proposal.tool_name in self.permission_map:
            return set(self.permission_map[proposal.tool_name])
        return {f"{proposal.tool_name}:invoke"}

    def _check_prerequisites(self, proposal: ToolCallProposal) -> None:
        """
        Validates workflow staging requirements (e.g., wire_dispatch requires staged_escrow).
        Fails closed with HALT_OUT_OF_ORDER_EXECUTION if prerequisite is omitted.
        """
        reqs = self.prerequisite_rules.get(proposal.tool_name)
        if not reqs:
            return

        session_completed = self.completed_actions_by_session.get(proposal.session_id, set())
        for req in reqs:
            if req not in session_completed:
                raise OutOfOrderExecutionError(
                    f"Action '{proposal.tool_name}' requires prerequisite step '{req}' in session "
                    f"'{proposal.session_id}', but '{req}' has not been completed."
                )

    def _compute_entropy_update(
        self, session_id: str, new_permissions: Set[str]
    ) -> Tuple[float, float, float, Dict[str, int]]:
        """
        Calculates Shannon permission entropy H_k, entropy rate Delta H_k,
        and entropy acceleration a_{H, k} for the active session.
        """
        session_counts = dict(self.session_permission_counts.get(session_id, {}))
        for perm in new_permissions:
            session_counts[perm] = session_counts.get(perm, 0) + 1

        total_invocations = sum(session_counts.values())
        if total_invocations == 0:
            h_k = 0.0
        else:
            h_k = 0.0
            for count in session_counts.values():
                if count > 0:
                    p = count / total_invocations
                    h_k -= p * math.log2(p)

        sess_history = self.session_trajectories.get(session_id, [])
        prev_entropy = sess_history[-1].permission_entropy if sess_history else 0.0
        delta_h_k = h_k - prev_entropy

        if len(sess_history) >= 2:
            prev_delta_h = sess_history[-1].entropy_rate
            accel_h_k = delta_h_k - prev_delta_h
        elif len(sess_history) == 1:
            accel_h_k = delta_h_k
        else:
            accel_h_k = 0.0

        return h_k, delta_h_k, accel_h_k, session_counts

    def _compute_feature_vector(self, proposal: ToolCallProposal, domain: int) -> List[float]:
        """
        Computes deterministic 64-dimensional feature vector over action payload
        without external machine learning weights or network requests.
        """
        vec = [0.0] * 64
        # Dimension 0: Normalized domain tier
        vec[0] = float(domain) / 5.0
        # Dimension 1: Normalized argument count
        vec[1] = min(1.0, float(len(proposal.arguments)) / 10.0)

        # Deterministic hashing of keys and values
        serialized_args = json.dumps(proposal.arguments, sort_keys=True)
        vec[2] = min(1.0, float(len(serialized_args)) / 512.0)

        # Tokenize tool name and arguments
        tokens = [proposal.tool_name]
        for k, v in proposal.arguments.items():
            tokens.append(k)
            tokens.append(str(v))

        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(3, 64):
                byte_val = digest[(i - 3) % len(digest)]
                sign = 1.0 if (byte_val & 0x80) == 0 else -1.0
                weight = float(byte_val & 0x7F) / 127.0
                vec[i] += sign * weight

        # Normalize to unit vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [x / norm for x in vec]
        return vec

    def _compute_trajectory_curvature(self, session_id: str, curr_vec: List[float]) -> float:
        """
        Computes discrete trajectory curvature kappa_k as the angular variation
        of sequential tangent vectors: kappa_k = ||u_k - u_{k-1}||_2 within session.
        """
        prev_feature_vec, prev_tangent_vec = self.session_curvature_state.get(session_id, (None, None))
        if prev_feature_vec is None:
            self.session_curvature_state[session_id] = (curr_vec, None)
            return 0.0

        # Tangent vector: tau_k = x_k - x_{k-1}
        diff = [c - p for c, p in zip(curr_vec, prev_feature_vec)]
        norm = math.sqrt(sum(d * d for d in diff))
        if norm < 1e-9:
            curr_tangent = [0.0] * len(curr_vec)
        else:
            curr_tangent = [d / norm for d in diff]

        if prev_tangent_vec is None:
            self.session_curvature_state[session_id] = (curr_vec, curr_tangent)
            return 0.0

        # Curvature: norm of difference between successive unit tangents
        t_diff = [c - p for c, p in zip(curr_tangent, prev_tangent_vec)]
        curvature = math.sqrt(sum(td * td for td in t_diff))

        self.session_curvature_state[session_id] = (curr_vec, curr_tangent)
        return curvature

    # --------------------------------------------------------------------------
    # Evaluation Pipeline
    # --------------------------------------------------------------------------

    def evaluate_proposal(self, proposal: ToolCallProposal) -> AdmissionReceipt:
        """
        Evaluates a tool call proposal against predictive trajectory drift constraints:
        1. Checks fail-closed latch status.
        2. Ingress inspection: homoglyph keys and token smuggling.
        3. Prerequisite staging validation.
        4. Calculates domain velocity v_k, entropy acceleration a_{H, k}, and curvature kappa_k.
        5. Trips fail-closed if thresholds are breached; otherwise admits proposal.
        """
        caid = proposal.compute_caid()

        # 1. Fail-closed latch check
        if self.is_tripped:
            raise LatchTrippedError(
                f"Action CAID {caid} rejected: Predictive trajectory drift latch is TRIPPED. "
                f"Trip reason: {self.trip_reason}"
            )

        # 2. Ingress structural inspection
        self.inspect_homoglyph_keys(proposal.arguments)
        self.inspect_token_smuggling(proposal.arguments)

        # 3. Prerequisite validation
        self._check_prerequisites(proposal)

        # 4. Resolve capability domain and permissions
        domain = self._resolve_domain(proposal)
        proposal.domain = domain
        permissions = self._resolve_permissions(proposal)
        proposal.required_permissions = permissions

        # 5. Domain velocity calculation
        sess_history = self.session_trajectories.get(proposal.session_id, [])
        if not sess_history or proposal.step_index <= 1:
            step_jump = 0.0
            velocity = 0.0
        else:
            prev_domain = sess_history[-1].domain_level
            step_jump = float(abs(domain - prev_domain))
            prev_velocity = sess_history[-1].domain_velocity
            velocity = (self.velocity_ema_alpha * step_jump) + ((1.0 - self.velocity_ema_alpha) * prev_velocity)

        # 6. Permission entropy calculation
        h_k, delta_h_k, accel_h_k, updated_counts = self._compute_entropy_update(proposal.session_id, permissions)

        # 7. Discrete trajectory curvature calculation
        feat_vec = self._compute_feature_vector(proposal, domain)
        curvature = self._compute_trajectory_curvature(proposal.session_id, feat_vec)

        # Evaluate threshold triggers
        velocity_breach = (velocity > self.max_velocity_threshold) or (step_jump > self.max_step_jump)
        entropy_breach = (accel_h_k > self.max_entropy_acceleration) or (delta_h_k > self.max_entropy_rate)
        curvature_breach = (curvature > self.max_curvature_threshold)

        if velocity_breach or entropy_breach or curvature_breach:
            self.is_tripped = True
            self.trip_reason = {
                "action_caid": caid,
                "curvature": curvature,
                "curvature_breach": curvature_breach,
                "domain_level": domain,
                "domain_step_jump": step_jump,
                "domain_velocity": velocity,
                "entropy_acceleration": accel_h_k,
                "entropy_breach": entropy_breach,
                "entropy_rate": delta_h_k,
                "permission_entropy": h_k,
                "step_index": proposal.step_index,
                "timestamp_ns": proposal.timestamp_ns,
                "tool_name": proposal.tool_name,
                "velocity_breach": velocity_breach,
            }
            raise PredictiveTrajectoryDriftError(
                f"HALT_PREDICTIVE_TRAJECTORY_DRIFT: Action '{proposal.tool_name}' (CAID {caid[:16]}) "
                f"tripped drift latch. Velocity={velocity:.2f} (max={self.max_velocity_threshold}), "
                f"StepJump={step_jump:.2f} (max={self.max_step_jump}), "
                f"EntropyAccel={accel_h_k:.2f} (max={self.max_entropy_acceleration}), "
                f"Curvature={curvature:.2f} (max={self.max_curvature_threshold})"
            )

        # Record nominal admitted step
        metrics = TrajectoryMetrics(
            step_index=proposal.step_index,
            domain_level=domain,
            domain_step_jump=step_jump,
            domain_velocity=velocity,
            permission_entropy=h_k,
            entropy_rate=delta_h_k,
            entropy_acceleration=accel_h_k,
            trajectory_curvature=curvature,
            cumulative_permissions=set(updated_counts.keys()),
            caid=caid,
            timestamp_ns=proposal.timestamp_ns,
        )

        self.history.append(metrics)
        self.admitted_history.append(proposal)
        self.session_trajectories.setdefault(proposal.session_id, []).append(metrics)
        self.session_admitted.setdefault(proposal.session_id, []).append(proposal)
        self.session_permission_counts[proposal.session_id] = updated_counts
        self.cumulative_permission_counts.update(updated_counts)

        session_set = self.completed_actions_by_session.setdefault(proposal.session_id, set())
        session_set.add(proposal.tool_name)

        return AdmissionReceipt(
            admitted=True,
            action_caid=caid,
            step_index=proposal.step_index,
            metrics=metrics,
            latch_tripped=False,
        )

    # --------------------------------------------------------------------------
    # Step-Up Warrant Reset
    # --------------------------------------------------------------------------

    def reset_with_step_up_warrant(
        self,
        warrant: Dict[str, Any],
        supervisor_public_key: Optional[ed25519.Ed25519PublicKey] = None,
        now_ts: Optional[int] = None,
    ) -> bool:
        """
        Evaluates an authorized supervisor Ed25519 step-up warrant to reset a tripped latch.
        Validates warrant integrity, expiration, agent binding, and Ed25519 signature under RFC 8785 JCS.
        """
        required_fields = ("warrant_id", "target_agent_id", "action", "created_at", "expires_at", "signature")
        for f in required_fields:
            if f not in warrant or warrant[f] is None:
                raise StepUpWarrantInvalidError(f"Step-up warrant missing required field '{f}'")

        if warrant["target_agent_id"] != self.agent_id:
            raise StepUpWarrantInvalidError(
                f"Step-up warrant target_agent_id '{warrant['target_agent_id']}' does not match latch '{self.agent_id}'"
            )

        if warrant["action"] != "RESET_PREDICTIVE_TRAJECTORY_DRIFT":
            raise StepUpWarrantInvalidError(
                f"Step-up warrant action '{warrant['action']}' is not 'RESET_PREDICTIVE_TRAJECTORY_DRIFT'"
            )

        current_time = int(time.time()) if now_ts is None else int(now_ts)
        if current_time > int(warrant["expires_at"]):
            raise StepUpWarrantInvalidError(
                f"Step-up warrant expired at {warrant['expires_at']} (current: {current_time})"
            )

        # Resolve public key
        pub_key = supervisor_public_key
        if pub_key is None:
            supervisor_id = warrant.get("supervisor_id", "default_supervisor")
            pub_key = self.supervisor_public_keys.get(supervisor_id)

        if pub_key is None:
            raise StepUpWarrantInvalidError("No registered supervisor public key available for verification")

        # Canonicalize unsigned fields under RFC 8785
        unsigned_warrant = {k: v for k, v in warrant.items() if k != "signature"}
        canonical_bytes = encode_jcs(unsigned_warrant)

        sig_raw = base64.b64decode(warrant["signature"])
        try:
            pub_key.verify(sig_raw, canonical_bytes)
        except Exception as e:
            raise StepUpWarrantInvalidError(f"Supervisor Ed25519 signature verification failed: {e}")

        # Reset latch state
        self.is_tripped = False
        self.trip_reason = None
        self.session_curvature_state.clear()
        self.session_trajectories.clear()
        self.session_admitted.clear()
        self.session_permission_counts.clear()
        self.history.clear()
        self.admitted_history.clear()
        self.cumulative_permission_counts.clear()
        self.completed_actions_by_session.clear()
        return True

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry summarizing trajectory metrics and latch status."""
        return {
            "agent_id": self.agent_id,
            "cumulative_permissions_count": len(self.cumulative_permission_counts),
            "history_length": len(self.history),
            "is_tripped": self.is_tripped,
            "latest_metrics": asdict(self.history[-1]) if self.history else None,
            "trip_reason": self.trip_reason,
        }


# ==============================================================================
# Adversarial Trajectory Chaos Fuzzer
# ==============================================================================

class AdversarialTrajectoryChaosFuzzer:
    """
    Multi-turn adversarial chaos perturbation engine:
    1. Injects zero-width whitespace, Unicode tags, and hidden base64 chunks into arguments.
    2. Substitutes JSON keys with visually identical Cyrillic or Greek homoglyphs.
    3. Generates out-of-order execution step proposals skipping staging prerequisites.
    4. Evaluates drift latch fail-closed invariants under adversarial campaigns.
    """

    HOMOGLYPH_REPLACEMENTS = {
        "a": "\u0430",  # Cyrillic small a
        "c": "\u0441",  # Cyrillic small es
        "e": "\u0435",  # Cyrillic small ie
        "o": "\u043e",  # Cyrillic small o
        "p": "\u0440",  # Cyrillic small er
        "x": "\u0445",  # Cyrillic small ha
        "y": "\u0443",  # Cyrillic small u
        "i": "\u0456",  # Cyrillic small i
    }

    @classmethod
    def inject_homoglyph_keys(
        cls, payload: Dict[str, Any], target_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Replaces characters in target dictionary keys with visually indistinguishable homoglyphs.
        """
        targets = set(target_keys or ["amount", "destination", "recipient", "account", "token", "payload"])
        result: Dict[str, Any] = {}

        for k, v in payload.items():
            new_key = k
            if k in targets:
                # Replace first matching replaceable character
                for orig_char, confusable in cls.HOMOGLYPH_REPLACEMENTS.items():
                    if orig_char in k:
                        new_key = k.replace(orig_char, confusable, 1)
                        break

            if isinstance(v, dict):
                result[new_key] = cls.inject_homoglyph_keys(v, target_keys)
            elif isinstance(v, list):
                result[new_key] = [
                    cls.inject_homoglyph_keys(x, target_keys) if isinstance(x, dict) else x
                    for x in v
                ]
            else:
                result[new_key] = v

        return result

    @classmethod
    def inject_zero_width_tokens(cls, text: str, token_type: str = "zero_width_space") -> str:
        """Injects invisible zero-width characters into string."""
        char_map = {
            "zero_width_space": "\u200b",
            "zero_width_non_joiner": "\u200c",
            "zero_width_joiner": "\u200d",
            "bom": "\ufeff",
            "word_joiner": "\u2060",
        }
        injected_char = char_map.get(token_type, "\u200b")
        if len(text) <= 1:
            return f"{text}{injected_char}"
        mid = len(text) // 2
        return f"{text[:mid]}{injected_char}{text[mid:]}"

    @classmethod
    def inject_unicode_tags(cls, text: str, tag_str: str = "smuggle") -> str:
        """Encodes tag_str as Unicode Language Tag characters (U+E0001 - U+E007F)."""
        tags = "".join(chr(0xE0000 + ord(c)) for c in tag_str)
        return f"{text}{tags}"

    @classmethod
    def inject_base64_smuggling(cls, text: str, payload: str = "eval(process.env.SECRET)") -> str:
        """Embeds covert base64 chunk with prohibited payload markers into string."""
        encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        return f"{text} data:text/plain;base64,{encoded}"

    # --------------------------------------------------------------------------
    # Proposal Fuzzing Generators
    # --------------------------------------------------------------------------

    def fuzz_proposal_homoglyph(
        self, proposal: ToolCallProposal, target_key: str = "amount"
    ) -> ToolCallProposal:
        """Returns proposal perturbed with homoglyph dictionary keys."""
        fuzzed_args = self.inject_homoglyph_keys(proposal.arguments, [target_key])
        return ToolCallProposal(
            tool_name=proposal.tool_name,
            arguments=fuzzed_args,
            session_id=proposal.session_id,
            step_index=proposal.step_index,
            timestamp_ns=proposal.timestamp_ns,
            domain=proposal.domain,
            required_permissions=proposal.required_permissions,
            metadata=proposal.metadata,
        )

    def fuzz_proposal_token_smuggling(
        self, proposal: ToolCallProposal, smuggling_type: str = "zero_width"
    ) -> ToolCallProposal:
        """Returns proposal perturbed with smuggled tokens in string arguments."""
        fuzzed_args: Dict[str, Any] = {}
        for k, v in proposal.arguments.items():
            if isinstance(v, str):
                if smuggling_type == "zero_width":
                    fuzzed_args[k] = self.inject_zero_width_tokens(v)
                elif smuggling_type == "unicode_tags":
                    fuzzed_args[k] = self.inject_unicode_tags(v)
                elif smuggling_type == "base64_hidden":
                    fuzzed_args[k] = self.inject_base64_smuggling(v)
                else:
                    fuzzed_args[k] = self.inject_zero_width_tokens(v)
            else:
                fuzzed_args[k] = v

        return ToolCallProposal(
            tool_name=proposal.tool_name,
            arguments=fuzzed_args,
            session_id=proposal.session_id,
            step_index=proposal.step_index,
            timestamp_ns=proposal.timestamp_ns,
            domain=proposal.domain,
            required_permissions=proposal.required_permissions,
            metadata=proposal.metadata,
        )

    def fuzz_proposal_out_of_order(
        self, tool_name: str = "wire_dispatch", session_id: str = "session-chaos-ooo"
    ) -> ToolCallProposal:
        """Returns out-of-order execution proposal skipping required staging prerequisite."""
        return ToolCallProposal(
            tool_name=tool_name,
            arguments={"amount": 500000, "destination": "acct_dest_9999"},
            session_id=session_id,
            step_index=1,
        )

    def fuzz_excessive_velocity_leap(
        self, session_id: str = "session-chaos-vel"
    ) -> List[ToolCallProposal]:
        """
        Returns two-step trajectory where step 2 leaps across capability tiers
        (e.g., READ_ONLY -> FINANCIAL_DISPATCH).
        """
        step1 = ToolCallProposal(
            tool_name="lookup_balance",
            arguments={"account_id": "acct_source_1111"},
            session_id=session_id,
            step_index=1,
            domain=CapabilityDomain.READ_ONLY,
        )
        step2 = ToolCallProposal(
            tool_name="wire_dispatch",
            arguments={"amount": 250000, "destination": "acct_dest_2222"},
            session_id=session_id,
            step_index=2,
            domain=CapabilityDomain.FINANCIAL_DISPATCH,
        )
        return [step1, step2]

    def run_fuzz_campaign(
        self, latch: PredictiveTrajectoryDriftLatch, rounds: int = 50
    ) -> Dict[str, Any]:
        """
        Executes multi-round fuzzing testbed across all perturbation vectors.
        Verifies that 100% of adversarial injections fail closed under the stated model.
        """
        catches: Dict[str, int] = {
            HALT_PREDICTIVE_TRAJECTORY_DRIFT: 0,
            HALT_HOMOGLYPH_KEY_INJECTION: 0,
            HALT_TOKEN_SMUGGLING_DETECTED: 0,
            HALT_OUT_OF_ORDER_EXECUTION: 0,
        }
        total_evaluations = 0

        # Vector 1: Homoglyph Key Injections
        for i in range(rounds):
            prop = ToolCallProposal(
                tool_name="lookup_balance",
                arguments={"account": f"acct_{i}", "amount": 1000 + i},
                session_id=f"chaos-homoglyph-{i}",
                step_index=1,
            )
            fuzzed = self.fuzz_proposal_homoglyph(prop, "amount")
            total_evaluations += 1
            try:
                latch.evaluate_proposal(fuzzed)
            except HomoglyphKeyInjectionError:
                catches[HALT_HOMOGLYPH_KEY_INJECTION] += 1

        # Vector 2: Token Smuggling (Zero-width, Unicode tags, Base64)
        smuggle_types = ["zero_width", "unicode_tags", "base64_hidden"]
        for i in range(rounds):
            smuggle_t = smuggle_types[i % len(smuggle_types)]
            prop = ToolCallProposal(
                tool_name="query_catalog",
                arguments={"item_query": f"standard_catalog_query_{i}"},
                session_id=f"chaos-smuggle-{i}",
                step_index=1,
            )
            fuzzed = self.fuzz_proposal_token_smuggling(prop, smuggle_t)
            total_evaluations += 1
            try:
                latch.evaluate_proposal(fuzzed)
            except TokenSmugglingDetectedError:
                catches[HALT_TOKEN_SMUGGLING_DETECTED] += 1

        # Vector 3: Out-of-order execution step injection
        for i in range(rounds):
            ooo_prop = self.fuzz_proposal_out_of_order(
                tool_name="wire_dispatch", session_id=f"chaos-ooo-{i}"
            )
            total_evaluations += 1
            try:
                latch.evaluate_proposal(ooo_prop)
            except OutOfOrderExecutionError:
                catches[HALT_OUT_OF_ORDER_EXECUTION] += 1

        # Vector 4: Excessive domain shift velocity leap
        for i in range(rounds):
            fresh_latch = PredictiveTrajectoryDriftLatch(
                agent_id=f"agent-fuzz-{i}", max_velocity_threshold=2.0
            )
            props = self.fuzz_excessive_velocity_leap(session_id=f"chaos-vel-{i}")
            # Admit step 1
            fresh_latch.evaluate_proposal(props[0])
            # Step 2 also needs staging prerequisite bypassed or met to test pure velocity
            fresh_latch.completed_actions_by_session[props[1].session_id] = {"staged_escrow"}
            total_evaluations += 1
            try:
                fresh_latch.evaluate_proposal(props[1])
            except PredictiveTrajectoryDriftError:
                catches[HALT_PREDICTIVE_TRAJECTORY_DRIFT] += 1

        return {
            "catches": catches,
            "rounds_per_vector": rounds,
            "total_adversarial_evaluations": total_evaluations,
        }


# ==============================================================================
# CLI Self-Test Runner
# ==============================================================================

def run_self_test() -> bool:
    """
    Executes self-test suite exercising nominal execution, adversarial rejection,
    and Ed25519 supervisor step-up warrant reset.
    """
    supervisor_priv = ed25519.Ed25519PrivateKey.generate()
    supervisor_pub = supervisor_priv.public_key()

    latch = PredictiveTrajectoryDriftLatch(
        agent_id="agent-selftest-01",
        max_velocity_threshold=2.0,
        max_step_jump=2.0,
        max_entropy_acceleration=1.5,
        max_curvature_threshold=1.85,
        supervisor_public_keys={"supervisor-root": supervisor_pub},
    )
    fuzzer = AdversarialTrajectoryChaosFuzzer()

    # 1. Nominal progressive trajectory: READ_ONLY -> CONFIG_PROBE -> FINANCIAL_DISPATCH
    sess = "session-nominal-01"
    t1 = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account_id": "acct_source_001"},
        session_id=sess,
        step_index=1,
    )
    r1 = latch.evaluate_proposal(t1)
    assert r1.admitted is True

    t2 = ToolCallProposal(
        tool_name="staged_escrow",
        arguments={"amount": 100000, "destination": "acct_dest_002"},
        session_id=sess,
        step_index=2,
    )
    r2 = latch.evaluate_proposal(t2)
    assert r2.admitted is True

    t3 = ToolCallProposal(
        tool_name="wire_dispatch",
        arguments={"amount": 100000, "destination": "acct_dest_002"},
        session_id=sess,
        step_index=3,
    )
    r3 = latch.evaluate_proposal(t3)
    assert r3.admitted is True

    # 2. Homoglyph key injection rejection
    t_homoglyph = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account": "acct_test", "amount": 50000},
        session_id="session-homoglyph-01",
        step_index=1,
    )
    t_homoglyph_fuzzed = fuzzer.fuzz_proposal_homoglyph(t_homoglyph, "amount")
    homoglyph_caught = False
    try:
        latch.evaluate_proposal(t_homoglyph_fuzzed)
    except HomoglyphKeyInjectionError as err:
        homoglyph_caught = (err.error_code == HALT_HOMOGLYPH_KEY_INJECTION)
    assert homoglyph_caught is True

    # 3. Token smuggling rejection
    t_smuggle = ToolCallProposal(
        tool_name="query_catalog",
        arguments={"query": "active_accounts"},
        session_id="session-smuggle-01",
        step_index=1,
    )
    t_smuggle_fuzzed = fuzzer.fuzz_proposal_token_smuggling(t_smuggle, "zero_width")
    smuggle_caught = False
    try:
        latch.evaluate_proposal(t_smuggle_fuzzed)
    except TokenSmugglingDetectedError as err:
        smuggle_caught = (err.error_code == HALT_TOKEN_SMUGGLING_DETECTED)
    assert smuggle_caught is True

    # 4. Out-of-order execution rejection
    t_ooo = ToolCallProposal(
        tool_name="wire_dispatch",
        arguments={"amount": 99999, "destination": "acct_dest_unauthorized"},
        session_id="session-ooo-01",
        step_index=1,
    )
    ooo_caught = False
    try:
        latch.evaluate_proposal(t_ooo)
    except OutOfOrderExecutionError as err:
        ooo_caught = (err.error_code == HALT_OUT_OF_ORDER_EXECUTION)
    assert ooo_caught is True

    # 5. Domain velocity drift trip
    drift_sess = "session-drift-01"
    t_base = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account_id": "acct_source_001"},
        session_id=drift_sess,
        step_index=1,
    )
    latch.evaluate_proposal(t_base)
    # Satisfy staging prerequisite out-of-band to evaluate pure capability velocity
    latch.completed_actions_by_session[drift_sess] = {"staged_escrow"}

    t_leap = ToolCallProposal(
        tool_name="wire_dispatch",
        arguments={"amount": 999999, "destination": "acct_dest_002"},
        session_id=drift_sess,
        step_index=2,
    )
    drift_caught = False
    try:
        latch.evaluate_proposal(t_leap)
    except PredictiveTrajectoryDriftError as err:
        drift_caught = (err.error_code == HALT_PREDICTIVE_TRAJECTORY_DRIFT)
    assert drift_caught is True
    assert latch.is_tripped is True

    # Subsequent proposals must be rejected while tripped
    tripped_rejection = False
    try:
        latch.evaluate_proposal(t_base)
    except LatchTrippedError as err:
        tripped_rejection = (err.error_code == HALT_LATCH_ALREADY_TRIPPED)
    assert tripped_rejection is True

    # 6. Ed25519 supervisor step-up warrant reset
    now = int(time.time())
    warrant = {
        "action": "RESET_PREDICTIVE_TRAJECTORY_DRIFT",
        "created_at": now,
        "expires_at": now + 3600,
        "nonce": "nonce-selftest-7744",
        "reason": "Supervisor manual re-alignment after evaluated drift event",
        "supervisor_id": "supervisor-root",
        "target_agent_id": latch.agent_id,
        "warrant_id": "warrant-stepup-001",
    }
    canonical_warrant_bytes = encode_jcs(warrant)
    raw_sig = supervisor_priv.sign(canonical_warrant_bytes)
    warrant["signature"] = base64.b64encode(raw_sig).decode("ascii")

    reset_result = latch.reset_with_step_up_warrant(warrant, supervisor_pub)
    assert reset_result is True
    assert latch.is_tripped is False

    # 7. Multi-vector chaos fuzzer campaign
    campaign_results = fuzzer.run_fuzz_campaign(latch, rounds=25)
    total_evals = campaign_results["total_adversarial_evaluations"]
    total_catches = sum(campaign_results["catches"].values())
    assert total_catches == total_evals

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predictive Trajectory Drift Latch & Chaos Fuzzer (AEIB Station 1 Prototype)"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Execute self-test suite validating nominal trajectories and adversarial vectors",
    )
    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        if success:
            print("Self-test completed: nominal trajectories and adversarial perturbations evaluated.")
            sys.exit(0)
        else:
            print("Self-test failed: unexpected evaluation anomaly.", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
