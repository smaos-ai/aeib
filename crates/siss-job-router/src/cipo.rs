/// CIPO Trace Distillation: captures SLM failures from OmniRoute escalations and distills them
/// into RefinementSignal lessons that teach the local SLM to handle previously failing tasks.
use crate::confidence_scorer::RoutingTier;
use chrono::{DateTime, Utc};

/// Trace of a Tier1 → Tier3 escalation due to VerificationGate failure.
#[derive(Debug, Clone)]
pub struct CipoTrace {
    pub payload: String,
    pub slm_output: String,
    pub gate_error_raw: String,
    pub tier_escalated_from: RoutingTier,
    pub tier_escalated_to: RoutingTier,
    pub timestamp: DateTime<Utc>,
}

/// A distilled lesson from one or more CipoTrace records.
#[derive(Debug, Clone)]
pub struct RefinementSignal {
    pub lesson: String,
    pub confidence: f64,
    pub source_trace_count: usize,
}

pub struct CipoDistiller;

impl CipoDistiller {
    /// Distill a batch of failure traces into refinement signals.
    /// Groups by tier_escalated_from; produces one RefinementSignal per group.
    pub fn distill(traces: &[CipoTrace]) -> Vec<RefinementSignal> {
        if traces.is_empty() {
            return vec![];
        }

        // Group by escalation source tier
        let mut by_tier: std::collections::HashMap<String, Vec<&CipoTrace>> =
            std::collections::HashMap::new();

        for trace in traces {
            let tier_key = format!("{:?}", trace.tier_escalated_from);
            by_tier.entry(tier_key).or_insert_with(Vec::new).push(trace);
        }

        // Produce one signal per group
        by_tier
            .into_iter()
            .map(|(_, group)| {
                let count = group.len();
                let first = group[0];

                let gate_err_snippet = first.gate_error_raw.chars().take(60).collect::<String>();
                let payload_snippet = first.payload.chars().take(40).collect::<String>();

                let lesson = format!(
                    "SLM failed: {} → retrain on [{}]",
                    gate_err_snippet, payload_snippet
                );

                let confidence = ((count as f64) / 10.0).clamp(0.0, 1.0);

                RefinementSignal {
                    lesson,
                    confidence,
                    source_trace_count: count,
                }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_distill_empty() {
        let signals = CipoDistiller::distill(&[]);
        assert!(signals.is_empty());
    }

    #[test]
    fn test_distill_single_trace() {
        let trace = CipoTrace {
            payload: "test_payload".to_string(),
            slm_output: "bad output".to_string(),
            gate_error_raw: "not valid json".to_string(),
            tier_escalated_from: RoutingTier::Tier1RapidMLX,
            tier_escalated_to: RoutingTier::Tier3Opus,
            timestamp: Utc::now(),
        };

        let signals = CipoDistiller::distill(&[trace]);
        assert_eq!(signals.len(), 1);
        assert!(signals[0].lesson.contains("SLM failed"));
        assert!(signals[0].lesson.contains("test_payload"));
        assert_eq!(signals[0].source_trace_count, 1);
    }

    #[test]
    fn test_distill_confidence_clamped() {
        let traces: Vec<CipoTrace> = (0..15)
            .map(|i| CipoTrace {
                payload: format!("payload_{}", i),
                slm_output: "bad".to_string(),
                gate_error_raw: "not json".to_string(),
                tier_escalated_from: RoutingTier::Tier1RapidMLX,
                tier_escalated_to: RoutingTier::Tier3Opus,
                timestamp: Utc::now(),
            })
            .collect();

        let signals = CipoDistiller::distill(&traces);
        assert_eq!(signals.len(), 1);
        assert!(signals[0].confidence <= 1.0);
    }
}
