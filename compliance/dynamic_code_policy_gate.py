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
compliance/dynamic_code_policy_gate.py
================================================================================
Dynamic Execution Policy & Signed Plugin Manifest Gate.
Evaluated under the stated model. Prototype scaffold for AEIB Station 1.

Enforces:
1. AST Dynamic Execution Ban (DynamicExecutionASTScanner):
   - Bans direct function calls: eval, exec, compile, __import__.
   - Bans module imports and attribute accesses: importlib, ctypes, subprocess.
   - Bans dynamic class and native loader calls: ctypes.CDLL, dlopen, DexClassLoader.
   - Detects reflection sandbox escape patterns: __subclasses__, __globals__, __code__.
2. Signed Plugin Manifest Enforcement (SignedPluginManifestVerifier):
   - Standard AEIB plugin manifest schema:
     plugin_id, version, publisher_did, publisher_pubkey_b64,
     entrypoint_file, entrypoint_sha256, allowed_capabilities, issued_at, expires_at.
   - Cryptographic verification via real Ed25519 over RFC 8785 JCS canonical bytes.
   - SHA-256 digest validation of entrypoint code against manifest entrypoint_sha256.
   - Publisher DID thumbprint verification against publisher public key.
   - Dynamic code AST scanning of entrypoint code before admission.
   - Fails closed on unsigned, expired, tampered, or dynamic plugins.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

from src.jcs_canonicalizer import encode_jcs


# ------------------------------------------------------------------------------
# AST Scanner Data Structures & Constants
# ------------------------------------------------------------------------------

FORBIDDEN_DIRECT_CALLS = {
    "eval": "CRITICAL_DYNAMIC_EXECUTION_EVAL",
    "exec": "CRITICAL_DYNAMIC_EXECUTION_EXEC",
    "compile": "CRITICAL_DYNAMIC_EXECUTION_COMPILE",
    "__import__": "CRITICAL_DYNAMIC_EXECUTION_IMPORT",
    "dlopen": "CRITICAL_DYNAMIC_LOADER_DLOPEN",
    "DexClassLoader": "CRITICAL_DYNAMIC_LOADER_DEXCLASSLOADER",
}

FORBIDDEN_MODULE_ROOTS = {
    "importlib": "CRITICAL_DYNAMIC_EXECUTION_IMPORTLIB",
    "ctypes": "CRITICAL_DYNAMIC_EXECUTION_CTYPES",
    "subprocess": "CRITICAL_DYNAMIC_EXECUTION_SUBPROCESS",
}

NATIVE_LOADER_ATTRS = {
    "CDLL": "CRITICAL_DYNAMIC_LOADER_CDLL",
    "cdll": "CRITICAL_DYNAMIC_LOADER_CDLL",
    "windll": "CRITICAL_DYNAMIC_LOADER_CDLL",
    "oledll": "CRITICAL_DYNAMIC_LOADER_CDLL",
    "LoadLibrary": "CRITICAL_DYNAMIC_LOADER_CDLL",
    "dlopen": "CRITICAL_DYNAMIC_LOADER_DLOPEN",
    "DexClassLoader": "CRITICAL_DYNAMIC_LOADER_DEXCLASSLOADER",
}

REFLECTION_ESCAPE_ATTRS = {
    "__subclasses__": "CRITICAL_REFLECTION_INTROSPECTION",
    "__globals__": "CRITICAL_REFLECTION_INTROSPECTION",
    "__code__": "CRITICAL_REFLECTION_INTROSPECTION",
}


@dataclass(frozen=True)
class ASTViolation:
    """Represents an observed AST policy violation."""
    rule_id: str
    severity: str  # "CRITICAL" | "MAJOR"
    message: str
    line_number: int
    column_offset: int
    node_type: str
    symbol: str


@dataclass(frozen=True)
class ASTScanReport:
    """Structured report returned by DynamicExecutionASTScanner."""
    target: str
    violations: List[ASTViolation]
    is_clean: bool
    has_critical_violations: bool

    def summary_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "is_clean": self.is_clean,
            "has_critical_violations": self.has_critical_violations,
            "total_violations": len(self.violations),
            "critical_violations_count": sum(1 for v in self.violations if v.severity == "CRITICAL"),
            "major_violations_count": sum(1 for v in self.violations if v.severity == "MAJOR"),
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "message": v.message,
                    "line_number": v.line_number,
                    "column_offset": v.column_offset,
                    "node_type": v.node_type,
                    "symbol": v.symbol,
                }
                for v in self.violations
            ],
        }


# ------------------------------------------------------------------------------
# AST Dynamic Execution Ban Visitor & Scanner
# ------------------------------------------------------------------------------

def _resolve_attribute_chain(node: ast.AST) -> str:
    """Recursively resolves an attribute chain to dotted string (e.g. 'ctypes.CDLL')."""
    parts: List[str] = []
    curr: ast.AST = node
    while isinstance(curr, ast.Attribute):
        parts.append(curr.attr)
        curr = curr.value
    if isinstance(curr, ast.Name):
        parts.append(curr.id)
    return ".".join(reversed(parts))


class DynamicExecutionASTVisitor(ast.NodeVisitor):
    """
    AST visitor detecting forbidden dynamic code execution, dynamic imports,
    native library loaders, and reflection sandbox escapes.
    """

    def __init__(self, filename: str = "<memory>") -> None:
        self.filename = filename
        self.violations: List[ASTViolation] = []
        self._recorded_keys: Set[Tuple[int, str, str]] = set()

    def _record_violation(
        self,
        node: ast.AST,
        rule_id: str,
        severity: str,
        message: str,
        symbol: str,
    ) -> None:
        lineno = getattr(node, "lineno", 1) or 1
        col_offset = getattr(node, "col_offset", 0) or 0
        key = (lineno, rule_id, symbol)
        if key in self._recorded_keys:
            return
        self._recorded_keys.add(key)
        self.violations.append(
            ASTViolation(
                rule_id=rule_id,
                severity=severity,
                message=message,
                line_number=lineno,
                column_offset=col_offset,
                node_type=type(node).__name__,
                symbol=symbol,
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_module = alias.name.split(".")[0]
            if root_module in FORBIDDEN_MODULE_ROOTS:
                rule_id = FORBIDDEN_MODULE_ROOTS[root_module]
                self._record_violation(
                    node=node,
                    rule_id=rule_id,
                    severity="CRITICAL",
                    message=f"Forbidden module import observed: '{alias.name}'",
                    symbol=alias.name,
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_module = node.module.split(".")[0]
            if root_module in FORBIDDEN_MODULE_ROOTS:
                rule_id = FORBIDDEN_MODULE_ROOTS[root_module]
                self._record_violation(
                    node=node,
                    rule_id=rule_id,
                    severity="CRITICAL",
                    message=f"Forbidden from-import from module: '{node.module}'",
                    symbol=node.module,
                )
        for alias in node.names:
            if alias.name in FORBIDDEN_DIRECT_CALLS:
                rule_id = FORBIDDEN_DIRECT_CALLS[alias.name]
                self._record_violation(
                    node=node,
                    rule_id=rule_id,
                    severity="CRITICAL",
                    message=f"Forbidden dynamic execution symbol imported: '{alias.name}'",
                    symbol=alias.name,
                )
            elif alias.name in NATIVE_LOADER_ATTRS:
                rule_id = NATIVE_LOADER_ATTRS[alias.name]
                self._record_violation(
                    node=node,
                    rule_id=rule_id,
                    severity="CRITICAL",
                    message=f"Forbidden native/dynamic loader symbol imported: '{alias.name}'",
                    symbol=alias.name,
                )
            elif alias.name == "import_module":
                self._record_violation(
                    node=node,
                    rule_id="CRITICAL_DYNAMIC_EXECUTION_IMPORTLIB",
                    severity="CRITICAL",
                    message="Forbidden dynamic import function imported: 'import_module'",
                    symbol=alias.name,
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # 1. Direct function calls
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in FORBIDDEN_DIRECT_CALLS:
                rule_id = FORBIDDEN_DIRECT_CALLS[func_name]
                self._record_violation(
                    node=node,
                    rule_id=rule_id,
                    severity="CRITICAL",
                    message=f"Forbidden direct function call observed: '{func_name}()'",
                    symbol=func_name,
                )
            elif func_name == "getattr":
                # Check for reflective acquisition of forbidden primitives
                if (
                    len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                ):
                    attr_val = node.args[1].value
                    if attr_val in FORBIDDEN_DIRECT_CALLS or attr_val in NATIVE_LOADER_ATTRS or attr_val == "import_module":
                        self._record_violation(
                            node=node,
                            rule_id="CRITICAL_DYNAMIC_EXECUTION_REFLECTIVE",
                            severity="CRITICAL",
                            message=f"Reflective dynamic symbol resolution observed: getattr(..., '{attr_val}')",
                            symbol=f"getattr:{attr_val}",
                        )

        # 2. Attribute calls (e.g., ctypes.CDLL, importlib.import_module, builtins.eval)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            full_chain = _resolve_attribute_chain(node.func)

            if attr_name in FORBIDDEN_DIRECT_CALLS:
                rule_id = FORBIDDEN_DIRECT_CALLS[attr_name]
                self._record_violation(
                    node=node,
                    rule_id=rule_id,
                    severity="CRITICAL",
                    message=f"Forbidden dynamic execution call observed: '{full_chain}()'",
                    symbol=full_chain,
                )
            elif attr_name in NATIVE_LOADER_ATTRS:
                rule_id = NATIVE_LOADER_ATTRS[attr_name]
                self._record_violation(
                    node=node,
                    rule_id=rule_id,
                    severity="CRITICAL",
                    message=f"Forbidden native/dynamic loader call observed: '{full_chain}()'",
                    symbol=full_chain,
                )
            elif attr_name == "import_module" or full_chain.startswith("importlib."):
                self._record_violation(
                    node=node,
                    rule_id="CRITICAL_DYNAMIC_EXECUTION_IMPORTLIB",
                    severity="CRITICAL",
                    message=f"Forbidden dynamic import call observed: '{full_chain}()'",
                    symbol=full_chain,
                )
            elif full_chain.startswith("ctypes."):
                self._record_violation(
                    node=node,
                    rule_id="CRITICAL_DYNAMIC_EXECUTION_CTYPES",
                    severity="CRITICAL",
                    message=f"Forbidden ctypes invocation observed: '{full_chain}()'",
                    symbol=full_chain,
                )
            elif full_chain.startswith("subprocess."):
                self._record_violation(
                    node=node,
                    rule_id="CRITICAL_DYNAMIC_EXECUTION_SUBPROCESS",
                    severity="CRITICAL",
                    message=f"Forbidden subprocess invocation observed: '{full_chain}()'",
                    symbol=full_chain,
                )

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        full_chain = _resolve_attribute_chain(node)
        if node.attr in NATIVE_LOADER_ATTRS and full_chain.startswith("ctypes."):
            rule_id = NATIVE_LOADER_ATTRS[node.attr]
            self._record_violation(
                node=node,
                rule_id=rule_id,
                severity="CRITICAL",
                message=f"Forbidden native loader attribute access observed: '{full_chain}'",
                symbol=full_chain,
            )
        elif node.attr in REFLECTION_ESCAPE_ATTRS:
            rule_id = REFLECTION_ESCAPE_ATTRS[node.attr]
            self._record_violation(
                node=node,
                rule_id=rule_id,
                severity="CRITICAL",
                message=f"Forbidden reflection introspection attribute observed: '{node.attr}'",
                symbol=node.attr,
            )
        self.generic_visit(node)


class DynamicExecutionASTScanner:
    """
    Scans Python source code using ast.parse to detect dynamic code execution,
    untrusted native loaders, and reflection primitives.
    """

    def scan_code(self, source_code: str, filename: str = "<memory>") -> ASTScanReport:
        try:
            tree = ast.parse(source_code, filename=filename)
        except SyntaxError as exc:
            violation = ASTViolation(
                rule_id="CRITICAL_SYNTAX_ERROR",
                severity="CRITICAL",
                message=f"SyntaxError encountered while parsing AST: {exc}",
                line_number=getattr(exc, "lineno", 1) or 1,
                column_offset=getattr(exc, "offset", 0) or 0,
                node_type="SyntaxError",
                symbol=getattr(exc, "text", "") or "<unknown>",
            )
            return ASTScanReport(
                target=filename,
                violations=[violation],
                is_clean=False,
                has_critical_violations=True,
            )

        visitor = DynamicExecutionASTVisitor(filename=filename)
        visitor.visit(tree)
        violations = visitor.violations
        has_critical = any(v.severity == "CRITICAL" for v in violations)
        return ASTScanReport(
            target=filename,
            violations=violations,
            is_clean=len(violations) == 0,
            has_critical_violations=has_critical,
        )

    def scan_file(self, file_path: Union[str, Path]) -> ASTScanReport:
        path = Path(file_path)
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            violation = ASTViolation(
                rule_id="CRITICAL_FILE_READ_ERROR",
                severity="CRITICAL",
                message=f"Failed to read file: {exc}",
                line_number=1,
                column_offset=0,
                node_type="FileError",
                symbol=str(path),
            )
            return ASTScanReport(
                target=str(path),
                violations=[violation],
                is_clean=False,
                has_critical_violations=True,
            )
        return self.scan_code(content, filename=str(path))


# ------------------------------------------------------------------------------
# Publisher DID & Thumbprint Binding
# ------------------------------------------------------------------------------

def compute_ed25519_thumbprint(pubkey: Union[Ed25519PublicKey, bytes]) -> str:
    """
    Computes canonical SHA-256 hex thumbprint of an Ed25519 public key.
    """
    if isinstance(pubkey, Ed25519PublicKey):
        raw_bytes = pubkey.public_bytes_raw()
    elif isinstance(pubkey, bytes):
        raw_bytes = pubkey
    else:
        raise TypeError(f"Expected Ed25519PublicKey or bytes, observed {type(pubkey).__name__}")
    if len(raw_bytes) != 32:
        raise ValueError(f"Ed25519 public key must be exactly 32 bytes, observed {len(raw_bytes)}")
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_publisher_did(pubkey: Union[Ed25519PublicKey, bytes]) -> str:
    """
    Computes standard publisher DID bound to Ed25519 public key thumbprint:
    did:key:<sha256_thumbprint>
    """
    thumbprint = compute_ed25519_thumbprint(pubkey)
    return f"did:key:{thumbprint}"


def verify_publisher_did(publisher_did: str, pubkey: Union[Ed25519PublicKey, bytes]) -> bool:
    """
    Evaluates whether the publisher DID matches the public key thumbprint under the stated model.
    Accepts did:key:<sha256>, did:key:sha256:<sha256>, did:aeib:<sha256>, or RFC 7638 JWK thumbprint.
    """
    try:
        if isinstance(pubkey, Ed25519PublicKey):
            raw_bytes = pubkey.public_bytes_raw()
        elif isinstance(pubkey, bytes):
            raw_bytes = pubkey
        else:
            return False
        if len(raw_bytes) != 32:
            return False

        thumbprint_hex = hashlib.sha256(raw_bytes).hexdigest()

        # Interoperability with RFC 7638 JWK thumbprint
        jwk = {
            "crv": "Ed25519",
            "kty": "OKP",
            "x": base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("="),
        }
        jkt = base64.urlsafe_b64encode(hashlib.sha256(encode_jcs(jwk)).digest()).decode("ascii").rstrip("=")

        valid_set = {
            f"did:key:{thumbprint_hex}",
            f"did:key:sha256:{thumbprint_hex}",
            f"did:aeib:{thumbprint_hex}",
            f"did:key:{jkt}",
            f"did:key:jkt:{jkt}",
        }
        if publisher_did in valid_set:
            return True
        if publisher_did.endswith(thumbprint_hex) or publisher_did.endswith(jkt):
            return True
        return False
    except Exception:
        return False


def decode_pubkey_b64(pubkey_b64: str) -> Ed25519PublicKey:
    """Decodes standard or urlsafe base64 string to Ed25519PublicKey."""
    clean_b64 = pubkey_b64.strip()
    padded = clean_b64 + "=" * ((4 - len(clean_b64) % 4) % 4)
    try:
        raw_bytes = base64.b64decode(padded)
    except Exception:
        raw_bytes = base64.urlsafe_b64decode(padded)
    if len(raw_bytes) != 32:
        raise ValueError(f"Ed25519 public key must be exactly 32 bytes, observed {len(raw_bytes)}")
    return Ed25519PublicKey.from_public_bytes(raw_bytes)


# ------------------------------------------------------------------------------
# Signed Plugin Manifest Verifier
# ------------------------------------------------------------------------------

REQUIRED_MANIFEST_FIELDS: Set[str] = {
    "plugin_id",
    "version",
    "publisher_did",
    "publisher_pubkey_b64",
    "entrypoint_file",
    "entrypoint_sha256",
    "allowed_capabilities",
    "issued_at",
    "expires_at",
}


@dataclass(frozen=True)
class ManifestVerificationResult:
    """Result returned by SignedPluginManifestVerifier."""
    valid: bool
    disposition: str  # "AUTHORIZED" | "HALTED"
    rejection_code: Optional[str]
    plugin_id: Optional[str] = None
    manifest_caid: Optional[str] = None
    entrypoint_sha256: Optional[str] = None
    violations: List[ASTViolation] = field(default_factory=list)
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "disposition": self.disposition,
            "rejection_code": self.rejection_code,
            "plugin_id": self.plugin_id,
            "manifest_caid": self.manifest_caid,
            "entrypoint_sha256": self.entrypoint_sha256,
            "violations_count": len(self.violations),
            "details": self.details or {},
        }


class SignedPluginManifestVerifier:
    """
    Enforces cryptographic integrity and AST purity for AEIB plugin manifests.
    """

    def __init__(self, scanner: Optional[DynamicExecutionASTScanner] = None) -> None:
        self.scanner = scanner or DynamicExecutionASTScanner()

    @staticmethod
    def create_signed_manifest(
        plugin_id: str,
        version: str,
        private_key: Ed25519PrivateKey,
        entrypoint_path: Union[str, Path],
        allowed_capabilities: List[str],
        issued_at: Optional[int] = None,
        expires_at: Optional[int] = None,
        validity_duration_sec: int = 3600,
    ) -> Dict[str, Any]:
        """
        Helper to construct and sign an AEIB plugin manifest using RFC 8785 JCS and real Ed25519.
        """
        path = Path(entrypoint_path)
        if not path.exists():
            raise FileNotFoundError(f"Entrypoint file not found: {path}")

        code_bytes = path.read_bytes()
        code_sha256 = hashlib.sha256(code_bytes).hexdigest()

        pubkey = private_key.public_key()
        pubkey_b64 = base64.b64encode(pubkey.public_bytes_raw()).decode("ascii")
        publisher_did = compute_publisher_did(pubkey)

        now = int(time.time())
        ts_issued = issued_at if issued_at is not None else now
        ts_expires = expires_at if expires_at is not None else (ts_issued + validity_duration_sec)

        manifest_dict: Dict[str, Any] = {
            "allowed_capabilities": list(allowed_capabilities),
            "entrypoint_file": path.name,
            "entrypoint_sha256": code_sha256,
            "expires_at": ts_expires,
            "issued_at": ts_issued,
            "plugin_id": plugin_id,
            "publisher_did": publisher_did,
            "publisher_pubkey_b64": pubkey_b64,
            "version": version,
        }

        canonical_bytes = encode_jcs(manifest_dict)
        sig_bytes = private_key.sign(canonical_bytes)
        manifest_dict["signature_b64"] = base64.b64encode(sig_bytes).decode("ascii")
        return manifest_dict

    def verify_manifest_dict(
        self,
        manifest_dict: Dict[str, Any],
        base_dir: Optional[Union[str, Path]] = None,
        current_time: Optional[float] = None,
    ) -> ManifestVerificationResult:
        """
        Verifies a parsed manifest dictionary against cryptographic, temporal,
        digest, and AST dynamic code execution constraints.
        """
        # 1. Schema check
        missing_fields = REQUIRED_MANIFEST_FIELDS - set(manifest_dict.keys())
        if missing_fields:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_INVALID_MANIFEST_SCHEMA",
                details={"missing_fields": sorted(list(missing_fields))},
            )

        # 2. Signature presence
        sig_b64 = manifest_dict.get("signature_b64")
        if not sig_b64 or not isinstance(sig_b64, str) or not sig_b64.strip():
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_UNSIGNED_PLUGIN",
                plugin_id=manifest_dict.get("plugin_id"),
            )

        # 3. Decode publisher public key
        pubkey_b64 = manifest_dict.get("publisher_pubkey_b64", "")
        try:
            pubkey = decode_pubkey_b64(pubkey_b64)
        except Exception as exc:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_INVALID_PUBLISHER_KEY",
                plugin_id=manifest_dict.get("plugin_id"),
                details={"error": str(exc)},
            )

        # 4. Publisher DID thumbprint verification
        publisher_did = manifest_dict.get("publisher_did", "")
        if not verify_publisher_did(publisher_did, pubkey):
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_PUBLISHER_DID_MISMATCH",
                plugin_id=manifest_dict.get("plugin_id"),
                details={
                    "claimed_did": publisher_did,
                    "expected_thumbprint": compute_ed25519_thumbprint(pubkey),
                },
            )

        # 5. Ed25519 cryptographic signature verification over RFC 8785 JCS
        payload_to_verify = {k: v for k, v in manifest_dict.items() if k != "signature_b64"}
        try:
            canonical_bytes = encode_jcs(payload_to_verify)
            sig_bytes = base64.b64decode(sig_b64, validate=True)
            pubkey.verify(sig_bytes, canonical_bytes)
        except (InvalidSignature, ValueError, Exception) as exc:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_INVALID_PLUGIN_SIGNATURE",
                plugin_id=manifest_dict.get("plugin_id"),
                details={"error": str(exc)},
            )

        manifest_caid = hashlib.sha256(canonical_bytes).hexdigest()

        # 6. Temporal validity check
        now = current_time if current_time is not None else time.time()
        expires_at = manifest_dict.get("expires_at", 0)
        issued_at = manifest_dict.get("issued_at", 0)

        if now > expires_at or issued_at > expires_at:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_PLUGIN_MANIFEST_EXPIRED",
                plugin_id=manifest_dict.get("plugin_id"),
                manifest_caid=manifest_caid,
                details={"now": now, "issued_at": issued_at, "expires_at": expires_at},
            )

        # 7. Entrypoint file on-disk existence and SHA-256 match
        entrypoint_rel = manifest_dict.get("entrypoint_file", "")
        if base_dir:
            entrypoint_path = Path(base_dir) / entrypoint_rel
        else:
            entrypoint_path = Path(entrypoint_rel)

        if not entrypoint_path.exists() or not entrypoint_path.is_file():
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_PLUGIN_DIGEST_MISMATCH",
                plugin_id=manifest_dict.get("plugin_id"),
                manifest_caid=manifest_caid,
                details={"error": f"Entrypoint file not found: {entrypoint_path}"},
            )

        try:
            code_bytes = entrypoint_path.read_bytes()
        except Exception as exc:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_PLUGIN_DIGEST_MISMATCH",
                plugin_id=manifest_dict.get("plugin_id"),
                manifest_caid=manifest_caid,
                details={"error": f"Failed reading entrypoint: {exc}"},
            )

        actual_sha256 = hashlib.sha256(code_bytes).hexdigest()
        expected_sha256 = manifest_dict.get("entrypoint_sha256", "").strip()
        if expected_sha256.startswith("sha256:"):
            expected_sha256 = expected_sha256[7:]
        expected_sha256 = expected_sha256.lower()

        if actual_sha256.lower() != expected_sha256:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_PLUGIN_DIGEST_MISMATCH",
                plugin_id=manifest_dict.get("plugin_id"),
                manifest_caid=manifest_caid,
                entrypoint_sha256=actual_sha256,
                details={"actual_sha256": actual_sha256, "expected_sha256": expected_sha256},
            )

        # 8. Dynamic execution AST scan
        try:
            code_str = code_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_DYNAMIC_CODE_DETECTED",
                plugin_id=manifest_dict.get("plugin_id"),
                manifest_caid=manifest_caid,
                entrypoint_sha256=actual_sha256,
                details={"error": f"UTF-8 decode failure: {exc}"},
            )

        report = self.scanner.scan_code(code_str, filename=str(entrypoint_path))
        if report.has_critical_violations:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_DYNAMIC_CODE_DETECTED",
                plugin_id=manifest_dict.get("plugin_id"),
                manifest_caid=manifest_caid,
                entrypoint_sha256=actual_sha256,
                violations=report.violations,
                details={"critical_violations": [v.rule_id for v in report.violations if v.severity == "CRITICAL"]},
            )

        # All checks passed cleanly
        return ManifestVerificationResult(
            valid=True,
            disposition="AUTHORIZED",
            rejection_code=None,
            plugin_id=manifest_dict.get("plugin_id"),
            manifest_caid=manifest_caid,
            entrypoint_sha256=actual_sha256,
            violations=report.violations,
            details={
                "allowed_capabilities": manifest_dict.get("allowed_capabilities", []),
                "publisher_did": publisher_did,
                "version": manifest_dict.get("version"),
            },
        )

    def verify_manifest_file(
        self,
        manifest_path: Union[str, Path],
        current_time: Optional[float] = None,
    ) -> ManifestVerificationResult:
        path = Path(manifest_path)
        if not path.exists():
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_MANIFEST_FILE_NOT_FOUND",
                details={"path": str(path)},
            )
        try:
            manifest_dict = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return ManifestVerificationResult(
                valid=False,
                disposition="HALTED",
                rejection_code="HALT_INVALID_MANIFEST_JSON",
                details={"error": str(exc)},
            )
        return self.verify_manifest_dict(
            manifest_dict=manifest_dict,
            base_dir=path.parent,
            current_time=current_time,
        )


# ------------------------------------------------------------------------------
# Unified DynamicCodePolicyGate
# ------------------------------------------------------------------------------

class DynamicCodePolicyGate:
    """
    AEIB Station 1 Execution Boundary Gate.
    Integrates DynamicExecutionASTScanner and SignedPluginManifestVerifier.
    """

    def __init__(self, scanner: Optional[DynamicExecutionASTScanner] = None) -> None:
        self.scanner = scanner or DynamicExecutionASTScanner()
        self.verifier = SignedPluginManifestVerifier(scanner=self.scanner)

    def scan_file(self, file_path: Union[str, Path]) -> ASTScanReport:
        return self.scanner.scan_file(file_path)

    def scan_code(self, source_code: str, filename: str = "<memory>") -> ASTScanReport:
        return self.scanner.scan_code(source_code, filename=filename)

    def verify_manifest(
        self,
        manifest_target: Union[str, Path, Dict[str, Any]],
        base_dir: Optional[Union[str, Path]] = None,
        current_time: Optional[float] = None,
    ) -> ManifestVerificationResult:
        if isinstance(manifest_target, dict):
            return self.verifier.verify_manifest_dict(
                manifest_dict=manifest_target,
                base_dir=base_dir,
                current_time=current_time,
            )
        path = Path(manifest_target)
        return self.verifier.verify_manifest_file(path, current_time=current_time)

    def evaluate_plugin_admission(
        self,
        manifest_target: Union[str, Path, Dict[str, Any]],
        base_dir: Optional[Union[str, Path]] = None,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        res = self.verify_manifest(manifest_target, base_dir=base_dir, current_time=current_time)
        return res.valid, res.rejection_code, res.to_dict()


# ------------------------------------------------------------------------------
# Self-Test Verification Harness
# ------------------------------------------------------------------------------

def run_self_test() -> bool:
    """
    Executes internal self-test evaluation covering nominal and falsification scenarios.
    Returns True if all scenarios behave strictly as evaluated under the stated model.
    """
    scanner = DynamicExecutionASTScanner()
    verifier = SignedPluginManifestVerifier(scanner=scanner)
    gate = DynamicCodePolicyGate(scanner=scanner)

    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        key = Ed25519PrivateKey.generate()

        # 1. Nominal clean plugin
        clean_code = "def add_numbers(a: int, b: int) -> int:\n    return a + b\n"
        clean_file = td / "clean_plugin.py"
        clean_file.write_text(clean_code, encoding="utf-8")

        manifest = verifier.create_signed_manifest(
            plugin_id="nominal-plugin",
            version="1.0.0",
            private_key=key,
            entrypoint_path=clean_file,
            allowed_capabilities=["compute:local"],
        )
        res_nom = verifier.verify_manifest_dict(manifest, base_dir=td)
        assert res_nom.valid is True, f"Nominal plugin evaluation halted: {res_nom.rejection_code}"
        assert res_nom.disposition == "AUTHORIZED"
        assert res_nom.rejection_code is None

        # 2. Falsification: eval()
        eval_code = "def run(x):\n    return eval('x + 1')\n"
        rep_eval = scanner.scan_code(eval_code)
        assert rep_eval.has_critical_violations is True
        assert any(v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_EVAL" for v in rep_eval.violations)

        # 3. Falsification: compile()
        comp_code = "c = compile('a = 1', '<str>', 'exec')\n"
        rep_comp = scanner.scan_code(comp_code)
        assert rep_comp.has_critical_violations is True
        assert any(v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_COMPILE" for v in rep_comp.violations)

        # 4. Falsification: importlib
        impl_code = "import importlib\nm = importlib.import_module('sys')\n"
        rep_impl = scanner.scan_code(impl_code)
        assert rep_impl.has_critical_violations is True
        assert any(v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_IMPORTLIB" for v in rep_impl.violations)

        # 5. Falsification: ctypes.CDLL
        cdll_code = "import ctypes\nlibc = ctypes.CDLL('libc.so.6')\n"
        rep_cdll = scanner.scan_code(cdll_code)
        assert rep_cdll.has_critical_violations is True
        assert any(
            v.rule_id in ("CRITICAL_DYNAMIC_LOADER_CDLL", "CRITICAL_DYNAMIC_EXECUTION_CTYPES")
            for v in rep_cdll.violations
        )

        # 6. Falsification: Tampered entrypoint digest
        tampered_manifest = dict(manifest)
        clean_file.write_text(clean_code + "\n# altered bit\n", encoding="utf-8")
        res_tamp = verifier.verify_manifest_dict(tampered_manifest, base_dir=td)
        assert res_tamp.valid is False
        assert res_tamp.rejection_code == "HALT_PLUGIN_DIGEST_MISMATCH"

        # Restore file for subsequent tests
        clean_file.write_text(clean_code, encoding="utf-8")

        # 7. Falsification: Forged publisher signature
        key_attacker = Ed25519PrivateKey.generate()
        bad_sig_manifest = dict(manifest)
        forged_sig = key_attacker.sign(b"forged_bytes")
        bad_sig_manifest["signature_b64"] = base64.b64encode(forged_sig).decode("ascii")
        res_forge = verifier.verify_manifest_dict(bad_sig_manifest, base_dir=td)
        assert res_forge.valid is False
        assert res_forge.rejection_code == "HALT_INVALID_PLUGIN_SIGNATURE"

        # 8. Falsification: Expired plugin manifest
        expired_manifest = verifier.create_signed_manifest(
            plugin_id="expired-plugin",
            version="1.0.0",
            private_key=key,
            entrypoint_path=clean_file,
            allowed_capabilities=["read:telemetry"],
            issued_at=int(time.time()) - 7200,
            expires_at=int(time.time()) - 3600,
        )
        res_exp = verifier.verify_manifest_dict(expired_manifest, base_dir=td)
        assert res_exp.valid is False
        assert res_exp.rejection_code == "HALT_PLUGIN_MANIFEST_EXPIRED"

        # 9. Falsification: Unsigned plugin manifest
        unsigned_manifest = dict(manifest)
        unsigned_manifest.pop("signature_b64", None)
        res_unsign = verifier.verify_manifest_dict(unsigned_manifest, base_dir=td)
        assert res_unsign.valid is False
        assert res_unsign.rejection_code == "HALT_UNSIGNED_PLUGIN"

        # 10. Falsification: Publisher DID mismatch
        mismatched_did_manifest = dict(manifest)
        mismatched_did_manifest["publisher_did"] = "did:key:0000000000000000000000000000000000000000000000000000000000000000"
        # Re-sign with mismatched DID to isolate the DID check
        payload_mismatch = {k: v for k, v in mismatched_did_manifest.items() if k != "signature_b64"}
        mismatched_did_manifest["signature_b64"] = base64.b64encode(
            key.sign(encode_jcs(payload_mismatch))
        ).decode("ascii")
        res_did = verifier.verify_manifest_dict(mismatched_did_manifest, base_dir=td)
        assert res_did.valid is False
        assert res_did.rejection_code == "HALT_PUBLISHER_DID_MISMATCH"

    return True


# ------------------------------------------------------------------------------
# CLI Interface
# ------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="AEIB Dynamic Execution Policy Gate & Signed Plugin Manifest Verifier"
    )
    parser.add_argument(
        "--scan-file",
        type=str,
        help="Scan a Python source file for dynamic code execution patterns",
    )
    parser.add_argument(
        "--verify-manifest",
        type=str,
        help="Verify a signed AEIB plugin manifest file and its entrypoint",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Execute internal verification test suite",
    )

    args = parser.parse_args()
    gate = DynamicCodePolicyGate()

    if args.self_test:
        success = run_self_test()
        if success:
            sys.stdout.write("Self-test completed: all verification scenarios passed under stated model.\n")
            return 0
        else:
            sys.stderr.write("Self-test encountered failure.\n")
            return 1

    if args.scan_file:
        report = gate.scan_file(args.scan_file)
        if report.has_critical_violations:
            sys.stdout.write(f"DISPOSITION: HALTED (critical violations in {args.scan_file})\n")
            for v in report.violations:
                sys.stdout.write(f"  Line {v.line_number}:{v.column_offset} [{v.severity}] {v.rule_id}: {v.message}\n")
            return 1
        elif not report.is_clean:
            sys.stdout.write(f"DISPOSITION: ADMITTED_WITH_WARNINGS (major violations in {args.scan_file})\n")
            for v in report.violations:
                sys.stdout.write(f"  Line {v.line_number}:{v.column_offset} [{v.severity}] {v.rule_id}: {v.message}\n")
            return 0
        else:
            sys.stdout.write(f"DISPOSITION: AUTHORIZED (clean AST observed in {args.scan_file})\n")
            return 0

    if args.verify_manifest:
        result = gate.verify_manifest(args.verify_manifest)
        if result.valid:
            sys.stdout.write("DISPOSITION: AUTHORIZED\n")
            sys.stdout.write(f"Plugin ID: {result.plugin_id}\n")
            sys.stdout.write(f"Manifest CAID: {result.manifest_caid}\n")
            sys.stdout.write(f"Entrypoint SHA-256: {result.entrypoint_sha256}\n")
            return 0
        else:
            sys.stdout.write("DISPOSITION: HALTED\n")
            sys.stdout.write(f"Rejection Code: {result.rejection_code}\n")
            if result.violations:
                sys.stdout.write("AST Violations:\n")
                for v in result.violations:
                    sys.stdout.write(f"  Line {v.line_number}:{v.column_offset} [{v.severity}] {v.rule_id}: {v.message}\n")
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
