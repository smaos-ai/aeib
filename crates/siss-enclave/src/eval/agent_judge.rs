use std::time::Duration;
use tokio::sync::mpsc;

const DIVERGENCE_THRESHOLD: f64 = 0.15;
const F1_SCORE_THRESHOLD: f64 = 0.85;

pub struct EvaluationRequest {
    pub divergence: f64,
    pub f1_score: f64,
}

#[derive(Debug)]
pub struct JudgeResult {
    pub divergence: f64,
    pub f1_score: f64,
    pub accepted: bool,
    pub reason: String,
}

pub struct AgentJudge {
    receiver: mpsc::Receiver<EvaluationRequest>,
    timeout: Duration,
}

impl AgentJudge {
    pub fn new(receiver: mpsc::Receiver<EvaluationRequest>, timeout: Duration) -> Self {
        Self { receiver, timeout }
    }

    /// Evaluates the next shadow result from the channel, returning a fail-closed
    /// JudgeResult if the timeout is breached or thresholds are not met.
    pub async fn evaluate_next(&mut self) -> Result<JudgeResult, String> {
        // Wrap recv() in timeout for Fail-Closed semantics
        let result = tokio::time::timeout(self.timeout, self.receiver.recv()).await;

        match result {
            Ok(Some(req)) => {
                // Evaluate thresholds
                let (accepted, reason) = self.evaluate_request(&req);

                Ok(JudgeResult {
                    divergence: req.divergence,
                    f1_score: req.f1_score,
                    accepted,
                    reason,
                })
            }
            Ok(None) => {
                // Channel closed, fail-closed
                Ok(JudgeResult {
                    divergence: 0.0,
                    f1_score: 0.0,
                    accepted: false,
                    reason: "Channel closed".to_string(),
                })
            }
            Err(_) => {
                // Timeout fired, fail-closed
                Ok(JudgeResult {
                    divergence: 0.0,
                    f1_score: 0.0,
                    accepted: false,
                    reason: "Evaluation timeout exceeded".to_string(),
                })
            }
        }
    }

    fn evaluate_request(&self, req: &EvaluationRequest) -> (bool, String) {
        // Check divergence threshold
        if req.divergence >= DIVERGENCE_THRESHOLD {
            return (
                false,
                format!(
                    "Divergence {} exceeds threshold {}",
                    req.divergence, DIVERGENCE_THRESHOLD
                ),
            );
        }

        // Check F1 score threshold
        if req.f1_score < F1_SCORE_THRESHOLD {
            return (
                false,
                format!(
                    "F1 score {} below threshold {}",
                    req.f1_score, F1_SCORE_THRESHOLD
                ),
            );
        }

        // Both thresholds passed
        (true, "Approved by Agent-as-Judge".to_string())
    }
}
