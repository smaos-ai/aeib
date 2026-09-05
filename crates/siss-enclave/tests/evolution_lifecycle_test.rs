use anyhow::Result;
use siss_enclave::events::sse_emitter::SseEmitter;
use siss_enclave::orchestrator::evolution_gate::{
    DoubleBufferedSwap, EvolutionGate, Judge, RceStateMachine, Verdict,
};
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Clone, Default)]
struct CallLog {
    calls: Arc<Mutex<Vec<String>>>,
}

impl CallLog {
    async fn push(&self, call: &str) {
        self.calls.lock().await.push(call.to_string());
    }

    async fn get(&self) -> Vec<String> {
        self.calls.lock().await.clone()
    }
}

#[derive(Clone)]
struct MockJudge {
    pass: bool,
    log: CallLog,
}

#[async_trait::async_trait]
impl Judge for MockJudge {
    async fn evaluate_next(&self) -> Result<Verdict> {
        self.log.push("JUDGE_EVAL").await;
        Ok(Verdict {
            pass: self.pass,
            reason: "".into(),
            approved_for_modalities: vec![],
        })
    }
}

#[derive(Clone)]
struct MockSwap {
    log: CallLog,
}

#[async_trait::async_trait]
impl DoubleBufferedSwap for MockSwap {
    async fn execute_swap(&self, _version: u64) -> Result<()> {
        self.log.push("SWAP_EXEC").await;
        Ok(())
    }
    async fn discard(&self, _version: u64) -> Result<()> {
        self.log.push("SWAP_DISCARD").await;
        Ok(())
    }
}

#[derive(Clone)]
struct MockRce {
    log: CallLog,
}

#[async_trait::async_trait]
impl RceStateMachine for MockRce {
    async fn pause_workflow_with_persistence(&self) -> Result<()> {
        self.log.push("RCE_PAUSE").await;
        Ok(())
    }
    async fn resume_workflow_approve_with_persistence(&self, _version: u64) -> Result<()> {
        self.log.push("RCE_RESUME_APPROVE").await;
        Ok(())
    }
    async fn resume_workflow_rollback(&self) -> Result<()> {
        self.log.push("RCE_RESUME_ROLLBACK").await;
        Ok(())
    }
}

#[tokio::test]
async fn should_swap_and_resume_when_judge_passes() {
    let log = CallLog::default();
    let judge = MockJudge {
        pass: true,
        log: log.clone(),
    };
    let swap = MockSwap { log: log.clone() };
    let rce = MockRce { log: log.clone() };
    let (tx, _) = tokio::sync::mpsc::unbounded_channel();
    let emitter = SseEmitter::new(tx);

    let gate = EvolutionGate {
        judge: Box::new(judge),
        swap: Box::new(swap),
        rce: Box::new(rce),
        emitter,
    };

    gate.process_evolution(42).await.unwrap();

    let calls = log.get().await;
    // Verify strict sequence: Pause -> Judge -> Swap -> Resume -> SSE
    assert_eq!(
        calls,
        vec!["RCE_PAUSE", "JUDGE_EVAL", "SWAP_EXEC", "RCE_RESUME_APPROVE"]
    );
}

#[tokio::test]
async fn should_discard_and_rollback_when_judge_fails() {
    let log = CallLog::default();
    let judge = MockJudge {
        pass: false,
        log: log.clone(),
    };
    let swap = MockSwap { log: log.clone() };
    let rce = MockRce { log: log.clone() };
    let (tx, _) = tokio::sync::mpsc::unbounded_channel();
    let emitter = SseEmitter::new(tx);

    let gate = EvolutionGate {
        judge: Box::new(judge),
        swap: Box::new(swap),
        rce: Box::new(rce),
        emitter,
    };

    gate.process_evolution(42).await.unwrap();

    let calls = log.get().await;
    // Verify Swap is NOT called on judge failure
    assert_eq!(
        calls,
        vec![
            "RCE_PAUSE",
            "JUDGE_EVAL",
            "SWAP_DISCARD",
            "RCE_RESUME_ROLLBACK"
        ]
    );
}
