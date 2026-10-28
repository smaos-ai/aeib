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
src/slop_filter.py
================================================================================
Automated PR Slop Filter & Dependency Provenance Gate (Scaffold).

Evaluated under the stated model (scaffold verifier):
Protects open-source repositories from low-quality AI code generation (slop),
slopsquatting (hallucinated package additions), and unverified high-risk mutations.

Scope limits (stated plainly):
- This filter does NOT run any proof checker (Lean 4, TLC, Z3). For T2/T3 diffs
  it only checks that a checker-run *record* is present, structurally well-formed,
  bound to the supplied proof text by SHA-256, and reports exit code 0. A caller
  can fabricate such a record; actual verification must happen in CI by running
  the checker itself (e.g. ``scripts/run_tlc_formal_gate.sh`` for the TLA+ model).
  The OK status is therefore ``OK_PROOF_OBLIGATION_RECORD_PRESENT``, not "verified".
- Dependency detection inspects added diff lines only (Python imports via ``ast``
  with a regex fallback, dynamic ``__import__`` / ``importlib.import_module``
  string literals, and PEP 508 requirement lines in requirements files,
  ``pyproject.toml`` and unlabelled diffs). ``package.json`` and other ecosystems
  are not inspected.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import posixpath
import re
import sys
from dataclasses import dataclass
from typing import Any, FrozenSet, Iterator, List, Mapping, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class SlopEvaluationResult:
    """Outcome of slop filter evaluation on candidate pull request diff."""

    passed: bool
    reason_code: str
    risk_tier: str
    detected_hallucinated_packages: Tuple[str, ...]


@dataclass(frozen=True)
class ProofObligationRecord:
    """Record of an external proof-checker run, bound to the proof text by digest.

    The filter does not execute the checker; it only validates this record.
    """

    checker: str
    artifact_sha256: str
    checker_exit_code: int
    checker_version: str


@dataclass(frozen=True)
class RequirementSpec:
    """A dependency requirement parsed from an added diff line."""

    name: str
    pinned: bool


ProofRecordInput = Union[ProofObligationRecord, Mapping[str, Any]]

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_REQ_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?P<extras>\[[A-Za-z0-9._,\s-]*\])?"
    r"(?P<spec>(?:\s*(?:===|==|>=|<=|~=|!=|>|<)\s*[A-Za-z0-9.*+!_-]+\s*,?)*)"
    r"\s*(?:;.*)?$"
)
_SPEC_ITEM = re.compile(r"(===|==|>=|<=|~=|!=|>|<)\s*([A-Za-z0-9.*+!_-]+)")
_DYNAMIC_IMPORT = re.compile(
    r"(?:__import__|import_module)\(\s*[\"']([A-Za-z0-9_.]+)[\"']"
)
_FROM_IMPORT = re.compile(r"^from\s+(\.*)([A-Za-z0-9_.]*)\s+import\b")
_PLAIN_IMPORT = re.compile(r"^import\s+(.+)$")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def _top_level(module: str) -> str:
    return module.split(".")[0].lower()


def _parse_requirement(content: str) -> Optional[RequirementSpec]:
    """Parses a PEP 508-style requirement line; returns None if not a requirement."""
    # Comment-only, option (-r/-e) and empty lines fail the name pattern below.
    text = content.partition(" #")[0].strip()
    m = _REQ_LINE.match(text)
    if m is None:
        return None
    items = _SPEC_ITEM.findall(m.group("spec") or "")
    pinned = (
        len(items) == 1
        and items[0][0] in ("==", "===")
        and "*" not in items[0][1]
    )
    return RequirementSpec(name=_normalize(m.group("name")), pinned=pinned)


def _python_imports(content: str) -> List[str]:
    """Returns absolute top-level module names imported by one added line."""
    found: List[str] = []
    try:
        tree = ast.parse(content.strip())
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.extend(_top_level(alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    found.append(_top_level(node.module))
            elif isinstance(node, ast.Call) and node.args:
                func = node.func
                fname = (
                    func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute)
                    else ""
                )
                arg0 = node.args[0]
                if (
                    fname in ("__import__", "import_module")
                    and isinstance(arg0, ast.Constant)
                    and isinstance(arg0.value, str)
                    and arg0.value
                    and not arg0.value.startswith(".")
                ):
                    found.append(_top_level(arg0.value))
        return found

    # Regex fallback for lines that are not standalone-parseable Python.
    stripped = content.strip()
    m_from = _FROM_IMPORT.match(stripped)
    if m_from:
        if not m_from.group(1) and m_from.group(2):
            found.append(_top_level(m_from.group(2)))
    else:
        m_imp = _PLAIN_IMPORT.match(stripped)
        if m_imp:
            for part in m_imp.group(1).split(","):
                token = part.strip().split(" ")[0].strip("()")
                if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", token):
                    found.append(_top_level(token))
    for mod in _DYNAMIC_IMPORT.findall(stripped):
        found.append(_top_level(mod))
    return found


class SlopFilter:
    """
    Evaluates pull request diffs to intercept hallucinated dependencies
    and require a digest-bound proof-obligation record on high-risk modifications.
    """

    STANDARD_STDLIB_MODULES: FrozenSet[str] = frozenset(
        {
            "abc", "argparse", "ast", "asyncio", "base64", "collections",
            "concurrent", "contextlib", "copy", "csv", "ctypes", "dataclasses",
            "datetime", "decimal", "enum", "errno", "fcntl", "functools",
            "hashlib", "hmac", "importlib", "inspect", "io", "itertools",
            "json", "logging", "math", "multiprocessing", "os", "pathlib",
            "pickle", "platform", "queue", "re", "secrets", "shutil",
            "signal", "socket", "sqlite3", "ssl", "stat", "string",
            "subprocess", "sys", "tempfile", "threading", "time", "typing",
            "unittest", "urllib", "uuid", "warnings", "weakref", "zoneinfo",
        }
    ) | frozenset(getattr(sys, "stdlib_module_names", ()))

    HIGH_RISK_KEYWORDS: FrozenSet[str] = frozenset(
        {
            "transfer", "wire", "escrow", "crypto", "ed25519", "private_key",
            "signing", "wallet", "x402", "settlement", "payment", "execute_wire",
        }
    )

    SUPPORTED_PROOF_CHECKERS: FrozenSet[str] = frozenset({"lean4", "tlc", "z3"})

    def __init__(
        self,
        allowed_packages: Optional[Sequence[str]] = None,
    ) -> None:
        if allowed_packages is not None:
            self._allowed: FrozenSet[str] = frozenset(allowed_packages)
        else:
            self._allowed = frozenset(
                {"pytest", "cryptography", "hypothesis", "pydantic", "fastapi"}
            )
        self._allowed_normalized: FrozenSet[str] = frozenset(
            _normalize(p) for p in self._allowed
        )

    def classify_risk_tier(self, diff: str) -> str:
        """Classifies pull request risk based on semantic keywords."""
        lower = diff.lower()
        for kw in self.HIGH_RISK_KEYWORDS:
            if kw in lower:
                return "T3"

        if "def " in diff or "class " in diff or "async def " in diff:
            return "T2"

        return "T1"

    @staticmethod
    def _added_lines(diff: str) -> Iterator[Tuple[str, str]]:
        """Yields (file_kind, content) for each added line.

        file_kind is "python", "requirements", "pyproject", "other" or "unknown".
        """
        kind = "unknown"
        for line in diff.splitlines():
            line_strip = line.strip()
            if line_strip.startswith("+++"):
                path = line_strip[3:].strip().lower()
                base = posixpath.basename(path)
                if base.endswith((".py", ".pyi")):
                    kind = "python"
                elif re.match(r"^(requirements|constraints)[\w.-]*\.(txt|in)$", base):
                    kind = "requirements"
                elif base == "pyproject.toml":
                    kind = "pyproject"
                else:
                    kind = "other"
                continue
            if not line_strip.startswith("+"):
                continue
            yield kind, line_strip[1:].strip()

    def _requirements(self, diff: str) -> List[RequirementSpec]:
        reqs: List[RequirementSpec] = []
        for kind, content in self._added_lines(diff):
            if kind == "requirements":
                spec = _parse_requirement(content)
            elif kind == "pyproject":
                m = re.match(r"^[\"']([^\"']+)[\"']\s*,?$", content)
                spec = _parse_requirement(m.group(1)) if m else None
            elif kind == "unknown":
                spec = _parse_requirement(content)
                # Outside a known requirements file, a bare word or a spaced
                # comparison is far more likely code than a requirement.
                if spec is not None and not re.match(
                    r"^[A-Za-z0-9._-]+(\[[^\]]*\])?(===|==|>=|<=|~=|!=|>|<)\d", content
                ):
                    spec = None
            else:
                spec = None
            if spec is not None:
                reqs.append(spec)
        return reqs

    def scan_for_hallucinated_packages(self, diff: str) -> Tuple[str, ...]:
        """Detects imported or added packages not present in the allowed set or stdlib."""
        found: List[str] = []

        def _record(pkg: str) -> None:
            if pkg in self.STANDARD_STDLIB_MODULES:
                return
            if _normalize(pkg) in self._allowed_normalized:
                return
            if pkg not in found:
                found.append(pkg)

        for kind, content in self._added_lines(diff):
            if kind in ("python", "unknown"):
                for mod in _python_imports(content):
                    _record(mod)

        for spec in self._requirements(diff):
            if spec.name not in self._allowed_normalized and spec.name not in found:
                found.append(spec.name)

        return tuple(found)

    def scan_for_unpinned_requirements(self, diff: str) -> Tuple[str, ...]:
        """Returns names of added requirements not pinned with a single exact ``==``."""
        out: List[str] = []
        for spec in self._requirements(diff):
            if not spec.pinned and spec.name not in out:
                out.append(spec.name)
        return tuple(out)

    def check_proof_obligation(
        self, proof_text: Optional[str], proof_record: Optional[ProofRecordInput]
    ) -> str:
        """Checks that a checker-run record is present and bound to ``proof_text``.

        Does not run any checker. Returns a reason code.
        """
        if not isinstance(proof_text, str) or not proof_text.strip():
            return "REJECT_MISSING_PROOF_OBLIGATION"
        if isinstance(proof_record, ProofObligationRecord):
            fields: Mapping[str, Any] = {
                "checker": proof_record.checker,
                "artifact_sha256": proof_record.artifact_sha256,
                "checker_exit_code": proof_record.checker_exit_code,
                "checker_version": proof_record.checker_version,
            }
        elif isinstance(proof_record, Mapping):
            fields = proof_record
        else:
            return "REJECT_MISSING_PROOF_OBLIGATION"

        checker = fields.get("checker")
        digest = fields.get("artifact_sha256")
        exit_code = fields.get("checker_exit_code")
        version = fields.get("checker_version")
        if (
            checker not in self.SUPPORTED_PROOF_CHECKERS
            or not isinstance(digest, str)
            or _SHA256_HEX.match(digest) is None
            or not isinstance(exit_code, int)
            or isinstance(exit_code, bool)
            or not isinstance(version, str)
            or not version.strip()
        ):
            return "REJECT_MISSING_PROOF_OBLIGATION"

        expected = hashlib.sha256(proof_text.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(expected, digest):
            return "REJECT_PROOF_ARTIFACT_DIGEST_MISMATCH"
        if exit_code != 0:
            return "REJECT_PROOF_CHECKER_FAILED"
        return "OK_PROOF_OBLIGATION_RECORD_PRESENT"

    def evaluate_pull_request(
        self,
        diff: str,
        proof_script: Optional[str] = None,
        proof_record: Optional[ProofRecordInput] = None,
    ) -> SlopEvaluationResult:
        """
        Evaluates a diff against slopsquatting and proof-obligation invariants.

        ``proof_script`` is the proof text; ``proof_record`` is the checker-run
        record bound to it. Passing only ``proof_script`` (legacy callers) fails
        closed with ``REJECT_MISSING_PROOF_OBLIGATION`` on T2/T3 diffs. No checker
        is executed here.
        """
        if not diff or not diff.strip():
            return SlopEvaluationResult(
                passed=False,
                reason_code="REJECT_EMPTY_DIFF",
                risk_tier="T0",
                detected_hallucinated_packages=(),
            )

        tier = self.classify_risk_tier(diff)
        hallucinated = self.scan_for_hallucinated_packages(diff)
        if len(hallucinated) > 0:
            return SlopEvaluationResult(
                passed=False,
                reason_code="REJECT_SLOPSQUATTING_PACKAGE",
                risk_tier=tier,
                detected_hallucinated_packages=hallucinated,
            )

        unpinned = self.scan_for_unpinned_requirements(diff)
        if len(unpinned) > 0:
            return SlopEvaluationResult(
                passed=False,
                reason_code="REJECT_UNPINNED_DEPENDENCY",
                risk_tier=tier,
                detected_hallucinated_packages=(),
            )

        if tier in ("T2", "T3"):
            code = self.check_proof_obligation(proof_script, proof_record)
            return SlopEvaluationResult(
                passed=code == "OK_PROOF_OBLIGATION_RECORD_PRESENT",
                reason_code=code,
                risk_tier=tier,
                detected_hallucinated_packages=(),
            )

        return SlopEvaluationResult(
            passed=True,
            reason_code="OK_LOW_RISK_NO_PROOF_OBLIGATION",
            risk_tier=tier,
            detected_hallucinated_packages=(),
        )
