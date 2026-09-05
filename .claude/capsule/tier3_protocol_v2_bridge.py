"""
CAPSULE Tier 3 Protocol v2 Bridge — Sovereign Inference with API Fallback.

Implements the Bridge layer for Protocol v2, orchestrating:
- LocalInferenceEngine: deterministic local inference (Tier 2 cache, temp=0.0)
- ExternalAPIFallback: Claude API as backup when local fails
- BridgeProtocol: request routing (local first → fallback → rule-based default)
- CostMetrics: track local vs external spend, optimize for 90%+ local preference

Architecture:
  Request → BridgeProtocol.route() → LocalInferenceEngine (try local)
                                   → ExternalAPIFallback (if local fails)
                                   → RuleBasedDefault (if both fail)
                                   → CostMetrics (track all paths)

Cost Target: 90%+ requests via local inference, external < 10% of total cost.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Import Tier 2 cache
from capsule.tier2_deterministic_llm import CapsuleLLMCache

# Anthropic SDK for fallback API calls
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


@dataclass
class LocalStats:
    """Statistics for local inference engine."""
    calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class ExternalStats:
    """Statistics for external API fallback."""
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class RoutingStats:
    """Statistics for bridge routing decisions."""
    local_routed: int = 0
    fallback_routed: int = 0
    default_routed: int = 0


class LocalInferenceEngine:
    """
    Local deterministic inference engine using Tier 2 cache.

    All inference uses temperature=0.0 for determinism.
    Delegates to CapsuleLLMCache from Tier 2.
    """

    COST_PER_INPUT_TOKEN = 0.0001  # Haiku pricing

    def __init__(self, cache_dir: str = ".claude/llm_cache"):
        """
        Initialize local inference engine.

        Args:
            cache_dir: Directory for caching LLM responses
        """
        self.cache_dir = Path(cache_dir)
        self.cache = CapsuleLLMCache(cache_dir=str(cache_dir))
        self.stats = LocalStats()

    def query(
        self,
        prompt: str,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Query local inference engine with deterministic caching.

        Temperature parameter is ignored; always uses 0.0.

        Args:
            prompt: Input prompt
            temperature: Ignored (always 0.0 for determinism)

        Returns:
            Schema-compliant response dict
        """
        try:
            # Call Tier 2 cache with temperature=0.0
            response = self.cache.query(prompt, temperature=0.0)

            # Update statistics
            self.stats.calls += 1
            if response.get("status") == "success":
                tokens = response.get("tokens_used", 0)
                self.stats.total_tokens += tokens
                self.stats.total_cost += tokens * self.COST_PER_INPUT_TOKEN

            return response

        except Exception as exc:
            # Local inference failed
            self.stats.calls += 1
            self.stats.errors += 1
            logger.warning(f"Local inference failed: {exc}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for local inference."""
        return {
            "calls": self.stats.calls,
            "errors": self.stats.errors,
            "total_tokens": self.stats.total_tokens,
            "total_cost": self.stats.total_cost
        }


class ExternalAPIFallback:
    """
    External Claude API fallback when local inference fails.

    Uses Anthropic SDK with temperature=0.0 for determinism.
    Wraps responses in schema-compliant format.
    """

    COST_PER_INPUT_TOKEN = 0.0001  # Haiku pricing

    def __init__(self):
        """
        Initialize external API fallback.

        Requires ANTHROPIC_API_KEY environment variable.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.api_key = api_key
        self.client = Anthropic(api_key=api_key) if Anthropic else None
        self.stats = ExternalStats()

    def call_external(self, prompt: str) -> Dict[str, Any]:
        """
        Call external Claude API as fallback.

        Args:
            prompt: Input prompt

        Returns:
            Schema-compliant response dict

        Raises:
            Exception: If API call fails or no client configured
        """
        if not self.client:
            raise RuntimeError(
                "Anthropic SDK not installed. "
                "Install with: pip install anthropic"
            )

        try:
            # Call Claude API with temperature=0.0
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1024,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract response text
            response_text = response.content[0].text if response.content else ""
            tokens_used = response.usage.input_tokens

            # Update statistics
            self.stats.calls += 1
            self.stats.successes += 1
            self.stats.total_tokens += tokens_used
            self.stats.total_cost += tokens_used * self.COST_PER_INPUT_TOKEN

            # Return schema-compliant response
            return {
                "status": "success",
                "content": response_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "claude-api-fallback",
                "tokens_used": tokens_used
            }

        except Exception as exc:
            # External API failed
            self.stats.calls += 1
            self.stats.failures += 1
            logger.warning(f"External API call failed: {exc}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for external API."""
        return {
            "calls": self.stats.calls,
            "successes": self.stats.successes,
            "failures": self.stats.failures,
            "total_tokens": self.stats.total_tokens,
            "total_cost": self.stats.total_cost
        }


class RuleBasedDefault:
    """Rule-based fallback when both local and external fail."""

    @staticmethod
    def generate_default_response(prompt: str) -> Dict[str, Any]:
        """
        Generate rule-based default response.

        Args:
            prompt: Original prompt (unused in current implementation)

        Returns:
            Schema-compliant error response
        """
        return {
            "status": "error",
            "content": "Both local and external inference unavailable. System in degraded mode.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "rule-default",
            "tokens_used": 0
        }


class BridgeProtocol:
    """
    Protocol v2 Bridge — request routing with three-tier fallback.

    Routing order: Local → External API → Rule-based Default
    All paths tracked in CostMetrics for optimization.
    """

    def __init__(self, cache_dir: str = ".claude/llm_cache"):
        """
        Initialize bridge protocol.

        Args:
            cache_dir: Directory for caching (passed to LocalInferenceEngine)
        """
        self.cache_dir = Path(cache_dir)
        self.local_engine = LocalInferenceEngine(cache_dir=cache_dir)
        self.routing_stats = RoutingStats()
        self.cost_metrics = CostMetrics()

        # Try to initialize external API (may fail if no API key)
        try:
            self.external_fallback = ExternalAPIFallback()
        except ValueError:
            logger.warning("ANTHROPIC_API_KEY not set; external fallback disabled")
            self.external_fallback = None

    def route(self, prompt: str) -> Dict[str, Any]:
        """
        Route request through bridge protocol.

        Workflow:
        1. Try local inference (Tier 2 cache)
        2. If local fails, try external API (Fallback)
        3. If both fail, return rule-based default

        Args:
            prompt: Input prompt

        Returns:
            Schema-compliant response from one of the routing paths
        """
        # Attempt local inference first
        try:
            response = self.local_engine.query(prompt)

            # Check if response indicates success
            if response.get("status") == "success":
                self.routing_stats.local_routed += 1
                tokens = response.get("tokens_used", 0)
                self.cost_metrics.record_local_call(
                    cost=tokens * LocalInferenceEngine.COST_PER_INPUT_TOKEN,
                    tokens=tokens
                )
                return response

        except Exception as exc:
            logger.warning(f"Local inference failed: {exc}")

        # Local failed or returned error status; try external fallback
        if self.external_fallback:
            try:
                response = self.external_fallback.call_external(prompt)
                self.routing_stats.fallback_routed += 1
                tokens = response.get("tokens_used", 0)
                self.cost_metrics.record_external_call(
                    cost=tokens * ExternalAPIFallback.COST_PER_INPUT_TOKEN,
                    tokens=tokens
                )
                return response

            except Exception as exc:
                logger.warning(f"External fallback failed: {exc}")

        # Both local and external failed; use rule-based default
        self.routing_stats.default_routed += 1
        response = RuleBasedDefault.generate_default_response(prompt)
        return response

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        total_routed = (
            self.routing_stats.local_routed +
            self.routing_stats.fallback_routed +
            self.routing_stats.default_routed
        )

        return {
            "local_routed": self.routing_stats.local_routed,
            "fallback_routed": self.routing_stats.fallback_routed,
            "default_routed": self.routing_stats.default_routed,
            "total_routed": total_routed
        }

    def get_cost_report(self) -> Dict[str, Any]:
        """Get cost metrics report."""
        metrics_report = self.cost_metrics.get_report()
        routing_stats = self.get_routing_stats()

        return {
            "routing": routing_stats,
            "costs": metrics_report,
            "local_engine_stats": self.local_engine.get_stats(),
            "external_fallback_stats": (
                self.external_fallback.get_stats()
                if self.external_fallback
                else {"calls": 0, "successes": 0, "failures": 0, "total_cost": 0.0}
            )
        }


class CostMetrics:
    """
    Cost tracking for local vs external inference.

    Tracks:
    - Local calls: count, tokens, cost
    - External calls: count, tokens, cost
    - Preference ratio: local_calls / total_calls (target >= 0.90)
    - Cost ratio: external_cost / total_cost (target < 0.10)
    """

    def __init__(self):
        """Initialize cost metrics tracker."""
        self.local_calls = 0
        self.local_tokens = 0
        self.local_cost = 0.0

        self.external_calls = 0
        self.external_tokens = 0
        self.external_cost = 0.0

    def record_local_call(self, cost: float, tokens: int) -> None:
        """
        Record a local inference call.

        Args:
            cost: Cost in USD
            tokens: Input tokens used
        """
        self.local_calls += 1
        self.local_tokens += tokens
        self.local_cost += cost

    def record_external_call(self, cost: float, tokens: int) -> None:
        """
        Record an external API call.

        Args:
            cost: Cost in USD
            tokens: Input tokens used
        """
        self.external_calls += 1
        self.external_tokens += tokens
        self.external_cost += cost

    def get_report(self) -> Dict[str, Any]:
        """
        Generate cost metrics report.

        Returns:
            Dict with local/external calls, costs, and preference ratios
        """
        total_calls = self.local_calls + self.external_calls
        total_cost = self.local_cost + self.external_cost

        # Calculate preference ratio (local calls / total calls)
        preference_ratio = 0.0
        if total_calls > 0:
            preference_ratio = self.local_calls / total_calls

        # Calculate cost ratio (external cost / total cost)
        cost_ratio = 0.0
        if total_cost > 0:
            cost_ratio = self.external_cost / total_cost

        return {
            "local_calls": self.local_calls,
            "local_tokens": self.local_tokens,
            "local_cost": self.local_cost,
            "external_calls": self.external_calls,
            "external_tokens": self.external_tokens,
            "external_cost": self.external_cost,
            "total_calls": total_calls,
            "total_tokens": self.local_tokens + self.external_tokens,
            "total_cost": total_cost,
            "preference_ratio": preference_ratio,
            "cost_ratio": cost_ratio,
            "meets_preference_target": preference_ratio >= 0.90,
            "meets_cost_target": cost_ratio < 0.10
        }
