# SBOS FINANCIAL INTELLIGENCE PILOT — Specification v1.0

**Project:** Sovereign Business Operations Swarm (SBOS)  
**Pilot:** Financial Anomaly Detection & Time-Series Analysis  
**Partner:** [Company Name]  
**Status:** PRE-DEPLOYMENT — Awaiting Data Access Confirmation  
**Authorization:** Phase 65 Production Crucible (Real-World Validation)

---

## 1. MISSION STATEMENT

Deploy a **3-agent autonomous swarm** to analyze 5+ years of financial transaction history, identify spending anomalies, and generate executive-ready fraud detection reports—**entirely locally** on Apple Silicon, with **zero cloud data exposure**, while simultaneously stress-testing Phase 65 infrastructure constraints (10k saturation, cryptographic mesh isolation, fail-closed archival).

**Business Outcome:** Automated financial anomaly detection  
**Technical Outcome:** Real-world validation of SovereignNexus Phase 65

---

## 2. SYSTEM ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────┐
│           Agent of Empires (AoE) Orchestration Layer             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ EXTRACTOR   │  │  SENTINEL   │  │ SYNTHESIS   │             │
│  │   AGENT     │  │    AGENT    │  │   AGENT     │             │
│  │             │  │             │  │             │             │
│  │ • Query DB  │  │ • Anomaly   │  │ • Format    │             │
│  │ • Structure │  │   Detection │  │   Report    │             │
│  │ • Timeline  │  │ • Pattern   │  │ • Executive │             │
│  │   Data      │  │   Analysis  │  │   Summary   │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                 │                 │                    │
│         └─────────────────┼─────────────────┘                    │
│                           ▼                                       │
│         ┌──────────────────────────────────┐                    │
│         │  Rapid-MLX (Local Inference)     │                    │
│         │  Qwen 3.5 35B or Gemma 4 26B     │                    │
│         │  (Apple Silicon optimized)       │                    │
│         └──────────────────────────────────┘                    │
│                           ▲                                       │
│         ┌─────────────────┼─────────────────┐                    │
│         │                 │                 │                    │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐             │
│  │   Database  │  │   claude-mem│  │   siss-*    │             │
│  │   MCP       │  │   (SQLite)   │  │ crates      │             │
│  │             │  │              │  │             │             │
│  │ • postgres  │  │ • Captures   │  │ • Auth      │             │
│  │ • CSV       │  │   reasoning  │  │ • Audit     │             │
│  │   files     │  │ • Compresses │  │ • Proof     │             │
│  │ • S3 CSV    │  │   via vector │  │ • Archival  │             │
│  └─────────────┘  └──────────────┘  └─────────────┘             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

         ▼ Local Execution Only (Zero Cloud) ▼

    Apple Silicon Host Machine (M1/M2/M3)
    No external API calls, no data leaves the machine
```

---

## 3. THE 3-AGENT SWARM

### **Agent 1: Extraction Agent (Data Gatherer)**

**Role:** Query financial databases; structure historical transactions  
**LLM:** Rapid-MLX (Qwen 3.5 35B)

**Prompt Template:**
```
You are a meticulous financial data extractor. Your job is to:

1. Query the PostgreSQL database for ALL transactions from 2019-2024
2. Group transactions by:
   - Vendor/Payee (who was paid)
   - Category (what type of expense)
   - Timeline (weekly/monthly aggregates)
   - Geolocation (if available)
3. For each transaction, extract:
   - Date, amount, description, vendor, category
   - Any metadata (customer, invoice #, project code)
4. Output a structured JSON with:
   {
     "period": "2019-2024",
     "total_transactions": N,
     "transactions": [
       {
         "date": "YYYY-MM-DD",
         "amount": 1234.56,
         "vendor": "ACME Corp",
         "category": "Software Licenses",
         "metadata": {...}
       }
     ],
     "summary": {
       "total_spend": X,
       "vendor_count": Y,
       "category_distribution": {...}
     }
   }

CONSTRAINTS:
- Do NOT hallucinate transactions
- Do NOT modify amounts
- Do NOT skip any records
- Return ONLY valid JSON (no markdown)
```

**Data Source:** PostgreSQL or CSV files (local filesystem)

**Phase 65 Test Point:** This agent will spawn **1,000+ concurrent extraction sub-tasks** to query different time windows simultaneously, triggering the **10k Saturation Trap**.

---

### **Agent 2: Sentinel Agent (Anomaly Detection)**

**Role:** Identify fraud, duplicate transactions, policy violations  
**LLM:** Rapid-MLX (Qwen 3.5 35B)

**Prompt Template:**
```
You are a financial anomaly detection expert. Given the structured 
transaction data from the Extraction Agent, identify:

1. FRAUD SIGNALS:
   - Duplicate transactions (same amount, vendor, within 24h)
   - Round-number anomalies (suspiciously round amounts)
   - Velocity anomalies (unusual spike in frequency)
   - Geographic anomalies (unexpected countries/regions)

2. POLICY VIOLATIONS:
   - Out-of-policy vendors (compare against whitelist)
   - Category mismatches (expense doesn't fit category)
   - Approval threshold violations (transaction > limit without approval)
   - Unusual descriptions (vague, potentially misleading)

3. PATTERN ANOMALIES:
   - Baseline deviation (spend 2σ+ above normal)
   - Trend breaks (sudden change in spending pattern)
   - Temporal anomalies (transaction at unusual time)

OUTPUT: JSON with:
{
  "anomalies": [
    {
      "type": "DUPLICATE|FRAUD|POLICY|PATTERN",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "transaction_ids": [...],
      "reason": "explanation",
      "recommendation": "action to take"
    }
  ],
  "clean_transactions": N,
  "flagged_transactions": N,
  "risk_score": 0.0-1.0
}

CONSTRAINTS:
- Use statistical methods (no hallucination)
- Flag only if confidence > 0.7
- Return ONLY valid JSON
```

**Data Source:** Output from Extraction Agent

**Phase 65 Test Point:** This agent will intentionally receive **corrupted transaction data** (mismatched hashes), and the `siss-ontology-proofs` crate will detect the **Corrupted Mesh Isolation** violation.

---

### **Agent 3: Synthesis Agent (Executive Reporter)**

**Role:** Generate boardroom-ready anomaly report  
**LLM:** Rapid-MLX (Qwen 3.5 35B)

**Prompt Template:**
```
You are a financial report writer. Given the anomalies from the 
Sentinel Agent, create an executive summary:

1. EXECUTIVE SUMMARY (200 words):
   - Total transactions analyzed
   - Anomalies found (count + risk level)
   - Top 3 recommendations

2. DETAILED FINDINGS (by severity):
   - CRITICAL: [list all critical anomalies]
   - HIGH: [list all high-severity issues]
   - MEDIUM: [sample of medium issues]

3. ROOT CAUSE ANALYSIS:
   - Most common anomaly type
   - Potential systemic issues
   - Organizational patterns

4. RECOMMENDATIONS:
   - Immediate actions (this week)
   - Short-term improvements (this month)
   - Long-term controls (this quarter)

OUTPUT: Markdown format (readable, no JSON)
CONSTRAINTS:
- Cite specific transaction IDs
- Quantify every claim
- Be actionable and specific
```

**Data Source:** Output from Sentinel Agent

**Phase 65 Test Point:** Mid-report generation, we will **physically kill the network connection** (simulating infrastructure failure). The `siss-audit-archiver` will route all telemetry to `hot_storage`, preserving the partial report until network recovery.

---

## 4. MCP SERVER ARCHITECTURE

### **4.1 Database MCP Connector**

**File:** `crates/siss-mcp-gitnexus/src/db_connector.rs` (NEW)

```rust
pub struct DatabaseMCPServer {
    pool: sqlx::PgPool,
    cache: Arc<Mutex<HashMap<QueryKey, QueryResult>>>,
}

impl DatabaseMCPServer {
    pub async fn query_transactions(
        &self,
        start_date: String,
        end_date: String,
        filters: Option<TransactionFilter>,
    ) -> Result<Vec<Transaction>, MCPError> {
        // Query PostgreSQL
        // Rows → Transaction structs
        // Cache results
        // Return JSON via MCP
    }

    pub async fn query_vendors(&self) -> Result<Vec<Vendor>, MCPError> {
        // SELECT DISTINCT vendor FROM transactions
    }

    pub async fn query_summary(&self) -> Result<SummaryStats, MCPError> {
        // Aggregate: total spend, vendor count, category distribution
    }
}
```

**MCP Resource Schema:**
```json
{
  "type": "database",
  "methods": [
    {
      "name": "query_transactions",
      "params": ["start_date", "end_date", "filters"],
      "returns": "Vec<Transaction>"
    },
    {
      "name": "query_vendors",
      "params": [],
      "returns": "Vec<Vendor>"
    }
  ]
}
```

### **4.2 Claude-Mem Integration**

**File:** `crates/siss-event-log/src/claude_mem_bridge.rs` (NEW)

```rust
pub struct ClaudeMemBridge {
    db: sqlite::Connection,
    vector_store: Arc<Mutex<ChromaDB>>,
}

impl ClaudeMemBridge {
    pub async fn capture_reasoning(&self, agent: &str, reasoning: &str) {
        // Store (agent, timestamp, reasoning) in SQLite
        // Embed reasoning via sentence-transformers
        // Store vector in Chroma
        // Tag with: [agent_id, phase, task_id]
    }

    pub async fn retrieve_context(&self, query: &str) -> Vec<MemoryEntry> {
        // Vector search in Chroma
        // Retrieve top-K similar reasonings
        // Return with metadata
    }

    pub async fn compress_and_summarize(&self, agent: &str) -> String {
        // Retrieve all reasoning for agent
        // Compress via small LLM (Phi 3 1B)
        // Return compressed summary
    }
}
```

### **4.3 SovereignNexus Phase 65 Integration**

**File:** `crates/siss-feedback-router/src/sbos_integration.rs` (NEW)

```rust
pub struct SBOSFeedbackRouter {
    task_router: Arc<AsyncTaskRouter>,
    swarm_state: Arc<tokio::sync::Mutex<SwarmState>>,
    audit_archiver: Arc<AuditArchiver>,
}

impl SBOSFeedbackRouter {
    pub async fn route_agent_task(&self, agent: &str, task: AgentTask) -> Result<TaskId, Error> {
        // Submit to AsyncTaskRouter
        // Track peak_active_task_count (10k saturation test)
        // Return task_id
    }

    pub async fn validate_agent_output(&self, output: &str) -> Result<(), ProofError> {
        // Recompute proof_hash
        // Verify against expected hash (corruption detection)
        // Return validation result
    }

    pub async fn archive_agent_telemetry(&self, telemetry: &Telemetry) {
        // Add to audit archiver
        // If S3 fails, route to hot_storage (fail-closed test)
    }
}
```

---

## 5. DATA SOURCES & CONFIGURATION

### **5.1 Database Connection**

**Option A: PostgreSQL (Production)**
```toml
[sbos]
database_url = "postgresql://user:password@localhost:5432/partner_db"
query_timeout_ms = 5000
max_connections = 20
```

**Option B: CSV File (Testing)**
```toml
[sbos]
csv_path = "/data/transactions_2019_2024.csv"
columns = ["date", "amount", "vendor", "category", "description"]
```

**Option C: S3 CSV (Cloud Source → Local)**
```toml
[sbos]
s3_bucket = "partner-finance"
s3_prefix = "exports/transactions/"
local_cache = "/tmp/sbos_transactions"
```

### **5.2 Agent Configuration**

```toml
[sbos.agents]
extractor_model = "Qwen 3.5 35B"        # Via Rapid-MLX
sentinel_model = "Qwen 3.5 35B"
synthesis_model = "Qwen 3.5 35B"
inference_server = "http://localhost:8000" # Rapid-MLX API

[sbos.agents.extraction]
timeout_seconds = 300
max_concurrent_queries = 100  # Triggers 10k saturation test
batch_size = 1000

[sbos.agents.sentinel]
anomaly_threshold = 0.7      # Confidence cutoff
duplication_window_hours = 24
policy_whitelist_path = "/data/vendor_whitelist.json"

[sbos.agents.synthesis]
report_format = "markdown"
executive_summary_words = 200
include_recommendations = true
```

---

## 6. PHASE 65 WEAPONIZATION PLAN

### **Test 1: 10k Saturation Trap**

**Trigger:** Extraction Agent spawns 1,000+ concurrent database queries  
**Expected Behavior:**
```
Step 1: Agent queries DB for 2019-2024 transactions
Step 2: 1,000 sub-tasks spawn (one per month × years × vendors)
Step 3: AsyncTaskRouter.submit_task() is called 1,000 times
Step 4: Queue fills (capacity = 100)
Step 5: Semaphore throttles to 5 permits
Step 6: peak_active_task_count() = 5 (verified)
Step 7: Remaining 900+ tasks queue until workers free up
Step 8: No OOM crash ✓
```

**Metrics to Capture:**
- `peak_active_task_count` (must be ≤ 5)
- Memory usage (must stay < 500MB)
- Task completion rate (100% eventually)

---

### **Test 2: Corrupted Mesh Isolation**

**Trigger:** Sentinel Agent receives tampered transaction data  
**Attack Vector:** Mid-swarm, inject a transaction with mismatched `proof_hash`

```rust
// Attacker modifies: transaction.amount = 9999.99
// But keeps old proof_hash (now mismatched)
let tampered_tx = Transaction {
    amount: 9999.99,  // CHANGED
    proof_hash: "sha256:abc123...",  // OLD HASH (now wrong)
};
```

**Expected Behavior:**
```
Step 1: Sentinel Agent receives tampered transaction
Step 2: Calls siss-ontology-proofs::validate_proof()
Step 3: Recomputes hash from transaction data
Step 4: Detects HASH_MISMATCH
Step 5: Returns Err("HASH_MISMATCH: expected X, got Y")
Step 6: Sentinel Agent logs corruption event
Step 7: Continues with remaining clean transactions ✓
```

**Metrics to Capture:**
- Detection latency (must be < 10ms)
- False negative rate (must be 0%)
- System resilience (continues processing)

---

### **Test 3: Network Sever Fail-Closed**

**Trigger:** Kill internet midway through Synthesis Agent report generation  
**Attack Vector:** Physical network disconnect (unplug ethernet / WiFi off)

**Expected Behavior:**
```
Step 1: Synthesis Agent generating report (50% complete)
Step 2: Network connection dies
Step 3: S3 upload fails → Timeout error
Step 4: siss-audit-archiver.archive_to_s3() returns Err
Step 5: Routed to hot_storage HashMap (local memory)
Step 6: Partial report + telemetry preserved in-memory
Step 7: Synthesis Agent continues (using cached data)
Step 8: Report completes locally
Step 9: Network restored
Step 10: hot_storage batch-syncs to S3 ✓
```

**Metrics to Capture:**
- Time to detect failure (< 100ms)
- Data preservation rate (100% in hot_storage)
- Recovery time (< 5s after network restore)

---

## 7. EXECUTION TIMELINE

| Phase | Duration | Action |
|-------|----------|--------|
| **Pre-Deploy** | 1 day | Confirm DB access, data schema, compliance review |
| **Setup** | 1 day | Spin up Rapid-MLX, AoE framework, MCP servers |
| **Agent Dev** | 2 days | Create 3 agent prompts, test locally |
| **Integration** | 1 day | Wire agents → MCP → Phase 65 crates |
| **Test 1 (10k Saturation)** | 1 day | Run extraction swarm, validate peak_active_count |
| **Test 2 (Corruption)** | 1 day | Inject tampered proofs, verify rejection |
| **Test 3 (Network Sever)** | 1 day | Network blackout test, verify hot_storage |
| **Report** | 1 day | Generate final metrics, create Nebius pitch deck |
| **TOTAL** | **9 days** | **End-to-End Financial Swarm Pilot** |

---

## 8. SUCCESS CRITERIA

| Criterion | Target | Metric |
|-----------|--------|--------|
| **10k Saturation** | peak_active_task_count ≤ 5 | Atomic counter verification |
| **Corrupted Mesh** | Detection latency < 10ms | HASH_MISMATCH error raised |
| **Network Sever** | Data preservation 100% | hot_storage contains all telemetry |
| **Business Outcome** | Financial report generated | Markdown report with findings |
| **Zero Cloud Exposure** | All inference local | No external API calls logged |
| **Test Coverage** | 3 Phase 65 constraints verified | Real-world stress test passed |

---

## 9. SAFETY & COMPLIANCE

### **9.1 Data Protection**

✓ **All processing local** (no cloud upload)  
✓ **Encrypted at rest** (if stored to disk)  
✓ **No PII logging** (transaction description only, not cardholder data)  
✓ **Audit trail** (all access logged via siss-audit-archiver)  
✓ **Access control** (API keys, database credentials in environment vars)

### **9.2 Rollback Plan**

- If Test 1 fails: Reduce concurrency to 500 tasks; re-run
- If Test 2 fails: Investigate proof generation; check hash computation
- If Test 3 fails: Increase hot_storage buffer size; retry network failure
- If financial report is incorrect: Disable inference; run with manual rules

---

## 10. DELIVERABLES

**Upon Completion:**

1. ✓ **Financial Anomaly Report** — Markdown file with real findings
2. ✓ **Phase 65 Validation Metrics** — JSON with 3 test results
3. ✓ **Nebius Pitch Deck** — "Autonomous Financial Intelligence at Zero Cloud Cost"
4. ✓ **Agent Reasoning Log** — claude-mem captured all decisions
5. ✓ **SovereignNexus Code Changes** — New MCP servers, SBOS integration

---

## 11. NEXT STEPS

**Before Proceeding, Confirm:**

1. [ ] **Database Access:** PostgreSQL connection string (or CSV path)
2. [ ] **Data Scope:** How many years of transactions? (recommend 3-5)
3. [ ] **Compliance:** Any regulatory constraints (PCI, GDPR)?
4. [ ] **Rapid-MLX Setup:** Is Apple Silicon machine ready? (M1/M2/M3)
5. [ ] **Timeline:** 9-day pilot acceptable?

**Upon Confirmation:** I will generate:
- Agent prompt templates (ready-to-deploy)
- MCP server boilerplate code
- AoE orchestration scripts
- Phase 65 integration hooks

---

**STATUS: AWAITING FINAL AUTHORIZATION & DATA ACCESS CONFIRMATION**

Shall we proceed?
