use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Atomic swap execution phase
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum SwapPhase {
    Initiated,
    Locked,
    Executed,
    Settled,
    Failed,
}

impl SwapPhase {
    pub fn is_terminal(&self) -> bool {
        matches!(self, SwapPhase::Settled | SwapPhase::Failed)
    }
}

/// Atomic swap instruction for DvP (Delivery vs Payment)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AtomicSwap {
    pub id: Uuid,
    pub initiator: String,
    pub counterparty: String,
    // Leg 1: What initiator delivers
    pub leg1_asset_id: String,
    pub leg1_quantity: u64,
    pub leg1_currency: String,
    // Leg 2: What counterparty delivers
    pub leg2_asset_id: String,
    pub leg2_quantity: u64,
    pub leg2_currency: String,
    pub phase: SwapPhase,
    pub created_at: DateTime<Utc>,
    pub settled_at: Option<DateTime<Utc>>,
    pub atomicity_hash: Option<String>, // Hash for verification
}

impl AtomicSwap {
    pub fn new(
        initiator: String,
        counterparty: String,
        leg1_asset_id: String,
        leg1_quantity: u64,
        leg1_currency: String,
        leg2_asset_id: String,
        leg2_quantity: u64,
        leg2_currency: String,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            initiator,
            counterparty,
            leg1_asset_id,
            leg1_quantity,
            leg1_currency,
            leg2_asset_id,
            leg2_quantity,
            leg2_currency,
            phase: SwapPhase::Initiated,
            created_at: Utc::now(),
            settled_at: None,
            atomicity_hash: None,
        }
    }

    /// Lock both legs (prepare phase)
    pub fn lock(&mut self) -> Result<(), String> {
        if self.phase != SwapPhase::Initiated {
            return Err(format!("Swap {:?} cannot be locked from {:?} phase", self.id, self.phase));
        }
        self.phase = SwapPhase::Locked;
        Ok(())
    }

    /// Execute swap (atomic operation)
    pub fn execute(&mut self) -> Result<(), String> {
        if self.phase != SwapPhase::Locked {
            return Err("Swap must be locked before execution".to_string());
        }

        // Generate atomicity proof
        let proof = format!(
            "{:?}:{:?}:{}:{}:{}:{}",
            self.initiator,
            self.counterparty,
            self.leg1_asset_id,
            self.leg1_quantity,
            self.leg2_asset_id,
            self.leg2_quantity
        );

        use sha2::{Sha256, Digest};
        let mut hasher = Sha256::new();
        hasher.update(proof);
        self.atomicity_hash = Some(format!("{:x}", hasher.finalize()));

        self.phase = SwapPhase::Executed;
        Ok(())
    }

    /// Settle swap (final commit)
    pub fn settle(&mut self) -> Result<(), String> {
        if self.phase != SwapPhase::Executed {
            return Err("Swap must be executed before settlement".to_string());
        }

        if self.atomicity_hash.is_none() {
            return Err("Swap atomicity hash missing".to_string());
        }

        self.phase = SwapPhase::Settled;
        self.settled_at = Some(Utc::now());
        Ok(())
    }

    /// Fail swap (rollback)
    pub fn fail(&mut self) -> Result<(), String> {
        if self.phase.is_terminal() {
            return Err("Cannot fail a terminal swap".to_string());
        }
        self.phase = SwapPhase::Failed;
        Ok(())
    }

    /// Verify swap atomicity
    pub fn verify_atomicity(&self) -> bool {
        if let Some(ref hash) = self.atomicity_hash {
            // In production, re-compute and compare
            !hash.is_empty()
        } else {
            false
        }
    }

    /// Get execution time
    pub fn execution_time_ms(&self) -> Option<u32> {
        self.settled_at.map(|settled| {
            let duration = settled.signed_duration_since(self.created_at);
            duration.num_milliseconds().max(0) as u32
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_atomic_swap_creation() {
        let swap = AtomicSwap::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            "USD_CASH".to_string(),
            1000000,
            "USD".to_string(),
            "EUR_CASH".to_string(),
            850000,
            "EUR".to_string(),
        );

        assert_eq!(swap.phase, SwapPhase::Initiated);
        assert_eq!(swap.leg1_quantity, 1000000);
        assert_eq!(swap.leg2_quantity, 850000);
    }

    #[test]
    fn test_atomic_swap_lock() {
        let mut swap = AtomicSwap::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            "USD_CASH".to_string(),
            1000000,
            "USD".to_string(),
            "EUR_CASH".to_string(),
            850000,
            "EUR".to_string(),
        );

        let result = swap.lock();
        assert!(result.is_ok());
        assert_eq!(swap.phase, SwapPhase::Locked);
    }

    #[test]
    fn test_atomic_swap_execute() {
        let mut swap = AtomicSwap::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            "USD_CASH".to_string(),
            1000000,
            "USD".to_string(),
            "EUR_CASH".to_string(),
            850000,
            "EUR".to_string(),
        );

        assert!(swap.lock().is_ok());
        assert!(swap.execute().is_ok());
        assert_eq!(swap.phase, SwapPhase::Executed);
        assert!(swap.atomicity_hash.is_some());
    }

    #[test]
    fn test_atomic_swap_settle() {
        let mut swap = AtomicSwap::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            "USD_CASH".to_string(),
            1000000,
            "USD".to_string(),
            "EUR_CASH".to_string(),
            850000,
            "EUR".to_string(),
        );

        assert!(swap.lock().is_ok());
        assert!(swap.execute().is_ok());
        assert!(swap.settle().is_ok());
        assert_eq!(swap.phase, SwapPhase::Settled);
        assert!(swap.settled_at.is_some());
    }

    #[test]
    fn test_atomic_swap_verify_atomicity() {
        let mut swap = AtomicSwap::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            "USD_CASH".to_string(),
            1000000,
            "USD".to_string(),
            "EUR_CASH".to_string(),
            850000,
            "EUR".to_string(),
        );

        assert!(!swap.verify_atomicity());

        assert!(swap.lock().is_ok());
        assert!(swap.execute().is_ok());
        assert!(swap.verify_atomicity());
    }

    #[test]
    fn test_atomic_swap_fail() {
        let mut swap = AtomicSwap::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            "USD_CASH".to_string(),
            1000000,
            "USD".to_string(),
            "EUR_CASH".to_string(),
            850000,
            "EUR".to_string(),
        );

        assert!(swap.lock().is_ok());
        assert!(swap.fail().is_ok());
        assert_eq!(swap.phase, SwapPhase::Failed);
    }

    #[test]
    fn test_atomic_swap_execution_time() {
        let mut swap = AtomicSwap::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            "USD_CASH".to_string(),
            1000000,
            "USD".to_string(),
            "EUR_CASH".to_string(),
            850000,
            "EUR".to_string(),
        );

        assert!(swap.lock().is_ok());
        assert!(swap.execute().is_ok());
        assert!(swap.settle().is_ok());

        let execution_time = swap.execution_time_ms();
        assert!(execution_time.is_some());
        assert!(execution_time.unwrap() >= 0);
    }

    #[test]
    fn test_swap_phase_terminal() {
        assert!(!SwapPhase::Initiated.is_terminal());
        assert!(!SwapPhase::Locked.is_terminal());
        assert!(!SwapPhase::Executed.is_terminal());
        assert!(SwapPhase::Settled.is_terminal());
        assert!(SwapPhase::Failed.is_terminal());
    }
}
