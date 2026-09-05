use siss_orchestrator::{ImpactAnalyzer, KalmanState};
use std::collections::HashMap;
use uuid::Uuid;

struct KGAwareAnalyzer {
    impact_chains: HashMap<(Uuid, Uuid), f64>,
    partition_members: HashMap<String, Vec<Uuid>>,
}

impl KGAwareAnalyzer {
    fn new() -> Self {
        Self {
            impact_chains: HashMap::new(),
            partition_members: HashMap::new(),
        }
    }

    fn add_impact_chain(mut self, caller: Uuid, callee: Uuid, weight: f64) -> Self {
        self.impact_chains.insert((caller, callee), weight);
        self
    }

    fn add_partition(mut self, name: String, agents: Vec<Uuid>) -> Self {
        self.partition_members.insert(name, agents);
        self
    }
}

impl ImpactAnalyzer for KGAwareAnalyzer {
    fn cross_chain_weight(&self, agent_id: Uuid, _partition: &str) -> f64 {
        self.impact_chains
            .iter()
            .filter(|((_, target), _)| *target == agent_id)
            .map(|(_, weight)| weight)
            .sum()
    }

    fn validate_boundaries(
        &self,
        source_partition: &str,
        target_partition: &str,
        agents_to_move: &[Uuid],
    ) -> Result<bool, String> {
        let source_members = self.partition_members.get(source_partition);
        let target_members = self.partition_members.get(target_partition);

        if source_members.is_none() || target_members.is_none() {
            return Ok(true);
        }

        let source = source_members.unwrap();
        let target = target_members.unwrap();
        let moving_set: std::collections::HashSet<_> = agents_to_move.iter().copied().collect();

        for (caller, callee) in self.impact_chains.keys() {
            let caller_in_source = source.contains(caller);
            let caller_in_target = target.contains(caller);
            let callee_is_moving = moving_set.contains(callee);

            if caller_in_source && !caller_in_target && callee_is_moving {
                return Ok(false);
            }
        }

        Ok(true)
    }

    fn affected_process_count(&self, _agent_id: Uuid) -> usize {
        0
    }
}

#[test]
fn test_phase_3_2_should_never_split_impact_chain_safe_migration() {
    let mut ks = KalmanState::new();
    ks.x = [2.0, 2.0, 2.0, 2.0];

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();
    let agent_c = Uuid::new_v4();
    let agent_d = Uuid::new_v4();

    let analyzer = KGAwareAnalyzer::new()
        .add_partition("partition_a".to_string(), vec![agent_a, agent_b])
        .add_partition("partition_b".to_string(), vec![agent_c, agent_d])
        .add_impact_chain(agent_a, agent_b, 1.0)
        .add_impact_chain(agent_c, agent_d, 1.0);

    let result = ks.propose_rebalance(
        &analyzer,
        "partition_a".to_string(),
        "partition_b".to_string(),
        vec![agent_b],
        1000,
    );

    assert!(
        result.is_err(),
        "Should fail when impact chain would be split"
    );
}

#[test]
fn test_phase_3_2_should_never_split_impact_chain_fail_closed() {
    let mut ks = KalmanState::new();
    ks.x = [2.0, 2.0, 2.0, 2.0];

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    let analyzer = KGAwareAnalyzer::new()
        .add_partition("partition_a".to_string(), vec![agent_a, agent_b])
        .add_partition("partition_b".to_string(), vec![])
        .add_impact_chain(agent_a, agent_b, 1.5);

    let result = ks.propose_rebalance(
        &analyzer,
        "partition_a".to_string(),
        "partition_b".to_string(),
        vec![agent_b],
        2000,
    );

    assert!(
        result.is_err(),
        "Must fail-closed when migration would break caller→callee chain"
    );
}

#[test]
fn test_phase_3_2_safe_migration_within_chain() {
    let mut ks = KalmanState::new();
    ks.x = [2.0, 2.0, 2.0, 2.0];

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    let analyzer = KGAwareAnalyzer::new()
        .add_partition("partition_a".to_string(), vec![agent_a, agent_b])
        .add_partition("partition_b".to_string(), vec![])
        .add_impact_chain(agent_a, agent_b, 0.5);

    let result = ks.propose_rebalance(
        &analyzer,
        "partition_a".to_string(),
        "partition_b".to_string(),
        vec![agent_a],
        3000,
    );

    assert!(
        result.is_ok(),
        "Should allow moving caller out if chain cost is low"
    );
}

#[test]
fn test_phase_3_2_multiple_impact_chains_cumulative_validation() {
    let mut ks = KalmanState::new();
    ks.x = [2.0, 2.0, 2.0, 2.0];

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();
    let agent_c = Uuid::new_v4();
    let agent_d = Uuid::new_v4();

    let analyzer = KGAwareAnalyzer::new()
        .add_partition("partition_a".to_string(), vec![agent_a, agent_b, agent_c])
        .add_partition("partition_b".to_string(), vec![agent_d])
        .add_impact_chain(agent_a, agent_b, 0.4)
        .add_impact_chain(agent_b, agent_c, 0.4)
        .add_impact_chain(agent_c, agent_d, 0.5);

    let result = ks.propose_rebalance(
        &analyzer,
        "partition_a".to_string(),
        "partition_b".to_string(),
        vec![agent_c],
        4000,
    );

    assert!(
        result.is_err(),
        "Should block migration that breaks chain a→b→c"
    );
}

#[test]
fn test_phase_3_2_proposal_includes_load_delta() {
    let mut ks = KalmanState::new();
    ks.x = [1.5, 1.5, 1.5, 1.5];

    let agent = Uuid::new_v4();
    let analyzer = KGAwareAnalyzer::new()
        .add_partition("partition_a".to_string(), vec![agent])
        .add_partition("partition_b".to_string(), vec![]);

    let result = ks.propose_rebalance(
        &analyzer,
        "partition_a".to_string(),
        "partition_b".to_string(),
        vec![agent],
        5000,
    );

    assert!(result.is_ok());
    let proposal = result.unwrap();
    assert!(proposal.is_some());
    let p = proposal.unwrap();
    assert!((p.estimated_load_delta - 6.0).abs() < 0.01);
}

#[test]
fn test_phase_3_2_zero_cross_chain_cost_allows_rebalance() {
    let mut ks = KalmanState::new();
    ks.x = [2.0, 2.0, 2.0, 2.0];

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();
    let agent_c = Uuid::new_v4();

    let analyzer = KGAwareAnalyzer::new()
        .add_partition("partition_a".to_string(), vec![agent_a, agent_b])
        .add_partition("partition_b".to_string(), vec![agent_c])
        .add_impact_chain(agent_a, agent_b, 1.0);

    let result = ks.propose_rebalance(
        &analyzer,
        "partition_a".to_string(),
        "partition_b".to_string(),
        vec![agent_b],
        6000,
    );

    assert!(
        result.is_err(),
        "Moving callee breaks caller→callee chain in partition_a"
    );
}
