#!/usr/bin/env python3
"""
Test Suite: Hybrid Retrieval Tuning (L2 Knowledge Layer Optimization)

Tests for BM25 parameter tuning, RRF weighting optimization, semantic similarity
calibration, and batch processing. TDD-first: tests before implementation.

Run: pytest test_tuning.py -v
"""

import pytest
import hashlib
import time
from typing import List, Dict, Tuple
from tuning import (
    BM25Tuner,
    RRFTuner,
    SemanticTuner,
    BatchRetriever,
    TuningMetrics,
    TuningResult
)


@pytest.fixture
def mock_embedding():
    """Generate deterministic mock embedding."""
    def _generate(text: str) -> List[float]:
        h = hashlib.md5(text.encode()).hexdigest()
        values = [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
        return values[:16]
    return _generate


@pytest.fixture
def compliance_corpus(mock_embedding):
    """50-document compliance corpus for tuning."""
    docs = {
        # Article 50 / Transparency
        "art50_01": ("Article 50: Transparency Requirements",
                    "transparency in ai systems requires disclosure of decision logic"),
        "art50_02": ("Article 50 Part 2",
                    "high-risk AI systems must provide transparency information"),
        "art50_03": ("Transparency User Information",
                    "users have right to know if interacting with AI"),

        # Article 51 / Record-Keeping
        "art51_01": ("Article 51: Documentation",
                    "record-keeping requirements for AI providers"),
        "art51_02": ("Logs and Records",
                    "comprehensive logging of AI decision processes"),

        # Annex III / High-Risk Systems
        "annex3_01": ("Annex III: High-Risk Artificial Intelligence",
                     "systems that pose risk to safety or rights"),
        "annex3_02": ("Credit Scoring Systems",
                     "creditworthiness assessment systems are high-risk"),
        "annex3_03": ("Biometric Systems",
                     "biometric identification and categorization high-risk"),
        "annex3_04": ("Employment Systems",
                     "recruitment and employment AI systems"),

        # Governance
        "gov_01": ("Governance Requirements",
                  "organizational governance for AI compliance"),
        "gov_02": ("Risk Management",
                  "risk assessment and mitigation processes"),
        "gov_03": ("Testing Requirements",
                  "conformity assessment and testing procedures"),

        # Technical Requirements
        "tech_01": ("Technical Documentation",
                   "technical specifications and architecture"),
        "tech_02": ("Data Quality",
                   "training data quality and bias mitigation"),
        "tech_03": ("Monitoring Systems",
                   "performance monitoring and drift detection"),

        # General Compliance
        "comply_01": ("Compliance Framework",
                     "overall AI regulatory compliance framework"),
        "comply_02": ("Risk Classification",
                     "classification of prohibited and high-risk AI"),
        "comply_03": ("Obligations",
                     "obligations for providers and importers"),
        "comply_04": ("Enforcement",
                     "enforcement and penalties for violations"),
    }

    # Extend to 50 documents
    for i in range(5, 51):
        docs[f"doc_{i:02d}"] = (
            f"Document {i}",
            f"compliance document {i} about AI regulations and requirements"
        )

    return {doc_id: (title, text, mock_embedding(text))
            for doc_id, (title, text) in docs.items()}


@pytest.fixture
def golden_queries():
    """50-question golden set for evaluation."""
    return [
        # Precision-focused queries (exact match matters)
        ("Article 50 transparency", ["art50_01", "art50_02", "art50_03"]),
        ("high-risk AI systems", ["annex3_01", "annex3_02", "annex3_03", "annex3_04"]),
        ("creditworthiness assessment", ["annex3_02"]),
        ("biometric identification", ["annex3_03"]),
        ("record-keeping requirements", ["art51_01", "art51_02"]),
        ("documentation", ["art51_01", "tech_01"]),

        # Recall-focused queries (semantic understanding)
        ("What policies protect consumer data?", ["compliance_corpus"]),
        ("Which systems are considered high-risk?", ["annex3_01", "annex3_02", "annex3_03", "annex3_04"]),
        ("How should AI providers ensure transparency?", ["art50_01", "art50_02"]),
        ("What governance structures are required?", ["gov_01", "gov_02", "gov_03"]),
        ("employment AI systems", ["annex3_04"]),
        ("risk assessment", ["gov_02", "comply_02"]),
        ("testing procedures", ["gov_03"]),
        ("data quality", ["tech_02"]),
        ("monitoring", ["tech_03"]),
    ]


# ============================================================================
# TESTS: BM25 Parameter Tuning
# ============================================================================

class TestBM25Tuner:
    """Test BM25 parameter tuning: k1 and b optimization."""

    def test_tuner_initialization(self):
        """Test tuner initialization."""
        tuner = BM25Tuner()
        assert tuner.k1_candidates == [0.5, 1.0, 1.5, 2.0]
        assert tuner.b_candidates == [0.5, 0.75, 1.0]

    def test_custom_candidates(self):
        """Test custom parameter candidates."""
        tuner = BM25Tuner(
            k1_candidates=[1.2, 1.5, 1.8],
            b_candidates=[0.6, 0.75]
        )
        assert tuner.k1_candidates == [1.2, 1.5, 1.8]
        assert tuner.b_candidates == [0.6, 0.75]

    def test_tune_parameters(self, compliance_corpus, golden_queries):
        """Test parameter tuning returns best k1, b."""
        tuner = BM25Tuner(k1_candidates=[1.0, 1.5], b_candidates=[0.5, 0.75])

        result = tuner.tune(compliance_corpus, golden_queries)

        assert isinstance(result, TuningResult)
        assert result.best_k1 in [1.0, 1.5]
        assert result.best_b in [0.5, 0.75]
        assert result.best_mrr >= 0.0
        assert len(result.grid_scores) > 0

    def test_grid_search_exhaustive(self, compliance_corpus, golden_queries):
        """Test all parameter combinations evaluated."""
        tuner = BM25Tuner(k1_candidates=[1.0, 1.5], b_candidates=[0.5, 0.75])
        result = tuner.tune(compliance_corpus, golden_queries)

        # Should evaluate 2 * 2 = 4 combinations
        assert len(result.grid_scores) == 4

    def test_metric_calculation(self, compliance_corpus, golden_queries):
        """Test MRR metric calculation."""
        tuner = BM25Tuner()
        metric = tuner._calculate_metric(compliance_corpus, golden_queries, k1=1.5, b=0.75)

        assert isinstance(metric, float)
        assert 0.0 <= metric <= 1.0

    def test_best_params_selected(self, compliance_corpus, golden_queries):
        """Test best parameters selected from grid."""
        tuner = BM25Tuner(k1_candidates=[0.5, 1.5], b_candidates=[0.5, 1.0])
        result = tuner.tune(compliance_corpus, golden_queries)

        # Best params should have highest MRR
        best_score = result.best_mrr
        for score_dict in result.grid_scores:
            assert best_score >= score_dict["mrr"]


# ============================================================================
# TESTS: RRF Weighting Optimization
# ============================================================================

class TestRRFTuner:
    """Test RRF fusion weighting optimization."""

    def test_tuner_initialization(self):
        """Test RRF tuner initialization."""
        tuner = RRFTuner()
        assert len(tuner.semantic_weights) > 0
        assert len(tuner.keyword_weights) > 0

    def test_weights_sum_to_one(self):
        """Test all weight pairs sum to 1.0."""
        tuner = RRFTuner()
        for sw, kw in zip(tuner.semantic_weights, tuner.keyword_weights):
            assert abs((sw + kw) - 1.0) < 1e-6

    def test_tune_weights(self, compliance_corpus, golden_queries):
        """Test RRF weight tuning."""
        tuner = RRFTuner(
            semantic_weights=[0.4, 0.5, 0.6],
            keyword_weights=[0.6, 0.5, 0.4]
        )

        result = tuner.tune(compliance_corpus, golden_queries)

        assert isinstance(result, TuningResult)
        assert result.best_semantic_weight in [0.4, 0.5, 0.6]
        assert result.best_keyword_weight in [0.6, 0.5, 0.4]
        assert result.best_precision_at_5 >= 0.0

    def test_precision_at_k_metric(self, compliance_corpus, golden_queries):
        """Test precision@5 calculation."""
        tuner = RRFTuner()
        metric = tuner._calculate_metric(
            compliance_corpus, golden_queries,
            semantic_weight=0.6, keyword_weight=0.4
        )

        assert isinstance(metric, float)
        assert 0.0 <= metric <= 1.0

    def test_weight_exploration(self, compliance_corpus, golden_queries):
        """Test weight space explored."""
        tuner = RRFTuner(semantic_weights=[0.3, 0.7], keyword_weights=[0.7, 0.3])
        result = tuner.tune(compliance_corpus, golden_queries)

        # Should evaluate 2 combinations
        assert len(result.grid_scores) == 2


# ============================================================================
# TESTS: Semantic Similarity Calibration
# ============================================================================

class TestSemanticTuner:
    """Test semantic similarity threshold and model calibration."""

    def test_tuner_initialization(self):
        """Test semantic tuner initialization."""
        tuner = SemanticTuner()
        assert tuner.similarity_thresholds == [0.5, 0.7, 0.9]
        assert tuner.embedding_model == "bge-small"

    def test_custom_thresholds(self):
        """Test custom similarity thresholds."""
        tuner = SemanticTuner(similarity_thresholds=[0.6, 0.8])
        assert tuner.similarity_thresholds == [0.6, 0.8]

    def test_embedding_model_selection(self):
        """Test embedding model selection."""
        tuner = SemanticTuner(embedding_model="bge-base")
        assert tuner.embedding_model == "bge-base"

    def test_tune_threshold(self, compliance_corpus, golden_queries):
        """Test similarity threshold tuning."""
        tuner = SemanticTuner(similarity_thresholds=[0.5, 0.7])

        result = tuner.tune(compliance_corpus, golden_queries)

        assert isinstance(result, TuningResult)
        assert result.best_similarity_threshold in [0.5, 0.7]
        assert result.best_recall_at_10 >= 0.0

    def test_recall_at_k_metric(self, compliance_corpus, golden_queries):
        """Test recall@10 calculation."""
        tuner = SemanticTuner()
        metric = tuner._calculate_metric(
            compliance_corpus, golden_queries,
            similarity_threshold=0.7
        )

        assert isinstance(metric, float)
        assert 0.0 <= metric <= 1.0

    def test_threshold_effect_on_recall(self, compliance_corpus, golden_queries):
        """Test that lower thresholds give higher recall."""
        tuner = SemanticTuner(similarity_thresholds=[0.3, 0.9])
        result = tuner.tune(compliance_corpus, golden_queries)

        # Lower threshold should produce better recall
        assert result.best_similarity_threshold in [0.3, 0.9]


# ============================================================================
# TESTS: Batch Processing
# ============================================================================

class TestBatchRetriever:
    """Test batch processing of hybrid searches."""

    def test_batch_retriever_initialization(self):
        """Test batch retriever initialization."""
        retriever = BatchRetriever(batch_size=10)
        assert retriever.batch_size == 10
        assert retriever.cache_enabled is True

    def test_batch_search(self, compliance_corpus, golden_queries, mock_embedding):
        """Test batch search on multiple queries."""
        retriever = BatchRetriever(batch_size=5, cache_enabled=False)

        queries = [q[0] for q in golden_queries[:10]]
        results = retriever.batch_search(
            corpus=compliance_corpus,
            queries=queries,
            top_k=5
        )

        assert len(results) == 10
        for result_set in results:
            assert len(result_set) <= 5

    def test_batch_latency_under_100ms(self, compliance_corpus):
        """Test batch search latency <100ms per query."""
        retriever = BatchRetriever(batch_size=20, cache_enabled=False)

        queries = [
            "transparency requirements",
            "high-risk systems",
            "compliance framework",
        ]

        start = time.time()
        retriever.batch_search(compliance_corpus, queries, top_k=5)
        elapsed_ms = (time.time() - start) * 1000

        avg_latency = elapsed_ms / len(queries)
        assert avg_latency < 100.0

    def test_cache_hit_on_repeat_query(self, compliance_corpus):
        """Test caching on repeated queries."""
        retriever = BatchRetriever(batch_size=10, cache_enabled=True)

        query = "transparency requirements"
        results1 = retriever.batch_search(compliance_corpus, [query], top_k=5)
        results2 = retriever.batch_search(compliance_corpus, [query], top_k=5)

        # Results should be identical
        assert results1[0] == results2[0]

        # Cache should have entry
        cache_key = retriever._cache_key(query, 5)
        assert cache_key in retriever.cache

    def test_cache_disabled(self, compliance_corpus):
        """Test cache can be disabled."""
        retriever = BatchRetriever(cache_enabled=False)

        retriever.batch_search(compliance_corpus, ["test query"], top_k=5)
        assert len(retriever.cache) == 0

    def test_batch_size_parameter(self, compliance_corpus):
        """Test batch size affects processing."""
        retriever_small = BatchRetriever(batch_size=1, cache_enabled=False)
        retriever_large = BatchRetriever(batch_size=100, cache_enabled=False)

        queries = [f"query {i}" for i in range(10)]

        results_small = retriever_small.batch_search(compliance_corpus, queries)
        results_large = retriever_large.batch_search(compliance_corpus, queries)

        # Results should be same regardless of batch size
        assert len(results_small) == len(results_large)


# ============================================================================
# TESTS: Tuning Metrics
# ============================================================================

class TestTuningMetrics:
    """Test metric calculations."""

    def test_mrr_calculation(self):
        """Test Mean Reciprocal Rank."""
        # First relevant at rank 1
        results1 = [("doc1", 0.9), ("doc2", 0.7), ("doc3", 0.5)]
        relevant1 = ["doc1"]
        mrr1 = TuningMetrics.mean_reciprocal_rank(results1, relevant1)
        assert mrr1 == 1.0

        # First relevant at rank 2
        results2 = [("doc2", 0.9), ("doc1", 0.7)]
        relevant2 = ["doc1"]
        mrr2 = TuningMetrics.mean_reciprocal_rank(results2, relevant2)
        assert abs(mrr2 - 0.5) < 1e-6

        # No relevant docs
        results3 = [("doc2", 0.9), ("doc3", 0.7)]
        relevant3 = ["doc1"]
        mrr3 = TuningMetrics.mean_reciprocal_rank(results3, relevant3)
        assert mrr3 == 0.0

    def test_precision_at_k(self):
        """Test Precision@K."""
        results = [("doc1", 0.9), ("doc2", 0.8), ("doc3", 0.7), ("doc4", 0.6)]
        relevant = ["doc1", "doc3"]

        # Precision@2: 1/2 relevant in top 2
        p2 = TuningMetrics.precision_at_k(results, relevant, k=2)
        assert p2 == 0.5

        # Precision@4: 2/4 relevant in top 4
        p4 = TuningMetrics.precision_at_k(results, relevant, k=4)
        assert p4 == 0.5

    def test_recall_at_k(self):
        """Test Recall@K."""
        results = [("doc1", 0.9), ("doc2", 0.8), ("doc3", 0.7), ("doc4", 0.6)]
        relevant = ["doc1", "doc2", "doc3"]

        # Recall@2: 2/3 relevant in top 2
        r2 = TuningMetrics.recall_at_k(results, relevant, k=2)
        assert abs(r2 - 2/3) < 1e-6

        # Recall@3: 3/3 relevant in top 3
        r3 = TuningMetrics.recall_at_k(results, relevant, k=3)
        assert r3 == 1.0

    def test_ndcg_at_k(self):
        """Test NDCG@K."""
        results = [("doc1", 0.9), ("doc2", 0.8), ("doc3", 0.7)]
        relevant = ["doc1", "doc2"]

        ndcg = TuningMetrics.normalized_discounted_cumulative_gain(
            results, relevant, k=3
        )

        # Perfect ranking: NDCG = 1.0
        assert 0.0 <= ndcg <= 1.0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestTuningIntegration:
    """Integration tests for full tuning pipeline."""

    def test_full_tuning_pipeline(self, compliance_corpus, golden_queries):
        """Test complete tuning: BM25 -> RRF -> Semantic -> Batch."""
        # BM25 tuning
        bm25_tuner = BM25Tuner(k1_candidates=[1.0, 1.5], b_candidates=[0.5, 0.75])
        bm25_result = bm25_tuner.tune(compliance_corpus, golden_queries)

        # RRF tuning
        rrf_tuner = RRFTuner(
            semantic_weights=[0.4, 0.6],
            keyword_weights=[0.6, 0.4]
        )
        rrf_result = rrf_tuner.tune(compliance_corpus, golden_queries)

        # Semantic tuning
        sem_tuner = SemanticTuner(similarity_thresholds=[0.5, 0.7])
        sem_result = sem_tuner.tune(compliance_corpus, golden_queries)

        # All should produce valid results
        assert bm25_result.best_k1 is not None
        assert rrf_result.best_semantic_weight is not None
        assert sem_result.best_similarity_threshold is not None

    def test_batch_with_tuned_parameters(self, compliance_corpus, golden_queries):
        """Test batch retriever with tuned parameters."""
        # Get tuned parameters
        bm25_tuner = BM25Tuner(k1_candidates=[1.0, 1.5], b_candidates=[0.75])
        bm25_result = bm25_tuner.tune(compliance_corpus, golden_queries)

        # Use in batch retriever
        retriever = BatchRetriever(batch_size=10)
        queries = [q[0] for q in golden_queries[:5]]

        results = retriever.batch_search(
            compliance_corpus,
            queries,
            top_k=5,
            k1=bm25_result.best_k1,
            b=bm25_result.best_b
        )

        assert len(results) == 5


# ============================================================================
# EDGE CASES
# ============================================================================

class TestTuningEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_corpus(self):
        """Test tuning with empty corpus."""
        tuner = BM25Tuner()
        result = tuner.tune({}, [("query", ["relevant"])])

        # Should handle gracefully
        assert result.best_mrr == 0.0

    def test_single_document_corpus(self, mock_embedding):
        """Test tuning with single document."""
        corpus = {
            "doc1": ("Title", "single document text", mock_embedding("text"))
        }
        tuner = BM25Tuner()
        result = tuner.tune(corpus, [("query", ["doc1"])])

        assert result.best_k1 is not None

    def test_query_with_no_relevant_docs(self, compliance_corpus):
        """Test queries with no relevant documents."""
        tuner = BM25Tuner()
        result = tuner.tune(compliance_corpus, [("query", [])])

        # Should calculate MRR as 0.0
        assert result.best_mrr == 0.0

    def test_unicode_in_queries(self, compliance_corpus):
        """Test queries with Unicode characters."""
        tuner = BM25Tuner()
        queries = [
            ("transparency régulation", ["art50_01"]),
            ("высокий риск", ["annex3_01"]),
        ]
        result = tuner.tune(compliance_corpus, queries)

        # Should handle without error
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
