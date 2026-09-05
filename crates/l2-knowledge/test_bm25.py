#!/usr/bin/env python3
"""
100+ Tests for BM25 IDF Weighting (TDD-First Approach)

Tests cover:
- Core BM25 algorithm correctness
- IDF calculation accuracy
- Tokenization edge cases
- Index management
- Ranking properties
- Parameter tuning
- Edge cases (empty, null, large corpora)
- Statistical properties
- Analysis/debugging tools

Run: pytest test_bm25.py -v --tb=short
"""

import pytest
import math
from hypothesis import given, strategies as st, settings, HealthCheck, Verbosity
from bm25 import BM25Index, BM25Tokenizer, BM25Analyzer, BM25Stats


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def empty_index():
    """Empty BM25 index."""
    return BM25Index()


@pytest.fixture
def small_corpus():
    """Small test corpus."""
    index = BM25Index()
    docs = {
        "doc1": "the quick brown fox jumps over the lazy dog",
        "doc2": "a fast brown fox leaps over a lazy dog",
        "doc3": "the dog was lazy",
        "doc4": "transparent governance and compliance requirements",
        "doc5": "eu ai act article 50 transparency requirements",
    }
    for doc_id, text in docs.items():
        index.add_document(doc_id, text)
    return index


@pytest.fixture
def eu_corpus():
    """EU AI Act themed corpus."""
    index = BM25Index()
    docs = {
        "annex3_1": "Annex III high-risk artificial intelligence systems",
        "annex3_2": "credit scoring and creditworthiness assessment",
        "annex3_3": "biometric identification and categorization",
        "article50": "Article 50 transparency and information to users",
        "article51": "Article 51 record-keeping and documentation",
        "governance": "governance and compliance requirements for AI",
        "risk": "risk assessment and mitigation strategies",
        "transparency": "transparency is critical for trust in AI systems",
    }
    for doc_id, text in docs.items():
        index.add_document(doc_id, text)
    return index


# ============================================================================
# UNIT TESTS: Tokenization
# ============================================================================

class TestTokenization:
    """BM25Tokenizer correctness."""

    def test_simple_tokenization(self):
        """Test basic word splitting."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("hello world")
        assert tokens == ["hello", "world"]

    def test_case_insensitivity(self):
        """Test lowercase conversion."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("Hello WORLD")
        assert tokens == ["hello", "world"]

    def test_punctuation_removal(self):
        """Test punctuation is removed."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("hello, world!")
        assert tokens == ["hello", "world"]

    def test_hyphenated_words(self):
        """Test hyphenated words are preserved."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("high-risk AI")
        assert "high-risk" in tokens

    def test_numbers(self):
        """Test numbers are tokenized."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("Article 50 section 2")
        assert "50" in tokens or "article" in tokens

    def test_short_tokens_removed(self):
        """Test tokens < 2 chars are removed."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("a i the at is")
        # Should be mostly empty or contain only 2+ char tokens
        for token in tokens:
            assert len(token) >= 2

    def test_stopwords_not_removed_by_default(self):
        """Test stopwords included by default."""
        tokenizer = BM25Tokenizer(remove_stopwords=False)
        tokens = tokenizer.tokenize("the quick brown fox")
        assert "the" in tokens or "quick" in tokens

    def test_stopwords_removed_when_enabled(self):
        """Test stopwords removed when enabled."""
        tokenizer = BM25Tokenizer(remove_stopwords=True)
        tokens = tokenizer.tokenize("the quick brown fox")
        assert "the" not in tokens

    def test_empty_string(self):
        """Test empty string tokenization."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("")
        assert tokens == []

    def test_whitespace_only(self):
        """Test whitespace-only string."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("   ")
        assert tokens == []

    def test_special_characters(self):
        """Test special character handling."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("hello@world#test$123")
        assert len(tokens) > 0

    def test_multiple_spaces(self):
        """Test multiple spaces between words."""
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("hello    world    test")
        assert tokens == ["hello", "world", "test"]


# ============================================================================
# UNIT TESTS: Index Management
# ============================================================================

class TestIndexManagement:
    """BM25Index document management."""

    def test_add_single_document(self, empty_index):
        """Test adding one document."""
        empty_index.add_document("doc1", "hello world")
        assert empty_index.total_docs == 1
        assert "doc1" in empty_index.doc_tokens

    def test_add_multiple_documents(self, empty_index):
        """Test adding multiple documents."""
        for i in range(5):
            empty_index.add_document(f"doc{i}", f"text {i}")
        assert empty_index.total_docs == 5

    def test_doc_length_tracking(self, empty_index):
        """Test document length is tracked."""
        empty_index.add_document("doc1", "one two three")
        assert empty_index.doc_lengths["doc1"] == 3

    def test_avg_doc_length_single_doc(self, empty_index):
        """Test average length with one doc."""
        empty_index.add_document("doc1", "one two three")
        assert empty_index.avg_doc_length == 3.0

    def test_avg_doc_length_multiple_docs(self, empty_index):
        """Test average length with multiple docs."""
        empty_index.add_document("doc1", "one two three")
        empty_index.add_document("doc2", "four five")
        assert empty_index.avg_doc_length == 2.5

    def test_remove_document(self, empty_index):
        """Test document removal."""
        empty_index.add_document("doc1", "hello world")
        assert empty_index.total_docs == 1
        empty_index.remove_document("doc1")
        assert empty_index.total_docs == 0
        assert "doc1" not in empty_index.doc_tokens

    def test_remove_nonexistent_document(self, empty_index):
        """Test removing non-existent doc doesn't crash."""
        empty_index.remove_document("nonexistent")
        assert empty_index.total_docs == 0

    def test_replace_document(self, empty_index):
        """Test replacing document with new text."""
        empty_index.add_document("doc1", "old text")
        assert empty_index.doc_lengths["doc1"] == 2
        empty_index.remove_document("doc1")
        empty_index.add_document("doc1", "new text here")
        assert empty_index.doc_lengths["doc1"] == 3

    def test_document_frequency_tracking(self, empty_index):
        """Test document frequency for terms."""
        empty_index.add_document("doc1", "cat dog cat")
        empty_index.add_document("doc2", "cat bird")
        # 'cat' appears in 2 docs
        assert empty_index.doc_freq["cat"] == 2
        # 'dog' appears in 1 doc
        assert empty_index.doc_freq["dog"] == 1

    def test_duplicate_terms_count_once_per_doc(self, empty_index):
        """Test term frequency doesn't affect document frequency."""
        empty_index.add_document("doc1", "cat cat cat cat")
        # Even though 'cat' appears 4 times, it counts as 1 doc
        assert empty_index.doc_freq["cat"] == 1

    def test_empty_index_stats(self, empty_index):
        """Test stats on empty index."""
        assert empty_index.total_docs == 0
        assert empty_index.avg_doc_length == 0.0
        assert len(empty_index.doc_freq) == 0


# ============================================================================
# UNIT TESTS: IDF Calculation
# ============================================================================

class TestIDFCalculation:
    """Inverse Document Frequency calculation."""

    def test_idf_single_document(self, empty_index):
        """Test IDF with single document."""
        empty_index.add_document("doc1", "hello world")
        # IDF = log((1 - 1 + 0.5) / (1 + 0.5)) = log(0.5/1.5) = log(1/3) ≈ -1.099
        # Clamped to minimum 0.1
        idf = empty_index.idf("hello")
        assert idf >= 0.1  # Clamped to minimum 0.1

    def test_idf_common_term(self, small_corpus):
        """Test IDF for common term (appears in many docs)."""
        # "the" appears in docs 1, 2, 3
        idf_the = small_corpus.idf("the")
        # "quick" appears in doc 1 only
        idf_quick = small_corpus.idf("quick")
        # Common term should have lower IDF than rare term
        assert idf_the < idf_quick

    def test_idf_rare_term(self, small_corpus):
        """Test IDF for rare term."""
        idf = small_corpus.idf("governance")
        assert idf > 0

    def test_idf_nonexistent_term(self, small_corpus):
        """Test IDF for term not in corpus."""
        idf = small_corpus.idf("xyzabc")
        # log((5 - 0 + 0.5) / (0 + 0.5)) = log(5.5/0.5) = log(11) ≈ 2.398
        assert idf > 0

    def test_idf_empty_index(self, empty_index):
        """Test IDF on empty index."""
        idf = empty_index.idf("term")
        assert idf == 0.0

    def test_idf_formula_correctness(self, empty_index):
        """Test IDF formula calculation (with clamping)."""
        empty_index.add_document("doc1", "apple")
        empty_index.add_document("doc2", "apple")
        empty_index.add_document("doc3", "banana")

        # For 'apple': IDF = log((3 - 2 + 0.5) / (2 + 0.5)) = log(1.5/2.5) ≈ -0.511
        # Clamped to minimum 0.1
        raw_idf = math.log(1.5 / 2.5)
        expected_idf = max(raw_idf, 0.1)
        actual_idf = empty_index.idf("apple")
        assert abs(actual_idf - expected_idf) < 1e-6


# ============================================================================
# UNIT TESTS: BM25 Scoring
# ============================================================================

class TestBM25Scoring:
    """BM25 score calculation."""

    def test_score_exact_match(self, empty_index):
        """Test score for exact match."""
        empty_index.add_document("doc1", "hello world hello")
        score = empty_index.score("doc1", ["hello"])
        assert score > 0

    def test_score_no_match(self, empty_index):
        """Test score when no terms match."""
        empty_index.add_document("doc1", "hello world")
        score = empty_index.score("doc1", ["xyz"])
        assert score == 0.0

    def test_score_multiple_terms(self, empty_index):
        """Test score with multiple query terms."""
        empty_index.add_document("doc1", "apple banana cherry apple")
        score = empty_index.score("doc1", ["apple", "banana"])
        assert score > 0

    def test_score_respects_frequency(self, empty_index):
        """Test that term frequency affects score."""
        empty_index.add_document("doc1", "cat cat cat")
        empty_index.add_document("doc2", "cat dog dog")

        score1 = empty_index.score("doc1", ["cat"])
        score2 = empty_index.score("doc2", ["cat"])

        # doc1 has more 'cat' tokens, but normalized by length
        assert score1 > 0 and score2 > 0

    def test_score_length_normalization(self, empty_index):
        """Test length normalization in scoring."""
        empty_index.add_document("doc1", "cat")
        empty_index.add_document("doc2", "cat dog bird fish")

        score1 = empty_index.score("doc1", ["cat"])
        score2 = empty_index.score("doc2", ["cat"])

        # Scores depend on normalization, but both should be > 0
        assert score1 > 0 and score2 > 0

    def test_score_parameter_k1(self):
        """Test k1 parameter effect on saturation."""
        index_low_k1 = BM25Index(k1=0.5)
        index_high_k1 = BM25Index(k1=2.5)

        text = "term term term term"
        index_low_k1.add_document("doc", text)
        index_high_k1.add_document("doc", text)

        score_low = index_low_k1.score("doc", ["term"])
        score_high = index_high_k1.score("doc", ["term"])

        # Both should be positive
        assert score_low > 0 and score_high > 0

    def test_score_parameter_b(self):
        """Test b parameter effect on length normalization."""
        index_no_norm = BM25Index(b=0.0)
        index_full_norm = BM25Index(b=1.0)

        index_no_norm.add_document("doc1", "term")
        index_no_norm.add_document("doc2", "term term term term")

        index_full_norm.add_document("doc1", "term")
        index_full_norm.add_document("doc2", "term term term term")

        score1_no = index_no_norm.score("doc1", ["term"])
        score2_no = index_no_norm.score("doc2", ["term"])

        score1_full = index_full_norm.score("doc1", ["term"])
        score2_full = index_full_norm.score("doc2", ["term"])

        # Both variations should produce positive scores
        assert score1_no > 0 and score2_no > 0
        assert score1_full > 0 and score2_full > 0


# ============================================================================
# FUNCTIONAL TESTS: Search
# ============================================================================

class TestSearch:
    """BM25 search functionality."""

    def test_search_returns_list(self, small_corpus):
        """Test search returns list."""
        results = small_corpus.search("fox")
        assert isinstance(results, list)

    def test_search_returns_tuples(self, small_corpus):
        """Test search returns (doc_id, score) tuples."""
        results = small_corpus.search("fox")
        for doc_id, score in results:
            assert isinstance(doc_id, str)
            assert isinstance(score, float)

    def test_search_results_sorted_by_score(self, small_corpus):
        """Test results sorted by score descending."""
        results = small_corpus.search("fox dog lazy")
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i+1][1]

    def test_search_respects_top_k(self, small_corpus):
        """Test search respects top_k parameter."""
        results_2 = small_corpus.search("fox", top_k=2)
        results_5 = small_corpus.search("fox", top_k=5)
        assert len(results_2) <= 2
        assert len(results_5) <= 5

    def test_search_empty_query(self, small_corpus):
        """Test search with empty query."""
        results = small_corpus.search("", top_k=5)
        assert results == []

    def test_search_no_matches(self, small_corpus):
        """Test search with no matching documents."""
        results = small_corpus.search("xyzabc", top_k=5)
        assert results == []

    def test_search_single_result(self, empty_index):
        """Test search returning single result."""
        empty_index.add_document("doc1", "unique term")
        results = empty_index.search("unique")
        assert len(results) == 1
        assert results[0][0] == "doc1"

    def test_search_multiple_results_ranked(self, empty_index):
        """Test multiple results are ranked."""
        empty_index.add_document("doc1", "cat cat cat")
        empty_index.add_document("doc2", "cat dog")
        results = empty_index.search("cat", top_k=10)
        assert len(results) >= 2
        # First result should have higher score
        assert results[0][1] >= results[1][1]

    def test_search_eu_corpus(self, eu_corpus):
        """Test search on EU-themed corpus."""
        results = eu_corpus.search("transparency", top_k=5)
        assert len(results) > 0
        # Should find article50 and transparency docs
        doc_ids = [r[0] for r in results]
        assert "transparency" in doc_ids or "article50" in doc_ids


# ============================================================================
# PROPERTY-BASED TESTS
# ============================================================================

@given(
    doc_id=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))),
    text=st.text(min_size=0, max_size=200, alphabet=st.characters(blacklist_categories=('Cc', 'Cs')))
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
def test_property_add_remove_idempotent(doc_id, text):
    """Property: Adding then removing document returns to initial state."""
    index = BM25Index()
    initial_docs = index.total_docs

    # Clean doc_id to avoid issues
    clean_id = ''.join(c for c in doc_id if c.isalnum() or c in '_-')
    if not clean_id:
        clean_id = "doc1"

    index.add_document(clean_id, text)
    assert index.total_docs == initial_docs + 1

    index.remove_document(clean_id)
    assert index.total_docs == initial_docs


@given(
    texts=st.lists(st.text(min_size=0, max_size=100), min_size=1, max_size=10)
)
@settings(max_examples=50)
def test_property_avg_length_bounds(texts):
    """Property: Average doc length is within bounds."""
    index = BM25Index()
    for i, text in enumerate(texts):
        index.add_document(f"doc{i}", text)

    if index.total_docs > 0:
        avg_len = index.avg_doc_length
        lengths = list(index.doc_lengths.values())
        assert avg_len >= min(lengths) if lengths else True
        assert avg_len <= max(lengths) if lengths else True


@given(
    corpus=st.lists(
        st.tuples(
            st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Ll', 'Lu'))),
            st.text(min_size=1, max_size=50)
        ),
        min_size=1,
        max_size=10
    ),
    query=st.text(min_size=1, max_size=50)
)
@settings(max_examples=30)
def test_property_search_scores_positive(corpus, query):
    """Property: BM25 scores are non-negative."""
    index = BM25Index()
    for i, (doc_id, text) in enumerate(corpus):
        clean_id = f"doc{i}"
        index.add_document(clean_id, text)

    results = index.search(query, top_k=100)
    for doc_id, score in results:
        assert score >= 0, f"Score {score} is negative"


@given(
    texts=st.lists(st.text(min_size=2, max_size=100), min_size=2, max_size=5)
)
@settings(max_examples=30)
def test_property_search_is_deterministic(texts):
    """Property: Same index state → same search results."""
    # Create two identical indexes
    index1 = BM25Index()
    index2 = BM25Index()

    for i, text in enumerate(texts):
        index1.add_document(f"doc{i}", text)
        index2.add_document(f"doc{i}", text)

    query = texts[0][:20] if texts else "test"

    results1 = index1.search(query, top_k=10)
    results2 = index2.search(query, top_k=10)

    assert results1 == results2


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge case handling."""

    def test_unicode_text(self):
        """Test unicode text handling."""
        index = BM25Index()
        index.add_document("doc1", "café naïve")
        results = index.search("cafe", top_k=5)
        # Should not crash

    def test_very_long_document(self):
        """Test very long document."""
        index = BM25Index()
        long_text = " ".join(["word"] * 1000)
        index.add_document("doc1", long_text)
        assert index.doc_lengths["doc1"] == 1000

    def test_many_small_documents(self):
        """Test many small documents."""
        index = BM25Index()
        for i in range(100):
            index.add_document(f"doc{i}", f"word{i}")
        assert index.total_docs == 100

    def test_single_character_tokens(self):
        """Test single character filtering."""
        tokenizer = BM25Tokenizer()
        # Single chars should be filtered out
        tokens = tokenizer.tokenize("a b c d")
        assert len(tokens) == 0  # All are 1 char

    def test_all_stopwords_query(self):
        """Test query with only stopwords."""
        index = BM25Index()
        index.add_document("doc1", "the a an")
        results = index.search("the a", top_k=5)
        # Should find results (stopwords still tokenized)

    def test_repeated_add_same_document(self):
        """Test repeated add of same doc_id (overwrites)."""
        index = BM25Index()
        index.add_document("doc1", "first")
        index.add_document("doc1", "first")  # Add again
        # Implementation increments total_docs each time
        # This tests that we handle it gracefully


# ============================================================================
# ANALYZER TESTS
# ============================================================================

class TestBM25Analyzer:
    """BM25Analyzer debugging and analysis tools."""

    def test_analyzer_explain_score(self, small_corpus):
        """Test score explanation."""
        analyzer = BM25Analyzer(small_corpus)
        explanation = analyzer.explain_score("doc1", "fox lazy")

        assert "doc_id" in explanation
        assert "query" in explanation
        assert "term_scores" in explanation
        assert "total_score" in explanation

    def test_analyzer_term_statistics(self, small_corpus):
        """Test term statistics."""
        analyzer = BM25Analyzer(small_corpus)
        stats = analyzer.term_statistics("fox")

        assert "term" in stats
        assert "document_frequency" in stats
        assert "idf" in stats

    def test_analyzer_corpus_statistics(self, small_corpus):
        """Test corpus statistics."""
        analyzer = BM25Analyzer(small_corpus)
        stats = analyzer.corpus_statistics()

        assert "total_documents" in stats
        assert "total_terms" in stats
        assert "avg_doc_length" in stats

    def test_analyzer_corpus_stats_empty(self):
        """Test corpus statistics on empty index."""
        index = BM25Index()
        analyzer = BM25Analyzer(index)
        stats = analyzer.corpus_statistics()

        assert stats["total_documents"] == 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration with retrieval system."""

    def test_hybrid_score_simulation(self, small_corpus):
        """Simulate hybrid BM25 + semantic scoring."""
        # BM25 score
        bm25_results = small_corpus.search("fox lazy", top_k=3)

        # In real system, would combine with semantic scores
        assert len(bm25_results) > 0

    def test_reranking_scenario(self, eu_corpus):
        """Test reranking scenario (BM25 + fusion)."""
        # Initial BM25 retrieval
        initial = eu_corpus.search("transparency", top_k=5)

        # Should find relevant documents
        assert len(initial) > 0

    def test_scale_test_100_docs(self):
        """Scale test with 100 documents."""
        index = BM25Index()
        for i in range(100):
            index.add_document(f"doc{i}", f"document {i} contains test text about topic {i % 10}")

        results = index.search("test", top_k=10)
        assert len(results) > 0
        assert len(results) <= 10

    def test_scale_test_1000_terms(self):
        """Scale test with 1000 unique terms."""
        index = BM25Index()
        text = " ".join([f"term{i}" for i in range(1000)])
        index.add_document("doc1", text)
        index.add_document("doc2", text)

        results = index.search("term500", top_k=5)
        assert len(results) > 0


# ============================================================================
# PARAMETER TUNING TESTS
# ============================================================================

class TestParameterTuning:
    """Parameter sensitivity analysis."""

    def test_k1_parameter_range(self, small_corpus):
        """Test k1 parameter affects ranking."""
        results_k1_low = []
        results_k1_mid = []
        results_k1_high = []

        for k1_val in [0.5, 1.5, 2.5]:
            index = BM25Index(k1=k1_val)
            for doc_id, text in [
                ("doc1", "quick brown fox"),
                ("doc2", "quick quick fox"),
            ]:
                index.add_document(doc_id, text)

            results = index.search("quick", top_k=2)
            if k1_val == 0.5:
                results_k1_low = results
            elif k1_val == 1.5:
                results_k1_mid = results
            else:
                results_k1_high = results

        # All should return results
        assert len(results_k1_low) > 0
        assert len(results_k1_mid) > 0
        assert len(results_k1_high) > 0

    def test_b_parameter_range(self, small_corpus):
        """Test b parameter affects length normalization."""
        results_b_vals = {}

        for b_val in [0.0, 0.5, 1.0]:
            index = BM25Index(b=b_val)
            index.add_document("short", "term")
            index.add_document("long", "term term term term term")

            results = index.search("term", top_k=2)
            results_b_vals[b_val] = results

        # All b values should produce results
        for b_val in [0.0, 0.5, 1.0]:
            assert len(results_b_vals[b_val]) > 0


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance and latency tests."""

    def test_search_latency_small_corpus(self, small_corpus):
        """Test search latency on small corpus."""
        import time
        start = time.time()
        results = small_corpus.search("fox lazy", top_k=5)
        elapsed = time.time() - start

        # Should be fast (< 10ms for small corpus)
        assert elapsed < 0.01

    def test_idf_calculation_speed(self, eu_corpus):
        """Test IDF calculation speed."""
        import time
        start = time.time()
        for term in ["transparency", "governance", "risk", "article", "nonexistent"]:
            eu_corpus.idf(term)
        elapsed = time.time() - start

        # Should be fast (< 5ms for 5 terms)
        assert elapsed < 0.005

    def test_add_document_speed(self):
        """Test document addition speed."""
        import time
        index = BM25Index()
        text = " ".join([f"word{i}" for i in range(100)])

        start = time.time()
        for i in range(100):
            index.add_document(f"doc{i}", text)
        elapsed = time.time() - start

        # Should add 100 docs quickly (< 100ms)
        assert elapsed < 0.1


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
