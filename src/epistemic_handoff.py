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
src/epistemic_handoff.py
================================================================================
Epistemic Handoff & Cross-Model Taint Gate.

Evaluated under the stated model:
Defends against Cross-Model Prompt Injection, Semantic Entropy Decay,
and Taint Laundering in Mixture-of-Models (MoM) workflows:

1. Neurosymbolic Typed Boundaries:
   Models exchange RFC 8785 canonical artifacts containing typed AST diffs,
   bounded structured keys, and explicit epistemic unknowns, rather than
   unstructured natural-language prompt dumps.

2. Taint Monotonicity (Join-Semilattice):
   If an upstream model touches unvetted external data or executable payloads,
   the artifact taint level escalates immutably and cannot be laundered
   or downgraded by any downstream model.

3. Epistemic Ledger (Known Unknowns):
   Any tainted handoff must carry non-empty explicit unverified assumptions
   (`known_unknowns`) that downstream verifiers must falsify.

4. Cryptographic Parent Chaining:
   Every child artifact binds its parent artifact hash via SHA-256 over
   RFC 8785 canonical JCS bytes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs


class ModelTier(str, Enum):
    FLASH_REFLEX = "FLASH_REFLEX"
    ARGON_LIBRARIAN = "ARGON_LIBRARIAN"
    OPUS_SURGEON = "OPUS_SURGEON"


class TaintLevel(str, Enum):
    CLEAN_INTERNAL = "CLEAN_INTERNAL"
    TAINTED_EXTERNAL_READ = "TAINTED_EXTERNAL_READ"
    TAINTED_EXECUTABLE = "TAINTED_EXECUTABLE"


class HaltHandoffViolationError(Exception):
    """Raised when an artifact violates epistemic, taint, or cryptographic bounds."""


@dataclass(frozen=True)
class HandoffArtifact:
    """
    RFC 8785 canonical typed envelope passed between model tiers.
    Rejects raw natural-language prompt injections.
    """

    source_tier: ModelTier
    target_tier: ModelTier
    task_id: str
    taint_level: TaintLevel
    ast_diffs: Tuple[str, ...]
    structured_findings: Mapping[str, Any]
    known_unknowns: Tuple[str, ...]
    parent_artifact_hash: Optional[str] = None
    artifact_hash: str = field(init=False)

    def __post_init__(self) -> None:
        payload: Dict[str, Any] = {
            "ast_diffs": list(self.ast_diffs),
            "known_unknowns": list(self.known_unknowns),
            "parent_artifact_hash": self.parent_artifact_hash,
            "source_tier": self.source_tier.value,
            "structured_findings": self.structured_findings,
            "taint_level": self.taint_level.value,
            "target_tier": self.target_tier.value,
            "task_id": self.task_id,
        }
        canonical_bytes = encode_jcs(payload)
        digest = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        object.__setattr__(self, "artifact_hash", digest)


class CrossModelTaintGate:
    """
    Validates cross-model handoffs and enforces taint monotonicity.
    """

    TAINT_ORDER: Mapping[TaintLevel, int] = {
        TaintLevel.CLEAN_INTERNAL: 0,
        TaintLevel.TAINTED_EXTERNAL_READ: 1,
        TaintLevel.TAINTED_EXECUTABLE: 2,
    }

    MAX_RAW_STRING_LEN: int = 200

    @classmethod
    def validate_handoff(
        cls,
        artifact: HandoffArtifact,
        parent_artifact: Optional[HandoffArtifact] = None,
    ) -> None:
        # 1. Cryptographic chain of custody
        if parent_artifact is not None:
            if artifact.parent_artifact_hash != parent_artifact.artifact_hash:
                raise HaltHandoffViolationError(
                    f"HALT_CHAIN_OF_CUSTODY_BROKEN: expected parent {parent_artifact.artifact_hash}, "
                    f"got {artifact.parent_artifact_hash}"
                )

            # 2. Monotonic taint escalation (cannot downgrade taint)
            parent_rank = cls.TAINT_ORDER[parent_artifact.taint_level]
            current_rank = cls.TAINT_ORDER[artifact.taint_level]
            if current_rank < parent_rank:
                raise HaltHandoffViolationError(
                    f"HALT_TAINT_MONOTONICITY_VIOLATION: cannot downgrade taint from "
                    f"{parent_artifact.taint_level.value} to {artifact.taint_level.value}"
                )

        # 3. Epistemic ledger obligation: tainted handoffs must name known unknowns
        if artifact.taint_level != TaintLevel.CLEAN_INTERNAL and not artifact.known_unknowns:
            raise HaltHandoffViolationError(
                "HALT_EPISTEMIC_UNKNOWN_EMPTY: tainted artifacts must explicitly declare known_unknowns"
            )

        # 4. Neurosymbolic boundary check: no raw text dumps or RAG dumps inside structured findings
        cls._scan_nested_payload(artifact.structured_findings)

    @classmethod
    def _scan_nested_payload(cls, val: Any) -> None:
        if isinstance(val, str):
            if len(val) > cls.MAX_RAW_STRING_LEN:
                raise HaltHandoffViolationError(
                    f"HALT_NEUROSYMBOLIC_VIOLATION: raw text field exceeds maximum length "
                    f"{cls.MAX_RAW_STRING_LEN} (observed {len(val)} chars)"
                )
        elif isinstance(val, Mapping):
            for k, v in val.items():
                cls._scan_nested_payload(v)
        elif isinstance(val, (list, tuple, set, frozenset)):
            for item in val:
                cls._scan_nested_payload(item)
