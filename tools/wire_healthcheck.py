#!/usr/bin/env python3
"""
tools/wire_healthcheck.py: is the system actually wired? (prototype; observed facts only)

Reports what physically exists and runs four functional probes against the REAL components:
  1. liveness     each gate call through the probe wrapper appends exactly one row to a JSONL log
  2. sensitivity  known-bad candidates (eval, dunder escape, forbidden import, stub body) are halted
  3. specificity  a known-good candidate is allowed
  4. replay       the same effect dispatched twice through the real EO1 interlock produces exactly
                  one effect at a counting target; the second attempt is refused
Plus measurements:
  - gate latency at three input sizes (p50 ns). This is a scaling measurement, not a proof:
    a latency threshold says nothing about complexity, so no "O(1)" verdict is printed.
  - payload size in bytes and characters only. Token counts are reported as UNAVAILABLE unless a
    provider usage field or the provider's own tokenizer is present; len/4 is never used.
  - agent (LLM) traffic: NOT_OBSERVABLE_FROM_REPO; no endpoint in this repo carries it.

Each sensitivity row runs a positive control: the same payload through a disabled (allow-all) gate
must be accepted, otherwise the row is INCONCLUSIVE. Exit code 0 only if all four probes hold.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.jcs_canonicalizer import encode_jcs  # noqa: E402
from src.scaffold_detector import detect_scaffolds  # noqa: E402
from src.vesper_harness_gates import HackDetectionGate  # noqa: E402

Gate = Callable[[str], Tuple[bool, str]]

KNOWN_BAD: Tuple[Tuple[str, str], ...] = (
    ("eval_call", "def generate_blocks(v, k, t):\n    return eval('1')\n"),
    ("dunder_escape", "def generate_blocks(v, k, t):\n    return ().__class__.__bases__[0]\n"),
    ("forbidden_import", "import os\ndef generate_blocks(v, k, t):\n    return []\n"),
    ("stub_body", "def generate_blocks(v, k, t):\n    pass\n"),
)
KNOWN_GOOD = ("def generate_blocks(v, k, t):\n"
              "    base = (0, 1, 3)\n"
              "    return [tuple(sorted((x + s) % v for x in base)) for s in range(v)]\n")
CANDIDATE_FILES = (
    "src/truth_compass.py", "src/eo1_write_before_execute.py", "src/eo1_effect_key.py",
    "src/scaffold_detector.py", "tools/run_all_verification_gates.py", "TRUTH_MANIFESTO.md",
    # Names used by pasted designs; checked, not assumed.
    "src/daily_o1_truth_compass.py", "src/learning_ontology.py", "src/observability_proxy.py",
    "src/system_health_telemetry.py",
)


def default_gate(source: str) -> Tuple[bool, str]:
    """The repo's real pre-flight checks: Vesper AST gate, then the AST scaffold detector."""
    ok, reason = HackDetectionGate.inspect_candidate(source)
    if not ok:
        return False, reason
    det = detect_scaffolds(None, source)
    if det.scaffold_count:
        return False, "HALT_SCAFFOLD:" + ",".join(sorted({f.category for f in det.findings}))
    return True, "OK_ALLOW"


def allow_all_gate(source: str) -> Tuple[bool, str]:
    """Positive-control gate: accepts everything."""
    return True, "OK_ALLOW_CONTROL"


class ProbeLog:
    """Append-only JSONL log written by the probe wrapper (the 'wire' being checked)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def rows(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())

    def call(self, gate: Gate, label: str, source: str) -> Tuple[bool, str]:
        t0 = time.monotonic_ns()
        ok, reason = gate(source)
        elapsed = time.monotonic_ns() - t0
        row = {"label": label, "ok": ok, "reason": reason, "elapsed_ns": elapsed,
               "bytes": len(source.encode("utf-8")), "chars": len(source),
               "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(encode_jcs(row).decode("utf-8") + "\n")
        return ok, reason


def probe_liveness(log: ProbeLog, gate: Gate) -> Dict[str, Any]:
    before = log.rows()
    log.call(gate, "liveness", KNOWN_GOOD)
    after = log.rows()
    return {"probe": "liveness", "rows_before": before, "rows_after": after, "holds": after == before + 1}


def probe_sensitivity(log: ProbeLog, gate: Gate) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for label, src in KNOWN_BAD:
        ctrl_ok, _ = log.call(allow_all_gate, f"control:{label}", src)
        ok, reason = log.call(gate, f"sensitivity:{label}", src)
        verdict = "INCONCLUSIVE" if not ctrl_ok else ("DEFENDED" if not ok else "BROKEN")
        rows.append({"payload": label, "reason": reason, "verdict": verdict})
    return {"probe": "sensitivity", "rows": rows, "holds": all(r["verdict"] == "DEFENDED" for r in rows)}


def probe_specificity(log: ProbeLog, gate: Gate) -> Dict[str, Any]:
    ok, reason = log.call(gate, "specificity", KNOWN_GOOD)
    return {"probe": "specificity", "reason": reason, "holds": ok}


def probe_replay(workdir: Path) -> Dict[str, Any]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from src.eo1_write_before_execute import LatchedCaidExecutionHaltedError, PreDispatchIntentInterlock

    interlock = PreDispatchIntentInterlock(
        ledger_path=workdir / "ledger.jsonl", output_state_dir=workdir / "state",
        boundary_private_key=Ed25519PrivateKey.generate(), authority_id="wire-healthcheck")
    effects = {"count": 0}

    def target() -> Dict[str, Any]:
        effects["count"] += 1
        return {"status": "applied"}

    payload = {"amount_minor": 1000, "currency": "EUR", "to": "acct-1", "ref": "inv-1"}
    interlock.dispatch("https://target.local/pay", "payments.transfer", payload, dispatch_fn=target)
    refused = ""
    try:
        interlock.dispatch("https://target.local/pay", "payments.transfer", payload, dispatch_fn=target)
    except LatchedCaidExecutionHaltedError as exc:
        refused = type(exc).__name__
    return {"probe": "replay", "effects_at_target": effects["count"], "second_attempt": refused or "ACCEPTED",
            "holds": effects["count"] == 1 and bool(refused)}


def measure_scaling(gate: Gate, sizes: Tuple[int, ...] = (10, 100, 1000), reps: int = 5) -> Dict[str, Any]:
    out = []
    for n in sizes:
        src = "".join(f"def f{i}(x):\n    return x + {i}\n" for i in range(n))
        samples = []
        for _ in range(reps):
            t0 = time.monotonic_ns()
            gate(src)
            samples.append(time.monotonic_ns() - t0)
        out.append({"functions": n, "bytes": len(src.encode("utf-8")), "p50_ns": int(statistics.median(samples))})
    first, last = out[0]["p50_ns"], out[-1]["p50_ns"]
    return {"sizes": out, "p50_ratio_largest_over_smallest_x100": (last * 100 // first) if first else 0,
            "note": "scaling measurement only; no complexity verdict"}


def environment() -> Dict[str, Any]:
    env: Dict[str, Any] = {"binaries": {}, "candidate_files": {}, "git": {}}
    for name in ("python3", "pytest", "git", "node", "xcodebuild", "xcrun"):
        env["binaries"][name] = shutil.which(name)
    xcode = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True, timeout=10) \
        if shutil.which("xcode-select") else None
    env["xcode_developer_dir"] = xcode.stdout.strip() if xcode and xcode.returncode == 0 else None
    for rel in CANDIDATE_FILES:
        p = ROOT / rel
        env["candidate_files"][rel] = {"exists": p.exists(), "bytes": p.stat().st_size if p.is_file() else None}
    if shutil.which("git"):
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        status = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True, timeout=60)
        env["git"] = {"head": head.stdout.strip() or None,
                      "changed_entries": len([ln for ln in status.stdout.splitlines() if ln.strip()])}
    return env


def run_healthcheck(gate: Gate = default_gate, workdir: Optional[Path] = None) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="wire_hc_") as tmp:
        base = Path(workdir) if workdir else Path(tmp)
        base.mkdir(parents=True, exist_ok=True)
        log = ProbeLog(base / "probe_log.jsonl")
        probes = [probe_liveness(log, gate), probe_sensitivity(log, gate), probe_specificity(log, gate),
                  probe_replay(base / "eo1")]
        report = {
            "checked_at_ns": time.time_ns(),
            "probes": probes,
            "all_probes_hold": all(p["holds"] for p in probes),
            "gate_scaling": measure_scaling(gate),
            "tokens": "UNAVAILABLE: no provider usage fields or provider tokenizer on this host; sizes are bytes/chars",
            "agent_llm_traffic": "NOT_OBSERVABLE_FROM_REPO",
            "probe_log_rows": log.rows(),
        }
    report["report_sha256"] = hashlib.sha256(encode_jcs({k: v for k, v in report.items() if k != "checked_at_ns"})).hexdigest()
    return report


def main() -> int:
    report = {"environment": environment(), **run_healthcheck()}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["all_probes_hold"] else 1


if __name__ == "__main__":
    sys.exit(main())
