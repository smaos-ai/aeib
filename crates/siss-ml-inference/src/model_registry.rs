use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelMetadata {
    pub name: String,
    pub version: String,
    pub input_shape: Vec<usize>,
    pub output_shape: Vec<usize>,
    pub quantized: bool,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub tags: HashMap<String, String>,
}

impl ModelMetadata {
    pub fn new(
        name: String,
        version: String,
        input_shape: Vec<usize>,
        output_shape: Vec<usize>,
    ) -> Self {
        ModelMetadata {
            name,
            version,
            input_shape,
            output_shape,
            quantized: false,
            created_at: chrono::Utc::now(),
            tags: HashMap::new(),
        }
    }

    pub fn with_tags(mut self, tags: HashMap<String, String>) -> Self {
        self.tags = tags;
        self
    }

    pub fn with_quantized(mut self, quantized: bool) -> Self {
        self.quantized = quantized;
        self
    }
}

#[derive(Debug, Clone)]
pub struct ModelRegistry {
    models: std::collections::HashMap<String, ModelMetadata>,
}

impl ModelRegistry {
    pub fn new() -> Self {
        ModelRegistry {
            models: HashMap::new(),
        }
    }

    pub fn register(&mut self, id: String, metadata: ModelMetadata) -> bool {
        if self.models.contains_key(&id) {
            return false;
        }
        self.models.insert(id, metadata);
        true
    }

    pub fn get(&self, id: &str) -> Option<&ModelMetadata> {
        self.models.get(id)
    }

    pub fn list(&self) -> Vec<String> {
        self.models.keys().cloned().collect()
    }

    pub fn unregister(&mut self, id: &str) -> bool {
        self.models.remove(id).is_some()
    }

    pub fn count(&self) -> usize {
        self.models.len()
    }
}

impl Default for ModelRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_model_metadata_creation() {
        let metadata = ModelMetadata::new(
            "test_model".to_string(),
            "1.0.0".to_string(),
            vec![1, 224, 224, 3],
            vec![1, 1000],
        );

        assert_eq!(metadata.name, "test_model");
        assert_eq!(metadata.version, "1.0.0");
        assert_eq!(metadata.input_shape, vec![1, 224, 224, 3]);
        assert_eq!(metadata.output_shape, vec![1, 1000]);
        assert!(!metadata.quantized);
    }

    #[test]
    fn test_model_metadata_with_tags() {
        let mut tags = HashMap::new();
        tags.insert("framework".to_string(), "tensorflow".to_string());
        tags.insert("hardware".to_string(), "cpu".to_string());

        let metadata = ModelMetadata::new(
            "test".to_string(),
            "1.0.0".to_string(),
            vec![1, 10],
            vec![1, 5],
        )
        .with_tags(tags.clone());

        assert_eq!(metadata.tags, tags);
    }

    #[test]
    fn test_model_metadata_with_quantized() {
        let metadata = ModelMetadata::new(
            "test".to_string(),
            "1.0.0".to_string(),
            vec![1, 10],
            vec![1, 5],
        )
        .with_quantized(true);

        assert!(metadata.quantized);
    }

    #[test]
    fn test_registry_register() {
        let mut registry = ModelRegistry::new();
        let metadata = ModelMetadata::new(
            "model1".to_string(),
            "1.0".to_string(),
            vec![1, 10],
            vec![1, 5],
        );

        assert!(registry.register("model1".to_string(), metadata));
        assert_eq!(registry.count(), 1);
    }

    #[test]
    fn test_registry_duplicate_registration() {
        let mut registry = ModelRegistry::new();
        let metadata = ModelMetadata::new(
            "model1".to_string(),
            "1.0".to_string(),
            vec![1, 10],
            vec![1, 5],
        );

        registry.register("model1".to_string(), metadata.clone());
        assert!(!registry.register("model1".to_string(), metadata));
        assert_eq!(registry.count(), 1);
    }

    #[test]
    fn test_registry_get() {
        let mut registry = ModelRegistry::new();
        let metadata = ModelMetadata::new(
            "model1".to_string(),
            "1.0".to_string(),
            vec![1, 10],
            vec![1, 5],
        );

        registry.register("model1".to_string(), metadata.clone());
        let retrieved = registry.get("model1").unwrap();
        assert_eq!(retrieved.name, "model1");
    }

    #[test]
    fn test_registry_list() {
        let mut registry = ModelRegistry::new();

        for i in 0..3 {
            let metadata = ModelMetadata::new(
                format!("model{}", i),
                "1.0".to_string(),
                vec![1, 10],
                vec![1, 5],
            );
            registry.register(format!("model{}", i), metadata);
        }

        let list = registry.list();
        assert_eq!(list.len(), 3);
    }

    #[test]
    fn test_registry_unregister() {
        let mut registry = ModelRegistry::new();
        let metadata = ModelMetadata::new(
            "model1".to_string(),
            "1.0".to_string(),
            vec![1, 10],
            vec![1, 5],
        );

        registry.register("model1".to_string(), metadata);
        assert!(registry.unregister("model1"));
        assert_eq!(registry.count(), 0);
        assert!(registry.get("model1").is_none());
    }

    #[test]
    fn test_registry_default() {
        let registry = ModelRegistry::default();
        assert_eq!(registry.count(), 0);
    }
}
