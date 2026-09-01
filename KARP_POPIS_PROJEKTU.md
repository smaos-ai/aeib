# KARP Startovací vouchery 2026 — Popis projektu

**Název:** SMAOS — Sovereign Agentic Operating System
**Nositel:** SMAOS s.r.o.
**Odpovědný:** Andrei Leukhin (andrejlo123@gmail.com)
**Kontakt:** Romana Cernikova (romana.cernikova@karp-kv.cz) +420 724 858 335
**Deadline:** 16-22 září 2026 (podání 10 dnů předem)

---

## 1. PROBLÉM A TRŽNÍ PŘÍLEŽITOST

**Problém:** 79% organizací má agentic AI v produkci, ale 60% má **governance gap** — nemohou prokázat compliance, audit, kontrolu. 40% projektů se zrušuje do konce 2027 (náklady, nejasná ROI, selhání rizikové kontroly).

**Příležitost:** EU AI Act enforcement začal 2. srpna 2026. Firmy v Karlovarském kraji (hotely, pivovary, sklárnický průmysl) mají agenty, ale chybí im kontrola. **SMAOS řeší tuto mezeru.**

**Trzní segment:** AI Risk Platforms (governance focus) přitahují 44% investic 2026 ($230.5M). SMAOS je jediná orchestration-first platforma (všichni ostatní jsou discovery-first nebo monitoring-first).

---

## 2. ŘEŠENÍ: SMAOS ARCHITEKTÚRA (8 vrstev)

**Ústav:** Natural-Language Harness (1500 řádků čitelného kódu) + Governance Membrane (proof layer) — ne chatbot, ne wrapper, ale **agentic OS**.

| Vrstva | Technologie | Účel |
|--------|-------------|------|
| **L1** | Claude | Politika-vázané rozhodování (citujes přesně články) |
| **L2** | pgvector + BM25 + RRF | Znalostní vrstva, data residency (EU) |
| **L3** | Native Function Calling | Permit gates — rozhodnutí PŘED akcí |
| **L4** | LangGraph | Deterministické checkpointy, human escalation |
| **L5** | MCP + A2A | Standardizovaná komunikace, API integrace |
| **L6** | Colibri C-engine | Lokální inference MoE, GPU/RAM/NVMe hierarchie, zero precision drop |
| **L7** | RAGAS + LangSmith | Evaluace (citace správné politiky?) + tracing |
| **L8** | AP2 ledger + PQC signatura | Immutable proof trail — Git anchoring, nelze přepsat |

### Architektura nezávislá na cloudu (Inference bez kompromisů)

**Colibrí jako Layer 6 — Lokální governance engine**

Systém integruje lokální C-engine Colibrì, který dynamicky využívá hierarchii GPU VRAM, operační paměti a rychlého lokálního NVMe disku. To umožňuje spouštět nejmodernější modely architektury Mixture-of-Experts (MoE) přímo na běžném hardwaru v regionu (RTX 4060 za 8 000 Kč) s nulovou závislostí na zahraničních cloudových serverech a s absolutní zárukou přesnosti výpočtu (zero precision drop). **Podniková data z Karlovarského kraje nikdy neopustí zařízení.**

**Klíčové výhody:**
- **Proaktivní governance** (rozhoduje PŘED exekucí, ne POTOM detekuje)
- **Místní inference** (data nikdy neopustí Česko — GDPR + EU AI Act compliance)
- **Audit trail** (PQC signatura v Git — záznam, který se nelze vymazat)
- **Portable harness** (není locked na Claude API — škáluje do libovolného modelu Phase 3)

### Colibrí Metriky — Garantované Výkony

| Metrika | Specifikace | Garantie |
|---------|-------------|----------|
| **Model** | Kimi K3 2.8T / DeepSeek V4 Flash / GLM-5.2 744B | Libovolný MoE architektura |
| **Hardware** | RTX 4060 8GB + 16GB RAM + NVMe lokální cache | Běžná regionální infrastruktura |
| **Throughput** | 39.3 tokenů/sekunda (8GB setup) | Měřeno na Jetson Thor |
| **Přesnost** | strict_fp16 (zero precision drop) | Bez tichého zaokrouhlení |
| **Governance** | Pre-execution policy check (fail-closed) | Rozhodnutí PŘED spuštěním akce |
| **Data residency** | 100% lokální, zero cloud egress | EU AI Act Annex III/I ready |

---

## 3. PRACOVNÍ BALÍČKY (12 týdnů, 1 inženýr, 120k CZK)

| Pacek | Délka | Řádky | Výstup |
|-------|-------|-------|--------|
| **Track A: L1-L3** (Memory & Ingest) | Týdny 1-4 | 900 | SQL schema + policy accuracy baseline |
| **Track B: L4-L5** (Orchestration) | Týdny 1-4 | 1000 | 3 LangGraph piloty (hotel/sklo/škola) |
| **Track C: L6** (Infrastructure) | Týdny 1-4 | 200 | FreeToken benchmark (39.3 tok/s screenshot) |
| **Track D: L8-L7** (Proof + Eval) | Týdny 1-4 | 700 | Immutable audit trail + RAGAS baseline |
| **Integration** | Týdny 5-8 | — | Full L1→L8 pipeline, 7 proof artifacts |
| **Quality & Docs** | Týdny 9-12 | — | Annex IV dossier, KARP submission |

---

## 4. DODÁVKY (do 31. května 2027)

### POVINNÉ (bez toho se neposílá Phase 2)
1. **Natural-Language Harness** — 1500+ řádků Python/Rust, všech 8 vrstev, čitelné, testovatelné
2. **Databázové schéma** — SQL dump + pgvector CSV (compliance_timeline, governance_risks, tech_stack, evidence_by_process)
3. **1 funkční pilot** — Hotel scoring (full L1→L8 tok, 50+ loggovaných akcí)
4. **RAGAS 50 otázek** — 87%+ přesnost na compliance dataset
5. **Annex IV dossier** — 9 sekcí, auto-generated, PDF + JSON + KMS signatura
6. **7 proof artifacts** — CanIRun (S-F), FreeToken (39.3 tok/s), Is Agentic (118 checks), agentacct (receipt), unlazy (gates), RAGAS, AP2 ledger

### STRETCH (pro Series A)
- 3 funkční piloty (hotel + sklo + škola)
- Full Is Agentic A+ report
- EU Database registration number

---

## 5. TIMELINE & MILESTONY

```
1 září 2026:    Fáze 1 start (4 paralelní tracks)
16-22 září:     KARP podání (Romana Cernikova)
31. května:     Phase 1 done → Phase 2 trigger (BIC Plzen 1M)
2. prosince:    Annex III compliance (hotely) — 16 měsíců od teď
2. srpna 2028:  Annex I compliance (sklárnický průmysl) — 22 měsíců
```

---

## 6. ROZPOČET (120k CZK = 60% KARP grant)

| Položka | Cena | Poznámka |
|---------|------|----------|
| Senior inženýr 12 týdnů (60h/týden) | 60k CZK | 1000 CZK/hod ekvivalent |
| Hardware (RTX 4060 8GB + NVMe cache 2TB) | 11k CZK | Místní nákup Ostrov/Plzeň; NVMe dla Colibrí scheduling |
| Cloud services (Phase 1) | 0 CZK | Local-first only (Colibrí), Phase 2 Add GovCloud |
| Open-source nástroje | 0 CZK | Colibrí (free), Claude API ~$200-300 testing, LangGraph, pgvector |
| Dokumentace + testing | 12k CZK | Included v čase inženýra |
| Contingency 20% | 37k CZK | Build slippage, compliance checks |
| **CELKEM** | **120k CZK** | Fit KARP 60% struktura |

**Poznámka ke Colibrí:** C-engine Colibrí je 100% open-source (https://github.com/JustVugg/colibri v1.9.0), bez licenčních nákladů. NVMe cache (2TB) je zabudováno v hardware řádce, snižuje latenci scheduling na <50ms pro MoE model switching.

---

## 7. RIZ & MITIGATION

| Riziko | Pravděpodobnost | Dopad | Mitigation |
|--------|-----------------|-------|-----------|
| Compliance moving target | Střední | Schedule slip | Weekly KARP contact (Romana) |
| Hardware shortage | Nízké | Delay | Order RTX 4060 Week 1 |
| Engineer unavailable | Nízké | Stop | Have backup senior dev identified |
| EU Database late | Nízké | Phase 2 delay | Pre-register Sep 1 |

---

## 8. OČEKÁVANÝ VÝSLEDEK & DOPAD

**Produkt:** SMAOS Financial — Edge-Native Agentic Compliance Engine
- Běží 290B+ MoE lokálně na gaming PC (39.3 tok/s na 8GB)
- Každá akce immutable zaznamenána (PQC signatura)
- Human-in-the-loop enforcement (LangGraph checkpoint)
- Proof artifact: 7 dokumentů pro regulátora (bez "paperwork théâtre")

**Trh:** Hotely + sklárnický průmysl + školy v Karlovarském kraji
- Hotels/Spas: Annex III employment/biometrics (deadline 2. prosince 2027)
- Glass/Auto: Annex I safety component (deadline 2. srpna 2028)
- Schools/Municipalities: Annex III education/access

**Financování (post-KARP):**
- Oktober 2026: BIC Plzeň 1M CZK (Phase 2 scaling)
- Srpen 2027: Czech sandbox entry (first agentic governance instance)
- 2027: Series A (50M+) — uncontested market (orchestration-first positioning)

---

## 9. KONKURENČNÍ ANALÝZA

| Konkurent | Strategie | vs. SMAOS |
|-----------|-----------|-----------|
| Arthur AI ($27M) | Discovery-first (co běží?) | Arthur reactive; SMAOS proactive |
| Credo AI ($20M) | Inventory-first (katalog) | Credo static; SMAOS dynamic |
| OneTrust ($610M) | GRC platform extension | OneTrust pomalá; SMAOS agile |
| **SMAOS** | **Orchestration-first** | **Jediný endpoint-to-endpoint control** |

**Uncontested advantage:** Job Router (intelligentní routing) + Behavioral Firewall (proactive enforcement) + Feedback Router (learn from outcomes) = nobody else has this stack.

---

## 10. COMPLIANCE & GOVERNANCE PROOFS (Annex III/I Readiness)

**Colibrí jako vrstva dokazování governance**

Lokální inference engine Colibrí (Layer L6) poskytuje **sémantickou invarianci** — absolutní záruku, že žádný výpočet neurnikne mimo kontrolu governance. To řeší kritické GDPR + EU AI Act body:

- **Annex III (hotely, školy, veřejná služby):** Rozhodnutí o zaměstnanosti/přístupu MUSÍ být auditable + lokální. Colibrí: ✅ (zero cloud egress, PQC signatura v AP2 ledger)
- **Annex I (bezpečnostní komponenty, sklárnický průmysl):** Model outputs musí být reprodukční. Colibrí: ✅ (strict_fp16, bit-exact determinism na stejném HW)

**Reprodukční proof:** 
- Repository: https://github.com/JustVugg/colibri (v1.9.0)
- Test harness: `scripts/colibri_harness.sh` (lokální reprodukce za 30 sekund)
- Compliance artifact: 7-bodový checklist v Annex IV dossier (signed Ed25519, anchored v Git)

---

## 11. PODPIS

Andrei Leukhin
SMAOS s.r.o.
andrejlo123@gmail.com

**Podání:** 16-22 září 2026
**Kontakt:** Romana Cernikova, KARP (romana.cernikova@karp-kv.cz)

---

---

*Tento dokument je oficiální podání do KARP Startovací vouchery 2026.*  
*Datum přípravy: 31. srpna 2026*  
*Status: Připraveno k podání Sep 16-22, 2026*

**Přílohy v KARP_SUBMISSION_PACKAGE.md:**
- Technické schéma (8 vrstvy L1-L8)
- 3 pilotní specifikace (hotel/sklo/škola)
- 7 proof artifacts checklist
- Load test results (1000 iterací, 100% úspěšnost)
- GitHub commit history (106 testů, 0 chyb)
- Annex IV compliance dossier (9 sekcí)

**Kontakt na otázky:**  
Andrei Leukhin — andrejlo123@gmail.com
