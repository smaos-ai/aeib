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
ios_steward_guard.py — iOS Invariant Core Guard (Wave 8 prototype).

Evaluated under the stated model:
- Classifies iOS security authorities (*.entitlements, Info.plist,
  PrivacyInfo.xcprivacy, anything inside *.xcodeproj / *.xcworkspace, and the
  Xcode 27.2 JSON project format *.xcproj) by exact
  basename / extension / path segment, not by substring.
- A change to an authority requires an Ed25519 approval from a pinned approver
  key that signs the exact proposal CAID (path + diff digest). A bare token
  string is NOT accepted (that would be a trivial verifier).
- Scans the ADDED diff lines (joined, so a plist key and its <true/> on the
  next added line are matched together) for private-key literals, an ATS
  NSAllowsArbitraryLoads=true opt-out, and hardcoded secrets. Removing such a
  line is allowed.

Limitations (stated honestly): the scanner is lexical. It does not detect
secrets that are split, encoded, or loaded at runtime, and it does not parse
plist/xcconfig semantics. The guard only sees the diff it is given; the caller
(harness) must produce that diff from the real worktree.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs

APPROVAL_DOMAIN = "aeib.ios_steward.approval.v1"


@dataclass(frozen=True)
class IOSProposal:
    target_file_path: str
    proposed_diff: str
    approval_signature_hex: Optional[str] = None


class IOSStewardGuard:
    """Guards invariant iOS assets against unapproved modification."""

    IMMUTABLE_FILE_NAMES: FrozenSet[str] = frozenset(
        {"Info.plist", "PrivacyInfo.xcprivacy", "project.pbxproj"}
    )
    IMMUTABLE_FILE_EXTENSIONS: Tuple[str, ...] = (".entitlements", ".xcprivacy")
    IMMUTABLE_DIR_EXTENSIONS: Tuple[str, ...] = (".xcodeproj", ".xcworkspace", ".xcproj")

    _FORBIDDEN_ADDED_LINE_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
        (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"), "PRIVATE_KEY_LITERAL"),
        (
            re.compile(
                r"""(?:["']?NSAllowsArbitraryLoads["']?\s*[:=]\s*(?:true|YES|1)\b"""
                r"""|<key>\s*NSAllowsArbitraryLoads\s*</key>\s*<true\s*/>)"""
            ),
            "NSAllowsArbitraryLoads_ATS_BYPASS",
        ),
        (
            re.compile(
                r"""(?:api_secret|app_secret|client_secret|access_token)\s*[:=]\s*["'][^"']{8,}["']"""
            ),
            "HARDCODED_API_SECRET",
        ),
    )

    def __init__(self, trusted_approver_public_key_hex: Optional[str] = None) -> None:
        self._approver_key: Optional[Ed25519PublicKey] = None
        if trusted_approver_public_key_hex is not None:
            self._approver_key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(trusted_approver_public_key_hex)
            )

    # ------------------------------------------------------------------ paths
    @staticmethod
    def canonicalize_path(target_file_path: Any) -> Tuple[Optional[str], str]:
        if not isinstance(target_file_path, str) or not target_file_path.strip():
            return None, "HALT_INVALID_EMPTY_PATH"
        if "\x00" in target_file_path or "\\" in target_file_path:
            return None, "HALT_NON_POSIX_OR_NUL_PATH"
        normed = posixpath.normpath(target_file_path)
        if normed.startswith("/") or normed == ".." or normed.startswith("../"):
            return None, f"HALT_PATH_TRAVERSAL_IN_TARGET:{normed}"
        return normed, ""

    @classmethod
    def is_immutable_ios_authority(cls, normed_path: str) -> bool:
        basename = posixpath.basename(normed_path)
        if basename in cls.IMMUTABLE_FILE_NAMES:
            return True
        if basename.endswith(cls.IMMUTABLE_FILE_EXTENSIONS):
            return True
        return any(seg.endswith(cls.IMMUTABLE_DIR_EXTENSIONS) for seg in normed_path.split("/"))

    # ------------------------------------------------------------------- diff
    @staticmethod
    def added_lines(diff_text: str) -> Tuple[str, ...]:
        """Lines added by a unified diff. Text with no +/- markers is treated
        as wholly added (new-file content)."""
        lines = diff_text.splitlines()
        has_markers = any(
            (ln.startswith("+") and not ln.startswith("+++"))
            or (ln.startswith("-") and not ln.startswith("---"))
            for ln in lines
        )
        if not has_markers:
            return tuple(lines)
        return tuple(ln[1:] for ln in lines if ln.startswith("+") and not ln.startswith("+++"))

    # ---------------------------------------------------------------- digests
    @classmethod
    def compute_proposal_caid(cls, proposal: IOSProposal) -> str:
        normed, reason = cls.canonicalize_path(proposal.target_file_path)
        if normed is None:
            raise ValueError(reason)
        payload: Dict[str, Any] = {
            "diff_sha256": hashlib.sha256(proposal.proposed_diff.encode("utf-8")).hexdigest(),
            "is_invariant_core": cls.is_immutable_ios_authority(normed),
            "target_file_path": normed,
        }
        return f"sha256:{hashlib.sha256(encode_jcs(payload)).hexdigest()}"

    @classmethod
    def approval_message(cls, proposal_caid: str) -> bytes:
        return encode_jcs({"domain": APPROVAL_DOMAIN, "proposal_caid": proposal_caid})

    @classmethod
    def sign_approval(cls, proposal: IOSProposal, approver_key: Ed25519PrivateKey) -> str:
        """Human-approver side: sign the exact proposal CAID."""
        return approver_key.sign(cls.approval_message(cls.compute_proposal_caid(proposal))).hex()

    def _approval_valid(self, proposal: IOSProposal) -> bool:
        if self._approver_key is None or not proposal.approval_signature_hex:
            return False
        try:
            self._approver_key.verify(
                bytes.fromhex(proposal.approval_signature_hex),
                self.approval_message(self.compute_proposal_caid(proposal)),
            )
        except (InvalidSignature, ValueError):
            return False
        return True

    # ---------------------------------------------------------------- policy
    def evaluate_ios_proposal(self, proposal: IOSProposal) -> Tuple[bool, str]:
        normed, reason = self.canonicalize_path(proposal.target_file_path)
        if normed is None:
            return False, reason
        if not isinstance(proposal.proposed_diff, str):
            return False, "HALT_DIFF_NOT_TEXT"

        added_text = "\n".join(self.added_lines(proposal.proposed_diff))
        for pattern, label in self._FORBIDDEN_ADDED_LINE_PATTERNS:
            if pattern.search(added_text):
                return False, f"HALT_SECURITY_SENSITIVE_CONSTANT_VIOLATION:{label}"

        if self.is_immutable_ios_authority(normed):
            if not self._approval_valid(proposal):
                return False, f"HALT_IOS_INVARIANT_CORE_MUTATION_FORBIDDEN:{normed}"
            return True, "OK_IOS_INVARIANT_CORE_CHANGE_APPROVED"

        return True, "OK_IOS_REFLECTIVE_SHELL_AUTHORIZED"
