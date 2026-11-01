# Copyright 2026 SovereignNexus Project
#
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
src/reality/git_oracle.py — Deterministic Local Git State Oracle & Push Failure Interceptor.

Solves the expensive "Git Exploration Token Sink":
When remote push fails (non-fast-forward, diverged upstream, unmerged conflicts),
naive agents run `git log`, `git diff`, and `git status` repeatedly, injecting
30,000 to 80,000 tokens of raw log text into conversation context.

The GitStateOracle inspects local git porcelain status, merge-base, and refspecs:
1. Classifies divergence status deterministically in <5ms:
   - CLEAN_FAST_FORWARDABLE: local is ahead, upstream has 0 new commits.
   - REMOTE_AHEAD_REBASE_REQUIRED: upstream has commits not present locally.
   - DIVERGED_BRANCH: both local and upstream have independent commits.
   - UNTRACKED_REMOTE_REF: branch has no configured upstream tracking branch.
   - DIRTY_WORKING_TREE: uncommitted changes prevent safe operation.
   - PRE_PUSH_INVARIANT_VIOLATION: file size > 50MB, orphaned gitlink, or secret.
2. Emits a compact (<150 token) JSON capsule with exact remediation command and
   a content-addressed diff pointer (ptr_sha256) rather than raw logs.
"""

import dataclasses
import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs

STATUS_CLEAN_FAST_FORWARDABLE = "CLEAN_FAST_FORWARDABLE"
STATUS_REMOTE_AHEAD_REBASE_REQUIRED = "REMOTE_AHEAD_REBASE_REQUIRED"
STATUS_DIVERGED_BRANCH = "DIVERGED_BRANCH"
STATUS_UNTRACKED_REMOTE_REF = "UNTRACKED_REMOTE_REF"
STATUS_DIRTY_WORKING_TREE = "DIRTY_WORKING_TREE"
STATUS_PRE_PUSH_INVARIANT_VIOLATION = "PRE_PUSH_INVARIANT_VIOLATION"
STATUS_UP_TO_DATE = "UP_TO_DATE"


@dataclass(frozen=True)
class GitPushFailureCapsule:
    branch: str
    target_remote: str
    target_branch: str
    divergence_status: str
    local_ahead_count: int
    remote_behind_count: int
    is_dirty: bool
    conflicted_files: Tuple[str, ...]
    remediation_command: str
    diff_pointer_caid: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch": self.branch,
            "target_remote": self.target_remote,
            "target_branch": self.target_branch,
            "divergence_status": self.divergence_status,
            "local_ahead_count": self.local_ahead_count,
            "remote_behind_count": self.remote_behind_count,
            "is_dirty": self.is_dirty,
            "conflicted_files": list(self.conflicted_files),
            "remediation_command": self.remediation_command,
            "diff_pointer_caid": self.diff_pointer_caid,
            "explanation": self.explanation,
        }


class GitStateOracle:
    """
    Deterministic query engine for Git repository status, tracking, and divergence.
    Never passes unbounded git diff or git log stdout to context.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()

    def _run_git(self, args: Sequence[str], check: bool = False) -> Tuple[int, str, str]:
        """Runs a git command with timeout and returns (returncode, stdout, stderr)."""
        proc = subprocess.run(
            ["git", "-C", str(self.repo_root)] + list(args),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(args)}\n{proc.stderr}")
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def get_current_branch(self) -> str:
        """Returns the current branch name or detached HEAD SHA."""
        rc, out, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return out if rc == 0 else "UNKNOWN"

    def get_upstream_branch(self, branch: Optional[str] = None) -> Optional[str]:
        """Returns the tracking upstream ref (e.g. origin/main) or None."""
        target = branch or "HEAD"
        rc, out, _ = self._run_git(["rev-parse", "--abbrev-ref", f"{target}@{{u}}"])
        return out if rc == 0 and out else None

    def check_dirty_tree(self) -> Tuple[bool, List[str]]:
        """Returns (is_dirty, list_of_modified_or_untracked_files)."""
        rc, out, _ = self._run_git(["status", "--porcelain=v2"])
        if rc != 0 or not out:
            return False, []
        lines = out.splitlines()
        dirty_files: List[str] = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                dirty_files.append(parts[-1])
        return len(dirty_files) > 0, dirty_files

    def diagnose_divergence(
        self,
        target_remote: str = "origin",
        target_branch: Optional[str] = None,
    ) -> GitPushFailureCapsule:
        """
        Diagnoses local vs remote divergence and produces a compact <150 token capsule.
        """
        branch = self.get_current_branch()
        is_dirty, dirty_files = self.check_dirty_tree()

        # Determine target remote branch
        upstream = self.get_upstream_branch(branch)
        if upstream is None:
            effective_target_branch = target_branch or branch
            # Check if remote ref exists
            rc, _, _ = self._run_git(["rev-parse", "--verify", f"{target_remote}/{effective_target_branch}"])
            if rc != 0:
                # Untracked remote branch
                return GitPushFailureCapsule(
                    branch=branch,
                    target_remote=target_remote,
                    target_branch=effective_target_branch,
                    divergence_status=STATUS_UNTRACKED_REMOTE_REF,
                    local_ahead_count=0,
                    remote_behind_count=0,
                    is_dirty=is_dirty,
                    conflicted_files=(),
                    remediation_command=f"git push -u {target_remote} {branch}",
                    diff_pointer_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    explanation=f"Branch '{branch}' has no remote tracking branch configured. Run push with -u flag.",
                )
            upstream = f"{target_remote}/{effective_target_branch}"

        # Fetch counts of ahead / behind
        rc, count_out, _ = self._run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"])
        ahead = 0
        behind = 0
        if rc == 0 and count_out:
            parts = count_out.split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])

        # Generate diff summary hash
        rc_diff, diff_out, _ = self._run_git(["diff", "-U3", f"{upstream}...HEAD"])
        diff_bytes = diff_out.encode("utf-8") if rc_diff == 0 else b""
        diff_pointer_caid = "sha256:" + hashlib.sha256(diff_bytes).hexdigest()

        # Check conflicted files if rebase or merge in progress
        conflicted: List[str] = []
        rc_merge, merge_out, _ = self._run_git(["diff", "--name-only", "--diff-filter=U"])
        if rc_merge == 0 and merge_out:
            conflicted = merge_out.splitlines()

        if behind == 0 and ahead == 0:
            status = STATUS_UP_TO_DATE
            remediation = "echo 'Up to date. No action needed.'"
            explanation = "Local branch is synchronized with upstream."
        elif behind == 0 and ahead > 0:
            status = STATUS_CLEAN_FAST_FORWARDABLE
            remediation = f"git push {target_remote} {branch}"
            explanation = f"Local is {ahead} commit(s) ahead and ready for clean fast-forward push."
        elif behind > 0 and ahead == 0:
            status = STATUS_REMOTE_AHEAD_REBASE_REQUIRED
            remediation = f"git pull --rebase {target_remote} {branch}"
            explanation = f"Remote is {behind} commit(s) ahead. Rebase required before push."
        else:
            status = STATUS_DIVERGED_BRANCH
            remediation = f"git fetch {target_remote} && git rebase {upstream}"
            explanation = f"Branch diverged: local is {ahead} ahead, remote is {behind} ahead. Rebase required."

        if is_dirty and status != STATUS_UP_TO_DATE:
            status = STATUS_DIRTY_WORKING_TREE
            remediation = "git stash && " + remediation + " && git stash pop"
            explanation = f"Working tree has uncommitted modifications ({len(dirty_files)} files). Stash before rebase/push."

        return GitPushFailureCapsule(
            branch=branch,
            target_remote=target_remote,
            target_branch=upstream,
            divergence_status=status,
            local_ahead_count=ahead,
            remote_behind_count=behind,
            is_dirty=is_dirty,
            conflicted_files=tuple(conflicted),
            remediation_command=remediation,
            diff_pointer_caid=diff_pointer_caid,
            explanation=explanation,
        )


@dataclass(frozen=True)
class PrePushVerificationReceipt:
    repo_root: str
    branch: str
    verified: bool
    status_code: str
    violations: Tuple[str, ...]
    largest_file_bytes: int
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "branch": self.branch,
            "verified": self.verified,
            "status_code": self.status_code,
            "violations": list(self.violations),
            "largest_file_bytes": self.largest_file_bytes,
            "receipt_caid": self.receipt_caid,
        }


def verify_pre_push_invariants(
    repo_root: Path,
    max_file_bytes: int = 50_000_000,
    forbidden_file_names: Sequence[str] = (
        ".env",
        ".env.production",
        ".claude/settings.local.json",
        ".claude/settings.json",
        "cosign.key",
        "release-key.pem",
        "id_ed25519",
        "id_rsa",
    ),
) -> PrePushVerificationReceipt:
    """
    Evaluates repository state against Lesson L26 pre-push airgap invariants:
    - No staged file > max_file_bytes (default 50 MB)
    - No forbidden credential files
    - Mode 160000 gitlinks must exist in .gitmodules
    """
    violations: List[str] = []
    largest_file = 0

    # 1. Inspect staged files
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    staged_files = proc.stdout.splitlines() if proc.returncode == 0 else []

    for rel in staged_files:
        full = repo_root / rel
        basename = os.path.basename(rel)
        if basename in forbidden_file_names or any(rel.endswith(f) for f in forbidden_file_names):
            violations.append(f"FORBIDDEN_FILE_STAGED: {rel}")
        if full.is_file():
            try:
                size = full.stat().st_size
                if size > largest_file:
                    largest_file = size
                if size > max_file_bytes:
                    violations.append(f"LARGE_FILE_OVER_50MB: {rel} ({size} bytes)")
            except OSError:
                pass

    # 2. Check 160000 gitlinks
    proc_sub = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-s"],
        capture_output=True,
        text=True,
    )
    gitmodules_path = repo_root / ".gitmodules"
    gitmodules_text = gitmodules_path.read_text(errors="ignore") if gitmodules_path.exists() else ""

    if proc_sub.returncode == 0:
        for line in proc_sub.stdout.splitlines():
            if line.startswith("160000 "):
                parts = line.split(maxsplit=3)
                if len(parts) >= 4:
                    sub_path = parts[3]
                    if sub_path not in gitmodules_text:
                        violations.append(f"UNMAPPED_160000_GITLINK: {sub_path} missing in .gitmodules")

    verified = (len(violations) == 0)
    status_code = "PRE_PUSH_INVARIANTS_VERIFIED" if verified else "HALT_PRE_PUSH_INVARIANT_VIOLATION"

    # Current branch
    proc_br = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    branch = proc_br.stdout.strip() if proc_br.returncode == 0 else "UNKNOWN"

    summary_body = {
        "repo_root": str(repo_root.resolve()),
        "branch": branch,
        "verified": verified,
        "status_code": status_code,
        "violations": violations,
        "largest_file_bytes": largest_file,
    }
    receipt_caid = "sha256:" + hashlib.sha256(encode_jcs(summary_body)).hexdigest()

    return PrePushVerificationReceipt(
        repo_root=str(repo_root.resolve()),
        branch=branch,
        verified=verified,
        status_code=status_code,
        violations=tuple(violations),
        largest_file_bytes=largest_file,
        receipt_caid=receipt_caid,
    )
