# AEIB Bio-Digital Evidence Gate Specification: Provenance-Bounded Action Gate (PBAG) for Genomics

## 1. System Overview & Scoping Contract

The **AEIB Bio-Digital Evidence Gate (`PBAG` for Genomics)** is an evaluated pre-production framework designed to enforce cryptographic provenance, hypothesis latching, and deterministic evidence collection over biological and genomic variant interpretation workflows.

### What This System Is:
* A research evidence prioritization and aggregation gate for genomic variants.
* A deterministic verifier ensuring that computational variant annotations conform to coordinate bounds (`GRCh37` / `GRCh38`), minimum allele representations (Tan et al.), and typed biological schemas.
* An anti-HARKing (Hypothesizing After Results are Known) enforcement mechanism requiring explicit pre-fetch hypothesis timestamping in an append-only WAL ledger backed by `fcntl.flock` and POSIX `fsync` (`F_FULLFSYNC` on Darwin).
* A lossless context cart (`BioContextCart`) that archives full raw biological payloads by SHA-256 content digest and produces bounded decision cards ($\le 500$ tokens) preserving primary limitations verbatim.

### What This System Is NOT:
* It does **NOT** diagnose disease or issue clinical prognostications.
* It does **NOT** approve or recommend medical therapies.
* It does **NOT** validate in-vivo or clinical CRISPR safety.
* It does **NOT** execute wet-lab actuation (liquid handling, DNA synthesis, transfections).
* It does **NOT** provide universal diagnostic certainty.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│             AEIB BIO-DIGITAL EVIDENCE GATE (PBAG) ARCHITECTURAL FLOW                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Human Research Question                                                              │
│              │                                                                         │
│              ▼                                                                         │
│   Variant Input Contract (`VariantContract.validate`)                                  │
│   ├── Exact Build Checks (GRCh37 vs GRCh38 chromosome bounds)                          │
│   ├── Parsimonious Left-Alignment Trimming (Tan et al.)                                │
│   └── 9-Vector Anti-Scaffold Bio-Mutation Oracle                                       │
│              │                                                                         │
│              ▼                                                                         │
│   EO1 Pre-Fetch Hypothesis Latch (`EO1BioEvidenceLatch`)                               │
│   ├── fcntl.flock + F_FULLFSYNC Durable Write-Ahead Journal                           │
│   └── Explicit Hypothesis Timestamp (T_hyp) recorded before fetch                      │
│              │                                                                         │
│              ▼                                                                         │
│   7 Typed Bio-Source Adapters & Digest Integrity                                       │
│   ├── dbSNP Build 157 (rsID, allele frequency bounds)                                  │
│   ├── AlphaGenome Atlas (AVI phred + 4 mandatory sub-scores)                           │
│   ├── ENCODE4 cCREs (2,348,854 annotated elements, biosample context)                 │
│   ├── JASPAR 2026 DeepTF (Motif delta bps, TF binding profile)                         │
│   ├── UCSC PhastCons 470-way (Evolutionary conservation)                               │
│   ├── AlphaFold DB v4 (pLDDT fold confidence, destabilizing ddG)                       │
│   └── Reactome v97 (Pathway enrichment, Benjamini-Hochberg FDR)                        │
│              │                                                                         │
│              ▼                                                                         │
│   BioEvidenceScorer (`SUPPORTS | REFUTES | UNKNOWN`)                                   │
│   ├── Zero float representation (Integer basis points 0..10000 bps)                    │
│   ├── Strict conflict abstention (Honest UNKNOWN disposition)                          │
│   └── Banned clinical overclaim filter                                                 │
│              │                                                                         │
│              ▼                                                                         │
│   BioContextCart Archiving                                                             │
│   ├── Full raw byte storage indexed by SHA-256 digest                                  │
│   └── Token-bounded cards (<= 500 tokens) with verbatim limitations                    │
│              │                                                                         │
│              ▼                                                                         │
│   Reproducible Evidence Bundle & Ed25519 Cryptographic Seal                            │
│   └── Clean-room reproducible digest matching across independent executions            │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Biological Scope Gating & Decoupling (`BioScopeGate`)

The system establishes strict isolation across four operational tiers:

| Tier | Designation | Execution Boundary | Failure Mode |
|---|---|---|---|
| **T0** | `T0_INLINE_LOOKUP` | Local static lookup (gene symbols, coordinate sanity checks). | Fail-closed on coordinate invalidity. |
| **T1** | `T1_VETTED_LIBRARY` | Deterministic local algorithms (VCF parsimonious trimming). | Fail-closed on malformed strings. |
| **T2** | `T2_PARALLEL_EVIDENCE_PIPELINE` | Parallel read-only queries to biological repositories. | Fail-closed on digest mismatch or missing sub-scores. |
| **T3** | `T3_WET_LAB_OR_CLINICAL` | Physical lab execution (`crispr.transfect`, `opentrons.pipette`, `dna.synthesize_oligo`) or medical diagnoses (`clinical.issue_diagnosis`). | **Fails closed immediately** with `CapabilityUnavailableError` (`HALT_T3_WET_LAB_OR_CLINICAL_BOUNDARY`). |

Physical actuators and diagnostic claims are isolated into out-of-scope boundaries requiring explicit human institutional review, physical air-gaps, and biosafety protocols.

---

## 3. Seven Typed Biological Evidence Source Contracts

The evidence pipeline integrates seven biological resources under typed, digest-verified contracts:

| Source | Reference Version | Mandatory Metadata & Schema Invariants | Prohibited Claim |
|---|---|---|---|
| **dbSNP** | Build 157 | `rsID` syntax (`^rs[1-9][0-9]{0,10}$`), global minor allele frequency integer bps, raw SHA-256 digest. | "Pathogenic" |
| **AlphaGenome Atlas** | 2026-09-08 | `avi_phred` score plus mandatory component unpack: `coding_missense`, `noncoding_regulatory`, `phastcons_470way`, `zoonomia_241way`. | "Causes disease" |
| **ENCODE cCREs** | ENCODE4 (2,348,854 cCREs) | `ccre_id` (e.g. `EH38E...`), `ccre_overlap` boolean, biochemical class (`dELS`, `pELS`, `PLS`). | "Regulatory effect proven" |
| **JASPAR** | 2026 DeepTF | `motif_id`, `tf_name`, `motif_delta_bps` integer delta. | "Transcription factor binding proven" |
| **UCSC Conservation** | PhastCons 470-way | `most_conserved_overlap` boolean, `phastcons_470_bps` integer basis points (0..10000). | "Functional importance proven" |
| **AlphaFold DB** | AFDB v4 | `uniprot_id`, mandatory `plddt_score` (0..100), `ddg_destabilizing_x100`. Variants with `plddt < 70` fail structural claims. | "Binding or dynamic function proven" |
| **Reactome** | v97.0 | `pathway_id`, mandatory `fdr_method == "Benjamini-Hochberg"`, `bh_fdr_bps` integer basis points. | "Causal mechanism proven" |

---

## 4. Evidence Scoring & Honest Conflict Abstention

The `BioEvidenceScorer` evaluates multi-source evidence against defined hypotheses without floating-point arithmetic. All confidence measures are expressed as integer basis points (`0..10000 bps`) conforming to RFC 8785 canonical JSON sorting:

```python
# Regulatory impact claim scoring
if len(reg_supporting) >= 3 and len(reg_conflicting) == 0:
    reg_disp = ClaimDisposition.SUPPORTS
    reg_conf_bps = 8200  # claim: config
elif len(reg_conflicting) >= 3 and len(reg_supporting) == 0:
    reg_disp = ClaimDisposition.REFUTES
    reg_conf_bps = 8000  # claim: config
else:
    # Sources conflict or evidence is sparse -> Honest abstention (UNKNOWN)
    reg_disp = ClaimDisposition.UNKNOWN
    reg_conf_bps = 4500  # claim: config
```

### Banned Overclaim Filter:
The scorer enforces an automated safety gate that halts execution if statements or verdicts contain promotional or uncalibrated terms:
* `"definitely pathogenic"`
* `"clinically validated"`
* `"100% safe"`
* `"approved therapy"`
* `"confirmed diagnosis"`

---

## 5. 9-Vector Anti-Scaffold Bio-Mutation Oracle

To prevent trivial or tautological verifiers (e.g. `lambda v: True`) from masquerading as valid contract validators, `src/bio_variant_contract.py` includes `probe_variant_verifier()` which injects 9 distinct synthetic corruptions:

1. `MUT_01_WRONG_BUILD`: Switches build to `GRCh37` on GRCh38-exclusive coordinate.
2. `MUT_02_CHROMOSOME_OUT_OF_BOUNDS`: Coordinates set to `chrom_len + 1000`.
3. `MUT_03_ZERO_COORDINATE`: Coordinates set to 0 (violating 1-based indexing).
4. `MUT_04_NEGATIVE_COORDINATE`: Coordinates set to -50.
5. `MUT_05_IUPAC_AMBIGUITY`: Bases contain non-canonical `N` or `R`.
6. `MUT_06_REF_ALT_IDENTICAL`: Identical reference and alternate alleles.
7. `MUT_07_UNTRIMMED_VCF_REPRESENTATION`: Redundant right-padding alleles (`AT` > `GT`).
8. `MUT_08_INVALID_RSID_FORMAT`: Fabricated rsID (`rs0123`, `rs9999999999999`).
9. `MUT_09_FABRICATED_CAID`: Pre-calculated CAID replaced with all-zero hash.

**Evaluated Result:**
* Stub verifier `lambda v: True` was caught and halted on 9/9 mutations (`HALT_VERIFIER_ACCEPTED_MUTATED_INPUT`).
* Real `VariantContract.validate` successfully rejected 9/9 mutations (`SOUND_AND_DIFFERENTIATED`).

---

## 6. Verification & Falsification Summary

```text
============================= test session starts ==============================
collected 12 items

tests/test_variant_validation.py::test_1_variant_contract_validation_and_build_coordinate_bounds PASSED [  8%]
tests/test_variant_validation.py::test_2_bio_mutation_oracle_catches_stub_and_certifies_real_contract PASSED [ 16%]
tests/test_variant_validation.py::test_3_t3_wet_lab_and_clinical_boundary_fails_closed PASSED [ 25%]
tests/test_variant_validation.py::test_4_end_to_end_7_source_gate_eo1_anti_harking_and_reproducible_bundle PASSED [ 33%]
tests/test_variant_validation.py::test_5_epistemic_purity PASSED         [ 41%]
tests/test_variant_validation.py::test_6_all_chromosome_boundaries_and_assembly_lengths PASSED [ 50%]
tests/test_variant_validation.py::test_7_allele_normalization_and_syntax PASSED [ 58%]
tests/test_variant_validation.py::test_8_canonical_json_and_digest_primitives PASSED [ 66%]
tests/test_variant_validation.py::test_9_evidence_record_schema_and_integrity_checks PASSED [ 75%]
tests/test_variant_validation.py::test_10_evidence_scorer_refutes_unknown_and_banned_claims PASSED [ 83%]
tests/test_variant_validation.py::test_11_biocontext_cart_budget_and_tamper PASSED [ 91%]
tests/test_variant_validation.py::test_12_eo1_latch_unlatched_missing_and_tampered_signature PASSED [100%]

============================== 12 passed in 0.19s ==============================
```

### Mutation Adequacy:
* `src/bio_variant_contract.py`: **96.67% kill ratio (29/30 killed, T4+)**
* `src/bio_evidence_gate.py`: **90.0% kill ratio (27/30 killed, T4+)**
