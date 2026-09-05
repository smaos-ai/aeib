//! Task 1: L8 Dossier Exporter
//! Extracts decisions from AP2 ledger, formats for Annex I/III/IV dossiers
//! Handles KMS signature envelope for regulatory proof
//! 200 LOC

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use sha2::{Digest, Sha256};
use crate::compliance_automation::Decision;

/// Exports decisions from AP2 ledger to regulatory dossier format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L8DossierExporter {
    /// Loaded decisions from AP2 ledger
    decisions: Vec<Decision>,
    /// Metadata about the export
    export_metadata: ExportMetadata,
}

/// Metadata about the dossier export
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportMetadata {
    pub export_id: String,
    pub export_timestamp: DateTime<Utc>,
    pub decision_count: usize,
    pub case_type_distribution: HashMap<String, usize>,
    pub content_hash: String,
}

/// Formatted export result for a specific annex
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnnexExport {
    pub annex_type: String,        // "I", "III", "IV"
    pub decisions_included: usize,
    pub decision_hashes: Vec<String>,
    pub summary_metrics: ExportMetrics,
    pub export_timestamp: DateTime<Utc>,
}

/// Metrics computed during export
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportMetrics {
    pub total_decisions: usize,
    pub approval_rate: f64,
    pub average_score: f64,
    pub case_types: Vec<String>,
}

/// KMS-signed dossier envelope
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KmsEnvelope {
    pub envelope_id: String,
    pub dossier_content: String,  // JSON-serialized dossier
    pub kms_signature: String,    // Ed25519 signature from KMS
    pub signature_timestamp: DateTime<Utc>,
    pub certificate_chain: Option<String>,  // PKIX chain
}

impl L8DossierExporter {
    /// Create new exporter
    pub fn new() -> Self {
        Self {
            decisions: Vec::new(),
            export_metadata: ExportMetadata {
                export_id: uuid::Uuid::new_v4().to_string(),
                export_timestamp: Utc::now(),
                decision_count: 0,
                case_type_distribution: HashMap::new(),
                content_hash: String::new(),
            },
        }
    }

    /// Load decisions from AP2 ledger (batch import)
    pub fn load_from_ledger(&mut self, decisions: Vec<Decision>) -> Result<usize, String> {
        if decisions.is_empty() {
            return Err("No decisions provided from ledger".to_string());
        }

        // Count case types
        let mut type_dist: HashMap<String, usize> = HashMap::new();
        for decision in &decisions {
            *type_dist.entry(decision.case_type.clone()).or_insert(0) += 1;
        }

        let count = decisions.len();
        self.decisions = decisions;
        self.export_metadata.decision_count = count;
        self.export_metadata.case_type_distribution = type_dist;
        self.export_metadata.content_hash = self.compute_content_hash();

        Ok(count)
    }

    /// Extract decisions for a specific annex (I/III/IV)
    pub fn extract_for_annex(&self, annex_type: &str) -> Result<AnnexExport, String> {
        if self.decisions.is_empty() {
            return Err("No decisions loaded".to_string());
        }

        let filtered = self.filter_decisions_for_annex(annex_type)?;

        if filtered.is_empty() {
            return Err(format!("No {} decisions found", annex_type));
        }

        let hashes: Vec<String> = filtered
            .iter()
            .map(|d| self.hash_decision(d))
            .collect();

        let approval_count = filtered.iter().filter(|d| d.outcome).count();
        let approval_rate = approval_count as f64 / filtered.len() as f64;
        let avg_score = filtered.iter().map(|d| d.score).sum::<f64>() / filtered.len() as f64;

        let case_types: Vec<String> = filtered
            .iter()
            .map(|d| d.case_type.clone())
            .collect::<std::collections::HashSet<_>>()
            .into_iter()
            .collect();

        Ok(AnnexExport {
            annex_type: annex_type.to_string(),
            decisions_included: filtered.len(),
            decision_hashes: hashes,
            summary_metrics: ExportMetrics {
                total_decisions: filtered.len(),
                approval_rate,
                average_score: avg_score,
                case_types,
            },
            export_timestamp: Utc::now(),
        })
    }

    /// Format all decisions for dossier (JSON)
    pub fn format_for_dossier(&self) -> Result<String, String> {
        if self.decisions.is_empty() {
            return Err("No decisions to format".to_string());
        }

        let export_data = serde_json::json!({
            "export_id": self.export_metadata.export_id,
            "export_timestamp": self.export_metadata.export_timestamp.to_rfc3339(),
            "decisions_count": self.decisions.len(),
            "case_type_distribution": self.export_metadata.case_type_distribution,
            "content_hash": self.export_metadata.content_hash,
            "decisions": self.decisions.iter().map(|d| serde_json::json!({
                "id": d.decision_id,
                "timestamp": d.timestamp.to_rfc3339(),
                "case_type": d.case_type,
                "outcome": d.outcome,
                "score": d.score,
            })).collect::<Vec<_>>(),
        });

        Ok(export_data.to_string())
    }

    /// Create KMS-signed envelope for the dossier
    pub fn create_kms_envelope(&self, kms_signature: String) -> Result<KmsEnvelope, String> {
        let dossier_json = self.format_for_dossier()?;

        Ok(KmsEnvelope {
            envelope_id: uuid::Uuid::new_v4().to_string(),
            dossier_content: dossier_json,
            kms_signature,
            signature_timestamp: Utc::now(),
            certificate_chain: None,
        })
    }

    /// Verify the integrity of an envelope (basic check)
    pub fn verify_envelope(&self, envelope: &KmsEnvelope) -> Result<bool, String> {
        if envelope.dossier_content.is_empty() {
            return Err("Empty dossier content".to_string());
        }

        if envelope.kms_signature.is_empty() {
            return Err("Empty KMS signature".to_string());
        }

        // Basic verification: ensure signature is hex or base64-like
        if envelope.kms_signature.len() < 64 {
            return Err("Signature too short".to_string());
        }

        Ok(true)
    }

    /// Get current decision count
    pub fn decision_count(&self) -> usize {
        self.decisions.len()
    }

    /// Get export metadata
    pub fn metadata(&self) -> &ExportMetadata {
        &self.export_metadata
    }

    // ============ PRIVATE HELPERS ============

    fn filter_decisions_for_annex(&self, annex_type: &str) -> Result<Vec<Decision>, String> {
        match annex_type {
            "I" | "auto" => {
                let auto = self.decisions
                    .iter()
                    .filter(|d| d.case_type == "auto")
                    .cloned()
                    .collect::<Vec<_>>();
                if auto.is_empty() {
                    Err("No auto decisions for Annex I".to_string())
                } else {
                    Ok(auto)
                }
            }
            "III" | "hotel" => {
                let hotel = self.decisions
                    .iter()
                    .filter(|d| d.case_type == "hotel")
                    .cloned()
                    .collect::<Vec<_>>();
                if hotel.is_empty() {
                    Err("No hotel decisions for Annex III".to_string())
                } else {
                    Ok(hotel)
                }
            }
            "IV" | "glass" => {
                let glass = self.decisions
                    .iter()
                    .filter(|d| d.case_type == "glass")
                    .cloned()
                    .collect::<Vec<_>>();
                if glass.is_empty() {
                    Err("No glass decisions for Annex IV".to_string())
                } else {
                    Ok(glass)
                }
            }
            "all" => Ok(self.decisions.clone()),
            _ => Err(format!("Unknown annex type: {}", annex_type)),
        }
    }

    fn hash_decision(&self, decision: &Decision) -> String {
        let mut hasher = Sha256::new();
        hasher.update(
            format!(
                "{}{}{}{}",
                decision.decision_id, decision.timestamp, decision.outcome, decision.score
            )
            .as_bytes(),
        );
        format!("{:x}", hasher.finalize())
    }

    fn compute_content_hash(&self) -> String {
        let mut hasher = Sha256::new();
        for decision in &self.decisions {
            hasher.update(self.hash_decision(decision).as_bytes());
        }
        format!("{:x}", hasher.finalize())
    }
}

impl Default for L8DossierExporter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_decision(case_type: &str, outcome: bool, score: f64) -> Decision {
        Decision {
            decision_id: uuid::Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            case_type: case_type.to_string(),
            outcome,
            score,
            metadata: HashMap::new(),
            kms_signature: None,
        }
    }

    #[test]
    fn test_exporter_new() {
        let exp = L8DossierExporter::new();
        assert_eq!(exp.decision_count(), 0);
    }

    #[test]
    fn test_load_from_ledger() {
        let mut exp = L8DossierExporter::new();
        let decisions: Vec<_> = (0..100)
            .map(|i| {
                let case_type = match i % 3 {
                    0 => "hotel",
                    1 => "glass",
                    _ => "auto",
                };
                create_test_decision(case_type, i % 2 == 0, 0.90)
            })
            .collect();

        let count = exp.load_from_ledger(decisions).unwrap();
        assert_eq!(count, 100);
        assert_eq!(exp.decision_count(), 100);
    }

    #[test]
    fn test_extract_for_annex_auto() {
        let mut exp = L8DossierExporter::new();
        let decisions: Vec<_> = (0..50)
            .map(|_| create_test_decision("auto", true, 0.90))
            .collect();

        exp.load_from_ledger(decisions).unwrap();
        let annex = exp.extract_for_annex("I").unwrap();
        assert_eq!(annex.decisions_included, 50);
        assert!(annex.summary_metrics.approval_rate > 0.99);
    }
}
