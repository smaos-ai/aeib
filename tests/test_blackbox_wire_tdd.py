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
tests/test_blackbox_wire_tdd.py — Black-Box Interface TDD & Real Digital Twin Tests.

Evaluates clean-room black-box reverse engineering of the Station 1 Wire Contract
against a stateful local digital twin HTTP server on real TCP localhost (127.0.0.1:0).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blackbox_wire_tdd_harness import (
    CleanRoomBlackBoxEngine,
    RealLocalPaymentTwinServer,
    execute_declarative_vectors,
)


def test_declarative_vectors_against_real_twin_server():
    """Evaluates the full declarative JSONL vectors against the real TCP twin server."""
    vectors_file = REPO_ROOT / "evidence" / "conformance_vectors_v1.jsonl"
    assert vectors_file.exists(), f"Missing vectors file: {vectors_file}"

    with RealLocalPaymentTwinServer() as twin:
        engine = CleanRoomBlackBoxEngine(
            target_host=twin.host,
            target_port=twin.port,
            sprint_ceiling_minor=1000_00,
            pinned_recipients={"iban:DE89370400440532013000"},
            shared_secret_key=b"clean-room-wire-secret-2026",
        )

        res = execute_declarative_vectors(vectors_file, engine, twin)

        assert res["status"] == "PASS"
        assert res["total_vectors"] >= 10
        assert res["twin_duplicate_bugs"] == 0
        assert res["twin_raw_mutations"] == 2
        assert twin.dataset.pinned_accounts["iban:DE89370400440532013000"] == 700_00


def test_blackbox_cli_json_execution():
    """Evaluates CLI execution with --json output."""
    cmd = [sys.executable, str(REPO_ROOT / "tools" / "blackbox_wire_tdd_harness.py"), "--json"]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}"

    data = json.loads(proc.stdout)
    assert data["status"] == "PASS"
    assert data["twin_duplicate_bugs"] == 0
    assert data["total_vectors"] >= 10


def test_negative_payload_and_malformed_frames_fail_closed():
    """Asserts that non-dict frames or negative amounts fail closed with explicit error codes."""
    with RealLocalPaymentTwinServer() as twin:
        engine = CleanRoomBlackBoxEngine(
            target_host=twin.host,
            target_port=twin.port,
            sprint_ceiling_minor=1000_00,
            pinned_recipients={"iban:DE89370400440532013000"},
            shared_secret_key=b"clean-room-wire-secret-2026",
        )

        # 1. Non-dict JSON payload (list instead of object)
        r1 = json.loads(engine.handle_wire_frame(b'["DISPATCH", "invalid"]'))
        assert r1["disposition"] == "NOT_DISPATCHED"
        assert r1["error_code"] == "ERR_INVALID_SCHEMA"

        # 2. Negative amount injection
        r2 = json.loads(
            engine.handle_wire_frame(
                json.dumps(
                    {
                        "action": "DISPATCH",
                        "operation_id": "op-neg",
                        "amount_minor": -500,
                        "recipient": "iban:DE89370400440532013000",
                        "caid_token": "any",
                    }
                ).encode("utf-8")
            )
        )
        assert r2["disposition"] == "NOT_DISPATCHED"
        assert r2["error_code"] == "ERR_INVALID_SCHEMA"


def test_banned_promotional_words_check():
    """Enforces AGENTS.md epistemic boundary on all owned files."""
    files_to_check = [
        REPO_ROOT / "tools" / "blackbox_wire_tdd_harness.py",
        REPO_ROOT / "tests" / "test_blackbox_wire_tdd.py",
        REPO_ROOT / "schemas" / "aeib_station1_interface.yaml",
    ]

    banned_stems = [
        "guaran" + "tee",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven universal" + "ly",
        "unassail" + "able",
        "im" + "mune",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]

    for path in files_to_check:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for stem in banned_stems:
            matches = re.findall(r"\b" + stem + r"\b", text, re.IGNORECASE)
            assert (
                len(matches) == 0
            ), f"Banned word '{stem}' found in {path.name}: {matches}"
