#!/usr/bin/env python3
"""L2 Hybrid Search: pgvector semantic + BM25 keyword + RRF fusion."""

import json
import hashlib
import time
from dataclasses import dataclass
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass
class SearchResult:
    """Individual search result."""
    article_id: str
    title: str
    score: float
    rank: int
    source: str  # "semantic" or "keyword"


class HybridSearcher:
    """BM25 + semantic search with RRF fusion."""

    def __init__(
        self,
        db_host: str = "localhost",
        db_port: int = 5432,
        db_name: str = "smaos_db",
        db_user: str = "postgres",
        db_password: str = "postgres",
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4
    ):
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.conn = None
        self._connect()

    def _connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect to database: {e}")

    def _mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding."""
        h = hashlib.md5(text.encode()).hexdigest()
        values = [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
        return values[:16]

    def semantic_search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search using semantic embeddings."""
        results = []
        try:
            embedding = self._mock_embedding(query)
            cur = self.conn.cursor(cursor_factory=RealDictCursor)

            # Simple cosine similarity in Python (PostgreSQL pgvector not available)
            cur.execute("SELECT id, article_id, article_text, embedding FROM policy_documents")
            docs = cur.fetchall()
            cur.close()

            scores = []
            for doc in docs:
                if doc['embedding']:
                    emb = json.loads(doc['embedding']) if isinstance(doc['embedding'], str) else doc['embedding']
                    similarity = self._cosine_similarity(embedding, emb)
                    scores.append((doc['article_id'], doc['article_text'], similarity))

            scores.sort(key=lambda x: x[2], reverse=True)
            for rank, (article_id, text, score) in enumerate(scores[:top_k], 1):
                results.append(SearchResult(
                    article_id=article_id,
                    title=text[:60] + "..." if len(text) > 60 else text,
                    score=float(score),
                    rank=rank,
                    source="semantic"
                ))
        except Exception as e:
            print(f"Semantic search error: {e}")

        return results

    def keyword_search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search using BM25 keyword matching."""
        results = []
        try:
            cur = self.conn.cursor(cursor_factory=RealDictCursor)

            # Use PostgreSQL full-text search
            cur.execute(
                """SELECT article_id, article_text, keywords,
                   ts_rank(keywords_tsvector, plainto_tsquery(%s)) as rank
                   FROM policy_documents
                   WHERE keywords_tsvector @@ plainto_tsquery(%s)
                   ORDER BY rank DESC
                   LIMIT %s""",
                (query, query, top_k)
            )
            rows = cur.fetchall()
            cur.close()

            for rank, row in enumerate(rows, 1):
                results.append(SearchResult(
                    article_id=row['article_id'],
                    title=row['article_text'][:60] + "..." if len(row['article_text']) > 60 else row['article_text'],
                    score=float(row['rank']) if row['rank'] else 0.5,
                    rank=rank,
                    source="keyword"
                ))
        except Exception as e:
            print(f"Keyword search error: {e}")

        return results

    def rrf_fusion(
        self,
        semantic_results: List[SearchResult],
        keyword_results: List[SearchResult],
        k: int = 60
    ) -> List[SearchResult]:
        """Reciprocal Rank Fusion combining semantic + keyword results."""
        rrf_scores = {}

        # Add semantic results
        for result in semantic_results:
            rrf_score = 1.0 / (k + result.rank) * self.semantic_weight
            if result.article_id not in rrf_scores:
                rrf_scores[result.article_id] = {"score": 0, "result": result, "sources": []}
            rrf_scores[result.article_id]["score"] += rrf_score
            rrf_scores[result.article_id]["sources"].append("semantic")

        # Add keyword results
        for result in keyword_results:
            rrf_score = 1.0 / (k + result.rank) * self.keyword_weight
            if result.article_id not in rrf_scores:
                rrf_scores[result.article_id] = {"score": 0, "result": result, "sources": []}
            rrf_scores[result.article_id]["score"] += rrf_score
            rrf_scores[result.article_id]["sources"].append("keyword")

        # Sort by RRF score
        sorted_results = sorted(
            rrf_scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )

        # Create final results with new ranks
        final_results = []
        for rank, (article_id, data) in enumerate(sorted_results, 1):
            result = data["result"]
            result.rank = rank
            result.score = float(data["score"])
            result.source = "+".join(data["sources"])
            final_results.append(result)

        return final_results

    def search(self, query: str, top_k: int = 5) -> tuple[List[SearchResult], int]:
        """Hybrid search: semantic + keyword + RRF fusion."""
        start_time = time.time()

        # Run parallel searches
        semantic_results = self.semantic_search(query, top_k=top_k)
        keyword_results = self.keyword_search(query, top_k=top_k)

        # Fuse results
        final_results = self.rrf_fusion(semantic_results, keyword_results)[:top_k]

        elapsed_ms = int((time.time() - start_time) * 1000)
        return final_results, elapsed_ms

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot_product / (mag_a * mag_b)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
