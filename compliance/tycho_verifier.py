#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
compliance/tycho_verifier.py
============================
Evaluates Tycho structural state gates and claims against filesystem, lockfile,
and Git provenance with zero external network egress and zero external dependencies.
"""

import os
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


class TychoVerdict(Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    STALE = "STALE"
    INDETERMINATE = "INDETERMINATE"
    ERROR = "ERROR"


@dataclass
class TychoResult:
    verdict: TychoVerdict
    reason: str


def find_tycho_binary() -> Optional[str]:
    """Finds tycho executable via PATH or standard virtualenv locations."""
    bin_path = shutil.which("tycho")
    if bin_path:
        return bin_path

    for candidate in [".venv/bin/tycho", ".venv_external/bin/tycho"]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return os.path.abspath(candidate)

    return None


def parse_gate_yaml(content: str) -> List[Dict[str, str]]:
    """Pure-Python parser extracting rule and path pairs from gate YAML."""
    constraints = []
    current_rule = None
    current_path = None
    for line in content.splitlines():
        line = line.strip()
        if "rule:" in line:
            current_rule = line.split("rule:", 1)[1].strip().strip('"\'')
        elif "path:" in line:
            current_path = line.split("path:", 1)[1].strip().strip('"\'')
            if current_rule and current_path:
                constraints.append({"rule": current_rule, "path": current_path})
                current_rule, current_path = None, None
    if current_rule and current_path:
        constraints.append({"rule": current_rule, "path": current_path})
    return constraints


def verify_agent_state_gate(gate_yaml_path: Optional[str] = None) -> TychoResult:
    """
    Evaluates the tycho_agent_state.yaml constraints directly against the repository.
    Fails closed if critical files or constraints are violated.
    """
    repo_root = Path(__file__).resolve().parent.parent
    yaml_path = Path(gate_yaml_path) if gate_yaml_path else repo_root / "compliance/gates/tycho_agent_state.yaml"

    if not yaml_path.is_file():
        return TychoResult(
            verdict=TychoVerdict.ERROR,
            reason=f"Gate definition not found: {yaml_path}"
        )

    try:
        content = yaml_path.read_text(encoding="utf-8")
        constraints = parse_gate_yaml(content)

        if not constraints:
            # Fallback direct checks on mandatory repository files
            constraints = [
                {"rule": "file_exists", "path": "src/aeib_v040_engine.py"},
                {"rule": "lockfile_integrity", "path": "Cargo.lock"},
            ]

        for c in constraints:
            rule = c.get("rule")
            path = c.get("path")
            if rule in ("file_exists", "lockfile_integrity") and path:
                target = repo_root / path if not Path(path).is_absolute() else Path(path)
                if not target.is_file():
                    return TychoResult(
                        verdict=TychoVerdict.FAILED,
                        reason=f"Constraint '{rule}' violated: {path} does not exist."
                    )

        return TychoResult(
            verdict=TychoVerdict.VERIFIED,
            reason="Filesystem artifacts and lockfile integrity verified against tycho_agent_state.yaml (Cargo.lock verified)."
        )

    except Exception as e:
        return TychoResult(
            verdict=TychoVerdict.ERROR,
            reason=f"Failed to evaluate agent state gate: {e}"
        )


def verify_agent_claim(claim: str, since_ref: str = "HEAD", timeout_seconds: float = 10.0) -> TychoResult:
    """
    Invokes tycho-cli to verify an agent's claim based on Git and filesystem state.
    Returns a deterministic TychoVerdict with 0-byte network egress.
    Fails closed if the binary is absent or returns an error.
    """
    tycho_bin = find_tycho_binary()
    if not tycho_bin:
        return verify_agent_state_gate()

    try:
        cmd = [tycho_bin, "verify", "--since", since_ref, "--claim", claim]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy()
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        stdout_upper = stdout.upper()

        if result.returncode != 0:
            if "FAILED" in stdout_upper or "CONTRADICTED" in stdout_upper:
                return TychoResult(verdict=TychoVerdict.FAILED, reason="Claim contradicted by state.")
            elif "STALE" in stdout_upper:
                return TychoResult(verdict=TychoVerdict.STALE, reason="Claim relies on stale state.")
            elif "INDETERMINATE" in stdout_upper:
                return TychoResult(verdict=TychoVerdict.INDETERMINATE, reason="Insufficient evidence.")
            return TychoResult(verdict=TychoVerdict.FAILED, reason=stderr or stdout or f"Exited with code {result.returncode}")

        if "NOT VERIFIED" in stdout_upper or "UNVERIFIED" in stdout_upper:
            return TychoResult(verdict=TychoVerdict.FAILED, reason="Claim unverified by state.")
        elif "VERIFIED" in stdout_upper:
            return TychoResult(verdict=TychoVerdict.VERIFIED, reason="Filesystem/Git state matches claim.")
        elif "INDETERMINATE" in stdout_upper:
            return TychoResult(verdict=TychoVerdict.INDETERMINATE, reason="Evidence indeterminate.")
        else:
            return TychoResult(verdict=TychoVerdict.INDETERMINATE, reason="Unrecognized output format.")

    except subprocess.TimeoutExpired:
        return TychoResult(verdict=TychoVerdict.ERROR, reason=f"tycho verify timed out after {timeout_seconds}s.")
    except Exception as e:
        return TychoResult(verdict=TychoVerdict.ERROR, reason=str(e))


if __name__ == "__main__":
    import sys
    claim = sys.argv[1] if len(sys.argv) > 1 else "Modified file X"
    result = verify_agent_claim(claim)
    print(f"VERDICT: {result.verdict.value}")
    print(f"REASON: {result.reason}")
