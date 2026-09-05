# 🧠 SDIP Vision: Sovereign Decision Intelligence Protocol
**Status:** LOCKED (Phase DB-3+, post-Phase 25)  
**Last Updated:** 2026-05-30  
**Prerequisite:** Phase 25 (ReBAC) + Phase DB-2 (Vector Search) + Phase DB-3 (Crystallization)

---

## Problem Statement
Agentic swarms lack a **deterministic, mathematically verifiable decision-scoring layer** that bridges mission utility, covenant alignment, and reversibility. Current systems optimize for a single metric (revenue, uptime) and drift from their founding principles.

---

## The Innovation: Decision Quality Score (DQS)

```rust
pub struct DecisionIntent {
    pub id: String,
    pub context: String,              // Mission context (e.g., "File PCT patents")
    pub mission_utility: f64,         // 0.0–1.0 (Series A value alignment)
    pub covenant_risk: f64,           // 0.0–1.0 (Threat to 1%/99% principle)
    pub epistemic_confidence: f64,    // 0.0–1.0 (Data freshness + certainty)
    pub blast_radius: BlastRadius,    // Simulation result (reversibility, impact)
}

// DQS = (Mission_Utility × 0.4) + (Covenant_Alignment × 0.4) + (Reversibility × 0.2)
// - Penalties: fog_penalty if epistemic_confidence < 0.7, blast_penalty if critical
// - Decision is GOOD if DQS > 0.6 AND blast.critical == false AND covenant_risk == 0
pub fn calculate_dqs(intent: &DecisionIntent) -> f64 { ... }
```

---

## Three Vectors of Deep Think

### Vector 1: Mission-Safety-Reversibility Balance
- **Mission Utility (40%):** Alignment with Series A / Prague PoC / investor narrative
- **Covenant Alignment (40%):** 1%/99% principle preserved; local-first, fail-closed
- **Reversibility (20%):** Can the decision be undone in <24h? Lower cost = higher score

### Vector 2: Counterfactual Blast-Radius Simulation
- **Pre-execution:** Simulate decision on dependency graph (ReBAC relationships, IP timelines, credit limits)
- **Shadow Run:** Does the decision create cycles? Exceed thermal thresholds? Risk patent filing?
- **Output:** Blast-Radius Score (0.0–1.0). If > 0.7, auto-escalate to Human Gate.

### Vector 3: Epistemic Uncertainty Scoring
- Every input (Nebius pricing, patent status, market data) has **Confidence Score** + **Recency Score**
- If system must decide but intel is stale (>24h), trigger **Recon Agent** to refresh before evaluating
- Prevents decisions on bad data

---

## Winning KPIs (Prove the System Works)

| KPI | Definition | Target |
|-----|-----------|--------|
| **Alignment Velocity** | Time from Decision Trigger → Verified Action | `<200ms` |
| **Covenant Compliance Rate** | % decisions passing 1%/99% + Safety Geometry checks | `100.0%` |
| **Fog Reduction Rate** | % of "Unknown" states resolved by Recon Agents pre-decision | `>85%` |
| **Blast-Radius Containment** | Max impact of a failed decision | `1 Capsule` (isolated) |
| **Human Gate Efficiency** | % Autonomous vs. Human escalation | `99% Auto / 1% Human` |

---

## Architecture Fusion: Palantir + Army OODA

| Concept | Translation | SDIP Innovation |
|---------|------------|-----------------|
| Palantir Object Model | Decision Intent as first-class entity | DQS is a cryptographically auditable proof of decision quality |
| Army OODA Loop | SOVA (Sense, Orient, Verify, Act) | **Verify** = DQS + Blast-Radius check before Act |
| Commander's Intent | Architect's Covenant | If covenant threatened, halt even if rule says proceed |
| Center of Gravity | Critical Dependency Node | Identify single point of failure; protect it; guarantee victory |

---

## Integration Points (When Built)

### Phase 25 (ReBAC Foundation) → SDIP
- DecisionStore (Phase DB-1) holds decisions
- ReBAC relationships inform blast-radius simulation
- Policy decisions trigger DQS evaluation

### Phase DB-2 (Vector Search) → SDIP
- Semantic similarity of decisions (query: "Decisions that risked IP?")
- Fuzzy matching on intent descriptions
- Historical DQS trends (was this decision type risky before?)

### Phase DB-3 (Crystallization) → SDIP
- Working memory (raw decisions) → Episodic (with DQS scores)
- Episodic → Semantic (decision archetypes: "patent filing", "vendor negotiation")
- Semantic → Procedural (decision rules: "Always verify IP counsel before proceeding")

### Phase 32+ (A2UI & Mesh Sync) → SDIP
- Human Gate escalations render as A2UI prompts
- Team agents query shared DQS history for parallel decisions
- Covenant alignment becomes first-class agent capability

---

## Research Dependencies (Validate Before Building)

- [ ] Palantir Object Model: How are decisions modeled in production systems?
- [ ] Army OODA vs. SOVA: Is "Verify" the right step? What does verification mean operationally?
- [ ] DQS weights (0.4/0.4/0.2): Are these empirically sound? Test on past decisions.
- [ ] Blast-Radius Sim: Which graph operations are critical? How deep to simulate? Cost-benefit?
- [ ] Epistemic Scoring: What makes data "fresh"? 24h? Depends on domain?

---

## Success Criteria

- DQS is deterministic (same inputs → same score, always)
- Covenant violations are caught with 100% accuracy (false negatives = unacceptable)
- Blast-radius simulations run in <50ms (fit within decision latency budget)
- System explains every decision in human-readable format ("Why was this DQS = 0.7?")
- All decisions are cryptographically auditable (Merkle-hashed to EXEC_LOG.json)

---

## NOT in Scope (Phase DB-3+)

- Reinforcement learning on DQS (no neural networks yet)
- Causal inference (stays structural + rule-based)
- Real-time market data integration (Phase DB-2 vector search is dependency)
- Multi-agent negotiation (deferred to Mesh Sync)

---

## Implementation Sequence (Future)

1. **Phase DB-2:** Add sqlite-vss or qdrant-client for semantic search
2. **Phase DB-3:** Implement crystallization pipeline (Working → Episodic tiers)
3. **Phase DB-3+:** Draft `decision_intent.rs` struct + DQS algorithm
4. **Phase DB-3+:** Implement `blast_radius_sim()` function (graph traversal)
5. **Phase DB-3+:** Wire into DecisionStore (Phase DB-1 trait extension)
6. **Phase DB-3+:** Integration tests: DQS + ReBAC policies + Real decisions

---

## Locked Status

This design is **intentionally DEFERRED.** It is mathematically sound and strategically essential, but it requires the nervous system (Phase 25 + DB-2/3) to be fully wired before the brain (SDIP) can function.

**No further design work until Phase 25 ReBAC is complete and Phase DB-2/3 are underway.**

This is the Correctness Doctrine in action: don't optimize prematurely; build the foundation first.
