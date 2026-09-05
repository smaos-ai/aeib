# Sovereign Multi-Agent OS — Three-Plane Architecture

**Date:** 2026-05-07
**Status:** Foundational
**Scope:** Complete system architecture for the Sovereign Intelligence Substrate Standard (SISS)

---

## Implementation Contract

```
AoE runs the sessions.
SISS governs the intelligence.
MCP tools execute the work.
Everything else is forbidden.
```

---

## What This Architecture Replaces

This is a full-stack replacement, not an incremental upgrade.

| Legacy Pattern | SMAOS Replacement |
|---|---|
| Python orchestrators | AoE Operator Plane |
| Ad-hoc agent shells | siss-agent-shell |
| Mixed governance | AP2 + ReBAC Gatekeeper |
| Tool chaos | MCP Skill Plane |
| Memory hacks | SISS Memory Lifecycle |
| Safety patches | Behavioral Firewall |
| Manual tuning | Defensive Evolution Engine |
| Model sprawl | Rust Job Router |
| Terminal chaos | AoE tmux + worktrees + Docker |
| Custom CLIs | AoE TUI + Web Dashboard |
| Prompt-only governance | AP2 mandates + GovernanceRules |
| Unstructured memory | Knowledge Graph + Ebbinghaus decay |
| Unsafe tool calling | MCP strict schemas + Gatekeeper |
| Manual model selection | ComplexityBasedStrategy routing |
| Static safety rules | Configurable FirewallChecker patterns |
| Ad-hoc telemetry | Feedback Router + MeshFlow |

---

## 1. Operator Plane — Mission Control (AoE)

**Purpose:** Own all sessions, terminals, worktrees, and containers.
**Implementation:** Agent of Empires (AoE).

### Owns
- tmux session topology
- git worktree isolation (one per agent)
- Docker sandboxing
- Remote dashboard (Tailscale/Cloudflare)
- Operator approvals
- Session persistence
- Agent status, diffs, logs display

### Replaces
- OpenSwarm
- Custom CLIs
- Terminal multiplexing scripts
- Manual worktree management
- Ad-hoc Docker setups

### Non-Responsibilities
- No governance
- No model selection
- No memory
- No safety logic

**AoE = Operator Plane. It is the cockpit, not the brain.**

---

## 2. Cognitive Plane — SISS (The Brain)

**Purpose:** Govern all intelligence, safety, memory, and evolution.

### Owns
- AP2 mandates (capability + spend envelopes)
- ReBAC authorization (graph-based access control)
- Persona doctrine (role-bound behavior)
- MeshFlow trajectories (multi-agent coordination)
- Behavioral Firewall (runtime safety)
- Memory lifecycle (crystallization, decay, supersession)
- Feedback Router (telemetry ingestion + quality scoring)
- Defensive Evolution Engine (self-hardening from violations)
- Rust Job Router (local SLM vs cloud LLM dispatch)

### Replaces
- Agent frameworks
- Prompt-only governance
- Unstructured memory
- Unsafe tool calling
- Manual model selection
- Static safety rules
- Ad-hoc telemetry

### Components (Implementation Status)

| Component | Crate | Status |
|-----------|-------|--------|
| Knowledge Graph Schema (16 nodes, 27 edges, 6 invariants) | `siss-graph-core` + `siss-graph-db` | Done |
| Gatekeeper (AP2 + ReBAC authorization pipeline) | `siss-gatekeeper` | Done |
| Context Cartography (Visible Field assembly) | `siss-context-cartography` | Done |
| Rust Job Router (complexity-based hardware dispatch) | `siss-job-router` | Done |
| Behavioral Firewall (budget, tool, content safety) | `siss-behavioral-firewall` | Done |
| Feedback Router (scoring + crystallization) | `siss-feedback-router` | Done |
| AP2 mandates + budget integrity | `siss-graph-core` (invariant/ap2) | Done |
| Memory decay (Ebbinghaus curve + GC) | `siss-graph-core` (invariant/memory) | Done |
| GovernanceRule enforcement | `siss-graph-core` (invariant/governance) | Done |
| Persona Doctrine (role-bound behavior constraints) | — | Future |
| MeshFlow (multi-agent trajectory logging) | — | Future |
| Defensive Evolution Engine (self-hardening) | — | Future |
| siss-agent-shell (session adapter for AoE) | — | Future |

### Session Adapter (siss-agent-shell)

The bridge between Operator Plane and Cognitive Plane:
- Runs inside each AoE tmux/Docker session
- Authenticates with Gatekeeper on session start
- Enforces AP2 + ReBAC on every action
- Routes all model calls through Job Router
- Passes output through Behavioral Firewall
- Emits telemetry to Feedback Router
- Crystallizes results into Knowledge Graph

**SISS = Cognitive Plane. It is the governed intelligence substrate.**

---

## 3. Skill Plane — MCP Tool Packs (Execution)

**Purpose:** Provide bounded, stateless capabilities.

### Owns
- DeepSec scanners
- Repo tools (git, file, search)
- CI/test runners
- Build systems
- Infra readers (read-only)

### Replaces
- Custom tool wrappers
- Unsafe shell commands
- Direct FS access
- Unbounded tool calls
- Mixed-responsibility agents

### Rules
- All tools exposed via MCP protocol
- Strict input/output schemas
- No hidden side effects
- Operate only inside the AoE worktree
- Every invocation governed by AP2 + Gatekeeper
- Tool usage audited via INITIATED_BY + PRODUCED edges

**Skill Plane = Execution Plane. Tools do work; SISS governs them.**

---

## 4. Core Invariants — The Dramatic Innovations

### A. Sovereign by Default
All cognition runs on local SLMs (Rapid-MLX / Apple GPU) unless AP2 explicitly allows cloud escalation. The `ComplexityBasedStrategy` routes Trivial/Simple/Moderate locally. Only Complex/Heavy tasks touch frontier models.

### B. Personas as System Services
Each Persona is a versioned, restartable cognitive service with:
- Typed identity (HumanRole / AiAgent / SystemDaemon)
- ReBAC permission edges (CAN_READ, CAN_WRITE, CAN_EXECUTE)
- AP2 budget envelopes (IntentMandate → PaymentMandate → PaymentReceipt)
- Freeze capability (critical GovernanceRule violations freeze the Persona)
- Swarm support (spawned_by field for agent-spawned sub-agents)

### C. Defenses as Packages
Firewall rules (`ContentSafetyConfig`), AP2 profiles, GovernanceRules, and retrieval policies (`RetrievalConfig`) are all configurable data — not hardcoded logic. They evolve like OS security updates:
- New forbidden patterns added to ContentSafetyConfig without code changes
- New GovernanceRules inserted into the graph at runtime
- RetrievalConfig tuned per-tenant

### D. Strict Plane Separation
```
Operator Plane (AoE) != Cognitive Plane (SISS) != Skill Plane (MCP)
```
- AoE never makes governance decisions
- SISS never manages terminals or containers
- MCP tools never access memory or mandates directly
- Cross-plane communication only through defined interfaces (siss-agent-shell)

### E. Meaningful Human Control
- AoE dashboard shows all agent activity in real-time
- Operator approvals gate irreversible actions
- Auditor Persona validates governance compliance
- VIOLATED_BY edges create full audit trail
- PaymentReceipt chain provides tamper-proof transaction history

---

## 5. Current Implementation Map

```
sovereign-nexus/
  crates/
    siss-graph-core/          # Foundation: 16 node types, 27 edges, 6 invariants (58 tests)
    siss-graph-db/            # Persistence: PostgreSQL + Apache AGE, 4 migrations, 6 repos
    siss-gatekeeper/          # Cognitive: ReBAC + AP2 + GovernanceRule pipeline (15 tests)
    siss-job-router/          # Cognitive: complexity routing + Executor dispatch (13 tests)
    siss-context-cartography/ # Cognitive: Visible Field + Session management (11 tests)
    siss-behavioral-firewall/ # Cognitive: budget/tool/content safety checkers (23 tests)
    siss-feedback-router/     # Cognitive: scoring + crystallization (11 tests)
  docs/
    architecture/             # This document
    superpowers/
      specs/                  # Design specifications (Steps A-F)
      plans/                  # Implementation plans (Steps A-E)
```

**Total: 7 crates, 86 Rust source files, 131 tests, 0 clippy warnings, 32 commits**

### Value Loop (Complete)

```
pending → [Gatekeeper] → authorized → [Cartography] → Session created
                                            ↓
                                     [Job Router] → routing → executing
                                                                  ↓
completed ← [Feedback Router] ← crystallizing ← [Firewall] ← guarding
```

### Task FSM (Complete)

```
pending → authorized → routing → executing → guarding → crystallizing → completed
                                                                      → failed (from any state)
```

---

## 6. Next Frontiers

| Priority | Component | Plane | What It Unlocks |
|----------|-----------|-------|-----------------|
| 1 | `siss-agent-shell` | Cognitive | Makes the brain usable from AoE sessions |
| 2 | AoE integration | Operator | tmux + worktrees + Docker + dashboard |
| 3 | MCP Tool Packs | Skill | Real tool execution (git, fs, CI) |
| 4 | Real Executors | Cognitive | Rapid-MLX + frontier API integration |
| 5 | Persona Doctrine | Cognitive | Role-bound behavior constraints |
| 6 | MeshFlow | Cognitive | Multi-agent trajectory coordination |
| 7 | AP2 refund + reinforcement | Cognitive | Full economic + learning flywheel |
| 8 | Defensive Evolution Engine | Cognitive | Self-hardening from violations |
