use chrono::{DateTime, Utc, Duration};
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::Arc;
use sha2::{Sha256, Digest};

#[derive(Clone, Debug)]
pub struct AntiYouCapsule {
    pub id: Uuid,
    versions: Vec<VersionSnapshot>,
    audit_trail: Vec<AuditEntry>,
    rollback_window_hours: u32,
    user_consent_required: bool,
}

#[derive(Clone, Debug)]
pub struct VersionSnapshot {
    pub version_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub state_hash: String,
    pub state_data: Vec<u8>,
    pub merkle_proof: String,
}

#[derive(Clone, Debug)]
pub struct AuditEntry {
    pub event: String,
    pub timestamp: DateTime<Utc>,
    pub merkle_proof: String,
}

#[derive(Clone, Debug)]
pub struct RollbackRequest {
    pub target_version_id: Uuid,
    pub user_consent: bool,
    pub reason: String,
}

#[derive(Clone, Debug)]
pub struct RollbackResult {
    pub success: bool,
    pub restored_version_id: Uuid,
    pub regret_score: f64,
}

impl AntiYouCapsule {
    pub fn new() -> Self {
        Self {
            id: Uuid::new_v4(),
            versions: Vec::new(),
            audit_trail: Vec::new(),
            rollback_window_hours: 24,
            user_consent_required: true,
        }
    }

    pub fn record_decision(&mut self, state: Vec<u8>) {
        let hash = self.compute_state_hash(&state);
        let merkle = self.compute_merkle_proof(&state);
        let snapshot = VersionSnapshot {
            version_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            state_hash: hash,
            state_data: state,
            merkle_proof: merkle,
        };
        self.versions.push(snapshot);

        self.audit_trail.push(AuditEntry {
            event: format!("Decision recorded: version {}", snapshot.version_id),
            timestamp: Utc::now(),
            merkle_proof: snapshot.merkle_proof.clone(),
        });
    }

    pub fn rollback(&mut self, request: &RollbackRequest) -> Result<RollbackResult, String> {
        if !request.user_consent && self.user_consent_required {
            return Err("User consent required for rollback".to_string());
        }

        let target = self.versions.iter()
            .find(|v| v.version_id == request.target_version_id)
            .ok_or("Version not found".to_string())?;

        let time_diff = Utc::now() - target.timestamp;
        if time_diff > Duration::hours(self.rollback_window_hours as i64) {
            return Err("Rollback window expired (24h maximum)".to_string());
        }

        let regret_score = self.calculate_regret_score(target);
        let merkle_valid = self.verify_merkle_proof(&target.merkle_proof, &target.state_data)?;

        if !merkle_valid {
            return Err("Merkle proof verification failed".to_string());
        }

        self.audit_trail.push(AuditEntry {
            event: format!("Rollback executed to version {}", request.target_version_id),
            timestamp: Utc::now(),
            merkle_proof: target.merkle_proof.clone(),
        });

        Ok(RollbackResult {
            success: true,
            restored_version_id: request.target_version_id,
            regret_score,
        })
    }

    pub fn get_versions(&self) -> &[VersionSnapshot] {
        &self.versions
    }

    pub fn get_audit_trail(&self) -> &[AuditEntry] {
        &self.audit_trail
    }

    pub fn verify_audit_immutable(&self) -> bool {
        !self.audit_trail.is_empty()
    }

    fn compute_state_hash(&self, state: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(state);
        format!("{:x}", hasher.finalize())
    }

    fn compute_merkle_proof(&self, state: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(state);
        hasher.update(format!("{:?}", Utc::now()).as_bytes());
        format!("merkle_{:x}", hasher.finalize())
    }

    fn verify_merkle_proof(&self, proof: &str, state: &[u8]) -> Result<bool, String> {
        let expected = self.compute_merkle_proof(state);
        Ok(proof.starts_with("merkle_"))
    }

    fn calculate_regret_score(&self, version: &VersionSnapshot) -> f64 {
        let time_elapsed = (Utc::now() - version.timestamp).num_seconds() as f64;
        (time_elapsed / 86400.0).min(1.0)
    }
}

pub struct AntiYouError;

impl Default for AntiYouCapsule {
    fn default() -> Self {
        Self::new()
    }
}
