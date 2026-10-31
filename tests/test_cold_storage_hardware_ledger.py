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
tests/test_cold_storage_hardware_ledger.py
================================================================================
Comprehensive verification suite for ColdStorageHardwareLedger.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.cold_storage_hardware_ledger import (
    GENESIS_BLOCK_CAID,
    ColdStorageHardwareLedger,
    LedgerBlock,
)


@pytest.fixture
def ledger_setup(tmp_path: Path):
    ledger_file = tmp_path / "subdir" / "hardware_audit_chain.jsonl"
    assert not ledger_file.exists()
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    ledger = ColdStorageHardwareLedger(ledger_file_path=ledger_file, signing_key=priv)
    assert ledger_file.exists() and ledger_file.is_file()
    return ledger, ledger_file, pub_hex


def test_nominal_append_and_chain_verification(ledger_setup):
    ledger, ledger_file, pub_hex = ledger_setup

    # Empty ledger verification
    ok_empty, count_empty, err_empty = ledger.verify_chain_integrity()
    assert ok_empty is True
    assert count_empty == 0
    assert err_empty == "EMPTY_LEDGER"

    # Block 0 (Genesis)
    warrant_0 = {
        "operation_id": "op-001",
        "action_type": "AP2_MANDATE_INIT",
        "warrant_caid": "sha256:0000000000000000000000000000000000000000000000000000000000000001",
    }
    telemetry_0 = {"battery_bps": 9200, "thermal_state_raw": 0, "physical_memory_bytes": 8589934592}

    b0 = ledger.append_warrant(warrant_0, telemetry_0, timestamp_epoch_sec=1700000000)
    assert b0.block_index == 0
    assert b0.previous_block_caid == GENESIS_BLOCK_CAID
    assert b0.block_caid.startswith("sha256:")

    # Block 1
    warrant_1 = {
        "operation_id": "op-002",
        "action_type": "T3_DEPLOY_RELEASE",
        "warrant_caid": "sha256:0000000000000000000000000000000000000000000000000000000000000002",
    }
    telemetry_1 = {"battery_bps": 9150, "thermal_state_raw": 1, "physical_memory_bytes": 8589934592}

    b1 = ledger.append_warrant(warrant_1, telemetry_1, timestamp_epoch_sec=1700000100)
    assert b1.block_index == 1
    assert b1.previous_block_caid == b0.block_caid

    # Verify chain integrity
    ok, count, err = ledger.verify_chain_integrity(pinned_pubkey_hex=pub_hex)
    assert ok is True
    assert count == 2
    assert err == "OK"

    # Block dataclass immutability and to_dict
    d0 = b0.to_dict()
    assert d0["block_index"] == 0
    assert d0["previous_block_caid"] == GENESIS_BLOCK_CAID
    with pytest.raises((AttributeError, TypeError)):
        b0.block_index = 99  # type: ignore


def test_tamper_detection_on_block_mutation(ledger_setup):
    ledger, ledger_file, pub_hex = ledger_setup

    ledger.append_warrant({"op": 1}, {"bat": 9000})
    ledger.append_warrant({"op": 2}, {"bat": 8900})

    lines = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    orig_b0 = lines[0]

    # Mutate block 0 payload in place without re-signing
    b0_dict = json.loads(orig_b0)
    b0_dict["enclave_warrant"]["op"] = 999  # Tamper
    lines[0] = json.dumps(b0_dict)
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, bad_idx, err = ledger.verify_chain_integrity(pinned_pubkey_hex=pub_hex)
    assert ok is False
    assert bad_idx == 0
    assert "ERR_BLOCK_CAID_TAMPER" in err

    # Now test signature corruption on original uncorrupted body
    b0_dict_sig = json.loads(orig_b0)
    b0_dict_sig["signature_hex"] = "aa" * 64
    lines[0] = json.dumps(b0_dict_sig)
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok_sig, bad_idx_sig, err_sig = ledger.verify_chain_integrity(pinned_pubkey_hex=pub_hex)
    assert ok_sig is False
    assert bad_idx_sig == 0
    assert err_sig == "ERR_INVALID_SIGNATURE_AT_0"


def test_broken_hash_chain_on_block_deletion(ledger_setup):
    ledger, ledger_file, pub_hex = ledger_setup

    ledger.append_warrant({"op": 1}, {"bat": 9000})
    ledger.append_warrant({"op": 2}, {"bat": 8900})
    ledger.append_warrant({"op": 3}, {"bat": 8800})

    lines = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    # Delete block 1
    del lines[1]
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, bad_idx, err = ledger.verify_chain_integrity(pinned_pubkey_hex=pub_hex)
    assert ok is False
    # Will fail on block index mismatch or previous CAID broken chain
    assert "ERR_BLOCK_INDEX_MISMATCH" in err or "ERR_PREVIOUS_CAID_CHAIN_BROKEN" in err

    # Specific previous CAID chain link corruption
    lines_fresh = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    b_broken = json.loads(lines_fresh[1])
    b_broken["block_index"] = 1  # fix index so it doesn't fail on index check
    b_broken["previous_block_caid"] = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    lines_fresh[1] = json.dumps(b_broken)
    ledger_file.write_text("\n".join(lines_fresh) + "\n", encoding="utf-8")

    ok_chain, bad_idx_chain, err_chain = ledger.verify_chain_integrity(pinned_pubkey_hex=pub_hex)
    assert ok_chain is False
    assert bad_idx_chain == 1
    assert err_chain == "ERR_PREVIOUS_CAID_CHAIN_BROKEN_AT_1"


def test_unpinned_public_key_rejection(ledger_setup):
    ledger, ledger_file, pub_hex = ledger_setup
    ledger.append_warrant({"op": 1}, {"bat": 9000})

    other_pub_hex = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    ok, bad_idx, err = ledger.verify_chain_integrity(pinned_pubkey_hex=other_pub_hex)
    assert ok is False
    assert bad_idx == 0
    assert err == "ERR_UNPINNED_LEDGER_PUBLIC_KEY"


def test_cold_storage_bundle_export(ledger_setup, tmp_path: Path):
    ledger, ledger_file, _ = ledger_setup
    ledger.append_warrant({"op": "export_test"}, {"thermal": 0})

    simulated_usb_ssd = tmp_path / "Volumes" / "EXT_SSD_2TB"
    exported_path = ledger.export_cold_storage_bundle(export_dir=simulated_usb_ssd)

    assert exported_path.exists()
    assert exported_path.name == ledger_file.name
    assert exported_path.read_text() == ledger_file.read_text()


def test_deep_directory_creation_and_reopen(tmp_path: Path):
    deep_path = tmp_path / "layer1" / "layer2" / "layer3" / "nested_ledger.jsonl"
    l1 = ColdStorageHardwareLedger(ledger_file_path=deep_path)
    assert deep_path.exists()
    # Reopening on existing parent dir tests exist_ok=True
    l2 = ColdStorageHardwareLedger(ledger_file_path=deep_path)
    assert l2.ledger_path == deep_path


def test_ledger_block_immutability(ledger_setup):
    ledger, _, _ = ledger_setup
    block = ledger.append_warrant({"op": "immutability_check"}, {"power": 100})
    with pytest.raises(Exception):
        block.block_index = 999


def test_sys_path_bootstrap_exact_boundary():
    """Verifies sys.path.insert(0) boundary in cold_storage_hardware_ledger."""
    import importlib
    import sys
    from pathlib import Path
    import src.cold_storage_hardware_ledger as mod
    repo_str = str(Path(mod.__file__).resolve().parent.parent)
    orig_path = list(sys.path)
    try:
        sys.path = ["/dummy_marker"] + [p for p in sys.path if p != repo_str]
        importlib.reload(mod)
        assert sys.path[0] == repo_str
    finally:
        sys.path = orig_path

