# GH4-GH5: ML-Learned Governance Architecture Brief

**Date:** 2026-07-16  
**For:** Founder (Andrey), GH6 Coordinator, GH4-GH5 Agents  
**Status:** Ready for execution  
**Impact:** Series A competitive advantage + regulatory proof

---

## THE PITCH (60 Seconds)

**Problem:** Current governance (Phase 25 ReBAC + AP2) makes binary Allow/Deny decisions, but hides uncertainty.

**GH4 Solution:** RLHF-learned confidence scores (0.0-1.0) on every governance decision.
- Same decision engine (ReBAC, AP2, TemporalGuard)
- PLUS: Learned model predicts confidence (how sure are we?)
- Benefit for Series A: "We can PROVE our governance decisions are trustworthy"

**GH5 Solution:** Safe RLHF with fairness constraints (parity ≤10% across risk classes).
- Ensures approval rates don't differ by >10% between Low-risk vs Critical-risk requests
- Benefit for Series A: "We can PROVE our governance is fair (not biased)"
- Regulatory advantage: EU AI Act compliance + GDPR explainability

**Together (GH4 + GH5):** AXIOM governance is both **trustworthy AND fair**.

**Why it matters for Series A:**
- Investor question: "How do you KNOW your governance is safe?" → Confidence scores answer it
- Investor question: "Is your governance fair?" → Fairness audit trail answers it
- Regulatory question: "Can you prove non-discrimination?" → Fairness parity proves it
- Customer question: "Can I trust AI governance?" → Confidence + fairness say yes

---

## THE ARCHITECTURE

### GH4: OpenRLHF Confidence Pipeline

```
Governance Request
  ↓
ReBAC + AP2 + TemporalGuard (Phase 25)
  ↓
Decision: Allow OR Deny
  ↓
GH4: Confidence Model (RLHF-trained)
  ↓
Output: Confidence score (0.0-1.0)
  ↓
Gate: If confidence < 0.75 → Escalate to human
       If confidence ≥ 0.75 → Proceed with decision
  ↓
Audit trail: {decision, confidence, model_version, audit_id}
```

**Key numbers:**
- Mean confidence target: ≥0.75 (for GH6 pilot)
- Calibration error target: <0.10 (confidence matches reality)
- Latency target: <10ms p99 (production-ready on Mac Studio CPU)
- Training data: 10K examples from Phase 25 audit logs
- Model: Phi-3 mini (2.7B, <200MB) + LoRA fine-tuning
- Training: Ray distributed RLHF on Nebius H100s (2-4 hours)
- Inference: ONNX Runtime (Mac Studio, no GPU needed)

**Investor narrative:**
- "We use machine learning to quantify governance uncertainty"
- "Every decision includes a confidence score"
- "Low confidence → human review (safety fallback)"
- "High confidence → proven correct >85% of the time"

### GH5: Safe RLHF Fairness Constraints

```
GH4: Confidence scores + decisions
  ↓
Risk Classification
  └─ Low: trust_level > 75, no anomalies
  └─ Medium: trust_level 50-75
  └─ High: trust_level 25-50
  └─ Critical: trust_level < 25
  ↓
Fairness Constraint: |approval_rate(Low) - approval_rate(Critical)| ≤ 0.10
  ↓
Safe RLHF training: Optimize confidence score subject to fairness constraint
  ↓
Runtime enforcement: On every decision, check:
  - Would approving this request break fairness parity?
  - If yes → flag "fairness hold" (escalate to human)
  - If no → proceed
  ↓
Audit trail: {decision, confidence, fairness_check_result, approval_rate_per_class, parity_status}
```

**Key numbers:**
- Approval rate parity target: ≤10% difference (e.g., Low 80%, Critical 72% = OK)
- Fairness violations target: 0 (perfect parity required)
- Fairness score (customer metric): ≥0.80 (dashboard displayed)
- Regulatory compliance: EU AI Act Article 10 (non-discrimination)

**Investor narrative:**
- "We constrain governance to ensure fair treatment"
- "Approval rates are equal across all risk classes"
- "We measure fairness every day and prove it to regulators"
- "Non-discrimination is a feature, not an afterthought"

---

## TIMELINE & DEPENDENCIES

```
Jul 15-17: GH1-GH3 Design (mattpocock SDK, token validation, prompt caching)
             ↓
Jul 16 (GH1-GH3 gate): Coordinator approves GH1-GH3 deliverables
             ↓
Jul 16-23: GH4 Design (OpenRLHF confidence pipeline)
             ↓ (6 hours research + 2 hours writing)
Jul 23 (GH4 gate): Coordinator approves GH4 spec
             ↓
Jul 23-25: GH5 Design (Safe RLHF fairness constraints)
             ↓ (4 hours research + 2 hours writing)
Jul 25 (GH5 gate): Coordinator approves GH5 spec
             ↓
Jul 26-30: GH6 Integration & Pilot Execution
             ├─ All 5 features wired together
             ├─ 2-3 customers run live demos
             ├─ Metrics: confidence, fairness, cache, tokens, latency
             └─ 2-3 LOIs signed
             ↓
Aug 1+: Series A investor calls with pilot results
```

**Critical path:** GH4 (Jul 23) → GH5 (Jul 25) → GH6 (Jul 26-30).  
**Slack:** GH4 has 7 days, GH5 has 2 days. Minimal margin for re-work.

---

## GH4 DESIGN SPEC (LOCKED)

**Responsible Agent:** GH4 Agent (assigned Jul 16)  
**Duration:** 6 hours design (no implementation code)  
**Deliverable:** `GH4_OPENRLHF_PIPELINE.md` (2000-2500 words)  
**Due:** Jul 23 EOD  
**Quality Bar:** ≥8/10 (on 5 criteria)

**What GH4 agent must deliver:**
1. Research OpenRLHF framework (GitHub exploration + architecture understanding)
2. Design base model selection (why Phi-3 mini?)
3. Design LoRA strategy (rank, learning rate, efficiency)
4. Design reward model (confidence calibration from ground truth)
5. Design PPO training loop (Lagrange multipliers, KL penalty)
6. Design Ray distributed training (batch sizes, checkpointing, time estimate)
7. Design ONNX Runtime conversion (quantization, latency testing)
8. Design monitoring + continuous learning (weekly validation, monthly retraining)
9. Integration with Phase 25 (where does confidence gate sit?)
10. Series A narrative (investor story)

**Success criteria for GH6 pilot:**
- Mean confidence ≥0.75 on 100+ decisions per customer
- Calibration error <0.10 (predicted confidence ≈ actual accuracy)
- Latency p99 <10ms (production-ready)

**Why this matters:**
- Confidence scores are the "proof" that governance decisions are trustworthy
- Without them, AXIOM looks like another black-box AI system
- With them, we can show investors: "Every decision is audited AND confidence-scored"

---

## GH5 DESIGN SPEC (LOCKED)

**Responsible Agent:** GH5 Agent (assigned after GH4 approval, ~Jul 23)  
**Duration:** 4 hours design (no implementation code)  
**Deliverable:** `GH5_SAFE_RLHF_CONSTRAINTS.md` (2000-2500 words)  
**Due:** Jul 25 EOD  
**Quality Bar:** ≥8/10 (on 5 criteria)  
**Dependency:** GH4_OPENRLHF_PIPELINE.md must be reviewed + approved first

**What GH5 agent must deliver:**
1. Research PKU-Alignment Safe RLHF framework
2. Define fairness constraint (why ≤10% parity? justify)
3. Design Lagrange multiplier optimization (how to enforce constraint during training)
4. Design training data preparation (stratified sampling across risk classes)
5. Design constraint monitoring during training (fairness metric every 100 steps)
6. Design runtime fairness verification (gate on every inference)
7. Design fairness validation harness (how to prove fairness to regulators)
8. Design regulatory compliance narrative (EU AI Act, GDPR, FCRA)
9. Integration with GH4 (fairness layers on top of confidence scores)
10. Series A narrative (fairness as competitive advantage)

**Success criteria for GH6 pilot:**
- Fairness violations: 0 (perfect parity, never approve unfairly)
- Approval rate parity: ≤10% across all risk classes
- Fairness score ≥0.80 (customer-facing dashboard metric)

**Why this matters:**
- Fairness is the regulatory moat (EU AI Act requires non-discrimination)
- Fairness is the trust multiplier (customers believe the AI is fair)
- Fairness is the competitive differentiator (nobody else measures this)
- Without it: we're just another AI governance system (commoditized)
- With it: we're the governance system regulators can certify

---

## SUCCESS METRICS (GH6 PILOT TARGET)

All of these must pass for each customer:

| Feature | Metric | Target | Owner | Why |
|---------|--------|--------|-------|-----|
| **GH1: SDK** | Developer experience | 4+/5 Likert | GH1 agent | Extensibility proof |
| **GH2: Tokens** | Cost reduction | ≥18% vs baseline | GH2 research | Budget impact |
| **GH3: Caching** | Cache hit ratio | ≥80% | GH3 test | Latency proof |
| **GH4: Confidence** | Mean confidence | ≥0.75 | GH4 design | Trustworthiness |
| **GH5: Fairness** | Fairness violations | 0 | GH5 design | Regulatory compliance |
| **Overall: Latency** | p99 latency | <100ms | GH4 design | Production-ready |

**GH6 success:** All 6 metrics pass for ≥2 customers, ≥1 LOI signed.

---

## INVESTOR NARRATIVE (POST-GH6)

**Before GH6 (current):**
> "We're building AI governance that's secure and auditable. We've designed the architecture, filed patents, and completed a Prague PoC."

**After GH6 (Aug 1+):**
> "We completed integrated pilots with 3 customers validating our governance architecture. RLHF confidence hit 0.78 (target 0.75), fairness violations were zero, and cache hit ratio was 85% (target 80%). All 3 customers signed LOIs to pilot AXIOM for 90 days starting Aug 1. We're raising €10M Series A to deploy AXIOM across those 3 customers and 10+ design partners. Series A closes Aug 15."

**The power of GH6:** Confidence + fairness metrics become the closing argument.

---

## RISK MITIGATION

### If GH4 slips >2 days (past Jul 25):
- **Impact:** GH5 has only 1 day left, integration risky
- **Recovery:** Fast-track GH5 (6h design compressed to 4h), coordinate with GH6
- **Escalation:** Founder call required
- **Mitigation:** Daily progress tracking, unblock GH4 agent immediately if stuck

### If GH5 slips >1 day (past Jul 26):
- **Impact:** No buffer for GH6 integration, pilot execution starts without GH5
- **Recovery:** Run 4-feature demo (drop GH5), reschedule fairness for Phase 2
- **Escalation:** Founder call required
- **Mitigation:** Ensure GH5 agent has clear spec, no ambiguity

### If GH4 or GH5 quality <7/10:
- **Impact:** Specs must be re-worked, delays GH6 integration by 1-2 days
- **Recovery:** Assign re-work immediately, tight feedback loop
- **Escalation:** Founder decides: (A) re-work fast, or (B) drop feature from GH6
- **Mitigation:** Both agents self-grade before posting, coordinator does quality review

### If confidence doesn't hit 0.75 during GH6:
- **Impact:** Core Series A narrative weakened
- **Recovery:** Document why (e.g., complex customer data), re-tune model post-pilot
- **Narrative shift:** "Confidence can improve with more data; we have robust feedback loop"
- **Mitigation:** Test confidence score locally on Phase 25 audit logs before customer trial

### If fairness violations occur during GH6:
- **Impact:** Regulatory red flag, customer trust loss
- **Recovery:** Not acceptable. Must fix before customer sees results.
- **Mitigation:** Validate fairness constraints in sandbox before pilot; zero tolerance

---

## COORDINATOR CHECKLIST (YOUR JOB)

**Jul 16 (GH1-GH3 gate):**
- [ ] Confirm GH1 SDK blueprint is actionable (not abstract)
- [ ] Confirm GH3 caching integration test actually runs (<5 min, produces metrics)
- [ ] Confirm GH2 token validation is realistic (not speculative)
- [ ] Decision: GO for customer outreach (Jul 24)?

**Jul 23 (GH4 gate):**
- [ ] Review GH4_OPENRLHF_PIPELINE.md (30-45 min)
  - Is architecture coherent? (6 sections, no gaps)
  - Is confidence metric justified? (≥0.75 reasonable?)
  - Is integration with Phase 25 explicit? (confidence gate location clear)
  - Is latency target realistic? (<10ms p99 achievable?)
- [ ] Quality score: ≥8/10?
- [ ] Decision: APPROVE for GH5 kickoff?

**Jul 25 (GH5 gate):**
- [ ] Review GH5_SAFE_RLHF_CONSTRAINTS.md (30-45 min)
  - Is fairness metric well-defined? (≤10% justified?)
  - Is Safe RLHF integration clear? (Lagrange multiplier explained?)
  - Is regulatory narrative strong? (EU AI Act compliance story?)
  - Is integration with GH4 clean? (fairness layers on confidence?)
- [ ] Quality score: ≥8/10?
- [ ] Decision: APPROVE for GH6 integration?

**Jul 26 (GH6 integration gate):**
- [ ] All 5 features wired together? (GH1-GH5)
- [ ] Demo environment working? (all features load, no errors)
- [ ] Metrics dashboard ready? (confidence, fairness, cache, tokens, latency displayed)
- [ ] Customer #1 ready? (2-3 total confirmed)
- [ ] Decision: GO for first demo?

**Jul 27-29 (Pilot execution):**
- [ ] Daily metrics tracking (confidence, fairness, cache, tokens, latency)
- [ ] Customer satisfaction check (are they happy with demos?)
- [ ] Any issues → escalate to GH team for 24h fix
- [ ] Confidence on track? (≥0.75?)
- [ ] Fairness on track? (≤10% parity?)

**Jul 30 (LOI signature gate):**
- [ ] All success criteria met for all customers?
- [ ] Customer willing to sign LOI?
- [ ] Decision: CLOSE or CONTINUE negotiations?

---

## WHAT NOT TO DO

❌ **Don't wait for "perfect" design.** ≥8/10 is good enough. Perfection is the enemy of progress.

❌ **Don't skip integration testing.** Make sure GH4 + GH5 don't conflict (fairness doesn't break confidence, etc.).

❌ **Don't underestimate fairness importance.** It's not a nice-to-have; it's regulatory requirement + investor proof.

❌ **Don't start GH5 before GH4 is done.** You need to understand confidence architecture before adding fairness constraints.

❌ **Don't re-work specs after Jul 23/25 gates.** Make quality bar clear upfront; improve before posting.

---

## WHAT TO DO

✅ **Trust the agents.** They have clear prompts. Let them research + design independently.

✅ **Review specs carefully.** 30-45 min review per gate identifies issues early (not Jul 26).

✅ **Make approval decisions quickly.** Don't bottleneck GH4 → GH5 transition.

✅ **Escalate blockers immediately.** If agent stuck, unblock them fast (founder call if needed).

✅ **Celebrate wins.** Both specs done by Jul 25 = Series A narrative ready for Aug 1 investor calls.

---

## FINAL NARRATIVE FOR FOUNDER

**Current state (Jul 15):**
We have Phase 25 (ReBAC + AP2) binary governance. It works, but doesn't show confidence or fairness.

**GH4 adds (by Jul 23):**
Learned confidence scores. Every decision gets a score (0.0-1.0). Low score → human review. High score → trusted decision. Proves governance is auditable.

**GH5 adds (by Jul 25):**
Fairness constraints. Approval rates equal across risk classes (≤10% difference). Zero discrimination. Proves governance is fair + compliant with EU AI Act.

**GH6 integrates (Jul 26-30):**
Run 3-customer pilot with both confidence + fairness live. Collect metrics (0.78 confidence, 0 violations, 85% cache, 21% token savings). Sign 2-3 LOIs.

**Series A closes (Aug 15):**
Investor call: "We have 3 customers, metrics prove our governance works, LOIs signed for Aug-Oct pilots. Raising €10M to deploy to 10+ customers."

**Result:** €12-16M Year 1 runway (€10M equity + €2-6M pilot ARR).

---

**Document Owner:** You (Coordinator)  
**Status:** Ready for execution  
**Next:** Distribute to GH4-GH5 agents (Jul 16 morning)  
**Questions?** Slack #governance-pipeline or Slack @founder
