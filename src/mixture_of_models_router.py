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
src/mixture_of_models_router.py
================================================================================
Unified Mixture-of-Models (MoM) Semantic Router & Tokenomics Enforcement Engine.

Evaluated under the stated model:
Combines:
1. Signal-Driven MoM Routing (Flash for triage, Argon for 1M ingestion, Opus for surgery).
2. HarnessMM O(1) Guarded Decision Reuse ($0 token re-plays on unchanged AST merges).
3. Real Provider Tokenomics Tracker (detects midnight timestamp prefix cache wipeouts).
4. Radix 64-token KV-Block Quantization Aligner (Moonshot Mooncake / SGLang cache preservation).

Epistemic boundary: Prototype router and cache scaffold. Operates locally with zero
external network egress.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from src.sovereign_moat_upgrades import (
    Jurisdiction,
    ModelManifest,
    SovereignMoMRouter,
    SovereignRoutingRequest,
)


@dataclass(frozen=True)
class MoMRoutingDecision:
    """Output routing decision from the Mixture-of-Models dispatcher."""

    assigned_model: str
    role_description: str
    estimated_cost_tier: str
    target_token_budget: int
    requires_escalation: bool


@dataclass(frozen=True)
class ProviderTurnUsage:
    """Observed token usage counters for a single agent interaction turn."""

    turn_index: int
    uncached_input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


class MixtureOfModelsSemanticRouter:
    """
    Signal-driven decision routing framework for Mixture-of-Models (MoM) development.
    Routes tasks dynamically across Flash, Argon, and Opus based on context size, risk tier,
    and oracle feedback loops to achieve calibrated accuracy at bounded cost.
    """

    FLASH_RATE = 0.05 / 1_000_000.0
    ARGON_RATE = 2.00 / 1_000_000.0
    OPUS_RATE = 4.00 / 1_000_000.0

    @classmethod
    def route_request(
        cls,
        repo_tokens: int,
        task_risk: str,
        oracle_failed: bool = False,
        has_syntax_errors: bool = False,
    ) -> MoMRoutingDecision:
        """
        Routes an incoming engineering task based on objective AST and repo metrics.
        """
        # Rule 1: Surgical escalation on deterministic oracle failure or high risk
        if oracle_failed or task_risk == "high":
            return MoMRoutingDecision(
                assigned_model="claude-opus-5.5-medium",
                role_description="The Surgeon: High-precision AST repair and complex multi-file adjudication.",
                estimated_cost_tier="Premium ($4.00/1M in)",
                target_token_budget=4000,
                requires_escalation=True,
            )

        # Rule 2: Micro-cost triage for syntax checks or linting via Flash / local reflex
        if has_syntax_errors or repo_tokens < 5000:
            return MoMRoutingDecision(
                assigned_model="gemini-flash-reflex",
                role_description="The Spinal Reflex: Micro-syntax fixes and RTK terminal noise compression.",
                estimated_cost_tier="Micro ($0.05/1M in)",
                target_token_budget=1000,
                requires_escalation=False,
            )

        # Rule 3: Massive repository context ingestion via Gemini 4 Argon Librarian
        if repo_tokens >= 50000:
            return MoMRoutingDecision(
                assigned_model="gemini-4-argon-high-thinking",
                role_description="The Librarian: Large-scale 1M+ context repository ingestion and import closure mapping.",
                estimated_cost_tier="Efficient ($2.00/1M in)",
                target_token_budget=20000,
                requires_escalation=False,
            )

        # Default balanced tier
        return MoMRoutingDecision(
            assigned_model="gemini-4-argon-standard",
            role_description="The Standard Worker: Balanced feature implementation and unit test generation.",
            estimated_cost_tier="Balanced ($2.00/1M in)",
            target_token_budget=8000,
            requires_escalation=False,
        )

    @classmethod
    def dispatch(
        cls,
        repo_tokens: int,
        task_risk: str,
        oracle_failed: bool = False,
        has_syntax_errors: bool = False,
    ) -> MoMRoutingDecision:
        """Alias for route_request."""
        return cls.route_request(
            repo_tokens=repo_tokens,
            task_risk=task_risk,
            oracle_failed=oracle_failed,
            has_syntax_errors=has_syntax_errors,
        )

    @classmethod
    def route_sovereign_request(
        cls,
        request: SovereignRoutingRequest,
        candidate_model: ModelManifest,
        repo_tokens: int,
        task_risk: str = "medium",
        oracle_failed: bool = False,
        has_syntax_errors: bool = False,
    ) -> Tuple[MoMRoutingDecision, str]:
        """
        Unified sovereign routing gate:
        1. Enforces geopolitical export control boundaries via SovereignMoMRouter.
        2. Routes to appropriate model tier via MoMRoutingDecision.
        """
        sovereign_receipt = SovereignMoMRouter.dispatch_sovereign_route(
            request, candidate_model
        )
        decision = cls.route_request(
            repo_tokens=repo_tokens,
            task_risk=task_risk,
            oracle_failed=oracle_failed,
            has_syntax_errors=has_syntax_errors,
        )
        return decision, sovereign_receipt


class HarnessMMGuardedDecisionCache:
    """
    Caches oracle-verified diffs behind a 3-part state guard.
    Replays verified patches in O(1) at 0 LLM tokens when intent, AST root, and contract match.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, str] = {}

    @staticmethod
    def _key(intent_hash: str, merkle_root: str, contract_digest: str) -> str:
        raw = f"{intent_hash}:{merkle_root}:{contract_digest}"
        return f"harness_mm:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    def get_cached_diff(
        self, intent_hash: str, merkle_root: str, contract_digest: str
    ) -> Optional[str]:
        return self._cache.get(self._key(intent_hash, merkle_root, contract_digest))

    def store_verified_diff(
        self, intent_hash: str, merkle_root: str, contract_digest: str, diff: str
    ) -> None:
        self._cache[self._key(intent_hash, merkle_root, contract_digest)] = diff

    def size(self) -> int:
        return len(self._cache)


class ProductionTokenomicsMonitor:
    """
    Tracks real provider token usage counters and halts on prefix cache wipeouts.
    """

    def __init__(self, expected_prefix_tokens: int) -> None:
        self.expected_prefix_tokens = expected_prefix_tokens

    def audit_turn(self, turn: ProviderTurnUsage) -> Tuple[bool, str]:
        # Turn 0 initializes the prefix cache.
        # If Turn >= 1 experiences cache creation of half or more of expected prefix tokens,
        # a prefix cache wipeout has occurred (e.g., dynamic timestamp in system prompt).
        if turn.turn_index >= 1 and turn.cache_creation_input_tokens >= (
            self.expected_prefix_tokens // 2
        ):
            return False, "HALT_MIDNIGHT_PREFIX_CACHE_WIPEOUT"
        return True, "OK_CACHE_HEALTHY"


class RadixKVBlockAligner:
    """
    Computes 64-token GPU block alignment padding (Mooncake / SGLang discrete KV allocation).
    """

    BLOCK_SIZE: int = 64

    @classmethod
    def compute_padding_tokens(cls, token_count: int) -> int:
        remainder = token_count % cls.BLOCK_SIZE
        if remainder == 0:
            return 0
        return cls.BLOCK_SIZE - remainder

    @classmethod
    def align_token_count(cls, token_count: int) -> int:
        return token_count + cls.compute_padding_tokens(token_count)
