# Offline Document Intelligence Demo App — Architectural Specification

## 1. Problem Statement

**Objective:** Build a Sovereign Intelligence Factory demonstration that processes highly sensitive, classified PDFs completely offline on a Mac Studio cluster (18GB unified memory) without leaking a single byte to the cloud.

**Constraints:**
- Zero outbound network traffic (air-gapped)
- Memory discipline: Operator Plane in terminal only (TUI via ratatui)
- Preserve 0.08s Time-To-First-Token (TTFT) guarantee via DeltaNet KV cache pruning
- Multi-agent concurrent inference without cross-contamination
- All actions gated through AP2 Timestamp and Burn Protocol (prevent replay)
- L0-L3 Context Cartography memory tiers route parsed document state

**Success Criteria:**
1. TUI renders live tmux session activity (Agent Alpha, Agent Beta isolated)
2. PDF ingestion processes classified documents through quarantine zone
3. Parsed documents flow through L0-L3 without shattering TTFT SLA
4. Concurrent agents analyze documents in parallel via DeltaNet
5. All inferences logged to immutable Policy Ledger (Phase 28)
6. No agent can replay an analysis mandate via AP2 nonce burn

---

## 2. Architecture Layers

### L0: Physical Inference Engine (Rapid-MLX)
- **Component:** rapid-mlx 0.6.4 serving qwen3.5-4b on port 8080
- **Memory Budget:** 2.5-4GB unified memory (KV cache + weights)
- **Latency SLA:** 0.08s TTFT (sub-100ms guaranteed)
- **Throughput:** 160 tok/s per concurrent request
- **Isolation:** Loopback-only (127.0.0.1:8080), no public routes

### L1: Operator Plane (TUI Layer)
- **Component:** ratatui-based terminal UI
- **Responsibilities:**
  - Render live tmux session panes (agent-alpha, agent-beta)
  - Display PDF ingestion queue and processing status
  - Show parsed document metadata (title, page count, entity extraction results)
  - Render real-time inference streams (token generation progress)
  - Visualize memory tier state (L2-L3 cache hit/miss rates)
  - Display Policy Ledger audit trail (recent actions)
- **Interaction Model:**
  - Keyboard commands: `<q>` quit, `<a>` upload PDF to Alpha, `<b>` upload to Beta, `<c>` clear cache, `<space>` pause/resume
  - Direct tmux pane switching via mouse click or `<tab>`
  - Real-time log scrolling (latest 20 actions)

### L2: Cognitive Memory Plane (Context Cartography)
- **Component:** siss-context-cartography with document-specific routes
- **Responsibilities:**
  - **Visible Field:** Currently active PDF title, page range, extracted entities
  - **Gray Fog:** Previous 3 documents analyzed in this session (compressed embeddings)
  - **Context Map:** Semantic index of entity mentions across all analyzed PDFs (cumulative this session)
  - **Data Flow:** L0 inference outputs → entity extraction → L2 routes
  - **Eviction Policy:** LRU when combined L2 state exceeds 500MB
  - **TTL:** 30-minute session window (reset on new PDF)

### L3: Durable Reasoning State (Policy Ledger + Chaos Petri Quarantine)
- **Component:** siss-enclave Phase 28 (Policy Ledger) + Phase 29 (Chaos Petri)
- **Responsibilities:**
  - **Audit Trail:** All document ingestions, agent assignments, analysis mandates
  - **Quarantine Zone:** `/var/lib/smaos/chaos_petri_quarantine/` for validating ingested PDFs
  - **Merkle Chain:** Immutable hash-linked record of all inferences
  - **AP2 Burn Log:** Executed mandates and burned nonces (replay prevention)
  - **Data Retention:** Permanent (session-independent)

### L4: Sneakernet Ingress (USB Air-Gap)
- **Component:** Phase 30 IngressGatekeeper (if PDF comes via USB)
- **Responsibilities:**
  - Validate multi-signature AP2 quorum on USB payload
  - Decrypt documents to Chaos Petri quarantine
  - Route validated docs to L2 ingestion pipeline

---

## 3. Data Models

### 3.1 PDF Ingestion Manifest
```rust
pub struct DocumentManifest {
    pub document_id: String,          // UUID
    pub filename: String,
    pub ingestion_timestamp_ms: u64,
    pub source: IngestionSource,      // USB, Loopback, Memory
    pub total_pages: usize,
    pub quarantine_path: Option<PathBuf>,
    pub status: DocumentStatus,       // Quarantined, Parsed, Indexed
    pub parsed_page_count: usize,
    pub entities_extracted: usize,
    pub l2_memory_budget_bytes: u64,
}

pub enum IngestionSource {
    UsbSneakernet,
    LoopbackApi,
    MemoryBuffer,
}

pub enum DocumentStatus {
    Quarantined,
    ParsingInProgress,
    Parsed,
    Indexed,
    AnalysisComplete,
}
```

### 3.2 Parsed Document (Post-Ingestion)
```rust
pub struct ParsedDocument {
    pub document_id: String,
    pub pages: Vec<ParsedPage>,
    pub embedding_cache: Option<Vec<f32>>,  // L2 semantic index
    pub entity_index: HashMap<String, Vec<EntityMention>>,
    pub l2_memory_used: u64,
    pub last_accessed_ms: u64,
}

pub struct ParsedPage {
    pub page_num: usize,
    pub text: String,
    pub extracted_entities: Vec<Entity>,
    pub tokens_count: usize,
}

pub struct Entity {
    pub text: String,
    pub entity_type: String,  // PERSON, ORG, LOCATION, etc.
    pub confidence: f32,
}
```

### 3.3 Analysis Mandate (AP2-Gated)
```rust
pub struct AnalysisMandate {
    pub mandate_id: String,            // UUID
    pub document_id: String,
    pub analysis_type: AnalysisType,
    pub assigned_agent: AgentSession,  // Alpha or Beta tmux pane
    pub nonce: String,                 // AP2 burn protocol
    pub timestamp_ms: u64,
    pub ttl_ms: u64,                   // 3600000 (1 hour)
    pub operator_did: Vec<u8>,         // Ed25519 public key
    pub signature: Vec<u8>,
    pub status: MandateStatus,
}

pub enum AnalysisType {
    EntityExtraction,
    SemanticSearch { query: String },
    SummaryGeneration,
    ComplianceCheck,
}

pub enum MandateStatus {
    Pending,
    Authorized,
    Executing,
    Completed { result: String },
    Failed { reason: String },
}
```

### 3.4 Agent Session (tmux Pane)
```rust
pub struct AgentSession {
    pub agent_id: String,              // "alpha" or "beta"
    pub tmux_pane: String,             // "agent-alpha-session:0"
    pub git_worktree: PathBuf,         // /worktrees/alpha or /worktrees/beta
    pub current_document: Option<String>,
    pub active_mandates: Vec<String>,
    pub inference_tokens_generated: u64,
    pub memory_tier_state: MemoryTierState,
    pub last_activity_ms: u64,
}

pub struct MemoryTierState {
    pub l2_visible_field_bytes: u64,
    pub l2_gray_fog_bytes: u64,
    pub l2_context_map_bytes: u64,
    pub l3_ledger_entries: usize,
    pub cache_hit_rate: f32,           // L2 embeddings cache
    pub ttft_last_request_ms: u64,
}
```

### 3.5 TUI State
```rust
pub struct TuiState {
    pub active_pane: ActivePane,
    pub agent_alpha: AgentSession,
    pub agent_beta: AgentSession,
    pub document_queue: Vec<DocumentManifest>,
    pub current_document: Option<ParsedDocument>,
    pub analysis_results: Vec<AnalysisMandate>,
    pub memory_pressure: f32,          // 0.0 to 1.0
    pub ttft_violation_count: u64,
    pub scroll_offset: usize,
    pub log_buffer: VecDeque<LogEntry>,
}

pub enum ActivePane {
    AlphaTmux,
    BetaTmux,
    DocumentQueue,
    AnalysisResults,
    MemoryMetrics,
}

pub struct LogEntry {
    pub timestamp_ms: u64,
    pub agent: String,
    pub event: String,
    pub severity: LogLevel,
}

pub enum LogLevel {
    Info,
    Warn,
    Error,
}
```

---

## 4. PDF Ingestion Pipeline

### Step 1: Quarantine & Validation
1. PDF arrives via loopback API or USB (Sneakernet)
2. MD5 hash computed, stored in Chaos Petri quarantine
3. If USB: AP2 multi-signature quorum check (Phase 30 IngressGatekeeper)
4. If loopback: signature optional (operator-trusted network)
5. **Guardrail:** Reject files > 100MB (memory constraint)

### Step 2: PDF Parsing
1. Extract text + metadata using `pdfium-render` crate
2. Page-by-page decomposition
3. Entity extraction via regex + NER heuristics (offline, no cloud)
4. Compute semantic embeddings using rapid-mlx (local inference)
5. **Guardrail:** If parsing takes > 2 seconds per page, split batch

### Step 3: L2 Memory Routing
1. Computed embeddings → L2 Visible Field (current page)
2. Previous page summary → L2 Gray Fog
3. Entity mentions across all pages → L2 Context Map (semantic index)
4. **Guardrail:** If L2 state exceeds 500MB, evict oldest document (LRU)

### Step 4: L3 Durability
1. Write document manifest to Policy Ledger (Merkle hash)
2. Write entity index to siss-context-cartography
3. Quarantine PDF marked as "Parsed"
4. **Guardrail:** If ledger write fails, quarantine stays locked (fail-closed)

---

## 5. Multi-Agent Orchestration (tmux)

### Session Layout
```
┌─────────────────────────────────────────────────────────┐
│ SMAOS Operator Plane (ratatui TUI)                       │
├─────────────────────────┬─────────────────────────────┤
│ Agent Alpha (tmux pane) │ Agent Beta (tmux pane)      │
│ /worktrees/alpha        │ /worktrees/beta             │
│ DeltaNet Inference      │ DeltaNet Inference          │
│ Request Window: 0-5ms   │ Request Window: 5-10ms      │
├─────────────────────────┴─────────────────────────────┤
│ Document Queue | Analysis Results | Memory Metrics     │
│ Policy Ledger Audit Trail (immutable log)              │
└─────────────────────────────────────────────────────────┘
```

### Concurrent Execution Model
1. **Alpha Agent (Pane 1):** Assigned to Entity Extraction
   - Receives document via AP2 AnalysisMandate (nonce burned)
   - Submits `POST /v1/chat/completions` to rapid-mlx
   - DeltaNet KV cache pruning ensures 0.08s TTFT
   - Results written to L3 Policy Ledger

2. **Beta Agent (Pane 2):** Assigned to Semantic Search (parallel)
   - Receives different document or different page range
   - Same rapid-mlx endpoint, different KV cache snapshot
   - No cross-contamination (isolated L2 memory per agent)
   - Results merged in TUI at analysis completion

### Isolation Guarantee (DeltaNet)
- Alpha request T0: KV cache snapshot A
- Beta request T0+1μs: KV cache snapshot B (pruned)
- Both inference pipelines execute in parallel
- Cache hit rate ≥ 95% (tokens reused from previous pages)
- **Result:** Sub-100ms TTFT for both concurrent requests

---

## 6. TUI Components & Rendering

### 6.1 Main Layout
```
┌──────────────────────────────────────────────────────┐
│ [SMAOS] Offline Document Intelligence | Memory: 67% │
├──────────────────────────────────────────────────────┤
│ α: Entity Extract | β: Semantic Search               │
├────────────────────┬────────────────────────────────┤
│ Alpha Tmux Pane    │ Beta Tmux Pane                 │
│ (20 lines)         │ (20 lines)                     │
│                    │                                 │
│ $ > last_cmd       │ $ > current_analysis           │
│ > output...        │ > inference progress...        │
├────────────────────┴────────────────────────────────┤
│ Queue: [doc1.pdf | doc2.pdf] Status: Parsing doc2   │
├──────────────────────────────────────────────────────┤
│ Log (latest 10):                                      │
│ [18:46:23.401] INFO  Alpha: Entity extraction started│
│ [18:46:23.425] INFO  Beta: Semantic index loaded     │
│ [18:46:24.102] INFO  Alpha: Mandate exec burned nonce│
└──────────────────────────────────────────────────────┘
```

### 6.2 Components
1. **Header:** App name, total memory, TTFT status
2. **Agent Panes:** Two tmux panes side-by-side (read-only mirrors)
3. **Queue Panel:** Document queue, current status, progress bar
4. **Metrics Panel:** L2 cache hit rate, L3 ledger entries, mandate burn count
5. **Log Buffer:** Scrollable audit trail (latest 20 events)

### 6.3 Interaction
- `<a>`: Upload PDF to Alpha (prompts for file path)
- `<b>`: Upload PDF to Beta
- `<tab>`: Switch focus between panes
- `<space>`: Pause/resume inference
- `<c>`: Clear L2 cache (manual eviction)
- `<l>`: Toggle log verbosity (INFO → DEBUG)
- `<q>`: Quit (graceful shutdown, save state to ledger)

### 6.4 Real-Time Updates
- Refresh rate: 100ms (10 Hz)
- **Sources of updates:**
  1. Polling `/v1/models` on rapid-mlx (health check)
  2. Reading tmux pane output via `tmux capture-pane`
  3. Querying siss-context-cartography for L2 state
  4. Reading Policy Ledger for new audit entries
  5. Checking AP2 burned nonces (mandate execution log)

---

## 7. Memory Tier Flow (No TTFT Shattering)

### Scenario: Concurrent Analysis of Two Documents

**Time T0: Alpha processes doc1 (10 pages)**
```
L0 (Inference):
  Rapid-MLX KV cache: [page1_tokens, page2_tokens, ...]
  DeltaNet pruning: Remove oldest 30% (LRU)
  
L2 (Context Cartography):
  Visible Field: page3 text + current entity mentions
  Gray Fog: pages 1-2 entity summary (compressed)
  Context Map: All entity co-occurrences (index)
  
L3 (Policy Ledger):
  Manifest: {doc1_id, 10 pages, entity count}
  Audit: "Alpha: entity extraction mandate executed"
```

**Time T0+10ms: Beta processes doc2 (in parallel)**
```
L0 (Inference):
  Rapid-MLX KV cache: NEW SNAPSHOT (Beta's request)
  DeltaNet pruning: Reuse 95% tokens from doc1 (semantic overlap)
  TTFT guarantee: Still 0.08s (cache hit rate 95%)
  
L2 (Context Cartography):
  Visible Field: page1 of doc2 (different agent session)
  Gray Fog: (empty, new document)
  Context Map: Isolated semantic index for doc2
  
L3 (Policy Ledger):
  Manifest: {doc2_id, N pages, entity count}
  Audit: "Beta: semantic search mandate executed"
```

### Memory Pressure Handling
- **If L2+L3 exceeds 14GB:** Evict oldest Gray Fog entry (LRU)
- **If L2+L3 exceeds 15GB:** Evict oldest Visible Field entry
- **If L2+L3 exceeds 16GB:** Pause new ingestion, alert operator
- **Guardrail:** Rapid-MLX always reserves 2.5-4GB (never evicted)

---

## 8. Testing Strategy

### 8.1 Unit Tests
```rust
#[cfg(test)]
mod tests {
    // Test 1: PDF quarantine and validation
    #[test]
    fn test_pdf_quarantine_and_md5_hash() { }
    
    // Test 2: Entity extraction accuracy
    #[test]
    fn test_entity_extraction_from_page() { }
    
    // Test 3: L2 memory routing (Visible Field → Gray Fog)
    #[test]
    fn test_l2_gray_fog_eviction() { }
    
    // Test 4: AP2 mandate nonce burn (replay prevention)
    #[test]
    fn test_ap2_mandate_replay_attack_prevented() { }
    
    // Test 5: DeltaNet concurrent cache isolation
    #[test]
    fn test_deltanet_kv_cache_isolation() { }
    
    // Test 6: TTFT SLA guarantee
    #[test]
    fn test_ttft_under_concurrent_load() { }
}
```

### 8.2 Integration Tests
1. **PDF Ingestion End-to-End**
   - Upload 5-page PDF → validate quarantine → parse → index → verify L3 ledger
   
2. **Concurrent Agent Analysis**
   - Alpha and Beta simultaneously analyze different documents
   - Verify no mandate nonce collision (AP2 burn works)
   - Verify TTFT ≤ 0.08s for both agents
   
3. **Memory Pressure**
   - Ingest 10 PDFs sequentially (total ~500MB parsed state)
   - Monitor L2 eviction (LRU should trigger at ~450MB)
   - Verify no TTFT degradation during eviction
   
4. **Chaos Petri Integration**
   - Inject malformed PDF (Phase 29 sensor spoofing test)
   - Verify quarantine rejects with Chaos Petri alert
   - Verify Policy Ledger logs rejection
   
5. **Sneakernet (Optional)**
   - Create USB payload with multi-signature AP2 quorum
   - Ingest via Phase 30 IngressGatekeeper
   - Verify document reaches L2 via quarantine

### 8.3 Performance Benchmarks
| Metric | Target | Method |
|--------|--------|--------|
| PDF ingestion latency | < 2s per page | Time page parse + embed |
| TUI refresh rate | 100ms (10 Hz) | Measure render time |
| TTFT (concurrent) | ≤ 0.08s | Measure Alpha + Beta overlap |
| L2 cache hit rate | ≥ 95% | Count token reuse |
| Memory footprint | ≤ 16GB total | Monitor `ps` RSS + virtual |
| AP2 nonce burn | < 1ms | Measure HashSet insert |

---

## 9. Failure Modes & Guardrails

| Failure | Guardrail | Recovery |
|---------|-----------|----------|
| PDF parse fails | Quarantine remains locked, retry prompt | Manual re-upload |
| L2 memory exhausted | Evict oldest Gray Fog (LRU) | Operator alert + log |
| TTFT exceeds 0.08s | Log warning, pause new ingestion | Clear L2 cache (`<c>`) |
| AP2 nonce collision | Reject mandate, log attempt | TUI shows "Replay blocked" |
| Rapid-MLX crash | Graceful shutdown, save state to L3 | Manual restart + resume |
| Policy Ledger write fails | Transaction rollback, fail-closed | Alert operator, quarantine stays locked |

---

## 10. Implementation Roadmap

### Phase 0: Foundation (Week 1)
- [ ] Create `crates/demo-app` crate (Rust project structure)
- [ ] Implement data models (DocumentManifest, ParsedDocument, AnalysisMandate)
- [ ] Set up ratatui TUI skeleton
- [ ] Integrate siss-context-cartography for L2 routing

### Phase 1: PDF Pipeline (Week 2)
- [ ] Implement PDF quarantine (Chaos Petri integration)
- [ ] Implement PDF parser + entity extraction
- [ ] Implement L2 memory routing (Visible Field → Gray Fog → Context Map)
- [ ] Unit tests for ingestion pipeline

### Phase 2: Agent Orchestration (Week 3)
- [ ] Tmux pane mirroring in TUI
- [ ] AnalysisMandate lifecycle (pending → authorized → executing → completed)
- [ ] AP2 mandate signing + nonce burn verification
- [ ] DeltaNet concurrent inference validation

### Phase 3: TUI & Integration (Week 4)
- [ ] Full ratatui UI (pane rendering, log scrolling, metrics)
- [ ] Real-time updates (100ms refresh)
- [ ] Keyboard interaction (`<a>`, `<b>`, `<space>`, etc.)
- [ ] Integration tests (end-to-end PDF → inference → ledger)

### Phase 4: Polish & Demo (Week 5)
- [ ] Performance benchmarking (TTFT, cache hit rate, memory)
- [ ] Chaos Petri adversarial testing (malformed PDFs, nonce collisions)
- [ ] Documentation + demo script
- [ ] Live demo execution (classified PDF analysis)

---

## 11. Specification Approval Checklist

- [ ] Data models align with L0-L3 architecture
- [ ] PDF pipeline is fail-closed (Chaos Petri quarantine enforces)
- [ ] AP2 mandate burn prevents replay (nonce uniqueness guaranteed)
- [ ] DeltaNet concurrent isolation is mathematically proven (KV cache snapshots)
- [ ] TTFT SLA is achievable (0.08s with 95% cache hit rate)
- [ ] TUI is memory-efficient (no web framework bloat)
- [ ] Failure modes have explicit guardrails (no silent crashes)
- [ ] Testing strategy covers all critical paths (unit + integration + chaos)
- [ ] Implementation roadmap is realistic (5-week sprint)

---

**Specification Status: READY FOR IMPLEMENTATION**

The Offline Document Intelligence Demo App is architecturally sound and aligned with the Sovereign Multi-Agent OS core infrastructure (Phases 28-30).
