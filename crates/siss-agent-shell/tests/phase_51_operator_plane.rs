/// Phase 51: Agent of Empires (AoE) & Parallel Swarm Orchestration
/// RED gate: 9 failing tests define expected behavior for the operator plane.
/// Invariants: (1) WorktreeSandbox proves branch exclusivity
///             (2) EscalationInbox routes Phase 50 approval cards to the SwarmMcpServer bus
///             (3) AoETelemetryHub wires agent status + kill switch
use chrono::Utc;
use siss_agent_shell::a2ui::escalation::{EscalationReason, EscalationRequest};
use siss_agent_shell::ag_ui::AgentState;
use siss_agent_shell::aoe_telemetry::{AoETelemetryHub, TelemetryError};
use siss_agent_shell::escalation_inbox::EscalationInbox;
use siss_agent_shell::orchestrator::{ProvisionError, TmuxSpawner};
use siss_agent_shell::sandbox::{SandboxAllocator, SandboxError};
use siss_agent_shell::swarm_channel::{InMemorySwarmState, SwarmChannel};
use siss_agent_shell::swarm_mcp_server::SwarmMcpServer;
use siss_agent_shell::ucp::UcpContract;
use std::sync::Arc;
use uuid::Uuid;

// MockTmuxSpawner: records kill calls for assertion
#[derive(Clone)]
struct MockTmuxSpawner {
    killed: Arc<std::sync::Mutex<Vec<String>>>,
}

impl MockTmuxSpawner {
    fn new() -> Self {
        MockTmuxSpawner {
            killed: Arc::new(std::sync::Mutex::new(Vec::new())),
        }
    }

    fn get_killed(&self) -> Vec<String> {
        self.killed.lock().unwrap().clone()
    }
}

#[async_trait::async_trait]
impl TmuxSpawner for MockTmuxSpawner {
    async fn spawn(&self, _name: &str, _working_dir: &str) -> Result<(), ProvisionError> {
        Ok(())
    }

    async fn kill(&self, name: &str) {
        self.killed.lock().unwrap().push(name.to_string());
    }
}

// Test 1: SandboxAllocator allocates unique branches
#[test]
fn test_sandbox_allocates_unique_branches() {
    let allocator = SandboxAllocator::new();
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    let result_a = allocator.allocate(agent_a, "agent-a", "/path/to/a");
    let result_b = allocator.allocate(agent_b, "agent-b", "/path/to/b");

    assert!(result_a.is_ok());
    assert!(result_b.is_ok());
}

// Test 2: SandboxAllocator rejects duplicate branch
#[test]
fn test_sandbox_rejects_duplicate_branch() {
    let allocator = SandboxAllocator::new();
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    let result_a = allocator.allocate(agent_a, "shared-branch", "/path/to/a");
    let result_b = allocator.allocate(agent_b, "shared-branch", "/path/to/b");

    assert!(result_a.is_ok());
    assert!(matches!(
        result_b,
        Err(SandboxError::BranchAlreadyAllocated {
            branch,
            held_by
        }) if branch == "shared-branch" && held_by == agent_a
    ));
}

// Test 3: SandboxAllocator release allows reallocation
#[test]
fn test_sandbox_release_allows_reallocation() {
    let allocator = SandboxAllocator::new();
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    let sandbox_a = allocator
        .allocate(agent_a, "shared-branch", "/path/to/a")
        .unwrap();
    allocator.release(sandbox_a);
    let result_b = allocator.allocate(agent_b, "shared-branch", "/path/to/b");

    assert!(result_b.is_ok());
}

// Test 4: EscalationInbox routes to SwarmMcpServer
#[tokio::test]
async fn test_escalation_inbox_routes_to_mcp_server() {
    let server = Arc::new(SwarmMcpServer::new("sqlite::memory:").await.unwrap());
    let inbox = EscalationInbox::new(server);

    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: Uuid::new_v4(),
        skill_id: "audit".to_string(),
        agreed_price: 100,
        terms: "Standard".to_string(),
        created_at: Utc::now(),
    };

    let request = EscalationRequest {
        task_id: Uuid::new_v4(),
        contract,
        reason: EscalationReason::BudgetExceeded {
            required: 100,
            available: 50,
        },
    };

    let result = inbox.submit("agent-a", request.clone()).await;
    assert!(result.is_ok());

    let pending = inbox.pending().await.unwrap();
    assert_eq!(pending.len(), 1);
    assert_eq!(pending[0].task_id, request.task_id);
}

// Test 5: EscalationInbox dismiss removes entry
#[tokio::test]
async fn test_escalation_inbox_dismiss_removes_entry() {
    let server = Arc::new(SwarmMcpServer::new("sqlite::memory:").await.unwrap());
    let inbox = EscalationInbox::new(server);

    let task_id = Uuid::new_v4();
    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: Uuid::new_v4(),
        skill_id: "audit".to_string(),
        agreed_price: 100,
        terms: "Standard".to_string(),
        created_at: Utc::now(),
    };

    let request = EscalationRequest {
        task_id,
        contract,
        reason: EscalationReason::HumanApprovalRequired {
            policy: "High value".to_string(),
        },
    };

    inbox.submit("agent-a", request).await.unwrap();
    assert_eq!(inbox.pending().await.unwrap().len(), 1);

    inbox.dismiss("agent-a", task_id).await.unwrap();
    assert_eq!(inbox.pending().await.unwrap().len(), 0);
}

// Test 6: EscalationInbox phase isolation
#[tokio::test]
async fn test_escalation_inbox_phase_isolation() {
    let server = Arc::new(SwarmMcpServer::new("sqlite::memory:").await.unwrap());
    let inbox = EscalationInbox::new(server.clone());

    // Add escalation
    let contract = UcpContract {
        contract_id: Uuid::new_v4(),
        buyer_agent_id: Uuid::new_v4(),
        seller_agent_id: Uuid::new_v4(),
        skill_id: "audit".to_string(),
        agreed_price: 100,
        terms: "Standard".to_string(),
        created_at: Utc::now(),
    };

    let request = EscalationRequest {
        task_id: Uuid::new_v4(),
        contract,
        reason: EscalationReason::BudgetExceeded {
            required: 100,
            available: 50,
        },
    };

    inbox.submit("agent-a", request).await.unwrap();

    // Add knowledge atom via different method (simulating concurrent publish)
    let knowledge_payload = siss_agent_shell::swarm_mcp_server::SwarmStatePayload {
        idempotency_key: format!("knowledge:alpha:{}", Uuid::new_v4()),
        agent_id: "alpha".to_string(),
        phase: "KNOWLEDGE_ATOM".to_string(),
        status: "VulnerabilityFound".to_string(),
        payload_json: Some("{}".to_string()),
    };
    server.update_swarm_state(knowledge_payload).await.unwrap();

    // pending() should only return escalations
    let pending = inbox.pending().await.unwrap();
    assert_eq!(pending.len(), 1);
}

// Test 7: AoETelemetryHub reports state
#[test]
fn test_telemetry_hub_reports_state() {
    let tmux = MockTmuxSpawner::new();
    let ledger = Arc::new(InMemorySwarmState::new());
    let channel = Arc::new(SwarmChannel::with_capacity(100));
    let hub = AoETelemetryHub::new(tmux, ledger, channel);

    let agent_id = Uuid::new_v4();
    let result = hub.report(
        agent_id,
        AgentState::Running,
        50,
        "worktree-a",
        "siss-agent-alpha",
    );

    assert!(result.is_ok());

    let telemetry = hub.get(agent_id);
    assert!(telemetry.is_some());
    let t = telemetry.unwrap();
    assert_eq!(t.state, AgentState::Running);
    assert_eq!(t.progress, 50);
    assert_eq!(t.tmux_name, "siss-agent-alpha");
}

// Test 8: AoETelemetryHub kill_switch terminates tmux
#[tokio::test]
async fn test_telemetry_hub_kill_switch_terminates_tmux() {
    let tmux = MockTmuxSpawner::new();
    let ledger = Arc::new(InMemorySwarmState::new());
    let channel = Arc::new(SwarmChannel::with_capacity(100));
    let hub = AoETelemetryHub::new(tmux.clone(), ledger, channel);

    let agent_id = Uuid::new_v4();
    hub.report(
        agent_id,
        AgentState::Running,
        75,
        "worktree-a",
        "siss-agent-test",
    )
    .unwrap();

    let result = hub.kill_switch(agent_id).await;
    assert!(result.is_ok());

    let killed = tmux.get_killed();
    assert!(killed.contains(&"siss-agent-test".to_string()));
}

// Test 9: AoETelemetryHub kill_switch fails on unknown agent
#[tokio::test]
async fn test_telemetry_hub_kill_switch_fails_unknown_agent() {
    let tmux = MockTmuxSpawner::new();
    let ledger = Arc::new(InMemorySwarmState::new());
    let channel = Arc::new(SwarmChannel::with_capacity(100));
    let hub = AoETelemetryHub::new(tmux, ledger, channel);

    let unknown_agent = Uuid::new_v4();
    let result = hub.kill_switch(unknown_agent).await;

    assert!(matches!(result, Err(TelemetryError::AgentNotFound(id)) if id == unknown_agent));
}
