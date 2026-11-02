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
    CandidateToolProposal,
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
    assert len(resp["proposal"]["id"]) == 21  # 'prop_' (5) + 16 hex chars
    assert len(captured) == 1
    assert captured[0]["target_tool"] == "transfer_tokens"
    assert captured[0]["arguments"]["synthetic_eval"] is True


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


def test_default_station1_dispatcher():
    # Router without explicit station1_dispatcher uses default
    router = PerceptionFastPathRouter()
    resp = router.evaluate_request(
        raw_prompt="pay 100 EUR to merchant",
        slm_model_id="apple/ane-slm-core",
    )
    assert resp["routing"] == "ROUTED_TO_STATION_1_CONSEQUENTIAL_LATCH"
    s1 = resp["station1_response"]
    assert s1["status"] == "STATION1_ENQUEUED"
    assert s1["escrow_locked"] is True


def test_perception_cache_hit_and_lookup_balance():
    router = PerceptionFastPathRouter()
    # 1. First call: non-consequential, resolves fast path with lookup_balance
    resp1 = router.evaluate_request("Check my available quota", "apple/ane-slm-core")
    assert resp1["routing"] == "PERCEPTION_FAST_PATH_RESOLVED"
    assert resp1["tool"] == "lookup_balance"

    # 2. Second call: cache hit
    resp2 = router.evaluate_request("Check my available quota", "apple/ane-slm-core")
    assert resp2["routing"] == "PERCEPTION_CACHE_HIT"
    assert resp2["result"]["tool"] == "lookup_balance"

    # 3. Third call after 61s TTL expiration: cache miss, fast path re-resolved
    import time
    cache_key = list(router.perception_cache.keys())[0]
    val, _ = router.perception_cache[cache_key]
    router.perception_cache[cache_key] = (val, time.time() - 60.5)
    resp3 = router.evaluate_request("Check my available quota", "apple/ane-slm-core")
    assert resp3["routing"] == "PERCEPTION_FAST_PATH_RESOLVED"


def test_candidate_tool_proposal_frozenness():
    import dataclasses

    prop = CandidateToolProposal(
        proposal_id="p1",
        slm_model_id="m1",
        target_tool="t1",
        proposed_arguments={},
        is_consequential=False,
        confidence_score=0.9,
        generated_at=100,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        prop.confidence_score = 1.0  # type: ignore[misc]
