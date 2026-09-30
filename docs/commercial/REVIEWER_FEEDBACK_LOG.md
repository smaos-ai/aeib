# AEIB v0.2.0 Reviewer Discovery & Feedback Log

**Standard:** Agent Execution Integrity Benchmark (AEIB v0.2.0)  
**Document Purpose:** Systematic capture of engineering feedback, stack realities, and product iteration triggers from 1-on-1 technical review calls.  
**Classification:** Internal Research & Discovery Intake  
**Status:** Active  

---

## 📋 Standardized 4-Part Intake Rubric

Use this questionnaire to guide the 15-to-20 minute technical review calls.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               DISCOVERY CALL INTAKE RUBRIC                             │
├─────────────────────────┬───────────────────────────────┬──────────────────────────────┤
│ 1. 4 CORE PRIMITIVES    │ 2. STACK REALITIES            │ 3. VERDICT & NEXT STEPS      │
│ • Idempotency Symmetry  │ • Primary Languages/Frameworks│ • Obvious / Missing X / Void │
│ • 7-State Taxonomy Fit  │ • Existing Saga/Idempotency   │ • Sandbox vs. Production     │
│ • Probe Timeouts        │ • Real Post-504 Incident Pain │ • Specific Edge Cases Flagged│
│ • Sidecar vs. Filter    │                               │                              │
└─────────────────────────┴───────────────────────────────┴──────────────────────────────┘
```

---

### Section 1: The Four Open Engineering Questions

#### Q1: Idempotency Symmetry (UUIDv5 vs. Server Tokens)
* *Prompt*: *"We derive a deterministic UUIDv5 key from the normalized payload prior to wire egress. Does this match how your APIs handle deduplication, or do your backend services require client-generated UUIDv4 or server-assigned tokens?"*
* **Key Signals**:
  - Do their gateways accept an `X-Idempotency-Key` or `Idempotency-Key` header?
  - Does their backend verify payload hash consistency on duplicate key receipt, or do they reject duplicate keys outright?

#### Q2: 7-State Taxonomy Fit Against Real Gateway Drops
* *Prompt*: *"Our taxonomy splits ambiguous outcomes into `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, `RECONCILIATION_FAILED`, and `PROBE_EXCEPTION`. Does this cover your real transport failure modes, or is there a distributed state missing?"*
* **Key Signals**:
  - What happens when a load balancer drops connection before TLS handshake vs. after request body transmission?
  - Do they distinguish between downstream database deadlocks vs. reverse proxy timeouts?

#### Q3: Handling Probe Timeouts & Inconsistent Reads in Sagas
* *Prompt*: *"When the out-of-band probe itself encounters a timeout (`PROBE_EXCEPTION`), how do your systems differentiate an unreachable ledger from a transaction that aborted?"*
* **Key Signals**:
  - Do they use read-replicas that suffer replication lag (stale read risk)?
  - How long do they hold transactions in quarantine before escalating to manual human review?

#### Q4: Deployment Surface (Sidecar Proxy vs. Embedded Filter)
* *Prompt*: *"Would your platform team prefer this boundary guard running as an out-of-process local sidecar proxy (Mode 2), or as an in-process runtime filter like `ProofOrStopFilter.java` (Mode 3)?"*
* **Key Signals**:
  - Sidecar preferences: Kubernetes Istio/Envoy, local Docker, zero language dependency.
  - Filter preferences: Sub-millisecond latency, zero network hop, JVM WebClient / Spring Boot integration.

---

### 🛡️ The "Temporal / Kafka / Sagas" Objection Pivot

When enterprise architects say:
> *"We already solve this with Temporal / Kafka / Saga patterns."*

**The Pivot to Deliver Immediately**:
> *"Temporal guarantees the workflow runs to completion, but it cannot know whether the downstream core banking system actually committed the transaction when the TCP connection resets or an HTTP 504 drops.*  
>  
> *If your Temporal activity throws an error on a 504, Temporal will execute a blind retry and double-charge the client. AEIB is the boundary state-machine logic and cryptographic receipt layer that tells Temporal NOT to retry until a specific out-of-band ledger probe completes."*

---

### Section 2: Target Stack Realities

* **Languages & Runtimes**: Java (Spring Boot / LangChain4j), Python (FastAPI / LangChain / AutoGen), Go, Rust, Node.js.
* **Orchestration & Workflow Engines**: Temporal, Camunda, Kafka Outbox, AWS Step Functions, custom state machines.
* **Historical Post-504 Incident Pain**: Have they personally dealt with duplicate payments, double-allocation of credit, or audit findings due to dead-socket retries?

---

### Section 3: Sentiment Classification & Action Triggers

* **Primitive Reception**:
  - [ ] **A. Obvious & Already Solved** → *Ask: "Which library or middleware solved it for you?"*
  - [ ] **B. Interesting, but Missing X** → *Ask: "What exact invariant or hook is X?"*
  - [ ] **C. Confusing / Not Relevant** → *Ask: "Where did we lose you in the 5-minute tour?"*
* **Engagement Intent**:
  - [ ] **Sandbox Experiment** *(Send them the local Docker / CLI harness)*
  - [ ] **Wants Production-Ready** *(Flag for v0.3 RFC 8785 / proxy roadmap)*
  - [ ] **No Use Case** *(De-prioritize this persona profile)*

---

## 📝 Reviewer Call Records (Initial Triad)

---

### Review Record 01: Martin Brachtl (Česká spořitelna / Erste Group)
* **Date**: *Pending Call*
* **Role**: Head of Digital Architecture & APIs (Prague)
* **Target Focus**: API Gateways, reverse proxy 504 timeouts, retry storm mitigation.

| Dimension | Reviewer Response & Engineering Notes |
| :--- | :--- |
| **Q1 (Idempotency)** | *Pending* |
| **Q2 (7-State Taxonomy)** | *Pending* |
| **Q3 (Probe Timeouts)** | *Pending* |
| **Q4 (Sidecar vs Filter)** | *Pending* |
| **Stack Realities** | Java 17/21, Spring Boot, OpenShift/K8s, Kong/Apigee API Gateways. |
| **Past Incident Pain** | API retry loops cascading into backend core banking under high latency. |
| **Verdict Category** | [ ] Obvious & Solved • [ ] Interesting (Missing X) • [ ] Confusing |
| **Actionable Iterations** | *To be filled during call* |

---

### Review Record 02: Stefan Steiner (Raiffeisen Bank International)
* **Date**: *Pending Call*
* **Role**: Lead Payments & Settlement Architect (Vienna)
* **Target Focus**: Core settlement APIs, wire transaction finality, saga rollback boundaries.

| Dimension | Reviewer Response & Engineering Notes |
| :--- | :--- |
| **Q1 (Idempotency)** | *Pending* |
| **Q2 (7-State Taxonomy)** | *Pending* |
| **Q3 (Probe Timeouts)** | *Pending* |
| **Q4 (Sidecar vs Filter)** | *Pending* |
| **Stack Realities** | Java Spring Boot, Kafka, ISO 20022 payment engines, relational clearing ledgers. |
| **Past Incident Pain** | Severed sockets during payment clearing triggering duplicate reconciliation tickets. |
| **Verdict Category** | [ ] Obvious & Solved • [ ] Interesting (Missing X) • [ ] Confusing |
| **Actionable Iterations** | *To be filled during call* |

---

### Review Record 03: Daniel Čermák (UniCredit Bank Slovakia)
* **Date**: *Pending Call*
* **Role**: Head of Operational Risk & Architecture (Bratislava)
* **Target Focus**: DORA Article 17 incident evidence, supervisory audit trail reconstruction.

| Dimension | Reviewer Response & Engineering Notes |
| :--- | :--- |
| **Q1 (Idempotency)** | *Pending* |
| **Q2 (7-State Taxonomy)** | *Pending* |
| **Q3 (Probe Timeouts)** | *Pending* |
| **Q4 (Sidecar vs Filter)** | *Pending* |
| **Stack Realities** | Enterprise Java, Oracle DB, microservices, cross-border NBS/ECB reporting pipelines. |
| **Past Incident Pain** | Explaining unrecorded transport timeouts and missing receipts to supervisory examiners. |
| **Verdict Category** | [ ] Obvious & Solved • [ ] Interesting (Missing X) • [ ] Confusing |
| **Actionable Iterations** | *To be filled during call* |

---

## 🔄 Iteration Backlog Driven by Feedback

Use this section to record immediate code and documentation changes resulting from reviewer feedback:

1. **Mapping Contract Iterations** (`mapping/transport-to-disposition-mapping.yaml`):
   - *TBD based on reviewer edge cases.*
2. **Evidence Model Iterations** (`transport.jsonl`, `probe.jsonl`, signed view):
   - *TBD based on reviewer schema critique.*
3. **UI / Triage Workflow Iterations** (Triage Queue, Merkle tree viewer):
   - *TBD based on reviewer operational friction.*
4. **Positioning & Messaging Iterations**:
   - *TBD based on what resonated vs. what caused confusion.*
