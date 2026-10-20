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
tests/test_dynamic_code_policy_gate.py
================================================================================
Test suite evaluating Dynamic Code Policy Gate & Signed Plugin Manifest Verifier.
Evaluated under the stated model. Conforms to AGENTS.md zero-mock & cryptographic purity.

Tests:
1. Nominal clean plugin verification (Ed25519, RFC 8785 JCS, clean AST).
2. Falsification 1: eval("2 + 2") fails closed with CRITICAL_DYNAMIC_EXECUTION_EVAL.
3. Falsification 2: compile("...", "", "exec") fails closed with CRITICAL_DYNAMIC_EXECUTION_COMPILE.
4. Falsification 3: importlib import or importlib.import_module fails closed.
5. Falsification 4: ctypes.CDLL("libc.so.6") fails closed with CRITICAL_DYNAMIC_LOADER_CDLL.
6. Falsification 5: Tampered entrypoint file fails closed with HALT_PLUGIN_DIGEST_MISMATCH.
7. Falsification 6: Forged publisher signature fails closed with HALT_INVALID_PLUGIN_SIGNATURE.
8. Falsification 7: Expired plugin manifest fails closed with HALT_PLUGIN_MANIFEST_EXPIRED.
9. Falsification 8: Unsigned plugin manifest fails closed with HALT_UNSIGNED_PLUGIN.
10. Falsification 9: Publisher DID mismatch fails closed with HALT_PUBLISHER_DID_MISMATCH.
11. CLI --self-test execution via subprocess.
12. CLI --scan-file and --verify-manifest via subprocess.
13. Epistemic boundary and zero banned words verification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from compliance.dynamic_code_policy_gate import (
    DynamicCodePolicyGate,
    DynamicExecutionASTScanner,
    SignedPluginManifestVerifier,
    compute_publisher_did,
    compute_ed25519_thumbprint,
    verify_publisher_did,
)
from src.jcs_canonicalizer import encode_jcs


# ------------------------------------------------------------------------------
# Test 1: Nominal Clean Plugin
# ------------------------------------------------------------------------------

def test_nominal_clean_plugin_verification(tmp_path: Path) -> None:
    """Evaluates nominal plugin admission with clean AST and valid signed manifest."""
    entrypoint = tmp_path / "telemetry_processor.py"
    entrypoint.write_text(
        "def process_metrics(raw_readings: list[int]) -> int:\n"
        "    accumulator = 0\n"
        "    for val in raw_readings:\n"
        "        accumulator += val\n"
        "    return accumulator\n",
        encoding="utf-8",
    )

    publisher_key = Ed25519PrivateKey.generate()
    verifier = SignedPluginManifestVerifier()

    manifest = verifier.create_signed_manifest(
        plugin_id="telemetry-plugin-v1",
        version="1.0.0",
        private_key=publisher_key,
        entrypoint_path=entrypoint,
        allowed_capabilities=["read:telemetry", "compute:local"],
        validity_duration_sec=3600,
    )

    manifest_file = tmp_path / "plugin_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Verify via SignedPluginManifestVerifier
    result = verifier.verify_manifest_file(manifest_file)
    assert result.valid is True
    assert result.disposition == "AUTHORIZED"
    assert result.rejection_code is None
    assert result.plugin_id == "telemetry-plugin-v1"
    assert result.manifest_caid is not None
    assert len(result.violations) == 0

    # Verify via DynamicCodePolicyGate
    gate = DynamicCodePolicyGate()
    admitted, halt_code, record = gate.evaluate_plugin_admission(manifest_file)
    assert admitted is True
    assert halt_code is None
    assert record is not None
    assert record["disposition"] == "AUTHORIZED"


# ------------------------------------------------------------------------------
# Test 2: Falsification 1 — eval("2 + 2")
# ------------------------------------------------------------------------------

def test_falsification_eval_detection(tmp_path: Path) -> None:
    """Evaluates AST ban against direct eval() calls."""
    eval_code = (
        "def compute(payload: str):\n"
        "    return eval('2 + 2')\n"
    )

    scanner = DynamicExecutionASTScanner()
    report = scanner.scan_code(eval_code)

    assert report.is_clean is False
    assert report.has_critical_violations is True

    eval_violations = [v for v in report.violations if v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_EVAL"]
    assert len(eval_violations) >= 1
    assert eval_violations[0].severity == "CRITICAL"
    assert eval_violations[0].line_number == 2
    assert eval_violations[0].symbol == "eval"

    # Evaluate manifest verifier fails closed when entrypoint contains eval
    bad_file = tmp_path / "eval_plugin.py"
    bad_file.write_text(eval_code, encoding="utf-8")
    pub_key = Ed25519PrivateKey.generate()
    manifest = SignedPluginManifestVerifier.create_signed_manifest(
        plugin_id="eval-plugin",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=bad_file,
        allowed_capabilities=["compute:local"],
    )

    verifier = SignedPluginManifestVerifier(scanner=scanner)
    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_DYNAMIC_CODE_DETECTED"
    assert any(v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_EVAL" for v in res.violations)


# ------------------------------------------------------------------------------
# Test 3: Falsification 2 — compile("...", "", "exec")
# ------------------------------------------------------------------------------

def test_falsification_compile_detection(tmp_path: Path) -> None:
    """Evaluates AST ban against compile() invocations."""
    compile_code = (
        "code_source = 'value = 42'\n"
        "compiled_obj = compile(code_source, '<virtual>', 'exec')\n"
    )

    scanner = DynamicExecutionASTScanner()
    report = scanner.scan_code(compile_code)

    assert report.is_clean is False
    assert report.has_critical_violations is True

    compile_violations = [v for v in report.violations if v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_COMPILE"]
    assert len(compile_violations) >= 1
    assert compile_violations[0].severity == "CRITICAL"
    assert compile_violations[0].symbol == "compile"

    # Evaluate manifest rejection
    bad_file = tmp_path / "compile_plugin.py"
    bad_file.write_text(compile_code, encoding="utf-8")
    pub_key = Ed25519PrivateKey.generate()
    manifest = SignedPluginManifestVerifier.create_signed_manifest(
        plugin_id="compile-plugin",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=bad_file,
        allowed_capabilities=["compute:local"],
    )

    verifier = SignedPluginManifestVerifier(scanner=scanner)
    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_DYNAMIC_CODE_DETECTED"
    assert any(v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_COMPILE" for v in res.violations)


# ------------------------------------------------------------------------------
# Test 4: Falsification 3 — importlib import & import_module
# ------------------------------------------------------------------------------

def test_falsification_importlib_detection(tmp_path: Path) -> None:
    """Evaluates AST ban against importlib imports and dynamic import calls."""
    code_direct_import = (
        "import importlib\n"
        "loaded = importlib.import_module('os')\n"
    )
    code_from_import = (
        "from importlib import import_module\n"
        "target = import_module('sys')\n"
    )

    scanner = DynamicExecutionASTScanner()

    # Pattern A: import importlib
    report_a = scanner.scan_code(code_direct_import)
    assert report_a.has_critical_violations is True
    assert any(v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_IMPORTLIB" for v in report_a.violations)

    # Pattern B: from importlib import import_module
    report_b = scanner.scan_code(code_from_import)
    assert report_b.has_critical_violations is True
    assert any(v.rule_id == "CRITICAL_DYNAMIC_EXECUTION_IMPORTLIB" for v in report_b.violations)

    # Manifest verifier rejection
    bad_file = tmp_path / "importlib_plugin.py"
    bad_file.write_text(code_direct_import, encoding="utf-8")
    pub_key = Ed25519PrivateKey.generate()
    manifest = SignedPluginManifestVerifier.create_signed_manifest(
        plugin_id="importlib-plugin",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=bad_file,
        allowed_capabilities=["compute:local"],
    )

    verifier = SignedPluginManifestVerifier(scanner=scanner)
    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_DYNAMIC_CODE_DETECTED"


# ------------------------------------------------------------------------------
# Test 5: Falsification 4 — ctypes.CDLL & Native Loaders
# ------------------------------------------------------------------------------

def test_falsification_ctypes_and_native_loader_detection(tmp_path: Path) -> None:
    """Evaluates AST ban against ctypes.CDLL, dlopen, and DexClassLoader."""
    code_ctypes_cdll = (
        "import ctypes\n"
        "libc = ctypes.CDLL('libc.so.6')\n"
    )
    code_dlopen = (
        "def load_lib():\n"
        "    return dlopen('libm.so')\n"
    )
    code_dex = (
        "def init_loader(apk_path):\n"
        "    return DexClassLoader(apk_path)\n"
    )

    scanner = DynamicExecutionASTScanner()

    # Pattern A: ctypes.CDLL
    report_cdll = scanner.scan_code(code_ctypes_cdll)
    assert report_cdll.has_critical_violations is True
    assert any(
        v.rule_id in ("CRITICAL_DYNAMIC_LOADER_CDLL", "CRITICAL_DYNAMIC_EXECUTION_CTYPES")
        for v in report_cdll.violations
    )

    # Pattern B: dlopen
    report_dlopen = scanner.scan_code(code_dlopen)
    assert report_dlopen.has_critical_violations is True
    assert any(v.rule_id == "CRITICAL_DYNAMIC_LOADER_DLOPEN" for v in report_dlopen.violations)

    # Pattern C: DexClassLoader
    report_dex = scanner.scan_code(code_dex)
    assert report_dex.has_critical_violations is True
    assert any(v.rule_id == "CRITICAL_DYNAMIC_LOADER_DEXCLASSLOADER" for v in report_dex.violations)

    # Manifest verifier rejection
    bad_file = tmp_path / "native_loader_plugin.py"
    bad_file.write_text(code_ctypes_cdll, encoding="utf-8")
    pub_key = Ed25519PrivateKey.generate()
    manifest = SignedPluginManifestVerifier.create_signed_manifest(
        plugin_id="native-plugin",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=bad_file,
        allowed_capabilities=["compute:local"],
    )

    verifier = SignedPluginManifestVerifier(scanner=scanner)
    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_DYNAMIC_CODE_DETECTED"


# ------------------------------------------------------------------------------
# Test 6: Falsification 5 — Tampered Entrypoint Digest Mismatch
# ------------------------------------------------------------------------------

def test_falsification_tampered_entrypoint_digest(tmp_path: Path) -> None:
    """Evaluates fail-closed halt when entrypoint code content is tampered with."""
    entrypoint = tmp_path / "safe_agent_tool.py"
    entrypoint.write_text("def run():\n    return 'clean_output'\n", encoding="utf-8")

    pub_key = Ed25519PrivateKey.generate()
    verifier = SignedPluginManifestVerifier()

    manifest = verifier.create_signed_manifest(
        plugin_id="safe-tool",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=entrypoint,
        allowed_capabilities=["read:status"],
    )

    # Tamper with file on disk by flipping a bit or adding a line
    entrypoint.write_text("def run():\n    return 'clean_output'\n# injected modification\n", encoding="utf-8")

    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_PLUGIN_DIGEST_MISMATCH"


# ------------------------------------------------------------------------------
# Test 7: Falsification 6 — Forged Publisher Signature
# ------------------------------------------------------------------------------

def test_falsification_forged_publisher_signature(tmp_path: Path) -> None:
    """Evaluates fail-closed halt on invalid or forged publisher signature."""
    entrypoint = tmp_path / "valid_code.py"
    entrypoint.write_text("def run():\n    return 100\n", encoding="utf-8")

    valid_pub_key = Ed25519PrivateKey.generate()
    attacker_key = Ed25519PrivateKey.generate()

    verifier = SignedPluginManifestVerifier()
    manifest = verifier.create_signed_manifest(
        plugin_id="forged-sig-target",
        version="1.0.0",
        private_key=valid_pub_key,
        entrypoint_path=entrypoint,
        allowed_capabilities=["read:telemetry"],
    )

    # Attacker re-signs with their own key without changing publisher_pubkey_b64
    payload = {k: v for k, v in manifest.items() if k != "signature_b64"}
    forged_sig = attacker_key.sign(encode_jcs(payload))
    manifest["signature_b64"] = base64.b64encode(forged_sig).decode("ascii")

    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_INVALID_PLUGIN_SIGNATURE"


# ------------------------------------------------------------------------------
# Test 8: Falsification 7 — Expired Plugin Manifest
# ------------------------------------------------------------------------------

def test_falsification_expired_plugin_manifest(tmp_path: Path) -> None:
    """Evaluates temporal expiration gating."""
    entrypoint = tmp_path / "expired_code.py"
    entrypoint.write_text("def run():\n    return 42\n", encoding="utf-8")

    pub_key = Ed25519PrivateKey.generate()
    verifier = SignedPluginManifestVerifier()

    now = int(time.time())
    manifest = verifier.create_signed_manifest(
        plugin_id="expired-manifest-plugin",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=entrypoint,
        allowed_capabilities=["read:data"],
        issued_at=now - 7200,
        expires_at=now - 3600,  # Expired 1 hour ago
    )

    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path, current_time=now)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_PLUGIN_MANIFEST_EXPIRED"


# ------------------------------------------------------------------------------
# Test 9: Falsification 8 — Unsigned Plugin Manifest
# ------------------------------------------------------------------------------

def test_falsification_unsigned_plugin_manifest(tmp_path: Path) -> None:
    """Evaluates rejection of plugin manifest missing signature_b64."""
    entrypoint = tmp_path / "unsigned_code.py"
    entrypoint.write_text("def calculate():\n    return 1\n", encoding="utf-8")

    pub_key = Ed25519PrivateKey.generate()
    verifier = SignedPluginManifestVerifier()

    manifest = verifier.create_signed_manifest(
        plugin_id="unsigned-plugin",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=entrypoint,
        allowed_capabilities=["read:data"],
    )

    # Strip signature
    del manifest["signature_b64"]

    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_UNSIGNED_PLUGIN"


# ------------------------------------------------------------------------------
# Test 10: Falsification 9 — Publisher DID Mismatch
# ------------------------------------------------------------------------------

def test_falsification_publisher_did_mismatch(tmp_path: Path) -> None:
    """Evaluates rejection when publisher DID does not bind to public key thumbprint."""
    entrypoint = tmp_path / "did_mismatch_code.py"
    entrypoint.write_text("def compute():\n    return 123\n", encoding="utf-8")

    pub_key = Ed25519PrivateKey.generate()
    verifier = SignedPluginManifestVerifier()

    manifest = verifier.create_signed_manifest(
        plugin_id="did-mismatch-plugin",
        version="1.0.0",
        private_key=pub_key,
        entrypoint_path=entrypoint,
        allowed_capabilities=["read:data"],
    )

    # Fabricate unrelated DID and re-sign with valid key
    manifest["publisher_did"] = "did:key:0000111122223333444455556666777788889999aaaabbbbccccddddeeeeffff"
    payload = {k: v for k, v in manifest.items() if k != "signature_b64"}
    manifest["signature_b64"] = base64.b64encode(pub_key.sign(encode_jcs(payload))).decode("ascii")

    res = verifier.verify_manifest_dict(manifest, base_dir=tmp_path)
    assert res.valid is False
    assert res.disposition == "HALTED"
    assert res.rejection_code == "HALT_PUBLISHER_DID_MISMATCH"


# ------------------------------------------------------------------------------
# Test 11: CLI --self-test Subprocess Execution
# ------------------------------------------------------------------------------

def test_cli_self_test_subprocess() -> None:
    """Evaluates dynamic_code_policy_gate.py --self-test CLI subprocess execution."""
    gate_script = Path(__file__).resolve().parent.parent / "compliance" / "dynamic_code_policy_gate.py"
    proc = subprocess.run(
        [sys.executable, str(gate_script), "--self-test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"CLI self-test failed with code {proc.returncode}:\n{proc.stderr}\n{proc.stdout}"
    assert "Self-test completed: all verification scenarios passed" in proc.stdout


# ------------------------------------------------------------------------------
# Test 12: CLI --scan-file and --verify-manifest Subprocess
# ------------------------------------------------------------------------------

def test_cli_scan_file_and_verify_manifest_subprocess(tmp_path: Path) -> None:
    """Evaluates CLI flags --scan-file and --verify-manifest in standalone invocation."""
    gate_script = Path(__file__).resolve().parent.parent / "compliance" / "dynamic_code_policy_gate.py"

    # 1. Clean file scan
    clean_file = tmp_path / "cli_clean.py"
    clean_file.write_text("def fn(): return 42\n", encoding="utf-8")
    proc_clean = subprocess.run(
        [sys.executable, str(gate_script), "--scan-file", str(clean_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_clean.returncode == 0
    assert "DISPOSITION: AUTHORIZED" in proc_clean.stdout

    # 2. Eval file scan
    eval_file = tmp_path / "cli_eval.py"
    eval_file.write_text("result = eval('1+1')\n", encoding="utf-8")
    proc_eval = subprocess.run(
        [sys.executable, str(gate_script), "--scan-file", str(eval_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_eval.returncode == 1
    assert "DISPOSITION: HALTED" in proc_eval.stdout
    assert "CRITICAL_DYNAMIC_EXECUTION_EVAL" in proc_eval.stdout

    # 3. Valid manifest verification
    pub_key = Ed25519PrivateKey.generate()
    verifier = SignedPluginManifestVerifier()
    manifest = verifier.create_signed_manifest(
        plugin_id="cli-manifest-plugin",
        version="2.0.0",
        private_key=pub_key,
        entrypoint_path=clean_file,
        allowed_capabilities=["read:telemetry"],
    )
    manifest_file = tmp_path / "valid_manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    proc_manifest = subprocess.run(
        [sys.executable, str(gate_script), "--verify-manifest", str(manifest_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_manifest.returncode == 0
    assert "DISPOSITION: AUTHORIZED" in proc_manifest.stdout
    assert "cli-manifest-plugin" in proc_manifest.stdout


# ------------------------------------------------------------------------------
# Test 13: Epistemic Boundary & Banned Words Absence
# ------------------------------------------------------------------------------

def test_banned_words_absence_in_new_files() -> None:
    """Verifies that no banned promotional terms exist in newly authored modules."""
    repo_root = Path(__file__).resolve().parent.parent
    files_to_check = [
        repo_root / "compliance" / "dynamic_code_policy_gate.py",
        repo_root / "tests" / "test_dynamic_code_policy_gate.py",
    ]

    # Dynamically split strings so test itself never contains forbidden tokens
    banned_tokens = [
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven " + "universally",
        "unhack" + "able",
        "guar" + "antee",
        "guar" + "anteed",
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"File {file_path} not found"
        content = file_path.read_text(encoding="utf-8").lower()
        for token in banned_tokens:
            count = content.count(token.lower())
            assert count == 0, f"Observed banned token '{token}' in {file_path}"
