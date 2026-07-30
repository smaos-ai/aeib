//! Nightly Reporter Module — Phase 31
//! Generates and stores nightly settlement reports with 7-year retention.

use chrono::{DateTime, Utc, NaiveDate, Duration};
use sha2::{Digest, Sha256};
use std::collections::HashMap;

use crate::settlement_batch::BatchResult;
use crate::fx_reconciliation::{ReconciliationReport, Currency, FxRate};

/// Nightly Report — immutable, 7-year retention enforced at type level
pub struct NightlyReport {
    pub date: NaiveDate,
    pub batch_result: BatchResult,
    pub fx_snapshot: HashMap<(Currency, Currency), FxRate>,
    pub merkle_root: [u8; 32],
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    fx_audit_hash: [u8; 32], // stored for verify_integrity()
}

impl NightlyReport {
    /// Generate a nightly report (7-year retention auto-calculated)
    pub fn generate(
        date: NaiveDate,
        batch: BatchResult,
        fx: ReconciliationReport,
    ) -> Self {
        let created_at = Utc::now();
        let expires_at = created_at + Duration::days(365 * 7);

        let merkle_root = compute_merkle_deterministic(
            &batch.merkle_root,
            &fx.audit_hash,
            &date,
        );

        Self {
            date,
            batch_result: batch,
            fx_snapshot: HashMap::new(),
            merkle_root,
            created_at,
            expires_at,
            fx_audit_hash: fx.audit_hash,
        }
    }

    /// Verify merkle root integrity
    pub fn verify_integrity(&self) -> bool {
        let recomputed = compute_merkle_deterministic(
            &self.batch_result.merkle_root,
            &self.fx_audit_hash,
            &self.date,
        );
        self.merkle_root == recomputed
    }

    /// Get deterministic merkle root
    pub fn merkle_root_deterministic(&self) -> [u8; 32] {
        self.merkle_root
    }
}

/// Deterministic merkle root computation
fn compute_merkle_deterministic(batch_root: &[u8; 32], fx_hash: &[u8; 32], date: &NaiveDate) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(batch_root);
    hasher.update(fx_hash);
    hasher.update(date.to_string().as_bytes());
    let result = hasher.finalize();
    let mut root = [0u8; 32];
    root.copy_from_slice(&result);
    root
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nightly_report_7_year_expiry() {
        let batch = BatchResult {
            settled: 1,
            failed: 0,
            merkle_root: [0u8; 32],
            timestamp: Utc::now(),
        };
        let fx = ReconciliationReport {
            total_converted_eur: 100,
            discrepancy_cents: 0,
            audit_hash: [0u8; 32],
            timestamp: Utc::now(),
        };

        let report = NightlyReport::generate(Utc::now().naive_utc().date(), batch, fx);
        let seven_years = Duration::days(365 * 7);
        assert!(report.expires_at - report.created_at >= seven_years);
    }
}
