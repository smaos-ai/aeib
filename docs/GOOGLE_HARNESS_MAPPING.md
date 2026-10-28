# SMAOS as the Verification Layer for the Industrial Agent Harness
## Formal Mapping to Google’s Five-Stage Industrial Agent Pipeline

> **“SMAOS is the verification layer for the harness. It audits the harness, not the model.”**

---

### Executive Thesis

Google’s *Harness Thesis* demonstrates that frontier language models are rapidly commoditizing. The sustainable enterprise asset is the **execution harness**—the infrastructure that coordinates intent, manages sandboxes, guides trajectories, and enforces safety boundaries.

However, existing harnesses have a fatal blindspot: they conflate *dispatched actions* with *verified physical outcomes*. When an agent issues a mutating tool call over an ambiguous connection (e.g., HTTP 504 Gateway Timeout), the harness cannot verify whether the state mutation occurred on the physical downstream system.

SMAOS sits directly across Google’s 5-stage pipeline as the **Layer 5 Consequence Integrity Boundary**:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STAGE V: META-DEBUG & AUDIT                        │
│             Zero-Egress chDB OLAP / ISO 42006 Reconstructable Audit         │
└──────────────────────────────────────▲──────────────────────────────────────┘
                                       │ Ed25519 SCITT Work Receipts
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                    STAGE IV: VERIFICATION & STATE ATTESTATION                │
│    Deterministic Post-Condition Probes ("Paris Hotel + Breakfast" State)    │
│           Wall-Clock Authority Freshness Delta (ΔAuth = tn - t0)            │
└──────────────────────────────────────▲──────────────────────────────────────┘
                                       │ Verified Trajectory & Hashes
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                    STAGE III: TRAJECTORY & WIRE TRANSPORT                   │
│        Model Context Protocol (MCP) Interception & RFC 8785 JCS Hashing      │
│        SHA-256 Idempotency Key Binding & Fail-Closed 504 Quarantine          │
└──────────────────────────────────────▲──────────────────────────────────────┘
                                       │ Policy Clearance (Sub-100ms)
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                      STAGE II: HARNESS & LOCAL POLICY GATES                 │
│         Pre-Dispatch System 1 Typed Gating (CONFIRMED vs. REFUSED)          │
│               NVIDIA OpenShell / BlueField Sentry OS Sandbox                │
└──────────────────────────────────────▲──────────────────────────────────────┘
                                       │ Intent & Authority Grants
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                       STAGE I: SPECIFICATION & INTENT                       │
│              Task Declarations, Role Permissions & Bitemporal TTL           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Detailed Stage-by-Stage Mapping

| Google Harness Stage | Industry Default Approach | SMAOS Role & Primitive | Operational & Audit Benefit |
|---|---|---|---|
| **I. Specification** | Prompt engineering, static markdown instructions. | Consumes intent, authority grants ($t_0$), and cryptographic policy parameters. | Establishes unambiguous baseline for authority validity. |
| **II. Harness** | Language SDK wrappers (LangChain, AutoGen). | Wraps Model Context Protocol (MCP) tool calls; executes sub-100ms System 1 typed gating. | **Zero token egress** on policy violation; drops invalid calls at socket. |
| **III. Trajectory** | Unstructured JSON logs sent to SaaS aggregators. | Intercepts MCP JSON-RPC, computes RFC 8785 JCS hashes, and binds SHA-256 idempotency keys. | Eliminates silent parameter drift; binds identical wire keys across retries. |
| **IV. Verification** | "LLM-as-a-Judge" or string pattern matching. | Deterministic downstream state probes; forces `dispatched_unconfirmed` on HTTP 504. | **100% elimination of double-spend**; separates action claims from outcome facts. |
| **V. Meta-Debug** | Ad-hoc text search in centralized cloud logs. | In-process embedded **chDB** OLAP engine over local JSONL Merkle receipts. | **Reconstructable evidence** satisfying ISO/IEC 42006 & DORA Art. 17. |

---

### The Operational Axiom

* **Layer 4 (OpenShell / BlueField Sentry):** Governs *intent*, local operating system calls, and container bounds.
* **Layer 5 (SMAOS / AEIB):** Governs *consequence integrity* and outcome receipts at the external transport wire.

> *"Actions are claims. Outcomes are evidence."*
