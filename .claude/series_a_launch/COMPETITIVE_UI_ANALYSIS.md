# SMAOS UI: Competitive Analysis & Next-Gen Features

**Purpose:** Identify best-in-class UI patterns for AI governance systems  
**Sources:** CopilotKit, Cursor IDE, Claude Code, OpenAI Assistants, Anthropic A2UI  
**Date:** Sep 1, 2026

---

## 🔍 WHAT COMPETITORS DO WELL

### 1. OpenAI Assistants (Message-Based UI)
**Pattern:** Conversational thread + structured inputs side-by-side
```
Left:  Chat history (collapsible thread)
Right: Current message + structured form (API schema-based)
```
**What they do:** Context switching is seamless; you always see prior decisions

**What we should steal:**
- ✅ Collapsible thread history (show prior intents)
- ✅ Schema-driven form generation (already have this)
- ✅ Message-style ledger entries (not raw JSON)

---

### 2. Cursor IDE (Code Editor with AI Sidebar)
**Pattern:** Main editor + AI inspector pane + action buttons in-line
```
Center: Main work surface (large, scrollable)
Right:  AI reasoning/proof (reads-only, always visible)
Left:   Quick actions + settings (collapsible)
```
**What they do:** AI reasoning is VISIBLE but doesn't interrupt workflow

**What we should steal:**
- ✅ Inline action buttons (✓ Authorize / 🚫 Revise) on nodes
- ✅ Collapsible left panel (hide intent form once submitted)
- ✅ Reasoning sidebar shows WHY a decision was blocked

---

### 3. Claude Code Dashboard (Agentic UX)
**Pattern:** Task queue + live execution graph + proof artifacts
```
Top:    Task metadata (title, status, created-at)
Left:   Tool history (what was called, in order)
Center: Execution graph (DAG visualization)
Right:  Results/artifacts (generated code, files)
```
**What they do:** You can see EVERY step the agent took, in order

**What we should steal:**
- ✅ Tool call history (who called what, when)
- ✅ Argument viewer (what data went into each tool)
- ✅ Return value inspector (what came back)
- ✅ Artifact export buttons (download proof ledger as PDF/JSON)

---

### 4. Anthropic A2UI (Declarative Card Protocol)
**Pattern:** Cards describe intent → Card describes decision → Card describes action
```
Each card = one semantic unit (intent / classification / gate / execution)
```
**What they do:** Non-technical stakeholders can understand compliance decisions

**What we should steal:**
- ✅ **Rule cards** — Each triggered rule shown as a card
- ✅ **Citation cards** — Legal basis inline with the rule
- ✅ **Impact cards** — "This decision affects: CAR ↓ 0.35%, CET1 breach risk ↑ 5%"
- ✅ **Authority cards** — Who authorized (CRO name, timestamp, role)

---

### 5. Figma (Permissions & Collaboration UI)
**Pattern:** Inline permissions → action → confirmation
```
User hovers over node → sees permissions required → clicks "Request Access" → CRO notified → approval shows inline
```
**What they do:** Permissions are not a separate flow; they're in-context

**What we should steal:**
- ✅ **Inline veto gates** — Don't pop modal; show gate right on the node
- ✅ **CRO notification badge** — "CRO notified 3 min ago"
- ✅ **Approval status** — Once CRO signs, show signature timestamp + fingerprint

---

## 🎯 WHAT WE'RE SOLVING (Unique to SMAOS)

| Competitor | Solves | Missing |
|---|---|---|
| OpenAI Assistants | Conversational AI | Pre-execution gates, cryptographic proof |
| Cursor | Code editing flow | Compliance audit trail, immutable ledger |
| Claude Code | Agentic execution | Fail-closed veto gates, regulatory proofs |
| A2UI | Card protocol | Real cryptography, Basel III specifics |
| Figma | Collaboration perms | Treasury risk classification, CAR automation |

**Our moat:** We are the ONLY system that:
1. ✅ Blocks execution BEFORE it happens (fail-closed)
2. ✅ Cryptographically proves who authorized (Ed25519)
3. ✅ Connects regulatory compliance to every decision (article citations)
4. ✅ Automates Basel III CAR validation (specific to banking)
5. ✅ Provides immutable audit trail (SEC Rule 17a-4)

**Therefore, our UI should emphasize:**
- Proof/verification (not just execution)
- Regulatory citations (not just rules)
- Cryptographic assurance (not just logs)
- Fail-closed gates (not just warnings)

---

## 💡 RECOMMENDED UI FEATURES (Next Phase)

### Phase 1: Already Done ✅
- [x] 3-pane layout (intent / execution / proof)
- [x] Real-time risk preview
- [x] Proof ledger with copy-to-clipboard
- [x] Ed25519 signature verification
- [x] Network isolation badge
- [x] Live progress bar

### Phase 2: High-Impact (Implement Next)

#### 2.1 Rule Cards (Regulatory Context)
**What:** Each triggered rule appears as a card with citation
```
┌─────────────────────────────────────────┐
│ 🚫 RULE: Basel III CAR Buffer Breach    │
│                                         │
│ Triggered: CET1 10.18% < 10.50%        │
│ Impact: €32M capital shortfall          │
│                                         │
│ Legal Basis: CRR Article 92 (ECB)       │
│ Regulatory Deadline: Dec 2, 2027        │
│ Enforcement: BaFin / ECB                │
│                                         │
│ References:                             │
│   • Basel III.1, Jan 2023               │
│   • EU Directive 2013/36/EU (CRD V)     │
│   • ECB Single Rulebook Q&A             │
│                                         │
│ Status: Awaiting CRO Authorization      │
└─────────────────────────────────────────┘
```

**Why:** Regulators WANT to see citations in the UI. Proof that system knows the law.

---

#### 2.2 Impact Dashboard (CAR/Risk Visualization)
**What:** Real-time chart showing how decision affects capital ratios
```
Before:  CET1: 11.2%  |████████░░| CAR: 10.82%
Trade:   +€50M exposure
After:   CET1: 10.18% |███░░░░░░| CAR: 9.98%
                      ↓ BREACH   ↓ BREACH
```

**Why:** CROs need to see financial impact in real-time, not in a separate report.

---

#### 2.3 Inline Approval Flow (No Modal Pop-Up)
**What:** Veto gate appears INLINE in the execution graph, not in a modal
```
Center Pane shows:
[Intent] → [Tool 1] → [Tool 2] ⟶ [🔐 VETO GATE]  ← CRO authorization here
                                   Authorize | Revise

Right Pane shows:
📜 Proof Ledger (updates in real-time as CRO signs)
```

**Why:** Users shouldn't lose context when authorizing. Everything stays visible.

---

#### 2.4 Tool Argument Inspector (CopilotKit-Style)
**What:** Expand any execution node to see inputs + outputs
```
Tool: compute_cet1_capital
Inputs:
  - tier1_capital: 8,500,000,000
  - tier2_capital: 2,000,000,000
  - risk_weighted_assets: 97,032,000,000
  - cet1_threshold: 10.5

Execution: ✓ 42ms

Output:
  - cet1_ratio: 10.18%
  - is_compliant: false
  - breach_description: "CET1 10.18% < 10.50% threshold"
```

**Why:** Traders need to understand WHY the system blocked them. Show the math.

---

#### 2.5 Authority Badge (Who Signed & When)
**What:** Every proof receipt shows CRO name, role, timestamp, fingerprint
```
✓ Authorized by: Sarah Chen (CRO, Head of Risk)
  Signed: Sep 1, 2026 14:23:45 UTC
  Signature: ed25519:a7f8e9d2c1b4f6a3e5c8d1b9f2e4a6c8
  Verified: Yes (live crypto.subtle.verify)
```

**Why:** Auditors need to know WHO made each decision. Attribution = accountability.

---

#### 2.6 Timeline Visualization (Gantt-Style)
**What:** Show execution flow as a timeline, not a vertical list
```
Intent submitted:     |████|
Risk classification:        |██|
Tool 1 (prepare):                |███|
Tool 2 (execute):                    |███████|
Veto gate triggered:                         |🔐|
CRO authorization:                           |✓|
Trade executed:                                |██|

Total: 2.34 seconds
```

**Why:** Regulators care about latency. Show proof that system is <300ms.

---

#### 2.7 Regulatory Export (PDF + JSON + Signed)
**What:** One-click export of entire session as compliance package
```
Button: "📥 Export for Compliance Review"

Generates:
  1. session-proof-ledger.json (all receipts)
  2. session-audit-trail.pdf (formatted for BaFin)
  3. session-signature-verification.json (crypto proofs)
  4. session-evidence.zip (all artifacts)

Each file Ed25519-signed by system public key.
```

**Why:** UniCredit compliance team needs to submit proof to regulators. Make it a button click.

---

#### 2.8 Drift Heuristic Visualization
**What:** Live indicator showing if authorization patterns are unusual
```
Authorization Baseline: 20% of trades blocked
This Session:           32% of trades blocked
Status: ⚠️ ABOVE BASELINE

Possible causes:
  - Market volatility (CAR pressure)
  - Counterparty downgrades (RWA increased)
  - System misconfiguration

Action: Review CAR thresholds with CRO
```

**Why:** Anomaly detection helps catch operational issues early.

---

### Phase 3: Nice-to-Have (If Time)

#### 3.1 Notification Center (CRO Alert)
```
🔔 CRO Notifications
├─ 14:23 — High-risk trade from London desk (Goldman Sachs, €50M)
├─ 14:15 — CAR dropped below 10.7% (warning threshold)
└─ 14:05 — New e-signature requested (Sarah Chen)
```

#### 3.2 Replay / Audit Trail Browser
```
Play ▶️ the entire execution session step-by-step
See what the agent saw at each point
Re-verify signatures live (Shift+Click)
```

#### 3.3 A/B Test Mode (For Training)
```
What if CAR threshold was 9.5% instead of 10.5%?
This trade would: ✓ PASS (instead of BLOCK)
Impact: CET1 would be 9.18% (still breach)
```

---

## 🎨 UI PATTERN RECOMMENDATIONS

### For Veto Gates:
**CURRENT (Good):** Modal card with 2 buttons (Authorize / Revise)  
**RECOMMENDED:** Keep modal BUT add inline preview in execution graph showing "🔐 PENDING_CRO_AUTH (Sarah Chen notified)"

### For Proof Ledger:
**CURRENT (Good):** Expandable cards with JSON payload  
**RECOMMENDED:** Add "Message-style" view (like Slack) where each receipt reads like a sentence:
```
✓ 14:23:45 — Trade AUTHORIZED by Sarah Chen (CRO)
  Reason: CAR buffer breach justified by Q3 rebalancing plan
  Signature: ed25519:a7f8... (verified)
  References: CRR Article 92, ECB guidance

🔧 14:23:02 — Trade CLASSIFIED as high-risk (€50M, CAR-impacting)
  Rules: Basel III CAR Buffer (CET1 < 10.5%)
  Impact: €32M capital shortfall

📤 14:22:58 — Trade SUBMITTED by London desk
  Amount: €50M, Counterparty: Goldman Sachs
  Instrument: Corporate Bond
```

### For Execution Graph:
**CURRENT (Good):** Timeline with status icons  
**RECOMMENDED:** Add "Swim lanes" (one lane per actor):
```
System Lane:    [Intent] → [Classify] → [Build Graph] → [Execute] ⟶ [Veto]
CRO Lane:       (waiting)                                            [Authorize]
Compliance Lane: (monitoring)                                        (recording)
```

---

## ✅ IMPLEMENTATION PRIORITY

| Feature | Impact | Effort | Score | Recommend |
|---------|--------|--------|-------|-----------|
| Rule Cards | ⭐⭐⭐⭐⭐ | 2 days | 10 | **DO NOW** |
| Impact Dashboard | ⭐⭐⭐⭐ | 1.5 days | 9 | **DO NOW** |
| Inline Approval | ⭐⭐⭐⭐ | 1 day | 9 | **DO NOW** |
| Tool Inspector | ⭐⭐⭐⭐ | 2 days | 8 | NEXT |
| Authority Badge | ⭐⭐⭐⭐ | 1 day | 8 | NEXT |
| Timeline Viz | ⭐⭐⭐ | 2 days | 7 | STRETCH |
| Compliance Export | ⭐⭐⭐⭐ | 1.5 days | 8 | NEXT |
| Drift Heuristic | ⭐⭐⭐ | 1 day | 6 | POLISH |

---

## 🎯 RECOMMENDATION FOR UNICREDIT PILOT

**For Oct 1-31 pilot:** Implement Priority 1 + 2 features
- Rule Cards (shows them we understand EU AI Act + Basel III)
- Impact Dashboard (shows them real CAR impact)
- Inline Approval (shows them seamless UX)
- Compliance Export (shows them we're audit-ready)

**By Nov 1 (production go-live):** Add Priority 3
- Tool Inspector (traders need to understand system)
- Authority Badge (auditors need attribution)
- Message-style ledger (compliance loves audit trails)

**By Dec 1 (Series A pitch):** Complete everything
- Full regulatory export flow
- Drift detection + anomaly alerts
- Replay/audit browser
- A/B test mode for training

---

## 💼 WHY THIS MATTERS FOR SERIES A

Investors will ask: **"How do you make compliance reviewable?"**

**Current answer:** "Click expand on receipt, see JSON signature, click verify button."

**Better answer:** "Here's the entire audit trail as cards with citations. Here's the impact dashboard showing CAR impact in real-time. Here's the compliance export button that generates BaFin-ready PDF. Every decision is attributed to the CRO who signed it."

**The difference:** First is technical. Second is regulatory-grade.

---

## 📋 ACTION ITEMS

### This Week (Sep 1-7):
- [ ] Design Rule Cards (regulatory citations)
- [ ] Design Impact Dashboard (CAR before/after)
- [ ] Design Inline Approval Flow (no modal)

### Week of Sep 8-15:
- [ ] Code Rule Cards (2 days)
- [ ] Code Impact Dashboard (1.5 days)
- [ ] Implement Inline Approval (1 day)

### Week of Sep 16-22:
- [ ] Add Compliance Export (1.5 days)
- [ ] Test with mock UniCredit data
- [ ] Demo to CRO advisory

### Oct 1 (Pilot kickoff):
- [ ] Deploy with Rule Cards + Impact Dashboard
- [ ] Train UniCredit traders on new UI

---

## 🚀 DELIVERABLE

**By Oct 31:** UniCredit will have:
1. ✅ 3-pane agentic governance UI (done)
2. ✅ Real Ed25519 cryptographic proof (done)
3. ✅ **Rule Cards with regulatory citations** (NEW)
4. ✅ **Impact Dashboard (CAR visualization)** (NEW)
5. ✅ **Inline veto gate authorization** (NEW)
6. ✅ **Compliance export for BaFin** (NEW)

**This is not a governance tool anymore. This is a regulatory compliance system.**

Investors see this and say: "This is production-ready. Banks will pay for this."

---

**Next move:** Start Rule Cards design today. 2-day implementation will change everything.
