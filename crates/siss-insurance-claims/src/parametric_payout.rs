use crate::types::ParametricTrigger;
use chrono::{Datelike, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum PayoutError {
    #[error("Payout not found: {0}")]
    PayoutNotFound(Uuid),
    #[error("Invalid payout state")]
    InvalidState,
    #[error("Payout operation failed")]
    OperationFailed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParametricPayout {
    pub id: Uuid,
    pub claim_id: Uuid,
    pub trigger: ParametricTrigger,
    pub payout_amount: u64, // in cents
    pub executed_at: Option<chrono::DateTime<chrono::Utc>>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

pub struct ParametricPayoutEngine {
    payouts: DashMap<Uuid, ParametricPayout>,
}

impl ParametricPayoutEngine {
    pub fn new() -> Self {
        Self {
            payouts: DashMap::new(),
        }
    }

    /// Create a parametric payout with trigger conditions
    pub fn create_payout(
        &self,
        claim_id: Uuid,
        trigger: ParametricTrigger,
        amount: u64,
    ) -> Result<ParametricPayout, PayoutError> {
        let payout = ParametricPayout {
            id: Uuid::new_v4(),
            claim_id,
            trigger,
            payout_amount: amount,
            executed_at: None,
            created_at: Utc::now(),
        };

        self.payouts.insert(payout.id, payout.clone());
        Ok(payout)
    }

    /// Execute a parametric payout (when trigger conditions are met)
    pub fn execute_payout(&self, payout_id: &Uuid) -> Result<ParametricPayout, PayoutError> {
        let mut payout = self
            .payouts
            .get_mut(payout_id)
            .ok_or(PayoutError::PayoutNotFound(*payout_id))?;

        payout.executed_at = Some(Utc::now());
        Ok(payout.clone())
    }

    /// Get all pending payouts (not executed)
    pub fn get_pending_payouts(&self) -> Result<Vec<ParametricPayout>, PayoutError> {
        let pending: Vec<_> = self
            .payouts
            .iter()
            .filter(|p| p.executed_at.is_none())
            .map(|p| p.clone())
            .collect();

        Ok(pending)
    }

    /// Get executed payouts
    pub fn get_executed_payouts(&self) -> Result<Vec<ParametricPayout>, PayoutError> {
        let executed: Vec<_> = self
            .payouts
            .iter()
            .filter(|p| p.executed_at.is_some())
            .map(|p| p.clone())
            .collect();

        Ok(executed)
    }

    /// Get payouts for a specific claim
    pub fn get_payouts_for_claim(
        &self,
        claim_id: &Uuid,
    ) -> Result<Vec<ParametricPayout>, PayoutError> {
        let payouts: Vec<_> = self
            .payouts
            .iter()
            .filter(|p| p.claim_id == *claim_id)
            .map(|p| p.clone())
            .collect();

        Ok(payouts)
    }

    /// Check if a trigger condition is met
    pub fn check_trigger(
        &self,
        trigger: &ParametricTrigger,
        data: &PayoutData,
    ) -> Result<bool, PayoutError> {
        match trigger {
            ParametricTrigger::EventThreshold {
                event_type: _,
                threshold,
            } => Ok(data.event_severity.unwrap_or(0) >= *threshold),
            ParametricTrigger::TimeWindow { start_day, end_day } => {
                let today = Utc::now().ordinal();
                Ok(today >= *start_day as u32 && today <= *end_day as u32)
            }
            ParametricTrigger::DataFeed {
                source: _,
                min_value,
            } => Ok(data.feed_value.unwrap_or(0.0) >= *min_value),
        }
    }

    /// Get total payout amount for claims
    pub fn get_total_payouts(&self) -> Result<u64, PayoutError> {
        let total: u64 = self.payouts.iter().map(|p| p.payout_amount).sum();

        Ok(total)
    }

    /// Settle multiple claims (batch settlement)
    pub fn settle_batch(&self, claim_ids: &[Uuid]) -> Result<Vec<ParametricPayout>, PayoutError> {
        let mut settled = Vec::new();

        for claim_id in claim_ids {
            let payouts = self.get_payouts_for_claim(claim_id)?;
            for payout in payouts {
                if payout.executed_at.is_none() {
                    let executed = self.execute_payout(&payout.id)?;
                    settled.push(executed);
                }
            }
        }

        Ok(settled)
    }
}

impl Default for ParametricPayoutEngine {
    fn default() -> Self {
        Self::new()
    }
}

/// Data for trigger evaluation
#[derive(Debug, Clone)]
pub struct PayoutData {
    pub event_severity: Option<i32>,
    pub feed_value: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_and_execute_payout() {
        let engine = ParametricPayoutEngine::new();
        let claim_id = Uuid::new_v4();
        let trigger = ParametricTrigger::EventThreshold {
            event_type: "earthquake".to_string(),
            threshold: 7,
        };

        let payout = engine.create_payout(claim_id, trigger, 100_000_00).unwrap();
        assert!(payout.executed_at.is_none());

        let executed = engine.execute_payout(&payout.id).unwrap();
        assert!(executed.executed_at.is_some());
    }

    #[test]
    fn test_get_pending_payouts() {
        let engine = ParametricPayoutEngine::new();

        for i in 0..3 {
            let claim_id = Uuid::new_v4();
            let trigger = ParametricTrigger::EventThreshold {
                event_type: "flood".to_string(),
                threshold: 3,
            };
            let _ = engine
                .create_payout(claim_id, trigger, (i + 1) as u64 * 50_000_00)
                .unwrap();
        }

        let pending = engine.get_pending_payouts().unwrap();
        assert_eq!(pending.len(), 3);
    }
}
