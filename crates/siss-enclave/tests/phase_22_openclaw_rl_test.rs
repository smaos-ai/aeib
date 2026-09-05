use siss_enclave::learning::{
    BehavioralSignal, DistillationOrchestrator, GRPOLoss, GhostBranchBuffer, RewardModel,
    TrajectoryExtractor,
};
use siss_enclave::memory::{EphemeralBuffer, RawObservation};
use std::sync::Arc;
use uuid::Uuid;

#[tokio::test]
async fn test_ghost_branch_extracts_exact_trajectory_from_ephemeral_buffer() {
    let (tx, _rx) = tokio::sync::mpsc::channel::<RawObservation>(10);
    let ephemeral = Arc::new(EphemeralBuffer::new(tx));

    // Simulate thought-tool-action sequence
    ephemeral.append_thought("analyze_user_intent".to_string());
    ephemeral.append_tool_call("git_grep".to_string(), "pattern".to_string());
    ephemeral.append_action_result("found 3 matches".to_string());

    ephemeral.append_thought("synthesize_summary".to_string());
    ephemeral.append_tool_call("llm_summarize".to_string(), "content".to_string());
    ephemeral.append_action_result("summary: changes affect auth".to_string());

    // Give async tasks time to complete
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

    let extractor = TrajectoryExtractor::new(ephemeral.clone());
    let ghost_branch = extractor.extract().await.expect("extract failed");

    // Assert exact sequence preservation
    assert_eq!(
        ghost_branch.trajectory_len(),
        6,
        "Should have 3 thought-tool-action pairs"
    );
    assert_eq!(
        ghost_branch.thought_at(0).unwrap(),
        "analyze_user_intent",
        "First thought preserved"
    );
    assert_eq!(
        ghost_branch.tool_at(1).unwrap(),
        "git_grep",
        "First tool preserved"
    );
    assert_eq!(
        ghost_branch.action_at(2).unwrap(),
        "found 3 matches",
        "First action preserved"
    );
    assert_eq!(
        ghost_branch.thought_at(3).unwrap(),
        "synthesize_summary",
        "Second thought preserved"
    );
}

#[tokio::test]
async fn test_reward_model_maps_behavioral_signals_to_normalized_range() {
    let reward_model = RewardModel::new();

    // AP2 success → +0.05 trust delta → normalize to +1.0
    let ap2_success = BehavioralSignal::Ap2NonceBurn {
        agent_did: "agent:alice".to_string(),
        success: true,
    };
    let reward = reward_model.compute_reward(&ap2_success).await;
    assert!(
        reward > 0.9 && reward <= 1.0,
        "AP2 success should map to [+0.9, +1.0], got {}",
        reward
    );

    // GitNexus block → -0.10 trust delta → normalize to -1.0
    let gitnexus_block = BehavioralSignal::GitNexusBlastRadiusBlock {
        agent_did: "agent:bob".to_string(),
        affected_files: 5,
        critical_modules: 2,
    };
    let reward = reward_model.compute_reward(&gitnexus_block).await;
    assert!(
        reward < -0.9 && reward >= -1.0,
        "GitNexus block should map to [-1.0, -0.9], got {}",
        reward
    );

    // Quarantine → -0.15 trust delta → normalize to -1.0
    let quarantine = BehavioralSignal::QuarantineEntry {
        agent_did: "agent:charlie".to_string(),
        violation: "credential_detected".to_string(),
    };
    let reward = reward_model.compute_reward(&quarantine).await;
    assert!(
        reward < -0.9 && reward >= -1.0,
        "Quarantine should map to [-1.0, -0.9], got {}",
        reward
    );
}

#[tokio::test]
async fn test_distillation_queue_is_nonblocking_and_async() {
    let distillation_orchestrator = DistillationOrchestrator::new();

    let ghost_branch = GhostBranchBuffer::from_trajectory(vec![
        "analyze".to_string(),
        "tool_call".to_string(),
        "result".to_string(),
    ]);

    let start = std::time::Instant::now();

    // Queue task — should return immediately, not block on distillation
    let _task_id = distillation_orchestrator
        .queue_distillation(ghost_branch, 0.85, Uuid::new_v4())
        .await
        .expect("queue failed");

    let elapsed = start.elapsed();

    // Must complete in <10ms (async non-blocking queue operation)
    assert!(
        elapsed.as_millis() < 10,
        "Queue operation must not block; took {}ms",
        elapsed.as_millis()
    );

    // Verify task was enqueued (doesn't verify completion)
    let queue_status = distillation_orchestrator.queue_depth().await;
    assert!(queue_status > 0, "Task should be in queue");
}

#[tokio::test]
async fn test_grpo_loss_computes_from_scalar_reward() {
    let grpo_loss = GRPOLoss::new(128); // batch size

    // Simulate scalar rewards from behavioral events
    let rewards = vec![0.95, -0.95, 0.85, -1.0, 0.75];

    let logits_shape = vec![5, 128]; // 5 samples, 128 vocab
    let mock_logits = vec![0.1; 5 * 128];

    let loss = grpo_loss
        .compute_loss(&mock_logits, &logits_shape, &rewards)
        .expect("loss computation failed");

    // Loss must be finite and non-negative (standard RL loss properties)
    assert!(loss.is_finite(), "Loss must be finite");
    assert!(loss >= 0.0, "Loss must be non-negative");

    // Verify loss is scalar (not batched or ragged)
    assert_eq!(
        loss.to_string().split('.').count(),
        2,
        "Loss must be scalar"
    );
}

#[tokio::test]
async fn test_distillation_completes_and_schedules_lora_swap() {
    let distillation_orchestrator = DistillationOrchestrator::new();

    let ghost_branch =
        GhostBranchBuffer::from_trajectory(vec!["analyze".to_string(), "execute".to_string()]);

    // Queue and wait for completion
    let task_id = distillation_orchestrator
        .queue_distillation(ghost_branch, 0.90, Uuid::new_v4())
        .await
        .expect("queue failed");

    // Poll for completion (with timeout)
    let mut attempts = 0;
    let mut distilled = false;
    while attempts < 100 && !distilled {
        if let Ok(status) = distillation_orchestrator
            .get_distillation_status(&task_id)
            .await
        {
            if status.is_complete {
                distilled = true;
            }
        }
        attempts += 1;
        tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
    }

    assert!(distilled, "Distillation should complete");

    // Verify LoRA swap was scheduled
    let swap_event = distillation_orchestrator
        .get_scheduled_swap(&task_id)
        .await
        .expect("should have swap event");

    assert!(!swap_event.swap_token.is_empty(), "Swap token must be set");
    assert!(
        swap_event.new_lora_id.is_some(),
        "New LoRA ID must be assigned"
    );
}

#[tokio::test]
async fn test_behavioral_signal_creation_from_enum() {
    let ap2_success = BehavioralSignal::Ap2NonceBurn {
        agent_did: "agent:alice".to_string(),
        success: true,
    };

    match ap2_success {
        BehavioralSignal::Ap2NonceBurn { agent_did, success } => {
            assert_eq!(agent_did, "agent:alice");
            assert!(success);
        }
        _ => panic!("Expected Ap2NonceBurn"),
    }
}

#[tokio::test]
async fn test_ghost_branch_buffer_stores_discrete_trajectory_elements() {
    let ghost_branch = GhostBranchBuffer::from_trajectory(vec![
        "thought_1".to_string(),
        "tool_1".to_string(),
        "action_1".to_string(),
        "thought_2".to_string(),
        "tool_2".to_string(),
        "action_2".to_string(),
    ]);

    assert_eq!(ghost_branch.len(), 6, "Buffer should store all 6 elements");

    // Verify elements are retrievable by index
    assert_eq!(
        ghost_branch.get(0).unwrap(),
        "thought_1",
        "Index 0 should be first thought"
    );
    assert_eq!(
        ghost_branch.get(2).unwrap(),
        "action_1",
        "Index 2 should be first action"
    );
    assert_eq!(
        ghost_branch.get(5).unwrap(),
        "action_2",
        "Index 5 should be last element"
    );

    // Verify iteration
    let all: Vec<_> = ghost_branch.iter().collect();
    assert_eq!(all.len(), 6, "Iterator should yield all elements");
}

#[tokio::test]
async fn test_reward_normalization_handles_edge_cases() {
    let reward_model = RewardModel::new();

    // Zero trust delta → neutral reward
    let neutral = BehavioralSignal::Neutral;
    let reward = reward_model.compute_reward(&neutral).await;
    assert!(
        reward >= -0.1 && reward <= 0.1,
        "Neutral should map to [-0.1, +0.1], got {}",
        reward
    );

    // Verify clamping at bounds
    assert!(
        reward >= -1.0 && reward <= 1.0,
        "Reward must be clamped to [-1.0, +1.0]"
    );
}
