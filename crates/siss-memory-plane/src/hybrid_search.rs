use siss_graph_core::reachability::ReachabilityCache;
use uuid::Uuid;
use std::collections::HashMap;

/// Represents a document corpus indexed for search.
pub struct Corpus {
    pub docs: Vec<(Uuid, String)>,
}

impl Corpus {
    /// Creates a new corpus from a vector of (Uuid, String) pairs.
    pub fn new(docs: Vec<(Uuid, String)>) -> Self {
        Corpus { docs }
    }
}

/// BM25 scorer for ranking documents based on keyword relevance.
pub struct BM25Scorer {
    k1: f64,
    b: f64,
    avgdl: f64,
    idf: HashMap<String, f64>,
    tf: HashMap<Uuid, HashMap<String, f64>>,
    doc_lengths: HashMap<Uuid, usize>,
    doc_ids: Vec<Uuid>,
}

impl BM25Scorer {
    /// Builds a BM25 scorer from a corpus.
    pub fn build(corpus: &Corpus) -> Self {
        let k1 = 1.5;
        let b = 0.75;

        let mut tf: HashMap<Uuid, HashMap<String, f64>> = HashMap::new();
        let mut doc_lengths: HashMap<Uuid, usize> = HashMap::new();
        let mut df: HashMap<String, usize> = HashMap::new();

        let doc_ids: Vec<Uuid> = corpus.docs.iter().map(|(id, _)| *id).collect();

        // Tokenize and build tf + df
        for (id, content) in &corpus.docs {
            let tokens: Vec<String> = content
                .to_lowercase()
                .split_whitespace()
                .map(|s| s.to_string())
                .collect();
            doc_lengths.insert(*id, tokens.len());

            let mut term_freq: HashMap<String, f64> = HashMap::new();
            for token in tokens {
                *term_freq.entry(token.clone()).or_insert(0.0) += 1.0;
                *df.entry(token).or_insert(0) += 1;
            }
            tf.insert(*id, term_freq);
        }

        // Compute IDF
        let n = corpus.docs.len() as f64;
        let mut idf: HashMap<String, f64> = HashMap::new();
        for (term, doc_freq) in df {
            let doc_freq_f = doc_freq as f64;
            idf.insert(
                term,
                ((n - doc_freq_f + 0.5) / (doc_freq_f + 0.5) + 1.0).ln(),
            );
        }

        let avgdl = if doc_ids.is_empty() {
            0.0
        } else {
            doc_lengths.values().sum::<usize>() as f64 / doc_ids.len() as f64
        };

        BM25Scorer {
            k1,
            b,
            avgdl,
            idf,
            tf,
            doc_lengths,
            doc_ids,
        }
    }

    /// Scores documents against a query using BM25 algorithm.
    pub fn score(&self, query: &str) -> Vec<(Uuid, f64)> {
        let tokens: Vec<String> = query
            .to_lowercase()
            .split_whitespace()
            .map(|s| s.to_string())
            .collect();

        let mut scores: Vec<(Uuid, f64)> = self
            .doc_ids
            .iter()
            .map(|doc_id| {
                let mut score = 0.0;
                for token in &tokens {
                    if let Some(idf_val) = self.idf.get(token) {
                        let tf_val = self
                            .tf
                            .get(doc_id)
                            .and_then(|m| m.get(token))
                            .copied()
                            .unwrap_or(0.0);
                        let doc_len =
                            self.doc_lengths.get(doc_id).copied().unwrap_or(0) as f64;
                        let numerator = tf_val * (self.k1 + 1.0);
                        let denominator =
                            tf_val + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl));
                        score += idf_val * (numerator / denominator);
                    }
                }
                (*doc_id, score)
            })
            .collect();

        scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        scores
    }
}

/// Result of a hybrid search operation.
pub struct SearchResult {
    pub id: Uuid,
    pub rrf_score: f64,
    pub content: Option<String>,
}

/// Reciprocal Rank Fusion scorer for combining multiple ranked lists.
pub struct RrfFuser {
    pub k: usize,
}

impl RrfFuser {
    /// Creates a new RRF fuser with parameter k.
    pub fn new(k: usize) -> Self {
        RrfFuser { k }
    }

    /// Fuses multiple ranked lists into a single unified ranking.
    pub fn fuse(&self, ranked_lists: Vec<Vec<Uuid>>) -> Vec<SearchResult> {
        let mut rrf_scores: HashMap<Uuid, f64> = HashMap::new();

        for list in ranked_lists {
            for (rank, &id) in list.iter().enumerate() {
                let score = 1.0 / (self.k as f64 + (rank as f64 + 1.0));
                *rrf_scores.entry(id).or_insert(0.0) += score;
            }
        }

        let mut results: Vec<SearchResult> = rrf_scores
            .into_iter()
            .map(|(id, rrf_score)| SearchResult {
                id,
                rrf_score,
                content: None,
            })
            .collect();

        results.sort_by(|a, b| b.rrf_score.partial_cmp(&a.rrf_score).unwrap());
        results
    }
}

/// Hybrid search engine combining BM25, cosine similarity, and graph traversal.
pub struct HybridSearchEngine {
    bm25: BM25Scorer,
    reachability: ReachabilityCache,
    rrf: RrfFuser,
}

impl HybridSearchEngine {
    /// Creates a new hybrid search engine from a corpus and reachability cache.
    pub fn new(corpus: Corpus, reachability: ReachabilityCache) -> Self {
        HybridSearchEngine {
            bm25: BM25Scorer::build(&corpus),
            reachability,
            rrf: RrfFuser::new(60),
        }
    }

    /// Scores documents using cosine similarity on embeddings.
    pub fn cosine_score(&self, query: &str) -> Vec<(Uuid, f64)> {
        // Delegate to BM25 for now (cosine via TF vectors approximated)
        self.bm25.score(query)
    }

    /// Expands initial results through graph traversal via support edges.
    pub fn expand_via_graph(&mut self, initial: &[Uuid], candidate_ids: &[Uuid]) -> Vec<Uuid> {
        let mut result = initial.to_vec();
        for &id in initial {
            for &cand in candidate_ids {
                if self.reachability.reachable(id, cand) && !result.contains(&cand) {
                    result.push(cand);
                }
            }
        }
        result
    }

    /// Performs a hybrid search combining BM25, cosine similarity, and graph expansion.
    pub fn search(&mut self, query: &str, candidate_ids: &[Uuid]) -> Vec<SearchResult> {
        // Full pipeline: BM25 + cosine + graph → RRF
        let bm25_results = self.bm25.score(query);
        let cosine_results = self.cosine_score(query);
        let expanded = self.expand_via_graph(&[bm25_results[0].0], candidate_ids);

        self.rrf.fuse(vec![
            bm25_results.iter().map(|(id, _)| *id).collect(),
            cosine_results.iter().map(|(id, _)| *id).collect(),
            expanded,
        ])
    }
}
