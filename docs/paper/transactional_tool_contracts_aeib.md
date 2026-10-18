# Transactional Tool Contracts for Parallel AI Agents: Eliminating Late-Commit Duplicates and Parallel Budget Anomalies via Out-of-Process TCC and Three-State Wire Finality

**Authors:** SovereignNexus Architecture Group  
**Target Tracks:** VLDB / SIGMOD (Industrial Track) &bull; EuroSys / SoCC (Systems & Distributed State)  
**Status:** Academic Manuscript & Systems Architecture Blueprint (October 2026)  
**Artifact Codebase:** `src/sqlite_acid_tcc_boundary.py`, `tests/test_tcc_parallel_acid_vs_base_anomalies.py`, `tools/measure_parallel_economics.py`  
**Epistemic Notice:** All experimental measurements reported herein are evaluated under the stated model within reproducible, controlled test environments.

---

## Abstract

Modern autonomous agent frameworks increasingly deploy parallel subagents to execute complex multi-step workflows across external microservices and Model Context Protocol (MCP) tool endpoints. However, recent empirical audits demonstrate that unconstrained agentic concurrency triggers catastrophic system failures: Trofimov & Novikov's census of 98,291 MCP tools (*arXiv:2609.15397*) cataloged the **Parallel Budget Overrun Anomaly**, where parallel workers overcommit budgets across non-compensatable actions, while Jiapeng Li's 25,930-episode study (*arXiv:2609.29095*) established **Proposition 1**, proving that downstream write delays ($\delta$) and NoSQL eventual-consistency read-replica lag ($\lambda$) cause "verify-then-retry" agents to duplicate external mutations in 56%–74% of runs. Concurrently, Fudan University's 2,124-run concurrency evaluation (*arXiv:2610.10263*) revealed that native parallel swarms degrade pass rates by up to -11.9% while multiplying token consumption by 1.41x–3.31x across 28 distinct concurrency failure patterns.

While recent literature proposes "Semantic ACID" (*arXiv:2608.13900*) via local workspace rollbacks, local snapshots cannot roll back irreversible external mutations (e.g., payment transfers, non-refundable reservations, infrastructure deletions). In this paper, we present the **Agent Execution Integrity Boundary (AEIB)**, an out-of-process Layer 3 execution coordinator that brings 40 years of distributed database principles to parallel agent systems. AEIB introduces:
1. **Station 1 Pre-Dispatch Try-Confirm-Cancel (TCC) Escrow:** Serializes parallel subagent budget reservations in a single SQLite `BEGIN IMMEDIATE` ACID transaction before opening external network sockets, eliminating parallel budget leakage.
2. **Station 2 Visibility-Lag Fencing (`t_reconcile >= t_dispatch + delta_max + lambda_max`):** Replaces naive verification retries with an `EFFECT_INDETERMINATE` wire latch that halts re-dispatches until the downstream replication boundary elapses, defeating Proposition 1.
3. **Structured Concurrency Contracts:** Combines disjoint write-set enforcement ($A_i \cap A_j = \emptyset$) with $\le 250$-word saliency-folded JSON receipts, preventing inter-agent context clobbering.

Evaluated across reproducible, zero-mock test suites, AEIB eliminates 100% of irrecoverable non-refundable budget losses in parallel overrun scenarios, blocks 100% of duplicate mutations across simulated NoSQL replication lag windows, and reduces context overhead by over 60% compared to unconstrained peer-to-peer swarms.

---

## 1. Introduction: The Agent-Microservice Boundary Crisis

The evolution of generative AI agents has transitioned rapidly from single-turn conversational assistance to autonomous distributed actuation. Frameworks such as OpenCode 2.0, Claude Code, OpenAI Codex, and Kimi Code orchestrate multi-agent swarms that parallelize tasks across database connectors, cloud APIs, and Model Context Protocol (MCP) servers.

However, AI framework design has largely ignored four decades of distributed systems lessons. When agents interact with stateful microservices, they reproduce the exact anomalies that plagued the transition from monolithic relational databases to distributed NoSQL architectures in 2010–2020:

1. **Non-Compensatable Actions Shatter Saga Patterns:** Distributed transaction patterns like Saga rely on compensating transactions ($C_i$) to undo failed steps ($T_i$). When parallel subagents execute irreversible operations—such as booking a non-refundable airline ticket or initiating an external SEPA wire transfer—no compensating transaction exists. If an accompanying parallel step fails, the workflow aborts, leaving un-recoverable financial leakage (*arXiv:2609.15397*).
2. **Eventual Consistency and Late-Commit Illusion (Proposition 1):** In distributed microservices, writes commit with latency $\delta$, and read replicas synchronize with lag $\lambda$. When an agent encounters an HTTP 504 gateway timeout, naive frameworks instruct the model to "verify state before retrying." Reading from a lagging read replica at $t < \delta + \lambda$ returns `absent`, leading the model to assume the mutation never executed and trigger a duplicate dispatch. Li (*arXiv:2609.29095*) proved that this defect is structural: in 90% of duplicate episodes, the agent's LLM supervisor reports the task as a clean success.
3. **Unstructured Concurrency Chaos:** Uncoordinated agent spawning creates combinatorial failure surfaces ($E = \frac{N(N-1)}{2}$), where subagents overwrite shared interfaces and drift into recursive delegation loops (*arXiv:2610.10263*).
4. **Credential Harvest in Exploited Runtimes:** Real-world compromises—including CVE-2026-33017 (unauthenticated remote code execution in Langflow) and CVE-2025-67644 (checkpoint SQL injection)—demonstrate that attackers routinely exploit agent runtimes to harvest downstream API keys from `.env` files and process memory.

AEIB resolves these crises not by adding more prompt engineering, but by establishing a deterministic, out-of-process **Layer 3 Transactional Boundary**.

---

## 2. Related Work: Semantic ACID vs. Wire Finality

### 2.1 The Limits of "Semantic ACID" (arXiv:2608.13900)
Tsinghua University's `ACID-Agent` (*Sun et al., August 2026*) formalized "Semantic ACID" for data-lake exploration, defining Semantic Atomicity, Semantic Consistency, Semantic Isolation, and Semantic Durability on append-only workspaces and local write-ahead logs (`KramaBench`).

While `ACID-Agent` is a significant milestone for local data analysis, its model fundamentally assumes that **all side effects are compensatable within local workspaces**. It explicitly leaves open the challenge of **irreversible external mutations across distributed microservices**. Once an HTTP packet leaves the host and lands on a banking clearinghouse or cloud infrastructure hypervisor, local snapshot rollbacks are powerless. AEIB directly occupies this non-compensatable domain.

### 2.2 Concurrency Pitfalls & Swarm Pathologies (arXiv:2610.10263, arXiv:2602.02276)
Fudan University (*Li et al., October 2026*) evaluated 2,124 runs across Codex, Claude Code, and Kimi Code, identifying 28 concurrency failure patterns that reduce benchmark pass rates by -11.9% while inflating token costs by 1.41x–3.31x. Concurrently, Moonshot AI's PARL study (*arXiv:2602.02276*) mathematically formalized **Critical Steps**:
$$\text{CriticalSteps} = \sum_{t=1}^{T} \left( S_{\text{main}}^{(t)} + \max_i S_{\text{sub}, i}^{(t)} \right)$$
and identified **Spurious Parallelism**, where subagents burn tokens without reducing critical path latency or producing verified outputs.

---

## 3. The AEIB Architecture: Out-of-Process TCC & Visibility-Lag Fencing

AEIB decouples the probabilistic reasoning of LLM agents from the deterministic mechanics of transaction finality. It operates across three specialized stations:

```
+-----------------------------------------------------------------------------------------+
|                                    HOST RUNTIME                                         |
|                                                                                         |
|  [ Untrusted Parallel Subagents ]                      [ AEIB Out-of-Process Boundary ]  |
|  +------------------------------+                      +-----------------------------+  |
|  | Subagent 1: Non-Refund Flight|                      | Station 1: Pre-Socket TCC   |  |
|  | Subagent 2: Hotel Booking    | -- Try Reservation-> | - SQLite BEGIN IMMEDIATE    |  |
|  | Subagent 3: Transport Ticket |                      | - All-or-Nothing Budget Escrow|
|  +------------------------------+                      +--------------+--------------+  |
|                                                                       |                 |
|                                                                       v                 |
|                                                        +-----------------------------+  |
|                                                        | Station 2: Wire Latch       |  |
|                                                        | - EFFECT_INDETERMINATE Latch|  |
|                                                        | - Visibility-Lag Fence      |  |
|                                                        |   (t >= t_0 + delta + lambda)|
|                                                        | - Single-Flight Probe: 1    |  |
|                                                        +--------------+--------------+  |
|                                                                       |                 |
+-----------------------------------------------------------------------|-----------------+
                                                                        | Outbound Wire
                                                                        v (CAID Bound)
                                                         +-----------------------------+
                                                         | Downstream Microservices    |
                                                         | (NoSQL / Payment Rails)     |
                                                         +-----------------------------+
```

### 3.1 Station 1: Pre-Socket Try-Confirm-Cancel (TCC) Escrow
To eliminate the Parallel Budget Overrun Anomaly (*arXiv:2609.15397*), AEIB implements Alibaba Seata-style TCC within a local SQLite database configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and full durability synchronization (`PRAGMA synchronous=FULL`).

Before any subagent is permitted to open an external socket, all parallel branches must submit their planned mutation amounts in an atomic `tcc_try_reserve_all_or_nothing` call executed under `BEGIN IMMEDIATE`. The database engine evaluates:
$$\text{reserved\_minor} + \text{confirmed\_minor} + \sum_{i} \text{requested\_minor}_i \le \text{budget\_minor}$$
If the cumulative sum exceeds the workflow ceiling, the entire batch is rejected with `HALT_TCC_PRE_COMMIT_BUDGET_INVARIANT_VIOLATION` before any external HTTP connection is initialized. Zero external mutations occur; zero non-refundable capital leaks.

### 3.2 Station 2: Visibility-Lag Fencing & Three-State Wire Finality
To defeat Proposition 1 (*arXiv:2609.29095*), Station 2 replaces binary success/failure assumptions with three-state transport finality: `CONFIRMED`, `REFUTED`, and `EFFECT_INDETERMINATE`.

When an outbound call experiences a network partition, timeout (HTTP 504), or connection reset:
1. **Latching:** Station 2 latches the operation into `EFFECT_INDETERMINATE`. The reserved funds remain locked in the TCC escrow journal (`AT58`), preventing timeout-smurfing.
2. **The Visibility-Lag Fence:** Let $\delta_{\text{max}}$ be the maximum write-commit delay of the primary database and $\lambda_{\text{max}}$ be the maximum eventual-consistency replication lag of read replicas. AEIB enforces the fence condition:
   $$t_{\text{reconcile}} \ge t_{\text{dispatch}} + \delta_{\text{max}} + \lambda_{\text{max}}$$
   Any attempt by the agent to query a read replica or trigger a retry while $t < t_{\text{dispatch}} + \delta_{\text{max}} + \lambda_{\text{max}}$ is intercepted and blocked with `BLOCKED_VISIBILITY_LAG_FENCE_ACTIVE`.
3. **Authoritative Single-Flight Probe:** Once the fence elapses, Station 2 executes a single probe (`ProbeBudget: 1`) bound to the Content-Addressable Identifier (`CAID`):
   $$\text{CAID} = \text{sha256}(\text{encode\_jcs}(\text{action\_payload}))$$
   If the downstream primary confirms settlement, state transitions to `CONFIRMED` (`RECONCILED_ALREADY_COMMITTED_NO_RETRY`). If the primary confirms the mutation never arrived, state transitions to `CANCELLED_REFUTED`, releasing the escrow.

### 3.3 Structured Concurrency & Disjoint Write Partitions
To eliminate the 28 failure patterns of unconstrained dynamic concurrency (*arXiv:2610.10263*), AEIB enforces:
- **Move 1 (Disjoint Write-Sets):** Parallel subagents execute in isolated directories/worktrees where $A_i \cap A_j = \emptyset$.
- **Move 2 (Contract Freeze):** Before worker fan-out, interfaces and schemas are canonicalized into an RFC 8785 JCS digest (`spec_caid`).
- **Move 3 (Saliency-Folded Hand-Back):** Subagents return strictly bounded $\le 250$-word JSON receipts, collapsing parent context accumulation by over 60%.
- **Move 4 (Temporal Leases):** Subagents operate under a 90-second heartbeat lease, reaping stalled workers automatically.

---

## 4. Empirical Evaluation & Runnable Proofs

All benchmarks are implemented in pure Python stdlib and SQLite in [`tests/test_tcc_parallel_acid_vs_base_anomalies.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tests/test_tcc_parallel_acid_vs_base_anomalies.py) and [`tools/measure_parallel_economics.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/measure_parallel_economics.py), verified under zero-mock compliance enforcers.

### 4.1 Benchmark 1: Defeating the Parallel Budget Overrun Anomaly (arXiv:2609.15397)
- **Workload:** An agent workflow with a strict €1,500 budget spawns two parallel subagents: Subagent 1 books a €900 non-refundable flight; Subagent 2 books a €700 refundable hotel. Total requested: €1,600.
- **Naive Parallel + Saga Baseline:** Both workers inspect initial budget (€1,500), determine €900 $\le$ €1,500 and €700 $\le$ €1,500, and fire external tool dispatches concurrently. Both succeed locally. The workflow detects budget overrun (€1,600 > €1,500) and triggers Saga rollback. The hotel is cancelled, but the non-refundable flight cannot be undone. **Result: €900 leaked damage.**
- **AEIB SQLite TCC Boundary:** Both requests are evaluated inside `tcc_try_reserve_all_or_nothing` under `BEGIN IMMEDIATE`. Because $900 + 700 = 1600 > 1500$, the ACID transaction executes a rollback. Zero external HTTP requests fire. **Result: €0 leaked damage.**

### 4.2 Benchmark 2: Defeating Proposition 1 Late Commit & Replica Lag (arXiv:2609.29095)
- **Workload:** Primary database commits with delay $\delta = 2s$; read replica lags by $\lambda = 3s$ ($\delta + \lambda = 5s$). An outbound payment times out at $t = 1s$.
- **Naive Verify-Then-Retry Agent:** At $t = 2s$, the agent queries the read replica, which returns `absent`. Believing the transaction dropped, the agent retries without an idempotency fence. When the primary's late commit finishes at $t = 2.5s$, the second request also commits, producing a duplicate charge.
- **AEIB Outbox + Visibility-Lag Fence:** At $t = 2s$, the agent attempts to reconcile. Station 2 detects $t < t_0 + 5s$ and blocks the inquiry with `BLOCKED_VISIBILITY_LAG_FENCE_ACTIVE`. At $t = 6s$, after the replication window elapses, the single-flight probe queries the primary, discovers the commit succeeded, and marks `CONFIRMED` without retrying. **Result: Zero duplicate charges.**

### 4.3 Benchmark 3: Multi-Threaded Stress Test
We subjected `SqliteAcidTccBoundary` to a 10-thread concurrent burst where each thread attempted a €250 reservation against a €1,000 budget:
- Exactly 4 threads succeeded ($4 \times 250 = 1000$).
- Exactly 6 threads were deterministically rejected with `HALT_TCC_PRE_COMMIT_BUDGET_INVARIANT_VIOLATION`.
- Final reserved budget was exactly €1,000. Zero race conditions, zero negative balances.

### 4.4 Benchmark 4: Observability & Token Economics (ParaGUIBench, Moonshot PARL)
Using [`tools/measure_parallel_economics.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/measure_parallel_economics.py) on a 4-workstream task ($4 \times 8 = 32$ steps, 80k base context):
- **Critical-Path Step Reduction ($S$):** Dropped from 32 steps (Serial) and 36 steps (Mesh Swarm) to 10 critical-path steps ($S = 3.20\times$ speedup).
- **Total Billed Tokens:** Dropped from 3,880,000 tokens (Serial) and 8,342,000 tokens (Mesh Swarm) to 1,506,400 tokens (61.2% reduction).
- **Human Review Load:** Dropped from 80,000 transcript tokens to 1,900 tokens (1 frozen contract + 4 compact receipts, a 97.6% reduction).

---

## 5. Limitations & Bounded Trust Model

In compliance with strict epistemic standards, AEIB defines bounded behavioral envelopes under the stated model:
1. **Target Semantics:** AEIB relies on downstream targets providing idempotent inquiry endpoints (e.g., `GET /charges/{id}`). If a target API is non-atomic and executes partial writes without idempotency support, the boundary halts fail-closed but cannot repair target-side corruption.
2. **Key Custody:** Private signing keys residing in host memory can be exfiltrated if the host kernel is compromised. Production deployments require hardware HSM or Cloud KMS integration.
3. **Availability vs. Safety:** AEIB prioritizes safety over availability; network ambiguity results in intentional fail-closed latching until verified reconciliation completes.

---

## 6. Conclusion

The "AI Execution Gap" is fundamentally a distributed transactions problem. By replacing post-hoc Saga rollbacks with pre-dispatch SQLite TCC escrow, and eliminating Proposition 1 read-lag duplicates with visibility-lag fencing, AEIB provides the first deterministic execution boundary for parallel AI agents.

---

### References

1. Zhaoyan Sun, X. Wang, Guoliang Li. *Agentic Transaction: Towards ACID-Compliant Agent Systems.* arXiv:2608.13900, August 2026.
2. A. Trofimov, B. Novikov. *When Tool Calls Succeed but Workflows Fail: Anomalies at the Agent–Tool Boundary.* arXiv:2609.15397, September 2026.
3. Jiapeng Li. *Where Does Exactly-Once Live? Model, Harness, and Tool-Contract Effects on Duplicate Side Effects in LLM Agents.* arXiv:2609.29095, September 2026.
4. Han Li, HanHaoNing Li, Ziqian Jiang, Yiling Lou. *When Sub-Agents Work in Parallel: The Promises and Pitfalls of Dynamic Concurrency.* arXiv:2610.10263, October 2026.
5. Moonshot AI. *Kimi K2.5 / K2.6 Agent Swarm & Parallel-Agent Reinforcement Learning (PARL).* arXiv:2602.02276, 2026.
6. *TrajAudit & The RootSE Benchmark: Root-Cause Localization in Failed Agent Trajectories.* arXiv:2605.26563, May 2026.
7. Yuxi Chen et al. *Token Economics for LLM Agents: A Dual-View Study.* arXiv:2605.09104, May 2026.
8. *ParaGUIBench: Benchmarking Parallel Multi-Agent Architectures.* arXiv:2607.22689, July 2026.
