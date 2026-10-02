# 🛡️ SovereignNexus / SMAOS: Air-Gapped AI Agent Wire-Truth Engine (`v0.2.4`)

> **Deterministic boundary integrity, transport fault trapping, and ambiguity resolution for autonomous AI agent workflows.**
>
> Existing work defines deterministic action identity, signed execution receipts, unknown-effect states, and reconciliation architectures. AEIB contributes a concrete, versioned transport-to-disposition mapping contract, an explicit disposition-to-retry-policy vocabulary, and an offline verifier that checks whether the declared mapping was applied. The implementation is evaluated under a declared local fault model and is intended to interoperate with, but does not claim conformance to, emerging execution-boundary and action-receipt drafts.

[![Release](https://img.shields.io/badge/release-v0.2.4-blue.svg)](https://github.com/sovreignnexus/smaos/releases/tag/v0.2.4)
[![Evidence](https://img.shields.io/badge/evidence-multi--env%20verified-success.svg)](docs/EVIDENCE.md)
[![Rust Tests](https://img.shields.io/badge/rust%20tests-22%20passed-green.svg)](https://github.com/smaos-ai/star-protocol)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Egress](https://img.shields.io/badge/egress-0%20bytes%20(air--gapped)-success.svg)](#privacy--zero-egress-invariant)

---

## 🏛️ Core Technical Documentation

| Document | Purpose | Key Contents |
| :--- | :--- | :--- |
| **[`ARCHITECTURE.md`](ARCHITECTURE.md)** | Systems Architecture & Specification | 6-stage lifecycle, wire trap, state prober, and DeepSeek/Qwen integration. |
| **[`OPERATIONS.md`](OPERATIONS.md)** | Deployment Runbook | Docker configurations, PostgreSQL connection pooling, health checks, troubleshooting. |
| **[`docs/EVIDENCE.md`](docs/EVIDENCE.md)** | Empirical Evidence & Benchmarks | Multi-env matrix (PG15/PG16), 10,000-op soak data, third-party framework comparison. |
| **[`LIMITATIONS.md`](LIMITATIONS.md)** | Epistemic Scope & Boundaries | Normative calibrations, statistical bounds (Rule of Three), non-claims. |
| **[`claims.json`](claims.json)** | Machine-Readable Claims Register | Formal assertions C1–C5 mapped directly to execution evidence. |

---

## 🚨 The Problem: The "Omniscience Trap" & Speculative Retries

When an autonomous payment or cloud agent dispatches a mutating tool call and the remote network drops with an **HTTP 504 Gateway Timeout** or **TCP RST**:
1. Standard agent frameworks (LangChain, AutoGen, CrewAI, native OpenAI Tool Calling) catch the transport exception and pass the error text back to the LLM prompt.
2. The LLM interprets the timeout as a failed call and executes a **speculative retry**.
3. **The Disaster:** If the remote server committed the write before the socket dropped, the speculative retry produces a **duplicate debit, double-provisioning, or ledger divergence**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FRAMEWORK COMPARISON: €400 MUTATING DEBIT                       │
├───────────────────────────────────┬────────────────────────────────────────────────────┤
│  UNPROTECTED FRAMEWORK            │  AEIB PROTECTED SUBSTRATE                          │
│  (LangChain / AutoGen / CrewAI)   │  (SMAOS Deterministic Wire Gate)                   │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 1. Agent dispatches €400 debit    │ 1. Agent dispatches €400 debit with UUIDv5 key     │
│ 2. DB commits; Balance = €600     │ 2. DB commits; Balance = €600                      │
│ 3. Network drops with HTTP 504    │ 3. Network drops with HTTP 504                     │
│ 4. Framework catches 504, prompts │ 4. Wire trap intercepts 504; halts execution       │
│    LLM: "Request timed out, retry"│ 5. Executes OOB probe against authoritative DB     │
│ 5. LLM blindly re-dispatches debit│ 6. Probe confirms commit; blocks duplicate retry   │
│ 6. DUPLICATE DEBIT COMMITTED!     │ 7. Receipt emitted with disposition: CONFIRMED     │
│                                   │                                                    │
│ Final Balance: €200.00            │ Final Balance: €600.00                             │
│ Duplicate Debits: 1               │ Duplicate Debits: 0                                │
│ Financial Loss: €400.00           │ Financial Loss: €0.00                              │
│ Verdict: DUPLICATE_MUTATION_FAIL  │ Verdict: FAIL_CLOSED_INVARIANT_PRESERVED           │
└───────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## ⚡ 60-Second Quickstart (100% Local / Air-Gapped)

### Option 1: Native Rust Engine (Star Protocol / DORA Kit)
```bash
git clone https://github.com/smaos-ai/star-protocol.git
cd star-protocol
cargo test
```
*Executes 22 native Rust tests (17 unit + 5 integration) in ~0.01 seconds.*

### Option 2: Production Benchmark & Soak Test
```bash
git clone https://github.com/smaos-ai/smaos-ai-sandbox.git
cd smaos-ai-sandbox
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 benchmarks/multi_env_matrix/run_production_benchmarks.py
```
*Generates multi-environment evidence across PostgreSQL 15 & 16 Docker containers and executes a 10,000-operation soak test.*

### Option 3: Air-Gapped Docker Container
```bash
docker compose up
```
*Navigates to local dashboard at `http://127.0.0.1:8765`.*

---

## 🛡️ Core Engineering Invariants

1. **RFC 8785 (JCS) Deterministic Canonicalization:** Payloads are serialized using the strict JSON Canonicalization Scheme before digest calculation.
2. **UUIDv5 Idempotency Keys:** Deterministically derived from the canonical payload digest and action identity under RFC 4122.
3. **In-Process Wire Trap:** Catches HTTP 504, 502, 503, and TCP RST at the socket layer, quarantining unconfirmed transitions into `DISPATCHED_UNCONFIRMED`.
4. **Out-of-Band State Reconciliation:** Enforces the fundamental invariant:
   $$\mathbf{authorized\ write} \neq \mathbf{persisted\ write} \neq \mathbf{correct\ outcome}$$
   Authoritative downstream state probes (`PostgresProbeAdapter`, `DatabaseStateProber`) verify physical row persistence before any retry is authorized.
5. **RFC 9052 COSE_Sign1 SCITT Receipts:** Outcomes are cryptographically sealed using Ed25519 asymmetric signatures, verifiable offline with zero network egress.

---

## ⚠️ Operational Limits & Epistemic Boundaries

1. **Local Harness Evaluation:** Evidence is gathered under a declared local fault injection harness. It does not replace institutional integration testing.
2. **Statistical Upper Bound:** Under the **Rule of Three** for zero observed events ($3/N$), 0/50 empirical trials establish a **95% confidence upper bound of 5.8%** on the failure rate.
3. **No Statutory Certification:** This software produces structured technical audit trails. It does not constitute formal statutory compliance certification under DORA (Regulation (EU) 2022/2554) or the EU AI Act without formal supervisory review.
4. **Prior Art Recognition:** Credits foundational research and IETF drafts including `draft-zambo-aer1-04`, `draft-schrock-action-evidence-boundary-07`, and `draft-mih-scitt-agent-action-capsule-05`.

---

## 📜 License & Author

Apache License 2.0. Developed by **Andrii Leukhin** (Independent Researcher & Founder, SovereignNexus project, ORCID: [`0009-0004-9543-8263`](https://orcid.org/0009-0004-9543-8263), `andrejlo123@gmail.com`).  
*Note: SovereignNexus is an independent research initiative (incorporation pending in the Czech Republic).*
