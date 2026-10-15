# AEIB Architectural Deployment Profile & Egress Broker Composition Note
**Integration Topology: Sandbox Substrates, Egress Enforcement, and the AEIB Execution Boundary**

```text
Document Version : 1.1.0-rc.1
Release Baseline : v1.0.0-rc.3 / v1.1 Sequence
Status           : Standardized Integration Architecture
Classification   : Technical Systems Architecture
Epistemic Notice : Evaluated under the stated model. Preserves strict epistemic lock.
```

---

## 1. Executive Summary: The Data Plane Boundary Gap

Modern enterprise agentic deployments increasingly adopt isolation substrates (such as gVisor or Firecracker microVMs) paired with network-level credential-injection proxies (e.g., `atenet-egress`) and semantic gateway inspection layers (`agentgateway`). 

While this architecture solves credential isolation and protocol-level tool filtering, **it stops short of consequential execution integrity**:
1. Egress proxies inject credentials and enforce allowlists, but do not bind the exact canonical mutation payload.
2. Semantic gateways inspect tool calls, but treat an `HTTP 504 Gateway Timeout` or `TCP RST` as a generic transport error, triggering automated retry loops that cause duplicate financial side effects.
3. Neither substrate generates tamper-evident, offline-verifiable execution receipts for regulatory and audit scrutiny.

**AEIB does not replace sandbox worker isolation or Vault/KMS credential stores.** Instead, AEIB operates as the **consequential execution finality boundary** at the Payments MCP / financial socket interface.

---

## 2. Layered Architecture: Substrate + Gateway vs. AEIB

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE AGENTIC EXECUTION TOPOLOGY                     │
└──────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 1. WORKER ISOLATION LAYER (Agent Substrate)                              │
  │ • gVisor / Firecracker microVM sandboxes (orders-agent, support-agent).  │
  │ • Zero-Secret Workers: Containers hold NO private keys and NO certs.     │
  └───────────────────────────────────┬──────────────────────────────────────┘
                                      │ (Internal socket)
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 2. EGRESS ENFORCEMENT & CREDENTIAL INJECTION (atenet-egress)             │
  │ • Mutual TLS actor identification.                                       │
  │ • Ephemeral token retrieval from Enterprise Secret Store (Vault / KMS).   │
  │ • Default-deny IP/DNS routing policy.                                    │
  └───────────────────────────────────┬──────────────────────────────────────┘
                                      │ (Injected egress)
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 3. SEMANTIC PROTOCOL INSPECTION (agentgateway)                           │
  │ • Granular MCP, A2A, and LLM tool-call filtering.                        │
  │ • Prompt-injection heuristic scrubbing.                                  │
  └───────────────────────────────────┬──────────────────────────────────────┘
                                      │ (Pre-dispatch candidate action)
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 4. AEIB CONSEQUENTIAL EXECUTION BOUNDARY (Station 0 to Station 4)        │
  │ • Station 0: Capability manifest admission & parameter validation.       │
  │ • Station 1: Exact RFC 8785 JCS CAID binding & commit-time Tn check.     │
  │ • EO-1 WAL: Durable DISPATCH_INTENT fsync before socket allocation.      │
  │ • Station 2: HTTP 504 / TCP RST latch (EFFECT_INDETERMINATE, retry_safe:0│
  │ • Station 2: Bounded reconciliation probe under Target Evidence Contract.│
  │ • Station 3: Append-only Ed25519 ContinuityReceipt hash chain.          │
  │ • Station 4: Offline cross-language verification (Java, Python, WASM).   │
  └───────────────────────────────────┬──────────────────────────────────────┘
                                      │ (Governed Layer 7 write)
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 5. TARGET ENTERPRISE FINANCIAL API (Core Banking, SEPA, Stripe, Adyen)   │
  │ • Authenticated status endpoint (contracts/refund_status_v1.schema.json).│
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Comparative Capability Matrix

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                INDUSTRY BROKER STACK vs. AEIB FINALITY BOUNDARY              │
├──────────────────────────────┬────────────────────────┬──────────────────────┤
│ CAPABILITY LAYER             │ SUBSTRATE + GATEWAY    │ AEIB v1.0 / v1.1     │
├──────────────────────────────┼────────────────────────┼──────────────────────┤
│ Worker isolation (microVM)   │ Included               │ Complementary host   │
│ Vault/KMS secret injection   │ Included               │ Complementary / Ref  │
│ Coarse MCP tool allow/block  │ Included               │ Station 0 Manifest   │
│ Exact RFC 8785 CAID binding  │ Not established        │ Station 1 Interlock  │
│ Durable pre-dispatch intent  │ Not established        │ EO-1 WAL persistence │
│ HTTP 504 / TCP RST latching  │ Not established        │ EFFECT_INDETERMINATE │
│ Anti-blind-retry enforcement │ Not established        │ retry_safe: false    │
│ Authenticated target probe   │ Not established        │ Station 2 Reconciler │
│ Offline Ed25519 receipts     │ Not established        │ Station 3 & 4 WASM   │
└──────────────────────────────┴────────────────────────┴──────────────────────┘
```

---

## 4. Model Interchangeability & Harness-Aware Distillation (HAD)

Recent empirical findings in agent distillation (e.g., KAIST AI, arXiv:2610.02858v1) show that when enterprise deployers distill large frontier reasoning models into smaller, cost-effective Small Language Models (SLMs), **the boundary harness remains fixed**. In Harness-Aware Distillation (HAD), candidate actions that contradict the harness's state records are dropped during training and inference.

### Technical Consequence for AEIB:
1. **Model Weight Independence**: Enterprise safety, authority, and financial policy cannot reside inside model weights or system prompts. Model checkpoints are transient, updated, or distilled to optimize latency and compute cost.
2. **Fixed Deterministic Predicate**: AEIB evaluates the deterministic standing predicate:
   $$\text{Standing}(T_n) = \text{GrantValid} \wedge \text{EpochFresh} \wedge \text{CAIDMatch} \wedge \text{TargetAllowed} \wedge \neg\text{Halted}$$
   Regardless of whether the caller is a frontier foundation model or a distilled local SLM, any proposed action violating this predicate is blocked at $T_n$ before external socket allocation.

---

## 5. Deployment Guidelines & Network Domain Boundaries

1. **Zone 1 (Untrusted / Reasoner Domain)**:
   - Contains agent runtime, prompt context, and worker memory.
   - Holds no financial credentials, private signing keys, or direct external network routes.
2. **Zone 2 (Governed Execution Boundary)**:
   - Houses the AEIB proxy sidecar and durable write-ahead journal.
   - Holds the Ed25519 ledger signing key and manages local `/var/run/aeib/halt.state`.
   - Directly intercepts outbound socket connections to financial tools.
3. **Zone 3 (Target Financial Services)**:
   - External banking primary, SEPA gateway, or payment processor.
   - Exposes an authenticated reconciliation endpoint conforming to `refund_status_v1`.
4. **Zone 4 (Independent Offline Auditor)**:
   - Operates in zero-network cleanroom environments.
   - Runs `smaos_verify.wasm`, the Java CLI verifier, or the Python verifier to attest cryptographic receipt chains without network egress.

---

## 6. Constrained Decision Models ("Jev"-Style) vs. Deterministic Authorization

Specialized decision models—such as Strands Decider 2B (local agent gates), GLiNER2.5-Decide (340M encoder), Clef / Clef-flash, and OpenAI Decisions API—operate on a constrained paradigm: allowed answers in, a label or score out.

Enterprise architects frequently make the mistake of wiring a small neural decision model in front of a tool call and mistaking it for an "authorization gate." AEIB explicitly establishes the boundary:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│        NEURAL DECISION MODEL ("JEV"-STYLE) vs. AEIB EXECUTION BOUNDARY       │
├──────────────────────────────┬────────────────────────┬──────────────────────┤
│ PROPERTY                     │ DECISION MODEL GATE    │ AEIB STATION 1–3     │
├──────────────────────────────┼────────────────────────┼──────────────────────┤
│ Evaluation Mechanism         │ Probabilistic weights  │ Deterministic math   │
│ Output Type                  │ Label / score over     │ Boolean standing +   │
│                              │ allowed answers        │ Ed25519 receipt      │
│ Exact Wire Digest (`CAID`)   │ Cannot verify SHA-256  │ Enforces RFC 8785 JCS│
│ Single-Use Replay Protection │ Stateless / none       │ Atomic ticket burn   │
│ Policy Epoch Rotation (`Δ`)  │ Blind to epoch state   │ Fails closed (`AT31`)│
│ Post-Dispatch `HTTP 504`     │ Blind to wire state    │ Latches INDETERMINATE│
│ EU Data Residency            │ Varies (US-hosted APIs)│ 100% local / on-prem │
└──────────────────────────────┴────────────────────────┴──────────────────────┘
```

### Safe Composition Architecture:
- **Upstream Intent Triage (Zone 1)**: An enterprise can deploy a local Strands Decider 2B or EU-hosted classification endpoint within the Reasoning Plane to classify a support ticket into a candidate refund category.
- **Downstream Execution Interlock (Zone 2)**: Once proposed, AEIB evaluates the resulting `CandidateAction` deterministically at the execution boundary. Probabilistic models never possess authority to release wire sockets.
- **Sovereign Residency Advantage**: Many external decision APIs lack dedicated EU data residency. AEIB executes entirely in-process or as a local sidecar with an offline WASM verifier (`smaos_verify.wasm`), introducing zero cross-border telemetry or egress.

---

## 7. The Lossy Compression Trap (rtk 1.0) & The Byte-Exact Wire Invariant

Agent-agnostic CLI token compression proxies (such as `rtk 1.0` or ScaleDown) shrink tool and shell output by 60–90% (e.g., condensing a 40-line `git status` into 3 lines) to optimize LLM context window cost.

While valuable for interactive developer scratchpads, **lossy output proxies introduce a severe integrity hazard if applied to consequential execution paths**:
1. **Target Evidence Destruction**: The `contracts/refund_status_v1.schema.json` reconciliation contract requires exact, uncompacted parameters (`operation_id`, `target_transaction_id`, `operation_status`, `amount_minor_units`, `target_signature`) to resolve an `EFFECT_INDETERMINATE` state. A proxy that truncates or summarizes responses destroys cryptographic verification.
2. **Boundary Invariant**: Lossy compression proxies are strictly confined to **Tier 1 (Read-Only / Developer Scratchpad)**. All Station 1 (`CandidateAction`) and Station 2 (`TargetEvidenceContract`) traffic must traverse an uncompacted, byte-exact channel.

---

## 8. Multi-Agent Workspaces (GitSwarm) vs. Non-Bypassable Delegation (AT39 & AT46)

Architectures such as Meta's GitSwarm (arXiv:2610.04862v1) coordinate asynchronous multi-agent collaboration around a shared, branchable Git repository, using atomic commits to accumulate intermediate reasoning and track semantic dependencies across episodes.

### Threat Model & Boundary Enforcement:
- **Shared Workspace Risk**: Because all agents in a swarm have write access to branches in the shared Git repository, the repository is inside the agents' writable blast radius.
- **Untrusted Context Rule**: AEIB treats shared repository commits as untrusted workspace context. An agent cannot self-authorize a consequential external mutation simply by referencing a commit or comment authored by a peer agent.
- **Cryptographic Attenuation**: Consequential mutations require a cryptographically signed, attenuated delegation chain anchored to an authorized human or root policy grant (`AT39`).
- **Ledger Isolation**: Audit receipts (`ContinuityReceipt`) must be persisted to append-only journals outside the agents' writable Git trees (`AT46`), preventing agents from rewriting historical execution evidence.

---

## 9. Formal Provenance Discipline & Epistemic Hygiene (Genesis AiX / NC2.5 Triad)

AEIB strictly adheres to formal provenance discipline, separating technical reality from rhetorical claims:
1. **Three-Way Claim Partition**:
   - *Direct Quotation*: Exact reproduction of standard clauses, code symbols, or hash digests.
   - *Reasonable Implication*: Logical inferences derived from documented architectural topologies.
   - *Technical Proof*: Reproducible, deterministic execution traces, passing test suites, and SHA-256 hash-bound artifacts.
2. **Rejection of Narrative Overclaim**:
   - Calling a component "the foundation" or "the bedrock" in documentation does not constitute evidence that an enforcement boundary exists.
   - Under AEIB's Acceptance Framework, no claim in `CLAIM_CONTROL_TEST_ARTIFACT_MATRIX.yaml` is marked `PASS` based on architectural narrative—only on committed code, SHA-256 artifact digests, and reproducible cleanroom test logs.

