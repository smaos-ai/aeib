# GitHub Integration Streams — Agent Quick Reference

**Format:** One-page lookup for agents. Read your section, then read full prompt.

---

## AGENT-GH1: mattpocock/skills → Creator SDK Design

**Task:** #162
**Duration:** ~2 hours
**Research:** https://github.com/mattpocock/skills

**What to do:**
1. Explore mattpocock/skills repository
2. Extract how they organize composable prompts
3. Learn their .claude directory pattern
4. Design a Creator SDK TypeScript version based on their pattern
5. Show how it integrates with siss-night-cycle operators

**Deliverable Path:**
```
/Users/andriileukhin/Documents/SovereignNexus/.claude/GH1_SDK_DESIGN_BLUEPRINT.md
```

**What to include (5 sections):**
1. mattpocock/skills pattern summary (200 words)
2. Proposed Creator SDK directory structure
3. Composable prompt pattern for TypeScript
4. siss-night-cycle operator integration examples
5. SDK distribution file paths

**When done:**
- Post comment on task #162
- Include: link to doc + 1-sentence pattern summary + recommendation (Yes/No)

**Full instructions:** Read `.claude/GH_AGENT_GH1_PROMPT.md`

---

## AGENT-GH2: Token Optimization Validation

**Task:** #163
**Duration:** ~1 hour
**Research:** https://github.com/pleasedodisturb/awesome-llm-token-optimization

**What to do:**
1. Scan the awesome list for top 10 strategies (by stars + adoption)
2. Understand what each strategy does + how much reduction it provides
3. Learn what drona23 v8 does (research this separately)
4. Learn what Anthropic prompt caching does
5. Compare: which of top 10 is drona23 already using? Which is missing?
6. Answer: Is 18-25% token reduction realistic? (Yes/No/Partial)
7. Recommend 1-3 strategies to add to A1

**Deliverable Path:**
```
/Users/andriileukhin/Documents/SovereignNexus/.claude/GH2_TOKEN_VALIDATION.md
```

**What to include (5 sections):**
1. Top 10 strategies (table with star counts)
2. Comparison matrix: drona23 v8 vs community best practices
3. Anthropic prompt caching analysis
4. Validation result: Is 18-25% realistic? (explicit Yes/No/Partial + confidence)
5. Recommendations for A1 (1-3 strategies with effort/priority)

**When done:**
- Post comment on task #163
- Include: link to doc + validation result (1 sentence) + top strategy to add first

**Full instructions:** Read `.claude/GH_AGENT_GH2_PROMPT.md`

---

## AGENT-GH3: prompt-caching Integration Test

**Task:** #164
**Duration:** ~2 hours
**Research:** https://github.com/flightlesstux/prompt-caching

**What to do:**
1. Understand flightlesstux prompt caching debugging tools
2. Learn how cache_control and cache breakpoint inspection works
3. Load T2 test suite from `~/.claude/test-prompt-caching.py`
4. Integrate flightlesstux cache analysis tools
5. Build executable Python script that:
   - Runs 10 governance gate requests (2 cold, 8 warm cache)
   - Measures cache hit ratio, cost, breakpoints
   - Outputs metrics to JSON
6. Analyze results with flightlesstux tools
7. Determine: Did we achieve ≥80% cache hit ratio?
8. Write results summary document

**Deliverable Paths:**
```
/Users/andriileukhin/Documents/SovereignNexus/test_prompt_caching_integration.py
/Users/andriileukhin/Documents/SovereignNexus/.claude/GH3_PROMPT_CACHING_RESULTS.md
```

**Test script requirements:**
- Load `~/.claude/test-prompt-caching.py` from T2
- Integrate flightlesstux cache analysis
- Execute 10 requests (governance gates)
- Output metrics JSON
- Should run in <5 minutes
- Must be executable: `python3 test_prompt_caching_integration.py`

**Results document (6 sections):**
1. Test execution summary (date, environment, parameters)
2. Cache performance metrics (baseline + warm cache, hit ratio %)
3. Breakpoint analysis (what was cached? where did it miss?)
4. Cost analysis ($ saved + annualized projection)
5. Validation vs ≥80% target (PASS/FAIL + explanation)
6. Recommendations (rollout to production? Yes/No)

**When done:**
- Post comment on task #164
- Include: link to script + results doc + cache hit ratio [X%] + PASS/FAIL + recommendation

**Full instructions:** Read `.claude/GH_AGENT_GH3_PROMPT.md`

---

## AGENT-GH4: OpenRLHF Governance Pipeline Design

**Task:** #[GH4 task ID, TBD]  
**Duration:** ~6 hours design (not implementation)  
**Research:** https://github.com/OpenLMLab/OpenRLHF  
**Deadline:** 2026-07-23 EOD  
**Status:** Blocked on GH1-GH3 completion (ready Jul 16)

**What to do:**
1. Research OpenRLHF framework deeply (2 hours)
2. Design governance confidence scoring pipeline (RLHF model that outputs 0.0-1.0 scores)
3. Specify training architecture (Ray on Nebius H100s)
4. Specify inference architecture (ONNX Runtime on Mac Studio, <10ms latency)
5. Design monitoring + continuous learning strategy

**Deliverable Path:**
```
/Users/andriileukhin/Documents/SovereignNexus/GH4_OPENRLHF_PIPELINE.md
```

**What to include (6 sections + appendix):**
1. Problem statement (binary decisions hide uncertainty)
2. Solution overview (learned confidence scores from RLHF)
3. Architecture design (5 subsections: OpenRLHF overview, model, training, inference, monitoring)
4. Integration with Phase 25 (how does GH4 hook into ReBAC + AP2?)
5. Metrics & success criteria (confidence ≥0.75 mean for GH6 pilot)
6. Series A narrative (investor story)

**When done:**
- Post comment on task #[GH4]
- Include: link to doc + 1-sentence summary + key metric (confidence ≥0.75)

**Full instructions:** Read `.claude/GH_AGENT_GH4_PROMPT.md`

---

## AGENT-GH5: Safe RLHF Fairness Constraints Design

**Task:** #[GH5 task ID, TBD]  
**Duration:** ~4 hours design (not implementation)  
**Research:** PKU-Alignment Safe RLHF framework  
**Deadline:** 2026-07-25 EOD  
**Dependency:** GH4 must be complete first  
**Status:** Blocked on GH4 (ready Jul 23)

**What to do:**
1. Research Safe RLHF + fairness measurement (2 hours)
2. Design fairness constraint model (parity ≤10% approval rate difference)
3. Specify training with constraint enforcement (Lagrange multipliers)
4. Specify runtime fairness verification + audit trail
5. Design fairness validation harness (regulatory-auditable)

**Deliverable Path:**
```
/Users/andriileukhin/Documents/SovereignNexus/GH5_SAFE_RLHF_CONSTRAINTS.md
```

**What to include (8 sections + appendix):**
1. Problem statement (fairness constraints for governance)
2. Solution overview (Safe RLHF with parity constraints)
3. Architecture design (5 subsections: Safe RLHF overview, fairness definition, training, inference, validation)
4. Integration with GH4 (layers on confidence scores)
5. Fairness validation harness (how to prove fairness to regulators)
6. Metrics & success criteria (0 fairness violations, parity ≤10%)
7. Regulatory compliance story (EU AI Act + GDPR narrative)
8. Series A narrative (competitive advantage)

**When done:**
- Post comment on task #[GH5]
- Include: link to doc + fairness metric definition + regulatory angle (1 sentence each)

**Full instructions:** Read `.claude/GH_AGENT_GH5_PROMPT.md`

---

## Shared Context

**Master dispatch document (read after your agent prompt):**
```
.claude/GITHUB_INTEGRATION_STREAMS_DISPATCH.md
```

**GH4-GH5 coordination:**
- GH4 (confidence) + GH5 (fairness) are sequential but overlapping
- GH4 due Jul 23, GH5 due Jul 25 (48h gap for feedback/iteration)
- Both must be ready by Jul 26 for GH6 pilot integration
- Key metric: RLHF confidence ≥0.75 mean (GH6 target)
- Key metric: Fairness violations = 0 (GH6 target)

**Key context:**
- Deadline: GH4 (Jul 23), GH5 (Jul 25)
- Quality threshold: ≥8/10 (if <7/10, re-work needed)
- GH4 + GH5 are design specs, not implementation
- Success criteria: all in GH6_CONTEXT_MAP.md

---

## File Organization

Your agent creates unique files. No overlap with other agents:

**GH1 only:**
- .claude/GH1_SDK_DESIGN_BLUEPRINT.md

**GH2 only:**
- .claude/GH2_TOKEN_VALIDATION.md

**GH3 only:**
- test_prompt_caching_integration.py
- .claude/GH3_PROMPT_CACHING_RESULTS.md

**GH4 only:**
- .claude/GH4_OPENRLHF_PIPELINE.md

**GH5 only:**
- .claude/GH5_SAFE_RLHF_CONSTRAINTS.md

**Shared input (GH3 only):**
- ~/.claude/test-prompt-caching.py (read-only, from T2)

---

## Contact & Escalation

If you:
- Need clarification on requirements → re-read your full prompt file
- Hit a blocker → document it + create task comment describing issue
- Finish early → verify quality ≥8/10, then post completion comment
- Run into errors → don't suppress them; include error details in completion comment

---

## TL;DR Quick Start

1. **GH1:** mattpocock → SDK design blueprint (2h) → post comment [Jul 17]
2. **GH2:** awesome-llm-token → validation doc (1h) → post comment [Jul 16]
3. **GH3:** flightlesstux → integration test (2h) → post comment [Jul 17]
4. **GH4:** OpenRLHF → governance pipeline design (6h) → post comment [Jul 23]
5. **GH5:** Safe RLHF → fairness constraints design (4h) → post comment [Jul 25]

GH1/GH2/GH3 parallel (due Jul 16-17).  
GH4 starts after GH1-GH3 (due Jul 23).  
GH5 starts after GH4 (due Jul 25).  
GH6 (coordinator) integrates all 5 by Jul 26 for pilot.

Read your agent prompt file first. Then master dispatch. Then execute.
