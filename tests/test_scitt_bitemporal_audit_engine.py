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
tests/test_scitt_bitemporal_audit_engine.py — Tests for SCITT Audit Engine & AT70b Anti-Reset Anchor
"""

import base64
import os
import tempfile
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.scitt_bitemporal_audit_engine import (
    ScittAuditViolation,
    ScittBitemporalAuditEngine,
    SupervisorRecoveryWarrant,
)


def test_nominal_scitt_append_and_sth_anchor():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = ScittBitemporalAuditEngine(storage_dir=tmpdir)
        ev1 = engine.append_event(
            aggregate_type="ACCOUNT",
            aggregate_id="acc_991",
            event_type="ESCROW_RESERVED",
            payload={"amount_minor": 10000, "currency": "EUR"},
        )
        assert ev1["tree_size"] == 1
        assert ev1["entry_index"] == 0

        ev2 = engine.append_event(
            aggregate_type="ACCOUNT",
            aggregate_id="acc_991",
            event_type="DISPATCH_CONFIRMED",
            payload={"amount_minor": 10000, "tx_ref": "tx_abc123"},
        )
        assert ev2["tree_size"] == 2
        assert ev2["entry_index"] == 1

        # Check STH anchor file on disk
        anchor_path = os.path.join(tmpdir, "scitt_sth_anchor.json")
        assert os.path.exists(anchor_path)


def test_falsification_at70a_clock_drift_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = ScittBitemporalAuditEngine(storage_dir=tmpdir)
        fake_future_time = int(time.time()) + 100  # 100s in future > 5s
        with pytest.raises(ScittAuditViolation) as exc:
            engine.append_event(
                aggregate_type="AUDIT",
                aggregate_id="test",
                event_type="ACTION",
                payload={"test": 1},
                client_timestamp=fake_future_time,
            )
        assert "HALT_CLOCK_DRIFT_EXCEEDED" in str(exc.value)


def test_falsification_at70b_two_file_wipe_detected():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = ScittBitemporalAuditEngine(storage_dir=tmpdir)
        engine.append_event(
            aggregate_type="LEDGER",
            aggregate_id="tx_1",
            event_type="COMMIT",
            payload={"val": 1},
        )
        engine.append_event(
            aggregate_type="LEDGER",
            aggregate_id="tx_2",
            event_type="COMMIT",
            payload={"val": 2},
        )

        # Adversary attempts a two-file local state wipe by removing the ledger
        ledger_file = os.path.join(tmpdir, "scitt_ledger.jsonl")
        os.unlink(ledger_file)

        # On restart, boot check detects missing ledger against embedded STH
        with pytest.raises(ScittAuditViolation) as exc:
            ScittBitemporalAuditEngine(
                storage_dir=tmpdir,
                sth_signer=engine.sth_signer,
            )
        assert "HALT_TWO_FILE_WIPE_DETECTED_AGAINST_SCITT_ANCHOR" in str(exc.value)


def test_recovery_with_supervisor_warrant():
    supervisor_priv = ed25519.Ed25519PrivateKey.generate()
    supervisor_pub = supervisor_priv.public_key()

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = ScittBitemporalAuditEngine(storage_dir=tmpdir, supervisor_pubkey=supervisor_pub)
        engine.append_event(
            aggregate_type="LEDGER",
            aggregate_id="tx_1",
            event_type="COMMIT",
            payload={"val": 1},
        )

        # Corrupt / delete ledger
        ledger_file = os.path.join(tmpdir, "scitt_ledger.jsonl")
        os.unlink(ledger_file)

        # Create valid supervisor recovery warrant
        ts = int(time.time())
        warrant_payload = {
            "authorized_reset_timestamp": ts,
            "previous_sth_root": "previous_root",
            "reason": "DR_RECOVERY_AFTER_INCIDENT",
            "supervisor_id": "sup_risk_officer_01",
            "warrant_id": "warrant_rec_001",
        }
        sig = supervisor_priv.sign(encode_jcs(warrant_payload))
        warrant = SupervisorRecoveryWarrant(
            warrant_id=warrant_payload["warrant_id"],
            supervisor_id=warrant_payload["supervisor_id"],
            authorized_reset_timestamp=ts,
            previous_sth_root=warrant_payload["previous_sth_root"],
            reason=warrant_payload["reason"],
            signature_b64=base64.b64encode(sig).decode("ascii"),
        )

        # Unlock and reset with warrant
        engine.recover_with_warrant(warrant)

        # Now boot check succeeds
        new_engine = ScittBitemporalAuditEngine(
            storage_dir=tmpdir,
            sth_signer=engine.sth_signer,
            supervisor_pubkey=supervisor_pub,
        )
        assert len(new_engine.leaves) == 0


def test_banned_words_absence_in_scitt_files():
    for fpath in ["src/scitt_bitemporal_audit_engine.py", "tests/test_scitt_bitemporal_audit_engine.py"]:
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read().lower()
        forbidden = [
            "guaran" + "tee",
            "bullet" + "proof",
            "enterprise-" + "grade",
            "production-" + "safe",
            "100% " + "secure",
            "unassail" + "able",
        ]
        for word in forbidden:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
