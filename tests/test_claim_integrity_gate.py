"""Tests for compliance/claim_integrity_gate.py (claim-integrity ratchet gate).

Fixtures live in tests/fixtures/claim_integrity/ and are parsed, never executed.
`bad_*` fixtures must be flagged for their rule; `clean_*` fixtures must not be.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "compliance"))

import claim_integrity_gate as cig  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "claim_integrity"
GATE = REPO_ROOT / "compliance" / "claim_integrity_gate.py"


def scan_fixture(name: str, profile: str = "metric"):
    gate = cig.ClaimIntegrityGate(REPO_ROOT)
    rel = f"tests/fixtures/claim_integrity/{name}"
    source = (REPO_ROOT / rel).read_text(encoding="utf-8")
    return gate.scan_source(rel, source, profile=profile)


def rules_of(findings):
    return sorted({f.rule for f in findings})


def test_scanner_mutation_adequacy_invariants(tmp_path):
    import ast as _ast

    # Lines 326 & 333: _is_trivial_test exact boolean return
    assert cig.ModuleAnalyzer._is_trivial_test(_ast.parse("True", mode="eval").body) is True
    assert cig.ModuleAnalyzer._is_trivial_test(_ast.parse("__name__ == '__main__'", mode="eval").body) is True
    assert cig.ModuleAnalyzer._is_trivial_test(_ast.parse("x > 0", mode="eval").body) is False

    gate = cig.ClaimIntegrityGate(REPO_ROOT)
    # Line 379: IfExp guards verdict emission in CI002
    assert gate.scan_source("src/x.py", 'def f(ok):\n    x = print("100% PASS") if ok else None\n    return x\n') == []

    # Line 420: bound_only_to_true with unbound parameter must not trigger CI006
    assert gate.scan_source("src/x.py", 'def f(flag):\n    return {"simulated": True, "passed": flag}\n') == []

    # Line 612: literal_derived BinOp depth + 1 boundary at depth=7 vs depth=8
    tree = _ast.parse("x = 1\n")
    scanner = cig.ModuleAnalyzer(gate, "src/x.py", "x = 1\n", tree, frozenset())
    assert scanner.literal_derived(_ast.parse('"a" + "b"', mode="eval").body, depth=7) is True
    assert scanner.literal_derived(_ast.parse('("a" + "b") + "c"', mode="eval").body, depth=7) is False

    # Line 640: top-level (fn is None) Name seed in CI005 must not be treated as a parameter
    top_ci005 = gate.scan_source(
        "src/x.py",
        'SEED = b"x" * 32\nEd25519PrivateKey.from_private_bytes(SEED)\n',
    )
    assert [f.rule for f in top_ci005] == ["CI005"]

    # Line 687: CI006 string on a SUCCESS_FLAG_KEYS key ("passed") in vs not in SUCCESS_STRINGS
    assert gate.scan_source("src/x.py", 'd = {"simulated": True, "passed": "FAILED"}\n') == []
    assert [f.rule for f in gate.scan_source("src/x.py", 'd = {"simulated": True, "passed": "PASS"}\n')] == ["CI006"]

    # Lines 799 & 801: in_scope checks .py suffix and top-level directory
    assert cig.ClaimIntegrityGate.in_scope("src/foo.py") is True
    assert cig.ClaimIntegrityGate.in_scope("README.md") is False
    assert cig.ClaimIntegrityGate.in_scope("unknown_root/foo.py") is False

    # Lines 838 & 840: discover_staged in a temporary git repository
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("doc\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/a.py", "README.md"], cwd=tmp_path, check=True)
    tmp_gate = cig.ClaimIntegrityGate(tmp_path)
    staged = tmp_gate.discover_staged()
    assert staged == ["src/a.py"]
    assert isinstance(tmp_gate._staged_sources["src/a.py"], str)
    assert tmp_gate._staged_sources["src/a.py"] == "x = 1\n"


# ---------------------------------------------------------------------------
# Bad fixtures: each MUST be flagged for its rule.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fixture, rule, min_count",
    [
        ("bad_ci001_metric_literal.py", "CI001", 4),
        ("bad_ci002_unconditional_verdict.py", "CI002", 4),
        ("bad_ci003_trivial_verifier.py", "CI003", 3),
        ("bad_ci004_tool_claim.py", "CI004", 1),
        ("bad_ci005_hardcoded_key.py", "CI005", 3),
        ("bad_ci006_simulated_success.py", "CI006", 2),
        ("bad_ci008_dynamic_zone_import.py", "CI008", 2),
    ],
)
def test_bad_fixture_is_flagged(fixture, rule, min_count):
    findings = [f for f in scan_fixture(fixture) if f.rule == rule]
    assert len(findings) >= min_count, f"{fixture}: expected >= {min_count} {rule} findings, got {findings}"
    assert all(f.severity == "ERROR" for f in findings)


def test_bad_ci001_snippets_name_the_metric():
    snippets = {f.snippet for f in scan_fixture("bad_ci001_metric_literal.py") if f.rule == "CI001"}
    assert "token_reduction_bps=7834" in snippets
    assert "accuracy=0.93" in snippets
    assert "latency_ms=12.5" in snippets


def test_audit_bypass_fixture_is_caught_by_claim_gate():
    """The audit sample that passed all three pre-existing gates must now be caught."""
    found = rules_of(scan_fixture("bad_audit_bypass.py"))
    for rule in ("CI001", "CI002", "CI003", "CI006", "CI008"):
        assert rule in found, f"{rule} missing from {found}"


def test_ci007_echo_assertions_are_warnings():
    findings = [f for f in scan_fixture("bad_ci007_echo_case.py", profile="test") if f.rule == "CI007"]
    assert len(findings) == 2
    assert all(f.severity == "WARN" for f in findings)


def test_profiles_scope_rules_by_path():
    gate = cig.ClaimIntegrityGate(REPO_ROOT)
    assert gate.profile_for("src/foo.py") == "metric"
    assert gate.profile_for("tools/foo.py") == "metric"
    assert gate.profile_for("compliance/foo.py") == "prod"
    assert gate.profile_for("tests/test_foo.py") == "test"
    assert gate.profile_for("test_root_level.py") == "test"
    # CI001 applies only to src/ and tools/.
    source = (FIXTURES / "bad_ci001_metric_literal.py").read_text(encoding="utf-8")
    assert "CI001" in rules_of(gate.scan_source("src/x.py", source))
    assert "CI001" not in rules_of(gate.scan_source("compliance/x.py", source))


# ---------------------------------------------------------------------------
# Clean fixtures: MUST NOT be flagged.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fixture",
    [
        "clean_computed_metrics.py",
        "clean_conditional_verdict.py",
        "clean_real_verifier.py",
        "clean_scaffold_module.py",
        "clean_tool_invocation.py",
        "clean_derived_key.py",
        "clean_honest_status.py",
    ],
)
def test_clean_fixture_not_flagged(fixture):
    findings = scan_fixture(fixture)
    assert findings == [], f"{fixture} unexpectedly flagged: {[(f.rule, f.line, f.snippet) for f in findings]}"


def test_clean_echo_case_not_flagged():
    assert scan_fixture("clean_echo_case.py", profile="test") == []


def test_claim_annotation_suppresses_ci001_only_on_that_line():
    gate = cig.ClaimIntegrityGate(REPO_ROOT)
    src = "a_ms = 250  # claim: config\nb_ms = 250\nc_rate = 0.25  # claim: assumption\n"
    findings = gate.scan_source("src/x.py", src)
    assert [(f.rule, f.line) for f in findings] == [("CI001", 2)]


# ---------------------------------------------------------------------------
# Ratchet behaviour.
# ---------------------------------------------------------------------------
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_gate(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(root), *args],
        capture_output=True, text=True, check=False,
    )


def test_ratchet_baseline_suppresses_old_and_fails_new(tmp_path):
    _write(tmp_path / "compliance" / "check_zone_boundary.py", 'ZONE2_PREFIXES = ["enterprise"]\n')
    mod = tmp_path / "src" / "legacy.py"
    _write(mod, "def report():\n    savings_usd = 4.43\n    return savings_usd\n")

    first = _run_gate(tmp_path, "--all")
    assert first.returncode == 1, first.stdout + first.stderr
    assert "CI001" in first.stdout

    upd = _run_gate(tmp_path, "--all", "--update-baseline")
    assert upd.returncode == 0, upd.stdout + upd.stderr
    baseline = json.loads((tmp_path / "compliance" / "claim_integrity_baseline.json").read_text())
    assert baseline["summary"] == {"CI001": 1}

    again = _run_gate(tmp_path, "--all")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "baseline_debt=1" in again.stdout

    # Line shifts must not invalidate the baseline (keyed by snippet hash, not line).
    _write(mod, "# moved\n\ndef report():\n    savings_usd = 4.43\n    return savings_usd\n")
    assert _run_gate(tmp_path, "--all").returncode == 0

    # A new violation fails even though the old one stays baselined.
    _write(mod, mod.read_text() + "\ndef verify_token(tok):\n    _ = tok\n    return True\n")
    new = _run_gate(tmp_path, "--all")
    assert new.returncode == 1
    assert "CI003" in new.stdout and "baseline_debt=1" in new.stdout

    # A second copy of a baselined snippet is new debt (multiplicity counted).
    _write(mod, "def report():\n    savings_usd = 4.43\n    other = {'savings_usd': 4.43}\n    return savings_usd, other\n")
    dup = _run_gate(tmp_path, "--all", "--json")
    payload = json.loads(dup.stdout)
    assert dup.returncode == 1 and payload["new_error_count"] == 1


def test_warn_findings_do_not_fail_the_gate(tmp_path):
    _write(tmp_path / "src" / "engine.py", "def compute():\n    return 7834\n")
    _write(
        tmp_path / "tests" / "test_engine.py",
        "from src.engine import compute\n\ndef test_x():\n    assert compute() == 7834\n",
    )
    res = _run_gate(tmp_path, "--all", "--json")
    payload = json.loads(res.stdout)
    assert res.returncode == 0
    assert [f["rule"] for f in payload["new"]] == ["CI007"]


def test_fixture_dir_excluded_from_all_scan():
    gate = cig.ClaimIntegrityGate(REPO_ROOT)
    rels = gate.discover_all()
    assert rels, "discovery returned nothing"
    assert not any(r.startswith("tests/fixtures/claim_integrity/") for r in rels)
    assert "compliance/claim_integrity_gate.py" not in rels
    assert "tests/test_claim_integrity_gate.py" in rels


def test_paths_mode_scans_fixture_when_explicit():
    res = subprocess.run(
        [sys.executable, str(GATE), "--paths", str(FIXTURES / "bad_ci003_trivial_verifier.py"),
         "--profile", "prod", "--baseline", str(FIXTURES / "does_not_exist.json")],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert res.returncode == 1
    assert "CI003" in res.stdout


def test_real_repo_passes_with_committed_baseline():
    """The gate over the real repository, with the recorded baseline, exits 0 (no new ERRORs)."""
    res = subprocess.run([sys.executable, str(GATE), "--all"], capture_output=True, text=True,
                         check=False, cwd=REPO_ROOT)
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]
    assert "new_errors=0" in res.stdout
