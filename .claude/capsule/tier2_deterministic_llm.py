"""
CAPSULE Tier 2 Deterministic LLM Caching Layer.

Implements deterministic LLM response caching with:
- SHA256-based prompt hashing for cache keys
- Cache hit/miss tracking and cost accounting
- Schema validation for LLM responses
- Fallback mechanism on LLM failure
- Temperature=0.0 enforcement for determinism
- Cost tracking and reporting (cache vs LLM)
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def call_llm(prompt: str, temperature: float = 0.0) -> Dict[str, Any]:
    """
    Call the LLM with deterministic parameters.

    This is a stub that can be mocked in tests or replaced with
    actual LLM client implementation (e.g., Anthropic SDK).

    Args:
        prompt: Input prompt
        temperature: Sampling temperature (should always be 0.0)

    Returns:
        LLM response dict with schema fields
    """
    # Stub implementation - will be replaced by actual LLM client
    raise NotImplementedError("LLM client not configured")


class CapsuleLLMCache:
    """
    Deterministic LLM response cache with fallback support.

    Features:
    - SHA256 prompt hashing for deterministic cache keys
    - Cache hit/miss tracking
    - LLM response schema validation
    - Rule-based fallback on LLM failure
    - Temperature=0.0 enforcement
    - Cost tracking and reporting
    """

    # Cost constants (USD)
    COST_PER_INPUT_TOKEN = 0.0001  # Haiku pricing
    COST_PER_CACHE_HIT = 0.00001   # Fixed cost per cache hit

    # Required schema fields and types
    REQUIRED_SCHEMA = {
        "status": str,
        "content": str,
        "timestamp": str,
        "model": str,
        "tokens_used": int
    }

    # Valid status values
    VALID_STATUS_VALUES = {"success", "error"}

    def __init__(self, cache_dir: str = ".claude/llm_cache"):
        """
        Initialize deterministic LLM cache.

        Args:
            cache_dir: Directory for storing cached responses
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Counters for metrics
        self._call_count = 0  # Total call count (for attribute checking)
        self._llm_call_count = 0
        self._cache_hit_count = 0
        self._fallback_count = 0

        # Cost tracking
        self._total_tokens_used = 0
        self._total_cache_hits = 0

    def _hash_prompt(self, prompt: str) -> str:
        """
        Generate deterministic SHA256 hash for prompt.

        Args:
            prompt: Input prompt string

        Returns:
            64-character SHA256 hex digest
        """
        return hashlib.sha256(prompt.encode()).hexdigest()

    def _get_cache_path(self, prompt_hash: str) -> Path:
        """
        Get cache file path for prompt hash.

        Args:
            prompt_hash: Hashed prompt

        Returns:
            Path to cache JSON file
        """
        return self.cache_dir / f"{prompt_hash}.json"

    def _validate_schema(self, response: Dict[str, Any]) -> bool:
        """
        Validate LLM response against expected schema.

        Args:
            response: Response dict to validate

        Returns:
            True if valid, raises ValueError otherwise

        Raises:
            ValueError: If schema validation fails
        """
        # Check all required fields present
        for field, expected_type in self.REQUIRED_SCHEMA.items():
            if field not in response:
                raise ValueError(f"Response missing required field: {field}")

            # Check field type
            value = response[field]
            if not isinstance(value, expected_type):
                raise ValueError(
                    f"Response field '{field}' has incorrect type: "
                    f"expected {expected_type.__name__}, got {type(value).__name__}"
                )

        # Validate status enum
        if response["status"] not in self.VALID_STATUS_VALUES:
            raise ValueError(
                f"Response has invalid status value: {response['status']}. "
                f"Must be one of {self.VALID_STATUS_VALUES}"
            )

        return True

    def _rule_based_fallback(self, prompt: str) -> Dict[str, Any]:
        """
        Generate rule-based fallback response when LLM fails.

        Args:
            prompt: Original prompt (used for regex-based extraction)

        Returns:
            Fallback response dict with schema-compliant fields
        """
        # Extract any JSON-like structure or fallback to generic response
        fallback_content = "Fallback response (LLM unavailable)"

        # Try to extract useful content from prompt for better fallback
        json_match = re.search(r'\{[^}]*\}', prompt)
        if json_match:
            try:
                extracted = json.loads(json_match.group())
                if extracted:
                    fallback_content = f"Fallback: {json.dumps(extracted)}"
            except (json.JSONDecodeError, ValueError):
                pass

        # Return schema-compliant error response
        return {
            "status": "error",
            "content": fallback_content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "fallback-rule-engine",
            "tokens_used": 0
        }

    def query(self, prompt: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        """
        Query LLM with caching, validation, and fallback.

        Workflow:
        1. Hash prompt for cache key
        2. Check cache - if hit, return cached result
        3. Call LLM with temperature=0.0
        4. Validate response schema
        5. Cache successful response
        6. If LLM fails, return fallback (not cached)

        Args:
            prompt: Input prompt
            temperature: Ignored (always uses 0.0 for determinism)

        Returns:
            LLM response dict or fallback dict on failure
        """
        # Hash prompt for cache key
        prompt_hash = self._hash_prompt(prompt)
        cache_path = self._get_cache_path(prompt_hash)

        # Check cache first
        if cache_path.exists():
            cached_response = json.loads(cache_path.read_text())
            self._cache_hit_count += 1
            self._total_cache_hits += 1
            return cached_response

        # Cache miss - try LLM call
        self._llm_call_count += 1

        try:
            # Call LLM with temperature=0.0 (enforce determinism)
            response = call_llm(prompt, temperature=0.0)

            # Validate schema
            self._validate_schema(response)

            # Cache successful response
            cache_path.write_text(json.dumps(response, indent=2))

            # Track tokens for cost calculation
            self._total_tokens_used += response.get("tokens_used", 0)

            return response

        except Exception as exc:
            # LLM failed - return fallback (not cached)
            self._fallback_count += 1
            logger.warning(f"LLM call failed: {exc}. Using fallback.")
            return self._rule_based_fallback(prompt)

    def get_cost_report(self) -> Dict[str, Any]:
        """
        Generate cost report comparing cache hits vs LLM calls.

        Returns:
            Dict with:
            - llm_calls: Number of LLM API calls
            - cache_hits: Number of cache hits
            - llm_cost: Cost of LLM calls (tokens * COST_PER_INPUT_TOKEN)
            - cache_hit_cost: Cost of cache hits (hits * COST_PER_CACHE_HIT)
            - ratio: cache_hit_cost / llm_cost (< 0.01 = good)
        """
        llm_cost = self._total_tokens_used * self.COST_PER_INPUT_TOKEN
        cache_hit_cost = self._total_cache_hits * self.COST_PER_CACHE_HIT

        # Calculate ratio safely
        ratio = 0.0
        if llm_cost > 0:
            ratio = cache_hit_cost / llm_cost

        return {
            "llm_calls": self._llm_call_count,
            "cache_hits": self._cache_hit_count,
            "fallback_count": self._fallback_count,
            "llm_cost": llm_cost,
            "cache_hit_cost": cache_hit_cost,
            "ratio": ratio
        }
