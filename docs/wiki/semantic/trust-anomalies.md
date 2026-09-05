# Trust Anomaly Patterns — Phase 22 Synthesis

Synthesized patterns of recurring trust collapses. Entries are appended when an anomaly pattern reaches ≥ 3 occurrences.

**Structure:** One pattern per sovereign (source_id).

**Format:**

```markdown
## Anomaly Pattern: <source_id_prefix>

| Field | Value |
|-------|-------|
| Source Sovereign | <uuid> |
| Total Occurrences | N |
| Latest Score | I16 |
| Dominant Cause | (description) |
| First Detected | ISO 8601 date |
| Last Detected | ISO 8601 date |
| Recommended Action | (action string) |
```

**Dominant Cause Categories:**
- `decay_collapse`: decay_component < -50 (>15 days zero interaction)
- `slash_accumulation`: implicit_component < -30 (3+ active slashes)
- `mixed_decay_slash`: both conditions true
- `transitive_loss`: transitive_component dropped to 0

**Recommended Actions:**
- "Revoke explicit trust edges; notify governance"
- "Sweep eligibility revocation; re-establish tenure requirements"
- "Investigate slash events; query behavioral anomalies"
- "Monitor recovery trajectory post-interaction"

---

**Last Updated:** 2026-05-11
