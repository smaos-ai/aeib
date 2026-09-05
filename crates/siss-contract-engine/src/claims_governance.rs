use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Claim {
    pub id: Uuid,
    pub claimant_id: Uuid,
    pub amount_cents: i64,
    pub created_at: Option<DateTime<Utc>>,
    pub status: ClaimStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum ClaimStatus {
    Created,
    Verified,
    Settled,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProofCapsule {
    pub claim_id: Uuid,
    pub merkle_hash: [u8; 32],
    pub parent_hash: [u8; 32],
    pub verified_at: Option<DateTime<Utc>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FraudAlert {
    pub claim_id: Uuid,
    pub claimant_id: Uuid,
    pub anomaly_score: f64,
    pub alert_type: FraudAlertType,
    pub detected_at: DateTime<Utc>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum FraudAlertType {
    UnusualFrequency,
    UnusualAmount,
    UnusualPattern,
    HighRiskProfile,
}

pub struct ClaimsGovernance {
    claims: Arc<DashMap<Uuid, Claim>>,
    proof_capsules: Arc<DashMap<Uuid, ProofCapsule>>,
    fraud_alerts: Arc<DashMap<Uuid, Vec<FraudAlert>>>,
}

impl ClaimsGovernance {
    pub fn new() -> Self {
        Self {
            claims: Arc::new(DashMap::new()),
            proof_capsules: Arc::new(DashMap::new()),
            fraud_alerts: Arc::new(DashMap::new()),
        }
    }

    pub async fn create_claim(
        &self,
        claimant_id: Uuid,
        amount_cents: i64,
    ) -> Result<Claim, String> {
        let claim_id = Uuid::new_v4();
        let now = Utc::now();

        let claim = Claim {
            id: claim_id,
            claimant_id,
            amount_cents,
            created_at: Some(now),
            status: ClaimStatus::Created,
        };

        // Create merkle proof capsule
        let merkle_hash = self.compute_merkle_hash(&claim);
        let parent_hash = self.get_last_merkle_hash();

        let capsule = ProofCapsule {
            claim_id,
            merkle_hash,
            parent_hash,
            verified_at: Some(now),
        };

        self.claims.insert(claim_id, claim.clone());
        self.proof_capsules.insert(claim_id, capsule);

        Ok(claim)
    }

    pub async fn get_proof_capsule(&self, claim_id: &Uuid) -> Result<ProofCapsule, String> {
        self.proof_capsules
            .get(claim_id)
            .map(|c| c.clone())
            .ok_or_else(|| format!("Proof capsule not found for claim {}", claim_id))
    }

    pub async fn verify_claim_chain(&self) -> Result<bool, String> {
        // Verify merkle chain integrity
        // This is a simplified check - in production, would validate full chain

        if self.proof_capsules.is_empty() {
            return Ok(true);
        }

        // For each capsule, verify parent hash matches previous claim's hash
        let mut prev_hash = [0u8; 32];
        let mut valid = true;

        let mut capsules: Vec<_> = self
            .proof_capsules
            .iter()
            .map(|ref_multi| ref_multi.value().clone())
            .collect();

        capsules.sort_by_key(|c| c.verified_at.unwrap_or_else(Utc::now));

        for capsule in capsules {
            if capsule.parent_hash != prev_hash && prev_hash != [0u8; 32] {
                valid = false;
                break;
            }
            prev_hash = capsule.merkle_hash;
        }

        Ok(valid)
    }

    pub async fn detect_fraud(&self) -> Result<Vec<FraudAlert>, String> {
        let mut alerts = Vec::new();

        // Group claims by claimant
        let mut claimant_claims: std::collections::HashMap<Uuid, Vec<Claim>> =
            std::collections::HashMap::new();

        for entry in self.claims.iter() {
            claimant_claims
                .entry(entry.claimant_id)
                .or_insert_with(Vec::new)
                .push(entry.value().clone());
        }

        // Detect fraud patterns per claimant
        for (claimant_id, claims) in claimant_claims.iter() {
            let anomaly_score = self.compute_anomaly_score(claims);

            // Trigger on any significant anomaly or multiple claims
            if anomaly_score > 0.3 || claims.len() > 4 {
                // High anomaly = potential fraud
                for claim in claims {
                    let alert = FraudAlert {
                        claim_id: claim.id,
                        claimant_id: *claimant_id,
                        anomaly_score: anomaly_score.max(0.5), // Ensure minimum alert score
                        alert_type: self.classify_fraud_type(claims),
                        detected_at: Utc::now(),
                    };

                    alerts.push(alert.clone());

                    // Store alert
                    self.fraud_alerts
                        .entry(*claimant_id)
                        .or_insert_with(Vec::new)
                        .push(alert);
                }
            }
        }

        Ok(alerts)
    }

    // Helper functions

    fn compute_merkle_hash(&self, claim: &Claim) -> [u8; 32] {
        let mut hasher = Sha256::new();

        let data = format!(
            "{}||{}||{}",
            claim.claimant_id,
            claim.amount_cents,
            claim.created_at.unwrap_or_else(Utc::now)
        );

        hasher.update(data.as_bytes());
        let result = hasher.finalize();

        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }

    fn get_last_merkle_hash(&self) -> [u8; 32] {
        // Get the hash of the most recently created claim
        let mut hashes: Vec<_> = self
            .proof_capsules
            .iter()
            .map(|ref_multi| {
                (
                    ref_multi.value().verified_at.unwrap_or_else(Utc::now),
                    ref_multi.value().merkle_hash,
                )
            })
            .collect();

        hashes.sort_by(|a, b| b.0.cmp(&a.0));

        hashes.first().map(|(_, hash)| *hash).unwrap_or([0u8; 32])
    }

    fn compute_anomaly_score(&self, claims: &[Claim]) -> f64 {
        if claims.is_empty() {
            return 0.0;
        }

        let mut score = 0.0;

        // Frequency anomaly: multiple claims in short time
        if claims.len() > 3 {
            score += (claims.len() as f64 / 10.0).min(0.4);
        }

        // Amount anomaly: significant variation in claim amounts
        let amounts: Vec<i64> = claims.iter().map(|c| c.amount_cents).collect();
        let mean = amounts.iter().sum::<i64>() / claims.len() as i64;
        let variance: f64 = amounts
            .iter()
            .map(|a| {
                let diff = (*a - mean) as f64;
                diff * diff
            })
            .sum::<f64>()
            / claims.len() as f64;

        let std_dev = variance.sqrt();
        let coef_var = std_dev / mean as f64;

        if coef_var > 0.5 {
            score += (coef_var / 2.0).min(0.3);
        }

        // Temporal anomaly: claims at unusual times (simplified check)
        if claims.iter().any(|c| {
            c.created_at
                .unwrap_or_else(Utc::now)
                .format("%H")
                .to_string()
                .parse::<u32>()
                .unwrap_or(12)
                > 22
                || c.created_at
                    .unwrap_or_else(Utc::now)
                    .format("%H")
                    .to_string()
                    .parse::<u32>()
                    .unwrap_or(12)
                    < 6
        }) {
            score += 0.3;
        }

        score.min(1.0)
    }

    fn classify_fraud_type(&self, claims: &[Claim]) -> FraudAlertType {
        if claims.len() > 3 {
            return FraudAlertType::UnusualFrequency;
        }

        let amounts: Vec<i64> = claims.iter().map(|c| c.amount_cents).collect();
        let mean = amounts.iter().sum::<i64>() / claims.len() as i64;

        if amounts.iter().any(|a| (a - mean).abs() > mean / 2) {
            return FraudAlertType::UnusualAmount;
        }

        FraudAlertType::UnusualPattern
    }
}

impl Default for ClaimsGovernance {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_claims_creation() {
        let claims = ClaimsGovernance::new();
        let claimant_id = Uuid::new_v4();

        let claim = claims.create_claim(claimant_id, 100_000_00).await.unwrap();

        assert_eq!(claim.claimant_id, claimant_id);
        assert_eq!(claim.amount_cents, 100_000_00);
        assert_eq!(claim.status, ClaimStatus::Created);
    }

    #[tokio::test]
    async fn test_proof_capsule_creation() {
        let claims = ClaimsGovernance::new();
        let claim = claims
            .create_claim(Uuid::new_v4(), 50_000_00)
            .await
            .unwrap();

        let capsule = claims.get_proof_capsule(&claim.id).await.unwrap();

        assert_eq!(capsule.claim_id, claim.id);
        assert_eq!(capsule.merkle_hash.len(), 32);
    }

    #[tokio::test]
    async fn test_chain_verification_empty() {
        let claims = ClaimsGovernance::new();
        let result = claims.verify_claim_chain().await;

        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[tokio::test]
    async fn test_fraud_detection_clean() {
        let claims = ClaimsGovernance::new();
        let _ = claims
            .create_claim(Uuid::new_v4(), 50_000_00)
            .await
            .unwrap();

        let alerts = claims.detect_fraud().await.unwrap();
        assert_eq!(alerts.len(), 0);
    }
}
