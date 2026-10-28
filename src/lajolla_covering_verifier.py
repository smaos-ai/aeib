"""Deterministic La Jolla Covering-Design Verifier.

Verifies whether a proposed set of blocks forms a valid (v, k, t) covering
design where every t-subset of a v-element set {0, ..., v - 1} is contained
in at least one block of size k.

Fixes the defects identified in the draft blueprint:
  1. Uses `src.jcs_canonicalizer.encode_jcs` exclusively (single-source JCS).
  2. Reports the actual computed Schoenheim bound in
     `HALT_BLOCK_COUNT_BELOW_SCHONHEIM_BOUND:{block_count}<{lower_bound}`
     instead of a hardcoded `<10`.
  3. Replaces the dead `if spec.v > 32 and spec.t >= 4: pass` branch with a
     real fail-closed `max_t_subsets` budget check
     (`HALT_COMBINATORIAL_BUDGET_EXCEEDED`).
  4. Normalizes block order and point order inside each block before computing
     `receipt_caid`, so isomorphic block orderings produce identical receipts.
"""
from __future__ import annotations

import hashlib
import itertools
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Dict[str, Any]) -> str:
    """Compute an RFC 8785 JCS SHA-256 content-addressable identifier."""
    return "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()


def _is_strict_int(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool)


def compute_schonheim_bound(v: int, k: int, t: int) -> int:
    """Compute the Schoenheim lower bound L(v, k, t) = ceil(v/k * L(v-1, k-1, t-1))."""
    if not (_is_strict_int(v) and _is_strict_int(k) and _is_strict_int(t)):
        raise ValueError("HALT_INVALID_DESIGN_PARAMETERS")
    if not (0 < t <= k <= v):
        raise ValueError("HALT_INVALID_DESIGN_PARAMETERS")
    bound = 1
    for i in range(t - 1, -1, -1):
        v_i = v - i
        k_i = k - i
        bound = (v_i * bound + k_i - 1) // k_i
    return bound


@dataclass(frozen=True)
class CoveringDesignSpec:
    v: int
    k: int
    t: int
    blocks: Tuple[Tuple[int, ...], ...]


@dataclass(frozen=True)
class CoveringVerificationReport:
    is_valid: bool
    v: int
    k: int
    t: int
    block_count: int
    schonheim_lower_bound: int
    total_t_subsets: int
    covered_t_subsets: int
    reason_code: str
    receipt_caid: str

    @property
    def is_valid_covering(self) -> bool:
        return self.is_valid

    @property
    def halt_reason(self) -> str:
        return self.reason_code


class LajollaCoveringVerifier:
    """Exhaustive mathematical verifier for (v, k, t) covering designs."""

    DEFAULT_MAX_T_SUBSETS = 250_000
    compute_schonheim_bound = staticmethod(compute_schonheim_bound)

    @classmethod
    def verify_design(
        cls,
        spec: CoveringDesignSpec,
        max_t_subsets: int = DEFAULT_MAX_T_SUBSETS,
    ) -> CoveringVerificationReport:
        """Verify structural invariants, Schoenheim lower bound, and exhaustive t-subset coverage."""
        if not (_is_strict_int(spec.v) and _is_strict_int(spec.k) and _is_strict_int(spec.t)):
            return cls._build_report(spec, False, 0, 0, 0, "HALT_INVALID_DESIGN_PARAMETERS", [])
        if not (0 < spec.t <= spec.k <= spec.v):
            return cls._build_report(spec, False, 0, 0, 0, "HALT_INVALID_DESIGN_PARAMETERS", [])

        lower_bound = compute_schonheim_bound(spec.v, spec.k, spec.t)
        total_t = math.comb(spec.v, spec.t)

        if total_t > max_t_subsets:
            return cls._build_report(
                spec,
                False,
                lower_bound,
                total_t,
                0,
                f"HALT_COMBINATORIAL_BUDGET_EXCEEDED:{total_t}>{max_t_subsets}",
                [],
            )

        normalized_blocks: List[Tuple[int, ...]] = []
        seen_blocks: Set[Tuple[int, ...]] = set()
        for idx, block in enumerate(spec.blocks):
            if len(block) != spec.k:
                return cls._build_report(
                    spec,
                    False,
                    lower_bound,
                    total_t,
                    0,
                    f"HALT_INVALID_BLOCK_CARDINALITY:block_{idx}",
                    [],
                )
            for p in block:
                if not _is_strict_int(p) or p < 0 or p >= spec.v:
                    return cls._build_report(
                        spec,
                        False,
                        lower_bound,
                        total_t,
                        0,
                        f"HALT_POINT_OUT_OF_BOUNDS:block_{idx}",
                        [],
                    )
            if len(set(block)) != spec.k:
                return cls._build_report(
                    spec,
                    False,
                    lower_bound,
                    total_t,
                    0,
                    f"HALT_DUPLICATE_POINTS_IN_BLOCK:block_{idx}",
                    [],
                )
            norm_blk = tuple(sorted(block))
            if norm_blk in seen_blocks:
                return cls._build_report(
                    spec,
                    False,
                    lower_bound,
                    total_t,
                    0,
                    f"HALT_DUPLICATE_BLOCK:block_{idx}",
                    [],
                )
            seen_blocks.add(norm_blk)
            normalized_blocks.append(norm_blk)

        canonical_blocks = [list(b) for b in sorted(normalized_blocks)]

        if len(spec.blocks) < lower_bound:
            return cls._build_report(
                spec,
                False,
                lower_bound,
                total_t,
                0,
                f"HALT_BLOCK_COUNT_BELOW_SCHONHEIM_BOUND:{len(spec.blocks)}<{lower_bound}",
                canonical_blocks,
            )

        covered_subsets: Set[Tuple[int, ...]] = set()
        for norm_blk in normalized_blocks:
            for sub in itertools.combinations(norm_blk, spec.t):
                covered_subsets.add(sub)

        covered_count = len(covered_subsets)
        if covered_count < total_t:
            first_uncovered: Tuple[int, ...] = ()
            for t_sub in itertools.combinations(range(spec.v), spec.t):
                if t_sub not in covered_subsets:
                    first_uncovered = t_sub
                    break
            return cls._build_report(
                spec,
                False,
                lower_bound,
                total_t,
                covered_count,
                f"HALT_UNCOVERED_T_SUBSET:{first_uncovered}",
                canonical_blocks,
            )

        return cls._build_report(
            spec,
            True,
            lower_bound,
            total_t,
            covered_count,
            "OK_COVERING_DESIGN_VERIFIED",
            canonical_blocks,
        )

    @staticmethod
    def _build_report(
        spec: CoveringDesignSpec,
        is_valid: bool,
        lower_bound: int,
        total_t: int,
        covered_t: int,
        reason: str,
        canonical_blocks: List[List[int]],
    ) -> CoveringVerificationReport:
        caid = sha256_jcs_caid(
            {
                "block_count": len(spec.blocks),
                "canonical_blocks": canonical_blocks,
                "covered_t_subsets": covered_t,
                "is_valid": is_valid,
                "k": spec.k if _is_strict_int(spec.k) else -1,
                "reason_code": reason,
                "schonheim_lower_bound": lower_bound,
                "t": spec.t if _is_strict_int(spec.t) else -1,
                "total_t_subsets": total_t,
                "v": spec.v if _is_strict_int(spec.v) else -1,
            }
        )
        return CoveringVerificationReport(
            is_valid=is_valid,
            v=spec.v,
            k=spec.k,
            t=spec.t,
            block_count=len(spec.blocks),
            schonheim_lower_bound=lower_bound,
            total_t_subsets=total_t,
            covered_t_subsets=covered_t,
            reason_code=reason,
            receipt_caid=caid,
        )
