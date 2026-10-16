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
tests/test_integration_gates_g1_g7.py
Evaluates the signed G1-G7 gate report produced by scripts/run_integration_gates_g1_g7.py.
G1-G5 are locally evaluated; G6 and G7 require an external party and a customer and are
expected to report local prerequisites only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from src.jcs_canonicalizer import encode_jcs
import run_integration_gates_g1_g7 as gates

LOCAL_PENDING = "LOCAL_PREREQUISITES_PASS_EXTERNAL_PARTY_PENDING"


@pytest.fixture(scope="module")
def envelope(tmp_path_factory):
    out = tmp_path_factory.mktemp("g17") / "report.json"
    return gates.run_all_gates(output_path=out)


def test_g1_g5_evaluated_pass(envelope):
    g = envelope["report"]["gates"]
    for gid in (
        "G1_source_and_deps_locked",
        "G2_component_tests_passed",
        "G3_real_target_integrated",
        "G4_14_fault_matrix_passed",
        "G5_fresh_checkout_verified",
    ):
        assert g[gid]["status"] == "EVALUATED_PASS", gid


def test_g6_g7_not_claimed_as_external_pass(envelope):
    r = envelope["report"]
    for gid in ("G6_separate_party_reproduced", "G7_customer_pilot_accepted"):
        assert r["gates"][gid]["status"] == LOCAL_PENDING
    assert r["all_gates_passed"] is False
    assert r["all_local_prerequisites_passed"] is True
    assert set(r["external_gates_pending"]) == {
        "G6_separate_party_reproduced",
        "G7_customer_pilot_accepted",
    }
    assert r["audit_status"] == "LOCAL PASS; INDEPENDENT REPRODUCTION PENDING"


def test_g7_incident_candidate_boundary(envelope):
    b = envelope["report"]["gates"]["G7_customer_pilot_accepted"][
        "dora_art17_incident_candidate_boundary"
    ]
    assert b["classification_owner"] == "customer_defined"
    assert b["reporting_decision"] == "not_determined_by_aeib"
    assert b["financial_entity_awareness_time"] == "unknown_until_supplied"


def test_report_digest_and_signature_verify(envelope):
    stmt = encode_jcs(envelope["report"])
    assert envelope["report_digest"].replace("sha256:", "") == hashlib.sha256(stmt).hexdigest()
    sig = envelope["signature"]
    pub = serialization.load_pem_public_key(sig["public_key_pem"].encode("utf-8"))
    assert isinstance(pub, Ed25519PublicKey)
    pub.verify(base64.b64decode(sig["signature_b64"]), stmt)


def test_tampered_report_fails_verification(envelope):
    tampered = json.loads(json.dumps(envelope["report"]))
    tampered["all_gates_passed"] = True
    sig = envelope["signature"]
    pub = serialization.load_pem_public_key(sig["public_key_pem"].encode("utf-8"))
    with pytest.raises(Exception):
        pub.verify(base64.b64decode(sig["signature_b64"]), encode_jcs(tampered))
