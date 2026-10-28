#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
src/dynamic_seig.py
================================================================================
SEIG v0.1: Dynamic Self-Evolution Integrity Gate for Runtime-Synthesized Tools.

Governs runtime tool synthesis and self-modifying agent behaviors (Chrysalis / Agent S4):
1. In-flight AST security audit of self-authored Python code strings.
2. Capability scope assertion (blocks unauthorized network sockets, raw OS calls, and process spawning).
3. Ephemeral subprocess dry-run execution with strict timeout bounds.
4. Mutation vector probe to verify that synthesized tools reject corrupted inputs.

Evaluated under the stated model:
- AST analysis is an in-flight static pre-filter for self-synthesized tool proposals.
- Subprocess dry-run provides isolated execution testing (prototype).
- `mount_authorized` is strictly FALSE in SEIG v0.1; SEIG never authorizes tool mounting
  into a live agent runtime by itself, requiring subsequent external policy evaluation
  and human oversight.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

DEFAULT_EXECUTION_TIMEOUT_SEC: float = 1.5  # claim: config
MAX_ERROR_MSG_LEN: int = 200  # claim: config


@dataclass(frozen=True)
class SEIGVerdict:
    """Immutable verdict for a synthesized tool evaluation."""
    verdict: str  # "STATIC_AND_DRYRUN_ACCEPTED" | "REJECTED"
    halt_code: str
    tool_name: str
    code_digest: str
    violations: Tuple[str, ...]
    dry_run_latency_ms: float
    mount_authorized: bool = False  # Strictly False in SEIG v0.1


class DynamicSelfEvolutionIntegrityGate:
    """
    In-flight static security and isolated dry-run evaluator for synthesized code.
    Fails closed on syntax errors, unauthorized imports, mock stubs, and mutation survival.
    """

    FORBIDDEN_AST_NODES = (
        ast.Delete,
        ast.Global,
        ast.Nonlocal,
    )

    FORBIDDEN_MODULES_OR_ATTRS = frozenset(
        {
            "subprocess",
            "os.system",
            "os.popen",
            "shutil",
            "ctypes",
            "socket",
            "urllib.request",
            "requests",
            "sys.modules",
            "builtins.eval",
            "builtins.exec",
        }
    )

    FORBIDDEN_METHOD_NAMES = frozenset(
        {
            "system",
            "popen",
            "eval",
            "exec",
        }
    )

    def __init__(self, execution_timeout_sec: float = DEFAULT_EXECUTION_TIMEOUT_SEC) -> None:
        self.timeout_sec = execution_timeout_sec

    def audit(
        self,
        tool_name: str,
        source_code: str,
        capability_contract: Optional[Dict[str, Any]] = None,
        sample_args: Optional[Dict[str, Any]] = None,
    ) -> SEIGVerdict:
        """
        Performs static AST inspection and dry-run verification of self-authored tool code.
        """
        t0 = time.perf_counter()
        violations: List[str] = []
        code_digest = f"sha256:{hashlib.sha256(source_code.encode('utf-8')).hexdigest()}"

        # 1. In-flight Static AST Security Audit
        try:
            tree = ast.parse(source_code, filename=f"<synthetic:{tool_name}>")
        except SyntaxError as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return SEIGVerdict(
                verdict="REJECTED",
                halt_code="HALT_SYNTHESIZED_TOOL_SYNTAX_ERROR",
                tool_name=tool_name,
                code_digest=code_digest,
                violations=(f"SyntaxError:Line {exc.lineno}:{exc.msg}",),
                dry_run_latency_ms=elapsed_ms,
                mount_authorized=False,
            )

        for node in ast.walk(tree):
            if isinstance(node, self.FORBIDDEN_AST_NODES):
                violations.append(f"FORBIDDEN_AST_NODE:{type(node).__name__}")

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.FORBIDDEN_MODULES_OR_ATTRS:
                        violations.append(f"FORBIDDEN_IMPORT:{alias.name}")

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    full_name = f"{mod}.{alias.name}" if mod else alias.name
                    if mod in self.FORBIDDEN_MODULES_OR_ATTRS or full_name in self.FORBIDDEN_MODULES_OR_ATTRS:
                        violations.append(f"FORBIDDEN_IMPORT_FROM:{full_name}")

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                if attr_name in self.FORBIDDEN_METHOD_NAMES:
                    violations.append(f"FORBIDDEN_METHOD_CALL:{attr_name}")

            # Stub heuristics
            if isinstance(node, ast.FunctionDef):
                non_doc = [
                    s for s in node.body
                    if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
                ]
                if len(non_doc) == 1 and isinstance(non_doc[0], ast.Return):
                    ret = non_doc[0].value
                    if isinstance(ret, ast.Constant) and ret.value is True:
                        violations.append(f"HALT_SYNTHESIZED_TOOL_STUB_DETECTED:{node.name}")
                    elif isinstance(ret, ast.Dict):
                        for k, v in zip(ret.keys, ret.values):
                            if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                                val_str = str(v.value).lower()
                                if val_str in ("simulated", "mock", "stub"):
                                    violations.append(f"HALT_SYNTHESIZED_TOOL_STUB_DETECTED:{node.name}")

        if violations:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return SEIGVerdict(
                verdict="REJECTED",
                halt_code="HALT_SYNTHESIZED_TOOL_FORBIDDEN_IMPORT",
                tool_name=tool_name,
                code_digest=code_digest,
                violations=tuple(violations),
                dry_run_latency_ms=elapsed_ms,
                mount_authorized=False,
            )

        # 2. Isolated Dry-Run in Ephemeral Subprocess
        dry_res = self._run_dry_run(source_code, tool_name, sample_args=sample_args)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if not dry_res["passed"]:
            return SEIGVerdict(
                verdict="REJECTED",
                halt_code=dry_res["halt_code"],
                tool_name=tool_name,
                code_digest=code_digest,
                violations=(dry_res["error"],),
                dry_run_latency_ms=elapsed_ms,
                mount_authorized=False,
            )

        return SEIGVerdict(
            verdict="STATIC_AND_DRYRUN_ACCEPTED",
            halt_code="OK_SEIG_ACCEPTED",
            tool_name=tool_name,
            code_digest=code_digest,
            violations=(),
            dry_run_latency_ms=round(elapsed_ms, 3),
            mount_authorized=False,
        )

    def verify_against_vectors(
        self,
        tool_name: str,
        source_code: str,
        positive_vectors: Sequence[Dict[str, Any]],
        mutation_vectors: Sequence[Dict[str, Any]],
    ) -> SEIGVerdict:
        """
        Validates synthesized tool behavior against positive and mutation vectors.
        Fails closed with HALT_SYNTHESIZED_TOOL_MUTATION_SURVIVED if the tool vacously
        accepts corrupted mutation inputs without raising an error or returning rejection.
        """
        first_pos = positive_vectors[0] if positive_vectors else None
        initial_verdict = self.audit(
            tool_name=tool_name,
            source_code=source_code,
            capability_contract={},
            sample_args=first_pos,
        )
        if initial_verdict.verdict != "STATIC_AND_DRYRUN_ACCEPTED":
            return initial_verdict

        probe_res = self._run_vector_probe(
            source_code=source_code,
            tool_name=tool_name,
            positive_vectors=positive_vectors,
            mutation_vectors=mutation_vectors,
        )

        if not probe_res["passed"]:
            return SEIGVerdict(
                verdict="REJECTED",
                halt_code=probe_res["halt_code"],
                tool_name=tool_name,
                code_digest=initial_verdict.code_digest,
                violations=(probe_res["error"],),
                dry_run_latency_ms=initial_verdict.dry_run_latency_ms,
                mount_authorized=False,
            )

        return initial_verdict

    def _run_dry_run(
        self,
        source_code: str,
        tool_name: str,
        sample_args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Runs the synthesized code once in an ephemeral subprocess."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                dir=tmpdir,
                delete=False,
                encoding="utf-8",
            )
            sample_json = json.dumps(sample_args) if sample_args is not None else "None"
            harness_script = (
                source_code
                + f"\n\nif __name__ == '__main__':\n"
                + f"    import inspect, json, sys\n"
                + f"    sample = {sample_json}\n"
                + f"    try:\n"
                + f"        if '{tool_name}' in globals():\n"
                + f"            fn = globals()['{tool_name}']\n"
                + f"            if callable(fn):\n"
                + f"                if sample is not None:\n"
                + f"                    res = fn(**sample)\n"
                + f"                else:\n"
                + f"                    sig = inspect.signature(fn)\n"
                + f"                    req = [p for p in sig.parameters.values() if p.default == inspect.Parameter.empty and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]\n"
                + f"                    if not req:\n"
                + f"                        res = fn()\n"
                + f"                    else:\n"
                + f"                        res = 'OK_PARAM_SIGNATURE'\n"
                + f"        else:\n"
                + f"            res = 'OK_MODULE_INIT'\n"
                + f"    except Exception as e:\n"
                + f"        print(f'EXC:{{e}}', file=sys.stderr)\n"
                + f"        sys.exit(1)\n"
            )
            fpath.write(harness_script)
            fpath.flush()
            fpath.close()

            try:
                res = subprocess.run(
                    [sys.executable, fpath.name],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                )
                if res.returncode != 0:
                    err = res.stderr.strip()[:MAX_ERROR_MSG_LEN]
                    return {
                        "passed": False,
                        "halt_code": "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED",
                        "error": err if err else "EXIT_NONZERO",
                    }
            except subprocess.TimeoutExpired:
                return {
                    "passed": False,
                    "halt_code": "HALT_SYNTHESIZED_TOOL_TIMEOUT",
                    "error": "ERR_DRYRUN_TIMEOUT",
                }
            except Exception as exc:
                return {
                    "passed": False,
                    "halt_code": "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED",
                    "error": str(exc),
                }

        return {"passed": True, "halt_code": "OK", "error": ""}

    def _run_vector_probe(
        self,
        source_code: str,
        tool_name: str,
        positive_vectors: Sequence[Dict[str, Any]],
        mutation_vectors: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Probes synthesized tool against positive and negative mutation vectors in subprocess."""
        with tempfile.TemporaryDirectory() as tmpdir:
            probe_path = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                dir=tmpdir,
                delete=False,
                encoding="utf-8",
            )
            harness_code = f"""
import json
import sys

{source_code}

pos_vecs = {json.dumps(list(positive_vectors))}
mut_vecs = {json.dumps(list(mutation_vectors))}

if "{tool_name}" not in globals():
    sys.exit(2)

fn = globals()["{tool_name}"]

# Test positive vectors
for vec in pos_vecs:
    try:
        fn(**vec)
    except Exception as e:
        print(f"POS_FAIL:{{e}}")
        sys.exit(3)

# Test mutation vectors
for vec in mut_vecs:
    try:
        res = fn(**vec)
        # If tool returns True or static dict on corrupted input without failing, mutant survived
        if res is True or (isinstance(res, dict) and str(res.get("status", "")).lower() in ("simulated", "mock", "ok")):
            print(f"MUT_SURVIVED:{{vec}}")
            sys.exit(4)
    except Exception:
        pass  # Expected rejection of corrupted input

sys.exit(0)
"""
            probe_path.write(harness_code)
            probe_path.flush()
            probe_path.close()

            try:
                proc = subprocess.run(
                    [sys.executable, probe_path.name],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                )
                if proc.returncode == 4:
                    return {
                        "passed": False,
                        "halt_code": "HALT_SYNTHESIZED_TOOL_MUTATION_SURVIVED",
                        "error": proc.stdout.strip()[:MAX_ERROR_MSG_LEN],
                    }
                elif proc.returncode != 0:
                    raw_err = proc.stdout.strip() or proc.stderr.strip()
                    return {
                        "passed": False,
                        "halt_code": "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED",
                        "error": raw_err[:MAX_ERROR_MSG_LEN],
                    }
            except subprocess.TimeoutExpired:
                return {
                    "passed": False,
                    "halt_code": "HALT_SYNTHESIZED_TOOL_TIMEOUT",
                    "error": "ERR_PROBE_TIMEOUT",
                }
            except Exception as exc:
                return {
                    "passed": False,
                    "halt_code": "HALT_SYNTHESIZED_TOOL_DRYRUN_FAILED",
                    "error": str(exc),
                }

        return {"passed": True, "halt_code": "OK", "error": ""}
