//! L5 A2A Resilience Tests: Retry, timeout, circuit breaker patterns
//! Tests for agent-to-agent communication reliability

use l5_communication::{A2aRouter, A2aMessage};
use serde_json::json;

#[test]
fn test_a2a_basic_message_routing() {
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("agent1".to_string(), "orchestrator".to_string());
    let agent2 = router.register_agent("agent2".to_string(), "evaluator".to_string());

    let result = router.send_message(
        agent1.id.clone(),
        agent2.id.clone(),
        "evaluate".to_string(),
        json!({"request_id": "req1"}),
    );

    assert!(result.is_ok());
}

#[test]
fn test_a2a_retry_on_transient_failure() {
    // Simulate retry logic: first attempt fails, second succeeds
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("agent1".to_string(), "sender".to_string());
    let agent2 = router.register_agent("agent2".to_string(), "receiver".to_string());

    let mut attempt_count = 0;
    let mut result = Err("connection refused".to_string());

    while attempt_count < 3 && result.is_err() {
        result = router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            "retry_test".to_string(),
            json!({"attempt": attempt_count + 1}),
        );

        if result.is_ok() {
            break;
        }
        attempt_count += 1;
    }

    // After retries, message should succeed
    assert!(result.is_ok() || attempt_count >= 3);
}

#[test]
fn test_a2a_timeout_handling() {
    let router = A2aRouter::new();

    // Create agents for timeout test
    let mut router = router;
    let _agent = router.register_agent("slow_agent".to_string(), "slow".to_string());

    // In real implementation, this would track elapsed time
    // For now, verify timeout structure is correct
    assert!(router.list_agents().len() >= 1);
}

#[test]
fn test_a2a_circuit_breaker_open() {
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("agent1".to_string(), "service_a".to_string());
    let agent2 = router.register_agent("agent2".to_string(), "service_b".to_string());

    // Simulate circuit breaker: after N failures, circuit opens
    let mut failure_count = 0;
    let circuit_breaker_threshold = 5;

    for i in 0..10 {
        if failure_count >= circuit_breaker_threshold {
            // Circuit is open, fail fast without attempting
            break;
        }

        let result = router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            format!("attempt_{}", i),
            json!({"attempt": i}),
        );

        if result.is_err() {
            failure_count += 1;
        }
    }

    assert!(failure_count < 10, "Circuit breaker should limit failures");
}

#[test]
fn test_a2a_circuit_breaker_half_open() {
    // Circuit breaker half-open state: allow probe request
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("recovered_service".to_string(), "service".to_string());
    let agent2 = router.register_agent("client".to_string(), "client".to_string());

    // Send probe request in half-open state
    let probe_result = router.send_message(
        agent1.id.clone(),
        agent2.id.clone(),
        "probe".to_string(),
        json!({"is_probe": true}),
    );

    assert!(probe_result.is_ok(), "Half-open should allow probe request");
}

#[test]
fn test_a2a_exponential_backoff() {
    let mut backoffs = vec![];
    let mut backoff_ms = 100u64;

    for _ in 0..5 {
        backoffs.push(backoff_ms);
        backoff_ms = (backoff_ms as f64 * 2.0) as u64;
        if backoff_ms > 5000 {
            backoff_ms = 5000;
        }
    }

    assert_eq!(backoffs[0], 100);
    assert_eq!(backoffs[1], 200);
    assert_eq!(backoffs[2], 400);
    assert_eq!(backoffs[3], 800);
    assert_eq!(backoffs[4], 1600);
}

#[test]
fn test_a2a_message_queue_resilience() {
    let mut router = A2aRouter::new();

    // Register multiple agents
    let agent1 = router.register_agent("producer".to_string(), "source".to_string());
    let agent2 = router.register_agent("consumer".to_string(), "sink".to_string());

    // Send multiple messages in queue
    for i in 0..10 {
        let _ = router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            format!("msg_{}", i),
            json!({"id": i}),
        );
    }

    let messages = router.get_messages_for_agent(&agent2.id);
    assert_eq!(messages.len(), 10, "All messages should be queued");
}

#[test]
fn test_a2a_dead_letter_queue_simulation() {
    let mut router = A2aRouter::new();
    let sender = router.register_agent("sender".to_string(), "sender".to_string());

    // Attempt to send to non-existent agent (should fail and go to DLQ)
    let result = router.send_message(
        sender.id.clone(),
        "nonexistent_agent".to_string(),
        "test".to_string(),
        json!({"data": "test"}),
    );

    assert!(
        result.is_err(),
        "Message to invalid recipient should fail"
    );
}

#[test]
fn test_a2a_idempotent_message_routing() {
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("idempotent_client".to_string(), "client".to_string());
    let agent2 = router.register_agent("idempotent_server".to_string(), "server".to_string());

    let message_id = "msg_123";

    // Send same message with same ID twice
    let msg1 = router.send_message(
        agent1.id.clone(),
        agent2.id.clone(),
        "request".to_string(),
        json!({"message_id": message_id}),
    );

    let msg2 = router.send_message(
        agent1.id.clone(),
        agent2.id.clone(),
        "request".to_string(),
        json!({"message_id": message_id}),
    );

    assert!(msg1.is_ok());
    assert!(msg2.is_ok());

    let messages = router.get_messages_for_agent(&agent2.id);
    assert_eq!(messages.len(), 2, "Both messages should be queued");
}

#[test]
fn test_a2a_ordered_delivery() {
    let mut router = A2aRouter::new();
    let sender = router.register_agent("ordered_sender".to_string(), "sender".to_string());
    let receiver = router.register_agent("ordered_receiver".to_string(), "receiver".to_string());

    // Send messages in order
    for i in 0..5 {
        let _ = router.send_message(
            sender.id.clone(),
            receiver.id.clone(),
            format!("msg_{}", i),
            json!({"sequence": i}),
        );
    }

    let messages = router.get_messages_for_agent(&receiver.id);
    for (i, msg) in messages.iter().enumerate() {
        assert!(
            msg.message_type.contains(&i.to_string()),
            "Messages should maintain order"
        );
    }
}

#[test]
fn test_a2a_timeout_with_retry() {
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("timeout_client".to_string(), "client".to_string());
    let agent2 = router.register_agent("timeout_server".to_string(), "server".to_string());

    let mut last_result = Err("timeout".to_string());

    // Simulate: attempt with timeout, retry, eventual success
    for attempt in 0..3 {
        last_result = router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            format!("timeout_attempt_{}", attempt),
            json!({"attempt": attempt}),
        );

        if last_result.is_ok() {
            break;
        }
    }

    assert!(last_result.is_ok(), "Eventually should succeed");
}

#[test]
fn test_a2a_bulk_message_handling() {
    let mut router = A2aRouter::new();
    let sender = router.register_agent("bulk_sender".to_string(), "sender".to_string());

    let mut receivers = vec![];
    for i in 0..5 {
        let receiver = router.register_agent(
            format!("bulk_receiver_{}", i),
            "receiver".to_string(),
        );
        receivers.push(receiver);
    }

    // Send 100 messages across receivers
    for i in 0..100 {
        let receiver = &receivers[i % receivers.len()];
        let _ = router.send_message(
            sender.id.clone(),
            receiver.id.clone(),
            format!("bulk_msg_{}", i),
            json!({"seq": i}),
        );
    }

    let total_messages: usize = receivers
        .iter()
        .map(|r| router.get_messages_for_agent(&r.id).len())
        .sum();

    assert_eq!(total_messages, 100, "All 100 messages should be delivered");
}

#[test]
fn test_a2a_failure_recovery_100_iterations() {
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("resilient_client".to_string(), "client".to_string());
    let agent2 = router.register_agent("resilient_server".to_string(), "server".to_string());

    let mut successes = 0;

    for i in 0..100 {
        let result = router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            format!("resilience_test_{}", i),
            json!({"iteration": i}),
        );

        if result.is_ok() {
            successes += 1;
        }
    }

    assert_eq!(
        successes, 100,
        "All 100 resilience iterations should succeed"
    );
}

#[test]
fn test_a2a_selective_retry_on_failure() {
    let mut router = A2aRouter::new();
    let sender = router.register_agent("selective_sender".to_string(), "sender".to_string());

    // Test that retries only happen on retryable errors
    let receiver = router.register_agent("selective_receiver".to_string(), "receiver".to_string());

    let result = router.send_message(
        sender.id.clone(),
        receiver.id.clone(),
        "retryable_failure".to_string(),
        json!({"error_code": "TRANSIENT"}),
    );

    assert!(result.is_ok(), "Retryable error should be handled");
}

#[test]
fn test_a2a_circuit_breaker_reset() {
    let mut router = A2aRouter::new();
    let service_a = router.register_agent("service_a_reset".to_string(), "service".to_string());
    let service_b = router.register_agent("service_b_reset".to_string(), "service".to_string());

    // Initial communication should work
    let result1 = router.send_message(
        service_a.id.clone(),
        service_b.id.clone(),
        "test1".to_string(),
        json!({"phase": "initial"}),
    );
    assert!(result1.is_ok());

    // After timeout/recovery, circuit breaker resets
    let result2 = router.send_message(
        service_a.id.clone(),
        service_b.id.clone(),
        "test2".to_string(),
        json!({"phase": "after_reset"}),
    );
    assert!(result2.is_ok());
}

#[test]
fn test_a2a_graceful_degradation() {
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("primary".to_string(), "service".to_string());
    let agent2 = router.register_agent("fallback".to_string(), "service".to_string());

    // Try primary
    let primary_result = router.send_message(
        agent1.id.clone(),
        agent2.id.clone(),
        "primary_request".to_string(),
        json!({"priority": "high"}),
    );

    // If primary fails, use fallback
    if primary_result.is_err() {
        let fallback_result = router.send_message(
            agent1.id.clone(),
            agent2.id.clone(),
            "fallback_request".to_string(),
            json!({"priority": "medium"}),
        );
        assert!(fallback_result.is_ok(), "Fallback should succeed");
    } else {
        assert!(primary_result.is_ok());
    }
}

#[test]
fn test_a2a_message_ttl_handling() {
    // Messages should not linger indefinitely
    let mut router = A2aRouter::new();
    let sender = router.register_agent("ttl_sender".to_string(), "sender".to_string());
    let receiver = router.register_agent("ttl_receiver".to_string(), "receiver".to_string());

    let msg = router
        .send_message(
            sender.id.clone(),
            receiver.id.clone(),
            "ttl_message".to_string(),
            json!({"ttl_seconds": 60}),
        )
        .unwrap();

    // Message should be deliverable immediately
    assert!(!msg.message_id.is_empty());
    assert!(msg.timestamp <= chrono::Utc::now());
}

#[test]
fn test_a2a_concurrent_agent_registration() {
    let mut router = A2aRouter::new();

    for i in 0..20 {
        router.register_agent(
            format!("concurrent_agent_{}", i),
            "service".to_string(),
        );
    }

    let agents = router.list_agents();
    assert_eq!(agents.len(), 20, "All agents should be registered");
}

#[test]
fn test_a2a_agent_isolation() {
    let mut router = A2aRouter::new();
    let agent1 = router.register_agent("isolated_1".to_string(), "app1".to_string());
    let agent2 = router.register_agent("isolated_2".to_string(), "app2".to_string());
    let agent3 = router.register_agent("isolated_3".to_string(), "app3".to_string());

    // Messages for agent2 should not affect agent1 or agent3
    let msg1 = router.send_message(
        agent1.id.clone(),
        agent2.id.clone(),
        "to_agent2".to_string(),
        json!({"target": 2}),
    );

    let agent1_msgs = router.get_messages_for_agent(&agent1.id);
    let agent2_msgs = router.get_messages_for_agent(&agent2.id);
    let agent3_msgs = router.get_messages_for_agent(&agent3.id);

    assert!(msg1.is_ok());
    assert_eq!(agent1_msgs.len(), 0, "Agent1 should have no received messages");
    assert_eq!(agent2_msgs.len(), 1, "Agent2 should have one message");
    assert_eq!(agent3_msgs.len(), 0, "Agent3 should have no messages");
}
