/// Phase 49: Knowledge Atom Protocol — Typed cross-worktree swarm sync
/// Single source of truth: SwarmMcpServer Arc<RwLock<HashMap>> for KnowledgeAtom exchange.
use crate::swarm_mcp_server::{GlobalStateFilter, SwarmMcpServer, SwarmStatePayload};
use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use siss_graph_core::node::memory::{ConsolidationTier, compute_decay, is_gc_eligible};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::Arc;
use uuid::Uuid;

/// Knowledge kind for swarm discovery and filtering.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum KnowledgeKind {
    VulnerabilityFound,
    ArchitecturalPattern,
    BlastRadiusWarning,
    RefactoringOpportunity,
}

/// Typed knowledge atom: discoverable by kind, symbol, confidence, source.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnowledgeAtom {
    pub atom_id: Uuid,
    pub kind: KnowledgeKind,
    pub source_worktree: String,  // "alpha" or "beta"
    pub symbol_path: String,      // e.g. "siss_gatekeeper::tokens::IntentMandate"
    pub content: String,          // human-readable insight
    pub confidence: f64,          // 0.0–1.0
    pub provenance_hash: String,  // deterministic hex hash of content
    pub reinforcement_count: u32, // incremented by reinforce()
    pub discovered_at: DateTime<Utc>,
}

impl KnowledgeAtom {
    /// Create atom with provenance hash auto-computed from content.
    pub fn new(
        kind: KnowledgeKind,
        source_worktree: &str,
        symbol_path: &str,
        content: &str,
        confidence: f64,
    ) -> Self {
        KnowledgeAtom {
            atom_id: Uuid::new_v4(),
            kind,
            source_worktree: source_worktree.to_string(),
            symbol_path: symbol_path.to_string(),
            content: content.to_string(),
            confidence: confidence.clamp(0.0, 1.0),
            provenance_hash: compute_provenance_hash(content),
            reinforcement_count: 0,
            discovered_at: Utc::now(),
        }
    }

    /// Effective confidence accounting for elapsed time since discovery.
    /// Uses Episodic tier stability (48h) with Ebbinghaus decay formula.
    pub fn effective_confidence(&self, now: DateTime<Utc>) -> f64 {
        let elapsed = now.signed_duration_since(self.discovered_at);
        let elapsed_hours = elapsed.num_seconds() as f64 / 3600.0;
        let stability_hours = 48.0; // Episodic tier stability
        self.confidence * (-elapsed_hours / stability_hours).exp()
    }

    /// Asymptotic reinforcement boost: confidence += (1.0 - confidence) * 0.05
    pub fn reinforce(&mut self) {
        self.confidence = (self.confidence + (1.0 - self.confidence) * 0.05).clamp(0.0, 1.0);
        self.reinforcement_count += 1;
    }

    /// Whether this atom is eligible for garbage collection.
    pub fn is_gc_eligible(&self, now: DateTime<Utc>, threshold: f64) -> bool {
        let effective = self.effective_confidence(now);
        is_gc_eligible(effective, threshold)
    }
}

/// Knowledge bus error variants.
#[derive(Debug, PartialEq, Eq)]
pub enum KnowledgeBusError {
    SerializationFailed(String),
    StoreFailed(String),
    DeserializationFailed(String),
}

/// Deterministic content hash using DefaultHasher.
/// PROOF: pure function — same content always → same hex string.
pub fn compute_provenance_hash(content: &str) -> String {
    let mut h = DefaultHasher::new();
    content.hash(&mut h);
    format!("{:016x}", h.finish())
}

/// SwarmKnowledgeBus: single-brain sync protocol over SwarmMcpServer.
pub struct SwarmKnowledgeBus {
    server: Arc<SwarmMcpServer>,
}

impl SwarmKnowledgeBus {
    /// Create knowledge bus from shared SwarmMcpServer.
    pub fn new(server: Arc<SwarmMcpServer>) -> Self {
        SwarmKnowledgeBus { server }
    }

    /// Publish KnowledgeAtom to shared bus.
    /// Serializes atom → SwarmStatePayload.payload_json
    /// idempotency_key = format!("knowledge:{}:{}", worktree_id, atom.atom_id)
    /// phase = "KNOWLEDGE_ATOM"
    /// status = format!("{:?}", atom.kind)
    pub async fn publish(
        &self,
        atom: KnowledgeAtom,
        worktree_id: &str,
    ) -> Result<(), KnowledgeBusError> {
        let payload_json = serde_json::to_string(&atom)
            .map_err(|e| KnowledgeBusError::SerializationFailed(e.to_string()))?;

        let payload = SwarmStatePayload {
            idempotency_key: format!("knowledge:{}:{}", worktree_id, atom.atom_id),
            agent_id: worktree_id.to_string(),
            phase: "KNOWLEDGE_ATOM".to_string(),
            status: format!("{:?}", atom.kind),
            payload_json: Some(payload_json),
        };

        self.server
            .update_swarm_state(payload)
            .await
            .map_err(|e| KnowledgeBusError::StoreFailed(e))?;

        Ok(())
    }

    /// Query atoms by kind across all worktrees.
    /// Filters by phase="KNOWLEDGE_ATOM" and deserializes matching atoms.
    pub async fn query_by_kind(
        &self,
        kind: &KnowledgeKind,
    ) -> Result<Vec<KnowledgeAtom>, KnowledgeBusError> {
        let payloads = self
            .server
            .get_global_state(GlobalStateFilter {
                phase_filter: Some("KNOWLEDGE_ATOM".to_string()),
            })
            .await
            .map_err(|e| KnowledgeBusError::StoreFailed(e))?;

        let mut results = Vec::new();
        for payload in payloads {
            if let Some(json_str) = &payload.payload_json {
                let atom: KnowledgeAtom = serde_json::from_str(json_str)
                    .map_err(|e| KnowledgeBusError::DeserializationFailed(e.to_string()))?;
                if atom.kind == *kind {
                    results.push(atom);
                }
            }
        }

        Ok(results)
    }

    /// Query atoms by symbol path substring match.
    pub async fn query_by_symbol(
        &self,
        symbol: &str,
    ) -> Result<Vec<KnowledgeAtom>, KnowledgeBusError> {
        let payloads = self
            .server
            .get_global_state(GlobalStateFilter {
                phase_filter: Some("KNOWLEDGE_ATOM".to_string()),
            })
            .await
            .map_err(|e| KnowledgeBusError::StoreFailed(e))?;

        let mut results = Vec::new();
        for payload in payloads {
            if let Some(json_str) = &payload.payload_json {
                let atom: KnowledgeAtom = serde_json::from_str(json_str)
                    .map_err(|e| KnowledgeBusError::DeserializationFailed(e.to_string()))?;
                if atom.symbol_path.contains(symbol) {
                    results.push(atom);
                }
            }
        }

        Ok(results)
    }

    /// Query atoms by confidence threshold.
    /// Returns all atoms with effective_confidence(now) >= threshold.
    pub async fn query_by_confidence(
        &self,
        threshold: f64,
    ) -> Result<Vec<KnowledgeAtom>, KnowledgeBusError> {
        let payloads = self
            .server
            .get_global_state(GlobalStateFilter {
                phase_filter: Some("KNOWLEDGE_ATOM".to_string()),
            })
            .await
            .map_err(|e| KnowledgeBusError::StoreFailed(e))?;

        let now = Utc::now();
        let mut results = Vec::new();
        for payload in payloads {
            if let Some(json_str) = &payload.payload_json {
                let atom: KnowledgeAtom = serde_json::from_str(json_str)
                    .map_err(|e| KnowledgeBusError::DeserializationFailed(e.to_string()))?;
                if atom.effective_confidence(now) >= threshold {
                    results.push(atom);
                }
            }
        }

        Ok(results)
    }

    /// Reinforce an atom (boost confidence and increment reinforcement count).
    /// Re-serializes the updated atom back to the bus.
    pub async fn reinforce_atom(
        &self,
        atom_id: Uuid,
        worktree_id: &str,
    ) -> Result<(), KnowledgeBusError> {
        let payloads = self
            .server
            .get_global_state(GlobalStateFilter {
                phase_filter: Some("KNOWLEDGE_ATOM".to_string()),
            })
            .await
            .map_err(|e| KnowledgeBusError::StoreFailed(e))?;

        let mut updated_atom = None;
        for payload in payloads {
            if let Some(json_str) = &payload.payload_json {
                let mut atom: KnowledgeAtom = serde_json::from_str(json_str)
                    .map_err(|e| KnowledgeBusError::DeserializationFailed(e.to_string()))?;
                if atom.atom_id == atom_id {
                    atom.reinforce();
                    updated_atom = Some(atom);
                    break;
                }
            }
        }

        let atom = updated_atom.ok_or(KnowledgeBusError::StoreFailed(format!(
            "atom {} not found",
            atom_id
        )))?;

        let payload_json = serde_json::to_string(&atom)
            .map_err(|e| KnowledgeBusError::SerializationFailed(e.to_string()))?;

        let payload = SwarmStatePayload {
            idempotency_key: format!("knowledge:{}:{}", worktree_id, atom.atom_id),
            agent_id: worktree_id.to_string(),
            phase: "KNOWLEDGE_ATOM".to_string(),
            status: format!("{:?}", atom.kind),
            payload_json: Some(payload_json),
        };

        self.server
            .update_swarm_state(payload)
            .await
            .map_err(|e| KnowledgeBusError::StoreFailed(e))?;

        Ok(())
    }
}
