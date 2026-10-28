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
tests/test_slop_filter.py
================================================================================
Test suite for Automated PR Slop Filter & Dependency Provenance Gate.
Evaluated under the stated model (scaffold verifier).
Zero-mock, deterministic AST coverage and mutation adequacy verification.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pytest

from src.slop_filter import ProofObligationRecord, SlopEvaluationResult, SlopFilter


def test_slop_evaluation_result_frozenness() -> None:
    res = SlopEvaluationResult(
        passed=True,
        reason_code="OK_LOW_RISK_NO_PROOF_OBLIGATION",
        risk_tier="T1",
        detected_hallucinated_packages=(),
    )
    assert res.passed is True
    assert res.reason_code == "OK_LOW_RISK_NO_PROOF_OBLIGATION"
    assert res.risk_tier == "T1"
    assert res.detected_hallucinated_packages == ()

    with pytest.raises(dataclasses.FrozenInstanceError):
        # type-ignore to verify runtime immutability
        res.passed = False  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        res.reason_code = "CHANGED"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        res.risk_tier = "T3"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        res.detected_hallucinated_packages = ("evil",)  # type: ignore[misc]


def test_slop_filter_initialization() -> None:
    sf_default = SlopFilter()
    assert "pytest" in sf_default._allowed
    assert "cryptography" in sf_default._allowed
    assert "fastapi" in sf_default._allowed

    sf_custom = SlopFilter(allowed_packages=["numpy", "scipy"])
    assert "numpy" in sf_custom._allowed
    assert "scipy" in sf_custom._allowed
    assert "pytest" not in sf_custom._allowed


def test_slop_filter_empty_or_whitespace_diff() -> None:
    sf = SlopFilter()

    res_empty = sf.evaluate_pull_request("")
    assert res_empty.passed is False
    assert res_empty.reason_code == "REJECT_EMPTY_DIFF"
    assert res_empty.risk_tier == "T0"
    assert res_empty.detected_hallucinated_packages == ()

    res_ws = sf.evaluate_pull_request("   \n\t  \n   ")
    assert res_ws.passed is False
    assert res_ws.reason_code == "REJECT_EMPTY_DIFF"
    assert res_ws.risk_tier == "T0"
    assert res_ws.detected_hallucinated_packages == ()


def test_slop_filter_stdlib_and_allowed_dependencies() -> None:
    sf = SlopFilter()
    diff = """
--- a/src/util.py
+++ b/src/util.py
@@ -1,3 +1,6 @@
+import json
+import hashlib
+from pathlib import Path
+import pytest
+from cryptography.hazmat.primitives import hashes
+import pydantic
"""
    hallucinated = sf.scan_for_hallucinated_packages(diff)
    assert hallucinated == ()

    # Ignored lines (diff headers, unchanged lines, deletions)
    diff_ignored = """
--- a/src/util.py
+++ b/src/util.py
-import evil_package_a
 def existing_function():
+++ c/other.py
"""
    assert sf.scan_for_hallucinated_packages(diff_ignored) == ()


def test_slop_filter_hallucinated_package_detection() -> None:
    sf = SlopFilter()
    diff = """
+import hallucinated_crypto_proxy
+from hallucinated_crypto_proxy import helper
+from rogue_ai_package import runner
+fake-dep-tool==2.4.0
+fake-dep-tool==2.4.0
+pytest==8.1.1
"""
    hallucinated = sf.scan_for_hallucinated_packages(diff)
    assert "hallucinated_crypto_proxy" in hallucinated
    assert "rogue_ai_package" in hallucinated
    assert "fake_dep_tool" in hallucinated
    assert "pytest" not in hallucinated
    # Deduplication verified
    assert hallucinated.count("hallucinated_crypto_proxy") == 1
    assert hallucinated.count("fake_dep_tool") == 1

    res = sf.evaluate_pull_request(diff)
    assert res.passed is False
    assert res.reason_code == "REJECT_SLOPSQUATTING_PACKAGE"
    assert res.detected_hallucinated_packages == hallucinated


def test_slop_filter_risk_tier_classification() -> None:
    sf = SlopFilter()

    # T3 keywords
    for kw in [
        "transfer", "wire", "escrow", "crypto", "ed25519", "private_key",
        "signing", "wallet", "x402", "settlement", "payment", "execute_wire"
    ]:
        diff_kw = f"+# critical operation\n+val = handle_{kw}()"
        assert sf.classify_risk_tier(diff_kw) == "T3"

    # T3 case insensitivity
    assert sf.classify_risk_tier("+PAYMENT_GATEWAY = True") == "T3"

    # T2 code constructs
    assert sf.classify_risk_tier("+def calculate_sum(a, b): return a + b") == "T2"
    assert sf.classify_risk_tier("+class DataRecord:\n+    pass") == "T2"
    assert sf.classify_risk_tier("+async def fetch_record():\n+    return None") == "T2"

    # T1 non-code or low-risk changes
    assert sf.classify_risk_tier("+# Just updating documentation notes") == "T1"
    assert sf.classify_risk_tier("+VERSION = '1.2.3'") == "T1"


def _record(proof_text: str, *, checker: str = "tlc", exit_code: int = 0,
            digest: str | None = None, version: str = "2.19") -> dict:
    return {
        "checker": checker,
        "artifact_sha256": digest if digest is not None
        else hashlib.sha256(proof_text.encode("utf-8")).hexdigest(),
        "checker_exit_code": exit_code,
        "checker_version": version,
    }


DIFF_T2 = "+def parse_config():\n+    return {}"
DIFF_T3 = "+def execute_wire(amount, recipient):\n+    transfer(amount)"
PROOF = "Spec == Init /\\ [][Next]_vars"


def test_slop_filter_t1_needs_no_proof_obligation() -> None:
    sf = SlopFilter()
    diff_t1 = "+# documentation update\n+DOCS_URL = 'https://example.com'"
    res = sf.evaluate_pull_request(diff_t1, proof_script=None)
    assert res.passed is True
    assert res.reason_code == "OK_LOW_RISK_NO_PROOF_OBLIGATION"
    assert res.risk_tier == "T1"


def test_proof_obligation_missing_or_blank_rejected() -> None:
    sf = SlopFilter()
    for script in (None, "", "   \n  "):
        res = sf.evaluate_pull_request(DIFF_T2, proof_script=script, proof_record=_record("x"))
        assert res.passed is False
        assert res.reason_code == "REJECT_MISSING_PROOF_OBLIGATION"
        assert res.risk_tier == "T2"
    res3 = sf.evaluate_pull_request(DIFF_T3)
    assert res3.passed is False
    assert res3.reason_code == "REJECT_MISSING_PROOF_OBLIGATION"
    assert res3.risk_tier == "T3"


def test_regression_theorem_comment_without_record_rejected() -> None:
    # Old code accepted any text containing "theorem" / "Spec ==" as a proof.
    sf = SlopFilter()
    for script in ("# theorem", "theorem correctness : Inv", PROOF):
        res = sf.evaluate_pull_request(DIFF_T2, proof_script=script)
        assert res.passed is False
        assert res.reason_code == "REJECT_MISSING_PROOF_OBLIGATION"


def test_regression_proof_digest_mismatch_rejected() -> None:
    sf = SlopFilter()
    rec = _record("a different proof text")
    res = sf.evaluate_pull_request(DIFF_T3, proof_script=PROOF, proof_record=rec)
    assert res.passed is False
    assert res.reason_code == "REJECT_PROOF_ARTIFACT_DIGEST_MISMATCH"
    assert res.risk_tier == "T3"


def test_regression_proof_checker_nonzero_exit_rejected() -> None:
    sf = SlopFilter()
    for code in (1, -1, 2):
        res = sf.evaluate_pull_request(DIFF_T2, proof_script=PROOF,
                                       proof_record=_record(PROOF, exit_code=code))
        assert res.passed is False
        assert res.reason_code == "REJECT_PROOF_CHECKER_FAILED"


def test_proof_obligation_record_present_ok() -> None:
    sf = SlopFilter()
    for checker in ("lean4", "tlc", "z3"):
        res = sf.evaluate_pull_request(DIFF_T3, proof_script=PROOF,
                                       proof_record=_record(PROOF, checker=checker))
        assert res.passed is True
        assert res.reason_code == "OK_PROOF_OBLIGATION_RECORD_PRESENT"
        assert res.risk_tier == "T3"
    rec = ProofObligationRecord(
        checker="z3",
        artifact_sha256=hashlib.sha256(PROOF.encode("utf-8")).hexdigest(),
        checker_exit_code=0,
        checker_version="4.13.0",
    )
    res2 = sf.evaluate_pull_request(DIFF_T2, proof_script=PROOF, proof_record=rec)
    assert res2.passed is True
    assert res2.reason_code == "OK_PROOF_OBLIGATION_RECORD_PRESENT"
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.checker_exit_code = 1  # type: ignore[misc]


def test_proof_obligation_malformed_records_rejected() -> None:
    sf = SlopFilter()
    good = _record(PROOF)
    bad_variants = [
        {**good, "checker": "coq"},
        {**good, "checker": None},
        {**good, "artifact_sha256": good["artifact_sha256"].upper()},
        {**good, "artifact_sha256": good["artifact_sha256"][:-1]},
        {**good, "artifact_sha256": 12345},
        {**good, "checker_exit_code": "0"},
        {**good, "checker_exit_code": False},
        {**good, "checker_version": ""},
        {**good, "checker_version": "   "},
        {**good, "checker_version": None},
        {k: v for k, v in good.items() if k != "checker"},
        {k: v for k, v in good.items() if k != "artifact_sha256"},
        {k: v for k, v in good.items() if k != "checker_exit_code"},
        {k: v for k, v in good.items() if k != "checker_version"},
        "not-a-record",
    ]
    for rec in bad_variants:
        res = sf.evaluate_pull_request(DIFF_T2, proof_script=PROOF, proof_record=rec)  # type: ignore[arg-type]
        assert res.passed is False, rec
        assert res.reason_code == "REJECT_MISSING_PROOF_OBLIGATION", rec
    assert sf.check_proof_obligation(PROOF, good) == "OK_PROOF_OBLIGATION_RECORD_PRESENT"
    assert sf.check_proof_obligation(None, good) == "REJECT_MISSING_PROOF_OBLIGATION"


def test_slop_filter_hallucinated_package_with_high_risk_tier() -> None:
    sf = SlopFilter()
    diff = """
+import unvetted_crypto_lib
+def execute_wire(amount):
+    transfer(amount)
"""
    proof = "theorem safety : Inv"
    res = sf.evaluate_pull_request(diff, proof_script=proof, proof_record=_record(proof))
    assert res.passed is False
    assert res.reason_code == "REJECT_SLOPSQUATTING_PACKAGE"
    assert res.risk_tier == "T3"
    assert res.detected_hallucinated_packages == ("unvetted_crypto_lib",)


def test_regression_import_forms_detected() -> None:
    sf = SlopFilter()
    cases = {
        "+import requests as r": ("requests",),
        "+import os, evilpkg": ("evilpkg",),
        '+mod = __import__("evilpkg")': ("evilpkg",),
        '+m = importlib.import_module("evilpkg.sub")': ("evilpkg",),
        "+from evilpkg.sub import thing as t": ("evilpkg",),
        "+import evilpkg.sub": ("evilpkg",),
        "+evilpkg>=1.0": ("evilpkg",),
        "+evil-pkg[extra]==1.2": ("evil_pkg",),
        "+    import evilpkg  # indented": ("evilpkg",),
        "+if True: import evilpkg": ("evilpkg",),
    }
    for diff, expected in cases.items():
        assert sf.scan_for_hallucinated_packages(diff) == expected, diff
        res = sf.evaluate_pull_request(diff)
        assert res.passed is False, diff
        assert res.reason_code == "REJECT_SLOPSQUATTING_PACKAGE", diff


def test_regression_import_fallback_regex_paths() -> None:
    sf = SlopFilter()
    # Lines that are not standalone-parseable Python fall back to regex.
    assert sf.scan_for_hallucinated_packages("+import os, evilpkg as e  \\") == ("evilpkg",)
    assert sf.scan_for_hallucinated_packages("+from evilpkg import (") == ("evilpkg",)
    assert sf.scan_for_hallucinated_packages("+from . import (") == ()
    assert sf.scan_for_hallucinated_packages("+from .evilpkg import (") == ()
    assert sf.scan_for_hallucinated_packages("+from evilpkg.sub import (") == ("evilpkg",)
    assert sf.scan_for_hallucinated_packages('+x = (__import__("evilpkg")') == ("evilpkg",)
    assert sf.scan_for_hallucinated_packages("+import (") == ()


def test_relative_and_stdlib_imports_allowed() -> None:
    sf = SlopFilter()
    diff = """
+++ b/src/mod.py
+from . import sibling
+from .pkg import thing
+from ..parent import other
+from __future__ import annotations
+import importlib
+m = importlib.import_module(".local", __package__)
+import collections.abc
"""
    assert sf.scan_for_hallucinated_packages(diff) == ()
    assert sf.scan_for_unpinned_requirements(diff) == ()


def test_requirement_files_and_pinning() -> None:
    sf = SlopFilter()
    req_diff = """
--- a/requirements.txt
+++ b/requirements.txt
+pytest==8.1.1
+# comment line
+-r other.txt
+-e git+https://example.invalid/x.git#egg=x
+ # indented comment
+
+hypothesis
"""
    assert sf.scan_for_hallucinated_packages(req_diff) == ()
    assert sf.scan_for_unpinned_requirements(req_diff) == ("hypothesis",)
    res = sf.evaluate_pull_request(req_diff)
    assert res.passed is False
    assert res.reason_code == "REJECT_UNPINNED_DEPENDENCY"
    assert res.risk_tier == "T1"

    sf2 = SlopFilter(allowed_packages=["pytest", "Py-Yaml"])
    for line in ("pytest>=8", "pytest~=8.1", "pytest==8.*", "pytest>=8,<9",
                 "pytest", "pytest!=8.0"):
        d = f"+++ b/requirements-dev.txt\n+{line}"
        assert sf2.scan_for_unpinned_requirements(d) == ("pytest",), line
    for line in ("pytest==8.1.1", "pytest===8.1.1", "py_yaml==6.0 ; python_version>'3'",
                 "pytest==8.1.1  # pinned"):
        d = f"+++ b/requirements.txt\n+{line}"
        assert sf2.scan_for_unpinned_requirements(d) == (), line
        assert sf2.scan_for_hallucinated_packages(d) == (), line
        assert sf2.evaluate_pull_request(d).passed is True, line

    # Unknown-context unpinned allowed dependency
    res_u = sf.evaluate_pull_request("+pytest>=8.0")
    assert res_u.passed is False
    assert res_u.reason_code == "REJECT_UNPINNED_DEPENDENCY"
    assert sf.scan_for_hallucinated_packages("+pytest>=8.0") == ()


def test_pyproject_dependency_lines() -> None:
    sf = SlopFilter()
    diff = """
+++ b/pyproject.toml
+dependencies = [
+    "evilpkg>=2.0",
+    'pytest==8.1.1',
+]
"""
    assert sf.scan_for_hallucinated_packages(diff) == ("evilpkg",)
    assert sf.scan_for_unpinned_requirements(diff) == ("evilpkg",)
    assert sf.scan_for_hallucinated_packages('+++ b/pyproject.toml\n+"pytest>=8",') == ()
    assert sf.scan_for_unpinned_requirements('+++ b/pyproject.toml\n+"pytest>=8",') == ("pytest",)


def test_python_files_ignore_requirement_like_lines_and_other_files_ignored() -> None:
    sf = SlopFilter()
    # In a .py file, "x==1" is code, not a requirement.
    assert sf.scan_for_hallucinated_packages("+++ b/src/a.py\n+evilpkg==1.0") == ()
    # Non-Python, non-requirement files are not scanned for imports.
    assert sf.scan_for_hallucinated_packages("+++ b/README.md\n+import evilpkg") == ()
    # Unknown context: spaced comparisons and bare words are code, not requirements.
    assert sf.scan_for_hallucinated_packages("+total == 1") == ()
    assert sf.scan_for_hallucinated_packages("+evilpkg") == ()
    # Header resets per file.
    multi = "+++ b/README.md\n+import a1\n+++ b/x.py\n+import evilpkg"
    assert sf.scan_for_hallucinated_packages(multi) == ("evilpkg",)


def test_requirement_spec_frozen() -> None:
    from src.slop_filter import RequirementSpec

    spec = RequirementSpec(name="pytest", pinned=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.pinned = False  # type: ignore[misc]
