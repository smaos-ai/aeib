use siss_enclave::eval::agent_judge::{AgentJudge, EvaluationRequest};
use std::time::Duration;
use tokio::sync::mpsc;

#[tokio::test]
async fn test_judge_rejects_high_divergence() {
    let (tx, rx) = mpsc::channel(10);
    let mut judge = AgentJudge::new(rx, Duration::from_secs(5));

    // divergence >= 0.15 should fail
    let req = EvaluationRequest {
        divergence: 0.16,
        f1_score: 1.0,
    };
    tx.send(req).await.unwrap();

    let result = judge.evaluate_next().await.unwrap();
    assert_eq!(result.accepted, false, "Must reject divergence >= 0.15");
}

#[tokio::test]
async fn test_judge_rejects_low_f1_score() {
    let (tx, rx) = mpsc::channel(10);
    let mut judge = AgentJudge::new(rx, Duration::from_secs(5));

    // F1 score dropping below baseline (e.g., < 0.95) should fail
    let req = EvaluationRequest {
        divergence: 0.05,
        f1_score: 0.80,
    };
    tx.send(req).await.unwrap();

    let result = judge.evaluate_next().await.unwrap();
    assert_eq!(result.accepted, false, "Must reject F1 score regression");
}

#[tokio::test]
async fn test_judge_timeout_fails_closed() {
    let (_tx, rx) = mpsc::channel(10);
    // Aggressive timeout for test
    let mut judge = AgentJudge::new(rx, Duration::from_millis(10));

    // No message sent, channel stays open, judge should timeout and fail closed
    let result = judge.evaluate_next().await.unwrap();
    assert_eq!(
        result.accepted, false,
        "Must fail-closed on evaluation timeout"
    );
}
