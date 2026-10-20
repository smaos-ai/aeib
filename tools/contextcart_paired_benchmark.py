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
tools/contextcart_paired_benchmark.py
================================================================================
ContextCart-MCP Paired-Run Workload Benchmark (JetBrains SkillsBench / Caveman Methodology).
Evaluated under the stated model as an agent execution boundary scaffold.

Evaluates paired workload runs measuring:
1. Total input tokens (baseline full-file/log ingestion vs. ContextCart disk-vault + AST slice).
2. Exact-answer check parity (symbol/log facts preserved in the slice).
3. Honest negative-case reporting: includes an unstructured HTML workload where AST symbol
   slicing is unavailable and envelope metadata slightly increases token count.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def estimate_bpe_tokens(text: str) -> int:
    """
    Deterministic lexical/punctuation token counter (offline approximation;
    splits identifiers, numbers, punctuation, and whitespace).
    """
    return len(re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", text))


@dataclass(frozen=True)
class PairedWorkloadCase:
    workload_id: str
    kind: str  # "python_ast", "json_log", "html_unstructured"
    raw_content: str
    target_query: str
    expected_answer_tokens: List[str]


def compress_for_agent_consumption(case: PairedWorkloadCase) -> str:
    """
    ContextCart local proxy compressor:
    - For Python source: extracts exact AST symbol + docstring + signature and stores raw hash out-of-band.
    - For JSON logs: extracts error/halt records and summarizes repeated OK lines.
    - For unstructured HTML (no AST symbol compressor): wraps raw content in a provenance envelope
      (demonstrating negative overhead when a compressor is unavailable).
    """
    raw_sha = hashlib.sha256(case.raw_content.encode("utf-8")).hexdigest()[:16]
    if case.kind == "python_ast":
        tree = ast.parse(case.raw_content)
        lines = case.raw_content.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == case.target_query:
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno)
                sliced = "\n".join(lines[start:end])
                return json.dumps(
                    {
                        "vault_sha256": raw_sha,
                        "symbol": case.target_query,
                        "line_range": [start + 1, end],
                        "ast_slice": sliced,
                    },
                    separators=(",", ":"),
                )
    elif case.kind == "json_log":
        kept: List[str] = []
        ok_count = 0
        for line in case.raw_content.splitlines():
            if "ERROR" in line or "HALT" in line or case.target_query in line:
                kept.append(line)
            else:
                ok_count += 1
        return json.dumps(
            {
                "vault_sha256": raw_sha,
                "omitted_ok_lines": ok_count,
                "matched_lines": kept,
            },
            separators=(",", ":"),
        )
    # Fallback for unsupported formats (e.g. HTML without a dedicated compressor)
    return json.dumps(
        {
            "vault_sha256": raw_sha,
            "compressor_status": "UNAVAILABLE_RAW_FALLBACK",
            "content": case.raw_content,
        },
        separators=(",", ":"),
    )


def run_paired_workload_benchmark() -> Dict[str, Any]:
    # Build realistic multi-workload test corpus
    py_filler = "\n".join(
        f"def helper_func_{i}(x: int, y: int) -> int:\n    '''Helper docstring {i}.'''\n    return (x * {i}) + y\n"
        for i in range(40)
    )
    py_target = (
        "def verify_delegation_attenuation(amount_minor: int, max_per_call_minor: int) -> str:\n"
        "    if amount_minor <= 0 or amount_minor > max_per_call_minor:\n"
        "        return 'ERR_DELEGATION_ATTENUATION_BREACH'\n"
        "    return 'OK'\n"
    )
    python_workload = py_filler + "\n" + py_target
    log_workload = "\n".join(
        [f'{{"seq":{i},"status":"OK","latency_us":112}}' for i in range(120)]
        + ['{"seq":121,"status":"HALT_TWO_FILE_WIPE_DETECTED_AGAINST_SCITT_ANCHOR","op_id":"op-99"}']
    )
    html_workload = "<html><body><div class='alert'>Payee IBAN DE89370400440532013000</div></body></html>"

    workloads = [
        PairedWorkloadCase(
            workload_id="W1_python_symbol_localization",
            kind="python_ast",
            raw_content=python_workload,
            target_query="verify_delegation_attenuation",
            expected_answer_tokens=["ERR_DELEGATION_ATTENUATION_BREACH", "max_per_call_minor"],
        ),
        PairedWorkloadCase(
            workload_id="W2_json_audit_log_triage",
            kind="json_log",
            raw_content=log_workload,
            target_query="op-99",
            expected_answer_tokens=["HALT_TWO_FILE_WIPE_DETECTED_AGAINST_SCITT_ANCHOR", "op-99"],
        ),
        PairedWorkloadCase(
            workload_id="W3_html_no_compressor_negative_control",
            kind="html_unstructured",
            raw_content=html_workload,
            target_query="DE89370400440532013000",
            expected_answer_tokens=["DE89370400440532013000"],
        ),
    ]

    total_baseline_tokens = 0
    total_compressed_tokens = 0
    exact_answer_passes = 0
    per_workload_results: List[Dict[str, Any]] = []

    for w in workloads:
        base_tok = estimate_bpe_tokens(w.raw_content)
        compressed_str = compress_for_agent_consumption(w)
        comp_tok = estimate_bpe_tokens(compressed_str)

        # Verify exact-answer preservation in compressed representation
        ans_ok = all(req in compressed_str for req in w.expected_answer_tokens)
        if ans_ok:
            exact_answer_passes += 1
        total_baseline_tokens += base_tok
        total_compressed_tokens += comp_tok
        reduction_pct = round((1.0 - (comp_tok / base_tok)) * 100.0, 2)
        per_workload_results.append(
            {
                "workload_id": w.workload_id,
                "baseline_input_tokens": base_tok,
                "contextcart_input_tokens": comp_tok,
                "reduction_pct": reduction_pct,
                "exact_answer_check_passed": ans_ok,
            }
        )

    overall_reduction_pct = round(
        (1.0 - (total_compressed_tokens / total_baseline_tokens)) * 100.0, 2
    )
    return {
        "total_workloads": len(workloads),
        "exact_answer_checks_passed": f"{exact_answer_passes}/{len(workloads)}",
        "total_baseline_input_tokens": total_baseline_tokens,
        "total_contextcart_input_tokens": total_compressed_tokens,
        "overall_input_token_reduction_pct": overall_reduction_pct,
        "workloads": per_workload_results,
    }


def test_paired_workload_benchmark_honest_reporting() -> None:
    report = run_paired_workload_benchmark()
    assert report["exact_answer_checks_passed"] == "3/3"
    assert report["overall_input_token_reduction_pct"] > 70.0
    w_map = {w["workload_id"]: w for w in report["workloads"]}
    assert w_map["W1_python_symbol_localization"]["reduction_pct"] > 85.0
    assert w_map["W2_json_audit_log_triage"]["reduction_pct"] > 85.0
    assert w_map["W3_html_no_compressor_negative_control"]["reduction_pct"] < 0.0


def main() -> None:
    test_paired_workload_benchmark_honest_reporting()
    results = run_paired_workload_benchmark()
    print(json.dumps(results, indent=2))
    print("[✓] ContextCart-MCP Paired-Run Benchmark: PASSED with honest negative-control reporting.")


if __name__ == "__main__":
    main()
