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
