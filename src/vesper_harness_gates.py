#!/usr/bin/env python3
"""
Dual-VESPER Combinatorial Discovery Harness (`src/vesper_harness_gates.py`).

Synthesizes:
1. `HackDetectionGate` (Ishibashi et al., arXiv:2605.15221v1): Pre-flight AST gate
   blocking forbidden imports, dunder introspection, top-level calls, float literals,
   `float()` calls, and Python 3 `ast.Div` (`/`) true-division float exploits.
2. `LajollaCoveringVerifier` (dishonest-scoring referee analogous to VESPER,
   arXiv:2210.16746v3): Independent exact-integer referee checking block cardinality,
   point bounds, Schonheim lower bound L(v, k, t), and exhaustive t-subset coverage,
   returning exact `missing_subsets_count`.
3. `HistoryDistiller` (arXiv:2605.15221v1 & AgenticEvolve arXiv:2610.31326v1):
   Compresses trial history into a <60-word signal tracking both uncovered-subset
   velocity and block-count reduction toward the Schonheim bound.
4. `VesperDiscoveryHarness`: Evaluates candidate algebraic generators out-of-process
   in a separate Python interpreter (`-I`) with an empty environment (`env={}`),
   ephemeral temporary working directory, CPU/memory rlimits, execution timeout,
   and a per-run stdout verification token (process isolation, not a sandbox).
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import os
import secrets
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, FrozenSet, List, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs
from src.lajolla_covering_verifier import compute_schonheim_bound as _compute_schonheim_bound


def _validate_no_floats_or_non_str_keys(node: Any) -> None:
    if isinstance(node, float):
        raise ValueError("ERR_FLOAT_FORBIDDEN_IN_JCS")
    if isinstance(node, dict):
        for key, val in node.items():
            if not isinstance(key, str):
                raise ValueError("ERR_NON_STRING_KEY")
            _validate_no_floats_or_non_str_keys(val)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _validate_no_floats_or_non_str_keys(item)


def sha256_jcs_caid(payload: Any) -> str:
    """Compute a deterministic RFC 8785 JCS SHA-256 content-addressed identifier."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        _validate_no_floats_or_non_str_keys(payload)
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


# ============================================================================
# 1. Pre-Flight AST Hack Detection Gate (arXiv:2605.15221v1)
# ============================================================================
class HackDetectionGate:
    """
    Intercepts LLM-generated candidate code BEFORE execution:
    - Allows only pure combinatorial stdlib imports (`math`, `itertools`);
      blocks `verifier`, `scorer`, `evaluator`, `os`, `sys`, `subprocess`, etc.
    - Blocks all dunder attribute/name introspection (`__builtins__`, `__globals__`,
      `__subclasses__`, `__class__`, `__bases__`, `__mro__`, etc.) and frame access.
    - Blocks forbidden calls (`eval`, `exec`, `compile`, `open`, `getattr`, `float`).
    - Blocks float literals (`0.1`) AND Python 3 true division (`ast.Div`: `1 / 3`)
      to eliminate IEEE 754 epsilon exploits in exact combinatorial domains.
    """

    ALLOWED_IMPORTS: FrozenSet[str] = frozenset({"math", "itertools"})

    FORBIDDEN_IMPORTS: FrozenSet[str] = frozenset(
        {
            "verifier",
            "scorer",
            "evaluator",
            "sys",
            "os",
            "subprocess",
            "inspect",
            "shutil",
            "socket",
            "ctypes",
            "pickle",
            "importlib",
            "builtins",
            "io",
            "pathlib",
        }
    )

    FORBIDDEN_DUNDERS: FrozenSet[str] = frozenset(
        {
            "__globals__",
            "__builtins__",
            "__import__",
            "__spec__",
            "__loader__",
            "__dict__",
            "__code__",
            "__subclasses__",
            "__class__",
            "__bases__",
            "__mro__",
            "gi_frame",
            "f_locals",
            "f_globals",
            "f_back",
        }
    )

    FORBIDDEN_CALLS: FrozenSet[str] = frozenset(
        {
            "eval",
            "exec",
            "compile",
            "__import__",
            "open",
            "getattr",
            "setattr",
            "delattr",
            "globals",
            "locals",
            "vars",
            "breakpoint",
            "input",
        }
    )

    @classmethod
    def inspect_candidate(cls, source_code: str) -> Tuple[bool, str]:
        if not isinstance(source_code, str):
            return False, "HALT_EMPTY_CANDIDATE_AST"
        try:
            tree = ast.parse(source_code)
        except SyntaxError as exc:
            return False, f"HALT_SYNTAX_ERROR:{exc.msg}"

        if not tree.body:
            return False, "HALT_EMPTY_CANDIDATE_AST"

        for stmt in tree.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.Expr)):
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        return False, "HALT_TOP_LEVEL_CALL_FORBIDDEN"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in cls.ALLOWED_IMPORTS:
                        return False, f"HALT_HACK_FORBIDDEN_IMPORT:{alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    return False, "HALT_HACK_FORBIDDEN_IMPORT:relative"
                mod_name = node.module or ""
                root = mod_name.split(".")[0]
                if root not in cls.ALLOWED_IMPORTS:
                    return False, f"HALT_HACK_FORBIDDEN_IMPORT:{mod_name}"
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                return False, "HALT_HACK_GLOBAL_MUTATION_FORBIDDEN"
            elif isinstance(node, ast.Attribute):
                if node.attr in cls.FORBIDDEN_DUNDERS:
                    return False, f"HALT_HACK_DUNDER_ACCESS:{node.attr}"
            elif isinstance(node, ast.Name):
                if node.id in cls.FORBIDDEN_DUNDERS:
                    return False, f"HALT_HACK_DUNDER_ACCESS:{node.id}"
            elif isinstance(node, ast.Constant) and isinstance(node.value, float):
                return False, "HALT_HACK_FLOAT_PRECISION_EXPLOIT"
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                return False, "HALT_HACK_FLOAT_TRUE_DIVISION_EXPLOIT"
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "float":
                    return False, "HALT_HACK_FLOAT_PRECISION_EXPLOIT"
                if node.func.id in cls.FORBIDDEN_CALLS:
                    return False, f"HALT_HACK_FORBIDDEN_CALL:{node.func.id}"

        return True, "OK_HACK_FREE_CANDIDATE"


# ============================================================================
# 2. Independent La Jolla Covering-Design Referee
# ============================================================================
@dataclass(frozen=True)
class CoveringVerificationResult:
    v: int
    k: int
    t: int
    blocks_used: int
    schonheim_lower_bound: int
    missing_subsets_count: int
    first_missing_subset: Tuple[int, ...]
    is_valid_covering: bool
    halt_reason: str
    receipt_caid: str


class LajollaCoveringVerifier:
    """Independent exact-integer referee for (v, k, t)-covering designs."""

    @staticmethod
    def compute_schonheim_bound(v: int, k: int, t: int) -> int:
        if isinstance(v, bool) or isinstance(k, bool) or isinstance(t, bool):
            raise ValueError("ERR_INVALID_COVERING_PARAMETERS")
        if t <= 0 or v < k:
            return 0
        if v == k:
            return 1
        return _compute_schonheim_bound(v, k, t)

    @classmethod
    def verify_blocks(
        cls, v: int, k: int, t: int, blocks: Sequence[Sequence[int]]
    ) -> CoveringVerificationResult:
        if (
            isinstance(v, bool)
            or isinstance(k, bool)
            or isinstance(t, bool)
            or not isinstance(v, int)
            or not isinstance(k, int)
            or not isinstance(t, int)
            or v <= 0
            or k <= 0
            or t <= 0
            or not (t <= k <= v)
        ):
            raise ValueError("ERR_INVALID_COVERING_PARAMETERS")

        if not isinstance(blocks, Sequence) or isinstance(blocks, (str, bytes)):
            raise ValueError("ERR_INVALID_BLOCKS_CONTAINER")

        schonheim = cls.compute_schonheim_bound(v, k, t)
        universe = set(range(v))
        normalized_blocks: List[FrozenSet[int]] = []

        for idx, blk in enumerate(blocks):
            if not isinstance(blk, Sequence) or isinstance(blk, (str, bytes)) or len(blk) != k:
                return CoveringVerificationResult(
                    v,
                    k,
                    t,
                    len(blocks),
                    schonheim,
                    -1,
                    (),
                    False,
                    f"HALT_BLOCK_CARDINALITY_MISMATCH_AT_INDEX:{idx}",
                    sha256_jcs_caid({"idx": idx, "k": k, "t": t, "v": v}),
                )
            if any(isinstance(pt, bool) for pt in blk):
                return CoveringVerificationResult(
                    v,
                    k,
                    t,
                    len(blocks),
                    schonheim,
                    -1,
                    (),
                    False,
                    f"HALT_INVALID_OR_DUPLICATE_POINTS_AT_INDEX:{idx}",
                    sha256_jcs_caid({"idx": idx, "k": k, "t": t, "v": v}),
                )
            f_blk = frozenset(blk)
            if len(f_blk) != k or not f_blk.issubset(universe):
                return CoveringVerificationResult(
                    v,
                    k,
                    t,
                    len(blocks),
                    schonheim,
                    -1,
                    (),
                    False,
                    f"HALT_INVALID_OR_DUPLICATE_POINTS_AT_INDEX:{idx}",
                    sha256_jcs_caid({"idx": idx, "k": k, "t": t, "v": v}),
                )
            normalized_blocks.append(f_blk)

        missing_count = 0
        first_missing: Tuple[int, ...] = ()
        for t_sub in itertools.combinations(range(v), t):
            f_sub = frozenset(t_sub)
            if not any(f_sub.issubset(b) for b in normalized_blocks):
                missing_count += 1
                if not first_missing:
                    first_missing = tuple(t_sub)

        if len(blocks) < schonheim:
            reason = f"HALT_BLOCK_COUNT_BELOW_SCHONHEIM_BOUND:{len(blocks)}<{schonheim}"
            is_valid = False
        elif missing_count > 0:
            reason = f"HALT_UNCOVERED_T_SUBSETS:{missing_count}"
            is_valid = False
        else:
            reason = "OK_COVERING_DESIGN_EXHAUSTIVELY_VERIFIED"
            is_valid = True

        caid = sha256_jcs_caid(
            {
                "blocks": [sorted(b) for b in normalized_blocks],
                "is_valid": is_valid,
                "k": k,
                "missing_count": missing_count,
                "schonheim": schonheim,
                "t": t,
                "v": v,
            }
        )
        return CoveringVerificationResult(
            v=v,
            k=k,
            t=t,
            blocks_used=len(blocks),
            schonheim_lower_bound=schonheim,
            missing_subsets_count=missing_count,
            first_missing_subset=first_missing,
            is_valid_covering=is_valid,
            halt_reason=reason,
            receipt_caid=caid,
        )


# ============================================================================
# 3. History Distiller (Two-Stage Velocity + <60-Word Directive)
# ============================================================================
@dataclass(frozen=True)
class TrialRecord:
    generation: int
    blocks_used: int
    missing_subsets: int
    schonheim_lower_bound: int


class HistoryDistiller:
    """Compresses trial lineage into a bounded <60-word algebraic directive."""

    @staticmethod
    def distill_signal(trials: Sequence[TrialRecord]) -> str:
        if not trials:
            return "GEN 0: No history. Propose initial cyclic base block mod v."
        latest = trials[-1]
        gap_to_optimal = latest.blocks_used - latest.schonheim_lower_bound
        if len(trials) >= 3:
            delta_missing = trials[-3].missing_subsets - latest.missing_subsets
            delta_blocks = trials[-3].blocks_used - latest.blocks_used
            velocity = (
                f"Velocity: {delta_missing:+d} subsets/3 gens, "
                f"{delta_blocks:+d} blocks saved/3 gens."
            )
        else:
            velocity = "Velocity: Insufficient data."

        return (
            f"[HISTORY_DISTILLATION]\n"
            f"Gen: {latest.generation} | Blocks: {latest.blocks_used} | "
            f"Schonheim Bound: {latest.schonheim_lower_bound} | Gap: {gap_to_optimal}\n"
            f"Missing Subsets: {latest.missing_subsets}. {velocity}\n"
            f"DIRECTIVE: Do not request full DB. Use 80K tokens to algebraically "
            f"prove why your next base block eliminates the remaining {latest.missing_subsets} subsets."
        )


# ============================================================================
# 4. Out-of-Process Vesper Discovery Harness (process isolation, not a sandbox)
# ============================================================================
_CHILD_RUNNER_SCRIPT = """\
import importlib.util
import json
import resource
import sys

token = sys.argv[1]
v = int(sys.argv[2])
k = int(sys.argv[3])
t = int(sys.argv[4])

try:
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
except Exception:
    pass

spec = importlib.util.spec_from_file_location("candidate", "candidate.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
gen_fn = getattr(mod, "generate_blocks", None)
if not callable(gen_fn):
    sys.stdout.write(token + ":HALT_MISSING_GENERATE_BLOCKS_ENTRYPOINT\\n")
    sys.exit(0)

raw_blocks = gen_fn(v, k, t)
if not isinstance(raw_blocks, (list, tuple)):
    sys.stdout.write(token + ":HALT_INVALID_GENERATOR_RETURN_TYPE\\n")
    sys.exit(0)

serialized = []
for blk in raw_blocks:
    if not isinstance(blk, (list, tuple, set, frozenset)):
        sys.stdout.write(token + ":HALT_INVALID_BLOCK_ELEMENT_TYPE\\n")
        sys.exit(0)
    row = []
    for pt in blk:
        if isinstance(pt, bool) or not isinstance(pt, int):
            sys.stdout.write(token + ":HALT_NON_INTEGER_POINT\\n")
            sys.exit(0)
        row.append(int(pt))
    serialized.append(row)

sys.stdout.write(token + ":OK:" + json.dumps(serialized, separators=(",", ":")) + "\\n")
"""


@dataclass(frozen=True)
class EvaluatedCandidate:
    candidate_id: str
    is_hack_suspected: bool
    halt_or_status_code: str
    blocks_used: int
    missing_subsets_count: int
    is_valid_covering: bool
    receipt_caid: str


class VesperDiscoveryHarness:
    """
    Executes candidate algebraic generators in a separate Python interpreter (`-I`)
    with an empty environment (`env={}`), a temporary working directory, CPU rlimits,
    a timeout, and a per-run verification token (process isolation, not a sandbox),
    then verifies the generated blocks via `LajollaCoveringVerifier`.
    """

    def __init__(self, v: int, k: int, t: int, timeout_sec: float = 5.0) -> None:
        if (
            isinstance(v, bool)
            or isinstance(k, bool)
            or isinstance(t, bool)
            or v <= 0
            or k <= 0
            or t <= 0
            or not (t <= k <= v)
        ):
            raise ValueError("ERR_INVALID_COVERING_PARAMETERS")
        self.v = v
        self.k = k
        self.t = t
        self.timeout_sec = timeout_sec
        self.trials: List[TrialRecord] = []

    @staticmethod
    def _halted_candidate(candidate_id: str, halt_code: str) -> EvaluatedCandidate:
        return EvaluatedCandidate(
            candidate_id=candidate_id,
            is_hack_suspected=True,
            halt_or_status_code=halt_code,
            blocks_used=-1,
            missing_subsets_count=-1,
            is_valid_covering=False,
            receipt_caid=sha256_jcs_caid({"candidate_id": candidate_id, "reason": halt_code}),
        )

    def evaluate_candidate(
        self, candidate_id: str, candidate_code: str
    ) -> EvaluatedCandidate:
        is_clean, reason = HackDetectionGate.inspect_candidate(candidate_code)
        if not is_clean:
            return self._halted_candidate(candidate_id, reason)

        run_token = secrets.token_hex(16)
        with tempfile.TemporaryDirectory(prefix="vesper_eval_") as tmpdir:
            script_path = os.path.join(tmpdir, "candidate.py")
            with open(script_path, "w", encoding="utf-8") as handle:
                handle.write(candidate_code)

            try:
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-c",
                        _CHILD_RUNNER_SCRIPT,
                        run_token,
                        str(self.v),
                        str(self.k),
                        str(self.t),
                    ],
                    cwd=tmpdir,
                    env={},
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return self._halted_candidate(candidate_id, "HALT_CANDIDATE_EXECUTION_TIMEOUT")

        if proc.returncode != 0:
            return self._halted_candidate(candidate_id, "HALT_CANDIDATE_RUNTIME_EXCEPTION")

        matched_line = ""
        prefix = f"{run_token}:"
        for line in proc.stdout.splitlines():
            if line.startswith(prefix):
                matched_line = line[len(prefix) :]
                break

        if not matched_line:
            return self._halted_candidate(candidate_id, "HALT_MISSING_STDOUT_TOKEN")

        if not matched_line.startswith("OK:"):
            return self._halted_candidate(candidate_id, matched_line)

        blocks: List[List[int]] = json.loads(matched_line[3:])
        verdict = LajollaCoveringVerifier.verify_blocks(self.v, self.k, self.t, blocks)
        self.trials.append(
            TrialRecord(
                generation=len(self.trials) + 1,
                blocks_used=verdict.blocks_used,
                missing_subsets=max(0, verdict.missing_subsets_count),
                schonheim_lower_bound=verdict.schonheim_lower_bound,
            )
        )
        return EvaluatedCandidate(
            candidate_id=candidate_id,
            is_hack_suspected=False,
            halt_or_status_code=verdict.halt_reason,
            blocks_used=verdict.blocks_used,
            missing_subsets_count=verdict.missing_subsets_count,
            is_valid_covering=verdict.is_valid_covering,
            receipt_caid=verdict.receipt_caid,
        )
