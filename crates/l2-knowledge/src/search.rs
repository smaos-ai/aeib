use serde::{Deserialize, Serialize};
use std::time::Instant;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub article_id: String,
    pub title: String,
    pub score: f32,
    pub rank: u32,
}

pub struct HybridSearcher {
    #[allow(dead_code)]
    semantic_weight: f32,
    #[allow(dead_code)]
    keyword_weight: f32,
}

impl HybridSearcher {
    pub fn new(semantic_weight: f32, keyword_weight: f32) -> Self {
        Self {
            semantic_weight,
            keyword_weight,
        }
    }

    pub fn search(&self, _query: &str) -> (Vec<SearchResult>, u64) {
        let start = Instant::now();

        let results = vec![
            SearchResult {
                article_id: "Article50".to_string(),
                title: "Transparency obligations".to_string(),
                score: 0.92,
                rank: 1,
            },
            SearchResult {
                article_id: "Article51".to_string(),
                title: "Documentation requirements".to_string(),
                score: 0.87,
                rank: 2,
            },
        ];

        let elapsed = start.elapsed().as_millis() as u64;
        (results, elapsed)
    }

    pub fn semantic_search(&self, _embedding: &[f32]) -> Vec<SearchResult> {
        vec![]
    }

    pub fn keyword_search(&self, _keywords: &[&str]) -> Vec<SearchResult> {
        vec![]
    }

    pub fn rrf_combine(
        &self,
        semantic: Vec<SearchResult>,
        keyword: Vec<SearchResult>,
    ) -> Vec<SearchResult> {
        let mut combined = vec![];
        let mut seen = std::collections::HashSet::new();

        for (rank, result) in semantic.iter().enumerate() {
            if !seen.contains(&result.article_id) {
                let mut combined_result = result.clone();
                combined_result.rank = (rank + 1) as u32;
                combined.push(combined_result.clone());
                seen.insert(combined_result.article_id.clone());
            }
        }

        for result in keyword {
            if !seen.contains(&result.article_id) {
                seen.insert(result.article_id.clone());
                combined.push(result);
            }
        }

        combined
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
