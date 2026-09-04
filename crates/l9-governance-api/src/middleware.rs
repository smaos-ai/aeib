use crate::error::ApiError;
use crate::models::TenantContext;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use uuid::Uuid;

pub struct TenantRegistry {
    api_keys: HashMap<String, Uuid>,
    tenants: HashMap<Uuid, TenantInfo>,
}

#[derive(Clone)]
pub struct TenantInfo {
    pub id: Uuid,
    pub name: String,
    pub region: String,
}

impl TenantRegistry {
    pub fn new() -> Self {
        Self {
            api_keys: HashMap::new(),
            tenants: HashMap::new(),
        }
    }

    pub fn register_tenant(
        &mut self,
        name: String,
        region: String,
    ) -> Result<(Uuid, String), ApiError> {
        let tenant_id = Uuid::new_v4();
        let api_key = format!("sk_{}", uuid::Uuid::new_v4());

        let key_hash = Self::hash_api_key(&api_key);
        self.api_keys.insert(key_hash, tenant_id);

        self.tenants.insert(
            tenant_id,
            TenantInfo {
                id: tenant_id,
                name,
                region,
            },
        );

        Ok((tenant_id, api_key))
    }

    pub fn validate_api_key(&self, api_key: &str) -> Result<TenantContext, ApiError> {
        let key_hash = Self::hash_api_key(api_key);

        match self.api_keys.get(&key_hash) {
            Some(&tenant_id) => match self.tenants.get(&tenant_id) {
                Some(tenant_info) => Ok(TenantContext {
                    tenant_id,
                    api_key: api_key.to_string(),
                    region: tenant_info.region.clone(),
                }),
                None => Err(ApiError::InvalidTenant),
            },
            None => Err(ApiError::Unauthorized("Invalid API key".to_string())),
        }
    }

    pub fn get_tenant(&self, tenant_id: Uuid) -> Result<TenantInfo, ApiError> {
        self.tenants
            .get(&tenant_id)
            .cloned()
            .ok_or_else(|| ApiError::InvalidTenant)
    }

    fn hash_api_key(api_key: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(api_key.as_bytes());
        hex::encode(hasher.finalize())
    }
}

impl Default for TenantRegistry {
    fn default() -> Self {
        Self::new()
    }
}

pub struct RateLimiter {
    pub limits: HashMap<Uuid, usize>,
    pub window_size_secs: usize,
}

impl RateLimiter {
    pub fn new(requests_per_minute: usize) -> Self {
        Self {
            limits: HashMap::new(),
            window_size_secs: 60 / (requests_per_minute.max(1)),
        }
    }

    pub fn check_limit(&mut self, tenant_id: Uuid) -> Result<(), ApiError> {
        let current_count = self.limits.entry(tenant_id).or_insert(0);
        if *current_count >= (60 / self.window_size_secs) {
            return Err(ApiError::RateLimited);
        }
        *current_count += 1;
        Ok(())
    }

    pub fn reset_for_tenant(&mut self, tenant_id: Uuid) {
        self.limits.remove(&tenant_id);
    }
}

impl Default for RateLimiter {
    fn default() -> Self {
        Self::new(60)
    }
}
