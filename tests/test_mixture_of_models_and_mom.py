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
tests/test_mixture_of_models_and_mom.py
================================================================================
Falsification & verification suite for MoM Semantic Router, HarnessMM Cache,
Radix KV Aligner, and Tokenomics Monitor.
"""

import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.mixture_of_models_router import (
    MixtureOfModelsSemanticRouter,
    HarnessMMGuardedDecisionCache,
    ProductionTokenomicsMonitor,
    ProviderTurnUsage,
    RadixKVBlockAligner,
)


def test_mom_router_dispatch_logic() -> None:
    # 1. Oracle failure forces Opus escalation regardless of repo size
    dec_esc = MixtureOfModelsSemanticRouter.route_request(100000, "medium", oracle_failed=True)
    assert dec_esc.assigned_model == "claude-opus-5.5-medium"
    assert dec_esc.target_token_budget == 4000
    assert dec_esc.requires_escalation is True

    # High task risk also forces Opus
    dec_risk = MixtureOfModelsSemanticRouter.dispatch(2000, "high", oracle_failed=False)
    assert dec_risk.assigned_model == "claude-opus-5.5-medium"
    assert dec_risk.target_token_budget == 4000
    assert dec_risk.requires_escalation is True

    # 2. Large context routes to Argon Librarian
    dec_arg = MixtureOfModelsSemanticRouter.route_request(75000, "medium", oracle_failed=False)
    assert dec_arg.assigned_model == "gemini-4-argon-high-thinking"
    assert dec_arg.target_token_budget == 20000
    assert dec_arg.requires_escalation is False

    # 3. Small context or syntax error routes to Flash reflex
    dec_fl = MixtureOfModelsSemanticRouter.route_request(2000, "low", has_syntax_errors=True)
    assert dec_fl.assigned_model == "gemini-flash-reflex"
    assert dec_fl.target_token_budget == 1000
    assert dec_fl.requires_escalation is False

    dec_small = MixtureOfModelsSemanticRouter.route_request(4000, "low", has_syntax_errors=False)
    assert dec_small.assigned_model == "gemini-flash-reflex"
    assert dec_small.target_token_budget == 1000
    assert dec_small.requires_escalation is False

    # 4. Balanced tier for medium repos
    dec_std = MixtureOfModelsSemanticRouter.route_request(20000, "medium", has_syntax_errors=False)
    assert dec_std.assigned_model == "gemini-4-argon-standard"
    assert dec_std.target_token_budget == 8000
    assert dec_std.requires_escalation is False

    # 5. Verify default parameter values in dispatch
    dec_def = MixtureOfModelsSemanticRouter.dispatch(20000, "medium")
    assert dec_def.assigned_model == "gemini-4-argon-standard"
    assert dec_def.requires_escalation is False

    # 6. Exact tier boundaries: 4999 / 5000 and 49999 / 50000
    assert MixtureOfModelsSemanticRouter.route_request(4999, "medium").assigned_model == "gemini-flash-reflex"
    assert MixtureOfModelsSemanticRouter.route_request(5000, "medium").assigned_model == "gemini-4-argon-standard"
    assert MixtureOfModelsSemanticRouter.route_request(49999, "medium").assigned_model == "gemini-4-argon-standard"
    assert MixtureOfModelsSemanticRouter.route_request(50000, "medium").assigned_model == "gemini-4-argon-high-thinking"


def test_harnessmm_guarded_decision_reuse() -> None:
    cache = HarnessMMGuardedDecisionCache()
    assert cache.size() == 0

    patch = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-1\n+2\n"
    cache.store_verified_diff("intent_1", "merkle_root_1", "contract_1", patch)
    assert cache.size() == 1

    # Exact match -> O(1) hit at 0 LLM tokens
    hit = cache.get_cached_diff("intent_1", "merkle_root_1", "contract_1")
    assert hit == patch

    # Drifted AST merkle root -> Cache miss
    miss_ast = cache.get_cached_diff("intent_1", "merkle_root_2", "contract_1")
    assert miss_ast is None

    # Drifted intent hash -> Cache miss
    miss_intent = cache.get_cached_diff("intent_2", "merkle_root_1", "contract_1")
    assert miss_intent is None

    # Drifted contract digest -> Cache miss
    miss_contract = cache.get_cached_diff("intent_1", "merkle_root_1", "contract_2")
    assert miss_contract is None


def test_tokenomics_monitor_cache_wipeout() -> None:
    monitor = ProductionTokenomicsMonitor(expected_prefix_tokens=4000)

    # Turn 0: Clean cache creation
    ok0, msg0 = monitor.audit_turn(ProviderTurnUsage(0, 200, 4000, 0, 50))
    assert ok0 is True
    assert msg0 == "OK_CACHE_HEALTHY"

    # Turn 1: Normal cached read
    ok1, msg1 = monitor.audit_turn(ProviderTurnUsage(1, 100, 0, 4000, 60))
    assert ok1 is True
    assert msg1 == "OK_CACHE_HEALTHY"

    # Turn 0 with heavy cache creation is permitted (cold start)
    ok_turn0, _ = monitor.audit_turn(ProviderTurnUsage(0, 50, 3999, 0, 50))
    assert ok_turn0 is True

    # Turn 1 with exactly threshold - 1 is OK (1999 < 2000)
    ok_sub, _ = monitor.audit_turn(ProviderTurnUsage(1, 50, 1999, 1000, 50))
    assert ok_sub is True

    # Turn 1 with exactly threshold (2000) triggers HALT
    ok_thresh, code_thresh = monitor.audit_turn(ProviderTurnUsage(1, 50, 2000, 1000, 50))
    assert ok_thresh is False
    assert code_thresh == "HALT_MIDNIGHT_PREFIX_CACHE_WIPEOUT"

    # Turn 2: Midnight wipeout (prefix re-created due to volatile timestamp)
    ok2, code = monitor.audit_turn(ProviderTurnUsage(2, 200, 4000, 0, 50))
    assert ok2 is False
    assert code == "HALT_MIDNIGHT_PREFIX_CACHE_WIPEOUT"


def test_radix_kv_block_aligner() -> None:
    # 0 tokens requires 0 padding
    assert RadixKVBlockAligner.compute_padding_tokens(0) == 0
    assert RadixKVBlockAligner.align_token_count(0) == 0

    # Exactly 64 tokens requires 0 padding
    assert RadixKVBlockAligner.compute_padding_tokens(64) == 0
    assert RadixKVBlockAligner.align_token_count(64) == 64

    # 65 tokens needs 63 padding to reach 128
    assert RadixKVBlockAligner.compute_padding_tokens(65) == 63
    assert RadixKVBlockAligner.align_token_count(65) == 128

    # 100 tokens needs 28 padding to reach 128
    assert RadixKVBlockAligner.compute_padding_tokens(100) == 28
    assert RadixKVBlockAligner.align_token_count(100) == 128


def test_sovereign_mom_routing_integration() -> None:
    from src.sovereign_moat_upgrades import (
        Jurisdiction,
        ModelManifest,
        SovereignRoutingRequest,
    )

    req_pii = SovereignRoutingRequest(
        task_id="wire-task-01",
        contains_pii_or_finance=True,
        required_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    foreign_model = ModelManifest(
        model_id="qwen-72b-node",
        weight_snapshot_digest="sha256:weights_qwen",
        hosting_jurisdiction=Jurisdiction.RESTRICTED_EXPORT,
    )

    # Sensitive task to restricted export jurisdiction MUST HALT
    with pytest.raises(ValueError, match="HALT_GEOPOLITICAL_TAINT_VIOLATION"):
        MixtureOfModelsSemanticRouter.route_sovereign_request(
            request=req_pii,
            candidate_model=foreign_model,
            repo_tokens=10000,
            task_risk="medium",
        )

    # Domestic model succeeds and returns both MoMRoutingDecision and sovereign receipt
    domestic_model = ModelManifest(
        model_id="claude-opus-domestic",
        weight_snapshot_digest="sha256:weights_domestic",
        hosting_jurisdiction=Jurisdiction.EU_US_DOMESTIC,
    )
    decision, receipt = MixtureOfModelsSemanticRouter.route_sovereign_request(
        request=req_pii,
        candidate_model=domestic_model,
        repo_tokens=75000,
        task_risk="medium",
    )
    assert decision.assigned_model == "gemini-4-argon-high-thinking"
    assert receipt == "OK_ROUTED_TO_SOVEREIGN_MODEL:claude-opus-domestic"

    # repo_tokens has no silent default: a caller that omits the context size
    # must not be routed as if it were a 10k-token repository.
    with pytest.raises(TypeError):
        MixtureOfModelsSemanticRouter.route_sovereign_request(  # type: ignore[call-arg]
            request=req_pii, candidate_model=domestic_model
        )

