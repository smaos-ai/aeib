use serde::{Deserialize, Serialize};
use std::time::Instant;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SSEPayload {
    pub event_type: String,
    pub trace_id: Uuid,
    pub agent_id: Uuid,
    pub task_id: Uuid,
    pub timestamp: String,
    pub decision: String,
    pub deny_phase: Option<String>,
    pub deny_reason: Option<String>,
    pub phase_breakdown: Vec<PhaseBreakdown>,
    pub total_evaluation_latency_ms: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseBreakdown {
    pub phase: String,
    pub result: String,
    pub latency_ms: f64,
}

#[derive(Debug, Clone)]
pub struct SSERouter {
    latency_budget_ms: f64,
}

impl SSERouter {
    pub fn new(latency_budget_ms: f64) -> Self {
        SSERouter { latency_budget_ms }
    }

    pub fn transform_mandate_to_sse(
        &self,
        trace_id: Uuid,
        agent_id: Uuid,
        task_id: Uuid,
        decision: String,
        deny_phase: Option<String>,
        deny_reason: Option<String>,
        phase_breakdown: Vec<(String, String, f64)>,
        total_latency_ms: f64,
    ) -> Result<SSEPayload, String> {
        let event_type = if decision == "Deny" {
            "mandate_denial".to_string()
        } else if total_latency_ms > self.latency_budget_ms {
            "mandate_allow_slow".to_string()
        } else {
            "mandate_allow".to_string()
        };

        let phases = phase_breakdown
            .into_iter()
            .map(|(phase, result, latency)| PhaseBreakdown {
                phase,
                result,
                latency_ms: latency,
            })
            .collect();

        Ok(SSEPayload {
            event_type,
            trace_id,
            agent_id,
            task_id,
            timestamp: chrono::Utc::now().to_rfc3339(),
            decision,
            deny_phase,
            deny_reason,
            phase_breakdown: phases,
            total_evaluation_latency_ms: total_latency_ms,
        })
    }

    pub fn emit_to_stream(&self, payload: SSEPayload) -> Result<String, String> {
        let serialized =
            serde_json::to_string(&payload).map_err(|e| format!("Serialization failed: {}", e))?;
        Ok(format!("data: {}\n\n", serialized))
    }

    pub fn assert_latency_budget(&self, actual_latency_ms: f64) -> Result<(), String> {
        if actual_latency_ms > self.latency_budget_ms {
            Err(format!(
                "Latency {} ms exceeds budget {} ms",
                actual_latency_ms, self.latency_budget_ms
            ))
        } else {
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sovereign(id: u64) -> Uuid {
        Uuid::from_u64_pair(id, 0)
    }

    #[test]
    fn test_sse_payload_mandate_denial() {
        let router = SSERouter::new(100.0);
        let trace_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let phases = vec![
            ("ReBAC".to_string(), "Allow".to_string(), 2.1),
            ("AP2".to_string(), "Allow".to_string(), 1.8),
            ("Temporal".to_string(), "Deny".to_string(), 38.6),
        ];

        let payload = router
            .transform_mandate_to_sse(
                trace_id,
                agent_id,
                task_id,
                "Deny".to_string(),
                Some("Temporal".to_string()),
                Some("Rate limit exceeded (61 req/min)".to_string()),
                phases,
                42.5,
            )
            .expect("Transform failed");

        assert_eq!(payload.event_type, "mandate_denial");
        assert_eq!(payload.decision, "Deny");
        assert_eq!(payload.deny_phase, Some("Temporal".to_string()));
        assert!(payload.deny_reason.is_some());
        assert_eq!(payload.phase_breakdown.len(), 3);
    }

    #[test]
    fn test_sse_latency_budget_within_threshold() {
        let router = SSERouter::new(100.0);
        let latency = 42.5;

        let result = router.assert_latency_budget(latency);
        assert!(result.is_ok(), "Latency within budget should pass");
    }

    #[test]
    fn test_sse_latency_budget_exceeds_threshold() {
        let router = SSERouter::new(100.0);
        let latency = 125.5;

        let result = router.assert_latency_budget(latency);
        assert!(result.is_err(), "Latency exceeding budget should fail");
    }

    #[test]
    fn test_sse_payload_serialization_to_stream() {
        let router = SSERouter::new(100.0);
        let trace_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let phases = vec![
            ("ReBAC".to_string(), "Allow".to_string(), 2.1),
            ("AP2".to_string(), "Allow".to_string(), 1.8),
            ("Temporal".to_string(), "Deny".to_string(), 38.6),
        ];

        let payload = router
            .transform_mandate_to_sse(
                trace_id,
                agent_id,
                task_id,
                "Deny".to_string(),
                Some("Temporal".to_string()),
                Some("Rate limit exceeded".to_string()),
                phases,
                42.5,
            )
            .expect("Transform failed");

        let sse_string = router.emit_to_stream(payload).expect("SSE emit failed");
        assert!(sse_string.starts_with("data:"));
        assert!(sse_string.ends_with("\n\n"));
        assert!(sse_string.contains("mandate_denial"));
    }

    #[test]
    fn test_sse_slow_allow_event_type() {
        let router = SSERouter::new(100.0);
        let trace_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let phases = vec![
            ("ReBAC".to_string(), "Allow".to_string(), 50.0),
            ("AP2".to_string(), "Allow".to_string(), 40.0),
            ("Temporal".to_string(), "Allow".to_string(), 35.0),
        ];

        let payload = router
            .transform_mandate_to_sse(
                trace_id,
                agent_id,
                task_id,
                "Allow".to_string(),
                None,
                None,
                phases,
                125.0, // Exceeds 100ms budget
            )
            .expect("Transform failed");

        assert_eq!(payload.event_type, "mandate_allow_slow");
    }

    #[test]
    fn test_sse_phase_breakdown_order() {
        let router = SSERouter::new(100.0);
        let trace_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let phases = vec![
            ("ReBAC".to_string(), "Allow".to_string(), 2.1),
            ("AP2".to_string(), "Allow".to_string(), 1.8),
            ("Temporal".to_string(), "Deny".to_string(), 38.6),
        ];

        let payload = router
            .transform_mandate_to_sse(
                trace_id,
                agent_id,
                task_id,
                "Deny".to_string(),
                Some("Temporal".to_string()),
                Some("Rate limit exceeded".to_string()),
                phases,
                42.5,
            )
            .expect("Transform failed");

        assert_eq!(payload.phase_breakdown[0].phase, "ReBAC");
        assert_eq!(payload.phase_breakdown[1].phase, "AP2");
        assert_eq!(payload.phase_breakdown[2].phase, "Temporal");
    }

    #[test]
    fn test_sse_payload_timestamp_iso8601() {
        let router = SSERouter::new(100.0);
        let trace_id = Uuid::new_v4();
        let agent_id = sovereign(1);
        let task_id = Uuid::new_v4();

        let phases = vec![("ReBAC".to_string(), "Allow".to_string(), 2.1)];

        let payload = router
            .transform_mandate_to_sse(
                trace_id,
                agent_id,
                task_id,
                "Allow".to_string(),
                None,
                None,
                phases,
                2.1,
            )
            .expect("Transform failed");

        assert!(!payload.timestamp.is_empty());
        assert!(payload.timestamp.contains("T"));
        assert!(payload.timestamp.contains("Z") || payload.timestamp.contains("+"));
    }

    #[test]
    fn test_sse_routing_multiple_denials() {
        let router = SSERouter::new(100.0);

        let denials = vec![
            ("ReBAC", "No relationship"),
            ("AP2", "Blacklisted"),
            ("Temporal", "Rate limited"),
        ];

        for (phase, reason) in denials {
            let phases = vec![(phase.to_string(), "Deny".to_string(), 5.0)];

            let payload = router
                .transform_mandate_to_sse(
                    Uuid::new_v4(),
                    sovereign(1),
                    Uuid::new_v4(),
                    "Deny".to_string(),
                    Some(phase.to_string()),
                    Some(reason.to_string()),
                    phases,
                    5.0,
                )
                .expect("Transform failed");

            assert_eq!(payload.event_type, "mandate_denial");
            assert_eq!(payload.deny_phase, Some(phase.to_string()));
        }
    }
}
