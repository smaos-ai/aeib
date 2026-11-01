#!/usr/bin/env python3
"""
tests/test_bpf_lsm_profile_compiler.py
================================================================================
Verification & Falsification Suite for Linux Kernel BPF_LSM Security Compiler.

Evaluated under the stated model. Validates compliance with Linux kernel BTF
definitions, Tetragon TracingPolicy schema constraints, and fail-closed
mitigation of permissive wildcard security policy bypasses.
Zero mock frameworks, 100.00% mutation adequacy target.
================================================================================
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.bpf_lsm_profile_compiler import (
    HALT_ARGUMENT_TYPE_MISMATCH,
    HALT_INVALID_LSM_HOOK,
    HALT_PERMISSIVE_BYPASS_DETECTED,
    KNOWN_LSM_HOOKS,
    _BASE_B,
    _CURVE_D,
    _FIELD_P,
    _ID_PT,
    _ORDER_L,
    _SQRT_M1,
    _finv,
    _jcs_number,
    _jcs_serialize,
    _rec_x,
    _x_b,
    _y_b,
    ed25519_sign_manifest,
    encode_jcs,
    BPFLSMProfileCompiler,
    BPFLSMStaticLinter,
    BPFLSMValidationError,
    parse_yaml_tracing_policy,
    run_compiler_self_test,
)


def test_positive_tetragon_aeib_enforcer_compilation(tmp_path: Path) -> None:
    """Verifies that the canonical compliance/tetragon_aeib_enforcer.yaml passes linting and compiles."""
    policy_path = Path("compliance/tetragon_aeib_enforcer.yaml")
    assert policy_path.is_file(), "Canonical Tetragon policy file not found"

    compiled_profile = BPFLSMProfileCompiler.compile(policy_path)
    assert compiled_profile["format"] == "AEIB_BPF_LSM_SECURITY_PROFILE_V1"
    assert "canonical_digest_sha256" in compiled_profile
    assert len(compiled_profile["canonical_digest_sha256"]) == 64

    manifest = compiled_profile["profile_manifest"]
    assert manifest["profile_name"] == "aeib-kernel-lsm-enforcer"
    assert manifest["target_subsystem"] == "linux_bpf_lsm"
    assert len(manifest["kernel_lsm_hooks"]) == 2

    hook_names = {h["call"] for h in manifest["kernel_lsm_hooks"]}
    assert "security_socket_connect" in hook_names
    assert "security_file_open" in hook_names


def test_falsification_unknown_lsm_hook_halts_closed() -> None:
    """Falsification 1: Unknown or unvetted LSM hook call fails closed with HALT_INVALID_LSM_HOOK."""
    unvetted_policy_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: malicious-unvetted-hook
spec:
  kprobes:
    - call: "security_arbitrary_unvetted_trap"
      syscall: false
      args:
        - index: 0
          type: "sock"
      selectors:
        - matchActions:
            - action: Override
"""
    parsed = parse_yaml_tracing_policy(unvetted_policy_yaml)
    linter = BPFLSMStaticLinter(parsed)

    with pytest.raises(BPFLSMValidationError) as exc_info:
        linter.validate()

    assert exc_info.value.halt_code == HALT_INVALID_LSM_HOOK
    assert "Unknown or unvetted LSM hook" in exc_info.value.message


def test_falsification_permissive_wildcard_file_write_halts_closed() -> None:
    """Falsification 2: Permissive wildcard write rule fails closed with HALT_PERMISSIVE_BYPASS_DETECTED."""
    permissive_write_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: permissive-root-wildcard
spec:
  kprobes:
    - call: "security_file_open"
      syscall: false
      args:
        - index: 0
          type: "file"
      selectors:
        - matchArgs:
            - index: 0
              operator: "Prefix"
              values:
                - "/"
          matchFlags:
            - index: 0
              operator: "HasAny"
              values:
                - "O_WRONLY"
                - "O_TRUNC"
          matchActions:
            - action: Override
"""
    parsed = parse_yaml_tracing_policy(permissive_write_yaml)
    linter = BPFLSMStaticLinter(parsed)

    with pytest.raises(BPFLSMValidationError) as exc_info:
        linter.validate()

    assert exc_info.value.halt_code == HALT_PERMISSIVE_BYPASS_DETECTED
    assert "permissive root wildcard path" in exc_info.value.message


def test_falsification_argument_type_mismatch_halts_closed() -> None:
    """Falsification 3: Argument type mismatch with BTF definitions fails with HALT_ARGUMENT_TYPE_MISMATCH."""
    type_mismatch_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: argument-type-mismatch
spec:
  kprobes:
    - call: "security_socket_connect"
      syscall: false
      args:
        - index: 0
          type: "file"
      selectors:
        - matchActions:
            - action: Override
"""
    parsed = parse_yaml_tracing_policy(type_mismatch_yaml)
    linter = BPFLSMStaticLinter(parsed)

    with pytest.raises(BPFLSMValidationError) as exc_info:
        linter.validate()

    assert exc_info.value.halt_code == HALT_ARGUMENT_TYPE_MISMATCH
    assert "Argument type mismatch" in exc_info.value.message


def test_cli_compiler_self_test_execution() -> None:
    """Verifies that bpf_lsm_profile_compiler.py --self-test runs and passes."""
    cmd = [sys.executable, "src/bpf_lsm_profile_compiler.py", "--self-test"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "[VALID] BPF_LSM Compiler Self-Test" in proc.stdout


def test_direct_run_compiler_self_test() -> None:
    """Verifies direct execution of run_compiler_self_test returns True."""
    assert run_compiler_self_test() is True


def test_ed25519_sign_manifest_and_curve_invariants() -> None:
    """Validates Ed25519 signing primitives, curve constants, and RFC 8032 test vectors."""
    assert _FIELD_P == 2**255 - 19
    assert _ORDER_L == 2**252 + 27742317777372353535851937790883648493
    assert _CURVE_D == (-121665 * pow(121666, _FIELD_P - 2, _FIELD_P)) % _FIELD_P
    assert _SQRT_M1 == pow(2, (_FIELD_P - 1) // 4, _FIELD_P)
    assert _ID_PT == (0, 1, 1, 0)
    assert _finv(5) == pow(5, _FIELD_P - 2, _FIELD_P)
    assert _rec_x(_y_b, 0) == _x_b
    assert _BASE_B[2] == 1

    seed = b"\x00" * 32
    msg = b"test message"
    pub, sig = ed25519_sign_manifest(seed, msg)
    assert pub.hex() == "3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29"
    assert sig.hex() == "68c4cc2cb078e1802f43f5d2f741c942229fd920afe00e0c1fe753a0d67afa44facb218fb80df78cb9197a19fdc35366f0ff1e156cf94db8244809c6310c4408"

    with pytest.raises(ValueError):
        ed25519_sign_manifest(b"short_seed", msg)


def test_jcs_number_formatting() -> None:
    """Validates RFC 8785 canonical number serialization edge cases."""
    assert _jcs_number(0.0) == "0"
    assert _jcs_number(100.0) == "100"
    assert _jcs_number(12.34) == "12.34"
    assert _jcs_number(1e21) == "1e+21"
    assert _jcs_number(1.23e25) == "1.23e+25"
    assert _jcs_number(-42.5) == "-42.5"
    assert _jcs_number(-0.001) == "-0.001"
    assert _jcs_number(1e-6) == "0.000001"
    assert _jcs_number(1e-7) == "1e-7"


def test_jcs_boolean_and_serialization() -> None:
    """Validates boolean serialization in RFC 8785 JCS encoding."""
    assert _jcs_serialize(None) == "null"
    assert _jcs_serialize(True) == "true"
    assert _jcs_serialize(False) == "false"
    assert encode_jcs({"active": True, "enabled": False}) == b'{"active":true,"enabled":false}'


def test_yaml_dash_on_own_line() -> None:
    """Validates parsing a list where dash appears on its own line followed by indented fields."""
    yaml_text = """
spec:
  items:
    -
      name: subitem
"""
    parsed = parse_yaml_tracing_policy(yaml_text)
    assert parsed.get("spec", {}).get("items") == [{"name": "subitem"}]


def test_known_lsm_hooks_bprm_check_security_requires_selectors() -> None:
    """Validates that bprm_check_security strictly requires non-empty selectors."""
    assert KNOWN_LSM_HOOKS["bprm_check_security"]["requires_non_empty_selectors"] is True

    policy_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: bprm-empty-sel
spec:
  kprobes:
    - call: "bprm_check_security"
      args:
        - index: 0
          type: "linux_binprm"
      selectors: []
"""
    parsed = parse_yaml_tracing_policy(policy_yaml)
    linter = BPFLSMStaticLinter(parsed)
    with pytest.raises(BPFLSMValidationError) as exc:
        linter.validate()
    assert exc.value.halt_code == HALT_ARGUMENT_TYPE_MISMATCH


def test_security_file_open_write_flags_without_enforcement_halts() -> None:
    """Validates that security_file_open with write flags but no enforcement halts closed."""
    policy_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: write-no-enforcement
spec:
  kprobes:
    - call: security_file_open
      args:
        - index: 0
          type: file
      selectors:
        - matchArgs:
            - index: 0
              operator: "Prefix"
              values:
                - "/var/log"
          matchFlags:
            - index: 0
              operator: "HasAny"
              values:
                - "O_WRONLY"
          matchActions:
            - action: Post
"""
    parsed = parse_yaml_tracing_policy(policy_yaml)
    linter = BPFLSMStaticLinter(parsed)
    with pytest.raises(BPFLSMValidationError) as exc:
        linter.validate()
    assert exc.value.halt_code == HALT_PERMISSIVE_BYPASS_DETECTED


def test_argument_entry_non_int_index_halts() -> None:
    """Validates that non-integer argument index fails closed with HALT_ARGUMENT_TYPE_MISMATCH."""
    policy_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: bad-arg-index
spec:
  kprobes:
    - call: "security_file_open"
      args:
        - index: "invalid_string_index"
          type: "file"
      selectors:
        - matchActions:
            - action: Override
"""
    parsed = parse_yaml_tracing_policy(policy_yaml)
    linter = BPFLSMStaticLinter(parsed)
    with pytest.raises(BPFLSMValidationError) as exc:
        linter.validate()
    assert exc.value.halt_code == HALT_ARGUMENT_TYPE_MISMATCH
    assert "must specify integer 'index' and string 'type'" in exc.value.message


def test_security_socket_connect_wildcard_ip_halts() -> None:
    """Validates that single wildcard IP (0.0.0.0 or *) halts with HALT_PERMISSIVE_BYPASS_DETECTED."""
    policy_yaml_zero = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: socket-wildcard-zero
spec:
  kprobes:
    - call: "security_socket_connect"
      args:
        - index: 0
          type: "sock"
      selectors:
        - matchArgs:
            - index: 0
              operator: "DAddr"
              values:
                - "0.0.0.0"
          matchActions:
            - action: Override
"""
    linter_zero = BPFLSMStaticLinter(parse_yaml_tracing_policy(policy_yaml_zero))
    with pytest.raises(BPFLSMValidationError) as exc:
        linter_zero.validate()
    assert exc.value.halt_code == HALT_PERMISSIVE_BYPASS_DETECTED

    policy_yaml_star = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: socket-wildcard-star
spec:
  kprobes:
    - call: "security_socket_connect"
      args:
        - index: 0
          type: "sock"
      selectors:
        - matchArgs:
            - index: 0
              operator: "DAddr"
              values:
                - "*"
          matchActions:
            - action: Override
"""
    linter_star = BPFLSMStaticLinter(parse_yaml_tracing_policy(policy_yaml_star))
    with pytest.raises(BPFLSMValidationError) as exc:
        linter_star.validate()
    assert exc.value.halt_code == HALT_PERMISSIVE_BYPASS_DETECTED


def test_cli_exit_codes_and_error_handling(tmp_path: Path) -> None:
    """Validates deterministic CLI exit codes under file errors, validation halts, and parsing exceptions."""
    nonexistent = tmp_path / "does_not_exist.yaml"
    proc_lint_missing = subprocess.run(
        [sys.executable, "src/bpf_lsm_profile_compiler.py", "--lint", str(nonexistent)],
        capture_output=True,
        text=True,
    )
    assert proc_lint_missing.returncode == 2

    proc_compile_missing = subprocess.run(
        [sys.executable, "src/bpf_lsm_profile_compiler.py", "--compile", str(nonexistent)],
        capture_output=True,
        text=True,
    )
    assert proc_compile_missing.returncode == 2

    corrupted_file = tmp_path / "corrupted_bytes.yaml"
    corrupted_file.write_bytes(b"\xff\xfe\x00\x00")
    proc_corrupt = subprocess.run(
        [sys.executable, "src/bpf_lsm_profile_compiler.py", "--lint", str(corrupted_file)],
        capture_output=True,
        text=True,
    )
    assert proc_corrupt.returncode == 2

    invalid_policy_file = tmp_path / "invalid_policy.yaml"
    invalid_policy_file.write_text("""
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: bad-hook
spec:
  kprobes:
    - call: "security_unvetted_hook"
      args:
        - index: 0
          type: "sock"
      selectors:
        - matchActions:
            - action: Override
""")
    proc_invalid = subprocess.run(
        [sys.executable, "src/bpf_lsm_profile_compiler.py", "--lint", str(invalid_policy_file)],
        capture_output=True,
        text=True,
    )
    assert proc_invalid.returncode == 1
