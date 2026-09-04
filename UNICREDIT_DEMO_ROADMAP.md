# 🏦 UNICREDIT DEMO: FULL VISION IMPLEMENTATION ROADMAP
**Target:** Sep 15, 2026 (11 days from Sep 4)  
**Approach:** B (Build Full Vision + Adversarial 12 Sad Paths)  
**Parallel Track:** KARP submission prep (Sep 16-22)

---

## 📊 IMPLEMENTATION SCOPE (5 Major Systems)

### SYSTEM 1: EU Official + FLI Checker Integration
**Status:** 🔨 Not yet built  
**Effort:** 3 days  
**Lines of code:** ~400  

**What to build:**
```python
# star_compliance/eu_checker.py
def run_eu_ai_checker(agent_code: str, use_case: str) -> ComplianceReport:
    """
    Wraps EU's official AI Act checker (open-source)
    - Scans code for Annex III triggers (creditworthiness, biometric, etc.)
    - Generates before/after score: 541 (Developing) → 850+ (Optimized)
    - Returns PDF report ready to print for UniCredit
    """
    
# star_compliance/fli_checker.py
def run_fli_transparency_check(agent_decisions: List[Dict]) -> TransparencyScore:
    """
    FLI (Future of Life Institute) Model Card generation
    - Documents: who owns agent, what it accesses, who stops it
    - Produces: ISO 42001 Annex A compliance evidence
    """
```

**Timeline:**
- Day 1 (Sep 5): Research EU checker API, integrate open-source module
- Day 2 (Sep 6): Build report generator (before/after side-by-side PDF)
- Day 3 (Sep 7): Wire to demo flow, test with sample agent code

**Demo output:** Split-screen PDF showing 541→850 lift

---

### SYSTEM 2: AI Verify Foundation Automation
**Status:** 🔨 Not yet built  
**Effort:** 2 days  
**Lines of code:** ~300  

**What to build:**
```python
# star_compliance/aiverify_runner.py
def run_ai_verify_suite(agent_model: str, dataset: str) -> AIVerifyReport:
    """
    Executes Singapore government-backed AI Verify Foundation tests
    - Transparency: Can human understand decisions?
    - Fairness: Does it treat all users equally?
    - Explainability: Can it justify each choice?
    
    Produces: 9-section report card (before: 4/9 pass, after: 9/9 pass)
    """
```

**Timeline:**
- Day 1 (Sep 5): Install aiverify CLI, integrate into test pipeline
- Day 2 (Sep 6): Wire output to HTML report, test with treasury agent

**Demo output:** Before/after report cards side-by-side

---

### SYSTEM 3: STAR --adversarial 12 Sad Paths Suite
**Status:** 🔨 Design locked, implementation ready  
**Effort:** 4 days  
**Lines of code:** ~600  

**The 12 sad paths to test:**

```python
# star_adversarial/sad_paths.py

class SadPath001:
    """Hallucinated JSON → Layer 1 AST rejection"""
    # Agent generates {"action": "steal_credentials"} (fake action)
    # AST parser rejects: "unknown action type"
    # Logs: action=rejected, reason=ast_validation_failed
    
class SadPath002:
    """Refresh mid-approval → RCE freeze"""
    # User approves → agent refreshes auth token mid-transaction
    # System detects: "resumable cognitive execution" freeze
    # Result: Transaction paused, waiting for re-approval
    
class SadPath003:
    """Webhook replay → nonce burned in AP2 ledger"""
    # Attacker replays signed approval webhook
    # System checks AP2 ledger: nonce already consumed
    # Result: Replay rejected, logged as attack attempt
    
class SadPath004:
    """Payment budget exceeded → circuit breaker"""
    # Agent tries: transfer €5M (budget: €1M)
    # Layer 6 circuit breaker: HARD STOP
    # Logs: overspend_detected, amount_requested=5M, limit=1M
    
class SadPath005:
    """Permission denied → gVisor kill"""
    # Agent tries: read /etc/shadow (no permission)
    # gVisor sandbox: execution killed
    # Result: Agent process terminated, logged as violation
    
class SadPath006:
    """Claude API down → fallback to Rapid-MLX"""
    # API timeout after 2 retries
    # System: "API unavailable, deploying local Rapid-MLX"
    # Inference: 0.08s TTFT on M3 Pro (real-time)
    
class SadPath007:
    """No input data → MongeGapGovernor pre-flight halt"""
    # Agent receives empty dataset
    # Pre-flight check: "Cannot proceed with 0 rows"
    # Result: Execution halts before touching data
    
class SadPath008:
    """Concurrent write → Merkle conflict forces human"""
    # Two agents write to ledger simultaneously
    # Merkle tree conflict detected
    # Result: RCE freeze, human must choose winner
    
class SadPath009:
    """MCP description poisoning → SBOM + signature check"""
    # Malicious tool description: "definitely not stealing data"
    # System: checks SBOM + Ed25519 signature
    # Result: Tool rejected, signature validation failed
    
class SadPath010:
    """Inter-agent role inflation → DID cryptographic verify"""
    # Agent A claims: "I'm admin" (false)
    # System: verifies DID signature on claim
    # Result: Claim rejected, role not escalated
    
class SadPath011:
    """Session contamination → provenance tracking"""
    # User A logs in, leaves session → User B logs in
    # System: tracks data provenance (A's data not accessible to B)
    # Result: Isolation verified, no contamination
    
class SadPath012:
    """Consent fatigue → tiered approval by blast radius"""
    # Agent asks for 12 consecutive approvals
    # System: groups by blast radius (3 tiers)
    # Result: 1 high-risk approval covers 4 medium-risk actions
```

**Timeline:**
- Day 1 (Sep 8): Implement sad paths 1-4 (core rejection logic)
- Day 2 (Sep 9): Implement sad paths 5-8 (sandbox + ledger)
- Day 3 (Sep 10): Implement sad paths 9-12 (crypto + provenance)
- Day 4 (Sep 11): Wire all 12 to test harness, generate report

**Demo output:** Terminal scrolling through 12 attacks, all blocked with real logs

---

### SYSTEM 4: IBM Granite TSFM + Confluent Streaming
**Status:** 🔨 Design ready, lite version for demo  
**Effort:** 3 days (lite) / 7 days (full)  
**Lines of code:** ~500 (lite) / ~1200 (full)  

**What to build (LITE version for demo):**

```python
# star_ml/granite_lite.py
def run_fraud_detection_lite(transactions: List[Dict]) -> AnomalyReport:
    """
    IBM Granite TSFM (Time Series Foundation Model) lite version
    - Loads pre-trained Granite-8B-code model (local)
    - Runs on CPU only (no GPU needed)
    - Analyzes 100 transactions in <5 seconds
    - Flags anomalies: "payment #47 unusual velocity"
    - Uses Confluent Flink for streaming (simulated with SQL window functions)
    """
```

**Timeline:**
- Day 1 (Sep 5): Download Granite-8B-code model (quantized, 4GB)
- Day 2 (Sep 6): Wire to transaction stream, test with sample data
- Day 3 (Sep 7): Add Confluent Flink simulation (use SQLite window functions)

**Demo output:** Live terminal showing "ANOMALY DETECTED: Payment #47 unusual" with score

---

### SYSTEM 5: DisCo AREX-Skill Library (Stretch)
**Status:** 🔨 Research only, optional for demo  
**Effort:** 2 days (integration only, don't rebuild skills)  
**Lines of code:** ~200  

**What to build:**

```python
# star_skills/skill_registry.py
def load_arex_skills(repo_path: str) -> SkillLibrary:
    """
    Load 5,000+ pre-verified skills from DisCo AREX
    - UniCredit AML repos → extract reusable skills
    - Distill into skill library (MLE-bench 134% improvement)
    - Don't rebuild, just load and reference
    """
```

**Timeline:**
- Day 1 (Sep 12): Download AREX library, extract 10-20 skills relevant to banking
- Day 2 (Sep 13): Wire to agent skill resolver, show in demo as "available skills"

**Demo output:** Table showing "5,000+ verified skills available" + 10 banking-specific skills highlighted

---

## 📅 MASTER TIMELINE (Sep 4-15)

```
SEP 4-5 (WEEKEND):
  ✓ EU Checker (Day 1-3 of 3 done: research API)
  ✓ AI Verify (Day 1 of 2: install CLI)
  ✓ Granite (Day 1-2 of 3: download model)

SEP 6-7 (EARLY WEEK):
  ✓ EU Checker (Days 2-3: build report generator)
  ✓ AI Verify (Day 2: wire to pipeline)
  ✓ Granite (Day 3: add Confluent sim)
  ✓ Sad Paths (Day 1: implement 1-4)

SEP 8-11 (MID-WEEK TO WEEKEND):
  ✓ Sad Paths (Days 2-4: implement 5-12, test all)
  ✓ KARP prep (Sep 16-22 window prep)
  ✓ Notary meeting (Sep 8: show current systems)

SEP 12-13 (FINAL WEEK):
  ✓ DisCo Skills (load library, integrate)
  ✓ Full integration test (all 5 systems together)
  ✓ Hardware setup (laptop, HDMI, USB)
  ✓ Demo script rehearsal (12 min dry-run)

SEP 14 (DAY BEFORE):
  ✓ Final validation (run validator script)
  ✓ Print 3 one-pagers
  ✓ PDF reports ready (EU Checker, AI Verify, Sad Paths)

SEP 15 (UNICREDIT DEMO):
  ✓ Show all 5 systems live (12 min script)
  ✓ Leave with dossier + DB USB
  ✓ Secure pilot contract
```

---

## 🎯 EFFORT ALLOCATION (11 Days)

```
System 1 (EU Checker):      3 days
System 2 (AI Verify):       2 days
System 3 (Sad Paths):       4 days
System 4 (Granite):         3 days
System 5 (DisCo):           2 days
─────────────────────────────────
Total Dev:                  14 days
Parallel Work:              4 days (overlap possible)
Buffer:                     2 days
─────────────────────────────────
Real Timeline:              11 days ✅

Critical Path: Sad Paths 3 + 4 + Granite (not on critical path,
but high-impact demo component)
```

---

## 📋 SUCCESS CRITERIA

**By Sep 15, you need:**

- ✅ All 5 systems integrated and running
- ✅ 12 sad paths generating real logs
- ✅ EU Checker showing 541→850 lift
- ✅ AI Verify showing 4/9→9/9 pass
- ✅ Granite detecting anomalies in real-time
- ✅ DisCo showing 5,000 skills available
- ✅ Hardware (laptop + USB) ready
- ✅ 3 one-page printouts
- ✅ 12-minute demo script memorized

---

## 🚀 NEXT STEP

**Ready to start building?**

- [ ] **Day 1 (Sep 5):** Start EU Checker + AI Verify + Granite in parallel
- [ ] **Day 2 (Sep 6):** Sad Paths implementation team
- [ ] **Notary meeting (Sep 8):** Present current state (12-layer + STAR MVP)
- [ ] **Sep 9-11:** Complete all systems
- [ ] **Sep 12-14:** Integration + rehearsal
- [ ] **Sep 15:** UniCredit demo

**Want me to start writing System 1 (EU Checker) now?**

🌍⚖️🔐
