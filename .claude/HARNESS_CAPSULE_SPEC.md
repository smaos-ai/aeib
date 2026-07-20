# HarnessCapsule — Constitutional Wrapper for Agent Frameworks
## Connector Spec v1.0 — LangChain, Ollama, AutoGPT Compatible

---

## 🎯 Purpose

Wrap any open-source agent framework (LangChain, Ollama, AutoGPT, CrewAI) under Axiom Protocol governance WITHOUT requiring rewrites. Pre-execution safety gates + cryptographic audit trail + 1%/99% settlement layer.

**Dramatically Different:** Instead of forking or competing with open-source tools, HarnessCapsule makes them trustworthy—adding sovereignty without sacrificing flexibility.

---

## 🏗️ Architecture

```
Agent Framework (LangChain, Ollama, etc.)
        ↓
  HarnessCapsule
        ↓
┌─────────────────────────────────────┐
│ 1. Pre-Execution Safety Gate        │ ← Fail-closed invariant validation
│ 2. Blast-Radius Scoring             │ ← MongeGapGovernor + temporal decay
│ 3. Cryptographic Approval Layer     │ ← Ed25519 human gate for high-risk
│ 4. AP2 Settlement Stub              │ ← 1%/99% micro-royalty enforcement
│ 5. Merkle-DAG Provenance            │ ← Immutable audit trail
│ 6. Post-Execution Verification      │ ← Result integrity check
└─────────────────────────────────────┘
        ↓
    Execution ✓
```

---

## 📋 Interfaces

### 1. HarnessCapsule::wrap()
**Input:** Any agent action (tool call, decision, output)  
**Output:** SafetyDecision (Approved | Quarantined | CircuitBreaker)

```rust
pub trait HarnessCapsule {
    fn wrap(&self, agent_action: AgentAction) -> SafetyDecision;
}

pub enum SafetyDecision {
    Approved {
        action: AgentAction,
        merkle_proof: String,
        timestamp: u64,
    },
    Quarantined {
        reason: String,
        blast_radius: f64,
        fallback_action: Option<AgentAction>,
    },
    CircuitBreaker {
        breach_count: usize,
        safe_mode_activated: bool,
    },
}
```

---

## 🔧 Implementation Path (Per Framework)

### LangChain Integration
**Module:** `axiom-langchain-harness`

```python
from langchain.agents import AgentExecutor
from axiom_harness import HarnessCapsule

class AxiomAgentExecutor(AgentExecutor):
    def __init__(self, *args, harness: HarnessCapsule, **kwargs):
        super().__init__(*args, **kwargs)
        self.harness = harness
    
    def _call(self, inputs, **kwargs):
        # Standard LangChain flow...
        for step in self.agent.plan():
            # 1. Pre-execution gate
            decision = self.harness.wrap(step.action)
            
            if decision.status == "APPROVED":
                result = step.execute()
                # 2. Post-execution verification
                verified = self.harness.verify_result(result)
                if verified:
                    yield result
                else:
                    # Fallback to safe policy
                    yield decision.fallback_action
            
            elif decision.status == "QUARANTINED":
                # Log breach, execute fallback
                yield decision.fallback_action
            
            elif decision.status == "CIRCUIT_BREAKER":
                # Stop agent, activate safe mode
                return self._safe_mode()
```

**Integration effort:** ~2-3 days (add 500 LOC wrapper, zero LangChain changes)

---

### Ollama Integration
**Module:** `axiom-ollama-harness`

Ollama is a local model runtime. HarnessCapsule wraps the inference loop:

```bash
# Standard: ollama run gemma:7b "prompt"
# Axiom:   axiom-run gemma:7b "prompt" --harness-capsule --safety-level=high
```

**Key differences:**
- Pre-execution: Compute safety score for prompt embedding
- Inference: Monitor for out-of-distribution tokens (MongeGap drift detection)
- Post-execution: Verify output confidence; reject if below threshold

**Integration effort:** ~1-2 days (add CLI wrapper + inference hook)

---

### AutoGPT Integration
**Module:** `axiom-autogpt-harness`

AutoGPT executes multi-step tasks autonomously. HarnessCapsule adds human-in-the-loop gates:

```python
class AxiomAgent(BaseAgent):
    def execute_step(self, step):
        # 1. Compute blast radius for this step
        blast = self.harness.compute_blast_radius(step)
        
        # 2. If high-risk (blast > threshold), request approval
        if blast > 0.7:
            approval = self.human_gate.request_approval(step)
            if not approval.verified:
                return self.harness.fallback(step)
        
        # 3. Execute with monitoring
        result = super().execute_step(step)
        
        # 4. Verify result integrity
        verified = self.harness.verify_result(result)
        return result if verified else self.harness.fallback(step)
```

**Integration effort:** ~3-4 days (add blast-radius + human-gate modules)

---

## 🛡️ Safety Geometry Covenant

Every HarnessCapsule wrapper enforces:

| Invariant | Implementation | Verification |
|-----------|---------------|--------------|
| **Fail-Closed** | Pre-execution gate blocks unsafe actions; fallback is safe default | Unit tests: test_high_blast_radius_blocks, test_quarantine_blocks |
| **Cryptographic Audit** | Every wrapped action logged with Ed25519 signature + Merkle root | Integration test: test_audit_trail_verifiable |
| **1%/99% Settlement** | AP2 stub routes micro-royalties: 1% to Axiom infra, 99% to creators/sources | Test: test_ap2_settlement_enforced |
| **Human Sovereignty** | Human gate required for high-risk actions; non-bypassable | Test: test_human_gate_required_for_blast_radius_gt_0.7 |
| **Local-First Execution** | All gates run locally; zero cloud escalation for critical decisions | Test: test_offline_capability |

---

## 📊 Blast Radius Scoring (MongeGapGovernor Integration)

```rust
pub fn compute_blast_radius(action: &AgentAction) -> f64 {
    let base_score = match action.action_type {
        ActionType::ToolCall => 0.3,
        ActionType::DataAccess => 0.5,
        ActionType::StateChange => 0.7,
        ActionType::FinancialTransaction => 0.9,
    };
    
    // Apply temporal decay: older actions have lower blast radius
    let age_seconds = now() - action.timestamp;
    let decay_factor = 1.0 - (age_seconds as f64 / 86400.0).min(0.5);  // max 50% decay
    
    let decayed_score = base_score * decay_factor;
    
    // Check adversarial injection: has this action pattern appeared suspiciously often?
    let injection_penalty = check_adversarial_pattern(action);
    
    (decayed_score + injection_penalty).min(1.0)
}
```

**Thresholds:**
- **≤ 0.3:** Auto-approve
- **0.3–0.7:** Log & monitor
- **0.7–0.9:** Request human approval
- **≥ 0.9:** Quarantine, activate safe mode

---

## 🔌 AP2 Settlement Stub

Every wrapped action that succeeds generates a micro-royalty:

```rust
pub struct AP2Settlement {
    pub action_id: String,
    pub value_created: f64,           // estimated value (e.g., tokens generated, queries answered)
    pub axiom_fee: f64,               // 1% to Axiom infra
    pub creator_payout: f64,          // 99% to creator/source
    pub timestamp: u64,
}

impl AP2Settlement {
    pub fn settle(&self) {
        // Log to immutable ledger
        ledger.record(&self);
        
        // Route payments
        transfer(creator_wallet, self.creator_payout);
        transfer(axiom_wallet, self.axiom_fee);
        
        // Merkle-root for audit
        merkle_proof = compute_proof(&self);
        exec_log.append(merkle_proof);
    }
}
```

---

## 📦 Rollout (Prioritized)

### Phase 1: LangChain (Week 1)
- [ ] `axiom-langchain-harness` crate created
- [ ] Wrap `AgentExecutor._call()` with pre-execution gate
- [ ] Add MongeGapGovernor + AP2 settlement stub
- [ ] Unit tests: 8/8 green
- [ ] Demo: LangChain ReAct agent with Axiom safety gates

### Phase 2: Ollama (Week 2)
- [ ] `axiom-ollama-harness` CLI wrapper
- [ ] Integrate MongeGap drift detection for inference
- [ ] Local-only execution (zero cloud escalation)
- [ ] Demo: Gemma 7B running under Axiom governance on M3 Pro

### Phase 3: AutoGPT (Week 3)
- [ ] `axiom-autogpt-harness` wrapper
- [ ] Human gate for multi-step autonomous execution
- [ ] Circuit breaker after 3 quarantine events
- [ ] Demo: Multi-step task with human checkpoints

### Phase 4: API + Connectors (Week 4)
- [ ] PublishMIT-licensed reference implementation
- [ ] GitHub issue templates for framework integrations
- [ ] Community PRs for CrewAI, Anthropic SDK, other frameworks

---

## ✅ Success Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| **LangChain wrapper LOC** | <1000 | Code review |
| **Ollama CLI latency overhead** | <50ms per action | Benchmark |
| **AutoGPT human-in-the-loop approval time** | <2min average | User study |
| **AP2 settlement accuracy** | 100% (all successful actions route correctly) | Ledger audit |
| **Test coverage** | ≥90% for all safety gates | Coverage report |
| **GitHub stars (first 30 days)** | ≥100 | Trending tracker |

---

## 🚀 Competitive Positioning

**Why this matters:**
- LangChain doesn't have pre-execution safety (policy-based only)
- Ollama has no governance layer (pure inference)
- AutoGPT has no fail-closed gates (escalation-based only)
- **HarnessCapsule adds all three without forking or competing**

**Market implication:** Every team using LangChain + Ollama + AutoGPT will want Axiom's governance layer → 3.2x valuation multiplier.

---

## 📋 Implementation Checklist

- [ ] Create `axiom-langchain-harness` directory structure
- [ ] Implement `HarnessCapsule` trait (Rust interface)
- [ ] Python wrapper for LangChain integration
- [ ] MongeGapGovernor integration (blast radius scoring)
- [ ] AP2 settlement stub (micro-royalty routing)
- [ ] Ed25519 signing + Merkle proof generation
- [ ] Unit tests (8/8 passing)
- [ ] Integration tests with real LangChain agents
- [ ] CLI tool for Ollama (`axiom-run` command)
- [ ] Documentation + examples
- [ ] GitHub public release (MIT license)
