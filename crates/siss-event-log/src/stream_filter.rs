use std::time::{SystemTime, UNIX_EPOCH};

pub struct StreamFilter {
    min_risk_class: u8,
}

#[derive(Debug, Clone)]
pub struct EnrichedEvent {
    pub raw: String,
    pub policy_source: String,
    pub requester_id: String,
    pub evaluated_at: u64,
    pub risk_class: u8,
}

impl StreamFilter {
    pub fn new(min_risk_class: u8) -> Self {
        StreamFilter { min_risk_class }
    }

    pub fn enrich(
        &self,
        raw: String,
        policy_source: String,
        requester_id: String,
        risk_class: u8,
    ) -> Option<EnrichedEvent> {
        if risk_class >= self.min_risk_class {
            let evaluated_at = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_millis() as u64;

            Some(EnrichedEvent {
                raw,
                policy_source,
                requester_id,
                evaluated_at,
                risk_class,
            })
        } else {
            None
        }
    }

    pub fn passes(&self, event: &EnrichedEvent) -> bool {
        event.risk_class >= self.min_risk_class
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_low_risk_event_filtered_out() {
        let filter = StreamFilter::new(50);
        let result = filter.enrich(
            "test_event".to_string(),
            "policy_source".to_string(),
            "requester_1".to_string(),
            30, // below threshold of 50
        );
        assert!(result.is_none());
    }

    #[test]
    fn test_enriched_event_includes_decision_context() {
        let filter = StreamFilter::new(50);
        let result = filter.enrich(
            "test_event".to_string(),
            "policy_source".to_string(),
            "requester_1".to_string(),
            80, // above threshold of 50
        );

        assert!(result.is_some());
        let enriched = result.unwrap();
        assert_eq!(enriched.raw, "test_event");
        assert_eq!(enriched.policy_source, "policy_source");
        assert_eq!(enriched.requester_id, "requester_1");
        assert_eq!(enriched.risk_class, 80);
        assert!(enriched.evaluated_at > 0);
    }

    #[test]
    fn test_filter_does_not_mutate_original_stream() {
        let filter = StreamFilter::new(50);

        // Create multiple enriched events to ensure filtering doesn't affect stream types
        let event1 = filter.enrich(
            "event1".to_string(),
            "policy1".to_string(),
            "user1".to_string(),
            60,
        );

        let event2 = filter.enrich(
            "event2".to_string(),
            "policy2".to_string(),
            "user2".to_string(),
            40,
        );

        let event3 = filter.enrich(
            "event3".to_string(),
            "policy3".to_string(),
            "user3".to_string(),
            70,
        );

        // Verify filtering behavior is consistent
        assert!(event1.is_some());
        assert!(event2.is_none());
        assert!(event3.is_some());

        // Verify passes() method works correctly
        let passed_event = event1.unwrap();
        assert!(filter.passes(&passed_event));

        let another_event = filter.enrich(
            "event4".to_string(),
            "policy4".to_string(),
            "user4".to_string(),
            50,
        );
        assert!(another_event.is_some());
        assert!(filter.passes(&another_event.unwrap()));
    }
}
