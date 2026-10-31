#!/usr/bin/env python3
"""
SovereignNexus Phase VII Priority #1: Adversarial AST Mutation Verifier.
Status: INTERNAL PREVIEW COMMISSIONED

Enforces Lesson L23 & Security-Sensitive Survivor Zero-Tolerance:
1. Synthesizes semantic AST mutants across four operator families:
   - Comparison boundary perturbations (`>` <-> `>=`, `<` <-> `<=`, `==` <-> `!=`)
   - Off-by-one loop bounds (`range(n)` -> `range(n + 1)`)
   - Boolean operator inversions (`and` <-> `or`)
   - Non-negative integer constant perturbations (`c` -> `c + 1`)
2. Evaluates each mutant against an executable test oracle using temporary module loading
   or out-of-process isolated interpreter execution ("process isolation, not a sandbox")
   with a per-run verification token.
3. Blocks merge (`BLOCK_MERGE`) if `mutation_score_bps < minimum_score_bps` (9000 bps)
   OR if ANY surviving mutant resides in a security-sensitive path (`auth`, `token`,
   `payment`, `crypto`, `delegation`, `migration`, `policy`, `public_api`, `temporal`, `eo1`).
"""

import ast
import copy
import hashlib
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.jcs_canonicalizer import encode_jcs

DEFAULT_MINIMUM_SCORE_BPS: int = 9000  # claim: config
DEFAULT_MAX_MUTANTS: int = 30  # claim: config

SECURITY_SENSITIVE_PATH_KEYWORDS: Tuple[str, ...] = (
    "auth",
    "token",
    "payment",
    "crypto",
    "delegation",
    "migration",
    "policy",
    "public_api",
    "temporal",
    "eo1",
)


def sha256_caid(payload: Any) -> str:
    """Compute a deterministic SHA-256 CAID over raw bytes, UTF-8 text, or RFC 8785 JCS JSON."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class MutantSiteSpec:
    mutant_id: str
    file_path: str
    line_number: int
    mutation_class: str
    original_snippet: str
    mutated_snippet: str
    mutated_source: str
    reason_if_survived: str
    required_test_name: str


@dataclass(frozen=True)
class SurvivingMutantRecord:
    mutant_id: str
    file: str
    line_number: int
    mutation_class: str
    mutation: str
    security_sensitive: bool
    reason: str
    required_test: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line_number": self.line_number,
            "mutant_id": self.mutant_id,
            "mutation": self.mutation,
            "mutation_class": self.mutation_class,
            "reason": self.reason,
            "required_test": self.required_test,
            "security_sensitive": self.security_sensitive,
        }


@dataclass(frozen=True)
class MutationAdequacyReport:
    mutation_score_bps: int
    total_mutants: int
    killed: int
    survived: int
    equivalent_mutants: int
    unverified_mutants: int
    security_sensitive_survivors: int
    survivors: Tuple[SurvivingMutantRecord, ...]
    verdict: str  # "ALLOW_MERGE" | "BLOCK_MERGE"
    reason: str
    report_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "equivalent_mutants": self.equivalent_mutants,
            "killed": self.killed,
            "mutation_score_bps": self.mutation_score_bps,
            "reason": self.reason,
            "report_caid": self.report_caid,
            "security_sensitive_survivors": self.security_sensitive_survivors,
            "survived": self.survived,
            "survivors": [s.to_dict() for s in self.survivors],
            "total_mutants": self.total_mutants,
            "unverified_mutants": self.unverified_mutants,
            "verdict": self.verdict,
        }


def _load_module_namespace_from_source(source_code: str, tmp_dir: str, mod_tag: str) -> Dict[str, Any]:
    """Load Python source code from an ephemeral file via importlib without calling exec/eval."""
    mod_path = Path(tmp_dir) / f"{mod_tag}.py"
    mod_path.write_text(source_code, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(mod_tag, str(mod_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"ERR_MODULE_SPEC_LOAD_FAILED:{mod_tag}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(vars(module))


_ISOLATED_RUNNER_SCRIPT = """
import importlib.util
import json
import pathlib
import sys

req = json.loads(sys.stdin.read())
token = req["token"]
tmp_dir = pathlib.Path(req["tmp_dir"])

def load_ns(src_text, tag):
    p = tmp_dir / f"{tag}.py"
    p.write_text(src_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(tag, str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

test_mod = load_ns(req["test_source"], "test_oracle_mod")
test_fns = [getattr(test_mod, name) for name in dir(test_mod) if name.startswith("test_") and callable(getattr(test_mod, name))]
if not test_fns:
    print(json.dumps({"token": token, "status": "ERR_NO_TEST_FUNCTIONS"}))
    sys.exit(0)

base_mod = load_ns(req["base_source"], "cand_base")
for fn in test_fns:
    fn(vars(base_mod))

killed_ids = []
for idx, item in enumerate(req["mutants"]):
    mid = item["mutant_id"]
    msrc = item["mutated_source"]
    try:
        m_mod = load_ns(msrc, f"cand_mut_{idx}")
        for fn in test_fns:
            fn(vars(m_mod))
    except Exception:
        killed_ids.append(mid)

print(json.dumps({"token": token, "status": "OK", "killed_ids": killed_ids}))
"""


class AdversarialMutationVerifier:
    """
    Synthesizes semantic AST mutants and evaluates whether the test suite kills them.
    Enforces zero-tolerance for surviving mutants in security-sensitive paths.
    """

    CMP_SWAP_MAP = {
        ast.Gt: (ast.GtE, "CMP_BOUNDARY_GT_TO_GTE", "No test covers exact equality boundary"),
        ast.GtE: (ast.Gt, "CMP_BOUNDARY_GTE_TO_GT", "No test covers exact equality boundary"),
        ast.Lt: (ast.LtE, "CMP_BOUNDARY_LT_TO_LTE", "No test covers exact equality boundary"),
        ast.LtE: (ast.Lt, "CMP_BOUNDARY_LTE_TO_LT", "No test covers exact equality boundary"),
        ast.Eq: (ast.NotEq, "CMP_INVERT_EQ_TO_NEQ", "Equality branch not asserted by test oracle"),
        ast.NotEq: (ast.Eq, "CMP_INVERT_NEQ_TO_EQ", "Inequality branch not asserted by test oracle"),
    }

    def __init__(
        self,
        minimum_score_bps: int = DEFAULT_MINIMUM_SCORE_BPS,
        max_mutants: int = DEFAULT_MAX_MUTANTS,
    ) -> None:
        if minimum_score_bps <= 0 or minimum_score_bps > 10000:
            raise ValueError("ERR_INVALID_MINIMUM_SCORE_BPS")
        if max_mutants <= 0:
            raise ValueError("ERR_INVALID_MAX_MUTANTS")
        self.minimum_score_bps = minimum_score_bps
        self.max_mutants = max_mutants

    @staticmethod
    def is_security_sensitive_path(file_path: str) -> bool:
        lower = file_path.lower()
        return any(kw in lower for kw in SECURITY_SENSITIVE_PATH_KEYWORDS)

    @staticmethod
    def _append_mutant(
        mutants: List[MutantSiteSpec],
        file_path: str,
        node: ast.AST,
        mutation_class: str,
        orig_str: str,
        mut_str: str,
        tree_copy: ast.AST,
        reason: str,
        test_prefix: str,
    ) -> None:
        lineno = int(getattr(node, "lineno", 0))
        mut_id = f"MUT_{len(mutants) + 1:02d}"
        mutants.append(
            MutantSiteSpec(
                mutant_id=mut_id,
                file_path=file_path,
                line_number=lineno,
                mutation_class=mutation_class,
                original_snippet=orig_str,
                mutated_snippet=mut_str,
                mutated_source=ast.unparse(tree_copy),
                reason_if_survived=reason,
                required_test_name=f"{test_prefix}_{lineno}",
            )
        )

    def generate_semantic_mutants(
        self,
        file_path: str,
        source_code: str,
    ) -> Tuple[MutantSiteSpec, ...]:
        tree = ast.parse(source_code, filename=file_path)
        all_nodes = list(ast.walk(tree))
        mutants: List[MutantSiteSpec] = []

        for idx, node in enumerate(all_nodes):
            if len(mutants) >= self.max_mutants:
                break

            # 1. Comparison Boundary Perturbations (> <-> >=, < <-> <=, == <-> !=)
            if isinstance(node, ast.Compare) and len(node.ops) == 1:
                op_type = type(node.ops[0])
                if op_type in self.CMP_SWAP_MAP:
                    new_op_cls, m_class, reason = self.CMP_SWAP_MAP[op_type]
                    tree_copy = copy.deepcopy(tree)
                    target = list(ast.walk(tree_copy))[idx]
                    assert isinstance(target, ast.Compare)
                    orig_str = ast.unparse(target)
                    target.ops[0] = new_op_cls()
                    mut_str = ast.unparse(target)
                    self._append_mutant(
                        mutants,
                        file_path,
                        node,
                        m_class,
                        orig_str,
                        mut_str,
                        tree_copy,
                        reason,
                        "test_exact_boundary_line",
                    )
                    continue

            # 2. Off-by-One in `range(n)` -> `range(n + 1)`
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "range"
                and len(node.args) == 1
            ):
                tree_copy = copy.deepcopy(tree)
                target = list(ast.walk(tree_copy))[idx]
                assert isinstance(target, ast.Call)
                orig_str = ast.unparse(target)
                target.args[0] = ast.BinOp(
                    left=target.args[0],
                    op=ast.Add(),
                    right=ast.Constant(value=1),
                )
                mut_str = ast.unparse(target)
                self._append_mutant(
                    mutants,
                    file_path,
                    node,
                    "OFF_BY_ONE_RANGE",
                    orig_str,
                    mut_str,
                    tree_copy,
                    "Loop upper bound off-by-one not checked",
                    "test_loop_range_bound_line",
                )
                continue

            # 3. Boolean Operator Inversion (`and` <-> `or`)
            if isinstance(node, ast.BoolOp):
                tree_copy = copy.deepcopy(tree)
                target = list(ast.walk(tree_copy))[idx]
                assert isinstance(target, ast.BoolOp)
                orig_str = ast.unparse(target)
                target.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
                mut_str = ast.unparse(target)
                self._append_mutant(
                    mutants,
                    file_path,
                    node,
                    "BOOL_CONJUNCTION_SWAP",
                    orig_str,
                    mut_str,
                    tree_copy,
                    "Independent clauses of boolean guard not tested",
                    "test_boolean_clauses_line",
                )
                continue

            # 4. Integer Constant Perturbation (`c` -> `c + 1`)
            if isinstance(node, ast.Constant) and type(node.value) is int:
                tree_copy = copy.deepcopy(tree)
                target = list(ast.walk(tree_copy))[idx]
                assert isinstance(target, ast.Constant)
                orig_val = int(node.value)
                new_val = orig_val + 1
                target.value = new_val
                self._append_mutant(
                    mutants,
                    file_path,
                    node,
                    "CONST_OFF_BY_ONE",
                    str(orig_val),
                    str(new_val),
                    tree_copy,
                    "Integer truncation or loose inequality masked constant perturbation",
                    "test_exact_constant_line",
                )

        return tuple(mutants)

    def evaluate_mutation_adequacy(
        self,
        file_path: str,
        source_code: str,
        test_oracle_fn: Callable[[Dict[str, Any]], None],
    ) -> MutationAdequacyReport:
        """
        Executes `test_oracle_fn(namespace)` against the unmutated code first,
        then against every generated semantic mutant.
        A mutant is KILLED if `test_oracle_fn` raises an AssertionError or Exception.
        """
        mutants = self.generate_semantic_mutants(file_path, source_code)
        if not mutants:
            raise ValueError(f"ERR_NO_MUTANTS_GENERATED:{file_path}")

        killed = 0
        survivors: List[SurvivingMutantRecord] = []
        is_sec_path = self.is_security_sensitive_path(file_path)

        with tempfile.TemporaryDirectory(prefix="aeib_mut_eval_") as tmp_dir:
            base_ns = _load_module_namespace_from_source(source_code, tmp_dir, "cand_base")
            test_oracle_fn(base_ns)

            for idx, m in enumerate(mutants):
                try:
                    mut_ns = _load_module_namespace_from_source(
                        m.mutated_source, tmp_dir, f"cand_mut_{idx}"
                    )
                    test_oracle_fn(mut_ns)
                except Exception:
                    killed += 1
                else:
                    survivors.append(
                        SurvivingMutantRecord(
                            mutant_id=m.mutant_id,
                            file=file_path,
                            line_number=m.line_number,
                            mutation_class=m.mutation_class,
                            mutation=f"{m.original_snippet} -> {m.mutated_snippet}",
                            security_sensitive=is_sec_path,
                            reason=m.reason_if_survived,
                            required_test=m.required_test_name,
                        )
                    )

        return self._finalize_report(file_path, len(mutants), killed, survivors)

    def evaluate_mutation_adequacy_isolated(
        self,
        file_path: str,
        source_code: str,
        test_source_code: str,
        timeout_seconds: int = 10,
    ) -> MutationAdequacyReport:
        """
        Out-of-process evaluation for untrusted candidate/test code (process isolation, not a sandbox).
        Uses a separate interpreter (`sys.executable -I`), empty environment, temporary working
        directory, timeout, and per-run token verification on stdout.
        """
        mutants = self.generate_semantic_mutants(file_path, source_code)
        if not mutants:
            raise ValueError(f"ERR_NO_MUTANTS_GENERATED:{file_path}")

        run_token = secrets.token_hex(16)
        with tempfile.TemporaryDirectory(prefix="aeib_mut_iso_") as tmp_dir:
            runner_file = Path(tmp_dir) / "_runner.py"
            runner_file.write_text(_ISOLATED_RUNNER_SCRIPT, encoding="utf-8")
            req_payload = {
                "token": run_token,
                "tmp_dir": tmp_dir,
                "base_source": source_code,
                "test_source": test_source_code,
                "mutants": [
                    {"mutant_id": m.mutant_id, "mutated_source": m.mutated_source}
                    for m in mutants
                ],
            }
            proc = subprocess.run(
                [sys.executable, "-I", str(runner_file)],
                input=json.dumps(req_payload),
                capture_output=True,
                text=True,
                cwd=tmp_dir,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": tmp_dir,
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                timeout=timeout_seconds,
                check=False,
            )

        if proc.returncode != 0:
            raise RuntimeError(f"ERR_ISOLATED_MUTATION_RUNNER_FAILED:{proc.stderr.strip()}")
        try:
            resp = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception as exc:
            raise RuntimeError("ERR_ISOLATED_STDOUT_PARSE_FAILED") from exc
        if resp.get("token") != run_token or resp.get("status") != "OK":
            raise RuntimeError(f"ERR_ISOLATED_TOKEN_OR_STATUS_INVALID:{resp.get('status')}")

        killed_set = set(resp.get("killed_ids", []))
        is_sec_path = self.is_security_sensitive_path(file_path)
        survivors: List[SurvivingMutantRecord] = []
        for m in mutants:
            if m.mutant_id not in killed_set:
                survivors.append(
                    SurvivingMutantRecord(
                        mutant_id=m.mutant_id,
                        file=file_path,
                        line_number=m.line_number,
                        mutation_class=m.mutation_class,
                        mutation=f"{m.original_snippet} -> {m.mutated_snippet}",
                        security_sensitive=is_sec_path,
                        reason=m.reason_if_survived,
                        required_test=m.required_test_name,
                    )
                )
        return self._finalize_report(file_path, len(mutants), len(killed_set), survivors)

    def _finalize_report(
        self,
        file_path: str,
        total: int,
        killed: int,
        survivors: List[SurvivingMutantRecord],
    ) -> MutationAdequacyReport:
        survived_count = len(survivors)
        sec_survivors = sum(1 for s in survivors if s.security_sensitive)
        score_bps = (killed * 10000) // total

        if score_bps < self.minimum_score_bps and sec_survivors > 0:
            verdict = "BLOCK_MERGE"
            reason = (
                f"Mutation score ({score_bps} bps) below {self.minimum_score_bps} bps "
                f"and {sec_survivors} security-sensitive survivor(s) detected"
            )
        elif sec_survivors > 0:
            verdict = "BLOCK_MERGE"
            reason = (
                f"Security-sensitive survivor detected in {file_path} "
                f"({sec_survivors} survivor(s) at {score_bps} bps)"
            )
        elif score_bps < self.minimum_score_bps:
            verdict = "BLOCK_MERGE"
            reason = f"Mutation score ({score_bps} bps) below threshold ({self.minimum_score_bps} bps)"
        else:
            verdict = "ALLOW_MERGE"
            reason = f"All {killed}/{total} mutants killed ({score_bps} bps) with 0 security-sensitive survivors"

        unsigned_payload = {
            "equivalent_mutants": 0,
            "file_path": file_path,
            "killed": killed,
            "mutation_score_bps": score_bps,
            "reason": reason,
            "security_sensitive_survivors": sec_survivors,
            "survived": survived_count,
            "survivors": [s.to_dict() for s in survivors],
            "total_mutants": total,
            "unverified_mutants": 0,
            "verdict": verdict,
        }
        return MutationAdequacyReport(
            mutation_score_bps=score_bps,
            total_mutants=total,
            killed=killed,
            survived=survived_count,
            equivalent_mutants=0,
            unverified_mutants=0,
            security_sensitive_survivors=sec_survivors,
            survivors=tuple(survivors),
            verdict=verdict,
            reason=reason,
            report_caid=sha256_caid(unsigned_payload),
        )
