# Unverified Claims Register

> [!CAUTION]
> **Do not send any claim listed here to an investor, customer, partner, regulator, patent office or the public until either (a) the evidence in the "Evidence required" column exists in this repository and has been checked, or (b) the claim has been removed from the source file.**
> This applies to every file named below, including email templates and the `send-series-a.sh` batch sender in `.claude/series_a_launch/`.

- **Compiled:** 2026-10-26, from the Section 42 pre-market go/no-go audit and its claims scan (`hits.tsv`, 3,358 keyword hits across 15 roots).
- **Classes:**
  - **UNBACKED**: no supporting document, test, attestation or measurement was found in the repo.
  - **CONTRADICTED**: repo contents or a reproduced run show the claim is false as written.
- **Search performed for supporting evidence (2026-10-26):**
  - We searched filenames for LOI, invoice, signed contract, SOC 2 report and attestation PDFs. The only matches were **unsigned templates**: `docs/legal/LOI_Israeli_Defense_Partner_Template.md` and `.claude/market/israel/loi-response-template.md`. No signed LOI, contract, invoice, PO or auditor report exists in the repo.
  - `EVIDENCE_MANIFEST.md` §"Explicit Scope Limitations" itself states AEIB does **NOT** claim ISO 42001, EU AI Act, SOC 2 or DORA compliance.
- **Coverage:** the rows below are the specific instances found. The same claims are repeated in many more lines. Every file listed in the `DO_NOT_SEND_UNVERIFIED.md` notices should be treated as containing unverified material until reviewed line by line.

---

## 1. Traction / revenue / customers

| File:line | Exact claim (verbatim or trimmed) | Class | Evidence required |
|---|---|---|---|
| `.claude/series_a_launch/QUICK_START_GUIDE.md:228` | "Lead with traction (3 paying pilots)" | UNBACKED | Signed pilot agreements + invoices/payment records for 3 pilots |
| `.claude/series_a_launch/QUICK_START_GUIDE.md:267` | "3 paying pilots + 120+ controls = unforgettable proof point" | UNBACKED | Same as above; control inventory with tests |
| `.claude/series_a_launch/5_INVESTOR_FAQ.md:378` | "3 paying pilots (not warm leads) = customer execution proven" | UNBACKED | Same as above |
| `.claude/series_a_launch/2_FINANCIAL_MODEL.md:68` | "Pilot Y0 \| 3 \| €200k \| €50k \| €600k" (presented as pilot revenue) | UNBACKED | Contracts/invoices; otherwise relabel as projection |
| `.claude/investor-materials/50-WARM-VC-LIST.md:74` | "4 finance pilots in-flight. €480K ARR by Oct 2026." | UNBACKED | 4 signed pilot agreements with fees; ARR calculation from invoices |
| `.claude/investor-materials/COLD-EMAIL-TEMPLATE.md:122` | "4 pilots in-flight = €480K ARR by Oct 2026." | UNBACKED | Same as above |
| `.claude/investor-materials/COLD-EMAIL-TEMPLATE.md:98` | "4 pilots in-flight = €380K ARR by Oct 2026." (healthcare) | UNBACKED | Signed agreements |
| `.claude/investor-materials/COLD-EMAIL-TEMPLATE.md:146` | "5 pilots in-flight = €750K ARR by Oct 2026." (defense) | UNBACKED | Signed agreements |
| `.claude/investor-materials/50-WARM-VC-LIST.md:46` | "€95K healthcare pilot in-flight." | UNBACKED | Signed agreement |
| `.claude/investor-materials/SERIES-A-INVESTOR-DECK.md:54,66` | "€2.15M ARR in 4 Months" / "4-Month ARR: €2.15M (across 3 independent sales teams…)" | UNBACKED | Revenue ledger, contracts, sales-team records |
| `.claude/investor-materials/COLD-EMAIL-TEMPLATE.md:22,50,72` | "We have proof. €2.15M ARR in 4 months across 3 channels." | UNBACKED | Same as above |
| `.claude/investor-materials/TERM-SHEET-OUTLINE.md:28` | "Total 4-month ARR: €2.15M" | UNBACKED | Same as above |
| `.claude/investor-materials/PILOT-DEAL-STRUCTURES.md:141` | "Total ARR by Dec 2026: €2.15M across 3+ pilots per channel" | UNBACKED | Same as above |
| `.claude/investor-materials/SERIES-A-INVESTOR-DECK.md:60` | "Proven enterprise willingness-to-pay: €250K-€500K+/yr per customer" | UNBACKED | Priced, signed offers or customer interviews with documented WTP |
| `.claude/investor-materials/investor-deck-final.md:251` | "5 enterprise customers signed (JPMorgan, Novartis, Intel, Renko, 1 gov), 3 government LOIs inbound" | UNBACKED | 5 signed customer contracts + 3 LOIs |
| `.claude/investor-materials/investor-deck-final.md:193,196` | "Renko Smartgrid \| LIVE … €55K MRR" / "Renko current: €55K MRR" | UNBACKED | Contract + invoices for Renko |
| `.claude/investor-materials/investor-deck-final.md:376` | "Ukraine (75 nodes) + Israel (IDF integration) + Renko (€55K MRR validation) are not projections. They're deployed. We have three LOIs from JPM…" | UNBACKED | Deployment records, signed LOIs |
| `.claude/investor-materials/warm-intros.md:613` | "Renko financial pilot: Revenue expanded to €175K MRR (€2.1M ARR run-rate)" | UNBACKED | Invoices |
| `.claude/investor-materials/pitch-deck.md:157` | "Renko financial pilot: AP2 settlement validation live (€55K MRR contracted)" | UNBACKED | Contract |
| `.claude/investor-materials/02-ONE-PAGER.md:54` | "Field deployments: Ukraine (75 Jetson Orin + Starlink, ICRC partnership), Israel (IDF C4I integration)" | UNBACKED | Deployment records + partner confirmation |
| `.claude/investor-materials/04-INVESTOR-STORY-ARC.md:113` | "Ukraine + Israel field deployments prove operability in contested environments." | UNBACKED | Same as above + field telemetry |
| `.claude/investor-materials/04-INVESTOR-STORY-ARC.md:151` | "Four capsule families already deployed in production" | UNBACKED | Deployment records |
| `.claude/investor-materials/06-TALKING-POINTS.md:38` | "We have 75 Jetson Orin nodes live in Ukraine as we speak. ICRC partnership. MacArthur funding." | UNBACKED | Deployment records, partnership and grant documents |
| `.claude/investor-materials/pitch-deck.md:152` | "Ukraine: 75 Jetson Orin + Starlink nodes LIVE (July 15, 2026) - ICRC partnership + MacArthur funding" | UNBACKED | Same as above |
| `Series-A-Materials/01_PITCH_DECK_V2_15_SLIDES.md:118,304` | "Revenue Run Rate: €83K/month (€180K ARR)"; "Customer Revenue: €180K ARR as of June 6, 2026 (contracts signed)" | UNBACKED (also internally inconsistent: €83K/month ≠ €180K/yr) | Signed contracts + invoices |
| `Series-A-Materials/02_ONEPAGER_EXECUTIVE_SUMMARY.md:26` | "Contract Proof: €180K ARR (Prague CB, German Regulator, Creator Platform)" | UNBACKED | Signed contracts with each named party |
| `Series-A-Materials/DELIVERABLES_SUMMARY.txt:89` | "Customer Revenue: €180K ARR (3 customers: Prague CB €35K, German Regulator €40K, Creator Platform €8K)" | UNBACKED (also inconsistent: these add to €83K, not €180K) | Contracts/invoices |
| `Series-A-Materials/VALIDATION_REPORT.md:131` | "Customer Revenue \| €180K ARR (3 customers) \| Signed contracts + SLA proof \| … \| Validated ✅" | UNBACKED: "Validated" has no artefact behind it | The signed contracts it cites |
| `Series-A-Materials/INDEX.md:291`, `README.md:38,300` | "€180K ARR (3 customers) \| Contracts" | UNBACKED | Same as above |
| `.claude/reports/night-cycle/SERIES_A_PITCH_DECK.md:87,100,363` | "Prague Central Bank: EUR 50k/year contract … ✓ Validated"; "Win rate: 100% of pilots → production contracts" | UNBACKED | Contract; conversion records |

## 2. Named third parties (implied relationships)

| File:line | Exact claim | Class | Evidence required |
|---|---|---|---|
| `.claude/investor-materials/warm-intros.md:21` | "JPMorgan just signed AXIOM as a design partner." | UNBACKED | Signed design-partner agreement; written permission to name |
| `.claude/investor-materials/investor-deck-final.md:251,376` | JPMorgan, Novartis, Intel, Renko named as signed customers / LOI issuers | UNBACKED | Signed documents + permission to name |
| `.claude/investor-materials/02-ONE-PAGER.md:54`; `05-EMAIL-TEMPLATES.md:235`; `00-DELIVERY-SUMMARY.txt:224` | "ICRC partnership" / "ICRC partnership active" | UNBACKED | Partnership agreement; ICRC consent to be named |
| `.claude/investor-materials/01-PITCH-DECK-OUTLINE.md:100`; `pitch-deck.md:152` | "MacArthur funding" | UNBACKED | Grant letter |
| `.claude/investor-materials/02-ONE-PAGER.md:54`; `investor-deck-final.md:232` | "Israel (IDF C4I integration)" / "IDF C4I integration live on July 17" | UNBACKED | Contract/authorisation from the Israeli MoD/IDF |
| `.claude/series_a_launch/02-EMAIL-TEMPLATES-TIER1.txt:31` | "Live deployments: IDF C4I integration (classified system, TS/CS compliant by Sept 30)" | UNBACKED | Same as above + accreditation |
| `.claude/series_a_launch/05-EMAIL-TEMPLATES-TIER4.txt:64` | "Per our on-site briefing, AXIOM is IDF-ready. Dilithium signing is operational." | UNBACKED. The ML-DSA path (`tools/hybrid_pqc_envelope.py`) needs a Rust signer binary; the PQC tests **skip** on this host | Record of the briefing; a passing ML-DSA test run on the target host |
| `.claude/series_a_launch/TREASURY_STACK_READINESS.md:3,159` | "READY FOR UNICREDIT PILOT (Oct 2026)"; "UniCredit Pilot: Oct 1 - Dec 31" | UNBACKED: implies an agreed pilot | Pilot agreement or written confirmation from UniCredit |
| `Series-A-Materials/02_ONEPAGER_EXECUTIVE_SUMMARY.md:26` | "Prague CB, German Regulator, Creator Platform" as paying customers | UNBACKED | Contracts + permission to name |
| `.claude/reports/night-cycle/palantir/PILOT_METRICS_FOR_INVESTORS.md:16` | "Prague, Frankfurt, and London pilot participants reported zero service interruptions" | UNBACKED | Participant identities, signed pilot terms, monitoring exports |

## 3. Compliance / certification

| File:line | Exact claim | Class | Evidence required |
|---|---|---|---|
| `.claude/investor-materials/investor-deck-final.md:351` | "We're the only compliant solution." (EU AI Act) | UNBACKED; CONTRADICTED by `EVIDENCE_MANIFEST.md` scope limitations ("Does NOT claim … EU AI Act … compliance") | Conformity assessment; market survey supporting "only" |
| `.claude/series_a_launch/EXECUTION_SUMMARY.md:215` | "Real compliance (EU AI Act Article 14, SEC Rule 17a-4)" | UNBACKED / CONTRADICTED (same scope note) | Legal opinion + conformity assessment |
| `.claude/series_a_launch/README_UNICREDIT_DEMO.md:44` | "Uneditable, cryptographically proven, SEC Rule 17a-4 compliant." | UNBACKED | 17a-4(f) WORM storage assessment / third-party attestation letter |
| `.claude/series_a_launch/UNICREDIT_OUTREACH_EMAIL.md:46` | "…cryptographically verified, SEC Rule 17a-4 compliant." | UNBACKED | Same as above |
| `.claude/series_a_launch/SERIES_A_INVESTOR_BRIEF.md:122` | "SEC Rule 17a-4: Immutable ledger compliant" | UNBACKED. The EO1 ledger is a single-host file; the red team showed rollback of a matching older ledger+HWM pair cannot be detected without an external anchor | Same as above |
| `.claude/series_a_launch/OUTREACH_PLAYBOOK.md:126` | "JSON + PDF, SEC Rule 17a-4 compliant" | UNBACKED | Same as above |
| `.claude/series_a_launch/TREASURY_STACK_READINESS.md:178` | "Audit trail passes SEC Rule 17a-4 compliance check" | UNBACKED: no such check exists in the repo | The check itself + its output |
| `.claude/investor-materials/warm-intros.md:464` | "Security: SOC 2 Type II + penetration testing (annually)" | UNBACKED. `PILOT_METRICS_FOR_INVESTORS.md:292` itself says SOC2 Type II is "❌ Pending" | SOC 2 Type II report from a licensed CPA firm; pentest report |
| `.claude/investor-materials/QUICK-REFERENCE.txt:59` | "Post-quantum ready now. Field-proven. TS/CS compliant." | UNBACKED | Accreditation by the relevant national authority |
| `.claude/investor-materials/04-INVESTOR-STORY-ARC.md:113` | "Only post-quantum governance layer that's classified-system ready (TS/CS compliant)." | UNBACKED | Same as above |
| `.claude/series_a_launch/05-EMAIL-TEMPLATES-TIER4.txt:56` | "AXIOM Protocol, TS/CS compliant" | UNBACKED | Same as above |
| `.claude/investor-materials/PILOT-DEAL-STRUCTURES.md:45` | "DORA-compliant incident log" | UNBACKED. `src/ocr_audit/reporter.py` emits DORA *label mappings* only, unsigned | Legal mapping reviewed by counsel; DORA RTS conformance evidence |
| `.claude/investor-materials/PILOT-DEAL-STRUCTURES.md:74` | "CMMC-compliant pre-execution governance … assessment-ready audit log" | UNBACKED | C3PAO assessment |
| `.claude/series_a_launch/4_CUSTOMER_VALIDATION_PLAN.md:214,238` | "CMMC-Compliant Audit Trail" / "Fully compliant" | UNBACKED | Same as above |
| `.claude/series_a_launch/5_INVESTOR_FAQ.md:288` | "School District: €100k ACV, 2k access logs, CMMC-compliant, reference ready" | UNBACKED (customer + compliance) | Contract + C3PAO assessment |
| `Series-A-Materials/README.md:297`; `VALIDATION_REPORT.md:58` | "CMMC 23/23 practices complete" | UNBACKED. `Series-A-Materials/test_series_a_artifacts.py:298` only checks that the string "CMMC 23/23" *appears* in the materials (a trivial verifier) | Practice-by-practice evidence + assessor sign-off |
| `.claude/investor-materials/warm-intros.md:224` | "cryptographic audit trail (HIPAA compliant)" | UNBACKED | HIPAA risk assessment, BAA |

## 4. Patent technical claims

> [!WARNING]
> Send these to patent counsel **before** filing or relying on any priority claim. Incorrect statements in a filing can harm enforceability.

| File:line | Exact claim | Class | Evidence required |
|---|---|---|---|
| `.claude/patent/AXIOM_FILING_PACKAGE.txt:57` | "IVB is implemented and proven in siss-night-cycle (Lean 4 proofs: ρ, σ, φ, α, π, δ, λ)" | **CONTRADICTED.** `find crates/siss-night-cycle -name '*.lean'` → **0 files**. `lean` and `lake` are not installed, so none of the repo's 10 `.lean` files (in `proofs/` and `formal-verification/lean/`) have been checked on this host, and none of them sit in `siss-night-cycle` | Lean 4 sources for the named operators, plus a `lake build` log showing they check with no `sorry` |
| `.claude/patent/AXIOM_PROVISIONAL_CLAIMS_FINAL.md:67` | same sentence as above | CONTRADICTED | Same as above |
| `.claude/patent/AXIOM_FILING_PACKAGE.txt:131`; `COUNSEL_COVER_LETTER.md:55` | "IVB language tied to proven code: siss-night-cycle (Lean 4) … ✓" | CONTRADICTED | Same as above |
| `.claude/investor-materials/01-PITCH-DECK-OUTLINE.md:161` | "Live implementation: siss-night-cycle/src/operators.rs (Lean 4 proofs)" | CONTRADICTED. `operators` is a Rust module directory; it has no Lean | Same as above |
| `.claude/investor-materials/04-INVESTOR-STORY-ARC.md:147`; `03-INVESTOR-TARGETING-STRATEGY.md:262`; `06-TALKING-POINTS.md:118`; `warm-intros.md:110`; `05-EMAIL-TEMPLATES.md:72,258,295`; `02-ONE-PAGER.md:127` | "Lean 4 proofs" / "IVB proofs are in Lean 4 (public GitHub, auditable)" | CONTRADICTED | Same as above |
| `.claude/patent/AXIOM_FILING_PACKAGE.txt:70-73`; `AXIOM_PROVISIONAL_CLAIMS_FINAL.md:83-86` | "All cryptographic primitives are quantum-resistant: Signatures: Ed25519 + CRYSTALS-Dilithium (hybrid) … Covenant enforcement: Ed25519 signing on every mutation" | **CONTRADICTED.** Ed25519 is not quantum-resistant. `src/ocr_audit/reporter.py` labelled its output "Ed25519+ML-DSA-65" while producing no signature at all (relabelled 2026-10-26) | Code path that signs every mutation with ML-DSA, and a test run on the target host |
| `.claude/patent/AXIOM_FILING_PACKAGE.txt:142` | "All signatures use Ed25519 + Dilithium hybrid mode (quantum-resistant)." | CONTRADICTED (see row above) | Same as above |
| `.claude/patent/PROVISIONAL_CLAIMS_FINAL_v1.0.md:144`; `PROVISIONAL_CLAIMS_OUTLINE_v1.0.md:144` | "SMAOS architecture is the first production sys[tem]…" | UNBACKED: no production deployment evidence; "first" needs a prior-art search | Deployment evidence; prior-art search |
| `.claude/investor-materials/investor-deck-final.md:373` | "We're post-quantum ready today. Ed25519 + CRYSTALS-Dilithium are NIST-standardized." | UNBACKED as a product claim. Ed25519 is not PQ, and ML-DSA signing runs only through an external binary that is absent on this host | Passing ML-DSA tests on target host |

## 5. Benchmark / performance numbers

| File:line | Exact claim | Class | Evidence required / reproduced value |
|---|---|---|---|
| `FOR_REVIEWERS.md:161-162` (before 2026-10-26) | "Naive Retry 500/500 100.0%"; "Payload-Derived Key 314/500 62.8%" | **CONTRADICTED. Corrected in place** to the reproduced values **302/500 (60.4%)** and **187/500 (37.4%)** from `python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42` (deterministic simulation) | n/a: fixed |
| `FOR_REVIEWERS.md:163` | "Server-Side Stable Key \| 0 /500 \| 0.0% \| UNRESOLVED DROPS" | Incomplete. The same run reports **198 unresolved** for this arm | Add the 198 count (outside this edit's line scope) |
| `FOR_REVIEWERS.md:164,167` | "ZERO DUPLICATES (0.86ms)" / "~0.86 ms p50" | UNBACKED. The harness run on 2026-10-26 prints no latency. The real-class EO1 benchmark measured **+14.3 ms p50 / +47.0 ms p95** added latency | A command that prints this p50; otherwise replace with the real-class figure |
| `.claude/investor-materials/investor-deck-final.md:173-174` | "Merkle-DAG consistency 100%"; "Deterministic replay accuracy 100%" | UNBACKED: no command or output cited | Named test/benchmark + output file |
| `.claude/investor-materials/series-a-brief.md:67,126,143` | "Sub-5ms verification latency = 100x faster than manual audit"; "3.2ms latency"; "4.1ms latency" | UNBACKED | Benchmark script + host spec + raw timings |
| `.claude/investor-materials/series-a-brief.md:163` | "ALL AUTHENTIC (confidence: 100%)" | UNBACKED | Verifier output; definition of "confidence" |
| `.claude/investor-materials/warm-intros.md:463` | "SLA: 99.9% uptime" | UNBACKED: no hosted service exists to measure | Monitoring data from a running service |
| `.claude/reports/night-cycle/SERIES_A_PITCH_DECK.md:56,92,368` | "Zero data loss in live pilot (99.91% uptime, 102µs P99 latency)" | UNBACKED: no live pilot evidence | Monitoring exports from the pilot |
| `.claude/reports/night-cycle/palantir/PILOT_METRICS_FOR_INVESTORS.md:10,28-33,164,180,196` | Per-region daily uptime tables (99.87–99.96%), "P99 latency 102µs" | UNBACKED: no raw monitoring data in repo | Raw monitoring exports |
| `Series-A-Materials/DELIVERABLES_SUMMARY.txt:15,25`; `03_INVESTOR_TEMPLATES_PERSONALIZED.md:138` | "Data-backed metrics: Vision API <1ms" | UNBACKED: no benchmark output cited | Benchmark command + output |
| Pasted "7-dimension packer" figures (98.9%, 99.3%, 96.4%, "95% cost drop", "100% constraint recall") | Not in repo files; were in pasted material | UNBACKED: never measured (audit §6) | A real tokenizer and provider cache counters |

---

## How to clear a row

1. Put the evidence artefact in the repo (or in a referenced data room with its SHA-256 recorded in `EVIDENCE_MANIFEST.md`).
2. Add the command or document path to the row and change the class to **BACKED (date, reviewer)**.
3. Otherwise delete or reword the claim at the source line, and mark the row **REMOVED (date)**.
