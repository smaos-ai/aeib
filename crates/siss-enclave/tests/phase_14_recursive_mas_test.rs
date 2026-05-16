use siss_enclave::memory::{ConsolidatedEntry, GrayFog, ObservationTier, ZonalMemory};
use siss_enclave::swarm::{
    A2ATask, A2ATaskStatus, RecursiveMasDispatcher, SwarmAgentCard, SwarmCapabilities, SwarmError,
    SwarmSkill, SwarmWorker, WorkerResult,
};
use uuid::Uuid;

#[test]
fn test_swarm_agent_card_serializes_correctly() {
    let card = SwarmAgentCard {
        agent_id: Uuid::new_v4(),
        name: "TestAgent".to_string(),
        version: "1.0".to_string(),
        url: "http://localhost:8080".to_string(),
        skills: vec![SwarmSkill {
            id: "test_skill".to_string(),
            name: "Test Skill".to_string(),
            description: "A test skill".to_string(),
        }],
        capabilities: SwarmCapabilities {
            can_stream: true,
            can_push_notifications: false,
        },
    };

    let json = serde_json::to_string(&card).expect("serialize failed");
    let parsed: serde_json::Value = serde_json::from_str(&json).expect("parse failed");

    assert_eq!(parsed["capabilities"]["canStream"], true);
    assert_eq!(parsed["capabilities"]["canPushNotifications"], false);

    let deserialized: SwarmAgentCard = serde_json::from_str(&json).expect("deserialize failed");
    assert_eq!(card, deserialized);
}

#[test]
fn test_a2a_task_carries_only_uuid_refs() {
    let task = A2ATask {
        task_id: Uuid::new_v4(),
        root_agent_id: Uuid::new_v4(),
        worker_agent_id: Uuid::new_v4(),
        context_refs: vec![Uuid::new_v4(), Uuid::new_v4()],
        skill_id: "summarize".to_string(),
        token_budget: 100,
    };

    let json = serde_json::to_string(&task).expect("serialize failed");
    let parsed: serde_json::Value = serde_json::from_str(&json).expect("parse failed");

    assert!(parsed["context_refs"].is_array());
    assert_eq!(parsed["context_refs"].as_array().unwrap().len(), 2);

    assert!(parsed.get("content").is_none());
    assert!(parsed.get("tokens").is_none());
}

#[tokio::test]
async fn test_dispatcher_routes_to_correct_worker_by_skill_id() {
    let zonal = std::sync::Arc::new(ZonalMemory::new(10, 100, 0.95, 100));
    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());

    let worker_summarize = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "Summarizer".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "summarize".to_string(),
                name: "Summarize".to_string(),
                description: "Summarizes content".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: std::sync::Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: None,
                    error: None,
                }
            })
        }),
    };

    let worker_classify = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "Classifier".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8081".to_string(),
            skills: vec![SwarmSkill {
                id: "classify".to_string(),
                name: "Classify".to_string(),
                description: "Classifies content".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: std::sync::Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: None,
                    error: None,
                }
            })
        }),
    };

    dispatcher.register_worker(worker_summarize).await;
    dispatcher.register_worker(worker_classify).await;

    let task_id_1 = dispatcher
        .dispatch("summarize", vec![], 100)
        .await
        .expect("dispatch summarize failed");
    let task_id_2 = dispatcher
        .dispatch("classify", vec![], 100)
        .await
        .expect("dispatch classify failed");

    assert_ne!(
        task_id_1, task_id_2,
        "Different skills should generate different task IDs"
    );
}

#[tokio::test]
async fn test_unknown_skill_returns_error_immediately() {
    let zonal = std::sync::Arc::new(ZonalMemory::new(10, 100, 0.95, 100));
    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());

    let result = dispatcher.dispatch("nonexistent", vec![], 100).await;

    assert!(result.is_err());
    match result {
        Err(SwarmError::UnknownSkill(skill)) => {
            assert_eq!(skill, "nonexistent");
        }
        _ => panic!("Expected UnknownSkill error"),
    }
}

#[tokio::test]
async fn test_dispatch_projects_only_referenced_uuids_not_full_fog() {
    let mut layers = std::collections::HashMap::new();
    let entry_ids: Vec<Uuid> = (0..5).map(|_| Uuid::new_v4()).collect();

    let entries: Vec<ConsolidatedEntry> = entry_ids
        .iter()
        .map(|&id| ConsolidatedEntry {
            id,
            content: format!("entry_{}", id),
            confidence: 0.8,
            tier: ObservationTier::Semantic,
            token_count: 50,
        })
        .collect();

    layers.insert(ObservationTier::Semantic, entries.clone());

    let fog = GrayFog { layers };
    let zonal = std::sync::Arc::new(ZonalMemory::with_fog(fog, 10));

    let expected_count = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let expected_count_clone = expected_count.clone();

    let worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "Pruner".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "test_pruning".to_string(),
                name: "Test Pruning".to_string(),
                description: "Tests pruning".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: std::sync::Arc::new(move |entries: Vec<ConsolidatedEntry>| {
            let count = entries.len();
            expected_count_clone.store(count, std::sync::atomic::Ordering::SeqCst);
            Box::pin(async {
                WorkerResult {
                    artifact: None,
                    error: None,
                }
            })
        }),
    };

    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());
    dispatcher.register_worker(worker).await;

    let context_refs = vec![entry_ids[0], entry_ids[2]];
    dispatcher
        .dispatch("test_pruning", context_refs, 200)
        .await
        .expect("dispatch failed");

    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

    assert_eq!(
        expected_count.load(std::sync::atomic::Ordering::SeqCst),
        2,
        "Dispatcher should materialize only referenced UUIDs from Gray Fog"
    );
}

#[tokio::test]
async fn test_dispatch_broadcasts_lifecycle_sse_events() {
    let zonal = std::sync::Arc::new(ZonalMemory::new(10, 100, 0.95, 100));
    let (dispatcher, mut subscriber) = RecursiveMasDispatcher::new(zonal, Uuid::new_v4());

    let worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "EventWorker".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "event_test".to_string(),
                name: "Event Test".to_string(),
                description: "Tests events".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: std::sync::Arc::new(|_| {
            Box::pin(async {
                WorkerResult {
                    artifact: None,
                    error: None,
                }
            })
        }),
    };

    dispatcher.register_worker(worker).await;

    let task_id = dispatcher
        .dispatch("event_test", vec![], 100)
        .await
        .expect("dispatch failed");

    let mut events = vec![];
    let mut attempts = 0;
    while attempts < 50 && events.len() < 3 {
        match tokio::time::timeout(tokio::time::Duration::from_millis(10), subscriber.recv()).await
        {
            Ok(Ok(event)) => events.push(event),
            _ => {}
        }
        attempts += 1;
    }

    assert!(
        events.len() >= 3,
        "Expected at least 3 lifecycle events, got {}",
        events.len()
    );

    assert_eq!(events[0].task_id, task_id);
    assert_eq!(events[0].status, A2ATaskStatus::Pending);

    assert_eq!(events[1].task_id, task_id);
    assert_eq!(events[1].status, A2ATaskStatus::Running);

    assert_eq!(events[2].task_id, task_id);
    assert_eq!(events[2].status, A2ATaskStatus::Completed);
}

#[tokio::test]
async fn test_worker_artifact_written_to_gray_fog() {
    let zonal = std::sync::Arc::new(ZonalMemory::new(10, 100, 0.95, 100));
    let (dispatcher, _sub) = RecursiveMasDispatcher::new(zonal.clone(), Uuid::new_v4());

    let artifact_content = "artifact_result_content";
    let artifact_content_clone = artifact_content.to_string();

    let worker = SwarmWorker {
        card: SwarmAgentCard {
            agent_id: Uuid::new_v4(),
            name: "ArtifactWorker".to_string(),
            version: "1.0".to_string(),
            url: "http://localhost:8080".to_string(),
            skills: vec![SwarmSkill {
                id: "artifact_test".to_string(),
                name: "Artifact Test".to_string(),
                description: "Tests artifacts".to_string(),
            }],
            capabilities: SwarmCapabilities {
                can_stream: false,
                can_push_notifications: false,
            },
        },
        handler: std::sync::Arc::new(move |_| {
            let content = artifact_content_clone.clone();
            Box::pin(async move {
                WorkerResult {
                    artifact: Some(ConsolidatedEntry {
                        id: Uuid::new_v4(),
                        content,
                        confidence: 0.95,
                        tier: ObservationTier::Semantic,
                        token_count: 50,
                    }),
                    error: None,
                }
            })
        }),
    };

    dispatcher.register_worker(worker).await;

    dispatcher
        .dispatch("artifact_test", vec![], 100)
        .await
        .expect("dispatch failed");

    tokio::time::sleep(tokio::time::Duration::from_millis(250)).await;

    let snapshot = zonal.fog_snapshot();
    let all_entries: Vec<_> = snapshot
        .layers
        .values()
        .flat_map(|entries| entries.iter())
        .filter(|e| e.content == artifact_content)
        .collect();

    assert!(
        !all_entries.is_empty(),
        "Artifact should be written back to Gray Fog"
    );
    assert_eq!(all_entries[0].content, artifact_content);
    assert_eq!(all_entries[0].confidence, 0.95);
}
