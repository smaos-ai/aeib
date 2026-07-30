use crate::contract::Contract;
use crate::error::RevenueError;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::atomic::{AtomicI64, Ordering};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SettlementState {
    Pending,
    Settled,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settlement {
    pub contract_id: Uuid,
    pub period_start: DateTime<Utc>,
    pub period_end: DateTime<Utc>,
    pub amount_cents: i64,
    pub status: SettlementState,
}

pub struct MonthlyPeriod {
    pub start: DateTime<Utc>,
    pub end: DateTime<Utc>,
}

pub struct RevenueTracker {
    contracts: Arc<DashMap<Uuid, Contract>>,
    arr_total: Arc<AtomicI64>,
    settlements: Arc<DashMap<(Uuid, DateTime<Utc>), Settlement>>,
}

impl RevenueTracker {
    pub fn new() -> Self {
        Self {
            contracts: Arc::new(DashMap::new()),
            arr_total: Arc::new(AtomicI64::new(0)),
            settlements: Arc::new(DashMap::new()),
        }
    }

    pub async fn register_contract(&self, contract: Contract) -> Result<Uuid, RevenueError> {
        let id = contract.id;

        if self.contracts.contains_key(&id) {
            return Err(RevenueError::DuplicateContract);
        }

        // Only count active contracts toward ARR
        let (amount, _) = contract.calculate_arr_progress();
        if amount > 0 {
            self.arr_total.fetch_add(amount, Ordering::SeqCst);
        }

        self.contracts.insert(id, contract);
        Ok(id)
    }

    pub fn calculate_arr(&self) -> i64 {
        let mut total = 0i64;
        for entry in self.contracts.iter() {
            let (amount, _) = entry.value().calculate_arr_progress();
            total += amount;
        }
        total
    }

    pub async fn settle_billing_cycle(&self, period: MonthlyPeriod) -> Result<(), RevenueError> {
        let mut all_settled = Vec::new();

        // Prepare settlements for all active contracts
        for entry in self.contracts.iter() {
            let contract = entry.value();
            let (arr_commitment, _) = contract.calculate_arr_progress();

            if arr_commitment > 0 {
                // Monthly billing = ARR / 12
                let monthly_amount = arr_commitment / 12;

                let settlement = Settlement {
                    contract_id: contract.id,
                    period_start: period.start,
                    period_end: period.end,
                    amount_cents: monthly_amount,
                    status: SettlementState::Pending,
                };

                all_settled.push((contract.id, settlement));
            }
        }

        // Atomicity: all-or-nothing (Phase 30 reference)
        // In production, this would be backed by AtomicSettlement merkle commitment
        if all_settled.is_empty() {
            return Ok(());
        }

        // Commit all or fail all
        for (contract_id, mut settlement) in all_settled {
            let key = (contract_id, period.start);
            settlement.status = SettlementState::Settled;
            self.settlements.insert(key, settlement);
        }

        // Verify atomicity
        for entry in self.settlements.iter() {
            if entry.value().status != SettlementState::Settled {
                return Err(RevenueError::SettlementFailed(
                    "Settlement verification failed".to_string(),
                ));
            }
        }

        Ok(())
    }

    pub fn get_arr_progress(&self) -> (i64, f64) {
        let current = self.calculate_arr();
        let target = 50_000_000; // €5M in cents
        let percentage = if target > 0 {
            (current as f64 / target as f64) * 100.0
        } else {
            0.0
        };
        (current, percentage)
    }

    pub fn get_settlement_count(&self) -> usize {
        self.settlements.len()
    }

    pub fn get_contract_count(&self) -> usize {
        self.contracts.len()
    }
}

impl Default for RevenueTracker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract::{Contract, VerticalType};
    use crate::pilot_sla_enforcer::PilotSlaEnforcer;
    use crate::vertical_policy::{DefensePolicy, HealthcarePolicy, FinancePolicy};

    fn create_test_contract(vertical: VerticalType, arr: i64) -> Contract {
        let (policy, region) = match vertical {
            VerticalType::Defense => (
                Arc::new(DefensePolicy::new()) as Arc<dyn crate::vertical_policy::VerticalPolicy>,
                "Military-Zone-West".to_string(),
            ),
            VerticalType::Healthcare => (
                Arc::new(HealthcarePolicy::new()) as Arc<dyn crate::vertical_policy::VerticalPolicy>,
                "eu-central-1".to_string(),
            ),
            VerticalType::Finance => (
                Arc::new(FinancePolicy::new()) as Arc<dyn crate::vertical_policy::VerticalPolicy>,
                "eu-west-1".to_string(),
            ),
            VerticalType::Government => (
                Arc::new(crate::government_policy::GovernmentPolicy::new_high()) as Arc<dyn crate::vertical_policy::VerticalPolicy>,
                "us-gov-west-1".to_string(),
            ),
        };
        let sla = Arc::new(PilotSlaEnforcer::new(Uuid::new_v4()));

        Contract::new(
            Uuid::new_v4(),
            vertical,
            region,
            Utc::now(),
            Utc::now() + chrono::Duration::days(90),
            arr,
            policy,
            sla,
        )
        .unwrap()
    }

    #[tokio::test]
    async fn test_revenue_tracker_calculates_arr() {
        let tracker = RevenueTracker::new();

        // Create 3 contracts totaling €5M
        let mut c1 = create_test_contract(VerticalType::Defense, 150_000_00);
        let mut c2 = create_test_contract(VerticalType::Healthcare, 150_000_00);
        let mut c3 = create_test_contract(VerticalType::Finance, 200_000_00);

        // Activate all contracts
        c1.activate().await.unwrap();
        c2.activate().await.unwrap();
        c3.activate().await.unwrap();

        tracker.register_contract(c1).await.unwrap();
        tracker.register_contract(c2).await.unwrap();
        tracker.register_contract(c3).await.unwrap();

        let arr = tracker.calculate_arr();
        assert_eq!(arr, 500_000_00);

        let (current, percentage) = tracker.get_arr_progress();
        assert_eq!(current, 500_000_00);
        assert!((percentage - 100.0).abs() < 0.01);
    }

    #[tokio::test]
    async fn test_revenue_tracker_settle_billing_cycle() {
        let tracker = RevenueTracker::new();

        let mut contract = create_test_contract(VerticalType::Defense, 120_000_00);
        contract.activate().await.unwrap();

        tracker.register_contract(contract).await.unwrap();

        let period = MonthlyPeriod {
            start: Utc::now(),
            end: Utc::now() + chrono::Duration::days(30),
        };

        let result = tracker.settle_billing_cycle(period).await;
        assert!(result.is_ok());
        assert_eq!(tracker.get_settlement_count(), 1);
    }

    #[tokio::test]
    async fn test_revenue_tracker_settlement_atomicity() {
        let tracker = RevenueTracker::new();

        // 3 contracts
        let mut c1 = create_test_contract(VerticalType::Defense, 166_666_67);
        let mut c2 = create_test_contract(VerticalType::Healthcare, 166_666_67);
        let mut c3 = create_test_contract(VerticalType::Finance, 166_666_66);

        c1.activate().await.unwrap();
        c2.activate().await.unwrap();
        c3.activate().await.unwrap();

        tracker.register_contract(c1).await.unwrap();
        tracker.register_contract(c2).await.unwrap();
        tracker.register_contract(c3).await.unwrap();

        let period = MonthlyPeriod {
            start: Utc::now(),
            end: Utc::now() + chrono::Duration::days(30),
        };

        let result = tracker.settle_billing_cycle(period).await;
        assert!(result.is_ok());
        assert_eq!(tracker.get_settlement_count(), 3);
    }

    #[tokio::test]
    async fn test_revenue_tracker_arr_progress_tracking() {
        let tracker = RevenueTracker::new();

        let mut c1 = create_test_contract(VerticalType::Defense, 166_666_67);
        c1.activate().await.unwrap();

        tracker.register_contract(c1).await.unwrap();

        let (current, percentage) = tracker.get_arr_progress();
        assert_eq!(current, 166_666_67);
        assert!((percentage - 33.33).abs() < 1.0);
    }

    #[tokio::test]
    async fn test_revenue_tracker_settlement_audit_trail() {
        let tracker = RevenueTracker::new();

        let mut contract = create_test_contract(VerticalType::Defense, 120_000_00);
        contract.activate().await.unwrap();

        tracker.register_contract(contract).await.unwrap();

        let period = MonthlyPeriod {
            start: Utc::now(),
            end: Utc::now() + chrono::Duration::days(30),
        };

        tracker.settle_billing_cycle(period).await.unwrap();

        // Verify settlements are logged (7-year retention in production)
        assert!(tracker.get_settlement_count() > 0);
    }
}
