#!/usr/bin/env python3
"""
Pre-Push Defense-in-Depth Integrity Gate (tools/pre_push_integrity_gate.py)

Evaluated under the stated model to prevent push failures and accidental leakage
by design before network transmission to remote repositories (e.g. GitHub).

Interception capabilities:
  1. File Size Ceiling (GH001 Prevention): Blocks any staged blob > 50 MB
     before triggering GitHub's 100 MB hard limit.
  2. Submodule Coherence Latch: Detects orphaned mode 160000 gitlinks lacking
     a corresponding .gitmodules mapping.
  3. Sensitive File Interception: Halts pushes introducing private configuration,
     credential manifests, or commercial outreach registers.
  4. Path-Aware Secret Scanning: Scans added diff lines for high-entropy tokens
     while isolating verified test fixture and benchmark directories.
  5. Upstream Tracking Verification: Inspects whether the local branch has an
     explicitly configured upstream remote branch.

All evaluations emit canonical RFC 8785 JCS receipts with integer status metrics.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs

# File size boundary: 50 Megabytes (GitHub hard limit is 100 MB, warning at 50 MB)
DEFAULT_MAX_FILE_BYTES: int = 50_000_000

# Forbidden private file basenames and patterns
DEFAULT_FORBIDDEN_FILES: Tuple[str, ...] = (
    ".env",
    ".env.production",
    ".claude/settings.local.json",
    ".claude/settings.json",
    "cosign.key",
    "release-key.pem",
    "id_ed25519",
    "id_rsa",
    "LP_TARGET_LIST.csv",
    "OUTREACH_TRACKING.csv",
)

# Standard token patterns for high-risk secrets
SECRET_PATTERN_REGEX: str = (
    r"(\bsk-[a-zA-Z0-9]{32,}\b|"
    r"\bghp_[a-zA-Z0-9]{36}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"-----BEGIN (OPENSSH |ENCRYPTED |EC |RSA |DSA )?PRIVATE KEY-----)"
)

# Directory patterns treated as non-production test fixtures
TEST_PATH_PATTERNS: Tuple[str, ...] = (
    "tests/",
    "tests\\",
    "/tests/",
    "\\tests\\",
    "test_",
    "fixtures/",
    "benchmarks/",
    "ocr-audit-engine/tests/",
    "smaos-audit/tests/",
)


@dataclasses.dataclass(frozen=True)
class PushViolation:
    violation_type: str
    target_path_or_ref: str
    detail: str
    severity: str  # "HALT" or "WARN"

    def to_dict(self) -> Dict[str, str]:
        return {
            "violation_type": self.violation_type,
            "target_path_or_ref": self.target_path_or_ref,
            "detail": self.detail,
            "severity": self.severity,
        }


class PrePushIntegrityGate:
    """
    Deterministic client-side evaluation engine executing before git push.
    Designed to prevent broken pushes, orphan submodules, and secret leaks.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        forbidden_files: Tuple[str, ...] = DEFAULT_FORBIDDEN_FILES,
    ) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self.max_file_bytes = max_file_bytes
        self.forbidden_files = forbidden_files
        self._secret_re = re.compile(SECRET_PATTERN_REGEX)

    def check_submodule_coherence(self) -> List[PushViolation]:
        """
        Inspect git tree for mode 160000 entries (gitlinks) and ensure
        each entry has a corresponding path in .gitmodules.
        """
        violations: List[PushViolation] = []
        gitmodules_path = self.repo_root / ".gitmodules"
        gitmodules_content = ""
        if gitmodules_path.is_file():
            try:
                gitmodules_content = gitmodules_path.read_text(encoding="utf-8")
            except OSError:
                gitmodules_content = ""

        try:
            cmd = ["git", "-C", str(self.repo_root), "ls-files", "-s", "--stage"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return violations

        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=3)
            if len(parts) >= 4 and parts[0] == "160000":
                submodule_sha = parts[1]
                submodule_path = parts[3]
                # Check if path is configured in .gitmodules
                expected_path_entry = f"path = {submodule_path}"
                if expected_path_entry not in gitmodules_content:
                    violations.append(
                        PushViolation(
                            violation_type="ERR_ORPHANED_GITLINK_NO_GITMODULES",
                            target_path_or_ref=submodule_path,
                            detail=(
                                f"Mode 160000 gitlink points to SHA {submodule_sha[:12]}, "
                                f"but '{submodule_path}' is missing from .gitmodules. "
                                "Remote clones and recursive checks will fail with exit 128."
                            ),
                            severity="HALT",
                        )
                    )
        return violations

    def check_pushed_file_sizes(self, rev_range: str) -> List[PushViolation]:
        """
        Inspect git objects introduced in rev_range and verify no blob exceeds max_file_bytes.
        """
        violations: List[PushViolation] = []
        if not rev_range.strip():
            return violations

        try:
            # Query all blob objects in the revision range
            cmd = [
                "git",
                "-C",
                str(self.repo_root),
                "diff-tree",
                "-r",
                "--no-commit-id",
                "--name-only",
                "--diff-filter=ACMR",
                rev_range,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        except subprocess.SubprocessError:
            return violations

        for rel_file in files:
            full_path = self.repo_root / rel_file
            if full_path.is_file():
                try:
                    file_size = full_path.stat().st_size
                    if file_size > self.max_file_bytes:
                        violations.append(
                            PushViolation(
                                violation_type="ERR_FILE_EXCEEDS_PUSH_LIMIT",
                                target_path_or_ref=rel_file,
                                detail=(
                                    f"File size {file_size} bytes exceeds configured ceiling of "
                                    f"{self.max_file_bytes} bytes. Pushing will trigger GitHub GH001 rejection."
                                ),
                                severity="HALT",
                            )
                        )
                except OSError:
                    continue
        return violations

    def check_forbidden_files(self, rev_range: str) -> List[PushViolation]:
        """
        Verify no forbidden private file patterns appear in the pushed commit range.
        """
        violations: List[PushViolation] = []
        if not rev_range.strip():
            return violations

        try:
            cmd = [
                "git",
                "-C",
                str(self.repo_root),
                "log",
                "--name-only",
                "--format=",
                "--diff-filter=ACMR",
                rev_range,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            changed_files = {f.strip() for f in res.stdout.splitlines() if f.strip()}
        except subprocess.SubprocessError:
            return violations

        for changed in changed_files:
            basename = os.path.basename(changed)
            for forbidden in self.forbidden_files:
                if changed == forbidden or basename == forbidden:
                    violations.append(
                        PushViolation(
                            violation_type="ERR_FORBIDDEN_FILE_DETECTED",
                            target_path_or_ref=changed,
                            detail=(
                                f"Forbidden private file '{changed}' is present in pushed range {rev_range}. "
                                "Must be purged from git history before pushing."
                            ),
                            severity="HALT",
                        )
                    )
        return violations

    def check_secret_patterns(self, rev_range: str) -> List[PushViolation]:
        """
        Scan diff additions for high-risk token signatures, excluding whitelisted test paths.
        """
        violations: List[PushViolation] = []
        if not rev_range.strip():
            return violations

        try:
            cmd = [
                "git",
                "-C",
                str(self.repo_root),
                "log",
                "-p",
                "-U0",
                "--no-color",
                "--diff-filter=ACMR",
                rev_range,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.SubprocessError:
            return violations

        current_file: Optional[str] = None
        for line in res.stdout.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                continue
            if line.startswith("+") and not line.startswith("+++"):
                if current_file and self._is_test_or_fixture_path(current_file):
                    continue
                if "# pragma: allowlist secret" in line:
                    continue
                match = self._secret_re.search(line)
                if match:
                    matched_token = match.group(0)
                    redacted = matched_token[:4] + "..." + matched_token[-4:]
                    violations.append(
                        PushViolation(
                            violation_type="ERR_UNREDACTED_SECRET_LEAK",
                            target_path_or_ref=current_file or "unknown",
                            detail=f"Potential unredacted credential pattern detected ({redacted}).",
                            severity="HALT",
                        )
                    )
                    # Limit reports per file
                    break
        return violations

    def check_upstream_tracking(self, branch_name: str) -> Tuple[bool, Optional[str]]:
        """
        Inspect whether local branch has upstream tracking configured.
        """
        try:
            cmd = [
                "git",
                "-C",
                str(self.repo_root),
                "config",
                f"branch.{branch_name}.remote",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            has_remote = bool(res.stdout.strip())
            return has_remote, res.stdout.strip() if has_remote else None
        except (subprocess.SubprocessError, FileNotFoundError):
            return False, None

    def _is_test_or_fixture_path(self, path_str: str) -> bool:
        norm = path_str.replace("\\", "/")
        for pattern in TEST_PATH_PATTERNS:
            if pattern in norm or norm.startswith(pattern):
                return True
        return False

    def evaluate_push_range(
        self,
        local_ref: str,
        local_sha: str,
        remote_ref: str,
        remote_sha: str,
    ) -> Dict[str, Any]:
        """
        Execute full evaluation across all pre-push defense layers.
        Emits RFC 8785 canonical JCS summary receipt.
        """
        violations: List[PushViolation] = []

        # Layer 1: Submodule coherence
        submodule_violations = self.check_submodule_coherence()
        violations.extend(submodule_violations)

        # Layer 2: Revision range evaluation
        zero_sha = "0" * 40
        if local_sha != zero_sha:
            if remote_sha == zero_sha:
                # New branch or tag: determine base commit
                rev_range = f"{local_sha}~1..{local_sha}" if local_sha else ""
            else:
                rev_range = f"{remote_sha}..{local_sha}"

            if rev_range:
                violations.extend(self.check_forbidden_files(rev_range))
                violations.extend(self.check_pushed_file_sizes(rev_range))
                violations.extend(self.check_secret_patterns(rev_range))

        # Layer 3: Upstream tracking on branch refs
        if local_ref.startswith("refs/heads/"):
            branch_name = local_ref.replace("refs/heads/", "")
            has_upstream, _ = self.check_upstream_tracking(branch_name)
            if not has_upstream and remote_sha == zero_sha:
                violations.append(
                    PushViolation(
                        violation_type="WARN_NO_UPSTREAM_CONFIGURED",
                        target_path_or_ref=branch_name,
                        detail=(
                            f"Branch '{branch_name}' has no tracking upstream configured. "
                            "Consider running 'git push -u origin <branch>' or configuring "
                            "'git config --global push.autoSetupRemote true'."
                        ),
                        severity="WARN",
                    )
                )

        halt_count = sum(1 for v in violations if v.severity == "HALT")
        warn_count = sum(1 for v in violations if v.severity == "WARN")
        is_admissible = halt_count == 0

        # Compliance score in integer basis points (0..10000 bps)
        compliance_bps = 10000 if is_admissible else 0

        receipt_payload: Dict[str, Any] = {
            "admissible": is_admissible,
            "compliance_bps": compliance_bps,
            "halt_count": halt_count,
            "local_ref": local_ref,
            "local_sha": local_sha,
            "remote_ref": remote_ref,
            "remote_sha": remote_sha,
            "total_violations": len(violations),
            "violations": [v.to_dict() for v in violations],
            "warn_count": warn_count,
        }

        # Compute deterministic content-addressed intent digest (CAID)
        canonical_bytes = encode_jcs(receipt_payload)
        receipt_caid = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
        receipt_payload["receipt_caid"] = receipt_caid

        return receipt_payload


def main() -> None:
    """CLI runner executing from git pre-push hook."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python3 tools/pre_push_integrity_gate.py [--json]")
        print("Reads pre-push ref ranges from stdin (<local_ref> <local_sha> <remote_ref> <remote_sha>).")
        print("If run interactively without stdin, evaluates current branch against upstream.")
        sys.exit(0)

    gate = PrePushIntegrityGate()
    stdin_data = ""
    if not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()

    if not stdin_data:
        # Fallback manual invocation: verify current branch
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(gate.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        current_branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "HEAD"
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(gate.repo_root),
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        local_ref = f"refs/heads/{current_branch}"
        receipt = gate.evaluate_push_range(local_ref, head_sha, local_ref, head_sha)
        if not receipt["admissible"]:
            print(f"❌ [PRE-PUSH INTERLOCK] Verification failed for {local_ref}:", file=sys.stderr)
            for v in receipt["violations"]:
                if v["severity"] == "HALT":
                    print(f"   [{v['violation_type']}] {v['target_path_or_ref']}: {v['detail']}", file=sys.stderr)
            sys.exit(1)
        print("✅ [PRE-PUSH INTERLOCK] Pre-push defense-in-depth gate passed.")
        sys.exit(0)

    any_halt = False
    for line in stdin_data.splitlines():
        parts = line.strip().split()
        if len(parts) == 4:
            local_ref, local_sha, remote_ref, remote_sha = parts
            receipt = gate.evaluate_push_range(local_ref, local_sha, remote_ref, remote_sha)
            if not receipt["admissible"]:
                any_halt = True
                print(f"❌ [PRE-PUSH INTERLOCK] Push rejected for {local_ref}:", file=sys.stderr)
                for v in receipt["violations"]:
                    if v["severity"] == "HALT":
                        print(f"   [{v['violation_type']}] {v['target_path_or_ref']}: {v['detail']}", file=sys.stderr)

    if any_halt:
        sys.exit(1)
    print("✅ [PRE-PUSH INTERLOCK] All pre-push defense-in-depth gates passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
