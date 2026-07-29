use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AP2Entry {
    pub id: Uuid,
    pub session_id: Uuid,
    pub charge_amount: f64,
    pub sovereign_fee: f64,
    pub outcome_value: f64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug)]
pub struct AP2Ledger {
    session_budget: Arc<AtomicU64>,
    hard_cap_cents: u64, // $12.43 = 1243 cents
    entries: Arc<parking_lot::RwLock<Vec<AP2Entry>>>,
}

impl AP2Ledger {
    pub fn new() -> Self {
        Self {
            session_budget: Arc::new(AtomicU64::new(1243)), // $12.43 in cents
            hard_cap_cents: 1243,
            entries: Arc::new(parking_lot::RwLock::new(Vec::new())),
        }
    }

    pub async fn charge_budget(&self, amount_usd: f64) -> Result<AP2Entry, String> {
        let amount_cents = (amount_usd * 100.0) as u64;

        let current = self.session_budget.load(Ordering::SeqCst);
        if amount_cents > current {
            return Err(format!("Budget exceeded: {} cents remaining, {} cents requested", current, amount_cents));
        }

        let sovereign_fee = amount_usd * 0.01; // 1% to sovereign
        let outcome_value = amount_usd * 0.99; // 99% to outcome

        let entry = AP2Entry {
            id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            charge_amount: amount_usd,
            sovereign_fee,
            outcome_value,
            created_at: Utc::now(),
        };

        self.session_budget.fetch_sub(amount_cents, Ordering::SeqCst);
        self.entries.write().push(entry.clone());

        Ok(entry)
    }

    pub fn remaining_budget(&self) -> f64 {
        let cents = self.session_budget.load(Ordering::SeqCst);
        cents as f64 / 100.0
    }

    pub fn hard_cap_usd(&self) -> f64 {
        self.hard_cap_cents as f64 / 100.0
    }

    pub fn total_charged(&self) -> f64 {
        let remaining = self.remaining_budget();
        let hard_cap = self.hard_cap_usd();
        hard_cap - remaining
    }
}

impl Default for AP2Ledger {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_ledger_creation() {
        let ledger = AP2Ledger::new();
        assert_eq!(ledger.hard_cap_usd(), 12.43);
        assert_eq!(ledger.remaining_budget(), 12.43);
    }

    #[tokio::test]
    async fn test_charge_within_budget() {
        let ledger = AP2Ledger::new();
        let result = ledger.charge_budget(5.0).await;
        assert!(result.is_ok());
        let entry = result.unwrap();
        assert_eq!(entry.charge_amount, 5.0);
    }

    #[tokio::test]
    async fn test_charge_exceeds_budget() {
        let ledger = AP2Ledger::new();
        let result = ledger.charge_budget(15.0).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_ap2_1_99_split() {
        let ledger = AP2Ledger::new();
        let entry = ledger.charge_budget(1.0).await.unwrap();
        assert!((entry.sovereign_fee - 0.01).abs() < 0.001);
        assert!((entry.outcome_value - 0.99).abs() < 0.001);
    }
}
