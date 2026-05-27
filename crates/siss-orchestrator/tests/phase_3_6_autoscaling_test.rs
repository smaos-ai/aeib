use uuid::Uuid;
use std::collections::HashMap;

#[derive(Clone, Debug)]
struct ScalingMetrics {
    current_agents: usize,
    total_tasks: u32,
    avg_latency_ms: u32,
    cpu_utilization: f64,
    memory_utilization: f64,
}

#[derive(Clone, Debug, PartialEq)]
enum ScalingAction {
    None,
    ScaleUp { count: usize, reason: String },
    ScaleDown { count: usize, reason: String },
}

#[derive(Clone, Debug)]
struct AutoScalingEngine {
    min_agents: usize,
    max_agents: usize,
    scale_up_threshold: f64,
    scale_down_threshold: f64,
    target_utilization: f64,
}

impl AutoScalingEngine {
    fn new(min_agents: usize, max_agents: usize) -> Self {
        Self {
            min_agents,
            max_agents,
            scale_up_threshold: 0.8,
            scale_down_threshold: 0.3,
            target_utilization: 0.65,
        }
    }

    fn decide_scaling(&self, metrics: &ScalingMetrics) -> ScalingAction {
        if metrics.current_agents >= self.max_agents {
            return ScalingAction::None;
        }

        let utilization = (metrics.cpu_utilization + metrics.memory_utilization) / 2.0;

        if utilization > self.scale_up_threshold {
            let additional_agents = ((metrics.current_agents as f64 * 0.25).ceil() as usize).max(1);
            return ScalingAction::ScaleUp {
                count: additional_agents.min(self.max_agents - metrics.current_agents),
                reason: format!("Utilization {:.2}% exceeds threshold {:.2}%", utilization * 100.0, self.scale_up_threshold * 100.0),
            };
        }

        if metrics.current_agents > self.min_agents && utilization < self.scale_down_threshold {
            let agents_to_remove = ((metrics.current_agents as f64 * 0.15).ceil() as usize).max(1);
            return ScalingAction::ScaleDown {
                count: agents_to_remove.min(metrics.current_agents - self.min_agents),
                reason: format!("Utilization {:.2}% below threshold {:.2}%", utilization * 100.0, self.scale_down_threshold * 100.0),
            };
        }

        ScalingAction::None
    }

    fn estimate_required_agents(&self, tasks: u32, capacity_per_agent: u32) -> usize {
        let required = (tasks as f64 / capacity_per_agent as f64).ceil() as usize;
        required.max(self.min_agents).min(self.max_agents)
    }

    fn calculate_optimal_agent_count(&self, metrics: &ScalingMetrics) -> usize {
        let ideal = (metrics.total_tasks as f64 / (100.0 * self.target_utilization)).ceil() as usize;
        ideal.max(self.min_agents).min(self.max_agents)
    }
}

#[test]
fn test_phase_3_6_autoscaling_engine_creation() {
    let engine = AutoScalingEngine::new(5, 100);
    assert_eq!(engine.min_agents, 5);
    assert_eq!(engine.max_agents, 100);
}

#[test]
fn test_phase_3_6_no_scaling_at_low_utilization() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 50,
        total_tasks: 500,
        avg_latency_ms: 50,
        cpu_utilization: 0.5,
        memory_utilization: 0.55,
    };

    let action = engine.decide_scaling(&metrics);
    assert_eq!(action, ScalingAction::None);
}

#[test]
fn test_phase_3_6_scale_up_on_high_utilization() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 10,
        total_tasks: 500,
        avg_latency_ms: 250,
        cpu_utilization: 0.85,
        memory_utilization: 0.9,
    };

    let action = engine.decide_scaling(&metrics);
    assert!(matches!(action, ScalingAction::ScaleUp { .. }));
}

#[test]
fn test_phase_3_6_scale_up_magnitude_proportional() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 20,
        total_tasks: 900,
        avg_latency_ms: 300,
        cpu_utilization: 0.95,
        memory_utilization: 0.92,
    };

    let action = engine.decide_scaling(&metrics);
    match action {
        ScalingAction::ScaleUp { count, .. } => {
            assert!(count >= 5);
        }
        _ => panic!("Expected ScaleUp"),
    }
}

#[test]
fn test_phase_3_6_scale_down_on_low_utilization() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 50,
        total_tasks: 100,
        avg_latency_ms: 20,
        cpu_utilization: 0.1,
        memory_utilization: 0.15,
    };

    let action = engine.decide_scaling(&metrics);
    assert!(matches!(action, ScalingAction::ScaleDown { .. }));
}

#[test]
fn test_phase_3_6_scale_down_respects_minimum() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 5,
        total_tasks: 50,
        avg_latency_ms: 15,
        cpu_utilization: 0.05,
        memory_utilization: 0.1,
    };

    let action = engine.decide_scaling(&metrics);
    assert_eq!(action, ScalingAction::None);
}

#[test]
fn test_phase_3_6_scale_up_respects_maximum() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 100,
        total_tasks: 5000,
        avg_latency_ms: 500,
        cpu_utilization: 1.0,
        memory_utilization: 1.0,
    };

    let action = engine.decide_scaling(&metrics);
    assert_eq!(action, ScalingAction::None);
}

#[test]
fn test_phase_3_6_estimate_required_agents() {
    let engine = AutoScalingEngine::new(5, 100);

    let required = engine.estimate_required_agents(1000, 100);
    assert!(required >= 10);
    assert!(required <= 100);

    let required_min = engine.estimate_required_agents(10, 100);
    assert_eq!(required_min, 5);
}

#[test]
fn test_phase_3_6_calculate_optimal_agent_count() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 10,
        total_tasks: 2000,
        avg_latency_ms: 100,
        cpu_utilization: 0.65,
        memory_utilization: 0.65,
    };

    let optimal = engine.calculate_optimal_agent_count(&metrics);
    assert!(optimal >= 5);
    assert!(optimal <= 100);
    assert!(optimal > metrics.current_agents);
}

#[test]
fn test_phase_3_6_scaling_action_reason_provided() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 10,
        total_tasks: 500,
        avg_latency_ms: 250,
        cpu_utilization: 0.85,
        memory_utilization: 0.95,
    };

    let action = engine.decide_scaling(&metrics);
    match action {
        ScalingAction::ScaleUp { reason, .. } => {
            assert!(!reason.is_empty());
            assert!(reason.contains("Utilization"));
        }
        _ => panic!("Expected ScaleUp with reason"),
    }
}

#[test]
fn test_phase_3_6_hysteresis_prevents_oscillation() {
    let engine = AutoScalingEngine::new(5, 100);

    let high_util = ScalingMetrics {
        current_agents: 10,
        total_tasks: 800,
        avg_latency_ms: 200,
        cpu_utilization: 0.85,
        memory_utilization: 0.80,
    };

    let low_util = ScalingMetrics {
        current_agents: 15,
        total_tasks: 300,
        avg_latency_ms: 50,
        cpu_utilization: 0.50,
        memory_utilization: 0.55,
    };

    let action_up = engine.decide_scaling(&high_util);
    assert!(matches!(action_up, ScalingAction::ScaleUp { .. }));

    let action_none = engine.decide_scaling(&low_util);
    assert_eq!(action_none, ScalingAction::None);
}

#[test]
fn test_phase_3_6_multiple_scaling_decisions_idempotent() {
    let engine = AutoScalingEngine::new(5, 100);
    let metrics = ScalingMetrics {
        current_agents: 10,
        total_tasks: 500,
        avg_latency_ms: 100,
        cpu_utilization: 0.50,
        memory_utilization: 0.55,
    };

    let action1 = engine.decide_scaling(&metrics);
    let action2 = engine.decide_scaling(&metrics);

    assert_eq!(action1, action2);
}

#[test]
fn test_phase_3_6_zero_agents_edge_case() {
    let engine = AutoScalingEngine::new(1, 100);
    let metrics = ScalingMetrics {
        current_agents: 1,
        total_tasks: 10,
        avg_latency_ms: 15,
        cpu_utilization: 0.1,
        memory_utilization: 0.12,
    };

    let action = engine.decide_scaling(&metrics);
    assert_eq!(action, ScalingAction::None);
}
