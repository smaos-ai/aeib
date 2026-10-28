# ⚡ AEIB Enterprise v1.0 — Quick Start Reviewer Guide

> **Release Statement:**  
> AEIB Enterprise v1.0 is a review distribution containing the v0.2.4 verified core and experimental enterprise extensions. The verified core has passed its documented structural, negative-vector, PostgreSQL, and SQLite tests. The included soak command is currently smoke validation; extended endurance, multi-tenant security, broad framework interoperability, independent reproduction, production deployment, and regulatory assessment remain pending.

---

## 🏛️ Scope, Versioning & Epistemic Boundaries

* **Core Engine (`v0.2.4` Baseline):** Empirically verified core including zero-mock AST purity, PostgreSQL 16 connection pooling with 3000ms statement timeout trapping, 6-gate negative vector fail-closed suite, and the RFC 8785 canonical mapping contract.
* **Review Distribution Label (`v1.0`):** Packaging and evaluation distribution assembling the verified core alongside experimental extensions. Phase 2 does not inherit the v0.2.4 evidence automatically.
* **Phase 2 Status:** Marked explicitly as:
  - Experimental.
  - Reference implementation.
  - Not production-validated.
  - Not independently reproduced.
  - Not a compliance certification.

---

## 🌐 Architectural Positioning: Temporal & LangGraph

* **Temporal.io:** Operates on an event-sourced durable execution model providing deterministic workflow replay, state persistence, and activity retries. While application-level idempotency is a standard best practice in Temporal design patterns, idempotency is not natively enforced at the HTTP/action transport boundary by the orchestration engine itself. AEIB is designed as a complementary downstream wire trap and out-of-band state reconciler for post-commit 504 drops, not as a replacement for Temporal.
* **LangGraph:** Operates as a graph-based agent orchestration runtime managing cyclical state machines, human-in-the-loop approvals, and checkpointed memory transitions. The reviewed AEIB scenario evaluates a post-dispatch disposition contract not included in the examined LangGraph integration.
* **Framing:** AEIB acts as an in-process, post-dispatch wire-reconciliation layer operating alongside these runtimes rather than competing with them.

---

## 🎯 Enterprise Wedge: Palantir AIP Abstractions & Deterministic Staging Sandbox

AEIB provides an agile, plug-and-play alternative to monolithic enterprise stacks (such as Palantir AIP) by formalizing three core enterprise primitives:

1. **Nouns & Verbs**: MCP tools decompose into target business entities (`Noun`) and action primitives (`Verb`), deriving action identity via:
   $$\text{CAID} = H(\text{Noun}_{\text{EntityID}} \parallel \text{Verb}_{\text{Action}} \parallel \text{JCS}(\text{Payload}))$$
2. **The Deterministic Staging Sandbox**: The outbox states `DISPATCHED_UNCONFIRMED` and `RECONCILIATION_CONFLICT` operate as a cryptographically sealed staging sandbox. High-stakes mutations remain staged and frozen until OOB probe reconciliation or Human-in-the-Loop (HITL) authorization unlocks them.
3. **Purpose-Driven Identity**: OpenTelemetry spans and SCITT receipts carry tamper-evident `tenant_id`, `principal_did`, and `purpose_marking` metadata for strict tenant boundary enforcement.

---

## 🚀 Reviewer Verification Run (< 10 Seconds)

Execute the three standard verification commands from the package root:

```bash
# 1. Structural AST purity & SHA-256 manifest check
python compliance/verify-audit-pack.py

# 2. Negative vector security suite (6 fail-closed gates)
pytest benchmarks/test_negative_vectors.py -v

# 3. Long-haul harness smoke validation
python benchmarks/soak_test_long_haul.py --smoke
```

---

## 🧪 Long-Haul Harness Smoke Validation

> **Important Qualification:**  
> The included soak test command (`--smoke`) is a **smoke validation** of the harness infrastructure, memory tracking, and fault traps—not long-haul soak evidence:
> - **Duration:** `0.0s` (rapid smoke run)
> - **Operations:** `50`
> - **Injected Faults:** `12`
> 
> Genuine "long-haul soak evidence" is strictly reserved for multi-hour or multi-day endurance runs (`--mode=endurance`) with persistent time-series logs and continuous resource telemetry.

---

## 📂 Scoped Repository Layout

```text
aeib-enterprise-v1.0/
├── QUICK_START_REVIEW.md               # 1-page reviewer reproduction guide
├── README.md                           # Two-phase architecture & positioning overview
├── ZERO_MOCK_POLICY.md                 # AST-enforced prohibition of unittest.mock
├── QUALITY_GATE_ARCHITECTURE.md        # TPS Jidoka / Poka-Yoke specification
├── transport-to-disposition-mapping.yaml # Core v0.2.4 YAML Mapping Contract
├── aeib_mcp_proxy.py                   # [Phase 2] Stdio MCP JSON-RPC proxy
├── aeib_postgresql_probe/
│   └── adapter.py                      # Live PostgreSQL 16 OOB state prober
├── benchmarks/
│   ├── test_negative_vectors.py        # 6-gate fail-closed security suite
│   ├── soak_test_smoke.py              # Smoke test for soak harness health
│   └── soak_test_long_haul.py          # [Phase 2] Long-haul stability daemon
├── telemetry/
│   ├── observability.py                # [Phase 2] OTel gen_ai.invoke_agent tracer
│   ├── aeib_grafana_dashboard.json     # [Phase 2] Grafana dashboard definition
│   └── soak_telemetry.csv              # Time-series telemetry output
├── compliance/
│   ├── claims.json                     # Epistemic bounds & statistical limits
│   ├── verify-audit-pack.py            # AST purity & SHA-256 manifest verifier
│   └── aeib_manifest.json              # SHA-256 digest index (LOCKED)
└── .github/workflows/
    └── matrix-ci.yml                   # Ubuntu + macOS x Python 3.12–3.14 CI
```
