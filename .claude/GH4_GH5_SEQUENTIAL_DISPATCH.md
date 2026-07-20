# GitHub Integration Streams GH4-GH5 - Sequential Dispatch Configuration

**Dispatch Time:** 2026-07-16 (after GH1-GH3 completion gates)  
**GH4 Start:** 2026-07-16 EOD (as soon as GH1-GH3 confirmed ready)  
**GH4 Due:** 2026-07-23 17:00 UTC  
**GH5 Start:** 2026-07-23 EOD (after GH4 completion)  
**GH5 Due:** 2026-07-25 17:00 UTC  
**Total Duration:** 9 days (sequential pipeline)

---

## OVERVIEW

GH4 and GH5 form the **ML-learned governance** centerpiece for Series A.

- **GH4:** Confidence scoring (RLHF model that outputs 0.0-1.0 per governance decision)
- **GH5:** Fairness constraints (Safe RLHF ensuring equal treatment across risk classes)

Both are **design specs only** (no implementation code). Both must be ready by Jul 26 for GH6 pilot integration.

---

## CRITICAL TIMELINE

| Date | Milestone | Owner | Decision | Impact |
|------|-----------|-------|----------|--------|
| Jul 16 | GH1-GH3 gate passed | GH1/2/3 agents | ✓ GO | GH4 unblocked |
| Jul 17 | GH1 + GH3 deliverables confirmed | Coordinator | ✓ Verify | Customer outreach ready |
| Jul 23 | GH4 OPENRLHF design done | GH4 agent | Review + approve | GH5 unblocked |
| Jul 24 | 2-3 customers confirmed | Coordinator | ✓ Critical gate | Pilot execution |
| Jul 25 | GH5 Safe RLHF design done | GH5 agent | Review + approve | All 5 features ready |
| Jul 26-30 | GH6 integrated pilot | Coordinator | Execution phase | 2-3 LOIs signed |

**Critical Path:** GH4 (Jul 23) → GH5 (Jul 25) → GH6 integration (Jul 26).  
**Slack Buffer:** GH4 7 days, GH5 2 days. Minimal margin for re-work.

---

## DISPATCH CONFIGURATION

### AGENT-GH4: OpenRLHF Governance Pipeline Design

**Duration:** ~6 hours design work (research heavy)  
**Prompt Location:** `.claude/GH_AGENT_GH4_PROMPT.md`  
**Status:** Ready to launch (depends on GH1-GH3 completion)

**Mission:**
Design a complete RLHF-based governance evaluation pipeline that produces confidence scores (0.0-1.0) for every governance decision. The confidence score indicates how certain the model is that its decision (Allow/Deny) is correct.

**Core Design Tasks:**
1. Research OpenRLHF framework deeply (understand RLHF architecture, training, inference)
2. Design base model architecture (recommend Phi-3 mini 2.7B)
3. Design LoRA fine-tuning strategy (rank 8-16, efficient training)
4. Design reward model (confidence calibration)
5. Design PPO optimization (training loop)
6. Design Ray distributed training (Nebius H100s, 2-4 hours expected)
7. Design ONNX Runtime inference (Mac Studio CPU, <10ms latency p99)
8. Design monitoring + continuous learning (weekly validation, monthly retraining)

**Key Metrics (GH6 Target):**
- Mean confidence: ≥0.75 (core success metric)
- Calibration error: <0.10 (scores match reality)
- Latency p99: <10ms (production-ready)
- Training data: 10K examples (from Phase 25 audit logs)

**Deliverable:**
```
/Users/andriileukhin/Documents/SovereignNexus/GH4_OPENRLHF_PIPELINE.md
```

**Document Spec (2000-2500 words):**
- Executive summary (problem + solution)
- OpenRLHF framework overview (why it's right tool)
- Architecture design (4 subsections: model, training, inference, monitoring)
- Integration with Phase 25 (how confidence gate sits in pipeline)
- Series A narrative (investor story)
- Implementation sketch (pseudo-code, no full code)
- Research appendix (OpenRLHF, Ray, ONNX findings)

**Post-Completion Task:** Comment on task #[GH4] with:
- Link to GH4_OPENRLHF_PIPELINE.md
- Key metric: "Mean confidence ≥0.75 for GH6 pilot"
- Integration point: "Hooks into Phase 25 TemporalGuard (confidence gating)"
- Status: "Ready for GH5 sequencing"
- Quality score: [X]/10

**Research Hours Breakdown:**
- OpenRLHF deep dive: 2 hours
- Policy-as-text modeling: 1 hour
- Ray training architecture: 1.5 hours
- ONNX Runtime optimization: 1 hour
- Calibration & monitoring: 1 hour
- **Total research:** 6.5 hours (covered in 6h duration via focused scope)

**Deliverable Quality Checklist:**
- [ ] All 6 sections present + coherent
- [ ] OpenRLHF research thorough (framework understood)
- [ ] Architecture is concrete (not theoretical)
- [ ] Integration with Phase 25 is explicit
- [ ] Series A narrative is compelling
- [ ] Success metrics clearly defined (≥0.75 confidence)
- [ ] No placeholder text
- [ ] 2000-2500 words
- [ ] Spell-checked + grammar-checked

**File Isolation:**
- Creates: `.claude/GH4_OPENRLHF_PIPELINE.md` ✓ (unique)
- Reads: github.com/OpenLMLab/OpenRLHF (external research)
- Reads: Ray cluster docs (external)
- Reads: ONNX Runtime docs (external)
- Reads: GH6_CONTEXT_MAP.md (context only)
- **Conflict risk:** NONE

---

### AGENT-GH5: Safe RLHF Fairness Constraints Model Design

**Duration:** ~4 hours design work (research + constraint modeling)  
**Prompt Location:** `.claude/GH_AGENT_GH5_PROMPT.md`  
**Dependency:** GH4 must be complete + reviewed first  
**Status:** Blocked on GH4 (ready after Jul 23)

**Mission:**
Design a constrained RLHF model that enforces fairness during training and inference. The model must maintain high confidence (from GH4) while ensuring approval rates are equal across risk classes (Low/Medium/High/Critical).

**Core Design Tasks:**
1. Research Safe RLHF framework (PKU-Alignment implementation)
2. Design fairness constraint (≤10% parity in approval rates across risk classes)
3. Design Lagrange multiplier optimization (constraint enforcement)
4. Design training pipeline with constraint monitoring
5. Design runtime fairness verification (gate on every decision)
6. Design fairness validation harness (regulatory-auditable)
7. Design regulatory compliance narrative (EU AI Act, GDPR, FCRA)

**Key Metrics (GH6 Target):**
- Fairness violations: 0 (perfect parity)
- Approval rate parity: ≤10% difference across risk classes
- Fairness score: ≥0.80 (dashboard metric)

**Deliverable:**
```
/Users/andriileukhin/Documents/SovereignNexus/GH5_SAFE_RLHF_CONSTRAINTS.md
```

**Document Spec (2000-2500 words):**
- Executive summary (problem + solution)
- PKU-Alignment Safe RLHF overview (why for governance)
- Fairness constraint design (parity definition, measurement, enforcement)
- Training pipeline with constraints (4 subsections: data, monitoring, optimization, convergence)
- Runtime constraint enforcement (fairness gate in inference)
- Validation harness (auditable proof of fairness)
- Regulatory compliance story (investor narrative)
- Implementation sketch (pseudo-code)
- Research appendix (Safe RLHF, fairness metrics, regulatory requirements)

**Post-Completion Task:** Comment on task #[GH5] with:
- Link to GH5_SAFE_RLHF_CONSTRAINTS.md
- Fairness metric: "≤10% approval rate parity across risk classes"
- Integration: "Layers on GH4 confidence (same model, + fairness gate)"
- Status: "Ready for GH6 pilot (all 5 features finalized)"
- Quality score: [X]/10

**Research Hours Breakdown:**
- Safe RLHF framework: 1.5 hours
- Fairness metrics + measurement: 1 hour
- Fairness validation methodologies: 1 hour
- Regulatory compliance framing: 0.5 hours
- **Total research:** 4 hours

**Deliverable Quality Checklist:**
- [ ] All 8 sections present + coherent
- [ ] Safe RLHF research thorough
- [ ] Fairness constraint is well-defined (≤10% justified)
- [ ] Regulatory compliance narrative is strong
- [ ] Integration with GH4 is explicit (layers cleanly)
- [ ] Validation harness is auditable (regulators can verify)
- [ ] Series A narrative is compelling
- [ ] No placeholder text
- [ ] 2000-2500 words
- [ ] Spell-checked + grammar-checked

**File Isolation:**
- Creates: `.claude/GH5_SAFE_RLHF_CONSTRAINTS.md` ✓ (unique)
- Reads: github.com/PKU-Alignment/safe-rlhf (external research)
- Reads: Fairness tools (IBM AIF360, Google What-If, Fairlearn)
- Reads: GH4_OPENRLHF_PIPELINE.md (dependency, reviewed before GH5 starts)
- Reads: GH6_COORDINATOR_BRIEF.md (context)
- **Conflict risk:** NONE

---

## EXECUTION SEQUENCE

### Phase 1: GH4 Execution (Jul 16-23)

**Jul 16 (Gate: GH1-GH3 ready)**
- Coordinator confirms GH1 SDK blueprint + GH3 caching integration are working
- GH4 agent receives go-ahead
- GH4 agent starts research phase (OpenRLHF, Ray, ONNX)

**Jul 18-22 (GH4 Design Work)**
- GH4 agent completes research (6.5 hours documentation)
- Writes GH4_OPENRLHF_PIPELINE.md (2000-2500 words)
- Self-grades against 5 success criteria
- If <8/10 on any criterion, revises

**Jul 23 (GH4 Completion)**
- GH4 agent posts completion comment on task #[GH4]
- Coordinator reviews spec (30-45 min)
- Feedback loop: Coordinator → GH4 agent (if revisions needed)
- **Decision Gate:** Is GH4 ≥8/10 quality? Approve for GH5 kickoff.

### Phase 2: GH5 Execution (Jul 23-25)

**Jul 23 (Gate: GH4 approved)**
- Coordinator approves GH4 spec
- GH5 agent receives prompt + GH4_OPENRLHF_PIPELINE.md
- GH5 agent starts research phase (Safe RLHF, fairness metrics, regulatory)

**Jul 24 (GH5 Design Work)**
- GH5 agent completes research (4 hours documentation)
- Writes GH5_SAFE_RLHF_CONSTRAINTS.md (2000-2500 words)
- Verifies integration with GH4 (fairness layers cleanly on confidence)
- Self-grades against 5 success criteria

**Jul 25 (GH5 Completion)**
- GH5 agent posts completion comment on task #[GH5]
- Coordinator reviews spec (30-45 min)
- Feedback loop: Coordinator → GH5 agent (if revisions needed)
- **Decision Gate:** Is GH5 ≥8/10 quality? Approve for GH6 integration.

### Phase 3: GH6 Integration (Jul 26-30)

**Jul 26 (ALL 5 FEATURES READY)**
- GH4_OPENRLHF_PIPELINE.md + GH5_SAFE_RLHF_CONSTRAINTS.md + GH1-GH3 deliverables all finalized
- Coordinator wires all 5 features together for pilot demo
- 2-3 customers arrive for live demo
- Demo #1: Creator SDK (GH1)
- Demo #2: Token optimization (GH2)
- Demo #3: Prompt caching (GH3)
- Demo #4: RLHF confidence (GH4)
- Demo #5: Fairness constraints (GH5)

**Jul 27-28 (Integration Trial)**
- Run 100+ governance decisions on real customer data
- Collect metrics: confidence, cache hit, tokens, latency, fairness
- Verify all success criteria met

**Jul 29-30 (Closeout)**
- Final metrics review
- LOI negotiation
- 2-3 LOIs signed

---

## SUCCESS CRITERIA

### GH4 Success (Single Agent Evaluation)

| Criterion | Weight | Bar | Verification |
|-----------|--------|-----|--------------|
| Architecture completeness | 25% | All 6 sections, coherent design | Checklist pass |
| Technical depth | 25% | OpenRLHF + Ray + ONNX research thorough | Research appendix |
| Integration clarity | 20% | Phase 25 hook point explicit | Architecture section |
| Investor readability | 15% | Non-technical summary compelling | Series A section |
| Practicality | 15% | Design actually implementable | Implementation sketch passes review |

**Overall:** ≥8/10 required. <7/10 triggers re-work.

### GH5 Success (Single Agent Evaluation)

| Criterion | Weight | Bar | Verification |
|-----------|--------|-----|--------------|
| Fairness design | 25% | ≤10% parity justified, measurement clear | Constraint section |
| Safe RLHF integration | 25% | Lagrange multiplier explained, constraint enforcement clear | Training section |
| Regulatory framing | 20% | EU AI Act + GDPR narrative strong | Compliance section |
| Validation completeness | 15% | Validation harness is auditable | Validation section |
| GH4 integration | 15% | Layers cleanly on confidence scores | Integration section |

**Overall:** ≥8/10 required. <7/10 triggers re-work.

### GH6 Success (Both Combined)

| Metric | Target | Why | Owner |
|--------|--------|-----|-------|
| **RLHF Confidence** | ≥0.75 mean | Proves audit trail trustworthiness | GH4 design validates this |
| **Fairness Parity** | ≤10% difference | Non-discrimination proof | GH5 design validates this |
| **Cache Hit Ratio** | ≥80% | Cost savings | GH3 design validates this |
| **Token Reduction** | ≥18% | Budget proof | GH2 research validates this |
| **Latency p99** | <100ms | Production-ready | GH4 design targets <10ms |
| **Fairness Violations** | 0 | Perfect parity | GH5 design enforces |

**All 6 must pass per customer for GH6 to succeed.**

---

## MONITORING & ESCALATION

### Daily Standup (Coordinator + Agents)

**GH4 Week (Jul 16-23):**
- Morning: "How far in research?" (progress check)
- Evening: "Blockers?" (any unclear requirements?)
- Trend: Is GH4 on track for Jul 23 deadline?

**GH5 Week (Jul 23-25):**
- After GH4 approval: "GH5 kickoff confirmed"
- Daily: "How far in design?" (progress check)
- Jul 25 EOD: "GH5 complete, ready for GH6"

### Escalation Triggers

**If GH4 slips past Jul 23:**
- Impact: GH5 must compress (2 days instead of 2.5), GH6 integration risky
- Action: Coordinator decision → (A) Accelerate GH5, or (B) Reschedule pilot to Aug 2
- Owner: Founder approval needed if >24h slip

**If GH5 slips past Jul 25:**
- Impact: GH6 integration must happen Jul 26 morning, no buffer
- Action: Coordinate emergency review (30 min), fast-track approval
- Owner: Coordinator can approve if quality ≥8/10, else escalate

**If either design <7/10 quality:**
- Impact: Re-work required, shifts deadline 1-2 days
- Action: Assign re-work task immediately
- Owner: Same agent (preferred) or different agent (if expert needed)

---

## FILE INVENTORY (ISOLATION VERIFICATION)

### GH4 Files
- Creates: `.claude/GH4_OPENRLHF_PIPELINE.md` ✓ (unique)
- Reads: github.com/OpenLMLab/OpenRLHF (external)
- Reads: Ray docs, ONNX Runtime docs (external)
- Reads: GH6_CONTEXT_MAP.md (research context)
- **Conflict risk:** NONE

### GH5 Files
- Creates: `.claude/GH5_SAFE_RLHF_CONSTRAINTS.md` ✓ (unique)
- Reads: github.com/PKU-Alignment/safe-rlhf (external)
- Reads: GH4_OPENRLHF_PIPELINE.md (input, after Jul 23)
- Reads: Fairness tools docs (external)
- Reads: GH6_CONTEXT_MAP.md (research context)
- **Conflict risk:** NONE

**Verdict:** Both agents are file-orthogonal + sequential (GH4 → GH5). Safe to execute as designed.

---

## EXECUTION CHECKLIST

**Pre-Launch (Jul 15):**
- [ ] GH_AGENT_GH4_PROMPT.md created
- [ ] GH_AGENT_GH5_PROMPT.md created
- [ ] GH4_GH5_SEQUENTIAL_DISPATCH.md created (this file)
- [ ] GH_AGENT_QUICK_REFERENCE.md updated with GH4/GH5 sections
- [ ] GH6_COORDINATOR_BRIEF.md confirms GH4 (Jul 23) + GH5 (Jul 25) milestones

**GH4 Launch (Jul 16, after GH1-GH3 gate):**
- [ ] GH1-GH3 confirmed ready (Coordinator decision)
- [ ] GH4 agent receives prompt + research tasks
- [ ] GH4 agent confirms research plan
- [ ] Research begins (Jul 16 evening or Jul 17 morning)

**GH4 Completion (Jul 23):**
- [ ] GH4_OPENRLHF_PIPELINE.md written (2000-2500 words)
- [ ] All 6 sections present + coherent
- [ ] Research appendix documents OpenRLHF, Ray, ONNX findings
- [ ] Self-grade: ≥8/10 on all 5 criteria
- [ ] Completion comment posted on task #[GH4]
- [ ] Coordinator reviews spec (30-45 min)

**GH5 Launch (Jul 23, after GH4 approval):**
- [ ] GH4 approved (quality ≥8/10)
- [ ] GH5 agent receives prompt + GH4 spec
- [ ] GH5 agent confirms research plan + GH4 integration strategy
- [ ] Research begins (Jul 23 evening)

**GH5 Completion (Jul 25):**
- [ ] GH5_SAFE_RLHF_CONSTRAINTS.md written (2000-2500 words)
- [ ] All 8 sections present + coherent
- [ ] GH4 integration verified (fairness layers cleanly)
- [ ] Research appendix documents Safe RLHF, fairness, regulatory findings
- [ ] Self-grade: ≥8/10 on all 5 criteria
- [ ] Completion comment posted on task #[GH5]
- [ ] Coordinator reviews spec (30-45 min)

**GH6 Integration (Jul 26):**
- [ ] Both specs approved + finalized
- [ ] GH1-GH3 deliverables also finalized
- [ ] All 5 features wired together for demo
- [ ] Demo environment ready (customer-facing)

---

## NEXT STEPS (POST-COMPLETION)

### After GH4 Approval (Jul 23):
- GH5 agent begins research immediately (no wait time)
- Coordinator shares GH4 spec with GH6 team (for integration planning)
- GH6 team flags any integration concerns (address before GH5 final)

### After GH5 Approval (Jul 25):
- Coordinator wires GH4 + GH5 into GH6 demo environment
- All 5 features tested together (integration test)
- Metrics dashboard prepared (confidence, fairness, cache, tokens, latency)
- Customer demo script finalized (walkthrough of all 5)

### GH6 Execution (Jul 26-30):
- Deploy all 5 features to production demo environment
- Run with 2-3 customers (100+ governance decisions per customer)
- Collect metrics + customer feedback
- Sign 2-3 LOIs by Jul 30

---

## COMMUNICATION PLAN

### Task Updates
- **GH4 agent:** Post daily progress (research complete → writing → self-review → ready)
- **GH5 agent:** Post daily progress (research complete → writing → GH4 integration → ready)
- **Coordinator:** Monitor progress, escalate if slips detected, make approval decisions

### Slack Channels
- **#governance-pipeline:** GH4-GH5 technical discussions
- **#series-a:** GH4-GH5 progress updates (for founder awareness)
- **#gh6-pilot:** Integration coordination + customer prep

### Status Reports
- **Every evening (6 PM UTC):**
  - Coordinator to founder: "GH4/GH5 progress, blockers (if any), tomorrow's plan"
  - Format: 3-4 bullets, 5 min read

---

**Document Owner:** Coordinator (Andrey Leukhin)  
**Status:** Ready for dispatch  
**Date Created:** 2026-07-15  
**Last Update:** 2026-07-15  
**Next Review:** Jul 16 (after GH1-GH3 gate)
