#!/usr/bin/env python3
"""Integration tests for L2 Hybrid Search."""

import pytest
import sys
from retrieval import HybridSearcher, SearchResult


class TestHybridSearcher:
    """Test suite for HybridSearcher."""

    @pytest.fixture
    def searcher(self):
        """Create searcher instance with test database."""
        try:
            s = HybridSearcher(
                db_host="localhost",
                db_port=5432,
                db_name="smaos_db",
                db_user="postgres",
                db_password="postgres"
            )
            yield s
            s.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_connection(self, searcher):
        """Test database connection."""
        assert searcher.conn is not None

    def test_semantic_search_latency(self, searcher):
        """Test semantic search latency <100ms."""
        results, elapsed_ms = searcher.search("transparency compliance", top_k=5)
        assert elapsed_ms < 100, f"Search took {elapsed_ms}ms, expected <100ms"
        print(f"Semantic search latency: {elapsed_ms}ms")

    def test_semantic_search_results(self, searcher):
        """Test semantic search returns results."""
        results, _ = searcher.search("Article 50 transparency", top_k=3)
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)
        print(f"Semantic search returned {len(results)} results")

    def test_keyword_search_transparency(self, searcher):
        """Test BM25 keyword search for 'transparency'."""
        results = searcher.keyword_search("transparency", top_k=5)
        assert len(results) > 0
        assert any("transparency" in r.title.lower() or "transparency" in r.article_id.lower()
                  for r in results)
        print(f"Keyword search for 'transparency' returned {len(results)} results")
        for r in results:
            print(f"  - {r.article_id}: {r.title} (score={r.score:.2f})")

    def test_keyword_search_high_risk(self, searcher):
        """Test BM25 keyword search for high-risk classification."""
        results = searcher.keyword_search("high-risk classification", top_k=5)
        assert len(results) > 0
        print(f"Keyword search for 'high-risk' returned {len(results)} results")

    def test_rrf_fusion_combines_sources(self, searcher):
        """Test RRF combines semantic and keyword results."""
        semantic = searcher.semantic_search("governance risk", top_k=5)
        keyword = searcher.keyword_search("governance risk", top_k=5)
        fused = searcher.rrf_fusion(semantic, keyword)

        assert len(fused) > 0
        assert all(r.source in ["semantic", "keyword", "semantic+keyword"] for r in fused)
        print(f"RRF fusion combined {len(semantic)} semantic + {len(keyword)} keyword results")

    def test_compliance_deadline_query(self, searcher):
        """Test query: hotel credit scoring Annex III deadline."""
        # This query tests both semantic understanding and keyword matching
        results, elapsed_ms = searcher.search(
            "hotel credit scoring Annex III deadline",
            top_k=3
        )
        assert elapsed_ms < 100
        assert len(results) > 0
        print(f"Query 'hotel credit scoring Annex III': found {len(results)} in {elapsed_ms}ms")
        for r in results:
            print(f"  Rank {r.rank}: {r.article_id} ({r.source}) - {r.title}")

    def test_glass_safety_query(self, searcher):
        """Test query: glass safety high-risk AI."""
        results, elapsed_ms = searcher.search(
            "glass safety high-risk AI Article 6",
            top_k=3
        )
        assert elapsed_ms < 100
        assert len(results) > 0
        print(f"Query 'glass safety high-risk': found {len(results)} in {elapsed_ms}ms")

    def test_article_transparency_query(self, searcher):
        """Test query: Article 50 transparency requirements."""
        results, elapsed_ms = searcher.search("Article 50 transparency", top_k=5)
        assert len(results) > 0
        assert elapsed_ms < 100
        assert any("transparency" in str(r.article_id).lower() for r in results)
        print(f"Query 'Article 50 transparency': {elapsed_ms}ms")

    def test_documentation_query(self, searcher):
        """Test query: documentation audit trail."""
        results, elapsed_ms = searcher.search("documentation audit trail", top_k=5)
        assert len(results) > 0
        assert elapsed_ms < 100
        print(f"Query 'documentation audit': {elapsed_ms}ms, {len(results)} results")

    def test_gdpr_privacy_query(self, searcher):
        """Test query: GDPR security encryption."""
        results, elapsed_ms = searcher.search("GDPR security encryption privacy", top_k=5)
        assert len(results) > 0
        assert elapsed_ms < 100
        print(f"Query 'GDPR security': {elapsed_ms}ms, {len(results)} results")

    def test_nist_rmf_query(self, searcher):
        """Test query: NIST RMF governance."""
        results, elapsed_ms = searcher.search("NIST risk management framework", top_k=5)
        assert len(results) > 0
        assert elapsed_ms < 100
        print(f"Query 'NIST RMF': {elapsed_ms}ms, {len(results)} results")

    def test_result_ranking(self, searcher):
        """Test that RRF produces valid rankings."""
        results, _ = searcher.search("transparency", top_k=5)
        ranks = [r.rank for r in results]
        assert ranks == sorted(ranks), "Results should be ranked in order"
        assert all(r.score > 0 for r in results), "All scores should be positive"

    def test_query_idempotence(self, searcher):
        """Test that same query returns same results."""
        results1, _ = searcher.search("high-risk", top_k=5)
        results2, _ = searcher.search("high-risk", top_k=5)
        assert len(results1) == len(results2)
        assert [r.article_id for r in results1] == [r.article_id for r in results2]

    def test_top_k_respected(self, searcher):
        """Test that top_k parameter is respected."""
        for k in [1, 3, 5, 10]:
            results, _ = searcher.search("policy", top_k=k)
            assert len(results) <= k, f"Expected <={k} results, got {len(results)}"


class TestLatencyBenchmark:
    """Latency benchmarks for Stream B success criteria."""

    @pytest.fixture
    def searcher(self):
        """Create searcher instance."""
        try:
            s = HybridSearcher()
            yield s
            s.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_compliance_query_latency(self, searcher):
        """Verify <100ms latency on compliance queries."""
        queries = [
            "Article 50 transparency",
            "hotel credit scoring Annex III",
            "glass safety high-risk AI",
            "GDPR security encryption",
            "NIST risk management"
        ]

        latencies = []
        for query in queries:
            _, elapsed_ms = searcher.search(query, top_k=5)
            latencies.append(elapsed_ms)
            assert elapsed_ms < 100, f"Query '{query}' took {elapsed_ms}ms"

        avg_latency = sum(latencies) / len(latencies)
        print(f"Average latency: {avg_latency:.1f}ms (target <100ms)")
        assert avg_latency < 100


if __name__ == "__main__":
    # Run tests
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-s"  # Show print statements
    ])
    sys.exit(exit_code)
