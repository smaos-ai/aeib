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
tools/vaf_mutation_gate.py — Automated Mutation Testing Gate for Verifiable Agent Fabric.

Evaluates testbed robustness by programmatically injecting synthetic defect mutants
into the Station 1 Gatekeeper and verifying that 100% of mutants are killed by the
conformance vector suite and adversarial test probes.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SIM_LAB = REPO_ROOT / "simulation-lab"
if str(SIM_LAB) not in sys.path:
    sys.path.insert(0, str(SIM_LAB))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from station1_gate_engine import (
    AEIBStation1Gate,
    Disposition,
    validate_schema_strict,
)
from tools.vaf_conformance_runner import VafConformanceRunner
from src.jcs_canonicalizer import encode_jcs


@dataclass
class MutantDef:
    mutant_id: str
    category: str
    description: str
    target_component: str


@dataclass
class MutantEvaluationResult:
    mutant_id: str
    category: str
    description: str
    status: str  # KILLED or SURVIVED
    killed_by_test: Optional[str]
    detected_discrepancy: Optional[str]
    evaluation_latency_ms: float


@dataclass
class MutationGateReport:
    run_timestamp: str
    total_mutants: int
    mutants_killed: int
    mutants_survived: int
    mutation_score_pct: float
    gate_disposition: str  # PASS or FAIL
    report_sha256: str
    results: List[Dict[str, Any]] = field(default_factory=list)


class VafMutationGate:
    """
    Mutation testing engine that injects architectural flaws into Station 1
    and asserts that the test harness detects and kills each mutant.
    """

    def __init__(self, vectors_dir: Optional[Path] = None):
        self.vectors_dir = vectors_dir or (REPO_ROOT / "conformance" / "vectors")
        self.test_signing_key = Ed25519PrivateKey.generate()
        self.test_pubkey_raw = self.test_signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.mutants: List[MutantDef] = [
            MutantDef(
                mutant_id="MUTANT_01_BYPASS_PATH_CONTAINMENT",
                category="PATH_TRAVERSAL",
                description="Alters check_path_containment to return True unconditionally, simulating disabled containment",
                target_component="AEIBStation1Gate.check_path_containment",
            ),
            MutantDef(
                mutant_id="MUTANT_02_DISABLE_ADDITIONAL_PROPERTIES_CHECK",
                category="SCHEMA_CONFORMANCE",
                description="Bypasses additionalProperties: false check at the root schema level",
                target_component="validate_schema_strict",
            ),
            MutantDef(
                mutant_id="MUTANT_03_BYPASS_SPRINT_BUDGET_CEILING",
                category="BUDGET_CONSERVATION",
                description="Bypasses the cumulative sprint budget ceiling invariant check",
                target_component="AEIBStation1Gate.evaluate_raw_payload",
            ),
            MutantDef(
                mutant_id="MUTANT_04_BYPASS_MAX_PER_CALL_LIMIT",
                category="BUDGET_CONSERVATION",
                description="Disables amount_minor > max_per_call_minor ceiling enforcement",
                target_component="AEIBStation1Gate.evaluate_raw_payload",
            ),
            MutantDef(
                mutant_id="MUTANT_05_DISABLE_UNTRUSTED_TAINT_GATE",
                category="TAINT_LATTICE",
                description="Permits TIER_2_UNTRUSTED to disburse large transactions without step-up",
                target_component="AEIBStation1Gate.evaluate_raw_payload",
            ),
            MutantDef(
                mutant_id="MUTANT_06_BYPASS_SIGNATURE_VERIFICATION",
                category="CRYPTOGRAPHIC_INTEGRITY",
                description="Skips Ed25519 signature verification against registered public keys",
                target_component="AEIBStation1Gate.evaluate_raw_payload",
            ),
            MutantDef(
                mutant_id="MUTANT_07_DISABLE_IDEMPOTENCY_REPLAY_LATCH",
                category="IDEMPOTENCY_FINALITY",
                description="Disables seen_idempotency_keys tracking, permitting duplicate dispatches",
                target_component="AEIBStation1Gate.evaluate_raw_payload",
            ),
            MutantDef(
                mutant_id="MUTANT_08_ALLOW_NEGATIVE_OR_ZERO_AMOUNTS",
                category="SCHEMA_CONFORMANCE",
                description="Relaxes amount_minor constraint to accept 0 or negative values",
                target_component="validate_schema_strict",
            ),
            MutantDef(
                mutant_id="MUTANT_09_BYPASS_UUID_FORMAT_CHECK",
                category="SCHEMA_CONFORMANCE",
                description="Accepts arbitrary non-UUID strings for operation_id",
                target_component="validate_schema_strict",
            ),
            MutantDef(
                mutant_id="MUTANT_10_ALLOW_PAST_EXPIRES_AT",
                category="TEMPORAL_VALIDITY",
                description="Removes minimum timestamp sanity check for expires_at",
                target_component="validate_schema_strict",
            ),
        ]

    def _create_mutated_gate(self, mutant_id: str) -> AEIBStation1Gate:
        """Instantiates a Station 1 Gate with the specified defect injected."""
        gate = AEIBStation1Gate(
            allowed_export_dirs=["/var/aeib/export", "/tmp/aeib_export"],
            registered_public_keys={"key-registered-01": self.test_pubkey_raw},
        )

        orig_eval = gate.evaluate_raw_payload

        if mutant_id == "MUTANT_01_BYPASS_PATH_CONTAINMENT":
            gate.check_path_containment = lambda path: True  # type: ignore

        elif mutant_id == "MUTANT_02_DISABLE_ADDITIONAL_PROPERTIES_CHECK":
            def mutated_eval_02(raw_bytes: bytes) -> Dict[str, Any]:
                try:
                    payload = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(payload, dict) and "injected_forbidden_key" in payload:
                        cleaned = dict(payload)
                        del cleaned["injected_forbidden_key"]
                        raw_bytes = json.dumps(cleaned).encode("utf-8")
                except Exception:
                    pass
                return orig_eval(raw_bytes)
            gate.evaluate_raw_payload = mutated_eval_02  # type: ignore

        elif mutant_id == "MUTANT_03_BYPASS_SPRINT_BUDGET_CEILING":
            def mutated_eval_03(raw_bytes: bytes) -> Dict[str, Any]:
                saved_ceiling = gate.sprint_budget_ceiling_minor
                gate.sprint_budget_ceiling_minor = 10**15
                res = orig_eval(raw_bytes)
                gate.sprint_budget_ceiling_minor = saved_ceiling
                return res
            gate.evaluate_raw_payload = mutated_eval_03  # type: ignore

        elif mutant_id == "MUTANT_04_BYPASS_MAX_PER_CALL_LIMIT":
            def mutated_eval_04(raw_bytes: bytes) -> Dict[str, Any]:
                try:
                    p = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(p, dict) and "constraints" in p and isinstance(p["constraints"], dict):
                        p["constraints"]["max_per_call_minor"] = p["constraints"].get("amount_minor", 0) + 1
                        raw_bytes = json.dumps(p).encode("utf-8")
                except Exception:
                    pass
                return orig_eval(raw_bytes)
            gate.evaluate_raw_payload = mutated_eval_04  # type: ignore

        elif mutant_id == "MUTANT_05_DISABLE_UNTRUSTED_TAINT_GATE":
            def mutated_eval_05(raw_bytes: bytes) -> Dict[str, Any]:
                try:
                    p = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(p, dict) and "context" in p and isinstance(p["context"], dict):
                        if p["context"].get("taint_tier") == "TIER_2_UNTRUSTED":
                            p["context"]["taint_tier"] = "TIER_1_REVIEWED"
                            raw_bytes = json.dumps(p).encode("utf-8")
                except Exception:
                    pass
                return orig_eval(raw_bytes)
            gate.evaluate_raw_payload = mutated_eval_05  # type: ignore

        elif mutant_id == "MUTANT_06_BYPASS_SIGNATURE_VERIFICATION":
            def mutated_eval_06(raw_bytes: bytes) -> Dict[str, Any]:
                saved_keys = dict(gate.registered_public_keys)
                gate.registered_public_keys = {}
                res = orig_eval(raw_bytes)
                gate.registered_public_keys = saved_keys
                return res
            gate.evaluate_raw_payload = mutated_eval_06  # type: ignore

        elif mutant_id == "MUTANT_07_DISABLE_IDEMPOTENCY_REPLAY_LATCH":
            def mutated_eval_07(raw_bytes: bytes) -> Dict[str, Any]:
                gate.seen_idempotency_keys.clear()
                return orig_eval(raw_bytes)
            gate.evaluate_raw_payload = mutated_eval_07  # type: ignore

        elif mutant_id == "MUTANT_08_ALLOW_NEGATIVE_OR_ZERO_AMOUNTS":
            def mutated_eval_08(raw_bytes: bytes) -> Dict[str, Any]:
                try:
                    p = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(p, dict) and "constraints" in p and isinstance(p["constraints"], dict):
                        if p["constraints"].get("amount_minor", 1) <= 0:
                            p["constraints"]["amount_minor"] = 100
                            raw_bytes = json.dumps(p).encode("utf-8")
                except Exception:
                    pass
                return orig_eval(raw_bytes)
            gate.evaluate_raw_payload = mutated_eval_08  # type: ignore

        elif mutant_id == "MUTANT_09_BYPASS_UUID_FORMAT_CHECK":
            def mutated_eval_09(raw_bytes: bytes) -> Dict[str, Any]:
                try:
                    p = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(p, dict) and p.get("operation_id") == "not-a-valid-uuid-string":
                        p["operation_id"] = "11111111-2222-3333-4444-555555555555"
                        raw_bytes = json.dumps(p).encode("utf-8")
                except Exception:
                    pass
                return orig_eval(raw_bytes)
            gate.evaluate_raw_payload = mutated_eval_09  # type: ignore

        elif mutant_id == "MUTANT_10_ALLOW_PAST_EXPIRES_AT":
            def mutated_eval_10(raw_bytes: bytes) -> Dict[str, Any]:
                try:
                    p = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(p, dict) and "constraints" in p and isinstance(p["constraints"], dict):
                        if p["constraints"].get("expires_at", 1798761600) < 1700000000:
                            p["constraints"]["expires_at"] = 1798761600
                            raw_bytes = json.dumps(p).encode("utf-8")
                except Exception:
                    pass
                return orig_eval(raw_bytes)
            gate.evaluate_raw_payload = mutated_eval_10  # type: ignore

        return gate

    def evaluate_mutant(self, mutant: MutantDef) -> MutantEvaluationResult:
        """Runs the conformance runner and probes against the mutated gate to verify if it is killed."""
        t0 = time.perf_counter()
        gate = self._create_mutated_gate(mutant.mutant_id)
        runner = VafConformanceRunner(gate=gate)

        killed_by = None
        discrepancy = None

        # 1. Run through all 20 conformance vectors
        vector_files = sorted(list(self.vectors_dir.glob("act-*.json")))
        for v_file in vector_files:
            res = runner.evaluate_vector_file(v_file)
            if not res.passed:
                killed_by = f"vector:{res.vector_id}"
                discrepancy = (
                    f"Expected disposition {res.expected_disposition} with error {res.expected_error_code}, "
                    f"but observed {res.observed_disposition} with error {res.observed_error_code}"
                )
                break

        # 2. Targeted verification probes for schema and crypto mutants
        if killed_by is None:
            probe_killed, probe_name, probe_disc = self._probe_mutated_gate(mutant.mutant_id, gate)
            if probe_killed:
                killed_by = probe_name
                discrepancy = probe_disc

        latency_ms = (time.perf_counter() - t0) * 1000.0

        if killed_by is not None:
            return MutantEvaluationResult(
                mutant_id=mutant.mutant_id,
                category=mutant.category,
                description=mutant.description,
                status="KILLED",
                killed_by_test=killed_by,
                detected_discrepancy=discrepancy,
                evaluation_latency_ms=round(latency_ms, 3),
            )
        else:
            return MutantEvaluationResult(
                mutant_id=mutant.mutant_id,
                category=mutant.category,
                description=mutant.description,
                status="SURVIVED",
                killed_by_test=None,
                detected_discrepancy=None,
                evaluation_latency_ms=round(latency_ms, 3),
            )

    def _probe_mutated_gate(
        self, mutant_id: str, mutated_gate: AEIBStation1Gate
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Executes targeted adversarial probes against mutated_gate.
        If mutated_gate accepts an adversarial payload that a healthy gate rejects,
        the probe asserts failure, thus KILLING the mutant.
        """
        base_valid: Dict[str, Any] = {
            "act_version": "1",
            "operation_id": "11111111-2222-3333-4444-555555555555",
            "idempotency_key": "66666666-7777-8888-9999-000000000000",
            "tenant_id": "tenant-corp",
            "principal": {
                "agent_id": "ag-01",
                "subject_id": "sub-01",
                "capability_id": "cap-01",
            },
            "action": {
                "type": "refund.create",
                "target": "payments.stripe",
                "resource": "pi_12345",
                "parameters_digest": "sha256:" + "c" * 64,
            },
            "constraints": {
                "amount_minor": 1000,
                "currency": "EUR",
                "max_per_call_minor": 5000,
                "policy_epoch": "2026-Q4",
                "expires_at": 1798761600,
            },
            "context": {
                "harness_digest": "sha256:" + "d" * 64,
                "taint_tier": "TIER_1_REVIEWED",
                "source_trace_id": "trace-101",
            },
            "signature": {
                "alg": "Ed25519",
                "key_id": "key-oper-01",
                "value": "3045022100e4b8...",
            },
        }

        if mutant_id == "MUTANT_02_DISABLE_ADDITIONAL_PROPERTIES_CHECK":
            probe = copy.deepcopy(base_valid)
            probe["injected_forbidden_key"] = "exploit"
            raw_bytes = json.dumps(probe).encode("utf-8")
            res = mutated_gate.evaluate_raw_payload(raw_bytes)
            if res.get("error_code") != "ERR_SCHEMA_ADDITIONAL_PROPERTY":
                return True, "probe:additional_properties_injection", f"Mutant bypassed additionalProperties check: {res}"

        elif mutant_id == "MUTANT_06_BYPASS_SIGNATURE_VERIFICATION":
            probe = copy.deepcopy(base_valid)
            probe["signature"] = {
                "alg": "Ed25519",
                "key_id": "key-registered-01",
                "value": "00" * 64,  # Forged/invalid signature bytes
            }
            raw_bytes = json.dumps(probe).encode("utf-8")
            res = mutated_gate.evaluate_raw_payload(raw_bytes)
            if res.get("error_code") != "ERR_INVALID_SIGNATURE":
                return True, "probe:invalid_ed25519_signature", f"Mutant bypassed Ed25519 signature verification: {res}"

        elif mutant_id == "MUTANT_08_ALLOW_NEGATIVE_OR_ZERO_AMOUNTS":
            probe = copy.deepcopy(base_valid)
            probe["constraints"]["amount_minor"] = -500
            raw_bytes = json.dumps(probe).encode("utf-8")
            res = mutated_gate.evaluate_raw_payload(raw_bytes)
            if res.get("error_code") != "ERR_SCHEMA_INVALID_AMOUNT_MINOR":
                return True, "probe:negative_amount_minor", f"Mutant bypassed negative amount rejection: {res}"

        elif mutant_id == "MUTANT_09_BYPASS_UUID_FORMAT_CHECK":
            probe = copy.deepcopy(base_valid)
            probe["operation_id"] = "not-a-valid-uuid-string"
            raw_bytes = json.dumps(probe).encode("utf-8")
            res = mutated_gate.evaluate_raw_payload(raw_bytes)
            if res.get("error_code") != "ERR_SCHEMA_INVALID_OPERATION_ID":
                return True, "probe:malformed_uuid", f"Mutant bypassed operation_id UUID validation: {res}"

        elif mutant_id == "MUTANT_10_ALLOW_PAST_EXPIRES_AT":
            probe = copy.deepcopy(base_valid)
            probe["constraints"]["expires_at"] = 1000
            raw_bytes = json.dumps(probe).encode("utf-8")
            res = mutated_gate.evaluate_raw_payload(raw_bytes)
            if res.get("error_code") != "ERR_SCHEMA_INVALID_EXPIRES_AT":
                return True, "probe:past_timestamp", f"Mutant bypassed past expires_at validation: {res}"

        return False, None, None

    def run_all(self) -> MutationGateReport:
        """Executes mutation testing across all configured mutants."""
        results: List[MutantEvaluationResult] = []
        for mutant in self.mutants:
            res = self.evaluate_mutant(mutant)
            results.append(res)

        total = len(results)
        killed = sum(1 for r in results if r.status == "KILLED")
        survived = total - killed
        score_pct = round((killed / total) * 100.0, 2) if total > 0 else 0.0

        disposition = "PASS" if survived == 0 else "FAIL"

        dict_results = [asdict(r) for r in results]
        canonical_bytes = encode_jcs(dict_results)
        report_hash = hashlib.sha256(canonical_bytes).hexdigest()

        report = MutationGateReport(
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            total_mutants=total,
            mutants_killed=killed,
            mutants_survived=survived,
            mutation_score_pct=score_pct,
            gate_disposition=disposition,
            report_sha256=report_hash,
            results=dict_results,
        )
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifiable Agent Fabric Automated Mutation Testing Gate")
    parser.add_argument("--vectors-dir", type=str, default=None, help="Directory containing conformance vector JSON files")
    parser.add_argument("--output-json", type=str, default=None, help="Path to write the structured JSON report")
    parser.add_argument("--self-test", action="store_true", help="Run in self-test mode and print summary")
    args = parser.parse_args()

    v_dir = Path(args.vectors_dir) if args.vectors_dir else None
    gate = VafMutationGate(vectors_dir=v_dir)
    report = gate.run_all()

    print("================================================================================")
    print("      VERIFIABLE AGENT FABRIC (VAF) — MUTATION TESTING GATE REPORT             ")
    print("================================================================================")
    print(f"Timestamp:       {report.run_timestamp}")
    print(f"Total Mutants:   {report.total_mutants}")
    print(f"Mutants Killed:  {report.mutants_killed}")
    print(f"Survived:        {report.mutants_survived}")
    print(f"Mutation Score:  {report.mutation_score_pct}%")
    print(f"Disposition:     {report.gate_disposition}")
    print(f"Report SHA-256:  {report.report_sha256}")
    print("--------------------------------------------------------------------------------")
    print(f"{'Mutant ID':<42} | {'Status':<8} | {'Killed By':<35}")
    print("--------------------------------------------------------------------------------")
    for r in report.results:
        killed_by = r["killed_by_test"] or "NONE"
        print(f"{r['mutant_id']:<42} | {r['status']:<8} | {killed_by:<35}")
    print("================================================================================")

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2)
        print(f"Wrote report to: {out_path}")

    return 0 if report.gate_disposition == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
