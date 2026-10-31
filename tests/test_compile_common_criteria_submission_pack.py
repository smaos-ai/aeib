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
tests/test_compile_common_criteria_submission_pack.py
================================================================================
Verification suite for CommonCriteriaSubmissionCompiler and evaluator harness.
Evaluated under the stated model with unmocked cryptographic and AST checks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.compile_common_criteria_submission_pack import (
    CommonCriteriaSubmissionCompiler,
    compute_merkle_root,
    count_words,
    sha256_jcs_caid,
    sha256_text,
)


@pytest.fixture
def submission_compiler(tmp_path: Path) -> CommonCriteriaSubmissionCompiler:
    pack_dir = tmp_path / "submission_pack"
    return CommonCriteriaSubmissionCompiler(pack_dir=pack_dir)


def test_submission_pack_nominal_compilation(submission_compiler: CommonCriteriaSubmissionCompiler):
    """Evaluates full compilation and artifact creation of ISO/IEC 15408-3 package."""
    manifest, manifest_path = submission_compiler.compile_pack()

    assert manifest_path.exists()
    assert manifest["status"] == "INTERNAL PREVIEW COMMISSIONED"
    assert manifest["toe_reference"] == "SovereignNexus AEIB v1.1"
    assert manifest["evaluation_assurance_level"] == "EAL4+ (ALC_FLR.2 + AVA_VAN.4)"
    assert manifest["documents_count"] == 6
    assert manifest["total_words"] >= 3000
    assert manifest["created_epoch_ms"] > 1_700_000_000_000
    assert manifest["submission_merkle_root"].startswith("sha256:")
    assert manifest["manifest_caid"].startswith("sha256:")

    # Verify all 6 documents exist physically
    docs = manifest["documents"]
    assert len(docs) == 6
    for filename, meta in docs.items():
        doc_file = submission_compiler.pack_dir / filename
        assert doc_file.exists(), f"Missing file: {filename}"
        assert meta["sha256"].startswith("sha256:")
        assert meta["words"] > 0
        assert meta["component"] != ""

    runner_file = submission_compiler.pack_dir / "05_INDEPENDENT_TEST_RUNNER_ATE_IND_2.py"
    assert os.access(runner_file, os.X_OK)
    assert (runner_file.stat().st_mode & 0o777) == 0o755


def test_compute_merkle_root_boundary_conditions():
    """Evaluates Merkle tree boundary cases for empty and singleton leaves."""
    import hashlib
    empty_root = compute_merkle_root([])
    assert empty_root == f"sha256:{hashlib.sha256(b'').hexdigest()}"

    single_leaf = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    assert compute_merkle_root([single_leaf]) == single_leaf


def test_submission_pack_zero_floats(submission_compiler: CommonCriteriaSubmissionCompiler):
    """Verifies that no floating-point numbers exist in the serialized manifest."""
    manifest, _ = submission_compiler.compile_pack()

    def _assert_no_floats(obj: object, path: str = "") -> None:
        if isinstance(obj, float):
            pytest.fail(f"Forbidden float detected at path '{path}': {obj}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _assert_no_floats(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                _assert_no_floats(item, f"{path}[{idx}]")

    _assert_no_floats(manifest)


def test_submission_pack_verification_and_tampering(
    submission_compiler: CommonCriteriaSubmissionCompiler,
):
    """Evaluates pack verification and deterministic rejection of any tampering."""
    _, manifest_path = submission_compiler.compile_pack()
    pack_dir = submission_compiler.pack_dir

    # 1. Nominal verification
    ok, errors = CommonCriteriaSubmissionCompiler.verify_submission_pack(pack_dir)
    assert ok is True
    assert len(errors) == 0

    # 2. Tampering a document file content
    target_doc = pack_dir / "00_SECURITY_TARGET_EAL4_PLUS.md"
    orig_content = target_doc.read_text(encoding="utf-8")
    target_doc.write_text(orig_content + "\n<!-- Tamper injection -->", encoding="utf-8")

    ok_tamper, errors_tamper = CommonCriteriaSubmissionCompiler.verify_submission_pack(pack_dir)
    assert ok_tamper is False
    assert any("ERR_DIGEST_MISMATCH:00_SECURITY_TARGET_EAL4_PLUS.md" in e for e in errors_tamper)
    assert any("ERR_MERKLE_ROOT_MISMATCH" in e for e in errors_tamper)

    # Restore content
    target_doc.write_text(orig_content, encoding="utf-8")
    assert CommonCriteriaSubmissionCompiler.verify_submission_pack(pack_dir)[0] is True

    # 3. Tampering manifest field
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["status"] = "PRODUCTION_CERTIFIED"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    ok_field, errors_field = CommonCriteriaSubmissionCompiler.verify_submission_pack(pack_dir)
    assert ok_field is False
    assert any("ERR_MANIFEST_CAID_MISMATCH" in e for e in errors_field)


def test_submission_pack_missing_and_corrupt(tmp_path: Path):
    """Evaluates fail-closed handling of nonexistent and corrupt manifests."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    ok1, errs1 = CommonCriteriaSubmissionCompiler.verify_submission_pack(empty_dir)
    assert ok1 is False
    assert "ERR_MANIFEST_MISSING" in errs1

    corrupt_dir = tmp_path / "corrupt"
    corrupt_dir.mkdir()
    (corrupt_dir / "SUBMISSION_MANIFEST.json").write_text("{malformed json...", encoding="utf-8")
    ok2, errs2 = CommonCriteriaSubmissionCompiler.verify_submission_pack(corrupt_dir)
    assert ok2 is False
    assert any("ERR_INVALID_JSON" in e for e in errs2)


def test_independent_runner_standalone_execution(
    submission_compiler: CommonCriteriaSubmissionCompiler,
):
    """Evaluates that 05_INDEPENDENT_TEST_RUNNER_ATE_IND_2.py runs cleanly as a standalone script."""
    submission_compiler.compile_pack()
    runner_path = submission_compiler.pack_dir / "05_INDEPENDENT_TEST_RUNNER_ATE_IND_2.py"

    res = subprocess.run(
        [sys.executable, str(runner_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "COMMON CRITERIA ISO/IEC 15408-3 EVALUATOR HARNESS (ATE_IND.2)" in res.stdout
    assert "Submission Manifest & Merkle Tree Root: VALIDATED" in res.stdout
    assert "Independent Standalone Evaluator Self-Tests: VALIDATED" in res.stdout
    assert "EVALUATION VERDICT: CONFORMANCE_EVALUATION_COMPLETE" in res.stdout


def test_submission_compiler_cli_workflow(tmp_path: Path):
    """Evaluates CLI invocation for compilation and verification."""
    pack_dir = tmp_path / "cli_pack"
    res1 = subprocess.run(
        [
            sys.executable,
            "tools/compile_common_criteria_submission_pack.py",
            "--out-dir",
            str(pack_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "COMMON CRITERIA ISO/IEC 15408-3 EAL4+ LAB SUBMISSION PACKAGE" in res1.stdout
    assert "=" * 80 in res1.stdout
    assert "-" * 80 in res1.stdout
    assert (pack_dir / "SUBMISSION_MANIFEST.json").exists()

    res2 = subprocess.run(
        [
            sys.executable,
            "tools/compile_common_criteria_submission_pack.py",
            "--verify",
            str(pack_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[✓] Common Criteria EAL4+ Submission Pack Verified" in res2.stdout
