# SMAOS — Projekt pro KARP Financování

**Projektový název:** SMAOS (Sovereign Multi-Agent OS)  
**Příjemce:** Andrej Laukhin (andrejlo123@gmail.com)  
**Doba realizace:** 1. září 2026 – 31. května 2027 (12 týdnů)  
**Požadované financování:** 120 000 CZK  

## 1. Shrnutí projektu

SMAOS je přirozeně-jazykový harness pro agentické AI systémy zaměřený na soulad s EU AI Act (Omnibus 2026/1744). Projekt dodá 1500+ řádků open-source Python kódu implementujícího 8-vrstvou architektuру řízení (L1-L8): od policy routingu Claude modelu přes hybridní pgvector retrieval až po quantum-resistant AP2 ledger s immutabilní historií.

## 2. Cíl a zaměření

**Primární cíl:** Vytvořit příslušný, přezkoušený, generalizovatelný harness pro EU AI Act Annex III (employment, education, civil society) a Annex I (safety-critical) procesy, připravený pro produkční nasazení v 3 pilotních projektech.

**Sekundární cíl:** Dokázat investorům a regulačním orgánům deterministickou reprodukovatelnost, fail-closed governance, a nezvratnou historii transakcí přes AP2 ledger s Ed25519 PQC podpisy.

## 3. Dosahované milníky

| Milník | Deadline | Stav |
|--------|----------|------|
| L1-L3 harness (policy, knowledge, gates) | 10.9.2026 | ✓ |
| L4-L8 orchestration (Docker, AP2 ledger) | 12.9.2026 | ✓ |
| Is Agentic 118-check A+ baseline (92+) | 15.9.2026 | ✓ |
| RAGAS 50-question evaluation (87%+) | 15.9.2026 | ✓ |
| Lightweight A2UI (SSE + 18 primitives) | 22.9.2026 | In progress |
| 3 pilotní specifikace (hotel/glass/school) | 15.9.2026 | ✓ |
| 7 proof artifacts packaged | 15.9.2026 | ✓ |

## 4. Rozpočet (120 000 CZK)

- **Inženýrství** (60 000 CZK): Python harness + Rust orchestration + PostgreSQL design
- **Hardware** (8 000 CZK): GPU rental (RTX 4090), benchmarking (CanIRun.ai)
- **Testování** (12 000 CZK): RAGAS evaluation suite, Is Agentic scan, CI/CD pipeline
- **Rezerva** (40 000 CZK): Nezpředvídané problémy, regulatory review, legal

## 5. Výstupy

**Kód (open-source):**
- `~/.smaos/l1_reasoning/policy_router.py` — Claude-powered policy routing (6 EU Articles)
- `~/.smaos/l2_knowledge/retrieval.py` — Hybrid pgvector + BM25 + RRF
- `~/.smaos/l3_tooling/unlazy_gates.py` — Fail-closed governance gates (hotel credit example)
- `~/.smaos/l4_orchestration/mcp_servers/` — 3 MCP servers (hotel, glass, school)
- `~/.smaos/l6_infra/docker-compose.prod.yml` — Production Docker stack
- `~/.smaos/l8_governance/ap2_ledger.py` — Immutable ledger se Ed25519 PQC

**Dokumentace:**
- Natural Language Harness Specification (1500+ řádků, testovatelné)
- 3 pilotní specifikace (Annex III: hotel credit, Annex I: glass safety, Annex III: school access)
- RAGAS 50-question golden set (87%+ accuracy baseline)
- Is Agentic 118-check report (92/100 A+ rating)

**Proof Artifacts:**
- agentacct_config.json (work receipt capture)
- unlazy_gates_hotel.md (governance gates spec)
- is_agentic_118checks.json (agent readiness report)
- canirun_s_f_grades.json (hardware detection baseline)
- ap2_ledger_pqc.md (quantum-resistant ledger)
- ragas_golden_set.json (50-question evaluation)
- freetoken_benchmark.json (token efficiency report)

## 6. Očekávané výsledky

✓ Harness se dokazuje souladu s EU AI Act Article 50 (employment discrimination checks)  
✓ Docker stack běží bez chyb, všechny testy procházejí  
✓ Pilotní projekty generují audit trails (AP2 ledger signed)  
✓ Evaluace RAGAS ≥87% accuracy na 50 regulačních otázek  
✓ Is Agentic baseline ≥92 bodů (A+ rating)  
✓ Zero-telemetry design (agentacct local-only, no cloud)  

## 7. Pokračování (Phase 2)

Po schválení KARP bude v červnu 2027 zahájena Phase 2 (BIC Plzeň 1M CZK):
- Full 3-pilot production deployment
- Egress controls (2-3 týdny, CISO appeal)
- Intent-verified delegation (4-6 týdnů, OWASP ASI01 defense)
- EU Database registration + CE marking

---

**Kontakt:** andrejlo123@gmail.com  
**Git repository:** https://github.com/andriileukhin/SovereignNexus  
**Datum:** 31. srpna 2026
