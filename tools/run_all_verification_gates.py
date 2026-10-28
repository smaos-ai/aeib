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
tools/run_all_verification_gates.py
================================================================================
Unified AEIB / SMAOS Verification Gate Orchestrator.
Executes all verification suites, mutation oracles, formal MAGS provers, and
benchmark verification scripts in sequence. Fails closed immediately on any
assertion failure or banned term.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import FrozenSet, List, Tuple

BANNED_TERMS = (
    "100% safe",
    "clinically validated",
    "quantum-safe",
    "zero vulnerabilities",
    "proven universal[l]y",
    "bullet[p]roof",
    "enterprise-[g]rade",
    "production-[s]afe",
    "100% [s]ecure",
    "unassailable",
    "unhackable",
    "bank-grade",
    "production-ready",
)


def run_cmd(name: str, cmd: List[str]) -> Tuple[bool, float, str]:
    print(f"\n[GATE RUNNING] {name}...")
    print(f"  Command: {' '.join(cmd)}")
    t0 = time.perf_counter()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120.0)
        elapsed = (time.perf_counter() - t0) * 1000.0
        if res.returncode != 0:
            print(f"  [FAILED] {name} exited with status {res.returncode}")
            print("--- STDOUT ---")
            print(res.stdout[-1500:])
            print("--- STDERR ---")
            print(res.stderr[-1500:])
            return False, elapsed, res.stderr or res.stdout
        print(f"  [PASSED] {name} ({elapsed:.1f}ms)")
        return True, elapsed, res.stdout
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {name} exceeded 120s limit.")
        return False, 120000.0, "TIMEOUT"
    except Exception as exc:
        print(f"  [ERROR] {name} threw exception: {exc}")
        return False, 0.0, str(exc)


# Files whose job is to define the denylist (and therefore must contain the
# literals). Paths are relative to the repository root.
DENYLIST_DEFINITION_FILES: Tuple[str, ...] = (
    "tools/run_all_verification_gates.py",
)


def _denylist_definition_files() -> FrozenSet[Path]:
    return frozenset(Path(p).resolve() for p in DENYLIST_DEFINITION_FILES)


# A line that is ONLY a word-bounded regex literal, e.g.  r"\bterm\b",
# is a denylist definition entry (prose never has this shape). Only such
# lines are exempt; every other line of the same file is still scanned.
_DENYLIST_REGEX_LITERAL_LINE = re.compile(r"""^\s*r?(["'])\\b[^"'\n]*\\b\1\s*,?\s*$""")


def _strip_denylist_regex_literal_lines(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not _DENYLIST_REGEX_LITERAL_LINE.match(line)
    )


def check_banned_terms_in_codebase() -> bool:
    print("\n[GATE RUNNING] Banned Term & Anti-Overclaim Scanner...")
    roots = ("src", "tools", "tests", "benchmarks")
    violations = 0
    for root in roots:
        p = Path(root)
        if not p.exists():
            continue
        for fpath in p.rglob("*.py"):
            text = fpath.read_text(encoding="utf-8", errors="ignore")
            # Only explicit denylist-definition files are exempt. Mentioning the
            # token "BANNED_TERMS" no longer opts a file out of the scan.
            if fpath.resolve() in _denylist_definition_files():
                continue
            lower_text = _strip_denylist_regex_literal_lines(text).lower()
            for term in BANNED_TERMS:
                # Terms are regex patterns (char-class form, as in the pre-commit hook's
                # BANNED_RE) so this denylist definition does not itself trip the hook.
                if re.search(term.lower(), lower_text):
                    print(f"  [VIOLATION] Banned term '{term}' found in {fpath}")
                    violations += 1
    if violations > 0:
        print(f"  [FAILED] Found {violations} banned overclaim instances.")
        return False
    print(f"  [OK] {violations} banned overclaim terms found in scanned roots.")
    return True


def main() -> None:
    print("==================================================================")
    print(" AEIB / SMAOS UNIFIED VERIFICATION GATE RUNNER")
    print("==================================================================")
    gates: List[Tuple[str, List[str]]] = [
        ("Phase 0 & Track 1 Core Guard Lock", [sys.executable, "src/aeib_track1_and_calibrated_guards.py"]),
        ("Variant Input Contract & 9-Vector Oracle", [sys.executable, "src/bio_variant_contract.py"]),
        ("Variant Evidence Benchmark", [sys.executable, "benchmarks/variant_evidence_benchmark.py"]),
        ("Inverse Lifecycle Referee & Complexity Profiler", [sys.executable, "src/inverse_lifecycle_referee.py"]),
        ("Zone Boundary Enforcement Scanner", [sys.executable, "compliance/check_zone_boundary.py"]),
        ("AST Purity Scanner", [sys.executable, "compliance/ast_purity.py", "."]),
        ("Zero-Mock Enforcer", [sys.executable, "compliance/no_mock_enforcer.py"]),
        ("Claim Integrity Gate", [sys.executable, "compliance/claim_integrity_gate.py", "--all"]),
        ("Formal MAGS Gate & Bounded Model Checker", ["pytest", "tests/test_formal_mags_gate.py", "-v"]),
        ("Kernel Apoptosis Gate & Homeostatic Membrane", ["pytest", "tests/test_kernel_apoptosis_gate.py", "-v"]),
        ("Apoptosis Sentinel & Verification Tax Benchmark", ["pytest", "tests/test_apoptosis_sentinel.py", "-v"]),
        ("Epistemic Intent Compiler", ["pytest", "tests/test_epistemic_intent_compiler.py", "-v"]),
        ("Repo Reverse-Engineering & Architectural Synthesis Engine", ["pytest", "tests/test_repo_reverse_engineering_engine.py", "-v"]),
        (
            "Frontier Dynamic SEIG & Stateful HITL Suite",
            [
                "pytest",
                "tests/test_inverse_lifecycle_referee.py",
                "tests/test_dynamic_seig.py",
                "tests/test_stateful_hitl.py",
                "tests/test_external_policy_gate.py",
                "tests/test_harness_router.py",
                "tests/test_human_translation_compiler.py",
                "-v",
            ],
        ),
        (
            "Sections 30-32 Durable EO1, HyperSU, LJCR, & Bio-AEIB Suites",
            [
                "pytest",
                "tests/test_eo1_write_before_execute.py",
                "tests/test_hypersu_fts.py",
                "tests/test_hypersu_provenance.py",
                "tests/test_aeib_gateway_integrity_benchmark.py",
                "tests/test_toyota_volvo_dac_checkpoint_monitor.py",
                "tests/test_model_integrity_layer_and_bio_aeib_gate.py",
                "tests/test_oct2026_runtime_trace_contextcart_and_hazard_gate.py",
                "tests/test_dir_antiscaffold_and_x402_escrow_engine.py",
                "tests/test_antigravity_token_telemetry_audit.py",
                "tests/test_epistemic_verifier_and_x402_governor.py",
                "tests/test_claim_integrity_gate.py",
                "tests/test_zk_budget_proof_engine.py",
                "tests/test_covering_design_discovery.py",
                "-v",
            ],
        ),
        (
            "Sections 35-38 Anti-Scaffold, Track 1, Tri-Track, & Bio-Digital Suites",
            [
                "pytest",
                "tests/test_anti_scaffold_falsifier.py",
                "tests/test_aeib_track1_and_calibrated_guards.py",
                "tests/test_gemma_developer_agent_engine.py",
                "tests/test_huntr_agent_vulnerability_scanner.py",
                "tests/test_coinbase_x402_agent_gateway.py",
                "tests/test_variant_validation.py",
                "tests/test_sources_dbsnp.py",
                "tests/test_sources_alphagenome_encode.py",
                "tests/test_variant_evidence_pipeline.py",
                "-v",
            ],
        ),
        (
            "Sections 40-43 Autopoietic Epistemic Mesh & Sovereign Moat Suites",
            [
                "pytest",
                "tests/test_sovereign_moat_upgrades.py",
                "tests/test_deterministic_graph_executor.py",
                "tests/test_model_manifest_verifier.py",
                "tests/test_slop_filter.py",
                "tests/test_pre_tool_use_chain.py",
                "tests/test_pre_tool_use_chain_binding.py",
                "tests/test_anti_gravity_context_cart.py",
                "tests/test_parallel_tracks_abcde.py",
                "tests/test_wave7_steward_sphinx_and_escalation.py",
                "tests/test_wave7_defect_probes.py",
                "tests/test_ios_harness_boundary.py",
                "tests/test_truth_compass.py",
                "tests/test_truth_compass_repo_integration.py",
                "tests/test_jcs_canonicalizer_discovery.py",
                "tests/test_biometric_hitl_gate.py",
                "tests/test_proof_carrying_handoff.py",
                "tests/test_mixture_of_models_and_mom.py",
                "tests/test_rssi_harness_evolver.py",
                "tests/test_notebooklm_bridge.py",
                "-v",
            ],
        ),
    ]

    results: List[Tuple[str, bool, float]] = []
    all_passed = True
    for name, cmd in gates:
        passed, latency, _ = run_cmd(name, cmd)
        results.append((name, passed, latency))
        if not passed:
            all_passed = False
            # Fail fast on critical early gates
            if "Phase 0" in name or "Zone Boundary" in name or "AST Purity" in name:
                print("\n[HALT] Critical base gate failed. Aborting sequence.")
                sys.exit(1)

    # Run Banned Terms Scan
    t_ban = time.perf_counter()
    banned_ok = check_banned_terms_in_codebase()
    results.append(("Banned Term & Anti-Overclaim Scanner", banned_ok, (time.perf_counter() - t_ban) * 1000.0))
    if not banned_ok:
        all_passed = False

    print("\n==================================================================")
    print(" VERIFICATION GATE SUMMARY TABLE")
    print("==================================================================")
    print(f"{'GATE / COMPONENT':<50} | {'STATUS':<8} | {'LATENCY':<10}")
    print("-" * 74)
    for name, passed, lat in results:
        status_str = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:<50} | {status_str:<8} | {lat:>7.1f}ms")
    print("-" * 74)

    passed_count = sum(1 for _, ok, _ in results if ok)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(
        f"\n{passed_count}/{len(results)} gates exited 0 on {stamp}; "
        "see per-gate output above. This is not a certification."
    )
    if all_passed:
        sys.exit(0)
    print("[HALT] One or more verification gates failed.")
    sys.exit(1)


if __name__ == "__main__":
    main()
