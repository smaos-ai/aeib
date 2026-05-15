use siss_enclave::{
    eval::agent_judge::{AgentJudge, EvaluationRequest},
    model::modality::{Modality, PerModalityScores},
    orchestrator::evolution_gate::Judge,
};
use std::time::Duration;
use tokio::sync::mpsc;

#[tokio::test]
async fn test_all_five_pillars_pass() {
    let (tx, rx) = mpsc::channel(10);
    let judge: Box<dyn Judge> = Box::new(AgentJudge::new(rx, Duration::from_secs(1)));

    let request = EvaluationRequest {
        divergence: 0.10,
        f1_score: 0.90,
        robustness_score: 0.95,
        alignment_score: 0.85,
        corebench_score: 0.80,
        per_modality: vec![
            PerModalityScores {
                modality: Modality::Text,
                divergence: 0.05,
                f1_score: 0.95,
                robustness: 0.95,
                alignment: 0.85,
                corebench: 0.80,
            },
            PerModalityScores {
                modality: Modality::Vision,
                divergence: 0.08,
                f1_score: 0.92,
                robustness: 0.91,
                alignment: 0.81,
                corebench: 0.76,
            },
            PerModalityScores {
                modality: Modality::Audio,
                divergence: 0.12,
                f1_score: 0.88,
                robustness: 0.92,
                alignment: 0.82,
                corebench: 0.78,
            },
        ],
    };

    tokio::spawn(async move {
        let _ = tx.send(request).await;
    });

    let verdict = judge.evaluate_next().await.unwrap();
    assert!(verdict.pass, "All pillars pass: verdict should be true");
    assert_eq!(
        verdict.approved_for_modalities.len(),
        3,
        "All three modalities should be approved"
    );
    assert!(verdict.approved_for_modalities.contains(&Modality::Text));
    assert!(verdict.approved_for_modalities.contains(&Modality::Vision));
    assert!(verdict.approved_for_modalities.contains(&Modality::Audio));
}

#[tokio::test]
async fn test_robustness_pillar_blocks_swap() {
    let (tx, rx) = mpsc::channel(10);
    let judge: Box<dyn Judge> = Box::new(AgentJudge::new(rx, Duration::from_secs(1)));

    let request = EvaluationRequest {
        divergence: 0.10,
        f1_score: 0.90,
        robustness_score: 0.89, // below 0.90 threshold
        alignment_score: 0.85,
        corebench_score: 0.80,
        per_modality: vec![],
    };

    tokio::spawn(async move {
        let _ = tx.send(request).await;
    });

    let verdict = judge.evaluate_next().await.unwrap();
    assert!(
        !verdict.pass,
        "Robustness below threshold: verdict should be false"
    );
    assert!(
        verdict.reason.to_lowercase().contains("robustness"),
        "Reason should mention robustness"
    );
}

#[tokio::test]
async fn test_alignment_pillar_blocks_swap() {
    let (tx, rx) = mpsc::channel(10);
    let judge: Box<dyn Judge> = Box::new(AgentJudge::new(rx, Duration::from_secs(1)));

    let request = EvaluationRequest {
        divergence: 0.10,
        f1_score: 0.90,
        robustness_score: 0.95,
        alignment_score: 0.79, // below 0.80 threshold
        corebench_score: 0.80,
        per_modality: vec![],
    };

    tokio::spawn(async move {
        let _ = tx.send(request).await;
    });

    let verdict = judge.evaluate_next().await.unwrap();
    assert!(
        !verdict.pass,
        "Alignment below threshold: verdict should be false"
    );
    assert!(
        verdict.reason.to_lowercase().contains("alignment"),
        "Reason should mention alignment"
    );
}

#[tokio::test]
async fn test_corebench_pillar_blocks_swap() {
    let (tx, rx) = mpsc::channel(10);
    let judge: Box<dyn Judge> = Box::new(AgentJudge::new(rx, Duration::from_secs(1)));

    let request = EvaluationRequest {
        divergence: 0.10,
        f1_score: 0.90,
        robustness_score: 0.95,
        alignment_score: 0.85,
        corebench_score: 0.74, // below 0.75 threshold
        per_modality: vec![],
    };

    tokio::spawn(async move {
        let _ = tx.send(request).await;
    });

    let verdict = judge.evaluate_next().await.unwrap();
    assert!(
        !verdict.pass,
        "CoReBench below threshold: verdict should be false"
    );
    assert!(
        verdict.reason.to_lowercase().contains("corebench"),
        "Reason should mention corebench"
    );
}

#[tokio::test]
async fn test_per_modality_partial_approval() {
    let (tx, rx) = mpsc::channel(10);
    let judge: Box<dyn Judge> = Box::new(AgentJudge::new(rx, Duration::from_secs(1)));

    let request = EvaluationRequest {
        divergence: 0.10,
        f1_score: 0.90,
        robustness_score: 0.95,
        alignment_score: 0.85,
        corebench_score: 0.80,
        per_modality: vec![
            PerModalityScores {
                modality: Modality::Text,
                divergence: 0.05,
                f1_score: 0.95,
                robustness: 0.95,
                alignment: 0.85,
                corebench: 0.80,
            },
            PerModalityScores {
                modality: Modality::Vision,
                divergence: 0.10,
                f1_score: 0.92,
                robustness: 0.91,
                alignment: 0.50, // below 0.80 threshold
                corebench: 0.76,
            },
        ],
    };

    tokio::spawn(async move {
        let _ = tx.send(request).await;
    });

    let verdict = judge.evaluate_next().await.unwrap();
    assert!(verdict.pass, "Global pillars pass: verdict should be true");
    assert_eq!(
        verdict.approved_for_modalities.len(),
        1,
        "Only Text modality should be approved"
    );
    assert!(verdict.approved_for_modalities.contains(&Modality::Text));
    assert!(!verdict.approved_for_modalities.contains(&Modality::Vision));
}

#[tokio::test]
async fn test_verdict_propagates_approved_modalities() {
    let (tx, rx) = mpsc::channel(10);
    let judge: Box<dyn Judge> = Box::new(AgentJudge::new(rx, Duration::from_secs(1)));

    let request = EvaluationRequest {
        divergence: 0.10,
        f1_score: 0.90,
        robustness_score: 0.95,
        alignment_score: 0.85,
        corebench_score: 0.80,
        per_modality: vec![PerModalityScores {
            modality: Modality::Audio,
            divergence: 0.12,
            f1_score: 0.88,
            robustness: 0.92,
            alignment: 0.82,
            corebench: 0.78,
        }],
    };

    tokio::spawn(async move {
        let _ = tx.send(request).await;
    });

    // Use the Judge trait
    let verdict = judge.evaluate_next().await.unwrap();
    assert!(verdict.pass, "Judge trait should return pass=true");
    assert_eq!(
        verdict.approved_for_modalities.len(),
        1,
        "Judge trait should propagate approved_for_modalities"
    );
    assert!(verdict.approved_for_modalities.contains(&Modality::Audio));
}
