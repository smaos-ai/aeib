use anyhow::Result;
use async_trait::async_trait;
use std::time::Duration;
use tokio::sync::mpsc;
use tokio::sync::Mutex;

use crate::model::modality::{Modality, PerModalityScores};
use crate::orchestrator::evolution_gate::{Judge, Verdict};

const DIVERGENCE_THRESHOLD: f64 = 0.15;
const F1_SCORE_THRESHOLD: f64 = 0.85;
const ROBUSTNESS_THRESHOLD: f64 = 0.90;
const ALIGNMENT_THRESHOLD: f64 = 0.80;
const COREBENCH_THRESHOLD: f64 = 0.75;

pub struct EvaluationRequest {
    pub divergence: f64,
    pub f1_score: f64,
    pub robustness_score: f64,
    pub alignment_score: f64,
    pub corebench_score: f64,
    pub per_modality: Vec<PerModalityScores>,
}

#[derive(Debug)]
pub struct JudgeResult {
    pub divergence: f64,
    pub f1_score: f64,
    pub accepted: bool,
    pub reason: String,
    pub approved_for_modalities: Vec<Modality>,
}

pub struct AgentJudge {
    receiver: Mutex<mpsc::Receiver<EvaluationRequest>>,
    timeout: Duration,
}

impl AgentJudge {
    pub fn new(receiver: mpsc::Receiver<EvaluationRequest>, timeout: Duration) -> Self {
        Self {
            receiver: Mutex::new(receiver),
            timeout,
        }
    }

    /// Evaluates the next shadow result from the channel, returning a fail-closed
    /// JudgeResult if the timeout is breached or thresholds are not met.
    pub async fn evaluate_next(&self) -> Result<JudgeResult, String> {
        // Wrap recv() in timeout for Fail-Closed semantics
        let result = tokio::time::timeout(self.timeout, self.receiver.lock().await.recv()).await;

        match result {
            Ok(Some(req)) => {
                // Evaluate thresholds
                let (accepted, reason, approved_modalities) = self.evaluate_request(&req);

                Ok(JudgeResult {
                    divergence: req.divergence,
                    f1_score: req.f1_score,
                    accepted,
                    reason,
                    approved_for_modalities: approved_modalities,
                })
            }
            Ok(None) => {
                // Channel closed, fail-closed
                Ok(JudgeResult {
                    divergence: 0.0,
                    f1_score: 0.0,
                    accepted: false,
                    reason: "Channel closed".to_string(),
                    approved_for_modalities: vec![],
                })
            }
            Err(_) => {
                // Timeout fired, fail-closed
                Ok(JudgeResult {
                    divergence: 0.0,
                    f1_score: 0.0,
                    accepted: false,
                    reason: "Evaluation timeout exceeded".to_string(),
                    approved_for_modalities: vec![],
                })
            }
        }
    }

    fn evaluate_request(&self, req: &EvaluationRequest) -> (bool, String, Vec<Modality>) {
        // Check global pillars in order: divergence, f1, robustness, alignment, corebench
        // First failure short-circuits with pass=false

        if req.divergence >= DIVERGENCE_THRESHOLD {
            return (
                false,
                format!(
                    "Divergence {} exceeds threshold {}",
                    req.divergence, DIVERGENCE_THRESHOLD
                ),
                vec![],
            );
        }

        if req.f1_score < F1_SCORE_THRESHOLD {
            return (
                false,
                format!(
                    "F1 score {} below threshold {}",
                    req.f1_score, F1_SCORE_THRESHOLD
                ),
                vec![],
            );
        }

        if req.robustness_score < ROBUSTNESS_THRESHOLD {
            return (
                false,
                format!(
                    "Robustness score {} below threshold {}",
                    req.robustness_score, ROBUSTNESS_THRESHOLD
                ),
                vec![],
            );
        }

        if req.alignment_score < ALIGNMENT_THRESHOLD {
            return (
                false,
                format!(
                    "Alignment score {} below threshold {}",
                    req.alignment_score, ALIGNMENT_THRESHOLD
                ),
                vec![],
            );
        }

        if req.corebench_score < COREBENCH_THRESHOLD {
            return (
                false,
                format!(
                    "CoReBench score {} below threshold {}",
                    req.corebench_score, COREBENCH_THRESHOLD
                ),
                vec![],
            );
        }

        // Global pillars pass. Now evaluate per-modality.
        let mut approved_modalities = vec![];
        for modality_scores in &req.per_modality {
            if self.modality_passes(&modality_scores) {
                approved_modalities.push(modality_scores.modality.clone());
            }
        }

        // All global pillars passed
        (
            true,
            "Approved by Agent-as-Judge".to_string(),
            approved_modalities,
        )
    }

    fn modality_passes(&self, scores: &PerModalityScores) -> bool {
        scores.divergence < DIVERGENCE_THRESHOLD
            && scores.f1_score >= F1_SCORE_THRESHOLD
            && scores.robustness >= ROBUSTNESS_THRESHOLD
            && scores.alignment >= ALIGNMENT_THRESHOLD
            && scores.corebench >= COREBENCH_THRESHOLD
    }
}

#[async_trait]
impl Judge for AgentJudge {
    async fn evaluate_next(&self) -> Result<Verdict> {
        let result = self
            .evaluate_next()
            .await
            .map_err(|e| anyhow::anyhow!("{}", e))?;
        Ok(Verdict {
            pass: result.accepted,
            reason: result.reason,
            approved_for_modalities: result.approved_for_modalities,
        })
    }
}
