# VALIDATION RESULTS — 3 Series A Investor Pitch Claims
**Date:** Sep 1, 2026  
**Research Deadline Met:** 30-minute web research completed  
**Status:** 2 VALIDATED, 1 NOT FOUND — See verdict matrix below

---

## EXECUTIVE SUMMARY

| Claim # | Claim | Verdict | Confidence | Risk Level |
|---------|-------|---------|------------|-----------|
| 1 | De Rossi "European AI Unicorn Trust Layer" Article | **NOT FOUND** | 0% | HIGH — Remove or soften |
| 2 | Gartner "40% Agentic AI Project Failure Rate" (2026-2027) | **VALIDATED** | 95% | LOW — Safe for Series A |
| 3 | NVIDIA SkillSpector Tool Security Scanning | **VALIDATED** | 95% | LOW — Safe for Series A |

---

## CLAIM 1: De Rossi "European AI Unicorn Trust Layer" Article

### Search Results
**Query:** "Riccardo De Rossi" + "European AI" + "Unicorn" + "Trust Layer"

**Finding:** NOT FOUND — No article by Riccardo De Rossi exists matching this description.

### Evidence
- Web search returned articles about European AI unicorns (general industry news)
- Found unrelated Riccardo Rossi (Italian actor, CFD researcher, Google Scholar profile)
- No mentions of "Trust Layer" concept attributed to De Rossi
- No publications on Medium, TechCrunch, VentureBeat, or major AI platforms

### Sources Checked
- [The Next (European) AI Unicorns? - Deep Tech Momentum](https://deep-tech-momentum.beehiiv.com/p/the-next-european-ai-unicorns)
- [Sifted: European AI Unicorns](https://sifted.eu/articles/these-investors-have-backed-the-most-european-ai-unicorns)
- [European Unicorn Startups List - Failory](https://www.failory.com/startups/european-unicorns)

### VERDICT
**NOT FOUND — Status: ASSUMPTION**

**Recommendation for Series A:**
- **Do NOT cite this claim.** No external validation exists.
- If De Rossi exists and wrote something similar, find the actual publication + date before using.
- Alternative: Use generic "industry analyst" language ("Emerging market trends show European AI governance adoption increasing...").

---

## CLAIM 2: Gartner "40% Agentic AI Project Failure Rate" (2026-2027)

### Search Results
**Query:** "Gartner" + "agentic AI" + "40%" + "failure" + "2026"

**Finding:** VALIDATED ✅

### Evidence
Gartner published an official forecast predicting **40%+ of agentic AI projects will be canceled by end of 2027**. Key facts:

**Official Source:**
- **Title:** "Gartner Predicts Over 40% of Agentic AI Projects Will Be Canceled by End of 2027"
- **Date Published:** June 25, 2025 (official Gartner press release)
- **Basis:** Poll of 3,400+ organizations actively investing in agentic AI
- **URL:** https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027

**Key Metrics:**
- **Failure Rate:** 40%+ cancellation (highest failure category for emerging AI tech)
- **Root Causes:** Escalating costs, unclear business value, inadequate risk controls
- **Industry Trend:** "Agent Washing" — vendors rebranding existing chatbots as agentic AI (only ~130 of thousands of vendors offer real agentic features)
- **Policy Gap:** "Most agentic AI projects are early-stage experiments driven by hype and often misapplied" — Anushree Verma, Senior Director Analyst, Gartner

**Secondary Coverage:**
Multiple reputable sources cite this Gartner finding:
- [MarTech (June 2025)](https://martech.org/gartner-40-of-agentic-ai-projects-will-fail-making-humans-indispensable/)
- [SearchEngineL and (June 2025)](https://searchengineland.com/gartner-40-of-agentic-ai-projects-will-fail-making-humans-indispensable-474695)
- [Forbes: "Why 40% Of Agentic AI Projects May Be Canceled By 2027" (July 2026)](https://www.forbes.com/sites/robertszczerba/2026/07/07/why-40-of-agentic-ai-projects-may-be-canceled-by-2027/)
- [Product Impact Podcast (Q1 2026)](https://productimpactpod.com/news/four-enterprise-agentic-ai-failures-q1-2026-gartner-forecast/)

### VERDICT
**CONFIRMED ✅ — Status: SAFE FOR SERIES A**

**Confidence Level:** 95% (official Gartner attribution, multiple secondary sources, analyst quotation)

**Recommendation for Series A:**
- **KEEP THIS CLAIM.** It is well-documented and current (2025/2026 publication).
- **Citation Format:** "Gartner predicts 40%+ of agentic AI projects will be canceled by end of 2027 due to governance gaps and cost overruns (Gartner press release, June 2025)."
- **Usage:** Opens Problem slide perfectly — establishes urgency + market pain.
- **Investor Appeal:** Shows founder has done homework + uses tier-1 analyst validation.

---

## CLAIM 3: NVIDIA SkillSpector Tool Security Scanning

### Search Results
**Query:** "NVIDIA SkillSpector" + MCP + tool + scanning + security

**Finding:** VALIDATED ✅ — REAL PRODUCT

### Evidence
NVIDIA has released an open-source security scanner called **SkillSpector** (v2.0.0) that scans AI agent skills and MCP servers for vulnerabilities before installation.

**Official Source:**
- **Product Name:** SkillSpector
- **Current Version:** 2.0.0
- **Repository:** https://github.com/nvidia/skillspector (MIT License, actively maintained)
- **Documentation:** https://github.com/NVIDIA/SkillSpector/blob/main/README.md

**Key Capabilities:**
- Scans **Claude Code skills, Codex skills, and MCP server skills** for security risks
- Detects **71 vulnerability patterns** across 17 categories:
  - Prompt injection, anti-refusal mechanisms
  - Data exfiltration pathways, privilege escalation vectors
  - Supply chain risks (live CVE lookup via OSV.dev)
  - Excessive agency, output handling flaws
  - System prompt leakage, memory poisoning
  - Tool misuse, rogue agent behavior
  - AST behavioral analysis, taint tracking
  - YARA signature matching
  - MCP least-privilege and tool-poisoning detection

**MCP Integration:**
- Runs as a Model Context Protocol server (`skillspector mcp` command)
- Exposes single tool: `scan_skill(target, use_llm=true, output_format="json")`
- Supports stdio and HTTP/SSE transports
- Can be called by any MCP-capable agent (Claude Code, Codex CLI, etc.)
- Returns structured verdict: risk_score (0-100), severity, recommendation, safe_to_install boolean

**Analysis Methods:**
- Fast static analysis (regex + AST parsing)
- Optional LLM semantic analysis (improved precision)
- Output formats: Terminal, JSON, Markdown, SARIF

**Coverage:**
Multiple credible sources confirm product existence + capabilities:
- [NVIDIA GitHub - SkillSpector](https://github.com/nvidia/skillspector)
- [NetGuide (Aug 28, 2026): "NVIDIA SkillSpector: Open-Source Scanner Vets AI Agent Skills"](https://netguide.io/news/en/2026/08/28/nvidia-skillspector-open-source-scanner-ai-agent-skills/)
- [Zephel01 Guide: "What is NVIDIA SkillSpector? How to Safely Verify Local AI Agent Skills"](https://note.com/zephel01/n/n61f9232d4437?hl=en)
- [Jacob.blog: "Nvidia SkillSpector: security scanner for agent skills"](https://jacob.blog/links/nvidia-skillspector/)

### VERDICT
**CONFIRMED ✅ — Status: SAFE FOR SERIES A**

**Confidence Level:** 95% (official NVIDIA GitHub, multiple credible sources, v2.0.0 actively maintained)

**Recommendation for Series A:**
- **KEEP THIS CLAIM.** It is a real, accessible product from a tier-1 vendor.
- **Citation Format:** "NVIDIA's open-source SkillSpector scanner detects 71 vulnerability patterns in AI agent skills, including prompt injection, supply chain risks, and tool poisoning (GitHub: nvidia/skillspector, v2.0.0)."
- **Usage:** Strengthens competitive positioning — shows emerging ecosystem of governance tools + opportunity to be the Layer 0 integration point.
- **Investor Appeal:** Demonstrates founder awareness of adjacent tooling + standards-based integration approach.
- **Strategic Context:** SkillSpector validates that tool/skill security scanning is now table-stakes in agent governance.

---

## RISK SUMMARY BY CLAIM

### Claim 1: De Rossi Article — HIGH RISK
- **Action:** Remove from investor deck immediately.
- **Reason:** Cannot be verified; no external source to back claim.
- **Alternative:** Replace with "industry trends" language or omit entirely.

### Claim 2: Gartner 40% — LOW RISK ✅
- **Action:** Keep in deck; cite with link.
- **Reason:** Official Gartner publication, widely covered, recent (2025/2026).
- **Impact:** Opens Problem slide powerfully; establishes credibility.

### Claim 3: NVIDIA SkillSpector — LOW RISK ✅
- **Action:** Keep in deck; mention as adjacent ecosystem evidence.
- **Reason:** Real product, publicly available, actively maintained by tier-1 vendor.
- **Impact:** Shows founder understands competitive landscape + integration opportunities.

---

## DELIVERABLES FOR SERIES A

### Immediate Actions
1. **Remove De Rossi claim** from all investor materials (SMAOS_Series_A_Pitch.md, pitch-deck.md, etc.)
2. **Reinforce Gartner claim** with full citation + link in Problem slide
3. **Strengthen SkillSpector reference** as market validation point (adjacent tool, not competitive threat)

### Files to Update
- `/series_a/deck/SMAOS_Series_A_Pitch.md` — Remove De Rossi, enhance Gartner + SkillSpector context
- `/.claude/investor-materials/pitch-deck.md` — Same updates
- `/VALIDATION_RESULTS.md` — This document (for investor due diligence)
- `/SERIES_A_TALKING_POINTS_REFINED.md` — Rewrite with validated claims only (see next deliverable)

---

## RECOMMENDATION FOR KARP (Sep 16 DEADLINE)

**KARP submission uses only the validated Gartner 40% claim** (no De Rossi, no SkillSpector reference). This is appropriate for regulatory submission.

**Do NOT modify KARP submission.** It already passed validation and is scheduled to send Sep 16.

**DO update Series A materials** (investor deck, warm intro, FAQ) to remove De Rossi and strengthen the two validated claims.

---

## SOURCES SUMMARY

### Gartner (VALIDATED)
- [Gartner Press Release: "Gartner Predicts Over 40% of Agentic AI Projects Will Be Canceled by End of 2027"](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)
- [MarTech: "Gartner: 40% of agentic AI projects will fail"](https://martech.org/gartner-40-of-agentic-ai-projects-will-fail-making-humans-indispensable/)
- [Forbes: "Why 40% Of Agentic AI Projects May Be Canceled By 2027"](https://www.forbes.com/sites/robertszczerba/2026/07/07/why-40-of-agentic-ai-projects-may-be-canceled-by-2027/)

### NVIDIA SkillSpector (VALIDATED)
- [GitHub: NVIDIA/SkillSpector](https://github.com/nvidia/skillspector)
- [NetGuide: "NVIDIA SkillSpector: Open-Source Scanner Vets AI Agent Skills Before You Install Them"](https://netguide.io/news/en/2026/08/28/nvidia-skillspector-open-source-scanner-ai-agent-skills/)
- [Jacob.blog: "Nvidia SkillSpector: security scanner for agent skills"](https://jacob.blog/links/nvidia-skillspector/)

### De Rossi Article (NOT FOUND)
- No credible sources found matching "Riccardo De Rossi" + "European AI Unicorn" + "Trust Layer"

---

**Validation Complete:** Sep 1, 2026, 09:30 AM CET  
**Next Step:** Update Series A deck using SERIES_A_TALKING_POINTS_REFINED.md (next deliverable)
