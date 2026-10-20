#!/usr/bin/env python3
"""
tests/test_bpf_lsm_profile_compiler.py
================================================================================
Verification & Falsification Suite for Linux Kernel BPF_LSM Security Compiler.

Evaluated under the stated model. Validates compliance with Linux kernel BTF
definitions, Tetragon TracingPolicy schema constraints, and fail-closed
mitigation of permissive wildcard security policy bypasses.
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
    BPFLSMProfileCompiler,
    BPFLSMStaticLinter,
    BPFLSMValidationError,
    parse_yaml_tracing_policy,
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
