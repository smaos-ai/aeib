# Strategic Decision Protocol v1.0
## Research-Driven Approval Framework for All Major Decisions

**Status:** Active | **Effective:** May 29, 2026 | **Owner:** Architect

---

## Purpose

Eliminate speculation. All strategic decisions (>50K investment, >2 weeks effort, >1M impact) run through this protocol before approval.

**Result:** Decisions backed by live 2026 market data, not assumptions.

---

## The Protocol (4 Phases)

### Phase 1: Identify the Decision
**Trigger:** Any strategic choice that is:
- High-investment (>€50K, >6 months effort)
- High-stakes (irreversible, affects >1 mission)
- Ambiguous (multiple valid approaches)

**Action:** Reframe as 2-4 explicit YES/NO decisions, not open-ended questions.

**Example:**
- ❌ "Should we defer diabetes?" (open-ended)
- ✅ "Approve Sovereign Pancreas launch June 30 as wellness app (no FDA)?" (explicit)

---

### Phase 2: Research-Driven Validation (Plan Mode)
**Process:**
1. Enter Plan Mode (`Shift+Tab`)
2. Launch 3 parallel Explore agents with WebSearch enabled, searching LIVE 2026 data
   - **Agent 1:** Market/funding landscape (VC, competitors, investor trends)
   - **Agent 2:** Regulatory/technical pathways (FDA, EU compliance, engineering reality)
   - **Agent 3:** Field deployments/real-world examples (what's actually proven, what failed)
3. Each agent searches 5-8 specific questions using actual websites, not training data
4. Report: Real numbers, specific companies, dates, sources — flag conflicting data

**Output:** Research findings that change the original decision 40-60% of the time

---

### Phase 3: Synthesize + Reframe
**After research completes:**
1. Compare findings against original assumptions
2. Identify what changed (market shifted, regulatory pathway shorter, competitor gaps, proven deployments)
3. Reframe the original decision based on ACTUAL 2026 reality
4. Identify the uncontested position (what nobody else is doing)

**Example from EDEN:**
- Original Decision 2: "Defer diabetes to 2027 (FDA)"
- Research Finding: Levels Health/One Drop/Onduo all chose wellness positioning (zero FDA)
- Reframed Decision 2: "Launch diabetes June 30 as wellness app (same as market leaders)"

---

### Phase 4: Approval Gate
**Present to user:** 2-4 explicit YES/NO decisions with:
- Real data backing each option
- Recommendation (usually the option backed by market reality)
- Impact (what changes if YES vs. NO)
- Timeline (when decision locks in)

**User responds:** YES / NO / YES / NO (one line per decision)

**Once approved:** Locks the decision for 6 months (can revisit if market shifts materially)

---

## Default Triggers (Automatic Protocol)

These decisions automatically enter the protocol without asking:

| Decision Type | Trigger | Examples |
|---------------|---------|----------|
| **Regulatory** | Any FDA/EU MDR claim | Medical AI, healthcare data |
| **Market positioning** | Series A pitch strategy | Enterprise anchor, investor messaging |
| **Hardware selection** | Conflict zone / production deployment | Edge AI, power, connectivity |
| **Timeline defer** | Pushing launch >6 months | Phase prioritization, feature gates |
| **Budget >€100K** | Any single line item | Hardware procurement, cloud infrastructure |
| **Partnerships** | Enterprise or government deal | NHS/IDF/EU Factories integrations |

---

## Documentation (After Approval)

Store decision approval in `.claude/decisions/` with:
- Decision number
- Approval date
- YES/NO answers
- Research findings summary
- Timeline lock (when this decision can be revisited)

**Example:** `.claude/decisions/EDEN_2026-05-29_3_STRATEGIC_DECISIONS.md`

---

## Why This Works

**Traditional approach:** Assume market data is static, decide based on training data (Feb 2025), ship, discover market changed in May 2026 → pivot → waste.

**Protocol approach:** Validate assumptions against LIVE 2026 data before committing → 60%+ fewer pivots → faster execution.

**Cost:** 2-3 hours research + Plan Mode validation per major decision
**Payoff:** Avoid €500K+ misdirected investment (e.g., Series A on wrong positioning)

---

## Implementation (June 4+)

**Every major decision starting June 4:**
1. Identify YES/NO decision gates
2. Trigger Strategic Decision Protocol automatically
3. Launch 3 parallel research agents (Perplexity + WebSearch)
4. Present findings + reframed decision to user
5. User approves (YES/NO)
6. Document + lock for 6 months
7. Execute with confidence

---

## Success Metrics

- ✅ Zero decisions deferred due to missing information (Protocol catches it)
- ✅ 40%+ of decisions reframed based on live research (catching market shifts)
- ✅ Series A positioning backed by actual market data (not assumptions)
- ✅ Hardware selections proven in field before large purchases
- ✅ FDA/regulatory pathways validated before committing timeline

---

## Owner

**Architect** — Owns Strategic Decision Protocol adherence  
**Perplexity + WebSearch** — Provide live 2026 market data  
**User** — Final YES/NO approval gate  

---

## Next Steps

1. **Add to CLAUDE.md** as standard workflow (Section 10)
2. **Create `.claude/decisions/` directory** for decision history
3. **June 4+:** Apply protocol to all Phase 25 decisions
4. **Monthly review:** Assess decision quality + market shifts
