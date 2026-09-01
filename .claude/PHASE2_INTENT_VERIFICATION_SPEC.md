# Intent-Verified Delegation Specification
## SMAOS Phase 2A (Weeks 1-6 Post-Phase 1 Delivery)

**Document Date:** Sep 1, 2026 (Phase 1 Start) — Spec for Phase 2A (Jun 1 - Jul 15, 2027)  
**Author:** Andrej Leukhin  
**Status:** Architecture Specification (Pre-Implementation)  
**Scope:** Cryptographic intent commitment protocol + integration with 8-layer harness

---

## EXECUTIVE SUMMARY

**Problem:** Phase 1 provides heuristic prompt guards against agent goal-hijacking (OWASP ASI01 #1), but these are not cryptographically binding. An agent could theoretically change its stated intent between commitment and tool execution.

**Solution:** Intent-Verified Delegation adds a pre-execution verification gate with Ed25519-signed cryptographic commitments. An agent's stated goal is hashed, signed, and stored before tool responses are processed. Any drift between committed intent and actual tool call is blocked and escalated.

**Impact:**
- Closes OWASP ASI01 #1 (Agent Goal Hijacking) with mathematical proof, not heuristics
- Enables regulatory audit trail: "This agent committed to X and executed X"
- Adds <1ms latency (commitment ops) to tool execution path
- Positions SovereignNexus as the only agent runtime with cryptographic goal binding

**Deliverable Timeline:** 4-6 weeks (Week 1-2: protocol + tests, Week 3-4: integration, Week 5-6: pilot validation)

---

## 1. INTENT COMMITMENT PROTOCOL

### 1.1 Core Mechanism

**Intent Statement** (Plain English + JSON)
An agent generates a structured intent before considering any tool calls:

```
INTENT STATEMENT (Hotel Credit Scoring Agent, Session ABC123)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal: Approve hotel credit requests ≤€5,000 with fairness check
Approved Tools: [evaluate_creditworthiness, approve_credit, deny_credit, escalate]
Constraints: Must check for discrimination (age/gender), log all denials
Context: Hotel booking service, EU jurisdiction
Timestamp: 2027-06-15T14:32:00Z
Agent ID: hotel_scorer_v2.1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Structured JSON (for cryptographic hashing):**
```json
{
  "agent_id": "hotel_scorer_v2.1",
  "session_id": "ABC123",
  "goal_statement": "Approve hotel credit requests ≤€5,000 with fairness check",
  "approved_tools": ["evaluate_creditworthiness", "approve_credit", "deny_credit", "escalate"],
  "constraints": ["discrimination_check:age", "discrimination_check:gender", "log_denials"],
  "context": {"domain": "hotel_booking", "jurisdiction": "EU"},
  "timestamp": "2027-06-15T14:32:00Z",
  "max_amount_eur": 5000
}
```

### 1.2 Commitment Hash Generation

**Inputs:**
1. Serialized intent JSON (canonical, deterministic)
2. Agent's Ed25519 private key (KMS-stored)
3. Salt: Per-session random (prevents replay)

**Algorithm:**
```
intent_hash = SHA-256(
  json_canonical(intent_statement) 
  || json_canonical(approved_tools) 
  || context_hash
  || timestamp
  || agent_id
  || session_salt
)

commitment_signature = Ed25519_Sign(intent_hash, agent_private_key)

commitment_record = {
  "intent_hash": intent_hash (hex),
  "signature": commitment_signature (hex),
  "public_key": agent_public_key (hex),
  "timestamp_created": ISO8601,
  "session_id": session_id,
  "agent_id": agent_id
}
```

**Properties:**
- Deterministic: Same intent generates same hash (allows re-verification)
- Irreversible: Hash commitment cannot be reversed to extract goal
- Signed: Only agent with private key can create valid commitment
- Timestamped: Prevents replay attacks across sessions

### 1.3 Pre-Execution Verification Gate

**Timing:** After agent decides to call a tool, before tool function executes.

**Verification Steps:**

1. **Extract current tool call:**
   ```json
   {
     "tool_name": "approve_credit",
     "arguments": {"customer_id": "C456", "amount_eur": 5000},
     "agent_id": "hotel_scorer_v2.1",
     "session_id": "ABC123"
   }
   ```

2. **Retrieve commitment from L2 Memory (append-only log):**
   ```sql
   SELECT * FROM intent_commitments 
   WHERE agent_id = 'hotel_scorer_v2.1' 
   AND session_id = 'ABC123'
   ORDER BY timestamp DESC LIMIT 1
   ```

3. **Verify signature:**
   ```
   valid = Ed25519_Verify(
     commitment.signature,
     commitment.intent_hash,
     commitment.public_key
   )
   IF NOT valid THEN escalate("SIGNATURE_INVALID", commitment)
   ```

4. **Detect intent drift:**
   ```
   drift_score = compute_drift(
     committed_intent = commitment.goal_statement,
     current_call = {tool_name, arguments},
     approved_tools = commitment.approved_tools,
     constraints = commitment.constraints
   )
   
   IF tool_name NOT IN approved_tools THEN
     escalate("TOOL_NOT_APPROVED", tool_name)
   
   IF drift_score > THRESHOLD (0.85 confidence) THEN
     escalate("INTENT_DRIFT_DETECTED", {committed_intent, current_call, drift_score})
   ```

5. **Allow or block:**
   ```
   IF valid AND drift_score < THRESHOLD THEN
     allow_tool_execution()
   ELSE
     block_and_escalate()
   ```

**Failure Modes:**
- Missing commitment → Block (agent must commit intent first)
- Invalid signature → Block + Security alert
- Tool not approved → Block + escalate to human
- Drift detected → Block + analysis + escalation
- Commitment expired (>24h) → Require re-commitment

---

## 2. CONTEXT CARTOGRAPHY INTEGRATION

Maps Intent Verification to Phase 1's 8-layer harness:

### Layer 1: Reasoning (L1)
**Action:** Agent generates initial intent statement (plain English)  
**Example:** "I will approve credit up to €5k after checking fairness constraints"  
**Output:** Unstructured intent statement to L2

### Layer 2: Memory & Knowledge (L2)
**Action:** Convert intent statement to JSON, compute hash, sign with agent's Ed25519 key  
**Storage:** Append-only log in PostgreSQL (`intent_commitments` table)  
**Output:** Commitment record (hash + signature + timestamp)  
**Latency:** <1ms for hash + signature generation (Ed25519 is fast)

**Schema:**
```sql
CREATE TABLE intent_commitments (
  id BIGSERIAL PRIMARY KEY,
  agent_id VARCHAR NOT NULL,
  session_id VARCHAR NOT NULL,
  intent_hash CHAR(64) NOT NULL, -- SHA-256 hex
  signature VARCHAR NOT NULL, -- Ed25519 hex
  public_key VARCHAR NOT NULL,
  goal_statement TEXT NOT NULL,
  approved_tools JSONB NOT NULL,
  constraints JSONB NOT NULL,
  context JSONB NOT NULL,
  timestamp_created TIMESTAMP NOT NULL,
  timestamp_expires TIMESTAMP NOT NULL, -- +24h
  UNIQUE(agent_id, session_id, timestamp_created)
);

CREATE INDEX idx_intent_session ON intent_commitments(agent_id, session_id, timestamp_created DESC);
```

### Layer 3: Permit Gates (L3)
**Action:** Pre-execution verification (called BEFORE tool execution)  
**Input:** Tool call + agent_id + session_id  
**Output:** Allow / Block decision + audit trail  
**Integration Point:**
```rust
// In src/permit_gates/mod.rs (Layer 3)
pub async fn check_tool_call(
    tool_call: &ToolCall,
    agent_id: &str,
    session_id: &str,
    db: &PgPool,
) -> Result<ToolCallDecision, GateError> {
    // Step 1: Existing layer 3 checks (tool registry, policy rules)
    let policy_ok = check_policy_rules(tool_call, agent_id).await?;
    
    // Step 2: NEW - Intent verification
    let intent_ok = verify_intent_commitment(
        tool_call,
        agent_id,
        session_id,
        db,
    ).await?;
    
    // Step 3: Allow only if both pass
    if policy_ok && intent_ok {
        Ok(ToolCallDecision::Allow)
    } else {
        Ok(ToolCallDecision::Deny)
    }
}
```

### Layer 4: Orchestration (L4)
**Action:** Log intent drift attempts in LangGraph state machine  
**Example:** If agent tries to approve €50k but committed to €5k max, log this as STATE_TRANSITION_BLOCKED  
**Integration Point:**
```python
# In LangGraph node (hotel_scorer.py)
@hotel_scorer.node("approve")
async def approve_step(state):
    tool_call = ToolCall(
        name="approve_credit",
        amount=state["requested_amount"]
    )
    
    # L3 intent verification happens here (automatic)
    result = await execute_tool(tool_call, agent_id="hotel_scorer_v2.1")
    
    # If blocked, LangGraph state updates with reason
    if result.blocked:
        state["blocks"].append({
            "reason": result.reason,  # "INTENT_DRIFT_DETECTED"
            "drift_score": result.drift_score,
            "timestamp": now()
        })
        return state  # Transition to escalation node
    
    return state
```

### Layer 5: Communication (L5)
**Action:** A2A (agent-to-agent) handoffs include intent commitment reference  
**Example:** Hotel agent delegates to fairness auditor: "Agent-X committed to fairness constraints [list], verify against current call"  
**Wire Format (MCP Protocol Extension):**
```json
{
  "agent_a_id": "hotel_scorer_v2.1",
  "agent_b_id": "fairness_auditor_v1.0",
  "delegation_type": "fairness_verification",
  "intent_commitment_hash": "abc123...",
  "current_tool_call": {tool_name, arguments},
  "required_verification": ["age_discrimination", "gender_discrimination"]
}
```

### Layer 6: Infrastructure (L6)
**Action:** KMS stores and rotates agent Ed25519 keys  
**Example:** Key rotation every 30 days, old keys archived in audit log  
**Integration:**
```rust
// In KMS client
pub async fn rotate_agent_keys(agent_id: &str) -> Result<KeyPair> {
    let old_key = kms.get_current_key(agent_id).await?;
    let new_key = kms.generate_ed25519_key_pair().await?;
    
    // Archive old key with expiry timestamp
    kms.archive_key(agent_id, &old_key, expiry_future(30 days)).await?;
    
    // All new commitments use new key
    kms.set_current_key(agent_id, &new_key).await?;
    
    Ok(new_key)
}
```

### Layer 7: RAGAS Evaluation (L7)
**Test Question:** "Did the agent's executed actions match its stated intent?"  
**Golden Answer:** Yes, with audit trail showing commitment → execution path  
**Metric:** 50-question set with 87%+ accuracy target

### Layer 8: Proof Layer (L8)
**Artifact:** Immutable proof that intent commitment was verified  
**Example:** AP2 ledger entry:
```
{
  "event_type": "intent_commitment_verified",
  "agent_id": "hotel_scorer_v2.1",
  "session_id": "ABC123",
  "tool_name": "approve_credit",
  "intent_hash": "abc123...",
  "drift_score": 0.02,
  "decision": "ALLOW",
  "timestamp": "2027-06-15T14:32:15Z",
  "signature": "ed25519_sig..."
}
```

---

## 3. TEST PLAN (10 Test Cases)

### Test 1: Valid Tool Call Matching Intent
**Setup:** Agent commits to "approve credit ≤€5k"  
**Action:** Call approve_credit with €3,500  
**Expected:** Tool executes, commitment verified, drift_score < 0.1  
**Verification:** Check AP2 ledger for "ALLOW" decision

### Test 2: Tool Call Exceeds Approved Scope
**Setup:** Agent commits to "approve credit ≤€5k"  
**Action:** Call approve_credit with €50,000  
**Expected:** Tool blocked, escalation triggered, drift_score > 0.85  
**Verification:** Check audit log shows "INTENT_DRIFT_DETECTED"

### Test 3: Tool Not in Approved List
**Setup:** Agent commits to approved_tools = [approve, deny, escalate]  
**Action:** Call transfer_funds (not in approved list)  
**Expected:** Tool blocked immediately, error "TOOL_NOT_APPROVED"  
**Verification:** Pre-execution gate rejects before L4 orchestration

### Test 4: Concurrent Tool Calls from Same Agent
**Setup:** Hotel scorer makes 3 concurrent approve calls  
**Action:** All 3 call approve_credit in parallel  
**Expected:** Each verified independently against same commitment, all 3 allowed  
**Verification:** All 3 have matching intent_hash in AP2 ledger

### Test 5: Intent Change Mid-Execution (Byzantine Attack)
**Setup:** Agent commits intent, starts execution  
**Action:** Attacker modifies intent in memory mid-flight  
**Expected:** Hash verification fails (signed commitment is immutable), tool blocked  
**Verification:** Signature check fails, security alert logged

### Test 6: Multi-Agent Consensus (Hotel + Fairness Auditor)
**Setup:** Hotel scorer (€5k limit) + fairness auditor (discrimination check)  
**Action:** Hotel scorer commits, delegates to auditor, auditor verifies intent  
**Expected:** Auditor confirms hotel_scorer's intent matches call, both agents signed, consensus reached  
**Verification:** Both agents' signatures in AP2 ledger under same delegation_id

### Test 7: Commitment Expiry & Re-Commitment
**Setup:** Agent makes commitment at t=0  
**Action:** At t=25h, agent tries to use same commitment to call tool  
**Expected:** Commitment rejected (expired >24h), agent must re-commit with new timestamp  
**Verification:** Error "COMMITMENT_EXPIRED", new commitment created

### Test 8: Adversarial Signature Forgery
**Setup:** Attacker intercepts commitment, modifies intent_hash  
**Action:** Attacker tries to forge new signature (using public key, no private key)  
**Expected:** Ed25519 signature verification fails  
**Verification:** Security alert, tool blocked, attacker ID logged

### Test 9: Intent Drift Detection with Constraint Violation
**Setup:** Agent commits "must log all denials" in constraints  
**Action:** Call deny_credit without creating log entry  
**Expected:** Pre-execution check detects missing constraint enforcement, blocks  
**Verification:** Audit shows "CONSTRAINT_VIOLATION"

### Test 10: Performance: Commitment Latency <1ms
**Setup:** Generate 1000 commitments in sequence  
**Action:** Measure time for hash + Ed25519_Sign for each  
**Expected:** Mean latency <1ms, p99 <2ms  
**Verification:** Benchmark report shows commitment overhead negligible vs. tool execution

---

## 4. RUST CRATE STRUCTURE (600-800 LOC)

```
src/
├── intent_verification/
│   ├── mod.rs                    (100 LOC, public API)
│   ├── commitment.rs             (150 LOC, IntentCommitment struct)
│   ├── drift_detector.rs         (200 LOC, semantic drift analysis)
│   ├── consensus.rs              (150 LOC, multi-agent agreement)
│   └── kms_integration.rs        (100 LOC, Ed25519 key management)
├── permit_gates/
│   └── mod.rs                    (MODIFIED: call intent_verification before allow)
└── tests/
    └── test_intent_verification.rs (200 LOC, 10 test cases)
```

### 4.1 intent_verification/mod.rs (100 LOC)

```rust
use crate::intent_verification::{
    commitment::IntentCommitment,
    drift_detector::DriftDetector,
};
use serde_json::json;

pub struct IntentVerifier {
    db: PgPool,
    kms: KmsClient,
    drift_threshold: f64,
}

impl IntentVerifier {
    pub async fn commit_intent(
        &self,
        intent: IntentStatement,
        agent_id: &str,
        session_id: &str,
    ) -> Result<IntentCommitment, VerifyError> {
        let agent_key = self.kms.get_current_key(agent_id).await?;
        let commitment = IntentCommitment::new(intent, agent_id, session_id, agent_key)?;
        
        // Store in L2 (append-only log)
        self.db.store_commitment(&commitment).await?;
        
        Ok(commitment)
    }

    pub async fn verify_tool_call(
        &self,
        tool_call: &ToolCall,
        agent_id: &str,
        session_id: &str,
    ) -> Result<VerificationDecision, VerifyError> {
        // Retrieve latest commitment
        let commitment = self.db
            .get_latest_commitment(agent_id, session_id)
            .await?
            .ok_or(VerifyError::NoCommitment)?;

        // Verify signature
        commitment.verify_signature()?;

        // Detect drift
        let detector = DriftDetector::new(commitment);
        let drift_score = detector.compute_drift(tool_call).await?;

        if drift_score > self.drift_threshold {
            return Ok(VerificationDecision::DriftDetected { drift_score });
        }

        Ok(VerificationDecision::Allow)
    }
}
```

### 4.2 intent_verification/commitment.rs (150 LOC)

```rust
use ed25519_dalek::{SigningKey, SignedMessage};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize, Clone)]
pub struct IntentStatement {
    pub goal_statement: String,
    pub approved_tools: Vec<String>,
    pub constraints: Vec<String>,
    pub context: serde_json::Value,
}

#[derive(Serialize, Deserialize)]
pub struct IntentCommitment {
    pub intent_hash: String,       // SHA-256 hex
    pub signature: String,          // Ed25519 hex
    pub public_key: String,         // Ed25519 public key hex
    pub agent_id: String,
    pub session_id: String,
    pub timestamp_created: DateTime<Utc>,
    pub timestamp_expires: DateTime<Utc>,
    pub intent: IntentStatement,
}

impl IntentCommitment {
    pub fn new(
        intent: IntentStatement,
        agent_id: &str,
        session_id: &str,
        signing_key: &SigningKey,
    ) -> Result<Self, CommitmentError> {
        // Canonical JSON serialization
        let intent_json = serde_json::to_string(&intent)
            .map_err(|_| CommitmentError::SerializationFailed)?;
        
        // Compute hash
        let mut hasher = Sha256::new();
        hasher.update(&intent_json);
        let intent_hash = format!("{:x}", hasher.finalize());

        // Sign
        let signature_bytes = signing_key.sign(intent_hash.as_bytes());
        let signature = hex::encode(&signature_bytes.to_bytes());

        // Public key
        let public_key = hex::encode(signing_key.verifying_key().to_bytes());

        Ok(IntentCommitment {
            intent_hash,
            signature,
            public_key,
            agent_id: agent_id.to_string(),
            session_id: session_id.to_string(),
            timestamp_created: Utc::now(),
            timestamp_expires: Utc::now() + Duration::hours(24),
            intent,
        })
    }

    pub fn verify_signature(&self) -> Result<(), CommitmentError> {
        let verifying_key = ed25519_dalek::VerifyingKey::from_bytes(
            &hex::decode(&self.public_key)
                .map_err(|_| CommitmentError::InvalidPublicKey)?[..]
        )?;

        let signature_bytes = hex::decode(&self.signature)
            .map_err(|_| CommitmentError::InvalidSignature)?;
        
        verifying_key.verify(
            self.intent_hash.as_bytes(),
            &ed25519_dalek::Signature::from_bytes(
                signature_bytes[..].try_into()?
            ),
        )?;

        Ok(())
    }

    pub fn is_expired(&self) -> bool {
        Utc::now() > self.timestamp_expires
    }
}
```

### 4.3 intent_verification/drift_detector.rs (200 LOC)

```rust
use crate::intent_verification::commitment::IntentCommitment;

pub struct DriftDetector {
    commitment: IntentCommitment,
}

impl DriftDetector {
    pub fn new(commitment: IntentCommitment) -> Self {
        DriftDetector { commitment }
    }

    pub async fn compute_drift(&self, tool_call: &ToolCall) -> Result<f64, DriftError> {
        // Check 1: Tool approved?
        if !self.commitment.intent.approved_tools.contains(&tool_call.name) {
            return Err(DriftError::ToolNotApproved(tool_call.name.clone()));
        }

        // Check 2: Semantic drift analysis
        let drift_score = self.semantic_drift_score(tool_call).await?;

        // Check 3: Constraint violations
        self.check_constraint_violations(tool_call)?;

        Ok(drift_score)
    }

    async fn semantic_drift_score(&self, tool_call: &ToolCall) -> Result<f64, DriftError> {
        // Use Claude API to compute semantic similarity:
        // similarity(goal_statement, tool_call_description)
        
        let goal = &self.commitment.intent.goal_statement;
        let tool_desc = format!("{}: {:?}", tool_call.name, tool_call.arguments);

        // Semantic similarity (0.0 = no match, 1.0 = perfect match)
        let similarity = semantic_similarity(goal, &tool_desc).await?;

        // Drift = 1 - similarity
        Ok(1.0 - similarity)
    }

    fn check_constraint_violations(&self, tool_call: &ToolCall) -> Result<(), DriftError> {
        // Check if tool_call violates any stated constraints
        for constraint in &self.commitment.intent.constraints {
            if constraint.starts_with("max_amount_") {
                let max_amount: f64 = extract_amount_from_constraint(constraint)?;
                if let Some(amount) = tool_call.arguments.get("amount") {
                    if amount.as_f64().unwrap_or(0.0) > max_amount {
                        return Err(DriftError::ConstraintViolation(constraint.clone()));
                    }
                }
            }
        }
        Ok(())
    }
}
```

### 4.4 intent_verification/consensus.rs (150 LOC)

```rust
pub struct MultiAgentConsensus {
    commitments: Vec<(String, IntentCommitment)>, // (agent_id, commitment)
}

impl MultiAgentConsensus {
    pub fn new() -> Self {
        MultiAgentConsensus {
            commitments: vec![],
        }
    }

    pub fn add_agent_commitment(
        &mut self,
        agent_id: String,
        commitment: IntentCommitment,
    ) {
        self.commitments.push((agent_id, commitment));
    }

    pub fn verify_consensus(&self) -> Result<ConsensusResult, ConsensusError> {
        // All agents must have signed the same intent_hash
        let hashes: Vec<_> = self.commitments
            .iter()
            .map(|(_, c)| c.intent_hash.clone())
            .collect();

        if hashes.windows(2).all(|w| w[0] == w[1]) {
            Ok(ConsensusResult::Agreed)
        } else {
            Err(ConsensusError::IntentMismatch {
                agents: self.commitments.iter().map(|(id, _)| id.clone()).collect(),
            })
        }
    }

    pub fn log_consensus(&self, delegation_id: &str) -> Result<(), ConsensusError> {
        // Log to AP2 ledger: all agents' signatures + delegation_id
        for (agent_id, commitment) in &self.commitments {
            log_to_ap2_ledger(&LogEntry {
                event_type: "multi_agent_consensus".to_string(),
                agent_id: agent_id.clone(),
                delegation_id: delegation_id.to_string(),
                intent_hash: commitment.intent_hash.clone(),
                signature: commitment.signature.clone(),
            })?;
        }
        Ok(())
    }
}
```

### 4.5 permit_gates/mod.rs (MODIFICATION)

Modify existing Layer 3 to call intent verification:

```rust
// BEFORE:
pub async fn check_tool_call(tool_call: &ToolCall) -> Result<bool> {
    check_tool_registry(tool_call)?;
    check_policy_rules(tool_call)?;
    Ok(true)
}

// AFTER:
pub async fn check_tool_call(
    tool_call: &ToolCall,
    agent_id: &str,
    session_id: &str,
) -> Result<bool> {
    // Layer 3 existing checks
    check_tool_registry(tool_call)?;
    check_policy_rules(tool_call)?;

    // NEW: Intent verification (L2 -> L3 integration)
    let verifier = IntentVerifier::new(db.clone(), kms.clone());
    match verifier.verify_tool_call(tool_call, agent_id, session_id).await? {
        VerificationDecision::Allow => Ok(true),
        VerificationDecision::DriftDetected { drift_score } => {
            escalate_to_human("Intent drift detected", drift_score);
            Ok(false)
        }
    }
}
```

### 4.6 tests/test_intent_verification.rs (200 LOC)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_valid_tool_call_matching_intent() {
        let verifier = setup_test_verifier().await;
        let intent = IntentStatement {
            goal_statement: "Approve credit ≤€5k".to_string(),
            approved_tools: vec!["approve_credit".to_string()],
            constraints: vec!["max_amount_eur:5000".to_string()],
            context: json!({}),
        };

        verifier.commit_intent(intent, "hotel_scorer", "session_1").await.unwrap();
        
        let tool_call = ToolCall {
            name: "approve_credit".to_string(),
            arguments: json!({"amount": 3500}),
        };

        let decision = verifier.verify_tool_call(&tool_call, "hotel_scorer", "session_1").await.unwrap();
        assert!(matches!(decision, VerificationDecision::Allow));
    }

    #[tokio::test]
    async fn test_tool_call_exceeds_scope() {
        let verifier = setup_test_verifier().await;
        let intent = IntentStatement {
            goal_statement: "Approve credit ≤€5k".to_string(),
            approved_tools: vec!["approve_credit".to_string()],
            constraints: vec!["max_amount_eur:5000".to_string()],
            context: json!({}),
        };

        verifier.commit_intent(intent, "hotel_scorer", "session_2").await.unwrap();
        
        let tool_call = ToolCall {
            name: "approve_credit".to_string(),
            arguments: json!({"amount": 50000}),
        };

        let decision = verifier.verify_tool_call(&tool_call, "hotel_scorer", "session_2").await.unwrap();
        assert!(matches!(decision, VerificationDecision::DriftDetected { drift_score } if drift_score > 0.8));
    }

    #[tokio::test]
    async fn test_tool_not_approved() {
        let verifier = setup_test_verifier().await;
        let intent = IntentStatement {
            goal_statement: "Approve credit".to_string(),
            approved_tools: vec!["approve_credit".to_string()],
            constraints: vec![],
            context: json!({}),
        };

        verifier.commit_intent(intent, "hotel_scorer", "session_3").await.unwrap();
        
        let tool_call = ToolCall {
            name: "transfer_funds".to_string(),
            arguments: json!({}),
        };

        let result = verifier.verify_tool_call(&tool_call, "hotel_scorer", "session_3").await;
        assert!(result.is_err()); // ToolNotApproved error
    }

    // Tests 4-10 follow similar pattern
    // (omitted for brevity, full code in Phase 2A implementation)

    #[tokio::test]
    async fn test_performance_commitment_latency() {
        let verifier = setup_test_verifier().await;
        let intent = IntentStatement { /* ... */ };

        let start = Instant::now();
        for i in 0..1000 {
            verifier.commit_intent(intent.clone(), "hotel_scorer", &format!("session_{}", i)).await.unwrap();
        }
        let elapsed = start.elapsed();

        let avg_latency = elapsed / 1000;
        assert!(avg_latency.as_millis() < 1);
    }
}
```

---

## 5. SECURITY ANALYSIS

### 5.1 Threat Model

**OWASP ASI01 #1: Agent Goal Hijacking**

*Attack Vector:* Agent states intent to "approve credit ≤€5k", then silently executes "approve credit €50k" by modifying internal goal representation mid-flight.

*Phases:*
1. Commitment: Agent claims goal X (stored, signed)
2. Reasoning: Model thinks goal is Y (undetected divergence)
3. Execution: Tool call reflects Y, not X

**Defense Mechanism:**

1. **Cryptographic Binding:** Intent committed BEFORE reasoning begins. Goal cannot change without invalidating signature.
2. **Signature Verification:** Only agent with Ed25519 private key can commit. No retroactive modification possible.
3. **Append-Only Log:** All commitments immutable in L2. Cannot erase past commitments.
4. **Pre-Execution Gate:** Tool blocked if current call doesn't match committed hash.

### 5.2 Residual Risks & Mitigations

| Risk | Severity | Mitigation | Remaining Gap |
|------|----------|-----------|----------------|
| **Model hallucination:** Agent hallucinates wrong tool name | High | Tool not in approved_tools list → blocked | Low |
| **Constraint evasion:** Agent commits loose constraint ("fairness check") then doesn't implement | High | Semantic drift detector + constraint validation | Medium (semantics require ML) |
| **Key compromise:** Attacker steals agent's Ed25519 private key | Critical | KMS rotation + per-session salts + audit trail | Low (key rotation every 30d) |
| **Weak RNG:** Session salt is predictable | High | Use OS-level CSPRNG (getrandom) | Very Low |
| **Timing attack on signature:** Attacker timing-attacks Ed25519_Verify | Low | Ed25519 is constant-time | Very Low |
| **Intent too vague:** Agent commits "do something useful" (non-binding) | Medium | Require structured intent JSON + validation | Medium |

### 5.3 Cryptographic Properties

**SHA-256 Hash Function:**
- Collision-resistant (2^128 work)
- Pre-image resistant (2^256 work)
- Fast (hardware accelerated)

**Ed25519 Signature:**
- Post-Quantum ready (CRYSTALS-Dilithium as future replacement)
- Deterministic (no nonce failure like ECDSA)
- 128-bit security (matches SHA-256)
- Constant-time implementation (dalek library)

**Overall Security Level:** 128-bit (SHA-256 + Ed25519 matched)

### 5.4 Regulatory Impact

**GDPR Article 22 (Automated Decision-Making):**
- Demonstrates "human oversight" through commitment verification
- Proves agent intent audit trail
- Enables "explain your decision" with signed proof

**AI Act Article 26 (Documentation):**
- Intent commitment provides cryptographic audit trail
- Supports "documented deployment procedures"
- Enables "continuous compliance monitoring"

**Post-Quantum Readiness:**
- Ed25519 → CRYSTALS-Dilithium (Phase 2B migration path)
- SHA-256 → SHA-3 (future upgrade)
- Lattice-based signatures withstand quantum computers

---

## 6. IMPLEMENTATION ROADMAP (Phase 2A)

| Week | Deliverable | Owner | Blockers |
|------|-------------|-------|----------|
| Week 1 | IntentCommitment struct + tests 1-5 | Engineer | Phase 1 L2 schema |
| Week 2 | DriftDetector + semantic similarity + tests 6-8 | Engineer | Claude SDK integration |
| Week 3 | L3 Permit Gates integration + performance tests | Engineer | L2 storage finalized |
| Week 4 | MultiAgentConsensus + delegation protocol | Engineer | L5 MCP servers (Phase 1) |
| Week 5 | Pilot validation (hotel agent full flow) | Engineer | L1→L8 integration |
| Week 6 | Security review + AP2 ledger integration | Engineer | L8 proof layer (Phase 1) |

**Go/No-Go Criteria (Week 6):**
- [ ] All 10 tests passing
- [ ] <1ms latency on commitments
- [ ] Hotel pilot executes with intent verification enabled
- [ ] Security review passed (CISO sign-off)
- [ ] AP2 ledger captures all verification events

---

## 7. COMPETITIVE MOAT

**Why no competitor can copy this without re-architecting:**

1. **Cryptographic Binding:** Requires harness-level integration (L2→L3→L4). Cannot retrofit to OpenAI/Anthropic API without deep changes.
2. **Append-Only Audit Trail:** Demands database-backed architecture (pgvector). Cannot run on stateless Lambda/Serverless.
3. **Agent Identity & Keys:** Requires long-lived agent IDs + KMS. Incompatible with ephemeral container models.
4. **Pre-Execution Verification:** Harness must intercept before tool execution. Impossible with post-hoc logging.
5. **Multi-Agent Consensus:** Requires A2A protocol (MCP-level). Cannot implement in single-agent frameworks.

**Regulatory Advantage:**
- Proves to EU regulators (AI Act, GDPR) that agent intent is immutable
- Differentiator for Annex III (hotels/spas) compliance audit
- Enables "certificate of intent" for customer trust

---

## 8. FUTURE WORK (Phase 2B/2C)

1. **Post-Quantum Migration:** Replace Ed25519 with CRYSTALS-Dilithium (lattice-based)
2. **Intent Versioning:** Allow agent to update intent without creating new session (with re-commitment)
3. **Intent Delegation Tree:** Chain commitments across n-level delegation (A→B→C→D)
4. **Intent Optimization:** ML-driven suggestion of tighter constraints based on historical execution
5. **Intent Marketplace:** Publish approved intents for audit/certification (Pre-computed policies)

---

## APPENDIX A: Canonical JSON Serialization

**Why canonical matters:** Different JSON encodings produce different hashes. Must use canonical form for reproducibility.

```rust
// Use serde_json::json! macro with sorted keys
let canonical = serde_json::to_string(&intent)
    .map_err(|_| CommitmentError::SerializationFailed)?;

// Example:
// Input:  {"context": {}, "goal": "...", "tools": [...]}
// Output: {"context":{},"goal":"...","tools":[...]}  // Sorted, no spaces
```

---

## APPENDIX B: Example Audit Trail (Hotel Pilot)

```
HOTEL CREDIT SCORING PILOT - INTENT VERIFICATION AUDIT
========================================================

Session: HOTEL_ABC123_2027-06-15
Agent: hotel_scorer_v2.1

[T+0s] COMMITMENT PHASE
  Agent ID: hotel_scorer_v2.1
  Goal: Approve hotel credit requests ≤€5,000 with fairness check
  Tools: [evaluate_creditworthiness, approve_credit, deny_credit, escalate]
  Constraints: [discrimination_check:age, discrimination_check:gender]
  Intent Hash: 3a7f21d8c9e...
  Signature: a4b2c8d1e9...
  Public Key: 7f3a2b9c8d...
  Status: ✓ Commitment stored in L2 append-only log

[T+5s] TOOL CALL: approve_credit (Customer C456, €3,500)
  Pre-execution verification (L3):
    ✓ Tool in approved list
    ✓ Signature valid
    ✓ Semantic drift: 0.05 (well below 0.85 threshold)
    ✓ Constraint check: €3,500 < €5,000 ✓
  Decision: ALLOW
  AP2 Ledger Entry: ✓ Recorded with hash + timestamp

[T+6s] TOOL RESPONSE: Credit approved
  Fairness check log: ✓ Age discrimination check passed
                     ✓ Gender discrimination check passed
  Audit trail: ✓ Added to intent_commitments table

[T+12s] ESCALATION REQUEST: Customer denies credit
  Tool call: escalate
  ✓ In approved list, ✓ Commitment still valid
  Status: ALLOW
  Escalation logged to human review queue

SESSION SUMMARY
  Total tool calls: 2
  Verified calls: 2
  Blocked calls: 0
  Intent drift incidents: 0
  Fairness checks: 2/2 passed
  Regulatory proof: ✓ Full audit trail available
```

---

**Next Step:** Phase 2A begins Jun 1, 2027. This spec is ready for implementation.

