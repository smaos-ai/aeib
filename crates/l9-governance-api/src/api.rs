use crate::error::ApiError;
use crate::handlers::{
    handle_create_policy, handle_get_metrics, handle_health_check, handle_initiate_settlement,
    handle_register_did, ApiState,
};
use crate::middleware::{RateLimiter, TenantRegistry};
use crate::models::{CreatePolicyRequest, InitiateSettlementRequest, RegisterDIDRequest};
use std::sync::{Arc, Mutex};
use uuid::Uuid;

pub struct GovernanceApi {
    pub tenant_registry: Arc<Mutex<TenantRegistry>>,
    pub rate_limiter: Arc<Mutex<RateLimiter>>,
    pub state: Arc<ApiState>,
}

impl GovernanceApi {
    pub fn new() -> Self {
        Self {
            tenant_registry: Arc::new(Mutex::new(TenantRegistry::new())),
            rate_limiter: Arc::new(Mutex::new(RateLimiter::new(60))),
            state: Arc::new(ApiState::new()),
        }
    }

    pub async fn register_tenant(
        &self,
        name: String,
        region: String,
    ) -> Result<(Uuid, String), ApiError> {
        let mut registry = self
            .tenant_registry
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        registry.register_tenant(name, region)
    }

    pub async fn validate_request(
        &self,
        api_key: &str,
    ) -> Result<uuid::Uuid, ApiError> {
        let registry = self
            .tenant_registry
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        match registry.validate_api_key(api_key) {
            Ok(ctx) => Ok(ctx.tenant_id),
            Err(e) => Err(e),
        }
    }

    pub async fn check_rate_limit(&self, tenant_id: Uuid) -> Result<(), ApiError> {
        let mut limiter = self
            .rate_limiter
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        limiter.check_limit(tenant_id)
    }

    pub async fn register_did(
        &self,
        api_key: &str,
        req: RegisterDIDRequest,
    ) -> Result<crate::models::ApiResponse<crate::models::RegisterDIDResponse>, ApiError> {
        let tenant_id = self.validate_request(api_key).await?;
        self.check_rate_limit(tenant_id).await?;

        let registry = self
            .tenant_registry
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        let tenant_ctx = registry.validate_api_key(api_key)?;
        drop(registry);

        handle_register_did(tenant_ctx, req, self.state.as_ref()).await
    }

    pub async fn create_policy(
        &self,
        api_key: &str,
        req: CreatePolicyRequest,
    ) -> Result<crate::models::ApiResponse<crate::models::CreatePolicyResponse>, ApiError> {
        let tenant_id = self.validate_request(api_key).await?;
        self.check_rate_limit(tenant_id).await?;

        let registry = self
            .tenant_registry
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        let tenant_ctx = registry.validate_api_key(api_key)?;
        drop(registry);

        handle_create_policy(tenant_ctx, req, self.state.as_ref()).await
    }

    pub async fn initiate_settlement(
        &self,
        api_key: &str,
        req: InitiateSettlementRequest,
    ) -> Result<crate::models::ApiResponse<crate::models::SettlementResponse>, ApiError> {
        let tenant_id = self.validate_request(api_key).await?;
        self.check_rate_limit(tenant_id).await?;

        let registry = self
            .tenant_registry
            .lock()
            .map_err(|_| ApiError::InternalError("Lock error".to_string()))?;

        let tenant_ctx = registry.validate_api_key(api_key)?;
        drop(registry);

        handle_initiate_settlement(tenant_ctx, req, self.state.as_ref()).await
    }

    pub async fn health_check(&self) -> Result<crate::models::ApiResponse<crate::models::HealthCheckResponse>, ApiError> {
        handle_health_check().await
    }

    pub async fn get_metrics(&self) -> Result<crate::models::ApiResponse<crate::models::MetricsResponse>, ApiError> {
        handle_get_metrics(self.state.as_ref()).await
    }
}

impl Default for GovernanceApi {
    fn default() -> Self {
        Self::new()
    }
}
