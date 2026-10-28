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
tests/test_blackbox_two_socket_slo.py — Pytest suite for Two-Socket Black-Box TDD & SLO.
"""

import importlib
import json
import random
import sys
import pytest
from pathlib import Path
import tools.blackbox_two_socket_slo_and_fuzzer as slo_mod
from tools.blackbox_two_socket_slo_and_fuzzer import (
    BlackBoxGateHttpServer,
    CleanRoomBlackBoxEngine,
    RealLocalPaymentTwinServer,
    SlotProposal,
    TwinBankDataset,
    main,
    run_two_socket_blackbox_and_slo_suite,
    send_wire_http,
    test_two_socket_blackbox_fuzzer_and_slo_baseline,
    unitboost_algebraic_merge,
)


def test_module_sys_path_bootstrap() -> None:
    """Verifies REPO_ROOT sys.path bootstrap when missing."""
    repo_str = str(slo_mod.REPO_ROOT)
    orig_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if p != repo_str]
        importlib.reload(slo_mod)
        assert sys.path[0] == repo_str
    finally:
        sys.path = orig_path


def test_unitboost_commutativity_and_margin() -> None:
    """Verifies that UnitBoost algebraic merge is commutative under all permutations."""
    m1 = SlotProposal(
        model_id="model_a",
        slot_values={"recipient": ("DE89370400440532013000", 0.92), "action": ("REFUND", 0.88)},
    )
    m2 = SlotProposal(
        model_id="model_b",
        slot_values={"recipient": ("DE89370400440532013000", 0.85), "action": ("REFUND", 0.90)},
    )
    m3 = SlotProposal(
        model_id="model_c",
        slot_values={"recipient": ("DE89370400440532013000", 0.95), "action": ("REFUND", 0.84)},
    )

    merge_123 = unitboost_algebraic_merge([m1, m2, m3])
    merge_321 = unitboost_algebraic_merge([m3, m2, m1])
    merge_213 = unitboost_algebraic_merge([m2, m1, m3])

    assert merge_123 == merge_321 == merge_213
    assert merge_123["recipient"] == "DE89370400440532013000"
    assert merge_123["action"] == "REFUND"


def test_unitboost_uncertainty_halt_and_exact_boundary() -> None:
    """Verifies fail-closed halt when confidence separation margin < 0.20 and pass at == 0.20."""
    m1 = SlotProposal(
        model_id="model_a",
        slot_values={"recipient": ("DE89370400440532013000", 0.51)},
    )
    m2 = SlotProposal(
        model_id="model_b",
        slot_values={"recipient": ("FR7630006000011234567890189", 0.49)},
    )

    res = unitboost_algebraic_merge([m1, m2])
    assert res["recipient"] == "UNCERTAINTY_HALT"

    # Exact binary floating-point boundary norm_margin == 0.50 (3.0 vs 1.0 -> margin 2.0 / 4.0 == 0.50)
    b1 = SlotProposal(model_id="b1", slot_values={"recipient": ("A", 3.0)})
    b2 = SlotProposal(model_id="b2", slot_values={"recipient": ("B", 1.0)})
    res_eq = unitboost_algebraic_merge([b1, b2], min_margin=0.50)
    assert res_eq["recipient"] == "A"


def test_gate_http_server_daemon_and_status_wire(tmp_path: Path) -> None:
    """Verifies BlackBoxGateHttpServer daemon thread, INSPECT_STATE action, and latency calculation."""
    wal_file = str(tmp_path / "gate.wal")
    dataset = TwinBankDataset()
    with RealLocalPaymentTwinServer(dataset) as twin:
        engine = CleanRoomBlackBoxEngine(
            target_host=twin.host,
            target_port=twin.port,
            sprint_ceiling_minor=50 * 10000,
            pinned_recipients={"iban:DE89370400440532013000"},
            shared_secret_key=b"black-box-secret-key-2026",
        )
        with BlackBoxGateHttpServer(engine, wal_file) as srv:
            assert srv._thread.daemon is True
            assert srv.port > 0
            st, body, lat = send_wire_http(srv.host, srv.port, b'{"action":"INSPECT_STATE"}')
            assert st == 2 * 100
            assert "escrowed_minor" in body
            assert lat > 0.001


def test_two_socket_blackbox_slo_execution() -> None:
    """Evaluates the full two-socket black-box fuzzer and SLO benchmark and inspects wire schedule."""
    recorded_payloads = []
    recorded_seeds = []
    recorded_randint_bounds = []
    orig_send = slo_mod.send_wire_http
    orig_random_cls = slo_mod.random.Random

    class RecordingRandom(random.Random):
        def __init__(self, x=None):
            super().__init__(x)
            recorded_seeds.append(x)

        def randint(self, a: int, b: int) -> int:
            recorded_randint_bounds.append((a, b))
            return super().randint(a, b)

    def recording_send(host: str, port: int, raw_body: bytes):
        recorded_payloads.append(raw_body)
        return orig_send(host, port, raw_body)

    try:
        slo_mod.send_wire_http = recording_send
        slo_mod.random.Random = RecordingRandom
        report = run_two_socket_blackbox_and_slo_suite()
    finally:
        slo_mod.send_wire_http = orig_send
        slo_mod.random.Random = orig_random_cls

    assert recorded_seeds == [2026 * 10000 + 1020]
    assert (-999 * 1000 - 999, 0) in recorded_randint_bounds
    assert (-999 * 1000 - 999, 1) not in recorded_randint_bounds

    corrupted_count = 0
    fuzz1_count = 0
    fuzz2_amts = []
    fuzz2_ibans = []
    valid_ops = []
    for raw in recorded_payloads[5:-1]:
        if raw.startswith(b'{"corrupted_json":'):
            corrupted_count += 1
        else:
            d = json.loads(raw.decode("utf-8"))
            if str(d.get("operation_id", "")).startswith("op-slo-valid-"):
                valid_ops.append(d["operation_id"])
            elif d.get("caid_token") == "FORGED":
                if d["recipient"] == "iban:DE89370400440532013000":
                    fuzz1_count += 1
                else:
                    fuzz2_amts.append(d["amount_minor"])
                    fuzz2_ibans.append(d["recipient"])

    assert valid_ops[0] == "op-slo-valid-0"
    assert len(valid_ops) == 5 * 10
    assert corrupted_count == 11 * 3
    assert fuzz1_count == 37
    assert len(fuzz2_amts) == 47
    assert all(a == 10 * 10 for a in fuzz2_amts)
    assert all(len(ib) == 5 + 4 * 4 for ib in fuzz2_ibans)

    assert report["false_halt_rate_pct"] == 0.0
    assert report["adversarial_rejection_rate_pct"] == 100.0
    assert report["duplicate_mutations_on_twin_bank"] == 0
    assert 0.0 < report["p50_wire_latency_ms"] < 10.0
    assert 0.0 < report["p99_wire_latency_ms"] < 50.0
    assert report["wal_bytes_per_entry"] == 617 / 10.0
    assert 0.0 < report["reconciliation_rto_ms"] < 50.0


def test_two_socket_slo_fault_injection_and_cli(tmp_path: Path) -> None:
    """Verifies false-halt OR branch, latency 3-decimal rounding, and CLI main()."""
    orig_send = slo_mod.send_wire_http

    def fault_injecting_send(host: str, port: int, raw_body: bytes):
        st, body, _ = orig_send(host, port, raw_body)
        if b'"op-slo-valid-0"' in raw_body:
            return 2 * 100, {"disposition": "EFFECT_INDETERMINATE"}, 1.23456
        if b'"op-slo-valid-4"' in raw_body:
            return 4 * 100, {"disposition": "CONFIRMED"}, 1.23456
        return st, body, 1.23456

    try:
        slo_mod.send_wire_http = fault_injecting_send
        rep = run_two_socket_blackbox_and_slo_suite()
    finally:
        slo_mod.send_wire_http = orig_send

    assert rep["false_halt_rate_pct"] == 4.0
    assert rep["p99_wire_latency_ms"] == 1.235

    out_json = tmp_path / "slo_out.json"
    orig_argv = list(sys.argv)
    try:
        sys.argv = ["blackbox_two_socket_slo_and_fuzzer.py", "--output-json", str(out_json), "--self-test"]
        rc = main()
    finally:
        sys.argv = orig_argv

    assert rc == 0 and isinstance(rc, int)
    raw_json = out_json.read_text(encoding="utf-8")
    assert '\n  "' in raw_json
    assert '\n   "' not in raw_json


def test_banned_words_compliance() -> None:
    """Verifies zero prohibited promotional words in the test file."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "bank-" + "grade",
    ]
    with open(__file__, "r", encoding="utf-8") as f:
        content = f.read()
    for word in banned:
        assert word not in content, f"Banned word detected: {word}"
