# ADVANCED SESSION BRIEFING — Notebook-Aligned Default
*Notebook Source: "17 Advanced Techniques for Mastering Claude Code"*
*Generated: 2026-05-29*

---

## ⚡ SESSION INITIALIZATION DEFAULTS (Auto-Load Every Session)

### Pre-Session Baseline
```bash
# Add to ~/.zshrc or ~/.bashrc
alias cc='claude --enable-auto-mode'

# DISABLE auto-memory (cache killer) in CLAUDE.md
# Set auto-memory = false in settings.json

# Add persistent status line
/statusline  # Shows context %, git branch, token cost
```

### Context Management (Non-Negotiable)
| Action | When | Command |
|--------|------|---------|
| **Clear** | Between unrelated tasks | `/clear` |
| **Compact** | Before >85% full | `/compact focus on [current goal]` |
| **Side-channel Q** | Need answer without pollution | `/btw <question>` |
| **Rewind** | Last action failed | `/rewind` (Esc+Esc) |

### Parallel Execution Strategy
- **Worktrees:** `claude --worktree <name>` for 3-5 concurrent agents (zero merge conflicts)
- **Subagents:** Append "use subagents" for heavy research → keeps main session clean
- **Background:** Ctrl+B to push long tasks (Docker, CI) to background

### TDD Workflow (Mandatory)
1. **Plan Mode:** `Shift+Tab` or `/plan` for multi-file tasks
2. **Write Test First:** Ensure test FAILS (RED) before implementing
3. **Implement:** Make test PASS (GREEN)
4. **Verify:** `cargo test --lib`, `cargo clippy -- -D warnings`
5. **Commit:** Only after verification passes

### Verification Checklist
- [ ] Paste RAW logs (never summarize bugs)
- [ ] Run self-verification commands after every change
- [ ] Use Playwright/Chrome for visual verification
- [ ] For regressions: `git bisect` with automated test script

### Automation Hooks (Security + Quality)
```bash
# PreToolUse (block destructive commands)
# PostToolUse (auto-format after every edit)
# PostCompact (re-inject task goals after compression)
```

### Critical Command Sequences
| Sequence | Command | Use Case |
|----------|---------|----------|
| Init Loop | `/init` → trim CLAUDE.md | Start of new session |
| Quick Undo | `/rewind` | Risky refactor failed |
| Poller | `/loop 5m <check>` | Background recurring check |
| Spawner | Ctrl+B | Long-running task (don't block) |

---

## 📊 CURRENT PROJECT STATE (May 29, 2026, 9:00 PM)

### Git State
- **Branch:** main
- **Uncommitted:** CLAUDE.md, session-briefing skill
- **Last Commit:** 6f553e7 (PHASE 2-3: Sneakernet with real AES-256-GCM + Ed25519)
- **Commits This Week:** 4 (Phase 2-1, 2-2, 2-3 complete + fix)

### Task Progress
- **Completed:** 31/47 (66%)
  - PHASE 2-1,2,3 (MLX, Chaos, Sneakernet) ✅
  - PHASE 3-1 through 3-6 (Full observability stack) ✅
  - PHASE 4b (Series A pitch deck) ✅
  - Night Shift SGP v1.0 (3 agents integrated) ✅

- **In Progress:** 4 tasks
  - PHASE 2-4: Live Swarm Demo Integration (Week 6)
  - PHASE 4: Series A Materials
  - PHASE 4a: CzechInvest & Nebius Grant Submissions
  - **NIGHT SHIFT v1: 4-Task Parallel Integration** (May 29–30) ⚡ READY NOW

- **Pending:** 12 tasks
  - PHASE 4c: Prague PoC Rehearsal (June 5)
  - PHASE 4d: Series A Investor Meetings
  - PHASE 1.5-A, B, C (Post-Series A planning)
  - Legal foundation (Czech, Israeli, transfer pricing)

### Notebook Insights (Integrated)
**Context Management:**
- CLAUDE.md is currently 200+ lines — **SHOULD BE <200**
- Auto-memory disabled (cache efficiency enabled) ✅
- Status line configured ✅

**Parallel Execution:**
- 4 worktrees ready for Night Shift v1 (sleep-guard, phi-v2, preactivation, pq-ready)
- Each isolated, zero merge conflicts by design
- Ready for simultaneous agent execution at 9 PM

**TDD Status:**
- Phase 2 code all TDD-verified (tests passing, clippy clean)
- Night Shift v1 designed with write-test-first discipline
- Skill file contains canonical TDD workflow

**Critical Gaps Identified:**
- Nebius grant (May 28 deadline) — **STATUS UNKNOWN**
- CzechInvest submission (May 31 deadline) — **PENDING**
- HITL Veto Flow rehearsal (May 29–30) — **READY TO EXECUTE**
- Phase 25 (ReBAC) — **BLOCKED UNTIL NIGHT SHIFT v1 VALIDATES**

---

## 🚀 NIGHT SHIFT v1 READINESS (Launch at 9:00 PM)

### 4-Task Parallel Execution
| Task | File | Goal | Test | Status |
|------|------|------|------|--------|
| 1️⃣ Sleep Guard | siss-sleep-guard/src/lib.rs | AES-256-GCM on system sleep | test_sleep_guard_prevents_cloud_leak | ✅ READY |
| 2️⃣ φ⁺ v2 | siss-night-cycle/src/phi.rs | Defect tolerance η parameter | test_defect_tolerant_compression_preserves_stressed_user_capsules | ✅ READY |
| 3️⃣ α⁺ | siss-affective-core/src/preactivation.rs | Predictive affective state | test_predictive_affective_state_matches_actual_within_5_percent | ✅ READY |
| 4️⃣ σ⁺ | siss-gatekeeper/src/crypto.rs | Post-quantum dual-auth | test_pq_dual_auth_roundtrip | ✅ READY |

### Shell Aliases (Add to ~/.zshrc)
```bash
alias za='cd .../night-sleep-guard && zsh'
alias zb='cd .../night-phi-v2 && zsh'
alias zc='cd .../night-preactivation && zsh'
alias zd='cd .../night-pq-ready && zsh'
```

### Launch Checklist
- [ ] Run pre-launch setup script (creates 4 worktrees + skill file)
- [ ] Add shell aliases + source ~/.zshrc
- [ ] Open 4 terminals: `za`, `zb`, `zc`, `zd`
- [ ] Launch `claude --enable-memory` in each
- [ ] Paste 4 agent prompts (TDD: write test → RED → GREEN)
- [ ] Run through night (agents verify own work via cargo test)
- [ ] 6:00 AM: Run consolidation script (merge + full test suite)
- [ ] Report: All 4 branches merged, tests passing, ready for investor demo

### Expected Outcome (6:00 AM)
```
✅ Sleep Guard: Cloud-sync blocked, AES-256-GCM encryption active
✅ φ⁺ v2: Defect tolerance η=0.3, 15%+ high-valence retention
✅ α⁺: Predictive affect computed, <5% error after 3 days
✅ σ⁺: Post-quantum dual-auth live, Dilithium verified

🎯 SMAOS 13-Layer Sapient Exoskeleton UPGRADED
   Ready for Israel investor demo (June 3)
```

---

## 📋 FURTHER RECOMMENDED STEPS (After Night Shift v1)

### Immediate (May 30–31, Before Israel Trip)
1. **Verify Nebius Grant Status** (May 28 deadline — check if submitted)
   - If NOT submitted: Submit immediately (blocks Phase 3 infrastructure)
   - If YES: Confirm receipt + bookmark for future correspondence

2. **Submit CzechInvest Grant** (May 31 deadline — 2 days)
   - Prerequisites: Czech s.r.o. confirmed + CzechInvest account active
   - Form fields likely ready from Nebius work
   - Timeline: May 31 23:59 UTC

3. **Execute HITL Veto Flow Rehearsal** (May 29–30, parallel to Night Shift)
   - Manually halt recovery mid-flight during Chaos Petri scenario
   - Verify fail-closed state (<5s shutdown)
   - Record for investor demo

### Short-Term (June 1–3, Before Israel)
4. **Finalize Series A Pitch Deck**
   - Visual production (Track C) complete by May 31
   - CRM population + warm intro sourcing (Track D) by June 1
   - Practice pitch with 13-layer exoskeleton + Night Shift v1 as proof points

5. **Patent Finalization**
   - Autonomous Opus 4.6 agent reportedly in progress
   - Coordinate with Pearl Cohen meeting (Tel Aviv, June 3)

6. **Live Swarm Rehearsal Script** (Phase 2-4)
   - Terminal scripts for M3 Pro cluster execution
   - Trigger all 12 Chaos Petri scenarios in sequence
   - Record investor demo footage
   - Deadline: June 5 (one week buffer before Prague demo)

### Medium-Term (June onwards, Post-Series A)
7. **Phase 25: ReBAC Foundation (Wave 1)**
   - Unblocks Phase 32 (A2UI) dashboard work
   - 12+ tests, PostgreSQL schema, relationship lifecycle
   - Estimated: 4–6 hours (single agent, TDD)

8. **Phase 3 Planning**
   - LoRA adapter training on Nebius H100 burst
   - DeltaNet compression for 50-agent Prague demo
   - Depends on Series A capital (May 31 CzechInvest + Nebius outcomes)

9. **SMAOS Messenger** (Phase 3 parallel)
   - WebSocket endpoint for Qwen3.5-4B local chat
   - AES-256-GCM encryption (Sneakernet proven)
   - Garmin physiological integration (HRV, Body Battery, sleep)
   - Affective/epistemic operators (α, γ, φ operators)

---

## 🎯 DECISION GATE: What's Your Priority Right Now?

**Choose ONE (in order of impact):**

1. **🚀 NIGHT SHIFT v1 LAUNCH (9:00 PM TODAY)**
   - Execute all 4 agents in parallel
   - Completes by 6:00 AM with full test pass
   - Unlocks Phase 25 work
   - Most time-sensitive (tonight-only execution window)

2. **📊 NEBIUS GRANT STATUS CHECK**
   - Verify if May 28 submission is confirmed
   - If not: submit immediately
   - If yes: acknowledge receipt
   - Duration: 15 min (can run in parallel with Night Shift)

3. **📈 SERIES A PITCH DECK FINALIZATION**
   - Incorporate Night Shift v1 results (once complete)
   - 13-layer exoskeleton + 4 new sovereign features = proof
   - Practice delivery
   - Duration: 2–3 hours (best after Night Shift completes)

4. **🧪 PHASE 25 TASK 1: ReBAC FOUNDATION**
   - Single-agent, TDD, 4–6 hours
   - Blocked until Night Shift v1 validates (or can run in parallel)
   - Unlocks Phase 32 dashboard work

---

## 🔐 CRITICAL REMINDERS (From Notebook)

✅ **Context:** Keep CLAUDE.md <200 lines (currently over — trim unnecessary rules)  
✅ **Parallelism:** Use git worktrees (not clones) to eliminate merge conflicts  
✅ **TDD:** Write test FIRST, see RED, implement, see GREEN (non-negotiable)  
✅ **Verification:** Paste RAW logs, never summarize bugs  
✅ **Automation:** PostToolUse hooks auto-format after every edit  
✅ **Background:** Use `/loop` or Ctrl+B for long tasks (don't block session)  

---

**NOTEBOOK SOURCE:** "17 Advanced Techniques for Mastering Claude Code" (100+ curated sources, validated techniques, peer-reviewed patterns)

**NEXT ACTION:** What's your priority? (Night Shift launch, Nebius check, pitch deck, or ReBAC?)
