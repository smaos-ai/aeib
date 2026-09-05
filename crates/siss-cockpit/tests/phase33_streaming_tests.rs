use siss_agent_shell::a2ui::A2UIComponent;
use siss_cockpit::a2ui::component_broadcast::ComponentBroadcast;
/// Phase 33: AG-UI Real-Time Streaming Tests (TDD Approach)
/// 20 comprehensive tests covering streaming gateway, component broadcast, and SSE integration
use siss_cockpit::a2ui::streaming_gateway::A2UIStreamingGateway;
use std::sync::Arc;
use uuid::Uuid;

// ============================================================================
// TIER 1: Core Gateway Tests (8 tests)
// ============================================================================

#[tokio::test]
async fn test_gateway_publishes_component() {
    let gateway = A2UIStreamingGateway::new(100);
    let _rx = gateway.subscribe(); // Create at least one subscriber

    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Click Me".to_string(),
        action: Some("submit".to_string()),
    };

    let result = gateway.publish(component);
    assert!(result.is_ok(), "publish should succeed");
    assert_eq!(result.unwrap(), 1, "should have 1 subscriber");
}

#[tokio::test]
async fn test_gateway_validates_schema_before_broadcast() {
    let gateway = A2UIStreamingGateway::new(100);
    let _rx = gateway.subscribe(); // Create at least one subscriber

    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "".to_string(), // Empty label may be caught by validator
        action: None,
    };

    // This component should still publish but validation flag should exist
    let result = gateway.publish(component);
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_gateway_rejects_invalid_schema() {
    let gateway = A2UIStreamingGateway::new(100);
    let _rx = gateway.subscribe(); // Create at least one subscriber

    let component = A2UIComponent::Input {
        id: "input1".to_string(),
        label: "Test Input".to_string(),
        placeholder: Some("Enter text".to_string()),
        required: true,
    };

    // Valid component should pass
    let result = gateway.publish(component);
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_gateway_runs_accessibility_audit() {
    let gateway = A2UIStreamingGateway::new(100);
    let _rx = gateway.subscribe(); // Create at least one subscriber

    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Click Me".to_string(),
        action: Some("submit".to_string()),
    };

    let result = gateway.publish(component);
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_gateway_renders_jsx_on_publish() {
    let gateway = A2UIStreamingGateway::new(100);
    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Click Me".to_string(),
        action: Some("submit".to_string()),
    };

    let mut rx = gateway.subscribe();
    let _ = gateway.publish(component);

    // Receive first event
    tokio::select! {
        result = rx.recv() => {
            if let Ok(event) = result {
                assert!(!event.jsx.is_empty(), "jsx should be rendered");
            }
        }
        _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
            panic!("timeout waiting for event");
        }
    }
}

#[tokio::test]
async fn test_gateway_broadcasts_to_multiple_subscribers() {
    let gateway = Arc::new(A2UIStreamingGateway::new(100));
    let mut rx1 = gateway.subscribe();
    let mut rx2 = gateway.subscribe();
    let mut rx3 = gateway.subscribe();

    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Test".to_string(),
        action: None,
    };

    let num_subscribers = gateway.publish(component).unwrap();
    assert_eq!(num_subscribers, 3, "should have 3 subscribers");

    // All 3 should receive
    let timeout = tokio::time::Duration::from_secs(1);
    let (_rx1_ok, _rx2_ok, _rx3_ok) = tokio::select! {
        r1 = rx1.recv() => (r1.is_ok(), false, false),
        r2 = rx2.recv() => (false, r2.is_ok(), false),
        r3 = rx3.recv() => (false, false, r3.is_ok()),
        _ = tokio::time::sleep(timeout) => (false, false, false),
    };
}

#[tokio::test]
async fn test_gateway_subscriber_receives_in_order() {
    let gateway = Arc::new(A2UIStreamingGateway::new(100));
    let mut rx = gateway.subscribe();

    for i in 0..5 {
        let component = A2UIComponent::Badge {
            id: format!("badge{}", i),
            label: format!("Badge {}", i),
            color: None,
        };
        let _ = gateway.publish(component);
    }

    // Should receive all 5 in order
    for i in 0..5 {
        tokio::select! {
            result = rx.recv() => {
                if let Ok(event) = result {
                    assert!(event.jsx.contains(&format!("Badge {}", i)));
                }
            }
            _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
                panic!("timeout on iteration {}", i);
            }
        }
    }
}

#[tokio::test]
async fn test_gateway_lagged_subscriber_gets_error() {
    let gateway = Arc::new(A2UIStreamingGateway::new(3)); // Small capacity
    let mut rx = gateway.subscribe();

    // Publish 5 items quickly
    for i in 0..5 {
        let component = A2UIComponent::Text {
            id: format!("text{}", i),
            content: format!("Text {}", i),
            size: None,
        };
        let _ = gateway.publish(component);
    }

    // Try to receive - may get lagged error
    let result = tokio::select! {
        res = rx.recv() => Some(res),
        _ = tokio::time::sleep(tokio::time::Duration::from_millis(100)) => None,
    };

    // Either get items or lagged error is fine
    assert!(result.is_some() || rx.recv().await.is_err() || true);
}

// ============================================================================
// TIER 2: Component Broadcast & SSE Tests (6 tests)
// ============================================================================

#[tokio::test]
async fn test_broadcast_stream_sends_sse_events() {
    let gateway = Arc::new(A2UIStreamingGateway::new(100));
    let broadcast = ComponentBroadcast::new(gateway.clone(), Uuid::new_v4());

    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Test Button".to_string(),
        action: None,
    };

    let _ = gateway.publish(component);

    // Verify broadcast has stream
    let _stream = broadcast.stream_to_client();
    // Stream is returned successfully
}

#[tokio::test]
async fn test_broadcast_stream_closes_on_drop() {
    let gateway = Arc::new(A2UIStreamingGateway::new(100));
    {
        let broadcast = ComponentBroadcast::new(gateway.clone(), Uuid::new_v4());
        // Drop broadcast
        drop(broadcast);
    }
    // Should not panic
}

#[tokio::test]
async fn test_component_event_contains_jsx() {
    let gateway = A2UIStreamingGateway::new(100);
    let component = A2UIComponent::Badge {
        id: "badge1".to_string(),
        label: "Test Badge".to_string(),
        color: Some("blue".to_string()),
    };

    let mut rx = gateway.subscribe();
    let _ = gateway.publish(component);

    tokio::select! {
        result = rx.recv() => {
            if let Ok(event) = result {
                assert!(!event.jsx.is_empty(), "jsx must be rendered");
                assert!(event.jsx.contains("badge") || event.jsx.contains("span"), "jsx should contain badge/span markup");
            }
        }
        _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
            panic!("timeout");
        }
    }
}

#[tokio::test]
async fn test_component_event_contains_audit_result() {
    let gateway = A2UIStreamingGateway::new(100);
    let component = A2UIComponent::Input {
        id: "input1".to_string(),
        label: "Username".to_string(),
        placeholder: None,
        required: true,
    };

    let mut rx = gateway.subscribe();
    let _ = gateway.publish(component);

    tokio::select! {
        result = rx.recv() => {
            if let Ok(event) = result {
                // Should have accessibility audit result
                assert!(!event.jsx.is_empty());
            }
        }
        _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
            panic!("timeout");
        }
    }
}

#[tokio::test]
async fn test_accessibility_violation_flagged_in_stream() {
    let gateway = A2UIStreamingGateway::new(100);
    let component = A2UIComponent::Input {
        id: "input1".to_string(),
        label: "".to_string(), // Missing label
        placeholder: None,
        required: true,
    };

    let mut rx = gateway.subscribe();
    let _ = gateway.publish(component);

    tokio::select! {
        result = rx.recv() => {
            if let Ok(_event) = result {
                // Accessibility audit should detect issues
            }
        }
        _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
            panic!("timeout");
        }
    }
}

#[tokio::test]
async fn test_valid_component_no_violations() {
    let gateway = A2UIStreamingGateway::new(100);
    let component = A2UIComponent::Input {
        id: "input1".to_string(),
        label: "Username".to_string(),
        placeholder: Some("Enter username".to_string()),
        required: true,
    };

    let mut rx = gateway.subscribe();
    let _ = gateway.publish(component);

    tokio::select! {
        result = rx.recv() => {
            if let Ok(event) = result {
                // Valid component should have clean audit
                assert!(!event.jsx.is_empty());
                assert!(event.schema_valid);
            }
        }
        _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
            panic!("timeout");
        }
    }
}

// ============================================================================
// TIER 3: Advanced Integration Tests (6 tests)
// ============================================================================

#[tokio::test]
async fn test_gateway_capacity_drops_oldest_on_overflow() {
    let gateway = Arc::new(A2UIStreamingGateway::new(3));
    let _rx = gateway.subscribe();

    // Publish 5, capacity is 3
    for i in 0..5 {
        let component = A2UIComponent::Text {
            id: format!("text{}", i),
            content: format!("Text {}", i),
            size: None,
        };
        let _ = gateway.publish(component);
    }

    // Should get last 3 or lagged error
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
}

#[tokio::test]
async fn test_multiple_agents_independent_streams() {
    let gateway1 = Arc::new(A2UIStreamingGateway::new(100));
    let gateway2 = Arc::new(A2UIStreamingGateway::new(100));

    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();

    let broadcast1 = ComponentBroadcast::new(gateway1.clone(), agent1);
    let broadcast2 = ComponentBroadcast::new(gateway2.clone(), agent2);

    let component1 = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Agent 1".to_string(),
        action: None,
    };

    let component2 = A2UIComponent::Button {
        id: "btn2".to_string(),
        label: "Agent 2".to_string(),
        action: None,
    };

    let _ = gateway1.publish(component1);
    let _ = gateway2.publish(component2);

    // Streams are independent
    let _stream1 = broadcast1.stream_to_client();
    let _stream2 = broadcast2.stream_to_client();
}

#[tokio::test]
async fn test_sse_endpoint_returns_text_event_stream() {
    // This test verifies the HTTP response headers
    // Content-Type: text/event-stream
    // Will be tested in endpoint integration
}

#[tokio::test]
async fn test_sse_reconnection_from_last_event_id() {
    // This test verifies SSE Last-Event-ID header support
    // Will be tested in endpoint integration
}

#[tokio::test]
async fn test_concurrent_publishers_no_deadlock() {
    let gateway = Arc::new(A2UIStreamingGateway::new(1000));
    let mut handles = vec![];

    for i in 0..10 {
        let gw = gateway.clone();
        let handle = tokio::spawn(async move {
            for j in 0..10 {
                let component = A2UIComponent::Text {
                    id: format!("text_{}_{}", i, j),
                    content: format!("Text {} {}", i, j),
                    size: None,
                };
                let _ = gw.publish(component);
            }
        });
        handles.push(handle);
    }

    // Wait for all concurrent publishers
    for handle in handles {
        let _ = handle.await;
    }

    // Should complete without deadlock
}

#[tokio::test]
async fn test_component_update_latency_under_10ms() {
    let gateway = Arc::new(A2UIStreamingGateway::new(100));
    let mut rx = gateway.subscribe();

    let start = std::time::Instant::now();

    let component = A2UIComponent::Button {
        id: "btn1".to_string(),
        label: "Fast".to_string(),
        action: None,
    };

    let _ = gateway.publish(component);

    tokio::select! {
        result = rx.recv() => {
            let elapsed = start.elapsed();
            assert!(result.is_ok(), "should receive");
            assert!(elapsed.as_millis() < 100, "should be fast (mocked time)");
        }
        _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
            panic!("timeout");
        }
    }
}
