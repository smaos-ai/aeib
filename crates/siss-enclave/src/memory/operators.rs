use crate::memory::zonal::{ConsolidatedEntry, GrayFog, LayeredFog, RawObservation};

pub struct CartographicOperators {
    pub max_tokens_per_entry: i64,
    pub jaccard_threshold: f64,
}

impl CartographicOperators {
    pub fn new(max_tokens_per_entry: i64, jaccard_threshold: f64) -> Self {
        Self {
            max_tokens_per_entry,
            jaccard_threshold,
        }
    }

    pub fn simplify(&self, entries: Vec<RawObservation>) -> Vec<RawObservation> {
        entries
            .into_iter()
            .map(|mut obs| {
                if obs.token_count() > self.max_tokens_per_entry {
                    let max_chars = (self.max_tokens_per_entry as f64 / 0.25) as usize;
                    obs.content.truncate(max_chars);
                }
                obs
            })
            .collect()
    }

    pub fn aggregate(&self, entries: Vec<RawObservation>) -> Vec<RawObservation> {
        if entries.is_empty() {
            return vec![];
        }

        let mut kept = vec![true; entries.len()];

        for i in 0..entries.len() {
            if !kept[i] {
                continue;
            }
            for j in (i + 1)..entries.len() {
                if !kept[j] {
                    continue;
                }

                let sim = jaccard(&entries[i].content, &entries[j].content);
                if sim >= self.jaccard_threshold {
                    if entries[j].confidence > entries[i].confidence {
                        kept[i] = false;
                        break;
                    } else {
                        kept[j] = false;
                    }
                }
            }
        }

        entries
            .into_iter()
            .zip(kept.into_iter())
            .filter_map(|(obs, k)| if k { Some(obs) } else { None })
            .collect()
    }

    pub fn layer(&self, entries: Vec<RawObservation>) -> LayeredFog {
        let mut layers: LayeredFog = std::collections::HashMap::new();

        for obs in entries {
            let token_count = obs.token_count();
            let tier = obs.tier;
            let consolidated = ConsolidatedEntry {
                id: obs.id,
                content: obs.content,
                confidence: obs.confidence,
                tier,
                token_count,
            };
            layers
                .entry(tier)
                .or_insert_with(Vec::new)
                .push(consolidated);
        }

        layers
    }

    pub fn run_cycle(&self, entries: Vec<RawObservation>) -> anyhow::Result<GrayFog> {
        let simplified = self.simplify(entries);
        let aggregated = self.aggregate(simplified);
        let layers = self.layer(aggregated);

        Ok(GrayFog { layers })
    }
}

fn jaccard(a: &str, b: &str) -> f64 {
    let a_words: std::collections::HashSet<&str> = a.split_whitespace().collect();
    let b_words: std::collections::HashSet<&str> = b.split_whitespace().collect();

    if a_words.is_empty() && b_words.is_empty() {
        return 0.0;
    }

    let intersection = a_words.intersection(&b_words).count() as f64;
    let union = a_words.union(&b_words).count() as f64;

    if union == 0.0 {
        0.0
    } else {
        intersection / union
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_jaccard_identical_strings() {
        assert_eq!(jaccard("hello world", "hello world"), 1.0);
    }

    #[test]
    fn test_jaccard_disjoint_strings() {
        let sim = jaccard("rust ownership", "python dynamic");
        assert!(sim < 0.5);
    }

    #[test]
    fn test_jaccard_empty_strings() {
        assert_eq!(jaccard("", ""), 0.0);
    }
}
