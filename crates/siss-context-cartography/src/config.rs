#[derive(Debug, Clone)]
pub struct RetrievalConfig {
    pub max_procedural: usize,
    pub max_semantic: usize,
    pub max_episodic: usize,
    pub tokens_per_char: f64,
    pub confidence_threshold: f64,
}

impl Default for RetrievalConfig {
    fn default() -> Self {
        Self {
            max_procedural: 20,
            max_semantic: 30,
            max_episodic: 10,
            tokens_per_char: 0.25,
            confidence_threshold: 0.1,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = RetrievalConfig::default();
        assert_eq!(config.max_procedural, 20);
        assert_eq!(config.max_semantic, 30);
        assert_eq!(config.max_episodic, 10);
        assert!((config.tokens_per_char - 0.25).abs() < f64::EPSILON);
        assert!((config.confidence_threshold - 0.1).abs() < f64::EPSILON);
    }
}
