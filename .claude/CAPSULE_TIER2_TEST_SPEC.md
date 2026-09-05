# CAPSULE Tier 2: Deterministic LLM Abstraction — Test Specification

**Status:** TDD Red Phase — All 8 tests FAIL (0/8 pass)  
**Test File:** `.claude/capsule/tests/test_tier2_deterministic_llm.py`  
**Config File:** `.claude/capsule/tests/conftest.py`  
**Created:** 2026-05-27

---

## 1. Overview

CAPSULE Tier 2 implements deterministic LLM response caching to reduce costs and ensure reproducibility. This test suite validates:

- **Cache Initialization:** Directory structure and state management
- **Deterministic Hashing:** SHA256-based prompt fingerprinting
- **Cache Hit/Miss Logic:** Proper cache bypass and LLM routing
- **Schema Validation:** Response format compliance
- **Fallback Execution:** Graceful degradation on LLM failure
- **Temperature Determinism:** temperature=0.0 enforcement
- **Cost Measurability:** Cache efficiency tracking

---

## 2. Test Suite (8 Tests)

### Test 1: `test_prompt_cache_initialization`
**Class:** `TestPromptCacheInitialization`

**Purpose:** Verify cache directory is created on first run and empty.

**Specification:**
- Cache directory: `DATA_DIR/llm_cache/`
- Initialization: Creates directory if missing
- State: Empty (no `.json` files) on first run
- Idempotent: Subsequent accesses reuse existing directory

**Setup:**
- Provide `temp_cache_dir` fixture (temporary Path)
- Import `CapsuleLLMCache` from `capsule.tier2_deterministic_llm`

**Assertions:**
- `cache.cache_dir.exists()` — directory exists
- `len(list(cache.cache_dir.glob("*.json"))) == 0` — empty on init
- `hasattr(cache, 'cache_dir')` — proper attribute
- `hasattr(cache, '_call_count')` — statistics tracking

**Expected Failure Reason:** `CapsuleLLMCache` class not yet implemented

---

### Test 2: `test_prompt_hash_deterministic`
**Class:** `TestPromptHashDeterminism`

**Purpose:** Same prompt always produces identical SHA256 hash.

**Specification:**
- Algorithm: `SHA256(prompt.encode())`
- Format: Hexadecimal string, 64 characters
- Determinism: 100 iterations of same prompt → 100 identical hashes
- Correctness: Hash matches expected SHA256 output

**Setup:**
- Provide `temp_cache_dir` fixture
- Call `cache._hash_prompt(prompt)` 100 times with identical input

**Assertions:**
- `len(set(hashes)) == 1` — all hashes identical
- `hash == hashlib.sha256(prompt.encode()).hexdigest()` — correct value
- `len(hash) == 64` — valid SHA256 length

**Expected Failure Reason:** `_hash_prompt()` method not implemented

---

### Test 3: `test_different_prompts_different_hashes`
**Class:** `TestPromptHashDeterminism`

**Purpose:** Different prompts produce different hashes (collision resistance).

**Specification:**
- Collision resistance: Per SHA256 guarantee
- Case sensitivity: "Paris" ≠ "paris" (different hashes)
- Whitespace sensitivity: Different spacing → different hash

**Setup:**
- Hash 3 distinct prompts: original, different content, different case

**Assertions:**
- `hash1 != hash2` — different content
- `hash1 != hash3` — different case
- `hash2 != hash3` — all unique

**Expected Failure Reason:** Hashing not yet implemented

---

### Test 4: `test_cache_hit_returns_cached_result`
**Class:** `TestCacheHitMiss`

**Purpose:** Cached response returned without calling LLM on cache hit.

**Specification:**
- Cache File: `DATA_DIR/llm_cache/{prompt_hash}.json`
- Cache Hit: LLM not called, cached result returned
- Statistics: `_cache_hit_count` incremented, `_llm_call_count` unchanged
- Response: Exact match with cached data

**Setup:**
- Create cache file by writing JSON to `{prompt_hash}.json`
- Mock `capsule.tier2_deterministic_llm.call_llm` (should not be called)
- Reset counters: `_llm_call_count = 0`, `_cache_hit_count = 0`

**Assertions:**
- `result == mock_llm_response` — returns cached data
- `mock_llm.assert_not_called()` — LLM not invoked
- `cache._cache_hit_count == 1` — hit recorded
- `cache._llm_call_count == 0` — call count unchanged

**Expected Failure Reason:** Cache hit logic not implemented

---

### Test 5: `test_cache_miss_calls_llm`
**Class:** `TestCacheHitMiss`

**Purpose:** New prompt triggers LLM call, result cached.

**Specification:**
- Cache Miss: LLM is called (not cached)
- Caching: Response saved to `{prompt_hash}.json`
- Statistics: `_llm_call_count` incremented, `_cache_hit_count` unchanged
- Temperature: LLM called with `temperature=0.0`

**Setup:**
- Ensure cache file does NOT exist for new prompt
- Mock `call_llm` to return `mock_llm_response`
- Reset counters

**Assertions:**
- `mock_llm.assert_called_once_with(prompt, temperature=0.0)` — correct call
- `result == mock_llm_response` — returns LLM response
- `cache_file.exists()` — response cached
- `json.loads(cache_file.read_text()) == mock_llm_response` — correct content
- `cache._llm_call_count == 1` — call recorded
- `cache._cache_hit_count == 0` — no hit

**Expected Failure Reason:** Cache miss and LLM integration not implemented

---

### Test 6: `test_llm_schema_validation`
**Class:** `TestLLMSchemaValidation`

**Purpose:** LLM result validated against expected schema.

**Specification:**
```json
{
  "status": "success" | "error",
  "content": string,
  "timestamp": ISO8601 datetime,
  "model": string,
  "tokens_used": non-negative integer
}
```

**Validation Rules:**
- All fields required
- Types strict (no coercion)
- Status only: "success" or "error"
- tokens_used must be integer ≥ 0

**Setup:**
- Use `valid_llm_schema` fixture
- Test 3 invalid cases: missing field, wrong type, invalid status

**Assertions:**
- `cache._validate_schema(valid_schema)` returns `True`
- Missing field raises `ValueError` with "missing required field"
- Wrong type raises `ValueError` with "incorrect type"
- Invalid status raises `ValueError` with "invalid status"

**Expected Failure Reason:** Schema validation not implemented

---

### Test 7: `test_fallback_on_llm_failure`
**Class:** `TestFallbackOnLLMFailure`

**Purpose:** LLM failure triggers rule-based fallback.

**Specification:**
- Trigger: `call_llm()` raises exception
- Strategy: Regex + keyword matching (simple rule engine)
- Response: Synthesized with `status='error'`, fallback content
- Caching: Fallback NOT cached (only successful responses)
- Statistics: `_llm_call_count` incremented, `_fallback_count` incremented

**Fallback Response Format:**
```json
{
  "status": "error",
  "content": "Fallback response (LLM unavailable)",
  "timestamp": ISO8601 datetime,
  "model": "fallback-rule-engine",
  "tokens_used": 0
}
```

**Setup:**
- Mock `call_llm` to raise `Exception("LLM service unavailable")`
- Reset counters

**Assertions:**
- `result` is not None
- `result['status'] == 'error'` — error status
- `isinstance(result['content'], str)` — has content
- Cache file NOT created for fallback
- `cache._llm_call_count == 1` — call attempt recorded
- `cache._fallback_count == 1` — fallback triggered

**Expected Failure Reason:** Fallback mechanism not implemented

---

### Test 8: `test_fallback_schema_compliance`
**Class:** `TestFallbackOnLLMFailure`

**Purpose:** Fallback response complies with schema.

**Specification:**
- Fallback must pass `_validate_schema()` check
- Fields: status="error", model="fallback-rule-engine", tokens_used=0
- Content: Descriptive error message
- Timestamp: Valid ISO8601

**Setup:**
- Mock LLM failure
- Call `query()` and validate result

**Assertions:**
- `cache._validate_schema(result) == True`
- `result['status'] == 'error'`
- `result['model'] == 'fallback-rule-engine'`
- `result['tokens_used'] == 0`

**Expected Failure Reason:** Fallback implementation incomplete

---

### Test 9: `test_temperature_zero_determinism`
**Class:** `TestTemperatureZeroDeterminism`

**Purpose:** temperature=0.0 enforcement ensures identical results across calls.

**Specification:**
- All LLM calls use `temperature=0.0` (deterministic sampling)
- N calls with same prompt → N identical responses (cache + determinism)
- Parameter override: Caller can pass `temperature=0.7` but it's ignored/overridden
- Test: 10 sequential calls verify all results identical

**Setup:**
- Mock `call_llm` to return `mock_llm_response`
- Call `query(prompt)` 10 times
- Inspect `mock_llm.call_args_list` to verify parameter

**Assertions:**
- `call_args[1].get('temperature') == 0.0` for all calls
- `all(r == results[0] for r in results)` — all results identical
- Results should match even if cache is cleared (LLM determinism)

**Expected Failure Reason:** Temperature enforcement not implemented

---

### Test 10: `test_temperature_zero_enforcement`
**Class:** `TestTemperatureZeroDeterminism`

**Purpose:** Verify temperature=0.0 cannot be overridden.

**Specification:**
- Default temperature: 0.0
- Override attempt: `query(prompt, temperature=0.7)` → still uses 0.0
- LLM call kwargs: `call_llm(..., temperature=0.0)` always

**Setup:**
- Call `query("test prompt", temperature=0.7)` (explicit wrong temp)
- Mock `call_llm`

**Assertions:**
- `mock_llm.call_args[1].get('temperature') == 0.0`
- Passed temperature is overridden to 0.0

**Expected Failure Reason:** Temperature enforcement not implemented

---

### Test 11: `test_cost_reduction_measurable`
**Class:** `TestCostReductionMeasurable`

**Purpose:** Cache hit cost < 1% of LLM call cost.

**Specification:**
- LLM Cost: `tokens_used * $0.0001` (Haiku pricing)
  - Example: 150 tokens × $0.0001 = $0.015 per call
- Cache Hit Cost: Fixed `$0.00001` per hit (1% of avg LLM call)
- Measurability: `cache.get_cost_report()` returns structured data

**Cost Report Schema:**
```python
{
  "llm_calls": int,          # Number of LLM calls made
  "cache_hits": int,         # Number of cache hits
  "llm_cost": float,         # Total LLM cost in $
  "cache_hit_cost": float,   # Total cache hit cost in $
  "ratio": float             # cache_hit_cost / llm_cost (should be < 0.01)
}
```

**Setup:**
- Call LLM 5 times (5 unique prompts) → cache writes
- Query same 5 prompts again → 5 cache hits (no LLM calls)
- Call `get_cost_report()`

**Assertions:**
- `"llm_cost" in report`
- `"cache_hit_cost" in report`
- `"ratio" in report`
- `report["llm_calls"] == 5`
- `report["cache_hits"] == 5`
- `report["ratio"] < 0.01` — cache hit cost is <1% of LLM cost

**Expected Failure Reason:** Cost tracking not implemented

---

### Test 12: `test_cost_tracking_accuracy`
**Class:** `TestCostReductionMeasurable`

**Purpose:** Costs accurately tracked and reported.

**Specification:**
- Token cost: `tokens_used * $0.0001`
- Cache hit cost: `hit_count * $0.00001`
- Accuracy: Costs match expected calculations within 0.0001 tolerance

**Scenario:**
1. Call LLM 3 times with token counts: 100, 150, 200
2. Query cache 7 times (mix of the 3 prompts)
3. Verify costs: 
   - LLM: (100+150+200) × 0.0001 = $0.045
   - Cache: 7 × 0.00001 = $0.00007
   - Ratio: 0.00007 / 0.045 ≈ 0.00155 (< 0.01 ✓)

**Setup:**
- Mock LLM with different token counts per response
- Make 3 LLM calls, then 7 cache hits
- Call `get_cost_report()`

**Assertions:**
- `report["llm_calls"] == 3`
- `report["cache_hits"] == 7`
- `abs(report["llm_cost"] - 0.045) < 0.0001` — accuracy
- `abs(report["cache_hit_cost"] - 0.00007) < 0.000001` — accuracy
- `abs(report["ratio"] - 0.00155) < 0.0001` — ratio accuracy

**Expected Failure Reason:** Cost tracking not implemented

---

## 3. Fixtures

### `temp_cache_dir` (Path)
Provides a temporary directory for cache files.
```python
@pytest.fixture
def temp_cache_dir() -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
```

### `mock_llm_response` (Dict[str, Any])
Valid LLM response matching schema.
```python
{
  "status": "success",
  "content": "Paris is the capital of France.",
  "timestamp": "2026-05-27T...",
  "model": "claude-3-haiku",
  "tokens_used": 150
}
```

### `valid_llm_schema` (Dict[str, Any])
Valid schema for validation tests.

---

## 4. Expected Implementation

The tests define the contract for `CapsuleLLMCache` class:

**Location:** `capsule/tier2_deterministic_llm.py` (to be created)

**Public Interface:**
```python
class CapsuleLLMCache:
    def __init__(self, cache_dir: Path):
        """Initialize cache with directory."""
        pass

    def query(self, prompt: str, temperature: float = 0.0) -> Dict[str, Any]:
        """Query with caching. Returns schema-valid response."""
        pass

    def get_cost_report(self) -> Dict[str, Any]:
        """Return cost analysis."""
        pass

    # Private methods
    def _hash_prompt(self, prompt: str) -> str:
        """SHA256 hash of prompt."""
        pass

    def _validate_schema(self, response: Dict) -> bool:
        """Validate response against schema."""
        pass

    def _fallback(self, prompt: str) -> Dict[str, Any]:
        """Generate fallback response."""
        pass
```

**Key Requirements:**
1. Temperature always 0.0 (override caller attempts)
2. Cache files: `{cache_dir}/{sha256_hex}.json`
3. Schema validation on all responses
4. Fallback on LLM failure (no cache write)
5. Cost tracking: separate counters for LLM calls and cache hits
6. Cost constants:
   - LLM: `tokens_used * 0.0001`
   - Cache hit: `0.00001` per hit

---

## 5. Test Execution

**Command:**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus
pytest .claude/capsule/tests/test_tier2_deterministic_llm.py -v
```

**Expected Output (All Fail):**
```
test_tier2_deterministic_llm.py::TestPromptCacheInitialization::test_prompt_cache_initialization FAILED
test_tier2_deterministic_llm.py::TestPromptHashDeterminism::test_prompt_hash_deterministic FAILED
test_tier2_deterministic_llm.py::TestPromptHashDeterminism::test_different_prompts_different_hashes FAILED
test_tier2_deterministic_llm.py::TestCacheHitMiss::test_cache_hit_returns_cached_result FAILED
test_tier2_deterministic_llm.py::TestCacheHitMiss::test_cache_miss_calls_llm FAILED
test_tier2_deterministic_llm.py::TestLLMSchemaValidation::test_llm_schema_validation FAILED
test_tier2_deterministic_llm.py::TestFallbackOnLLMFailure::test_fallback_on_llm_failure FAILED
test_tier2_deterministic_llm.py::TestFallbackOnLLMFailure::test_fallback_schema_compliance FAILED
test_tier2_deterministic_llm.py::TestTemperatureZeroDeterminism::test_temperature_zero_determinism FAILED
test_tier2_deterministic_llm.py::TestTemperatureZeroDeterminism::test_temperature_zero_enforcement FAILED
test_tier2_deterministic_llm.py::TestCostReductionMeasurable::test_cost_reduction_measurable FAILED
test_tier2_deterministic_llm.py::TestCostReductionMeasurable::test_cost_tracking_accuracy FAILED

FAILED (0/12 pass)
```

---

## 6. References

- **Cache Implementation:** `.claude/capsule/src/tier2_deterministic_llm.py` (to be created)
- **Tier 1 Tests:** `.claude/capsule/tests/test_tier1_cryptographic_integrity.py`
- **Conftest:** `.claude/capsule/tests/conftest.py` (MockLLMService added)
- **Haiku Pricing:** $0.0001 per input token (claude-3-haiku-20250107)
