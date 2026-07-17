# GitHub Integration Streams GH1-GH3 - Parallel Dispatch Configuration

**Dispatch Time:** 2026-07-15 12:00 UTC
**Expected Completion:** 2026-07-17 17:00 UTC
**Total Duration:** ~5 hours (parallel execution)

## Dispatch Format

Three independent agents launched simultaneously. Each agent:
- Has its own focused scope
- Works in isolation (no file conflicts)
- Returns specific deliverable(s)
- Posts findings to task comment on completion

## Agent Assignments

### AGENT-GH1: mattpocock/skills SDK Design Research
**Duration:** 2 hours
**Prompt Location:** `.claude/GH_AGENT_GH1_PROMPT.md`

**Mission:** 
Research https://github.com/mattpocock/skills and extract the agent behavior package manager design pattern. Design a Creator SDK TypeScript architecture based on this pattern.

**Deliverable:** 
`.claude/GH1_SDK_DESIGN_BLUEPRINT.md`
- mattpocock/skills pattern summary (200 words)
- Proposed Creator SDK directory structure
- Composable prompt pattern design for TypeScript
- Integration with siss-night-cycle operators
- File path examples for SDK distribution

**Post-Completion Task:** Comment on task #162 with:
- Link to GH1_SDK_DESIGN_BLUEPRINT.md
- One-sentence pattern summary
- Recommendation: proceed with Creator SDK? (Yes/No)

**Independence:** Pure research, no code modifications. No conflicts with GH2 or GH3.

---

### AGENT-GH2: Token Optimization Validation
**Duration:** 1 hour
**Prompt Location:** `.claude/GH_AGENT_GH2_PROMPT.md`

**Mission:**
Research https://github.com/pleasedodisturb/awesome-llm-token-optimization and validate whether the 18-25% token reduction target is realistic based on community best practices.

**Deliverable:**
`.claude/GH2_TOKEN_VALIDATION.md`
- Top 10 strategies summary with star counts
- Comparison matrix: drona23 v8 vs community best practices
- Validation: Is 18-25% reduction realistic? (Yes/No with confidence)
- Recommendations: strategies to add to A1 implementation

**Post-Completion Task:** Comment on task #163 with:
- Link to GH2_TOKEN_VALIDATION.md
- Validation result: Is 18-25% realistic? (one sentence)
- Top recommendation: which 1 strategy should A1 add?

**Independence:** Pure research, no code modifications. No conflicts with GH1 or GH3.

---

### AGENT-GH3: prompt-caching Integration Test
**Duration:** 2 hours
**Prompt Location:** `.claude/GH_AGENT_GH3_PROMPT.md`

**Mission:**
Research https://github.com/flightlesstux/prompt-caching and create an integration test that measures prompt caching performance with siss-night-cycle governance gates.

**Deliverables:**
1. `test_prompt_caching_integration.py` - Executable test script
2. `.claude/GH3_PROMPT_CACHING_RESULTS.md` - Test results document

**Test Expectations:**
- Execute 10 governance gate requests (2 cold, 8 warm cache)
- Measure: cache hit ratio, cost reduction, cache breakpoint optimization
- Target: cache hit ratio ≥80%

**Post-Completion Task:** Comment on task #164 with:
- Link to both test script and results document
- Cache hit ratio achieved: [X%]
- Status: PASS (≥80%) or FAIL (<80%)
- Recommendation: proceed with prompt caching rollout?

**Independence:** 
- Uses T2 test-prompt-caching.py from ~/.claude (read-only)
- Creates new test files (no conflicts)
- No file overlap with GH1 or GH2

---

## File Inventory (Isolation Verification)

### GH1 Files
- Creates: `.claude/GH1_SDK_DESIGN_BLUEPRINT.md` ✓ (unique)
- Reads: github.com/mattpocock/skills (external) ✓
- Reads: crates/siss-night-cycle/src/operators/mod.rs (research only) ✓
- **Conflict risk:** NONE

### GH2 Files
- Creates: `.claude/GH2_TOKEN_VALIDATION.md` ✓ (unique)
- Reads: github.com/pleasedodisturb/awesome-llm-token-optimization (external) ✓
- **Conflict risk:** NONE

### GH3 Files
- Creates: `test_prompt_caching_integration.py` ✓ (unique)
- Creates: `.claude/GH3_PROMPT_CACHING_RESULTS.md` ✓ (unique)
- Reads: ~/.claude/test-prompt-caching.py (read-only, from T2) ✓
- Reads: github.com/flightlesstux/prompt-caching (external) ✓
- **Conflict risk:** NONE

**Verdict:** All 3 agents are file-orthogonal. Safe to execute in parallel.

---

## Execution Checklist

- [ ] All 3 prompt files created (GH_AGENT_GH1/2/3_PROMPT.md)
- [ ] Agents dispatched simultaneously (this document)
- [ ] Each agent has clear scope and deliverable path
- [ ] No file overlaps between agents
- [ ] Task completion tracking: #162, #163, #164
- [ ] Deadline: 2026-07-17 17:00 UTC

---

## Monitoring & Integration

**No blocking dependencies between agents.** Each completes independently.

**Final integration step (after all agents return):**
1. Verify all 3 deliverables exist
2. Verify task comments posted to #162, #163, #164
3. Confirm GH1 SDK design is actionable for next phase
4. Confirm GH2 validation informs A1 token reduction roadmap
5. Confirm GH3 test results justify prompt caching rollout decision

---

## Next Steps (Post-Completion)

**If GH1 ≥ 8/10 quality:**
- Prioritize Creator SDK implementation in Phase 34

**If GH2 validates 18-25% realistic:**
- Add top 2 recommended strategies to A1 implementation plan

**If GH3 achieves ≥80% cache hit ratio:**
- Schedule prompt caching rollout for production governance gates
- Measure annualized cost savings

**If any deliverable ≤ 7/10 quality:**
- Assign re-work task to same agent (or different agent)
- Deadline: 2026-07-18 EOD
