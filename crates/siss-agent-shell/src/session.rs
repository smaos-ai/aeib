use std::sync::Arc;

use chrono::Utc;
use sqlx::PgPool;

use siss_graph_core::node::NodeId;

use siss_behavioral_firewall::checker::FirewallChecker;
use siss_context_cartography::types::{CartographyRequest, VisibleField};
use siss_feedback_router::crystallizer::Crystallizer;
use siss_feedback_router::scorer::Scorer;
use siss_gatekeeper::signer::Signer;
use siss_job_router::executor::Executor;
use siss_job_router::strategy::RoutingStrategy;

use crate::ag_ui::status_emitter::{AgentState, emit_agent_status};
use crate::events::{
    AgentEvent,
    emitter::{EventEmitter, NoOpEmitter},
};
use crate::hooks::audit::AuditLogHook;
use crate::hooks::budget::BudgetGuardHook;
use crate::hooks::gatekeeper::GatekeeperHook;
use crate::hooks::{
    ExecutionContext, HookResult, LifecycleHook, SessionContext,
    runner::{run_execution_hooks, run_session_hooks},
};
use crate::pipeline;
use crate::types::{AgentShellError, IntentParams, IntentResult, SessionConfig};

/// The constitutional runtime — membrane between Operator and Cognitive planes.
pub struct AgentSession {
    pool: PgPool,
    persona_id: NodeId,
    tenant_id: NodeId,
    session_id: NodeId,
    intent_mandate_id: NodeId,
    visible_field: Option<VisibleField>,
    hooks: Vec<Box<dyn LifecycleHook>>,
    signer: Box<dyn Signer>,
    strategy: Box<dyn RoutingStrategy>,
    executor: Box<dyn Executor>,
    checkers: Vec<Box<dyn FirewallChecker>>,
    scorer: Box<dyn Scorer>,
    crystallizer: Box<dyn Crystallizer>,
    emitter: Arc<dyn EventEmitter>,
    budget_remaining: i64,
}

impl AgentSession {
    /// Start a new agent session.
    #[allow(clippy::too_many_arguments)]
    pub async fn start(
        pool: PgPool,
        config: SessionConfig,
        signer: Box<dyn Signer>,
        strategy: Box<dyn RoutingStrategy>,
        executor: Box<dyn Executor>,
        checkers: Vec<Box<dyn FirewallChecker>>,
        scorer: Box<dyn Scorer>,
        crystallizer: Box<dyn Crystallizer>,
        emitter: Option<Arc<dyn EventEmitter>>,
    ) -> Result<Self, AgentShellError> {
        // 1. Validate persona
        let persona_row = siss_graph_db::repo::node_repo::fetch_persona(&pool, config.persona_id.0)
            .await?
            .ok_or(AgentShellError::SessionStartDenied {
                reason: "Persona not found".into(),
            })?;
        let (_id, _tenant, _name, _kind, is_frozen) = persona_row;
        if is_frozen {
            return Err(AgentShellError::SessionStartDenied {
                reason: "Persona is frozen".into(),
            });
        }

        // 2. Create IntentMandate
        let mandate_id = siss_graph_db::repo::node_repo::insert_intent_mandate(
            &pool,
            config.budget_limit,
            "low",
            &[],
            config.tenant_id.0,
        )
        .await?;

        // 3. Build Visible Field
        let cartography_request = CartographyRequest {
            task_id: NodeId(uuid::Uuid::nil()), // No task yet — session-level context
            persona_id: config.persona_id,
            tenant_id: config.tenant_id,
            token_budget: config.token_budget,
        };
        // Cartography may fail if persona has no task — we handle gracefully
        let visible_field = siss_context_cartography::pipeline::build_context(
            &pool,
            &cartography_request,
            &config.retrieval_config,
        )
        .await
        .ok();

        let session_id = visible_field
            .as_ref()
            .map(|vf| vf.session_id)
            .unwrap_or(NodeId(uuid::Uuid::nil()));

        // 4. Register default hooks
        let hooks: Vec<Box<dyn LifecycleHook>> = vec![
            Box::new(GatekeeperHook::new(false)),
            Box::new(BudgetGuardHook::new(config.budget_limit)),
            Box::new(AuditLogHook::new()),
        ];

        let emitter: Arc<dyn EventEmitter> = emitter.unwrap_or_else(|| Arc::new(NoOpEmitter));

        // 5. Fire SessionStart hooks
        let session_ctx = SessionContext {
            session_id,
            persona_id: config.persona_id,
            tenant_id: config.tenant_id,
        };
        let result = run_session_hooks(&hooks, &session_ctx, |h, c| h.on_session_start(c));
        if let HookResult::Deny { reason } = result {
            return Err(AgentShellError::SessionStartDenied { reason });
        }

        emitter.emit(AgentEvent::SessionStarted {
            session_id: session_id.0,
            persona_id: config.persona_id.0,
            timestamp: Utc::now(),
        });

        emit_agent_status(AgentState::Running);

        Ok(Self {
            pool,
            persona_id: config.persona_id,
            tenant_id: config.tenant_id,
            session_id,
            intent_mandate_id: NodeId(mandate_id),
            visible_field,
            hooks,
            signer,
            strategy,
            executor,
            checkers,
            scorer,
            crystallizer,
            emitter,
            budget_remaining: config.budget_limit,
        })
    }

    /// Submit an intent for execution through the full value loop.
    pub async fn submit_intent(
        &mut self,
        params: IntentParams,
    ) -> Result<IntentResult, AgentShellError> {
        // 1. Fire PreExecution hooks
        let exec_ctx = ExecutionContext {
            task_id: None,
            intent: params.intent.clone(),
            estimated_cost: params.estimated_cost,
            verdict: None,
            quality_score: None,
        };
        let hook_result = run_execution_hooks(&self.hooks, &exec_ctx, |h, c| h.on_pre_execution(c));
        match hook_result {
            HookResult::Deny { reason } => {
                emit_agent_status(AgentState::Error);
                return Err(AgentShellError::IntentDenied { reason });
            }
            HookResult::Halt { reason } => {
                emit_agent_status(AgentState::Error);
                return Err(AgentShellError::IntentHalted { reason });
            }
            HookResult::Defer { reason, severity } => {
                emit_agent_status(AgentState::Error);
                return Err(AgentShellError::IntentDeferred { reason, severity });
            }
            HookResult::Continue => {}
        }

        // 2. Run the full pipeline
        let checker_refs: Vec<&dyn FirewallChecker> = self.checkers.iter().map(|c| &**c).collect();
        let zonal_context = self
            .visible_field
            .as_ref()
            .and_then(|vf| serde_json::to_value(vf).ok());
        let result = pipeline::run_intent_pipeline(
            &self.pool,
            self.persona_id,
            self.tenant_id,
            self.intent_mandate_id,
            &params.intent,
            &params.requested_tools,
            params.estimated_cost,
            zonal_context,
            params.skill_context.clone(),
            &*self.signer,
            &*self.strategy,
            &*self.executor,
            &checker_refs,
            &*self.scorer,
            &*self.crystallizer,
            &*self.emitter,
        )
        .await
        .map_err(|e| {
            emit_agent_status(AgentState::Error);
            e
        })?;

        // 3. Update budget tracking
        self.budget_remaining -= params.estimated_cost;

        // 4. Fire PostExecution hooks
        let post_ctx = ExecutionContext {
            task_id: Some(result.task_id),
            intent: params.intent,
            estimated_cost: params.estimated_cost,
            verdict: Some(result.verdict),
            quality_score: Some(result.quality_score),
        };
        let _ = run_execution_hooks(&self.hooks, &post_ctx, |h, c| h.on_post_execution(c));

        Ok(result)
    }

    /// Close the session.
    pub async fn close(&self) -> Result<(), AgentShellError> {
        // 1. Fire Stop hooks
        let ctx = SessionContext {
            session_id: self.session_id,
            persona_id: self.persona_id,
            tenant_id: self.tenant_id,
        };
        let _ = run_session_hooks(&self.hooks, &ctx, |h, c| h.on_stop(c));

        // 2. Mark session as completed (if we have a real session)
        if self.session_id.0 != uuid::Uuid::nil() {
            let _ = siss_graph_db::repo::node_repo::update_session_snapshot(
                &self.pool,
                self.session_id.0,
                serde_json::json!({"status": "completed"}),
            )
            .await;
        }

        // 3. Emit close event
        self.emitter.emit(AgentEvent::SessionClosed {
            session_id: self.session_id.0,
            timestamp: Utc::now(),
        });

        emit_agent_status(AgentState::Idle);

        Ok(())
    }

    /// Get the current session ID.
    pub fn session_id(&self) -> NodeId {
        self.session_id
    }

    /// Get the remaining budget.
    pub fn budget_remaining(&self) -> i64 {
        self.budget_remaining
    }

    /// Suspend the session (persist to DB, do not fire on_stop hooks).
    pub async fn suspend(&self) -> Result<(), AgentShellError> {
        // 1. Write {"status": "suspended"} to DB snapshot
        if self.session_id.0 != uuid::Uuid::nil() {
            let _ = siss_graph_db::repo::node_repo::update_session_snapshot(
                &self.pool,
                self.session_id.0,
                serde_json::json!({"status": "suspended"}),
            )
            .await;
        }

        // 2. Emit suspended state
        crate::ag_ui::status_emitter::emit_agent_status(
            crate::ag_ui::status_emitter::AgentState::Suspended,
        );

        // Note: on_stop hooks are NOT fired (session is resumable, not terminated)

        Ok(())
    }
}
