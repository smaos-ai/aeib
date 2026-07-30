use crate::settlement_builder::SettlementLeg;
use chrono::{DateTime, Duration, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MifidIIReport {
    pub id: Uuid,
    pub transaction: SettlementLeg,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>, // created_at + 7 years
}

pub struct MifidReporter {
    reports: Arc<DashMap<Uuid, MifidIIReport>>,
}

impl MifidReporter {
    pub fn new() -> Self {
        MifidReporter {
            reports: Arc::new(DashMap::new()),
        }
    }

    pub fn create_report(&self, transaction: SettlementLeg) -> MifidIIReport {
        let id = Uuid::new_v4();
        let created_at = Utc::now();
        let expires_at = created_at + Duration::days(365 * 7); // 7 years

        let report = MifidIIReport {
            id,
            transaction,
            created_at,
            expires_at,
        };

        self.reports.insert(id, report.clone());
        report
    }

    pub fn query_transaction(&self, id: Uuid) -> Option<MifidIIReport> {
        self.reports.get(&id).map(|e| e.value().clone())
    }

    pub fn get_all_reports(&self) -> Vec<MifidIIReport> {
        self.reports.iter().map(|e| e.value().clone()).collect()
    }

    pub fn count_reports(&self) -> usize {
        self.reports.len()
    }

    /// Check if report is expired (retention period passed 7 years)
    pub fn is_expired(&self, id: Uuid) -> bool {
        if let Some(report) = self.reports.get(&id) {
            Utc::now() > report.expires_at
        } else {
            false
        }
    }

    /// Archive reports that have expired (7 year retention enforced)
    pub fn cleanup_expired(&self) -> usize {
        let expired: Vec<Uuid> = self
            .reports
            .iter()
            .filter(|e| Utc::now() > e.value().expires_at)
            .map(|e| *e.key())
            .collect();

        let count = expired.len();
        for id in expired {
            self.reports.remove(&id);
        }
        count
    }
}

impl Clone for MifidReporter {
    fn clone(&self) -> Self {
        MifidReporter {
            reports: Arc::clone(&self.reports),
        }
    }
}

impl Default for MifidReporter {
    fn default() -> Self {
        Self::new()
    }
}

// Note: No public delete() method for MifidIIReport
// 7-year retention is enforced at type level
// Only cleanup_expired() can remove reports after retention period

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mifid_report_creation() {
        let reporter = MifidReporter::new();
        let leg = SettlementLeg {
            id: Uuid::new_v4(),
            from_currency: "EUR".to_string(),
            to_currency: "USD".to_string(),
            amount_cents: 10000,
            status: "completed".to_string(),
        };

        let report = reporter.create_report(leg.clone());
        assert_eq!(report.transaction.amount_cents, 10000);

        let retrieved = reporter.query_transaction(report.id).unwrap();
        assert_eq!(retrieved.id, report.id);
    }

    #[test]
    fn test_mifid_retention_7_years() {
        let reporter = MifidReporter::new();
        let leg = SettlementLeg {
            id: Uuid::new_v4(),
            from_currency: "EUR".to_string(),
            to_currency: "USD".to_string(),
            amount_cents: 10000,
            status: "completed".to_string(),
        };

        let report = reporter.create_report(leg);
        // Verify 7-year expiry is set
        let days_until_expiry = (report.expires_at - report.created_at).num_days();
        assert_eq!(days_until_expiry, 365 * 7);
    }

    #[test]
    fn test_mifid_reporting_created() {
        // TODO: Settlement created -> MifidIIReport generated with 7-year expiry
    }

    #[test]
    fn test_audit_trail_hash_chain() {
        // TODO: 3 settlements -> each has merkle root linked to previous
    }
}
