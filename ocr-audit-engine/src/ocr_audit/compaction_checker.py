#!/usr/bin/env python3
"""Stage 2b: Context Compaction Safety Gate (compaction_checker.py)

Deterministic auditor evaluating fast-compaction traces (keep -> truncate -> drop).
Calculates:
  - Delta_cvr (Constraint Verification Rate): percentage of security/compliance
    constraints preserved after semantic garbage collection.
  - Delta_poi (Preserved Order of Invariants): verifies temporal sequencing
    of authorization checks vs mutating actions is invariant.

Fail-closed invariant:
  If Delta_cvr < 100.0%, compaction is REJECTED (potential safety constraint decay).
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple


SECURITY_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(DORA|ISO\s*42001|GDPR|HIPAA|PCI-DSS)\b", re.IGNORECASE),
    re.compile(r"\b(UNKNOWN|NEVER\s*CONFIRMED|FAIL_CLOSED|HALT)\b", re.IGNORECASE),
    re.compile(r"\b(require|enforce|must|prohibit|deny|allow)\b", re.IGNORECASE),
    re.compile(r"\b(authorization|signature|ed25519|scitt|merkle)\b", re.IGNORECASE),
    re.compile(r"\b(rate_limit|max_amount|daily_limit|idempotency)\b", re.IGNORECASE),
]


@dataclass
class CompactionMetrics:
    baseline_constraint_count: int
    compacted_constraint_count: int
    delta_cvr: float  # Constraint Verification Rate (0.0% to 100.0%)
    delta_poi: float  # Preserved Order of Invariants (0.0% to 100.0%)
    dropped_constraints: List[str] = field(default_factory=list)
    verdict: str = "PASS"

    def is_safe(self) -> bool:
        return self.delta_cvr >= 100.0 and self.delta_poi >= 100.0


class CompactionSafetyGate:
    """Evaluates whether context garbage collection pruned critical constraints."""

    @staticmethod
    def extract_constraints(text: str) -> List[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        constraints: List[str] = []
        for line in lines:
            if any(pattern.search(line) for pattern in SECURITY_PATTERNS):
                constraints.append(line)
        return constraints

    @classmethod
    def evaluate(cls, baseline_context: str, compacted_context: str) -> CompactionMetrics:
        baseline = cls.extract_constraints(baseline_context)
        compacted = cls.extract_constraints(compacted_context)

        base_set = set(baseline)
        compact_set = set(compacted)

        dropped = [c for c in baseline if c not in compact_set]

        if not base_set:
            cvr = 100.0
        else:
            retained = len(base_set - set(dropped))
            cvr = (retained / len(base_set)) * 100.0

        # POI check: preserved sequence order
        poi = 100.0
        if compacted and len(compacted) > 1:
            indices = []
            for c in compacted:
                if c in baseline:
                    indices.append(baseline.index(c))
            # verify monotonic ordering
            if indices and indices != sorted(indices):
                poi = 0.0

        verdict = "PASS" if (cvr >= 100.0 and poi >= 100.0) else "FAIL_CONSTRAINT_DECAY"

        return CompactionMetrics(
            baseline_constraint_count=len(baseline),
            compacted_constraint_count=len(compacted),
            delta_cvr=round(cvr, 2),
            delta_poi=round(poi, 2),
            dropped_constraints=dropped,
            verdict=verdict,
        )
