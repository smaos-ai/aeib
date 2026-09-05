use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::node::NodeId;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConsolidationTier {
    Working,
    Episodic,
    Semantic,
    Procedural,
}

/// Stability constants in hours for each tier.
/// These determine how quickly confidence decays.
impl ConsolidationTier {
    pub fn stability_hours(&self) -> f64 {
        match self {
            Self::Working => 1.0,    // Ephemeral — TTL-based, but defined for completeness
            Self::Episodic => 48.0,  // 2 days
            Self::Semantic => 168.0, // 7 days
            Self::Procedural => 720.0, // 30 days
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkingMemory {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub session_id: NodeId,
    pub content: String,
    pub created_at: DateTime<Utc>,
}

impl WorkingMemory {
    pub fn new(content: String, session_id: NodeId, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            session_id,
            content,
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpisodicMemory {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub content: String,
    pub confidence_score: f64,
    pub quality_score: f64,
    pub last_reinforced_at: DateTime<Utc>,
    pub consolidation_tier: ConsolidationTier,
    pub content_hash: Vec<u8>,
    pub created_at: DateTime<Utc>,
}

impl EpisodicMemory {
    pub fn new(content: String, confidence_score: f64, tenant_id: NodeId) -> Self {
        let now = Utc::now();
        Self {
            id: NodeId::new(),
            tenant_id,
            content,
            confidence_score,
            quality_score: 0.0,
            last_reinforced_at: now,
            consolidation_tier: ConsolidationTier::Episodic,
            content_hash: Vec::new(),
            created_at: now,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SemanticMemory {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub content: String,
    pub confidence_score: f64,
    pub quality_score: f64,
    pub last_reinforced_at: DateTime<Utc>,
    pub consolidation_tier: ConsolidationTier,
    pub content_hash: Vec<u8>,
    pub created_at: DateTime<Utc>,
}

impl SemanticMemory {
    pub fn new(content: String, confidence_score: f64, tenant_id: NodeId) -> Self {
        let now = Utc::now();
        Self {
            id: NodeId::new(),
            tenant_id,
            content,
            confidence_score,
            quality_score: 0.0,
            last_reinforced_at: now,
            consolidation_tier: ConsolidationTier::Semantic,
            content_hash: Vec::new(),
            created_at: now,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProceduralMemory {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub content: String,
    pub confidence_score: f64,
    pub quality_score: f64,
    pub last_reinforced_at: DateTime<Utc>,
    pub consolidation_tier: ConsolidationTier,
    pub content_hash: Vec<u8>,
    pub created_at: DateTime<Utc>,
}

impl ProceduralMemory {
    pub fn new(content: String, confidence_score: f64, tenant_id: NodeId) -> Self {
        let now = Utc::now();
        Self {
            id: NodeId::new(),
            tenant_id,
            content,
            confidence_score,
            quality_score: 0.0,
            last_reinforced_at: now,
            consolidation_tier: ConsolidationTier::Procedural,
            content_hash: Vec::new(),
            created_at: now,
        }
    }
}

/// Compute the current effective confidence after Ebbinghaus decay.
/// Formula: confidence = initial * e^(-t / stability)
/// where t = hours since last reinforcement, stability = tier-dependent hours.
pub fn compute_decay(
    initial_confidence: f64,
    last_reinforced_at: DateTime<Utc>,
    tier: ConsolidationTier,
) -> f64 {
    let elapsed_hours = (Utc::now() - last_reinforced_at).num_seconds() as f64 / 3600.0;
    let stability = tier.stability_hours();
    initial_confidence * (-elapsed_hours / stability).exp()
}

/// Returns true if a memory node is eligible for garbage collection.
/// A node at exactly the threshold is NOT eligible.
pub fn is_gc_eligible(confidence_score: f64, threshold: f64) -> bool {
    confidence_score < threshold
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    #[test]
    fn test_create_working_memory() {
        let tenant_id = NodeId::new();
        let session_id = NodeId::new();
        let mem = WorkingMemory::new("scratch notes".into(), session_id, tenant_id);
        assert_eq!(mem.content, "scratch notes");
        assert_eq!(mem.session_id, session_id);
        assert_eq!(mem.tenant_id, tenant_id);
    }

    #[test]
    fn test_create_episodic_memory() {
        let tenant_id = NodeId::new();
        let mem = EpisodicMemory::new("deployed v2 to prod".into(), 0.9, tenant_id);
        assert_eq!(mem.content, "deployed v2 to prod");
        assert!((mem.confidence_score - 0.9).abs() < f64::EPSILON);
        assert_eq!(mem.consolidation_tier, ConsolidationTier::Episodic);
    }

    #[test]
    fn test_create_semantic_memory() {
        let tenant_id = NodeId::new();
        let mem = SemanticMemory::new("Rust ownership prevents data races".into(), 0.95, tenant_id);
        assert_eq!(mem.consolidation_tier, ConsolidationTier::Semantic);
    }

    #[test]
    fn test_create_procedural_memory() {
        let tenant_id = NodeId::new();
        let mem = ProceduralMemory::new("run cargo test before commit".into(), 0.85, tenant_id);
        assert_eq!(mem.consolidation_tier, ConsolidationTier::Procedural);
    }

    #[test]
    fn test_ebbinghaus_decay_episodic() {
        let tenant_id = NodeId::new();
        let mut mem = EpisodicMemory::new("event".into(), 1.0, tenant_id);
        mem.last_reinforced_at = Utc::now() - Duration::hours(24);
        let decayed = compute_decay(
            mem.confidence_score,
            mem.last_reinforced_at,
            ConsolidationTier::Episodic,
        );
        // Episodic stability = 48 hours. After 24h: e^(-24/48) = e^(-0.5) ~ 0.606
        assert!(decayed > 0.59 && decayed < 0.62, "decayed={}", decayed);
    }

    #[test]
    fn test_ebbinghaus_decay_semantic() {
        let tenant_id = NodeId::new();
        let mut mem = SemanticMemory::new("fact".into(), 1.0, tenant_id);
        mem.last_reinforced_at = Utc::now() - Duration::hours(24);
        let decayed = compute_decay(
            mem.confidence_score,
            mem.last_reinforced_at,
            ConsolidationTier::Semantic,
        );
        // Semantic stability = 168 hours (7 days). After 24h: e^(-24/168) ~ 0.867
        assert!(decayed > 0.85 && decayed < 0.88, "decayed={}", decayed);
    }

    #[test]
    fn test_ebbinghaus_decay_procedural() {
        let tenant_id = NodeId::new();
        let mut mem = ProceduralMemory::new("workflow".into(), 1.0, tenant_id);
        mem.last_reinforced_at = Utc::now() - Duration::hours(24);
        let decayed = compute_decay(
            mem.confidence_score,
            mem.last_reinforced_at,
            ConsolidationTier::Procedural,
        );
        // Procedural stability = 720 hours (30 days). After 24h: e^(-24/720) ~ 0.967
        assert!(decayed > 0.95 && decayed < 0.98, "decayed={}", decayed);
    }

    #[test]
    fn test_memory_below_gc_threshold() {
        assert!(is_gc_eligible(0.05, 0.1));
        assert!(!is_gc_eligible(0.15, 0.1));
        assert!(!is_gc_eligible(0.1, 0.1)); // exactly at threshold = not eligible
    }
}
