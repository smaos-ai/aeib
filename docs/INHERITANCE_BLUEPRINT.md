# Inheritance Blueprint: rebuilding this system from zero, in one direction

Status: prototype guide, written 2026-10-28 from what this repository measured. Every file path in
backticks below is checked by `tests/test_inheritance_blueprint_references.py`, so a renamed or
deleted file makes CI fail instead of leaving a dangling reference. Numbers carry the command or
file that produced them. Durations marked *(assumption)* were not measured.

> The code can be thrown away and rewritten. What is worth handing over is the judgment: what
> to build first, what to distrust, and which checks catch which mistakes.

---

## 1. The one idea to understand first

Four roles. No single entity may play two of them for the same action.

| Role | Who | What it may do | What it may never do |
|---|---|---|---|
| Proposer | the model / agent | propose code, plans, tool calls | grade its own proposal |
| Verifier | deterministic code (tests, AST gates, canonical hashes, model checker) | accept or reject with a typed reason | approve an irreversible consequence |
| Approver | a named human | accept residual risk for an irreversible action | type a claim's status by hand |
| Referee | the real target (bank API, file system, database) | decide what actually happened | be assumed; it must be read back |

Two invariants follow from the table:

1. **Status is computed, never typed.** A claim becomes VERIFIED only when a tool re-runs its check
   against the current tree (`src/truth_compass.py`, `tools/where_we_stand.py`). A person or agent
   writing "VERIFIED" without a check is rejected (`ERR_STATUS_WITHOUT_CHECK`).
2. **Uncertain means stopped.** If the outcome of an action is unknown (lost acknowledgement,
   timeout), the action is latched as `EFFECT_INDETERMINATE` and is not retried until a read-back
   settles it (`src/eo1_write_before_execute.py`, `src/eo1_reconciliation_adapter.py`).

---

## 2. Build order: brakes before the engine

Do not start phase N+1 until phase N's exit gate passes. Each phase names the module in this repo you
can compare your version against after you have written your own.

| Phase | Build | Exit gate (must pass) | Compare with | Time *(assumption)* |
|---|---|---|---|---|
| 0. Ground | One canonical serializer (RFC 8785 JCS, integers only, no floats), one strict JSON reader (reject duplicate keys, NaN) | Reference vectors in `tests/data/jcs` reproduce byte-for-byte; a differential test shows every other serializer in the repo agrees | `src/jcs_canonicalizer.py`, `src/strict_json_ingress.py`, `tests/test_jcs_single_source.py` | 3 days |
| 1. Compass | Truth ledger: claims with status, falsifier, and an executable check; status computed by re-running the check | Hand-typed VERIFIED is rejected; a failing test turns a claim REFUTED; T3 is blocked while a safety-critical claim is unverified | `src/truth_compass.py`, `tests/test_truth_compass.py`, `docs/truth/ledger.json` | 1 week |
| 2. Local gates | Pre-commit hook: AST purity (no eval/exec/pickle), no mocks of the code under test, claim gate, banned-word scan on added lines, fast tests | A planted bad commit (e.g. `exec(` in `src/`) is rejected by the hook | `scripts/hooks/pre-commit` (activated with `git config core.hooksPath scripts/hooks`), `compliance/ast_purity.py`, `compliance/no_mock_enforcer.py`, `compliance/claim_integrity_gate.py` | 1 week |
| 3. The latch | Intent ledger written before dispatch; `EFFECT_INDETERMINATE` latch; effect-key identity (the business fields, not the wording); read-back reconciler | Under injected lost-acks and reworded retries: 0 duplicate effects, 0 wrongly blocked distinct intents | `src/eo1_write_before_execute.py`, `src/eo1_effect_key.py`, `src/eo1_reconciliation_adapter.py`, `benchmarks/undobench_100_trial_effect_key.py` | 2 weeks |
| 4. Attack yourself | Mutation testing (with equivalent mutants excluded by the tool), red-team scripts with a positive control per row | Each core module has a mutation kill ratio of at least 90%, measured with all of its tests; every red-team row has a control that succeeds with the defence switched off | `tools/mutation_adequacy_gate.py`, `tests/test_mutation_adequacy_gate.py` | 2 weeks |
| 5. Boundaries | Package-install allowlist from lockfiles, protected paths (agent configs, CI, `.git`), egress allowlist, MCP tool-definition pinning, child processes with empty env + timeout + memory watchdog | Typosquat name, `.github/workflows` write, metadata-IP egress, changed tool description, and a 512 MiB child allocation are each refused with a typed reason | `src/package_install_gate.py`, `src/protected_path_egress_policy.py`, `src/mcp_schema_pinning.py`, `src/repo_reverse_engineering_engine.py` | 2 weeks |
| 6. Domain evidence | Only now: domain data (e.g. biology) with quorum across independent sources and identifiers checked against the live source | Every accession in a test fixture is verified against its database; a model prediction never authorizes a real-world action | `src/sources/dbsnp.py`, `tests/test_sources_dbsnp.py` | open |
| 7. Discovery | Search loops (proposer + immutable verifier), only after phases 0–5 hold | A candidate that imports the scorer, uses floats in an exact domain, or escapes via dunders is rejected before it runs; candidates run out of process | `src/vesper_harness_gates.py`, `src/lajolla_covering_verifier.py`, `tests/test_vesper_harness_gates.py` | open |

For a first pass, phases 0–3 are enough. They are the part buyers and reviewers care about. Phases
4–5 make it trustworthy, and phases 6–7 are optional.

---

## 3. The catch ledger: mistakes this repo already paid for

Each row comes from this repository's history. "Why" is a shortened 5-Whys chain down to the root
cause. "Gate" is what now catches the mistake automatically.

| # | What happened | Why (root cause) | Rule | Gate / evidence |
|---|---|---|---|---|
| 1 | About 20 local copies of "canonical JSON" diverged from RFC 8785 (key order, `1e+21`) | Each module wrote its own `json.dumps(sort_keys=True)`, because nothing forbade it, because "canonical" was treated as a style rather than a contract | One serializer. Every other copy is found by AST scan and fails CI | `tests/test_jcs_single_source.py`, `tests/test_jcs_canonicalizer_discovery.py` |
| 2 | An allele frequency of exactly 1.0 could be re-read as 1 basis point | Units were inferred from the Python literal type (float vs int), and canonical JSON writes `1.0` as `1` | Units are explicit fields; JCS payloads carry integer basis points | `src/sources/dbsnp.py`, `tests/test_sources_dbsnp.py` |
| 3 | The latch prevented duplicates but left most intents unresolved (`EFFECT_INDETERMINATE` with no way out) | Safety was built without liveness, so the read-back path was missing | Every latch ships with a read-back reconciler and an honest "still unknown" outcome | `docs/benchmarks/EO1_REAL_DUPLICATE_BENCHMARK.md` |
| 4 | A reworded retry (new memo, new UUID, fields reordered) got a new identity and passed the latch: 33 duplicates in 300 (11.0%, A2 row) | Identity was a hash of the whole payload, and payload wording is model-generated noise | Identity = declared business fields per tool (effect key). Unknown tool means refuse | `docs/benchmarks/EO1_REAL_DUPLICATE_BENCHMARK.md`, `src/eo1_effect_key.py` |
| 5 | A read-back saying "not applied" was trusted even though the request could still commit later (late commit, F9) | The reconciler assumed the target's state was final at read-back time. LIMBO (arXiv:2609.29095) shows that read-back alone cannot give exactly-once here | "Not applied" counts only if the target fences the key or a server deadline has passed; otherwise stay unknown | `docs/benchmarks/EO1_REAL_DUPLICATE_BENCHMARK.md` (A3 F9 rows), `src/eo1_protocol_model_checker.py` |
| 6 | Trivial verifiers: a "proof" accepted if the text contained the word `theorem`; a gate runner printed "certified" unconditionally; a file could opt out of the banned-word scan by mentioning the scanner's token | Checks verified the shape of the output, not the property, and nobody attacked the checker | A check must fail on a counterfeit input. Write that counterfeit test first | `src/slop_filter.py`, `tests/test_slop_filter.py`, `tools/run_all_verification_gates.py` |
| 7 | Mutation scores were raised by restyling the target code (`return None` → `return`) instead of strengthening tests | The meter counted equivalent mutants, and the incentive was the number | Fix the meter (with a regression test), never the target | `tests/test_mutation_adequacy_gate.py` |
| 8 | Two real arXiv papers would have been reported "NOT FOUND" | The lookup used the `http://` API endpoint and returned nothing, and no known-good control ID was checked | "Not found" needs a positive control that was found in the same lookup | session log; proposed rule L2 |
| 9 | A red-team row printed PASS without measuring anything | The row hardcoded `True` / read a string the harness never returns | Every red-team row runs the probe with the defence off as a control; if the control fails, print INCONCLUSIVE | red-team scripts; proposed rule L3 |
| 10 | On macOS a child process allocated 512 MiB despite `setrlimit` | Darwin does not enforce `RLIMIT_AS` for mmap-backed memory | Do not trust an OS limit you have not measured on that OS; add a parent-side RSS watchdog | `src/repo_reverse_engineering_engine.py`, `tests/test_repo_reverse_engineering_engine.py` |
| 11 | External documents claimed Lean 4 proofs, customers and certifications that no file supported | Marketing text was written before evidence and was never checked against the repo | External claims must name a file or test; the rest goes to a register | `docs/UNVERIFIED_CLAIMS_REGISTER.md`, `docs/EVIDENCE_ONE_PAGER.md` |
| 12 | A pasted test fixture used a fabricated ENCODE accession and an unrelated motif (CTCF) for an APOE variant | Identifiers were generated to look plausible and were not looked up | Every identifier in a fixture is resolved against its database before commit | session log |
| 13 | Pasted drafts ran candidate code in-process with `exec`, built a benchmark whose answer was computed by construction, and attributed a baseline to a paper that does not describe it | Drafts were treated as near-final, and the benchmark's prediction was encoded as its mechanism | Untrusted code runs out of process; a benchmark must be able to fail; attribute only what the source says | `src/vesper_harness_gates.py`, `benchmarks/undobench_100_trial_effect_key.py` |
| 14 | Scope sprawl: 279 markdown files at the repo root and 293 under `docs/` (counted 2026-10-28 with `find`/`ls`) | Every idea became a document before it became a test | One document per tested capability. Ideas without a test go to a backlog, not to `docs/` | this file |

---

## 4. The gates, by stage

| Stage | What runs | Where |
|---|---|---|
| Pre-commit (local, about 30 s) | claim gate on staged files, AST purity, no-mock, zone boundary, banned words on added lines, fast core tests | `scripts/hooks/pre-commit` |
| CI (every push) | full test suite, verification gate runner, JCS single-source differential | `.github/workflows/aeib-ci.yml`, `tools/run_all_verification_gates.py` |
| Simulation (before claiming anything about retries) | fault injection: lost ack, crash and restart, reworded retry (F8), late commit (F9), read-back timeout; deterministic seed | `benchmarks/eo1_real_duplicate_benchmark.py`, `benchmarks/undobench_100_trial_effect_key.py`, `tests/test_eo1_protocol_model_checker.py` |
| Mutation (per changed core module) | kill ratio with all tests of the module; survivors listed, not rounded up | `tools/mutation_adequacy_gate.py` |
| Release (irreversible, T3) | the truth compass must show no refuted claim and no unverified safety-critical claim; residual risk names a human (`accepted_by`) | `tools/where_we_stand.py --tier T3_IRREVERSIBLE` |

A gate that can be skipped quietly is not a gate. The hook can be bypassed with `--no-verify`, so CI
re-runs the same checks.

---

## 5. Do not build these (claimed, then falsified or unmeasured)

- **Kernel or hardware enforcement claims** (eBPF, TDX/SEV) for code that is scaffolding in Python.
  `ebpf/` and `hardware_attestation/` are structural scaffolding (AGENTS.md §5).
- **"Formally proven"** while Lean/TLC have never run: the repo's 10 `.lean` files are unchecked
  on this host, and `formal/tlaplus/TLC_OUTPUT.md` records what was and was not modelled.
- **Padding prompts to 64-token blocks to raise hosted cache hits.** No evidence was found; hosted
  APIs document exact-prefix matching (research note, summary-level only).
- **"Compaction" by truncating bytes.** A pasted KV-storage guard did this. Truncation is data loss.
- **Cross-host exactly-once.** The intent ledger is single-host; that limit is stated, not hidden.

---

## 6. Mentors to imitate, checked

### InterPro: independent signatures, curated integration (queried live 2026-10-28 with the `interpro-database` skill)

- InterPro has **54,922 entries**: 28,238 families, 21,768 domains, 3,516 homologous
  superfamilies, 779 conserved sites, 389 repeats, 133 active sites, 82 binding sites, 17 PTMs.
- It integrates signatures from **14 member databases**: Pfam, CATH-Gene3D, SUPERFAMILY, PANTHER,
  CDD, PROSITE profiles, SMART, NCBIfam, PROSITE patterns, PRINTS, HAMAP, PIRSF, SFLD, AntiFam.
  The list sometimes quoted with "TIGRFAMs" is out of date: TIGRFAMs is now part of NCBIfam.
- **Integration is curator review, not automatic voting.** Of 30,134 Pfam signatures, 29,136 are
  integrated into an InterPro entry and 998 are not. Unintegrated signatures still match proteins,
  but carry no curated InterPro entry.
- Example, APOE (UniProt P02649): Pfam PF01442 (domain) is integrated into IPR000074
  "Apolipoprotein A/E" (family). A separate PANTHER-derived family, IPR050163, also matches.

The lesson for this system: keep each source's raw signal with its provenance, and let a reviewed
step (here, a check plus a named approver) decide what becomes "integrated". The earlier summary
"InterPro classifies only when signatures agree" was wrong, and it is corrected here.

### Papers whose existence was checked on arXiv this session

| ID | Title (short) | What to take |
|---|---|---|
| 2609.29095 | Where Does Exactly-Once Live? (LIMBO) | Read-back alone cannot give exactly-once when late commits are possible; the target must fence |
| 2608.13900 | Agentic Transaction: Towards ACID-Compliant Agent Systems | Transactions for agents are already published. Do not claim to be first |
| 2610.14810 | KedgeFlow | The nearest competitor (control plane, signed grants). Cite it as prior art |
| 2610.05622 | UndoBench | An external benchmark to run against, instead of only private ones |
| 2608.09290 | OpenCodeReview (Alibaba) | Deterministic rules plus a diff-only reviewer beat self-review |
| 2605.15221 | Effective Harness Engineering for Algorithm Discovery | Fewer, deeper candidates; stronger models hack evaluators more often |
| 2610.31326 | AgenticEvolve | Persistent agents that run experiments between evaluations need fewer evaluations |

Prior-art note (research summary, 2026-10-27): the truth ledger combines existing ideas (Assurance 2.0
defeaters, in-toto/SLSA digest-bound attestations, dynamic re-checking). The possibly distinctive
part is narrow: only the tool can grant VERIFIED, by re-running tests against the current tree when
an irreversible action is requested.

### Engineering anchors (pages fetched 2026-10-28)

| Anchor | Source | What it means here |
|---|---|---|
| Jidoka: stop as soon as an abnormality is detected | https://global.toyota/en/company/vision-and-philosophy/production-system/ | A failing gate stops the pipeline; nobody "notes it and continues" |
| "Ask why five times" to reach the root cause | https://www.toyota-europe.com/about-us/toyota-quality | Section 3's "Why" column. Attribution to Taiichi Ohno's 1988 book was not opened, so it stays unverified |
| Activities should be idempotent, safe to execute multiple times | https://docs.temporal.io/activity-definition | Durable-execution engines protect their own state; the external side effect still needs a key the target honours (catch #5) |
| Same idempotency key with different parameters is an error; v1 keys may be pruned after 24 h | https://docs.stripe.com/api/idempotent_requests | Real targets bound key retention; a reconciler must not assume a key lives forever |
| SLSA v1.2 Build L1/L2/L3: provenance, then signed hosted provenance, then a hardened build | https://slsa.dev/spec/v1.2/build-track-basics | A shape for "who built what from which tree" receipts |
| Mutation testing surveys | Jia & Harman, IEEE TSE 37(5), 2011, doi:10.1109/TSE.2010.62; Papadakis et al., Advances in Computers, 2019, doi:10.1016/bs.adcom.2018.03.015 | Why the kill ratio is the adequacy meter, and why equivalent mutants must be handled (catch #7) |
| Blameless postmortems | https://sre.google/sre-book/postmortem-culture/ | How to write Section 3 rows: cause and fix, never blame |
| Agent-safety benchmarks from Chinese labs | arXiv 2412.14470 Agent-SafetyBench (Tsinghua); arXiv 2604.15774 MemEvoBench (mostly SJTU authors) | Agent memory drifts over time. Keep the ledger append-only and re-check evidence before acting |

---

## 7. Where the system stands today (measured 2026-10-28)

- `pytest tests/`: 3834 passed, 11 skipped, 0 failed (380 s, this host).
- `tools/run_all_verification_gates.py`: 18 of 18 gates exited 0. This is not a certification.
- `benchmarks/undobench_100_trial_effect_key.py` (synthetic payloads, in-memory target, not the
  official UndoBench harness): reworded-retry duplicates were 50/50 for naive retry, 50/50 for the
  full-payload latch, and 0/50 for the effect-key latch (Wilson 95% upper bound 7.14%), with 0
  wrongly blocked distinct intents.
- Open: lean/TLC never run; single-host ledger; no external reproduction; no git commit of this
  wave yet.

---

## 8. Letter (draft for the author to edit)

> What you are holding is less a codebase than a record of mistakes, written down so you do not pay
> for them twice. Some claims in this repo were once ahead of the evidence. The checks you inherit
> exist because of that.
>
> Three rules:
> 1. Build small pieces and seal each one with a test that would fail on a counterfeit.
> 2. The thing that wants an answer never scores the answer.
> 3. A refuted claim is progress. A hidden one is debt.
>
> Start with the compass. Build the brake before the engine.
