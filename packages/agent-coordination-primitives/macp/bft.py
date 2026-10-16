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
macp.bft
================================================================================
Gap 4: Zero-LLM Byzantine Fault Tolerant (BFT) Provenance Validator.
Validates subagent handback findings against disk state without secondary LLM invocations.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List


class SemanticValidationError(ValueError):
    """Raised when an agent report contains fabricated or unverifiable citations."""
    pass


class BFTProvenanceValidator:
    """Verifies that cited sources and digests match physical files on disk."""

    @staticmethod
    def verify_finding(
        repo_root: Path,
        finding: Dict[str, Any],
        line_window: int = 15,
    ) -> None:
        claim = str(finding.get("claim", "")).strip()
        source = str(finding.get("source", "")).strip()
        if not claim or not source:
            raise SemanticValidationError("Finding missing non-empty 'claim' or 'source'")

        # Web URLs are permitted if explicitly formatted as HTTP/HTTPS
        if source.startswith(("http://", "https://")):
            return

        parts = source.split(":")
        rel_path = parts[0]
        target_path = (repo_root / rel_path).resolve()

        if not target_path.exists() or not target_path.is_file():
            raise SemanticValidationError(f"Fabricated source file does not exist: {rel_path}")

        lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(parts) > 1 and parts[1].isdigit():
            line_no = int(parts[1])
            if line_no < 1 or line_no > max(len(lines), 1):
                raise SemanticValidationError(
                    f"Line number {line_no} out of range for {rel_path} (total lines: {len(lines)})"
                )
            start = max(0, line_no - 1 - line_window)
            end = min(len(lines), line_no + line_window)
            window_text = "\n".join(lines[start:end]).lower()
        else:
            window_text = "\n".join(lines).lower()

        # Deterministic SHA-256 verification
        expected_sha = finding.get("artifact_sha256")
        if expected_sha:
            actual_sha = f"sha256:{hashlib.sha256(target_path.read_bytes()).hexdigest()}"
            if actual_sha != expected_sha:
                raise SemanticValidationError(
                    f"SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"
                )

        anchor = finding.get("anchor_token") or finding.get("anchor_Token")
        if anchor and str(anchor).lower() not in window_text:
            raise SemanticValidationError(
                f"Anchor token '{anchor}' not found near {source}"
            )

    @classmethod
    def validate_handback(cls, repo_root: Path, handback: Dict[str, Any]) -> bool:
        findings: List[Dict[str, Any]] = handback.get("verified_findings", [])
        for finding in findings:
            cls.verify_finding(repo_root, finding)
        return True
