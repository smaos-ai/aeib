# Executive CISO & CRO Briefing Pack v2
## The MCP Trust-Gap Crisis & Execution-Integrity Defense (October 2026)

**Target Audience:** Chief Information Security Officers (CISOs), Chief Risk Officers (CROs), Heads of AI Governance, and Enterprise Security Architects.  
**Classification:** Technical Briefing & Architecture Defense  
**Reference Case:** Model Context Protocol (MCP) Trust Gaps & CVE-2026-14540 (Google MCP Toolbox SSRF)  
**Status:** LOCAL PASS; INDEPENDENT REPRODUCTION PENDING. Bounded synthetic benchmark and execution-evidence proposal with reported passing tests and a prior-art-adjusted claim set, prepared for independent reproduction.  

---

## 1. Executive Summary: The MCP Trust-Gap Crisis

On October 5, 2026, *Ars Technica* (Dan Goodin) reported on a systemic architectural vulnerability disclosed by independent security researcher Syed Anas Mohiuddin across enterprise deployments of the **Model Context Protocol (MCP)**. Implementations across major organizations—including Google's MCP Toolbox for Databases (CVE-2026-14540, CVSS 8.0), JPMorgan Chase, Weaviate, Rapid7, and government agencies—shared a common structural vulnerability: **downstream nodes implicitly trust instructions and parameters passed down from upstream agents.**

### The Core Failure Mode: Protocol Connectivity ≠ Execution Authority

MCP defines the wire mechanics for client-server tool communication, but deliberately delegates authorization and execution policy to implementers. When enterprise multi-agent workflows connect across MCP:

1. **Blind Downstream Trust:** Upstream agents pass tool instructions downstream. Specialized downstream execution nodes treat those instructions as authorized commands without independently re-verifying the root human authority.
2. **"Protocol Pivoting" & Indirect Prompt Injection:** An attacker who injects a prompt into an upstream reasoning agent can manipulate tool parameters passed to downstream nodes.
3. **Internal SSRF (CVE-2026-14540):** In Google's MCP Toolbox for Databases, an unconstrained HTTP client lacking restrictive redirect policies or target IP validation allowed coerced requests against internal network perimeters, exposing sensitive database instances.

> **The CISO Axiom:**  
> *"API gateways and prompt firewalls police what an agent is permitted to attempt ($T_0$). They cannot verify whether the executing tool maintains valid standing or whether parameters have drifted at the sub-second millisecond of wire dispatch ($T_{\text{dispatch}}$)."*

### Approved Industry Post Copy
> *"String for the human mind. Algorithmic strings for autonomous execution."*

---

## 2. Live Market Analysis & Competitive Landscape (October 2026)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              GLOBAL AGENT GOVERNANCE & RUNTIME SECURITY LANDSCAPE (OCT 2026)            │
├──────────────────────────┬──────────────────────────┬──────────────────────────────────┤
│ CATEGORY / SYSTEM        │ APPROACH & CAPABILITY    │ PUBLIC REVIEW GAP HYPOTHESIS     │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Pre-Execution Firewalls  │ Interposes on tool calls │ Stateless policy check; does not │
│ (AEGIS / arXiv:2603.12621│ with string scanning &   │ handle post-dispatch transport   │
│  & Open Agent Passport)  │ human review routing.    │ ambiguity (EFFECT_INDETERMINATE).│
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Behavioral Profilers     │ Parameterized DFA        │ Breaks on unstructured workflows;│
│ (Praetor Firewall)       │ tracking agent call      │ requires retraining on product   │
│                          │ trajectories.            │ changes; lacks target receipts.  │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Cryptographic Gateways   │ Signed decision receipts │ Pre-dispatch focus; does not     │
│ (JUTEQ / ScopeBlind /    │ using COSE/SCITT and JCS │ reconcile target-side execution  │
│  protect-mcp)            │ Ed25519 stdio proxies.   │ following HTTP 504 timeouts.     │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ AEIB v1.0 Core           │ 3-State Wire Interlock   │ Defines narrow wedge: T_n        │
│ (Target-Attested         │ (T_n Restraint, 504      │ restraint + 504 wire latching +  │
│  Execution Boundary)     │ latching, reconciliation)│ receiver refund attestation.     │
└──────────────────────────┴──────────────────────────┴──────────────────────────────────┘
```

### 3 Key Industry Trends & Review Gap Validation

1. **Shift from Prompt Wrappers to Pre-Execution Action Firewalls**: Enterprise security has recognized that text-filtering guardrails fail against multi-step tool execution. Modern platforms (AEGIS, Open Agent Passport, Certiv) enforce policy **at the tool invocation boundary before side effects occur**.
2. **The "Over-Privilege & Unchecked Tool-Call" Vulnerability**: Workstation AI agents execute an average of **42.8 tool calls per hour** through legitimate, system-signed binaries (`node`, `python3`, `zsh`), creating severe blindspots for traditional EDR, DLP, and CASB platforms.
3. **The Defensible Review Gap**:
   > **Defensible Gap Hypothesis**: Based on public materials reviewed on October 15, 2026, we did not find documented evidence that evaluated competitor platforms combine exact pre-dispatch parameter binding ($\text{CAID}$), durable dispatch intent logging ($\text{EO-1}$), post-dispatch transport-ambiguity handling (`EFFECT_INDETERMINATE`), and target-attested financial reconciliation (`refund_status_v1`). This represents a review gap in public materials, not proof that no competitor possesses these capabilities.

| Infrastructure Category | Representative Platforms | Exact Pre-Dispatch Action Binding (`CAID` / RFC 8785) | Durable Dispatch Intent (`EO-1` `fsync` Pre-Socket) | Post-Dispatch Transport Ambiguity Latching (`EFFECT_INDETERMINATE`) | Target-Attested Reconciliation (`refund_status_v1` Contract) | Documented Focus & Boundary Distinction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Pre-Execution Firewalls** | AEGIS (`arXiv:2603.12621`), Open Agent Passport | Evaluates tool call policies and string patterns | Stateless interception; no pre-socket log flush | Does not handle post-dispatch HTTP 504 / TCP RST ambiguity | No out-of-band target reconciliation contract | Focuses on pre-invocation policy checks and human approval routing. |
| **Behavioral Profilers** | Praetor Firewall | Tracks parameterized DFA call trajectories | No pre-socket durable intent journal | Breaks on unstructured workflows; no transport-ambiguity latch | Lacks cryptographic receiver-signed status receipts | Focuses on statistical trajectory anomaly detection; requires retraining on workflow shifts. |
| **Cryptographic Gateways** | JUTEQ, ScopeBlind, `protect-mcp` | Signs decision receipts using COSE/SCITT and JCS Ed25519 stdio proxies | Pre-dispatch decision logging | Does not latch or halt retries on post-dispatch HTTP 504 timeouts | Does not reconcile target-side state after wire drops | Focuses on pre-dispatch authorization signing over MCP stdio/HTTP transports. |
| **Durable Execution & Workflow Orchestration** | Temporal, Restate, DBOS | Configurable payload passing; general workflow state | Workflow history journaled; does not bind external socket creation directly | Activity failure triggers automated retry policies unless explicitly configured with custom non-retryable errors | Relies on custom developer-written activity compensation logic; no standard target evidence contract | Focuses on workflow completion across microservices; assumes downstream services handle idempotency keys. |
| **AEIB v1.0 Core** | AEIB Station 1–3 Boundary | **Enforced**: Deterministic RFC 8785 JCS canonical hash (`CAID`) validated at microsecond $T_n$ | **Enforced**: Signed `DISPATCH_INTENT` flushed to durable log before socket allocation | **Enforced**: Terminal latching on transport drop (`HTTP 504`, `TCP RST`); `retry_safe: false` | **Enforced**: Out-of-band `refund_status_v1` probe under strict `ProbeBudget: 1` before retry authorization | Delivers a specialized 3-state wire interlock ($T_n$ restraint + 504 latching + receiver refund attestation). |

---

## 3. The 11 Industry Signals vs. Bounded Design Intents

External technical and industry signals reflect emerging market needs and architectural design intents. In accordance with strict epistemic boundaries, AEIB does not claim these external developments validate or prove AEIB, nor does AEIB claim 1:1 functional equivalence. Instead, each signal maps to a bounded, verifiable design intent within the AEIB execution boundary:

| Signal ID & Domain | Observed Industry Signal | Source / Context | Bounded AEIB Design Intent & Concrete Mechanism | Epistemic Boundary & Verification Limit |
| :--- | :--- | :--- | :--- | :--- |
| **Signal 1: Security Fuzzing** | Algorithmic, non-LLM fuzzers discover critical bugs that probabilistic LLM scanners miss. | Bright Security (`STAR` Fuzzer) | Non-probabilistic parameter validation: Pre-dispatch parameters are validated against strict JSON schemas and RFC 8785 canonical hashes without LLM inference. | Evaluated across declared synthetic parameter sets; does not establish absence of unmodeled edge cases. |
| **Signal 2: Offline Edge Autonomy** | Local models run on edge devices, but workflows stall when cloud connectivity drops. Unmonitored internal agents risk silent drift. | METR & Edge Autonomy Report | Offline-capable verification under the stated browser and deployment constraints; out-of-band auditability without external network egress. | Verifier runs locally in Java 21, Python 3, or WASM; requires pre-distributed public keys. |
| **Signal 3: Deterministic Governance** | Contrast between probabilistic model uncertainty/hallucinations and deterministic evidence generation. | Elias Systems (High Precision Mode — HPM) | Deterministic execution boundary: Transforms probabilistic tool suggestions into strictly evaluated boolean standing predicates and Ed25519-signed receipts. | Bounded design intent; no claim of commercial alignment or 1:1 equivalence with Elias Systems. |
| **Signal 4: Agent Self-Evolution & Adaptation** | Autonomous self-improving agents adapt capabilities over iterations, risking unconstrained privilege expansion. | DeepMind (`Evo²` Framework) | Monotonic delegation attenuation (`AT39`): Subagent authority is bounded: $\text{Scope}_{\text{child}} \subseteq \text{Scope}_{\text{parent}}$. Upstream capability expansion cannot exceed root principal limits. | Tested on bounded multi-tier delegation scenarios; does not evaluate open-ended cognitive self-modification. |
| **Signal 5: Post-Quantum Cryptography** | PQC transitions (NIST FIPS 203/204/205) and hybrid signatures entering production protocols. | HAWK / NIST PQC Standards | Cryptographic architecture profile: Receipts currently use Ed25519; migration design status: `not_established` (Ed25519 test profile active; target PQC profile undetermined). | Cryptographic agility is architecturally planned in v1.1 research; no claim of immediate PQC deployment without test vectors. |
| **Signal 6: Multi-Agent Scientific Discovery** | Autonomous multi-agent swarms execute automated research workflows with high concurrency and tool mutation rates. | Sakana AI (Agentic Scientist) | Single-use ticket burning (`AT34`) and concurrency coalescing: Atomic single-use dispatch tokens prevent concurrent race conditions across parallel subagent branches. | Tested under local concurrency harnesses; uncoordinated distributed multi-cloud swarms require external consensus. |
| **Signal 7: Financial Digital Money & Assets** | Tokenized deposits, programmable settlement, and automated liquidity sweeps require cryptographic finality. | Oliver Wyman Digital Money Report | Target-attested financial reconciliation (`REC01`–`REC05`): Financial mutations require authenticated target receipts (`refund_status_v1`) before confirming state transitions. | Evaluates versioned target evidence schema; does not replace core banking ledger systems. |
| **Signal 8: Semantic Layer Drift Prevention** | Schema drift and semantic misalignment corrupt automated business intelligence and tool calling. | Modern Data 101 Semantic Framework | Content-addressed action identification ($\text{CAID}$): Binds tool parameters to SHA-256 digests over RFC 8785 JCS canonicalization. | Binding parameters to digests; semantic correctness of parameters is explicitly out of scope. |
| **Signal 9: Corporate Multi-Agent Simulation** | Enterprise-scale simulations of organizational agent interactions reveal cascading execution failures under transport stress. | MiniCorp Framework | 3-State wire latching (`AT35`): Transport drops (`HTTP 504`, `TCP RST`) latch the operation as `EFFECT_INDETERMINATE` with `retry_safe: false`. | Simulates behavior under defined transport scenarios; does not establish production equivalence across uncoordinated networks. |
| **Signal 10: OWASP Agentic Top 10** | Systemic vulnerabilities: prompt injection, insecure tool authorization, privilege escalation, unhandled wire ambiguity. | OWASP Top 10 for Agentic Applications | Integrated defense suite: `AT40`–`AT46` (boundary prompt injection immunity), `AT39` (delegation attenuation), `AT30`–`AT35` (pre-execution prevention). | Evaluated against declared synthetic attack vectors; not an exhaustive warranty against all attack classes. |
| **Signal 11: Durable Intent Journaling** | Requirement for pre-socket commitment logging to survive mid-execution process termination. | Enterprise Resilience Standards / EO-1 | Durable, append-oriented dispatch-intent journal with integrity protection and controlled retention (`EO-1`): Logs intent to disk before socket allocation. | Relies on local filesystem `fsync` integrity; does not provide multi-region replicated consensus. |

---

## 4. Calibrated Three-Tier Trust Hierarchy

To avoid overstating the epistemic authority of cryptographic receipts, AEIB classifies all generated evidence into three strictly separated tiers:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CALIBRATED THREE-TIER TRUST HIERARCHY                                         │
├─────────┬──────────────────────────┬──────────────────────────────────────────┬─────────────────────────────────┤
│ TIER    │ ATTESTATION LEVEL        │ WHAT IT PROVES                           │ WHAT IT DOES NOT PROVE          │
├─────────┼──────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────┤
│ Level 1 │ Agent-Signed             │ Proves an internal signer inside the     │ Does not establish that the     │
│         │                          │ agent runtime signed a log or action     │ signer key was uncompromised    │
│         │                          │ intent at timestamp T_0.                 │ or free from prompt injection.  │
├─────────┼──────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────┤
│ Level 2 │ Boundary-Signed          │ Proves a controlled boundary observed,   │ Does not by itself establish    │
│         │ (AEIB Station 1/3)       │ evaluated standing, or authorized a      │ target-side network execution   │
│         │                          │ dispatch.                                │ or downstream wire completion.  │
├─────────┼──────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────┤
│ Level 3 │ Target-Attested          │ Proves an authenticated target reported  │ Subject to target key custody,  │
│         │ (Receiver-Signed)        │ an operation-specific status under       │ API contract fidelity, and      │
│         │                          │ contract (refund_status_v1).             │ implementation trust model.     │
└─────────┴──────────────────────────┴──────────────────────────────────────────┴─────────────────────────────────┘
```

- **Level 1 (Agent-Signed)**: Proves an internal signer inside the agent runtime signed a record. Does not establish that the signer was uncompromised.
- **Level 2 (Boundary-Signed)**: Proves a controlled boundary observed or authorized a dispatch (e.g., AEIB Station 1/3 receipts). Does not by itself establish target-side effect.
- **Level 3 (Target-Attested / Receiver-Attested)**: Proves an authenticated target reported an operation-specific status under a versioned evidence contract (`refund_status_v1`). Subject to the target's key custody, API contract, and implementation trust model.

---

## 5. AEIB v1.0 Core Architecture: The Execution-Integrity Decision Boundary

AEIB sits directly at the wire boundary beneath agent reasoning engines and MCP transport handoffs. Grounded in the principle that **"Permissions are time-indexed claims; execution requires current standing plus effect evidence"** ($\text{Capability} \neq \text{Authority} \neq \text{Standing} \neq \text{Execution}$), AEIB intercepts unauthorized actions before consequence binds.

```text
                               ┌──────────────────────────┐
                               │  AGENCY / MODEL PLANE    │
                               │  LLM / Swarm Reasoning   │
                               └────────────┬─────────────┘
                                            │ Proposed Tool Call (JSON-RPC)
                                            ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │ STATION 0–1: PRE-DISPATCH RESTRAINT GATE (Tn Microsecond Interlock)                │
 │ • Validates Pinned MCP Protocol Version (2025-06-18)                               │
 │ • Computes Canonical Action Digest: CAID = SHA-256(JCS(parsed_params))             │
 │ • Checks Standing Predicate (GrantValid ∧ EpochFresh ∧ CAIDMatch ∧ TicketUnburned) │
 └──────────────────────────┬──────────────────────────────────────┬───────────────────┘
                            │                                      │
               VERDICT: DENIED (AT30–AT35)             VERDICT: ALLOWED
                            │                                      │
                            ▼                                      ▼
    ┌───────────────────────────────┐           ┌─────────────────────────────────────┐
    │ PRE-EXECUTION RESTRAINT RECORD│           │ STATION 2–3: SOCKET DISPATCH        │
    │ • socket_connect_invoked: false│          │ • Emits DISPATCH_INTENT (EO-1)      │
    │ • external_bytes: 0           │           │ • Single-use ticket burned          │
    │ • Level 2 Boundary Signed     │           └──────────────────┬──────────────────┘
    └───────────────────────────────┘                              │
                                                                   ▼
                                                ┌─────────────────────────────────────┐
                                                │ WIRE TRANSPORT (External Gateway)   │
                                                └──────────────────┬──────────────────┘
                                                                   │
                                                ┌──────────────────┴──────────────────┐
                                                │                                     │
                                         HTTP 200 OK                           HTTP 504 Timeout
                                                │                                     │
                                                ▼                                     ▼
                                ┌──────────────────────────────┐     ┌────────────────────────────────┐
                                │ LEVEL 3 TARGET RECONCILIATION│     │ 3-STATE WIRE LATCHING          │
                                │ • refund_status_v1 contract  │     │ • EFFECT_INDETERMINATE         │
                                │ • Receiver Ed25519 signature │     │ • retry_safe: false            │
                                │ • Pinned key trust anchor    │     │ • Automated retries frozen     │
                                └──────────────────────────────┘     │ • Out-of-band probe scheduled  │
                                                                     └────────────────────────────────┘
```

### The 7 Core Architectural Controls:
- **`CTRL-01` (Admissibility & Schema Pinning)**: Rejects malformed payloads or unapproved tools before evaluation (`AT30`).
- **`CTRL-02` (Temporal Standing Verification)**: Evaluates delegation grants and policy epochs at microsecond $T_n$ (`AT31`).
- **`CTRL-03` (Persistent Single-Use Authority)**: Atomically burns single-use authorization tickets prior to socket write (`AT34`).
- **`CTRL-04` (Governed HTTP/MCP Executor)**: Enforces pinned MCP version (`2025-06-18`) and exact $\text{CAID}$ wire binding (`MCP01`).
- **`CTRL-05` (Uncertain-Outcome Latching)**: Latches `HTTP 504` / `TCP RST` faults as `EFFECT_INDETERMINATE` with `retry_safe: false` (`AT35`).
- **`CTRL-06` (Bounded Target Reconciliation)**: Queries target state under strict `ProbeBudget: 1` using `refund_status_v1` (`REC01`).
- **`CTRL-07` (Operation-Bound Receipt & Verifier)**: Mints RFC 8785 canonical receipts signed with Ed25519, verified offline.

---

## 6. Regulatory & Auditor Crosswalk: DORA & EU AI Act Scope Bounds

AEIB produces structured, offline-verifiable execution telemetry supporting enterprise audit and governance workflows.

### Bounded Scope Envelope: What AEIB Provides vs. What AEIB Does NOT Do

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       BOUNDED REGULATORY CAPABILITY & SCOPE ENVELOPE                            │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│ REGULATORY REGIME             │ WHAT AEIB PROVIDES              │ WHAT AEIB DOES NOT DO         │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ DORA (Regulation (EU)         │ • Microsecond pre-dispatch      │ • Does NOT maintain entity-   │
│ 2022/2554)                    │   intent persistence and receipt│   level Register of Info.     │
│ Articles 17 & 28              │   chains (EO-1).                │ • Does NOT conduct supplier   │
│                               │ • Cryptographic transport traces│   due diligence or audits.    │
│                               │   supporting incident timelines.│                               │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ EU AI Act (Regulation (EU)    │ • Article 12 event logging with │ • Does NOT warrant system-wide│
│ 2024/1689)                    │   RFC 8785 canonical hashes.    │   conformity with Art. 15.    │
│ Articles 12, 14, 15, 43       │ • Article 14 deterministic stop │ • Does NOT automate legal     │
│                               │   and stage-dependent halt.     │   filings or dictate Art. 43  │
│                               │ • Pre-execution restraint logs. │   conformity routes.          │
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

- **EN 18286:2026 Scope Boundary**: Commission Implementing Decision (EU) 2026/2274 establishes a presumption of conformity strictly for Article 17 QMS lifecycle processes. It does not certify Layer 7 payload binding or wire proxy correctness. AEIB supplies un-tamperable runtime inputs that feed into the deployer's QMS repository.
- **Regime Isolation**: EU AI Act Article 73 (15-day serious incident reporting) and DORA Article 17 (4-hour major ICT incident notification) are maintained as parallel, un-conflated reporting pathways.

---

## 7. The Three Commercial Pilot Patterns

AEIB is packaged for production pilot validation across financial and regulated enterprises using three non-disruptive deployment patterns:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THREE COMMERCIAL PILOT PATTERNS                                 │
├──────────────────────────┬────────────────────────────────────┬─────────────────────────────────┤
│ PILOT PATTERN            │ OPERATIONAL MECHANISM              │ PRIMARY VALUE ARTIFACT          │
├──────────────────────────┼────────────────────────────────────┼─────────────────────────────────┤
│ Pattern A: 6-Week        │ Week 1: Scope high-risk actions.   │ Comparative baseline telemetry; │
│ Observe-Then-Enforce     │ Week 2: Shadow Mode evaluation.    │ hypothetical block reports      │
│ Pilot                    │ Week 3: Enforce deny-by-default.   │ prior to live enforcement lock. │
│                          │ Weeks 4–6: Reconcile & handover.   │                                 │
├──────────────────────────┼────────────────────────────────────┼─────────────────────────────────┤
│ Pattern B: Pre-Execution │ Formal designation for denial      │ Level 2 Boundary-Signed denial  │
│ Restraint Records        │ outputs (AT30–AT37) prior to       │ receipts proving 0 egress bytes │
│                          │ socket allocation.                 │ on out-of-policy mutations.     │
├──────────────────────────┼────────────────────────────────────┼─────────────────────────────────┤
│ Pattern C: Target-       │ First-class integration contract   │ Level 3 Target-Attested status  │
│ Attested Reconciliation  │ binding operation, amount,         │ bundles resolving HTTP 504      │
│ (refund_status_v1)       │ currency, and status under pinned  │ timeouts without blind retries. │
│                          │ receiver keys.                     │                                 │
└──────────────────────────┴────────────────────────────────────┴─────────────────────────────────┘
```

### 7.1 Pattern A: 6-Week Observe-Then-Enforce Pilot
1. **Week 1 (Scoping)**: Scope a single high-risk consequential action class (e.g., `refund_customer` or `disburse_payout`), pin the MCP protocol version (`2025-06-18`), and define canonical action digest ($\text{CAID}$) schemas.
2. **Week 2 (Shadow Mode)**: Deploy AEIB in passive observation mode.  
   *Explicit Constraint:* Shadow mode measures decisions and hypothetical blocks (`WOULD_BLOCK`) without preventing live execution.
3. **Week 3 (Enforce Deny-by-Default)**: Flip Station 0–1 to active fail-closed enforcement on the targeted action class, arresting stale epochs, expired grants, and parameter tampering prior to socket creation.
4. **Weeks 4–6 (Target Reconciliation, Fault Testing & Evidence Handover)**: Wire the authenticated `contracts/refund_status_v1.schema.json` target endpoint, execute controlled 504 / TCP reset fault injection, and hand over the offline-verifiable compliance evidence pack.

### 7.2 Pattern B: Pre-Execution Restraint Records
Formal designation for boundary denial outputs (`AT30`–`AT37`, `AT40`–`AT46`) proving zero egress bytes:
1. **Zero External I/O**: The transport interceptor records `socket_connect_invoked: false` and `external_bytes: 0`.
2. **Level 2 Boundary-Signed Receipt**: AEIB mints a tamper-evident pre-execution restraint record binding the rejected candidate action $\text{CAID}$, principal, active policy epoch, and rejection code under an Ed25519 signature.

### 7.3 Pattern C: Target-Attested Reconciliation (`refund_status_v1`)
First-class integration contract requiring operation, amount, currency, and status binding under pinned receiver keys:
1. **Automated Latching**: Post-dispatch `HTTP 504` / `TCP RST` faults latch the operation as `EFFECT_INDETERMINATE` with `retry_safe: false`.
2. **Level 3 Receiver Attestation**: Out-of-band reconciliation queries the target status endpoint under `ProbeBudget: 1`, requiring a valid receiver Ed25519 signature over the canonical `refund_status_v1` payload before transitioning to `RESOLVED_CONFIRMED` or `RESOLVED_REFUTED`.

---

## 8. Reproducible CISO Verification Walkthrough

Enterprise security teams can independently reproduce the test suite and verify evidence offline:

```bash
# 1. Zone Boundary Architecture Enforcement
python3 compliance/check_zone_boundary.py

# 2. Execute AST purity & zero-mock compliance check
python3 compliance/ast_purity.py . && python3 compliance/no_mock_enforcer.py

# 3. Core Logic & Industrial Protection Tests
pytest tests/test_industrial_protection_matrix.py \
       tests/test_ansi_50bf_breaker_failure.py \
       tests/test_saga_compensation.py \
       tests/test_falsifiability_matrix.py -v

# 4. Phase 1 Pre-Execution Prevention Tests & Verifier
pytest tests/test_temporal_standing_check.py -k AT31_STALE_EPOCH_BLOCKED -v -s
python3 tools/verify_pre_execution_evidence.py \
  --bundle artifacts/pre_execution/AT31_pre_execution_evidence.json

# 5. Phase 2 Enforced Halt & Delegation Tests & Verifier
pytest tests/test_enforced_halt_and_delegation.py -v
python3 tools/verify_phase2_evidence.py --all --check-jcs-conformance

# 6. Phase 3 Boundary Injection & Operational Runbooks & Verifier
pytest tests/test_boundary_prompt_injection.py \
       tests/test_operational_runbooks.py -v
python3 tools/verify_phase3_evidence.py --all --check-jcs-conformance

# 7. Run deterministic 500-episode harness (seed 42)
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
```

---

## 9. Contact & Technical Dossier Access

* **Author:** Andrej Leukhin  
* **Affiliation:** SovereignNexus  
* **ORCID:** `0009-0004-9543-8263`  
* **Email:** `andrejlo123@gmail.com`  
* **Distribution Archive:** `dist/aeib-pilot-evidence-pack-v1.1.0-rc.1.tar.gz` (61 assets, SHA-256: `8010236a2275d2a8143214f69be097b55f5c5af114d0fdf5cfce01631a53bda9`)  
* **WASM Offline Verifier:** `dist/smaos_verify.wasm` (199,770 bytes) | `dist/verifier.html`
