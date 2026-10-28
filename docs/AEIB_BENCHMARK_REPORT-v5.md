# Agent Effect Integrity Benchmark (AEIB) — Technical Report v5
## Operational Integration Contract, Prior-Art Alignment, and Execution Evidence

**Document Version:** 5.0 (October 2026)  
**Classification:** Scientific Benchmark Report & Execution-Evidence Proposal  
**Author:** SovereignNexus Architecture Team  
**Focus:** Consequence Integrity (Layer 5), Identity Triad Binding, Track B Web-Mutation Finality, GIRAI 2026 Governance Bridge  
**Status:** AEIB v0.4.0 is a bounded synthetic benchmark and execution-evidence proposal, with reported passing tests and a prior-art-adjusted claim set, prepared for independent reproduction.  
**Distribution Archive:** `dist/aeib-v0.4.0-cleanroom.tar.gz`  
**Offline Verifier:** `dist/smaos_verify.wasm` (199,770 bytes)  
**Licenses:** Apache-2.0 (Software / Harness) | CC-BY-4.0 (Specifications & Documentation)  

> [!IMPORTANT]
> **Regulatory & Evaluative Scope Boundary:**  
> SMAOS and the AEIB benchmark suite are designed to generate verifiable telemetry and execution evidence that may support an organization’s internal control assessment. AEIB does not certify compliance with ISO/IEC 42001/42006, EU DORA (Regulation (EU) 2022/2554), EU AI Act (Regulation (EU) 2024/1689), US NIST AI RMF 1.0, or Chinese national standards (GB 45438-2025). ISO/IEC 42006 governs accreditation bodies, not software log formats. All standards mappings in this report represent illustrative control-objective crosswalks, not legal advice or official conformity assessments.  
> Under the declared synthetic Track B scenarios, the harness matched gateway dispositions to an independent target-side ledger and issued no speculative retry in the tested ambiguous cases (11/11 reported synthetic scenarios matched the declared oracle). The package does not establish universal exactly-once execution across arbitrary distributed networks, complete prompt-injection prevention, or real-world absence of duplicate remote effects outside the tested environment.

---

## 1. Executive Synthesis & Core Positioning

### 1.1 Final Approved Positioning

> **"AEIB is a vendor-neutral execution-evidence integration layer for state-changing agent actions. It binds a unique operation to an exact request, records transport ambiguity as a typed disposition, removes retry authority until reconciliation, and preserves evidence for separately authorized review and release."**

AEIB does **not** claim to have invented "exactly-once agent execution" or duplicate-side-effect benchmarking. Nor is AEIB a "technical standard" for AI governance. Instead, **AEIB proposes a portable effect-disposition and retry-authority contract for high-risk agent actions.**

The defensible technical contribution is an **operational integration contract**:

```text
unique operation binding (operation_id, request_digest, business_key)
        ↓
pre-dispatch standing evaluation (fail-closed check at T_dispatch)
        ↓
transport observation (capture Layer 7 / wire faults)
        ↓
typed indeterminate disposition (EFFECT_INDETERMINATE)
        ↓
retry authority removed (retry_safe: false lock)
        ↓
reconciliation claim (single-flight out-of-band target probe)
        ↓
raw evidence retained (RFC 8785 canonical hash & audit ledger)
        ↓
release separately authorized (decoupled audit release gate)
        ↓
OTel / SCITT / SIEM / DORA evidence projection
```

### 1.2 The Macro-to-Micro Governance Gap (GIRAI 2026 Bridge)

The 2026 Global Index on Responsible AI (GIRAI) findings and Tim Zlomke’s critique expose the systemic vulnerability of first-generation AI governance: **institutions treat authorization as a static, one-time event rather than a continuous, millisecond-level execution condition.**

```text
MACRO GOVERNANCE (GIRAI 2026)                MICRO EXECUTION (AEIB v0.4.0)
• 58% have transparency frameworks           • Static GRC approves Capability at T0
• Only 18% require public disclosures         • Standing decays mid-flight via network/policy drift
• Public sector AI lowest-scoring domain      • AEIB validates Standing at Tn (the millisecond of dispatch)
  └── "Adoption outpaces self-constraint"        └── "Fail-closed enforcement at the wire boundary"
```

While 58% of surveyed jurisdictions maintain high-level AI transparency frameworks, only 18% enforce binding public disclosure or runtime auditability. Across enterprise and government deployments, **adoption has outpaced the capacity for self-constraint**. High-level governance, GRC portals, and OAuth token issuance operate on human time scales (weeks, months, or session lifetimes), whereas consequential autonomous tool dispatches execute across sub-second TCP sockets where network faults silently decouple agent intent from external reality.

### 1.3 The Operational Axiom: Standing vs. Consequence

AEIB formalizes Zlomke's "time problem" of AI governance into a mathematical axiom evaluated at every consequential mutation boundary:

$$\text{Capability} \neq \text{Authority} \neq \text{Standing} \neq \text{Execution}$$

1. **Procurement & Identity Grant Static Capability ($T_0$):**  
   An active OAuth token, IAM role, or approved model catalog entry merely establishes that an agent was granted access to an API in the past. It does not evaluate whether the specific action remains valid at the moment of execution.
2. **Real-Time Network & Policy Realities Decay Standing ($T_n$):**  
   Between candidate action formulation and wire dispatch, network drops occur (`HTTP 504`, `TCP RST`), grants expire, tenant keys rotate, or policy epochs roll over. This introduces the **Time-of-Check to Time-of-Use (TOCTOU) Standing Race** (empirically evaluated in scenario **AT23**).
3. **AEIB Enforces Millisecond Self-Constraint ($T_{\text{dispatch}}$):**  
   Operating inline as the **Execution-Integrity Boundary**, the AEIB Gateway Adapter evaluates current standing at the exact millisecond of dispatch:
   * **Candidate Action Binding:** Pins request arguments via RFC 8785 JSON Canonicalization Scheme (JCS) payload hashing ($H(\text{JCS}(\text{Payload}))$, evaluated in **AT24**).
   * **Pre-Dispatch Gate:** Halts dispatch fail-closed if standing, policy epoch, or control health has degraded.
   * **Uncertainty Latching:** On wire-fault disconnects, freezes action state at `EFFECT_INDETERMINATE`, locks `retry_safe: false`, and suppresses speculative retry storms.

---

## 2. Prior-Art Integration & Comparative Metrology

### 2.1 The LIMBO Benchmark (arXiv:2609.29095) as Primary Prior Art

The central problem of duplicate side effects under agent transport faults is thoroughly established in prior art, most notably by **Li (2026), *"Where Does Exactly-Once Live? Model, Harness, and Tool-Contract Effects on Duplicate Side Effects in LLM Agents"*** ([arXiv:2609.29095](https://arxiv.org/abs/2609.29095)).

LIMBO provides an extensive empirical evaluation across:
* **6 services**, **12 fault modes**, **25,930 episodes**, and **9 frontier models**.
* Demonstrates duplicate rates of ~0.5% when read-backs can resolve outcomes, but **56%–74%** during in-flight network drop windows.
* Demonstrates that idempotency keys reduce duplicate rates substantially (from 28% to 4%), while highlighting that harness-level and tool-contract interactions dominate overall safety.

Consequently, `aeib-bench` does not claim novelty for duplicate-side-effect benchmarking. Instead:

> **"`aeib-bench` is a typed disposition and evidence-gating extension for duplicate-side-effect evaluations."**

### 2.2 Comprehensive Prior-Art Comparison Table

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   PRIOR-ART AND CONTRIBUTION MAPPING                                   │
├──────────────────────────┬───────────────────────────────┬─────────────────────────────────────────────┤
│ CLAIMED DOMAIN           │ CLOSEST PRIOR ART             │ AEIB CONTRIBUTION & DISTINCTION             │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────────────────────┤
│ Duplicate-Side-Effect    │ LIMBO (arXiv:2609.29095);     │ Typed effect disposition and retry-         │
│ Benchmarking             │ τ-bench; AgentDojo            │ authority evidence contract; focus on       │
│                          │                               │ control-plane latching & probe coalescing.  │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────────────────────┤
│ Idempotency Semantics    │ RFC 9110 §9.2.2; Stripe;      │ Explicit triad binding: unique operation_id │
│                          │ AWS Builders' Library; Adyen  │ ≠ request_digest ≠ provider idempotency key;│
│                          │                               │ hard interlock at agent execution boundary. │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────────────────────┤
│ Cryptographic Receipts   │ IETF SCITT (RFC 9943);        │ Implementation profile using Ed25519/JCS;   │
│ & Attestation            │ COSE_Sign1 (RFC 9052)         │ binds AEIB disposition lifecycle into       │
│                          │                               │ offline-verifiable audit journals.          │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────────────────────┤
│ Human-in-the-Loop        │ MCP Tools HITL spec;          │ Enforces access to primary raw evidence;    │
│ Review Gate              │ LangGraph Interrupts          │ motivated by arXiv:2609.28820 (AI summary   │
│                          │                               │ distortion); release separately authorized. │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────────────────────┤
│ Tool & Agent Observability│ OpenTelemetry GenAI Semantic  │ Proposes extension: gen_ai.effect_disposition│
│ Telemetry                │ Conventions (gen_ai.*)        │ event carrying operation_id & effect status.│
└──────────────────────────┴───────────────────────────────┴─────────────────────────────────────────────┘
```

### 2.3 Clarification on arXiv:2609.28820 (Human Review Motivation)

Previous drafts incorrectly referenced arXiv:2609.28820 as a "Raw-Evidence Review Protocol." To maintain strict scientific accuracy:
* **arXiv:2609.28820** is *"AI-Enabled Human Memory Manipulation: Misleading AI-Generated Summaries Distort Human Memory"* (Sim, Eiger, Kohno).
* It is **not** an AEIB protocol. It is cited solely as **empirical motivation** for ensuring that human review gates display **un-summarized raw wire evidence** rather than model-generated summaries, which are proven to distort operator judgment and risk assessments.

---

## 3. Required Identity Triad: Intent vs. Content vs. Provider Key

### 3.1 The Flaw of Content-Only Identifiers (CAID-Only)

Early designs equated action identity with the payload hash: $\text{CAID} = H(\text{JCS}(\text{payload}))$. While content hashing is necessary for parameter immutability, it is mathematically insufficient for intent representation:
* **Collision of Legitimate Transactions:** Two distinct, intentional payments of €50 to the same beneficiary on consecutive days share an identical canonical payload. A content-only identifier would conflate them as duplicate attempts.
* **RFC 9110 Compliance:** RFC 9110 defines idempotency in terms of repeated server-side effects; it does not turn a content digest into an intent identifier.

### 3.2 The AEIB Identity Triad

AEIB separates identity into three decoupled, orthogonal primitives:

```json
{
  "operation_id": "op:01J9X4K8V2M5...",
  "request_digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "business_idempotency_key": "idemp:transfer_20261007_001",
  "principal_id": "principal:user:usr_9942",
  "tenant_id": "tenant:ent_8820",
  "policy_epoch": "policy:epoch_104",
  "tool_schema_hash": "sha256:4a8c9b..."
}
```

1. **`operation_id` (Unique Intent / Approval Instance):** A unique, monotonic identifier (e.g., UUIDv7, ULID, or signed authorization token) representing this specific execution intent.
2. **`request_digest` (Exact Request Hash):** An RFC 8785 JCS canonical hash over the exact parameters: $H(\text{JCS}(\text{payload}))$. Ensures post-approval parameter immutability.
3. **`business_idempotency_key` (Target / Provider Identity):** The business token passed to the downstream API (e.g., `Idempotency-Key` header) to enforce target-side idempotency.

---

## 4. Extended Acceptance Test Suite: AT26–AT35

The full AEIB test harness exercises 21 governance and integration scenarios:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        AEIB EXTENDED ACCEPTANCE TEST MATRIX                            │
├──────┬──────────────────────────────────┬───────────────────────────────┬──────────────┤
│ TEST │ SCENARIO NAME                    │ FAULT / BOUNDARY CONDITION    │ DISPOSITION  │
├──────┼──────────────────────────────────┼───────────────────────────────┼──────────────┤
│ AT15 │ Unregistered Agent Dispatch      │ Agent not in inventory        │ REJECT (C2)  │
│ AT16 │ Delegation Scope Escalation      │ Verb exceeds grant scope      │ REJECT (C2)  │
│ AT17 │ Stale Grant / Epoch Expiry       │ Expired standing / epoch drift│ REJECT (C2)  │
│ AT18 │ Control-Plane Degradation        │ Unhealthy sub-component       │ CONTAINMENT  │
│ AT19 │ Agent Evidence Tampering         │ Append-only ledger violation  │ FORBIDDEN    │
│ AT20 │ Indeterminate Loop Escalation    │ Repeated 504 / RST wire drops │ ESCALATE (H) │
│ AT21 │ Memory Poisoning / Schema Drift  │ Tool schema hash divergence   │ REJECT (C3)  │
│ AT22 │ Cross-Boundary Federation        │ Invalid federation proof      │ REJECT (C2)  │
│ AT23 │ Millisecond Standing Race        │ TOCTOU revocation at dispatch │ REJECT (C1)  │
│ AT24 │ Candidate Payload Mutation       │ Post-approval parameter change│ REJECT (C3)  │
│ AT25 │ Ledger Hash Chain Compromise     │ Audit chain fork detected     │ CONTAIN (C5) │
├──────┼──────────────────────────────────┼───────────────────────────────┼──────────────┤
│ AT26 │ ProxyToolAbuseGuard              │ Auxiliary tool proxy egress   │ REJECT (C3)  │
│ AT27 │ A2A Lineage Shrouding            │ Swarm vendor/model bias       │ SHROUDED     │
│ AT28 │ eBPF/LSM Shadow Discovery        │ Unregistered binary execution │ REJECT (C4)  │
│ AT29 │ Memory-Digest Binding (TOCTOU)   │ Context drift post-approval   │ REJECT (C2)  │
├──────┼──────────────────────────────────┼───────────────────────────────┼──────────────┤
│ AT30 │ Operation Identity Collision     │ Same payload, distinct op_id  │ DISTINCT REC │
│ AT31 │ Request Mutation                 │ Same op_id, mutated digest    │ REJECT (C3)  │
│ AT32 │ Idempotency-Key Mismatch         │ Same biz key, mutated payload │ REJECT (C3)  │
│ AT33 │ LIMBO-Style Late Commit          │ Bounded wait timeout expired  │ LATE_RESOLVED│
│ AT34 │ Missing Read-Back Target         │ Target lacks status endpoint  │ UNCERTAIN    │
│ AT35 │ OpenTelemetry Projection         │ Map receipt to gen_ai span    │ PROJECTED    │
└──────┴───────────────────────────┴───────────────────────────────┴──────────────┘
```

### 4.1 Detailed Breakdown of New Prior-Art Scenarios (AT30–AT35)

* **AT30 (Operation Identity Collision):** Validates that two distinct candidate actions with identical canonical payloads produce two independent, non-colliding ledger entries with distinct hashes.
* **AT31 (Request Mutation):** Validates that if an action's canonical payload is modified after approval under the same `operation_id`, the gateway rejects dispatch with `REQUEST_DIGEST_MUTATED`.
* **AT32 (Idempotency-Key Mismatch):** Validates that reusing an existing `business_idempotency_key` with conflicting payload parameters triggers `IDEMPOTENCY_KEY_PAYLOAD_MISMATCH`, enforcing provider idempotency contracts.
* **AT33 (LIMBO-Style Late Commit):** When a bounded wait expires (5000ms), the gateway latches `EFFECT_INDETERMINATE` with `retry_safe: false` (issuing 0 speculative retries). A subsequent probe executed at 8000ms after late target commit (7000ms) resolves the disposition to `LATE_COMMIT_RESOLVED`.
* **AT34 (Missing Read-Back Target):** When a target API lacks a status read-back endpoint, the gateway preserves `EFFECT_INDETERMINATE`, blocks release authorization, and strictly makes **no claim of absence**.
* **AT35 (OpenTelemetry Event Projection):** Proposes a mapping from AEIB signed receipts into the emerging OpenTelemetry GenAI semantic conventions (`gen_ai.effect_disposition`).

### 4.2 The MCP Trust-Gap Crisis & AEIB Neutralization (Addressing CVE-2026-14540)

The October 2026 disclosure reported by Dan Goodin (*Ars Technica*, October 5, 2026) based on independent research by Syed Anas Mohiuddin exposed a structural vulnerability across enterprise deployments of the Model Context Protocol (MCP). The research identified that major implementations—including Google's MCP Toolbox for Databases (CVE-2026-14540, CVSS 8.0), JPMorgan Chase, Weaviate, Rapid7, and French/US government instances—suffered from an architectural trust gap: **downstream nodes implicitly trust instructions and parameters received from upstream agents.**

#### 4.2.1 The Architectural Failure Mode: Protocol Connectivity ≠ Execution Authority

MCP defines the wire mechanics for clients and servers to communicate, but deliberately delegates authorization and execution security to implementers. When multi-agent systems chain MCP tools:
1. **Implicit Trust Delegation:** An upstream agent compromised via indirect prompt injection passes manipulated parameters downstream. Downstream agents execute these without independent re-validation of root human authority.
2. **Protocol Pivoting & SSRF:** In CVE-2026-14540, the Google MCP Toolbox HTTP client lacked restrictive redirect policies and target IP validation, enabling attackers to coerce the tool into Server-Side Request Forgery (SSRF) against internal database endpoints.
3. **Absence of Runtime Execution Boundary:** Upstream prompt injection propagates across multi-agent boundaries unimpeded because transport connectivity is conflated with execution authority.

#### 4.2.2 AEIB v0.4.0 Enforcement Mechanics

AEIB operates as an independent execution-integrity decision boundary at the wire level beneath MCP transports:

```text
  Compromised Upstream MCP Agent (Prompt Injected)
                         │ (Passes manipulated tool call / SSRF payload)
                         ▼
        🛡️ AEIB EFFECT-INTEGRITY DECISION BOUNDARY
  ┌──────────────────────────────────────────────────────────────┐
  │ 1. Provenance Binding (AT16): Validates root user grant      │
  │ 2. Millisecond Standing (AT23): Asserts policy epoch at Tn   │
  │ 3. ProxyAbuseGuard (AT26): Traps un-whitelisted URIs (SSRF)  │
  │ 4. JCS Payload Pinning (AT24): Rejects argument mutations    │
  └──────────────────────────────────────────────────────────────┘
                         │
             [ FAIL-CLOSED REJECTION ]
                         ▼
      Blocked: DISPATCH_REJECTED (PROXY_EGRESS_VIOLATION)
```

1. **Cryptographic Delegation & Provenance Binding (`AT16`):** Every candidate action must carry an explicit delegation chain (`principal_id`, `user_principal`, `grant_id`). Downstream MCP tool calls cannot inherit trust implicitly; they must present a verifiable grant tracing back to authorized human intent.
2. **Millisecond Standing & Policy Freshness (`AT17`, `AT23`):** Re-evaluates active policy epochs and standing at the exact millisecond of dispatch ($T_{\text{dispatch}}$). If context has drifted or credentials have been revoked post-planning, the boundary halts execution fail-closed (`STALE_STANDING`).
3. **Pre-Dispatch Parameter & Egress Guardrails (`AT26`):** The `ProxyToolAbuseGuard` inspects URI parameters against destination allowlists before socket transmission, intercepting unauthorized internal endpoints and redirect attempts before SSRF can manifest.
4. **RFC 8785 JCS Payload Pinning (`AT24`, `AT31`):** Canonicalizes tool arguments under $H(\text{JCS}(\text{Payload}))$. If an injected prompt mutates arguments post-approval, the candidate action ID is invalidated and rejected with `CAID_MUTATION_REJECTED` / `REQUEST_DIGEST_MUTATED`.
5. **Uncertainty Latching & Target-Side Ground Truth (Track B):** If an MCP tool execution encounters transport drops or ambiguous responses, AEIB latches `EFFECT_INDETERMINATE` with `retry_safe: false`, resolving target state via independent single-flight probes rather than trusting downstream agent self-reports.

#### 4.2.3 MCP Trust-Gap Defense Matrix

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   MCP TRUST-GAP DEFENSE MATRIX                                         │
├──────────────────────────┬───────────────────────────────┬───────────────────────────────┬─────────────┤
│ MCP VULNERABILITY VECTOR │ CVE-2026-14540 / IMPACT       │ AEIB ENFORCEMENT MECHANISM    │ DISPOSITION │
├──────────────────────────┼───────────────────────────────┼───────────────────────────────┼─────────────┤
│ Cascading SSRF           │ Injected upstream prompt coerces│ ProxyToolAbuseGuard (AT26)    │ DISPATCH_   │
│ (CVE-2026-14540)         │ downstream tool into internal │ parameter destination allow-  │ REJECTED    │
│                          │ network requests (CVSS 8.0)   │ list pre-dispatch evaluation  │ (C3)        │
├──────────────────────────┼───────────────────────────────┼───────────────────────────────┼─────────────┤
│ Implicit Role            │ Downstream agent executes tool│ Delegation Chain Binding (AT16│ UNAUTHORIZED│
│ Inheritance              │ without verifying root user   │ cryptographic lineage tracing │ _DELEGATION │
│                          │ authorization                 │ back to root human principal  │ (C2)        │
├──────────────────────────┼───────────────────────────────┼───────────────────────────────┼─────────────┤
│ Stale Context            │ Upstream instructions execute │ TOCTOU Standing Gate (AT23)   │ STALE_      │
│ Injection                │ against expired permissions   │ T_dispatch policy epoch       │ STANDING    │
│                          │ or revoked credentials        │ re-evaluation                 │ (C1)        │
├──────────────────────────┼───────────────────────────────┼───────────────────────────────┼─────────────┤
│ Tool Argument            │ Upstream context drift mutates│ JCS Payload Pinning (AT24/31) │ CAID_       │
│ Mutation                 │ payload parameters post-human │ RFC 8785 canonical hash check │ MUTATION_   │
│                          │ approval                      │ invalidates candidate action  │ REJECTED(C3)│
├──────────────────────────┼───────────────────────────────┼───────────────────────────────┼─────────────┤
│ Retried SSRF / Storm     │ Transport failure triggers    │ Uncertainty Latching (Track B)│ EFFECT_     │
│ Amplification            │ speculative retry of injected │ locks retry_safe: false;      │ INDETERMI-  │
│                          │ requests against internal host│ single-flight probe to target │ NATE (C1)   │
└──────────────────────────┴───────────────────────────────┴───────────────────────────────┴─────────────┘
```

### 4.3 Seven-Layer Authorization Decoupling & Extended Acceptance Suite (AT30–AT41)

To prevent conflation of transport connectivity, identity credentials, and execution standing, AEIB formalizes a strict seven-layer authorization decoupling:

$$\text{MCP Auth} \neq \text{Agent Identity} \neq \text{Delegation Auth} \neq \text{Tool Auth} \neq \text{Destination Auth} \neq \text{Credential Audience} \neq \text{Business Effect Auth}$$

Schema pinning alone does not prevent SSRF or credential leakage; each boundary must be evaluated independently:

1. **AT30 (Audience Mismatch):** Validates that credentials bound to an approved service audience cannot be forwarded to an unapproved recipient, failing closed with `DISPATCH_REJECTED (AUDIENCE_MISMATCH)`.
2. **AT31 (Redirect Pivot SSRF):** Blocks redirect chains pivoting from an approved origin to cloud metadata (`169.254.169.254`) or unlisted destinations, addressing Google MCP Toolbox CVE-2026-14540.
3. **AT32 (DNS Rebinding Protection):** Resolves target hostnames and validates all resolved IP addresses against private (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.0/8`), and link-local ranges, intercepting DNS rebinding before connection dispatch.
4. **AT33 (Cross-Protocol Delegation Guard):** Rejects downward translation across protocol boundaries (e.g., Web/MCP to raw database socket or binary RPC) without cryptographic proof of standing and explicit protocol delegation rights.
5. **AT34 (Token Passthrough Without Ambient Fallback):** Prohibits client runners from auto-attaching ambient host Bearer tokens or credentials when an agent fails to provide an explicit bound grant.
6. **AT35 (Agent Card Mutation Guard):** Detects modifications to remote `agent-card.json` declarations against an approved cryptographic registry, rejecting unauthorized capability expansion.
7. **AT36 (Credential Leakage Guard):** Inspects tool execution outputs for secret retrieval attempts, JWTs, or private keys, quarantining them from model context.
8. **AT37 (Handshake Discovery SSRF):** Intercepts discovery URLs from `WWW-Authenticate` headers, `.well-known` endpoints, or `resource_metadata` prior to candidate creation or connection dispatch. If targeting cloud metadata or private IPs, emits `HANDSHAKE_BLOCKED` (CVE-2026-51994 defense).
9. **AT38 (Agent Card Discovery & Context Poisoning Guard):** Enforces a two-channel representation separating untrusted natural-language descriptions from structured capability facts. Attaches `provenance: remote_agent_card` and `instruction_authority: none` to untrusted descriptions, neutralizing prompt injection execution standing (Google A2A pattern).
10. **AT39 (Per-Hop Redirect Validation & TOCTOU Pinning):** Disables automatic redirect following. Every 3xx response has its Location header re-resolved and validated against restricted IP ranges and approved schemes, emitting a structured `redirect_chain` receipt (CVE-2026-64849 defense).
11. **AT40 (Header-Layer Destination Override Guard):** Prohibits out-of-band routing headers (`Host`, `X-Forwarded-Host`, `X-Atlassian-Jira-Url`, `:authority`) from steering requests away from the approved destination origin, rejecting overrides with `HEADER_DESTINATION_OVERRIDE` (CVE-2026-27826 defense).
12. **AT41 (URI Scheme & Address Normalization):** Prohibits non-HTTP URI schemes (`file://`, `gopher://`, `ftp://`, `unix://`), IPv6 loopbacks (`[::1]`, `::1`), IPv4-mapped IPv6 (`::ffff:127.0.0.1`), and non-canonical octal or hexadecimal IP notations (MarkItDown pattern).

---

## 5. Cryptography, Receipts, and Evidence Scope Boundaries

### 5.1 Clear Separation of Cryptographic Claims

To maintain rigorous technical integrity, AEIB explicitly documents what cryptographic receipts prove and what they do **not** prove:

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             CRYPTOGRAPHIC EVIDENCE BOUNDARIES                    │
├──────────────────────────────────┬───────────────────────────────────────────────┤
│ WHAT A SIGNED RECEIPT PROVES     │ WHAT A SIGNED RECEIPT DOES NOT PROVE          │
├──────────────────────────────────┼───────────────────────────────────────────────┤
│ • The gateway observed wire state│ • It does NOT prove the remote target         │
│   at a specific wall-clock time. │   successfully committed state.               │
├──────────────────────────────────┼───────────────────────────────────────────────┤
│ • Parameters were normalized via │ • It does NOT prove that no duplicate         │
│   RFC 8785 JCS prior to hash.    │   occurred outside the tested model.          │
├──────────────────────────────────┼───────────────────────────────────────────────┤
│ • The gateway policy evaluation  │ • It does NOT prove business correctness      │
│   failed closed on epoch drift.  │   or financial solvency.                      │
├──────────────────────────────────┼───────────────────────────────────────────────┤
│ • Local evidence ledger entry    │ • A signed receipt is NOT a Transparency      │
│   hash chain is intact.          │   Service inclusion receipt (RFC 9943).       │
└──────────────────────────────────┴───────────────────────────────────────────────┘
```

Hybrid Ed25519 / ML-DSA-65 signing is treated strictly as an **implementation profile**, not a novel cryptographic discovery.

---

## 6. Regulatory Alignment (Illustrative Control Crosswalks)

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    REGULATORY CONTROL CROSSWALK (2025–2026)                      │
├────────────────────┬──────────────────────────────────┬──────────────────────────┤
│ REGULATORY REGIME  │ STATUTORY REQUIREMENT            │ AEIB TECHNICAL PRIMITIVE │
├────────────────────┼──────────────────────────────────┼──────────────────────────┤
│ EU AI Act Art. 50  │ C2PA metadata & machine marking; │ Ed25519 signed receipts; │
│ (Aug 2 / Dec 2026) │ demonstrable attribution trail   │ RFC 8785 canonical hash  │
├────────────────────┼──────────────────────────────────┼──────────────────────────┤
│ EU DORA Art. 17    │ Dual-clock incident reporting    │ Latch journal timestamps │
│ (RTS 2025/301)     │ (4h/24h initial, 72h, 1mo)       │ & DORA timeline export   │
├────────────────────┼──────────────────────────────────┼──────────────────────────┤
│ IETF SCITT         │ Signed Statements (COSE_Sign1) & │ Offline WASM verifier &  │
│ (RFC 9943 Jun 2026)│ Transparency Service receipts    │ continuity receipt model │
├────────────────────┼──────────────────────────────────┼──────────────────────────┤
│ China GB 45438-2025│ Visible display + implicit       │ Cryptographic receipt &  │
│ (In force Sep 2025)│ metadata marking on AI mutations │ immutable audit payload  │
├────────────────────┼──────────────────────────────────┼──────────────────────────┤
│ US NIST AI RMF 1.0 │ GOVERN-1.7 & MANAGE-2.2          │ Fail-closed containment  │
│ (GenAI Profile)    │ incident handling & auditability │ & target oracle probe    │
└────────────────────┴──────────────────────────────────┴──────────────────────────┘
```

*Note on DORA:* AEIB generates supporting wire telemetry and incident timeline records; it does not satisfy DORA compliance requirements independently.

---

## 7. Track B Physical & Synthetic Benchmark Results

### 7.1 Scenario Coverage & Physical Verification
* **69 Core Tests Reported Passing:** The producing environment reports 69 passing tests across the declared local, synthetic, and integration-shaped suites (0.68s runtime).
* **Track B Web Mutation Finality (20 test cases covering 18 scenario IDs `B01`–`B11`, `BT12`–`BT18`)**: 100% matched to the declared target-side oracle under synthetic Layer 7 transport faults (`HTTP 504`, `TCP RST`, socket drops, stale DOM pages). Passed post-crash latch recovery (`BT16`), probe disagreement traps (`BT14`), and parameter tampering detection (`BT18`).
* **Decisive Demonstration**: Process crash during `HTTP 504` response drop $\to$ gateway restart from persistent SQLite WAL $\to$ blind agent retry blocked $\to$ single out-of-band target probe confirms `commit_count = 1`. The tested local target recorded one commit and the gateway issued no second retry.
* **Local Physical & TinyFish-Compatible Execution**: Evaluated over real kernel sockets and HTTP protocol boundaries (`test_live_physical_execution.py`). Local TinyFish-compatible profile tests: reported passed. Real TinyFish cloud session: pending external validation.
* **Strict Environmental Separation**:
  $$\text{real local HTTP/socket execution} \neq \text{real third-party external API} \neq \text{real TinyFish cloud execution} \neq \text{independent reproduction}$$

> **Approved Locked Benchmark Assertion:**  
> *"Under the declared synthetic and local physical evaluation harnesses, the AEIB gateway matched dispositions to a target-side ledger, withheld retry authority in tested ambiguous cases, and rejected the tested unauthorized egress, audience, delegation, and credential-handling cases. The local runtime experiment included real socket and HTTP behavior. Real-world efficacy across uncoordinated distributed systems, third-party APIs, and authenticated TinyFish cloud sessions remains subject to independent reproduction and provider-side validation."*

### 7.2 Strict Dispatch Ordering Invariant
```text
[Candidate Action] ──> [Latch Journal Write] ──> [Durable fsync] ──> [Wire Dispatch]
                              │
                              └── (Disk Full / Error) ──> Dispatch ABORTED (0 bytes sent)
```

---

## 8. Verification Instructions

The local verification harness enforces multi-layered assurance before any release candidate is published:

```bash
# 1. Zone Boundary Architecture Enforcement
python3 compliance/check_zone_boundary.py

# 2. Zero-Mock & AST Purity Verification
python3 compliance/ast_purity.py . && python3 compliance/no_mock_enforcer.py

# 3. Turnkey Track B Independent Reproduction Harness (4 gates, 100% passed)
python3 scripts/verify_track_b_reproduction.py

# 4. Full 69-Test Core Verification Matrix (All 69 Passed in 0.68s)
pytest tests/test_industrial_protection_matrix.py \
       tests/test_ansi_50bf_breaker_failure.py \
       tests/test_saga_compensation.py \
       tests/test_falsifiability_matrix.py \
       tests/test_track_b_scenarios.py \
       tests/test_aeib_mcp_egress_at30_at36.py \
       tests/test_aeib_mcp_egress_at37_at41.py \
       tests/test_live_physical_execution.py -v

# Breakdown:
#   - 32 Industrial Protection Matrix & Falsifiability Tests
#   - 20 Track B Web Mutation Finality Tests (covering 18 scenario IDs)
#   -  7 Egress & Audience Acceptance Tests (AT30–AT36)
#   -  5 Egress SSRF, Redirect & Normalization Tests (AT37–AT41)
#   -  5 Real Socket & TinyFish-Compatible Execution Tests

# 5. Deterministic 500-Episode Execution Integrity Harness (Seed 42)
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
```

---

## 9. Conclusion

AEIB v0.4.0 is grounded in empirical prior art (LIMBO, RFC 9110, SCITT RFC 9943, and OTel GenAI conventions) and macroeconomic realities (GIRAI 2026).

By replacing content-only identifiers with an **identity triad** (`operation_id` $\neq$ `request_digest` $\neq$ `business_key`), enforcing pre-dispatch standing checks immediately before network dispatch, and decoupling audit release from transport observation, AEIB provides the vital integration layer between agent harnesses, provider idempotency, target reconciliation, and human oversight.

---

## 10. GOD-AEIB Integration Test Battery (GOD-01 to GOD-06) & Joint Positioning

### Full GOD-AEIB Integration Test Suite

```text
                                GOD-AEIB INTEGRATION SUITE
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ GOD-01 (Intervention Binding)    • Interventions bind to (step_id, policy_epoch, CAID) │
│                                  • Replayed interventions from prior steps rejected     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GOD-02 (Replay Immutability)     • Replay mode disables physical wire dispatch (dry_run)│
│                                  • Direct socket connections explicitly blocked         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GOD-03 (Ask/Intervene Separation)• ASK = Read-only state inspection (zero state drift) │
│                                  • INTERVENE = Generates new CAID requiring auth       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GOD-04 (Target Primacy Divergence)• Simulation prediction ≠ Wire effectuation          │
│                                  • Target ledger evidence overrides simulation state   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GOD-05 (Export Tamper Detection) • Replay pack modification invalidates SHA3 / JCS     │
│                                  • Offline WASM verifier flags tamper failure          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ GOD-06 (Operator Authority RBAC) • Observation RBAC ≠ Release Authority                │
│                                  • Unauthorized attempt to release held action fails   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### The Target Primacy Invariant (`GOD-04`)

The resolution of simulation/target divergence establishes an essential architectural rule: **a social simulator or model reasoning trace cannot self-certify physical target state.**

$$\text{Target Ledger Evidence} \gg \text{Simulation Prediction}$$

If a GOD simulation or agent trajectory predicts successful execution (e.g., "Kubernetes deployment scaled"), but the out-of-band target ledger status probe returns `UNKNOWN`, `CONFLICT`, or a socket drop:

1. **Target Evidence Overrides Simulation**: The system records `EFFECT_INDETERMINATE`.
2. **Zero Success Assertion**: No positive confirmation is emitted to the operator or upstream agent.
3. **Retry Lockout**: `retry_safe: false` is latched; speculative retries are blocked until target-side reconciliation completes.

### Locked Strategic Positioning & Value Proposition

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ GOD   = Operator Observability, Trajectory Inspection & Steering Surface               │
│ AEIB  = Wire-Level Execution Integrity, Transport Latching & Consequence Boundary      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

> **The Joint Value Proposition:**  
> *"GOD allows an operator to understand, inspect, and steer complex agent societies in real time; AEIB enforces that any consequence-bearing wire action is cryptographically bound, observed at dispatch, reconciled against target ground truth, and never retried or released merely because the simulation or model claimed it succeeded."*

