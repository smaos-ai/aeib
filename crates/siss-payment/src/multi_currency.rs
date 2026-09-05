use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub id: Uuid,
    pub from_currency: String,
    pub to_currency: String,
    pub amount_cents: i64,
    pub converted_cents: i64,
    pub status: String,
    pub created_at: DateTime<Utc>,
}

pub struct MultiCurrencyLedger {
    entries: Arc<DashMap<Uuid, LedgerEntry>>,
}

impl MultiCurrencyLedger {
    pub fn new() -> Self {
        MultiCurrencyLedger {
            entries: Arc::new(DashMap::new()),
        }
    }

    pub fn add_entry(&self, entry: LedgerEntry) {
        self.entries.insert(entry.id, entry);
    }

    pub fn get_entry(&self, id: Uuid) -> Option<LedgerEntry> {
        self.entries.get(&id).map(|e| e.value().clone())
    }

    pub fn update_entry_status(&self, id: Uuid, status: String) -> Result<(), String> {
        if let Some(mut entry) = self.entries.get_mut(&id) {
            entry.status = status;
            Ok(())
        } else {
            Err(format!("Entry {} not found", id))
        }
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn all_entries(&self) -> Vec<LedgerEntry> {
        self.entries.iter().map(|e| e.value().clone()).collect()
    }
}

impl Clone for MultiCurrencyLedger {
    fn clone(&self) -> Self {
        MultiCurrencyLedger {
            entries: Arc::clone(&self.entries),
        }
    }
}

impl Default for MultiCurrencyLedger {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ledger_add_entry() {
        let ledger = MultiCurrencyLedger::new();
        let entry = LedgerEntry {
            id: Uuid::new_v4(),
            from_currency: "EUR".to_string(),
            to_currency: "USD".to_string(),
            amount_cents: 10000,
            converted_cents: 12000,
            status: "pending".to_string(),
            created_at: Utc::now(),
        };

        ledger.add_entry(entry.clone());
        assert_eq!(ledger.len(), 1);

        let retrieved = ledger.get_entry(entry.id).unwrap();
        assert_eq!(retrieved.amount_cents, 10000);
    }

    #[test]
    fn test_ledger_update_status() {
        let ledger = MultiCurrencyLedger::new();
        let entry_id = Uuid::new_v4();
        let entry = LedgerEntry {
            id: entry_id,
            from_currency: "EUR".to_string(),
            to_currency: "USD".to_string(),
            amount_cents: 10000,
            converted_cents: 12000,
            status: "pending".to_string(),
            created_at: Utc::now(),
        };

        ledger.add_entry(entry);
        ledger
            .update_entry_status(entry_id, "completed".to_string())
            .ok();

        let updated = ledger.get_entry(entry_id).unwrap();
        assert_eq!(updated.status, "completed");
    }

    #[test]
    fn test_stripe_webhook_idempotency() {
        // TODO: Verify duplicate webhook events produce only one ledger entry
    }

    #[test]
    fn test_end_to_end_eur_to_usdc() {
        // TODO: EUR payment -> convert to USDC -> stablecoin bridge -> ledger entry
    }
}
