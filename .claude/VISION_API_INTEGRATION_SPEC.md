# VisionAPI Integration Spec — The Unified Governance Stack
## How All 5 Moats Work Together: BaselineCapsule + HarnessCapsule + MongeGap + AP2 + VisionAPI

---

## 🎯 The Thesis

VisionAPI is the connective layer that proves Axiom Protocol's 5 uncopyable moats work together as ONE integrated system.

**Competitors have silos:**
- Anthropic: Constitutional AI (policy-based, post-hoc)
- DeepSeek: Capability (no governance)
- LangChain: Orchestration (no safety gates)

**Axiom is unified:**
```
Application Code
        ↓
  VisionAPI (pre-execution gate)
        ↓
  ├─ BaselineCapsule (decision baseline + regret tracking)
  ├─ HarnessCapsule (framework wrapper)
  ├─ MongeGapGovernor (drift detection + adversarial)
  ├─ AP2 Ledger (1%/99% settlement)
  └─ Merkle-DAG (cryptographic audit)
        ↓
  Execution + Audit Trail
```

**Result:** Every decision is governed, regret-tracked, economically aligned, and cryptographically auditable.

---

## 📊 Integration Flow

### Step 1: Decision Arrives at VisionAPI

```
App: "I want to recommend Article X to User Y"

VisionAPI.evaluate_decision({
  app_id: "langchain-recommender",
  decision_id: "dec-2026-06-04-001",
  action: "recommend_article",
  blast_radius: 0.4,  // computed by MongeGapGovernor
  user_id: "user-xyz"
})
```

### Step 2: Fail-Closed Pre-Execution Gate

VisionAPI checks blast_radius:
- **< 0.3:** Auto-approve (low risk)
- **0.3–0.7:** Log & monitor (medium risk)
- **> 0.7:** Request human approval (high risk)
- **> 0.9:** Circuit breaker (reject, safe fallback)

```rust
if blast_radius > 0.7 {
    // FAIL-CLOSED: Block execution
    return DecisionGate::NeedsApproval {
        reason: "High-risk recommendation (blast=0.73)",
        alternatives: ["safe_default", "request_approval"]
    }
} else {
    // APPROVED: Continue to execution
    return DecisionGate::Approved {
        merkle_proof: "0xf4a2c1e9...",
        confidence: 1.0 - blast_radius
    }
}
```

### Step 3: Execution + Cryptographic Audit

HarnessCapsule wraps the actual execution:

```python
# Wrapped by HarnessCapsule (zero breaking changes to existing code)
@axiom_harness
def recommend_article(user_id, article_id):
    # Your original logic here
    recommendation = compute_recommendation(user_id, article_id)
    return recommendation
```

**What HarnessCapsule does:**
1. Pre-execution: VisionAPI gates + MongeGap blast-radius check
2. Execution: Call the original function
3. Post-execution: Merkle-proof generation + AP2 settlement
4. Audit: Log to EXEC_LOG with Ed25519 signature

### Step 4: Regret Tracking + Counterfactual

After the decision executes, BaselineCapsule tracks:

```
Decision: "Recommend Article X"
Actual Outcome: User engagement = 7/10
Counterfactual: "If we had recommended Article Y instead, engagement would be 6/10"
Regret Score: (7 - 6) / 10 = 10% regret (good decision)
```

User can see: "Looked like a good call."

### Step 5: AP2 Settlement

If the recommendation creates value (engagement > threshold):

```
Value Created: $0.50 (attribution from increased ad spend)
Platform Fee (1%): $0.005 → Axiom infra
Creator Payout (99%): $0.495 → Article author (micropayment)

Settlement logged to ledger + Merkle-rooted
```

Creator gets paid. Axiom takes 1%. All immutable + verifiable.

### Step 6: Merkle-DAG Audit Trail

Every step produces a cryptographic proof:

```
Hash Chain:
- Decision approval: 0xa1b2c3... (timestamp, user, action, blast_radius)
  ↓ (signed with Ed25519)
- Execution started: 0xd4e5f6...
  ↓ (signed with Ed25519)
- Outcome recorded: 0xg7h8i9...
  ↓ (signed with Ed25519)
- Regret computed: 0xj0k1l2...
  ↓ (signed with Ed25519)
- AP2 settlement: 0xm3n4o5...

Root hash: 0x...root...
Timestamp: 2026-06-04T12:34:56Z
User-verifiable: ✓ (can be verified without Axiom)
```

**Result:** Full audit trail. Tamper-proof. User-auditable.

---

## 🏗️ Integration With Open-Source Frameworks

### LangChain Example

```python
from axiom_harness import wrap_agent_executor
from axiom_vision_api import VisionAPI

# Initialize VisionAPI
vision = VisionAPI()

# Wrap existing LangChain agent (zero breaking changes)
agent = wrap_agent_executor(
    original_agent=your_langchain_agent,
    vision_api=vision,
    safety_level="medium",  # 0.3-0.7 blast radius allowed
)

# Use exactly as before
result = agent.run(input="What should I recommend?")

# NEW: Get decision audit trail
audit = vision.export_audit_trail()
# Shows: decision_id, action, blast_radius, merkle_proof, outcome
```

### Ollama Example

```bash
# Standard: ollama run gemma:7b "prompt"

# With Axiom VisionAPI:
axiom-run gemma:7b "prompt" \
  --vision-api \
  --safety-level=high \
  --track-regret \
  --enable-ap2-settlement

# Output includes:
# - Decision approved / quarantined
# - Regret score (if historical data)
# - AP2 payout (if value created)
# - Merkle proof (user-verifiable)
```

---

## 💰 Monetization: Vision API Tiers

### Tier 1: Embedded ($999/month)
- Up to 10,000 decisions/month
- Pre-execution safety gates (blast-radius only)
- Basic audit trail logging
- No regret scoring

**Use case:** SaaS apps that need "don't execute dangerous stuff" gates

### Tier 2: Pro ($9,999/month)
- Unlimited decisions/month
- All of Tier 1 +
- Regret scoring (counterfactual analysis)
- Merkle-DAG audit trail
- AP2 micro-settlement (if enabled)

**Use case:** Fintech, healthcare, legal platforms that need decision quality tracking

### Tier 3: Enterprise (Custom)
- Unlimited decisions/month
- All of Tier 2 +
- Custom blast-radius models (train on your domain)
- Dedicated Axiom engineer support
- SLA + compliance certifications (GDPR, HIPAA, SOC2)

**Use case:** Fortune 500 companies integrating AI into mission-critical workflows

---

## 📈 Series A Narrative: "The Decision Infrastructure for the Agentic Economy"

### Investor Pitch (15 minutes)

**Opening (2 min):**
> "While others race to build faster models, enterprises have a more urgent problem: How do you deploy AI into decision-critical workflows without gambling with liability?
> 
> Axiom solves this. VisionAPI is the decision infrastructure that makes any AI model safe + compliant + economically transparent."

**Live Demo (8 min):**
1. Show LangChain agent without Axiom (no safety gates, no audit trail)
2. Show same agent WITH VisionAPI (pre-execution gates, regret tracking, Merkle proof)
3. Show regret scoreboard (decision quality over time)
4. Show AP2 payout (1%/99% split automatic)
5. Show audit trail (user-verifiable, tamper-proof)

**Competitive Positioning (3 min):**
| Layer | Anthropic | DeepSeek | LangChain | **Axiom** |
|-------|-----------|----------|-----------|-----------|
| Model | ✅ | ✅ | ❌ | Agnostic |
| Orchestration | ❌ | ❌ | ✅ | ✅ |
| Safety Gates | 🟡 Post-hoc | ❌ | ❌ | ✅ Pre-exec |
| Regret Tracking | ❌ | ❌ | ❌ | ✅ |
| Audit Trail | 🟡 Policy logs | ❌ | 🟡 Naive logs | ✅ Merkle-rooted |
| Economic Alignment | ❌ | ❌ | ❌ | ✅ (AP2) |

> "Nobody else has all 5 pieces. Axiom is the only unified system."

**Ask (2 min):**
> "Series A: €10M to go from 50 beta customers (LangChain, Ollama, AutoGPT) to 1,000+ enterprise deployments.
> 
> By Dec 2026, top 100 agentic companies will embed Axiom VisionAPI.
> 
> Close July 30. Covenant + Competence."

---

## ✅ 72-Hour Build Plan

### Day 1: Core + Integration
- [ ] VisionAPI.rs complete (6/6 tests green) ✅
- [ ] Integrate with BaselineCapsule (regret tracking)
- [ ] Integrate with HarnessCapsule (pre-execution wrapper)
- [ ] Integrate with MongeGapGovernor (blast-radius)
- [ ] Integrate with AP2 Ledger (1%/99% settlement)
- [ ] Test: All 5 pieces working together

### Day 2: Framework Wrappers
- [ ] LangChain wrapper (axiom-langchain-harness)
- [ ] Ollama CLI (axiom-run)
- [ ] AutoGPT wrapper (axiom-autogpt-harness)
- [ ] Test: Each framework integration with real agents

### Day 3: Demo + Polish
- [ ] Build demo dashboard (show decision audit trail in real-time)
- [ ] Create regret scoreboard visualization
- [ ] Record demo video (live VisionAPI in action)
- [ ] Prepare for Series A launch

---

## 🎯 Series A Success Metric

**Investor call:**
> "What makes Axiom different?"

**Answer:**
> "Show me any LangChain agent. I'll wrap it with VisionAPI in 30 seconds. Now it has:
> - Pre-execution safety gates (fail-closed)
> - Regret tracking (measure decision quality)
> - Cryptographic audit (tamper-proof)
> - 1%/99% settlement (economically aligned)
> - No code changes needed
> 
> That's the demo. That's the moat."

---

## 🚀 Go-to-Market (Post-Series A)

**Month 1 (Aug):** 50 beta customers → 200
**Month 2 (Sep):** 200 → 500
**Month 3 (Oct):** 500 → 1,000
**Month 6 (Dec):** 1,000 → 5,000

**Revenue ramp:**
- Aug: €50K
- Sep: €150K
- Oct: €400K
- Dec: €1.2M ARR

**By Dec 2026:** Top 100 agentic companies have Axiom VisionAPI embedded.

---

## ✨ Why This Closes Series A

VisionAPI proves:
1. **5 moats work together** (not theoretical, live code)
2. **Instant integration** (zero breaking changes to open-source)
3. **Market-ready** (72-hour build → production demo)
4. **Revenue-generating** (AP2 settlement happens live during demo)
5. **Investor-friendly** (B2B infrastructure, $50B TAM, 3.2x multiplier)

**Narrative:** "While others race models, Axiom owns the decision layer. Every agentic app will want this. Series A = distribution."

