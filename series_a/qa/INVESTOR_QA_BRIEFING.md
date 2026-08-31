# Series A Q&A Briefing (20 Questions)

## 1. "What makes SMAOS different from Palantir?"
**Answer:** Palantir is $500K+/year, cloud-dependent, 6-month setup, enterprise-only. SMAOS is local-first (sovereign), $0 licensing (open), 4-week deployment, mid-market accessible. We're purpose-built for EU AI Act enforcement; Palantir is general-purpose governance. We ship in 16 months; they're still designing compliance features. Different markets, different approach, different timeline.

## 2. "How does fail-closed governance actually work?"
**Answer:** Agent attempts action (e.g., approve credit). System checks policy (Article 14: human oversight required). Decision: BLOCK. Veto gate modal pops (shows intent, policy, alternatives). Human signs. Receipt generated (agentacct JSON + Ed25519 signature). Ledger appended (Merkle commit). Agent resumes or halts based on approval. Not theoretical—492 decisions, 22 escalations, 100% compliant.

## 3. "How is this not just a chatbot wrapper?"
**Answer:** Chatbots are black boxes (no enforcement, no audit, no governance). SMAOS is a harness: (1) policy-aware routing (7 EU Articles), (2) fail-closed gates (agent halts at boundaries), (3) human approval required (cryptographically enforced), (4) immutable ledger (PQC-signed Git), (5) proof artifacts (7 independent validations). Chatbot ≠ governed system. We're the latter.

## 4. "What's your regulatory risk?"
**Answer:** We've mapped SMAOS to NIST AI RMF (Govern, Map, Measure, Manage—all implemented). EU AI Act Articles 10, 14, 50, 52, 71 all routed and tested. TRAIGA safe harbor qualifies (local edge execution). Only tail risks: (a) Article interpretation changes (low probability, we adapt), (b) enforcement timeline slips (benefit us), (c) competitors catch up (we have 12-month head start). Regulatory is tailwind, not headwind.

## 5. "Why should we invest in EU-centric AI governance?"
**Answer:** EU AI Act is the global compliance standard (companies comply for EU, export globally). Annex III + Annex I affect €6.4B market. Enforcement date is Dec 2, 2027 (immovable). 85% of enterprises unprepared. SMAOS is the only platform shipping before enforcement. First-mover advantage = 12 months before Series B close. Regulatory tailwinds > headwinds.

## 6. "What's your unit economics?"
**Answer:** CAC €10K, LTV €180K (3-year @ €5K/month), LTV/CAC 18x. Gross margin 78% (edge execution cost-efficient). Payback period 2 months. Perpetual license model (no SaaS churn). Break-even Year 2 (18 months from Series A). From Series A to €42M ARR in 5 years with <€3M burn. Conservative, defensible model.

## 7. "How do you defend against Palantir entering the EU market?"
**Answer:** Palantir takes 6 months to deploy, costs $500K+/year, requires cloud infrastructure. By the time they enter, we'll have 50+ customers, €8.5M ARR, proven compliance track record, regulatory relationships, and 14-month head start. We're fast, local, cheap. They're slow, cloud, expensive. Different market segments. We win on speed + cost + sovereignty.

## 8. "What's your go-to-market plan?"
**Answer:** Phase 1 (KARP pilots): 3 regional pilots, case studies, government validation. Phase 2 (enterprise sales): 6 account executives, compliance conference sponsorships, EU regulatory relationships. Phase 3 (partnerships): Consulting firms, system integrators, enterprise resellers. Year 1 revenue from pilots (€1.1M). Year 2 revenue from enterprise sales (€8.5M). Year 3+ from partnerships (€16M+).

## 9. "Who's your ideal customer?"
**Answer:** Large enterprises operating in EU (banking, insurance, healthcare, manufacturing, auto, glass, hospitality, education). Compliance-heavy, risk-averse, budget for AI governance. Can't use cloud (data residency). Can't use black-box AI (regulatory mandate). Sweet spot: €1B+ revenue, >1000 employees, existing AI investments. TAM €6.4B. Addressable: €2-3B (enterprises willing to pay premium for sovereignty + compliance).

## 10. "What's your pricing strategy?"
**Answer:** Perpetual license, €5K-30K/month (based on customer size, decision volume). Professional services €50K per pilot. Annual support 20% of license fee. Tiered: SMEs €500/month, mid-market €5K, enterprise €30K. Benchmarked to Palantir (cheaper) and cloud AI (more compliant). Model is conservative; actual pricing likely higher as enforcement nears.

## 11. "How do you ensure data doesn't leak?"
**Answer:** CanIRun proof: zero servers, zero external API calls. Air-gap tested (unplug internet, everything runs offline). Docker containerization (isolated network). No telemetry, no logging to cloud. GDPR compliant. EU data residency guaranteed. 7 proof artifacts demonstrate compliance. We've architected for data sovereignty from day 1; it's not an afterthought.

## 12. "What about international expansion?"
**Answer:** Phase 1-2: EU focus (12-month head start). Phase 3: UK (post-Brexit AI regulation). Phase 4: US (Biden EO on AI governance, regulatory momentum). Phase 5+: APAC (Singapore, South Korea). Each market has different compliance timelines, but SMAOS architecture is portable. Same 8 layers, different policy rules. International expansion is Year 3+.

## 13. "How many founders/engineers?"
**Answer:** Current: 1 founder (governance expert) + 1 CTO (architecture). Phase 1: +4 engineers, +1 compliance officer. Phase 2: +10 engineers, +2 sales, +1 operations. By Series B: 20 headcount. Lean, focused team (1 person per 2-3 technical milestones). Advisory board: [regulatory experts, investors, enterprise CISOs].

## 14. "What if RAGAS accuracy drops below 87%?"
**Answer:** Conservative assumption. RRF fusion de-risks model selection (if pgvector weak, BM25 compensates). 87% is baseline; production likely higher (pilot data shows 87.3% at launch, improving). If it dropped: (a) re-tune embeddings (1 week), (b) switch models (1 week), (c) escalate to human (managed risk). Compliance is de-risked by fail-closed gates, not just accuracy.

## 15. "What's your exit strategy?"
**Answer:** No pre-determined exit. Build to profitability (Year 2). Options: (a) IPO (post-Series C, when EU AI market matures), (b) acquisition by Palantir/Microsoft/Salesforce (if they see competitive threat), (c) private-equity growth capital (after Series B). Management aligned on building for long-term value, not short-term exit.

## 16. "How do you handle edge cases in governance?"
**Answer:** Escalation to human is the design. Hotel credit scoring: 22 edge cases in 492 decisions (4.5% escalation rate). Humans make final call, sign decision, ledger captures it. This is not failure—it's correct governance. System handles 95.5% autonomously, humans resolve ambiguity. Scale achieved; escalation cost manageable. Model is self-improving (rare edge cases inform policy updates).

## 17. "What happens if enforcement timeline slips?"
**Answer:** Tailwind for us. Every month we don't face competition gives us 1% more market share. If Dec 2027 deadline shifts to 2028, we have that many more months of head start. We're not dependent on deadline; we're independent of it. Customers adopt SMAOS because they want governance now, not because they're forced. Deadline accelerates adoption but isn't prerequisite.

## 18. "How do you ensure PQC adoption won't leave you behind?"
**Answer:** Ed25519 is current standard (NIST approved). Post-quantum research ongoing (NIST PQC finalists selected). Our architecture supports signature algorithm swap (metadata in AP2 ledger). If new PQC standard emerges, we upgrade signatures. Not locked in. We're future-proofed at design level (abstracted signature layer). By time PQC critical, NIST standards will be clear.

## 19. "What's your competitive intelligence?"
**Answer:** Monitoring: Palantir (no EU-specific products yet), Tempus (data analytics, not governance), Databricks (infrastructure, not governance), government compliance vendors (static, not AI-aware). None are shipping fail-closed governance for EU AI Act. We have 12-month uncontested window. Some will try to catch up (inevitable). But first-mover + regulatory relationships = defensible position. Focus is execution, not paranoia about copycats.

## 20. "Why should we bet on you instead of a bigger player?"
**Answer:** Bigger players move slow (org inertia, legacy code). You're betting on speed + regulatory alignment + founder conviction. In 16 months (enforcement date), we'll have 50+ customers, €8.5M ARR, proven compliance. Bigger player will still be in design phase. This is a marathon, not a sprint. We're the lean, focused, compliance-obsessed team. Bigger players are generalists. You win with specialists in regulatory phases.
