"""
Tests for RepoReverseEngineeringEngine (v1.0.0).

Verifies AST topology extraction, cargo-cult flaw detection,
disproving reverse-engineer oracle, and Ed25519 cryptographic signing.
Strictly conforms to AGENTS.md epistemic rules.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import re
import pytest

from src.repo_reverse_engineering_engine import (
    AntiCargoCultScanner,
    DisprovingReverseEngineerOracle,
    FrontierInvariantSynthesizer,
    RepoASTTopologyExtractor,
    RepoReverseEngineeringEngine,
    encode_jcs,
    sha256_jcs,
    verify_synthesis_report,
    CargoCultVulnerability,
    RepoTopologySummary,
    DistilledInvariantCandidate,
    FalsificationOracleReceipt,
    ReverseEngineeringSynthesisReport,
    DEFAULT_CORRUPT_PROBES,
)


def test_1_ast_topology_extractor() -> None:
    code = '''
class EscrowStateMachine:
    def __init__(self):
        self.state = "INIT"

class OrdinaryDataHolder:
    pass

def main():
    pass

def run():
    pass

def entrypoint():
    pass

def cli():
    pass

def worker():
    pass

async def async_fetch():
    pass

def helper(x):
    return x + 1
'''
    extractor = RepoASTTopologyExtractor()
    empty = extractor.build_summary()
    assert (empty.total_files_scanned, empty.total_ast_nodes, empty.function_definitions_count,
            empty.class_definitions_count, empty.async_functions_count,
            empty.external_call_sites_count) == (0, 0, 0, 0, 0, 0)
    assert empty.entry_points == () and empty.identified_state_machines == ()
    extractor.scan_source_text("example.py", code)
    # Also scan an invalid file to test syntax error resilience
    extractor.scan_source_text("bad.py", "def bad(x: pass")

    summary = extractor.build_summary()
    assert summary.total_files_scanned == 1
    assert summary.class_definitions_count == 2
    assert summary.function_definitions_count == 7  # __init__, main, run, entrypoint, cli, worker, helper
    assert summary.async_functions_count == 1
    assert len(summary.entry_points) == 4
    assert summary.entry_points == (
        "example.py:main",
        "example.py:run",
        "example.py:entrypoint",
        "example.py:cli",
    )
    assert "example.py:worker" not in summary.entry_points
    assert "example.py:helper" not in summary.entry_points
    assert len(summary.identified_state_machines) == 1
    assert summary.identified_state_machines == ("example.py:EscrowStateMachine",)
    assert "example.py:OrdinaryDataHolder" not in summary.identified_state_machines


def test_2_anti_cargo_cult_scanner_catches_flaws() -> None:
    bad_code = '''
def verify_claim(x):
    return True

def check_boundary(x):
    return True

def validate_input(x):
    return True

def gate_execution(x):
    return True

def normal_function(x):
    return False

def innocent_calculation(x):
    return True

def mock_worker():
    pass

def dangerous_exec(user_input):
    eval(user_input)

def test_something():
    x = 10
    assert x == 42
    assert 42 == x
    assert True
    assert 42 == 42
    assert 42 != 43
    assert 42 == 43

def naive_firewall(prompt):
    if "admin" in prompt:
        return False
    return True
'''
    scanner = AntiCargoCultScanner()
    flaws = scanner.scan_file("test_vulns.py", bad_code)

    codes = [f.vulnerability_code for f in flaws]
    assert "MOCK_PASS_GATE" in codes
    assert "UNSAFE_DYNAMIC_EVAL" in codes
    assert "TAUTOLOGICAL_TEST_ASSERTION" in codes
    assert "PROMPT_ONLY_SCAFFOLD" in codes

    mock_flaws = [f for f in flaws if f.vulnerability_code == "MOCK_PASS_GATE"]
    assert len(mock_flaws) == 5  # 4 verifiers returning True + 1 pass stub
    tautological_flaws = [f for f in flaws if f.vulnerability_code == "TAUTOLOGICAL_TEST_ASSERTION"]
    assert len(tautological_flaws) == 2  # assert True and assert 42 == 42
    assert "assert 42 == 42" in tautological_flaws[1].description
    assert "assert 42 == 43" not in [f.description for f in tautological_flaws]

    # Test line number 1 check for line scanner
    line1_flaws = scanner.scan_file("line1.py", 'if "admin" in prompt: pass\n')
    assert len(line1_flaws) == 1
    assert line1_flaws[0].line_number == 1

    # Test syntax error scanner handling
    syntax_flaws = scanner.scan_file("syntax.py", "def broken(:")
    assert len(syntax_flaws) == 1
    assert syntax_flaws[0].vulnerability_code == "SYNTAX_ERROR"
    assert syntax_flaws[0].line_number == 1
    late_error = scanner.scan_file("late.py", "x = 1\ny = 2\ndef broken(:\n")
    assert late_error[0].line_number == 3
    assert len(scanner.scan_file("lt.py", "def test_lt():\n    assert 1 < 1\n")) == 0

    # Call-site counting: exactly 3 calls in this snippet.
    ext = RepoASTTopologyExtractor()
    ext.scan_source_text("calls.py", "a = f()\nb = g(h())\n")
    assert ext.build_summary().external_call_sites_count == 3

    # JCS keeps non-ASCII keys as raw UTF-8 (RFC 8785), not \\u escapes.
    assert encode_jcs({"ключ": 1}) == '{"ключ":1}'.encode("utf-8")
    # RFC 8785 sorts by UTF-16 code units: U+1F600 (surrogate D83D) sorts BEFORE U+FFFF.
    assert encode_jcs({"\uffff": 1, "\U0001F600": 2}) == '{"\U0001F600":2,"\uffff":1}'.encode("utf-8")


def test_3_disproving_oracle_flags_cargo_cult_and_validates_sound() -> None:
    oracle = DisprovingReverseEngineerOracle()

    # Flawed candidate that claims to be a payment gate but accepts overdrafts & negatives
    flawed_code = '''
def process_payment(req):
    # Buggy: no check for negative amount or balance overdraft
    return {"success": True, "new_balance": req.get("balance", 0) - req.get("amount", 0)}
'''
    flawed_receipt = oracle.evaluate_candidate(flawed_code, "process_payment", "overdraft_injection")
    assert flawed_receipt.disproved_as_cargo_cult is True
    assert flawed_receipt.mutant_detected_by_gate is False

    # Candidate that literally returns True
    true_code = '''
def process_payment(req):
    return True
'''
    true_receipt = oracle.evaluate_candidate(true_code, "process_payment", "overdraft_injection")
    assert true_receipt.disproved_as_cargo_cult is True
    assert true_receipt.mutant_detected_by_gate is False

    # Sound candidate that fails closed on invalid inputs
    sound_code = '''
def process_payment(req):
    amount = req.get("amount")
    balance = req.get("balance")
    if amount is None or balance is None or amount <= 0 or balance < amount:
        raise ValueError("ERR_INVALID_PAYMENT")
    return {"success": True, "new_balance": balance - amount}
'''
    sound_receipt = oracle.evaluate_candidate(sound_code, "process_payment", "overdraft_injection")
    assert sound_receipt.disproved_as_cargo_cult is False
    assert sound_receipt.mutant_detected_by_gate is True

    # Assert exact default probe structures
    assert len(DEFAULT_CORRUPT_PROBES) == 4
    assert DEFAULT_CORRUPT_PROBES[0] == {"amount": -100, "balance": 50}
    assert DEFAULT_CORRUPT_PROBES[1] == {"amount": 0, "balance": 0}
    assert DEFAULT_CORRUPT_PROBES[2] == {}
    assert DEFAULT_CORRUPT_PROBES[3] == {"amount": 1000, "balance": 10}

    # Candidate with exactly 1 failure (rejects negative, rejects overdraft, but accepts empty dict)
    single_fail_code = '''
def process_payment(req):
    if not req:
        return {"success": True, "new_balance": 0}
    amount = req.get("amount", 0)
    balance = req.get("balance", 0)
    if amount <= 0 or balance < amount:
        raise ValueError("ERR")
    return {"success": True, "new_balance": balance - amount}
'''
    single_fail_receipt = oracle.evaluate_candidate(single_fail_code, "process_payment", "overdraft_injection")
    assert single_fail_receipt.disproved_as_cargo_cult is True
    assert single_fail_receipt.mutant_detected_by_gate is False
    assert "Accepted 1 of 4 corrupt inputs" in single_fail_receipt.diagnostic_trace

    # Isolation check: candidate code runs in a child process, so it cannot
    # mutate this test process's state.
    import os as _os
    marker = "AEIB_REA_ISOLATION_MARKER"
    _os.environ.pop(marker, None)
    leak_code = (
        "import os\n"
        f"os.environ['{marker}'] = '1'\n"
        "def process_payment(req):\n"
        "    raise ValueError('reject')\n"
    )
    leak_receipt = oracle.evaluate_candidate(leak_code, "process_payment", "isolation")
    assert leak_receipt.disproved_as_cargo_cult is False
    assert marker not in _os.environ

    # Non-terminating candidate is cut off by the timeout instead of hanging.
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process
    hang = _run_probes_in_child_process("while True:\n    pass\n", "f", DEFAULT_CORRUPT_PROBES, timeout_s=1.0)
    assert hang["status"] == "timeout"

    # Child exits abnormally -> harness_error, and the oracle flags it (never passes it).
    crash = _run_probes_in_child_process("import os\nos._exit(3)\n", "f", DEFAULT_CORRUPT_PROBES)
    assert crash["status"] == "harness_error"
    crash_receipt = oracle.evaluate_candidate("import os\nos._exit(3)\n", "f", "crash")
    assert crash_receipt.disproved_as_cargo_cult is True
    assert crash_receipt.mutant_detected_by_gate is False
    assert "harness_error" in crash_receipt.diagnostic_trace

    # Verify 300-char stderr tail slice and 16-byte secrets.token_hex invocation
    import secrets as _secrets

    orig_tok_hex = _secrets.token_hex
    seen_nbytes = []

    def _checked_token_hex(nbytes: int = 32) -> str:
        seen_nbytes.append(nbytes)
        if nbytes != 16:
            raise ValueError(f"Expected 16 bytes, got {nbytes}")
        return orig_tok_hex(nbytes)

    _secrets.token_hex = _checked_token_hex  # type: ignore[assignment]
    try:
        stderr_300 = _run_probes_in_child_process(
            "import os, sys\nsys.stderr.write('P' + ('E' * 300))\nsys.stderr.flush()\nos._exit(3)\n",
            "f",
            DEFAULT_CORRUPT_PROBES,
        )
    finally:
        _secrets.token_hex = orig_tok_hex  # type: ignore[assignment]
    assert seen_nbytes == [16]
    assert stderr_300["status"] == "harness_error"
    assert "P" not in stderr_300["detail"]
    assert ("E" * 300) in stderr_300["detail"]

    # Direct child-runner contract for the ok / missing / not_callable / load_error statuses.
    ok = _run_probes_in_child_process(sound_code, "process_payment", DEFAULT_CORRUPT_PROBES)
    assert ok == {"status": "ok", "results": ["rejected", "rejected", "rejected", "rejected"]}
    assert _run_probes_in_child_process("x = 1", "nope", DEFAULT_CORRUPT_PROBES) == {"status": "missing"}
    assert _run_probes_in_child_process("x = 1", "x", DEFAULT_CORRUPT_PROBES) == {"status": "not_callable"}
    assert _run_probes_in_child_process("def broken(:", "f", DEFAULT_CORRUPT_PROBES)["status"] == "load_error"

    missing_r = oracle.evaluate_candidate("x = 10", "nonexistent_fn", "test")
    assert missing_r.mutant_detected_by_gate is False
    load_r = oracle.evaluate_candidate("def broken(:", "foo", "syntax")
    assert load_r.mutant_detected_by_gate is False
    assert load_r.mutant_injected == "nominal_parse"

    # Red-team a6: candidate prints a forged "all rejected" verdict and hard-exits.
    forged = (
        "import json, os, sys\n"
        "sys.stdout.write(json.dumps({'status': 'ok', 'results': ['rejected']*4}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "os._exit(0)\n"
    )
    forged_raw = _run_probes_in_child_process(forged, "f", DEFAULT_CORRUPT_PROBES)
    assert forged_raw["status"] == "harness_error"
    forged_receipt = oracle.evaluate_candidate(forged, "f", "forged_verdict")
    assert forged_receipt.disproved_as_cargo_cult is True
    assert forged_receipt.mutant_detected_by_gate is False

    # Missing symbol in scope
    missing_receipt = oracle.evaluate_candidate("x = 10", "nonexistent_fn", "test")
    assert missing_receipt.disproved_as_cargo_cult is True
    assert "symbol_missing" in missing_receipt.mutant_injected

    # Non-callable or unparseable target
    broken_receipt = oracle.evaluate_candidate("def broken(:", "foo", "syntax")
    assert broken_receipt.disproved_as_cargo_cult is True

    noncallable_receipt = oracle.evaluate_candidate("x = 42", "x", "noncallable")
    assert noncallable_receipt.disproved_as_cargo_cult is True
    assert noncallable_receipt.mutant_detected_by_gate is False
    assert noncallable_receipt.diagnostic_trace == "Target symbol is not callable."


def test_4_end_to_end_synthesis_report_and_signature_verification() -> None:
    engine = RepoReverseEngineeringEngine()

    files = {
        "engine.py": """
class AgentStateMachine:
    def __init__(self):
        self.state = "READY"

def run():
    pass
""",
        "safety.py": """
def check_gate(x):
    return True
""",
    }

    report = engine.analyze_repository("TrendingAgentRepo", files)
    assert report.target_name == "TrendingAgentRepo"
    assert report.topology.total_files_scanned == 2
    assert len(report.cargo_cult_flaws) >= 1
    assert len(report.distilled_invariants) == 4

    # Test invariant bps thresholds under mock flaw vs clean
    inv_map = {inv.invariant_id: inv for inv in report.distilled_invariants}
    assert inv_map["INV_DURABLE_INTENT_WAL"].suggested_bps_threshold == 10000
    assert inv_map["INV_ZERO_MOCK_DISCIPLINE"].suggested_bps_threshold == 10000
    assert inv_map["INV_DUAL_POLARITY_BMC"].suggested_bps_threshold == 10000
    assert inv_map["INV_HOMEOSTATIC_SENTINEL"].suggested_bps_threshold == 62 * 100

    # Invariants synthesized on a clean repo (no mock flaws)
    clean_invariants = FrontierInvariantSynthesizer().synthesize_invariants(report.topology, [])
    clean_map = {inv.invariant_id: inv for inv in clean_invariants}
    assert clean_map["INV_ZERO_MOCK_DISCIPLINE"].suggested_bps_threshold == 95 * 100

    # Test report falsification oracle defaults
    assert report.falsification_oracle.mutant_detected_by_gate is True
    assert report.falsification_oracle.disproved_as_cargo_cult is False

    # Verify Ed25519 signature
    assert verify_synthesis_report(report) is True

    # Tampered report verification fails
    tampered_report = dataclasses.replace(report, digest_sha256="0" * 64)
    assert verify_synthesis_report(tampered_report) is False

    # Dataclass frozenness assertions to kill mutmut constant mutants
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.target_name = "Tampered"  # type: ignore

    with pytest.raises(dataclasses.FrozenInstanceError):
        report.topology.total_files_scanned = 99  # type: ignore

    # RFC 8785 JCS encoding tests including UTF-8 preservation
    utf8_encoded = encode_jcs("привет")
    assert utf8_encoded == b'"\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82"'
    assert b"\\u043f" not in utf8_encoded

    with pytest.raises(ValueError, match="ERR_FLOAT_IN_JCS"):
        encode_jcs({"score": 99.5})

    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY_IN_JCS"):
        encode_jcs({1: "bad"})

    with pytest.raises(TypeError, match="ERR_UNSUPPORTED_TYPE_IN_JCS"):
        encode_jcs(object())

    # SHA-256 JCS helper
    digest = sha256_jcs({"a": 1, "b": [2, 3]})
    assert len(digest) == 64


def test_5_epistemic_linguistic_compliance() -> None:
    src_file = Path("src/repo_reverse_engineering_engine.py")
    test_file = Path("tests/test_repo_reverse_engineering_engine.py")

    banned_patterns = [
        r"\bguaran(?:tee|teed|tees|teeing)\b",
        r"\bproven\s+universally\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100%\s+secure\b",
        r"\bunassailable\b",
        r"\bimmune\b",
        r"\bunhackable\b",
        r"\bbank-grade\b",
        r"\bproduction-ready\b",
    ]

    for fpath in (src_file, test_file):
        text = fpath.read_text(encoding="utf-8")
        for pat in banned_patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            assert len(matches) == 0, f"Banned pattern '{pat}' found in {fpath}: {matches}"


# ---------------------------------------------------------------------------
# Seatbelt wrapping of the child oracle (red-team a6 rows 1 and 2). Real
# /usr/bin/sandbox-exec, real files, real local TCP listener; no mocks. Each
# denial assertion is paired with a process_isolation_only control showing the
# same candidate succeeds without Seatbelt.
# ---------------------------------------------------------------------------
from src.seatbelt_sandbox import seatbelt_available as _seatbelt_available  # noqa: E402

_requires_seatbelt = pytest.mark.skipif(
    not _seatbelt_available(), reason="macOS /usr/bin/sandbox-exec not available on this host"
)


def test_6_seatbelt_required_fails_closed_when_unavailable(tmp_path: Path) -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    marker = tmp_path / "must_not_exist.txt"
    code = f"open({str(marker)!r}, 'w').write('x')\ndef f(p):\n    return True\n"
    res = _run_probes_in_child_process(
        code, "f", DEFAULT_CORRUPT_PROBES[:1],
        sandbox="seatbelt_required", sandbox_exec_path=str(tmp_path / "no-sandbox-exec"),
    )
    assert res == {"status": "harness_error", "detail": "SEATBELT_UNAVAILABLE"}
    assert not marker.exists()  # the candidate never ran
    bad_mode = _run_probes_in_child_process(code, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox="off")
    assert bad_mode == {"status": "harness_error", "detail": "INVALID_SANDBOX_MODE"}
    assert not marker.exists()
    # "auto" with an unavailable sandbox-exec falls back to process isolation (documented).
    auto = _run_probes_in_child_process(
        code, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox="auto",
        sandbox_exec_path=str(tmp_path / "no-sandbox-exec"),
    )
    assert auto == {"status": "ok", "results": ["accepted"]}
    assert marker.read_text() == "x"


@_requires_seatbelt
def test_7_seatbelt_denies_writes_outside_temp_cwd(tmp_path: Path) -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    marker = tmp_path / "escape_marker.txt"
    code = (
        "import os\n"
        "def f(p):\n"
        "    open('inside_cwd.txt', 'w').write('ok')\n"
        "    assert open('inside_cwd.txt').read() == 'ok'\n"
        f"    open({str(marker)!r}, 'w').write('escaped')\n"
        "    return True\n"
    )
    for mode in ("auto", "seatbelt_required"):
        res = _run_probes_in_child_process(code, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox=mode)
        # PermissionError from the denied write is classified as "rejected".
        assert res == {"status": "ok", "results": ["rejected"]}, (mode, res)
        assert not marker.exists()
    # Control: without Seatbelt the same candidate escapes its temp cwd.
    ctrl = _run_probes_in_child_process(
        code, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox="process_isolation_only"
    )
    assert ctrl == {"status": "ok", "results": ["accepted"]}
    assert marker.read_text() == "escaped"


@_requires_seatbelt
def test_8_seatbelt_denies_network_from_child() -> None:
    import socket

    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]
    code = (
        "import socket\n"
        "def f(p):\n"
        f"    socket.create_connection(('127.0.0.1', {port}), timeout=3).close()\n"
        "    return True\n"
    )
    try:
        denied = _run_probes_in_child_process(code, "f", DEFAULT_CORRUPT_PROBES[:1])
        assert denied == {"status": "ok", "results": ["rejected"]}
        ctrl = _run_probes_in_child_process(
            code, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox="process_isolation_only"
        )
        assert ctrl == {"status": "ok", "results": ["accepted"]}
    finally:
        srv.close()


@_requires_seatbelt
def test_9_seatbelt_child_still_runs_normal_candidates() -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    # Interpreter + stdlib remain readable under the profile (json/hashlib imports work).
    code = (
        "import json, hashlib, decimal\n"
        "def f(p):\n"
        "    if p.get('amount', 0) <= 0:\n"
        "        raise ValueError('bad')\n"
        "    return {'success': hashlib.sha256(json.dumps(p).encode()).hexdigest() != ''}\n"
    )
    res = _run_probes_in_child_process(code, "f", DEFAULT_CORRUPT_PROBES, sandbox="seatbelt_required")
    assert res == {"status": "ok", "results": ["rejected", "rejected", "rejected", "accepted"]}


# ---------------------------------------------------------------------------
# Parent-side RSS watchdog (macOS does not enforce RLIMIT_AS). Real child
# processes, real allocations; no mocks. Red-team a6 "512MiB alloc" regression.
# ---------------------------------------------------------------------------
_HOLD_96MIB_2S = (
    "import time\n"
    "def f(p):\n"
    "    x = bytearray(96 * 1024 * 1024)\n"
    "    time.sleep(2)\n"
    "    return True\n"
)
_SPIKE_96MIB = (
    "def f(p):\n"
    "    x = bytearray(96 * 1024 * 1024)\n"
    "    del x\n"
    "    return True\n"
)
_BOUNDED = "def f(p):\n    return sum(i * i for i in range(100000)) > 0\n"


@pytest.mark.parametrize("mode", ["auto", "process_isolation_only"])
def test_10_rss_watchdog_kills_held_allocation_over_cap(mode: str) -> None:
    import time as _time

    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    t0 = _time.monotonic()
    res = _run_probes_in_child_process(
        _HOLD_96MIB_2S, "f", DEFAULT_CORRUPT_PROBES[:1], max_rss_mib=32, sandbox=mode
    )
    elapsed = _time.monotonic() - t0
    assert res["status"] == "HALT_CHILD_RSS_LIMIT_EXCEEDED", res
    assert type(res["peak_rss_kib"]) is int and res["peak_rss_kib"] > 32 * 1024
    assert res["max_rss_kib"] == 32 * 1024
    assert res["detail"] == f"peak_rss_kib={res['peak_rss_kib']} > max_rss_kib={32 * 1024}"
    # Killed while holding the allocation, not after the 2 s sleep finished.
    assert elapsed < 1.5, elapsed


def test_11_rss_watchdog_post_exit_peak_catches_short_spike() -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    res = _run_probes_in_child_process(_SPIKE_96MIB, "f", DEFAULT_CORRUPT_PROBES[:1], max_rss_mib=32)
    assert res["status"] == "HALT_CHILD_RSS_LIMIT_EXCEEDED", res
    assert res["peak_rss_kib"] > 32 * 1024


def test_12_bounded_computation_passes_under_cap() -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    for mode in ("auto", "process_isolation_only"):
        res = _run_probes_in_child_process(_BOUNDED, "f", DEFAULT_CORRUPT_PROBES[:1], max_rss_mib=32, sandbox=mode)
        assert res == {"status": "ok", "results": ["accepted"]}, (mode, res)
    # Default cap (256 MiB) leaves a 96 MiB working set alone.
    assert _run_probes_in_child_process(_SPIKE_96MIB, "f", DEFAULT_CORRUPT_PROBES[:1]) == {
        "status": "ok",
        "results": ["accepted"],
    }


def test_13_invalid_max_rss_mib_rejected_before_child_runs(tmp_path: Path) -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    marker = tmp_path / "ran.txt"
    code = f"open({str(marker)!r}, 'w').write('x')\ndef f(p):\n    return True\n"
    for bad in (True, False, 0, -1, 1.5, "32", None):
        res = _run_probes_in_child_process(
            code, "f", DEFAULT_CORRUPT_PROBES[:1], max_rss_mib=bad, sandbox="process_isolation_only"  # type: ignore[arg-type]
        )
        assert res == {"status": "harness_error", "detail": "INVALID_MAX_RSS_MIB"}, bad
        assert not marker.exists()
    # 1 MiB is a valid (if tiny) cap: the interpreter alone exceeds it.
    tiny = _run_probes_in_child_process(_BOUNDED, "f", DEFAULT_CORRUPT_PROBES[:1], max_rss_mib=1)
    assert tiny["status"] == "HALT_CHILD_RSS_LIMIT_EXCEEDED"
    assert tiny["max_rss_kib"] == 1024


def test_14_oracle_fails_closed_on_rss_halt() -> None:
    hog = "import time\ndef process_payment(p):\n    x = bytearray(400 * 1024 * 1024)\n    time.sleep(2)\n    return True\n"
    rc = DisprovingReverseEngineerOracle().evaluate_candidate(hog, "process_payment", "memory_hog")
    assert rc.disproved_as_cargo_cult is True
    assert rc.mutant_detected_by_gate is False
    assert rc.mutant_injected == "nominal_parse"
    assert "HALT_CHILD_RSS_LIMIT_EXCEEDED" in rc.diagnostic_trace


_requires_darwin = pytest.mark.skipif(
    __import__("sys").platform != "darwin", reason="ps-based RSS sampler is used on macOS only"
)


@_requires_darwin
def test_15_rss_sampler_and_unsampleable_fail_closed() -> None:
    import os
    import subprocess
    import sys
    import time as _time

    from src.repo_reverse_engineering_engine import (
        _rusage_maxrss_kib,
        _sample_child_rss_kib,
        _watch_child,
    )

    own = _sample_child_rss_kib(os.getpid())
    assert type(own) is int and own > 1024
    for bad_ps in ("/nonexistent/ps", "/usr/bin/false", "/bin/echo"):
        assert _sample_child_rss_kib(os.getpid(), bad_ps) is None, bad_ps
    assert _rusage_maxrss_kib(5 * 1024 * 1024) == 5 * 1024  # Darwin reports bytes

    def _spawn(code: str) -> subprocess.Popen:
        return subprocess.Popen([sys.executable, "-I", "-c", code], env={}, start_new_session=True)

    # RSS cannot be sampled on a live child -> killed, typed fail-closed outcome.
    p = _spawn("import time; time.sleep(5)")
    t0 = _time.monotonic()
    outcome, peak = _watch_child(p, 10.0, 1 << 20, ps_path="/nonexistent/ps")
    assert outcome == "rss_unsampleable"
    assert p.returncode == -9 and _time.monotonic() - t0 < 2.0
    assert type(peak) is int and peak > 0  # from wait4 ru_maxrss, never a silent 0

    # Wall-clock timeout -> process group SIGKILLed.
    p = _spawn("import time; time.sleep(5)")
    outcome, peak = _watch_child(p, 0.3, 1 << 20)
    assert outcome == "timeout" and p.returncode == -9 and peak > 0

    # Normal exit under the cap.
    p = _spawn("import sys; sys.exit(4)")
    outcome, peak = _watch_child(p, 10.0, 1 << 20)
    assert outcome == "exited" and p.returncode == 4 and 0 < peak <= 1 << 20


def test_16_vulnerability_record_is_frozen() -> None:
    vulns = AntiCargoCultScanner().scan_file("t.py", "def test_x():\n    assert True\n")
    assert vulns, "expected the trivial-assert heuristic to fire"
    with pytest.raises(dataclasses.FrozenInstanceError):
        vulns[0].line_number = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Descendant escape via fork + setsid (red-team follow-up to a6). With Seatbelt
# the oracle child runs under `(deny process-fork)` (PermissionError); without
# Seatbelt the child lowers RLIMIT_NPROC to (0, 0) before compiling candidate
# code so fork fails closed with BlockingIOError (EAGAIN). Real sandbox-exec,
# real fork, real 96 MiB allocation; no mocks.
# ---------------------------------------------------------------------------
_SETSID_GRANDCHILD_96MIB = (
    "import os, time\n"
    "_pid = os.fork()\n"
    "if _pid == 0:\n"
    "    os.setsid()\n"
    "    _x = bytearray(96 * 1024 * 1024)\n"
    "    time.sleep(0.3)\n"
    "    os._exit(0)\n"
    "def f(p):\n"
    "    return True\n"
)


@_requires_seatbelt
def test_17_setsid_grandchild_refused_under_oracle_default() -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    for kwargs in ({}, {"max_rss_mib": 64}):
        res = _run_probes_in_child_process(_SETSID_GRANDCHILD_96MIB, "f", DEFAULT_CORRUPT_PROBES[:1], **kwargs)
        assert res["status"] == "load_error", (kwargs, res)
        assert res["detail"].startswith("PermissionError: [Errno 1]"), res
    rc = DisprovingReverseEngineerOracle().evaluate_candidate(_SETSID_GRANDCHILD_96MIB, "f", "setsid_escape")
    assert rc.disproved_as_cargo_cult is True
    assert rc.mutant_detected_by_gate is False
    assert rc.mutant_injected == "nominal_parse"
    assert rc.diagnostic_trace.startswith("Nominal load failed (load_error): PermissionError")
    # A pure-computation candidate still passes under the same default.
    assert _run_probes_in_child_process(_BOUNDED, "f", DEFAULT_CORRUPT_PROBES[:1]) == {
        "status": "ok",
        "results": ["accepted"],
    }
    assert _run_probes_in_child_process(_BOUNDED, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox="seatbelt_required") == {
        "status": "ok",
        "results": ["accepted"],
    }


def test_18_setsid_grandchild_blocked_without_seatbelt_via_rlimit_nproc() -> None:
    from src.repo_reverse_engineering_engine import _run_probes_in_child_process

    # Without Seatbelt, RLIMIT_NPROC=(0, 0) blocks fork with BlockingIOError (EAGAIN).
    res = _run_probes_in_child_process(
        _SETSID_GRANDCHILD_96MIB, "f", DEFAULT_CORRUPT_PROBES[:1], max_rss_mib=64, sandbox="process_isolation_only"
    )
    assert res["status"] == "load_error", res
    assert "BlockingIOError" in res["detail"], res

    # Unprivileged candidate cannot raise RLIMIT_NPROC hard limit back up from 0.
    raise_rlimit_code = (
        "import resource\n"
        "resource.setrlimit(resource.RLIMIT_NPROC, (100, 100))\n"
        "def f(p):\n"
        "    return True\n"
    )
    raise_res = _run_probes_in_child_process(
        raise_rlimit_code, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox="process_isolation_only"
    )
    assert raise_res["status"] == "load_error", raise_res
    assert "ValueError" in raise_res["detail"], raise_res

    # Bounded pure-computation candidate still passes under process_isolation_only.
    assert _run_probes_in_child_process(
        _BOUNDED, "f", DEFAULT_CORRUPT_PROBES[:1], sandbox="process_isolation_only"
    ) == {
        "status": "ok",
        "results": ["accepted"],
    }

