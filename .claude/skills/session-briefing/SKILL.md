# Session Briefing Skill — Auto-Context Assembly

**Invoked at:** Session start via `/session-briefing` OR auto-fired on entry  
**Purpose:** Assemble complete project state: HANDOFF files, git status, NotebookLM updates, task list, logical next steps

---

## Execution Flow (Automatic — No User Action Required)

### Phase 1: Read Static Context (30s)
1. **HANDOFF files** — Read all 3:
   - `/HANDOFF.md` (current phase status)
   - `/HANDOFF-PHASE32.md` (next phase spec)
   - `/.claude/HANDOFF.md` (project directives)

2. **Git status** — Run and parse:
   ```bash
   git status --short
   git log --oneline -n 5
   ```
   Reports: uncommitted changes, commits ahead of main, branch state

3. **Task list** — Query task tracking:
   - Read task state (completed, pending, in_progress)
   - Parse blockers and dependencies

### Phase 2: Query Project Notebook (90s)
- Query NotebookLM `e1b91409-02f9-4300-8bf7-5dfd4426dd16` for:
  - Latest phase updates
  - Investor timeline and deadlines
  - Technical blockers or insights
  - Hardware/infrastructure notes

### Phase 3: Synthesize Briefing (30s)
Assemble into human-readable report with sections:

```
╔════════════════════════════════════════════════════════════════╗
║                    PROJECT BRIEFING                           ║
║                   SovereignNexus 2026-05-29                   ║
╚════════════════════════════════════════════════════════════════╝

📊 CURRENT STATUS
├─ Phase: [from HANDOFF]
├─ Completed: [% from task list]
├─ In Progress: [list with owners]
└─ Blockers: [if any]

📅 CRITICAL DEADLINES
├─ Nebius Grant: 2026-05-28 23:59 UTC [STATUS: ✓/✗/PENDING]
├─ Live Swarm Rehearsal: 2026-06-05 [in 7 days]
├─ Series A Pitch: 2026-06-10 [in 12 days]
└─ Prague PoC Demo: 2026-06-15 [in 17 days]

🔧 GIT STATE
├─ Branch: [current branch]
├─ Uncommitted changes: [count + summary]
├─ Commits ahead of main: [count]
└─ Last commit: [hash + msg]

📚 HANDOFF CONTEXT
├─ Phase 25 (ReBAC + AP2): [status from HANDOFF.md]
├─ Phase 32 (A2UI): [status from HANDOFF-PHASE32.md]
└─ Project Directives: [from .claude/HANDOFF.md]

💡 NOTEBOOK INSIGHTS
├─ Agentic AI Trends: [key findings]
├─ MCP/A2A Integration: [relevant updates]
└─ Investor Priorities: [from notebook research]

📋 NEXT LOGICAL STEPS (Ranked by Impact)
1. [Action] — [Why] — [Owner] — [Deadline]
2. [Action] — [Why] — [Owner] — [Deadline]
3. [Action] — [Why] — [Owner] — [Deadline]

🎯 SCOPE FOR THIS SESSION
└─ Recommended focus: [based on blockers + deadlines]
```

---

## How to Invoke

### Automatic (Recommended)
Add to `CLAUDE.md`:
```markdown
## Session Initialization
Every session, before responding to the first user message:
1. Run the `/session-briefing` skill
2. Present the briefing to the user
3. Ask: "What's your priority for this session?"
```

### Manual
```
/session-briefing
```

---

## Output Format

**Short Form (default):** Briefing report (3-5 min read)  
**Long Form (--full):** Add technical details, all task dependencies, all notebook sources

**Options:**
```
/session-briefing --full              # Verbose (10 min read)
/session-briefing --focus=phase32     # Focus on specific phase
/session-briefing --focus=deadlines   # Prioritize by deadline
/session-briefing --focus=blockers    # Show blockers first
```

---

## Implementation Details

### Files Read
- `/HANDOFF.md` — Current phase execution details
- `/HANDOFF-PHASE32.md` — Next phase spec (A2UI)
- `/.claude/HANDOFF.md` — Project governance directives
- Git state via `git status` + `git log`
- Task list (via TaskList tool)

### External Query
- NotebookLM notebook `e1b91409-02f9-4300-8bf7-5dfd4426dd16`
  - Query: "What are the latest project updates, phase status, and investor priorities?"

### Synthesis Logic
1. **Timeline:** Extract all deadlines from HANDOFF + task metadata
2. **Status:** Combine phase status + task completion % + git state
3. **Blockers:** Scan task dependencies, HANDOFF "blockers" sections, git status
4. **Next Steps:** Order by:
   - Critical path (blocks others)
   - Deadline proximity
   - Phase sequence dependency

---

## Example Output

```
╔════════════════════════════════════════════════════════════════╗
║              SovereignNexus Briefing — 2026-05-29            ║
╚════════════════════════════════════════════════════════════════╝

📊 CURRENT STATUS
├─ Phase: 25 (ReBAC + AP2) — 40% complete
├─ Completed: Tasks #14-23 (10/46)
├─ In Progress: #24 (Series A Investor Materials)
└─ Blockers: None — clean execution path

📅 CRITICAL DEADLINES
├─ ⚠️  Nebius Grant: TODAY 23:59 UTC [PENDING SUBMISSION]
├─ ✅ Live Swarm Rehearsal: 2026-06-05 (6 days)
├─ 📈 Series A Pitch: 2026-06-10 (11 days)
└─ 🎬 Prague PoC Demo: 2026-06-15 (16 days)

🔧 GIT STATE
├─ Branch: main
├─ Uncommitted changes: 3 files (siss-cockpit, siss-gatekeeper, HANDOFF.md)
├─ Commits ahead of main: 0
└─ Last commit: 08207c8 "Phase 2-1: Rapid-MLX Deployment"

📚 HANDOFF CONTEXT
├─ Phase 25: ReBAC Foundation (Wave 1) — Ready to start Task 1
├─ Phase 32: A2UI Schema Foundation — Blocked until Phase 25 merges
└─ Project Directives: Spec-Driven Development + TDD mandatory

💡 NOTEBOOK INSIGHTS
├─ Agentic AI: MCP/A2A patterns critical for Phase 3 design
├─ Sovereign AI: Infrastructure roadmap aligns with our 96GB Mac Studio plan
├─ Investor Focus: Deterministic replay + chaos resilience (Phase 2-2 delivered)

📋 NEXT LOGICAL STEPS (Ranked by Impact)
1. 🔴 Submit Nebius Grant (TODAY) — Gate for Phase 3 training infrastructure
2. 🟠 Task 1: ReBAC Foundation (Phase 25, Wave 1) — Unblocks A2UI work
3. 🟠 Live Swarm Rehearsal Script (Phase 2-4) — Investor demo readiness
4. 🟡 Finalize Series A Pitch Deck — Parallel to Phase 25 work
5. 🟢 Plan Phase 3 Architecture (LoRA + DeltaNet) — Post-Series A

🎯 RECOMMENDED FOCUS FOR THIS SESSION
→ Submit Nebius grant (30 min), then Task 1: ReBAC Foundation (4 hrs)
```

---

## Integration with CLAUDE.md

Add to your `/Users/andriileukhin/Documents/SovereignNexus/CLAUDE.md`:

```markdown
## 10. Session Initialization Protocol

At the start of every session:
1. Invoke `/session-briefing` skill (auto-fires)
2. Review the briefing output (3-5 min)
3. Respond to the skill's question: "What's your priority for this session?"
4. Task is set; context is locked. Execute the task.

This ensures every session starts with:
- ✅ Current phase status
- ✅ All critical deadlines visible
- ✅ Git state clear (uncommitted changes, merge status)
- ✅ Logical next steps ranked by impact
- ✅ Blockers identified
```

---

## Skill Behavior

**Triggers:**
- Manual: `/session-briefing`
- Auto: First message of new session (can be disabled via CLAUDE.md setting)

**Response Time:**
- Quick (default): ~2-3 min
- Full (--full): ~5-7 min
- Includes notebook query: +90s

**Caching:**
- Git state: Cached for 30s (re-fetch on demand)
- Task list: Cached for 60s
- Notebook query: No cache (always fresh)

**Fallback:**
- If notebook unreachable: Skip notebook section, show "Notebook unavailable"
- If git fails: Show "Unable to read git state"
- If task list fails: Show "Task tracking unavailable"

---

## Exit Criteria

Briefing is complete when output includes:
- [ ] Current phase + status
- [ ] All critical deadlines
- [ ] Git state (branch, uncommitted, ahead)
- [ ] HANDOFF context summary
- [ ] Next 3-5 logical steps
- [ ] Recommended session focus

User can then respond: "Focus on [X]" and the session proceeds with locked context.
