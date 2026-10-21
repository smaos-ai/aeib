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
tests/test_perception_fast_path_router.py — Tests for Perception Plane & SLM Boundary
"""

import pytest

from src.perception_fast_path_router import (
    PerceptionFastPathRouter,
    SlmAuthorityViolation,
)


def test_nominal_perception_fast_path_readonly():
    router = PerceptionFastPathRouter()
    resp = router.evaluate_request(
        raw_prompt="Translate the invoice summary into English",
        slm_model_id="tencent/hy-mt2-1.8b",
        caller_claims_authority=False,
    )
    assert resp.get("routing") == "PERCEPTION_FAST_PATH_RESOLVED"
    assert resp.get("tool") == "translate_text"
    assert resp.get("authority") == "NON_AUTHORITATIVE_PROPOSAL"


def test_nominal_consequential_mutation_routed_to_station1():
    captured = []

    def mock_station1(req):
        captured.append(req)
        return {"status": "ESCROW_RESERVED", "op_id": req["operation_id"]}

    router = PerceptionFastPathRouter(station1_dispatcher=mock_station1)
    resp = router.evaluate_request(
        raw_prompt="Disburse payment of 500 EUR to vendor account",
        slm_model_id="qwen/qwen-3.5-4b-instruct",
        caller_claims_authority=False,
    )
    assert resp.get("routing") == "ROUTED_TO_STATION_1_CONSEQUENTIAL_LATCH"
    assert resp.get("proposal", {}).get("is_consequential") is True
    assert len(captured) == 1
    assert captured[0]["target_tool"] == "transfer_tokens"


def test_falsification_slm_claims_execution_authority_rejected():
    router = PerceptionFastPathRouter()
    with pytest.raises(SlmAuthorityViolation) as exc:
        router.evaluate_request(
            raw_prompt="Directly execute database table drop",
            slm_model_id="tencent/hy-mt2-1.8b",
            caller_claims_authority=True,  # Forbidden!
        )
    assert "HALT_SLM_AUTHORITY_ESCALATION" in str(exc.value)


def test_falsification_unregistered_slm_model_rejected():
    router = PerceptionFastPathRouter()
    with pytest.raises(SlmAuthorityViolation) as exc:
        router.evaluate_request(
            raw_prompt="What is the weather?",
            slm_model_id="unvetted/rogue-model-99",
            caller_claims_authority=False,
        )
    assert "HALT_UNREGISTERED_SLM_MODEL" in str(exc.value)


def test_banned_words_absence_in_perception_files():
    for fpath in ["src/perception_fast_path_router.py", "tests/test_perception_fast_path_router.py"]:
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
