# WAVE 2 INITIALIZATION — PHASE 32 A2UI PAYLOAD
**Date:** May 20, 2026  
**Status:** READY FOR AGENT DISPATCH  
**Document Version:** 1.0  

---

## 🎯 EXECUTIVE SUMMARY

You are inheriting Phase 32 (A2UI Payload) at a critical juncture:
- ✅ A2UI schema is **complete and committed** to main (18 component primitives)
- ✅ NotebookLM cached artifacts are **being generated asynchronously**
- ❌ Cockpit renderer, validator, form handler, and integration tests are **NOT YET IMPLEMENTED**
- ⚠️ **Golden Rule:** Do NOT recreate worktrees. Create NEW task worktrees only if explicitly instructed.

Your mission: **Execute the 3-task Wave 2 sequence in parallel worktrees without file conflicts.**

---

## 📋 PHASE 32 GOAL (THE "ONE THING")

> **Enable agents to dynamically emit safe, declarative JSON-based UI components (18 primitives) via SSE → cockpit renders interactively → operator submits form → cockpit sends response back via SSE → agent receives structured data — with zero manual frontend engineering required.**

### Success Criteria
- [ ] Agent-side validator (pre-emit JSON validation) ✅ Cockpit-side renderer (HTML output for 18 components)
- [ ] Form handler (SSE bidirectional: cockpit ↔ agent)
- [ ] Integration tests (8 tests for full SSE loop)
- [ ] <200ms latency (agent emit → cockpit render)
- [ ] Zero clippy warnings, zero type errors

---

## 🏗️ WAVE 2 EXECUTION SEQUENCE

### **Task 1: Forms Handler** (Priority 2)
**Worktree:** `task1-a2ui-forms`  
**Owner:** Wave 2 Agent 1  
**Deliverable:** `crates/siss-cockpit/src/a2ui/form_handler.rs`

```rust
// FormSubmission capture from operator
// SSE response routing back to agent via Channels
// Validation against FormSubmission schema
```

**Blocker:** Must follow Cockpit Renderer output (Task 2)

---

### **Task 2: Cockpit Renderer** (Priority 1)
**Worktree:** `task2-a2ui-display`  
**Owner:** Wave 2 Agent 2  
**Deliverable:** `crates/siss-cockpit/src/a2ui/renderer.rs`

```rust
// Convert A2UIComponent JSON → HTML snippets
// Render all 18 primitives safely (fail-closed)
// Integrate into existing SSE stream handler
```

**Critical:** This unblocks Form Handler and Validator

---

### **Task 3: Agent-Side Validator** (Priority 3)
**Worktree:** `task3-a2ui-validator`  
**Owner:** Wave 2 Agent 3  
**Deliverable:** `crates/siss-agent-shell/src/a2ui/validator.rs`

```rust
// Pre-emit validation (fail-closed schema checks)
// Enforce 18-component primitive limit
// Catch malformed A2UIComponent JSON before SSE emit
```

**Dependency:** Must follow Task 2 (renderer confirms schema is valid)

---

## 📦 ARCHITECTURE (CONDENSED)

### **The Stack**
```
Agent (siss-dispatcher)
  ↓ emits A2UIComponent JSON
SSE Stream (AG-UI middleware)
  ↓ transports via typed events
Cockpit Renderer (siss-cockpit/a2ui/renderer.rs)
  ↓ HTML rendering (18 primitives)
Operator Interaction (HTML form)
  ↓ operator submits
Form Handler (siss-cockpit/a2ui/form_handler.rs)
  ↓ captures FormSubmission
SSE Response (back via Channels)
  ↓ sends to agent
Agent Validator (siss-agent-shell/a2ui/validator.rs)
  ↓ pre-emit safety gate
```

### **18 Component Primitives** (LOCKED)
Display (8): Text, Badge, Alert, Progress, Divider, Link, Tooltip, Breadcrumb  
Forms (6): Input, Textarea, Select, Checkbox, Radio, Button  
Layout (4): Card, Grid, Modal, Table

---

## ⚡ NOTEBOOKLM MCP INTEGRATION DOCTRINE V2

### **Cached Artifacts (Being Generated)**
These files are currently compiling in NotebookLM and will be injected into `docs/notebook-cache/`:

```
docs/notebook-cache/dependency_a2ui.md
docs/notebook-cache/error_a2ui.md
docs/notebook-cache/contract_a2ui.md
docs/notebook-cache/state_a2ui.md
```

### **How to Use Cached Artifacts**
```
/plan
REFERENCE: @docs/notebook-cache/contract_a2ui.md
TARGET: Task 2 (Cockpit Renderer)
CONSTRAINT: Code ONLY against mapped call sites.
OUTPUT: Unified diffs only.
```

**CRITICAL RULE:** If you need the same insight twice, use `USE CACHED: @docs/notebook-cache/<artifact>.md`. Do NOT re-query NotebookLM.

---

## 🚨 GOLDEN RULES (DO NOT VIOLATE)

### **Rule 1: Zero File Overlap**
Each worktree owns isolated files:
- `task1-a2ui-forms` → `crates/siss-cockpit/src/a2ui/form_handler.rs`
- `task2-a2ui-display` → `crates/siss-cockpit/src/a2ui/renderer.rs`
- `task3-a2ui-validator` → `crates/siss-agent-shell/src/a2ui/validator.rs`

**If you modify a file not in your list, you will cause merge conflicts.**

### **Rule 2: No Worktree Recreation**
If `task1-a2ui-forms` already exists, **DO NOT** run `git worktree add` again. You will corrupt the parallel execution.

### **Rule 3: Fail-Closed Validation**
Every A2UIComponent JSON payload MUST pass validation before emit. No exceptions.

### **Rule 4: Test Before Merge**
Run `cargo test -q` + `cargo check -q` in your worktree. All tests must pass. Zero clippy warnings.

### **Rule 5: Sequential Merge (Ordered)**
Merges happen in order:
1. Task 2 (Renderer) merges first
2. Task 1 (Form Handler) merges second
3. Task 3 (Validator) merges third

---

## 📊 CURRENT STATE (Inherited)

### **Main Branch**
```
✅ aed62d2 — Phase 32 Task 1: A2UI Schema Foundation
   └─ crates/siss-agent-shell/src/a2ui/schema.rs (147 LOC, 18 primitives)
   └─ crates/siss-agent-shell/src/a2ui/types.rs (16 LOC)
   └─ crates/siss-agent-shell/src/a2ui/mod.rs (5 LOC)
```

### **What's Missing**
```
❌ validator.rs (pre-emit validation)
❌ renderer.rs (A2UIComponent → HTML)
❌ form_handler.rs (operator submission capture)
❌ integration tests (8 E2E SSE tests)
❌ cockpit UI (JavaScript/HTML rendering)
```

### **Active Worktrees**
```
task1-a2ui-schema          [STALE - Phase 31 commit]
task1-foundation           [STALE - Phase 29 commit]
```

---

## 🔑 CRITICAL CONTEXT (Do NOT Ignore)

### **Context Cartography (Memory Model)**
- **Black Fog:** Unknown data (explore via tools)
- **Gray Fog:** Persistent memory (consolidated episodic/semantic/procedural)
- **Visible Field:** Active reasoning (attention budget governed)

Agents must manage context budget carefully. Use cached artifacts to reduce cognitive load.

### **RCE (Resumable Cognitive Execution)**
Approval gates pause agent execution for operator validation. A2UI components can trigger RCE pause points:
- Agent emits approval form (A2UI)
- Operator reviews + submits decision
- Agent resumes with FormSubmission payload

### **AP2 (Agent Payment Protocol)**
If your A2UI forms trigger financial actions, authorization uses cryptographic mandates. Not in scope for Phase 32, but understand the pattern.

---

## 🎬 NEXT AGENT: INITIALIZATION CHECKLIST

When you boot up as a Wave 2 agent:

- [ ] Read this entire document
- [ ] Fetch your assigned task (Task 1, 2, or 3)
- [ ] Check `docs/notebook-cache/` for cached artifacts
- [ ] Verify your worktree is clean (`git status`)
- [ ] Run `cargo check -q` to validate project state
- [ ] Implement your task (no file overlap!)
- [ ] Run `cargo test -q` + `cargo clippy -q`
- [ ] Create a unified diff (diffs only, no verbose output)
- [ ] Commit with clear message: `Phase 32 Task N: <description>`
- [ ] Wait for merge orchestration (DO NOT auto-merge)

---

## 📞 HANDOFF NOTES

**From the Cognitive Plane:**
- NotebookLM cached artifacts are **being generated right now**
- They will be available in Studio before you start coding
- Pull them into `docs/notebook-cache/` manually
- Use them to replace blind exploration (70% token savings)

**From the Operator Plane:**
- The Golden Rule of zero file overlap is **non-negotiable**
- If you violate it, merge conflicts will destroy parallel execution
- Reach out to the Cognitive Plane BEFORE you code if you're unsure

---

## 📎 REFERENCES

- **Phase 32 Specification:** `/PHASE_32_SPEC.md` (in project root)
- **NotebookLM Protocol:** `.claude/NOTEBOOKLM_PROTOCOL_TEMPLATES.yaml`
- **CLAUDE.md (Project Doctrine):** `/CLAUDE.md`
- **Architecture Spine:** `crates/siss-dispatcher/ARCHITECTURE.md`

---

## ✅ STATUS

**This document created:** May 20, 2026  
**A2UI Schema Status:** COMPLETE  
**Wave 2 Readiness:** READY FOR DISPATCH  
**Cognitive Plane:** STANDING BY  

**Awaiting:** NotebookLM artifact generation completion → manual pull into `docs/notebook-cache/`

---

**Next Agent: Your mission begins here. Good luck.**
