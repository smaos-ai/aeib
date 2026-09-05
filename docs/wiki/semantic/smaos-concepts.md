# SMAOS Concepts — Semantic Memory

**Purpose:** Distilled definitions of SMAOS entities, relationships, and decision patterns.

**Last Updated:** 2026-05-11

---

## Core Entities

### SovereignNode
- **Definition:** Represents a single sovereign (agent identity) in the SMAOS graph.
- **Properties:** `sovereign_id` (UUID), `created_at` (ISO 8601 timestamp)
- **Relationships:** `DEPENDS_ON` (linked to recovery/violation nodes)
- **Used By:** All recovery, scoring, violation tracking

### RecoveryNode
- **Definition:** Lifecycle event representing a sovereign's transition into recovery state.
- **Event Types:**
  - `probation_to_recovery` — clean probation exit, enters 8-week recovery
  - `recovery_to_active` — 8 weeks clean, returns to active status
  - `recovery_to_quarantine` — violation during recovery, re-quarantine (no appeal cooldown)
- **Properties:** `event_type`, `weeks_elapsed`, `evidence`, `timestamp`
- **Confidence:** 1.0 (deterministic via background sweep)

### ScoringNode
- **Definition:** Represents a score computation decision with full signal breakdown.
- **Properties:** `score` (0-100), `weeks_elapsed`, `slash_count`, `anomaly_count`, `settled_count`, `rationale`
- **Rationale Examples:**
  - "Graduated base 92 (week 4) - 20 slash penalty (2 slashes in 30d) = 72"
  - "Graduated base 85 (week 1) + 15 settlement bonus = 100 (capped)"
- **Confidence:** 0.95+ (deterministic Phase 19 formula applied to recovery base)

### ViolationNode
- **Definition:** Represents a violation of probation thresholds detected during recovery.
- **Properties:** `reason` (dispatch_spam, timeout_spam, revocation_pattern), `evidence`, `timestamp`
- **Relationships:** `TRIGGERS` (incoming from RecoveryNode that caused it)
- **Confidence:** 0.9-1.0 (depends on enforcement sweep sensitivity)

### TransitionNode
- **Definition:** Represents a state machine transition (probation→recovery, recovery→active, recovery→quarantine).
- **Properties:** `from_status`, `to_status`, `trigger`, `timestamp`
- **Audit Trail:** Every transition materialized in graph for replay/audit

---

## Relationship Types

### DEPENDS_ON
- **From:** RecoveryNode, ViolationNode, ScoringNode → **To:** SovereignNode
- **Meaning:** This decision/event belongs to this sovereign
- **Confidence:** Always 1.0 (deterministic)

### TRIGGERS
- **From:** RecoveryNode → **To:** ViolationNode
- **Meaning:** This recovery event caused a violation
- **Example:** Recovery week 3 (slashing detected) → violation → re-quarantine
- **Confidence:** 0.95+ (high confidence in causation chain)

### EXPLAINS
- **From:** ScoringNode → **To:** Signal (slash, anomaly, settlement evidence)
- **Meaning:** This signal contributed to the score computation
- **Confidence:** 0.9-1.0 (depends on signal recency)

### SUPERSEDES
- **From:** New decision → **To:** Old decision
- **Meaning:** This decision overrides a prior decision (e.g., new score > old score)
- **Example:** Day 30 score (slashes age out) supersedes day 1 score
- **Confidence:** 1.0 (deterministic time-based)

---

## Decision Patterns

### Pattern: Graduated Recovery with Signal Integration
1. Sovereign exits probation cleanly (30 days, no violations)
2. Enters `recovering` status; week_elapsed = 0
3. Every 7 days: score recomputes with recovered_base_score(weeks) + Phase 19 signals
4. If slash detected: score drops (penalty = -20); after 30d, penalty ages out
5. If violation detected: immediate re-quarantine (no appeal)
6. If 8 weeks clean: auto-transition to `active`

**Intelligence Graph Materialization:**
- RecoveryNode created on entry (probation_to_recovery)
- ScoringNode created weekly with current signal breakdown
- ViolationNode created if threshold breached (triggers TRIGGERS edge)
- TransitionNode created on exit (recovery_to_active or recovery_to_quarantine)

### Pattern: Blast Radius Analysis (GitNexus Impact)
- **Input:** Modified file (e.g., `crates/siss-graph-db/src/repo/peer_scoring_repo.rs`)
- **Analysis:** Who calls this? Who depends on this?
- **Output:** JSON with caller list + dependent list + confidence scores
- **Used By:** Task planning (Tasks 89, 90, 91 have GitNexus gates)

---

## Confidence Scoring

| Type | Score | Basis | Example |
|------|-------|-------|---------|
| Deterministic transition | 1.0 | State machine rule | RecoveryNode DEPENDS_ON SovereignNode |
| Signal-based penalty | 0.9-0.95 | Phase 19 formula + recency | Slash penalty = min(30, count*10) |
| Causation (violation) | 0.85-0.95 | Event ordering + threshold | ViolationNode TRIGGERS from RecoveryNode |
| Blast radius | 0.5-0.95 | Grep + git log coverage | impact(file_path) depends on grep matches |

---

## Query Examples

**Q: Get full recovery timeline for sovereign X**
```
MATCH (s:SovereignNode {sovereign_id: 'X'}) 
<- [DEPENDS_ON] - (r:RecoveryNode)
RETURN r.properties ORDER BY r.created_at
```

**Q: Why did sovereign X transition to quarantine?**
```
MATCH (r:RecoveryNode) - [TRIGGERS] -> (v:ViolationNode)
WHERE r.properties->>'sovereign_id' = 'X'
RETURN v.properties.reason, v.properties.evidence
```

**Q: Score trajectory during recovery**
```
MATCH (r:RecoveryNode) <- [DEPENDS_ON] - (s:ScoringNode)
WHERE r.properties->>'event_type' = 'probation_to_recovery'
RETURN s.properties.weeks_elapsed, s.properties.score
ORDER BY s.created_at
```

---

## Invariants

1. **Every RecoveryNode has exactly one SovereignNode** (via DEPENDS_ON)
2. **Every ViolationNode has at most one incoming TRIGGERS edge** (from recovery that triggered it)
3. **Scoring is deterministic:** same input (weeks, signals) always produces same score
4. **Confidence is monotonic:** violation/transition confidence >= signal confidence
5. **Timeline is immutable:** nodes created with `created_at` timestamp; no retroactive updates
