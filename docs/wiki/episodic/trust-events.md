# Trust Network Events — Phase 21/22

Append-only JSONL stream of trust anomaly events detected by the AutoResearch watcher.

**Format:** One JSON object per line.

**Fields:**
- `event_id` (UUID): Unique event identifier
- `event_type` (string): Always "trust_anomaly"
- `source_id` (UUID string): Sovereign establishing the trust
- `target_id` (UUID string): Sovereign receiving trust
- `score` (i16): Final hybrid_trust_score [0..100]
- `explicit_component` (i16): Explicit trust contribution
- `implicit_component` (i16): Implicit signals contribution (negative if penalties)
- `decay_component` (i16): Time decay contribution (negative)
- `transitive_component` (i16 or null): Transitive boost (capped at +15)
- `severity` (string): "critical" | "high" | "medium"
- `timestamp` (ISO 8601): Event UTC timestamp

**Severity rules:**
- `critical`: score < 25 OR decay_component < -50 OR implicit_component < -30
- `high`: score 25..50
- `medium`: score 50..75

---

**Last Updated:** 2026-05-11
