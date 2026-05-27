# Personal Palantir MVP — Night Shift Agent Specification

## Overview
4 autonomous agents execute in parallel (9pm–9am) to build an internal Chief-of-Staff tool that synthesizes 24h of deployment, test, and business metrics into actionable morning briefings.

---

## Agent 1: Palantir-Reader
**Role:** Ingest all night-shift reports and create unified JSON summary

**Input Data Sources:**
- `.claude/reports/night-cycle/multi_region/MULTI_REGION_REPORT.md`
- `.claude/reports/night-cycle/sla_monitor/SLA_DASHBOARD_REPORT.md`
- `.claude/reports/night-cycle/integration/INTEGRATION_REPORT.md`
- `.claude/reports/night-cycle/chaos_petri/CHAOS_PETRI_REPORT.md`
- All associated `.json` and `merkle_proof.json` files

**Processing Logic:**
1. Read each report markdown file
2. Extract: test_count, passed_count, failed_count, status (PASS/FAIL), key metrics
3. Parse JSON metrics for timestamp, summary statistics
4. Verify Merkle hash integrity (read merkle_proof.json, confirm hash matches)
5. Aggregate into unified structure

**Output: `palantir_reports_unified.json`**
```json
{
  "generated_at": "2026-05-27T09:00:00Z",
  "agents": [
    {
      "name": "multi-region",
      "status": "PASS",
      "tests_passed": 6,
      "tests_total": 6,
      "key_metrics": {
        "rto_ms": 30000,
        "rpo": 0,
        "quorum_size": 2
      },
      "merkle_hash": "...",
      "merkle_verified": true
    },
    // ... sla_monitor, integration, chaos_petri
  ],
  "aggregate_status": "ALL_PASS" | "PARTIAL_PASS" | "FAILED",
  "total_tests": 24,
  "total_passed": 24
}
```

**Success Criteria:**
- All 4 report files successfully parsed
- JSON output valid and complete
- Merkle hashes verified
- No missing fields

---

## Agent 2: Palantir-Git
**Role:** Extract git history, PR queue, test status, deployment events

**Input Sources:**
- `git log --oneline -50` (recent commits)
- `git branch -a` (all branches, especially night/* branches)
- `git status` (working tree state)
- Test output from last 24h (if available in logs)

**Processing Logic:**
1. Query git for last 50 commits
2. Extract: commit hash, message, timestamp, branch
3. Filter for night/* branches (agent work)
4. Count: PRs open, tests passing, deployment-related commits
5. Identify: blockers, failed tests, merge conflicts
6. Summarize deployment events (if Prague-Frankfurt production is live, pull metrics)

**Output: `palantir_git_status.json`**
```json
{
  "generated_at": "2026-05-27T09:00:00Z",
  "commits_24h": 12,
  "branches_active": ["night/agent-1-multiregion", "night/agent-2-sla", ...],
  "prs_open": 3,
  "tests_status": "PASSING",
  "recent_events": [
    {
      "timestamp": "...",
      "type": "commit" | "pr_created" | "test_passed" | "deployment",
      "description": "..."
    }
  ],
  "blockers": [],
  "working_tree_clean": true
}
```

**Success Criteria:**
- Git commands execute without error
- All branch/commit data accurate
- Blockers identified (if any)
- JSON output valid

---

## Agent 3: Palantir-Briefer
**Role:** Synthesize reports + git status into 3-5 bullet morning briefing

**Input Sources:**
- `palantir_reports_unified.json` (from Agent 1)
- `palantir_git_status.json` (from Agent 2)
- Previous day's briefing (if exists) for context

**Processing Logic:**
1. Read unified reports and git status
2. Identify: top wins (tests passing, deployments succeeded), top risks (failures, blockers)
3. Rank by impact: capital relevance, customer impact, technical debt
4. Draft 3-5 bullets that tell a story ("What happened overnight? What should I focus on today?")
5. Include: one key metric, one action item, one risk flag

**Output: `palantir_briefing.md`**
```markdown
# Morning Briefing — May 27, 2026

## Status: ✓ ALL SYSTEMS GREEN

**Night Shift Summary:**
- ✓ All 4 validation agents passed (24/24 tests)
- ✓ Multi-region replication validated (<30s RTO, zero RPO)
- ✓ 3 pilot customers operating under SLA thresholds (99.5% uptime)
- ⚠ Chaos Petri baseline stable but recommend weekly re-validation
- → **Action:** Finalize 2 investor decks today; Prague-Frankfurt production is proven asset

**Key Metric:** 100% test pass rate, zero production incidents

**Risk Flag:** None active. Proceed with Series A outreach.

**Next 24h:** Capital focus (VCs, grants). Night shift: CapsuleCommitActor refactor + compliance reports.
```

**Success Criteria:**
- Briefing is 3-5 bullets (concise)
- Briefing is actionable (clear what to focus on)
- Briefing matches actual data (no hallucinations)
- Markdown is well-formatted

---

## Agent 4: Palantir-Dashboard
**Role:** Generate real-time operational dashboard (metrics JSON)

**Input Sources:**
- `palantir_reports_unified.json` (Agent 1)
- `palantir_git_status.json` (Agent 2)
- System uptime/health (if available)
- Investor pipeline status (manual input or from notebook)

**Processing Logic:**
1. Aggregate all metrics from agents 1-2
2. Calculate KPIs: test pass rate, deployment health, agent availability
3. Flag alerts: any failed tests, blockers, SLA breaches
4. Structure for CLI/HTML rendering (flat JSON with visual-friendly keys)

**Output: `palantir_dashboard.json`**
```json
{
  "generated_at": "2026-05-27T09:00:00Z",
  "status": "GREEN",
  "kpis": {
    "test_pass_rate_pct": 100,
    "agents_healthy": 4,
    "deployments_stable": true,
    "production_uptime_pct": 99.8,
    "blockers_active": 0
  },
  "alerts": [],
  "agents": [
    {
      "name": "multi-region",
      "status": "HEALTHY",
      "last_check": "...",
      "tests_24h": 6,
      "pass_rate": 100
    }
  ],
  "capital": {
    "series_a_target": "€3.5M",
    "investor_meetings_scheduled": 0,
    "decks_ready": false
  },
  "next_actions": [
    "Finalize investor decks",
    "Schedule 5 warm intros",
    "Monitor production (Prague-Frankfurt)"
  ]
}
```

**Success Criteria:**
- All KPIs calculated
- Alert system functional
- Dashboard renders cleanly
- JSON is machine-readable

---

## Execution Plan

**Timeline:**
- 9:00pm: Agents spawn in tmux sessions (night-agent-1 through 4)
- 9:00pm–12:00am: Agents 1-2 run in parallel (ingest reports, git data)
- 12:00am–3:00am: Agent 3 synthesizes briefing
- 3:00am–6:00am: Agent 4 builds dashboard + polish
- 9:00am: User reviews briefing + dashboard, takes action

**Success = All 3 Artifacts Generated:**
1. ✓ `palantir_briefing.md` (readable, actionable)
2. ✓ `palantir_dashboard.json` (machine-readable, all KPIs present)
3. ✓ `palantir_memory.md` (structured facts for tomorrow)

**Location:** `.claude/reports/night-cycle/palantir/` (git-tracked)

---

## Failure Modes & Mitigation

| Failure | Mitigation |
|---------|-----------|
| Report files missing | Agents skip & note as "not found" in output |
| Git commands fail | Use cached data from last successful run |
| JSON malformed | Agents validate & log errors, return partial output |
| Briefing is generic | Agent 3 re-runs with explicit "tell a story" prompt |
| Dashboard blank | Agent 4 defaults to last known state + timestamp |

---

## Success = Tomorrow's Execution Plan

If all artifacts generated:
- User reads `palantir_briefing.md` at 9am (2 min read)
- User checks `palantir_dashboard.json` (visual scan)
- User executes action items from briefing
- Next night: agents execute new scope from today's spec

If any failures:
- User reviews logs, adjusts agent specs, re-run night shift
- Iterate until tool is reliable

---

## Deploy Command (9pm)

```bash
tmux send-keys -t night-agent-1 "/loop 'Agent-Palantir-Reader: Ingest all reports, create unified JSON summary. Output: palantir_reports_unified.json'" Enter

tmux send-keys -t night-agent-2 "/loop 'Agent-Palantir-Git: Extract git history, PR queue, test status. Output: palantir_git_status.json'" Enter

tmux send-keys -t night-agent-3 "/loop 'Agent-Palantir-Briefer: Synthesize reports into 3-5 bullet morning briefing. Output: palantir_briefing.md'" Enter

tmux send-keys -t night-agent-4 "/loop 'Agent-Palantir-Dashboard: Generate real-time metrics dashboard. Output: palantir_dashboard.json'" Enter
```

Agents execute 9pm–9am. Review briefing + dashboard by 9:30am.

---

**Ready to deploy night shift?**
