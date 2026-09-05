# SMAOS Phase 1: Sovereign AI Operating System
## CzechInvest KARP Grant Submission

---

## Executive Summary

SMAOS (Sovereign Modular Agentic Operating System) is an edge-native compliance engine that enables financial institutions to deploy AI agents safely in regulated environments. Unlike cloud-dependent alternatives, SMAOS operates entirely offline, executes pre-flight veto gates before any action (preventing regulatory breaches at the source), and generates immutable audit trails signed with Post-Quantum Cryptography. This addresses a critical gap: EU AI Act compliance (mandatory Dec 2026) requires demonstrable pre-execution safety, which no existing product provides. Phase 1 delivers a 1500-line harness, 3 pilot workflows (hotel credit scoring, glass manufacturing compliance, school budgeting), and a regulatory dossier suitable for CRD VI/CRDIV attestation.

---

## Technical Innovation

**Pre-Execution Veto Gates (Layer 3):** Every AI decision passes through a permission layer before execution. An intent (e.g., "approve 50M CZK loan") triggers classification, then hits policy rules derived from Basel III, EU AI Act, and institution-specific mandates. If policy blocks the action, the system halts and escalates to human review—preventing regulatory violations before they occur. This is fundamentally different from post-execution audit trails, which catch violations too late.

**Merkle-DAG Audit Trails (Layer 8, AP2 Ledger):** Every action (classify, authorize, reject, sign) produces an immutable, cryptographically-signed receipt. Receipts chain together in a Merkle-DAG, enabling regulators to replay any decision point, verify authorization, and trace who approved what and when. Unlike traditional logs, Merkle-DAGs are tamper-proof: altering one receipt invalidates all downstream receipts, immediately visible to auditors.

**Offline-First Architecture (Layer 6):** SMAOS caches policies, knowledge graphs, and compliance rules locally on the institution's hardware. No cloud dependencies, no internet required for core classification/veto logic. This satisfies data sovereignty requirements (CZK 10M+ transfers cannot route through foreign infrastructure) and resilience mandates (financial networks must operate during ISP failures).

**Post-Quantum Cryptography (Ed25519):** All signatures use Ed25519 (quantum-resistant), future-proofing audit trails against post-quantum attacks. Critical for 20+ year regulatory retention periods.

---

## Market Opportunity

**EU AI Act Compliance (Hard Deadline: Dec 2026):** Financial institutions must demonstrate that AI systems used for credit decisions, capital allocations, and market-sensitive actions have pre-execution safety mechanisms. Regulators (ECB, ESMA, CRD VI) are actively auditing AI governance; non-compliance risks millions in fines and license revocation.

**Addressable Market:** 47 Czech banks + 200+ credit unions + 50+ insurance firms (CZK 9.2T assets under regulation). Each requires AI safety infrastructure. Competitors (Darktrace, Fortive, Palantir) operate cloud-first, failing sovereignty requirements; SMAOS captures the underserved "local-first" segment.

**Unit Economics:** License 30 institutions at 500K CZK/year (Phase 2) = 15M CZK ARR. KARP 120K is 0.8% of Year 1 revenue, unlocking institutional pilots + regulatory dossiers.

---

## Team & Timeline

**Solo Engineer + Advisors:** Andrej Leukhin (CTO, cryptography/systems background) leads Phase 1 full-time. Advisors: regulatory counsel (Annex IV compliance), cryptographer (Ed25519 audit), compliance officer (Basel III policy encoding).

**Phase 1 (Sep 1 – May 31, 2027, 9 months):**
- Weeks 1–4: Memory/Knowledge layers (pgvector + BM25 + policy rules)
- Weeks 5–8: Orchestration (LangGraph pilots) + Communication (MCP servers)
- Weeks 9–12: Integration + Annex IV dossier + KARP submission (Sep 16–22 hard deadline)

**Phase 2 (Jun–Dec 2027, BIC Plzeň 1M CZK):** Production pilots with 3 institutions, EU Database pre-registration, CE marking.

---

## Budget Allocation (120,000 CZK)

| Category | Amount | Purpose |
|----------|--------|---------|
| Hardware (GPU/silicon for testing) | 35,000 CZK | Benchmarking Qwen 39.3B on 8GB RAM; FreeToken infrastructure; CanIRun.ai compliance proof |
| Legal/Regulatory (2 consultations) | 25,000 CZK | Annex IV dossier review; Basel III rule encoding validation; KMS signing protocol audit |
| Testing Infrastructure | 20,000 CZK | Playwright + Vitest enterprise features; pgvector benchmark suite; compliance test golden set (50 questions) |
| Travel + Networking | 15,000 CZK | CzechInvest Demo Day (Prague); EBA regulatory workshop (Oslo); BIC Plzeň partnership kickoff |
| Contingency (7%) | 10,000 CZK | Unforeseen cryptographic audit findings; EU AI Act clarifications; pilot delay absorption |

**Total:** 120,000 CZK (9-month runway, 13,333 CZK/month ops).

---

## Success Metrics & Outcomes

**KARP Deliverables (Dec 2026):**
- ✅ Harness: 1500+ lines, <0.1 bugs/100 lines (static + manual verification)
- ✅ Database: pgvector compliance queries <100ms on target hardware
- ✅ Pilots: 3 end-to-end flows (hotel credit scoring, glass manufacturing compliance, school budgeting) with signed audit trails
- ✅ Annex IV: 9-section regulatory dossier, KMS-signed, ECB-ready
- ✅ RAGAS Baseline: 87%+ accuracy on 50-question compliance golden set

**Series A Narrative (2027):**
- 30-institution pilot pipeline (500K CZK/year each = 15M CZK ARR target)
- Merkle-DAG proof artifacts (demonstrate tamper-proof audit trail to investors)
- EU Database pre-registration number (CE marking path visible)
- Regulatory attestation from CRD VI audit partner

**Competitive Moat:**
- Only product with offline-first + pre-execution veto gates + Post-Quantum Cryptography
- Czech sovereignty positioning vs. US/Chinese cloud alternatives
- Regulatory-first design (policy rules encoded at Layer 3, not bolted on)

---

## Contact & Next Steps

**Applicant:** Andrej Leukhin (andrejlo123@gmail.com)  
**Project Start:** Sep 1, 2026  
**Submission Deadline:** Sep 16–22, 2026  
**Expected KARP Decision:** Oct 31, 2026  
**Phase 1 Delivery:** May 31, 2027

---

**Word Count: 1,045 words (target 1-page print format with 10pt font, 1" margins)**
