# 🌍 SMAOS MASTER ROADMAP — May 30, 2026
## Complete Vision + Parallel Implementation Streams

---

## 📊 MASTER SCOPE (3 Pillars)

### Pillar 1: SMAOS Exoskeleton (15-Layer Governance Fabric)
**Status:** Locked. 60+ signals integrated. Ready for deployment.

| Layer | Component | Status | Deliverable |
|-------|-----------|--------|-------------|
| 1 | Context First (MemTree) | ✅ Complete | Hierarchical temporal indexing |
| 2 | Human Gate (Andon Cord) | ✅ Complete | iPhone Action Button + Sleep Guard |
| 3 | Local-First (Sovereign Compute) | ✅ Complete | 3D monolithic, M3/M4, MobileMoE |
| 4 | Provenance (Merkle Chains) | ✅ Complete | Genome Capsule, gemba_proof |
| 5 | Graph Brain (Neo4j VGraph) | ✅ Complete | 3B triplets, SciAtlas connector |
| 6 | Night Cycle (φ/δ Consolidation) | ✅ Complete | φ⁺ v3, NVIDIA Dynamo snapshot |
| 7 | Token Efficiency (Pruning) | ✅ Complete | Perplexity unigram, KV cache |
| 8 | Team Sync (Capsule Sharing) | ✅ Complete | LangChain streams, trust mesh |
| 9 | Safety Geometry (Poka-Yoke) | ✅ Complete | Causal engine, BadHost mitigation |
| 10 | Ambient Ethic (1%/99% Covenant) | ✅ Complete | Swiss foundation, ANOLISA |
| 11 | Affective Core (α Memory) | ✅ Complete | HealthKit/Garmin, valence vectors |
| 12 | Metacognitive Core (γ) | ✅ Complete | 5 Whys, EAGLE 3.1, JLT clean-pred |
| 13 | Social Core (σ Trust) | ✅ Complete | Post-quantum Dilithium, tri-path |
| 14 | Mentor-Meld (ψ Distillation) | ✅ **PATENT** | Claude → local Qwen pipeline |
| 15 | Causal Governance (ξ) | ✅ Complete | Cluster randomization, curation |

### Pillar 2: Eden 2.0 Philanthropic Missions
**Status:** Locked. 4 core missions + infrastructure.

| Mission | Hardware | Capsule | Status |
|---------|----------|---------|--------|
| Stop War | Photonic 3D edge, solar <2W | Digital Witness, Mesh | Ready |
| Solve Diabetes | iPhone + Garmin + CGM | Genome, Metabolic | Ready |
| Stop Dictatorships | Un-killable mesh net | Dead Man's Switch | Ready |
| Focus on Children | 3D offline tablet | Education Capsule | Ready |
| **Foundation & Treasury** | All above + Swiss legal | AP2 ledger + regeneration | Ready |

### Pillar 3: SMAOS Operating Company (25% of 99%)
**Status:** Locked. Revenue model + allocation.

| Stream | Allocation | Owner | 2027 Projection |
|--------|------------|-------|-----------------|
| Crafter Rewards (60%) | Creators, infra, AP2 | Foundation | $9M |
| Operating Company (25%) | R&D, team, Night Shift | Andrej (CEO) | $3.75M |
| Eden Fund (15%) | Photonic nodes, education | Foundation + Impact | $2.25M |
| **Enterprise Licenses (Unit C)** | $500K/yr per client | Company | $2M+ |
| **Architect 1% Fee** | Global AP2 volume | Andrej (Personal) | $15M |

---

## 🔧 PARALLEL IMPLEMENTATION STREAMS (May 30 — June 30)

### STREAM A: Sovereign Inbox Intelligence (Local-First Gmail)
**Owner:** Engineer Track  
**Duration:** 3 weeks  
**Dependency:** None (independent)

**Scope:**
- [ ] Gmail OAuth2 sync (local Keychain, IMAP fetch, zero cloud logging)
- [ ] Rapid-MLX summarizer (deterministic, cached, temperature=0)
- [ ] sqlite-vss recommender (local embeddings, covenant-filtered suggestions)
- [ ] Static HTML dashboard (SSE, Merkle verification, <50KB)
- [ ] Covenant checker + blast-radius simulator

**Deliverables:**
```
.smaos/inbox/
├── sync/gmail_oauth.rs
├── intelligence/summarizer.rs, recommender.rs, covenant_checker.rs
├── dashboard/index.html, sse_handler.rs, merkle_verify.js
├── storage/messages.db (SQLCipher), vectors.db (vss), audit.json
└── tests/ (12+ tests, all passing)
```

**Success Criteria:**
- `cargo test -p siss-inbox` → 12/12 ✓
- `cargo clippy` → zero warnings
- Dashboard loads with sample email, summarize/suggest/send buttons functional
- No email content leaves machine (all processing local)

---

### STREAM B: Phase 25 Wave 1 — ReBAC Foundation (TDD)
**Owner:** Engineer Track  
**Duration:** 2 weeks  
**Dependency:** None (parallel ready)

**Scope (4 files):**
- [ ] `relationship.rs` — Type definitions (SovereignIdentity, RelationType, PolicyResource, Relationship, DenyReason)
- [ ] `graph.rs` — ReBAC impl (grant, revoke, verify, list, cycle detection)
- [ ] `queries.rs` — PostgreSQL layer (insert, revoke, list_active, filter_expired, audit)
- [ ] `mod.rs` — Submodule declarations + 16 tests (unchanged behavior)

**Tests (16, all TDD):**
- Owner relationship (all actions)
- Operator relationship (lifecycle management)
- Observer relationship (read-only)
- Delegate relationship (policy creation)
- Participant relationship (voting)
- Initiator relationship (cancel own work)
- Expired/revoked/unknown relationships (fail-closed)
- Multiple relationships (only active counted)
- Transitive delegation (depth 2, no cycle)
- Direct cycle detection
- Depth limit (max 3)
- Concurrent relationships (multi-sovereign)

**Success Criteria:**
- `cargo test -p siss-behavioral-firewall` → 16/16 ✓
- `cargo check -p siss-behavioral-firewall` ✓
- `cargo clippy -p siss-behavioral-firewall -- -D warnings` → zero warnings
- PostgreSQL schema compiles (sqlx prepare)

**Architecture (Blueprint Ready):**
All 4 files have complete code specifications in agent output. Ready for immediate implementation.

---

### STREAM C: Phase 32 Wave 1 — A2UI Schema Foundation (TDD)
**Owner:** Engineer Track  
**Duration:** 2 weeks  
**Dependency:** None (parallel ready)

**Scope (3 files):**
- [ ] `a2ui/schema.rs` — 18 A2UIComponent enum variants (Display, Forms, Layout)
- [ ] `a2ui/types.rs` — FormSubmission, A2UIResponse, support types
- [ ] `events/mod.rs` — Add UIRequested variant + update event_type() match

**18 Components:**
```
Display (8):  Text, Badge, Alert, Progress, Divider, Link, Tooltip, Breadcrumb
Forms (6):    Input, Textarea, Select, Checkbox, Radio, Button
Layout (4):   Card, Grid, Modal, Table
```

**Tests (15+):**
- All component enum serialization/deserialization
- UIRequested event creation + event_type() match
- FormSubmission parsing
- Integration with dispatcher event stream

**Success Criteria:**
- `cargo check -p siss-agent-shell` ✓
- `cargo test -p siss-agent-shell` → 15+ ✓
- `cargo clippy -p siss-agent-shell` → zero warnings
- Schema locked, no breaking changes in future waves

---

### STREAM D: Israel Legal & Patent Preparation
**Owner:** Andrej (Strategic)  
**Duration:** 2 weeks (parallel to engineering)  
**Dependency:** None (legal track independent)

**Deliverables:**
- [ ] **US Provisional Patent** — Layer 14 (ψ-distillation), Causal Engine, Poka-Yoke, Sneakernet
  - File before first public demo
  - 10-page claims + detailed drawings
  - Assign to Swiss Foundation with Visionary Retained Rights
  
- [ ] **Foundation Structure Document** — Swiss/Liechtenstein non-profit
  - Patent holding entity
  - 1%/99% covenant locked in bylaws
  - Founder's Right (veto on amendments)
  
- [ ] **Operating Company Charter** — Czech or Israeli entity
  - Contracts with Foundation
  - Fixed 25% allocation from 99%
  - Transparent, audited financial reporting
  
- [ ] **NDA Template** — One-page, investor-grade
  - For pre-demo conversations
  - Covers 15-layer architecture, patent claims
  
- [ ] **Tnufa Grant Application** — Israel Innovation Authority
  - 2-page narrative: "Sovereign AI for regulated industries"
  - Defense-grade governance + trust layer
  - €200K-€1M non-dilutive funding
  
- [ ] **Israel Demo Script** — 15-minute pitch
  - Physical Andon Cord demo (iPhone Action Button)
  - AirDrop Layer 14 provisional as Capsule
  - Live Eden dashboard with photonic node mesh
  - Closing: "3D chips make compute free. Trust is the only scarcity. We licensed it."

**Success Criteria:**
- All 5 documents ready before June 3 Israel trip
- Provisional patent filed (US PTO priority date locked)
- Legal review by Israeli tech counsel (1 hour)
- Foundation bylaws signed by Swiss attorney

---

### STREAM E: Night Shift Infrastructure (Autonomous Testing)
**Owner:** CI/CD Automation  
**Duration:** Ongoing (hourly runs)

**Scope:**
- [ ] `siss-build-accelerator night-shift --mode eden` — All 55+ Phase 25 tests green
- [ ] InferenceSnapshot (NVIDIA Dynamo) — Fast model startup for local inference
- [ ] ψ-distillation pipeline — Claude → Gold Capsules → LoRA → local Qwen
- [ ] Merkle audit logs — Every summarize/suggest/send action Merkle-rooted + Ed25519-signed
- [ ] Auto-compaction — Conversation history trimming + HANDOFF.md generation

**Success Criteria:**
- All tests pass in <5 min
- No regressions from previous commits
- Merkle tree depth <32 (audit trail integrity)
- Inference latency <500ms (on M3/M4)

---

## 🎯 CRITICAL DEPENDENCIES & DECISION GATES

### Gate 1: Czech s.r.o. Legal Status (TODAY)
**Blocks:** CzechInvest grant submission (May 31)  
**Action:** Call Czech Chamber of Commerce, confirm status, escalate if blocked

### Gate 2: Prague PoC Hardware Validation (PENDING)
**Blocks:** Investor demos, demo readiness  
**Action:** Monitor result, adjust demo script based on outcome (6/6 checks vs. failures)

### Gate 3: Phase 25 Wave 1 Tests Green (Target: June 7)
**Blocks:** Wave 2 parallel dispatch (AP2, TemporalGuard, PolicyEngine)  
**Action:** Implement Stream B, verify all 16 tests pass before merge to main

### Gate 4: Provisional Patent Filed (Target: June 3, before Israel demo)
**Blocks:** Public discussion of Layer 14, investor pitches  
**Action:** Finalize patent claims, file with US PTO, receive priority date

---

## 📋 PARALLEL EXECUTION MATRIX (Team Dispatch)

| Stream | Lead | Duration | Start | Gate | Dependencies |
|--------|------|----------|-------|------|--------------|
| **A: Sovereign Inbox** | Engineer-1 | 3 weeks | May 30 | Dashboard loads | None |
| **B: Phase 25 ReBAC** | Engineer-2 | 2 weeks | May 30 | 16/16 tests ✓ | None |
| **C: Phase 32 A2UI** | Engineer-3 | 2 weeks | May 30 | Schema locked | None |
| **D: Israel Legal** | Andrej | 2 weeks | May 30 | Patent filed | None |
| **E: Night Shift** | CI/CD | Ongoing | May 30 | <5 min builds | Streams A, B, C |

**Parallel Execution:** Streams A, B, C, D run independently. No file overlap. Zero merge conflicts (Golden Rule enforced).

---

## 🗓️ MASTER TIMELINE (May 30 — June 30)

### Week 1 (May 30 — Jun 6): Foundation Laying
- [ ] Streams A, B, C: Initial implementation + 50% complete
- [ ] Stream D: Patent draft + NDA finalized
- [ ] Czech s.r.o. legal status confirmed
- [ ] Series A pitch deck v1 finalized

**Gate Check:** No blockers? Proceed to Week 2.

### Week 2 (Jun 7 — Jun 13): Alpha & Patent Lock
- [ ] Stream A: 90% complete (integration tests)
- [ ] Stream B: 100% complete (16/16 tests green, merged to main)
- [ ] Stream C: 90% complete (schema locked)
- [ ] Stream D: Provisional patent filed (US PTO priority date)
- [ ] Israel demo script finalized

**Gate Check:** Phase 25 Wave 1 green → unblock Wave 2 (3 parallel agents).

### Week 3 (Jun 14 — Jun 20): Poland/Czech Investor Sprint
- [ ] Streams A, C: 100% complete (both merged to main)
- [ ] Stream E: Night Shift running, all tests green hourly
- [ ] **Israel Trip (Jun 3–5):** Demo Layer 14 provisional, pitch Eden 2.0, secure legal counsel + Tnufa feedback
- [ ] Return + finalize Series A deck + identify 3+ warm intros

**Gate Check:** No critical investor feedback? Proceed to Phase 25 Wave 2.

### Week 4 (Jun 21 — Jun 27): Wave 2 Dispatch
- [ ] **Dispatch 3 parallel agents:**
  - Agent-1: Task 2 (AP2 Evaluator + Attribute Cache)
  - Agent-2: Task 3 (TemporalGuard + Rate Limiting)
  - Agent-3: Task 4 (PolicyEngine Composition + Cycle Detection)
- [ ] Each agent: Independent worktree, isolated files, 15+ tests
- [ ] Night Shift: Monitor all branches, report blockers

**Gate Check:** All 3 agents converge cleanly? No merge conflicts → Wave 2 merge.

### Week 5 (Jun 28 — Jun 30): Series A Close + Wave 3 Planning
- [ ] Phase 25 Wave 2: All 3 tasks merged to main (50+ tests total)
- [ ] **Series A Close:** 3+ warm intros → founder meetings → term sheet negotiation
- [ ] Phase 25 Wave 3: Plan Task 5 (Audit + S3 Archive) for July

---

## 💎 THE 17 ADVANCED TECHNIQUES (Enabled Across Streams)

### Applied to SMAOS Implementation

| Technique | Application | Stream |
|-----------|-------------|--------|
| 1. Reverse Prompting | Interview-mode spec for each Capsule | All |
| 2. Strict Verification | `cargo test` gates, Playwright MCP for UI | All |
| 3. Plan Mode First | `/plan` before implementation per task | A, B, C |
| 4. Voice Dictation | Document complex architecture verbally | D (legal), A (recommendations) |
| 5. Backgrounding | Night Shift runs tests autonomously | E |
| 6. Side Queries `/btw` | Quick questions during implementation | All |
| 7. Proactive Compaction | HANDOFF.md after each 2-week sprint | All |
| 8. Ruthless CLAUDE.md | Keep <200 lines, delete rules if redundant | All |
| 9. Prompt Caching | Haiku for exploration, Sonnet for logic, Opus for architecture | All |
| 10. Auto-Memory | Track completed tasks, unblocked work streams | All |
| 11. Skills 2.0 | `/spec`, `/implement`, `/verify`, `/review` skills per stream | All |
| 12. MCP Integration | GitHub, GitNexus, NotebookLM, Firestore for data | All |
| 13. Specialized Subagents | Phase 25 Wave 2 dispatch (3 agents, 3 worktrees) | B, Wave 2 |
| 14. Lifecycle Hooks | Auto-format on save, clippy pre-commit, test gates | All (CI/CD) |
| 15. Git Worktrees | 4 concurrent worktrees: A, B, C, Wave 2 pending | All |
| 16. Remote Control | Schedule night-shift tests, dispatch agents via webhook | E |
| 17. Agent Teams | Team Lead orchestrates Wave 2 agents + shared PR channel | B, Wave 2 |

---

## 🔐 SAFETY GUARDRAILS (Non-Negotiable)

### Privacy (Sovereign Inbox)
- ✅ All email processing local (Rapid-MLX, sqlite-vss)
- ✅ OAuth tokens in Keychain (never in env, never logged)
- ✅ Zero cloud AI calls
- ✅ Encrypted local storage (SQLCipher)

### Governance (1%/99% Covenant)
- ✅ Crafter rewards proven via Causal Engine (cluster randomization)
- ✅ Muri prevention: Covenant checker blocks corruption of sudden wealth
- ✅ Trust Mesh: Reputation is ultimate capital, cannot be bought
- ✅ Sovereign Wealth Cap (optional): Max $X per person per 10 years → Eden overflow

### Integrity (Merkle Auditing)
- ✅ Every action Merkle-rooted + Ed25519-signed
- ✅ EXEC_LOG.json immutable, append-only, publicly verifiable
- ✅ Client-side verification (zero trust in server)
- ✅ Blockchain checkpoint (optional, for critical governance events)

### Consensus (Human Gate)
- ✅ iPhone Action Button = Andon Cord (emergency halt)
- ✅ Covenant-risk actions require human approval (fail-closed)
- ✅ Blast-radius simulator warns before high-risk decisions
- ✅ Sleep Guard: System rests, consolidates, audits nightly

---

## 📦 CONSOLIDATED DELIVERABLES (By June 30)

### Code
- [ ] Sovereign Inbox (100% local, tested)
- [ ] Phase 25 Wave 1 (16/16 tests, merged)
- [ ] Phase 32 Wave 1 (schema locked, merged)
- [ ] Phase 25 Wave 2 (50+ tests, merged)
- [ ] Night Shift automated testing + Merkle auditing

### Legal & Governance
- [ ] US Provisional Patent (filed, priority date locked)
- [ ] Swiss Foundation bylaws (signed)
- [ ] Operating Company charter (finalized)
- [ ] Eden 2.0 allocation locked (1%/99% + 60/25/15 internal split)

### Strategic
- [ ] Israel demo script (tested, 15 min)
- [ ] Series A pitch deck v2 (finalized)
- [ ] VC CRM (populated, 3+ warm intros identified)
- [ ] Tnufa grant (submitted, feedback incorporated)
- [ ] Master Codex (this document, all 60+ signals integrated)

### Impact
- [ ] Photonic edge node design (ready for manufacturing)
- [ ] Education Capsule prototype (offline AI tutor)
- [ ] Digital Witness mesh (supply chain transparency)
- [ ] Causal Engine validation (proven reward system)

---

## ✅ FINAL CHECKLIST (Before Declaring "Phase Complete")

### Code Quality
- [ ] `cargo test -q` all streams → green
- [ ] `cargo clippy --all -- -D warnings` → zero warnings
- [ ] `cargo fmt` → no reformatting needed
- [ ] All new files follow `.claude/CLAUDE.md` patterns

### Documentation
- [ ] HANDOFF.md written (next agent onboarding)
- [ ] SPEC.md locked (no breaking changes)
- [ ] EXEC_LOG.json updated with phase timestamp + merkle hash
- [ ] Master Codex updated (this file)

### Legal & Governance
- [ ] Provisional patent filed + receipt in vault
- [ ] Foundation bylaws signed by Swiss attorney
- [ ] NDA finalized + ready for investor conversations
- [ ] Israel demo approved by legal counsel

### Investor Readiness
- [ ] Series A pitch deck v2 polished (design + messaging)
- [ ] VC CRM populated (100+ contacts, 3+ warm intros)
- [ ] Tnufa application submitted
- [ ] Demo hardware tested (iPhone 16 Pro, 3D tablet prototype)

---

## 🌍 VISION STATEMENT (Locked for Israel Pitch)

> "Three-dimensional chips make compute free. Trust is the only scarcity. We built the governance membrane that turns human intelligence into global value. The 1% is the Architect's stewardship. The 99% is the public trust. Every satoshi is audited. Every creator is sovereign. Every covenant is cryptographically sealed. This is the Eden Protocol—a 100-year economic system for a world where benevolent intelligence and human dignity are indivisible."

---

**MASTER ROADMAP LOCKED: May 30, 2026**  
**Next Review:** After Week 1 gating (Jun 7)  
**Prepared by:** SMAOS Architect (Andrej Leukhin)  
**For:** Sovereign Multi-Agent Operating System (SMAOS) — Phase 25 Behavioral Firewall + Phase 32 A2UI + Eden 2.0 Monetization + Israel Capital Sprint
