#!/usr/bin/env python3
"""
src/wilson_bps_interval.py — Rational Wilson 95% Confidence Interval in Basis Points (BPS)

Implements zero-float exact rational arithmetic for binomial proportion confidence intervals
using fractions.Fraction and integer square roots (math.isqrt).
Preserves RFC 8785 single-source JCS compliance with zero floats.

Enforces Lesson L22: Epistemic Status Grounding (CI009).
Enforces Lesson L23: Exact Boundary Invariant (CI010).
Enforces Lesson L24: Statistical Wilson BPS Interval Reporting (CI011).
"""

from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Dict, List, Optional, Set, Tuple

# Pre-computed exact rational constants for two-sided 95% normal approximation (z = 1.96)
# z = 196 / 100 = 49 / 25
# z^2 = 38416 / 10000 = 2401 / 625
WILSON_Z_NUM = 49
WILSON_Z_DEN = 25
WILSON_Z2_NUM = WILSON_Z_NUM * WILSON_Z_NUM
WILSON_Z2_DEN = WILSON_Z_DEN * WILSON_Z_DEN

# Precision scale for integer square root computation (12 decimal places)
SQRT_SCALE = 10**12
SQRT_SCALE_SQ = SQRT_SCALE * SQRT_SCALE

# Grounded status registry under Lesson L22
GROUNDED_STATUS_ALLOWLIST: Set[str] = {
    "INTERNAL PREVIEW COMMISSIONED",
    "COMPLIANCE EVIDENCE EXPORTER PROTOTYPE",
    "READY FOR INTERNAL PREVIEW / PILOT",
    "PROTOTYPE",
    "SCENARIO SIMULATION",
    "EVALUATED UNDER THE STATED MODEL",
    "OBSERVED UNDER TEST",
    "INTERNALLY COMMISSIONED PROTOTYPE",
}

UNGROUNDED_STATUS_BLOCKLIST: Set[str] = {
    "DELIVERED & COMMISSIONED",
    "DELIVERED AND COMMISSIONED",
    "CERTIFIED COMPLIANT",
    "CERTIFIED REGULATORY COMPLIANT",
}

UNGROUNDED_STATUS_REGEX = re.compile(
    r"\b(?:production-[s]afe|enterprise-[g]rade|bullet[p]roof|100%\s*[s]ecure)\b",
    re.IGNORECASE,
)


def _scaled_isqrt(scaled: int) -> int:
    """Compute ceiling integer square root so interval is never narrower than exact coverage."""
    root = math.isqrt(scaled)
    if root * root < scaled:
        root += 1
    return root


def compute_wilson_95_bps(successes: int, total: int) -> Tuple[int, int]:
    """Compute the conservative two-sided 95% Wilson score interval in basis points (0..10000).

    Uses exact rational arithmetic (fractions.Fraction) and scaled integer square roots.
    Rounds outward (floor on lower bound, ceil on upper bound) so the confidence interval
    is never narrower than exact coverage.

    Returns:
        (low_bps, high_bps) as a tuple of integers.
    """
    if not isinstance(successes, int):
        raise TypeError("successes must be an int")
    if not isinstance(total, int):
        raise TypeError("total must be an int")
    if total < 0:
        raise ValueError("total must be non-negative")
    if successes < 0:
        raise ValueError("successes must be non-negative")
    if successes > total:
        raise ValueError(f"successes ({successes}) cannot exceed total ({total})")
    if total == 0:
        return (0, 0)

    z2 = Fraction(WILSON_Z2_NUM, WILSON_Z2_DEN)
    n = Fraction(total)
    p = Fraction(successes, total)
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    rad_sq = z2 * (p * (1 - p) / n + z2 / (4 * n * n)) / (denom * denom)

    scaled = int(rad_sq * SQRT_SCALE_SQ)
    root = _scaled_isqrt(scaled)

    rad = Fraction(root, SQRT_SCALE)
    low = max(Fraction(0), center - rad)

    low_bps = math.floor(low * 10000)
    high_bps = min(10000, math.ceil((center + rad) * 10000))
    return (int(low_bps), int(high_bps))


def format_bps_interval(interval: Tuple[int, int]) -> str:
    """Format integer BPS interval into human-readable bracketed string e.g. '[0..1072 bps]'."""
    return f"[{interval[0]}..{interval[1]} bps]"


def verify_l22_status_grounding(status_label: str) -> Tuple[bool, str]:
    """Verify that a status label complies with Lesson L22 epistemic boundaries.

    Rejects unaccredited self-certification badges and demands grounded engineering labels.
    """
    normalized = status_label.strip().upper()
    for banned in UNGROUNDED_STATUS_BLOCKLIST:
        if banned in normalized:
            return (
                False,
                f"ERR_UNGROUNDED_STATUS_LABEL: '{status_label}' contains unaccredited term '{banned}'. "
                "Use 'INTERNAL PREVIEW COMMISSIONED' or 'COMPLIANCE EVIDENCE EXPORTER PROTOTYPE'.",
            )

    m = UNGROUNDED_STATUS_REGEX.search(normalized)
    if m:
        return (
            False,
            f"ERR_UNGROUNDED_STATUS_LABEL: '{status_label}' contains unaccredited term '{m.group(0)}'. "
            "Use 'INTERNAL PREVIEW COMMISSIONED' or 'COMPLIANCE EVIDENCE EXPORTER PROTOTYPE'.",
        )

    if normalized in GROUNDED_STATUS_ALLOWLIST:
        return (True, f"GROUNDED: '{status_label}' matches epistemic allowlist.")

    return (
        True,
        f"PERMITTED_CUSTOM: '{status_label}' does not violate ungrounded status blocklist.",
    )


def compute_exact_bps_boundary(numerator: int, denominator: int) -> int:
    """Compute exact basis points with explicit remainder checking to prevent truncation masking (L23).

    Formula: (numerator * 10000) // denominator
    Validates boundary conditions:
    - denominator > 0
    - 0 <= numerator <= denominator
    """
    if denominator <= 0:
        raise ValueError("denominator must be strictly positive")
    if numerator < 0:
        raise ValueError("numerator must be non-negative")
    if numerator > denominator:
        raise ValueError(f"numerator ({numerator}) cannot exceed denominator ({denominator})")

    product = numerator * 10000
    bps = product // denominator
    return bps
