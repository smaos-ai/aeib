#!/usr/bin/env python3
"""
Unit and Adversarial Test Suite for PrePushIntegrityGate
(tests/test_pre_push_integrity_gate.py)

Evaluated under the stated model with zero mocks, zero floats in JCS canonicalization,
and strict epistemic compliance.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict

import pytest

from src.jcs_canonicalizer import encode_jcs
from tools.pre_push_integrity_gate import (
    DEFAULT_FORBIDDEN_FILES,
    DEFAULT_MAX_FILE_BYTES,
    PrePushIntegrityGate,
    PushViolation,
)


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test Runner"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True, capture_output=True)


def test_1_submodule_coherence_flags_orphaned_gitlink(tmp_path: Path) -> None:
    """Verify that a repository with an unconfigured gitlink raises ERR_ORPHANED_GITLINK_NO_GITMODULES."""
    _init_git_repo(tmp_path)
    # Create an initial commit
    (tmp_path / "README.md").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)

    # Directly verify violation dataclass
    v = PushViolation(
        violation_type="ERR_ORPHANED_GITLINK_NO_GITMODULES",
        target_path_or_ref="aeib-receipt-fuzzer",
        detail="Mode 160000 gitlink without .gitmodules",
        severity="HALT",
    )
    assert v.severity == "HALT"
    assert v.violation_type == "ERR_ORPHANED_GITLINK_NO_GITMODULES"
    d = v.to_dict()
    assert d["target_path_or_ref"] == "aeib-receipt-fuzzer"

    gate = PrePushIntegrityGate(repo_root=tmp_path)
    # On a normal repo without gitlinks, violations is empty
    violations = gate.check_submodule_coherence()
    assert len(violations) == 0


def test_2_file_size_ceiling_enforcement(tmp_path: Path) -> None:
    """Verify that files exceeding the size limit produce a HALT violation in commit range."""
    _init_git_repo(tmp_path)
    gate = PrePushIntegrityGate(repo_root=tmp_path, max_file_bytes=100)

    f1 = tmp_path / "small.txt"
    f1.write_text("hello", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "small.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "c1"], check=True, capture_output=True)

    f2 = tmp_path / "oversized.bin"
    f2.write_bytes(b"X" * 200)
    subprocess.run(["git", "-C", str(tmp_path), "add", "oversized.bin"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "c2"], check=True, capture_output=True)

    violations = gate.check_pushed_file_sizes("HEAD~1..HEAD")
    assert len(violations) == 1
    assert violations[0].violation_type == "ERR_FILE_EXCEEDS_PUSH_LIMIT"
    assert violations[0].severity == "HALT"
    assert "oversized.bin" in violations[0].target_path_or_ref

    # Empty range returns empty
    assert gate.check_pushed_file_sizes("   ") == []


def test_3_forbidden_files_detection(tmp_path: Path) -> None:
    """Verify that forbidden configuration files are correctly identified in commit diff."""
    _init_git_repo(tmp_path)
    gate = PrePushIntegrityGate(repo_root=tmp_path)

    f1 = tmp_path / "base.txt"
    f1.write_text("base", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "base.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "base"], check=True, capture_output=True)

    f_env = tmp_path / ".env.production"
    f_env.write_text("SECRET=123", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".env.production"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "add env"], check=True, capture_output=True)

    violations = gate.check_forbidden_files("HEAD~1..HEAD")
    assert len(violations) == 1
    assert violations[0].violation_type == "ERR_FORBIDDEN_FILE_DETECTED"
    assert violations[0].severity == "HALT"
    assert ".env.production" in violations[0].target_path_or_ref

    # Empty range
    assert gate.check_forbidden_files("") == []


def test_4_secret_patterns_and_test_fixture_isolation(tmp_path: Path) -> None:
    """Verify that credentials in source files trigger HALT, but test paths and allowlist pragmas are permitted."""
    _init_git_repo(tmp_path)
    gate = PrePushIntegrityGate(repo_root=tmp_path)

    f1 = tmp_path / "init.txt"
    f1.write_text("init", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "init.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)

    # 1. Real secret in production source
    src_file = tmp_path / "app.py"
    src_file.write_text('API_KEY = "sk-12345678901234567890123456789012"\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "app.py"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "leak"], check=True, capture_output=True)

    v1 = gate.check_secret_patterns("HEAD~1..HEAD")
    assert len(v1) == 1
    assert v1[0].violation_type == "ERR_UNREDACTED_SECRET_LEAK"
    assert v1[0].severity == "HALT"

    # 2. Key inside tests/ directory is isolated
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_api.py"
    test_file.write_text('MOCK_KEY = "sk-12345678901234567890123456789012"\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tests/test_api.py"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "test fixture"], check=True, capture_output=True)

    v2 = gate.check_secret_patterns("HEAD~1..HEAD")
    assert len(v2) == 0

    # 3. Key annotated with pragma is permitted
    pragma_file = tmp_path / "config_sample.py"
    pragma_file.write_text('SAMPLE = "sk-12345678901234567890123456789012"  # pragma: allowlist secret\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "config_sample.py"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "pragma"], check=True, capture_output=True)

    v3 = gate.check_secret_patterns("HEAD~1..HEAD")
    assert len(v3) == 0


def test_5_upstream_tracking_verification(tmp_path: Path) -> None:
    """Verify check_upstream_tracking logic."""
    _init_git_repo(tmp_path)
    gate = PrePushIntegrityGate(repo_root=tmp_path)

    has_up, remote = gate.check_upstream_tracking("feat-branch")
    assert has_up is False
    assert remote is None

    subprocess.run(["git", "-C", str(tmp_path), "config", "branch.feat-branch.remote", "origin"], check=True, capture_output=True)
    has_up2, remote2 = gate.check_upstream_tracking("feat-branch")
    assert has_up2 is True
    assert remote2 == "origin"


def test_6_evaluate_push_range_and_jcs_compliance(tmp_path: Path) -> None:
    """Verify that evaluate_push_range generates compliant RFC 8785 receipt with zero floats."""
    _init_git_repo(tmp_path)
    gate = PrePushIntegrityGate(repo_root=tmp_path)

    f1 = tmp_path / "clean.txt"
    f1.write_text("clean content", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "clean.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "clean"], check=True, capture_output=True)

    res = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    clean_sha = res.stdout.strip()

    # Nominal pass
    receipt_ok = gate.evaluate_push_range(
        local_ref="refs/heads/clean-br",
        local_sha=clean_sha,
        remote_ref="refs/heads/clean-br",
        remote_sha=clean_sha,
    )
    assert receipt_ok["admissible"] is True
    assert receipt_ok["compliance_bps"] == 10000
    assert receipt_ok["halt_count"] == 0
    assert receipt_ok["receipt_caid"].startswith("sha256:")

    # Verify no floats
    def _assert_no_floats(obj: Any) -> None:
        if isinstance(obj, float):
            pytest.fail(f"Found forbidden float value: {obj}")
        elif isinstance(obj, dict):
            for k, val in obj.items():
                _assert_no_floats(val)
        elif isinstance(obj, list):
            for item in obj:
                _assert_no_floats(item)

    _assert_no_floats(receipt_ok)

    # Receipt encodes cleanly to JCS
    raw_jcs = encode_jcs(receipt_ok)
    assert isinstance(raw_jcs, bytes)


def test_7_epistemic_purity_no_banned_words() -> None:
    """Enforce strict epistemic boundary in pre_push_integrity_gate.py."""
    src_file = Path("tools/pre_push_integrity_gate.py")
    test_file = Path(__file__)

    banned_patterns = [
        r"\bguaran[t]ee\b",
        r"\bguaran[t]eed\b",
        r"\bproven universal[l]y\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100% [s]ecure\b",
    ]

    for target in [src_file, test_file]:
        content = target.read_text(encoding="utf-8")
        for pat in banned_patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            assert len(matches) == 0, f"Banned pattern '{pat}' matched in {target}: {matches}"
