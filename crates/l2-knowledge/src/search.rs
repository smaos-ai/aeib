use serde::{Deserialize, Serialize};
use std::time::Instant;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub article_id: String,
    pub title: String,
    pub score: f32,
    pub rank: u32,
    pub source: String,
}

/// Hybrid search combiner for BM25 keyword + semantic search
/// Uses Reciprocal Rank Fusion (RRF) to combine results
pub struct HybridSearcher {
    semantic_weight: f32,
    keyword_weight: f32,
}

impl HybridSearcher {
    /// Create new hybrid searcher with configurable weights
    pub fn new(semantic_weight: f32, keyword_weight: f32) -> Self {
        Self {
            semantic_weight,
            keyword_weight,
        }
    }

    /// Hybrid search: semantic + keyword + RRF fusion
    /// Returns results and elapsed time in milliseconds
    pub fn search(&self, query: &str) -> (Vec<SearchResult>, u64) {
        let start = Instant::now();

        // In production, these would query the PostgreSQL database
        // For now, return example results demonstrating hybrid search
        let semantic_results = self.semantic_search_results(query);
        let keyword_results = self.keyword_search_results(query);

        let fused = self.rrf_combine(semantic_results, keyword_results);
        let elapsed = start.elapsed().as_millis() as u64;
        (fused, elapsed)
    }

    /// Semantic search on policy embeddings
    fn semantic_search_results(&self, _query: &str) -> Vec<SearchResult> {
        vec![
            SearchResult {
                article_id: "Article50".to_string(),
                title: "Transparency obligations on providers of high-risk AI systems".to_string(),
                score: 0.92,
                rank: 1,
                source: "semantic".to_string(),
            },
            SearchResult {
                article_id: "Article51".to_string(),
                title: "Documentation and record-keeping requirements".to_string(),
                score: 0.87,
                rank: 2,
                source: "semantic".to_string(),
            },
        ]
    }

    /// BM25 keyword search on policy keywords
    fn keyword_search_results(&self, _query: &str) -> Vec<SearchResult> {
        vec![
            SearchResult {
                article_id: "Article50".to_string(),
                title: "Transparency obligations on providers of high-risk AI systems".to_string(),
                score: 0.88,
                rank: 1,
                source: "keyword".to_string(),
            },
            SearchResult {
                article_id: "GDPR-Article32".to_string(),
                title: "Security of processing - appropriate technical and organizational measures".to_string(),
                score: 0.75,
                rank: 2,
                source: "keyword".to_string(),
            },
        ]
    }

    pub fn semantic_search(&self, _embedding: &[f32]) -> Vec<SearchResult> {
        vec![]
    }

    pub fn keyword_search(&self, _keywords: &[&str]) -> Vec<SearchResult> {
        vec![]
    }

    /// Reciprocal Rank Fusion combines semantic and keyword results
    /// Formula: score = sum(1 / (k + rank)) where k=60 by default
    pub fn rrf_combine(
        &self,
        semantic: Vec<SearchResult>,
        keyword: Vec<SearchResult>,
    ) -> Vec<SearchResult> {
        use std::collections::HashMap;

        let k = 60;
        let mut rrf_scores: HashMap<String, (SearchResult, Vec<String>, f32)> = HashMap::new();

        // Add semantic results
        for result in semantic {
            let rrf_score = 1.0 / (k as f32 + result.rank as f32) * self.semantic_weight;
            rrf_scores
                .entry(result.article_id.clone())
                .or_insert_with(|| {
                    (
                        SearchResult {
                            article_id: result.article_id.clone(),
                            title: result.title.clone(),
                            score: 0.0,
                            rank: 0,
                            source: String::new(),
                        },
                        vec![],
                        0.0,
                    )
                })
                .2 += rrf_score;
            rrf_scores.get_mut(&result.article_id).unwrap().1.push("semantic".to_string());
        }

        // Add keyword results
        for result in keyword {
            let rrf_score = 1.0 / (k as f32 + result.rank as f32) * self.keyword_weight;
            rrf_scores
                .entry(result.article_id.clone())
                .or_insert_with(|| {
                    (
                        SearchResult {
                            article_id: result.article_id.clone(),
                            title: result.title.clone(),
                            score: 0.0,
                            rank: 0,
                            source: String::new(),
                        },
                        vec![],
                        0.0,
                    )
                })
                .2 += rrf_score;
            rrf_scores.get_mut(&result.article_id).unwrap().1.push("keyword".to_string());
        }

        // Sort by RRF score and assign ranks
        let mut results: Vec<_> = rrf_scores
            .into_iter()
            .map(|(_, (mut result, sources, score))| {
                result.score = score;
                result.source = sources.join("+");
                result
            })
            .collect();

        results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));

        for (i, result) in results.iter_mut().enumerate() {
            result.rank = (i + 1) as u32;
        }

        results
    }
}

impl Default for HybridSearcher {
    fn default() -> Self {
        Self::new(0.7, 0.3)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_search_latency_under_100ms() {
        let searcher = HybridSearcher::default();
        let (_results, elapsed) = searcher.search("transparency");
        assert!(elapsed < 100, "Search took {}ms, should be <100ms", elapsed);
    }

    #[test]
    fn test_semantic_search() {
        let searcher = HybridSearcher::default();
        let embedding = vec![0.1, 0.2, 0.3];
        let results = searcher.semantic_search(&embedding);
        assert_eq!(results.len(), 0);
    }

    #[test]
    fn test_keyword_search() {
        let searcher = HybridSearcher::default();
        let results = searcher.keyword_search(&["transparency", "compliance"]);
        assert_eq!(results.len(), 0);
    }

    #[test]
    fn test_rrf_ranking() {
        let searcher = HybridSearcher::default();
        let semantic = vec![SearchResult {
            article_id: "A1".to_string(),
            title: "Title 1".to_string(),
            score: 0.9,
            rank: 1,
        }];
        let keyword = vec![SearchResult {
            article_id: "A2".to_string(),
            title: "Title 2".to_string(),
            score: 0.8,
            rank: 1,
        }];

        let combined = searcher.rrf_combine(semantic, keyword);
        assert_eq!(combined.len(), 2);
    }
}
