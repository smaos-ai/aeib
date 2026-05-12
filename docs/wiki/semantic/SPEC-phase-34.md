# Phase 34 Delta: Consolidation Tier Promotion

**Status:** Approved | **Date:** 2026-05-11

## Summary

Phase 34 introduces a two-tier signal classification system: proven signals (confidence > 0.90) are promoted to Semantic tier with 30-day half-life and long-term structural memory; signals that fail (confidence < 0.85) are demoted back to Episodic tier for re-testing. This crystallizes the evolutionary feedback loop from Phases 28–33 into persistent, learned knowledge.

## Delta

**Adds:**
- Signal `tier` property: "episodic" | "semantic"
- Promotion on validation: confidence > 0.90 → Semantic (via Phase 32 reinforcement)
- Demotion on failure: confidence < 0.85 → Episodic (via Phase 33 FP decay)
- Hysteresis zone (0.85–0.90): prevents thrashing
- Semantic decay: 30-day half-life (ignores acceleration_mode)
- Audit timestamps: `promoted_at`, `last_demotion_at`

**Modifies:**
- `forecast_engine.rs`: Pass tier to decay formula; use 30-day HL for Semantic
- `signal_reinforcement.rs`: Call promotion function after boosting confidence
- `signal_acceleration.rs`: Skip acceleration_mode for Semantic signals
- `prediction_query.rs`: Extend SignalRow struct with tier, promoted_at

**New module:**
- `crates/siss-graph-db/src/signal_tier_promotion.rs` (promote/demote functions)

## Test Coverage (9 tests)

Promotion threshold, demotion threshold, hysteresis, 30-day decay, acceleration bypass, integration with reinforcement. See full spec for details.

## Integration

Phase 32 (Reinforcement) → Phase 34 (Promotion)  
Phase 33 (Acceleration) → Phase 34 (Skip accel for Semantic)  
Phase 29 (Decay) → Phase 34 (Tier-aware half-life)  
Phase 31 (Weighting) → Phase 35+ (optional confidence boost from Semantic)

---

**Full spec:** `phase-34-consolidation-tier-promotion.md`

**Key insight:** Signals that prove themselves become structural knowledge. The system learns and retains its learning through tier promotion. Episodic tier handles short-term adaptation; Semantic tier locks in long-term domain truths.
