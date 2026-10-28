#!/usr/bin/env python3
"""
compliance/claim_integrity_gate.py — Claim-Integrity Gate (AST-based, stdlib only)

Detects source patterns where a reported outcome is not backed by a computation
or an invocation under the stated model. Rules:

  CI001 ERROR  numeric literal bound to a metric-named key/var (src/, tools/)
               unless the line carries `# claim: assumption` or `# claim: config`.
  CI002 ERROR  print/log/return of a verdict string (PASS / VERIFIED / 100% /
               "0 violations") emitted on an unguarded path.
  CI003 ERROR  verify*/check*/validate*/is_valid* function whose every return is
               the constant True (or a dict with a constant truthy ok-flag) with
               no conditional, raise, or checking call.
  CI004 ERROR  module mentions an external verifier/attestation tool
               (lean/lake/bpftool/tetragon/tpm2_*/Phonon/SEV-SNP/TDX) and claims
               verification, yet never spawns a process / loads a native library
               and is not labelled scaffold/simulated in its module docstring.
  CI005 ERROR  private key or seed derived from a source literal
               (from_private_bytes(<literal>), sha256(b"...") seeds, ...).
  CI006 ERROR  dict combining a 'simulated' marker with a success flag set True.
  CI007 WARN   (tests/) assertion comparing a result attribute to a numeric
               literal that also appears in the imported src module (echo test).
  CI008 ERROR  dynamic import (importlib.import_module / __import__) of a Zone 2
               module prefix, which the static zone-boundary gate does not see.

Ratchet: existing findings are recorded in compliance/claim_integrity_baseline.json
keyed by (rule, file, normalized-snippet hash) with a multiplicity count. The gate
exits 1 only on NEW ERROR findings; baseline debt is reported, not failed.

Usage:
  python3 compliance/claim_integrity_gate.py --all
  python3 compliance/claim_integrity_gate.py --staged
  python3 compliance/claim_integrity_gate.py --paths src/foo.py tools/bar.py
  python3 compliance/claim_integrity_gate.py --all --update-baseline
  python3 compliance/claim_integrity_gate.py --all --json

This is a heuristic static scanner (prototype). A clean result means none of the
configured patterns were observed; it does not establish that claims are true.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import subprocess
import sys
import time
import tokenize
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_REL = "compliance/claim_integrity_baseline.json"
SELF_REL = "compliance/claim_integrity_gate.py"

SCAN_ROOTS = ("src", "tools", "compliance", "benchmarks", "scripts", "tests")
METRIC_SCOPE_ROOTS = ("src", "tools")
EXCLUDED_PREFIXES = ("tests/fixtures/claim_integrity",)
EXCLUDED_PARTS = {
    "__pycache__", "third_party", "node_modules", "scratch", ".venv", "venv",
    "venv_l2", "target", "dist", ".worktrees", "site-packages", ".git",
}

SEVERITY = {
    "CI001": "ERROR", "CI002": "ERROR", "CI003": "ERROR", "CI004": "ERROR",
    "CI005": "ERROR", "CI006": "ERROR", "CI007": "WARN", "CI008": "ERROR",
}
PROD_RULES = frozenset({"CI002", "CI003", "CI004", "CI005", "CI006", "CI008"})
PROFILES = {
    "metric": PROD_RULES | {"CI001"},
    "prod": PROD_RULES,
    "test": frozenset({"CI007", "CI008"}),
}

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
METRIC_NAME_RE = re.compile(
    r"(?:^|_)(?:bps|pct)$|_(?:rate|usd|ms|micros)$|(?:^|_)(?:accuracy|reduction|savings|score)$",
    re.IGNORECASE,
)
CLAIM_ANNOTATION_RE = re.compile(r"#\s*claim:\s*(assumption|config)\b", re.IGNORECASE)

VERDICT_WORD_RE = re.compile(
    r"(?<![A-Za-z_])(?<!NOT )(?<!NOT_)(?<!Not )(?<!not )(?:PASS(?:ED)?|VERIFIED)(?![A-Za-z])"
)
VERDICT_PCT_RE = re.compile(r"(?<![\d.])100(?:\.0+)?\s?%")
VERDICT_ZERO_RE = re.compile(
    r"(?<![\w.])0[ _](?:violations?|failures?|errors?|duplicates?|defects?|leaks?)\b",
    re.IGNORECASE,
)
VERDICT_HEADER_RE = re.compile(
    r"PASS(?:ED)?\s*[/|]\s*FAIL(?:ED)?|(?:expected|target|goal)\s*[:=]?\s*100(?:\.0+)?\s?%", re.IGNORECASE
)

VERIFIER_NAME_RE = re.compile(r"^_*(?:verify|check|validate|is_valid)", re.IGNORECASE)
OK_KEYS = {"valid", "ok", "verified", "is_valid", "passed", "success", "attested"}

TOOL_RE = re.compile(
    r"\b(lean4?|lake (?:build|env|exe|update)|lakefile|bpftool|tetragon|tpm2|phonon|sev[- ]?snp|tdx)\b", re.IGNORECASE
)
VERIFY_CLAIM_RE = re.compile(r"\b(verif(?:y|ied|ies|ying|ication)|attest\w*)\b", re.IGNORECASE)
SCAFFOLD_RE = re.compile(r"scaffold|simulat", re.IGNORECASE)
SPAWN_MODULES = {"subprocess", "ctypes", "pty", "multiprocessing"}
OS_SPAWN_RE = re.compile(r"^(?:exec\w*|spawn\w*|posix_spawn\w*|popen|system|fork\w*)$")

SUCCESS_FLAG_KEYS = {
    "success", "succeeded", "verified", "ok", "passed", "pass", "attested",
    "attached", "enforced", "valid", "is_valid", "sealed", "proven", "compliant",
    "accepted", "loaded",
}
SUCCESS_STRINGS = {"PASS", "PASSED", "VERIFIED", "SUCCESS", "OK"}

LOG_METHODS = {"debug", "info", "warning", "warn", "error", "critical", "exception", "log", "success"}
GUARD_CALL_RE = re.compile(r"(?:assert|verify|check|validate|ensure|require|self_?test|run_tests)", re.IGNORECASE)
EXIT_CALLS = {"sys.exit", "exit", "quit", "os._exit", "os.abort", "pytest.fail", "pytest.skip"}

DEFAULT_ZONE2_PREFIXES = ("aeib_postgresql_probe", "enterprise", "commercial")

TRIVIAL_INTS = set(range(-10, 11)) | {
    16, 24, 32, 60, 64, 100, 128, 255, 256, 512, 1000, 1024, 2048, 3600, 4096,
    10000, 65535, 65536, 86400, 100000, 1000000,
}
TRIVIAL_FLOATS = {0.0, 0.5, 1.0, 2.0, 10.0, 100.0, 1000.0}


@dataclass
class Finding:
    rule: str
    severity: str
    path: str
    line: int
    snippet: str
    message: str
    fingerprint: str = ""
    status: str = "new"  # "new" | "baseline"

    def key(self) -> str:
        return f"{self.rule}|{self.path}|{self.fingerprint}"


@dataclass
class ScanResult:
    findings: List[Finding] = field(default_factory=list)
    files_scanned: int = 0
    parse_errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic AST helpers
# ---------------------------------------------------------------------------
def _normalize(text: str, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _fingerprint(rule: str, snippet: str) -> str:
    return hashlib.sha256(f"{rule}\x1f{_normalize(snippet)}".encode("utf-8")).hexdigest()[:16]


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # unparse is best-effort for odd nodes
        return type(node).__name__


def _dotted(node: ast.AST) -> str:
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append(_dotted(node.func) + "()")
    return ".".join(reversed(parts))


def _call_name(call: ast.Call) -> str:
    return _dotted(call.func)


def _key_name(node: Optional[ast.AST]) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return sl.value
    return None


def _numeric_literal(node: Optional[ast.AST]) -> Optional[float]:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _numeric_literal(node.operand)
        if inner is not None:
            return -inner if isinstance(node.op, ast.USub) else inner
    return None


def _walk_local(node: ast.AST) -> Iterable[ast.AST]:
    """Walk a subtree without descending into nested function/class/lambda scopes."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        cur = stack.pop()
        yield cur
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(cur))


def _string_parts(node: ast.AST) -> List[str]:
    """Literal text of a Constant str or the constant parts of an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
    return []


def _verdict_match(text: str) -> Optional[str]:
    cleaned = VERDICT_HEADER_RE.sub(" ", text)
    for rx in (VERDICT_WORD_RE, VERDICT_PCT_RE, VERDICT_ZERO_RE):
        m = rx.search(cleaned)
        if m:
            return m.group(0)
    return None


def _comment_map(source: str) -> Dict[int, str]:
    comments: Dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comments[tok.start[0]] = tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return comments
    return comments


def _load_zone2_prefixes(root: Path) -> Tuple[str, ...]:
    path = root / "compliance" / "check_zone_boundary.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return DEFAULT_ZONE2_PREFIXES
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ZONE2_PREFIXES" for t in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return DEFAULT_ZONE2_PREFIXES
            return tuple(str(v) for v in value) or DEFAULT_ZONE2_PREFIXES
    return DEFAULT_ZONE2_PREFIXES


# ---------------------------------------------------------------------------
# Module analyzer
# ---------------------------------------------------------------------------
class ModuleAnalyzer:
    def __init__(self, gate: "ClaimIntegrityGate", rel: str, source: str, tree: ast.Module, rules: frozenset):
        self.gate = gate
        self.rel = rel
        self.source = source
        self.tree = tree
        self.rules = rules
        self.comments = _comment_map(source)
        self.parents: Dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node
        self.findings: List[Finding] = []
        self._seen: Set[Tuple[str, int, str]] = set()

    # -- reporting ---------------------------------------------------------
    def report(self, rule: str, node: Optional[ast.AST], snippet: str, message: str, line: Optional[int] = None) -> None:
        lineno = line if line is not None else getattr(node, "lineno", 1)
        snip = _normalize(snippet)
        dedupe = (rule, lineno, snip)
        if dedupe in self._seen:
            return
        self._seen.add(dedupe)
        self.findings.append(
            Finding(rule=rule, severity=SEVERITY[rule], path=self.rel, line=lineno,
                    snippet=snip, message=message, fingerprint=_fingerprint(rule, snip))
        )

    def run(self) -> List[Finding]:
        for rule in sorted(self.rules):
            getattr(self, f"rule_{rule.lower()}")()
        return self.findings

    # -- scope helpers -----------------------------------------------------
    def enclosing_function(self, node: ast.AST) -> Optional[ast.AST]:
        cur = self.parents.get(node)
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return cur
            cur = self.parents.get(cur)
        return None

    def _statement_of(self, node: ast.AST) -> ast.AST:
        cur = node
        while cur is not None and not isinstance(cur, ast.stmt):
            cur = self.parents.get(cur)
        return cur if cur is not None else node

    @staticmethod
    def _is_trivial_test(test: ast.AST) -> bool:
        if isinstance(test, ast.Constant):
            return True
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
        ):
            return True
        return False

    def _subtree_exits(self, stmt: ast.AST, in_loop_of: Optional[ast.AST]) -> bool:
        """True if stmt can divert control flow (raise/assert/exit/return/guard call)."""
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False  # definitions do not execute their bodies at definition time
        for sub in [stmt, *_walk_local(stmt)]:
            if isinstance(sub, (ast.Raise, ast.Assert)):
                return True
            if isinstance(sub, ast.Return) and sub is not stmt:
                return True
            if isinstance(sub, (ast.Continue, ast.Break)) and in_loop_of is not None:
                return True
            if isinstance(sub, ast.Call):
                name = _call_name(sub)
                if name in EXIT_CALLS:
                    return True
                if isinstance(sub.func, (ast.Name, ast.Attribute)) and GUARD_CALL_RE.search(name.split(".")[-1]):
                    return True
                if isinstance(sub.func, ast.Name) and sub.func.id in self.raising_functions():
                    return True
        return False

    def raising_functions(self) -> Set[str]:
        """Module-level functions whose bodies can abort (assert/raise/exit): calling one guards later code."""
        if not hasattr(self, "_raising_cache"):
            names: Set[str] = set()
            for node in self.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for sub in _walk_local(node):
                        if isinstance(sub, (ast.Assert, ast.Raise)) or (
                            isinstance(sub, ast.Call) and _call_name(sub) in EXIT_CALLS
                        ):
                            names.add(node.name)
                            break
            self._raising_cache = names
        return self._raising_cache

    def is_guarded(self, node: ast.AST) -> bool:
        """True if node executes only on a path shaped by a computed condition."""
        stmt = self._statement_of(node)
        # Expression-level conditionals around the node itself.
        cur: Optional[ast.AST] = node
        while cur is not None and cur is not stmt:
            parent = self.parents.get(cur)
            if isinstance(parent, (ast.IfExp, ast.BoolOp)):
                return True
            if isinstance(parent, ast.comprehension) and parent.ifs:
                return True
            cur = parent
        # Statement-level ancestors + preceding siblings.
        child: ast.AST = stmt
        parent = self.parents.get(child)
        loop: Optional[ast.AST] = None
        while parent is not None:
            if isinstance(parent, ast.If) and child is not parent.test:
                if not self._is_trivial_test(parent.test):
                    return True
            if isinstance(parent, ast.While) and not self._is_trivial_test(parent.test):
                return True
            if isinstance(parent, ast.Try) and (child in parent.body and parent.handlers or child in parent.handlers):
                return True
            if isinstance(parent, getattr(ast, "match_case", ())):
                return True
            if isinstance(parent, (ast.For, ast.AsyncFor, ast.While)) and loop is None:
                loop = parent
            for block_name in ("body", "orelse", "finalbody", "handlers"):
                block = getattr(parent, block_name, None)
                if isinstance(block, list) and child in block:
                    for prev in block[: block.index(child)]:
                        if self._subtree_exits(prev, loop if parent is loop else None):
                            return True
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.Module)):
                break
            child, parent = parent, self.parents.get(parent)
        return False

    def bound_only_to_true(self, name: str, scope: Optional[ast.AST]) -> bool:
        container = scope if scope is not None else self.tree
        values = []
        for sub in _walk_local(container):
            if isinstance(sub, ast.Assign):
                for t in sub.targets:
                    if isinstance(t, ast.Name) and t.id == name:
                        values.append(sub.value)
            elif isinstance(sub, (ast.AnnAssign, ast.AugAssign)) and isinstance(sub.target, ast.Name) and sub.target.id == name:
                values.append(sub.value)
        return bool(values) and all(isinstance(v, ast.Constant) and v.value is True for v in values)

    # -- CI001 -------------------------------------------------------------
    def _annotated(self, *nodes: ast.AST) -> bool:
        for n in nodes:
            for ln in {getattr(n, "lineno", 0), getattr(n, "end_lineno", 0)}:
                if ln and CLAIM_ANNOTATION_RE.search(self.comments.get(ln, "")):
                    return True
        return False

    def rule_ci001(self) -> None:
        for node in ast.walk(self.tree):
            pairs: List[Tuple[ast.AST, ast.AST, ast.AST]] = []
            if isinstance(node, ast.Dict):
                pairs = [(k, v, k) for k, v in zip(node.keys, node.values) if k is not None]
            elif isinstance(node, ast.Call):
                pairs = [(ast.Constant(kw.arg), kw.value, kw.value) for kw in node.keywords if kw.arg]
            elif isinstance(node, ast.Assign):
                pairs = [(t, node.value, t) for t in node.targets]
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                pairs = [(node.target, node.value, node.target)]
            for key, value, anchor in pairs:
                name = _key_name(key)
                num = _numeric_literal(value)
                if not name or num is None or num == 0:
                    continue
                if not METRIC_NAME_RE.search(name):
                    continue
                if self._annotated(anchor, value, self._statement_of(value)):
                    continue
                self.report(
                    "CI001", value, f"{name}={num!r}",
                    f"literal {num!r} bound to metric-named '{name}'; compute it or annotate "
                    f"'# claim: assumption' / '# claim: config'",
                )

    # -- CI002 -------------------------------------------------------------
    def _is_emit_call(self, call: ast.Call) -> bool:
        name = _call_name(call)
        if name in {"print", "sys.stdout.write", "click.echo", "console.print", "typer.echo"}:
            for kw in call.keywords:
                if kw.arg == "file" and "stderr" in _dotted(kw.value):
                    return False
            return True
        if isinstance(call.func, ast.Attribute) and call.func.attr in LOG_METHODS:
            receiver = _dotted(call.func.value).lower()
            return "log" in receiver
        return False

    def rule_ci002(self) -> None:
        for node in ast.walk(self.tree):
            candidates: List[ast.AST] = []
            if isinstance(node, ast.Call) and self._is_emit_call(node):
                candidates = list(node.args[:2])
            elif isinstance(node, ast.Return) and node.value is not None:
                val = node.value
                if isinstance(val, ast.Dict):
                    candidates = list(val.values)
                elif isinstance(val, (ast.Tuple, ast.List)):
                    candidates = list(val.elts)
                else:
                    candidates = [val]
            for cand in candidates:
                text = " ".join(_string_parts(cand))
                if not text:
                    continue
                hit = _verdict_match(text)
                if not hit or self.is_guarded(cand):
                    continue
                kind = "return" if isinstance(node, ast.Return) else _call_name(node)
                self.report(
                    "CI002", cand, f"{kind}: {_unparse(cand)}",
                    f"verdict text '{hit}' emitted on an unguarded path (not derived from a computed condition)",
                )

    # -- CI003 -------------------------------------------------------------
    @staticmethod
    def _constant_accept(value: Optional[ast.AST]) -> bool:
        if isinstance(value, ast.Constant) and value.value is True:
            return True
        if isinstance(value, ast.Dict):
            for k, v in zip(value.keys, value.values):
                if (
                    isinstance(k, ast.Constant) and isinstance(k.value, str)
                    and k.value.lower() in OK_KEYS
                    and isinstance(v, ast.Constant) and bool(v.value)
                ):
                    return True
        return False

    def rule_ci003(self) -> None:
        benign = {"print", "len", "str", "repr", "int", "float", "bool", "dict", "list", "tuple", "set", "id", "type"}
        for fn in ast.walk(self.tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not VERIFIER_NAME_RE.match(fn.name):
                continue
            if any(isinstance(d, ast.Name) and d.id == "abstractmethod" or
                   isinstance(d, ast.Attribute) and d.attr == "abstractmethod" for d in fn.decorator_list):
                continue
            body_nodes = [n for stmt in fn.body for n in (stmt, *_walk_local(stmt))]
            returns = [n for n in body_nodes if isinstance(n, ast.Return)]
            if not returns or not all(self._constant_accept(r.value) for r in returns):
                continue
            in_return: Set[ast.AST] = set()
            for r in returns:
                in_return.update(ast.walk(r))
            diverts = False
            for sub in body_nodes:
                if isinstance(sub, (ast.If, ast.IfExp, ast.Raise, ast.Try, ast.Assert, ast.While,
                                    ast.For, ast.AsyncFor, ast.BoolOp, ast.Compare, ast.With, ast.AsyncWith,
                                    ast.Await, ast.Yield, ast.YieldFrom)) or (
                    hasattr(ast, "Match") and isinstance(sub, ast.Match)
                ):
                    diverts = True
                    break
                if isinstance(sub, ast.Call):
                    name = _call_name(sub)
                    short = name.split(".")[-1]
                    if sub in in_return:
                        if GUARD_CALL_RE.search(short):
                            diverts = True
                            break
                        continue
                    if name in benign or self._is_emit_call(sub):
                        continue
                    diverts = True
                    break
            if diverts:
                continue
            self.report(
                "CI003", fn, f"def {fn.name}: returns {_unparse(returns[0].value)}",
                f"verifier '{fn.name}' accepts every input (constant success, no condition/raise/check)",
            )

    # -- CI004 -------------------------------------------------------------
    def _module_corpus(self) -> str:
        chunks: List[str] = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                chunks.append(node.value)
            elif isinstance(node, ast.Name):
                chunks.append(node.id)
            elif isinstance(node, ast.Attribute):
                chunks.append(node.attr)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                chunks.append(node.name)
            elif isinstance(node, ast.alias):
                chunks.append(node.name)
        return " ".join(chunks).replace("_", " ")

    def rule_ci004(self) -> None:
        doc = ast.get_docstring(self.tree) or ""
        if SCAFFOLD_RE.search(doc):
            return
        corpus = self._module_corpus()
        tools = sorted({m.group(1).lower().replace(" ", "-").replace("sevsnp", "sev-snp") for m in TOOL_RE.finditer(corpus)})
        if not tools or not VERIFY_CLAIM_RE.search(corpus):
            return
        if self.gate.module_spawns(self.rel, self.tree):
            return
        self.report(
            "CI004", None, f"tools={','.join(tools)}",
            f"module references {', '.join(tools)} and claims verification/attestation but never "
            f"spawns a process or loads a native library, and its docstring is not labelled scaffold/simulated",
            line=1,
        )

    # -- CI005 -------------------------------------------------------------
    def _assignments(self) -> Dict[str, List[ast.AST]]:
        if not hasattr(self, "_assign_cache"):
            table: Dict[str, List[ast.AST]] = {}
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            table.setdefault(t.id, []).append(node.value)
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                    table.setdefault(node.target.id, []).append(node.value)
            self._assign_cache = table
        return self._assign_cache

    def literal_derived(self, expr: Optional[ast.AST], depth: int = 0) -> bool:
        if expr is None or depth > 8:
            return False
        if isinstance(expr, ast.Constant):
            return isinstance(expr.value, (bytes, str, int)) and not isinstance(expr.value, bool) and expr.value not in ("", b"")
        if isinstance(expr, ast.JoinedStr):
            return all(isinstance(v, ast.Constant) for v in expr.values)
        if isinstance(expr, (ast.List, ast.Tuple)):
            return bool(expr.elts) and all(self.literal_derived(e, depth + 1) for e in expr.elts)
        if isinstance(expr, ast.BinOp):
            return self.literal_derived(expr.left, depth + 1) and self.literal_derived(expr.right, depth + 1)
        if isinstance(expr, ast.Subscript):
            return self.literal_derived(expr.value, depth + 1)
        if isinstance(expr, ast.Name):
            values = self._assignments().get(expr.id, [])
            return bool(values) and all(self.literal_derived(v, depth + 1) for v in values)
        if isinstance(expr, ast.Call):
            name = _call_name(expr)
            short = name.split(".")[-1]
            args = list(expr.args) + [kw.value for kw in expr.keywords]
            if isinstance(expr.func, ast.Attribute) and short in {"encode", "digest", "hexdigest", "ljust", "rjust", "zfill"}:
                return self.literal_derived(expr.func.value, depth + 1)
            if short == "range":
                return all(_numeric_literal(a) is not None for a in args)
            hash_like = name.startswith("hashlib.") or short in {
                "sha256", "sha512", "sha3_256", "sha3_512", "blake2b", "blake2s", "sha1", "md5",
                "fromhex", "bytes", "bytearray", "pbkdf2_hmac", "scrypt", "unhexlify", "b64decode",
            }
            if hash_like:
                return bool(args) and all(self.literal_derived(a, depth + 1) for a in args)
        return False

    def _is_parameter(self, target: ast.AST, at: ast.AST) -> bool:
        """A bare Name that is a parameter of the enclosing function is runtime-supplied."""
        if not isinstance(target, ast.Name):
            return False
        fn = self.enclosing_function(at)
        if fn is None:
            return False
        a = fn.args
        names = {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
        names |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
        return target.id in names

    def rule_ci005(self) -> None:
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            short = name.split(".")[-1]
            args = list(node.args) + [kw.value for kw in node.keywords if kw.arg in (None, "data", "seed", "private_value")]
            target: Optional[ast.AST] = None
            if short in {"from_private_bytes", "derive_private_key", "load_pem_private_key", "load_der_private_key"}:
                target = args[0] if args else None
            elif short in {"SigningKey", "PrivateKey"} and args:
                target = args[0]
            if target is None or self._is_parameter(target, node) or not self.literal_derived(target):
                continue
            self.report(
                "CI005", node, f"{short}({_unparse(target)})",
                "private key/seed derived from a source literal; load key material from a protected store",
            )

    # -- CI006 -------------------------------------------------------------
    def rule_ci006(self) -> None:
        for node in ast.walk(self.tree):
            pairs: List[Tuple[Optional[str], ast.AST]] = []
            if isinstance(node, ast.Dict):
                pairs = [(k.value if isinstance(k, ast.Constant) and isinstance(k.value, str) else None, v)
                         for k, v in zip(node.keys, node.values)]
            elif isinstance(node, ast.Call) and _call_name(node) == "dict":
                pairs = [(kw.arg, kw.value) for kw in node.keywords]
            if not pairs:
                continue
            marker = False
            flag: Optional[str] = None
            scope = self.enclosing_function(node)
            for key, value in pairs:
                kl = (key or "").lower()
                if "simulat" in kl and not (isinstance(value, ast.Constant) and value.value in (False, None, 0, "")):
                    marker = True
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and "simulat" in value.value.lower():
                    marker = True
                if kl in SUCCESS_FLAG_KEYS:
                    if isinstance(value, ast.Constant) and (
                        value.value is True or (isinstance(value.value, str) and value.value.upper() in SUCCESS_STRINGS)
                    ):
                        flag = key
                    elif isinstance(value, ast.Name) and self.bound_only_to_true(value.id, scope):
                        flag = key
            if marker and flag:
                self.report(
                    "CI006", node, _unparse(node),
                    f"'simulated' marker reported together with success flag '{flag}'=True",
                )

    # -- CI007 -------------------------------------------------------------
    def rule_ci007(self) -> None:
        src_literals: Set[float] = set()
        for node in ast.walk(self.tree):
            mods: List[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods.append(node.module)
                mods.extend(f"{node.module}.{a.name}" for a in node.names)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            for mod in mods:
                src_literals |= self.gate.module_literals(mod)
        if not src_literals:
            return
        for node in ast.walk(self.tree):
            pairs: List[Tuple[ast.AST, ast.AST]] = []
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
                t = node.test
                if len(t.ops) == 1 and isinstance(t.ops[0], ast.Eq):
                    pairs = [(t.left, t.comparators[0]), (t.comparators[0], t.left)]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {
                "assertEqual", "assertAlmostEqual", "assertEquals"
            } and len(node.args) >= 2:
                pairs = [(node.args[0], node.args[1]), (node.args[1], node.args[0])]
            for subject, expected in pairs:
                if isinstance(expected, ast.Call) and _call_name(expected).endswith("approx") and expected.args:
                    expected = expected.args[0]
                num = _numeric_literal(expected)
                if num is None or not isinstance(subject, (ast.Attribute, ast.Subscript, ast.Call)):
                    continue
                if isinstance(subject, ast.Call) and _call_name(subject) in {
                    "len", "int", "float", "round", "abs", "sum", "min", "max", "str", "sorted", "list"
                }:
                    continue
                if _is_trivial_number(num) or num not in src_literals:
                    continue
                self.report(
                    "CI007", node, _unparse(node.test if isinstance(node, ast.Assert) else node),
                    f"assertion echoes literal {num!r} that is hardcoded in the imported module",
                )
                break

    # -- CI008 -------------------------------------------------------------
    def rule_ci008(self) -> None:
        prefixes = self.gate.zone2_prefixes
        if self.rel.split("/", 1)[0] in prefixes:
            return
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name not in {"importlib.import_module", "import_module", "__import__", "importlib.__import__"}:
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                continue
            mod = node.args[0].value
            if any(mod == p or mod.startswith(p + ".") or mod.startswith(p) for p in prefixes):
                self.report(
                    "CI008", node, f"{name}({mod!r})",
                    f"dynamic import of Zone 2 module '{mod}' bypasses the static zone-boundary gate",
                )


def _is_trivial_number(num: float) -> bool:
    if isinstance(num, int):
        return num in TRIVIAL_INTS
    return num in TRIVIAL_FLOATS or (float(num).is_integer() and int(num) in TRIVIAL_INTS)


# ---------------------------------------------------------------------------
# Gate (file discovery, baseline ratchet)
# ---------------------------------------------------------------------------
class ClaimIntegrityGate:
    def __init__(self, root: Path = DEFAULT_ROOT, baseline_path: Optional[Path] = None):
        self.root = Path(root).resolve()
        self.baseline_path = Path(baseline_path) if baseline_path else self.root / BASELINE_REL
        self.zone2_prefixes = _load_zone2_prefixes(self.root)
        self._literal_cache: Dict[str, Set[float]] = {}
        self._spawn_cache: Dict[str, bool] = {}
        self._staged_sources: Dict[str, str] = {}

    # -- paths -------------------------------------------------------------
    def rel(self, path: Path) -> str:
        p = Path(path)
        if not p.is_absolute():
            p = (self.root / p)
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return p.as_posix()

    @staticmethod
    def excluded(rel: str) -> bool:
        if rel == SELF_REL:
            return True
        if any(rel == pre or rel.startswith(pre + "/") for pre in EXCLUDED_PREFIXES):
            return True
        return any(part in EXCLUDED_PARTS for part in rel.split("/"))

    @staticmethod
    def in_scope(rel: str) -> bool:
        if not rel.endswith(".py"):
            return False
        top = rel.split("/", 1)[0]
        return "/" not in rel or top in SCAN_ROOTS

    @staticmethod
    def profile_for(rel: str) -> str:
        parts = rel.split("/")
        name = parts[-1]
        if "tests" in parts[:-1] or name.startswith("test_") or name == "conftest.py":
            return "test"
        if parts[0] in METRIC_SCOPE_ROOTS:
            return "metric"
        return "prod"

    def discover_all(self) -> List[str]:
        out: Set[str] = set()
        for top in SCAN_ROOTS:
            base = self.root / top
            if not base.is_dir():
                continue
            for p in base.rglob("*.py"):
                rel = p.relative_to(self.root).as_posix()
                if not self.excluded(rel):
                    out.add(rel)
        for p in self.root.glob("*.py"):
            rel = p.relative_to(self.root).as_posix()
            if not self.excluded(rel):
                out.add(rel)
        return sorted(out)

    def discover_staged(self) -> List[str]:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=self.root, capture_output=True, text=True, check=True,
        )
        files = []
        for rel in proc.stdout.splitlines():
            rel = rel.strip()
            if not rel or not self.in_scope(rel) or self.excluded(rel):
                continue
            blob = subprocess.run(["git", "show", f":{rel}"], cwd=self.root, capture_output=True, text=True)
            if blob.returncode == 0:
                self._staged_sources[rel] = blob.stdout
                files.append(rel)
        return files

    # -- cross-module helpers ---------------------------------------------
    def _resolve_module(self, dotted: str) -> Optional[Path]:
        parts = dotted.split(".")
        candidates = [self.root.joinpath(*parts).with_suffix(".py"), self.root.joinpath(*parts) / "__init__.py"]
        if parts[0] not in ("src", "tools", "tests"):
            candidates.append(self.root.joinpath("src", *parts).with_suffix(".py"))
        for c in candidates:
            if c.is_file():
                return c
        return None

    def module_literals(self, dotted: str) -> Set[float]:
        if dotted in self._literal_cache:
            return self._literal_cache[dotted]
        lits: Set[float] = set()
        path = self._resolve_module(dotted)
        if path is not None:
            rel = self.rel(path)
            if self.profile_for(rel) != "test" or rel.startswith(EXCLUDED_PREFIXES):
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                except (SyntaxError, UnicodeDecodeError, OSError):
                    tree = None
                if tree is not None:
                    for n in ast.walk(tree):
                        num = _numeric_literal(n) if isinstance(n, (ast.Constant, ast.UnaryOp)) else None
                        if num is not None and not _is_trivial_number(num):
                            lits.add(num)
        self._literal_cache[dotted] = lits
        return lits

    @staticmethod
    def _tree_spawns(tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] in SPAWN_MODULES for a in node.names):
                return True
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in SPAWN_MODULES:
                return True
            if isinstance(node, ast.Call):
                name = _call_name(node)
                head, _, tail = name.rpartition(".")
                if head == "os" and OS_SPAWN_RE.match(tail):
                    return True
                if tail in {"create_subprocess_exec", "create_subprocess_shell"}:
                    return True
        return False

    def module_spawns(self, rel: str, tree: ast.Module) -> bool:
        if self._tree_spawns(tree):
            return True
        # One hop through first-party imports.
        pkg = rel.rsplit("/", 1)[0].replace("/", ".") if "/" in rel else ""
        for node in ast.walk(tree):
            mods: List[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.level:
                    base = pkg.split(".")[: len(pkg.split(".")) - (node.level - 1)] if pkg else []
                    mods.append(".".join([*base, node.module]))
                else:
                    mods.append(node.module)
                mods.extend(f"{m}.{a.name}" for m in list(mods) for a in node.names)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            for mod in mods:
                if mod in self._spawn_cache:
                    if self._spawn_cache[mod]:
                        return True
                    continue
                path = self._resolve_module(mod)
                result = False
                if path is not None:
                    try:
                        result = self._tree_spawns(ast.parse(path.read_text(encoding="utf-8")))
                    except (SyntaxError, UnicodeDecodeError, OSError):
                        result = False
                self._spawn_cache[mod] = result
                if result:
                    return True
        return False

    # -- scanning ----------------------------------------------------------
    def scan_source(self, rel: str, source: str, profile: Optional[str] = None) -> List[Finding]:
        tree = ast.parse(source, filename=rel)
        rules = PROFILES[profile or self.profile_for(rel)]
        return ModuleAnalyzer(self, rel, source, tree, rules).run()

    def scan(self, rels: Sequence[str], profile: Optional[str] = None) -> ScanResult:
        result = ScanResult()
        for rel in rels:
            source = self._staged_sources.get(rel)
            if source is None:
                try:
                    source = (self.root / rel).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    result.parse_errors.append(f"{rel}: {exc}")
                    continue
            try:
                result.findings.extend(self.scan_source(rel, source, profile))
            except SyntaxError as exc:
                result.parse_errors.append(f"{rel}:{exc.lineno}: SyntaxError")
                continue
            result.files_scanned += 1
        result.findings.sort(key=lambda f: (f.path, f.line, f.rule))
        return result

    # -- baseline ----------------------------------------------------------
    def load_baseline(self) -> Dict[str, int]:
        if not self.baseline_path.is_file():
            return {}
        data = json.loads(self.baseline_path.read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in data.get("entries", {}).items()}

    def apply_baseline(self, findings: List[Finding], baseline: Dict[str, int]) -> None:
        budget = dict(baseline)
        for f in findings:
            k = f.key()
            if budget.get(k, 0) > 0:
                budget[k] -= 1
                f.status = "baseline"
            else:
                f.status = "new"

    def write_baseline(self, findings: List[Finding], scanned: Sequence[str], full: bool) -> Dict[str, int]:
        entries: Dict[str, int] = {} if full else {
            k: v for k, v in self.load_baseline().items() if k.split("|")[1] not in set(scanned)
        }
        for f in findings:
            entries[f.key()] = entries.get(f.key(), 0) + 1
        summary = Counter()
        for k, v in entries.items():
            summary[k.split("|", 1)[0]] += v
        payload = {
            "version": 1,
            "tool": SELF_REL,
            "description": "Claim-integrity ratchet: pre-existing findings keyed by rule|file|snippet-hash -> count. "
                           "New findings beyond these counts fail the gate.",
            "summary": dict(sorted(summary.items())),
            "total": sum(entries.values()),
            "entries": dict(sorted(entries.items())),
        }
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self.baseline_path.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n", encoding="utf-8")
        return entries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Claim-integrity gate (AST-based ratchet).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--paths", nargs="+", help="Scan the given files.")
    mode.add_argument("--staged", action="store_true", help="Scan staged .py files (index content).")
    mode.add_argument("--all", action="store_true", help="Scan all in-scope files.")
    parser.add_argument("--update-baseline", action="store_true", help="Record current findings as baseline debt.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Repository root.")
    parser.add_argument("--baseline", default=None, help="Baseline file path.")
    parser.add_argument("--profile", choices=sorted(PROFILES), default=None,
                        help="Force a rule profile for --paths (default: derived from path).")
    parser.add_argument("--show-baseline", action="store_true", help="Also list baseline findings.")
    args = parser.parse_args(argv)

    started = time.monotonic()
    gate = ClaimIntegrityGate(Path(args.root), Path(args.baseline) if args.baseline else None)
    if args.all:
        rels = gate.discover_all()
    elif args.staged:
        rels = gate.discover_staged()
    else:
        rels = [gate.rel(Path(p)) for p in args.paths if p.endswith(".py")]

    result = gate.scan(rels, profile=args.profile if args.paths else None)

    if args.update_baseline:
        entries = gate.write_baseline(result.findings, rels, full=bool(args.all))
        print(f"[claim-gate] baseline written: {gate.rel(gate.baseline_path)} "
              f"({sum(entries.values())} findings in {len(entries)} keys, {len(rels)} files scanned)")

    baseline = gate.load_baseline()
    gate.apply_baseline(result.findings, baseline)
    new = [f for f in result.findings if f.status == "new"]
    new_errors = [f for f in new if f.severity == "ERROR"]
    debt = Counter(f.rule for f in result.findings if f.status == "baseline")
    resolved = 0
    if args.all:
        current = Counter(f.key() for f in result.findings)
        resolved = sum(max(0, v - current.get(k, 0)) for k, v in baseline.items())
    elapsed = time.monotonic() - started

    if args.json:
        print(json.dumps({
            "files_scanned": result.files_scanned,
            "new": [asdict(f) for f in new],
            "new_error_count": len(new_errors),
            "baseline_debt": dict(sorted(debt.items())),
            "baseline_resolved": resolved,
            "parse_errors": result.parse_errors,
            "elapsed_s": round(elapsed, 3),
            "findings": [asdict(f) for f in result.findings] if args.show_baseline else None,
        }, indent=1))
    else:
        shown = result.findings if args.show_baseline else new
        for f in shown:
            tag = "" if f.status == "new" else " (baseline)"
            print(f"{f.path}:{f.line}: {f.rule} [{f.severity}]{tag} {f.message} :: {f.snippet}")
        for err in result.parse_errors:
            print(f"[claim-gate] parse error (skipped): {err}", file=sys.stderr)
        debt_txt = ", ".join(f"{k}={v}" for k, v in sorted(debt.items())) or "none"
        print(f"[claim-gate] files={result.files_scanned} new_errors={len(new_errors)} "
              f"new_warnings={len(new) - len(new_errors)} baseline_debt={sum(debt.values())} ({debt_txt})"
              + (f" resolved_since_baseline={resolved}" if args.all else "")
              + f" elapsed={elapsed:.2f}s")
        if new_errors:
            print("[claim-gate] BLOCKED: new claim-integrity ERROR findings. Compute the value, label it "
                  "('# claim: assumption|config' for CI001), or fix the logic.", file=sys.stderr)
    return 1 if new_errors else 0


if __name__ == "__main__":
    sys.exit(run_cli())
