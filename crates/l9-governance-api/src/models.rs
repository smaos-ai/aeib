use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TenantContext {
    pub tenant_id: Uuid,
    pub api_key: String,
    pub region: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiRequest<T> {
    pub tenant_id: Uuid,
    pub data: T,
    pub timestamp: i64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ApiResponse<T> {
    pub success: bool,
    pub data: Option<T>,
    pub error: Option<String>,
    pub timestamp: i64,
}

impl<T> ApiResponse<T> {
    pub fn ok(data: T) -> Self {
        Self {
            success: true,
            data: Some(data),
            error: None,
            timestamp: chrono::Utc::now().timestamp(),
        }
    }

    pub fn error(message: String) -> Self {
        Self {
            success: false,
            data: None,
            error: Some(message),
            timestamp: chrono::Utc::now().timestamp(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tenant {
    pub id: Uuid,
    pub name: String,
    pub region: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisterDIDRequest {
    pub did_method: String,      // "sov", "key", "web"
    pub identifier: String,
    pub controller: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisterDIDResponse {
    pub did: String,
    pub controller: Option<String>,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreatePolicyRequest {
    pub category: String,      // "egress", "consent", "audit"
    pub rules: serde_json::Value,
    pub parent_policy_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreatePolicyResponse {
    pub policy_id: String,
    pub version: i32,
    pub published: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitiateSettlementRequest {
    pub from_org_did: String,
    pub to_org_did: String,
    pub amount: String,
    pub currency: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementResponse {
    pub settlement_id: String,
    pub status: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheckResponse {
    pub status: String,
    pub version: String,
    pub timestamp: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsResponse {
    pub total_policies: usize,
    pub total_settlements: usize,
    pub total_dids: usize,
    pub avg_response_time_ms: f64,
    pub timestamp: i64,
}

#[derive(Debug, Clone)]
pub struct AuditLog {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub action: String,
    pub resource: String,
    pub result: String,
    pub timestamp: i64,
}

impl AuditLog {
    pub fn new(
        tenant_id: Uuid,
        action: String,
        resource: String,
        result: String,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            tenant_id,
            action,
            resource,
            result,
            timestamp: chrono::Utc::now().timestamp(),
        }
    }
}
