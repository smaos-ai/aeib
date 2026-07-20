# OSINT Ghost CRM — Operational Playbook & Templates
## Local-First, Privacy-Preserving, Warm-Intro Mapping

---

## OPERATIONAL PRINCIPLES

**Privacy-First:** No API keys, no cloud calls, no data leakage.  
**Local-Only:** All ingestion + analysis happens on M3 Pro.  
**Manual Verification:** Semi-automated scrapers only; human judgment final.  
**Warm-Intro Focus:** Map relationships, not spy.

---

## DATA SCHEMA (Local Knowledge Graph)

**Location:** `~/.smaos/osint/schema.json`

```json
{
  "entities": [
    {
      "id": "inv_001",
      "name": "John Doe",
      "type": "vc_partner",
      "firm": "Glasswing Ventures",
      "title": "Partner",
      "focus_areas": ["AI", "Israel", "Defense"],
      "recent_signal": "Led €5M investment in Israeli AI safety startup (May 2026)",
      "signal_date": "2026-05-15",
      "warm_intro_path": ["Alice Smith (founder, Portfolio Co)", "Bob Jones (advisor)"],
      "timing_window": "June 1-15 (post-Series A conversations)",
      "narrative_hook": "Israeli VC + Pax Silica positioning = perfect fit for Axiom's geopolitical thesis",
      "confidence": 0.92,
      "sources": ["Crunchbase", "LinkedIn", "TechCrunch"],
      "last_updated": "2026-06-03"
    }
  ],
  "relationships": [
    {
      "source": "inv_001",
      "target": "inv_002",
      "type": "co_invested",
      "signal": "Both backed SafetyTech startup in 2025",
      "strength": 0.8
    }
  ],
  "signals": [
    {
      "entity_id": "inv_001",
      "signal_type": "investment_in_safety",
      "description": "Invested in AI safety + constitutional governance",
      "source": "Crunchbase",
      "date": "2026-05-15",
      "confidence": 0.95,
      "relevance_to_axiom": "HIGH"
    }
  ]
}
```

---

## INGEST PROCEDURE (Per Target)

### Step 1: Initial Research (5 minutes per investor)

**Tool:** Browser (incognito mode, no tracking)

```
Google: "[Investor Name] + AI safety"
         "[Investor Name] + governance"
         "[Investor Name] + 2026"

Check:
- Crunchbase profile (investments, focus areas)
- LinkedIn (recent posts, endorsements, connections)
- Twitter/X (recent sentiment on AI governance)
- TechCrunch (news mentions, latest investments)
- AngelList (portfolio companies)
```

**Record:**
- Recent investment (date, company, thesis)
- Quoted perspective on governance/safety
- Any mention of creator economy or compliance

### Step 2: Relationship Mapping (3 minutes per investor)

**Question:** "Who do I know who knows this investor?"

**Technique:**
- Check LinkedIn connections (visible + 2nd degree)
- Look for mutual portfolio companies (suggest intro path)
- Scan recent Axiom network (advisors, board, operators)

**Output:** `warm_intro_path` array (ordered by strength)

```
"warm_intro_path": [
  "Alice Smith (founder of portfolio company X, knew investor in 2024)",
  "Bob Jones (advisor to investor's fund, shared panel at AI Summit 2026)",
  "Carol Brown (connector, invested in same round as investor)"
]
```

### Step 3: Signal Identification (3 minutes per investor)

**Question:** "Why would this investor care about Axiom?"

**Search for:**
- Recent AI governance investments
- Mentions of fail-closed safety, cryptography, or economic alignment
- Regulatory focus (GDPR, AI Act, NIS2)
- Creator economy thesis

**Confidence scoring:**
- 0.95+: Direct investment in governance/safety
- 0.8-0.94: Strong thematic alignment
- 0.6-0.79: Tangential interest
- <0.6: Skip (low relevance)

### Step 4: Narrative Hook Drafting (2 minutes per investor)

**Template:**
```
"[Investor] recently backed [Company] for [Thesis].
Axiom's [Feature] directly solves [Problem].
Hook: [One-sentence positioning]"
```

**Examples:**

**For Israeli VC:**
> "Glasswing backed SafetyTech for constitutional AI. Axiom adds cryptographic governance + Pax Silica positioning. Hook: Israeli VC + Defense-grade AI Infrastructure = perfect narrative fit."

**For EU VC:**
> "Sapphire led round in governance compliance tools. Axiom's protocol-layer enforcement = GDPR/AI Act readiness 6 months early. Hook: EU regulatory moat + 3.2x valuation multiplier."

**For Creator-Focused VC:**
> "Ribbit backed creator platforms. Axiom's AP2 Ledger enforces 1%/99% payout cryptographically. Hook: $2B/month creator earnings + fair settlement = TAM unlock."

---

## BRIEF GENERATION TEMPLATE

**File:** `~/.smaos/osint/briefs/investor_[ID]_[NAME].md`

```markdown
# Warm-Intro Brief: [Investor Full Name]

## Profile
- **Firm:** [Firm Name]
- **Title:** Partner / Managing Director / Scout
- **Focus:** [Areas]
- **Assets Under Management:** $[X]M
- **Recent Signal:** [Investment or news from past 6 months]
- **Signal Date:** YYYY-MM-DD
- **Confidence in Fit:** [0.6-1.0]

## Why They Care About Axiom
> "[One-sentence thesis alignment]"

Example:
> "Recently backed SafetyTech for fail-closed governance; Axiom's cryptographic enforcement is 3.2x more defensible."

## Warm Introduction Path
1. **Primary:** [Name] (relationship type, last interaction)
   - Context: "[Shared portfolio company / panel / advisor network]"
   - Suggested: "I'll email [Name] asking for an intro"

2. **Secondary:** [Name] (if primary unavailable)
   - Context: "[Alternative connection]"

3. **If No Direct Path:** Use signal-based approach
   - "Your recent investment in [Company] aligns with Axiom's [Feature]. I'd love a 15-minute call."

## Timing Window
- **Optimal:** [Date range, e.g., June 5-12]
- **Reason:** Post-demo, pre-Series A close pressure
- **Availability:** Check LinkedIn for scheduled posts / time zone

## Email Subject Line (Draft)
```
[Investor Name] + [Warm intro name]: Govern any frontier model (Axiom Protocol)
```

## Email Hook (2-3 lines)
```
Hi [Name],

[Warm intro name] thought you'd be interested in Axiom—we're the governance 
layer for frontier AI that addresses your recent focus on [investment thesis].

Live demo attached (5 min). Available for a call this week?
```

## Follow-Up Sequence
- **Day 0:** Send initial email + demo
- **Day 2:** Check open (hint: "checking in on that Axiom demo")
- **Day 4:** Call booking (calendly link)
- **Day 7:** If no response, try warm intro path

## Notes
- [Any additional context from research]
- [Competitive dynamics or prior rejections]
- [Timing sensitivities]

---

**Status:** Ready for outreach  
**Last Updated:** [Date]  
**Confidence:** [0-1.0]
```

---

## BULK INGEST CHECKLIST (50 Targets)

```bash
# Create briefs directory
mkdir -p ~/.smaos/osint/briefs

# For each investor (manual process, ~20 min per investor):

1. Open investor brief template
2. Run OSINT research (Google, Crunchbase, LinkedIn)
3. Identify 1-3 warm intro paths
4. Identify recent signal (investment or news)
5. Draft narrative hook (one sentence)
6. Complete brief
7. Rate confidence (0.6-1.0)
8. Save to ~/.smaos/osint/briefs/investor_[ID]_[NAME].md

# Aggregate briefs into CSV for email outreach
for file in ~/.smaos/osint/briefs/*.md; do
  name=$(grep "^# Warm-Intro Brief:" "$file" | sed 's/.*: //')
  firm=$(grep "^- \*\*Firm:\*\*" "$file" | sed 's/.*: //')
  confidence=$(grep "^- \*\*Confidence:\*\*" "$file" | sed 's/.*: //')
  
  echo "\"$name\",\"$firm\",$confidence" >> ~/.smaos/osint/investor_roster.csv
done

# Expected output: 50 CSV entries
wc -l ~/.smaos/osint/investor_roster.csv
# Expected: ~51 lines (header + 50)
```

---

## PRIVACY & SECURITY CHECKLIST

- [ ] All research done in incognito browser (no tracking cookies)
- [ ] No API keys stored locally (manual ingest only)
- [ ] No outbound network calls from analysis machine
- [ ] Briefs stored encrypted (`~/.smaos/osint/briefs/` + file permissions 0600)
- [ ] No data synced to cloud (local-only)
- [ ] Delete browser history after ingest session
- [ ] Merkle-sign final roster (`sha256sum investor_roster.csv`)

---

## EXPECTED OUTPUT

**After 48 hours of OSINT ingest:**

- `~/.smaos/osint/schema.json` (50 entities + relationships)
- `~/.smaos/osint/briefs/` (50 markdown files, 1 per investor)
- `~/.smaos/osint/investor_roster.csv` (50 CSV entries, ready for Series A email batch)

**Result:** 50 warm-intro paths, each customized with narrative hook + timing window.

**Series A Impact:** 10-15% warm response rate (vs. 1-2% cold outreach).
