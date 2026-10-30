# SovereignNexus Visual Architecture, Mermaid Schematics & UI Blueprints


> **Classification:** Visual System Maps, Sequence Flows, State Machines & UI Walkthroughs

> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`



## 1. High-Level Macro Architecture

```mermaid
flowchart TD
    subgraph Ingest["Inference & Intent Intake"]
        A["LLM Reasoning Agent (DeepSeek, Claude, Gemma 4)"] --> B["ModelDecisionEnvelopeV1"]
    end
    subgraph AEIB_Core["SovereignNexus AEIB Deterministic Kernel"]
        B --> C{"Station 1: Intent Interlock"}
        C -->|Valid| D["EO1 WAL Journal (fcntl.flock + F_FULLFSYNC)"]
        C -->|Uncertain/504| E["Indeterminate Latch (0% Duplicate Writes)"]
        D --> F["Poka-Yoke AST & Toyota Jidoka SpecGuard"]
        F --> G["Fail-Closed Integer bps Escrow"]
    end
    subgraph Reality["Authoritative Physical Sinks"]
        G --> H["Financial Wires & x402 Micropayments"]
        G --> I["Production PostgreSQL 16"]
        G --> J["Bio Wet-Lab Actuators (PBAG Gate)"]
    end
```



## 2. 6-Stage Execution Lifecycle & Post-Commit Wire Trap

```mermaid
sequenceDiagram
    autonumber
    actor Agent as AI Agent
    participant Kernel as AEIB Deterministic Kernel
    participant Ledger as POSIX Append-Only WAL
    participant Wire as External Wire / API Socket
    participant Target as Authoritative Sink (DB/Bank)
    Agent->>Kernel: Propose Tool Mutation (CAID Bound)
    Kernel->>Ledger: Pre-Dispatch Intent Latch (F_FULLFSYNC)
    Kernel->>Wire: Open Socket & Dispatch Payload
    alt Transport Drop / HTTP 504
        Wire-->>Kernel: Network Severed (HTTP 504)
        Kernel->>Kernel: Latch EFFECT_INDETERMINATE
        Note over Kernel: Retry Prohibited (Blocks Double Spend)
    else HTTP 200 OK
        Wire-->>Kernel: HTTP 200 Success
        Kernel->>Ledger: Transition to COMMITTED
    end
```



## 3. Biological Action Gating & Scope Bisection (PBAG)

```mermaid
flowchart LR
    A["Proposed Biological Action"] --> B{"Scope Gate"}
    B -->|T0: Read-Only Lookup| C["dbSNP / AlphaGenome / ENCODE"]
    B -->|T1: Vetted Analysis| D["Local Bio Pipeline"]
    B -->|T2: Parallel Evidence| E["VariantEvidencePipeline (Concurrent)"]
    B -->|T3: Physical Wet-Lab| F["FAIL CLOSED: CapabilityUnavailableError"]
```



## 4. UI Layout Blueprints & Human-in-the-Loop Architecture

- **01-home.png**: Executive Command Center showing global fleet health, active budget escrows, and real-time fault rates.

- **02-governance-dashboard.png**: Regulatory compliance monitor mapping DORA Article 17, EU AI Act Article 12, and SCITT receipts.

- **03-security-view.png**: Forensic investigation console tracing 504 timeout recovery, CAID verification, and blocked duplicate retries.

- **04-creator-platform.png**: Agent deployment workbench configuring capability scopes, budget ceilings, and step-up warrants.