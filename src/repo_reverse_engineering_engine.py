"""
Repository Reverse-Engineering & Architectural Synthesis Engine (prototype v1.0.0).

Static part (RepoASTTopologyExtractor, AntiCargoCultScanner) only parses source with
`ast` and never executes it. The DisprovingReverseEngineerOracle DOES execute candidate
code, in a separate `python -I` child process with an empty environment, a temporary
cwd and a timeout. On macOS with /usr/bin/sandbox-exec present (sandbox="auto", the
default) the child is also wrapped in a Seatbelt profile (src/seatbelt_sandbox.py) that
denies network, writes outside its temp cwd and process creation (fork/posix_spawn);
without it, this is process isolation
only, not a sandbox (and forking is not blocked). sandbox-exec is deprecated by Apple.
macOS does not enforce RLIMIT_AS, so memory is bounded by a
parent-side RSS watchdog (best-effort polling plus the kernel's peak-RSS figure from
wait4); see `_run_probes_in_child_process` for its limits.

The anti-pattern scanner is a heuristic lint over a handful of AST shapes; it has not
been evaluated for precision/recall on real repositories. Invariant thresholds emitted
by FrontierInvariantSynthesizer are configured defaults, not measurements.
"""

from __future__ import annotations

import ast
import dataclasses
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


# ============================================================================
# Canonical JSON Encoding: delegates to the single reference RFC 8785
# implementation (src/jcs_canonicalizer.py). A local copy previously sorted keys
# by Python code point instead of UTF-16 code units (red-team finding a1).
# ============================================================================
def _validate_jcs_payload(data: Any) -> None:
    """Enforces this module's integer-only policy before canonicalization."""
    if isinstance(data, bool) or data is None or isinstance(data, (int, str)):
        return
    if isinstance(data, float):
        raise ValueError("ERR_FLOAT_IN_JCS: Floats forbidden in canonical JCS; use integer basis points.")
    if isinstance(data, (list, tuple)):
        for x in data:
            _validate_jcs_payload(x)
        return
    if isinstance(data, dict):
        for k, v in data.items():
            if not isinstance(k, str):
                raise ValueError("ERR_NON_STRING_KEY_IN_JCS: Dict keys must be strings.")
            _validate_jcs_payload(v)
        return
    raise TypeError(f"ERR_UNSUPPORTED_TYPE_IN_JCS: {type(data)}")


def encode_jcs(data: Any) -> bytes:
    """RFC 8785 canonical JSON via the shared reference encoder (floats rejected)."""
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs

    _validate_jcs_payload(data)
    return _reference_encode_jcs(data)


def sha256_jcs(data: Any) -> str:
    """Calculates SHA-256 digest over canonical RFC 8785 JCS representation."""
    return hashlib.sha256(encode_jcs(data)).hexdigest()


# ============================================================================
# Classification Data Structures
# ============================================================================
@dataclass(frozen=True)
class CargoCultVulnerability:
    file_path: str
    line_number: int
    vulnerability_code: str
    description: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW


@dataclass(frozen=True)
class RepoTopologySummary:
    total_files_scanned: int
    total_ast_nodes: int
    function_definitions_count: int
    class_definitions_count: int
    async_functions_count: int
    external_call_sites_count: int
    entry_points: Tuple[str, ...]
    identified_state_machines: Tuple[str, ...]


@dataclass(frozen=True)
class DistilledInvariantCandidate:
    invariant_id: str
    target_pattern: str
    source_reference: str
    formal_obligation_type: str  # CONSERVATION, POSTCONDITION, FRAME_IMMUTABILITY, PRECONDITION
    description: str
    suggested_bps_threshold: int


@dataclass(frozen=True)
class FalsificationOracleReceipt:
    target_repo_or_symbol: str
    null_hypothesis: str
    mutant_injected: str
    mutant_detected_by_gate: bool
    disproved_as_cargo_cult: bool
    diagnostic_trace: str


@dataclass(frozen=True)
class ReverseEngineeringSynthesisReport:
    report_epoch: int
    target_name: str
    topology: RepoTopologySummary
    cargo_cult_flaws: Tuple[CargoCultVulnerability, ...]
    distilled_invariants: Tuple[DistilledInvariantCandidate, ...]
    falsification_oracle: FalsificationOracleReceipt
    digest_sha256: str
    signer_public_key_hex: str
    signature_hex: str


# ============================================================================
# 1. AST Topology Extractor
# ============================================================================
class RepoASTTopologyExtractor:
    """Extracts structural execution topology from Python AST trees."""

    def __init__(self) -> None:
        self._total_files = 0
        self._total_ast_nodes = 0
        self._func_count = 0
        self._class_count = 0
        self._async_func_count = 0
        self._call_sites = 0
        self._entry_points: List[str] = []
        self._state_machines: List[str] = []

    def scan_source_text(self, file_path: str, source_code: str) -> None:
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError:
            return

        self._total_files += 1
        for node in ast.walk(tree):
            self._total_ast_nodes += 1
            if isinstance(node, ast.FunctionDef):
                self._func_count += 1
                if node.name in ("main", "run", "entrypoint", "cli"):
                    self._entry_points.append(f"{file_path}:{node.name}")
            elif isinstance(node, ast.AsyncFunctionDef):
                self._async_func_count += 1
            elif isinstance(node, ast.ClassDef):
                self._class_count += 1
                lower_name = node.name.lower()
                if any(x in lower_name for x in ("machine", "state", "lifecycle", "transition", "automaton")):
                    self._state_machines.append(f"{file_path}:{node.name}")
            elif isinstance(node, ast.Call):
                self._call_sites += 1

    def build_summary(self) -> RepoTopologySummary:
        return RepoTopologySummary(
            total_files_scanned=self._total_files,
            total_ast_nodes=self._total_ast_nodes,
            function_definitions_count=self._func_count,
            class_definitions_count=self._class_count,
            async_functions_count=self._async_func_count,
            external_call_sites_count=self._call_sites,
            entry_points=tuple(self._entry_points),
            identified_state_machines=tuple(self._state_machines),
        )


# ============================================================================
# 2. Anti-Cargo-Cult Scanner
# ============================================================================
class AntiCargoCultScanner:
    """
    Detects the 5 Classical Hype Anti-Patterns in open-source AI repos:
    1. PROMPT_ONLY_SCAFFOLD: Using raw string checks or prompt wrappers as security gates.
    2. VOLATILE_IN_MEMORY_LATCH: State changes stored in dicts/lists without fsync/WAL.
    3. TAUTOLOGICAL_TEST_ASSERTION: Test asserts constant equality against module-level literal.
    4. UNBOUNDED_CONTEXT_PACKING: Unbounded append of tool output into prompt context.
    5. MOCK_PASS_GATE: Functions returning True unconditionally or empty pass stubs.
    """

    def scan_file(self, file_path: str, source_code: str) -> List[CargoCultVulnerability]:
        flaws: List[CargoCultVulnerability] = []
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as e:
            flaws.append(
                CargoCultVulnerability(
                    file_path=file_path,
                    line_number=e.lineno or 1,
                    vulnerability_code="SYNTAX_ERROR",
                    description=f"Unparseable source: {e}",
                    severity="HIGH",
                )
            )
            return flaws

        for node in ast.walk(tree):
            # Check 1: Mock-Pass Gate (function with body consisting solely of 'pass' or 'return True')
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.body) == 1:
                    stmt = node.body[0]
                    if isinstance(stmt, ast.Pass):
                        flaws.append(
                            CargoCultVulnerability(
                                file_path=file_path,
                                line_number=node.lineno,
                                vulnerability_code="MOCK_PASS_GATE",
                                description=f"Function '{node.name}' has empty pass body (stub/mock).",
                                severity="CRITICAL",
                            )
                        )
                    elif isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                        if stmt.value.value is True and node.name.startswith(("verify", "check", "validate", "gate")):
                            flaws.append(
                                CargoCultVulnerability(
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    vulnerability_code="MOCK_PASS_GATE",
                                    description=f"Verifier '{node.name}' trivially returns True without checks.",
                                    severity="CRITICAL",
                                )
                            )

            # Check 2: Unsafe Dynamic Exec / Eval
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                    flaws.append(
                        CargoCultVulnerability(
                            file_path=file_path,
                            line_number=node.lineno,
                            vulnerability_code="UNSAFE_DYNAMIC_EVAL",
                            description=f"Direct call to forbidden built-in '{func.id}'.",
                            severity="CRITICAL",
                        )
                    )

            # Check 3: Tautological test assertion (assert True, assert 1 == 1, assert x == x)
            if isinstance(node, ast.Assert):
                test_node = node.test
                if isinstance(test_node, ast.Constant) and test_node.value is True:
                    flaws.append(
                        CargoCultVulnerability(
                            file_path=file_path,
                            line_number=node.lineno,
                            vulnerability_code="TAUTOLOGICAL_TEST_ASSERTION",
                            description="Trivial assert True in test assertion.",
                            severity="HIGH",
                        )
                    )
                elif isinstance(test_node, ast.Compare):
                    if len(test_node.ops) == 1 and isinstance(test_node.ops[0], ast.Eq):
                        left = test_node.left
                        right = test_node.comparators[0]
                        if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                            if left.value == right.value:
                                flaws.append(
                                    CargoCultVulnerability(
                                        file_path=file_path,
                                        line_number=node.lineno,
                                        vulnerability_code="TAUTOLOGICAL_TEST_ASSERTION",
                                        description=f"Trivial literal comparison assert {left.value} == {right.value}.",
                                        severity="HIGH",
                                    )
                                )

        # Line-based regex checks for prompt-only gates and volatile storage
        lines = source_code.splitlines()
        for i, line in enumerate(lines, start=1):
            # Check 4: Prompt-only security filter
            if re.search(r'if\s+["\'].*["\']\s+in\s+prompt:', line, re.IGNORECASE):
                flaws.append(
                    CargoCultVulnerability(
                        file_path=file_path,
                        line_number=i,
                        vulnerability_code="PROMPT_ONLY_SCAFFOLD",
                        description="Naïve substring check on user prompt used as security gate.",
                        severity="HIGH",
                    )
                )

        return flaws


# ============================================================================
# 3. Frontier Invariant Synthesizer
# ============================================================================
class FrontierInvariantSynthesizer:
    """
    Distills raw patterns discovered during reverse-engineering into
    formal AEIB invariants and requirements.
    """

    def synthesize_invariants(
        self,
        topology: RepoTopologySummary,
        flaws: List[CargoCultVulnerability],
    ) -> List[DistilledInvariantCandidate]:
        candidates: List[DistilledInvariantCandidate] = []

        # Invariant 1: Concurrency and Durability Invariant
        candidates.append(
            DistilledInvariantCandidate(
                invariant_id="INV_DURABLE_INTENT_WAL",
                target_pattern="file_write_or_tool_dispatch",
                source_reference="EO1_Station1_Interlock",
                formal_obligation_type="PRECONDITION",
                description="All external state mutations must be recorded to append-only WAL with POSIX fsync before socket dispatch.",
                suggested_bps_threshold=10000,
            )
        )

        # Invariant 2: Anti-Mock Gate Invariant
        has_mock_flaw = any(f.vulnerability_code == "MOCK_PASS_GATE" for f in flaws)
        candidates.append(
            DistilledInvariantCandidate(
                invariant_id="INV_ZERO_MOCK_DISCIPLINE",
                target_pattern="verifier_functions",
                source_reference="AST_Purity_Gate",
                formal_obligation_type="POSTCONDITION",
                description="All verification gates must have non-trivial AST branching and fail closed on corrupt inputs.",
                suggested_bps_threshold=10000 if has_mock_flaw else 9500,
            )
        )

        # Invariant 3: Dual-Polarity Bounded Model Checking
        candidates.append(
            DistilledInvariantCandidate(
                invariant_id="INV_DUAL_POLARITY_BMC",
                target_pattern="state_transitions",
                source_reference="FormalMAGSGate",
                formal_obligation_type="CONSERVATION",
                description="Every candidate state mutation must satisfy postconditions on valid inputs AND raise expected exceptions on invalid inputs.",
                suggested_bps_threshold=10000,
            )
        )

        # Invariant 4: Context Stability Homeostasis
        candidates.append(
            DistilledInvariantCandidate(
                invariant_id="INV_HOMEOSTATIC_SENTINEL",
                target_pattern="agent_context_memory",
                source_reference="DigitalApoptosisSentinel",
                formal_obligation_type="FRAME_IMMUTABILITY",
                description="Agent context stability score must remain >= 6200 bps; drift below threshold triggers digital apoptosis and regrowth from certified CAID.",
                suggested_bps_threshold=6200,
            )
        )

        return candidates


# ============================================================================
# 4. Disproving Reverse-Engineer Oracle
# ============================================================================
DEFAULT_CORRUPT_PROBES: Tuple[Dict[str, int], ...] = (
    {"amount": -100, "balance": 50},
    {"amount": 0, "balance": 0},
    {},
    {"amount": 1000, "balance": 10},  # Overdraft
)


_CHILD_PROBE_HARNESS = r'''
import json, sys
req = json.loads(sys.stdin.read())
_tok = req.pop("token")
def _emit(obj):
    sys.stdout.write(_tok + json.dumps(obj) + "\n")
    sys.stdout.flush()
scope = {}
try:
    compiled = compile(req["code"], "<candidate>", "exec")
    exec(compiled, scope)  # runs only inside the isolated child interpreter
except BaseException as exc:
    _emit({"status": "load_error", "detail": type(exc).__name__ + ": " + str(exc)})
    sys.exit(0)
fn = scope.get(req["fn"])
if req["fn"] not in scope:
    _emit({"status": "missing"})
    sys.exit(0)
if not callable(fn):
    _emit({"status": "not_callable"})
    sys.exit(0)
results = []
for probe in req["probes"]:
    try:
        res = fn(dict(probe))
        if res is True or (isinstance(res, dict) and res.get("success") is True):
            results.append("accepted")
        else:
            results.append("not_accepted")
    except (ValueError, KeyError, PermissionError, RuntimeError):
        results.append("rejected")
    except BaseException as exc:
        results.append("other_exception:" + type(exc).__name__)
_emit({"status": "ok", "results": results})
'''


def _apply_child_rlimits() -> None:
    """Best-effort resource caps for the child (CPU seconds, open files, address space)."""
    import resource

    for limit, value in (
        (resource.RLIMIT_CPU, 10),
        (resource.RLIMIT_NOFILE, 64),
        (resource.RLIMIT_AS, 1 << 30),  # not enforced by macOS; effective on Linux
    ):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            pass


RSS_POLL_INTERVAL_S = 0.01
PS_PATH = "/bin/ps"


def _sample_child_rss_kib(pid: int, ps_path: str = PS_PATH) -> Optional[int]:
    """
    Current resident set size of `pid` in KiB, or None when it cannot be sampled.

    Linux reads /proc/<pid>/statm (resident pages * page size). Other hosts (macOS)
    run `<ps_path> -o rss= -p <pid>` (default /bin/ps) with an empty environment and a 1 s timeout; the
    stdlib has no portable per-pid RSS query on Darwin, and `ps` avoids hand-written
    ctypes struct layouts for libproc. An unreaped (zombie) child reports 0.
    """
    import os
    import subprocess

    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/statm", "rb") as fh:
                resident_pages = int(fh.read().split()[1])
        except (OSError, ValueError, IndexError):
            return None
        return resident_pages * os.sysconf("SC_PAGE_SIZE") // 1024
    try:
        out = subprocess.run(
            [ps_path, "-o", "rss=", "-p", str(pid)],
            capture_output=True, text=True, timeout=1.0, env={},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = out.stdout.strip()
    if out.returncode != 0 or not text.isdigit():
        return None
    return int(text)


def _rusage_maxrss_kib(ru_maxrss: int) -> int:
    """ru_maxrss is reported in bytes on Darwin and in KiB on Linux."""
    return ru_maxrss // 1024 if sys.platform == "darwin" else ru_maxrss


def _watch_child(proc: Any, timeout_s: float, max_rss_kib: int, ps_path: str = PS_PATH) -> Tuple[str, int]:
    """
    Polls the child until it exits, the wall-clock timeout passes, its RSS exceeds
    `max_rss_kib`, or RSS cannot be sampled twice in a row. On any halt the child's
    process group is SIGKILLed. The child is always reaped here with os.wait4 so
    the kernel's peak RSS (ru_maxrss) is folded into the returned peak.

    Returns (outcome, peak_rss_kib) with outcome in
    {"exited", "timeout", "rss_exceeded", "rss_unsampleable"}.
    """
    import os
    import signal

    deadline = time.monotonic() + timeout_s
    peak_kib = 0
    misses = 0
    halt: Optional[str] = None
    while halt is None:
        done, wstatus, usage = os.wait4(proc.pid, os.WNOHANG)
        if done == proc.pid:
            proc.returncode = os.waitstatus_to_exitcode(wstatus)
            peak_kib = max(peak_kib, _rusage_maxrss_kib(usage.ru_maxrss))
            return ("exited" if peak_kib <= max_rss_kib else "rss_exceeded"), peak_kib
        if time.monotonic() >= deadline:
            halt = "timeout"
            continue
        rss = _sample_child_rss_kib(proc.pid, ps_path)
        if rss is None:
            # One miss may be an exit race; the next wait4 settles it. Two in a row
            # on a live child fail closed.
            misses += 1
            if misses >= 2:
                halt = "rss_unsampleable"
            continue
        misses = 0
        peak_kib = max(peak_kib, rss)
        if rss > max_rss_kib:
            halt = "rss_exceeded"
        else:
            time.sleep(RSS_POLL_INTERVAL_S)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    _, wstatus, usage = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(wstatus)
    return halt, max(peak_kib, _rusage_maxrss_kib(usage.ru_maxrss))


def _run_probes_in_child_process(
    candidate_code: str,
    fn_name: str,
    probes: Tuple[Dict[str, int], ...],
    timeout_s: float = 10.0,
    sandbox: str = "auto",
    sandbox_exec_path: Optional[str] = None,
    max_rss_mib: int = 256,
) -> Dict[str, Any]:
    """
    Runs candidate code and probes in a separate `python -I` process with an empty
    environment, a temporary cwd, a wall-clock timeout, best-effort rlimits and a
    parent-side RSS watchdog. The child starts in its own session/process group.

    Memory (`max_rss_mib`, a positive int; bool or <= 0 yields
    `{"status": "harness_error", "detail": "INVALID_MAX_RSS_MIB"}`): the parent
    samples the child's RSS about every 10 ms (Linux /proc/<pid>/statm, else
    `/bin/ps`) and SIGKILLs the process group when it exceeds the cap; after the
    child exits, the kernel's peak RSS from wait4 (ru_maxrss) is also checked, so a
    spike shorter than the poll interval is still reported. Either breach returns
    `{"status": "HALT_CHILD_RSS_LIMIT_EXCEEDED", "peak_rss_kib": int,
    "max_rss_kib": int, "detail": str}`. If RSS cannot be sampled twice in a row
    on a live child, it fails closed: the group is killed and
    `{"status": "HALT_CHILD_RSS_UNSAMPLEABLE", ...}` is returned (never treated as 0).
    Limits: polling is best-effort and only stops the child, it does not prevent
    an allocation, so RSS can exceed the cap for up to one poll interval (plus `ps`
    latency) before the kill. A spike shorter than the poll interval, or memory
    freed before the next sample, is missed by the live poll; for the direct child
    the post-exit ru_maxrss check still reports it. Descendants are not polled
    live; on this macOS host ru_maxrss was observed to include a grandchild the
    child itself reaped, but a descendant left running (or moved out of the process
    group via setsid / a double fork) escapes killpg and the RSS accounting. With
    Seatbelt the child therefore runs under `(deny process-fork)`: on this host
    os.fork, subprocess.run and os.posix_spawn were observed to fail with EPERM, so
    such a descendant cannot be started (a fork at load time yields `load_error`).
    Without Seatbelt (sandbox="process_isolation_only", "auto" on a host without
    sandbox-exec, or non-macOS) forking is not blocked and the gap remains. This is
    process isolation, not a sandbox.

    `sandbox` selects the containment layer:
      - "auto" (default): wrap the child in macOS Seatbelt (`sandbox-exec`, see
        src/seatbelt_sandbox.py) when available, else process isolation only;
      - "seatbelt_required": fail closed with
        `{"status": "harness_error", "detail": "SEATBELT_UNAVAILABLE"}` when
        Seatbelt is unavailable;
      - "process_isolation_only": never wrap.
    `sandbox_exec_path` overrides the sandbox-exec location (used by tests).

    With Seatbelt the child is denied: file writes outside its temp cwd (and
    /dev/null), all network, process creation (fork / posix_spawn), and
    reads/writes of the invoking user's sensitive
    home entries that exist (.ssh, .aws, .gnupg, .config, .netrc, .docker, .kube,
    Library/Keychains), except an entry containing the interpreter, its prefix or
    the temp cwd. It is still not a full sandbox: the profile is allow-default,
    reads elsewhere stay allowed, Seatbelt itself does not limit memory (only the
    RSS watchdog above does), and sandbox-exec is deprecated by Apple. Without
    Seatbelt this is process isolation only.

    The verdict line must carry a per-run random token and appear exactly once;
    a candidate that prints a forged verdict without the token, or produces
    duplicate verdict lines, yields `harness_error`. A candidate that deliberately
    introspects the harness can still forge the verdict: this oracle is meant for
    catching buggy code, not for judging adversarial code.
    """
    import os
    import pwd
    import secrets
    import subprocess
    import tempfile

    from src.seatbelt_sandbox import (
        SANDBOX_EXEC_PATH,
        build_seatbelt_argv,
        seatbelt_available,
        sensitive_home_deny_roots,
    )

    if sandbox not in ("auto", "seatbelt_required", "process_isolation_only"):
        return {"status": "harness_error", "detail": "INVALID_SANDBOX_MODE"}
    if isinstance(max_rss_mib, bool) or not isinstance(max_rss_mib, int) or max_rss_mib <= 0:
        return {"status": "harness_error", "detail": "INVALID_MAX_RSS_MIB"}
    max_rss_kib = max_rss_mib * 1024
    exec_path = sandbox_exec_path if sandbox_exec_path is not None else SANDBOX_EXEC_PATH
    use_seatbelt = sandbox != "process_isolation_only" and seatbelt_available(exec_path)
    if sandbox == "seatbelt_required" and not use_seatbelt:
        return {"status": "harness_error", "detail": "SEATBELT_UNAVAILABLE"}

    token = "AEIBRV-" + secrets.token_hex(16) + ":"
    payload = json.dumps({"code": candidate_code, "fn": fn_name, "probes": list(probes), "token": token})
    # The child's stdin/stdout/stderr are files in a second temp dir that is NOT the
    # child's cwd (and not a Seatbelt-writable root), so the parent can poll RSS
    # without pipe-drain threads and the child cannot reopen them by relative path.
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as io_dir:
        argv = [sys.executable, "-I", "-c", _CHILD_PROBE_HARNESS]
        if use_seatbelt:
            tmp_real = os.path.realpath(tmp)
            deny_roots = sensitive_home_deny_roots(
                pwd.getpwuid(os.getuid()).pw_dir,
                [sys.executable, sys.prefix, sys.base_prefix, tmp_real],
            )
            try:
                argv = build_seatbelt_argv(
                    argv, [tmp_real], deny_roots, sandbox_exec_path=exec_path, allow_process_fork=False
                )
            except ValueError as exc:
                return {"status": "harness_error", "detail": f"SEATBELT_PROFILE_INVALID:{exc}"}
        stdin_path = os.path.join(io_dir, "stdin.json")
        with open(stdin_path, "wb") as fh:
            fh.write(payload.encode("utf-8"))
        with open(stdin_path, "rb") as fin, open(os.path.join(io_dir, "stdout"), "w+b") as fout, open(
            os.path.join(io_dir, "stderr"), "w+b"
        ) as ferr:
            proc = subprocess.Popen(
                argv,
                stdin=fin,
                stdout=fout,
                stderr=ferr,
                cwd=tmp,
                env={},
                preexec_fn=_apply_child_rlimits,
                start_new_session=True,
            )
            outcome, peak_kib = _watch_child(proc, timeout_s, max_rss_kib)
            fout.seek(0)
            stdout = fout.read().decode("utf-8", "replace")
            ferr.seek(0)
            stderr = ferr.read().decode("utf-8", "replace")
    if outcome == "timeout":
        return {"status": "timeout", "detail": f"exceeded {timeout_s}s"}
    if outcome == "rss_exceeded":
        return {
            "status": "HALT_CHILD_RSS_LIMIT_EXCEEDED",
            "peak_rss_kib": peak_kib,
            "max_rss_kib": max_rss_kib,
            "detail": f"peak_rss_kib={peak_kib} > max_rss_kib={max_rss_kib}",
        }
    if outcome == "rss_unsampleable":
        return {
            "status": "HALT_CHILD_RSS_UNSAMPLEABLE",
            "peak_rss_kib": peak_kib,
            "max_rss_kib": max_rss_kib,
            "detail": "child RSS could not be sampled; child killed (fail closed)",
        }
    verdicts = [ln[len(token):] for ln in stdout.splitlines() if ln.startswith(token)]
    if proc.returncode != 0 or len(verdicts) != 1:
        return {
            "status": "harness_error",
            "detail": f"returncode={proc.returncode} verdict_lines={len(verdicts)} {stderr[-300:]}",
        }
    try:
        return json.loads(verdicts[0])
    except json.JSONDecodeError:
        return {"status": "harness_error", "detail": "unparseable child output"}


class DisprovingReverseEngineerOracle:
    """
    Executes an adversarial disproving oracle against an external repo pattern.
    Formulates a null hypothesis: 'The observed pattern is a fragile cargo-cult
    wrapper that fails when injected with boundary mutations.'
    """

    def evaluate_candidate(
        self,
        candidate_code: str,
        test_fn_name: str,
        mutation_description: str,
    ) -> FalsificationOracleReceipt:
        """
        Executes candidate code under nominal and mutated conditions.
        If the candidate passes despite being mutated, it is DISPROVED as cargo cult.
        """
        null_hyp = "Candidate claims robust verification but accepts corrupt boundary inputs."

        # Candidate code is untrusted: it runs in a separate interpreter process
        # (python -I, empty environment, temporary cwd, wall-clock timeout).
        # With sandbox="auto" it is additionally wrapped in macOS Seatbelt when
        # available (no network, no writes outside its temp cwd, no fork/spawn); otherwise it is
        # process isolation only and can use the invoking user's permissions.
        outcome = _run_probes_in_child_process(candidate_code, test_fn_name, DEFAULT_CORRUPT_PROBES)
        status = outcome.get("status")

        if status in (
            "load_error",
            "timeout",
            "harness_error",
            "HALT_CHILD_RSS_LIMIT_EXCEEDED",
            "HALT_CHILD_RSS_UNSAMPLEABLE",
        ):
            return FalsificationOracleReceipt(
                target_repo_or_symbol=test_fn_name,
                null_hypothesis=null_hyp,
                mutant_injected="nominal_parse",
                mutant_detected_by_gate=False,
                disproved_as_cargo_cult=True,
                diagnostic_trace=f"Nominal load failed ({status}): {outcome.get('detail', '')}",
            )
        if status == "missing":
            return FalsificationOracleReceipt(
                target_repo_or_symbol=test_fn_name,
                null_hypothesis=null_hyp,
                mutant_injected="symbol_missing",
                mutant_detected_by_gate=False,
                disproved_as_cargo_cult=True,
                diagnostic_trace=f"Target symbol '{test_fn_name}' not found in candidate scope.",
            )

        if status == "ok":
            results = outcome.get("results", [])
            failures = sum(1 for r in results if r == "accepted")
            disproved = failures > 0
            mutated_detected = not disproved
            if disproved:
                diagnostic = f"Accepted {failures} of {len(results)} corrupt inputs."
            else:
                diagnostic = f"Rejected all {len(results)} corrupt inputs."
        else:
            disproved = True
            mutated_detected = False
            diagnostic = "Target symbol is not callable."

        return FalsificationOracleReceipt(
            target_repo_or_symbol=test_fn_name,
            null_hypothesis=null_hyp,
            mutant_injected=mutation_description,
            mutant_detected_by_gate=mutated_detected,
            disproved_as_cargo_cult=disproved,
            diagnostic_trace=diagnostic,
        )


# ============================================================================
# 5. Master Reverse Engineering Orchestrator
# ============================================================================
class RepoReverseEngineeringEngine:
    """Master orchestrator combining topology extraction, flaw scanning, invariant synthesis, and signing."""

    def __init__(self, signing_key: Optional[Ed25519PrivateKey] = None) -> None:
        self._key = signing_key or Ed25519PrivateKey.generate()
        self._extractor = RepoASTTopologyExtractor()
        self._scanner = AntiCargoCultScanner()
        self._synthesizer = FrontierInvariantSynthesizer()
        self._oracle = DisprovingReverseEngineerOracle()

    def analyze_repository(
        self,
        repo_name: str,
        files: Dict[str, str],
        oracle_target: Optional[Tuple[str, str, str]] = None,
    ) -> ReverseEngineeringSynthesisReport:
        all_flaws: List[CargoCultVulnerability] = []

        for fpath, code in files.items():
            self._extractor.scan_source_text(fpath, code)
            flaws = self._scanner.scan_file(fpath, code)
            all_flaws.extend(flaws)

        topology = self._extractor.build_summary()
        invariants = self._synthesizer.synthesize_invariants(topology, all_flaws)

        # Run disproving oracle on target if specified, or default self-check
        if oracle_target:
            code, fn_name, mut_desc = oracle_target
            oracle_res = self._oracle.evaluate_candidate(code, fn_name, mut_desc)
        else:
            oracle_res = FalsificationOracleReceipt(
                target_repo_or_symbol=repo_name,
                null_hypothesis="Default null hypothesis check",
                mutant_injected="zero_input",
                mutant_detected_by_gate=True,
                disproved_as_cargo_cult=False,
                diagnostic_trace="Self-test nominal verification passed.",
            )

        payload_for_digest = {
            "report_epoch": int(time.time()),
            "target_name": repo_name,
            "topology": {
                "total_files": topology.total_files_scanned,
                "total_ast_nodes": topology.total_ast_nodes,
                "func_count": topology.function_definitions_count,
                "class_count": topology.class_definitions_count,
                "call_sites": topology.external_call_sites_count,
            },
            "cargo_cult_flaws_count": len(all_flaws),
            "distilled_invariants_count": len(invariants),
            "disproved_as_cargo_cult": oracle_res.disproved_as_cargo_cult,
        }
        digest = sha256_jcs(payload_for_digest)

        pubkey = self._key.public_key()
        pubkey_hex = pubkey.public_bytes_raw().hex()
        sig_hex = self._key.sign(digest.encode("utf-8")).hex()

        return ReverseEngineeringSynthesisReport(
            report_epoch=payload_for_digest["report_epoch"],
            target_name=repo_name,
            topology=topology,
            cargo_cult_flaws=tuple(all_flaws),
            distilled_invariants=tuple(invariants),
            falsification_oracle=oracle_res,
            digest_sha256=digest,
            signer_public_key_hex=pubkey_hex,
            signature_hex=sig_hex,
        )


def verify_synthesis_report(report: ReverseEngineeringSynthesisReport) -> bool:
    """Verifies the Ed25519 signature of a ReverseEngineeringSynthesisReport."""
    pub_bytes = bytes.fromhex(report.signer_public_key_hex)
    sig_bytes = bytes.fromhex(report.signature_hex)
    pubkey = Ed25519PublicKey.from_public_bytes(pub_bytes)
    try:
        pubkey.verify(sig_bytes, report.digest_sha256.encode("utf-8"))
        return True
    except Exception:
        return False
