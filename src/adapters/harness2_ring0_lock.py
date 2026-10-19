#!/usr/bin/env python3
"""
src/adapters/harness2_ring0_lock.py
================================================================================
Harness Policy Protection Enforcer (AT71).

EPISTEMIC BOUNDARY & TERMINOLOGY NOTICE:
In ordinary user-space Linux systems, file-level policy locks are user-space
or kernel-assisted controls (read-only mounts, immutable file attributes,
LSM policies, seccomp profiles, and separate service identities)—not x86 Ring 0.
Calling user-space hash checks "Ring 0" is misleading. This module implements
an OS-specific policy protection enforcer that validates candidate harness
modifications against pinned policy digests before activation.

Policy Protection Configuration Model:
```yaml
policy_protection:
  enforcement_layer: OS-specific
  options:
    - read_only_mount
    - immutable_file_attribute
    - LSM_policy
    - seccomp_profile
    - separate_service_identity
  failure_behavior: deny_and_halt
```

Anti-Tamper Mitigations:
- Remounting policy path: Enforced via mount namespaces without CAP_SYS_ADMIN.
- Editing copied policy: Evaluator strictly hashes pinned canonical paths.
- Replacing verifier binary: Read-only container rootfs or chattr +i.
- Spoofing policy loader: Mutual cryptographic verification of policy manifests.
- Restarting into permissive mode: Boot continuity check halts on missing/altered state.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Optional, Set, Tuple


def sha256_prefixed(data: bytes) -> str:
    """Computes a SHA-256 digest with standard prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class HarnessPolicyProtectionEnforcer:
    """
    Evaluates proposed harness candidate modifications from recursive self-improving agents,
    enforcing policy protection immutability.
    """

    POLICY_IMMUTABLE_COMPONENTS: Set[str] = {
        "guardrails",
        "plugins_aeib_middleware",
        "contracts",
    }
    # Backward compatibility alias
    RING_0_IMMUTABLE_COMPONENTS = POLICY_IMMUTABLE_COMPONENTS

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


# Backward compatibility alias
Harness2Ring0Enforcer = HarnessPolicyProtectionEnforcer
