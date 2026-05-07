# Sovereign Multi-Agent OS — Three-Plane Architecture

**Date:** 2026-05-07
**Status:** Foundational
**Scope:** Complete system architecture for the Sovereign Intelligence Substrate Standard (SISS)

---

## 1. Operator Plane — Mission Control (AoE)

**Purpose:** Own all sessions, terminals, worktrees, and containers.
**Implementation:** Agent of Empires (AoE).

### Responsibilities
- Create/manage tmux sessions
- Create/manage git worktrees (one per agent)
- Launch Docker sandboxes
- Provide TUI + Web Dashboard
- Enable remote access (Tailscale/Cloudflare)
- Display agent status, diffs, logs, approvals

### Non-Responsibilities
- No governance
- No model selection
- No memory
- No safety logic

**AoE = Operator Plane. It is the cockpit, not the brain.**

---

## 2. Cognitive Plane — SISS (The Brain)

**Purpose:** Govern all intelligence, safety, memory, and evolution.

### Components (Implementation Status)

| Component | Crate | Status |
|-----------|-------|--------|
| Gatekeeper (AP2 + ReBAC authorization) | `siss-gatekeeper` | Done |
| AP2 mandates (capability + spend envelopes) | `siss-graph-core` (invariant/ap2) | Done |
| Knowledge Graph Schema | `siss-graph-core` + `siss-graph-db` | Done |
| Context Cartography (Visible Field) | `siss-context-cartography` | Done |
| Rust Job Router (local SLM vs cloud LLM) | `siss-job-router` | Done |
| Behavioral Firewall (runtime safety) | `siss-behavioral-firewall` | Done |
| Memory Lifecycle (crystallization, decay) | `siss-feedback-router` + `siss-graph-core` | Done |
| Feedback Router (telemetry ingestion) | `siss-feedback-router` | Done |
| Persona Doctrine (role-bound behavior) | — | Future |
| MeshFlow (multi-agent trajectories) | — | Future |
| Defensive Evolution Engine (self-hardening) | — | Future |
| siss-agent-shell (session adapter) | — | Future |

### Session Adapter (siss-agent-shell)
- Runs inside each AoE tmux/Docker session
- Authenticates with Gatekeeper
- Enforces AP2 + ReBAC
- Routes all model calls via Job Router
- Emits telemetry to Feedback Router

**SISS = Cognitive Plane. It is the governed intelligence substrate.**

---

## 3. Skill Plane — MCP Tool Packs (Execution)

**Purpose:** Provide bounded, stateless capabilities.

### Implementation
- DeepSec scanners
- Repo tools
- CI/test runners
- Build systems
- Infra readers (read-only)

### Rules
- Exposed via MCP
- Strict schemas
- No hidden side effects
- Operate only inside the AoE worktree
- Governed by AP2 + Gatekeeper

**Skill Plane = Execution Plane. Tools do work; SISS governs them.**

---

## 4. Core Invariants

1. **Sovereign by Default:** All cognition runs on local SLMs unless AP2 explicitly allows cloud.
2. **Personas as System Services:** Each persona is a versioned, restartable cognitive service.
3. **Defenses as Packages:** Firewall rules, AP2 profiles, and retrieval policies evolve like OS security updates.
4. **Strict Plane Separation:** Operator Plane != Cognitive Plane != Skill Plane. No cross-plane leakage.
5. **Meaningful Human Control:** AoE dashboard + Auditor validation ensure humans remain in command.

---

## 5. Current Implementation Map

```
sovereign-nexus/
  crates/
    siss-graph-core/          # Foundation: 16 node types, 27 edges, 6 invariants (58 tests)
    siss-graph-db/            # Persistence: PostgreSQL + Apache AGE migrations, 6 repos
    siss-gatekeeper/          # Cognitive Plane: authorization pipeline (15 tests)
    siss-job-router/          # Cognitive Plane: task routing + dispatch (13 tests)
    siss-context-cartography/ # Cognitive Plane: Visible Field assembly (11 tests)
    siss-behavioral-firewall/ # Cognitive Plane: output validation (23 tests)
    siss-feedback-router/     # Cognitive Plane: scoring + crystallization (11 tests)
```

**Total: 7 crates, 86 Rust source files, 131 tests, 0 clippy warnings**

### Value Loop Coverage

```
pending → [Gatekeeper] → authorized → [Router] → routing → executing
    ↑                                                          ↓
    └── completed ← [Feedback] ← crystallizing ← [Firewall] ← guarding
```

The complete sense-decide-act-learn loop is implemented.
The Cognitive Plane core is built.
The Operator Plane and Skill Plane are the next frontiers.
