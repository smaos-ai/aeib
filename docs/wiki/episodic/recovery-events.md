# Recovery Events Log — Phase 20 Event Stream

**Purpose:** Immutable episodic memory of all Phase 20 recovery lifecycle events.

**Format:** Append-only JSON-L stream of events as sovereigns progress through recovery.

**Last Updated:** 2026-05-11

---

## Event Schema

Each event is a single JSON line with this structure:

```json
{
  "event_id": "uuid",
  "event_type": "recovery_entered|recovery_progressed|recovery_completed|recovery_violation",
  "sovereign_id": "uuid",
  "timestamp": "2026-05-11T12:34:56Z",
  "weeks_elapsed": 0,
  "current_score": 85,
  "details": {
    "reason": "clean_30_days",
    "slashes_count": 0,
    "anomalies_count": 0,
    "settled_count": 5
  }
}
```

---

## Event Types

### `recovery_entered`
- **Trigger:** Probation sweep completes, sovereign exits probation cleanly (30 days, no violations)
- **Score at Entry:** 80 (probation base) + Phase 19 signals
- **Next:** Wait for weekly sweeps to increment progress

### `recovery_progressed`
- **Trigger:** Weekly recovery sweep; week incremented, score recomputed
- **Score Change:** Graduated base + Phase 19 signals (slashes may age out after 30d)
- **Next:** Continue weekly sweeps or detect violation

### `recovery_completed`
- **Trigger:** Week 8 reached; 56+ days clean (no violations)
- **Score at Exit:** Should equal 100 (or less if active slashes/anomalies)
- **Next:** Transition to `active` status; recovery_log.recovery_exit_status = 'success'

### `recovery_violation`
- **Trigger:** Probation thresholds breached during recovery (dispatch, timeout, revocation)
- **Violation Reason:** dispute_spam, timeout_spam, or revocation_pattern
- **Next:** Immediate re-quarantine; recovery_log.recovery_exit_status = 'failure'

---

## Event Stream (Append-Only)

Events will be appended here as Phase 20 executes. Example format:

```
{"event_id":"...", "event_type":"recovery_entered", "sovereign_id":"...", "timestamp":"...", "weeks_elapsed":0, "current_score":82, "details":{"reason":"clean_30_days","slashes_count":0,"anomalies_count":0,"settled_count":3}}
{"event_id":"...", "event_type":"recovery_progressed", "sovereign_id":"...", "timestamp":"...", "weeks_elapsed":1, "current_score":83, "details":{"reason":"weekly_increment","slashes_count":0,"anomalies_count":0,"settled_count":4}}
...
```

Currently empty; will be populated during Phase 20 testing and execution.

---

## Query Examples

**Find all sovereigns who entered recovery:**
```bash
grep "recovery_entered" recovery-events.md
```

**Find all sovereigns who were re-quarantined during recovery:**
```bash
grep "recovery_violation" recovery-events.md
```

**Timeline for sovereign X:**
```bash
grep "\"sovereign_id\":\"X\"" recovery-events.md | jq .
```

---

## Integration with Intelligence Graph

Every event appended here also creates a corresponding node in the PostgreSQL + Apache AGE intelligence graph:
- `recovery_entered` → RecoveryNode + DEPENDS_ON SovereignNode
- `recovery_progressed` → ScoringNode + EXPLAINS edges to signals
- `recovery_completed` → TransitionNode + SUPERSEDES prior recovery_entered
- `recovery_violation` → ViolationNode + TRIGGERS from most recent RecoveryNode

This ensures both the episodic log (markdown) and semantic graph (DB) stay synchronized.
