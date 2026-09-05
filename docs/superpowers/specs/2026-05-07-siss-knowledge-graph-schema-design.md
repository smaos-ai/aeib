# SISS Knowledge Graph Schema Design

**Date:** 2026-05-07
**Status:** Approved
**Scope:** Step A — Foundation data model for the Sovereign Intelligence Substrate Standard (SISS)

---

## 1. Overview

The SISS Knowledge Graph is the gravitational core of the entire substrate. Every component — the Governance Gatekeeper, Job Router, Behavioral Firewall, Feedback Router, and Context Cartography — reads from or writes to this graph. The schema must natively support ReBAC (Relationship-Based Access Control), AP2 microtransactions, and a self-healing memory lifecycle with Ebbinghaus-decay-based consolidation.

### Core Value Loop

The graph anchors a continuous **sense-decide-act-learn** loop:

1. **Sense & Authorize** — Gatekeeper queries ReBAC edges + AP2 mandate chain
2. **Orient & Preload** — Context Cartography traverses memory edges to build the Visible Field
3. **Decide & Execute** — Job Router dispatches authorized Tasks to hardware
4. **Act & Guard** — Behavioral Firewall inspects Task trajectory against persona doctrine
5. **Learn & Crystallize** — Feedback Router scores the Task and writes new Memory nodes

---

## 2. Node Types

### 2.1 Identity Nodes

| Node | Description |
|------|-------------|
| `User` | A human operator. Authenticates externally. Can delegate to multiple Personas via `ACTS_AS`. |
| `Team` | A group of Users. Inherits and aggregates permissions. |
| `Tenant` | The top-level isolation boundary. All nodes belong to exactly one Tenant. |
| `Persona` | The operational identity through which all actions are performed. Can represent a human role, an AI agent profile (e.g., *Governance Gatekeeper*, *Adversary.Spend*), or a system daemon. Permissions resolve at the Persona level. |

**Key design decision:** Personas are the universal actor type. Humans and AI agents are both represented as Personas with different capability sets attached via ReBAC edges. A User can have many Personas (`ACTS_AS`), but every action in the system is performed by a Persona, never by a raw User.

### 2.2 Resource Nodes

| Node | Description |
|------|-------------|
| `Tool` | An executable capability (MCP server, API endpoint, shell command). Carries: `tool_uri`, `risk_class`, `version`. |
| `Skill` | A procedural capability composed of multiple Tools and/or prompts (Skill Packs). Carries: `skill_definition`, `required_tools[]`, `version`. |
| `Document` | Raw file, source data, or ingested reference material. Carries: `content_hash`, `mime_type`, `source_uri`. |

### 2.3 Memory Nodes

Memory is organized into four consolidation tiers following cognitive architecture principles. Each tier is a distinct node type because they have different lifecycle rules, decay rates, and query patterns.

| Node | Description | Decay Behavior |
|------|-------------|----------------|
| `Working_Memory` | Short-lived, session-scoped scratchpad. Evicted when Session ends unless promoted. | No decay — TTL-based eviction. |
| `Episodic_Memory` | Records of specific events, sessions, and outcomes. "What happened." | Moderate decay. Reinforced by recall. |
| `Semantic_Memory` | Distilled facts, rules, and domain knowledge. "What is true." | Slow decay. Reinforced by usage and validation. |
| `Procedural_Memory` | Learned workflows, patterns, and heuristics. "How to do things." | Slowest decay. Reinforced by successful execution. |

**Common attributes on all Memory nodes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `confidence_score` | `f64` | Dynamic score: strengthens with reinforcement, decays over time via Ebbinghaus curve. |
| `quality_score` | `f64` | Assigned by the Feedback Router after task completion. |
| `last_reinforced_at` | `timestamp` | Used to calculate time-based decay. |
| `created_at` | `timestamp` | Immutable creation time. |
| `consolidation_tier` | `enum` | Explicit tier label for polymorphic queries. |
| `content_hash` | `bytes` | Integrity verification. |
| `tenant_id` | `uuid` | Isolation boundary. |

### 2.4 AP2 / Transaction Nodes

The Agent Payment Protocol (AP2) uses a three-node mandate chain to create a tamper-proof audit trail for every compute transaction.

| Node | Description |
|------|-------------|
| `IntentMandate` | Preapproved budget envelope and guardrails for a class of tasks. Created by governance policy or human approval. |
| `PaymentMandate` | A specific, signed transaction request against an IntentMandate. One IntentMandate can authorize many PaymentMandates. |
| `PaymentReceipt` | Immutable record of a completed transaction. Created after successful execution. |

**AP2 Attributes:**

| Attribute | Applies To | Type | Description |
|-----------|-----------|------|-------------|
| `budget_limit` | IntentMandate | `i64` | Maximum synthetic spend in microunits. |
| `budget_spent` | IntentMandate | `i64` | Running total of consumed budget. |
| `risk_class` | IntentMandate, PaymentMandate | `enum(low, medium, high, critical)` | Determines routing and firewall scrutiny. |
| `allowed_tools` | IntentMandate | `uuid[]` | Whitelist of Tool node IDs this mandate authorizes. |
| `cryptographic_signature` | PaymentMandate, PaymentReceipt | `bytes` | Ed25519 signature for tamper-proof verification. |
| `amount` | PaymentMandate, PaymentReceipt | `i64` | Exact spend for this transaction. |
| `status` | PaymentMandate | `enum(pending, approved, rejected, expired)` | Lifecycle state. |
| `executed_at` | PaymentReceipt | `timestamp` | When the transaction was finalized. |

### 2.5 Governance Nodes

| Node | Description |
|------|-------------|
| `GovernanceRule` | A first-class graph object encoding a system invariant. Makes the substrate self-auditing and formally verifiable. |

GovernanceRule nodes transform hardcoded constraints into queryable, versionable, enforceable graph entities. The Governance Gatekeeper, Behavioral Firewall, and Feedback Router all read these nodes to determine what is permitted at runtime.

**GovernanceRule Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `rule_id` | `uuid` | Unique identifier. |
| `rule_type` | `enum(rebac, ap2, memory_lifecycle, task_fsm, context, custom)` | Which subsystem this rule governs. |
| `name` | `string` | Human-readable rule name (e.g., `budget_cannot_exceed_limit`). |
| `expression` | `string` | The formal rule expression. Can be a predicate in a DSL, a Cypher pattern, or a TLA+ snippet reference. |
| `severity` | `enum(advisory, enforced, critical)` | `advisory` = log violation. `enforced` = block the action. `critical` = block + alert + freeze the Persona. |
| `applies_to` | `string[]` | Node types or edge types this rule constrains (e.g., `["IntentMandate", "PaymentMandate"]`). |
| `version` | `i32` | Rule version for auditability. Only the latest active version is enforced. |
| `is_active` | `bool` | Soft-disable without deletion. |
| `created_by` | `uuid` | Persona who authored the rule. |
| `created_at` | `timestamp` | When the rule was created. |
| `tenant_id` | `uuid` | Tenant isolation. |

**Example GovernanceRules:**

| Rule Name | Type | Expression (pseudocode) | Severity |
|-----------|------|------------------------|----------|
| `budget_cannot_exceed_limit` | `ap2` | `IntentMandate.budget_spent <= IntentMandate.budget_limit` | `critical` |
| `cross_tenant_edge_forbidden` | `rebac` | `edge.source.tenant_id == edge.target.tenant_id` | `critical` |
| `memory_gc_threshold` | `memory_lifecycle` | `Memory.confidence_score >= 0.1 OR Memory.is_pinned == true` | `enforced` |
| `task_fsm_gatekeeper_only` | `task_fsm` | `Task.status transition pending->authorized requires actor.role == GovernanceGatekeeper` | `enforced` |
| `session_token_budget` | `context` | `Session.tokens_consumed <= Session.token_budget` | `enforced` |

**Governance Edges:**

| Edge | Direction | Description |
|------|-----------|-------------|
| `ENFORCES` | GovernanceRule -> Node Type | Declares which node type(s) this rule constrains. |
| `VIOLATED_BY` | GovernanceRule -> Task/Session | Audit trail: links a rule to the specific Task or Session that violated it. |
| `AUTHORED_BY` | GovernanceRule -> Persona | Who created or last modified this rule. |

### 2.6 Execution Nodes

| Node | Description |
|------|-------------|
| `Task` | The atomic unit of work. Represents a single intent flowing through the value loop. |
| `Session` | A bounded execution context anchoring the Visible Field. Groups Tasks and tracks runtime state. |

**Task Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `intent` | `string` | The original request or goal. |
| `complexity_class` | `enum(trivial, simple, moderate, complex, heavy)` | Determines routing to SLM vs frontier model. |
| `status` | `enum(pending, authorized, routing, executing, guarding, crystallizing, completed, failed)` | Full lifecycle state machine. |
| `hardware_target` | `enum(local_mlx, remote_frontier, hybrid)` | Assigned by Job Router. |
| `token_cost` | `i64` | Actual tokens consumed. |
| `created_at` | `timestamp` | When the intent was received. |
| `completed_at` | `timestamp` | When the task reached terminal state. |

**Session Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `started_at` | `timestamp` | Session creation time. |
| `token_budget` | `i64` | Maximum tokens allowed for this session. |
| `tokens_consumed` | `i64` | Running total. |
| `active_persona_id` | `uuid` | The Persona operating in this session. |
| `visible_field_snapshot` | `json` | Serialized record of what was preloaded into context. |
| `status` | `enum(active, suspended, completed, evicted)` | Session lifecycle. |

---

## 3. Relationship Edges

### 3.1 Identity & Governance Edges (ReBAC)

| Edge | Direction | Description |
|------|-----------|-------------|
| `MEMBER_OF` | User -> Team, Team -> Tenant | Organizational hierarchy. Permissions can inherit upward. |
| `ACTS_AS` | User -> Persona | 1:many identity delegation. A User can switch between Personas. |
| `BELONGS_TO` | Persona -> Tenant | Tenant isolation for Personas. |

### 3.2 Access Control Edges (ReBAC)

| Edge | Direction | Description |
|------|-----------|-------------|
| `CAN_READ` | Persona/Team -> Memory_Node/Document | Read access to data. |
| `CAN_WRITE` | Persona/Team -> Memory_Node/Document | Write/modify access to data. |
| `CAN_EXECUTE` | Persona -> Tool/Skill | Permission to invoke a capability. |
| `DENY_READ` | Persona/Team -> Memory_Node/Document | Explicit read denial. Overrides any `CAN_READ`. |
| `DENY_WRITE` | Persona/Team -> Memory_Node/Document | Explicit write denial. Overrides any `CAN_WRITE`. |
| `DENY_EXECUTE` | Persona -> Tool/Skill | Explicit execution denial. Overrides any `CAN_EXECUTE`. |

**ReBAC resolution rule:** When evaluating access, traverse: Persona -> direct edges, then Persona -> Team (via reverse `ACTS_AS` + `MEMBER_OF`) -> Team edges. First explicit `DENY` wins. Otherwise, any `ALLOW` grants access.

### 3.3 AP2 Transaction Edges

| Edge | Direction | Description |
|------|-----------|-------------|
| `AUTHORIZED_BY` | PaymentMandate -> IntentMandate | Links a specific transaction to its budget envelope. |
| `RECEIPTED_BY` | PaymentReceipt -> PaymentMandate | Links the audit trail to its transaction. |

### 3.4 Execution Edges

| Edge | Direction | Description |
|------|-----------|-------------|
| `INITIATED_BY` | Task -> Persona | Who triggered this task. |
| `GOVERNED_BY` | Task -> IntentMandate | Which mandate authorizes this task. |
| `PRODUCED` | Task -> Memory_Node | The crystallization link: what knowledge was created. |
| `SCOPED_TO` | Session -> Persona | Which Persona is operating in this session. |
| `CONTAINS` | Session -> Task | Groups tasks within a session. |
| `LOADED` | Session -> Memory_Node | What was preloaded into the Visible Field (audit trail). |

### 3.5 Cognitive & Knowledge Edges

| Edge | Direction | Description |
|------|-----------|-------------|
| `DEPENDS_ON` | Any -> Any | Functional dependency (tool prerequisites, skill composition). |
| `USES` | Skill -> Tool | Which tools a skill requires. |
| `SUPPORTS` | Memory -> Memory | Strengthens a claim. Increases target confidence_score. |
| `EXTENDS` | Memory -> Memory | Adds detail or context to existing knowledge. |
| `CONTRADICTS` | Memory -> Memory | Flags conflicting information for the Defensive Evolution Engine. |
| `SUPERSEDES` | Memory -> Memory | Explicitly deprecates stale facts. Sets target confidence_score toward zero. |

---

## 4. Constraints & Invariants

### 4.1 Tenant Isolation
- Every node MUST have a `tenant_id`.
- Cross-tenant edges are forbidden. All graph traversals are scoped to a single Tenant.

### 4.2 AP2 Budget Integrity
- `IntentMandate.budget_spent` MUST never exceed `IntentMandate.budget_limit`.
- A `PaymentMandate` can only be created if `AUTHORIZED_BY` points to an IntentMandate with sufficient remaining budget.
- `PaymentReceipt` nodes are append-only and immutable after creation.

### 4.3 Memory Lifecycle
- `Working_Memory` nodes are evicted when their parent Session reaches `completed` or `evicted` status, unless explicitly promoted to `Episodic_Memory`.
- `confidence_score` decays according to the Ebbinghaus forgetting curve: `confidence = initial * e^(-t / stability)`, where `t` is time since `last_reinforced_at` and `stability` is tier-dependent.
- A Memory node with `confidence_score` below a configurable threshold (`0.1` default) is eligible for garbage collection.

### 4.4 ReBAC Evaluation Order
1. Check direct Persona edges.
2. Traverse `ACTS_AS` (reverse) to User, then `MEMBER_OF` to Teams, then check Team edges.
3. First explicit `DENY` at any level terminates with denial.
4. Any `ALLOW` found grants access.
5. No matching edge = implicit deny.

### 4.5 Governance Rule Enforcement
- Every state-changing operation (node creation, edge creation, Task state transition, AP2 debit) MUST be checked against all active `GovernanceRule` nodes whose `applies_to` matches the affected entity.
- A `critical` severity violation immediately aborts the operation, freezes the acting Persona, and creates a `VIOLATED_BY` edge for audit.
- An `enforced` severity violation aborts the operation and logs the violation.
- An `advisory` severity violation logs the violation but allows the operation to proceed.
- GovernanceRule evaluation MUST complete before the operation commits (synchronous enforcement).

### 4.6 Task State Machine
```
pending -> authorized -> routing -> executing -> guarding -> crystallizing -> completed
                                                                           -> failed
```
- Only the Governance Gatekeeper can transition `pending -> authorized`.
- Only the Job Router can transition `authorized -> routing -> executing`.
- Only the Behavioral Firewall can transition `executing -> guarding`.
- Only the Feedback Router can transition `guarding -> crystallizing -> completed`.
- Any component can transition to `failed` with a reason.

---

## 5. Technology Decision: PostgreSQL + Graph Extension

### Rationale
- PostgreSQL as the storage engine provides ACID transactions, mature tooling, and the ability to run on local hardware (sovereignty requirement).
- Use Apache AGE (A Graph Extension) or equivalent to add Cypher-compatible graph query support on top of PostgreSQL, giving us both relational integrity and graph traversal performance.
- This avoids vendor lock-in to a standalone graph database while maintaining the ability to perform complex ReBAC traversals efficiently.

### Schema Strategy
- Each node type maps to a PostgreSQL table with typed columns for its attributes.
- Edges are stored in a unified `edges` table with `source_id`, `target_id`, `edge_type`, `tenant_id`, and `metadata` (JSONB).
- Apache AGE provides the graph query layer for multi-hop ReBAC traversals and knowledge graph navigation.
- All tables are partitioned by `tenant_id` for isolation and performance.

---

## 6. Open Questions (To Resolve During Implementation)

1. **Edge metadata:** Should edges carry attributes beyond type? (e.g., `CAN_READ` with `granted_at`, `expires_at`, `granted_by`)
2. **Temporal versioning:** Should we implement bitemporal tables (valid_time + transaction_time) for full auditability from day one, or add it later?
3. **Graph query performance:** At what scale do we need dedicated graph indexes vs. relying on AGE's default behavior?
4. **Multi-region:** Is Tenant isolation purely logical (same database) or physical (separate schemas/databases) at launch?

---

## 7. Success Criteria

The schema is correct when:

1. A Persona can be created, linked to a User via `ACTS_AS`, and granted `CAN_EXECUTE` on a Tool — all within a single Tenant boundary.
2. A ReBAC query can determine in <10ms whether a Persona has access to a Memory node, traversing Team memberships.
3. An IntentMandate can be created with a budget, a PaymentMandate can debit it, and the budget constraint holds under concurrent access.
4. A Task can flow through the full state machine (`pending` -> `completed`), producing a Memory node via `PRODUCED` and a PaymentReceipt via `RECEIPTED_BY`.
5. Memory nodes decay correctly over time, and garbage collection removes nodes below the confidence threshold.
6. A GovernanceRule can be created, linked via `ENFORCES` to a node type, and when violated, the operation is blocked and a `VIOLATED_BY` audit edge is created.
7. The system can list all active GovernanceRules for a given node type and evaluate them synchronously before committing any state change.
