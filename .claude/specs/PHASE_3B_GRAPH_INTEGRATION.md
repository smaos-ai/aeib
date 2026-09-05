# Phase 3B: Graph Integration & Search Wiring — TDD Spec

**Owner:** night-lick-2  
**Timeline:** 9pm–3am (6 hours)  
**Goal:** Relationship extraction, graph maintenance, and integration into HybridSearchEngine.search().

---

## Architecture

### Data Flow
```
New Fact → Relationship Extractor → Graph Builder → BFS Traversal → Search Ranking Integration
```

### Core Types

```rust
#[derive(Clone, Debug)]
pub struct GraphRelationship {
    pub source_id: Uuid,
    pub target_id: Uuid,
    pub relationship_type: RelationType,
    pub score: f64,  // [0.0, 1.0] relevance
}

#[derive(Clone, Debug, PartialEq)]
pub enum RelationType {
    SemanticSimilar,    // Topical overlap
    Contradicts,        // Opposing facts
    Supports,           // Reinforces
    Related,            // Weak connection
}

#[derive(Clone, Debug)]
pub struct GraphBuilder {
    pub relationships: Vec<GraphRelationship>,
    pub graph: HashMap<Uuid, Vec<(Uuid, f64)>>,  // fact_id -> [(related_id, score)]
}
```

### Algorithm

**Phase 1: Relationship Extraction**
```
For each pair (fact_a, fact_b):
  similarity = semantic_similarity(fact_a.text, fact_b.text)
  
  if similarity > 0.80:
    relationship_type = determine_type(fact_a, fact_b)
    score = similarity * type_weight(relationship_type)
    → Add GraphRelationship
```

**Phase 2: Bidirectional Graph Maintenance**
```
For each relationship (source → target):
  graph[source].push((target, score))
  graph[target].push((source, score))  // Bidirectional
```

**Phase 3: BFS Traversal for Related Facts**
```
fn traverse_graph(root_id: Uuid, depth: usize) -> Vec<(Uuid, f64)> {
  queue = [(root_id, 1.0)]
  visited = {root_id}
  results = []
  
  while queue not empty:
    (current_id, relevance) = queue.pop()
    for (neighbor_id, edge_score) in graph[current_id]:
      if neighbor_id not in visited AND relevance * edge_score > threshold:
        results.push((neighbor_id, relevance * edge_score))
        visited.insert(neighbor_id)
        queue.push((neighbor_id, relevance * edge_score))
  
  sort results by score DESC, return top_k
}
```

**Phase 4: Integration into HybridSearchEngine**
```
// Extend SearchResult to include related facts
// Modify search() to:
//   1. Compute base scores (BM25, vector, RRF)
//   2. Call traverse_graph(top_result_ids)
//   3. Boost ranking if related fact appears in results
```

---

## Test Suite (5 tests)

### Test 1: `test_relationship_extraction_finds_relevant_pairs`
- Input: 3 facts (2 similar, 1 unrelated)
- Expected: 1 relationship detected (the 2 similar ones)
- Verify: Similarity threshold = 0.80 enforced

### Test 2: `test_graph_insertion_maintains_bidirectional_links`
- Input: Relationship A → B with score 0.85
- Expected: 
  - graph[A] contains (B, 0.85)
  - graph[B] contains (A, 0.85)
- Verify: No orphan nodes, all edges bidirectional

### Test 3: `test_graph_traversal_returns_ranked_neighbors`
- Input: Root fact with 3 neighbors (scores: 0.90, 0.60, 0.50)
- Expected: BFS returns all 3, ordered by score DESC
- Verify: Top result has highest relevance

### Test 4: `test_search_ranking_incorporates_graph_relevance`
- Input: Query matching fact A; fact A has related fact B (high score)
- Expected: Fact B ranked higher than unrelated facts
- Verify: Related facts boost in final ranking

### Test 5: `test_graph_integration_deterministic`
- Input: Same set of facts, same relationships, run 10x
- Expected: Graph structure identical all 10 times
- Verify: No randomness in relationship extraction

---

## Implementation Checklist

- [ ] `pub enum RelationType` (4 variants)
- [ ] `pub struct GraphRelationship` with source_id, target_id, score
- [ ] `pub struct GraphBuilder` with relationships + graph HashMap
- [ ] `pub fn extract_relationships(facts: &[SemanticFact]) -> Vec<GraphRelationship>`
- [ ] `pub fn determine_relationship_type(fact_a: &str, fact_b: &str) -> RelationType`
- [ ] `pub fn build_graph(relationships: Vec<GraphRelationship>) -> HashMap<Uuid, Vec<(Uuid, f64)>>`
- [ ] `pub fn traverse_graph(root_id: Uuid, graph: &HashMap, depth: usize) -> Vec<(Uuid, f64)>`
- [ ] Modify `HybridSearchEngine::search()` to incorporate graph scores
- [ ] All helpers deterministic, no side effects

---

## Success Criteria

✓ All 5 tests passing  
✓ Graph traversal <100ms per query  
✓ No orphan nodes in graph  
✓ Search ranking visibly incorporates graph relevance  
✓ Report: GRAPH_BUILDER_REPORT.md + merkle_proof.json  

---

## Integration Points

**Phase 3A Output → Phase 3B Input:**
- SemanticFact.confidence_score (computed by 3A) → used in relationship weighting
- No direct data dependency; can run in parallel

**Phase 3B Output → HybridSearchEngine:**
- graph HashMap populated and integrated into search()
- SearchResult includes graph_relevance component

---

## Non-Blocking Deferred

- Multi-hop relationship discovery (depth > 2)
- Relationship type learning (rules-based for v2.2)
- Graph visualizations and export
- Relationship strength decay over time
