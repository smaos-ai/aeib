# TASK GH4: OpenRLHF Evaluation Pipeline Design

**Agent Role:** Design RLHF governance confidence scoring pipeline  
**Duration:** ~6 hours design (not implementation)  
**Research:** https://github.com/OpenLMLab/OpenRLHF  
**Due:** 2026-07-23 EOD  
**Status:** Ready for assignment

---

## OBJECTIVE

Design a complete ML-learned governance evaluation pipeline that replaces binary (Allow/Deny) decisions with learned confidence scores. This pipeline must:
- Accept governance requests (context, policy, risk class)
- Output confidence scores 0.0-1.0 for policy decisions
- Integrate as pre-execution gate (reject if confidence < 0.75 threshold)
- Meet <10ms latency requirement (Tier1 SLO)
- Be implementable on Ray distributed training (Nebius H100s) with ONNX Runtime inference (Mac Studio)

---

## DELIVERABLE PATH

```
/Users/andriileukhin/Documents/SovereignNexus/GH4_OPENRLHF_PIPELINE.md
```

**Format:** Architecture design spec + implementation sketch (NO CODE YET)  
**Length:** 2000-2500 words  
**Quality:** Investor-ready (clear, technical, data-driven)

---

## CORE PROBLEM

Current governance pipeline (Phase 25: ReBAC + AP2) makes binary decisions: "Allow" or "Deny".

**Problem:** Binary decisions hide uncertainty.
- Policy engine says "Allow" → but confidence only 0.65?
- What if we had 1000 decisions, 650 wrong?
- Investors ask: "How do you KNOW your governance is safe?"

**Solution:** RLHF-learned confidence scores.
- Same pipeline (ReBAC, AP2, TemporalGuard)
- Same decision (Allow/Deny)
- PLUS: Confidence score 0.0-1.0 from learned model
- Audit trail: "Decision: Allow | Confidence: 0.85 | Audit ID: abc123"
- Gate: If confidence < 0.75 → escalate to human reviewer

---

## DESIGN REQUIREMENTS (LOCKED)

### 1. Input Schema
```
GovernanceRequest {
  requester_id: UUID,          // Who is asking?
  action: PolicyAction,        // What do they want (approve_spending, delegate_role, etc.)?
  resource: PolicyResource,    // What are they asking about?
  context: RequestContext {
    sovereign_trust_level: 0-100,
    anomaly_severity: "low" | "medium" | "high" | "critical",
    time_window_allowed: bool,
    rate_limit_ok: bool,
    relationship_verified: bool,
    historical_decisions_by_requester: Vec<(action, decision, confidence)>,  // Last 50
  }
}
```

### 2. Output Schema
```
ConfidenceScoreResult {
  decision: "Allow" | "Deny",
  confidence: f32,              // 0.0 - 1.0
  explanation: Vec<String>,     // Why? Which rules fired?
  audit_id: UUID,
  inference_latency_ms: f32,
  model_version: String,
}
```

### 3. Deployment Architecture
- **Training:** Ray on Nebius H100s (distributed RLHF)
- **Inference:** ONNX Runtime on Mac Studio (96GB)
- **Latency requirement:** p99 < 10ms
- **Confidence threshold:** 0.75 (gate enforcement)

### 4. Training Data Schema
```
TrainingExample {
  features: GovernanceRequest,
  ground_truth_decision: "Allow" | "Deny",
  expert_confidence: 0.0-1.0,    // From human review
  outcome_label: "correct" | "incorrect" | "escalated",
  reward_signal: f32,             // RL reward (1.0 = correct, 0.5 = escalated, 0.0 = wrong)
}
```

---

## DESIGN SECTIONS (REQUIRED)

### Section 1: OpenRLHF Framework Overview (300 words)
- What is OpenRLHF? (briefly)
- Why it fits this problem (RLHF for governance is industry standard)
- How it compares to alternatives (SFT-only, rule-based, other RLHF frameworks)
- Key advantages for governance: interpretability + uncertainty quantification

### Section 2: Governance Model Architecture (400 words)
**Subsection 2a: Base Model Choice**
- Recommendation: Phi-3 mini (2.7B, <200MB ONNX)
- Why? (speed, latency, accuracy for policy decisions)
- Alternative: Llama-2 7B (consider trade-offs)

**Subsection 2b: LoRA Fine-Tuning Strategy**
- LoRA rank: suggest 8-16 (low-rank approximation)
- Learning rate: suggest 5e-4
- Why LoRA? (efficient, <100MB additional weights)

**Subsection 2c: RLHF Reward Model**
```
reward(decision, confidence, ground_truth) = 
  + 1.0 if (decision correct AND confidence > 0.75)
  + 0.5 if (decision correct AND confidence 0.5-0.75)
  - 0.5 if (decision wrong AND confidence high)
  - 1.0 if (decision wrong AND confidence > 0.9)
```

**Subsection 2d: Policy Optimization**
- Algorithm: PPO (Proximal Policy Optimization)
- KL penalty: 0.05 (prevent drift from base model)
- Why PPO? (stable, sample-efficient, used in Claude)

### Section 3: Training Pipeline (350 words)
**Subsection 3a: Data Collection Strategy**
- Source: Historical governance decisions (Phase 25 audit logs)
- Labeling: Expert review (human confidence + outcome verification)
- Minimum dataset: 10,000 examples
- Confidence calibration: Ensure labels are well-calibrated

**Subsection 3b: Ray Distributed Training**
- Setup: Ray cluster on Nebius (N GPU workers, each H100)
- Batch size: 32 per GPU (scale to cluster size)
- Distributed RLHF: vLLM for generation, Ray remote actors for reward model
- Checkpointing: Every 500 steps to S3
- Expected training time: 2-4 hours (10K examples, 3 epochs)

**Subsection 3c: Validation Strategy**
- Hold-out test set: 10% of data
- Metrics: Calibration error, accuracy, confidence AUC
- Calibration test: Compare predicted vs actual confidence
- Goal: Mean calibration error < 0.05

### Section 4: Inference Deployment (350 words)
**Subsection 4a: ONNX Runtime Conversion**
- Export: PyTorch → ONNX (with LoRA merged)
- Runtime: ONNX Runtime CPU (Mac Studio, no GPU needed for <10ms requirement)
- Quantization: INT8 (reduces model size 4x, <50MB)
- Verification: Compare ONNX outputs vs PyTorch (diff <1e-4)

**Subsection 4b: Latency Budget (p99 < 10ms)**
```
Token generation (max 5 tokens):    6-7 ms
Tokenization + post-processing:     1-2 ms
Request overhead:                   1-2 ms
Total p99:                          9-10 ms
```

**Subsection 4c: Integration with Phase 25 Pipeline**
- Hook point: After TemporalGuard check (just before decision cache)
- If confidence < 0.75 → flag for human review (return "Pending" instead of "Deny")
- If confidence >= 0.75 → proceed with cached decision
- Audit trail: Include confidence + model version in audit log

### Section 5: Monitoring & Continuous Learning (300 words)
**Subsection 5a: Telemetry**
- Collect: Every governance request + final decision + user feedback (escalation, correction)
- Metrics dashboard: Confidence distribution, calibration drift, accuracy by risk class
- Alerting: If calibration error > 0.10 or accuracy drops >5%

**Subsection 5b: Model Retraining Schedule**
- Weekly lightweight validation (1000 new examples)
- Monthly full retraining (accumulate 50K examples, 1 epoch)
- Trigger: If accuracy drops or calibration drifts

**Subsection 5c: A/B Testing Strategy**
- Compare: Old binary pipeline vs new confidence pipeline
- Metric: Does higher confidence → higher correctness? (correlation > 0.7)
- Rollout: 10% → 50% → 100% over 2 weeks

### Section 6: Series A Narrative (250 words)
**Subsection 6a: Investor Story**
- "We move from binary decisions to learned confidence."
- "Every governance decision includes a confidence score."
- "Decisions below 0.75 confidence are escalated to humans."
- "This proves our governance is auditable AND trustworthy."

**Subsection 6b: Competitive Advantage**
- Competitors: Black-box RLHF (confidence scores are private)
- We: Transparency (confidence scores visible + auditable)
- Regulatory appeal: Explainability + auditability

**Subsection 6c: Customer Value**
- "Know the confidence of every governance decision."
- "Use confidence as a business metric (when do we need escalation?)."
- "Calibrate escalation thresholds by risk tolerance."

---

## RESEARCH TASKS (YOU MUST DO)

### Task 1: OpenRLHF Deep Dive (2 hours)
Visit https://github.com/OpenLMLab/OpenRLHF. Read:
1. README + architecture overview
2. Example training script (look for PPO implementation)
3. Inference setup (how do they do deployment?)
4. LLM fine-tuning patterns (LoRA config, reward model)

Document findings:
- How does OpenRLHF structure the RLHF pipeline?
- What are typical model sizes? Training times?
- How do they handle reward model training?
- What inference frameworks do they use?

### Task 2: Policy-as-Text Modeling (1 hour)
Research how to represent governance policies as model input:
- Format policy rules as structured text
- Compress historical decisions into context (last 50 decisions per requester)
- Design confidence token (how does model output confidence?)

Option A: Add special token `[CONFIDENCE: X.XX]` to prompt
Option B: Use token probability distribution (argmax class + softmax confidence)
Option C: Separate scoring head (predict confidence as regression)

Recommend which approach is best for governance.

### Task 3: Ray Training Architecture (1.5 hours)
Research Ray cluster setup for RLHF:
- How to scale RLHF training across multiple H100s?
- What's the standard batch size + gradient accumulation strategy?
- How do distributed reward models work?
- Checkpoint format + S3 integration?

Document findings:
- Ray setup (how many GPUs, batch sizes)?
- Distributed RLHF best practices
- Expected training time estimate (for 10K examples)

### Task 4: ONNX Runtime Optimization (1 hour)
Research latency optimization for CPU inference:
- How to convert PyTorch→ONNX with LoRA?
- What quantization strategy (FP32, FP16, INT8)?
- How to achieve <10ms inference on Mac Studio CPU?
- Benchmarking methodology (measure p99, not average)

Document findings:
- Model size before/after quantization
- Latency before/after quantization
- ONNX conversion gotchas (LoRA merging, token generation)

### Task 5: Calibration & Monitoring (1 hour)
Research how to ensure confidence scores are well-calibrated:
- What's calibration error? (how to measure?)
- Calibration tests (Brier score, ECE)?
- How to detect calibration drift in production?
- Confidence as a business metric (what drives escalation rates?)

---

## SPECIFICATION STRUCTURE (YOUR OUTPUT)

```markdown
# GH4: OpenRLHF Governance Pipeline Design

## Executive Summary (150 words)
Summarize the entire approach in 2-3 paragraphs.

## 1. Problem Statement (200 words)
Binary decisions hide uncertainty. RLHF-learned confidence fixes it.

## 2. Solution Overview (300 words)
Same pipeline, + confidence scores from learned model.
Include diagram (ASCII or link to external image).

## 3. Architecture Design (1200 words)
3a. OpenRLHF Framework Overview
3b. Governance Model Architecture
3c. Training Pipeline
3d. Inference Deployment
3e. Monitoring & Continuous Learning

## 4. Integration with Phase 25 (200 words)
How does GH4 hook into ReBAC + AP2 + TemporalGuard?
Where does confidence score sit in audit trail?

## 5. Metrics & Success Criteria (150 words)
What's the success metric for GH6 pilot?
- Mean confidence 0.75+ → PASS
- Calibration error < 0.10 → PASS
- p99 latency < 10ms → PASS

## 6. Implementation Sketch (300 words)
Pseudo-code or step-by-step for training pipeline.
(NO FULL CODE, just structure)

## 7. Series A Narrative (250 words)
Why this matters for investors.
Competitive advantage + customer value.

## 8. Open Questions & Risks (150 words)
- What if 10K training examples isn't enough?
- How to handle adversarial attacks on confidence scores?
- What's the cost of running Ray cluster?

## Appendix: Research Findings
Document your OpenRLHF, Ray, ONNX findings.
Include links to key resources.
```

---

## SUCCESS CRITERIA (GRADED)

| Criterion | Weight | Details |
|-----------|--------|---------|
| **Architecture Completeness** | 25% | All 5 sections present, no gaps, design is coherent |
| **Technical Depth** | 25% | Research is thorough (OpenRLHF, Ray, ONNX, calibration) |
| **Integration Clarity** | 20% | Clear how GH4 hooks into Phase 25 pipeline |
| **Investor Readability** | 15% | Non-technical summary + narrative is compelling |
| **Practicality** | 15% | Design is actually implementable (not theoretical) |

**Overall Quality Bar:** ≥8/10 required. <7/10 = re-work needed.

---

## DELIVERABLE CHECKLIST

Before posting completion comment:

- [ ] Document is 2000-2500 words
- [ ] All 6 sections complete and coherent
- [ ] Research findings documented (OpenRLHF, Ray, ONNX, calibration)
- [ ] Architecture diagram included (ASCII or linked)
- [ ] Success metrics clearly stated for GH6 pilot
- [ ] Integration with Phase 25 pipeline is explicit
- [ ] Series A narrative is investor-ready
- [ ] No placeholder text or "TODO" sections
- [ ] Spell-checked + grammar-checked
- [ ] Follows formatting from GH1/GH2/GH3 docs

---

## COMPLETION STEPS

### After Design is Complete:

1. **Peer Review** (optional, 30 min)
   - Ask GH6 coordinator (founder) to review
   - Get feedback on: practicality, investor narrative, metrics

2. **Quality Score** (you)
   - Self-grade against 5 success criteria above
   - If <8/10 on any, revise before posting

3. **Post Completion Comment** (on task #[GH4])
   ```
   GH4 COMPLETED — OpenRLHF Governance Pipeline Design

   Deliverable: /Users/andriileukhin/Documents/SovereignNexus/GH4_OPENRLHF_PIPELINE.md

   Summary:
   - Architecture: [brief 1-liner]
   - Key metric: Confidence scores 0.75+ required for GH6 pilot
   - Integration: Hooks into Phase 25 TemporalGuard (confidence gating)
   - Status: Ready for GH5 sequencing + GH6 pilot coordination

   Design quality: [X]/10
   Investor ready: Yes/No
   Next: GH5 Safe RLHF (fairness constraints)
   ```

---

## CRITICAL NOTES FOR SUCCESS

1. **This is DESIGN, not implementation.** Focus on architecture + research. No code needed.
2. **Invest heavily in research** (5 hours). Understand OpenRLHF + Ray before writing spec.
3. **Think like an investor.** Why does confidence scoring matter? What's the competitive advantage?
4. **Be concrete about numbers.** Not "it will be fast" → "<10ms p99 latency on Mac Studio CPU."
5. **Architecture must integrate** with Phase 25 cleanly. Don't design in isolation.
6. **Series A narrative is critical.** This is demo #4 of 5. Make it compelling.

---

**Agent Owner:** GH4 Agent (assigned Jul 16)  
**Due Date:** 2026-07-23 EOD  
**Status:** Ready for research + design  
**Slack Channel:** #governance-pipeline (for questions)
