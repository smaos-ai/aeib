# TASK GH5: Safe RLHF Fairness Constraints Model Design

**Agent Role:** Design fairness-constrained value alignment for governance  
**Duration:** ~4 hours design (not implementation)  
**Research:** PKU-Alignment Safe RLHF framework  
**Due:** 2026-07-25 EOD  
**Status:** Ready for assignment (depends on GH4 completion)

---

## OBJECTIVE

Design a constrained RLHF model that enforces fairness constraints during training and inference. This model must:
- Maintain primary goal: confidence > 0.75 (from GH4)
- Subject to constraint: Pass-rate parity across risk classes (Low/Medium/High/Critical)
- Parity definition: ≤10% difference in approval rates across risk classes
- Output: Fairness metric + constraint verification per decision
- Audit trail: Every decision includes fairness constraint check result

---

## DELIVERABLE PATH

```
/Users/andriileukhin/Documents/SovereignNexus/GH5_SAFE_RLHF_CONSTRAINTS.md
```

**Format:** Fairness model specification + validation framework (NO CODE YET)  
**Length:** 2000-2500 words  
**Quality:** Regulatory-ready + investor-ready

---

## CORE PROBLEM

GH4 gives us confidence scores. But what if the model is biased?

**Scenario:** Model approves 95% of Low-risk requests but only 70% of High-risk requests.
- Technically correct per policy? Maybe.
- Fairly applied? No. Risk class shouldn't determine approval bias.
- Regulatory red flag? Yes. Explainability + auditability failing.

**Constraint:** Approval rate must be within 10% across all risk classes.
- Low-risk: 80% approval → acceptable range [70%, 90%]
- Medium-risk: 78% approval → acceptable range [70%, 90%]
- High-risk: 75% approval → acceptable range [70%, 90%]
- Critical-risk: 72% approval → acceptable range [70%, 90%]

**Solution:** Safe RLHF with fairness constraints (PKU-Alignment approach).
- Primary reward: Confidence from GH4 model
- Constraint reward: Parity penalty (punish approval rate deviations)
- Training: Optimize primary subject to constraint satisfaction
- Validation: Prove constraints hold before deployment

---

## DESIGN REQUIREMENTS (LOCKED)

### 1. Risk Classification Schema
```
RiskClass = "Low" | "Medium" | "High" | "Critical"

Determination logic:
- Low: trust_level > 75, no anomalies, within rate limits
- Medium: trust_level 50-75, minor anomalies, rate limit approaching
- High: trust_level 25-50, OR active anomaly detected
- Critical: trust_level < 25, OR critical anomaly, OR rate limit exceeded
```

### 2. Fairness Constraint Definition
```
Fairness := {
  target_parity: 0.10,  // ≤10% approval rate difference allowed
  
  approval_rate(risk_class) := 
    COUNT(decisions where risk_class AND decision="Allow") /
    COUNT(all decisions where risk_class)
  
  fairness_check(decisions) := 
    max_rate = max(approval_rate(rc) for rc in ["Low", "Medium", "High", "Critical"])
    min_rate = min(approval_rate(rc) for rc in ["Low", "Medium", "High", "Critical"])
    (max_rate - min_rate) <= target_parity
}
```

### 3. Constrained Reward Function
```
reward_primary(decision, confidence, ground_truth) = 
  [from GH4, confident > 0.75 is good]

reward_fairness(decisions_batch) =
  + 1.0 if fairness_check(decisions_batch) = true
  - 1.0 * (violation_magnitude) if fairness_check fails
  where violation_magnitude = (max_rate - min_rate - 0.10) / 0.10
  (penalty is 0 if within constraint, increases linearly if exceeds)

total_reward := 
  reward_primary (optimize primary goal)
  + lambda * reward_fairness (subject to fairness constraint)
  
  where lambda = Lagrange multiplier (adaptive)
```

### 4. Training Data Schema
```
TrainingBatch {
  decisions: Vec<GovernanceRequest + Decision + Confidence>,
  ground_truth_labels: Vec<Correctness>,
  risk_class_distribution: {
    "Low": count,
    "Medium": count,
    "High": count,
    "Critical": count,
  },
  fairness_violation_flag: bool,
  min_approval_rate: f32,
  max_approval_rate: f32,
}
```

### 5. Deployment Architecture
- **Training:** Safe RLHF with constraint enforcement
- **Inference:** Same as GH4, but with fairness verification layer
- **Constraint Check:** On every decision (blocking if fairness broken)
- **Monitoring:** Daily fairness audit (plot approval rates by risk class)

---

## DESIGN SECTIONS (REQUIRED)

### Section 1: PKU-Alignment Safe RLHF Overview (300 words)
- What is Safe RLHF? (constraint satisfaction for language models)
- Why it fits governance (fairness + safety + explainability)
- How it differs from unconstrained RLHF (Lagrange multipliers + constraint-aware loss)
- Key advantages for regulatory compliance

### Section 2: Fairness Constraint Design (400 words)
**Subsection 2a: Why Parity Matters**
- Regulatory angle: EU AI Act requires non-discrimination (Article 10)
- Business angle: Unfair bias = customer distrust = churn
- Investor angle: "We can PROVE our governance is fair"

**Subsection 2b: Parity Metric Definition**
- Definition: ≤10% difference in approval rates across risk classes
- Why 10%? (conservative, reflects real business tolerance)
- Baseline: Measure current (GH4 model) approval rates by risk class
  - If baseline already violates → flag for retraining before GH6

**Subsection 2c: Risk Class Distribution Strategy**
- Training data must include all 4 risk classes
- Minimum per class: 500 examples (sufficient for parity measurement)
- Sampling strategy: Stratified sampling (ensure all classes represented each epoch)
- Validation: Report parity metrics per class over multiple validation sets

**Subsection 2d: Fairness-Aware Loss Function**
```
Approach A: Lagrange Multiplier (recommended)
- Define constraint: g(theta) = |approval_rate_diff| - 0.10 <= 0
- Loss = primary_loss + lambda * max(0, g(theta))
- Adaptive lambda: increase if constraint violated, decrease if satisfied

Approach B: Constraint-Aware PPO
- Modify PPO to include fairness penalty in reward
- Every step: compute fairness metric, reward correct parity

Recommend: Approach A (standard in Safe RLHF literature)
```

### Section 3: Training Pipeline with Constraints (350 words)
**Subsection 3a: Data Preparation**
- Aggregate historical governance decisions (from Phase 25 audit logs)
- Label each decision with: ground truth correctness, risk class, outcome
- Filter: Ensure all 4 risk classes represented (min 500 examples each)
- Split: 80% train / 10% validation (fairness) / 10% test

**Subsection 3b: Constraint Measurement During Training**
- Every 100 steps: Compute fairness metric on validation set
- Check: Does |approval_rate_diff| <= 0.10?
- Log: Current approval rates for each risk class
- If violated: Increase lambda multiplier (penalize more)
- If satisfied: Decrease lambda (normal training resumes)

**Subsection 3c: Constraint-Aware Optimization**
```
Training loop:
1. Sample batch of governance requests (stratified by risk class)
2. Run policy (GH4 model + LoRA for fairness)
3. Compute primary reward (confidence from GH4)
4. Compute fairness constraint (approval rate parity)
5. Compute Lagrange multiplier update
6. Backprop with combined loss (primary + lambda * constraint)
7. Every 100 steps: validate fairness, update lambda
8. Stop if: constraint satisfied AND primary goal met
```

**Subsection 3d: Expected Training Time & Convergence**
- Dataset: 10K examples (2K per risk class)
- Epochs: 3-5 (fairness often converges faster than accuracy)
- Expected time: 2-4 hours on Ray cluster (same as GH4)
- Convergence criteria: Parity metric stable for 200+ steps, primary goal maintained

### Section 4: Inference & Constraint Enforcement (350 words)
**Subsection 4a: Runtime Fairness Check**
```
Inference flow:
1. Request comes in (governance decision needed)
2. Determine risk_class (Low/Medium/High/Critical)
3. Query fairness state (approval rates for all classes last 1000 decisions)
4. Run GH4 model → decision + confidence
5. Check: Would this decision violate parity if approved?
   - If yes: Flag as "fairness hold" (escalate to human)
   - If no: Proceed normally (or approve directly if confidence > 0.75)
6. Log: decision + risk_class + confidence + fairness_check_result
```

**Subsection 4b: Fairness State Management**
- Maintain rolling window: Last 1000 decisions per risk class
- Update in real-time as decisions made
- Metrics: Current approval rate per risk class
- Dashboard: Show approval rates + deviation from parity
- Alert: If deviation > 0.10 during production → escalate ops

**Subsection 4c: Constraint Verification & Audit Trail**
```
AuditEntry now includes:
{
  decision: "Allow" | "Deny",
  confidence: 0.85,
  risk_class: "Medium",
  fairness_check: "PASS" | "FAIRNESS_HOLD",
  approval_rate_low: 0.82,
  approval_rate_medium: 0.80,
  approval_rate_high: 0.79,
  approval_rate_critical: 0.78,
  parity_deviation: 0.04,  // max - min
  parity_status: "SATISFIED",  // <= 0.10
  model_version: "gh5_safe_rlhf_v1",
}
```

### Section 5: Validation & Regulatory Proof (300 words)
**Subsection 5a: Fairness Validation Harness**
```
Validation test suite:
1. Load historical governance decisions (10K examples)
2. Stratify by risk class
3. Run model on all 10K → decisions + confidence + fairness metrics
4. For each risk class:
   - Count approvals / total requests
   - Compute approval rate
   - Compare to target (within ≤10%)
5. Report: Table of approval rates by risk class
6. Verdict: "Fair" if all rates within 0.10 range, "Biased" otherwise
```

**Subsection 5b: Regulatory Compliance Story**
- EU AI Act Article 10: "Non-discrimination" → We measure parity + publish results
- GDPR Article 22: "Right to explanation" → Confidence + fairness score included
- SOx Section 302: "Management assessment of controls" → Fairness audit trail
- Customer trust: "Here's proof our governance is fair"

**Subsection 5c: Customer-Facing Metrics**
- Dashboard metric: "Fairness score" (0.0-1.0, higher = fairer)
- Calculation: 1.0 - (parity_deviation / 0.10) clamped to [0, 1]
- Interpretation: 1.0 = perfect parity, 0.0 = extreme bias
- SLA: Fairness score >= 0.80 at all times (or escalate)

### Section 6: Series A Narrative (200 words)
**Subsection 6a: Investor Story**
- "We build governance that's not just accurate, but FAIR."
- "Every decision is constrained: approval rates must be equal across risk classes."
- "Fairness is measured, monitored, and audited."
- "This regulatory advantage differentiates us from competitors."

**Subsection 6b: Competitive & Regulatory Positioning**
- Competitors: No fairness constraints (black box, biased risk)
- We: Transparent fairness (measured + certified)
- Regulatory advantage: EU AI Act + GDPR compliance story
- Customer advantage: Risk mitigation (no discrimination lawsuits)

**Subsection 6c: Customer Value**
- "Know your governance is fair."
- "Measure fairness daily."
- "Prove fairness to auditors + regulators."
- "Confidence in your AI decisions."

---

## RESEARCH TASKS (YOU MUST DO)

### Task 1: Safe RLHF Framework (1.5 hours)
Research PKU-Alignment Safe RLHF: https://github.com/PKU-Alignment/safe-rlhf

Read:
1. README + approach overview
2. Constraint definition pattern (how do they define constraints?)
3. Training loop (Lagrange multiplier implementation)
4. Examples (any governance or fairness examples?)

Document findings:
- How does Safe RLHF enforce constraints?
- What's the Lagrange multiplier update mechanism?
- Typical constraint examples (safety, helpfulness, fairness)?
- How to measure constraint satisfaction during training?

### Task 2: Fairness in AI Systems (1 hour)
Research fairness definitions + measurement:
- What is demographic parity? (vs equalized odds, calibration, etc.)
- Why parity is appropriate for governance (not just accuracy)
- How to measure fairness violations (AIF360, FAT/ML tools)
- Real-world case studies (Amazon hiring bias, COMPAS, etc.)

Document findings:
- Definition of fairness you'll use (demographic parity recommended)
- Why 10% threshold is reasonable
- How to present fairness to non-technical stakeholders

### Task 3: Fairness Validation Methodologies (1 hour)
Research how to validate fairness:
- How do ML engineers test for bias post-training?
- Fairness audit tools (IBM AIF360, Google What-If, Fairlearn)
- Statistical tests (disparate impact analysis, Fisher's exact test)
- Ongoing monitoring strategies (dashboard metrics, alert thresholds)

Document findings:
- Recommended validation test suite
- How to compute fairness metrics (approval rates by risk class)
- How to present fairness audit to regulators

### Task 4: Regulatory Compliance Framing (0.5 hours)
Research regulatory requirements for AI fairness:
- EU AI Act Article 10: Non-discrimination requirement
- GDPR Article 22: Right to explanation
- Sector-specific: FCRA (finance), HITECH (healthcare)
- What regulators want to see (proof of fairness testing)

Document findings:
- How to frame GH5 as regulatory compliance story
- What documentation regulators expect
- Customer value (risk mitigation)

---

## SPECIFICATION STRUCTURE (YOUR OUTPUT)

```markdown
# GH5: Safe RLHF Fairness Constraints Model Design

## Executive Summary (150 words)
Summarize fairness-constrained RLHF approach in 2-3 paragraphs.

## 1. Problem Statement (200 words)
Confidence scores alone don't guarantee fairness.
Need fairness constraints + measurement.

## 2. Solution Overview (300 words)
Safe RLHF with parity constraints.
Approval rates ≤10% difference across risk classes.

## 3. Architecture Design (1200 words)
3a. PKU-Alignment Safe RLHF Overview
3b. Fairness Constraint Design
3c. Training Pipeline with Constraints
3d. Inference & Constraint Enforcement
3e. Validation & Regulatory Proof

## 4. Integration with GH4 (200 words)
How does GH5 layer on top of GH4 confidence scores?
Where does fairness check sit in inference flow?

## 5. Fairness Validation Harness (250 words)
Step-by-step validation test suite.
How to prove fairness to regulators/customers.

## 6. Metrics & Success Criteria (150 words)
For GH6 pilot:
- Fairness violations: 0 (perfect)
- Approval rate parity: ≤10% difference
- Fairness score: ≥0.80 (dashboard metric)

## 7. Regulatory Compliance Story (200 words)
Why this matters for EU AI Act, GDPR, FCRA, etc.
Customer + investor narrative.

## 8. Implementation Sketch (250 words)
Pseudo-code or algorithm for constraint-aware training.
(NO FULL CODE, just structure)

## 9. Open Questions & Risks (150 words)
- What if fairness constraint conflicts with accuracy?
- How to handle adversarial attempts to game fairness metric?
- Real-time fairness enforcement cost?

## Appendix: Research Findings
Document Safe RLHF, fairness metrics, regulatory requirements.
Include links to frameworks + tools.
```

---

## SUCCESS CRITERIA (GRADED)

| Criterion | Weight | Details |
|-----------|--------|---------|
| **Fairness Design** | 25% | Parity metric well-defined, ≤10% threshold justified |
| **Safe RLHF Integration** | 25% | Constraint mechanism clear, Lagrange multiplier explained |
| **Regulatory Framing** | 20% | EU AI Act + GDPR compliance story compelling |
| **Validation Completeness** | 15% | Validation harness is testable + auditable |
| **Investor Readiness** | 15% | Competitive advantage + customer value clear |

**Overall Quality Bar:** ≥8/10 required. <7/10 = re-work needed.

---

## CRITICAL NOTES FOR SUCCESS

1. **This is DESIGN, not implementation.** Focus on fairness model + validation framework. No code.
2. **Research fairness deeply** (2-2.5 hours). Understand constraints + measurement before writing spec.
3. **Regulatory angle is CRITICAL.** GH5 is the "proof of fairness" story for Series A. Make it compelling.
4. **Integration with GH4 must be seamless.** GH5 layers on top (same confidence scores, + fairness gate).
5. **Validation harness must be auditable.** Regulators will want to see fairness test results. Design accordingly.
6. **10% parity threshold should be justified.** Why not 5%? Why not 15%? Explain the choice.

---

## DEPENDENCY & SEQUENCING

**GH5 depends on GH4.** 
- Wait for GH4_OPENRLHF_PIPELINE.md to be posted before finalizing GH5
- Once GH4 is ready, GH5 can start immediately (parallel work with coordinator review)
- Deliver GH5 by Jul 25 EOD

**GH6 depends on both GH4 + GH5.**
- Coordinator integration: Jul 26 (both specs ready for pilot)
- Pilot execution: Jul 26-30

---

## COMPLETION STEPS

### After Design is Complete:

1. **Peer Review with GH4 Agent** (optional, 30 min)
   - Ensure GH4 + GH5 integrate smoothly
   - GH4 confidence → GH5 fairness constraint
   - No conflicts in audit trail design

2. **Quality Score** (you)
   - Self-grade against 5 success criteria above
   - If <8/10 on any, revise before posting

3. **Post Completion Comment** (on task #[GH5])
   ```
   GH5 COMPLETED — Safe RLHF Fairness Constraints Design

   Deliverable: /Users/andriileukhin/Documents/SovereignNexus/GH5_SAFE_RLHF_CONSTRAINTS.md

   Summary:
   - Fairness constraint: ≤10% approval rate parity across risk classes
   - Integration: Layers on GH4 confidence (same model, + fairness gate)
   - Validation: Regulatory-auditable fairness test suite included
   - Status: Ready for GH6 pilot coordination (Jul 26+)

   Design quality: [X]/10
   Regulatory ready: Yes
   Investor ready: Yes
   Next: GH6 integrated pilot execution (all 5 features)
   ```

---

**Agent Owner:** GH5 Agent (assigned after GH4 complete, ~Jul 23)  
**Due Date:** 2026-07-25 EOD  
**Status:** Blocked on GH4 completion (estimated ~Jul 23)  
**Slack Channel:** #fairness-constraints (for questions)
