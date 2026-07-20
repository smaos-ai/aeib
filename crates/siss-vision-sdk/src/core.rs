use crate::{AuditEntry, Settlement, SplitRatio, VisionError, Result, EarningsSummary};
use uuid::Uuid;
use std::collections::HashMap;
use parking_lot::RwLock;
use chrono::Utc;

pub struct RevenueRouter {
    #[allow(dead_code)]
    test_mode: bool,
    settlements: RwLock<HashMap<Uuid, Settlement>>,
    earnings: RwLock<HashMap<Uuid, EarningsSummary>>,
}

impl RevenueRouter {
    pub fn new(test_mode: bool) -> Self {
        Self {
            test_mode,
            settlements: RwLock::new(HashMap::new()),
            earnings: RwLock::new(HashMap::new()),
        }
    }

    pub async fn calculate_split(
        &self,
        creator_id: Uuid,
        value: f64,
        ratio: SplitRatio,
    ) -> Result<Settlement> {
        let creator_payout = value * (ratio.creator_percentage / 100.0);
        let platform_fee = value * (ratio.platform_percentage / 100.0);

        let settlement = Settlement {
            decision_id: Uuid::new_v4(),
            creator_id,
            value_detected: value,
            creator_payout,
            platform_fee,
            timestamp: Utc::now(),
            merkle_proof: "0x_settlement_proof".to_string(),
        };

        self.settlements.write().insert(settlement.decision_id, settlement.clone());

        // Update earnings
        let mut earnings = self.earnings.write();
        let summary = earnings.entry(creator_id).or_insert_with(|| EarningsSummary {
            creator_id,
            total_detected: 0.0,
            creator_total: 0.0,
            platform_total: 0.0,
            by_platform: HashMap::new(),
            period_start: Utc::now(),
            period_end: Utc::now(),
        });

        summary.total_detected += value;
        summary.creator_total += creator_payout;
        summary.platform_total += platform_fee;

        Ok(settlement)
    }

    pub async fn get_earnings_summary(
        &self,
        creator_id: Uuid,
    ) -> Result<EarningsSummary> {
        self.earnings
            .read()
            .get(&creator_id)
            .cloned()
            .ok_or_else(|| VisionError::RevenueError("No earnings found".to_string()))
    }
}

pub struct AuditLog {
    #[allow(dead_code)]
    test_mode: bool,
    entries: RwLock<HashMap<Uuid, AuditEntry>>,
}

impl AuditLog {
    pub fn new(test_mode: bool) -> Self {
        Self {
            test_mode,
            entries: RwLock::new(HashMap::new()),
        }
    }

    pub async fn record(&self, entry: AuditEntry) -> Result<()> {
        self.entries.write().insert(entry.id, entry);
        Ok(())
    }

    pub async fn get_entry(&self, id: Uuid) -> Result<AuditEntry> {
        self.entries
            .read()
            .get(&id)
            .cloned()
            .ok_or_else(|| VisionError::AuditError("Entry not found".to_string()))
    }

    pub async fn get_entries_for_creator(&self, creator_id: Uuid) -> Result<Vec<AuditEntry>> {
        Ok(self
            .entries
            .read()
            .values()
            .filter(|e| e.creator_id == creator_id)
            .cloned()
            .collect())
    }
}
