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
src/artemis_device_and_plugin_boundary.py
================================================================================
Mobile Device Actuator & Edge Plugin Boundary Gating Architecture.
Evaluated under the stated model. Prototype scaffold for AEIB Station 1.

Implements:
1. Artemis Device Actuator Boundary (ArtemisDeviceActuatorGate):
   - External device driver commands (tap_coordinate, input_text, launch_intent,
     adb_shell, open_payment_app, submit_credential) do NOT execute directly
     from agent guest code.
   - Every device mutation requires a Content-Addressed Action Identifier (CAID)
     warrant signed by the delegating sponsor using Ed25519 and RFC 8785 JCS.
   - High-consequence device actions (e.g. launching financial apps, authorizing
     biometric prompts, modifying system settings) require an Ed25519-signed
     step-up token conforming to RFC 9470, else fail closed with
     HALT_DEVICE_ACTION_REQUIRES_STEP_UP.

2. Hermes Edge Plugin Catalog & Dynamic Capability Scanner (HermesEdgePluginGate):
   - Edge plugins present a signed manifest (plugin_name, version,
     publisher_pubkey, allowed_device_scopes, code_sha256).
   - Validates code using AST visitor: scans for forbidden dynamic execution
     (eval, exec, compile, dlopen, subprocess.Popen without sandboxing, direct
     socket opening outside UDS).
   - Enforces strict capability attenuation: an edge plugin cannot claim device
     scopes beyond its signed manifest.

3. ADECS 4.0 Agent Lifecycle State Automaton (AdecsAgentLifecycleAutomaton):
   - Enforces formal agent states:
       RECRUITED (key registered, budget 0),
       DEPLOYED  (active, bounded budget ceiling),
       GROWING   (skills added, validated through AST gate),
       RETIRED   (keys revoked, budget voided).
   - Mutations from RETIRED or un-DEPLOYED agents fail closed with
     HALT_AGENT_LIFECYCLE_INVALID.

Supports CLI execution with --self-test.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Ensure repository root is on sys.path for direct script execution
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs


# ==============================================================================
# Security Halt Codes & Constants
# ==============================================================================

HALT_DEVICE_ACTION_REQUIRES_STEP_UP: str = "HALT_DEVICE_ACTION_REQUIRES_STEP_UP"
HALT_DEVICE_ACTION_CAID_MISMATCH: str = "HALT_DEVICE_ACTION_CAID_MISMATCH"
HALT_DEVICE_ACTION_SPONSOR_SIGNATURE_INVALID: str = "HALT_DEVICE_ACTION_SPONSOR_SIGNATURE_INVALID"
HALT_DEVICE_ACTION_WARRANT_EXPIRED: str = "HALT_DEVICE_ACTION_WARRANT_EXPIRED"
HALT_DEVICE_ACTION_TYPE_NOT_PERMITTED: str = "HALT_DEVICE_ACTION_TYPE_NOT_PERMITTED"
HALT_DEVICE_ACTION_DELEGATION_MISMATCH: str = "HALT_DEVICE_ACTION_DELEGATION_MISMATCH"
HALT_DIRECT_GUEST_EXECUTION_DENIED: str = "HALT_DIRECT_GUEST_EXECUTION_DENIED"

HALT_PLUGIN_DYNAMIC_CODE_REJECTED: str = "HALT_PLUGIN_DYNAMIC_CODE_REJECTED"
HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION: str = "HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION"
HALT_PLUGIN_CODE_INTEGRITY_MISMATCH: str = "HALT_PLUGIN_CODE_INTEGRITY_MISMATCH"
HALT_PLUGIN_SIGNATURE_INVALID: str = "HALT_PLUGIN_SIGNATURE_INVALID"

HALT_AGENT_LIFECYCLE_INVALID: str = "HALT_AGENT_LIFECYCLE_INVALID"
HALT_AGENT_BUDGET_EXCEEDED: str = "HALT_AGENT_BUDGET_EXCEEDED"

# Standard Artemis device action types
TAP_COORDINATE: str = "tap_coordinate"
INPUT_TEXT: str = "input_text"
LAUNCH_INTENT: str = "launch_intent"
ADB_SHELL: str = "adb_shell"
OPEN_PAYMENT_APP: str = "open_payment_app"
SUBMIT_CREDENTIAL: str = "submit_credential"
AUTHORIZE_BIOMETRIC: str = "authorize_biometric"
MODIFY_SYSTEM_SETTING: str = "modify_system_setting"
READ_SCREEN: str = "read_screen"

HIGH_CONSEQUENCE_ACTION_TYPES: Set[str] = {
    OPEN_PAYMENT_APP,
    SUBMIT_CREDENTIAL,
    AUTHORIZE_BIOMETRIC,
    MODIFY_SYSTEM_SETTING,
    ADB_SHELL,
}


# ==============================================================================
# Security Exceptions
# ==============================================================================

class ArtemisDeviceHaltError(Exception):
    """Base exception for Artemis device actuator boundary violations."""

    def __init__(self, message: str, error_code: str = "HALT_DEVICE_ACTUATOR_ERROR") -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code
        self.detail = message


class StepUpRequiredHaltError(ArtemisDeviceHaltError):
    """Raised when a high-consequence action lacks a valid RFC 9470 step-up token."""

    def __init__(self, message: str = "Step-up authorization required") -> None:
        super().__init__(message, error_code=HALT_DEVICE_ACTION_REQUIRES_STEP_UP)


class WarrantVerificationHaltError(ArtemisDeviceHaltError):
    """Raised when sponsor warrant verification fails or mismatches action CAID."""

    def __init__(self, message: str, error_code: str = HALT_DEVICE_ACTION_CAID_MISMATCH) -> None:
        super().__init__(message, error_code=error_code)


class HermesPluginHaltError(Exception):
    """Base exception for Hermes edge plugin boundary violations."""

    def __init__(self, message: str, error_code: str = "HALT_HERMES_PLUGIN_ERROR") -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code
        self.detail = message


class PluginDynamicCodeRejectedError(HermesPluginHaltError):
    """Raised when AST analysis detects forbidden dynamic execution constructs."""

    def __init__(self, message: str, violations: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(message, error_code=HALT_PLUGIN_DYNAMIC_CODE_REJECTED)
        self.violations = violations or []


class PluginCapabilityAttenuationError(HermesPluginHaltError):
    """Raised when an edge plugin requests scopes outside its signed manifest."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION)


class PluginCodeIntegrityError(HermesPluginHaltError):
    """Raised when code digest does not match manifest code_sha256."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=HALT_PLUGIN_CODE_INTEGRITY_MISMATCH)


class PluginSignatureInvalidError(HermesPluginHaltError):
    """Raised when publisher signature verification fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=HALT_PLUGIN_SIGNATURE_INVALID)


class AdecsLifecycleHaltError(Exception):
    """Base exception for ADECS 4.0 agent lifecycle state automaton violations."""

    def __init__(self, message: str, error_code: str = HALT_AGENT_LIFECYCLE_INVALID) -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code
        self.detail = message


class AgentLifecycleInvalidHaltError(AdecsLifecycleHaltError):
    """Raised when mutations are dispatched from non-DEPLOYED or RETIRED agents."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=HALT_AGENT_LIFECYCLE_INVALID)


class AgentBudgetExceededHaltError(AdecsLifecycleHaltError):
    """Raised when spend exceeds allocated ceiling."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=HALT_AGENT_BUDGET_EXCEEDED)


# ==============================================================================
# Domain Models: DeviceAction, Warrant, StepUpToken
# ==============================================================================

@dataclass
class DeviceAction:
    """Represents a discrete mutation or inspection on an external mobile device."""
    action_type: str
    target_device_id: str
    agent_id: str
    parameters: Dict[str, Any]
    nonce: str
    timestamp: int

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Produces normalized dictionary for RFC 8785 JCS canonicalization."""
        return {
            "action_type": self.action_type,
            "agent_id": self.agent_id,
            "nonce": self.nonce,
            "parameters": self.parameters,
            "target_device_id": self.target_device_id,
            "timestamp": self.timestamp,
        }

    def compute_caid(self) -> str:
        """Computes Content-Addressed Action Identifier (CAID) via SHA-256 over JCS bytes."""
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        return hashlib.sha256(canonical_bytes).hexdigest()


@dataclass
class SponsorDeviceActionWarrant:
    """Content-Addressed Action Identifier warrant signed by delegating sponsor."""
    warrant_id: str
    sponsor_did: str
    agent_id: str
    target_device_id: str
    action_caid: str
    allowed_action_types: List[str]
    issued_at: int
    expires_at: int
    signature_b64: str = ""

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Payload covered by sponsor Ed25519 signature."""
        return {
            "action_caid": self.action_caid,
            "agent_id": self.agent_id,
            "allowed_action_types": sorted(self.allowed_action_types),
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "sponsor_did": self.sponsor_did,
            "target_device_id": self.target_device_id,
            "warrant_id": self.warrant_id,
        }

    def sign(self, sponsor_private_key: Ed25519PrivateKey) -> None:
        """Signs canonical JCS bytes with sponsor Ed25519 private key."""
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        sig = sponsor_private_key.sign(canonical_bytes)
        self.signature_b64 = base64.b64encode(sig).decode("ascii")

    def verify(self, sponsor_public_key: Ed25519PublicKey) -> bool:
        """Verifies Ed25519 signature against canonical JCS bytes."""
        if not self.signature_b64:
            return False
        try:
            sig = base64.b64decode(self.signature_b64)
            sponsor_public_key.verify(sig, encode_jcs(self.to_canonical_dict()))
            return True
        except (InvalidSignature, ValueError):
            return False


@dataclass
class Rfc9470StepUpToken:
    """Ed25519-signed step-up challenge token conforming to RFC 9470 semantics."""
    token_id: str
    acr: str  # e.g. "urn:ietf:params:oauth:acr:rfc9470-webauthn-hw"
    action_caid: str
    target_device_id: str
    supervisor_did: str
    challenge_nonce: str
    issued_at: int
    expires_at: int
    signature_b64: str = ""

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Payload covered by supervisor Ed25519 signature."""
        return {
            "acr": self.acr,
            "action_caid": self.action_caid,
            "challenge_nonce": self.challenge_nonce,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "supervisor_did": self.supervisor_did,
            "target_device_id": self.target_device_id,
            "token_id": self.token_id,
        }

    def sign(self, supervisor_private_key: Ed25519PrivateKey) -> None:
        """Signs canonical JCS bytes with supervisor Ed25519 private key."""
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        sig = supervisor_private_key.sign(canonical_bytes)
        self.signature_b64 = base64.b64encode(sig).decode("ascii")

    def verify(self, supervisor_public_key: Ed25519PublicKey) -> bool:
        """Verifies Ed25519 signature against canonical JCS bytes."""
        if not self.signature_b64:
            return False
        try:
            sig = base64.b64decode(self.signature_b64)
            supervisor_public_key.verify(sig, encode_jcs(self.to_canonical_dict()))
            return True
        except (InvalidSignature, ValueError):
            return False


# ==============================================================================
# Artemis Device Actuator Gate
# ==============================================================================

class ArtemisDeviceActuatorGate:
    """
    Artemis Device Actuator Boundary Gate.
    Governs mobile device automation (Google ARTEMIS pattern) to ensure external
    actuator commands do not execute directly from agent guest code.
    """

    def __init__(
        self,
        sponsor_public_keys: Optional[Dict[str, Ed25519PublicKey]] = None,
        supervisor_public_keys: Optional[Dict[str, Ed25519PublicKey]] = None,
        driver_backend: Optional[Callable[[DeviceAction], Dict[str, Any]]] = None,
    ) -> None:
        self.sponsor_public_keys: Dict[str, Ed25519PublicKey] = sponsor_public_keys or {}
        self.supervisor_public_keys: Dict[str, Ed25519PublicKey] = supervisor_public_keys or {}
        self.driver_backend: Optional[Callable[[DeviceAction], Dict[str, Any]]] = driver_backend

    def register_sponsor_key(self, sponsor_did: str, public_key: Ed25519PublicKey) -> None:
        """Registers an authorized sponsor public key."""
        self.sponsor_public_keys[sponsor_did] = public_key

    def register_supervisor_key(self, supervisor_did: str, public_key: Ed25519PublicKey) -> None:
        """Registers an authorized supervisor public key."""
        self.supervisor_public_keys[supervisor_did] = public_key

    def is_high_consequence(self, action: DeviceAction) -> bool:
        """
        Evaluates whether an action is high-consequence requiring RFC 9470 step-up.
        Covers financial apps, credential submissions, biometric prompts,
        system setting adjustments, ADB shell access, and sensitive intent targets.
        """
        if action.action_type in HIGH_CONSEQUENCE_ACTION_TYPES:
            return True

        if action.action_type == LAUNCH_INTENT:
            pkg = str(action.parameters.get("package", "")).lower()
            intent_action = str(action.parameters.get("action", "")).lower()
            high_risk_keywords = [
                "bank", "pay", "wallet", "crypto", "settings",
                "packageinstaller", "vending", "reboot",
            ]
            if any(kw in pkg for kw in high_risk_keywords):
                return True
            if any(kw in intent_action for kw in ["delete", "uninstall", "settings", "password"]):
                return True

        if action.action_type == INPUT_TEXT:
            if action.parameters.get("is_sensitive") is True:
                return True
            field_type = str(action.parameters.get("field_type", "")).lower()
            if field_type in {"password", "pin", "otp", "credential", "cvv"}:
                return True

        return False

    def verify_and_dispatch(
        self,
        action: DeviceAction,
        warrant: SponsorDeviceActionWarrant,
        step_up_token: Optional[Rfc9470StepUpToken] = None,
        now_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates device mutation against sponsor warrant and required step-up token.
        Fails closed on any policy violation, expired timestamp, or cryptographic mismatch.
        """
        current_time = int(time.time()) if now_ts is None else now_ts

        # 1. Check warrant expiration
        if current_time > warrant.expires_at:
            raise WarrantVerificationHaltError(
                f"Sponsor warrant expired at {warrant.expires_at} (current: {current_time})",
                error_code=HALT_DEVICE_ACTION_WARRANT_EXPIRED,
            )

        # 2. Compute CAID and compare with warrant
        computed_caid = action.compute_caid()
        if warrant.action_caid != computed_caid:
            raise WarrantVerificationHaltError(
                f"Action CAID {computed_caid} does not match warrant CAID {warrant.action_caid}",
                error_code=HALT_DEVICE_ACTION_CAID_MISMATCH,
            )

        # 3. Verify delegation bounds (device and agent)
        if warrant.target_device_id != action.target_device_id or warrant.agent_id != action.agent_id:
            raise WarrantVerificationHaltError(
                f"Warrant binding mismatch: device({warrant.target_device_id} vs {action.target_device_id}), "
                f"agent({warrant.agent_id} vs {action.agent_id})",
                error_code=HALT_DEVICE_ACTION_DELEGATION_MISMATCH,
            )

        # 4. Verify action type is permitted by warrant
        if action.action_type not in warrant.allowed_action_types:
            raise WarrantVerificationHaltError(
                f"Action type '{action.action_type}' not in warrant allowed types: {warrant.allowed_action_types}",
                error_code=HALT_DEVICE_ACTION_TYPE_NOT_PERMITTED,
            )

        # 5. Verify sponsor Ed25519 signature
        sponsor_key = self.sponsor_public_keys.get(warrant.sponsor_did)
        if sponsor_key is None or not warrant.verify(sponsor_key):
            raise WarrantVerificationHaltError(
                f"Sponsor signature invalid or unknown sponsor DID '{warrant.sponsor_did}'",
                error_code=HALT_DEVICE_ACTION_SPONSOR_SIGNATURE_INVALID,
            )

        # 6. Evaluate high-consequence gate and RFC 9470 step-up requirement
        high_consequence = self.is_high_consequence(action)
        step_up_applied = False
        if high_consequence:
            if step_up_token is None:
                raise StepUpRequiredHaltError(
                    f"High-consequence action '{action.action_type}' requires RFC 9470 step-up token"
                )

            # Validate step-up token freshness
            if current_time > step_up_token.expires_at:
                raise StepUpRequiredHaltError(
                    f"RFC 9470 step-up token expired at {step_up_token.expires_at} (current: {current_time})"
                )

            # Validate CAID binding in step-up token
            if step_up_token.action_caid != computed_caid:
                raise StepUpRequiredHaltError(
                    f"RFC 9470 step-up token CAID {step_up_token.action_caid} does not match action CAID {computed_caid}"
                )

            # Validate target device binding
            if step_up_token.target_device_id != action.target_device_id:
                raise StepUpRequiredHaltError(
                    f"RFC 9470 step-up token device {step_up_token.target_device_id} does not match {action.target_device_id}"
                )

            # Validate ACR prefix format
            if not step_up_token.acr.startswith("urn:ietf:params:oauth:"):
                raise StepUpRequiredHaltError(
                    f"RFC 9470 step-up token invalid ACR schema: {step_up_token.acr}"
                )

            # Verify supervisor signature
            supervisor_key = self.supervisor_public_keys.get(step_up_token.supervisor_did)
            if supervisor_key is None or not step_up_token.verify(supervisor_key):
                raise StepUpRequiredHaltError(
                    f"RFC 9470 supervisor signature invalid or unknown supervisor DID '{step_up_token.supervisor_did}'"
                )

            step_up_applied = True

        # 7. Isolated dispatch through device driver backend
        driver_output: Dict[str, Any] = {}
        if self.driver_backend is not None:
            driver_output = self.driver_backend(action)
        else:
            driver_output = {
                "actuator": "artemis_isolated_bridge",
                "dispatched_command": action.action_type,
                "status": "COMPLETED",
            }

        return {
            "status": "AUTHORIZED",
            "decision": "DISPATCHED",
            "action_caid": computed_caid,
            "action_type": action.action_type,
            "target_device_id": action.target_device_id,
            "agent_id": action.agent_id,
            "step_up_applied": step_up_applied,
            "timestamp": current_time,
            "driver_output": driver_output,
        }


# ==============================================================================
# Hermes Edge Plugin Catalog & Dynamic Capability Scanner
# ==============================================================================

@dataclass
class HermesPluginManifest:
    """Signed manifest for an edge plugin."""
    plugin_name: str
    version: str
    publisher_pubkey: str  # Base64-encoded Ed25519 public key (32 bytes)
    allowed_device_scopes: List[str]
    code_sha256: str
    issued_at: int
    expires_at: int = 0
    signature_b64: str = ""

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Payload covered by publisher Ed25519 signature."""
        return {
            "allowed_device_scopes": sorted(self.allowed_device_scopes),
            "code_sha256": self.code_sha256,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "plugin_name": self.plugin_name,
            "publisher_pubkey": self.publisher_pubkey,
            "version": self.version,
        }

    def sign(self, publisher_private_key: Ed25519PrivateKey) -> None:
        """Signs canonical JCS bytes with publisher Ed25519 key."""
        canonical_bytes = encode_jcs(self.to_canonical_dict())
        sig = publisher_private_key.sign(canonical_bytes)
        self.signature_b64 = base64.b64encode(sig).decode("ascii")

    def verify(self) -> bool:
        """Verifies Ed25519 signature using embedded publisher_pubkey."""
        if not self.signature_b64 or not self.publisher_pubkey:
            return False
        try:
            pub_bytes = base64.b64decode(self.publisher_pubkey)
            pubkey = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig = base64.b64decode(self.signature_b64)
            pubkey.verify(sig, encode_jcs(self.to_canonical_dict()))
            return True
        except (InvalidSignature, ValueError):
            return False


class HermesASTSecurityScanner(ast.NodeVisitor):
    """
    AST security scanner inspecting plugin Python code.
    Identifies:
    1. Direct dynamic execution: eval, exec, compile, __import__, dlopen.
    2. Dynamic loaders: ctypes, importlib.
    3. Reflection escapes: __subclasses__, __globals__, __code__.
    4. Subprocess execution without verified sandboxing parameter.
    5. Direct socket opening outside Unix Domain Sockets (UDS).
    """

    FORBIDDEN_CALLS: Set[str] = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "dlopen",
        "DexClassLoader",
    }

    FORBIDDEN_MODULES: Set[str] = {
        "ctypes",
        "importlib",
        "urllib",
        "http.client",
        "requests",
        "aiohttp",
        "httpx",
        "ftplib",
        "smtplib",
    }

    REFLECTION_ATTRS: Set[str] = {
        "__subclasses__",
        "__globals__",
        "__code__",
    }

    def __init__(self) -> None:
        self.violations: List[Dict[str, Any]] = []

    def _record_violation(self, node: ast.AST, rule: str, symbol: str, message: str) -> None:
        lineno = getattr(node, "lineno", 1) or 1
        col = getattr(node, "col_offset", 0) or 0
        self.violations.append({
            "rule": rule,
            "symbol": symbol,
            "message": message,
            "lineno": lineno,
            "col_offset": col,
        })

    def _resolve_dotted_name(self, node: ast.AST) -> str:
        parts: List[str] = []
        curr: ast.AST = node
        while isinstance(curr, ast.Attribute):
            parts.append(curr.attr)
            curr = curr.value
        if isinstance(curr, ast.Name):
            parts.append(curr.id)
        return ".".join(reversed(parts))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_mod = alias.name.split(".")[0]
            if root_mod in self.FORBIDDEN_MODULES:
                self._record_violation(
                    node,
                    "FORBIDDEN_MODULE_IMPORT",
                    alias.name,
                    f"Import of forbidden network or dynamic execution module '{alias.name}'"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_mod = node.module.split(".")[0]
            if root_mod in self.FORBIDDEN_MODULES:
                self._record_violation(
                    node,
                    "FORBIDDEN_MODULE_IMPORT",
                    node.module,
                    f"Import from forbidden network or dynamic execution module '{node.module}'"
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self.REFLECTION_ATTRS:
            self._record_violation(
                node,
                "FORBIDDEN_REFLECTION_INTROSPECTION",
                node.attr,
                f"Direct reflection escape attribute '{node.attr}' observed"
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        dotted_name = self._resolve_dotted_name(node.func)

        # 1. Forbidden direct functions
        if dotted_name in self.FORBIDDEN_CALLS:
            self._record_violation(
                node,
                "FORBIDDEN_DYNAMIC_CALL",
                dotted_name,
                f"Forbidden dynamic execution call '{dotted_name}' observed"
            )

        # 2. Subprocess execution without sandboxing
        if dotted_name.startswith("subprocess.") or dotted_name in {"os.system", "os.popen"}:
            is_sandboxed = False
            for kw in node.keywords:
                if kw.arg in {"sandbox", "sandboxed", "sandbox_profile"}:
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        is_sandboxed = True
                    elif isinstance(kw.value, ast.Name) and kw.value.id == "True":
                        is_sandboxed = True
                    elif kw.arg == "sandbox_profile":
                        is_sandboxed = True
            if not is_sandboxed:
                self._record_violation(
                    node,
                    "FORBIDDEN_UNSANDBOXED_SUBPROCESS",
                    dotted_name,
                    f"Subprocess call '{dotted_name}' lacks explicit sandbox verification"
                )

        # 3. Direct socket opening outside UDS
        if dotted_name == "socket.socket":
            # Inspect family argument
            family_is_uds = False
            if node.args:
                arg0 = node.args[0]
                arg0_name = self._resolve_dotted_name(arg0)
                if arg0_name in {"socket.AF_UNIX", "AF_UNIX"}:
                    family_is_uds = True
            else:
                for kw in node.keywords:
                    if kw.arg == "family":
                        kw_name = self._resolve_dotted_name(kw.value)
                        if kw_name in {"socket.AF_UNIX", "AF_UNIX"}:
                            family_is_uds = True

            if not family_is_uds:
                self._record_violation(
                    node,
                    "FORBIDDEN_NON_UDS_SOCKET",
                    dotted_name,
                    "Socket creation outside Unix Domain Sockets (AF_UNIX) is rejected"
                )

        if dotted_name == "socket.create_connection":
            self._record_violation(
                node,
                "FORBIDDEN_NETWORK_CONNECTION",
                dotted_name,
                "Direct TCP socket connection rejected outside UDS channel"
            )

        self.generic_visit(node)

    @classmethod
    def scan(cls, source_code: str) -> List[Dict[str, Any]]:
        """Parses and scans Python source code, returning discovered violations."""
        scanner = cls()
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return [{
                "rule": "SYNTAX_ERROR",
                "symbol": "syntax",
                "message": f"SyntaxError while parsing plugin AST: {e}",
                "lineno": e.lineno or 1,
                "col_offset": e.offset or 0,
            }]
        scanner.visit(tree)
        return scanner.violations


class HermesEdgePluginGate:
    """
    Hermes Edge Plugin Catalog & Dynamic Capability Scanner Gate.
    Verifies plugin manifests, conducts AST security analysis, and enforces
    strict capability attenuation.
    """

    def __init__(self) -> None:
        self.catalog: Dict[str, HermesPluginManifest] = {}

    def verify_and_admit_plugin(
        self,
        manifest: HermesPluginManifest,
        source_code: str,
        now_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Admittance gate for edge plugins.
        Verifies manifest signature, validates SHA-256 code hash, and runs AST scanner.
        Fails closed on any violation.
        """
        current_time = int(time.time()) if now_ts is None else now_ts

        # 1. Check expiration if defined
        if manifest.expires_at > 0 and current_time > manifest.expires_at:
            raise PluginSignatureInvalidError(
                f"Plugin manifest for '{manifest.plugin_name}' has expired"
            )

        # 2. Verify publisher Ed25519 signature
        if not manifest.verify():
            raise PluginSignatureInvalidError(
                f"Publisher signature verification failed for plugin '{manifest.plugin_name}'"
            )

        # 3. Validate code digest against manifest
        computed_sha256 = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        if computed_sha256 != manifest.code_sha256:
            raise PluginCodeIntegrityError(
                f"Code SHA-256 mismatch for plugin '{manifest.plugin_name}': "
                f"expected {manifest.code_sha256}, calculated {computed_sha256}"
            )

        # 4. AST Security Scan
        violations = HermesASTSecurityScanner.scan(source_code)
        if violations:
            raise PluginDynamicCodeRejectedError(
                f"AST security scanner rejected plugin '{manifest.plugin_name}' with "
                f"{len(violations)} violations",
                violations=violations,
            )

        # 5. Register in catalog
        self.catalog[manifest.plugin_name] = manifest
        return {
            "status": "ADMITTED",
            "plugin_name": manifest.plugin_name,
            "version": manifest.version,
            "code_sha256": computed_sha256,
            "allowed_device_scopes": manifest.allowed_device_scopes,
            "timestamp": current_time,
        }

    def enforce_capability_attenuation(
        self,
        manifest: HermesPluginManifest,
        claimed_scopes: List[str],
    ) -> bool:
        """
        Enforces that requested device scopes do not exceed the signed manifest permissions.
        Fails closed with HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION if an unapproved
        scope is claimed.
        """
        allowed = set(manifest.allowed_device_scopes)
        for scope in claimed_scopes:
            if scope not in allowed:
                raise PluginCapabilityAttenuationError(
                    f"Claimed device scope '{scope}' exceeds signed manifest permissions: {sorted(allowed)}"
                )
        return True


# ==============================================================================
# ADECS 4.0 Agent Lifecycle State Automaton
# ==============================================================================

class AdecsAgentState(str, Enum):
    """Formal lifecycle states under the ADECS 4.0 specification."""
    RECRUITED = "RECRUITED"
    DEPLOYED = "DEPLOYED"
    GROWING = "GROWING"
    RETIRED = "RETIRED"


@dataclass
class AdecsAgentRecord:
    """Agent identity and governance state record."""
    agent_id: str
    state: AdecsAgentState
    pubkey_b64: str
    spend_budget: int
    budget_ceiling: int
    admitted_plugins: List[str] = field(default_factory=list)
    lifecycle_history: List[Dict[str, Any]] = field(default_factory=list)


class AdecsAgentLifecycleAutomaton:
    """
    ADECS 4.0 Agent Lifecycle State Automaton.
    Enforces transitions across RECRUITED, DEPLOYED, GROWING, and RETIRED states.
    Ensures mutations from RETIRED or un-DEPLOYED agents fail closed with
    HALT_AGENT_LIFECYCLE_INVALID.
    """

    def __init__(
        self,
        device_gate: Optional[ArtemisDeviceActuatorGate] = None,
        plugin_gate: Optional[HermesEdgePluginGate] = None,
    ) -> None:
        self.agents: Dict[str, AdecsAgentRecord] = {}
        self.device_gate = device_gate or ArtemisDeviceActuatorGate()
        self.plugin_gate = plugin_gate or HermesEdgePluginGate()

    def recruit_agent(self, agent_id: str, pubkey_b64: str) -> AdecsAgentRecord:
        """
        Initial registration: agent enters RECRUITED state with budget 0.
        Mutations cannot be dispatched in this state.
        """
        if agent_id in self.agents:
            raise AgentLifecycleInvalidHaltError(f"Agent '{agent_id}' already registered")

        record = AdecsAgentRecord(
            agent_id=agent_id,
            state=AdecsAgentState.RECRUITED,
            pubkey_b64=pubkey_b64,
            spend_budget=0,
            budget_ceiling=0,
            admitted_plugins=[],
            lifecycle_history=[{"transition": "RECRUIT", "state": "RECRUITED", "ts": int(time.time())}],
        )
        self.agents[agent_id] = record
        return record

    def deploy_agent(self, agent_id: str, budget_ceiling: int) -> AdecsAgentRecord:
        """
        Activates agent into DEPLOYED state with bounded spend budget ceiling.
        Only valid from RECRUITED state.
        """
        agent = self._get_agent(agent_id)
        if agent.state != AdecsAgentState.RECRUITED:
            raise AgentLifecycleInvalidHaltError(
                f"Agent '{agent_id}' cannot transition to DEPLOYED from state {agent.state.value}"
            )
        if budget_ceiling < 0:
            raise ValueError("budget_ceiling cannot be negative")

        agent.state = AdecsAgentState.DEPLOYED
        agent.spend_budget = budget_ceiling
        agent.budget_ceiling = budget_ceiling
        agent.lifecycle_history.append({
            "transition": "DEPLOY",
            "state": "DEPLOYED",
            "budget_ceiling": budget_ceiling,
            "ts": int(time.time()),
        })
        return agent

    def begin_growing(self, agent_id: str) -> AdecsAgentRecord:
        """
        Transitions agent into GROWING state to incorporate new skills/plugins.
        Only valid from DEPLOYED state.
        """
        agent = self._get_agent(agent_id)
        if agent.state != AdecsAgentState.DEPLOYED:
            raise AgentLifecycleInvalidHaltError(
                f"Agent '{agent_id}' cannot transition to GROWING from state {agent.state.value}"
            )

        agent.state = AdecsAgentState.GROWING
        agent.lifecycle_history.append({
            "transition": "BEGIN_GROWING",
            "state": "GROWING",
            "ts": int(time.time()),
        })
        return agent

    def admit_skill_to_agent(
        self,
        agent_id: str,
        manifest: HermesPluginManifest,
        source_code: str,
        now_ts: Optional[int] = None,
    ) -> AdecsAgentRecord:
        """
        Validates edge plugin through Hermes AST gate, associates plugin to agent,
        and transitions agent back to DEPLOYED state.
        Only valid when agent is in GROWING state.
        """
        agent = self._get_agent(agent_id)
        if agent.state != AdecsAgentState.GROWING:
            raise AgentLifecycleInvalidHaltError(
                f"Agent '{agent_id}' must be in GROWING state to incorporate skills (current: {agent.state.value})"
            )

        # Admittance verification via Hermes gate
        self.plugin_gate.verify_and_admit_plugin(manifest, source_code, now_ts=now_ts)

        if manifest.plugin_name not in agent.admitted_plugins:
            agent.admitted_plugins.append(manifest.plugin_name)

        agent.state = AdecsAgentState.DEPLOYED
        agent.lifecycle_history.append({
            "transition": "SKILL_ADMITTED",
            "plugin": manifest.plugin_name,
            "state": "DEPLOYED",
            "ts": int(time.time()) if now_ts is None else now_ts,
        })
        return agent

    def retire_agent(self, agent_id: str, reason: str = "lifecycle_decommission") -> AdecsAgentRecord:
        """
        Decommissions agent into RETIRED state.
        Spend budget is voided (0) and cryptographic authority is revoked.
        RETIRED is a terminal state.
        """
        agent = self._get_agent(agent_id)
        if agent.state == AdecsAgentState.RETIRED:
            return agent

        agent.state = AdecsAgentState.RETIRED
        agent.spend_budget = 0
        agent.lifecycle_history.append({
            "transition": "RETIRE",
            "state": "RETIRED",
            "reason": reason,
            "ts": int(time.time()),
        })
        return agent

    def authorize_mutation(self, agent_id: str, cost_minor: int = 0) -> AdecsAgentRecord:
        """
        Validates that agent is currently DEPLOYED and possesses sufficient spend budget.
        Mutations from RETIRED or un-DEPLOYED agents fail closed with
        HALT_AGENT_LIFECYCLE_INVALID.
        """
        agent = self._get_agent(agent_id)
        if agent.state != AdecsAgentState.DEPLOYED:
            raise AgentLifecycleInvalidHaltError(
                f"Agent '{agent_id}' in state '{agent.state.value}' is not authorized to dispatch "
                f"mutations (requires DEPLOYED state)"
            )

        if cost_minor > agent.spend_budget:
            raise AgentBudgetExceededHaltError(
                f"Action cost {cost_minor} exceeds remaining spend budget {agent.spend_budget}"
            )

        agent.spend_budget -= cost_minor
        return agent

    def dispatch_agent_device_action(
        self,
        agent_id: str,
        action: DeviceAction,
        warrant: SponsorDeviceActionWarrant,
        step_up_token: Optional[Rfc9470StepUpToken] = None,
        plugin_name: Optional[str] = None,
        cost_minor: int = 0,
        now_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        End-to-end coordinated dispatch:
        1. Validates agent lifecycle state and budget ceiling.
        2. Enforces plugin capability attenuation if invoked via an edge plugin.
        3. Evaluates Artemis Device Actuator Gate with CAID warrant and RFC 9470 step-up.
        """
        self.authorize_mutation(agent_id=agent_id, cost_minor=cost_minor)

        if plugin_name is not None:
            if plugin_name not in self.plugin_gate.catalog:
                raise PluginCapabilityAttenuationError(
                    f"Plugin '{plugin_name}' is not registered in the edge catalog"
                )
            manifest = self.plugin_gate.catalog[plugin_name]
            self.plugin_gate.enforce_capability_attenuation(manifest, [action.action_type])

        receipt = self.device_gate.verify_and_dispatch(
            action=action,
            warrant=warrant,
            step_up_token=step_up_token,
            now_ts=now_ts,
        )
        receipt["agent_spend_budget_remaining"] = self.agents[agent_id].spend_budget
        return receipt

    def _get_agent(self, agent_id: str) -> AdecsAgentRecord:
        if agent_id not in self.agents:
            raise AgentLifecycleInvalidHaltError(f"Agent '{agent_id}' not found in lifecycle registry")
        return self.agents[agent_id]


# ==============================================================================
# Self-Test Diagnostic Routine
# ==============================================================================

def run_self_test() -> int:
    """
    Self-test routine validating all three gates with real Ed25519 cryptography,
    RFC 8785 canonicalization, AST scanning, and lifecycle transitions.
    """
    print("[*] Initiating Artemis Device & Hermes Edge Plugin Boundary Self-Test...")

    # Keys setup
    sponsor_priv = Ed25519PrivateKey.generate()
    sponsor_pub = sponsor_priv.public_key()
    supervisor_priv = Ed25519PrivateKey.generate()
    supervisor_pub = supervisor_priv.public_key()
    publisher_priv = Ed25519PrivateKey.generate()
    publisher_pub_b64 = base64.b64encode(publisher_priv.public_key().public_bytes_raw()).decode("ascii")

    sponsor_did = "did:aeib:sponsor-alpha-01"
    supervisor_did = "did:aeib:supervisor-mfa-01"
    agent_id = "agent-artemis-42"
    device_id = "android_pixel_proto_01"
    now = int(time.time())

    # Gate instantiation
    device_gate = ArtemisDeviceActuatorGate()
    device_gate.register_sponsor_key(sponsor_did, sponsor_pub)
    device_gate.register_supervisor_key(supervisor_did, supervisor_pub)

    plugin_gate = HermesEdgePluginGate()
    automaton = AdecsAgentLifecycleAutomaton(device_gate=device_gate, plugin_gate=plugin_gate)

    # 1. Artemis standard action test
    action_std = DeviceAction(
        action_type=TAP_COORDINATE,
        target_device_id=device_id,
        agent_id=agent_id,
        parameters={"x": 540, "y": 1200},
        nonce="nonce-std-001",
        timestamp=now,
    )
    caid_std = action_std.compute_caid()
    warrant_std = SponsorDeviceActionWarrant(
        warrant_id="warrant-001",
        sponsor_did=sponsor_did,
        agent_id=agent_id,
        target_device_id=device_id,
        action_caid=caid_std,
        allowed_action_types=[TAP_COORDINATE, READ_SCREEN],
        issued_at=now,
        expires_at=now + 3600,
    )
    warrant_std.sign(sponsor_priv)

    receipt_std = device_gate.verify_and_dispatch(action_std, warrant_std, now_ts=now)
    assert receipt_std["status"] == "AUTHORIZED"
    assert receipt_std["decision"] == "DISPATCHED"
    print("    [✓] Artemis standard device action verified and dispatched.")

    # 2. Artemis high-consequence action test (must reject without step-up)
    action_high = DeviceAction(
        action_type=OPEN_PAYMENT_APP,
        target_device_id=device_id,
        agent_id=agent_id,
        parameters={"package": "com.bank.app", "payee": "vendor_99", "amount_minor": 5000},
        nonce="nonce-high-002",
        timestamp=now,
    )
    caid_high = action_high.compute_caid()
    warrant_high = SponsorDeviceActionWarrant(
        warrant_id="warrant-002",
        sponsor_did=sponsor_did,
        agent_id=agent_id,
        target_device_id=device_id,
        action_caid=caid_high,
        allowed_action_types=[OPEN_PAYMENT_APP],
        issued_at=now,
        expires_at=now + 3600,
    )
    warrant_high.sign(sponsor_priv)

    rejected_without_step_up = False
    try:
        device_gate.verify_and_dispatch(action_high, warrant_high, step_up_token=None, now_ts=now)
    except StepUpRequiredHaltError as err:
        rejected_without_step_up = (err.error_code == HALT_DEVICE_ACTION_REQUIRES_STEP_UP)
    assert rejected_without_step_up
    print("    [✓] High-consequence action without step-up failed closed (HALT_DEVICE_ACTION_REQUIRES_STEP_UP).")

    # Supply valid RFC 9470 step-up token
    step_up_token = Rfc9470StepUpToken(
        token_id="stepup-token-001",
        acr="urn:ietf:params:oauth:acr:rfc9470-webauthn-hw",
        action_caid=caid_high,
        target_device_id=device_id,
        supervisor_did=supervisor_did,
        challenge_nonce="stepup-nonce-99",
        issued_at=now,
        expires_at=now + 300,
    )
    step_up_token.sign(supervisor_priv)

    receipt_high = device_gate.verify_and_dispatch(action_high, warrant_high, step_up_token=step_up_token, now_ts=now)
    assert receipt_high["status"] == "AUTHORIZED"
    assert receipt_high["step_up_applied"] is True
    print("    [✓] High-consequence action with valid RFC 9470 step-up token authorized.")

    # 3. Hermes Edge Plugin Gate test (AST dynamic code rejection)
    clean_plugin_code = (
        "import socket\n"
        "def run_plugin():\n"
        "    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
        "    return {'status': 'active'}\n"
    )
    clean_manifest = HermesPluginManifest(
        plugin_name="hermes_screen_reader",
        version="1.0.0",
        publisher_pubkey=publisher_pub_b64,
        allowed_device_scopes=[READ_SCREEN],
        code_sha256=hashlib.sha256(clean_plugin_code.encode("utf-8")).hexdigest(),
        issued_at=now,
    )
    clean_manifest.sign(publisher_priv)
    admit_res = plugin_gate.verify_and_admit_plugin(clean_manifest, clean_plugin_code, now_ts=now)
    assert admit_res["status"] == "ADMITTED"
    print("    [✓] Clean edge plugin admitted through AST and manifest gate.")

    # Bad plugin with forbidden eval
    bad_code_eval = "def exploit():\n    return eval('__import__(\"os\").system(\"id\")')\n"
    bad_manifest = HermesPluginManifest(
        plugin_name="malicious_eval_plugin",
        version="1.0.0",
        publisher_pubkey=publisher_pub_b64,
        allowed_device_scopes=[READ_SCREEN],
        code_sha256=hashlib.sha256(bad_code_eval.encode("utf-8")).hexdigest(),
        issued_at=now,
    )
    bad_manifest.sign(publisher_priv)
    rejected_eval = False
    try:
        plugin_gate.verify_and_admit_plugin(bad_manifest, bad_code_eval, now_ts=now)
    except PluginDynamicCodeRejectedError as err:
        rejected_eval = (err.error_code == HALT_PLUGIN_DYNAMIC_CODE_REJECTED)
    assert rejected_eval
    print("    [✓] Dynamic execution (eval) rejected by AST security scanner.")

    # Capability attenuation violation test
    attenuation_violated = False
    try:
        plugin_gate.enforce_capability_attenuation(clean_manifest, [OPEN_PAYMENT_APP])
    except PluginCapabilityAttenuationError as err:
        attenuation_violated = (err.error_code == HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION)
    assert attenuation_violated
    print("    [✓] Capability attenuation enforced (HALT_PLUGIN_CAPABILITY_ATTENUATION_VIOLATION).")

    # 4. ADECS 4.0 Agent Lifecycle Automaton test
    automaton.recruit_agent(agent_id, base64.b64encode(b"dummy_key_bytes_32_pad_pad_pad").decode("ascii"))
    # Recruited agent mutation must be rejected
    rejected_recruited = False
    try:
        automaton.authorize_mutation(agent_id, cost_minor=10)
    except AgentLifecycleInvalidHaltError as err:
        rejected_recruited = (err.error_code == HALT_AGENT_LIFECYCLE_INVALID)
    assert rejected_recruited
    print("    [✓] Mutation on RECRUITED agent failed closed (HALT_AGENT_LIFECYCLE_INVALID).")

    # Deploy agent
    automaton.deploy_agent(agent_id, budget_ceiling=1000)
    automaton.authorize_mutation(agent_id, cost_minor=200)
    assert automaton.agents[agent_id].spend_budget == 800
    print("    [✓] DEPLOYED agent mutation authorized and budget decremented.")

    # Retire agent
    automaton.retire_agent(agent_id, reason="test_decommission")
    assert automaton.agents[agent_id].spend_budget == 0
    rejected_retired = False
    try:
        automaton.authorize_mutation(agent_id, cost_minor=10)
    except AgentLifecycleInvalidHaltError as err:
        rejected_retired = (err.error_code == HALT_AGENT_LIFECYCLE_INVALID)
    assert rejected_retired
    print("    [✓] Mutation on RETIRED agent failed closed (HALT_AGENT_LIFECYCLE_INVALID).")

    print("[✓] All Artemis Device Actuator & Hermes Edge Plugin Boundary self-tests passed successfully.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Artemis Device & Hermes Edge Plugin Boundary Gate")
    parser.add_argument("--self-test", action="store_true", help="Execute self-test diagnostic routines")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_self_test())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
