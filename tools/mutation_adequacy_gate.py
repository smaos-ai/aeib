#!/usr/bin/env python3
"""
tools/mutation_adequacy_gate.py — Stdlib AST Mutation-Adequacy Gate (oracle-quality measurement).

Purpose (prototype, evaluated under the stated model):
    Coverage says "the line ran". Mutation adequacy asks the question that matters for an
    AI-written codebase: "if this line were wrong, would any test notice?"  A surviving mutant
    is a concrete, replayable hole in the test oracle (a line the tests do not actually check).

Grounding (fresh literature, Oct 2026):
    - arXiv:2609.24341v1: for LLM-generated Python suites, structural coverage sits near its
      ceiling and does not discriminate; Cosmic Ray mutation scores do.
    - arXiv:2609.09315v1: fault detection on LLM-induced faults is often near zero because the
      test oracle does not capture the faulty behaviour.
    - arXiv:2609.37322v1 (Mubric): mutation testing as a generic adequacy check for evaluators.

Method:
    1. Parse the target module with `ast`, enumerate mutation sites for a small, classic operator
       set (comparison flip, boolean-operator swap, `not` removal, constant perturbation,
       return-value replacement, arithmetic swap, raise removal).
    2. Deterministically sample up to `max_mutants` sites with a seeded RNG.
    3. Copy the repository's `src/` and `tests/` once into a temporary shadow root. For each
       mutant, overwrite only the shadow copy of the target file, run the selected pytest files
       in a fresh subprocess (`-x -q`, wall-clock timeout), and classify:
         KILLED   — tests failed (the oracle noticed)
         SURVIVED — tests passed (oracle hole)
         TIMEOUT  — counted as killed-by-timeout, reported separately
         INVALID  — mutant does not compile (excluded from the denominator)
    4. Report kill ratio = killed / (killed + survived + timeout) and list survivors with line
       numbers so a human or builder agent can add a targeted test.

Limitations (stated honestly):
    - Equivalent mutants are not detected automatically; some survivors may be behaviourally
      identical to the original and need human triage.
    - Sampling means the kill ratio is an estimate for the sampled sites, not the whole module.
    - The real `src/` tree is never modified; only the temporary shadow copy is mutated.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

STATUS_KILLED = "KILLED"
STATUS_SURVIVED = "SURVIVED"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_INVALID = "INVALID"

_CMP_FLIP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}
_BIN_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult}


@dataclass(frozen=True)
class MutationSite:
    """A single mutation location: operator, AST node ordinal, and source line."""

    operator: str
    node_index: int
    lineno: int
    description: str


@dataclass(frozen=True)
class MutantOutcome:
    site: MutationSite
    status: str
    elapsed_s: float
    mutant_sha256: str


@dataclass
class MutationAdequacyReport:
    target_file: str
    target_sha256: str
    test_files: Tuple[str, ...]
    seed: int
    sites_enumerated: int
    mutants_sampled: int
    killed: int = 0
    survived: int = 0
    timed_out: int = 0
    invalid: int = 0
    baseline_suite_passed: bool = False
    elapsed_total_s: float = 0.0
    outcomes: List[MutantOutcome] = field(default_factory=list)

    def kill_ratio(self) -> Optional[float]:
        denom = self.killed + self.survived + self.timed_out
        if denom == 0:
            return None
        return (self.killed + self.timed_out) / denom

    def survivors(self) -> List[MutationSite]:
        return [o.site for o in self.outcomes if o.status == STATUS_SURVIVED]

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["kill_ratio"] = self.kill_ratio()
        d["survivor_lines"] = sorted({s.lineno for s in self.survivors()})
        return d


def _is_docstring_expr(node: ast.AST, parents: Dict[int, ast.AST]) -> bool:
    parent = parents.get(id(node))
    if isinstance(parent, ast.Expr):
        grand = parents.get(id(parent))
        body = getattr(grand, "body", None)
        return bool(body) and body[0] is parent
    return False


def _build_parent_map(tree: ast.AST) -> Dict[int, ast.AST]:
    parents: Dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def enumerate_mutation_sites(source: str) -> List[MutationSite]:
    """Enumerates mutation sites in deterministic `ast.walk` order."""
    tree = ast.parse(source)
    parents = _build_parent_map(tree)
    sites: List[MutationSite] = []
    for idx, node in enumerate(ast.walk(tree)):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP_FLIP:
            sites.append(MutationSite("CMP_FLIP", idx, line, f"{type(node.ops[0]).__name__} flipped"))
        elif isinstance(node, ast.BoolOp):
            sites.append(MutationSite("BOOL_SWAP", idx, line, f"{type(node.op).__name__} swapped"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append(MutationSite("NOT_DROP", idx, line, "`not` removed"))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN_SWAP:
            sites.append(MutationSite("ARITH_SWAP", idx, line, f"{type(node.op).__name__} swapped"))
        elif isinstance(node, ast.Return) and node.value is not None and not (
            isinstance(node.value, ast.Constant) and node.value.value is None
        ):
            # `return None` -> `return None` is an equivalent mutant by construction; skip it
            # here rather than letting it be sampled as a survivor that no test could kill.
            sites.append(MutationSite("RETURN_NONE", idx, line, "return value replaced with None"))
        elif isinstance(node, ast.Raise):
            sites.append(MutationSite("RAISE_DROP", idx, line, "raise replaced with pass"))
        elif (
            isinstance(node, ast.Constant)
            and type(node.value) in (int, bool)
            and not _is_docstring_expr(node, parents)
        ):
            sites.append(MutationSite("CONST_PERTURB", idx, line, f"constant {node.value!r} perturbed"))
    return sites


class _Mutator(ast.NodeTransformer):
    def __init__(self, target_index: int, operator: str, index_map: Dict[int, int]) -> None:
        self.target_index = target_index
        self.operator = operator
        self.index_map = index_map
        self.applied = False

    def visit(self, node: ast.AST):  # type: ignore[override]
        if self.index_map.get(id(node)) == self.target_index and not self.applied:
            replaced = self._mutate(node)
            self.applied = True
            return replaced
        return super().visit(node)

    def _mutate(self, node: ast.AST) -> ast.AST:
        op = self.operator
        if op == "CMP_FLIP" and isinstance(node, ast.Compare):
            node.ops = [_CMP_FLIP[type(node.ops[0])]()]
            return node
        if op == "BOOL_SWAP" and isinstance(node, ast.BoolOp):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            return node
        if op == "NOT_DROP" and isinstance(node, ast.UnaryOp):
            return node.operand
        if op == "ARITH_SWAP" and isinstance(node, ast.BinOp):
            node.op = _BIN_SWAP[type(node.op)]()
            return node
        if op == "RETURN_NONE" and isinstance(node, ast.Return):
            node.value = ast.Constant(value=None)
            return node
        if op == "RAISE_DROP" and isinstance(node, ast.Raise):
            return ast.Pass()
        if op == "CONST_PERTURB" and isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                node.value = not node.value
            else:
                node.value = node.value + 1
            return node
        raise ValueError(f"Operator {op} does not apply to node {type(node).__name__}")


def apply_mutation(source: str, site: MutationSite) -> str:
    """Returns mutated source for one site (fresh parse each call; deterministic)."""
    tree = ast.parse(source)
    index_map = {id(n): i for i, n in enumerate(ast.walk(tree))}
    mutator = _Mutator(site.node_index, site.operator, index_map)
    new_tree = mutator.visit(tree)
    if not mutator.applied:
        raise ValueError(f"Mutation site {site} not found")
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


def _run_pytest(shadow_root: Path, test_files: Sequence[str], timeout_s: float) -> Tuple[str, float]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(shadow_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *test_files]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(shadow_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return STATUS_TIMEOUT, time.perf_counter() - t0
    elapsed = time.perf_counter() - t0
    return (STATUS_SURVIVED if proc.returncode == 0 else STATUS_KILLED), elapsed


def _prepare_shadow_root(repo_root: Path, dest: Path, test_files: Sequence[str]) -> None:
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    for sub in (
        "src",
        "specs",
        "tools",
        "compliance",
        "data",
        "proofs",
        "experiments",
        "adapters",
        "scripts",
        "simulation-lab",
        "v1.1-roadmap",
    ):
        if (repo_root / sub).is_dir():
            shutil.copytree(repo_root / sub, dest / sub, ignore=ignore)
    for sym_sub in (".agents", "docs", "schemas", "contracts", "conformance", "evidence", "formal"):
        if (repo_root / sym_sub).is_dir() and not (dest / sym_sub).exists():
            os.symlink(repo_root / sym_sub, dest / sym_sub)
    if (repo_root / "benchmarks").is_dir():
        (dest / "benchmarks").mkdir(parents=True, exist_ok=True)
        for pyf in (repo_root / "benchmarks").glob("*.py"):
            shutil.copy2(pyf, dest / "benchmarks" / pyf.name)
    (dest / "tests").mkdir(parents=True, exist_ok=True)
    if (repo_root / "tests" / "fixtures").is_dir():
        shutil.copytree(repo_root / "tests" / "fixtures", dest / "tests" / "fixtures", ignore=ignore)
    for name in ("__init__.py", "conftest.py"):
        src_file = repo_root / "tests" / name
        if src_file.is_file():
            shutil.copy2(src_file, dest / "tests" / name)
    for pyf in (repo_root / "tests").glob("*.py"):
        shutil.copy2(pyf, dest / "tests" / pyf.name)
    for rel in test_files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / rel, target)
    for cfg in ("pytest.ini", "conftest.py"):
        if (repo_root / cfg).is_file():
            shutil.copy2(repo_root / cfg, dest / cfg)
    # Root-level Python modules (e.g. aeib_mcp_proxy.py) are importable from the repo root
    # and were previously missing from the shadow, so their mutants could not be measured.
    for pyf in repo_root.glob("*.py"):
        if not (dest / pyf.name).exists():
            shutil.copy2(pyf, dest / pyf.name)
    # Test data directories (e.g. tests/data/jcs conformance vectors) were missing, which made
    # data-driven tests skip inside the shadow and silently weakened the measured kill ratio.
    for data_sub in ("data",):
        src_dir = repo_root / "tests" / data_sub
        if src_dir.is_dir() and not (dest / "tests" / data_sub).exists():
            shutil.copytree(src_dir, dest / "tests" / data_sub, ignore=ignore)
    # Benchmark packages (subdirectories with Python modules) imported by tests.
    if (repo_root / "benchmarks").is_dir():
        for sub in (repo_root / "benchmarks").iterdir():
            if sub.is_dir() and sub.name != "__pycache__" and any(sub.rglob("*.py")):
                if not (dest / "benchmarks" / sub.name).exists():
                    shutil.copytree(sub, dest / "benchmarks" / sub.name, ignore=ignore)


def run_mutation_adequacy(
    target_rel: str,
    test_files: Sequence[str],
    max_mutants: int = 30,
    seed: int = 42,
    per_mutant_timeout_s: float = 120.0,
    repo_root: Path = REPO_ROOT,
) -> MutationAdequacyReport:
    """Runs the full mutation-adequacy experiment against an isolated shadow copy."""
    t_start = time.perf_counter()
    target_path = repo_root / target_rel
    original = target_path.read_text(encoding="utf-8")
    sites = enumerate_mutation_sites(original)
    rng = random.Random(seed)
    sampled = sorted(rng.sample(sites, min(max_mutants, len(sites))), key=lambda s: s.node_index)

    report = MutationAdequacyReport(
        target_file=target_rel,
        target_sha256=hashlib.sha256(original.encode("utf-8")).hexdigest(),
        test_files=tuple(test_files),
        seed=seed,
        sites_enumerated=len(sites),
        mutants_sampled=len(sampled),
    )

    with tempfile.TemporaryDirectory(prefix="aeib_mutation_") as tmp:
        shadow = Path(tmp)
        _prepare_shadow_root(repo_root, shadow, test_files)
        shadow_target = shadow / target_rel
        shadow_target.parent.mkdir(parents=True, exist_ok=True)
        shadow_target.write_text(original, encoding="utf-8")

        baseline_status, _ = _run_pytest(shadow, test_files, per_mutant_timeout_s)
        report.baseline_suite_passed = baseline_status == STATUS_SURVIVED
        if not report.baseline_suite_passed:
            report.elapsed_total_s = time.perf_counter() - t_start
            return report

        for site in sampled:
            try:
                mutated = apply_mutation(original, site)
                compile(mutated, target_rel, "exec")
            except (SyntaxError, ValueError, TypeError):
                report.invalid += 1
                report.outcomes.append(MutantOutcome(site, STATUS_INVALID, 0.0, ""))
                continue
            shadow_target.write_text(mutated, encoding="utf-8")
            status, elapsed = _run_pytest(shadow, test_files, per_mutant_timeout_s)
            digest = hashlib.sha256(mutated.encode("utf-8")).hexdigest()
            report.outcomes.append(MutantOutcome(site, status, round(elapsed, 3), digest))
            if status == STATUS_KILLED:
                report.killed += 1
            elif status == STATUS_SURVIVED:
                report.survived += 1
            else:
                report.timed_out += 1
        shadow_target.write_text(original, encoding="utf-8")

    report.elapsed_total_s = round(time.perf_counter() - t_start, 3)
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Stdlib AST mutation-adequacy gate")
    parser.add_argument("--target", required=True, help="Repo-relative module path, e.g. src/x.py")
    parser.add_argument("--tests", required=True, nargs="+", help="Repo-relative pytest files")
    parser.add_argument("--max-mutants", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--min-kill-ratio", type=float, default=None,
                        help="Exit 1 if the measured kill ratio is below this threshold")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args(argv)

    report = run_mutation_adequacy(
        target_rel=args.target,
        test_files=args.tests,
        max_mutants=args.max_mutants,
        seed=args.seed,
        per_mutant_timeout_s=args.timeout,
    )
    payload = report.to_dict()
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    ratio = report.kill_ratio()
    print(
        f"[mutation-gate] target={report.target_file} baseline_passed={report.baseline_suite_passed} "
        f"sites={report.sites_enumerated} sampled={report.mutants_sampled} killed={report.killed} "
        f"survived={report.survived} timeout={report.timed_out} invalid={report.invalid} "
        f"kill_ratio={ratio if ratio is None else round(ratio, 4)} elapsed_s={report.elapsed_total_s}"
    )
    for site in report.survivors():
        print(f"  SURVIVED line {site.lineno}: {site.operator} ({site.description})")
    if not report.baseline_suite_passed:
        return 2
    if args.min_kill_ratio is not None and (ratio is None or ratio < args.min_kill_ratio):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
