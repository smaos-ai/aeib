use crate::exec_log::InMemoryAuditLog;
use crate::mandate::{Mandate, MandateError, MandateStore};
use chrono::{DateTime, Utc};
use std::sync::Arc;
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum GateError {
    #[error("Mandate expired")]
    MandateExpired,
    #[error("Mandate not found")]
    MandateNotFound,
    #[error("Invalid signature")]
    InvalidSignature,
    #[error("Jurisdiction violation: {0}")]
    JurisdictionViolation(String),
    #[error("Capability denied: {0}")]
    CapabilityDenied(String),
    #[error("Audit log failure: {0}")]
    AuditLogFailure(String),
}

impl From<MandateError> for GateError {
    fn from(e: MandateError) -> Self {
        match e {
            MandateError::Expired => GateError::MandateExpired,
            MandateError::NotFound => GateError::MandateNotFound,
            MandateError::InvalidSignature(_) => GateError::InvalidSignature,
            MandateError::JurisdictionViolation(s) => GateError::JurisdictionViolation(s),
            MandateError::AlreadyRevoked => GateError::MandateNotFound,
        }
    }
}

#[derive(Debug, Clone)]
pub struct CapabilityToken {
    pub id: Uuid,
    pub mandate_id: Uuid,
    pub action_scope: String,
    pub issued_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

impl CapabilityToken {
    pub fn is_expired(&self) -> bool {
        Utc::now() > self.expires_at
    }
}

#[derive(Debug, Clone)]
pub struct GateResult {
    pub allowed: bool,
    pub reason: String,
    pub capability_token: Option<CapabilityToken>,
    pub audit_id: Uuid,
}

pub struct Layer0Gate {
    mandate_store: Arc<dyn MandateStore>,
    exec_log: Arc<InMemoryAuditLog>,
}

impl Layer0Gate {
    pub fn new(mandate_store: Arc<dyn MandateStore>) -> Self {
        Self {
            mandate_store,
            exec_log: Arc::new(InMemoryAuditLog::new()),
        }
    }

    pub fn register_mandate(&self, mandate: Mandate) -> Result<Uuid, GateError> {
        self.mandate_store.insert_mandate(mandate.clone())?;
        Ok(mandate.id)
    }

    pub fn request_capability(
        &self,
        mandate_id: Uuid,
        action: &str,
    ) -> Result<CapabilityToken, GateError> {
        let mandate = self
            .mandate_store
            .get_mandate(mandate_id)?
            .ok_or(GateError::MandateNotFound)?;

        mandate.validate()?;

        if !mandate.action_allowed(action) {
            return Err(GateError::CapabilityDenied(format!(
                "Action '{}' not in scope {:?}",
                action, mandate.action_scope
            )));
        }

        let token = CapabilityToken {
            id: Uuid::new_v4(),
            mandate_id,
            action_scope: action.to_string(),
            issued_at: Utc::now(),
            expires_at: mandate.expires_at,
        };

        Ok(token)
    }

    pub fn invoke_tool(
        &self,
        token: &CapabilityToken,
        tool_name: &str,
        result_hash: [u8; 32],
    ) -> Result<i64, GateError> {
        if token.is_expired() {
            return Err(GateError::CapabilityDenied(
                "Capability token expired".to_string(),
            ));
        }

        let mandate = self
            .mandate_store
            .get_mandate(token.mandate_id)?
            .ok_or(GateError::MandateNotFound)?;

        mandate.validate()?;

        let audit_id = self
            .exec_log
            .append(
                token.mandate_id,
                &token.action_scope,
                tool_name,
                result_hash,
            )
            .map(|entry| entry.id)
            .map_err(|e| GateError::AuditLogFailure(e.to_string()))?;

        Ok(audit_id)
    }

    pub fn revoke_mandate(&self, mandate_id: Uuid) -> Result<(), GateError> {
        self.mandate_store
            .revoke_mandate(mandate_id)
            .map_err(Into::into)
    }

    pub fn verify_chain(&self) -> Result<bool, GateError> {
        self.exec_log
            .verify_chain()
            .map_err(|e| GateError::AuditLogFailure(e.to_string()))
    }

    pub fn merkle_root(&self) -> Result<[u8; 32], GateError> {
        self.exec_log
            .merkle_root()
            .map_err(|e| GateError::AuditLogFailure(e.to_string()))
    }
}
