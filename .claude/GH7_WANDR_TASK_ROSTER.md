# WANDR Task Roster — High-Value Selection for SovereignNexus Phase 2

**Purpose:** Pre-vetted task selection for Aug 1-15 validation track. Each task listed with mapping to SN Phase 2 strategic need.

---

## Tier 1: Core Validation Tasks (Must-Run — Aug 1-7)

### Task 1: `ai_model_layer_company_public_capability_source_table`
**Strategic mapping:** Competitive positioning (Fortress vs. Platform layers)
**Task structure:** 35 AI companies × 2 models × 4 evidence roles = 280-leaf scale
- Evidence roles: Release corroboration, Operational integration, Independent evaluation, Downstream developer use
- Measures: Breadth of vendor coverage + depth of evidence (soft_f1: coverage vs. hard_f1: complete evidence types)
**SN relevance:** Validates our AI model layer competitive mapping (what models exist, who's deploying, evidence quality)
**Hard_f1 utility:** Ensures we have evidence across all 4 types (vendor claims alone score 0.25)
**Est. cost:** $15 | **Est. time:** 6 hours wall-clock

### Task 2: `ai_mlops_vendor_claims`
**Strategic mapping:** Vendor capability claim validation (agentic AI, security, regulated finance)
**Task structure:** 50 vendors × 3 claim families × 2 evidence sides (vendor self-asserted vs. independent)
- Claim families: (1) Agentic AI capability, (2) Security/compliance/AI governance, (3) Regulated finance customer/case
- Evidence asymmetry: Tests whether independent corroboration exists for vendor claims
**SN relevance:** Validates Series A positioning claims ("we're the only platform for..." claims need independent backing)
**Hard_f1 utility:** Binary: vendor has independent validation OR not
**Est. cost:** $12 | **Est. time:** 5 hours wall-clock

### Task 3: `agentic_ai_soc_vendor_public_capability_source_table`
**Strategic mapping:** Security/compliance maturity (SOC2, governance signals)
**Task structure:** SOC2/governance vendor capabilities × evidence types
**SN relevance:** Maps governance moat (Stream 10) — SOC2 coverage, ISO 42001, EU AI Act readiness
**Hard_f1 utility:** Complete evidence for each vendor's governance claims
**Est. cost:** $10 | **Est. time:** 4 hours wall-clock

---

## Tier 2: Market Sizing & Regional Validation (Run 2-3 of 5 — Aug 1-7)

### Task 4: `hkex_ipo_pipeline_market_map`
**Strategic mapping:** Market timing + geographic TAM validation
**Task structure:** IPO pipeline by region/sector with timing signals
**SN relevance:** Validates Phase 2 market launch timing (which regions are "hot" for exits/acquisitions?)
**Est. cost:** $8 | **Est. time:** 4 hours wall-clock

### Task 5: `market_access_datasets`
**Strategic mapping:** Regional market access requirements (regulatory, technical, partnership)
**Task structure:** Market entry requirements by geography
**SN relevance:** EU regulatory moat (Stream 10) + Israel market (Stream 9) entry path validation
**Est. cost:** $8 | **Est. time:** 4 hours wall-clock

### Task 6: Custom Task — EU Regulatory Landscape
**Strategic mapping:** GDPR/NIS2/EU AI Act evidence synthesis
**Task structure:** Evidence inventory: (1) Official regulatory text (EU site), (2) Compliance guidance (EDPB, ENISA), (3) Vendor implementation (audit results), (4) Competitive compliance status
**SN relevance:** EU regulatory moat (Stream 10) — quantify evidence completeness for compliance narrative
**Hard_f1 utility:** Tests whether we have evidence across all 4 evidence types
**Est. cost:** Custom ($10) | **Est. time:** 6 hours wall-clock (includes custom task definition)

### Task 7: Custom Task — Israel Market Entry Validation
**Strategic mapping:** Israel market readiness (regulatory + VC + security use case)
**Task structure:** Evidence inventory: (1) Regulatory pathway (ILPO, defense), (2) VC landscape & funding trends, (3) Enterprise defense/security buyer landscape, (4) Competitive entry (who else is targeting?)
**SN relevance:** Israel market launch (Stream 9) — quantify evidence maturity
**Hard_f1 utility:** Complete evidence across all 4 evidence types = market-ready positioning
**Est. cost:** Custom ($10) | **Est. time:** 6 hours wall-clock

### Task 8: Custom Task — Creator Platform TAM Validation
**Strategic mapping:** Substack/Patreon ecosystem TAM anchor for Series A
**Task structure:** Evidence inventory: (1) Substack creator base + monetization stats, (2) Patreon ecosystem size + revenue, (3) Competitive creator platforms (Stripe, Gumroad, Buy Me a Coffee), (4) Market analyst reports (TAM sizing)
**SN relevance:** Series A narrative anchor — "Fortress €15B creator economy play"
**Hard_f1 utility:** Tests whether all 4 evidence types support TAM claim
**Est. cost:** Custom ($10) | **Est. time:** 6 hours wall-clock

---

## Tier 3: Optional Follow-Up Tasks (Run if Tier 1-2 soft_f1 < 0.75)

### Task 9: `ai_governance_jobs`
**Strategic mapping:** Governance maturity signals via hiring announcements
**Task structure:** AI company governance hiring + job postings = governance investment signals
**SN relevance:** Quick proxy for competitive governance capability
**Est. cost:** $8 | **Est. time:** 3 hours wall-clock

### Task 10: `ai_gtm_deployability_provenance`
**Strategic mapping:** GTM pathway maturity for AI vendors
**Task structure:** Evidence: (1) Official deployment docs, (2) Case studies, (3) Partner integrations, (4) Sales enablement
**SN relevance:** Maps competitive GTM maturity (how easy is it for vendors to deploy us?)
**Est. cost:** $10 | **Est. time:** 4 hours wall-clock

### Task 11: Brand Competitor Panels (Geographic Variants)
**Strategic mapping:** Regional competitive landscape for creator economy positioning
**Examples:** `latam_fare_payment_programs` (regional payment rails for Substack), market-specific competitor panels
**SN relevance:** APAC expansion (Stream 12) — regional competitive positioning
**Est. cost:** $8 each | **Est. time:** 3-4 hours wall-clock each

---

## Task Selection Strategy for Aug 1-15

**Recommended selection (Core + 2-3 Market Sizing tasks):**

| Deadline | Task | Category | Est. Cost | Owner | Note |
|----------|------|----------|-----------|-------|------|
| Aug 1 (kick-off) | Task 1: `ai_model_layer_company_public_capability_source_table` | AI/Competitive | $15 | GH7-Agent-2 | Launch first (longest) |
| Aug 2-3 (parallel) | Task 2: `ai_mlops_vendor_claims` | Vendor Claims | $12 | GH7-Agent-2 | Run in parallel |
| Aug 2-3 (parallel) | Task 3: `agentic_ai_soc_vendor_public_capability_source_table` | Governance | $10 | GH7-Agent-2 | Run in parallel |
| Aug 3-4 (sequential) | Task 6: Custom — EU Regulatory | Market/Regulatory | $10 | GH7-Agent-1 | Pre-defined custom |
| Aug 4-5 (sequential) | Task 7: Custom — Israel Market | Market/Regional | $10 | GH7-Agent-1 | Pre-defined custom |
| Aug 5-7 (if time) | Task 8: Custom — Creator TAM | Market/TAM | $10 | GH7-Agent-2 | Anchor for Series A |
| **Total** | | | **$67** | | 6 tasks, Aug 1-7 |

**If timeline tightens (Aug 1-5 only):**
- Drop Task 3 (governance—lower priority for initial pitch)
- Drop custom tasks (use existing WANDR tasks for quick validation)
- Keep: Task 1 (AI vendor mapping), Task 2 (vendor claims), Task 5 (market access) or Task 4 (IPO pipeline)
- **Cost: $35 | Time: 15 hours | Core validation remains strong**

**If expanding (Aug 1-15 full allocation):**
- Add Task 4 (IPO pipeline) + Task 9 (governance jobs) + Task 10 (GTM deployability)
- Add 1-2 geographic variants for APAC/LATAM
- **Cost: $110 | Time: 35 hours | Comprehensive Phase 2 validation**

---

## Deliverables Format (Standard Across All Tasks)

Each task produces:
1. **JSON result file** with soft_f1, hard_f1, and lineage (full + retrieval)
2. **Evidence inventory** (markdown): all sources found + dedup summary
3. **Verifier diagnostics** (JSON): which evidence satisfied/failed which claim dimension
4. **Human-readable report** (HTML): visual evidence quality breakdown

**Integration into Series A materials:**
- Headline: "Research quality validated using WANDR research benchmark (Perplexity AI)"
- Metrics slide: Show soft_f1 and hard_f1 across all 6 tasks
- Supporting appendix: Top 2-3 evidence synthesis examples from strongest tasks

---

## Notes on Custom Tasks

Custom tasks (Tasks 6-8) require ~4 hours setup (define evidence roles, write WANDR config). Pre-built WANDR tasks (Tasks 1-5, 9-10) are ready to run immediately.

**Recommendation:** Start with 3 pre-built tasks (1-3) in parallel Aug 1-3, then decide whether to invest in custom task definitions for market-specific validation (EU, Israel, Creator TAM).

If custom tasks are skipped, run Task 4 or Task 5 instead (both <$10, ready to go).

---

**Next step:** GH7-Agent-1 runs smoke test Jul 28. Confirm task selection by Jul 29 EOD.
