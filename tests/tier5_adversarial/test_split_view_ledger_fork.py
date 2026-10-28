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

r"""
test_split_view_ledger_fork.py — Acceptance Test AT55 (Split-View Fork Defense)
Evaluates external transparency anchor inclusion: if an adversary tampers with
the local Merkle root or presents split-view histories to internal vs external observers,
the discrepancy against the anchor trips RECONCILIATION_CONFLICT.
"""

import hashlib
import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.governance_boundary import AppendOnlyEvidenceLedger


class SplitViewForkError(RuntimeError):
    """Raised when local ledger state diverges from external transparency anchor."""
    disposition = "RECONCILIATION_CONFLICT"


def verify_ledger_against_external_anchor(
    ledger: AppendOnlyEvidenceLedger,
    external_transparency_anchor_root: str,
) -> bool:
    """
    Verifies that the local ledger root matches the externally anchored Merkle root.
    """
    # 1. Internal integrity check
    if not ledger.verify_integrity():
        raise SplitViewForkError("Local ledger cryptographic hash chain verification failed.")

    # 2. External anchor consistency check
    local_root = ledger.get_latest_hash()
    if local_root != external_transparency_anchor_root:
        raise SplitViewForkError(
            f"RECONCILIATION_CONFLICT: Local ledger root '{local_root}' conflicts "
            f"with external transparency anchor '{external_transparency_anchor_root}'."
        )

    return True


class TestSplitViewLedgerForkAT55:
    def setup_method(self):
        self.ledger = AppendOnlyEvidenceLedger()
        self.ledger.append({"event": "dispatch_authorized", "caid": "caid:sha256:1111"})
        self.ledger.append({"event": "transport_observation", "status": 504})
        self.ledger.append({"event": "effect_indeterminate_latch", "retry_safe": False})

    def test_matching_anchor_verifies_successfully(self):
        # Anchor is synchronized with latest local entry hash
        anchor_root = self.ledger.get_latest_hash()
        is_valid = verify_ledger_against_external_anchor(self.ledger, anchor_root)
        assert is_valid is True

    def test_divergent_anchor_triggers_reconciliation_conflict(self):
        # Adversary presents a ledger fork with a forged external anchor
        forged_anchor = "fa" * 32

        with pytest.raises(SplitViewForkError) as exc_info:
            verify_ledger_against_external_anchor(self.ledger, forged_anchor)

        assert "RECONCILIATION_CONFLICT" in str(exc_info.value)
        assert exc_info.value.disposition == "RECONCILIATION_CONFLICT"

    def test_internal_entry_tampering_triggers_reconciliation_conflict(self):
        # Adversary mutates an internal record in-place
        self.ledger.entries[1]["data"]["status"] = 200  # Attempt to rewrite 504 to 200!
        anchor_root = self.ledger.get_latest_hash()

        with pytest.raises(SplitViewForkError) as exc_info:
            verify_ledger_against_external_anchor(self.ledger, anchor_root)

        assert "hash chain verification failed" in str(exc_info.value)
