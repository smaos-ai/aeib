#!/usr/bin/env python3
"""
src/adapters/harness2_ring0_lock.py
================================================================================
Immutable "Ring-0" Harness Lock for Harness² & Terminal-RSI (AT71).

Inspired by Google Cloud Research Harness² (Propose-Probe-Compose optimization)
and Tencent Terminal-RSI (Recursive Self-Rewrite / RSR).

Evaluates under the stated model:
  1. Partitions the agent harness into:
     - Ring-3 Mutable Optimization Files: system_prompt, memory/EXPERIENCE.md,
       tool_guidance, subagents, skills, scripts.
     - Ring-0 Immutable Enforcement Files: guardrails, plugins/aeib_middleware, contracts.
  2. Ensures that recursive self-improving optimizers cannot rewrite or relax their
     own safety, financial, or wire-level execution invariants to artificially boost
     benchmark scores.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Optional, Set, Tuple


def sha256_prefixed(data: bytes) -> str:
    """Computes a SHA-256 digest with standard prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class Harness2Ring0Enforcer:
    """
    Evaluates proposed harness candidate modifications from recursive self-improving agents,
    strictly enforcing Ring-0 immutability.
    """

    RING_0_IMMUTABLE_COMPONENTS: Set[str] = {
        "guardrails",
        "plugins_aeib_middleware",
        "contracts",
    }

    RING_3_MUTABLE_COMPONENTS: Set[str] = {
        "system_prompt",
        "memory_experience_md",
        "tool_guidance",
        "subagents",
        "skills",
        "scripts",
    }

    def __init__(self, ring0_baseline_hashes: Dict[str, str]) -> None:
        self.ring0_baseline_hashes = dict(ring0_baseline_hashes)

    def validate_proposed_harness_candidate(
        self, candidate_files: Dict[str, bytes]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates a candidate harness package.
        Returns (is_valid, error_code).
        """
        for comp, expected_hash in self.ring0_baseline_hashes.items():
            if comp not in candidate_files:
                return False, f"HALT_RING0_COMPONENT_DELETED:{comp}"

            actual_hash = sha256_prefixed(candidate_files[comp])
            if actual_hash != expected_hash:
                return False, f"HALT_HARNESS2_RING0_RELAXATION_ATTEMPT:{comp}"

        return True, None
