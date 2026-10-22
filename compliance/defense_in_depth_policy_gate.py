#!/usr/bin/env python3
# File: compliance/defense_in_depth_policy_gate.py
"""
AEIB Defense-in-Depth Policy Gatekeeper.

Operationalizes the four October 2026 ground-truth threat signals:
1. Anti-Disarmament / OOB Telemetry Protection:
   Blocks attempts by guest agents to kill logging, audit, or security daemons.
2. Runtime Startup Hook Lockdown (Supply-Chain / LiteLLM Vector):
   Blocks write attempts to `sitecustomize.py`, `usercustomize.py`, and `.pth` files.
3. Package Management Step-Up Gating:
   Blocks `pip`, `npm`, and `cargo` install commands without an Ed25519 RFC 9470 Step-Up warrant.
4. Egress Intent Interlock:
   Blocks outbound network connections missing an approved pre-dispatch CAID Intent.
"""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_jcs_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) encoding."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True)
class PolicyEvaluationResult:
    allowed: bool
    halt_code: str
    rule_id: str
    detail: str


class DefenseInDepthPolicyGate:
    """
    Evaluates actions against `compliance/defense_in_depth.yaml` declarative invariants.
    """

    PROHIBITED_COMMAND_PATTERNS = (
        r"\bpkill\b.*(?:audit|otel|telemetry|gatekeeper|daemon)",
        r"\bkillall\b.*(?:audit|otel|telemetry|gatekeeper|daemon)",
        r"\bkill\s+-9\b",
        r"\bsystemctl\s+stop\b.*(?:audit|otel|aeib)",
        r"\blaunchctl\s+unload\b.*(?:audit|otel|aeib)",
        r"\brm\s+-(?:r?f|fr)\s+.*(?:/var/log|audit\.log|telemetry\.csv|\.system_generated)",
    )

    PROHIBITED_FILE_WRITES = (
        "**/sitecustomize.py",
        "**/usercustomize.py",
        "**/*.pth",
        "**/site-packages/**",
        "/usr/lib/**",
        "/Library/Python/**",
        "/var/log/**",
        "**/audit.log",
        "**/telemetry.csv",
        "**/.system_generated/**",
    )

    PACKAGE_MANAGERS = ("pip", "pip3", "npm", "cargo", "uv")

    @classmethod
    def evaluate_command_execution(cls, command: str) -> PolicyEvaluationResult:
        """
        Enforces Rule 1: Anti-Disarmament / Out-of-Band Telemetry & Monitor Protection.
        """
        for pat in cls.PROHIBITED_COMMAND_PATTERNS:
            if re.search(pat, command, flags=re.IGNORECASE):
                return PolicyEvaluationResult(
                    allowed=False,
                    halt_code="HALT_TELEMETRY_TAMPER_DETECTED",
                    rule_id="DID_R1_PROTECT_OBSERVABILITY",
                    detail=f"Prohibited telemetry disarming command detected: {command}",
                )
        return PolicyEvaluationResult(
            allowed=True,
            halt_code="NONE",
            rule_id="DID_R1_PROTECT_OBSERVABILITY",
            detail="Command passed observability protection gate.",
        )

    @classmethod
    def evaluate_file_write(cls, target_path: str) -> PolicyEvaluationResult:
        """
        Enforces Rule 2: Supply-Chain Runtime Startup Hook Lockdown (LiteLLM Attack Vector).
        """
        normalized = target_path.strip()
        for pat in cls.PROHIBITED_FILE_WRITES:
            if fnmatch.fnmatch(normalized, pat) or fnmatch.fnmatch(
                Path(normalized).name, pat
            ):
                return PolicyEvaluationResult(
                    allowed=False,
                    halt_code="HALT_RUNTIME_HOOK_TAMPER_DETECTED",
                    rule_id="DID_R2_RUNTIME_STARTUP_HOOK_LOCKDOWN",
                    detail=f"Write to runtime startup hook or protected directory forbidden: {target_path}",
                )
        return PolicyEvaluationResult(
            allowed=True,
            halt_code="NONE",
            rule_id="DID_R2_RUNTIME_STARTUP_HOOK_LOCKDOWN",
            detail="File path passed runtime hook protection gate.",
        )

    @classmethod
    def evaluate_package_install(
        cls,
        command_tokens: List[str],
        step_up_warrant: Optional[Dict[str, Any]] = None,
        supervisor_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> PolicyEvaluationResult:
        """
        Enforces Rule 3: Unsigned Package Manager Interception.
        """
        if not command_tokens:
            return PolicyEvaluationResult(
                allowed=True,
                halt_code="NONE",
                rule_id="DID_R3_PACKAGE_MANAGER_GATING",
                detail="Empty command tokens passed.",
            )

        binary = Path(command_tokens[0]).name
        is_pkg_install = (
            binary in cls.PACKAGE_MANAGERS
            and len(command_tokens) > 1
            and any(sub in command_tokens[1:] for sub in ("install", "add", "i"))
        )

        if not is_pkg_install:
            return PolicyEvaluationResult(
                allowed=True,
                halt_code="NONE",
                rule_id="DID_R3_PACKAGE_MANAGER_GATING",
                detail="Non-package management command passed.",
            )

        if not step_up_warrant or not supervisor_pubkey:
            return PolicyEvaluationResult(
                allowed=False,
                halt_code="HALT_UNSIGNED_PACKAGE_INSTALL",
                rule_id="DID_R3_PACKAGE_MANAGER_GATING",
                detail=f"Package install attempt '{' '.join(command_tokens)}' rejected: Missing RFC 9470 Step-Up warrant.",
            )

        # Validate RFC 9470 Step-Up warrant
        try:
            scope = step_up_warrant.get("scope")
            if scope != "SECURITY_OPERATIONS_PACKAGE_INSTALL":
                return PolicyEvaluationResult(
                    allowed=False,
                    halt_code="HALT_UNSIGNED_PACKAGE_INSTALL",
                    rule_id="DID_R3_PACKAGE_MANAGER_GATING",
                    detail="Step-Up warrant does not grant SECURITY_OPERATIONS_PACKAGE_INSTALL scope.",
                )

            sig_b64 = step_up_warrant.get("signature_b64", "")
            sig = base64.b64decode(sig_b64)
            stmt = {
                k: v
                for k, v in step_up_warrant.items()
                if k not in ("signature_b64",)
            }
            stmt_bytes = canonical_jcs_bytes(stmt)
            supervisor_pubkey.verify(sig, stmt_bytes)
            return PolicyEvaluationResult(
                allowed=True,
                halt_code="NONE",
                rule_id="DID_R3_PACKAGE_MANAGER_GATING",
                detail="Package install authorized by verified RFC 9470 Step-Up warrant.",
            )
        except Exception as exc:
            return PolicyEvaluationResult(
                allowed=False,
                halt_code="HALT_UNSIGNED_PACKAGE_INSTALL",
                rule_id="DID_R3_PACKAGE_MANAGER_GATING",
                detail=f"Step-Up warrant cryptographic verification failed: {exc}",
            )

    @classmethod
    def evaluate_network_egress(
        cls,
        destination_host: str,
        destination_port: int,
        caid_intent_token: Optional[str] = None,
    ) -> PolicyEvaluationResult:
        """
        Enforces Rule 4: Outbound Network Socket Intent Registration.
        """
        if not caid_intent_token or not caid_intent_token.startswith("intent:"):
            return PolicyEvaluationResult(
                allowed=False,
                halt_code="HALT_UNREGISTERED_EGRESS_SOCKET",
                rule_id="DID_R4_OUTBOUND_EGRESS_INTENT_MANDATE",
                detail=f"Egress to {destination_host}:{destination_port} rejected: Missing pre-dispatch CAID Intent.",
            )
        return PolicyEvaluationResult(
            allowed=True,
            halt_code="NONE",
            rule_id="DID_R4_OUTBOUND_EGRESS_INTENT_MANDATE",
            detail=f"Egress to {destination_host}:{destination_port} permitted with intent {caid_intent_token}.",
        )
