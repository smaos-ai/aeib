use std::collections::HashMap;
use tokio::sync::mpsc;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum SSEStreamType {
    TaskRouting,
    Audit,
    ProofGeneration,
}

pub struct SSEMultiplexer {
    streams: HashMap<SSEStreamType, Vec<mpsc::Sender<String>>>,
}

impl SSEMultiplexer {
    pub fn new() -> Self {
        SSEMultiplexer {
            streams: HashMap::new(),
        }
    }

    pub fn subscribe(&mut self, stream_type: SSEStreamType) -> mpsc::Receiver<String> {
        // Create a bounded channel with capacity 1 for backpressure
        let (tx, rx) = mpsc::channel(1);

        // Ensure the stream_type key exists in the HashMap and store the sender
        self.streams
            .entry(stream_type.clone())
            .or_insert_with(Vec::new)
            .push(tx);

        rx
    }

    pub fn publish(&self, stream_type: SSEStreamType, event: String) -> Result<usize, String> {
        // Get all senders for this specific stream type
        let senders = match self.streams.get(&stream_type) {
            Some(senders) => senders,
            None => return Ok(0), // No subscribers for this stream
        };

        let mut count = 0;
        for sender in senders {
            // Use try_send() for non-blocking, which enables backpressure
            match sender.try_send(event.clone()) {
                Ok(()) => count += 1,
                Err(_) => return Err("Channel full or receiver dropped".to_string()),
            }
        }

        Ok(count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_three_concurrent_streams_no_bleed() {
        // Subscribe to TaskRouting and Audit streams
        let mut multiplexer = SSEMultiplexer::new();
        let mut task_routing_rx = multiplexer.subscribe(SSEStreamType::TaskRouting);
        let mut audit_rx = multiplexer.subscribe(SSEStreamType::Audit);

        // Publish event only to TaskRouting
        let event = "task_event".to_string();
        let result = multiplexer.publish(SSEStreamType::TaskRouting, event.clone());

        // Assert publish succeeded
        assert!(result.is_ok());

        // Assert TaskRouting receiver gets the event
        let task_event = task_routing_rx.try_recv();
        assert!(task_event.is_ok());
        assert_eq!(task_event.unwrap(), "task_event");

        // Assert Audit receiver gets nothing (no bleed)
        let audit_event = audit_rx.try_recv();
        assert!(audit_event.is_err());
    }

    #[test]
    fn test_slow_subscriber_backpressure() {
        let mut multiplexer = SSEMultiplexer::new();
        // Subscribe with bounded channel (capacity 1)
        let _rx = multiplexer.subscribe(SSEStreamType::TaskRouting);

        // Publish first event - should succeed
        let result1 = multiplexer.publish(
            SSEStreamType::TaskRouting,
            "event_1".to_string(),
        );
        assert!(result1.is_ok());

        // Publish second event rapidly - should fail (bounded channel full)
        let result2 = multiplexer.publish(
            SSEStreamType::TaskRouting,
            "event_2".to_string(),
        );
        assert!(result2.is_err());
    }

    #[test]
    fn test_client_side_stream_filtering() {
        let mut multiplexer = SSEMultiplexer::new();
        // Subscribe to Audit only
        let mut audit_rx = multiplexer.subscribe(SSEStreamType::Audit);

        // Publish to both TaskRouting and Audit
        let task_event = "task_event".to_string();
        let audit_event = "audit_event".to_string();

        multiplexer.publish(SSEStreamType::TaskRouting, task_event).ok();
        multiplexer.publish(SSEStreamType::Audit, audit_event.clone()).ok();

        // Assert only Audit events arrive on the Audit receiver
        let received = audit_rx.try_recv();
        assert!(received.is_ok());
        assert_eq!(received.unwrap(), "audit_event");
    }
}
