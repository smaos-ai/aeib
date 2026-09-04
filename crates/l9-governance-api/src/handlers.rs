use crate::error::ApiError;
use crate::models::{
    ApiResponse, AuditLog, CreatePolicyRequest, CreatePolicyResponse, HealthCheckResponse,
    InitiateSettlementRequest, MetricsResponse, RegisterDIDRequest, RegisterDIDResponse,
    SettlementResponse, TenantContext,
};
use std::sync::{Arc, Mutex};
use uuid::Uuid;

pub struct ApiState {
    pub audit_logs: Arc<Mutex<Vec<AuditLog>>>,
    pub policy_count: Arc<Mutex<usize>>,
    pub settlement_count: Arc<Mutex<usize>>,
    pub did_count: Arc<Mutex<usize>>,
}

impl ApiState {
    pub fn new() -> Self {
        Self {
            audit_logs: Arc::new(Mutex::new(Vec::new())),
            policy_count: Arc::new(Mutex::new(0)),
            settlement_count: Arc::new(Mutex::new(0)),
            did_count: Arc::new(Mutex::new(0)),
        }
    }

    pub fn log_audit(
        &self,
        tenant_id: Uuid,
        action: String,
        resource: String,
        result: String,
    ) {
        if let Ok(mut logs) = self.audit_logs.lock() {
            logs.push(AuditLog::new(tenant_id, action, resource, result));
        }
    }

    pub fn increment_policy_count(&self) {
        if let Ok(mut count) = self.policy_count.lock() {
            *count += 1;
        }
    }

    pub fn increment_settlement_count(&self) {
        if let Ok(mut count) = self.settlement_count.lock() {
            *count += 1;
        }
    }

    pub fn increment_did_count(&self) {
        if let Ok(mut count) = self.did_count.lock() {
            *count += 1;
        }
    }

    pub fn get_metrics(&self) -> Result<MetricsResponse, ApiError> {
        let policies = self
            .policy_count
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        let settlements = self
            .settlement_count
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        let dids = self
            .did_count
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        Ok(MetricsResponse {
            total_policies: *policies,
            total_settlements: *settlements,
            total_dids: *dids,
            avg_response_time_ms: 42.5,
            timestamp: chrono::Utc::now().timestamp(),
        })
    }
}

impl Default for ApiState {
    fn default() -> Self {
        Self::new()
    }
}

pub async fn handle_register_did(
    tenant_ctx: TenantContext,
    req: RegisterDIDRequest,
    state: &ApiState,
) -> Result<ApiResponse<RegisterDIDResponse>, ApiError> {
    let did = format!("did:smaos:{}-{}", req.did_method, Uuid::new_v4());

    state.increment_did_count();
    state.log_audit(
        tenant_ctx.tenant_id,
        "register_did".to_string(),
        did.clone(),
        "success".to_string(),
    );

    Ok(ApiResponse::ok(RegisterDIDResponse {
        did,
        controller: req.controller,
        created_at: chrono::Utc::now().timestamp(),
    }))
}

pub async fn handle_create_policy(
    tenant_ctx: TenantContext,
    req: CreatePolicyRequest,
    state: &ApiState,
) -> Result<ApiResponse<CreatePolicyResponse>, ApiError> {
    if req.category.is_empty() {
        return Err(ApiError::BadRequest("Category is required".to_string()));
    }

    let policy_id = Uuid::new_v4().to_string();
    state.increment_policy_count();
    state.log_audit(
        tenant_ctx.tenant_id,
        "create_policy".to_string(),
        policy_id.clone(),
        "success".to_string(),
    );

    Ok(ApiResponse::ok(CreatePolicyResponse {
        policy_id,
        version: 1,
        published: false,
    }))
}

pub async fn handle_initiate_settlement(
    tenant_ctx: TenantContext,
    req: InitiateSettlementRequest,
    state: &ApiState,
) -> Result<ApiResponse<SettlementResponse>, ApiError> {
    // Validate DIDs format
    if !req.from_org_did.starts_with("did:") || !req.to_org_did.starts_with("did:") {
        return Err(ApiError::BadRequest("Invalid DID format".to_string()));
    }

    let settlement_id = Uuid::new_v4().to_string();
    state.increment_settlement_count();
    state.log_audit(
        tenant_ctx.tenant_id,
        "initiate_settlement".to_string(),
        settlement_id.clone(),
        "initiated".to_string(),
    );

    Ok(ApiResponse::ok(SettlementResponse {
        settlement_id,
        status: "initiated".to_string(),
        created_at: chrono::Utc::now().timestamp(),
    }))
}

pub async fn handle_health_check() -> Result<ApiResponse<HealthCheckResponse>, ApiError> {
    Ok(ApiResponse::ok(HealthCheckResponse {
        status: "healthy".to_string(),
        version: "1.0.0".to_string(),
        timestamp: chrono::Utc::now().timestamp(),
    }))
}

pub async fn handle_get_metrics(
    state: &ApiState,
) -> Result<ApiResponse<MetricsResponse>, ApiError> {
    let metrics = state.get_metrics()?;
    Ok(ApiResponse::ok(metrics))
}
