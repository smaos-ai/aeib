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
xctest_tamper_guard.py — XCTest / Swift Testing anti-reward-hacking gate (Wave 8 prototype).

Evaluated under the stated model:
- The guard reads the diff itself from the real git worktree
  (`git diff --no-color --no-ext-diff HEAD -- <path>`, out-of-process, empty
  env, timeout). It does not accept agent-reported booleans such as
  "test_failed" or "agent_attempted_test_edit" (trivial verifier).
- On a weakened test (deleted XCTAssert/#expect/#require line, deleted test
  function, injected tautology like XCTAssertTrue(true)) the outcome is HALT,
  unless the agent requests escalation and points at a real .xcresult bundle
  inside the repo; the guard hashes that bundle itself. Escalation is a
  non-penalized route to a human, NOT an approval to merge.
- Pinned-oracle rule: any removed/changed line in an existing test file halts
  (pure additions pass), and `evaluate_worktree()` checks every changed or
  deleted test file found by `git status`, so edits made through other tools
  (e.g. Xcode's own agent file tools) are covered too.

Limitations (stated honestly): detection is lexical over the diff. It flags a
deleted assertion even if an equivalent one is added elsewhere (fail closed),
and it does not detect weakening done through helper functions, changed
tolerances, or edits to production code that make a test vacuous. The
.xcresult digest proves a bundle with those bytes exists; it does not prove
the bundle came from an honest run.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.jcs_canonicalizer import encode_jcs

ALLOW = "ALLOW"
HALT = "HALT"
ESCALATE = "ESCALATE_TO_HUMAN"


@dataclass(frozen=True)
class XCTestVerdict:
    disposition: str
    reason: str
    diff_sha256: str
    xcresult_digest: Optional[str] = None


class XCTestTamperGuard:
    _DELETED_ASSERTION_RE = re.compile(
        r"^-(?!--)\s*(?:try\s+)?(?:XCTAssert\w*|XCTFail|#expect|#require)\b", re.MULTILINE
    )
    _TAUTOLOGY_RE = re.compile(
        r"^\+(?!\+\+)\s*(?:XCTAssert(?:True)?\s*\(\s*(?:true|1\s*==\s*1)\s*\)"
        r"|#expect\s*\(\s*true\s*\))",
        re.MULTILINE,
    )
    _DELETED_TEST_FUNC_RE = re.compile(
        r"^-(?!--)\s*(?:@Test\b[^\n]*\n-\s*)?(?:@Test\s+)?func\s+test\w*\s*\(|^-(?!--)\s*@Test\b",
        re.MULTILINE,
    )
    _REMOVED_LINE_RE = re.compile(r"^-(?!--)", re.MULTILINE)

    def __init__(self, repo_root: str, git_timeout_s: float = 20.0) -> None:
        if not isinstance(repo_root, str) or not repo_root.strip():
            raise ValueError("ERR_INVALID_REPO_ROOT")
        self.repo_root = os.path.realpath(repo_root)
        self.git_timeout_s = git_timeout_s

    # ----------------------------------------------------------------- paths
    def _resolve_inside_repo(self, rel_path: str) -> Optional[str]:
        if not isinstance(rel_path, str) or not rel_path.strip() or "\x00" in rel_path or os.path.isabs(rel_path):
            return
        full = os.path.realpath(os.path.join(self.repo_root, rel_path))
        if os.path.commonpath([self.repo_root, full]) != self.repo_root:
            return
        return full

    @staticmethod
    def is_xctest_file(file_path: str) -> bool:
        normed = posixpath.normpath(file_path)
        if not normed.endswith(".swift"):
            return False
        base = posixpath.basename(normed)
        if base.endswith(("Tests.swift", "Test.swift")):
            return True
        return any(seg.endswith(("Tests", "UITests")) for seg in normed.split("/")[:-1])

    # ------------------------------------------------------------------ diff
    def read_worktree_diff(self, rel_path: str) -> str:
        """Diff of the working tree vs HEAD for one path, read by the guard."""
        if self._resolve_inside_repo(rel_path) is None:
            raise ValueError("HALT_PATH_OUTSIDE_REPO")
        res = subprocess.run(
            ["git", "-C", self.repo_root, "diff", "--no-color", "--no-ext-diff", "HEAD", "--", rel_path],
            capture_output=True, text=True, timeout=self.git_timeout_s,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "GIT_CONFIG_NOSYSTEM": "1",
                 "HOME": self.repo_root},
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"HALT_GIT_DIFF_FAILED:{res.returncode}")
        return res.stdout

    @classmethod
    def detect_tampering_in_diff(cls, diff_text: str) -> Optional[str]:
        if cls._TAUTOLOGY_RE.search(diff_text):
            return "TAUTOLOGY_ASSERTION_INJECTION"
        if cls._DELETED_TEST_FUNC_RE.search(diff_text):
            return "TEST_CASE_DELETION"
        if cls._DELETED_ASSERTION_RE.search(diff_text):
            return "ASSERTION_DELETION"
        if cls._REMOVED_LINE_RE.search(diff_text):
            # Pinned-oracle rule: existing test lines are immutable. Changing an
            # expected value (200 -> 201) or rewriting a helper needs a removed
            # line, so pure additions pass and any edit of an existing line halts.
            return "EXISTING_TEST_LINE_MODIFIED"
        return

    def changed_paths(self) -> List[Tuple[str, str]]:
        """(status, path) for every change in the worktree vs HEAD, including
        untracked files, read from `git status --porcelain=v1 -z`."""
        res = subprocess.run(
            ["git", "-C", self.repo_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            capture_output=True, text=True, timeout=self.git_timeout_s,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "GIT_CONFIG_NOSYSTEM": "1",
                 "HOME": self.repo_root},
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"HALT_GIT_STATUS_FAILED:{res.returncode}")
        out: List[Tuple[str, str]] = []
        fields = res.stdout.split("\x00")
        i = 0
        while i < len(fields):
            entry = fields[i]
            i += 1
            if len(entry) < 4:
                continue
            status, path = entry[:2], entry[3:]
            out.append((status, path))
            if "R" in status or "C" in status:
                out.append(("D ", fields[i]))  # rename/copy source path follows
                i += 1
        return out

    def evaluate_worktree(self) -> Tuple[XCTestVerdict, ...]:
        """Evaluate every changed test file in the worktree (covers edits made
        by any tool, e.g. Xcode's own agent file-write tools, not only ours).
        Fails closed if git cannot be read."""
        try:
            changes = self.changed_paths()
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            return (XCTestVerdict(HALT, f"HALT_CANNOT_READ_WORKTREE:{type(exc).__name__}", ""),)
        verdicts = []
        for status, path in changes:
            if not self.is_xctest_file(path):
                continue
            if "D" in status:
                verdicts.append(XCTestVerdict(HALT, f"HALT_XCTEST_REWARD_HACKING_ATTEMPT:TEST_FILE_DELETED:{path}", ""))
            elif status == "??":
                verdicts.append(XCTestVerdict(ALLOW, f"OK_NEW_TEST_FILE:{path}", ""))
            else:
                verdicts.append(self.evaluate_path(path))
        return tuple(verdicts)

    # -------------------------------------------------------------- xcresult
    def digest_xcresult_bundle(self, rel_bundle_path: str) -> Optional[str]:
        """sha256 over JCS of sorted (relative path, file sha256) pairs. Symlinks
        inside the bundle are rejected. Returns None if not a bundle dir."""
        full = self._resolve_inside_repo(rel_bundle_path)
        if full is None or not full.endswith(".xcresult") or not os.path.isdir(full):
            return
        entries = []
        for dirpath, dirnames, filenames in os.walk(full):
            for name in dirnames + filenames:
                if os.path.islink(os.path.join(dirpath, name)):
                    return
            for name in filenames:
                p = os.path.join(dirpath, name)
                with open(p, "rb") as fh:
                    entries.append([os.path.relpath(p, full), hashlib.sha256(fh.read()).hexdigest()])
        if not entries:
            return
        entries.sort()
        return f"sha256:{hashlib.sha256(encode_jcs(entries)).hexdigest()}"

    # ---------------------------------------------------------------- policy
    def evaluate_path(
        self, rel_path: str, escalation_reason: Optional[str] = None,
        xcresult_bundle_path: Optional[str] = None,
    ) -> XCTestVerdict:
        try:
            diff_text = self.read_worktree_diff(rel_path)
        except (ValueError, RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            return XCTestVerdict(HALT, f"HALT_CANNOT_READ_DIFF:{type(exc).__name__}", "")
        return self.evaluate_diff(rel_path, diff_text, escalation_reason, xcresult_bundle_path)

    def evaluate_diff(
        self, rel_path: str, diff_text: str, escalation_reason: Optional[str] = None,
        xcresult_bundle_path: Optional[str] = None,
    ) -> XCTestVerdict:
        """Policy core. Public so the harness can apply it to a diff it produced
        itself; agents must not be the source of `diff_text`."""
        diff_sha = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
        if not self.is_xctest_file(rel_path):
            return XCTestVerdict(ALLOW, "OK_NON_TEST_FILE_MUTATION", diff_sha)
        kind = self.detect_tampering_in_diff(diff_text)
        if kind is None:
            return XCTestVerdict(ALLOW, "OK_XCTEST_MUTATION_COMPLIANT", diff_sha)
        if escalation_reason is None and xcresult_bundle_path is None:
            return XCTestVerdict(HALT, f"HALT_XCTEST_REWARD_HACKING_ATTEMPT:{kind}", diff_sha)
        if not isinstance(escalation_reason, str) or not escalation_reason.strip():
            return XCTestVerdict(HALT, "HALT_XCTEST_ESCALATION_MISSING_REASON", diff_sha)
        digest = self.digest_xcresult_bundle(xcresult_bundle_path or "")
        if digest is None:
            return XCTestVerdict(HALT, "HALT_XCTEST_ESCALATION_MISSING_OR_INVALID_XCRESULT", diff_sha)
        return XCTestVerdict(ESCALATE, f"ESCALATE_CONTRADICTORY_SPEC_OR_BROKEN_ORACLE:{kind}", diff_sha, digest)

    @staticmethod
    def escalation_receipt(rel_path: str, verdict: XCTestVerdict, escalation_reason: str) -> Dict[str, Any]:
        if verdict.disposition != ESCALATE or verdict.xcresult_digest is None:
            raise ValueError("ERR_RECEIPT_REQUIRES_ESCALATE_VERDICT")
        body: Dict[str, Any] = {
            "disposition": verdict.disposition,
            "escalation_reason": escalation_reason,
            "file_path": posixpath.normpath(rel_path),
            "git_diff_sha256": verdict.diff_sha256,
            "reason": verdict.reason,
            "xcresult_bundle_digest": verdict.xcresult_digest,
        }
        receipt = dict(body)
        receipt["receipt_caid"] = f"sha256:{hashlib.sha256(encode_jcs(body)).hexdigest()}"
        return receipt
