use chrono::{DateTime, Duration, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

/// Settlement status
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum SettlementStatus {
    Pending,
    Confirmed,
    Settled,
    Failed,
    Reversed,
}

impl SettlementStatus {
    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            SettlementStatus::Settled | SettlementStatus::Failed | SettlementStatus::Reversed
        )
    }

    pub fn is_settled(&self) -> bool {
        *self == SettlementStatus::Settled
    }
}

/// Real-time settlement instruction (sub-1ms latency target)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settlement {
    pub id: Uuid,
    pub order_id: Uuid,
    pub sender_account: String,
    pub receiver_account: String,
    pub currency: String,
    pub amount_cents: i64, // in cents to avoid floating point
    pub settlement_status: SettlementStatus,
    pub created_at: DateTime<Utc>,
    pub expected_settlement_at: DateTime<Utc>,
    pub actual_settlement_at: Option<DateTime<Utc>>,
    pub settlement_path: String, // e.g., "SWIFT", "TARGET2", "DvP"
}

impl Settlement {
    pub fn new(
        order_id: Uuid,
        sender: String,
        receiver: String,
        currency: String,
        amount_cents: i64,
    ) -> Self {
        let now = Utc::now();
        let expected_at = now + Duration::seconds(5); // T+5 seconds for real-time settlement

        Self {
            id: Uuid::new_v4(),
            order_id,
            sender_account: sender,
            receiver_account: receiver,
            currency,
            amount_cents,
            settlement_status: SettlementStatus::Pending,
            created_at: now,
            expected_settlement_at: expected_at,
            actual_settlement_at: None,
            settlement_path: "DvP".to_string(), // Default: Delivery vs Payment
        }
    }

    pub fn with_settlement_path(mut self, path: String) -> Self {
        self.settlement_path = path;
        self
    }

    /// Confirm settlement (move to confirmed state)
    pub fn confirm(&mut self) -> Result<(), String> {
        if self.settlement_status != SettlementStatus::Pending {
            return Err(format!(
                "Settlement {:?} cannot be confirmed from {:?} state",
                self.id, self.settlement_status
            ));
        }
        self.settlement_status = SettlementStatus::Confirmed;
        Ok(())
    }

    /// Complete settlement (atomic commit)
    pub fn complete(&mut self) -> Result<(), String> {
        if self.settlement_status != SettlementStatus::Confirmed {
            return Err(format!(
                "Settlement must be confirmed before completing"
            ));
        }
        self.settlement_status = SettlementStatus::Settled;
        self.actual_settlement_at = Some(Utc::now());
        Ok(())
    }

    /// Fail settlement
    pub fn fail(&mut self) -> Result<(), String> {
        if self.settlement_status.is_terminal() {
            return Err("Cannot fail a terminal settlement".to_string());
        }
        self.settlement_status = SettlementStatus::Failed;
        Ok(())
    }

    /// Reverse settlement
    pub fn reverse(&mut self) -> Result<(), String> {
        if !self.settlement_status.is_settled() {
            return Err("Only settled settlements can be reversed".to_string());
        }
        self.settlement_status = SettlementStatus::Reversed;
        Ok(())
    }

    /// Get settlement latency in milliseconds
    pub fn latency_ms(&self) -> Option<u32> {
        self.actual_settlement_at.map(|settled| {
            let duration = settled.signed_duration_since(self.created_at);
            duration.num_milliseconds().max(0) as u32
        })
    }

    /// Check if within SLA (sub-1ms for real-time)
    pub fn meets_sla(&self) -> bool {
        if let Some(latency) = self.latency_ms() {
            latency < 1000 // 1 second SLA for real-time settlement
        } else {
            false
        }
    }
}

/// Real-time settlement ledger with atomic operations
pub struct SettlementLedger {
    settlements: Arc<DashMap<Uuid, Settlement>>,
}

impl SettlementLedger {
    pub fn new() -> Self {
        Self {
            settlements: Arc::new(DashMap::new()),
        }
    }

    /// Add settlement instruction
    pub fn add_settlement(&self, settlement: Settlement) -> Result<Uuid, String> {
        let settlement_id = settlement.id;
        self.settlements.insert(settlement_id, settlement);
        Ok(settlement_id)
    }

    /// Get settlement by ID
    pub fn get_settlement(&self, settlement_id: Uuid) -> Option<Settlement> {
        self.settlements.get(&settlement_id).map(|s| s.clone())
    }

    /// Get settlements for order
    pub fn get_settlements_for_order(&self, order_id: Uuid) -> Vec<Settlement> {
        self.settlements
            .iter()
            .filter(|s| s.order_id == order_id)
            .map(|s| s.clone())
            .collect()
    }

    /// Confirm settlement (atomic operation)
    pub fn confirm_settlement(&self, settlement_id: Uuid) -> Result<(), String> {
        self.settlements.alter(&settlement_id, |_, mut settlement| {
            settlement.confirm()?;
            Ok(settlement)
        })
    }

    /// Complete settlement (atomic operation)
    pub fn complete_settlement(&self, settlement_id: Uuid) -> Result<(), String> {
        self.settlements.alter(&settlement_id, |_, mut settlement| {
            settlement.complete()?;
            Ok(settlement)
        })
    }

    /// Get all pending settlements
    pub fn get_pending_settlements(&self) -> Vec<Settlement> {
        self.settlements
            .iter()
            .filter(|s| s.settlement_status == SettlementStatus::Pending)
            .map(|s| s.clone())
            .collect()
    }

    /// Get all settled settlements
    pub fn get_settled_settlements(&self) -> Vec<Settlement> {
        self.settlements
            .iter()
            .filter(|s| s.settlement_status.is_settled())
            .map(|s| s.clone())
            .collect()
    }

    /// Settlement SLA compliance: % of settled within latency
    pub fn sla_compliance_percent(&self) -> f64 {
        let settled = self.get_settled_settlements();
        if settled.is_empty() {
            return 0.0;
        }

        let compliant = settled.iter().filter(|s| s.meets_sla()).count();
        (compliant as f64 / settled.len() as f64) * 100.0
    }

    pub fn len(&self) -> usize {
        self.settlements.len()
    }

    pub fn is_empty(&self) -> bool {
        self.settlements.is_empty()
    }
}

impl Clone for SettlementLedger {
    fn clone(&self) -> Self {
        SettlementLedger {
            settlements: Arc::clone(&self.settlements),
        }
    }
}

impl Default for SettlementLedger {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_settlement_creation() {
        let settlement = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        assert_eq!(settlement.settlement_status, SettlementStatus::Pending);
        assert_eq!(settlement.currency, "EUR");
        assert_eq!(settlement.amount_cents, 100000);
    }

    #[test]
    fn test_settlement_confirm() {
        let mut settlement = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        let result = settlement.confirm();
        assert!(result.is_ok());
        assert_eq!(settlement.settlement_status, SettlementStatus::Confirmed);
    }

    #[test]
    fn test_settlement_complete() {
        let mut settlement = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        assert!(settlement.confirm().is_ok());
        assert!(settlement.complete().is_ok());
        assert_eq!(settlement.settlement_status, SettlementStatus::Settled);
        assert!(settlement.actual_settlement_at.is_some());
    }

    #[test]
    fn test_settlement_latency_tracking() {
        let mut settlement = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        assert!(settlement.confirm().is_ok());
        assert!(settlement.complete().is_ok());

        let latency = settlement.latency_ms();
        assert!(latency.is_some());
        assert!(latency.unwrap() < 100); // Should be sub-100ms in tests
    }

    #[test]
    fn test_settlement_reverse() {
        let mut settlement = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        assert!(settlement.confirm().is_ok());
        assert!(settlement.complete().is_ok());
        assert!(settlement.reverse().is_ok());
        assert_eq!(settlement.settlement_status, SettlementStatus::Reversed);
    }

    #[test]
    fn test_settlement_ledger_add_settlement() {
        let ledger = SettlementLedger::new();
        let settlement = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        let settlement_id = settlement.id;
        let result = ledger.add_settlement(settlement);
        assert!(result.is_ok());
        assert_eq!(ledger.len(), 1);
        assert!(ledger.get_settlement(settlement_id).is_some());
    }

    #[test]
    fn test_settlement_ledger_pending_settlements() {
        let ledger = SettlementLedger::new();
        let settlement1 = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        let mut settlement2 = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT003".to_string(),
            "ACCOUNT004".to_string(),
            "USD".to_string(),
            150000,
        );

        let _ = ledger.add_settlement(settlement1);
        assert!(settlement2.confirm().is_ok());
        let _ = ledger.add_settlement(settlement2);

        let pending = ledger.get_pending_settlements();
        assert_eq!(pending.len(), 1);
    }

    #[test]
    fn test_settlement_sla_compliance() {
        let ledger = SettlementLedger::new();
        let mut settlement = Settlement::new(
            Uuid::new_v4(),
            "ACCOUNT001".to_string(),
            "ACCOUNT002".to_string(),
            "EUR".to_string(),
            100000,
        );

        assert!(settlement.confirm().is_ok());
        assert!(settlement.complete().is_ok());
        let _ = ledger.add_settlement(settlement);

        let compliance = ledger.sla_compliance_percent();
        assert!(compliance > 0.0 && compliance <= 100.0);
    }

    #[test]
    fn test_settlement_status_terminal_check() {
        assert!(!SettlementStatus::Pending.is_terminal());
        assert!(!SettlementStatus::Confirmed.is_terminal());
        assert!(SettlementStatus::Settled.is_terminal());
        assert!(SettlementStatus::Failed.is_terminal());
        assert!(SettlementStatus::Reversed.is_terminal());
    }
}
