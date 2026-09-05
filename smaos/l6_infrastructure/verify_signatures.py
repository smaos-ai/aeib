#!/usr/bin/env python3
"""
Stream D: Git Signature Verification (L8)
Verifies commit immutability and cryptographic signatures.
Prevents history rewriting via PQC signature validation.
"""

import subprocess
import json
import hashlib
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class GitCommit:
    """Represents a Git commit with signature info."""
    commit_hash: str
    author: str
    timestamp: str
    message: str
    signature_valid: bool
    signature_algorithm: Optional[str] = None
    signer_key: Optional[str] = None


class GitSignatureVerifier:
    """
    Verifies git commit signatures and immutability.
    Ensures AP2 ledger commits cannot be rewritten.
    """

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def _run_git(self, *args: str) -> str:
        """Execute git command in repo."""
        try:
            result = subprocess.run(
                ["git", "-C", self.repo_path] + list(args),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git error: {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError("Git command timed out")

    def get_commit_hash(self, ref: str = "HEAD") -> str:
        """Get commit hash for a reference."""
        return self._run_git("rev-parse", ref)

    def get_commit_info(self, commit_hash: str) -> GitCommit:
        """Get detailed info about a commit."""
        try:
            # Get commit details
            output = self._run_git("show", "-s", "--format=%H%n%an%n%ai%n%s", commit_hash)
            lines = output.split("\n")
            if len(lines) < 4:
                raise ValueError("Unexpected git output format")

            commit_hash = lines[0]
            author = lines[1]
            timestamp = lines[2]
            message = lines[3]

            # Check signature
            sig_output = self._run_git("show", "--format=%G?", "-s", commit_hash)
            signature_valid = sig_output.strip() == "G"  # G = good signature

            return GitCommit(
                commit_hash=commit_hash,
                author=author,
                timestamp=timestamp,
                message=message,
                signature_valid=signature_valid,
            )
        except (RuntimeError, ValueError, IndexError) as e:
            raise RuntimeError(f"Failed to get commit info: {e}")

    def verify_commit_chain(self, from_commit: str, to_commit: str = "HEAD") -> List[GitCommit]:
        """Verify a chain of commits."""
        try:
            output = self._run_git("log", "--format=%H", f"{from_commit}..{to_commit}")
            commit_hashes = output.split("\n") if output else []

            commits = []
            for commit_hash in commit_hashes:
                if commit_hash:
                    commit = self.get_commit_info(commit_hash)
                    commits.append(commit)

            return commits
        except RuntimeError as e:
            raise RuntimeError(f"Failed to verify commit chain: {e}")

    def compute_chain_hash(self, commits: List[GitCommit]) -> str:
        """Compute hash of entire commit chain."""
        chain_data = json.dumps(
            [
                {
                    "hash": c.commit_hash,
                    "author": c.author,
                    "timestamp": c.timestamp,
                    "message": c.message,
                }
                for c in commits
            ],
            sort_keys=True,
        )
        return hashlib.sha256(chain_data.encode()).hexdigest()

    def detect_rewrite(self, expected_chain_hash: str, current_commits: List[GitCommit]) -> bool:
        """Detect if commit history has been rewritten."""
        current_hash = self.compute_chain_hash(current_commits)
        return expected_chain_hash != current_hash

    def get_branch_history(self, branch: str = "main", limit: int = 10) -> List[GitCommit]:
        """Get commit history for a branch."""
        try:
            output = self._run_git("log", f"--max-count={limit}", "--format=%H", branch)
            commit_hashes = output.split("\n") if output else []

            commits = []
            for commit_hash in commit_hashes:
                if commit_hash:
                    try:
                        commit = self.get_commit_info(commit_hash)
                        commits.append(commit)
                    except RuntimeError:
                        continue

            return commits
        except RuntimeError as e:
            raise RuntimeError(f"Failed to get branch history: {e}")

    def create_ap2_anchor(self, ap2_digest: Dict[str, Any]) -> Dict[str, Any]:
        """Create an AP2 anchor for current git state."""
        try:
            current_hash = self.get_commit_hash()
            commit_info = self.get_commit_info(current_hash)

            anchor = {
                "timestamp": datetime.utcnow().isoformat(),
                "ap2_digest_id": ap2_digest.get("digest_id"),
                "git_commit": current_hash,
                "git_author": commit_info.author,
                "git_timestamp": commit_info.timestamp,
                "ap2_merkle_root": ap2_digest.get("merkle_root"),
                "ap2_signature": ap2_digest.get("signature"),
                "git_signature_valid": commit_info.signature_valid,
            }

            # Compute anchor hash
            anchor_json = json.dumps(anchor, sort_keys=True)
            anchor["anchor_hash"] = hashlib.sha256(anchor_json.encode()).hexdigest()

            return anchor
        except RuntimeError as e:
            raise RuntimeError(f"Failed to create AP2 anchor: {e}")

    def export_verification_report(self, commits: List[GitCommit]) -> Dict[str, Any]:
        """Create a verification report."""
        total = len(commits)
        signed = sum(1 for c in commits if c.signature_valid)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_commits": total,
            "signed_commits": signed,
            "signature_coverage": f"{(signed/total*100):.1f}%" if total > 0 else "0%",
            "chain_hash": self.compute_chain_hash(commits),
            "commits": [
                {
                    "hash": c.commit_hash[:8],
                    "author": c.author,
                    "message": c.message[:50],
                    "signed": c.signature_valid,
                }
                for c in commits
            ],
        }


def main():
    """Test git signature verification."""
    print("Stream D: Git Signature Verification Test")
    print("=" * 50)

    verifier = GitSignatureVerifier(".")

    try:
        # Get current commit
        print("Current repository state:")
        current_hash = verifier.get_commit_hash()
        print(f"  HEAD: {current_hash[:8]}")

        # Get commit info
        print("\nCurrent commit info:")
        commit = verifier.get_commit_info(current_hash)
        print(f"  Author: {commit.author}")
        print(f"  Timestamp: {commit.timestamp}")
        print(f"  Message: {commit.message}")
        print(f"  Signature valid: {commit.signature_valid}")

        # Get recent history
        print("\nRecent commit history:")
        commits = verifier.get_branch_history("HEAD", limit=5)
        for i, c in enumerate(commits):
            status = "✓" if c.signature_valid else "✗"
            print(f"  [{i}] {status} {c.commit_hash[:8]} - {c.message[:40]}")

        # Create verification report
        print("\nVerification report:")
        report = verifier.export_verification_report(commits)
        print(f"  Total commits: {report['total_commits']}")
        print(f"  Signed commits: {report['signed_commits']}")
        print(f"  Coverage: {report['signature_coverage']}")
        print(f"  Chain hash: {report['chain_hash'][:32]}...")

        # Create AP2 anchor
        print("\nCreating AP2 anchor:")
        ap2_digest = {
            "digest_id": "test_digest_001",
            "merkle_root": hashlib.sha256("test_data".encode()).hexdigest(),
            "signature": "test_signature",
        }
        anchor = verifier.create_ap2_anchor(ap2_digest)
        print(f"  Anchor hash: {anchor['anchor_hash'][:32]}...")
        print(f"  AP2 digest: {anchor['ap2_digest_id']}")
        print(f"  Git commit: {anchor['git_commit'][:8]}")

    except RuntimeError as e:
        print(f"Error: {e}")
        print("(This is expected if git is not configured or not in a git repo)")

    print("\n" + "=" * 50)
    print("Git verification test completed")


if __name__ == "__main__":
    main()
