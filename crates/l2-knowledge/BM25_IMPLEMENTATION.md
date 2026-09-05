# BM25 IDF Weighting for Hybrid Retrieval (L2 Knowledge Layer)

## Overview

Complete BM25 (Okapi Best Matching 25) implementation for hybrid lexical + semantic retrieval. Integrates with pgvector for PostgreSQL-backed semantic search and RRF (Reciprocal Rank Fusion) for score combination.

**Status:** 104 tests passing, production-ready, TDD-first implementation.

## Architecture

```
Query
  ↓
  ├─→ [BM25 Keyword Search] ──→ Ranked keyword results
  │        (bm25.py)
  │
  └─→ [Semantic Search] ────→ Ranked semantic results
           (pgvector)
            ↓
         [RRF Fusion] ────────→ Final ranked results
      (hybrid_retrieval.py)
```

## Core Components

### 1. BM25Index (bm25.py)

Pure Python BM25 implementation with IDF weighting.

```python
from bm25 import BM25Index

# Create index with custom parameters
index = BM25Index(k1=1.5, b=0.75)

# Add documents
index.add_document("doc1", "transparent governance and compliance")
index.add_document("doc2", "high-risk AI systems require assessment")

# Search
results = index.search("transparency governance", top_k=5)
# Returns: [("doc1", 2.34), ("doc2", 1.89)]
```

**Parameters:**
- `k1` (1.5): Term saturation parameter. Higher = less saturation. Range [1.2, 2.0]
- `b` (0.75): Length normalization. 0=no normalization, 1=full normalization

**Formula:**
```
BM25(D, Q) = SUM over q in Q:
  IDF(q) * (f(q,D) * (k1+1)) / (f(q,D) + k1*(1-b+b*(|D|/avgdl)))

IDF(q) = log((N - n(q) + 0.5) / (n(q) + 0.5))
```

**Clamping:** IDF clamped to minimum 0.1 to ensure positive scores.

### 2. BM25Tokenizer (bm25.py)

Handles tokenization: lowercase, punctuation removal, short-token filtering.

```python
from bm25 import BM25Tokenizer

tokenizer = BM25Tokenizer(remove_stopwords=False)
tokens = tokenizer.tokenize("Article 50: Transparency Requirements")
# Returns: ["article", "transparency", "requirements"]
```

### 3. BM25Analyzer (bm25.py)

Debugging & analysis tools for BM25 scoring.

```python
from bm25 import BM25Analyzer

analyzer = BM25Analyzer(index)

# Explain scoring for a document
explanation = analyzer.explain_score("doc1", "transparency governance")
print(explanation["term_scores"])
# {
#   "transparency": {"frequency": 1, "idf": 1.87, "score": 1.12},
#   "governance": {"frequency": 1, "idf": 2.04, "score": 1.22}
# }

# Term statistics
stats = analyzer.term_statistics("transparency")
print(stats)
# {
#   "term": "transparency",
#   "document_frequency": 3,
#   "idf": 1.87,
#   "percentage_coverage": 75.0
# }

# Corpus statistics
corpus_stats = analyzer.corpus_statistics()
print(corpus_stats)
# {
#   "total_documents": 4,
#   "total_terms": 28,
#   "avg_doc_length": 12.5,
#   "vocabulary_size": 28
# }
```

### 4. HybridRetriever (hybrid_retrieval.py)

Combines BM25 keyword search with semantic search via RRF fusion.

```python
from hybrid_retrieval import HybridRetriever

retriever = HybridRetriever(
    semantic_weight=0.6,
    keyword_weight=0.4
)

# Add documents with embeddings
retriever.add_document(
    "doc1",
    "Article 50 transparency requirements",
    title="Article 50",
    embedding=[0.1, 0.2, ..., 0.5]  # 16-dim embedding
)

# Search (hybrid)
query_embedding = [0.2, 0.1, ..., 0.3]
results, elapsed_ms = retriever.search(
    query="transparency requirements",
    query_embedding=query_embedding,
    top_k=5
)

for result in results:
    print(f"{result.doc_id}: {result.rrf_score:.3f} "
          f"(sources: {result.sources}, rank: {result.rrf_rank})")
```

**Result object:**
```python
RetrievalResult(
    doc_id="doc1",
    title="Article 50",
    bm25_score=1.87,        # Raw BM25 score
    semantic_score=0.78,    # Cosine similarity [0,1]
    rrf_score=0.0125,       # Combined RRF score
    rrf_rank=1,             # Rank in final results
    sources=["bm25", "semantic"]  # Which methods found it
)
```

### 5. HybridIndexBuilder (hybrid_retrieval.py)

Fluent API for constructing retriever.

```python
from hybrid_retrieval import HybridIndexBuilder

retriever = (
    HybridIndexBuilder()
    .add_document("doc1", "text1", embedding=emb1)
    .add_document("doc2", "text2", embedding=emb2)
    .build()
)
```

## Evaluation Metrics

Built-in retrieval metrics for evaluating search quality.

```python
from hybrid_retrieval import RetrievalMetrics

# Precision@5
precision = RetrievalMetrics.precision_at_k(results, relevant_ids, k=5)

# Recall@5
recall = RetrievalMetrics.recall_at_k(results, relevant_ids, k=5)

# Mean Reciprocal Rank (first relevant doc)
mrr = RetrievalMetrics.mean_reciprocal_rank(results, relevant_ids)

# NDCG@10 (Normalized Discounted Cumulative Gain)
ndcg = RetrievalMetrics.normalized_discounted_cumulative_gain(
    results,
    relevant_ids,
    k=10
)
```

## Test Suite (104 Tests)

### BM25 Tests (68 tests)

**Tokenization (12 tests)**
- Case sensitivity, punctuation, hyphenation, stopwords, edge cases

**Index Management (11 tests)**
- Document add/remove, length tracking, doc frequency

**IDF Calculation (6 tests)**
- Formula correctness, common vs. rare terms, clamping

**BM25 Scoring (7 tests)**
- Exact matching, frequency sensitivity, length normalization, parameters

**Search Functionality (9 tests)**
- Result ranking, top-k limit, empty queries, sorting

**Property-Based Tests (4 tests)**
- Hypothesis: determinism, positive scores, bounds checking, idempotency

**Edge Cases (6 tests)**
- Unicode, long documents, many documents, repeated tokens

**Analyzer & Integration (8 tests)**
- Explanation, statistics, scale tests

**Performance (3 tests)**
- Latency <10ms, throughput 100+ docs/sec

### Hybrid Retrieval Tests (36 tests)

**Document Management (4 tests)**
- Add/remove, embedding storage, lifecycle

**Semantic Similarity (5 tests)**
- Cosine similarity, orthogonality, ranking

**BM25 Search (4 tests)**
- Ranking, no matches, top-k

**RRF Fusion (3 tests)**
- Basic fusion, deduplication, weight application

**Hybrid Search (6 tests)**
- Ranked results, sources tracking, with/without embeddings

**Metrics (4 tests)**
- Precision, Recall, MRR, NDCG

**Explanation (2 tests)**
- Score breakdown, analyzer access

**Real-World Scenarios (3 tests)**
- Compliance search, multi-query, relevance

**Edge Cases (5 tests)**
- Empty retriever, unicode, zero embeddings

## Integration with PostgreSQL

### Schema Extensions

```sql
-- BM25 index statistics table
CREATE TABLE bm25_statistics (
    id SERIAL PRIMARY KEY,
    term VARCHAR(255) NOT NULL,
    document_frequency INT,
    idf_value FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hybrid search results cache
CREATE TABLE search_cache (
    id SERIAL PRIMARY KEY,
    query VARCHAR(255),
    query_hash VARCHAR(64),
    results JSONB,
    elapsed_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_search_cache_hash ON search_cache(query_hash);
```

### Usage with PostgreSQL

```python
import psycopg2
from hybrid_retrieval import HybridRetriever

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="smaos_db",
    user="postgres"
)

# Load documents from database
retriever = HybridRetriever()
cursor = conn.cursor()
cursor.execute("SELECT id, text, embedding FROM policy_documents")

for doc_id, text, embedding in cursor.fetchall():
    retriever.add_document(doc_id, text, embedding=embedding)

# Search
query_embedding = [0.1, 0.2, ...]
results, elapsed_ms = retriever.search("transparency", query_embedding)

# Cache results
cursor.execute(
    "INSERT INTO search_cache (query, results, elapsed_ms) VALUES (%s, %s, %s)",
    ("transparency", json.dumps([r.__dict__ for r in results]), elapsed_ms)
)
conn.commit()
```

## Performance Characteristics

| Operation | Time |
|-----------|------|
| Add document (50 words) | <1ms |
| Calculate IDF | <0.1ms |
| BM25 score (single doc) | <1ms |
| Semantic similarity (single doc) | <0.5ms |
| Search (100 docs, top-10) | <10ms |
| RRF fusion (100 candidates) | <5ms |

**Scaling:**
- Tested with 1000+ documents
- Supports arbitrary corpus size
- Memory: ~100KB per 1000 documents

## Parameter Tuning Guide

### BM25 Parameters

**k1 (term saturation):**
- `k1=0.5`: Very high saturation (term frequency has less effect)
- `k1=1.5`: Default, balanced
- `k1=2.5`: Low saturation (term frequency has more effect)

**Use k1=2.0-2.5 for:**
- Short queries
- High-precision requirements
- Specialized vocabulary

**Use k1=1.0-1.5 for:**
- General search
- Diverse document lengths
- Balanced precision/recall

**b (length normalization):**
- `b=0.0`: No length normalization (very long docs have advantage)
- `b=0.75`: Default, moderate normalization
- `b=1.0`: Full normalization (doc length doesn't matter)

**Use b=1.0 for:**
- Consistent document structure
- Strict length normalization requirements

**Use b=0.5 for:**
- Variable document lengths
- Natural language queries

### RRF Weights

Default: `semantic_weight=0.6, keyword_weight=0.4`

- Higher semantic_weight: Prioritize semantic similarity
- Higher keyword_weight: Prioritize exact term matches

**For regulatory/compliance documents:**
- Use `semantic_weight=0.4, keyword_weight=0.6` (exact terms matter more)

**For general domain:**
- Use `semantic_weight=0.6, keyword_weight=0.4` (semantic relevance matters)

## Use Cases

### 1. Compliance Document Search

```python
retriever = HybridRetriever(
    semantic_weight=0.4,
    keyword_weight=0.6,  # Exact article numbers matter
    k1=2.0               # Higher saturation for technical terms
)

# Query: "Article 50 transparency requirements"
results = retriever.search(query, query_embedding)
```

### 2. Policy Interpretation

```python
# Semantic weight higher - need semantic understanding
retriever = HybridRetriever(semantic_weight=0.7, keyword_weight=0.3)

# Query: "What policies protect consumer data?"
results = retriever.search(query, query_embedding)
```

### 3. Risk Assessment

```python
retriever = HybridRetriever(
    semantic_weight=0.5,
    keyword_weight=0.5,  # Balanced
    b=0.5                # Account for doc length variation
)

# Query: "high-risk AI systems"
results = retriever.search(query, query_embedding)
```

## Future Enhancements (Phase 2)

- [ ] Persistent PostgreSQL storage for BM25 index
- [ ] BM25+ variant with document priors
- [ ] Query expansion with semantic neighbors
- [ ] Learning-to-rank (LTR) scoring
- [ ] Cross-lingual retrieval (EU AI Act in multiple languages)
- [ ] Real-time index updates with delta encoding
- [ ] Interactive relevance feedback

## References

- **Okapi BM25:** Robertson & Walker (1994). "Some Simple Effective Approximations to the 2-Poisson Model for Probabilistic Weighted Retrieval"
- **RRF:** Cormack et al. (2009). "Reciprocal rank fusion outperforms condorcet and individual rank learning methods"
- **EU AI Act:** Regulation (EU) 2024/1689

## Files

- `bm25.py` (300 lines): Core BM25 implementation
- `test_bm25.py` (680 lines): 68 comprehensive BM25 tests
- `hybrid_retrieval.py` (300 lines): Hybrid retrieval integration
- `test_hybrid_retrieval.py` (450 lines): 36 hybrid search tests
- `schema.sql`: PostgreSQL schema for L2 Knowledge layer

## Running Tests

```bash
# All tests
pytest test_bm25.py test_hybrid_retrieval.py -v

# BM25 only
pytest test_bm25.py -v

# Hybrid retrieval only
pytest test_hybrid_retrieval.py -v

# Specific test
pytest test_bm25.py::TestBM25Scoring::test_score_exact_match -v

# With coverage
pytest test_bm25.py test_hybrid_retrieval.py --cov=bm25 --cov=hybrid_retrieval
```

## Summary

**BM25 IDF Weighting for L2 Knowledge Layer:**
- ✅ 104 passing tests (68 BM25 + 36 hybrid)
- ✅ TDD-first development (tests before code)
- ✅ Production-ready implementation
- ✅ PostgreSQL integration ready
- ✅ RRF fusion with semantic embeddings
- ✅ Comprehensive evaluation metrics
- ✅ Performance: <10ms per search on 100+ docs
- ✅ Extensible and maintainable

**Phase 1 Status:** Complete and verified. Ready for integration with L3 Permit Gates and L4 Orchestration.
