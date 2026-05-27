"""
CAPSULE Tier 2 Deterministic LLM Abstraction Test Suite.

This module contains comprehensive tests for CAPSULE's deterministic LLM caching layer:
- Prompt cache initialization and directory structure
- Deterministic hash generation (SHA256)
- Cache hit/miss handling
- LLM response schema validation
- Fallback execution on LLM failure
- Temperature=0.0 determinism across multiple calls
- Cost reduction measurability (cache hits vs LLM calls)

All tests intentionally FAIL initially (TDD red phase).
Implementation will be added to make tests pass (TDD green phase).

Test Status: 0/12 PASS (all expected to fail)
"""

import pytest
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


class TestPromptCacheInitialization:
    """Test cache directory initialization and structure."""

    def test_prompt_cache_initialization(self, temp_cache_dir: Path):
        """
        Test: Prompt cache directory is created on first run, empty initially.

        Specification:
        - Cache directory is created at DATA_DIR/llm_cache/
        - Directory is empty on first initialization
        - Subsequent accesses use existing directory

        Expected: Directory exists and is empty on first run
        Current: FAIL (requires CapsuleLLMCache initialization)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects cache initialization
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)

        # Directory should exist
        assert cache.cache_dir.exists(), \
            f"Cache directory should exist at {cache.cache_dir}"

        # Directory should be empty initially
        cache_files = list(cache.cache_dir.glob("*.json"))
        assert len(cache_files) == 0, \
            f"Cache directory should be empty initially, found {len(cache_files)} files"

        # Cache object should have proper attributes
        assert hasattr(cache, 'cache_dir'), "Cache should have cache_dir attribute"
        assert hasattr(cache, '_call_count'), "Cache should track call statistics"


class TestPromptHashDeterminism:
    """Test deterministic hash generation for prompts."""

    def test_prompt_hash_deterministic(self, temp_cache_dir: Path):
        """
        Test: Same prompt always produces identical SHA256 hash.

        Specification:
        - Hash algorithm: SHA256(prompt.encode())
        - Hash format: hexadecimal string, 64 characters
        - Same prompt in 100 iterations produces 100 identical hashes

        Expected: All hashes match for identical prompts
        Current: FAIL (requires deterministic hash implementation)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects deterministic hashing
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)

        prompt = "What is the capital of France?"
        hashes = []

        # Hash the same prompt 100 times
        for _ in range(100):
            hash_result = cache._hash_prompt(prompt)
            hashes.append(hash_result)

        # All hashes should be identical
        assert len(set(hashes)) == 1, \
            f"Expected 1 unique hash, got {len(set(hashes))}"

        # Hash should match SHA256(prompt.encode())
        expected_hash = hashlib.sha256(prompt.encode()).hexdigest()
        assert hashes[0] == expected_hash, \
            f"Hash mismatch: got {hashes[0]}, expected {expected_hash}"

        # Hash should be 64 characters (SHA256 hex)
        assert len(hashes[0]) == 64, \
            f"SHA256 hex digest should be 64 chars, got {len(hashes[0])}"

    def test_different_prompts_different_hashes(self, temp_cache_dir: Path):
        """
        Test: Different prompts produce different hashes.

        Specification:
        - Hash is collision-resistant (per SHA256)
        - Whitespace differences matter
        - Case sensitivity matters

        Expected: Distinct hashes for distinct prompts
        Current: FAIL (requires correct hash implementation)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects collision-resistant hashing
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)

        prompt1 = "What is the capital of France?"
        prompt2 = "What is the capital of Germany?"
        prompt3 = "what is the capital of france?"  # Different case

        hash1 = cache._hash_prompt(prompt1)
        hash2 = cache._hash_prompt(prompt2)
        hash3 = cache._hash_prompt(prompt3)

        # All hashes should be different
        assert hash1 != hash2, "Different prompts should produce different hashes"
        assert hash1 != hash3, "Case difference should produce different hash"
        assert hash2 != hash3, "All three hashes should be unique"


class TestCacheHitMiss:
    """Test cache hit and miss behavior."""

    def test_cache_hit_returns_cached_result(
        self,
        temp_cache_dir: Path,
        mock_llm_response: Dict[str, Any]
    ):
        """
        Test: Cached response is returned without calling LLM on cache hit.

        Specification:
        - Cache file: DATA_DIR/llm_cache/{prompt_hash}.json
        - Cache hit: LLM is NOT called, cached result returned
        - Call statistics: hit_count incremented, llm_call_count not incremented

        Expected: Cached result returned, LLM not called, stats updated
        Current: FAIL (requires cache hit logic)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects cache hit handling
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)
        prompt = "What is the capital of France?"

        # Prime the cache with a response
        prompt_hash = cache._hash_prompt(prompt)
        cache_file = cache.cache_dir / f"{prompt_hash}.json"
        cache_file.write_text(json.dumps(mock_llm_response))

        # Reset LLM call count
        cache._llm_call_count = 0
        cache._cache_hit_count = 0

        # Attempt to get response (should hit cache)
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            result = cache.query(prompt)

        # Cache hit should return the cached result
        assert result == mock_llm_response, \
            "Should return cached response on hit"

        # LLM should NOT have been called
        mock_llm.assert_not_called(), \
            "LLM should not be called on cache hit"

        # Statistics should reflect cache hit
        assert cache._cache_hit_count == 1, \
            "Cache hit count should be incremented"
        assert cache._llm_call_count == 0, \
            "LLM call count should not be incremented on cache hit"

    def test_cache_miss_calls_llm(
        self,
        temp_cache_dir: Path,
        mock_llm_response: Dict[str, Any]
    ):
        """
        Test: New prompt triggers LLM call, result is cached for next call.

        Specification:
        - Cache miss: LLM is called, response cached
        - Response is saved to DATA_DIR/llm_cache/{prompt_hash}.json
        - Call statistics: llm_call_count incremented, hit_count not incremented

        Expected: LLM called, result cached, stats updated
        Current: FAIL (requires cache miss + LLM call logic)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects cache miss handling and LLM integration
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)
        prompt = "What is the meaning of life?"

        # Ensure cache is empty
        prompt_hash = cache._hash_prompt(prompt)
        cache_file = cache.cache_dir / f"{prompt_hash}.json"
        assert not cache_file.exists(), "Cache should be empty for new prompt"

        # Reset counters
        cache._llm_call_count = 0
        cache._cache_hit_count = 0

        # Mock the LLM call
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            mock_llm.return_value = mock_llm_response

            # Query with new prompt (should trigger LLM)
            result = cache.query(prompt)

        # LLM should have been called
        mock_llm.assert_called_once_with(prompt, temperature=0.0)

        # Result should be the LLM response
        assert result == mock_llm_response, \
            "Should return LLM response on cache miss"

        # Response should be cached
        assert cache_file.exists(), \
            f"Response should be cached at {cache_file}"

        # Cached content should match response
        cached_content = json.loads(cache_file.read_text())
        assert cached_content == mock_llm_response, \
            "Cached response should match LLM response"

        # Statistics should reflect LLM call
        assert cache._llm_call_count == 1, \
            "LLM call count should be incremented"
        assert cache._cache_hit_count == 0, \
            "Cache hit count should not be incremented on miss"


class TestLLMSchemaValidation:
    """Test result validation against expected schema."""

    def test_llm_schema_validation(
        self,
        temp_cache_dir: Path,
        valid_llm_schema: Dict[str, Any]
    ):
        """
        Test: LLM result is validated against expected schema.

        Specification:
        - Schema: {
              "status": "success|error",
              "content": str,
              "timestamp": ISO8601 datetime,
              "model": str,
              "tokens_used": int
          }
        - Validation: All required fields present and correct type
        - Invalid response: Raises ValueError with clear error message

        Expected: Valid schema accepted, invalid schema rejected
        Current: FAIL (requires schema validation logic)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects schema validation
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)

        # Valid schema should pass
        assert cache._validate_schema(valid_llm_schema) is True, \
            "Valid schema should pass validation"

        # Missing 'content' field should fail
        invalid_schema_1 = {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "claude-3-haiku",
            "tokens_used": 150
        }
        with pytest.raises(ValueError, match="missing required field"):
            cache._validate_schema(invalid_schema_1)

        # Wrong type for 'tokens_used' should fail
        invalid_schema_2 = {
            "status": "success",
            "content": "Test response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "claude-3-haiku",
            "tokens_used": "not_an_int"
        }
        with pytest.raises(ValueError, match="incorrect type"):
            cache._validate_schema(invalid_schema_2)

        # Invalid status value should fail
        invalid_schema_3 = {
            "status": "pending",  # Should be "success" or "error"
            "content": "Test response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "claude-3-haiku",
            "tokens_used": 150
        }
        with pytest.raises(ValueError, match="invalid status"):
            cache._validate_schema(invalid_schema_3)


class TestFallbackOnLLMFailure:
    """Test fallback behavior when LLM call fails."""

    def test_fallback_on_llm_failure(self, temp_cache_dir: Path):
        """
        Test: LLM call fails → rule-based fallback executes.

        Specification:
        - Fallback strategy: Regex + keyword matching for schema extraction
        - Fallback result: Synthesized response with status='error', content='<fallback>'
        - Fallback is NOT cached (only successful LLM responses are cached)
        - Call statistics: llm_call_count incremented, fallback_count incremented

        Expected: Fallback executes, no cache write, stats updated
        Current: FAIL (requires fallback implementation)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects fallback handling
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)
        prompt = "What is the capital of France?"

        # Reset counters
        cache._llm_call_count = 0
        cache._fallback_count = 0

        # Mock LLM failure
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM service unavailable")

            # Query should trigger fallback
            result = cache.query(prompt)

        # Result should be fallback response
        assert result is not None, "Fallback should return a response"
        assert result.get("status") == "error", \
            "Fallback response should have status='error'"
        assert isinstance(result.get("content"), str), \
            "Fallback response should have content string"

        # Fallback should NOT be cached
        prompt_hash = cache._hash_prompt(prompt)
        cache_file = cache.cache_dir / f"{prompt_hash}.json"
        assert not cache_file.exists(), \
            "Fallback response should not be cached"

        # Statistics should reflect fallback
        assert cache._llm_call_count == 1, \
            "LLM call count should be incremented even on failure"
        assert cache._fallback_count == 1, \
            "Fallback count should be incremented"

    def test_fallback_schema_compliance(self, temp_cache_dir: Path):
        """
        Test: Fallback response complies with LLM schema.

        Specification:
        - Fallback must have all required fields: status, content, timestamp, model, tokens_used
        - status: "error"
        - content: "Fallback response (LLM unavailable)"
        - model: "fallback-rule-engine"
        - tokens_used: 0 (no LLM tokens consumed)

        Expected: Fallback response is schema-valid
        Current: FAIL (requires correct fallback schema)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects schema-compliant fallback
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)
        prompt = "Test prompt"

        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM failure")
            result = cache.query(prompt)

        # Validate fallback schema
        assert cache._validate_schema(result) is True, \
            "Fallback response should be schema-valid"
        assert result.get("status") == "error"
        assert result.get("model") == "fallback-rule-engine"
        assert result.get("tokens_used") == 0


class TestTemperatureZeroDeterminism:
    """Test determinism with temperature=0.0."""

    def test_temperature_zero_determinism(
        self,
        temp_cache_dir: Path,
        mock_llm_response: Dict[str, Any]
    ):
        """
        Test: Multiple calls with temperature=0.0 return identical results.

        Specification:
        - All LLM calls must use temperature=0.0 (deterministic sampling)
        - Same prompt queried N times produces N identical responses (via cache or LLM determinism)
        - Test: 10 sequential calls with cache cleared between calls

        Expected: All 10 results are identical
        Current: FAIL (requires temperature=0.0 enforcement)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects temperature=0.0 determinism
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)
        prompt = "Determinism test prompt"
        results = []

        # Mock LLM to return same response every time
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            mock_llm.return_value = mock_llm_response

            for i in range(10):
                # Query 10 times
                result = cache.query(prompt)
                results.append(result)

                # Verify temperature parameter is 0.0
                call_args = mock_llm.call_args_list[i]
                assert call_args[1].get('temperature') == 0.0, \
                    f"Call {i} should use temperature=0.0"

        # All results should be identical
        assert all(r == results[0] for r in results), \
            f"All {len(results)} results should be identical with temperature=0.0"

    def test_temperature_zero_enforcement(self, temp_cache_dir: Path):
        """
        Test: LLM is always called with temperature=0.0.

        Specification:
        - CapsuleLLMCache._query_llm() must always pass temperature=0.0
        - No other temperature values are accepted
        - Default temperature must be 0.0

        Expected: All LLM calls use temperature=0.0
        Current: FAIL (requires temperature enforcement)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects temperature=0.0 enforcement
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)

        # Attempt to query with explicit temperature (should be ignored)
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            mock_llm.return_value = {"status": "success", "content": "test"}

            cache.query("test prompt", temperature=0.7)

        # Verify LLM was called with temperature=0.0, not 0.7
        call_kwargs = mock_llm.call_args[1]
        assert call_kwargs.get('temperature') == 0.0, \
            "LLM call should override any temperature parameter with 0.0"


class TestCostReductionMeasurable:
    """Test cost reduction via cache hits."""

    def test_cost_reduction_measurable(
        self,
        temp_cache_dir: Path,
        mock_llm_response: Dict[str, Any]
    ):
        """
        Test: Cache hit cost < 1% of LLM call cost.

        Specification:
        - LLM call cost: ~tokens_used * COST_PER_TOKEN = 150 * $0.0001 = $0.015
        - Cache hit cost: ~$0.00001 (1% threshold)
        - Measurable: cache.get_cost_report() returns { llm_cost, cache_hit_cost, ratio }
        - Ratio calculation: cache_hit_cost / llm_cost < 0.01

        Expected: Cache hit cost is <1% of LLM cost
        Current: FAIL (requires cost tracking)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects cost tracking and reporting
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)

        # Prime cache with 5 LLM calls
        prompt_base = "Test prompt {}"
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            mock_llm.return_value = mock_llm_response

            for i in range(5):
                cache.query(prompt_base.format(i))

        # Reset LLM mock for cache hit phase
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            # Query existing prompts (cache hits)
            for i in range(5):
                cache.query(prompt_base.format(i))

            # LLM should not be called (cache hits)
            assert mock_llm.call_count == 0, \
                "LLM should not be called on cache hits"

        # Get cost report
        cost_report = cache.get_cost_report()

        # Verify report structure
        assert "llm_cost" in cost_report, "Report should have llm_cost"
        assert "cache_hit_cost" in cost_report, "Report should have cache_hit_cost"
        assert "ratio" in cost_report, "Report should have cost ratio"
        assert "llm_calls" in cost_report, "Report should have llm_calls count"
        assert "cache_hits" in cost_report, "Report should have cache_hits count"

        # Verify cost ratio is measurable and below threshold
        assert cost_report["llm_calls"] == 5, "Should have 5 LLM calls"
        assert cost_report["cache_hits"] == 5, "Should have 5 cache hits"

        # Cost ratio should be positive
        assert cost_report["ratio"] >= 0, "Cost ratio should be non-negative"

        # Cache hit cost should be less than 1% of LLM cost
        assert cost_report["ratio"] < 0.01, \
            f"Cache hit cost should be <1% of LLM cost, got {cost_report['ratio']*100:.2f}%"

    def test_cost_tracking_accuracy(
        self,
        temp_cache_dir: Path,
        mock_llm_response: Dict[str, Any]
    ):
        """
        Test: Cost tracking accurately reflects LLM calls and cache hits.

        Specification:
        - Token cost: $0.0001 per input token (Haiku pricing)
        - Cache hit cost: Fixed $0.00001 per hit (1% of avg LLM call)
        - Tracking: Incremental counters for each LLM call and cache hit
        - Report: cache.get_cost_report() returns cumulative costs

        Expected: Costs accurately tracked and reported
        Current: FAIL (requires accurate cost accounting)
        """
        from capsule.tier2_deterministic_llm import CapsuleLLMCache

        # FAIL: Expects cost tracking accuracy
        cache = CapsuleLLMCache(cache_dir=temp_cache_dir)

        # Simulate 3 LLM calls (3 unique prompts)
        mock_response_tokens_100 = mock_llm_response.copy()
        mock_response_tokens_100["tokens_used"] = 100

        mock_response_tokens_150 = mock_llm_response.copy()
        mock_response_tokens_150["tokens_used"] = 150

        mock_response_tokens_200 = mock_llm_response.copy()
        mock_response_tokens_200["tokens_used"] = 200

        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            mock_llm.side_effect = [
                mock_response_tokens_100,
                mock_response_tokens_150,
                mock_response_tokens_200
            ]

            cache.query("Prompt 1")
            cache.query("Prompt 2")
            cache.query("Prompt 3")

        # Now hit cache 7 times with different prompts
        with patch('capsule.tier2_deterministic_llm.call_llm') as mock_llm:
            cache.query("Prompt 1")  # Hit
            cache.query("Prompt 2")  # Hit
            cache.query("Prompt 3")  # Hit
            cache.query("Prompt 1")  # Hit
            cache.query("Prompt 2")  # Hit
            cache.query("Prompt 3")  # Hit
            cache.query("Prompt 1")  # Hit

            # No LLM calls should occur
            assert mock_llm.call_count == 0

        # Get cost report
        cost_report = cache.get_cost_report()

        # Verify counts
        assert cost_report["llm_calls"] == 3, "Should have exactly 3 LLM calls"
        assert cost_report["cache_hits"] == 7, "Should have exactly 7 cache hits"

        # Verify LLM cost reflects token count
        # Cost = (100 + 150 + 200) * 0.0001 = 450 * 0.0001 = 0.045
        expected_llm_cost = 0.045
        assert abs(cost_report["llm_cost"] - expected_llm_cost) < 0.0001, \
            f"LLM cost should be ~{expected_llm_cost}, got {cost_report['llm_cost']}"

        # Verify cache hit cost
        # Cost = 7 * 0.00001 = 0.00007
        expected_cache_cost = 0.00007
        assert abs(cost_report["cache_hit_cost"] - expected_cache_cost) < 0.000001, \
            f"Cache hit cost should be ~{expected_cache_cost}, got {cost_report['cache_hit_cost']}"

        # Verify ratio
        # Ratio = 0.00007 / 0.045 = 0.00155... which is < 0.01 ✓
        expected_ratio = 0.00007 / 0.045
        assert abs(cost_report["ratio"] - expected_ratio) < 0.0001, \
            f"Ratio should be ~{expected_ratio}, got {cost_report['ratio']}"


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_cache_dir() -> Path:
    """Provide a temporary cache directory for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Provide a valid mock LLM response matching the schema."""
    return {
        "status": "success",
        "content": "Paris is the capital of France.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "claude-3-haiku",
        "tokens_used": 150
    }


@pytest.fixture
def valid_llm_schema() -> Dict[str, Any]:
    """Provide a valid LLM response schema for validation tests."""
    return {
        "status": "success",
        "content": "This is a valid response.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "claude-3-haiku",
        "tokens_used": 42
    }
