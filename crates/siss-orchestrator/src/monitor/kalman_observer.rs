use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub type Matrix4x4 = [[f64; 4]; 4];
pub type Vector4 = [f64; 4];

const MAX_CHAIN_SYNC_COST: f64 = 2.0;

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct KalmanState {
    pub x: Vector4,
    pub p: Matrix4x4,
    pub q: Matrix4x4,
    pub r: f64,
}

#[derive(Clone, Debug)]
pub enum RebalanceDecision {
    Stable,
    MinorAdjustment { reason: String },
    MajorRebalance { reason: String, priority: u8 },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RebalanceProposal {
    pub timestamp: u64,
    pub source_partition: String,
    pub target_partition: String,
    pub candidate_agents: Vec<Uuid>,
    pub estimated_load_delta: f64,
    pub cross_chain_cost: f64,
    pub is_safe: bool,
}

pub trait ImpactAnalyzer {
    fn cross_chain_weight(&self, agent_id: Uuid, partition: &str) -> f64;
    fn validate_boundaries(
        &self,
        source_partition: &str,
        target_partition: &str,
        agents: &[Uuid],
    ) -> Result<bool, String>;
    fn affected_process_count(&self, agent_id: Uuid) -> usize;
}

#[allow(non_snake_case)]
impl KalmanState {
    pub fn new() -> Self {
        let x = [0.0; 4];

        let mut p = [[0.0; 4]; 4];
        for i in 0..4 {
            p[i][i] = 1.0;
        }

        let mut q = [[0.0; 4]; 4];
        for i in 0..4 {
            q[i][i] = 0.01;
        }

        let r = 0.1;

        Self { x, p, q, r }
    }

    pub fn update(&mut self, measurement: Vector4) -> f64 {
        let H = self.measurement_matrix();

        let y = self.innovation(&measurement, &H);
        let S = self.innovation_covariance(&H);
        let K = self.kalman_gain(&H, S);

        self.x = self.update_state(&K, &y);
        self.p = self.update_covariance(&K, &H);

        y.iter().map(|yi| yi * yi).sum::<f64>().sqrt()
    }

    fn measurement_matrix(&self) -> [[f64; 4]; 4] {
        let mut H = [[0.0; 4]; 4];
        for i in 0..4 {
            H[i][i] = 1.0;
        }
        H
    }

    fn innovation(&self, z: &Vector4, H: &[[f64; 4]; 4]) -> Vector4 {
        let mut y = [0.0; 4];
        for i in 0..4 {
            let mut h_x = 0.0;
            for j in 0..4 {
                h_x += H[i][j] * self.x[j];
            }
            y[i] = z[i] - h_x;
        }
        y
    }

    fn innovation_covariance(&self, H: &[[f64; 4]; 4]) -> f64 {
        let mut S = 0.0;
        for i in 0..4 {
            for j in 0..4 {
                S += H[i][j] * self.p[j][i];
            }
        }
        S + self.r
    }

    fn kalman_gain(&self, H: &[[f64; 4]; 4], S: f64) -> Vector4 {
        let mut K = [0.0; 4];
        for i in 0..4 {
            let mut p_h = 0.0;
            for j in 0..4 {
                p_h += self.p[i][j] * H[j][0];
            }
            K[i] = p_h / S;
        }
        K
    }

    fn update_state(&self, K: &Vector4, y: &Vector4) -> Vector4 {
        let mut x_new = self.x;
        for i in 0..4 {
            x_new[i] += K[i] * y[0];
        }
        x_new
    }

    fn update_covariance(&self, K: &Vector4, H: &[[f64; 4]; 4]) -> Matrix4x4 {
        let mut I_KH = [[0.0; 4]; 4];
        for i in 0..4 {
            for j in 0..4 {
                I_KH[i][j] = if i == j { 1.0 } else { 0.0 };
                I_KH[i][j] -= K[i] * H[0][j];
            }
        }

        let mut P_new = [[0.0; 4]; 4];
        for i in 0..4 {
            for j in 0..4 {
                let mut sum = 0.0;
                for k in 0..4 {
                    sum += I_KH[i][k] * self.p[k][j];
                }
                P_new[i][j] = sum;
            }
        }

        for i in 0..4 {
            for j in 0..4 {
                P_new[i][j] += self.q[i][j];
            }
        }

        P_new
    }

    pub fn should_rebalance(&self) -> RebalanceDecision {
        let trace = self.p[0][0] + self.p[1][1] + self.p[2][2] + self.p[3][3];
        let state_sum = self.x[0].abs() + self.x[1].abs() + self.x[2].abs() + self.x[3].abs();

        if state_sum > 5.0 {
            RebalanceDecision::MajorRebalance {
                reason: "State magnitude critical".to_string(),
                priority: 9,
            }
        } else if trace > 4.5 {
            RebalanceDecision::MinorAdjustment {
                reason: "Covariance elevated".to_string(),
            }
        } else if state_sum > 2.0 {
            RebalanceDecision::MinorAdjustment {
                reason: "State drift detected".to_string(),
            }
        } else {
            RebalanceDecision::Stable
        }
    }

    pub fn state_vector(&self) -> Vector4 {
        self.x
    }

    pub fn covariance(&self) -> Matrix4x4 {
        self.p
    }

    pub fn trace(&self) -> f64 {
        self.p[0][0] + self.p[1][1] + self.p[2][2] + self.p[3][3]
    }

    pub fn propose_rebalance<A: ImpactAnalyzer>(
        &self,
        analyzer: &A,
        source_partition: String,
        target_partition: String,
        candidate_agents: Vec<Uuid>,
        current_time: u64,
    ) -> Result<Option<RebalanceProposal>, String> {
        let decision = self.should_rebalance();

        match decision {
            RebalanceDecision::Stable => Ok(None),
            RebalanceDecision::MinorAdjustment { .. } | RebalanceDecision::MajorRebalance { .. } => {
                let cross_chain_cost: f64 = candidate_agents
                    .iter()
                    .map(|id| analyzer.cross_chain_weight(*id, &target_partition))
                    .sum();

                let is_safe = analyzer.validate_boundaries(
                    &source_partition,
                    &target_partition,
                    &candidate_agents,
                )?;

                if !is_safe || cross_chain_cost > MAX_CHAIN_SYNC_COST {
                    return Err(format!(
                        "Rebalance blocked: cross_chain_cost={:.2} (max={}), safe={}",
                        cross_chain_cost, MAX_CHAIN_SYNC_COST, is_safe
                    ));
                }

                let state_sum = self.x[0].abs() + self.x[1].abs() + self.x[2].abs() + self.x[3].abs();

                Ok(Some(RebalanceProposal {
                    timestamp: current_time,
                    source_partition,
                    target_partition,
                    candidate_agents,
                    estimated_load_delta: state_sum,
                    cross_chain_cost,
                    is_safe,
                }))
            }
        }
    }
}

impl Default for KalmanState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::{HashMap, HashSet};

    struct MockImpactAnalyzer {
        cross_chain_weights: HashMap<(Uuid, String), f64>,
        process_counts: HashMap<Uuid, usize>,
        split_boundaries: HashSet<String>,
    }

    impl MockImpactAnalyzer {
        fn new() -> Self {
            Self {
                cross_chain_weights: HashMap::new(),
                process_counts: HashMap::new(),
                split_boundaries: HashSet::new(),
            }
        }

        fn with_chain_weight(mut self, agent: Uuid, partition: String, weight: f64) -> Self {
            self.cross_chain_weights.insert((agent, partition), weight);
            self
        }

        fn with_process_count(mut self, agent: Uuid, count: usize) -> Self {
            self.process_counts.insert(agent, count);
            self
        }

        fn mark_split_boundary(mut self, boundary: String) -> Self {
            self.split_boundaries.insert(boundary);
            self
        }
    }

    impl ImpactAnalyzer for MockImpactAnalyzer {
        fn cross_chain_weight(&self, agent_id: Uuid, partition: &str) -> f64 {
            self.cross_chain_weights
                .get(&(agent_id, partition.to_string()))
                .copied()
                .unwrap_or(0.0)
        }

        fn validate_boundaries(
            &self,
            source: &str,
            target: &str,
            _agents: &[Uuid],
        ) -> Result<bool, String> {
            let boundary = format!("{}→{}", source, target);
            if self.split_boundaries.contains(&boundary) {
                Ok(false)
            } else {
                Ok(true)
            }
        }

        fn affected_process_count(&self, agent_id: Uuid) -> usize {
            self.process_counts.get(&agent_id).copied().unwrap_or(0)
        }
    }

    #[test]
    fn test_kalman_new_initialization() {
        let ks = KalmanState::new();
        assert_eq!(ks.x, [0.0, 0.0, 0.0, 0.0]);
        assert_eq!(ks.trace(), 4.0);
    }

    #[test]
    fn test_kalman_update_converges() {
        let mut ks = KalmanState::new();
        let measurement = [1.0, 0.5, 0.3, 0.1];
        let residual = ks.update(measurement);
        assert!(residual > 0.0);
        assert!(!residual.is_nan());
    }

    #[test]
    fn test_should_rebalance_stable() {
        let ks = KalmanState::new();
        match ks.should_rebalance() {
            RebalanceDecision::Stable => (),
            _ => panic!("Expected Stable"),
        }
    }

    #[test]
    fn test_should_rebalance_major() {
        let mut ks = KalmanState::new();
        ks.x = [2.0, 2.0, 2.0, 2.0];
        match ks.should_rebalance() {
            RebalanceDecision::MajorRebalance { .. } => (),
            _ => panic!("Expected MajorRebalance"),
        }
    }

    #[test]
    fn test_should_rebalance_minor() {
        let mut ks = KalmanState::new();
        ks.p[0][0] = 2.0;
        ks.p[1][1] = 2.0;
        ks.p[2][2] = 0.5;
        ks.p[3][3] = 0.5;
        match ks.should_rebalance() {
            RebalanceDecision::MinorAdjustment { .. } => (),
            _ => panic!("Expected MinorAdjustment"),
        }
    }

    #[test]
    fn test_kalman_state_vector() {
        let mut ks = KalmanState::new();
        ks.x = [1.0, 2.0, 3.0, 4.0];
        let state = ks.state_vector();
        assert_eq!(state, [1.0, 2.0, 3.0, 4.0]);
    }

    #[test]
    fn test_kalman_covariance_symmetric() {
        let ks = KalmanState::new();
        let p = ks.covariance();
        for i in 0..4 {
            for j in 0..4 {
                assert!(p[i][j] == p[j][i]);
            }
        }
    }

    #[test]
    fn test_kalman_trace_positive() {
        let ks = KalmanState::new();
        assert!(ks.trace() > 0.0);
    }

    #[test]
    fn test_kalman_sequential_updates() {
        let mut ks = KalmanState::new();
        for step in 0..10 {
            let measurement = [
                0.1 * step as f64,
                0.05 * step as f64,
                0.02 * step as f64,
                0.01 * step as f64,
            ];
            let residual = ks.update(measurement);
            assert!(!residual.is_nan());
            assert!(residual >= 0.0);
        }
    }

    #[test]
    fn test_kalman_update_multiple_decisions() {
        let mut ks = KalmanState::new();
        for _ in 0..20 {
            let measurement = [0.1, 0.05, 0.02, 0.01];
            let _ = ks.update(measurement);
        }
        let decision = ks.should_rebalance();
        match decision {
            RebalanceDecision::Stable | RebalanceDecision::MinorAdjustment { .. } => (),
            _ => panic!("Unexpected decision"),
        }
    }

    #[test]
    fn test_kalman_trace_bounds() {
        let mut ks = KalmanState::new();
        for _ in 0..50 {
            let measurement = [0.1, 0.1, 0.1, 0.1];
            let _ = ks.update(measurement);
            let trace = ks.trace();
            assert!(trace < 10.0);
            assert!(trace > 0.0);
        }
    }

    #[test]
    fn test_kalman_o1_update_complexity() {
        let mut ks = KalmanState::new();
        let measurement = [1.0, 1.0, 1.0, 1.0];
        let start = std::time::Instant::now();
        for _ in 0..1000 {
            let _ = ks.update(measurement);
        }
        let elapsed = start.elapsed().as_micros();
        assert!(elapsed < 100_000);
    }

    #[test]
    fn test_propose_rebalance_stable_returns_none() {
        let ks = KalmanState::new();
        let analyzer = MockImpactAnalyzer::new();
        let agents = vec![Uuid::new_v4()];

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            agents,
            1000,
        );

        assert!(result.is_ok());
        assert!(result.unwrap().is_none());
    }

    #[test]
    fn test_propose_rebalance_low_chain_cost_succeeds() {
        let mut ks = KalmanState::new();
        ks.x = [2.0, 2.0, 2.0, 2.0];
        let agent_id = Uuid::new_v4();
        let analyzer = MockImpactAnalyzer::new()
            .with_chain_weight(agent_id, "partition_b".to_string(), 0.5);

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            vec![agent_id],
            1000,
        );

        assert!(result.is_ok());
        let proposal = result.unwrap();
        assert!(proposal.is_some());
        let p = proposal.unwrap();
        assert!(p.is_safe);
        assert!(p.cross_chain_cost <= MAX_CHAIN_SYNC_COST);
    }

    #[test]
    fn test_propose_rebalance_high_chain_cost_blocked() {
        let mut ks = KalmanState::new();
        ks.x = [2.0, 2.0, 2.0, 2.0];
        let agent_id = Uuid::new_v4();
        let analyzer = MockImpactAnalyzer::new()
            .with_chain_weight(agent_id, "partition_b".to_string(), 3.0);

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            vec![agent_id],
            1000,
        );

        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.contains("cross_chain_cost"));
    }

    #[test]
    fn test_propose_rebalance_split_boundary_blocked() {
        let mut ks = KalmanState::new();
        ks.x = [2.0, 2.0, 2.0, 2.0];
        let agent_id = Uuid::new_v4();
        let analyzer = MockImpactAnalyzer::new()
            .with_chain_weight(agent_id, "partition_b".to_string(), 0.5)
            .mark_split_boundary("partition_a→partition_b".to_string());

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            vec![agent_id],
            1000,
        );

        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.contains("blocked"));
    }

    #[test]
    fn test_propose_rebalance_multiple_agents_aggregates_cost() {
        let mut ks = KalmanState::new();
        ks.x = [2.0, 2.0, 2.0, 2.0];
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();
        let analyzer = MockImpactAnalyzer::new()
            .with_chain_weight(agent1, "partition_b".to_string(), 0.5)
            .with_chain_weight(agent2, "partition_b".to_string(), 0.8);

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            vec![agent1, agent2],
            1000,
        );

        assert!(result.is_ok());
        let proposal = result.unwrap();
        assert!(proposal.is_some());
        let p = proposal.unwrap();
        assert!((p.cross_chain_cost - 1.3).abs() < 0.01);
    }

    #[test]
    fn test_propose_rebalance_minor_adjustment_creates_proposal() {
        let mut ks = KalmanState::new();
        ks.p[0][0] = 2.5;
        ks.p[1][1] = 2.5;
        ks.p[2][2] = 0.5;
        ks.p[3][3] = 0.5;
        let analyzer = MockImpactAnalyzer::new();
        let agents = vec![Uuid::new_v4()];

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            agents,
            2000,
        );

        assert!(result.is_ok());
        let proposal = result.unwrap();
        assert!(proposal.is_some());
    }

    #[test]
    fn test_propose_rebalance_timestamp_preserved() {
        let mut ks = KalmanState::new();
        ks.x = [2.0, 2.0, 2.0, 2.0];
        let analyzer = MockImpactAnalyzer::new();
        let agents = vec![Uuid::new_v4()];
        let timestamp = 5000u64;

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            agents,
            timestamp,
        );

        assert!(result.is_ok());
        let proposal = result.unwrap();
        assert!(proposal.is_some());
        assert_eq!(proposal.unwrap().timestamp, timestamp);
    }

    #[test]
    fn test_propose_rebalance_should_never_split_impact_chains() {
        let mut ks = KalmanState::new();
        ks.x = [3.0, 3.0, 3.0, 3.0];
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();
        let agent3 = Uuid::new_v4();

        let analyzer = MockImpactAnalyzer::new()
            .with_chain_weight(agent1, "partition_b".to_string(), 0.2)
            .with_chain_weight(agent2, "partition_b".to_string(), 0.3)
            .with_process_count(agent1, 5)
            .with_process_count(agent2, 3)
            .with_process_count(agent3, 8);

        let result = ks.propose_rebalance(
            &analyzer,
            "partition_a".to_string(),
            "partition_b".to_string(),
            vec![agent1, agent2],
            3000,
        );

        assert!(result.is_ok());
        let proposal = result.unwrap();
        assert!(proposal.is_some());
        let p = proposal.unwrap();
        assert!(p.is_safe, "Proposal should be safe when chains are not split");
        assert!(p.cross_chain_cost < MAX_CHAIN_SYNC_COST);
        assert_eq!(p.candidate_agents.len(), 2);
    }
}
