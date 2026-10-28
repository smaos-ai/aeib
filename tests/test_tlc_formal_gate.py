#!/usr/bin/env python3
"""Runs the real TLC gate (scripts/run_tlc_formal_gate.sh) when the pinned jar is installed.

The test SKIPS (never passes) when java or the verified jar is absent, so a green run here
always means TLC really executed. No network access: scripts/fetch_tla2tools.sh is separate.
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / "formal" / "bin" / "tla2tools.jar"
GATE = ROOT / "scripts" / "run_tlc_formal_gate.sh"
PINNED_SHA256 = "78f7e2c6bf9a8b65eda665a23e94431255587e0b43a834a4e2af1723562d9b4a"


def _java() -> str:
    found = shutil.which("java")
    if found:
        return found
    sdk = Path.home() / ".sdkman" / "candidates" / "java" / "current" / "bin" / "java"
    return str(sdk) if sdk.exists() else ""


def _jar_ok() -> bool:
    return JAR.is_file() and hashlib.sha256(JAR.read_bytes()).hexdigest() == PINNED_SHA256


needs_tlc = pytest.mark.skipif(
    not (_java() and _jar_ok()),
    reason="java or the pinned tla2tools.jar is absent (run scripts/fetch_tla2tools.sh); TLC not evidenced",
)


@needs_tlc
def test_tlc_gate_a5_clean_and_a4_counterexample():
    proc = subprocess.run(["bash", str(GATE)], capture_output=True, text=True, timeout=300,
                          env={**os.environ, "JAVA_BIN": _java()})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "[PASS] A5 (fenced): no error, 34047 distinct states" in proc.stdout
    assert "[PASS] A4 negative control: SafetyNoDuplicateEffect violated" in proc.stdout


@needs_tlc
def test_tlc_gate_fails_closed_on_tampered_jar(tmp_path):
    """Copy the repo gate layout with a corrupted jar: the gate must refuse (exit 2), not pass."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "formal" / "bin").mkdir(parents=True)
    shutil.copytree(ROOT / "formal" / "tlaplus", root / "formal" / "tlaplus")
    shutil.copy(GATE, root / "scripts" / "run_tlc_formal_gate.sh")
    (root / "formal" / "bin" / "tla2tools.jar").write_bytes(JAR.read_bytes() + b"x")
    proc = subprocess.run(["bash", str(root / "scripts" / "run_tlc_formal_gate.sh")],
                          capture_output=True, text=True, timeout=60, env={**os.environ, "JAVA_BIN": _java()})
    assert proc.returncode == 2
    assert "digest mismatch" in proc.stderr


def test_tlc_gate_script_is_executable_text_and_pins_digest():
    text = GATE.read_text(encoding="utf-8")
    assert PINNED_SHA256 in text
    assert "No error has been found" in text and "SafetyNoDuplicateEffect" in text
    assert "curl" not in text and "wget" not in text, "the gate itself must not use the network"
    assert PINNED_SHA256 in (ROOT / "scripts" / "fetch_tla2tools.sh").read_text(encoding="utf-8")
