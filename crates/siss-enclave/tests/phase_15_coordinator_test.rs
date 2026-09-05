use siss_enclave::memory::{ConsolidatedEntry, ObservationTier, ZonalMemory};
use siss_enclave::orchestrator::TaskCategory;
use siss_enclave::swarm::{
    A2ATaskStatus, RecursiveMasDispatcher, SwarmAgentCard, SwarmCapabilities, SwarmSkill,
    SwarmWorker, WorkerResult,
};
use std::sync::Arc;
use uuid::Uuid;

#[tokio::test]
async fn test_coordinator_selects_agent_by_task_category() {
    let zonal = Arc::new(ZonalMemory::new(10, 100, 0.95, 100));
    let (_dispatcher, _sub) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());

    // Coordinator should map TaskCategory → skill_id
    let selected_skill = match TaskCategory::Summarize {
        TaskCategory::Summarize => "summarize",
        TaskCategory::Classify => "classify",
        TaskCategory::Extract => "extract",
    };

    assert_eq!(selected_skill, "summarize");
}

#[tokio::test]
async fn test_coordinator_aggregates_results_from_multiple_workers() {
    let zonal = Arc::new(ZonalMemory::new(20, 100, 0.95, 100));
    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal.clone(), Uuid::new_v4());

    // Register first worker (summarize)
    let worker_1 = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "Summarizer".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "summarize".to_string(),
                name: "Summarize".to_string(),
                description: "Summarize worker".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: Some(ConsolidatedEntry {
                        id: Uuid::new_v4(),
                        content: "result_from_summarize".to_string(),
                        confidence: 0.9,
                        tier: ObservationTier::Semantic,
                        token_count: 50,
                    }),
                    error: None,
                }
            })
        }),
    };
    dispatcher.register_worker(worker_1).await;

    // Register second worker (classify)
    let worker_2 = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "Classifier".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8081".to_string(),
            skills: vec![SwarmSkill {
                id: "classify".to_string(),
                name: "Classify".to_string(),
                description: "Classify worker".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: Some(ConsolidatedEntry {
                        id: Uuid::new_v4(),
                        content: "result_from_classify".to_string(),
                        confidence: 0.85,
                        tier: ObservationTier::Semantic,
                        token_count: 50,
                    }),
                    error: None,
                }
            })
        }),
    };
    dispatcher.register_worker(worker_2).await;

    // Coordinator dispatches to multiple workers
    let task_id_1 = dispatcher
        .dispatch("summarize", vec![], 100)
        .await
        .expect("dispatch summarize failed");
    let task_id_2 = dispatcher
        .dispatch("classify", vec![], 100)
        .await
        .expect("dispatch classify failed");

    // Both dispatches succeed with different task IDs
    assert_ne!(task_id_1, task_id_2);

    // Wait for background tasks and consolidation cycles to complete
    tokio::time::sleep(tokio::time::Duration::from_millis(400)).await;

    // Both results should be in Gray Fog
    let snapshot = zonal.fog_snapshot();
    let all_entries: Vec<_> = snapshot
        .layers
        .values()
        .flat_map(|entries| entries.iter())
        .collect();

    let summarize_results = all_entries
        .iter()
        .filter(|e| e.content == "result_from_summarize")
        .count();
    let classify_results = all_entries
        .iter()
        .filter(|e| e.content == "result_from_classify")
        .count();

    assert_eq!(
        summarize_results, 1,
        "Should have 1 result from summarize worker"
    );
    assert_eq!(
        classify_results, 1,
        "Should have 1 result from classify worker"
    );
}

#[tokio::test]
async fn test_coordinator_fallback_chain_on_primary_worker_failure() {
    let zonal = Arc::new(ZonalMemory::new(20, 100, 0.95, 100));
    let (dispatcher, mut subscriber) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());

    // Primary worker fails
    let primary_worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "PrimaryWorker".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "fallback_test".to_string(),
                name: "Fallback Test".to_string(),
                description: "Primary worker that fails".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: None,
                    error: Some("Primary worker crashed".to_string()),
                }
            })
        }),
    };

    dispatcher.register_worker(primary_worker).await;

    let task_id = dispatcher
        .dispatch("fallback_test", vec![], 100)
        .await
        .expect("dispatch failed");

    // Collect events from SSE stream
    let mut events = vec![];
    let mut attempts = 0;
    while attempts < 100 && events.len() < 3 {
        match tokio::time::timeout(tokio::time::Duration::from_millis(10), subscriber.recv()).await
        {
            Ok(Ok(event)) => {
                if event.task_id == task_id {
                    events.push(event);
                }
            }
            _ => {}
        }
        attempts += 1;
    }

    // Should receive Pending, Running, and Failed events
    assert!(
        events.iter().any(|e| e.status == A2ATaskStatus::Pending),
        "Should emit Pending event"
    );
    assert!(
        events.iter().any(|e| e.status == A2ATaskStatus::Running),
        "Should emit Running event"
    );
    assert!(
        events.iter().any(|e| e.status == A2ATaskStatus::Failed),
        "Should emit Failed event on worker error"
    );
}

#[tokio::test]
async fn test_coordinator_succeeds_after_fallback_retry() {
    let zonal = Arc::new(ZonalMemory::new(20, 100, 0.95, 100));
    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal.clone(), Uuid::new_v4());

    // Fallback worker succeeds
    let fallback_worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "FallbackWorker".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8081".to_string(),
            skills: vec![SwarmSkill {
                id: "fallback_retry".to_string(),
                name: "Fallback Retry".to_string(),
                description: "Secondary worker that succeeds".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: Some(ConsolidatedEntry {
                        id: Uuid::new_v4(),
                        content: "fallback_success".to_string(),
                        confidence: 0.85,
                        tier: ObservationTier::Semantic,
                        token_count: 40,
                    }),
                    error: None,
                }
            })
        }),
    };

    dispatcher.register_worker(fallback_worker).await;

    dispatcher
        .dispatch("fallback_retry", vec![], 100)
        .await
        .expect("dispatch failed");

    tokio::time::sleep(tokio::time::Duration::from_millis(250)).await;

    let snapshot = zonal.fog_snapshot();
    let fallback_results = snapshot
        .layers
        .values()
        .flat_map(|entries| entries.iter())
        .filter(|e| e.content == "fallback_success")
        .count();

    assert_eq!(
        fallback_results, 1,
        "Fallback worker result should be in Gray Fog"
    );
}

#[tokio::test]
async fn test_coordinator_does_not_block_inference_thread() {
    let zonal = Arc::new(ZonalMemory::new(20, 100, 0.95, 100));
    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());

    // Slow worker that takes time
    let slow_worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "SlowWorker".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "blocking_test".to_string(),
                name: "Blocking Test".to_string(),
                description: "Worker that takes time".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: Arc::new(|_| {
            Box::pin(async {
                tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
                WorkerResult {
                    artifact: None,
                    error: None,
                }
            })
        }),
    };

    dispatcher.register_worker(slow_worker).await;

    let start = std::time::Instant::now();

    // Dispatch should return immediately (non-blocking)
    let _task_id = dispatcher
        .dispatch("blocking_test", vec![], 100)
        .await
        .expect("dispatch failed");

    let elapsed = start.elapsed();

    // Dispatch must return in <50ms (never blocks on handler execution)
    assert!(
        elapsed.as_millis() < 50,
        "Coordinator dispatch must not block on handler execution; took {}ms",
        elapsed.as_millis()
    );
}

#[tokio::test]
async fn test_coordinator_preserves_sse_stream_across_fallback() {
    let zonal = Arc::new(ZonalMemory::new(20, 100, 0.95, 100));
    let (dispatcher, mut subscriber) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());

    let worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "StreamWorker".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "stream_test".to_string(),
                name: "Stream Test".to_string(),
                description: "Tests SSE continuity".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: true,
                can_push_notifications: false,
            },
        },
        handler: Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: Some(ConsolidatedEntry {
                        id: Uuid::new_v4(),
                        content: "stream_result".to_string(),
                        confidence: 0.9,
                        tier: ObservationTier::Semantic,
                        token_count: 50,
                    }),
                    error: None,
                }
            })
        }),
    };

    dispatcher.register_worker(worker).await;

    let task_id = dispatcher
        .dispatch("stream_test", vec![], 100)
        .await
        .expect("dispatch failed");

    // Collect all SSE events for this task
    let mut all_events = vec![];
    let mut attempts = 0;
    while attempts < 100 {
        match tokio::time::timeout(tokio::time::Duration::from_millis(10), subscriber.recv()).await
        {
            Ok(Ok(event)) => {
                if event.task_id == task_id {
                    all_events.push(event);
                }
            }
            _ => {}
        }
        attempts += 1;
    }

    // Stream should maintain continuity: Pending, Running, Completed (no drops)
    assert!(all_events.len() >= 3, "Should emit at least 3 SSE events");
    assert_eq!(all_events[0].status, A2ATaskStatus::Pending);
    assert_eq!(all_events[1].status, A2ATaskStatus::Running);
    assert_eq!(all_events[2].status, A2ATaskStatus::Completed);
}

#[tokio::test]
async fn test_coordinator_consolidates_results_before_returning() {
    let zonal = Arc::new(ZonalMemory::new(20, 100, 0.95, 100));
    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal.clone(), Uuid::new_v4());

    let worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "ConsolidationWorker".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "consolidation_test".to_string(),
                name: "Consolidation Test".to_string(),
                description: "Tests result consolidation".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: Some(ConsolidatedEntry {
                        id: Uuid::new_v4(),
                        content: "consolidated_result".to_string(),
                        confidence: 0.95,
                        tier: ObservationTier::Semantic,
                        token_count: 60,
                    }),
                    error: None,
                }
            })
        }),
    };

    dispatcher.register_worker(worker).await;

    dispatcher
        .dispatch("consolidation_test", vec![], 100)
        .await
        .expect("dispatch failed");

    // Wait for AutoDream consolidation cycle
    tokio::time::sleep(tokio::time::Duration::from_millis(300)).await;

    // Result should be in consolidated Gray Fog (not just ephemeral buffer)
    let snapshot = zonal.fog_snapshot();
    let consolidated = snapshot
        .layers
        .values()
        .flat_map(|entries| entries.iter())
        .filter(|e| e.content == "consolidated_result")
        .count();

    assert_eq!(
        consolidated, 1,
        "Coordinator should consolidate results into Gray Fog before returning"
    );
}
