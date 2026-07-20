use uuid::Uuid;
use serde::{Deserialize, Serialize};

/// AP2 Settlement Record: cryptographically binding creator earnings to governance proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AP2SettlementRecord {
    pub settlement_id: Uuid,
    pub capsule_id: Uuid,              // Links to compliance capsule

    /// Creator information
    pub creator_address: String,       // Smart contract address or wallet
    pub creator_id: Uuid,

    /// Financial details
    pub inference_cost_usd: f64,       // Total cost (e.g., $0.001)
    pub creator_fee_usd: f64,          // 1% (e.g., $0.00001)
    pub platform_fee_usd: f64,         // 99% (e.g., $0.00099)

    /// Proof of compliance
    pub merkle_proof_hash: String,     // Links to EXEC_LOG
    pub governance_proof: bool,        // Was governance enforced?

    /// Settlement status
    pub status: SettlementStatus,
    pub timestamp: u64,                // When settled
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SettlementStatus {
    Pending,     // Waiting for governance proof
    Approved,    // Governance proved, ready to pay out
    Settled,     // Payment executed
    Failed,      // Governance violation, no payout
}

/// Payout simulation for creator economics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreatorPayoutSimulation {
    pub creator_id: Uuid,
    pub creator_address: String,

    /// Payout details
    pub daily_inferences: u64,         // e.g., 1M inferences/day
    pub cost_per_inference: f64,       // e.g., $0.003
    pub ap2_fee_percentage: f64,       // 1% = 0.01
    pub success_rate: f64,             // % of inferences that pass governance (0.0-1.0)

    /// Calculated earnings
    pub daily_revenue_usd: f64,        // total cost * daily_inferences
    pub daily_creator_earnings_usd: f64, // 1% * success_rate * daily_revenue
    pub monthly_earnings_usd: f64,     // daily * 30
    pub yearly_earnings_usd: f64,      // daily * 365
}

impl AP2SettlementRecord {
    pub fn new(
        capsule_id: Uuid,
        creator_address: String,
        creator_id: Uuid,
        inference_cost_usd: f64,
        merkle_proof_hash: String,
    ) -> Self {
        let creator_fee = inference_cost_usd * 0.01;    // 1%
        let platform_fee = inference_cost_usd * 0.99;   // 99%

        Self {
            settlement_id: Uuid::new_v4(),
            capsule_id,
            creator_address,
            creator_id,
            inference_cost_usd,
            creator_fee_usd: creator_fee,
            platform_fee_usd: platform_fee,
            merkle_proof_hash,
            governance_proof: false,
            status: SettlementStatus::Pending,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        }
    }

    /// Approve settlement (governance proved)
    pub fn approve_with_governance_proof(&mut self, merkle_proof_hash: String) {
        self.merkle_proof_hash = merkle_proof_hash;
        self.governance_proof = true;
        self.status = SettlementStatus::Approved;
    }

    /// Execute settlement (mark as settled)
    pub fn mark_settled(&mut self) {
        if self.governance_proof {
            self.status = SettlementStatus::Settled;
        }
    }

    /// Fail settlement (governance violation)
    pub fn mark_failed(&mut self) {
        self.status = SettlementStatus::Failed;
        self.governance_proof = false;
    }

    /// Check if settlement is ready for payout
    pub fn is_ready_for_payout(&self) -> bool {
        self.status == SettlementStatus::Approved && self.governance_proof
    }
}

impl CreatorPayoutSimulation {
    pub fn new(
        creator_id: Uuid,
        creator_address: String,
        daily_inferences: u64,
        cost_per_inference: f64,
        success_rate: f64,
    ) -> Self {
        let daily_revenue = daily_inferences as f64 * cost_per_inference;
        let daily_creator_earnings = daily_revenue * 0.01 * success_rate;

        Self {
            creator_id,
            creator_address,
            daily_inferences,
            cost_per_inference,
            ap2_fee_percentage: 0.01, // 1%
            success_rate: success_rate.clamp(0.0, 1.0),
            daily_revenue_usd: daily_revenue,
            daily_creator_earnings_usd: daily_creator_earnings,
            monthly_earnings_usd: daily_creator_earnings * 30.0,
            yearly_earnings_usd: daily_creator_earnings * 365.0,
        }
    }

    /// Get summary of creator earnings
    pub fn summary(&self) -> String {
        format!(
            "Creator {}: {} inferences/day @ ${:.6}/inference\nDaily earnings: ${:.4} | Monthly: ${:.2} | Yearly: ${:.2}",
            self.creator_id, self.daily_inferences, self.cost_per_inference,
            self.daily_creator_earnings_usd, self.monthly_earnings_usd, self.yearly_earnings_usd
        )
    }

    /// Scale simulation for 1M creators
    pub fn scale_to_market(base_simulation: &CreatorPayoutSimulation, creator_count: u64) -> f64 {
        base_simulation.yearly_earnings_usd * creator_count as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ap2_settlement_creation() {
        let capsule_id = Uuid::new_v4();
        let creator_id = Uuid::new_v4();
        let settlement = AP2SettlementRecord::new(
            capsule_id,
            "0xdeadbeef".to_string(),
            creator_id,
            0.001,
            "sha256:proof".to_string(),
        );

        assert_eq!(settlement.capsule_id, capsule_id);
        assert_eq!(settlement.creator_id, creator_id);
        assert_eq!(settlement.inference_cost_usd, 0.001);
        assert_eq!(settlement.creator_fee_usd, 0.00001); // 1% of 0.001
        assert_eq!(settlement.platform_fee_usd, 0.00099); // 99% of 0.001
    }

    #[test]
    fn test_ap2_settlement_approval_flow() {
        let capsule_id = Uuid::new_v4();
        let creator_id = Uuid::new_v4();
        let mut settlement = AP2SettlementRecord::new(
            capsule_id,
            "0xdeadbeef".to_string(),
            creator_id,
            0.001,
            String::new(),
        );

        // Initially pending
        assert_eq!(settlement.status, SettlementStatus::Pending);
        assert!(!settlement.is_ready_for_payout());

        // Approve with governance proof
        settlement.approve_with_governance_proof("sha256:proof".to_string());
        assert_eq!(settlement.status, SettlementStatus::Approved);
        assert!(settlement.is_ready_for_payout());

        // Mark settled
        settlement.mark_settled();
        assert_eq!(settlement.status, SettlementStatus::Settled);
    }

    #[test]
    fn test_ap2_settlement_failure() {
        let capsule_id = Uuid::new_v4();
        let creator_id = Uuid::new_v4();
        let mut settlement = AP2SettlementRecord::new(
            capsule_id,
            "0xdeadbeef".to_string(),
            creator_id,
            0.001,
            String::new(),
        );

        settlement.mark_failed();
        assert_eq!(settlement.status, SettlementStatus::Failed);
        assert!(!settlement.is_ready_for_payout());
    }

    #[test]
    fn test_creator_payout_simulation() {
        let creator_id = Uuid::new_v4();
        let sim = CreatorPayoutSimulation::new(
            creator_id,
            "0xdeadbeef".to_string(),
            1_000_000,           // 1M inferences/day
            0.003,               // $0.003 per inference
            0.95,                // 95% success rate
        );

        // Daily revenue: 1M * $0.003 = $3,000
        assert_eq!(sim.daily_revenue_usd, 3000.0);

        // Creator gets 1% * 95% = 0.95%: $3,000 * 0.0095 = $28.50
        assert!((sim.daily_creator_earnings_usd - 28.5).abs() < 0.01);

        // Monthly: $28.50 * 30 = $855
        assert!((sim.monthly_earnings_usd - 855.0).abs() < 0.01);

        // Yearly: $28.50 * 365 = $10,402.50
        assert!((sim.yearly_earnings_usd - 10402.5).abs() < 0.1);
    }

    #[test]
    fn test_creator_payout_market_scale() {
        let creator_id = Uuid::new_v4();
        let base_sim = CreatorPayoutSimulation::new(
            creator_id,
            "0xdeadbeef".to_string(),
            1_000_000,
            0.003,
            0.95,
        );

        // Scale to 1K creators
        let market_arr = CreatorPayoutSimulation::scale_to_market(&base_sim, 1_000);
        assert!((market_arr - 10_402_500.0).abs() < 100.0); // ~$10.4M ARR from 1K creators
    }

    #[test]
    fn test_creator_payout_summary() {
        let creator_id = Uuid::new_v4();
        let sim = CreatorPayoutSimulation::new(
            creator_id,
            "0xdeadbeef".to_string(),
            1_000_000,
            0.003,
            0.95,
        );

        let summary = sim.summary();
        assert!(summary.contains("1000000 inferences/day"));
        assert!(summary.contains("Daily earnings:"));
    }
}
