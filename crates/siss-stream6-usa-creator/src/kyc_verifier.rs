use chrono::{DateTime, Duration, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::error::{Stream6Error, Stream6Result};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum KYCStatus {
    Pending,
    Verified,
    Rejected,
    Expired,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KYCRecord {
    pub creator_id: Uuid,
    pub creator_name: String,
    pub status: KYCStatus,
    pub verified_at: Option<DateTime<Utc>>,
    pub expires_at: Option<DateTime<Utc>>,
}

impl KYCRecord {
    pub fn is_valid(&self) -> bool {
        match self.status {
            KYCStatus::Verified => {
                if let Some(expiry) = self.expires_at {
                    Utc::now() < expiry
                } else {
                    true
                }
            }
            _ => false,
        }
    }
}

pub struct KYCVerifier {
    cache: DashMap<Uuid, KYCRecord>,
}

impl KYCVerifier {
    pub fn new() -> Self {
        Self {
            cache: DashMap::new(),
        }
    }

    /// Verify creator identity against US databases.
    /// Creates initial KYC record with Pending status.
    /// Can be updated to Verified after state database lookup.
    pub async fn verify_identity(
        &self,
        creator_id: Uuid,
        creator_name: &str,
        _ssn: &str,
    ) -> Stream6Result<KYCStatus> {
        let record = KYCRecord {
            creator_id,
            creator_name: creator_name.to_string(),
            status: KYCStatus::Pending,
            verified_at: None,
            expires_at: None,
        };

        self.cache.insert(creator_id, record.clone());
        Ok(record.status)
    }

    /// Check if creator's KYC status is valid.
    pub fn get_kyc_status(&self, creator_id: Uuid) -> Stream6Result<KYCStatus> {
        self.cache
            .get(&creator_id)
            .map(|record| record.status)
            .ok_or_else(|| Stream6Error::KYCNotFound(creator_id.to_string()))
    }

    /// Retrieve full KYC record for a creator.
    pub fn get_kyc_record(&self, creator_id: Uuid) -> Stream6Result<KYCRecord> {
        self.cache
            .get(&creator_id)
            .map(|entry| entry.clone())
            .ok_or_else(|| Stream6Error::KYCNotFound(creator_id.to_string()))
    }

    /// Update KYC status for a creator.
    pub fn update_kyc_status(&self, creator_id: Uuid, status: KYCStatus) -> Stream6Result<()> {
        if let Some(mut record) = self.cache.get_mut(&creator_id) {
            record.status = status;
            if status == KYCStatus::Verified {
                record.verified_at = Some(Utc::now());
                record.expires_at = Some(Utc::now() + Duration::days(365));
            }
            Ok(())
        } else {
            Err(Stream6Error::KYCNotFound(creator_id.to_string()))
        }
    }

    /// Clear KYC cache for a creator (for testing).
    pub fn clear_cache(&self, creator_id: Uuid) {
        self.cache.remove(&creator_id);
    }
}

impl Default for KYCVerifier {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    #[tokio::test]
    async fn test_kyc_verifier_initial_status_is_pending() {
        // TODO: Implement test
    }

    #[tokio::test]
    async fn test_kyc_verifier_tracks_verified_creators() {
        // TODO: Implement test
    }

    #[tokio::test]
    async fn test_kyc_status_expiration() {
        // TODO: Implement test
    }
}
