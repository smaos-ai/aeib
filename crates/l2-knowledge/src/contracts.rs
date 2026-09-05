//! L2 Input/Output Contracts: Type-safe knowledge layer interfaces
//! Replaces implicit JSON with explicit trait boundaries between L1↔L2 and L2→L3

use crate::search::SearchResult;
use std::fmt;

/// Input contract for L2 (accepts L1Output via trait object)
pub trait L2Input: Send + Sync + fmt::Debug {
    fn request_id(&self) -> &str;
    fn article(&self) -> &str;
    fn compliance_level(&self) -> u8;
}

/// Output contract for L2 (what L2 sends to L3)
pub trait L2Output: Send + Sync + fmt::Debug {
    fn request_id(&self) -> &str;
    fn query(&self) -> &str;
    fn results_count(&self) -> usize;
    fn top_result(&self) -> Option<&SearchResult>;
    fn metadata(&self) -> L2Metadata;
}

/// Non-trait metadata struct
#[derive(Debug, Clone)]
pub struct L2Metadata {
    pub search_time_ms: u64,
    pub total_score: f32,
}

/// Concrete implementation of L2Input adapter
#[derive(Debug, Clone)]
pub struct KnowledgeRequest {
    request_id: String,
    article: String,
    compliance_level: u8,
    query: String,
}

impl KnowledgeRequest {
    pub fn new(request_id: String, article: String, compliance_level: u8, query: String) -> Self {
        Self {
            request_id,
            article,
            compliance_level,
            query,
        }
    }

    pub fn query(&self) -> &str {
        &self.query
    }
}

impl L2Input for KnowledgeRequest {
    fn request_id(&self) -> &str {
        &self.request_id
    }

    fn article(&self) -> &str {
        &self.article
    }

    fn compliance_level(&self) -> u8 {
        self.compliance_level
    }
}

/// Concrete implementation of L2Output
#[derive(Debug, Clone)]
pub struct KnowledgeResult {
    request_id: String,
    query: String,
    results: Vec<SearchResult>,
    metadata: L2Metadata,
}

impl KnowledgeResult {
    pub fn new(
        request_id: String,
        query: String,
        results: Vec<SearchResult>,
        search_time_ms: u64,
    ) -> Self {
        let total_score: f32 = results.iter().map(|r| r.score).sum();
        Self {
            request_id,
            query,
            results,
            metadata: L2Metadata {
                search_time_ms,
                total_score,
            },
        }
    }

    pub fn results(&self) -> &[SearchResult] {
        &self.results
    }
}

impl L2Output for KnowledgeResult {
    fn request_id(&self) -> &str {
        &self.request_id
    }

    fn query(&self) -> &str {
        &self.query
    }

    fn results_count(&self) -> usize {
        self.results.len()
    }

    fn top_result(&self) -> Option<&SearchResult> {
        self.results.first()
    }

    fn metadata(&self) -> L2Metadata {
        self.metadata.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_knowledge_request_creation() {
        let req = KnowledgeRequest::new(
            "req123".to_string(),
            "Article 50".to_string(),
            100,
            "transparency".to_string(),
        );
        assert_eq!(req.request_id(), "req123");
        assert_eq!(req.article(), "Article 50");
        assert_eq!(req.compliance_level(), 100);
        assert_eq!(req.query(), "transparency");
    }

    #[test]
    fn test_knowledge_request_l2_input_trait() {
        let req: Box<dyn L2Input> = Box::new(KnowledgeRequest::new(
            "id".to_string(),
            "Article".to_string(),
            50,
            "query".to_string(),
        ));
        assert_eq!(req.request_id(), "id");
        assert_eq!(req.compliance_level(), 50);
    }

    #[test]
    fn test_knowledge_result_empty() {
        let result = KnowledgeResult::new(
            "req123".to_string(),
            "transparency".to_string(),
            vec![],
            50,
        );
        assert_eq!(result.results_count(), 0);
        assert!(result.top_result().is_none());
    }

    #[test]
    fn test_knowledge_result_with_results() {
        let search_results = vec![
            SearchResult {
                article_id: "A50".to_string(),
                title: "Title 1".to_string(),
                score: 0.9,
                rank: 1,
                source: "semantic".to_string(),
            },
            SearchResult {
                article_id: "A51".to_string(),
                title: "Title 2".to_string(),
                score: 0.7,
                rank: 2,
                source: "keyword".to_string(),
            },
        ];
        let result = KnowledgeResult::new(
            "req456".to_string(),
            "compliance".to_string(),
            search_results,
            45,
        );

        assert_eq!(result.results_count(), 2);
        assert_eq!(result.top_result().unwrap().article_id, "A50");
        assert_eq!(result.metadata().search_time_ms, 45);
        assert!((result.metadata().total_score - 1.6).abs() < 0.01);
    }

    #[test]
    fn test_knowledge_result_trait_object() {
        let results = vec![SearchResult {
            article_id: "A".to_string(),
            title: "T".to_string(),
            score: 0.8,
            rank: 1,
            source: "s".to_string(),
        }];
        let kr = KnowledgeResult::new("r".to_string(), "q".to_string(), results, 10);
        let output: Box<dyn L2Output> = Box::new(kr);

        assert_eq!(output.request_id(), "r");
        assert_eq!(output.results_count(), 1);
        assert!(output.top_result().is_some());
    }

    #[test]
    fn test_knowledge_request_all_compliance_levels() {
        for level in &[0u8, 25, 50, 75, 100] {
            let req = KnowledgeRequest::new(
                "id".to_string(),
                "Article".to_string(),
                *level,
                "q".to_string(),
            );
            assert_eq!(req.compliance_level(), *level);
        }
    }

    #[test]
    fn test_l2_metadata_score_aggregation() {
        let results = vec![
            SearchResult {
                article_id: "A".to_string(),
                title: "T1".to_string(),
                score: 0.5,
                rank: 1,
                source: "s".to_string(),
            },
            SearchResult {
                article_id: "B".to_string(),
                title: "T2".to_string(),
                score: 0.3,
                rank: 2,
                source: "s".to_string(),
            },
            SearchResult {
                article_id: "C".to_string(),
                title: "T3".to_string(),
                score: 0.2,
                rank: 3,
                source: "s".to_string(),
            },
        ];
        let kr = KnowledgeResult::new("r".to_string(), "q".to_string(), results, 100);
        assert!((kr.metadata().total_score - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_knowledge_result_clone() {
        let results = vec![SearchResult {
            article_id: "A".to_string(),
            title: "T".to_string(),
            score: 0.8,
            rank: 1,
            source: "s".to_string(),
        }];
        let kr1 = KnowledgeResult::new("r".to_string(), "q".to_string(), results, 50);
        let kr2 = kr1.clone();

        assert_eq!(kr1.request_id(), kr2.request_id());
        assert_eq!(kr1.results_count(), kr2.results_count());
    }

    #[test]
    fn test_knowledge_request_clone() {
        let req1 = KnowledgeRequest::new(
            "id".to_string(),
            "Article".to_string(),
            75,
            "query".to_string(),
        );
        let req2 = req1.clone();
        assert_eq!(req1.request_id(), req2.request_id());
        assert_eq!(req1.compliance_level(), req2.compliance_level());
    }

    #[test]
    fn test_knowledge_result_empty_metadata() {
        let result = KnowledgeResult::new("r".to_string(), "q".to_string(), vec![], 0);
        let meta = result.metadata();
        assert_eq!(meta.search_time_ms, 0);
        assert_eq!(meta.total_score, 0.0);
    }

    #[test]
    fn test_l2_input_contract_consistency() {
        let req = KnowledgeRequest::new(
            "req789".to_string(),
            "Article 13".to_string(),
            85,
            "query_text".to_string(),
        );
        let input: &dyn L2Input = &req;

        assert_eq!(input.request_id(), "req789");
        assert_eq!(input.article(), "Article 13");
        assert_eq!(input.compliance_level(), 85);
    }
}
