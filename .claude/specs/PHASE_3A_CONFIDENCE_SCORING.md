# Phase 3A: Confidence Scoring Engine — TDD Spec

**Owner:** night-lick-1  
**Timeline:** 9pm–3am (6 hours)  
**Goal:** Deterministic confidence calculation with source weighting, corroboration, and contradiction detection.

---

## Architecture

### Data Flow
```
Fact Input → Source Analyzer → Corroboration Detector → Contradiction Handler → Confidence Score [0.0, 1.0]
```

### Core Types

```rust
#[derive(Clone, Debug)]
pub enum SourceType {
    Human,       // Explicit user input (high trust)
    LLM,         // Claude/other LLM inference (medium trust)
    API,         // External API response (medium-low trust)
    Document,    // External document/PDF (medium trust)
}

#[derive(Clone, Debug)]
pub struct ConfidenceSource {
    pub fact_id: Uuid,
    pub source_type: SourceType,
    pub source_url: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Clone, Debug)]
pub struct ConfidenceCalculator {
    pub fact_id: Uuid,
    pub sources: Vec<ConfidenceSource>,
    pub initial_confidence: f64,  // Before decay
}
```

### Algorithm

**Phase 1: Source Trust Weights**
```
base_confidence = match source_type {
    Human => 0.95,     // Highest trust
    LLM => 0.70,       // Medium trust
    API => 0.60,       // Lower trust
    Document => 0.75,  // Medium-high trust
}
```

**Phase 2: Corroboration Boost**
```
if sources.len() >= 2 {
    corroboration_boost = 0.05 * (sources.len() - 1).min(3) as f64  // Max +0.15
    confidence = (base_confidence + corroboration_boost).min(1.0)
} else {
    confidence = base_confidence
}
```

**Phase 3: Contradiction Detection**
```
For each new fact:
  For each existing fact in knowledge base:
    if semantic_similarity(new, existing) > 0.85 AND fact_text_contradicts(new, existing):
      → Mark existing as stale
      → Create supersession_chain(old_id → new_id)
      → Return contradiction_detected = true
```

---

## Test Suite (5 tests)

### Test 1: `test_source_trust_weights_vary_by_type`
- Input: 4 facts with source_types = [Human, LLM, API, Document]
- Expected: confidence_scores ≥ [0.90, 0.65, 0.55, 0.70]
- Determinism: Same input → same score (no randomness)

### Test 2: `test_corroboration_increases_confidence`
- Input: Fact with 1 source (confidence = 0.70) vs same fact with 3 sources
- Expected: confidence_3_sources > confidence_1_source by ≥ 0.10
- Verify: Corroboration boost applied correctly

### Test 3: `test_contradiction_marks_fact_stale`
- Input: Existing fact (confidence 0.80), new contradicting fact
- Expected: 
  - Old fact marked stale
  - superseded_by = new_fact_id
  - New fact receives higher confidence (0.85+)
- Verify: Contradiction chain created

### Test 4: `test_temporal_decay_with_ebbinghaus`
- Input: Fact created 7 days ago with confidence 0.90
- Expected: decayed_confidence ≈ 0.90 * exp(-7/7) ≈ 0.33
- Verify: Ebbinghaus formula applied correctly

### Test 5: `test_confidence_calculation_deterministic`
- Input: Same fact (same sources, same timestamps) calculated 100x
- Expected: Confidence score identical all 100 times
- Verify: No floating-point or randomness issues

---

## Implementation Checklist

- [ ] `pub struct SourceType` enum with 4 variants
- [ ] `pub struct ConfidenceSource` with fact_id, source_type, timestamp
- [ ] `pub fn compute_source_weight(source_type: SourceType) -> f64`
- [ ] `pub fn compute_corroboration_boost(source_count: usize) -> f64`
- [ ] `pub fn detect_contradiction(new_fact: &str, existing_facts: &[SemanticFact]) -> Option<Uuid>` (returns ID of contradicted fact)
- [ ] `pub fn calculate_confidence(sources: &[ConfidenceSource], existing_facts: &[SemanticFact]) -> (f64, Option<Uuid>)` (returns confidence + contradicted_fact_id)
- [ ] All helpers pure functions (deterministic, no side effects)

---

## Success Criteria

✓ All 5 tests passing  
✓ Confidence scores deterministic (no variance)  
✓ Contradiction detection <50ms per fact  
✓ Output integrated into SemanticFact.confidence_score field  
✓ Report: CONFIDENCE_SCORER_REPORT.md + merkle_proof.json  

---

## Non-Blocking Deferred

- Multi-language contradiction detection (English only for v2.2)
- Weighted contradiction severity (all contradictions treated equally)
- Confidence curve tuning (linear boost; can be polynomial later)
