use crate::error::SettlementError;
use crate::settlement::Settlement;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub id: String,
    pub settlement_id: Uuid,
    pub event_type: String, // "initiated", "confirmed", "aborted"
    pub data: serde_json::Value,
    pub digest: String,
    pub timestamp: DateTime<Utc>,
}

impl LedgerEntry {
    pub fn new(
        settlement_id: Uuid,
        event_type: String,
        data: serde_json::Value,
    ) -> Self {
        let timestamp = Utc::now();
        let digest = Self::compute_digest(settlement_id, &event_type, &timestamp);
        let id = format!("ledger_{}_{}", settlement_id, timestamp.timestamp());

        Self {
            id,
            settlement_id,
            event_type,
            data,
            digest,
            timestamp,
        }
    }

    pub fn compute_digest(
        settlement_id: Uuid,
        event_type: &str,
        timestamp: &DateTime<Utc>,
    ) -> String {
        use sha2::{Digest, Sha256};
        let data = format!("{}||{}||{}", settlement_id, event_type, timestamp.timestamp());
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        hex::encode(hasher.finalize())
    }
}

pub struct SettlementLedger {
    entries: HashMap<Uuid, Vec<LedgerEntry>>,
    all_entries: Vec<LedgerEntry>,
}

impl SettlementLedger {
    pub fn new() -> Self {
        Self {
            entries: HashMap::new(),
            all_entries: Vec::new(),
        }
    }

    pub fn record_settlement_initiated(
        &mut self,
        settlement: &Settlement,
    ) -> Result<String, SettlementError> {
        let data = serde_json::json!({
            "id": settlement.id,
            "from": settlement.from_org_did,
            "to": settlement.to_org_did,
            "amount": settlement.amount.to_string(),
            "currency": settlement.currency,
        });

        let entry = LedgerEntry::new(settlement.id, "initiated".to_string(), data);
        let digest = entry.digest.clone();

        self.entries
            .entry(settlement.id)
            .or_insert_with(Vec::new)
            .push(entry.clone());

        self.all_entries.push(entry);
        Ok(digest)
    }

    pub fn record_settlement_confirmed(
        &mut self,
        settlement: &Settlement,
        ledger_hash: &str,
    ) -> Result<String, SettlementError> {
        let data = serde_json::json!({
            "id": settlement.id,
            "status": "confirmed",
            "ledger_hash": ledger_hash,
        });

        let entry = LedgerEntry::new(settlement.id, "confirmed".to_string(), data);
        let digest = entry.digest.clone();

        self.entries
            .entry(settlement.id)
            .or_insert_with(Vec::new)
            .push(entry.clone());

        self.all_entries.push(entry);
        Ok(digest)
    }

    pub fn record_settlement_aborted(
        &mut self,
        settlement: &Settlement,
        reason: &str,
    ) -> Result<String, SettlementError> {
        let data = serde_json::json!({
            "id": settlement.id,
            "status": "aborted",
            "reason": reason,
        });

        let entry = LedgerEntry::new(settlement.id, "aborted".to_string(), data);
        let digest = entry.digest.clone();

        self.entries
            .entry(settlement.id)
            .or_insert_with(Vec::new)
            .push(entry.clone());

        self.all_entries.push(entry);
        Ok(digest)
    }

    pub fn get_settlement_history(
        &self,
        settlement_id: Uuid,
    ) -> Result<Vec<LedgerEntry>, SettlementError> {
        self.entries
            .get(&settlement_id)
            .cloned()
            .ok_or_else(|| SettlementError::NotFound("Settlement history not found".to_string()))
    }

    pub fn verify_ledger_entry(
        &self,
        settlement_id: Uuid,
        digest: &str,
    ) -> Result<bool, SettlementError> {
        match self.get_settlement_history(settlement_id) {
            Ok(history) => Ok(history.iter().any(|e| e.digest == digest)),
            Err(_) => Ok(false),
        }
    }

    pub fn get_all_entries(&self) -> Vec<LedgerEntry> {
        self.all_entries.clone()
    }

    pub fn get_entries_count(&self) -> usize {
        self.all_entries.len()
    }

    pub fn get_settlement_status(&self, settlement_id: Uuid) -> Result<String, SettlementError> {
        let history = self.get_settlement_history(settlement_id)?;
        if let Some(last_entry) = history.last() {
            Ok(last_entry.event_type.clone())
        } else {
            Err(SettlementError::NotFound("No status found".to_string()))
        }
    }
}

impl Default for SettlementLedger {
    fn default() -> Self {
        Self::new()
    }
}
