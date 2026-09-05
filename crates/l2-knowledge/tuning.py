#!/usr/bin/env python3
"""
Hybrid Retrieval Tuning: Parameter Optimization (L2 Knowledge Layer)

Optimizes hybrid retrieval via:
1. BM25 parameter tuning (k1, b)
2. RRF weighting optimization
3. Semantic similarity calibration
4. Batch processing with caching

Total: ~300 LOC, TDD-first implementation.
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from hybrid_retrieval import HybridRetriever


@dataclass
class TuningResult:
    """Result from parameter tuning."""
    best_k1: Optional[float] = None
    best_b: Optional[float] = None
    best_semantic_weight: Optional[float] = None
    best_keyword_weight: Optional[float] = None
    best_similarity_threshold: Optional[float] = None
    best_mrr: float = 0.0
    best_precision_at_5: float = 0.0
    best_recall_at_10: float = 0.0
    best_ndcg_at_10: float = 0.0
    grid_scores: List[Dict] = field(default_factory=list)


class TuningMetrics:
    """Evaluation metrics for retrieval tuning."""

    @staticmethod
    def mean_reciprocal_rank(
        results: List[Tuple[str, float]],
        relevant_ids: List[str]
    ) -> float:
        """Calculate Mean Reciprocal Rank (first relevant doc)."""
        if not relevant_ids:
            return 0.0

        relevant_set = set(relevant_ids)
        for rank, (doc_id, _) in enumerate(results, 1):
            if doc_id in relevant_set:
                return 1.0 / rank
        return 0.0

    @staticmethod
    def precision_at_k(
        results: List[Tuple[str, float]],
        relevant_ids: List[str],
        k: int = 5
    ) -> float:
        """Calculate Precision@K."""
        if not relevant_ids:
            return 0.0

        relevant_set = set(relevant_ids)
        top_k = results[:k]
        matches = sum(1 for doc_id, _ in top_k if doc_id in relevant_set)
        return matches / k if k > 0 else 0.0

    @staticmethod
    def recall_at_k(
        results: List[Tuple[str, float]],
        relevant_ids: List[str],
        k: int = 5
    ) -> float:
        """Calculate Recall@K."""
        if not relevant_ids:
            return 0.0

        relevant_set = set(relevant_ids)
        top_k = results[:k]
        matches = sum(1 for doc_id, _ in top_k if doc_id in relevant_set)
        return matches / len(relevant_ids) if len(relevant_ids) > 0 else 0.0

    @staticmethod
    def normalized_discounted_cumulative_gain(
        results: List[Tuple[str, float]],
        relevant_ids: List[str],
        k: int = 10
    ) -> float:
        """Calculate NDCG@K."""
        if not relevant_ids:
            return 0.0

        relevant_set = set(relevant_ids)
        top_k = results[:k]

        # Calculate DCG
        dcg = 0.0
        for rank, (doc_id, _) in enumerate(top_k, 1):
            if doc_id in relevant_set:
                dcg += 1.0 / (1.0 + __import__("math").log2(rank))

        # Calculate IDCG (ideal DCG)
        idcg = 0.0
        for rank in range(1, min(len(relevant_ids), k) + 1):
            idcg += 1.0 / (1.0 + __import__("math").log2(rank))

        if idcg == 0:
            return 0.0
        return dcg / idcg


class BM25Tuner:
    """Tune BM25 parameters (k1, b) via grid search."""

    def __init__(
        self,
        k1_candidates: Optional[List[float]] = None,
        b_candidates: Optional[List[float]] = None
    ):
        """Initialize BM25 tuner."""
        self.k1_candidates = k1_candidates or [0.5, 1.0, 1.5, 2.0]
        self.b_candidates = b_candidates or [0.5, 0.75, 1.0]

    def tune(
        self,
        corpus: Dict[str, Tuple[str, str, List[float]]],
        golden_queries: List[Tuple[str, List[str]]]
    ) -> TuningResult:
        """Tune BM25 parameters via grid search."""
        if not corpus or not golden_queries:
            return TuningResult()

        best_result = TuningResult()
        best_mrr = -1.0  # Start with -1 so first result is always selected

        for k1 in self.k1_candidates:
            for b in self.b_candidates:
                mrr = self._calculate_metric(corpus, golden_queries, k1, b)

                score_dict = {
                    "k1": k1,
                    "b": b,
                    "mrr": mrr
                }
                best_result.grid_scores.append(score_dict)

                if mrr > best_mrr:
                    best_mrr = mrr
                    best_result.best_k1 = k1
                    best_result.best_b = b
                    best_result.best_mrr = mrr

        return best_result

    def _calculate_metric(
        self,
        corpus: Dict[str, Tuple[str, str, List[float]]],
        golden_queries: List[Tuple[str, List[str]]],
        k1: float,
        b: float
    ) -> float:
        """Calculate MRR for given parameters."""
        retriever = HybridRetriever(k1=k1, b=b)

        for doc_id, (title, text, embedding) in corpus.items():
            retriever.add_document(doc_id, text, title=title, embedding=embedding)

        total_mrr = 0.0
        valid_queries = 0

        for query, relevant_ids in golden_queries:
            if not query or not relevant_ids:
                continue

            results = retriever.keyword_search(query, top_k=10)
            mrr = TuningMetrics.mean_reciprocal_rank(results, relevant_ids)

            total_mrr += mrr
            valid_queries += 1

        return total_mrr / valid_queries if valid_queries > 0 else 0.0


class RRFTuner:
    """Optimize RRF fusion weights (semantic vs keyword)."""

    def __init__(
        self,
        semantic_weights: Optional[List[float]] = None,
        keyword_weights: Optional[List[float]] = None
    ):
        """Initialize RRF tuner."""
        if semantic_weights is None:
            semantic_weights = [0.4, 0.5, 0.6]
        if keyword_weights is None:
            keyword_weights = [1.0 - w for w in semantic_weights]

        self.semantic_weights = semantic_weights
        self.keyword_weights = keyword_weights

    def tune(
        self,
        corpus: Dict[str, Tuple[str, str, List[float]]],
        golden_queries: List[Tuple[str, List[str]]]
    ) -> TuningResult:
        """Tune RRF weights via grid search."""
        if not corpus or not golden_queries:
            return TuningResult()

        best_result = TuningResult()
        best_precision = -1.0  # Start with -1 so first result is always selected

        for sem_w, kw_w in zip(self.semantic_weights, self.keyword_weights):
            precision = self._calculate_metric(
                corpus, golden_queries,
                sem_w, kw_w
            )

            score_dict = {
                "semantic_weight": sem_w,
                "keyword_weight": kw_w,
                "precision_at_5": precision
            }
            best_result.grid_scores.append(score_dict)

            if precision > best_precision:
                best_precision = precision
                best_result.best_semantic_weight = sem_w
                best_result.best_keyword_weight = kw_w
                best_result.best_precision_at_5 = precision

        return best_result

    def _calculate_metric(
        self,
        corpus: Dict[str, Tuple[str, str, List[float]]],
        golden_queries: List[Tuple[str, List[str]]],
        semantic_weight: float,
        keyword_weight: float
    ) -> float:
        """Calculate Precision@5 for given weights."""
        retriever = HybridRetriever(
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )

        for doc_id, (title, text, embedding) in corpus.items():
            retriever.add_document(doc_id, text, title=title, embedding=embedding)

        total_precision = 0.0
        valid_queries = 0

        for query, relevant_ids in golden_queries:
            if not query or not relevant_ids:
                continue

            # Get query embedding from first word (mock)
            query_emb = self._mock_embedding(query)

            semantic_results = retriever.semantic_search(query_emb, top_k=10)
            keyword_results = retriever.keyword_search(query, top_k=10)
            fusion_dict = retriever.rrf_fusion(semantic_results, keyword_results)

            # Sort by RRF score
            sorted_results = sorted(
                [(doc_id, data["rrf_score"]) for doc_id, data in fusion_dict.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]

            precision = TuningMetrics.precision_at_k(sorted_results, relevant_ids, k=5)
            total_precision += precision
            valid_queries += 1

        return total_precision / valid_queries if valid_queries > 0 else 0.0

    def _mock_embedding(self, text: str) -> List[float]:
        """Generate mock embedding."""
        h = hashlib.md5(text.encode()).hexdigest()
        return [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)][:16]


class SemanticTuner:
    """Calibrate semantic similarity threshold and embedding model."""

    def __init__(
        self,
        similarity_thresholds: Optional[List[float]] = None,
        embedding_model: str = "bge-small"
    ):
        """Initialize semantic tuner."""
        self.similarity_thresholds = similarity_thresholds or [0.5, 0.7, 0.9]
        self.embedding_model = embedding_model

    def tune(
        self,
        corpus: Dict[str, Tuple[str, str, List[float]]],
        golden_queries: List[Tuple[str, List[str]]]
    ) -> TuningResult:
        """Tune similarity threshold via grid search."""
        if not corpus or not golden_queries:
            return TuningResult()

        best_result = TuningResult()
        best_recall = -1.0  # Start with -1 so first result is always selected

        for threshold in self.similarity_thresholds:
            recall = self._calculate_metric(corpus, golden_queries, threshold)

            score_dict = {
                "similarity_threshold": threshold,
                "recall_at_10": recall
            }
            best_result.grid_scores.append(score_dict)

            if recall > best_recall:
                best_recall = recall
                best_result.best_similarity_threshold = threshold
                best_result.best_recall_at_10 = recall

        return best_result

    def _calculate_metric(
        self,
        corpus: Dict[str, Tuple[str, str, List[float]]],
        golden_queries: List[Tuple[str, List[str]]],
        similarity_threshold: float
    ) -> float:
        """Calculate Recall@10 for given threshold."""
        retriever = HybridRetriever()

        for doc_id, (title, text, embedding) in corpus.items():
            retriever.add_document(doc_id, text, title=title, embedding=embedding)

        total_recall = 0.0
        valid_queries = 0

        for query, relevant_ids in golden_queries:
            if not query or not relevant_ids:
                continue

            query_emb = self._mock_embedding(query)
            results = retriever.semantic_search(query_emb, top_k=10)

            # Filter by threshold
            filtered = [(doc_id, score) for doc_id, score in results
                       if score >= similarity_threshold]

            recall = TuningMetrics.recall_at_k(filtered, relevant_ids, k=10)
            total_recall += recall
            valid_queries += 1

        return total_recall / valid_queries if valid_queries > 0 else 0.0

    def _mock_embedding(self, text: str) -> List[float]:
        """Generate mock embedding."""
        h = hashlib.md5(text.encode()).hexdigest()
        return [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)][:16]


class BatchRetriever:
    """Batch processing for hybrid searches with caching."""

    def __init__(self, batch_size: int = 20, cache_enabled: bool = True):
        """Initialize batch retriever."""
        self.batch_size = batch_size
        self.cache_enabled = cache_enabled
        self.cache: Dict[str, List[Tuple[str, float]]] = {}

    def batch_search(
        self,
        corpus: Dict[str, Tuple[str, str, List[float]]],
        queries: List[str],
        top_k: int = 5,
        k1: float = 1.5,
        b: float = 0.75,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4
    ) -> List[List[Tuple[str, float]]]:
        """Search batch of queries."""
        retriever = HybridRetriever(
            k1=k1, b=b,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )

        for doc_id, (title, text, embedding) in corpus.items():
            retriever.add_document(doc_id, text, title=title, embedding=embedding)

        results_list = []

        # Process queries in batches
        for i in range(0, len(queries), self.batch_size):
            batch = queries[i:i+self.batch_size]

            for query in batch:
                cache_key = self._cache_key(query, top_k)

                if self.cache_enabled and cache_key in self.cache:
                    results = self.cache[cache_key]
                else:
                    query_emb = self._mock_embedding(query)
                    semantic_results = retriever.semantic_search(query_emb, top_k)
                    keyword_results = retriever.keyword_search(query, top_k)
                    fusion_dict = retriever.rrf_fusion(semantic_results, keyword_results)

                    results = sorted(
                        [(doc_id, data["rrf_score"]) for doc_id, data in fusion_dict.items()],
                        key=lambda x: x[1],
                        reverse=True
                    )[:top_k]

                    if self.cache_enabled:
                        self.cache[cache_key] = results

                results_list.append(results)

        return results_list

    def _cache_key(self, query: str, top_k: int) -> str:
        """Generate cache key."""
        key_str = f"{query}:{top_k}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _mock_embedding(self, text: str) -> List[float]:
        """Generate mock embedding."""
        h = hashlib.md5(text.encode()).hexdigest()
        return [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)][:16]


if __name__ == "__main__":
    print("Hybrid Retrieval Tuning (L2 Knowledge Layer)")
    print("Run: pytest test_tuning.py -v")
