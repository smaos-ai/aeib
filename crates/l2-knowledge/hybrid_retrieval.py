#!/usr/bin/env python3
"""
Hybrid Retrieval: BM25 + pgvector with RRF Fusion (L2 Knowledge Layer)

Integrates:
- BM25 IDF weighting for lexical/keyword search
- pgvector semantic embeddings (cosine similarity)
- Reciprocal Rank Fusion (RRF) to combine scores

Architecture:
  Query → [BM25 branch, Semantic branch] → RRF fusion → Ranked results
"""

import json
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from bm25 import BM25Index, BM25Tokenizer, BM25Analyzer


@dataclass
class RetrievalResult:
    """Retrieval result from hybrid search."""
    doc_id: str
    title: str
    bm25_score: float
    semantic_score: float
    rrf_score: float
    rrf_rank: int
    sources: List[str]  # ["bm25"] or ["semantic"] or ["bm25", "semantic"]


class HybridRetriever:
    """Hybrid retrieval: BM25 + semantic with RRF fusion."""

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        rrf_k: int = 60
    ):
        """
        Initialize hybrid retriever.

        Args:
            k1: BM25 term saturation (default 1.5)
            b: BM25 length normalization (default 0.75)
            semantic_weight: Weight for semantic results in RRF (default 0.6)
            keyword_weight: Weight for BM25 results in RRF (default 0.4)
            rrf_k: RRF parameter k (default 60)
        """
        self.bm25_index = BM25Index(k1=k1, b=b)
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.rrf_k = rrf_k

        # Document storage for retrieval
        self.documents = {}  # doc_id -> {"title": ..., "text": ..., "embedding": ...}

    def add_document(
        self,
        doc_id: str,
        text: str,
        title: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> None:
        """Add document to retriever."""
        self.documents[doc_id] = {
            "title": title or text[:100],
            "text": text,
            "embedding": embedding
        }
        self.bm25_index.add_document(doc_id, text)

    def remove_document(self, doc_id: str) -> None:
        """Remove document from retriever."""
        if doc_id in self.documents:
            del self.documents[doc_id]
        self.bm25_index.remove_document(doc_id)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Search using semantic similarity."""
        results = []

        for doc_id, doc_data in self.documents.items():
            if doc_data["embedding"]:
                similarity = self._cosine_similarity(
                    query_embedding,
                    doc_data["embedding"]
                )
                if similarity > 0:
                    results.append((doc_id, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def keyword_search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Search using BM25."""
        return self.bm25_index.search(query, top_k=top_k)

    def rrf_fusion(
        self,
        semantic_results: List[Tuple[str, float]],
        keyword_results: List[Tuple[str, float]],
    ) -> Dict[str, Dict]:
        """Reciprocal Rank Fusion combining both result sets."""
        fusion_scores = {}

        # Process semantic results
        for rank, (doc_id, score) in enumerate(semantic_results, 1):
            rrf_score = (1.0 / (self.rrf_k + rank)) * self.semantic_weight

            if doc_id not in fusion_scores:
                fusion_scores[doc_id] = {
                    "rrf_score": 0.0,
                    "bm25_score": 0.0,
                    "semantic_score": 0.0,
                    "sources": set()
                }

            fusion_scores[doc_id]["rrf_score"] += rrf_score
            fusion_scores[doc_id]["semantic_score"] = score
            fusion_scores[doc_id]["sources"].add("semantic")

        # Process keyword results
        for rank, (doc_id, score) in enumerate(keyword_results, 1):
            rrf_score = (1.0 / (self.rrf_k + rank)) * self.keyword_weight

            if doc_id not in fusion_scores:
                fusion_scores[doc_id] = {
                    "rrf_score": 0.0,
                    "bm25_score": 0.0,
                    "semantic_score": 0.0,
                    "sources": set()
                }

            fusion_scores[doc_id]["rrf_score"] += rrf_score
            fusion_scores[doc_id]["bm25_score"] = score
            fusion_scores[doc_id]["sources"].add("bm25")

        return fusion_scores

    def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5
    ) -> Tuple[List[RetrievalResult], int]:
        """Hybrid search: BM25 + semantic + RRF fusion."""
        start_time = time.time()

        # BM25 search
        keyword_results = self.keyword_search(query, top_k=top_k)

        # Semantic search (if embedding provided)
        semantic_results = []
        if query_embedding:
            semantic_results = self.semantic_search(query_embedding, top_k=top_k)

        # RRF fusion
        fusion_scores = self.rrf_fusion(semantic_results, keyword_results)

        # Sort by RRF score and rank
        sorted_docs = sorted(
            fusion_scores.items(),
            key=lambda x: x[1]["rrf_score"],
            reverse=True
        )

        # Create final results
        results = []
        for rank, (doc_id, scores) in enumerate(sorted_docs[:top_k], 1):
            if doc_id not in self.documents:
                continue

            doc_data = self.documents[doc_id]
            results.append(RetrievalResult(
                doc_id=doc_id,
                title=doc_data["title"],
                bm25_score=scores["bm25_score"],
                semantic_score=scores["semantic_score"],
                rrf_score=scores["rrf_score"],
                rrf_rank=rank,
                sources=sorted(list(scores["sources"]))
            ))

        elapsed_ms = int((time.time() - start_time) * 1000)
        return results, elapsed_ms

    def get_bm25_analyzer(self) -> BM25Analyzer:
        """Get BM25 analyzer for debugging."""
        from bm25 import BM25Analyzer
        return BM25Analyzer(self.bm25_index)

    def explain_search(
        self,
        query: str,
        doc_id: str,
        query_embedding: Optional[List[float]] = None
    ) -> Dict:
        """Explain search score for a document."""
        analyzer = self.get_bm25_analyzer()

        explanation = {
            "doc_id": doc_id,
            "query": query,
            "title": self.documents.get(doc_id, {}).get("title", ""),
            "bm25_explanation": analyzer.explain_score(doc_id, query),
            "semantic_score": 0.0,
            "sources": []
        }

        # Semantic explanation
        if query_embedding and doc_id in self.documents:
            doc_embedding = self.documents[doc_id].get("embedding")
            if doc_embedding:
                explanation["semantic_score"] = self._cosine_similarity(
                    query_embedding,
                    doc_embedding
                )
                explanation["sources"].append("semantic")

        if explanation["bm25_explanation"]["total_score"] > 0:
            explanation["sources"].append("bm25")

        return explanation


class HybridIndexBuilder:
    """Builder for constructing hybrid retriever from corpus."""

    def __init__(self):
        self.retriever = HybridRetriever()

    def add_document(
        self,
        doc_id: str,
        text: str,
        title: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> "HybridIndexBuilder":
        """Add document (fluent API)."""
        self.retriever.add_document(doc_id, text, title, embedding)
        return self

    def build(self) -> HybridRetriever:
        """Build and return retriever."""
        return self.retriever


# ============================================================================
# Statistics & Metrics
# ============================================================================

class RetrievalMetrics:
    """Calculate retrieval metrics (precision, recall, MRR, NDCG)."""

    @staticmethod
    def precision_at_k(results: List[RetrievalResult], relevant_ids: List[str], k: int) -> float:
        """Calculate Precision@k."""
        if not results or not relevant_ids:
            return 0.0

        retrieved_ids = [r.doc_id for r in results[:k]]
        relevant_retrieved = sum(1 for doc_id in retrieved_ids if doc_id in relevant_ids)

        return relevant_retrieved / k if k > 0 else 0.0

    @staticmethod
    def recall_at_k(results: List[RetrievalResult], relevant_ids: List[str], k: int) -> float:
        """Calculate Recall@k."""
        if not results or not relevant_ids:
            return 0.0

        retrieved_ids = [r.doc_id for r in results[:k]]
        relevant_retrieved = sum(1 for doc_id in retrieved_ids if doc_id in relevant_ids)

        return relevant_retrieved / len(relevant_ids) if len(relevant_ids) > 0 else 0.0

    @staticmethod
    def mean_reciprocal_rank(results: List[RetrievalResult], relevant_ids: List[str]) -> float:
        """Calculate Mean Reciprocal Rank (MRR)."""
        if not results or not relevant_ids:
            return 0.0

        for rank, result in enumerate(results, 1):
            if result.doc_id in relevant_ids:
                return 1.0 / rank

        return 0.0

    @staticmethod
    def normalized_discounted_cumulative_gain(
        results: List[RetrievalResult],
        relevant_ids: List[str],
        k: int = 10
    ) -> float:
        """Calculate NDCG@k."""
        if not results or not relevant_ids:
            return 0.0

        # DCG: sum of rel(i) / log2(i+1) for top-k
        dcg = 0.0
        for rank, result in enumerate(results[:k], 1):
            rel = 1.0 if result.doc_id in relevant_ids else 0.0
            dcg += rel / (math.log(rank + 1) / math.log(2))

        # IDCG: ideal DCG (all relevant docs ranked first)
        idcg = 0.0
        for rank in range(1, min(k, len(relevant_ids)) + 1):
            idcg += 1.0 / (math.log(rank + 1) / math.log(2))

        if idcg == 0:
            return 0.0

        return dcg / idcg


import math
