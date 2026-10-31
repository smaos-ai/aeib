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
tests/test_redteam_iphone_notary.py
Validates the 5 adversarial red-team probes for the Apple Silicon Biometric Notary.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.redteam_iphone_notary_adversarial import (
    probe_1_wysiwys_payload_alteration,
    probe_2_replay_expired_warrant,
    probe_3_unpinned_key_forgery,
    probe_4_corrupted_der_signature,
    probe_5_operator_human_veto,
    main,
)


def test_probe_1_wysiwys_payload_alteration() -> None:
    defended, detail = probe_1_wysiwys_payload_alteration()
    assert defended is True
    assert "DEFENDED" in detail


def test_probe_2_replay_expired_warrant() -> None:
    defended, detail = probe_2_replay_expired_warrant()
    assert defended is True
    assert "DEFENDED" in detail


def test_probe_3_unpinned_key_forgery() -> None:
    defended, detail = probe_3_unpinned_key_forgery()
    assert defended is True
    assert "DEFENDED" in detail


def test_probe_4_corrupted_der_signature() -> None:
    defended, detail = probe_4_corrupted_der_signature()
    assert defended is True
    assert "DEFENDED" in detail


def test_probe_5_operator_human_veto() -> None:
    defended, detail = probe_5_operator_human_veto()
    assert defended is True
    assert "DEFENDED" in detail


def test_redteam_main_entrypoint() -> None:
    ret = main()
    assert ret == 0
