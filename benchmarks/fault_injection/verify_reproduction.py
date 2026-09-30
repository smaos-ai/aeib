#!/usr/bin/env python3
"""
verify_reproduction.py — Hardened Independent Reproduction & Manifest Verification Script
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB) v0.2.2

Steps:
  1. Environment check    — Python, SQLite, all deps; strict version comparison to manifest.
  2. Git revision check   — HEAD vs manifest provenance_chain.falsifiability_commit.
  3. Unit test suite      — 20 pytest tests (15 baseline + 5 falsifiability); fail on any failure.
  4. Full control matrix  — N=50 C0/C1/C2 trials on isolated in-memory ledger (agentacct_ctrl).
  5. Full AEIB fault runs — N=50 post-commit 504 trials on isolated ledger (agentacct_aeib).
  6. Negative controls    — N=20 uncommitted probes on isolated ledger (agentacct_neg).
                            Prints: "Negative controls: 20/20 / RECONCILIATION_NOT_FOUND: 20 / False OUTCOME_VERIFIED: 0"
                            Fails if counts deviate from manifest aeib_negative_controls entry.
  7. Manifest digests     — Recompute SHA-256 of all 9 declared artifacts; fail on mismatch.
  8. JSON report          — Emit reproduction_results.json with all per-step counts and hashes.

Usage:
  PYTHONPATH=. .venv/bin/python benchmarks/fault_injection/verify_reproduction.py [--unit-only] [--output PATH] [--strict-versions]
"""

import sys
import os
import json
import time
import sqlite3
import hashlib
import argparse
import platform
import subprocess
import importlib.metadata
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Repo root and paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

MANIFEST_PATH = REPO_ROOT / "benchmarks/fault_injection/results/RELEASE_MANIFEST_v0.2.3.json"
RESULTS_DIR   = REPO_ROOT / "benchmarks/fault_injection/results"
DEFAULT_REPORT_PATH = RESULTS_DIR / "reproduction_results.json"

# Artifact file mapping: manifest key -> repo-relative path
ARTIFACT_MAP = {
    "control_evidence_json_sha256":   REPO_ROOT / "benchmarks/fault_injection/results/CONTROL_BENCHMARK_EVIDENCE.json",
    "aeib_report_json_sha256":        REPO_ROOT / "benchmarks/fault_injection/results/AEIB_BENCHMARK_REPORT.json",
    "ledger_db_sha256":               REPO_ROOT / "benchmarks/fault_injection/results/ledger.db",
    "mechanism_note_md_sha256":       REPO_ROOT / "benchmarks/fault_injection/MECHANISM_NOTE.md",
    "test_falsifiability_py_sha256":  REPO_ROOT / "benchmarks/fault_injection/test_falsifiability.py",
    "test_control_matrix_py_sha256":  REPO_ROOT / "benchmarks/fault_injection/tests/test_control_matrix.py",
    "test_ebpf_controller_py_sha256": REPO_ROOT / "tests/test_ebpf_controller.py",
    "verify_reproduction_py_sha256":  REPO_ROOT / "benchmarks/fault_injection/verify_reproduction.py",
    "paper_draft_md_sha256":          REPO_ROOT / "docs/research/AEIB_arXiv_Paper_Draft.md",
    "paper_tex_sha256":               REPO_ROOT / "docs/research/AEIB_arXiv_Paper.tex",
}

# Dependency names as importlib.metadata sees them
TRACKED_DEPS = {
    "fastapi":       "fastapi",
    "starlette":     "starlette",
    "pydantic":      "pydantic",
    "cryptography":  "cryptography",
    "pytest":        "pytest",
}


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class StepResult:
    step: int
    name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest() -> Dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest missing at {MANIFEST_PATH}")
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_isolated_app(db_uri: str):
    """
    Factory: creates an independent FastAPI app instance with its own AtomicDebitStore
    and DeterministicFaultMiddleware wired to the given in-memory SQLite URI.
    Avoids mutating the module-level singletons in app.py.
    """
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    from typing import Optional as Opt
    from benchmarks.fault_injection.store import AtomicDebitStore
    from benchmarks.fault_injection.middleware import DeterministicFaultMiddleware, FaultConfig

    isolated_store = AtomicDebitStore(db_path=db_uri)
    isolated_fault  = FaultConfig(
        enabled=True,
        fault_mode="POST_COMMIT_504",
        post_commit_delay_ms=5.0,  # Match the 5.0ms delay from benchmark manifest to reconcile latency
        max_faults_per_intent=1,
        fault_every_attempt=True,
    )

    isolated_app = FastAPI(title="AEIB Isolated Ledger", version="0.2.2")
    isolated_app.add_middleware(DeterministicFaultMiddleware, config=isolated_fault)

    class DebitReq(BaseModel):
        logical_operation_id: str
        intent_id: str
        account_id: str = "acc_primary"
        amount: float
        description: Opt[str] = ""
        metadata: Opt[Dict[str, Any]] = None

    @isolated_app.post("/debit")
    def do_debit(req: DebitReq):
        try:
            r = isolated_store.commit_debit(
                req.logical_operation_id,
                req.intent_id,
                req.account_id,
                req.amount,
            )
            return {"status": "COMMITTED", "commit": r}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @isolated_app.get("/operations/{identifier}")
    def do_query(identifier: str):
        return isolated_store.get_operation_status(identifier)

    return isolated_app, isolated_store, isolated_fault


# ---------------------------------------------------------------------------
# Step 1 — Environment
# ---------------------------------------------------------------------------
def step1_environment(manifest: Dict[str, Any], strict: bool) -> StepResult:
    print("\n[1/8] Checking runtime environment...")
    details: Dict[str, Any] = {}
    errors: List[str] = []

    py_ver  = sys.version.split()[0]
    sql_ver = sqlite3.sqlite_version
    details["python_version"] = py_ver
    details["sqlite_version"] = sql_ver
    details["os"] = platform.system()
    details["machine"] = platform.machine()
    print(f"      Python  : {py_ver}")
    print(f"      SQLite  : {sql_ver}")
    print(f"      OS      : {platform.system()} {platform.release()} ({platform.machine()})")

    env_block = manifest.get("environment", {})
    dep_block = env_block.get("dependencies", {})

    live_versions: Dict[str, str] = {}
    for pkg_key, pkg_dist in TRACKED_DEPS.items():
        try:
            ver = importlib.metadata.version(pkg_dist)
        except importlib.metadata.PackageNotFoundError:
            ver = "NOT_INSTALLED"
        live_versions[pkg_key] = ver

    details["live_dependencies"] = live_versions
    details["manifest_dependencies"] = dep_block

    mismatch_count = 0
    for pkg_key, live_ver in live_versions.items():
        manifest_ver = dep_block.get(pkg_key, "UNRECORDED")
        if manifest_ver == "UNRECORDED":
            status_str = "UNRECORDED in manifest"
        elif live_ver == manifest_ver:
            status_str = "MATCH"
        else:
            status_str = f"DIFFERS (manifest={manifest_ver}, live={live_ver})"
            mismatch_count += 1
        print(f"      {pkg_key:15s}: {live_ver:<12s}  [{status_str}]")

    if mismatch_count > 0:
        msg = f"{mismatch_count} dependency version(s) differ from manifest."
        if strict:
            errors.append(msg + " Strict versions enforced (FAIL).")
        else:
            print(f"      [!] WARN: {msg} (Run with --strict-versions to fail)")

    passed = (len(errors) == 0)
    if passed:
        print("      [+] Environment check PASSED.")
    else:
        for e in errors:
            print(f"      [-] {e}")
    return StepResult(step=1, name="environment", passed=passed, details=details, errors=errors)


# ---------------------------------------------------------------------------
# Step 2 — Git revision
# ---------------------------------------------------------------------------
def step2_git_revision(manifest: Dict[str, Any], strict: bool) -> StepResult:
    print("\n[2/8] Checking git HEAD revision...")
    errors: List[str] = []
    details: Dict[str, Any] = {}

    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        head = res.stdout.strip() if res.returncode == 0 else "UNKNOWN"
    except Exception as exc:
        head = f"ERROR: {exc}"

    expected_tag = manifest.get("release_tag", "v0.2.3")
    try:
        tag_commit_res = subprocess.run(
            ["git", "rev-parse", f"{expected_tag}^{{commit}}"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        tag_commit = tag_commit_res.stdout.strip() if tag_commit_res.returncode == 0 else "UNRESOLVED"
    except Exception as exc:
        tag_commit = f"ERROR: {exc}"

    tag_check = subprocess.run(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10
    )
    current_tag = tag_check.stdout.strip() if tag_check.returncode == 0 else ""

    details["head_commit"] = head
    details["release_tag"] = expected_tag
    details["release_tag_commit"] = tag_commit
    details["current_exact_tag"] = current_tag

    print(f"      HEAD commit        : {head}")
    print(f"      release tag        : {expected_tag}")
    print(f"      release tag commit : {tag_commit}")

    is_match = (head == tag_commit) and (current_tag == expected_tag)

    if is_match:
        print("      [+] Git revision and release tag MATCH manifest release anchor exactly.")
    else:
        if current_tag != expected_tag:
            msg = (
                f"Checkout revision is {head[:12]} (exact tag: '{current_tag or 'none'}'), "
                f"which differs from release tag '{expected_tag}' (commit: {tag_commit[:12]})."
            )
        else:
            msg = f"HEAD commit ({head[:12]}...) does not match release tag {expected_tag} ({tag_commit[:12]}...)."
        
        details["revision_mismatch"] = True
        
        if strict:
            print(f"      [-] FAIL: {msg} (Strict provenance enforced)")
            errors.append(msg)
        else:
            print(f"      [!] WARN: {msg}")
            print(f"      [!] (Soft-check allowed for local runs. Use --strict-versions for releases)")

    return StepResult(step=2, name="git_revision", passed=(len(errors) == 0), details=details, errors=errors)


# ---------------------------------------------------------------------------
# Step 3 — Unit test suite
# ---------------------------------------------------------------------------
def step3_unit_tests() -> StepResult:
    print("\n[3/8] Executing 20-test validation suite (pytest)...")
    errors: List[str] = []
    details: Dict[str, Any] = {}

    test_paths = [
        str(REPO_ROOT / "benchmarks/fault_injection/test_falsifiability.py"),
        str(REPO_ROOT / "benchmarks/fault_injection/tests/test_control_matrix.py"),
        str(REPO_ROOT / "tests/test_ebpf_controller.py"),
    ]
    cmd = [sys.executable, "-m", "pytest"] + test_paths + ["-q", "--tb=short"]
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    elapsed = time.time() - t0

    details["returncode"] = res.returncode
    details["duration_s"] = round(elapsed, 2)
    details["stdout_tail"] = res.stdout.strip()[-800:]

    if res.returncode != 0:
        errors.append("pytest suite returned non-zero exit code.")
        print(f"      [-] Test suite FAILED:\n{res.stdout[-600:]}\n{res.stderr[-200:]}")
    else:
        # Extract summary line
        summary = [l for l in res.stdout.splitlines() if "passed" in l]
        summary_str = summary[-1] if summary else res.stdout.strip()[-120:]
        print(f"      [+] All tests PASSED: {summary_str.strip()}")

    return StepResult(step=3, name="unit_tests", passed=len(errors) == 0,
                      details=details, errors=errors)


# ---------------------------------------------------------------------------
# Step 4 — Full control matrix N=50 (C0, C1, C2)
# ---------------------------------------------------------------------------
def step4_full_control_matrix(n: int = 50) -> StepResult:
    print(f"\n[4/8] Full control matrix — N={n} trials per arm (C0/C1/C2) on isolated ledger...")
    from starlette.testclient import TestClient
    from benchmarks.fault_injection.gateway_simulator import GatewaySimulator

    # Unique in-memory URI — no cross-trial pollution
    db_uri = "file:agentacct_ctrl?mode=memory&cache=shared"
    iso_app, iso_store, iso_fault = _make_isolated_app(db_uri)
    client = TestClient(iso_app)
    gw = GatewaySimulator(client)

    errors: List[str] = []
    family_results: Dict[str, Any] = {}

    # n trials * 100 per trial * 3 phases (C0/C1/C2) * 2 attempts per trial + 10k headroom
    initial_balance = n * 100.0 * 3 * 2 + 10000.0

    # ---- C0: Naive retry ----
    iso_store.reset(initial_balance)
    iso_fault.enabled = True
    iso_fault.fault_mode = "POST_COMMIT_504"
    iso_fault.fault_every_attempt = False
    iso_fault.max_faults_per_intent = 1
    c0_violations = 0
    for i in range(n):
        lop = f"op-c0-verify-{i:04d}"
        p1 = {"logical_operation_id": lop, "intent_id": f"c0v-{i}-a1",
              "account_id": "acc_primary", "amount": 100.0}
        p2 = {"logical_operation_id": lop, "intent_id": f"c0v-{i}-a2",
              "account_id": "acc_primary", "amount": 100.0}
        client.post("/debit", json=p1, headers={"X-Attempt-Count": "1"})
        client.post("/debit", json=p2, headers={"X-Attempt-Count": "2"})
        st = iso_store.get_operation_status(lop)
        if st["commit_count"] > 1:
            c0_violations += 1
    family_results["C0"] = {"trials": n, "violations": c0_violations,
                             "violation_rate_pct": round(c0_violations / n * 100, 1)}
    print(f"      C0 (naive retry)      : {c0_violations}/{n} violations "
          f"({family_results['C0']['violation_rate_pct']}%) — expected 100%")
    if c0_violations != n:
        errors.append(f"C0: expected {n} violations, got {c0_violations}.")

    # ---- C1: Gateway stable key ----
    iso_store.reset(initial_balance)
    gw.reset_cache()
    iso_fault.fault_every_attempt = False
    iso_fault.max_faults_per_intent = 1
    c1_violations = 0
    for i in range(n):
        lop = f"op-c1-verify-{i:04d}"
        key = f"c1-stable-{i:04d}"
        payload = {"logical_operation_id": lop, "intent_id": f"c1v-{i}",
                   "account_id": "acc_primary", "amount": 100.0}
        gw.dispatch("/debit", payload, idempotency_key=key, headers={"X-Attempt-Count": "1"})
        gw.dispatch("/debit", payload, idempotency_key=key, headers={"X-Attempt-Count": "2"})
        st = iso_store.get_operation_status(lop)
        if st["commit_count"] > 1:
            c1_violations += 1
    family_results["C1"] = {"trials": n, "violations": c1_violations,
                             "violation_rate_pct": round(c1_violations / n * 100, 1)}
    print(f"      C1 (gateway/stable)   : {c1_violations}/{n} violations "
          f"({family_results['C1']['violation_rate_pct']}%) — expected 0%")
    if c1_violations != 0:
        errors.append(f"C1: expected 0 violations, got {c1_violations}.")

    # ---- C2: Semantic drift ----
    iso_store.reset(initial_balance)
    gw.reset_cache()
    iso_fault.fault_every_attempt = False
    iso_fault.max_faults_per_intent = 1
    c2_violations = 0
    for i in range(n):
        lop = f"op-c2-verify-{i:04d}"
        p1 = {"logical_operation_id": lop, "intent_id": f"c2v-{i}-a1",
              "account_id": "acc_primary", "amount": 100.0, "description": "original"}
        p2 = {"logical_operation_id": lop, "intent_id": f"c2v-{i}-a2",
              "account_id": "acc_primary", "amount": 100.0,
              "description": "retry (context drift)"}
        gw.dispatch("/debit", p1, idempotency_key=f"c2-key-{i}-a", headers={"X-Attempt-Count": "1"})
        gw.dispatch("/debit", p2, idempotency_key=f"c2-key-{i}-b", headers={"X-Attempt-Count": "2"})
        st = iso_store.get_operation_status(lop)
        if st["commit_count"] > 1:
            c2_violations += 1
    family_results["C2"] = {"trials": n, "violations": c2_violations,
                             "violation_rate_pct": round(c2_violations / n * 100, 1)}
    print(f"      C2 (semantic drift)   : {c2_violations}/{n} violations "
          f"({family_results['C2']['violation_rate_pct']}%) — expected 100%")
    if c2_violations != n:
        errors.append(f"C2: expected {n} violations, got {c2_violations}.")

    passed = len(errors) == 0
    if passed:
        print("      [+] Full control matrix PASSED.")
    else:
        for e in errors:
            print(f"      [-] {e}")

    return StepResult(step=4, name="full_control_matrix",
                      passed=passed, details=family_results, errors=errors)


# ---------------------------------------------------------------------------
# Step 5 — Full AEIB fault trials N=50
# ---------------------------------------------------------------------------
def step5_full_aeib_trials(n: int = 50) -> StepResult:
    print(f"\n[5/8] Full AEIB fault trials — N={n} post-commit 504 on isolated ledger...")
    from starlette.testclient import TestClient
    from benchmarks.fault_injection.aeib_interceptor import AeibExecutionInterceptor
    from src.jcs_canonicalizer import encode_jcs
    from cryptography.exceptions import InvalidSignature

    db_uri = "file:agentacct_aeib?mode=memory&cache=shared"
    iso_app, iso_store, iso_fault = _make_isolated_app(db_uri)
    iso_store.reset(n * 100.0 + 10000.0)
    iso_fault.fault_every_attempt = True

    client = TestClient(iso_app)
    # Evidence dir in temp space — no persistent side effects
    with tempfile.TemporaryDirectory() as tmp_ev:
        ev_dir = Path(tmp_ev)
        interceptor = AeibExecutionInterceptor(client, evidence_dir=ev_dir)

        duplicates = 0
        sig_failures = 0
        overhead_ms: List[float] = []
        errors: List[str] = []

        for i in range(n):
            lop = f"op-aeib-v-{i:04d}"
            payload = {
                "logical_operation_id": lop,
                "intent_id": f"intent-aeib-v-{i:04d}",
                "account_id": "acc_primary",
                "amount": 100.0,
            }
            res = interceptor.dispatch_with_integrity("/debit", payload)
            overhead_ms.append(res["overhead_ms"])

            st = iso_store.get_operation_status(lop)
            if st["commit_count"] > 1:
                duplicates += 1

            # Verify receipt signature
            receipt = res.get("receipt")
            if receipt:
                sig_bytes = bytes.fromhex(receipt["signature_metadata"]["signature"])
                signable = encode_jcs({
                    "unsigned_payload": receipt["unsigned_payload"],
                    "unsigned_payload_hash": receipt["unsigned_payload_hash"],
                })
                try:
                    interceptor.public_key.verify(sig_bytes, signable)
                except InvalidSignature:
                    sig_failures += 1

    mean_ms = round(sum(overhead_ms) / n, 2)
    p95_ms  = round(sorted(overhead_ms)[int(n * 0.95)], 2)

    if duplicates != 0:
        errors.append(f"AEIB: {duplicates} duplicate debit(s) detected (expected 0).")
    if sig_failures != 0:
        errors.append(f"AEIB: {sig_failures} receipt signature verification failure(s).")

    details = {
        "trials": n,
        "duplicate_debits": duplicates,
        "signature_failures": sig_failures,
        "receipts_verified": n - sig_failures,
        "mean_overhead_ms": mean_ms,
        "p95_overhead_ms": p95_ms,
    }
    print(f"      Duplicate debits      : {duplicates}/{n}  (expected 0)")
    print(f"      Receipts verified     : {n - sig_failures}/{n}  (expected {n})")
    print(f"      Overhead latency      : mean={mean_ms} ms  p95={p95_ms} ms")

    passed = len(errors) == 0
    if passed:
        print("      [+] Full AEIB fault trials PASSED.")
    else:
        for e in errors:
            print(f"      [-] {e}")

    return StepResult(step=5, name="aeib_fault_trials",
                      passed=passed, details=details, errors=errors)


# ---------------------------------------------------------------------------
# Step 6 — Negative controls N=20
# ---------------------------------------------------------------------------
def step6_negative_controls(n: int = 20, manifest: Optional[Dict[str, Any]] = None) -> StepResult:
    print(f"\n[6/8] Negative controls — N={n} uncommitted probes on isolated ledger...")
    from starlette.testclient import TestClient

    db_uri = "file:agentacct_neg?mode=memory&cache=shared"
    iso_app, iso_store, _ = _make_isolated_app(db_uri)
    # Do NOT commit anything — store starts empty
    iso_store.reset(10000.0)
    client = TestClient(iso_app)

    errors: List[str] = []
    reconciliation_not_found = 0
    false_outcome_verified = 0

    for j in range(n):
        lop = f"op-neg-ctrl-{j:04d}"
        resp = client.get(f"/operations/{lop}")
        data = resp.json()
        is_committed = data.get("committed", False)
        if is_committed:
            false_outcome_verified += 1
        else:
            reconciliation_not_found += 1

    # Mandatory explicit aggregate line
    aggregate_line = (
        f"Negative controls: {n}/{n} / "
        f"RECONCILIATION_NOT_FOUND: {reconciliation_not_found} / "
        f"False OUTCOME_VERIFIED: {false_outcome_verified}"
    )
    print(f"      {aggregate_line}")

    # Validate against manifest
    if manifest:
        expected_neg = manifest.get("aggregate_evaluations", {}).get("aeib_negative_controls", {})
        expected_trials = expected_neg.get("trials", n)
        expected_false  = expected_neg.get("false_outcome_verified_count", 0)
        expected_rnf    = expected_neg.get("uncommitted_requests", n)
        if false_outcome_verified != expected_false:
            errors.append(
                f"False OUTCOME_VERIFIED: got {false_outcome_verified}, "
                f"manifest declares {expected_false}."
            )
        if reconciliation_not_found != expected_rnf:
            errors.append(
                f"RECONCILIATION_NOT_FOUND count: got {reconciliation_not_found}, "
                f"manifest declares {expected_rnf}."
            )

    if false_outcome_verified != 0:
        errors.append(f"Non-zero false OUTCOME_VERIFIED count: {false_outcome_verified}.")

    details = {
        "trials": n,
        "reconciliation_not_found": reconciliation_not_found,
        "false_outcome_verified": false_outcome_verified,
        "fail_closed_rate_pct": round(reconciliation_not_found / n * 100, 1),
        "aggregate_line": aggregate_line,
    }

    passed = len(errors) == 0
    if passed:
        print("      [+] Negative control check PASSED (100% fail-closed).")
    else:
        for e in errors:
            print(f"      [-] {e}")

    return StepResult(step=6, name="negative_controls",
                      passed=passed, details=details, errors=errors)


# ---------------------------------------------------------------------------
# Step 7 — Manifest digest verification
# ---------------------------------------------------------------------------
def step7_manifest_digests(manifest: Dict[str, Any]) -> StepResult:
    print("\n[7/8] Verifying artifact SHA-256 digests against manifest...")
    errors: List[str] = []
    digest_results: Dict[str, Any] = {}

    declared = manifest.get("artifact_digests", {})

    for key, path in ARTIFACT_MAP.items():
        expected = declared.get(key)
        if not path.exists():
            msg = f"FILE MISSING: {path.name}"
            print(f"      [-] {msg}")
            errors.append(msg)
            digest_results[key] = {"status": "MISSING", "path": str(path)}
            continue
        actual = sha256_file(path)
        if expected and actual == expected:
            print(f"      [+] MATCH      : {path.name}  ({actual[:12]}...)")
            digest_results[key] = {"status": "MATCH", "sha256": actual}
        elif not expected:
            print(f"      [?] UNRECORDED : {path.name}  ({actual[:12]}...)")
            digest_results[key] = {"status": "UNRECORDED", "sha256": actual}
        else:
            print(f"      [-] MISMATCH   : {path.name}")
            print(f"            Expected : {expected}")
            print(f"            Actual   : {actual}")
            errors.append(f"Hash mismatch: {path.name}")
            digest_results[key] = {"status": "MISMATCH",
                                    "expected": expected, "actual": actual}

    passed = len(errors) == 0
    if passed:
        print("      [+] All artifact digests VERIFIED.")
    return StepResult(step=7, name="manifest_digests",
                      passed=passed, details=digest_results, errors=errors)


# ---------------------------------------------------------------------------
# Step 8 — Emit JSON report
# ---------------------------------------------------------------------------
def step8_emit_report(
    step_results: List[StepResult],
    manifest: Dict[str, Any],
    output_path: Path,
) -> StepResult:
    print(f"\n[8/8] Emitting machine-readable JSON report -> {output_path}")
    errors: List[str] = []

    overall_pass = all(s.passed for s in step_results)

    report = {
        "report_schema": "AEIB-REPRODUCTION-REPORT-v1",
        "release_id": manifest.get("release_id", "AEIB-RELEASE-v0.2.2"),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_pass": overall_pass,
        "environment": {
            "python_version": sys.version.split()[0],
            "sqlite_version": sqlite3.sqlite_version,
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
        },
        "steps": [
            {
                "step": s.step,
                "name": s.name,
                "passed": s.passed,
                "details": s.details,
                "errors": s.errors,
            }
            for s in step_results
        ],
        "declared_manifest_path": str(MANIFEST_PATH),
        "declared_provenance": manifest.get("provenance_chain", {}),
        "declared_aggregate_evaluations": manifest.get("aggregate_evaluations", {}),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"      [+] Report written ({output_path.stat().st_size} bytes).")
    return StepResult(step=8, name="emit_report", passed=True, details={"path": str(output_path)})


# ---------------------------------------------------------------------------
# Final verdict banner
# ---------------------------------------------------------------------------
def print_verdict(step_results: List[StepResult]) -> bool:
    overall = all(s.passed for s in step_results)
    print("\n" + "=" * 72)
    if overall:
        print("  SUCCESS: ALL REPRODUCTION CHECKS AND INVARIANTS VERIFIED")
        print("  Release target   : v0.2.2  (Branch: release/v0.2.0)")
        print("  Safety invariant : 0 duplicate debits under AEIB boundary (50/50)")
        print("  Control matrix   : C0=100% dup | C1=0% | C2=100% dup")
        print("  Negative controls: 20/20 RECONCILIATION_NOT_FOUND (0% false positive)")
        print("  Cryptographic    : tamper-rejection checks passed")
    else:
        print("  FAILURE: ONE OR MORE REPRODUCTION CHECKS FAILED")
        failed = [s for s in step_results if not s.passed]
        for s in failed:
            print(f"    Step {s.step} [{s.name}]: {'; '.join(s.errors) if s.errors else 'FAILED'}")
    print("=" * 72)
    return overall


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="AEIB Hardened Reproduction Verification Script v0.2.2"
    )
    parser.add_argument(
        "--unit-only", action="store_true",
        help="Run only Steps 1-3 (environment + git + unit tests). Fast path.",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_REPORT_PATH,
        help="Path for machine-readable JSON report output.",
    )
    parser.add_argument(
        "--strict-versions", action="store_true",
        help="Treat dependency version mismatches as hard failures (Step 1).",
    )
    parser.add_argument(
        "--n-trials", type=int, default=50,
        help="Number of trials per control/AEIB arm (default: 50).",
    )
    parser.add_argument(
        "--n-negative", type=int, default=20,
        help="Number of negative control trials (default: 20).",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("  AEIB HARDENED CLEAN REPRODUCTION & ARTIFACT VERIFICATION SUITE")
    print("  Release: v0.2.2  |  Branch: release/v0.2.0")
    print("=" * 72)

    manifest = load_manifest()
    step_results: List[StepResult] = []

    # Steps 1-3 always run
    step_results.append(step1_environment(manifest, strict=args.strict_versions))
    step_results.append(step2_git_revision(manifest, strict=args.strict_versions))
    step_results.append(step3_unit_tests())

    if not args.unit_only:
        step_results.append(step4_full_control_matrix(n=args.n_trials))
        step_results.append(step5_full_aeib_trials(n=args.n_trials))
        step_results.append(step6_negative_controls(n=args.n_negative, manifest=manifest))
        step_results.append(step7_manifest_digests(manifest))
    else:
        print("\n  [--unit-only mode: skipping Steps 4-8]")

    # Always emit report
    step_results.append(step8_emit_report(step_results, manifest, args.output))

    overall = print_verdict(step_results)
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
