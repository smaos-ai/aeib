#!/usr/bin/env python3
"""Deterministic parallel-lane partitioner for agent worktrees (prototype).

Problem: two agents whose write sets are disjoint can still break each other.
Lane A changes ``f()`` in ``a.py``; lane B edits ``c.py``, which calls ``f()``.
Git merges both without a textual conflict and the build breaks.

This tool decides which lanes may run in parallel before dispatch:

* builds a Python import graph with its own resolver (absolute, ``from pkg
  import mod``, and relative imports with level), stdlib ``ast`` only;
* condenses import cycles with an iterative Tarjan SCC (a lane that writes one
  member of a cycle is treated as touching the whole cycle);
* footprint(L) = SCC-expanded writes of L plus their reverse importers up to
  ``hops`` (``hops=-1`` means transitive);
* lanes A and B conflict when either one's writes intersect the other's
  writes or footprint. With ``shared_caller_conflicts=True`` they also
  conflict when their footprints share an untouched caller;
* greedy colouring in lane-id order produces parallel waves; lanes whose
  written files cannot be parsed are fail-closed into their own serial wave.

Bare-name imports that rely on ``sys.path`` inserts (``from sovereign_search
import X`` with ``src/`` on the path) are resolved against ``IMPORT_ROOTS``.
A bare name that matches a local file stem but cannot be resolved is counted
as unresolved. String literals that exactly name a repository file path
(``"scripts/a.py"``) or a dotted repository module (``"src.a"``, as used by
``importlib.import_module``, ``__import__`` and plugin registries) are treated
as dependencies (conservative: may over-serialize). Coupling through
non-Python files (shared JSON fixtures, databases, ports) is NOT detected. A
partition plan does not replace running the full suite on the merged result.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs  # noqa: E402

MAX_FILE_BYTES: int = 2_000_000
MAX_LANES: int = 64
MAX_STRING_REF_CHARS: int = 256
SCAN_DIRS: Tuple[str, ...] = ("src", "tools", "tests", "benchmarks", "scripts", "compliance", "v1.1-roadmap")
IMPORT_ROOTS: Tuple[str, ...] = ("", "src", "scripts", "v1.1-roadmap", "tools")


@dataclass(frozen=True)
class ImportGraph:
    """Forward import edges between repository files."""

    forward: Mapping[str, FrozenSet[str]]
    reverse: Mapping[str, FrozenSet[str]]
    unparsable: FrozenSet[str]
    unresolved_import_count: int


@dataclass(frozen=True)
class Lane:
    """A unit of agent work with the files it intends to write."""

    lane_id: str
    write_set: FrozenSet[str]


@dataclass(frozen=True)
class LaneConflict:
    """Why two lanes may not run in the same wave."""

    lane_a: str
    lane_b: str
    reason: str
    witness_file: str


@dataclass(frozen=True)
class PartitionPlan:
    """Parallel waves plus the evidence used to build them."""

    waves: Tuple[Tuple[str, ...], ...]
    conflicts: Tuple[LaneConflict, ...]
    footprints: Mapping[str, FrozenSet[str]]
    serialized_unanalyzable: Tuple[str, ...]
    hops: int
    shared_caller_conflicts: bool
    unresolved_import_count: int
    plan_digest: str = field(default="")


def _resolve_path(base: str, known: Set[str]) -> Optional[str]:
    """Resolve a slash path (no suffix) to ``base.py`` or ``base/__init__.py``."""
    if not base or base.endswith("/"):
        return None
    for cand in (base + ".py", base + "/__init__.py"):
        if cand in known:
            return cand
    return None


def _resolve_dotted(dotted: str, known: Set[str], roots: Sequence[str]) -> Optional[str]:
    if not dotted:
        return None
    rel = dotted.replace(".", "/")
    for root in roots:
        hit = _resolve_path(f"{root}/{rel}" if root else rel, known)
        if hit is not None:
            return hit
    return None


def _local_names(known: Set[str]) -> Set[str]:
    """Top-level directory names and file stems present in the repository."""
    names: Set[str] = set()
    for p in known:
        parts = Path(p).parts
        names.add(parts[0])
        names.add(Path(p).stem)
    names.discard("__init__")
    return names


def resolve_imports(
    rel_path: str,
    source: str,
    known: Set[str],
    roots: Sequence[str] = IMPORT_ROOTS,
    local_names: Optional[Set[str]] = None,
) -> Tuple[Set[str], int]:
    """Return (resolved repository files imported by ``rel_path``, unresolved count).

    Raises SyntaxError / ValueError when the source cannot be parsed.
    """
    tree = ast.parse(source, filename=rel_path)
    names = local_names if local_names is not None else _local_names(known)
    resolved: Set[str] = set()
    unresolved = 0
    pkg_dir = list(Path(rel_path).parent.parts)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = _resolve_dotted(alias.name, known, roots)
                parent = alias.name
                while hit is None and "." in parent:
                    # importing a missing submodule still executes the parent package
                    parent = parent.rsplit(".", 1)[0]
                    hit = _resolve_dotted(parent, known, roots)
                if hit is not None:
                    resolved.add(hit)
                elif alias.name.split(".")[0] in names:
                    unresolved += 1
        elif isinstance(node, ast.ImportFrom):
            mod_rel = (node.module or "").replace(".", "/")
            if node.level:
                drop = node.level - 1
                if drop > len(pkg_dir):
                    unresolved += 1
                    continue
                base_dir = "/".join(pkg_dir[: len(pkg_dir) - drop])
                module_path = "/".join(p for p in (base_dir, mod_rel) if p)
                module_hit = _resolve_path(module_path, known) if mod_rel else _resolve_path(base_dir, known)
                search = [module_path]
            else:
                module_hit = _resolve_dotted(node.module or "", known, roots)
                search = [f"{r}/{mod_rel}" if r else mod_rel for r in roots]
            name_hit = False
            for alias in node.names:
                for base in search:
                    sub = _resolve_path(f"{base}/{alias.name}" if base else alias.name, known)
                    if sub is not None:
                        resolved.add(sub)
                        name_hit = True
                        break
            if module_hit is not None:
                resolved.add(module_hit)
            elif not name_hit:
                top = (node.module or "").split(".")[0]
                if node.level or top in names:
                    unresolved += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            ref = _resolve_string_reference(node.value, known, roots)
            if ref is not None:
                resolved.add(ref)
    resolved.discard(rel_path)
    return resolved, unresolved


def _resolve_string_reference(value: str, known: Set[str], roots: Sequence[str]) -> Optional[str]:
    """Map a string literal naming a repo file or dotted repo module to that file."""
    if len(value) > MAX_STRING_REF_CHARS or any(ch.isspace() for ch in value):
        return None
    if value in known:
        return value
    if "." in value and "/" not in value and not value.endswith(".py"):
        return _resolve_dotted(value, known, roots)
    return None


def build_import_graph(files: Mapping[str, str]) -> ImportGraph:
    """Build forward and reverse import edges over the given repository files."""
    known = set(files)
    names = _local_names(known)
    forward: Dict[str, FrozenSet[str]] = {}
    unparsable: Set[str] = set()
    unresolved_total = 0
    for rel_path in sorted(files):
        source = files[rel_path]
        if len(source.encode("utf-8", errors="replace")) > MAX_FILE_BYTES:
            unparsable.add(rel_path)
            forward[rel_path] = frozenset()
            continue
        try:
            deps, unresolved = resolve_imports(rel_path, source, known, IMPORT_ROOTS, names)
        except (SyntaxError, ValueError):
            unparsable.add(rel_path)
            forward[rel_path] = frozenset()
            continue
        forward[rel_path] = frozenset(deps)
        unresolved_total += unresolved
    reverse_build: Dict[str, Set[str]] = {p: set() for p in files}
    for src_file, deps in forward.items():
        for dep in deps:
            reverse_build[dep].add(src_file)
    reverse = {k: frozenset(v) for k, v in reverse_build.items()}
    return ImportGraph(forward=forward, reverse=reverse, unparsable=frozenset(unparsable), unresolved_import_count=unresolved_total)


def tarjan_scc(forward: Mapping[str, Iterable[str]]) -> List[FrozenSet[str]]:
    """Iterative Tarjan strongly connected components (no recursion limit)."""
    index_of: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    components: List[FrozenSet[str]] = []
    counter = 0
    for root in sorted(forward):
        if root in index_of:
            continue
        work: List[Tuple[str, Iterable[str]]] = [(root, iter(sorted(forward.get(root, ()))))]
        index_of[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index_of:
                    index_of[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(forward.get(child, ())))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index_of[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                comp: Set[str] = set()
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    comp.add(member)
                    if member == node:
                        break
                components.append(frozenset(comp))
    return components


def reverse_closure(graph: ImportGraph, seeds: Iterable[str], hops: int) -> FrozenSet[str]:
    """Files that import any seed, up to ``hops`` levels (-1 = transitive). Excludes seeds."""
    seed_set = set(seeds)
    seen: Set[str] = set(seed_set)
    frontier = set(seed_set)
    depth = 0
    while frontier and (hops < 0 or depth < hops):
        nxt: Set[str] = set()
        for f in frontier:
            for caller in graph.reverse.get(f, frozenset()):
                if caller not in seen:
                    seen.add(caller)
                    nxt.add(caller)
        frontier = nxt
        depth += 1
    return frozenset(seen - seed_set)


def partition_lanes(
    graph: ImportGraph,
    lanes: Sequence[Lane],
    hops: int = 1,
    shared_caller_conflicts: bool = False,
) -> PartitionPlan:
    """Group lanes into waves that can run in parallel under the stated model."""
    if len(lanes) > MAX_LANES:
        raise ValueError("ERR_TOO_MANY_LANES")
    ids = [lane.lane_id for lane in lanes]
    if len(set(ids)) != len(ids):
        raise ValueError("ERR_DUPLICATE_LANE_ID")
    if hops < -1:
        raise ValueError("ERR_INVALID_HOPS")

    scc_of: Dict[str, FrozenSet[str]] = {}
    for comp in tarjan_scc(graph.forward):
        for member in comp:
            scc_of[member] = comp

    writes: Dict[str, FrozenSet[str]] = {}
    footprints: Dict[str, FrozenSet[str]] = {}
    unanalyzable: List[str] = []
    for lane in sorted(lanes, key=lambda l: l.lane_id):
        expanded: Set[str] = set(lane.write_set)
        for f in lane.write_set:
            expanded |= scc_of.get(f, frozenset({f}))
        writes[lane.lane_id] = frozenset(expanded)
        footprints[lane.lane_id] = reverse_closure(graph, expanded, hops)
        if lane.write_set & graph.unparsable:
            unanalyzable.append(lane.lane_id)

    ordered = sorted(writes)
    conflicts: List[LaneConflict] = []
    adjacency: Dict[str, Set[str]] = {lid: set() for lid in ordered}
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            conflict: Optional[LaneConflict] = None
            overlap = writes[a] & writes[b]
            if overlap:
                conflict = LaneConflict(a, b, "WRITE_WRITE_OVERLAP", min(overlap))
            elif writes[a] & footprints[b]:
                conflict = LaneConflict(a, b, "A_WRITES_B_DEPENDENT", min(writes[a] & footprints[b]))
            elif writes[b] & footprints[a]:
                conflict = LaneConflict(a, b, "B_WRITES_A_DEPENDENT", min(writes[b] & footprints[a]))
            elif shared_caller_conflicts and footprints[a] & footprints[b]:
                conflict = LaneConflict(a, b, "SHARED_UNTOUCHED_CALLER", min(footprints[a] & footprints[b]))
            if conflict is not None:
                conflicts.append(conflict)
                adjacency[a].add(b)
                adjacency[b].add(a)

    waves: List[List[str]] = []
    for lid in ordered:
        if lid in unanalyzable:
            continue
        for wave in waves:
            if not any(other in adjacency[lid] for other in wave):
                wave.append(lid)
                break
        else:
            waves.append([lid])
    for lid in unanalyzable:
        waves.append([lid])

    plan = PartitionPlan(
        waves=tuple(tuple(w) for w in waves),
        conflicts=tuple(conflicts),
        footprints=footprints,
        serialized_unanalyzable=tuple(unanalyzable),
        hops=hops,
        shared_caller_conflicts=shared_caller_conflicts,
        unresolved_import_count=graph.unresolved_import_count,
    )
    return PartitionPlan(**{**plan.__dict__, "plan_digest": plan_digest(plan)})


def plan_to_json(plan: PartitionPlan) -> Dict[str, object]:
    """JSON-safe view of a plan (sorted, integers only)."""
    return {
        "conflicts": [
            {"lane_a": c.lane_a, "lane_b": c.lane_b, "reason": c.reason, "witness_file": c.witness_file}
            for c in plan.conflicts
        ],
        "footprint_sizes": {k: len(v) for k, v in sorted(plan.footprints.items())},
        "hops": plan.hops,
        "serialized_unanalyzable": list(plan.serialized_unanalyzable),
        "shared_caller_conflicts": plan.shared_caller_conflicts,
        "unresolved_import_count": plan.unresolved_import_count,
        "waves": [list(w) for w in plan.waves],
    }


def plan_digest(plan: PartitionPlan) -> str:
    """SHA-256 over RFC 8785 JCS of the plan view plus full footprints."""
    payload = plan_to_json(plan)
    payload["footprints"] = {k: sorted(v) for k, v in sorted(plan.footprints.items())}
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


def load_repo_files(root: Path, dirs: Sequence[str] = SCAN_DIRS) -> Dict[str, str]:
    """Read repository Python files (skips __pycache__ and broken symlinks)."""
    files: Dict[str, str] = {}
    for p in sorted(root.glob("*.py")):
        if p.is_symlink() and not p.exists():
            continue
        files[p.name] = p.read_text(encoding="utf-8", errors="replace")
    for d in dirs:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts or (p.is_symlink() and not p.exists()):
                continue
            files[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    return files


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lanes", required=True, help='JSON file: {"lane_id": ["path", ...], ...}')
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--hops", type=int, default=1)
    parser.add_argument("--shared-caller-conflicts", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    spec = json.loads(Path(args.lanes).read_text(encoding="utf-8"))
    lanes = [Lane(lane_id=k, write_set=frozenset(v)) for k, v in spec.items()]
    graph = build_import_graph(load_repo_files(root))
    plan = partition_lanes(graph, lanes, hops=args.hops, shared_caller_conflicts=args.shared_caller_conflicts)
    out = plan_to_json(plan)
    out["plan_digest"] = plan.plan_digest
    out["files_indexed"] = len(graph.forward)
    out["unparsable_files"] = len(graph.unparsable)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
