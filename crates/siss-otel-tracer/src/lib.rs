use uuid::Uuid;
use std::time::Instant;
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone)]
pub struct TraceContext {
    pub trace_id: Uuid,
    pub root_span_id: Uuid,
    pub agent_id: Uuid,
    pub intent_hash: String,
    pub task_id: Uuid,
    pub start_time: Instant,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum Decision {
    Allow,
    Deny,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum Phase {
    ReBAC,
    AP2,
    Temporal,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseOutcome {
    pub phase: Phase,
    pub result: Decision,
    pub latency_ms: f64,
    pub query_count: Option<u32>,
    pub deny_reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MandateDecision {
    pub trace_id: Uuid,
    pub root_span_id: Uuid,
    pub agent_id: Uuid,
    pub task_id: Uuid,
    pub decision: Decision,
    pub phase_outcomes: Vec<PhaseOutcome>,
    pub total_latency_ms: f64,
    pub deny_reason: Option<String>,
    pub deny_phase: Option<Phase>,
}

impl MandateDecision {
    pub fn new(
        trace_id: Uuid,
        root_span_id: Uuid,
        agent_id: Uuid,
        task_id: Uuid,
    ) -> Self {
        MandateDecision {
            trace_id,
            root_span_id,
            agent_id,
            task_id,
            decision: Decision::Allow,
            phase_outcomes: vec![],
            total_latency_ms: 0.0,
            deny_reason: None,
            deny_phase: None,
        }
    }

    pub fn add_phase_outcome(&mut self, outcome: PhaseOutcome) {
        if outcome.result == Decision::Deny {
            self.decision = Decision::Deny;
            self.deny_phase = Some(outcome.phase);
            self.deny_reason = outcome.deny_reason.clone();
        }
        self.phase_outcomes.push(outcome);
    }

    pub fn set_total_latency(&mut self, latency_ms: f64) {
        self.total_latency_ms = latency_ms;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sovereign(id: u64) -> Uuid {
        Uuid::from_u64_pair(id, 0)
    }

    #[test]
    fn test_trace_context_creation() {
        let trace_id = Uuid::new_v4();
        let root_span_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let ctx = TraceContext {
            trace_id,
            root_span_id,
            agent_id,
            intent_hash: "sha256_hash".to_string(),
            task_id,
            start_time: Instant::now(),
        };

        assert_eq!(ctx.trace_id, trace_id);
        assert_eq!(ctx.root_span_id, root_span_id);
        assert_eq!(ctx.agent_id, agent_id);
        assert_eq!(ctx.task_id, task_id);
    }

    #[test]
    fn test_mandate_decision_three_phase() {
        let trace_id = Uuid::new_v4();
        let root_span_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let mut decision = MandateDecision::new(trace_id, root_span_id, agent_id, task_id);

        decision.add_phase_outcome(PhaseOutcome {
            phase: Phase::ReBAC,
            result: Decision::Allow,
            latency_ms: 2.1,
            query_count: Some(4),
            deny_reason: None,
        });

        decision.add_phase_outcome(PhaseOutcome {
            phase: Phase::AP2,
            result: Decision::Allow,
            latency_ms: 1.8,
            query_count: None,
            deny_reason: None,
        });

        decision.add_phase_outcome(PhaseOutcome {
            phase: Phase::Temporal,
            result: Decision::Deny,
            latency_ms: 38.6,
            query_count: None,
            deny_reason: Some("Rate limit exceeded (61 req/min)".to_string()),
        });

        decision.set_total_latency(42.5);

        assert_eq!(decision.decision, Decision::Deny);
        assert_eq!(decision.phase_outcomes.len(), 3);
        assert_eq!(decision.deny_phase, Some(Phase::Temporal));
        assert!(decision.deny_reason.is_some());
        assert_eq!(decision.total_latency_ms, 42.5);
    }

    #[test]
    fn test_rebac_phase_with_query_count() {
        let rebac_outcome = PhaseOutcome {
            phase: Phase::ReBAC,
            result: Decision::Allow,
            latency_ms: 3.5,
            query_count: Some(4),
            deny_reason: None,
        };

        assert_eq!(rebac_outcome.phase, Phase::ReBAC);
        assert_eq!(rebac_outcome.result, Decision::Allow);
        assert_eq!(rebac_outcome.query_count, Some(4));
        assert!(rebac_outcome.deny_reason.is_none());
    }

    #[test]
    fn test_ap2_deny_with_rule_reason() {
        let ap2_deny = PhaseOutcome {
            phase: Phase::AP2,
            result: Decision::Deny,
            latency_ms: 2.8,
            query_count: None,
            deny_reason: Some("Policy 'blacklist_check' denied: Agent is blacklisted".to_string()),
        };

        assert_eq!(ap2_deny.result, Decision::Deny);
        assert!(ap2_deny.deny_reason.as_ref().unwrap().contains("blacklist_check"));
    }

    #[test]
    fn test_temporal_deny_with_context() {
        let temporal_deny = PhaseOutcome {
            phase: Phase::Temporal,
            result: Decision::Deny,
            latency_ms: 0.3,
            query_count: None,
            deny_reason: Some("Rate limit exceeded: 61 req/min (limit: 60)".to_string()),
        };

        assert_eq!(temporal_deny.result, Decision::Deny);
        assert!(temporal_deny.deny_reason.as_ref().unwrap().contains("61"));
    }

    #[test]
    fn test_mandate_decision_serialization() {
        let trace_id = Uuid::new_v4();
        let root_span_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let mut decision = MandateDecision::new(trace_id, root_span_id, agent_id, task_id);
        decision.add_phase_outcome(PhaseOutcome {
            phase: Phase::ReBAC,
            result: Decision::Allow,
            latency_ms: 2.1,
            query_count: Some(4),
            deny_reason: None,
        });
        decision.set_total_latency(2.1);

        let json = serde_json::to_string(&decision).expect("Serialization failed");
        assert!(json.contains("\"phase\":\"ReBAC\""));
        assert!(json.contains("\"decision\":\"Allow\""));
        assert!(json.contains("\"query_count\":4"));
    }

    #[test]
    fn test_mandate_first_deny_wins() {
        let trace_id = Uuid::new_v4();
        let root_span_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let mut decision = MandateDecision::new(trace_id, root_span_id, agent_id, task_id);

        decision.add_phase_outcome(PhaseOutcome {
            phase: Phase::ReBAC,
            result: Decision::Deny,
            latency_ms: 2.1,
            query_count: Some(2),
            deny_reason: Some("No relationship found".to_string()),
        });

        decision.add_phase_outcome(PhaseOutcome {
            phase: Phase::AP2,
            result: Decision::Deny,
            latency_ms: 1.8,
            query_count: None,
            deny_reason: Some("Blacklisted".to_string()),
        });

        assert_eq!(decision.deny_phase, Some(Phase::ReBAC));
        assert!(decision.deny_reason.as_ref().unwrap().contains("No relationship"));
    }

    #[test]
    fn test_trace_context_cockpit_fields() {
        let trace_id = Uuid::new_v4();
        let root_span_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let ctx = TraceContext {
            trace_id,
            root_span_id,
            agent_id,
            intent_hash: "d4a8e7f1c3b6a9e2f5c8d1b4a7e0f3c6".to_string(),
            task_id,
            start_time: Instant::now(),
        };

        assert!(!ctx.intent_hash.is_empty());
        assert_ne!(ctx.trace_id, Uuid::nil());
        assert_ne!(ctx.root_span_id, Uuid::nil());
        assert_ne!(ctx.agent_id, Uuid::nil());
    }
}
