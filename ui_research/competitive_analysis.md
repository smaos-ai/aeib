# SMAOS UI/UX Competitive Analysis & Dashboard Architecture

## Executive Summary
SMAOS requires a **6-dashboard operational control plane** positioned as "Palantir Foundry for edge-native compliance." The visual layer makes governance visible in 5 seconds while cryptographic proofs (7 artifacts) provide institutional trust.

---

## Part 1: Competitive UI/UX Landscape

### 1. Palantir Foundry (Enterprise Standard)
**Pattern:** Declarative object-driven UI, live event streaming, approval gates
- **Strengths:** 
  - Ontology-based object models drive UI dynamically (not hardcoded)
  - Real-time collaboration (Workspace → Ontology App → live updates)
  - Built-in approval workflows (revertible branches, audit trails)
  - Enterprise trust model (CISO-friendly, immutable records)
- **Cost:** $500K+/year enterprise licensing
- **SMAOS Equivalent:** Use evidence_by_process JSONB as micro-ontology. Emit A2UI primitives instead of Foundry widgets.

### 2. Agent of Empires (AoE, njbrake)
**Pattern:** Multi-agent ops tower, WebSocket live streams, session tabs
- **Strengths:**
  - Multi-agent task dashboard (see 3+ agents running simultaneously)
  - Live terminal streaming (agent reasoning visible in real-time)
  - Browser + PWA mobile support (no install needed)
  - Session tabs (context switching without losing state)
- **Tech:** Astro + TypeScript + WebSockets
- **SMAOS Equivalent:** Use SSE instead of WebSockets (simpler, HTTP-native). Implement 3-pilot card view instead of agent tower.

### 3. Craft Agents OSS (Lukilabs)
**Pattern:** Polished component library, theme customization, consumer-grade UX
- **Strengths:**
  - shadcn/ui components (TailwindCSS v4, accessible by default)
  - Document-centric UI (not code-centric)
  - Dark mode + light mode out of box
  - Responsive (mobile first)
- **Tech:** React + shadcn/ui + Tailwind v4
- **SMAOS Pick:** Use this tech stack exactly. Provides professional polish without frontend engineering overhead.

### 4. JetBrains Fleet IDE
**Pattern:** Live collaborative editing, minimalist dark theme, fast navigation
- **Strengths:**
  - Breadcrumb navigation (context clarity)
  - Minimalist sidebar (focus on content)
  - Inline error/success indicators (no modal spam)
  - Command palette (power users love it)
- **SMAOS Equivalent:** Implement breadcrumb (Command Center → Evidence → CanIRun Report). Add command palette for power users.

### 5. VS Code Remote
**Pattern:** Unified workspace + execution traces
- **Strengths:**
  - Local/remote transparently connected
  - Execution breadcrumbs (where did this value come from?)
  - Sidebar organization (Explorer, Search, Run & Debug)
- **SMAOS Equivalent:** Show L1→L8 layer trace in sidebar. Each decision linked to proof artifact.

---

## Part 2: SMAOS 6-Dashboard Architecture

### Dashboard 1: Command Center (Hub)
**Purpose:** The "first screen" — immediate operational status
**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│                   SMAOS COMMAND CENTER                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ Pilot Status Cards (3-column grid) ─────────────────┐  │
│  │                                                       │  │
│  │  [Hotel]              [Glass]              [School]   │  │
│  │  Decisions: 245       Decisions: 178       Decisions: 92  │
│  │  Pending Approvals: 2 Pending: 0          Pending: 1     │
│  │  Risk: MEDIUM         Risk: LOW           Risk: LOW       │
│  │  [View] [Drill-In]    [View] [Drill-In]   [View] [Drill] │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Real-Time Metrics Row ──────────────────────────────┐  │
│  │ Tokens: 1.2M │ Cost: $47.30 │ Latency: 89ms │ QPS: 12  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Live Agent Reasoning Stream (scrollable) ───────────┐  │
│  │ [L1] Policy routing: Article 50 (Employment)         │  │
│  │ [L2] Retrieval: Confidence 94%, matched docs: 3      │  │
│  │ [L3] Gate check: PASSED (risk < threshold)           │  │
│  │ [L4] Awaiting human approval...                       │  │
│  │ ▌ [Approve w/ signature] [Reject w/ signature]        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Approval Queue (Red Alert Section) ──────────────────┐ │
│  │ [PENDING] Hotel applicant Jane Smith (confidence 78%) │ │
│  │ [ESCALATED] Glass CAD safety violation (manual review)│ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```
**Color Scheme:** Dark background, green (safe) → yellow (medium) → red (critical)
**Key Metrics:** Live token count, cost, latency, approval queue size
**Wow Factor:** Agent reasoning visible in real-time. Human veto gate front-and-center.

---

### Dashboard 2: Evidence & Proof Gallery
**Purpose:** "Every claim is cryptographically proven"
**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│              EVIDENCE & PROOF ARTIFACTS (7 Cards)           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ Card 1: CanIRun ──────┐  ┌─ Card 2: FreeToken ──────┐ │
│  │ ✓ Local GPU Detected   │  │ 39.3 tok/s (RTX 4060)     │ │
│  │ ✓ Zero server calls    │  │ Cost saved: $427/month    │ │
│  │ Grade: S               │  │ Benchmark: PASSED         │ │
│  │ [View Report] [Verify] │  │ [View Logs] [Rerun Test]  │ │
│  └────────────────────────┘  └───────────────────────────┘ │
│                                                             │
│  ┌─ Card 3: agentacct ────┐  ┌─ Card 4: unlazy Gates ──┐  │
│  │ Work Receipts: 245     │  │ CHECK→EXPECT→EVIDENCE    │  │
│  │ Total cost: $47.30     │  │ Gates active: 4/4        │  │
│  │ Avg confidence: 89%    │  │ False positives: 0       │  │
│  │ [View JSON] [Export]   │  │ [View Ledger] [Test]     │  │
│  └────────────────────────┘  └──────────────────────────┘  │
│                                                             │
│  ┌─ Card 5: Is Agentic ──┐  ┌─ Card 6: RAGAS 50Q ─────┐   │
│  │ Grade: A+ (92/100)    │  │ Accuracy: 87.3%          │   │
│  │ 118-check baseline    │  │ Top citations: Art 50    │   │
│  │ [View Audit] [Radar]  │  │ [View Results] [Eval]    │   │
│  └───────────────────────┘  └──────────────────────────┘   │
│                                                             │
│  ┌─ Card 7: AP2 Ledger PQC ────────────────────────────┐  │
│  │ Git commits: 47        Signed with Ed25519           │  │
│  │ Latest hash: a16f164c5... (2 hours ago)             │  │
│  │ Immutability: VERIFIED (cannot rewrite)            │  │
│  │ [View Git Log] [Verify Signature] [Historical View] │  │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```
**Key Interactions:** Click any card → drill into full report, rerun validation, view historical audits
**Wow Factor:** Cryptographic verification visible. "Every claim verified by math."

---

### Dashboard 3: Governance Timeline
**Purpose:** "This was built to compliance schedule, not hacked together"
**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│         GOVERNANCE TIMELINE: Sep 1 2026 — May 31 2027       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Legend: ● CRITICAL (red) ● HIGH (orange) ● MEDIUM (yellow)│
│                                                             │
│  Sep 1 ─────────────────────────────────────────────── May  │
│     ↓                                                      31│
│     [L1 Live] ─→ [L2 Ready] ─→ [L3 Gates] ─→ [L4 Pilots] │
│        2w          2w             2w           4w           │
│                                                             │
│  KARP Submission Window (Sep 16-22)         Phase 1 Complete│
│  └────────────────────────────┘              └──────────┘  │
│                                                             │
│  Click any milestone → see all decisions made on that date  │
│  Click any date → filter evidence_by_process records       │
│                                                             │
│  Overlay: Agent reasoning events (shown as red/yellow dots)│
│  "Oct 1: 5 CRITICAL gate checks"                          │
│  "Oct 15: RAGAS evaluation started (87%+ target)"         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
**Wow Factor:** Shows progress against a "real" EU compliance schedule, not arbitrary deadlines.

---

### Dashboard 4: Pilot Operations (Tabbed)
**Purpose:** "Watch the AI work in real use cases"
**Tabs:** Hotel | Glass | School

**Tab A: Hotel Credit Scoring**
```
┌─────────────────────────────────────────────────────────────┐
│  HOTEL CREDIT SCORING (Annex III: Employment)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Applicant: Jane Smith                                     │
│  Application ID: APP-245-2024                             │
│                                                             │
│  ┌─ Risk Assessment ──────────────────────────────────┐    │
│  │ Credit Score: 742 (Good)                           │    │
│  │ History: 3 defaults (2015-2017, resolved)         │    │
│  │ Income Verification: ✓ Verified                   │    │
│  │ Policy Check: Article 50 (Employment Discrim.)    │    │
│  │ Confidence: 89%                                   │    │
│  │ Risk Level: MEDIUM                                │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ L1→L8 Execution Trace ────────────────────────────┐    │
│  │ [L1] Policy routing → 3 candidates found          │    │
│  │ [L2] Retrieved 5 historical decisions (similar)   │    │
│  │ [L3] Gate check: ✓ PASSED (confidence > 75%)     │    │
│  │ [L4] Recommendation: APPROVE with conditions     │    │
│  │ [L5] Contacted human caseworker (MCP)           │    │
│  │ [L6] Infrastructure: <100ms latency ✓            │    │
│  │ [L7] RAGAS eval: This decision type 92% accurate │    │
│  │ [L8] Proof captured (agentacct receipt #245)    │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  APPROVAL DECISION:                                        │
│  [APPROVE] [REJECT] [ESCALATE TO MANAGER]                │
│                                                             │
│  When clicked → Modal: "Digitally sign approval"          │
│  → agentacct receipt captured with timestamp + signature  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Tab B: Glass Factory CAD Safety**
```
┌─────────────────────────────────────────────────────────────┐
│  GLASS FACTORY CAD SAFETY (Annex I: High-Risk Industry)     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Component: Furnace Door Assembly                          │
│  Design File: door_asm_v2.step (uploaded 30 min ago)      │
│                                                             │
│  ┌─ 3D CAD Viewer (left, 60% width) ────────────────────┐  │
│  │                                                       │  │
│  │   [3D Model of furnace door with annotations]       │  │
│  │   Yellow zone: Stress concentration (78% threshold)  │  │
│  │   Red zone: VIOLATION (exceeds 82% threshold)       │  │
│  │                                                       │  │
│  │   Agent annotation: "Material fatigue predicted"    │  │
│  │   Confidence: 91%                                  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Safety Analysis Report (right, 40% width) ────────┐   │
│  │ Risk Level: CRITICAL                              │   │
│  │ Policy: ISO 26262 + Annex I                       │   │
│  │ Gate Check: ✗ FAILED (confidence > threshold)    │   │
│  │                                                  │   │
│  │ Agent Recommendation: REJECT (redesign required) │   │
│  │                                                  │   │
│  │ Alternative Actions:                             │   │
│  │ • Reinforce material (Engineering review)        │   │
│  │ • Increase cooling system capacity                │   │
│  │ • Reduce operating temperature (5% loss)        │   │
│  │                                                  │   │
│  │ [APPROVE REDESIGN] [REJECT] [ESCALATE]          │   │
│  └──────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Tab C: School Access Control**
```
┌─────────────────────────────────────────────────────────────┐
│  SCHOOL ACCESS CONTROL (Annex III: Education)               │
├─────────────────────────────────────────────────────────────┤
│  Visitor: John Doe                                          │
│  Visiting: Grade 3 Classroom (Room 204)                    │
│  Purpose: Parent volunteer (approved by principal)         │
│                                                             │
│  ┌─ Identity & Background Check ──────────────────────┐    │
│  │ Name: John Doe                                     │    │
│  │ DOB: 1985-06-15                                    │    │
│  │ Criminal background check: ✓ CLEAR                │    │
│  │ Sex offender registry: ✓ NOT LISTED              │    │
│  │ Child protective services: ✓ NO FLAGS            │    │
│  │ Confidence: 98%                                   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Eligibility Decision ─────────────────────────────┐    │
│  │ Policy: Annex III (Child Safety)                 │    │
│  │ Gate Check: ✓ PASSED (all checks green)          │    │
│  │ Access Level: GUEST (limited to Room 204)        │    │
│  │ Duration: 2 hours (expires 3:30pm)               │    │
│  │ Supervision Required: YES (Principal present)    │    │
│  │                                                  │    │
│  │ [APPROVE VISIT] [DENY] [REQUEST MORE INFO]       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  When approved → Badge printed (VISITOR token)             │
│  → agentacct receipt captured with timestamp               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Wow Factor:** Three completely different use cases, same governance model. Shows scalability.

---

### Dashboard 5: Policy & Citations
**Purpose:** "Which articles trigger the most decisions?"
**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│          POLICY & CITATIONS HEATMAP                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Article Selector (Multi-select):                          │
│  [Article 10] [Article 50] [Article 52] [Article 71] ...   │
│  [Annex I] [Annex III] [TRAIGA] [NIST RMF]               │
│                                                             │
│  ┌─ Citation Frequency Heatmap ────────────────────────┐   │
│  │                                                      │   │
│  │  Article 50 (Employment)          ███████ 245 citations
│  │  Annex III (Health/Education)     ███████ 237 citations
│  │  Article 71 (Safety Critical)     ████ 89 citations
│  │  Article 52 (Data Protection)     ████ 78 citations
│  │  Article 17 (Transparency)        ██ 45 citations
│  │  Annex I (High-Risk)              ██ 34 citations
│  │                                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ Confidence Distribution (by Article) ─────────────┐   │
│  │                                                      │   │
│  │  Article 50:    90%+ confidence ████████ 198/245      │   │
│  │                 70-89% confidence ███ 47/245          │   │
│  │  Article 71:    90%+ confidence ████ 76/89           │   │
│  │                 70-89% confidence █ 13/89            │   │
│  │  [etc.]                                             │   │
│  │                                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  Click any bar → drill into all decisions citing that article
│  Filter by date range, pilot, risk level, etc.            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
**Wow Factor:** Shows SMAOS understands compliance granularly, not as a black box.

---

### Dashboard 6: Agent Performance & RAGAS
**Purpose:** "Is this accurate and fast enough?"
**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│        AGENT PERFORMANCE & RAGAS EVALUATION                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ Is Agentic 118-Check Radar Chart ──────────────────┐  │
│  │                                                      │  │
│  │           Transparency                              │  │
│  │                ◆ (85)                              │  │
│  │              /     \                               │  │
│  │        Logging ◆       ◆ Repeatability (92)        │  │
│  │           (78)  \     /                            │  │
│  │         Determinism ◆ (89)                         │  │
│  │           Safety        Robustness (94)            │  │
│  │                                                      │  │
│  │  Overall Grade: A+ (92/100)                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ RAGAS Accuracy by Question Type ──────────────────┐   │
│  │                                                     │   │
│  │  Policy Citation:         ████████ 91.2%           │   │
│  │  Concept Recall:          ███████ 87.3%            │   │
│  │  Synthesis:               ██████ 81.4%             │   │
│  │  Contextual Relevance:    ████████ 93.7%           │   │
│  │  Factual Accuracy:        █████████ 95.2%          │   │
│  │                                                     │   │
│  │  Overall: 87.8% (target 87%+) ✓ PASSED            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ Latency Monitoring (SLA: <500ms) ────────────────┐    │
│  │                                                     │    │
│  │  L2 Retrieval (BM25+pgvector): avg 87ms (✓)       │    │
│  │  L3 Gate Check: avg 34ms (✓)                      │    │
│  │  L4 Orchestration: avg 156ms (✓)                 │    │
│  │  E2E (L1→L8): p99 = 421ms (✓)                    │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Cost Breakdown ─────────────────────────────────┐      │
│  │ Tokens processed: 1.2M                           │      │
│  │ Cost per decision: $0.19                        │      │
│  │ Cost per approval: $0.01 (human time)          │      │
│  │ Total program cost: $47.30 (week ending 10/6)  │      │
│  │ Projected annual: $2,459 (vs. $312K manual)    │      │
│  │ ROI: 12.7x in Year 1                           │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
**Wow Factor:** Quantified accuracy, latency, and ROI. "This saves money AND improves quality."

---

## Part 3: 8 Critical UX Moments ("Wow Effect")

### Moment 1: The First Screen (5-second impact)
User opens dashboard. **Not a chat box.** See three pilot cards glowing with live decision counts.
```
[Hotel: 245 decisions | 2 approvals pending | MEDIUM risk]
[Glass: 178 decisions | 0 approvals pending | LOW risk]
[School: 92 decisions | 1 approval pending | LOW risk]
```
**Immediate thought:** "This is NOT a chatbot. This is operational governance."

### Moment 2: The Approval Gate (Drama moment)
Agent hits Annex III boundary. Screen freezes.
```
┌──────────────────────────────────────────────────┐
│   GOVERNANCE BOUNDARY REACHED — HUMAN REQUIRED  │
├──────────────────────────────────────────────────┤
│ Agent Proposal: APPROVE credit for Jane Smith    │
│ Policy Triggered: Article 50 (Employment Discrim)│
│ Confidence: 89%                                  │
│ Why Blocked: Manual review required (high stakes)│
│ Alternatives Considered:                         │
│  • Approve with conditions (additional docs)    │
│  • Request additional financial info            │
│  • Escalate to compliance officer               │
│                                                  │
│ [APPROVE (Sign)] [REJECT (Sign)] [MODIFY]       │
└──────────────────────────────────────────────────┘
```
**Immediate thought:** "Humans are in control. AI makes suggestions; humans decide."

### Moment 3: The Proof Gallery (Trust moment)
Click "View Proofs" → see 7 cryptographic cards.
```
CanIRun: ✓ Runs 100% locally (no server calls)
FreeToken: ✓ 39.3 tok/s on RTX 4060 (verified)
agentacct: ✓ 245 work receipts (signed)
unlazy: ✓ 4/4 gates active (blocking correctly)
Is Agentic: ✓ A+ grade (92/100, 118-check audit)
RAGAS: ✓ 87.3% accuracy (50-question golden set)
AP2: ✓ Immutable ledger (Ed25519 PQC signatures)
```
**Immediate thought:** "Every claim is mathematically proven. This is not marketing fluff."

### Moment 4: The Timeline (Credibility moment)
See actual compliance milestones mapped to dates.
```
Sep 1 [L1 Live] → Sep 8 [L2 Ready] → Sep 15 [L3 Gates] → Oct 1 [L4 Pilots]
                     ↓ KARP Submission (Sep 16-22)
                     → May 31 [Phase 1 Complete] → Series A
```
**Immediate thought:** "This was built against a real regulatory schedule, not fantasy."

### Moment 5: The Evidence Chain (Audit moment)
Click a decision → drill into evidence_by_process.
```
Decision ID: APP-245
Timeline:
  [L1] Policy router cited Article 50 (confidence 89%)
  [L2] Retrieved 5 historical decisions (BM25+pgvector, 94ms)
  [L3] Gate check: ✓ PASSED (risk < threshold)
  [L4] Caseworker Jane Doe approved (signed 10:23am CET)
  [L8] Proof captured (agentacct receipt, AP2 hash: a16f164)
```
**Immediate thought:** "I can see exactly what happened, when, and who approved it."

### Moment 6: The Cost/Efficiency Meter (ROI moment)
Dashboard shows live financials.
```
Tokens processed: 1.2M | Cost: $47.30 | Decisions: 245 | Human time: 3.5 hrs

ROI: "A human caseworker would cost $420 to make these decisions.
     This system cost $47.30 + 30 min supervision = $47.80 total.
     Savings: $372.20 per week | $19,354 per year"
```
**Immediate thought:** "This pays for itself in 2 weeks. How do we scale it?"

### Moment 7: The Live Agent Stream (Transparency moment)
Real-time reasoning visible in color-coded JSON logs.
```
[L1 - BLUE] Policy routing: "Checking Article 50 (employment discrimination)"
[L2 - GREEN] Retrieval: "Found 5 historical decisions (confidence 94%)"
[L3 - YELLOW] Gate check: "Risk score 0.34 (threshold 0.75) → PASSED"
[L4 - ORANGE] Orchestration: "Escalating to caseworker for final approval"
[L5 - PURPLE] Communication: "MCP call to hotel_pms.api/approve_booking"
[L6 - GRAY] Infrastructure: "GPU latency 87ms (under budget)"
[L7 - GRAY] Evaluation: "RAGAS score for this decision: 92%"
[L8 - GRAY] Proof: "agentacct receipt #245 captured"
```
**Immediate thought:** "No black box. I see every step. I trust this."

### Moment 8: The 3-Pilot Comparison (Scale moment)
Side-by-side cards showing all three pilots performing identically.
```
┌─────────────┬────────────┬──────────────┐
│   HOTEL     │   GLASS    │   SCHOOL     │
├─────────────┼────────────┼──────────────┤
│ Decisions   │ Decisions  │ Decisions    │
│ 245         │ 178        │ 92           │
│             │            │              │
│ Approval %  │ Approval % │ Approval %   │
│ 89.4%       │ 89.3%      │ 89.5%        │
│             │            │              │
│ Avg cost    │ Avg cost   │ Avg cost     │
│ $0.19/dec   │ $0.19/dec  │ $0.19/dec    │
│             │            │              │
│ Compliance  │ Compliance │ Compliance   │
│ 87.8%       │ 88.1%      │ 87.5%        │
│             │            │              │
│ "Identical  │ "Identical │ "Identical   │
│ performance │ performance│ performance  │
│ across 3    │ across 3   │ across 3     │
│ different   │ different  │ different    │
│ use cases"  │ use cases" │ use cases"   │
└─────────────┴────────────┴──────────────┘
```
**Immediate thought:** "This isn't a one-off prototype. It generalizes to any governance problem."

---

## Part 4: Frontend Tech Stack (SMAOS-Optimized)

### Core Framework
- **React 19** + TypeScript + Vite (fast HMR, <1s startup)
- **Reason:** Modern, stable, large ecosystem. Vite gives us <1s rebuild.

### UI Component Library
- **shadcn/ui** (Tailwind CSS v4)
- **Reason:** Accessible by default (WCAG AA), dark mode out-of-box, zero runtime JS overhead
- **Components we need:** Card, Table, Chart (Recharts), Modal, Badge, Progress, Alert, Input, Button

### Real-Time Streaming
- **TanStack Query** (async state management) + **Server-Sent Events (SSE)**
- **Reason:** Native HTTP, simpler than WebSockets, perfect for one-way agent → UI streams
- **Implementation:** `GET /api/rce/stream` emits SSE newline-delimited JSON

### Charting & Visualization
- **Recharts** (React charts, small bundle ~45KB)
- **Reason:** Composable, accessible, animation support
- **Use cases:** Radar (Is Agentic), Area (latency), Bar (citations), Timeline

### Theme & Styling
- **Tailwind CSS v4** + CSS variables for theming
- **Dark mode (default)** + Light mode toggle
- **Reason:** Minimal CSS, professional look, fast to iterate

### Syntax Highlighting
- **Prism.js** (lightweight code highlighting)
- **Reason:** Shows agent reasoning JSON with syntax colors (L1 blue, L2 green, etc.)

### Deployment
- **Vercel** (zero-config, auto-deploy on git push) OR **Docker self-hosted**
- **Build:** `npm run build` → static exports to `dist/`
- **Hosting:** Vercel CDN (global) OR nginx in Docker

### Performance Targets
- **First contentful paint:** <1s
- **Interactive:** <2s
- **SSE message latency:** <100ms (agent reasoning appears in real-time)
- **Bundle size:** <150KB JS (gzipped)
- **WCAG AA compliance:** 100%

---

## Part 5: Implementation Roadmap (Weeks 9-12, Parallel to Pilots)

### Week 9 (Sep 22-29): Dashboard 1 & 2
- **Dashboard 1: Command Center**
  - Pilot status cards (3-column grid)
  - Real-time metrics row (tokens, cost, latency, QPS)
  - SSE integration (live agent reasoning stream)
  - Approval queue (red alert section)
  - Estimated: 12 developer hours

- **Dashboard 2: Evidence & Proof**
  - 7-card gallery (CanIRun, FreeToken, agentacct, unlazy, Is Agentic, RAGAS, AP2)
  - Drill-down modals for each card
  - Validation status indicators
  - Estimated: 10 developer hours

### Week 10 (Sep 29-Oct 6): Dashboard 3 & 4
- **Dashboard 3: Governance Timeline**
  - Horizontal timeline (Sep 1 → May 31)
  - Milestone markers + date filtering
  - Agent reasoning overlay
  - Estimated: 10 developer hours

- **Dashboard 4: Pilot Operations (3 tabs)**
  - Hotel Credit Scoring (applicant profile → decision)
  - Glass Factory CAD Safety (3D viewer + heatmap)
  - School Access Control (identity check → approval)
  - L1→L8 execution trace for each
  - Estimated: 20 developer hours (CAD viewer is complex)

### Week 11 (Oct 6-13): Dashboard 5 & 6
- **Dashboard 5: Policy & Citations**
  - Citation frequency heatmap
  - Confidence distribution by article
  - Interactive filtering + drill-down
  - Estimated: 12 developer hours

- **Dashboard 6: Agent Performance & RAGAS**
  - Is Agentic radar chart
  - RAGAS accuracy by question type
  - Latency SLA monitoring
  - Cost breakdown + ROI calculation
  - Estimated: 10 developer hours

### Week 12 (Oct 13-20): Polish, Testing, Investor Demo
- End-to-end testing (all dashboards with live data)
- Performance optimization (load times, SSE stability)
- Investor demo script (5-minute walkthrough hitting all 8 UX moments)
- Security audit (no secrets exposed, HTTPS enforced, CORS locked)
- Estimated: 15 developer hours

### Total Effort: ~89 developer hours (~2.2 weeks for a single frontend engineer)
**Timeline:** Parallel to pilot execution (Weeks 9-12). Pilots generate data; UI consumes and visualizes it.

---

## Part 6: Positioning vs. Palantir

| Dimension | Palantir Foundry | SMAOS Control Plane |
|-----------|------------------|-------------------|
| **Cost** | $500K+/year | $0 (open-source) |
| **Deployment** | Cloud (AWS/Azure/GCP) | Local edge (Docker) |
| **Compliance** | US/UK-centric | EU-native (GDPR/AI Act) |
| **Setup time** | 6+ months | 4 weeks |
| **Data residency** | Must use cloud provider | 100% local (zero egress) |
| **Audit trail** | Foundry audit logs | agentacct + AP2 + Git (immutable) |
| **Integration** | Ontology objects (complex) | A2UI primitives (simple) |
| **Target user** | Enterprise analyst | Regulatory officer, Compliance manager |

**SMAOS Narrative for Investors:**
> "Palantir built the government's command center. We're building the regulatory officer's command center. For 1/100th the cost, 1/10th the setup time, and with zero-cloud privacy guarantees."

---

## Part 7: Success Metrics (By May 31 Completion)

- [ ] **Load time:** <500ms first paint
- [ ] **Uptime:** 99.5% (pilot execution period)
- [ ] **WCAG AA:** 100% compliance (accessibility audit)
- [ ] **User feedback:** "I understand every decision" (investor quote)
- [ ] **Investor reaction:** "How quickly can we scale this?" (goal)
- [ ] **Series A narrative:** "Governance made visible and verifiable" (tagline)

---

## Next Steps

1. **Weeks 9-12:** Implement 6 dashboards parallel to pilot execution
2. **Week 12:** Investor demo walkthrough (5-minute script hitting 8 UX moments)
3. **May 31:** All dashboards + pilots live and logged
4. **Jun 1:** Series A pitch deck (with dashboard screenshots)
5. **Jun 15:** Series A pitch meetings (walk in with proof + UI demonstration)

