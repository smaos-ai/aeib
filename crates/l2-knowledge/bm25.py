#!/usr/bin/env python3
"""
BM25 IDF Weighting for Hybrid Retrieval (L2 Knowledge Layer)

Implements Okapi BM25 ranking function:
  BM25(D, Q) = SUM over q in Q:
    IDF(q) * (f(q,D) * (k1+1)) / (f(q,D) + k1*(1-b+b*(|D|/avgdl)))

Where:
  - IDF(q) = log((N - n(q) + 0.5) / (n(q) + 0.5))
  - f(q,D) = term frequency in document D
  - |D| = document length (word count)
  - avgdl = average document length
  - N = total documents
  - n(q) = documents containing term q
  - k1 = 1.5 (term saturation parameter)
  - b = 0.75 (length normalization parameter)

Integration: BM25 scores fused with pgvector semantic scores via RRF.
"""

import re
import math
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict


@dataclass
class BM25Stats:
    """Statistics for BM25 calculation."""
    total_docs: int
    doc_freq: Dict[str, int]  # term -> count of docs containing term
    avg_doc_length: float
    doc_lengths: Dict[str, int]  # doc_id -> length in words


class BM25Tokenizer:
    """Tokenization for BM25 (case-insensitive, removes punctuation)."""

    # Common stopwords (EU AI Act context)
    STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
        'who', 'when', 'where', 'why', 'how', 'by', 'from', 'up', 'about',
        'as', 'if', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once'
    }

    def __init__(self, remove_stopwords: bool = False):
        self.remove_stopwords = remove_stopwords

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text: lowercase, split on non-alphanumeric."""
        # Lowercase
        text = text.lower()

        # Split on non-alphanumeric + hyphen
        tokens = re.findall(r'\b[\w-]+\b', text)

        # Remove stopwords if enabled
        if self.remove_stopwords:
            tokens = [t for t in tokens if t not in self.STOPWORDS]

        # Remove short tokens (< 2 chars)
        tokens = [t for t in tokens if len(t) >= 2]

        return tokens


class BM25Index:
    """BM25 index: maintains statistics for scoring."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 index.

        Args:
            k1: Term saturation parameter (default 1.5, range [1.2, 2.0])
            b: Length normalization parameter (default 0.75, range [0, 1])
        """
        self.k1 = k1
        self.b = b
        self.tokenizer = BM25Tokenizer(remove_stopwords=False)

        self.total_docs = 0
        self.doc_freq = defaultdict(int)  # term -> doc count
        self.doc_lengths = {}  # doc_id -> length
        self.doc_tokens = {}  # doc_id -> token list
        self.all_terms = set()

    def add_document(self, doc_id: str, text: str) -> None:
        """Add document to index."""
        tokens = self.tokenizer.tokenize(text)
        self.doc_tokens[doc_id] = tokens
        self.doc_lengths[doc_id] = len(tokens)
        self.total_docs += 1

        # Update document frequency for each unique term in doc
        seen_terms = set()
        for token in tokens:
            if token not in seen_terms:
                self.doc_freq[token] += 1
                self.all_terms.add(token)
                seen_terms.add(token)

    def remove_document(self, doc_id: str) -> None:
        """Remove document from index."""
        if doc_id not in self.doc_tokens:
            return

        tokens = self.doc_tokens[doc_id]
        seen_terms = set()

        for token in tokens:
            if token not in seen_terms:
                self.doc_freq[token] -= 1
                if self.doc_freq[token] == 0:
                    del self.doc_freq[token]
                    self.all_terms.discard(token)
                seen_terms.add(token)

        del self.doc_tokens[doc_id]
        del self.doc_lengths[doc_id]
        self.total_docs -= 1

    @property
    def avg_doc_length(self) -> float:
        """Average document length."""
        if not self.doc_lengths:
            return 0.0
        return sum(self.doc_lengths.values()) / len(self.doc_lengths)

    def idf(self, term: str) -> float:
        """
        Calculate IDF (Inverse Document Frequency).

        IDF(term) = log((N - n(term) + 0.5) / (n(term) + 0.5))
        Clamped to minimum 0.1 to ensure positive scores.
        """
        if self.total_docs == 0:
            return 0.0

        n_term = self.doc_freq.get(term, 0)
        numerator = self.total_docs - n_term + 0.5
        denominator = n_term + 0.5

        if denominator == 0:
            return 0.1

        idf_value = math.log(numerator / denominator)
        # Clamp IDF to minimum 0.1 to ensure positive scores
        return max(idf_value, 0.1)

    def score(self, doc_id: str, query_tokens: List[str]) -> float:
        """
        Calculate BM25 score for document against query.

        BM25(doc) = SUM over q in query:
          IDF(q) * (f(q,doc) * (k1+1)) / (f(q,doc) + k1*(1-b+b*(|doc|/avgdl)))
        """
        if doc_id not in self.doc_tokens:
            return 0.0

        score = 0.0
        doc_tokens = self.doc_tokens[doc_id]
        doc_length = self.doc_lengths[doc_id]
        avgdl = self.avg_doc_length

        for query_term in query_tokens:
            # Count frequency of query term in document
            freq = doc_tokens.count(query_term)

            if freq > 0:
                idf_score = self.idf(query_term)

                # BM25 formula
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (
                    (1 - self.b) + self.b * (doc_length / (avgdl + 1e-10))
                )

                score += idf_score * (numerator / denominator)

        return score

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Search: return top-k documents scored by BM25.

        Returns: [(doc_id, score), ...] sorted by score descending
        """
        query_tokens = self.tokenizer.tokenize(query)

        if not query_tokens:
            return []

        scores = []
        for doc_id in self.doc_tokens:
            score = self.score(doc_id, query_tokens)
            if score > 0:
                scores.append((doc_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_stats(self) -> BM25Stats:
        """Get index statistics."""
        return BM25Stats(
            total_docs=self.total_docs,
            doc_freq=dict(self.doc_freq),
            avg_doc_length=self.avg_doc_length,
            doc_lengths=self.doc_lengths.copy()
        )


class BM25Analyzer:
    """Analyze BM25 scoring (debugging, analysis)."""

    def __init__(self, index: BM25Index):
        self.index = index

    def explain_score(self, doc_id: str, query: str) -> Dict:
        """Explain BM25 score breakdown for a document."""
        query_tokens = self.index.tokenizer.tokenize(query)

        if doc_id not in self.index.doc_tokens:
            return {"error": "Document not found"}

        explanation = {
            "doc_id": doc_id,
            "query": query,
            "query_tokens": query_tokens,
            "doc_length": self.index.doc_lengths[doc_id],
            "avg_doc_length": self.index.avg_doc_length,
            "k1": self.index.k1,
            "b": self.index.b,
            "total_score": 0.0,
            "term_scores": {}
        }

        doc_tokens = self.index.doc_tokens[doc_id]

        for term in query_tokens:
            freq = doc_tokens.count(term)
            idf = self.index.idf(term)

            if freq > 0:
                doc_length = self.index.doc_lengths[doc_id]
                avgdl = self.index.avg_doc_length

                numerator = freq * (self.index.k1 + 1)
                denominator = freq + self.index.k1 * (
                    (1 - self.index.b) + self.index.b * (doc_length / (avgdl + 1e-10))
                )
                term_score = idf * (numerator / denominator)

                explanation["term_scores"][term] = {
                    "frequency": freq,
                    "idf": idf,
                    "score": term_score
                }
                explanation["total_score"] += term_score

        return explanation

    def term_statistics(self, term: str) -> Dict:
        """Get statistics for a term."""
        doc_freq = self.index.doc_freq.get(term, 0)
        idf = self.index.idf(term)

        # Find documents containing term
        docs_with_term = []
        for doc_id, tokens in self.index.doc_tokens.items():
            if term in tokens:
                docs_with_term.append(doc_id)

        return {
            "term": term,
            "document_frequency": doc_freq,
            "idf": idf,
            "docs_containing_term": docs_with_term,
            "percentage_coverage": (doc_freq / max(self.index.total_docs, 1)) * 100
        }

    def corpus_statistics(self) -> Dict:
        """Get overall corpus statistics."""
        if not self.index.doc_lengths:
            return {
                "total_documents": 0,
                "total_terms": 0,
                "avg_doc_length": 0.0
            }

        doc_lengths = list(self.index.doc_lengths.values())

        return {
            "total_documents": self.index.total_docs,
            "total_terms": len(self.index.all_terms),
            "avg_doc_length": self.index.avg_doc_length,
            "min_doc_length": min(doc_lengths),
            "max_doc_length": max(doc_lengths),
            "median_doc_length": sorted(doc_lengths)[len(doc_lengths) // 2],
            "vocabulary_size": len(self.index.all_terms)
        }
