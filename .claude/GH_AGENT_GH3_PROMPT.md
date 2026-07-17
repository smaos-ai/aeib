# TASK GH3: prompt-caching Integration Test Design & Execution

## Objective
Research the flightlesstux/prompt-caching repository, understand its cache debugging tools, and create an integration test that measures prompt caching performance with siss-night-cycle governance gates.

## Scope
- Focus: https://github.com/flightlesstux/prompt-caching
- Goal: Design and execute an integration test
- Output: Test script + results summary document
- Expected achievement: ≥80% cache hit ratio on repeated governance prompts
- Deadline: 2026-07-17 EOD
- Do NOT modify existing codebase; this is new test code only

## Deliverable Paths
1. **Test Script:** `/Users/andriileukhin/Documents/SovereignNexus/test_prompt_caching_integration.py`
2. **Results Document:** `/Users/andriileukhin/Documents/SovereignNexus/.claude/GH3_PROMPT_CACHING_RESULTS.md`

## Background Context
- T2 (Anthropic prompt caching API) was already completed in a previous agent session
- Test file should be available at `~/.claude/test-prompt-caching.py`
- siss-night-cycle governance gates are the primary use case

## Specific Deliverables

### 1. Integration Test Script (`test_prompt_caching_integration.py`)

The script should:
- Import the T2 test-prompt-caching.py module (load at `~/.claude/test-prompt-caching.py`)
- Integrate flightlesstux cache analysis tools
- Execute 10 governance gate requests in sequence
- First 2 requests: measure baseline (cold cache)
- Next 8 requests: measure cache effectiveness (warm cache)
- Track:
  * Cache hit ratio (hits / total requests)
  * Cost reduction ($ saved by cache hits)
  * Cache breakpoint optimization (where did cache help most?)
  * Cache size and TTL

**Script Structure:**
```python
#!/usr/bin/env python3
"""
Prompt Caching Integration Test for siss-night-cycle Governance Gates

Tests cache performance using flightlesstux tools + Anthropic prompt caching API
Expected: cache hit ratio ≥80% on repeated governance gate prompts
"""

import sys
import json
from pathlib import Path

# 1. Load T2 test suite from ~/.claude/test-prompt-caching.py
# 2. Import flightlesstux cache analysis tools
# 3. Define 10 governance gate test requests
# 4. Execute cold cache baseline (requests 0-1)
# 5. Execute warm cache tests (requests 2-9)
# 6. Analyze results with flightlesstux tools
# 7. Output metrics: cache hit ratio, cost reduction, breakpoints
# 8. Save raw results to JSON for analysis
```

**Metrics to Capture (for each request):**
```json
{
  "request_id": 1,
  "sequence": "cold_cache",
  "governance_gate_type": "approval_gate",
  "prompt_tokens": 1250,
  "completion_tokens": 180,
  "cache_creation_input_tokens": 1250,
  "cache_read_input_tokens": 0,
  "cost_per_request_without_cache": 0.015,
  "cost_per_request_with_cache": 0.015,
  "cache_hit": false
}
```

Then for request 2 (warm cache):
```json
{
  "request_id": 2,
  "sequence": "warm_cache",
  "governance_gate_type": "approval_gate",
  "prompt_tokens": 1250,
  "completion_tokens": 185,
  "cache_creation_input_tokens": 0,
  "cache_read_input_tokens": 1250,
  "cost_per_request_without_cache": 0.015,
  "cost_per_request_with_cache": 0.0075,
  "cache_hit": true
}
```

### 2. Results Document (`GH3_PROMPT_CACHING_RESULTS.md`)

Format as:

#### Section A: Test Execution Summary
- Date/time of test
- Test environment (Python version, API version, etc.)
- Test parameters (10 governance gate requests, types, etc.)

#### Section B: Cache Performance Metrics
```
BASELINE (Cold Cache - Requests 0-1):
- Average tokens per request: [X]
- Average cost per request: $[Y]
- Total cost (2 requests): $[Z]

WARM CACHE (Requests 2-9):
- Cache hit ratio: [X%]
- Average cost per request: $[Y]
- Total cost (8 requests): $[Z]
- Cost savings vs no cache: $[W]
- Average savings per request: [Z%]

OVERALL RESULTS:
- Total cache hit ratio across all 10 requests: [X%]
- Total cost with caching: $[A]
- Total cost without caching: $[B]
- Overall savings: $[C] ([D%])
- Target achieved: ≥80% hit ratio? YES / NO
```

#### Section C: Breakpoint Analysis (flightlesstux tool output)
- What was cached? (which parts of the governance gate prompt)
- Cache breakpoints: where did the cache miss? (unexpected recompilation points)
- Optimization opportunities: what could improve hit ratio?

Example:
```
CACHE BREAKPOINTS:
- [breakpoint 1] System prompt cached (reused all 8 requests)
- [breakpoint 2] Context block cached (reused 6/8 requests)
- [breakpoint 3] Policy rules NOT cached (recompiled 4/8 requests - potential issue)

OPTIMIZATION OPPORTUNITY:
Policy rules should be static. Current cache miss rate: 50%.
Recommendation: Move policy rules into separate cache block
with longer TTL. Estimated improvement: 15% additional hit ratio.
```

#### Section D: Cost Analysis
- Per-request cost breakdown (with vs without cache)
- Annualized savings projection (assuming 1000 governance gates/day)
- ROI of implementing prompt caching

#### Section E: Validation Against Target
```
TARGET REQUIREMENT: Cache hit ratio ≥80%
ACHIEVED: [X%]
STATUS: ✓ PASS / ✗ FAIL

If FAIL: Root cause analysis
- Why is hit ratio below 80%?
- What's causing cache misses?
- What would improve it?
```

#### Section F: Recommendations
- Is prompt caching effective for governance gates? (Yes/No)
- Should it be deployed to production? (Recommendation + confidence)
- Next steps: additional optimization or proceed with rollout?

## Research Steps for Implementation

1. **Visit flightlesstux/prompt-caching:**
   - Understand how the cache debugging tool works
   - Learn the cache_control API and breakpoint inspection
   - Extract the cache analysis pattern

2. **Understand T2 context:**
   - Review ~/.claude/test-prompt-caching.py (should exist from previous T2 work)
   - Understand what Anthropic prompt caching API it uses
   - Learn the test pattern

3. **Design governance gate test requests:**
   - What are realistic governance gate prompts?
   - How should they vary across 10 requests?
   - Ensure variation is minimal (for cache effectiveness testing)

4. **Implement the test script:**
   - Load T2 test suite
   - Add flightlesstux cache analysis
   - Execute 10 requests with proper metrics collection
   - Output raw JSON results

5. **Analyze results:**
   - Calculate cache hit ratio, cost savings
   - Identify breakpoints using flightlesstux tools
   - Document findings in results document

## Output Format

### Script (`test_prompt_caching_integration.py`)
- Clean, executable Python (Python 3.9+)
- Well-commented, especially integration points
- Proper error handling
- Output to JSON file in same directory as script
- ~150-250 lines of code

### Document (`GH3_PROMPT_CACHING_RESULTS.md`)
- Clear sections A-F as outlined above
- Include JSON metrics snippets where helpful
- Professional tone, data-driven conclusions
- ~1000-1500 words
- Include raw metrics in appendix if needed

## Completion Verification

**Script must:**
- Be executable: `python3 test_prompt_caching_integration.py`
- Complete without errors
- Generate JSON output with all 10 requests' metrics
- Take <5 minutes to run

**Document must:**
- Clearly state whether ≥80% cache hit ratio was achieved
- Explain what flightlesstux analysis revealed
- Make a clear recommendation for production use
- Be ready to present to investors/stakeholders

## Post-Completion

After deliverables are complete, post a comment on task #164 with:
- Link to both test script and results document
- Cache hit ratio achieved: [X%]
- Status: PASS (≥80%) or FAIL (<80%)
- One recommendation: proceed with prompt caching rollout? (Yes/No)
