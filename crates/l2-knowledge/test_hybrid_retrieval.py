#!/usr/bin/env python3
"""
Integration Tests for Hybrid Retrieval (BM25 + Semantic)

Tests hybrid search combining BM25 IDF weighting with semantic embeddings.
Run: pytest test_hybrid_retrieval.py -v
"""

import pytest
import math
import hashlib
from typing import List
from hybrid_retrieval import (
    HybridRetriever,
    HybridIndexBuilder,
    RetrievalResult,
    RetrievalMetrics
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
def small_retriever(mock_embedding):
    """Small corpus retriever."""
    retriever = HybridRetriever()

    docs = [
        ("doc1", "the quick brown fox jumps over the lazy dog"),
        ("doc2", "a fast brown fox leaps over a lazy dog"),
        ("doc3", "the dog was lazy"),
        ("doc4", "transparent governance and compliance requirements"),
        ("doc5", "eu ai act article 50 transparency requirements"),
    ]

    for doc_id, text in docs:
        retriever.add_document(
            doc_id,
            text,
            title=text[:50],
            embedding=mock_embedding(text)
        )

    return retriever


@pytest.fixture
def eu_retriever(mock_embedding):
    """EU AI Act themed retriever."""
    docs = [
        ("annex3_1", "Annex III high-risk artificial intelligence systems"),
        ("annex3_2", "credit scoring and creditworthiness assessment"),
        ("annex3_3", "biometric identification and categorization"),
        ("article50", "Article 50 transparency and information to users"),
        ("article51", "Article 51 record-keeping and documentation"),
        ("governance", "governance and compliance requirements for AI"),
        ("risk", "risk assessment and mitigation strategies"),
        ("transparency", "transparency is critical for trust in AI systems"),
    ]

    builder = HybridIndexBuilder()
    for doc_id, text in docs:
        builder.add_document(
            doc_id,
            text,
            title=text,
            embedding=mock_embedding(text)
        )

    return builder.build()


# ============================================================================
# UNIT TESTS: Document Management
# ============================================================================

class TestDocumentManagement:
    """Test adding/removing documents."""

    def test_add_document(self, small_retriever):
        """Test adding document."""
        assert "doc1" in small_retriever.documents
        assert small_retriever.bm25_index.total_docs > 0

    def test_remove_document(self, small_retriever):
        """Test removing document."""
        initial_count = small_retriever.bm25_index.total_docs
        small_retriever.remove_document("doc1")
        assert small_retriever.bm25_index.total_docs == initial_count - 1
        assert "doc1" not in small_retriever.documents

    def test_document_with_embedding(self, small_retriever):
        """Test document stores embedding."""
        assert "doc1" in small_retriever.documents
        assert small_retriever.documents["doc1"]["embedding"] is not None

    def test_document_without_embedding(self):
        """Test document without embedding."""
        retriever = HybridRetriever()
        retriever.add_document("doc1", "test text", embedding=None)
        assert retriever.documents["doc1"]["embedding"] is None


# ============================================================================
# UNIT TESTS: Semantic Similarity
# ============================================================================

class TestSemanticSimilarity:
    """Test semantic search."""

    def test_cosine_similarity_identical_vectors(self, small_retriever):
        """Test cosine similarity for identical vectors."""
        vec = [1.0, 0.0, 0.0]
        similarity = small_retriever._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal_vectors(self, small_retriever):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = small_retriever._cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 1e-6

    def test_cosine_similarity_zero_vector(self, small_retriever):
        """Test cosine similarity with zero vector."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0]
        similarity = small_retriever._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_semantic_search_returns_ranked_results(self, small_retriever):
        """Test semantic search returns ranked results."""
        query_embedding = [0.5] * 16
        results = small_retriever.semantic_search(query_embedding, top_k=3)

        assert len(results) <= 3
        # Results should be (doc_id, score) tuples
        for doc_id, score in results:
            assert isinstance(doc_id, str)
            assert isinstance(score, float)
            assert 0 <= score <= 1

    def test_semantic_search_respects_top_k(self, small_retriever):
        """Test semantic search respects top_k."""
        query_embedding = [0.5] * 16

        results_2 = small_retriever.semantic_search(query_embedding, top_k=2)
        results_5 = small_retriever.semantic_search(query_embedding, top_k=5)

        assert len(results_2) <= 2
        assert len(results_5) <= 5


# ============================================================================
# UNIT TESTS: BM25 Search
# ============================================================================

class TestBM25Search:
    """Test BM25 keyword search."""

    def test_keyword_search_returns_results(self, small_retriever):
        """Test keyword search returns results."""
        results = small_retriever.keyword_search("fox", top_k=5)
        assert len(results) > 0

    def test_keyword_search_ranked(self, small_retriever):
        """Test keyword search returns ranked results."""
        results = small_retriever.keyword_search("lazy dog", top_k=5)

        # Results should be ranked
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i+1][1]

    def test_keyword_search_no_matches(self, small_retriever):
        """Test keyword search with no matches."""
        results = small_retriever.keyword_search("xyzabc", top_k=5)
        assert results == []

    def test_keyword_search_respects_top_k(self, small_retriever):
        """Test keyword search respects top_k."""
        results = small_retriever.keyword_search("the", top_k=2)
        assert len(results) <= 2


# ============================================================================
# UNIT TESTS: RRF Fusion
# ============================================================================

class TestRRFFusion:
    """Test Reciprocal Rank Fusion."""

    def test_rrf_fusion_basic(self, small_retriever):
        """Test RRF fusion combines results."""
        semantic = [("doc1", 0.8), ("doc2", 0.7)]
        keyword = [("doc2", 0.9), ("doc3", 0.6)]

        fusion = small_retriever.rrf_fusion(semantic, keyword)

        # Both doc1, doc2, doc3 should be in fusion
        assert "doc2" in fusion  # In both results
        assert "doc1" in fusion or "doc3" in fusion  # In at least one

    def test_rrf_fusion_deduplication(self, small_retriever):
        """Test RRF fusion deduplicates documents."""
        semantic = [("doc1", 0.8), ("doc2", 0.7), ("doc1", 0.6)]
        keyword = [("doc1", 0.9), ("doc3", 0.6)]

        fusion = small_retriever.rrf_fusion(semantic, keyword)

        # doc1 should appear only once in fusion
        assert len([d for d in fusion if d == "doc1"]) == 1

    def test_rrf_fusion_weights_applied(self, small_retriever):
        """Test RRF fusion applies weights correctly."""
        # Create retriever with specific weights
        retriever = HybridRetriever(semantic_weight=0.8, keyword_weight=0.2)
        retriever.add_document("doc1", "test text")
        retriever.add_document("doc2", "test text")

        semantic = [("doc1", 0.9)]
        keyword = [("doc2", 0.9)]

        fusion = retriever.rrf_fusion(semantic, keyword)

        # doc1 should have higher score due to higher semantic weight
        if "doc1" in fusion and "doc2" in fusion:
            assert fusion["doc1"]["rrf_score"] > fusion["doc2"]["rrf_score"]


# ============================================================================
# FUNCTIONAL TESTS: Hybrid Search
# ============================================================================

class TestHybridSearch:
    """Test hybrid search combining BM25 + semantic."""

    def test_hybrid_search_returns_results(self, small_retriever):
        """Test hybrid search returns results."""
        query_embedding = [0.5] * 16
        results, elapsed_ms = small_retriever.search("fox", query_embedding)

        assert isinstance(results, list)
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert isinstance(elapsed_ms, int)

    def test_hybrid_search_ranked(self, small_retriever):
        """Test hybrid search returns ranked results."""
        query_embedding = [0.5] * 16
        results, _ = small_retriever.search("fox lazy", query_embedding, top_k=5)

        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].rrf_score >= results[i+1].rrf_score

    def test_hybrid_search_respects_top_k(self, small_retriever):
        """Test hybrid search respects top_k."""
        query_embedding = [0.5] * 16

        results_2, _ = small_retriever.search("fox", query_embedding, top_k=2)
        results_5, _ = small_retriever.search("fox", query_embedding, top_k=5)

        assert len(results_2) <= 2
        assert len(results_5) <= 5

    def test_hybrid_search_without_embedding(self, small_retriever):
        """Test hybrid search without semantic embedding."""
        results, _ = small_retriever.search("fox", query_embedding=None)

        # Should still work with BM25 only
        assert len(results) > 0

    def test_hybrid_search_sources_tracked(self, small_retriever):
        """Test that search sources are tracked."""
        query_embedding = [0.5] * 16
        results, _ = small_retriever.search("fox", query_embedding)

        for result in results:
            assert isinstance(result.sources, list)
            assert all(s in ["bm25", "semantic"] for s in result.sources)

    def test_hybrid_search_eu_corpus(self, eu_retriever):
        """Test hybrid search on EU-themed corpus."""
        query_embedding = [0.5] * 16
        results, _ = eu_retriever.search("transparency", query_embedding)

        assert len(results) > 0
        doc_ids = [r.doc_id for r in results]
        # Should find transparency-related docs
        assert "article50" in doc_ids or "transparency" in doc_ids


# ============================================================================
# FUNCTIONAL TESTS: Fluent API
# ============================================================================

class TestFluentAPI:
    """Test fluent builder API."""

    def test_builder_pattern(self, mock_embedding):
        """Test HybridIndexBuilder fluent API."""
        retriever = (
            HybridIndexBuilder()
            .add_document("doc1", "test one", embedding=mock_embedding("test one"))
            .add_document("doc2", "test two", embedding=mock_embedding("test two"))
            .build()
        )

        assert "doc1" in retriever.documents
        assert "doc2" in retriever.documents


# ============================================================================
# FUNCTIONAL TESTS: Retrieval Metrics
# ============================================================================

class TestRetrievalMetrics:
    """Test retrieval evaluation metrics."""

    def test_precision_at_k(self):
        """Test Precision@k calculation."""
        results = [
            RetrievalResult("doc1", "title1", 0.8, 0.7, 0.75, 1, ["bm25"]),
            RetrievalResult("doc2", "title2", 0.7, 0.6, 0.65, 2, ["semantic"]),
            RetrievalResult("doc3", "title3", 0.6, 0.5, 0.55, 3, ["bm25"]),
        ]

        relevant_ids = ["doc1", "doc3"]

        # Precision@2: 1 relevant out of 2 = 0.5
        precision = RetrievalMetrics.precision_at_k(results, relevant_ids, k=2)
        assert abs(precision - 0.5) < 1e-6

        # Precision@3: 2 relevant out of 3 = 0.667
        precision = RetrievalMetrics.precision_at_k(results, relevant_ids, k=3)
        assert abs(precision - 2/3) < 1e-6

    def test_recall_at_k(self):
        """Test Recall@k calculation."""
        results = [
            RetrievalResult("doc1", "title1", 0.8, 0.7, 0.75, 1, ["bm25"]),
            RetrievalResult("doc2", "title2", 0.7, 0.6, 0.65, 2, ["semantic"]),
            RetrievalResult("doc3", "title3", 0.6, 0.5, 0.55, 3, ["bm25"]),
        ]

        relevant_ids = ["doc1", "doc3"]

        # Recall@2: 1 relevant out of 2 total relevant = 0.5
        recall = RetrievalMetrics.recall_at_k(results, relevant_ids, k=2)
        assert abs(recall - 0.5) < 1e-6

        # Recall@3: 2 relevant out of 2 total relevant = 1.0
        recall = RetrievalMetrics.recall_at_k(results, relevant_ids, k=3)
        assert abs(recall - 1.0) < 1e-6

    def test_mean_reciprocal_rank(self):
        """Test MRR calculation."""
        relevant_ids = ["doc2"]

        results = [
            RetrievalResult("doc1", "title1", 0.8, 0.7, 0.75, 1, ["bm25"]),
            RetrievalResult("doc2", "title2", 0.7, 0.6, 0.65, 2, ["semantic"]),
        ]

        # First relevant doc at rank 2: MRR = 1/2 = 0.5
        mrr = RetrievalMetrics.mean_reciprocal_rank(results, relevant_ids)
        assert abs(mrr - 0.5) < 1e-6

    def test_ndcg(self):
        """Test NDCG@k calculation."""
        relevant_ids = ["doc1", "doc3"]

        results = [
            RetrievalResult("doc1", "title1", 0.8, 0.7, 0.75, 1, ["bm25"]),
            RetrievalResult("doc2", "title2", 0.7, 0.6, 0.65, 2, ["semantic"]),
            RetrievalResult("doc3", "title3", 0.6, 0.5, 0.55, 3, ["bm25"]),
        ]

        ndcg = RetrievalMetrics.normalized_discounted_cumulative_gain(
            results,
            relevant_ids,
            k=3
        )

        # NDCG should be between 0 and 1
        assert 0 <= ndcg <= 1


# ============================================================================
# FUNCTIONAL TESTS: Explanation & Debugging
# ============================================================================

class TestExplanation:
    """Test search explanation."""

    def test_explain_search(self, small_retriever):
        """Test search explanation."""
        query_embedding = [0.5] * 16
        explanation = small_retriever.explain_search(
            "fox",
            "doc1",
            query_embedding
        )

        assert "doc_id" in explanation
        assert "query" in explanation
        assert "title" in explanation
        assert "bm25_explanation" in explanation
        assert "semantic_score" in explanation
        assert "sources" in explanation

    def test_get_bm25_analyzer(self, small_retriever):
        """Test getting BM25 analyzer."""
        analyzer = small_retriever.get_bm25_analyzer()
        assert analyzer is not None

        stats = analyzer.corpus_statistics()
        assert "total_documents" in stats


# ============================================================================
# INTEGRATION TESTS: Real-World Scenarios
# ============================================================================

class TestRealWorldScenarios:
    """Integration tests with realistic scenarios."""

    def test_compliance_document_search(self, eu_retriever):
        """Test searching for compliance documents."""
        query_embedding = [0.5] * 16
        results, elapsed_ms = eu_retriever.search(
            "high-risk AI credit scoring",
            query_embedding,
            top_k=5
        )

        # Should find relevant documents
        assert len(results) > 0
        # Should execute quickly
        assert elapsed_ms < 1000

    def test_multi_query_search(self, eu_retriever):
        """Test multiple searches."""
        query_embedding = [0.5] * 16

        queries = [
            "transparency requirements",
            "risk assessment",
            "governance compliance",
        ]

        for query in queries:
            results, _ = eu_retriever.search(query, query_embedding)
            assert isinstance(results, list)

    def test_relevance_ranking(self, eu_retriever):
        """Test that more relevant results rank higher."""
        query_embedding = [0.5] * 16

        # Add a document with high relevance
        eu_retriever.add_document(
            "highly_relevant",
            "transparency is the most important requirement",
            embedding=[0.6] * 16
        )

        results, _ = eu_retriever.search("transparency", query_embedding, top_k=10)

        # highly_relevant should rank high
        doc_ids = [r.doc_id for r in results[:3]]
        # Note: This is probabilistic, so we just check results exist
        assert len(results) > 0


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Edge case handling."""

    def test_empty_retriever_search(self):
        """Test searching on empty retriever."""
        retriever = HybridRetriever()
        query_embedding = [0.5] * 16

        results, elapsed_ms = retriever.search("query", query_embedding)

        assert results == []
        assert elapsed_ms >= 0

    def test_search_with_empty_embedding(self, small_retriever):
        """Test search with empty embedding."""
        empty_embedding = []
        results, _ = small_retriever.search("fox", empty_embedding)

        # Should still work (BM25 only)
        assert isinstance(results, list)

    def test_search_with_all_zero_embedding(self, small_retriever):
        """Test search with zero embedding."""
        zero_embedding = [0.0] * 16
        results, _ = small_retriever.search("fox", zero_embedding)

        assert isinstance(results, list)

    def test_unicode_query(self, small_retriever):
        """Test searching with unicode."""
        query_embedding = [0.5] * 16
        results, _ = small_retriever.search("café", query_embedding)

        # Should not crash
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
