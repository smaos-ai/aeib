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
tests/test_edge_telemetry_node.py — Unit and adversarial tests for edge telemetry verification.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jcs_canonicalizer import encode_jcs
from src.strict_json_ingress import loads_strict
from tools.verify_edge_telemetry_receipt import _has_float, main, verify_edge_telemetry_receipt


def test_has_float_unit() -> None:
    assert _has_float(1) is False
    assert _has_float("test") is False
    assert _has_float([1, 2, "3"]) is False
    assert _has_float({"a": 1, "b": [2, 3]}) is False
    assert _has_float(1.5) is True
    assert _has_float([1.0]) is True
    assert _has_float({"a": 2.0}) is True


@pytest.fixture(scope="module")
def valid_sample_receipt() -> dict:
    """Generate a real Ed25519 signed edge telemetry receipt."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_hex = pub.public_bytes_raw().hex()

    body = {
        "boundary_probes": {
            "physical_memory_bytes": 19327352832,
            "probe_path_traversal_blocked": True,
            "probe_root_fs_write_blocked": True,
            "thermal_state_raw": 0,
        },
        "node_id": "andrii’s iPhone (iPhone17,2, arm64e)",
        "os_version": "iOS 26.3 (Build 23D127)",
        "schema_version": "aeib.edge.telemetry.v1",
        "sequence_number": 1,
        "signer_pubkey_hex": pub_hex,
        "tags": ["edge", "a18pro"],
        "timestamp_epoch_s": 1793228987,
    }

    canon_bytes = encode_jcs(body)
    caid = "sha256:" + hashlib.sha256(canon_bytes).hexdigest()
    sig_hex = priv.sign(canon_bytes).hex()

    return {
        "receipt_body": body,
        "caid": caid,
        "signature_ed25519_hex": sig_hex,
        "envelope_version": "1.0",
    }


def test_valid_edge_receipt_verifies(valid_sample_receipt: dict) -> None:
    ok, reason, meta = verify_edge_telemetry_receipt(valid_sample_receipt)
    assert ok is True
    assert reason == "OK_EDGE_TELEMETRY_VERIFIED"
    assert meta["caid"] == valid_sample_receipt["caid"]
    assert meta["node_id"] == "andrii’s iPhone (iPhone17,2, arm64e)"
    assert meta["signer_pubkey_hex"] == valid_sample_receipt["receipt_body"]["signer_pubkey_hex"]
    assert meta["timestamp_epoch_s"] == 1793228987
    assert meta["thermal_state_raw"] == 0
    assert meta["physical_memory_bytes"] == 19327352832


def test_tampered_caid_is_rejected(valid_sample_receipt: dict) -> None:
    bad = copy.deepcopy(valid_sample_receipt)
    bad["caid"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    ok, reason, meta = verify_edge_telemetry_receipt(bad)
    assert ok is False
    assert reason == "ERR_CAID_DIGEST_MISMATCH"
    assert meta["claimed"] == bad["caid"]
    assert meta["computed"].startswith("sha256:")


def test_tampered_body_payload_fails_signature(valid_sample_receipt: dict) -> None:
    bad = copy.deepcopy(valid_sample_receipt)
    bad["receipt_body"]["sequence_number"] = 999
    bad["caid"] = "sha256:" + hashlib.sha256(encode_jcs(bad["receipt_body"])).hexdigest()
    ok, reason, _ = verify_edge_telemetry_receipt(bad)
    assert ok is False
    assert "ERR_ED25519_SIGNATURE_INVALID" in reason


def test_tampered_signature_is_rejected(valid_sample_receipt: dict) -> None:
    bad = copy.deepcopy(valid_sample_receipt)
    orig_sig = bad["signature_ed25519_hex"]
    flipped = ("0" if orig_sig[0] != "0" else "1") + orig_sig[1:]
    bad["signature_ed25519_hex"] = flipped
    ok, reason, _ = verify_edge_telemetry_receipt(bad)
    assert ok is False
    assert "ERR_ED25519_SIGNATURE_INVALID" in reason


def test_unpinned_public_key_is_rejected(valid_sample_receipt: dict) -> None:
    wrong_key_hex = "a" * 64
    ok, reason, _ = verify_edge_telemetry_receipt(
        valid_sample_receipt, expected_pubkey_hex=wrong_key_hex
    )
    assert ok is False
    assert reason == "ERR_UNPINNED_SIGNER_KEY"

    # Matching pubkey passes
    good_pubkey = valid_sample_receipt["receipt_body"]["signer_pubkey_hex"]
    ok2, reason2, _ = verify_edge_telemetry_receipt(
        valid_sample_receipt, expected_pubkey_hex=good_pubkey
    )
    assert ok2 is True
    assert reason2 == "OK_EDGE_TELEMETRY_VERIFIED"


def test_float_in_body_fails_closed(valid_sample_receipt: dict) -> None:
    bad1 = copy.deepcopy(valid_sample_receipt)
    bad1["receipt_body"]["boundary_probes"]["thermal_state_raw"] = 0.5
    ok, reason, _ = verify_edge_telemetry_receipt(bad1)
    assert ok is False
    assert reason == "ERR_FLOAT_IN_JCS_BODY"

    bad2 = copy.deepcopy(valid_sample_receipt)
    bad2["receipt_body"]["tags"] = ["edge", 2.5]
    ok, reason, _ = verify_edge_telemetry_receipt(bad2)
    assert ok is False
    assert reason == "ERR_FLOAT_IN_JCS_BODY"


def test_failed_sandbox_probe_fails_closed(valid_sample_receipt: dict) -> None:
    # Boolean False
    bad = copy.deepcopy(valid_sample_receipt)
    bad["receipt_body"]["boundary_probes"]["probe_root_fs_write_blocked"] = False
    priv = Ed25519PrivateKey.generate()
    bad["receipt_body"]["signer_pubkey_hex"] = priv.public_key().public_bytes_raw().hex()
    canon_bytes = encode_jcs(bad["receipt_body"])
    bad["caid"] = "sha256:" + hashlib.sha256(canon_bytes).hexdigest()
    bad["signature_ed25519_hex"] = priv.sign(canon_bytes).hex()

    ok, reason, probes = verify_edge_telemetry_receipt(bad)
    assert ok is False
    assert reason == "ERR_SANDBOX_CONTAINMENT_PROBE_FAILED"
    assert probes["probe_root_fs_write_blocked"] is False

    # String "true" instead of bool True
    bad_str = copy.deepcopy(valid_sample_receipt)
    bad_str["receipt_body"]["boundary_probes"]["probe_root_fs_write_blocked"] = "true"  # type: ignore[assignment]
    priv2 = Ed25519PrivateKey.generate()
    bad_str["receipt_body"]["signer_pubkey_hex"] = priv2.public_key().public_bytes_raw().hex()
    canon2 = encode_jcs(bad_str["receipt_body"])
    bad_str["caid"] = "sha256:" + hashlib.sha256(canon2).hexdigest()
    bad_str["signature_ed25519_hex"] = priv2.sign(canon2).hex()

    ok_str, reason_str, _ = verify_edge_telemetry_receipt(bad_str)
    assert ok_str is False
    assert reason_str == "ERR_SANDBOX_CONTAINMENT_PROBE_FAILED"

    # Path traversal failure
    bad3 = copy.deepcopy(valid_sample_receipt)
    bad3["receipt_body"]["boundary_probes"]["probe_path_traversal_blocked"] = False
    bad3["receipt_body"]["signer_pubkey_hex"] = priv.public_key().public_bytes_raw().hex()
    canon3 = encode_jcs(bad3["receipt_body"])
    bad3["caid"] = "sha256:" + hashlib.sha256(canon3).hexdigest()
    bad3["signature_ed25519_hex"] = priv.sign(canon3).hex()
    ok3, reason3, _ = verify_edge_telemetry_receipt(bad3)
    assert ok3 is False
    assert reason3 == "ERR_SANDBOX_CONTAINMENT_PROBE_FAILED"


def test_malformed_receipt_structures(valid_sample_receipt: dict) -> None:
    assert verify_edge_telemetry_receipt("not_a_dict")[0] is False  # type: ignore[arg-type]
    assert verify_edge_telemetry_receipt("not_a_dict")[1] == "ERR_INVALID_RECEIPT_FORMAT"

    bad = copy.deepcopy(valid_sample_receipt)
    del bad["envelope_version"]
    assert verify_edge_telemetry_receipt(bad)[1] == "ERR_MISSING_ENVELOPE_KEYS"

    bad = copy.deepcopy(valid_sample_receipt)
    bad["receipt_body"] = "not_a_dict"
    assert verify_edge_telemetry_receipt(bad)[1] == "ERR_INVALID_BODY_TYPE"

    bad = copy.deepcopy(valid_sample_receipt)
    bad["caid"] = 123
    assert verify_edge_telemetry_receipt(bad)[1] == "ERR_INVALID_CRYPTO_TYPES"

    bad = copy.deepcopy(valid_sample_receipt)
    bad["signature_ed25519_hex"] = 123
    assert verify_edge_telemetry_receipt(bad)[1] == "ERR_INVALID_CRYPTO_TYPES"

    bad = copy.deepcopy(valid_sample_receipt)
    bad["receipt_body"]["signer_pubkey_hex"] = "short"
    bad["caid"] = "sha256:" + hashlib.sha256(encode_jcs(bad["receipt_body"])).hexdigest()
    assert verify_edge_telemetry_receipt(bad)[1] == "ERR_INVALID_SIGNER_PUBKEY"

    bad = copy.deepcopy(valid_sample_receipt)
    del bad["receipt_body"]["boundary_probes"]
    priv = Ed25519PrivateKey.generate()
    bad["receipt_body"]["signer_pubkey_hex"] = priv.public_key().public_bytes_raw().hex()
    canon = encode_jcs(bad["receipt_body"])
    bad["caid"] = "sha256:" + hashlib.sha256(canon).hexdigest()
    bad["signature_ed25519_hex"] = priv.sign(canon).hex()
    ok, reason, _ = verify_edge_telemetry_receipt(bad)
    assert ok is False
    assert reason == "ERR_MISSING_BOUNDARY_PROBES"

    # JCS canonicalization failure (non-string key)
    bad_key = copy.deepcopy(valid_sample_receipt)
    bad_key["receipt_body"] = {123: "bad_key_type"}  # type: ignore[dict-item]
    ok_k, reason_k, _ = verify_edge_telemetry_receipt(bad_key)
    assert ok_k is False
    assert "ERR_JCS_CANONICALIZATION_FAILED" in reason_k


def test_main_cli_execution(valid_sample_receipt: dict, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    valid_file = tmp_path / "receipt_valid.json"
    valid_file.write_text(json.dumps(valid_sample_receipt), encoding="utf-8")
    pub_hex = valid_sample_receipt["receipt_body"]["signer_pubkey_hex"]

    # 1. Valid receipt file with pubkey pin
    exit_code = main(["--receipt", str(valid_file), "--pubkey", pub_hex])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "[VALID]" in out
    assert valid_sample_receipt["caid"] in out

    # 2. JSON mode
    exit_code = main(["--receipt", str(valid_file), "--json"])
    assert exit_code == 0
    out_json = json.loads(capsys.readouterr().out)
    assert out_json["valid"] is True
    assert out_json["metadata"]["caid"] == valid_sample_receipt["caid"]

    # 3. Missing file
    exit_code = main(["--receipt", str(tmp_path / "nonexistent.json")])
    assert exit_code == 2

    # 4. Bad JSON file
    bad_json_file = tmp_path / "bad.json"
    bad_json_file.write_text("{broken", encoding="utf-8")
    exit_code = main(["--receipt", str(bad_json_file)])
    assert exit_code == 2

    # 5. Invalid receipt (tampered)
    tampered = copy.deepcopy(valid_sample_receipt)
    tampered["caid"] = "sha256:0000"
    tampered_file = tmp_path / "receipt_tampered.json"
    tampered_file.write_text(json.dumps(tampered), encoding="utf-8")

    exit_code = main(["--receipt", str(tampered_file)])
    assert exit_code == 1
    assert "[INVALID]" in capsys.readouterr().out


def test_swift_compiled_node_generates_verifiable_receipt(tmp_path: Path) -> None:
    """End-to-end integration test: compiles Swift code and verifies output."""
    swift_bin = tmp_path / "edge_node"
    sources = [
        "tools/ios_edge_node/Sources/Core/JCSCanonicalizer.swift",
        "tools/ios_edge_node/Sources/Core/EdgeTelemetryNode.swift",
        "tools/ios_edge_node/Sources/CLI/main.swift",
    ]
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "DEVELOPER_DIR": "/Applications/Xcode.app/Contents/Developer",
    }
    compile_cmd = ["xcrun", "swiftc", *sources, "-o", str(swift_bin)]
    c_res = subprocess.run(compile_cmd, env=env, capture_output=True, text=True)
    assert c_res.returncode == 0, f"Swift compilation failed: {c_res.stderr}"

    run_res = subprocess.run([str(swift_bin)], capture_output=True, text=True)
    assert run_res.returncode == 0

    lines = run_res.stdout.strip().splitlines()
    assert "--- BEGIN SOVEREIGN EDGE TELEMETRY RECEIPT ---" in lines
    idx = lines.index("--- BEGIN SOVEREIGN EDGE TELEMETRY RECEIPT ---")
    receipt_json = lines[idx + 1]

    data = loads_strict(receipt_json)
    ok, reason, meta = verify_edge_telemetry_receipt(data)
    assert ok is True
    assert reason == "OK_EDGE_TELEMETRY_VERIFIED"
    assert meta["node_id"] == "andrii’s iPhone (iPhone17,2, arm64e)"
