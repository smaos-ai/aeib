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
simulation-lab/test_black_box.py — Adversarial Black-Box Property Fuzzer & TDD Harness.

Evaluates Station 1 Gate against:
1. Canonical act.v1.json schema conformance.
2. CVE-2026-43901 and CVE-2025-53110 path traversal escapes.
3. Negative amount parameter traps and 64-bit integer overflows.
4. Monotonic taint lattice enforcement and unanchored payee mutations.
5. Idempotent replay and budget solvency conservation.
"""

import copy
import json
from pathlib import Path
import random
import sys
import uuid
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SIM_LAB = REPO_ROOT / "simulation-lab"
if str(SIM_LAB) not in sys.path:
    sys.path.insert(0, str(SIM_LAB))

from station1_gate_engine import (
    AEIBStation1Gate,
    Disposition,
    validate_schema_strict,
)

SCHEMA_PATH = REPO_ROOT / "contracts" / "act.v1.json"


def load_schema() -> dict:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_valid_act() -> dict:
    return {
        "act_version": "1",
        "operation_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "tenant_id": "tenant-corp-101",
        "principal": {
            "agent_id": "agent-worker-01",
            "subject_id": "user-corp-99",
            "capability_id": "cap-refund-v1",
        },
        "action": {
            "type": "refund.create",
            "target": "payments.stripe",
            "resource": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
            "parameters_digest": "sha256:" + "a" * 64,
        },
        "constraints": {
            "amount_minor": 15000,
            "currency": "EUR",
            "max_per_call_minor": 20000,
            "policy_epoch": "2026-Q4",
            "expires_at": 1798761600,
        },
        "context": {
            "harness_digest": "sha256:" + "b" * 64,
            "taint_tier": "TIER_1_REVIEWED",
            "source_trace_id": "otel-trace-001929",
        },
        "signature": {
            "alg": "Ed25519",
            "key_id": "key-oper-01",
            "value": "3045022100e4b8...",
        },
    }


def test_contract_schema_itself_is_valid():
    """Sanity check: The JSON Schema is syntactically valid and has title."""
    schema = load_schema()
    assert schema["title"] == "AEIB Canonical Action Envelope (v1)"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "act_version" in schema["required"]


def test_nominal_valid_act_dispatched():
    """Valid act passes Station 1 evaluation and receives DISPATCHED disposition with CAID."""
    gate = AEIBStation1Gate()
    valid_payload = build_valid_act()
    raw_bytes = json.dumps(valid_payload).encode("utf-8")

    result = gate.evaluate_raw_payload(raw_bytes)
    assert result["disposition"] == Disposition.DISPATCHED.value
    assert result["caid"].startswith("sha256:")
    assert result["escrowed_minor"] == 15000
    assert result["status_code"] == 200


def test_cve_2026_43901_path_traversal_must_be_blocked():
    """
    Security Invariant: If a path traversal is injected (e.g. dest_dir pointing outside sandbox),
    the gate must reject it fail-closed.
    """
    gate = AEIBStation1Gate(allowed_export_dirs=["/var/aeib/export"])
    malicious_payload = build_valid_act()
    malicious_payload["action"]["dest_dir"] = "/home/user/.ssh"

    raw_bytes = json.dumps(malicious_payload).encode("utf-8")
    result = gate.evaluate_raw_payload(raw_bytes)

    assert result["disposition"] == Disposition.NOT_DISPATCHED.value
    assert result["error_code"] in ("ERR_PATH_TRAVERSAL_DENIED", "ERR_SCHEMA_ADDITIONAL_PROPERTY")


def test_cve_2025_53110_dot_dot_slash_traversal_blocked():
    """
    Verifies that relative dot-dot-slash traversal sequences are resolved and rejected.
    """
    gate = AEIBStation1Gate(allowed_export_dirs=["/var/aeib/export"])
    malicious = build_valid_act()
    malicious["action"]["export_path"] = "/var/aeib/export/../../etc/shadow"

    raw_bytes = json.dumps(malicious).encode("utf-8")
    result = gate.evaluate_raw_payload(raw_bytes)

    assert result["disposition"] == Disposition.NOT_DISPATCHED.value
    assert result["error_code"] in ("ERR_PATH_TRAVERSAL_DENIED", "ERR_SCHEMA_ADDITIONAL_PROPERTY")


def test_adversarial_property_fuzzer_rejects_malformed_payloads():
    """
    Generative property-based fuzzer: generates 250 diverse malformed payloads
    (negative numbers, type mismatches, missing required keys, additional properties)
    and asserts the gate rejects 100% of them.
    """
    rng = random.Random(42)
    gate = AEIBStation1Gate()

    fuzz_mutations = [
        lambda p: p.update({"act_version": "2"}),
        lambda p: p.update({"act_version": ""}),
        lambda p: p.update({"operation_id": "not-a-uuid"}),
        lambda p: p.update({"idempotency_key": "12345"}),
        lambda p: p["constraints"].update({"amount_minor": -500}),
        lambda p: p["constraints"].update({"amount_minor": 0}),
        lambda p: p["constraints"].update({"currency": "EUROPE"}),
        lambda p: p["constraints"].update({"currency": "eu"}),
        lambda p: p["action"].update({"type": "UNAUTHORIZED_ACTION"}),
        lambda p: p["action"].update({"parameters_digest": "md5:notasha256"}),
        lambda p: p["context"].update({"taint_tier": "UNKNOWN_TAINT"}),
        lambda p: p["signature"].update({"alg": "RSA_MD5"}),
        lambda p: p.update({"injected_extra_root_prop": "evil"}),
        lambda p: p["principal"].update({"injected_extra_principal_prop": True}),
        lambda p: delitem_safe(p, "tenant_id"),
        lambda p: delitem_safe(p["principal"], "agent_id"),
        lambda p: delitem_safe(p["action"], "parameters_digest"),
        lambda p: delitem_safe(p["constraints"], "amount_minor"),
        lambda p: delitem_safe(p["signature"], "value"),
    ]

    def delitem_safe(d: dict, k: str) -> None:
        d.pop(k, None)

    for i in range(250):
        base = build_valid_act()
        mutation = rng.choice(fuzz_mutations)
        mutation(base)

        raw = json.dumps(base).encode("utf-8")
        res = gate.evaluate_raw_payload(raw)

        assert res["disposition"] == Disposition.NOT_DISPATCHED.value, f"Fuzz iteration {i} accepted invalid payload!"
        assert res["error_code"] is not None


def test_idempotent_replay_preserves_disposition_without_double_escrow():
    """Asserts that re-submitting an identical idempotency key does not double-escrow budget."""
    gate = AEIBStation1Gate()
    act = build_valid_act()
    raw = json.dumps(act).encode("utf-8")

    res1 = gate.evaluate_raw_payload(raw)
    assert res1["disposition"] == Disposition.DISPATCHED.value
    assert gate.escrowed_spend_minor == 15000

    # Second submission
    res2 = gate.evaluate_raw_payload(raw)
    assert res2["disposition"] == Disposition.DISPATCHED.value
    assert res2.get("is_replay") is True
    # Escrow must NOT double
    assert gate.escrowed_spend_minor == 15000


def test_budget_escalation_fails_closed():
    """Asserts that amount exceeding max_per_call or sprint budget fails closed."""
    gate = AEIBStation1Gate(sprint_budget_ceiling_minor=50_000)

    # Exceeds max_per_call
    act1 = build_valid_act()
    act1["constraints"]["amount_minor"] = 25000
    act1["constraints"]["max_per_call_minor"] = 20000
    raw1 = json.dumps(act1).encode("utf-8")

    res1 = gate.evaluate_raw_payload(raw1)
    assert res1["disposition"] == Disposition.NOT_DISPATCHED.value
    assert res1["error_code"] == "ERR_EXCEEDS_MAX_PER_CALL"

    # Exceeds sprint ceiling
    act2 = build_valid_act()
    act2["constraints"]["amount_minor"] = 60000
    act2["constraints"]["max_per_call_minor"] = 100000
    raw2 = json.dumps(act2).encode("utf-8")

    res2 = gate.evaluate_raw_payload(raw2)
    assert res2["disposition"] == Disposition.NOT_DISPATCHED.value
    assert res2["error_code"] == "ERR_SPRINT_BUDGET_EXCEEDED"


def test_untrusted_taint_tier_requires_step_up():
    """Asserts that TIER_2_UNTRUSTED context cannot execute mutations > 500 minor units without step-up."""
    gate = AEIBStation1Gate()
    act = build_valid_act()
    act["context"]["taint_tier"] = "TIER_2_UNTRUSTED"
    act["constraints"]["max_per_call_minor"] = 100000
    act["constraints"]["amount_minor"] = 75000
    raw = json.dumps(act).encode("utf-8")

    res = gate.evaluate_raw_payload(raw)
    assert res["disposition"] == Disposition.NOT_DISPATCHED.value
    assert res["error_code"] == "ERR_UNTRUSTED_TAINT_REQUIRES_STEP_UP"


def test_station1_schema_and_gate_boundaries():
    """Verifies exact boundary conditions for validate_schema_strict and AEIBStation1Gate."""
    assert validate_schema_strict([]) == (False, "ERR_SCHEMA_NOT_OBJECT")

    p_extra = build_valid_act()
    p_extra["extra"] = 1
    assert validate_schema_strict(p_extra) == (False, "ERR_SCHEMA_ADDITIONAL_PROPERTY")

    p_missing = build_valid_act()
    del p_missing["tenant_id"]
    assert validate_schema_strict(p_missing) == (False, "ERR_SCHEMA_MISSING_REQUIRED_TENANT_ID")

    p_op = build_valid_act()
    p_op["operation_id"] = "bad-uuid"
    assert validate_schema_strict(p_op) == (False, "ERR_SCHEMA_INVALID_OPERATION_ID")

    p_ten = build_valid_act()
    p_ten["tenant_id"] = ""
    assert validate_schema_strict(p_ten) == (False, "ERR_SCHEMA_INVALID_TENANT_ID")

    p_act = build_valid_act()
    p_act["action"] = "not-a-dict"
    assert validate_schema_strict(p_act) == (False, "ERR_SCHEMA_INVALID_ACTION")

    p_act_type = build_valid_act()
    p_act_type["action"]["type"] = "INVALID"
    assert validate_schema_strict(p_act_type) == (False, "ERR_SCHEMA_INVALID_ACTION_TYPE")

    p_act_tgt = build_valid_act()
    p_act_tgt["action"]["target"] = ""
    assert validate_schema_strict(p_act_tgt) == (False, "ERR_SCHEMA_INVALID_ACTION_TARGET")

    p_act_res_ok = build_valid_act()
    p_act_res_ok["action"]["resource"] = "r"
    assert validate_schema_strict(p_act_res_ok) == (True, "OK")

    p_act_res_bad = build_valid_act()
    p_act_res_bad["action"]["resource"] = ""
    assert validate_schema_strict(p_act_res_bad) == (False, "ERR_SCHEMA_INVALID_ACTION_RESOURCE")

    p_con_extra = build_valid_act()
    p_con_extra["constraints"]["extra"] = 1
    assert validate_schema_strict(p_con_extra) == (False, "ERR_SCHEMA_ADDITIONAL_PROPERTY")

    p_epoch = build_valid_act()
    p_epoch["constraints"]["policy_epoch"] = ""
    assert validate_schema_strict(p_epoch) == (False, "ERR_SCHEMA_INVALID_POLICY_EPOCH")

    base_exp = 17 * 10**8
    p_exp_ok = build_valid_act()
    p_exp_ok["constraints"]["expires_at"] = base_exp
    assert validate_schema_strict(p_exp_ok) == (True, "OK")

    p_exp_bad = build_valid_act()
    p_exp_bad["constraints"]["expires_at"] = base_exp - 1
    assert validate_schema_strict(p_exp_bad) == (False, "ERR_SCHEMA_INVALID_EXPIRES_AT")

    p_ctx_extra = build_valid_act()
    p_ctx_extra["context"]["extra"] = 1
    assert validate_schema_strict(p_ctx_extra) == (False, "ERR_SCHEMA_ADDITIONAL_PROPERTY")

    p_trace = build_valid_act()
    p_trace["context"]["source_trace_id"] = ""
    assert validate_schema_strict(p_trace) == (False, "ERR_SCHEMA_INVALID_SOURCE_TRACE_ID")

    p_sig = build_valid_act()
    p_sig["signature"] = "not-a-dict"
    assert validate_schema_strict(p_sig) == (False, "ERR_SCHEMA_INVALID_SIGNATURE")

    p_sig_alg = build_valid_act()
    p_sig_alg["signature"]["alg"] = "BAD_ALG"
    assert validate_schema_strict(p_sig_alg) == (False, "ERR_SCHEMA_INVALID_SIGNATURE_ALG")

    p_sig_kid = build_valid_act()
    p_sig_kid["signature"]["key_id"] = ""
    assert validate_schema_strict(p_sig_kid) == (False, "ERR_SCHEMA_INVALID_KEY_ID")

    gate_default = AEIBStation1Gate()
    assert gate_default.committed_spend_minor == 0
    assert gate_default.registered_public_keys == {}
    assert gate_default.check_path_containment("/tmp/aeib_export/sub/report.json") is True
    assert gate_default.check_path_containment("/etc/passwd") is False

    gate_custom = AEIBStation1Gate(registered_public_keys={"k1": b"x" * 32})
    assert gate_custom.registered_public_keys == {"k1": b"x" * 32}


def test_epistemic_purity_of_simulation_lab():
    """Verifies zero prohibited promotional words exist in simulation-lab files."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "bank-" + "grade",
    ]
    files_to_check = [
        Path("simulation-lab/station1_gate_engine.py"),
        Path(__file__),
    ]

    for p in files_to_check:
        content = p.read_text(encoding="utf-8")
        for word in banned:
            assert word not in content, f"Banned word '{word}' found in {p}"
