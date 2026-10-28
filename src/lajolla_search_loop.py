"""La Jolla Covering-Design Search Loop (Structured Cyclic Orbits + Verifier Airlock).

Couples deterministic algebraic generator proposals (single-orbit and multi-orbit
cyclic shifts over Z_v, plus deterministic greedy completion) with the exact
`LajollaCoveringVerifier` airlock and `EpistemicBisector` prefix isolation.

Fixes the defects identified in the draft blueprint:
  1. Removes the non-existent `src.wave12_parallel_epistemic_engine` import.
  2. Replaces `float('inf')` with `Optional[int] = None` so all state remains
     strictly integer/None compatible with RFC 8785 JCS.
  3. Uses an explicit seeded `random.Random(seed)` instance instead of unseeded
     global `random.sample`.
  4. Wires `EpistemicBisector.bisect_minimal_covering_prefix` to isolate the
     exact block index where coverage completes in O(log B) verifier probes.
"""
from __future__ import annotations

import ast
import itertools
import math
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

from src.epistemic_bisector import BisectionResult, EpistemicBisector
from src.lajolla_covering_verifier import (
    CoveringDesignSpec,
    CoveringVerificationReport,
    LajollaCoveringVerifier,
    compute_schonheim_bound,
    sha256_jcs_caid,
)

ALLOWED_GENERATOR_IMPORTS = frozenset({"itertools", "math"})
FORBIDDEN_GENERATOR_CALLS = frozenset(
    {
        "__import__",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "input",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)
FORBIDDEN_VERIFIER_SYMBOLS = frozenset(
    {
        "LajollaCoveringVerifier",
        "PinnedBaseline",
        "coverdata",
        "verify_design",
    }
)
FORBIDDEN_FRAME_ATTRS = frozenset({"f_back", "f_globals", "f_locals", "gi_frame"})


@dataclass(frozen=True)
class GeneratorAstVerdict:
    is_safe: bool
    reason_code: str
    receipt_caid: str


class GeneratorHackDetectionGate:
    """AST static gate rejecting evaluation hacks in proposed generator code (arXiv:2605.15221v1)."""

    @classmethod
    def inspect_generator_code(cls, source_code: str) -> GeneratorAstVerdict:
        if not isinstance(source_code, str) or not source_code.strip():
            return cls._verdict(source_code, False, "HALT_EMPTY_GENERATOR_SOURCE")
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return cls._verdict(source_code, False, "HALT_GENERATOR_SYNTAX_ERROR")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in ALLOWED_GENERATOR_IMPORTS:
                        return cls._verdict(
                            source_code, False, f"HALT_FORBIDDEN_GENERATOR_IMPORT:{root}"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if node.level != 0 or mod not in ALLOWED_GENERATOR_IMPORTS:
                    target = mod if mod else "relative"
                    return cls._verdict(
                        source_code, False, f"HALT_FORBIDDEN_GENERATOR_IMPORT:{target}"
                    )
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                return cls._verdict(source_code, False, "HALT_GENERATOR_GLOBAL_MUTATION")
            elif isinstance(node, ast.Attribute):
                if (node.attr.startswith("__") and node.attr.endswith("__")) or (
                    node.attr in FORBIDDEN_FRAME_ATTRS
                ):
                    return cls._verdict(
                        source_code, False, f"HALT_GENERATOR_REFLECTION_ACCESS:{node.attr}"
                    )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_GENERATOR_CALLS:
                    return cls._verdict(
                        source_code, False, f"HALT_FORBIDDEN_GENERATOR_CALL:{node.func.id}"
                    )
            elif isinstance(node, ast.Name) and node.id in FORBIDDEN_VERIFIER_SYMBOLS:
                return cls._verdict(
                    source_code, False, f"HALT_VERIFIER_STATE_TAMPER_ATTEMPT:{node.id}"
                )

        return cls._verdict(source_code, True, "OK_GENERATOR_AST_CLEAN")

    @staticmethod
    def _verdict(source_code: str, is_safe: bool, reason_code: str) -> GeneratorAstVerdict:
        src_str = source_code if isinstance(source_code, str) else ""
        caid = sha256_jcs_caid(
            {
                "is_safe": is_safe,
                "reason_code": reason_code,
                "source_code": src_str,
            }
        )
        return GeneratorAstVerdict(is_safe=is_safe, reason_code=reason_code, receipt_caid=caid)


def develop_cyclic_orbits(
    v: int,
    k: int,
    base_blocks: Sequence[Sequence[int]],
) -> Tuple[Tuple[int, ...], ...]:
    """Develop one or more base blocks under the cyclic group Z_v = (Z/vZ, +)."""
    if not (isinstance(v, int) and not isinstance(v, bool) and isinstance(k, int) and not isinstance(k, bool)):
        raise ValueError("HALT_INVALID_ORBIT_PARAMETERS")
    if not (0 < k <= v) or len(base_blocks) == 0:
        raise ValueError("HALT_INVALID_ORBIT_PARAMETERS")

    seen: Set[Tuple[int, ...]] = set()
    ordered: List[Tuple[int, ...]] = []
    for base in base_blocks:
        if len(base) != k or len(set(base)) != k:
            raise ValueError("HALT_INVALID_BASE_BLOCK")
        for p in base:
            if not (isinstance(p, int) and not isinstance(p, bool)) or p < 0 or p >= v:
                raise ValueError("HALT_INVALID_BASE_BLOCK")
        for shift in range(v):
            shifted = tuple(sorted((p + shift) % v for p in base))
            if shifted not in seen:
                seen.add(shifted)
                ordered.append(shifted)
    return tuple(ordered)


class LajollaSearchOrchestrator:
    """Orchestrates algebraic candidate generation, exact verification, and prefix bisection."""

    def __init__(self, v: int, k: int, t: int, seed: int = 42) -> None:
        self.schonheim_bound = compute_schonheim_bound(v, k, t)
        if not (isinstance(seed, int) and not isinstance(seed, bool)):
            raise ValueError("HALT_INVALID_SEED")
        self.v = v
        self.k = k
        self.t = t
        self.seed = seed
        self._rng = random.Random(seed)
        self.verifier = LajollaCoveringVerifier()
        self.bisector = EpistemicBisector()
        self.best_block_count: Optional[int] = None
        self.best_design: Optional[CoveringDesignSpec] = None

    def propose_cyclic_generator(self, base_block: Sequence[int]) -> CoveringDesignSpec:
        """Develop a single base block under Z_v into a candidate CoveringDesignSpec."""
        blocks = develop_cyclic_orbits(self.v, self.k, [base_block])
        return CoveringDesignSpec(v=self.v, k=self.k, t=self.t, blocks=blocks)

    def propose_multi_orbit_generator(self, base_blocks: Sequence[Sequence[int]]) -> CoveringDesignSpec:
        """Develop multiple base blocks under Z_v into a candidate CoveringDesignSpec."""
        blocks = develop_cyclic_orbits(self.v, self.k, base_blocks)
        return CoveringDesignSpec(v=self.v, k=self.k, t=self.t, blocks=blocks)

    def evaluate_candidate(self, spec: CoveringDesignSpec) -> CoveringVerificationReport:
        """Verify a candidate spec and record it if it improves on `best_block_count`."""
        report = self.verifier.verify_design(spec)
        if report.is_valid:
            if self.best_block_count is None or report.block_count < self.best_block_count:
                self.best_block_count = report.block_count
                self.best_design = spec
        return report

    def evaluate_generator_proposal(
        self,
        source_code: str,
        base_blocks: Sequence[Sequence[int]],
    ) -> Tuple[GeneratorAstVerdict, Optional[CoveringVerificationReport]]:
        """Run Vesper AST hack detection before developing and verifying `base_blocks`."""
        verdict = GeneratorHackDetectionGate.inspect_generator_code(source_code)
        if not verdict.is_safe:
            return verdict, None
        spec = self.propose_multi_orbit_generator(base_blocks)
        return verdict, self.evaluate_candidate(spec)

    def bisect_critical_block(self, spec: CoveringDesignSpec) -> BisectionResult:
        """Isolate the minimal prefix of `spec.blocks` that achieves full t-subset coverage."""
        total_t = math.comb(self.v, self.t)
        labels = [f"block_{i}" for i in range(len(spec.blocks))]

        def is_prefix_full_cover(idx: int) -> bool:
            covered: Set[Tuple[int, ...]] = set()
            for blk in spec.blocks[: idx + 1]:
                norm_blk = tuple(sorted(blk))
                for sub in itertools.combinations(norm_blk, self.t):
                    covered.add(sub)
            return len(covered) == total_t

        return self.bisector.bisect_minimal_covering_prefix(labels, is_prefix_full_cover)

    def run_discovery_epoch(self, iterations: int = 10) -> List[CoveringVerificationReport]:
        """Run a bounded, seeded cyclic-generator discovery epoch over 0-anchored Z_v orbits."""
        if not (isinstance(iterations, int) and not isinstance(iterations, bool)) or iterations <= 0:
            raise ValueError("HALT_INVALID_ITERATION_COUNT")

        all_tails = list(itertools.combinations(range(1, self.v), self.k - 1))
        self._rng.shuffle(all_tails)

        results: List[CoveringVerificationReport] = []
        for i in range(iterations):
            tail = all_tails[i % len(all_tails)]
            base = (0,) + tail
            spec = self.propose_cyclic_generator(base)
            report = self.evaluate_candidate(spec)
            results.append(report)
        return results
