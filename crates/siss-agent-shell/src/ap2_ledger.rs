/// Phase 63: AP2 Burn Ledger — nonce-based one-mandate-one-execution invariant.

use std::collections::HashMap;
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MandateState {
    Active,
    Executed,
}

#[derive(Debug, Clone)]
pub struct LedgerEntry {
    pub nonce: Uuid,
    pub mandate_id: Uuid,
    pub mandate_hash: String,
    pub timestamp: DateTime<Utc>,
    pub state: MandateState,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BurnError {
    NonceAlreadyBurned { nonce: Uuid },
    EntryNotFound { nonce: Uuid },
}

pub struct Ap2BurnLedger {
    entries: HashMap<Uuid, LedgerEntry>,
}

impl Ap2BurnLedger {
    pub fn new() -> Self {
        Ap2BurnLedger {
            entries: HashMap::new(),
        }
    }

    pub fn register(
        &mut self,
        mandate_id: Uuid,
        nonce: Uuid,
        mandate_hash: String,
        timestamp: DateTime<Utc>,
    ) -> Result<(), BurnError> {
        if self.entries.contains_key(&nonce) {
            return Err(BurnError::NonceAlreadyBurned { nonce });
        }

        self.entries.insert(
            nonce,
            LedgerEntry {
                nonce,
                mandate_id,
                mandate_hash,
                timestamp,
                state: MandateState::Active,
            },
        );

        Ok(())
    }

    pub fn burn(&mut self, nonce: Uuid) -> Result<(), BurnError> {
        match self.entries.get_mut(&nonce) {
            None => Err(BurnError::EntryNotFound { nonce }),
            Some(entry) => {
                if entry.state == MandateState::Executed {
                    return Err(BurnError::NonceAlreadyBurned { nonce });
                }
                entry.state = MandateState::Executed;
                Ok(())
            }
        }
    }

    pub fn is_burned(&self, nonce: Uuid) -> bool {
        match self.entries.get(&nonce) {
            Some(entry) => entry.state == MandateState::Executed,
            None => false,
        }
    }

    pub fn compute_mandate_hash(mandate_id: Uuid, cart_id: Uuid, total: i64) -> String {
        format!("{}:{}:{}", mandate_id, cart_id, total)
    }

    pub fn get_entry(&self, nonce: Uuid) -> Option<&LedgerEntry> {
        self.entries.get(&nonce)
    }
}

impl Default for Ap2BurnLedger {
    fn default() -> Self {
        Self::new()
    }
}
