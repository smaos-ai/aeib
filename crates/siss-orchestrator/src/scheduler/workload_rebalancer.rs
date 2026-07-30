use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct AgentLoad {
    pub agent_id: Uuid,
    pub task_count: u32,
    pub latency_ms: u32,
    pub cpu_percent: u8,
}

#[derive(Clone, Debug)]
pub enum RebalanceAction {
    MoveTask {
        task_id: Uuid,
        from_agent: Uuid,
        to_agent: Uuid,
    },
    SpawnAgent {
        target_load: u32,
    },
    TerminateAgent {
        agent_id: Uuid,
    },
    NoOp,
}

#[derive(Clone, Debug)]
pub struct RebalancePlan {
    pub actions: Vec<RebalanceAction>,
    pub total_tasks_moved: u32,
    pub balance_score: f64,
    pub divide_depth: usize,
}

pub struct WorkloadRebalancer {
    agents: HashMap<Uuid, AgentLoad>,
    total_tasks: u32,
    min_load_threshold: u32,
    max_load_threshold: u32,
}

impl WorkloadRebalancer {
    pub fn new(expected_agent_count: usize) -> Self {
        let min_threshold = 5;
        let max_threshold = 50;

        Self {
            agents: HashMap::with_capacity(expected_agent_count),
            total_tasks: 0,
            min_load_threshold: min_threshold,
            max_load_threshold: max_threshold,
        }
    }

    pub fn register_agent(&mut self, agent_id: Uuid, load: AgentLoad) {
        self.agents.insert(agent_id, load);
        self.total_tasks += load.task_count;
    }

    pub fn update_load(&mut self, agent_id: Uuid, load: AgentLoad) {
        if let Some(old_load) = self.agents.get(&agent_id) {
            self.total_tasks -= old_load.task_count;
        }
        self.total_tasks += load.task_count;
        self.agents.insert(agent_id, load);
    }

    pub fn calculate_rebalance_plan(&self) -> RebalancePlan {
        if self.agents.is_empty() {
            return RebalancePlan {
                actions: vec![],
                total_tasks_moved: 0,
                balance_score: 1.0,
                divide_depth: 0,
            };
        }

        let mut actions = Vec::new();
        let mut divide_depth = 0;
        let agent_ids: Vec<Uuid> = self.agents.keys().copied().collect();

        self.rebalance_recursive(&agent_ids, &mut actions, &mut divide_depth);

        let balance_score = self.calculate_balance_score(&self.agents);
        let total_tasks_moved = actions
            .iter()
            .filter(|a| matches!(a, RebalanceAction::MoveTask { .. }))
            .count() as u32;

        RebalancePlan {
            actions,
            total_tasks_moved,
            balance_score,
            divide_depth,
        }
    }

    fn rebalance_recursive(
        &self,
        agents: &[Uuid],
        actions: &mut Vec<RebalanceAction>,
        depth: &mut usize,
    ) {
        if agents.is_empty() {
            return;
        }

        if agents.len() == 1 {
            return;
        }

        *depth += 1;

        let mid = agents.len() / 2;
        let (left_agents, right_agents) = agents.split_at(mid);

        let left_load: u32 = left_agents
            .iter()
            .map(|id| self.agents.get(id).map(|l| l.task_count).unwrap_or(0))
            .sum();

        let right_load: u32 = right_agents
            .iter()
            .map(|id| self.agents.get(id).map(|l| l.task_count).unwrap_or(0))
            .sum();

        if left_load > right_load + 10 {
            if let Some(overloaded) = left_agents
                .iter()
                .max_by_key(|id| self.agents.get(id).map(|l| l.task_count).unwrap_or(0))
            {
                if let Some(underutilized) = right_agents
                    .iter()
                    .min_by_key(|id| self.agents.get(id).map(|l| l.task_count).unwrap_or(0))
                {
                    actions.push(RebalanceAction::MoveTask {
                        task_id: Uuid::new_v4(),
                        from_agent: *overloaded,
                        to_agent: *underutilized,
                    });
                }
            }
        } else if right_load > left_load + 10 {
            if let Some(overloaded) = right_agents
                .iter()
                .max_by_key(|id| self.agents.get(id).map(|l| l.task_count).unwrap_or(0))
            {
                if let Some(underutilized) = left_agents
                    .iter()
                    .min_by_key(|id| self.agents.get(id).map(|l| l.task_count).unwrap_or(0))
                {
                    actions.push(RebalanceAction::MoveTask {
                        task_id: Uuid::new_v4(),
                        from_agent: *overloaded,
                        to_agent: *underutilized,
                    });
                }
            }
        }

        self.rebalance_recursive(left_agents, actions, depth);
        self.rebalance_recursive(right_agents, actions, depth);
    }

    fn calculate_balance_score(&self, loads: &HashMap<Uuid, AgentLoad>) -> f64 {
        if loads.is_empty() {
            return 1.0;
        }

        let task_counts: Vec<u32> = loads.values().map(|l| l.task_count).collect();
        if task_counts.is_empty() {
            return 1.0;
        }

        let mean = task_counts.iter().sum::<u32>() as f64 / task_counts.len() as f64;
        let variance = task_counts
            .iter()
            .map(|&x| {
                let diff = x as f64 - mean;
                diff * diff
            })
            .sum::<f64>()
            / task_counts.len() as f64;

        let std_dev = variance.sqrt();
        let cv = if mean > 0.0 { std_dev / mean } else { 0.0 };

        (1.0 / (1.0 + cv)).min(1.0)
    }

    pub fn check_spawn_needed(&self) -> bool {
        if self.agents.is_empty() {
            return false;
        }

        let avg_load = self.total_tasks as f64 / self.agents.len() as f64;
        avg_load > self.max_load_threshold as f64
    }

    pub fn check_terminate_needed(&self) -> Option<Uuid> {
        self.agents
            .iter()
            .find(|(_, load)| load.task_count < self.min_load_threshold)
            .map(|(id, _)| *id)
    }

    pub fn agent_count(&self) -> usize {
        self.agents.len()
    }

    pub fn total_task_count(&self) -> u32 {
        self.total_tasks
    }

    pub fn average_load(&self) -> f64 {
        if self.agents.is_empty() {
            return 0.0;
        }
        self.total_tasks as f64 / self.agents.len() as f64
    }
}

impl Default for WorkloadRebalancer {
    fn default() -> Self {
        Self::new(50)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rebalancer_creation() {
        let rebalancer = WorkloadRebalancer::new(50);
        assert_eq!(rebalancer.agent_count(), 0);
        assert_eq!(rebalancer.total_task_count(), 0);
    }

    #[test]
    fn test_register_agent() {
        let mut rebalancer = WorkloadRebalancer::new(50);
        let agent_id = Uuid::new_v4();
        let load = AgentLoad {
            agent_id,
            task_count: 10,
            latency_ms: 50,
            cpu_percent: 30,
        };
        rebalancer.register_agent(agent_id, load);
        assert_eq!(rebalancer.agent_count(), 1);
        assert_eq!(rebalancer.total_task_count(), 10);
    }

    #[test]
    fn test_update_load() {
        let mut rebalancer = WorkloadRebalancer::new(50);
        let agent_id = Uuid::new_v4();
        let load1 = AgentLoad {
            agent_id,
            task_count: 10,
            latency_ms: 50,
            cpu_percent: 30,
        };
        rebalancer.register_agent(agent_id, load1);
        assert_eq!(rebalancer.total_task_count(), 10);

        let load2 = AgentLoad {
            agent_id,
            task_count: 20,
            latency_ms: 60,
            cpu_percent: 40,
        };
        rebalancer.update_load(agent_id, load2);
        assert_eq!(rebalancer.total_task_count(), 20);
    }

    #[test]
    fn test_balanced_load_no_rebalance() {
        let mut rebalancer = WorkloadRebalancer::new(3);
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();
        let agent3 = Uuid::new_v4();

        rebalancer.register_agent(
            agent1,
            AgentLoad {
                agent_id: agent1,
                task_count: 10,
                latency_ms: 50,
                cpu_percent: 30,
            },
        );
        rebalancer.register_agent(
            agent2,
            AgentLoad {
                agent_id: agent2,
                task_count: 10,
                latency_ms: 50,
                cpu_percent: 30,
            },
        );
        rebalancer.register_agent(
            agent3,
            AgentLoad {
                agent_id: agent3,
                task_count: 10,
                latency_ms: 50,
                cpu_percent: 30,
            },
        );

        let plan = rebalancer.calculate_rebalance_plan();
        assert_eq!(plan.total_tasks_moved, 0);
        assert!(plan.balance_score >= 0.9);
    }

    #[test]
    fn test_imbalanced_load_triggers_rebalance() {
        let mut rebalancer = WorkloadRebalancer::new(3);
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();
        let agent3 = Uuid::new_v4();

        rebalancer.register_agent(
            agent1,
            AgentLoad {
                agent_id: agent1,
                task_count: 50,
                latency_ms: 100,
                cpu_percent: 80,
            },
        );
        rebalancer.register_agent(
            agent2,
            AgentLoad {
                agent_id: agent2,
                task_count: 5,
                latency_ms: 20,
                cpu_percent: 10,
            },
        );
        rebalancer.register_agent(
            agent3,
            AgentLoad {
                agent_id: agent3,
                task_count: 5,
                latency_ms: 20,
                cpu_percent: 10,
            },
        );

        let plan = rebalancer.calculate_rebalance_plan();
        assert!(plan.total_tasks_moved > 0);
    }

    #[test]
    fn test_divide_depth_logarithmic() {
        let mut rebalancer = WorkloadRebalancer::new(16);
        for i in 0..16 {
            let agent_id = Uuid::new_v4();
            rebalancer.register_agent(
                agent_id,
                AgentLoad {
                    agent_id,
                    task_count: 50 + i as u32,
                    latency_ms: 50,
                    cpu_percent: 50,
                },
            );
        }

        let plan = rebalancer.calculate_rebalance_plan();
        assert!(plan.divide_depth <= 16);
    }

    #[test]
    fn test_spawn_needed() {
        let mut rebalancer = WorkloadRebalancer::new(2);
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();

        rebalancer.register_agent(
            agent1,
            AgentLoad {
                agent_id: agent1,
                task_count: 60,
                latency_ms: 100,
                cpu_percent: 90,
            },
        );
        rebalancer.register_agent(
            agent2,
            AgentLoad {
                agent_id: agent2,
                task_count: 60,
                latency_ms: 100,
                cpu_percent: 90,
            },
        );

        assert!(rebalancer.check_spawn_needed());
    }

    #[test]
    fn test_terminate_needed() {
        let mut rebalancer = WorkloadRebalancer::new(3);
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();
        let agent3 = Uuid::new_v4();

        rebalancer.register_agent(
            agent1,
            AgentLoad {
                agent_id: agent1,
                task_count: 50,
                latency_ms: 50,
                cpu_percent: 50,
            },
        );
        rebalancer.register_agent(
            agent2,
            AgentLoad {
                agent_id: agent2,
                task_count: 50,
                latency_ms: 50,
                cpu_percent: 50,
            },
        );
        rebalancer.register_agent(
            agent3,
            AgentLoad {
                agent_id: agent3,
                task_count: 2,
                latency_ms: 20,
                cpu_percent: 5,
            },
        );

        assert!(rebalancer.check_terminate_needed().is_some());
        assert_eq!(rebalancer.check_terminate_needed(), Some(agent3));
    }

    #[test]
    fn test_average_load() {
        let mut rebalancer = WorkloadRebalancer::new(4);
        for i in 0..4 {
            let agent_id = Uuid::new_v4();
            rebalancer.register_agent(
                agent_id,
                AgentLoad {
                    agent_id,
                    task_count: 10 + i as u32,
                    latency_ms: 50,
                    cpu_percent: 30,
                },
            );
        }

        let avg = rebalancer.average_load();
        assert!((avg - 11.5).abs() < 0.1);
    }

    #[test]
    fn test_balance_score_high_variance() {
        let mut rebalancer = WorkloadRebalancer::new(3);
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();
        let agent3 = Uuid::new_v4();

        rebalancer.register_agent(
            agent1,
            AgentLoad {
                agent_id: agent1,
                task_count: 100,
                latency_ms: 100,
                cpu_percent: 80,
            },
        );
        rebalancer.register_agent(
            agent2,
            AgentLoad {
                agent_id: agent2,
                task_count: 1,
                latency_ms: 10,
                cpu_percent: 5,
            },
        );
        rebalancer.register_agent(
            agent3,
            AgentLoad {
                agent_id: agent3,
                task_count: 1,
                latency_ms: 10,
                cpu_percent: 5,
            },
        );

        let plan = rebalancer.calculate_rebalance_plan();
        assert!(plan.balance_score < 0.8);
    }

    #[test]
    fn test_empty_rebalancer() {
        let rebalancer = WorkloadRebalancer::new(50);
        let plan = rebalancer.calculate_rebalance_plan();
        assert_eq!(plan.actions.len(), 0);
        assert_eq!(plan.balance_score, 1.0);
    }
}
