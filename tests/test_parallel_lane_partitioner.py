"""Tests for tools/parallel_lane_partitioner.py."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from tools.parallel_lane_partitioner import (
    MAX_FILE_BYTES,
    MAX_LANES,
    MAX_STRING_REF_CHARS,
    LaneConflict,
    _resolve_path,
    ImportGraph,
    Lane,
    build_import_graph,
    load_repo_files,
    main,
    partition_lanes,
    plan_to_json,
    reverse_closure,
    resolve_imports,
    tarjan_scc,
)

REPO = {
    "src/a.py": "def f(x):\n    return x\n",
    "src/b.py": "def g():\n    return 1\n",
    "src/c.py": "from src.a import f\n\ndef use():\n    return f(1)\n",
    "src/d.py": "import src.c\n",
    "src/pkg/__init__.py": "",
    "src/pkg/m.py": "from . import n\nfrom .n import K\n",
    "src/pkg/n.py": "K = 1\n",
    "src/pkg/sub/__init__.py": "",
    "src/pkg/sub/q.py": "from .. import m\nfrom ..n import K\n",
    "tests/test_c.py": "from src.c import use\n",
}


def lanes(**spec):
    return [Lane(lane_id=k, write_set=frozenset(v)) for k, v in spec.items()]


def test_resolver_absolute_relative_and_package_forms() -> None:
    known = set(REPO)
    assert resolve_imports("src/c.py", REPO["src/c.py"], known) == ({"src/a.py"}, 0)
    assert resolve_imports("src/d.py", REPO["src/d.py"], known) == ({"src/c.py"}, 0)
    # `from . import n` also executes the package __init__, so it is a dependency
    assert resolve_imports("src/pkg/m.py", REPO["src/pkg/m.py"], known) == ({"src/pkg/__init__.py", "src/pkg/n.py"}, 0)
    assert resolve_imports("src/pkg/sub/q.py", REPO["src/pkg/sub/q.py"], known) == ({"src/pkg/__init__.py", "src/pkg/m.py", "src/pkg/n.py"}, 0)
    # package import resolves to __init__, dotted submodule falls back to parent package
    assert resolve_imports("x.py", "import src.pkg\n", known)[0] == {"src/pkg/__init__.py"}
    assert resolve_imports("x.py", "import src.pkg.missing\n", known)[0] == {"src/pkg/__init__.py"}
    assert resolve_imports("x.py", "from src.pkg import m, n\n", known)[0] == {"src/pkg/__init__.py", "src/pkg/m.py", "src/pkg/n.py"}
    # stdlib / third-party are ignored, local-looking misses are counted
    assert resolve_imports("x.py", "import os, json\nfrom typing import Any\n", known) == (set(), 0)
    assert resolve_imports("x.py", "import src.nothere\nfrom src.ghost import z\n", known) == (set(), 2)
    # relative import that climbs above the root is unresolved, not guessed
    assert resolve_imports("src/a.py", "from .... import x\n", known) == (set(), 1)
    assert resolve_imports("src/pkg/m.py", "from .ghost import z\n", known) == (set(), 1)
    # self-import is dropped
    assert resolve_imports("src/c.py", "import src.c\n", known) == (set(), 0)
    with pytest.raises(SyntaxError):
        resolve_imports("bad.py", "def (:\n", known)


def test_graph_reverse_edges_unparsable_and_oversize() -> None:
    files = dict(REPO)
    files["src/bad.py"] = "def (:\n"
    files["src/huge.py"] = "x = 1\n" * (MAX_FILE_BYTES // 6 + 1)
    g = build_import_graph(files)
    assert g.forward["src/c.py"] == frozenset({"src/a.py"})
    assert g.reverse["src/a.py"] == frozenset({"src/c.py"})
    assert g.reverse["src/c.py"] == frozenset({"src/d.py", "tests/test_c.py"})
    assert g.unparsable == frozenset({"src/bad.py", "src/huge.py"})
    assert g.forward["src/bad.py"] == frozenset()
    assert g.unresolved_import_count == 0
    with pytest.raises(FrozenInstanceError):
        g.unresolved_import_count = 1  # type: ignore[misc]
    at_cap = build_import_graph({"src/edge.py": "#" * MAX_FILE_BYTES})
    assert at_cap.unparsable == frozenset()


def test_tarjan_scc_cycles_and_deep_chain() -> None:
    comps = tarjan_scc({"a": ["b"], "b": ["c"], "c": ["a"], "d": ["a"], "e": []})
    as_sets = {frozenset(c) for c in comps}
    assert frozenset({"a", "b", "c"}) in as_sets
    assert frozenset({"d"}) in as_sets and frozenset({"e"}) in as_sets
    assert len(comps) == 3
    # two separate cycles sharing an edge between them stay separate
    two = {frozenset(c) for c in tarjan_scc({"a": ["b"], "b": ["a", "c"], "c": ["d"], "d": ["c"]})}
    assert two == {frozenset({"a", "b"}), frozenset({"c", "d"})}
    # 5000-node chain: iterative implementation must not hit the recursion limit
    chain = {f"n{i}": [f"n{i + 1}"] for i in range(5000)}
    chain["n5000"] = ["n0"]
    deep = tarjan_scc(chain)
    assert len(deep) == 1 and len(deep[0]) == 5001


def test_reverse_closure_hops() -> None:
    g = build_import_graph(REPO)
    assert reverse_closure(g, ["src/a.py"], 0) == frozenset()
    assert reverse_closure(g, ["src/a.py"], 1) == frozenset({"src/c.py"})
    assert reverse_closure(g, ["src/a.py"], 2) == frozenset({"src/c.py", "src/d.py", "tests/test_c.py"})
    assert reverse_closure(g, ["src/a.py"], -1) == frozenset({"src/c.py", "src/d.py", "tests/test_c.py"})
    assert reverse_closure(g, ["src/new_file.py"], 1) == frozenset()


def test_disjoint_writes_but_caller_dependency_is_serialized() -> None:
    """The trap: lane A changes f() in a.py, lane B edits c.py which calls f()."""
    g = build_import_graph(REPO)
    plan = partition_lanes(g, lanes(A=["src/a.py"], B=["src/c.py"]))
    assert plan.waves == (("A",), ("B",))
    assert [(c.lane_a, c.lane_b, c.reason, c.witness_file) for c in plan.conflicts] == [("A", "B", "B_WRITES_A_DEPENDENT", "src/c.py")]
    flipped = partition_lanes(g, lanes(A=["src/c.py"], B=["src/a.py"]))
    assert flipped.conflicts[0].reason == "A_WRITES_B_DEPENDENT"

    independent = partition_lanes(g, lanes(A=["src/a.py"], B=["src/b.py"]))
    assert independent.waves == (("A", "B"),)
    assert independent.conflicts == ()

    overlap = partition_lanes(g, lanes(A=["src/a.py", "src/b.py"], B=["src/b.py"]))
    assert overlap.conflicts[0].reason == "WRITE_WRITE_OVERLAP"
    assert overlap.conflicts[0].witness_file == "src/b.py"


def test_hops_and_shared_caller_policy() -> None:
    g = build_import_graph(REPO)
    # d.py depends on a.py only transitively (d -> c -> a)
    one_hop = partition_lanes(g, lanes(A=["src/a.py"], B=["src/d.py"]), hops=1)
    assert one_hop.waves == (("A", "B"),)
    two_hop = partition_lanes(g, lanes(A=["src/a.py"], B=["src/d.py"]), hops=2)
    assert two_hop.waves == (("A",), ("B",))
    assert partition_lanes(g, lanes(A=["src/a.py"], B=["src/d.py"]), hops=-1).waves == (("A",), ("B",))

    shared = {
        "src/x.py": "X = 1\n",
        "src/y.py": "Y = 1\n",
        "src/user.py": "from src.x import X\nfrom src.y import Y\n",
    }
    sg = build_import_graph(shared)
    default = partition_lanes(sg, lanes(A=["src/x.py"], B=["src/y.py"]))
    assert default.waves == (("A", "B"),)
    assert default.shared_caller_conflicts is False
    strict = partition_lanes(sg, lanes(A=["src/x.py"], B=["src/y.py"]), shared_caller_conflicts=True)
    assert strict.waves == (("A",), ("B",))
    assert (strict.conflicts[0].reason, strict.conflicts[0].witness_file) == ("SHARED_UNTOUCHED_CALLER", "src/user.py")


def test_cycle_expansion_and_fail_closed_unanalyzable() -> None:
    files = {
        "src/p.py": "import src.q\n",
        "src/q.py": "import src.p\n",
        "src/r.py": "R = 1\n",
        "src/bad.py": "def (:\n",
    }
    g = build_import_graph(files)
    # writing p.py touches the whole p<->q cycle, so a lane writing q.py overlaps
    plan = partition_lanes(g, lanes(A=["src/p.py"], B=["src/q.py"]))
    assert plan.conflicts[0].reason == "WRITE_WRITE_OVERLAP"
    assert plan.footprints["A"] == frozenset()  # cycle members are writes, not callers

    fc = partition_lanes(g, lanes(A=["src/bad.py"], B=["src/r.py"], C=["src/p.py"]))
    assert fc.serialized_unanalyzable == ("A",)
    assert fc.waves == (("B", "C"), ("A",))


def test_greedy_waves_deterministic_and_digest() -> None:
    g = build_import_graph(REPO)
    spec = dict(A=["src/a.py"], B=["src/b.py"], C=["src/c.py"], D=["src/pkg/n.py"], E=["src/pkg/m.py"])
    plan = partition_lanes(g, lanes(**spec))
    # A-C conflict, D-E conflict (m imports n); greedy by id
    assert plan.waves == (("A", "B", "D"), ("C", "E"))
    again = partition_lanes(g, list(reversed(lanes(**spec))))
    assert again.waves == plan.waves
    assert again.plan_digest == plan.plan_digest
    assert len(plan.plan_digest) == 64
    other = partition_lanes(g, lanes(**spec), hops=2)
    assert other.plan_digest != plan.plan_digest
    view = plan_to_json(plan)
    assert view["waves"] == [["A", "B", "D"], ["C", "E"]]
    assert view["footprint_sizes"]["A"] == 1
    assert view["hops"] == 1


def test_input_validation() -> None:
    g = build_import_graph(REPO)
    with pytest.raises(ValueError, match="ERR_DUPLICATE_LANE_ID"):
        partition_lanes(g, [Lane("A", frozenset()), Lane("A", frozenset())])
    with pytest.raises(ValueError, match="ERR_INVALID_HOPS"):
        partition_lanes(g, lanes(A=["src/a.py"]), hops=-2)
    many = [Lane(f"L{i:03d}", frozenset({f"src/new{i}.py"})) for i in range(MAX_LANES)]
    assert len(partition_lanes(g, many).waves) == 1
    with pytest.raises(ValueError, match="ERR_TOO_MANY_LANES"):
        partition_lanes(g, many + [Lane("extra", frozenset())])
    assert partition_lanes(g, []).waves == ()
    assert isinstance(g, ImportGraph)


def test_cli_and_loader(tmp_path, capsys) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "a.py").write_text("def f():\n    pass\n")
    (tmp_path / "src" / "c.py").write_text("from src.a import f\n")
    (tmp_path / "src" / "__pycache__" / "junk.py").write_text("x=1\n")
    files = load_repo_files(tmp_path)
    assert sorted(files) == ["src/a.py", "src/c.py"]
    lanes_file = tmp_path / "lanes.json"
    lanes_file.write_text(json.dumps({"A": ["src/a.py"], "B": ["src/c.py"]}))
    assert main(["--lanes", str(lanes_file), "--root", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["waves"] == [["A"], ["B"]]
    assert out["files_indexed"] == 2
    assert out["unparsable_files"] == 0
    assert len(out["plan_digest"]) == 64


def test_bare_name_imports_via_sys_path_roots() -> None:
    """Regression: `from sovereign_search import X` with src/ on sys.path was invisible."""
    files = {
        "src/sovereign_search.py": "X = 1\n",
        "scripts/research.py": "from sovereign_search import X\n",
        "v1.1-roadmap/harness.py": "from .helpers import H\nH2 = 1\n",
        "v1.1-roadmap/helpers.py": "H = 1\n",
        "tests/test_h.py": "from harness import H2\nimport sovereign_search\nfrom ghost_local import z\n",
        "tests/ghost_local_notes.py": "",
        "tools/t.py": "import harness.sub\n",
    }
    known = set(files)
    assert resolve_imports("scripts/research.py", files["scripts/research.py"], known) == ({"src/sovereign_search.py"}, 0)
    deps, unresolved = resolve_imports("tests/test_h.py", files["tests/test_h.py"], known)
    assert deps == {"v1.1-roadmap/harness.py", "src/sovereign_search.py"}
    assert unresolved == 0  # ghost_local is not a local stem (ghost_local_notes is)
    assert resolve_imports("x.py", "from ghost_local_notes.deep import q\n", known) == (set(), 1)
    # tests/ is not an import root, so a bare name matching a tests/ stem is unresolved (counted)
    assert resolve_imports("x.py", "import ghost_local_notes.deep\n", known) == (set(), 1)
    # relative import inside a directory whose name contains dots
    assert resolve_imports("v1.1-roadmap/harness.py", files["v1.1-roadmap/harness.py"], known) == ({"v1.1-roadmap/helpers.py"}, 0)
    # submodule miss falls back to the parent module and is not double counted
    assert resolve_imports("tools/t.py", files["tools/t.py"], known) == ({"v1.1-roadmap/harness.py"}, 0)
    g = build_import_graph(files)
    assert reverse_closure(g, ["src/sovereign_search.py"], 1) == frozenset({"scripts/research.py", "tests/test_h.py"})
    plan = partition_lanes(g, lanes(A=["src/sovereign_search.py"], B=["scripts/research.py"]))
    assert plan.waves == (("A",), ("B",))


def test_loader_includes_root_level_and_extra_dirs(tmp_path) -> None:
    (tmp_path / "aeib_verify.py").write_text("import src.a\n")
    for d in ("src", "scripts", "compliance", "v1.1-roadmap", "docs"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "m.py").write_text("x = 1\n")
    files = load_repo_files(tmp_path)
    assert sorted(files) == ["aeib_verify.py", "compliance/m.py", "scripts/m.py", "src/m.py", "v1.1-roadmap/m.py"]


def test_string_references_are_conservative_dependencies() -> None:
    files = {
        "src/a.py": "X = 1\n",
        "scripts/run.py": "print(1)\n",
        "src/c.py": (
            "import importlib\n"
            "m = importlib.import_module('src.a')\n"
            "n = __import__('src.a')\n"
            "PLUG = ['src.a']\n"
            "CMD = ['python3', 'scripts/run.py']\n"
            "NOISE = ['json.dumps', 'src', 'src.a ', 'x' * 3, 'scripts/run', 'src/a']\n"
        ),
    }
    known = set(files)
    assert resolve_imports("src/c.py", files["src/c.py"], known) == ({"src/a.py", "scripts/run.py"}, 0)
    assert resolve_imports("x.py", "S = 'src.a.py'\n", known) == (set(), 0)
    assert resolve_imports("x.py", "S = 'src.' + 'a'\n", known) == (set(), 0)  # only whole literals
    long_ref = "src." + "a" * 300
    assert resolve_imports("x.py", f"S = '{long_ref}'\n", known) == (set(), 0)
    g = build_import_graph(files)
    assert partition_lanes(g, lanes(A=["src/a.py"], B=["src/c.py"])).waves == (("A",), ("B",))
    assert partition_lanes(g, lanes(A=["scripts/run.py"], B=["src/c.py"])).waves == (("A",), ("B",))


def test_configured_limits_and_frozen_records() -> None:
    assert (MAX_FILE_BYTES, MAX_LANES, MAX_STRING_REF_CHARS) == (2_000_000, 64, 256)
    lane = Lane("A", frozenset())
    with pytest.raises(FrozenInstanceError):
        lane.lane_id = "B"  # type: ignore[misc]
    conflict = LaneConflict("A", "B", "WRITE_WRITE_OVERLAP", "x")
    with pytest.raises(FrozenInstanceError):
        conflict.reason = "X"  # type: ignore[misc]
    plan = partition_lanes(build_import_graph(REPO), lanes(A=["src/a.py"]))
    with pytest.raises(FrozenInstanceError):
        plan.waves = ()  # type: ignore[misc]


def test_path_and_string_reference_guards() -> None:
    assert _resolve_path("", {".py"}) is None
    assert _resolve_path("src/", {"src/.py", "src//__init__.py"}) is None
    assert _resolve_path("src/a", {"src/a.py"}) == "src/a.py"
    assert _resolve_path("src/pkg", {"src/pkg/__init__.py"}) == "src/pkg/__init__.py"
    # whitespace in a literal blocks resolution even when a matching file exists
    spaced = {"src/my mod.py": "", "src/x.py": ""}
    assert resolve_imports("q.py", "S = 'src.my mod'\n", set(spaced)) == (set(), 0)
    assert resolve_imports("q.py", "S = 'src/my mod.py'\n", set(spaced)) == (set(), 0)
    # length boundary: dotted literal of exactly MAX_STRING_REF_CHARS resolves, one more does not
    stem_ok = "m" * (MAX_STRING_REF_CHARS - len("src."))
    stem_long = stem_ok + "m"
    known = {f"src/{stem_ok}.py", f"src/{stem_long}.py"}
    assert resolve_imports("q.py", f"S = 'src.{stem_ok}'\n", known) == ({f"src/{stem_ok}.py"}, 0)
    assert resolve_imports("q.py", f"S = 'src.{stem_long}'\n", known) == (set(), 0)
    # one resolved name in a from-import suppresses the unresolved count
    pk = {"src/pkg/__init__.py": "", "src/pkg/m.py": ""}
    assert resolve_imports("q.py", "from src.pkg import m, ghost\n", set(pk)) == ({"src/pkg/__init__.py", "src/pkg/m.py"}, 0)
    assert resolve_imports("q.py", "from srcz import m\n", {"srcz/m.py"}) == ({"srcz/m.py"}, 0)
    assert resolve_imports("q.py", "from srcz import ghost\n", {"srcz/m.py"}) == (set(), 1)


def test_cli_defaults_and_script_entrypoint(tmp_path, capsys) -> None:
    import subprocess
    import sys as _sys
    from pathlib import Path

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("X = 1\n")
    lanes_file = tmp_path / "lanes.json"
    lanes_file.write_text(json.dumps({"A": ["src/a.py"]}))
    assert main(["--lanes", str(lanes_file), "--root", str(tmp_path)]) == 0
    raw = capsys.readouterr().out
    assert raw.startswith('{\n  "conflicts": []')  # indent=2, sorted keys
    keys = list(json.loads(raw))
    assert keys == sorted(keys)
    assert json.loads(raw)["hops"] == 1
    with pytest.raises(SystemExit) as missing:
        main(["--root", str(tmp_path)])
    assert missing.value.code == 2

    # run as a script from an unrelated cwd: needs the REPO_ROOT sys.path bootstrap
    script = Path(__file__).resolve().parents[1] / "tools" / "parallel_lane_partitioner.py"
    proc = subprocess.run(
        [_sys.executable, str(script), "--lanes", str(lanes_file), "--root", str(tmp_path), "--hops", "-1"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, env={"PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert json.loads(proc.stdout)["hops"] == -1
    help_proc = subprocess.run([_sys.executable, str(script), "--help"], cwd=tmp_path, capture_output=True, text=True, timeout=60, env={"PATH": "/usr/bin:/bin"})
    assert "Deterministic parallel-lane partitioner" in help_proc.stdout
