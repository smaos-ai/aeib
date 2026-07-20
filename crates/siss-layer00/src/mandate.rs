use chrono::{DateTime, Utc};
use dashmap::DashMap;
use std::sync::Arc;
use thiserror::Error;
use uuid::Uuid;
use crate::attestation::{verify_signature, AttestationError};

#[derive(Debug, Clone, Error)]
pub enum MandateError {
    #[error("Mandate expired")]
    Expired,
    #[error("Mandate not found")]
    NotFound,
    #[error("Invalid signature: {0}")]
    InvalidSignature(#[from] AttestationError),
    #[error("Jurisdiction violation: {0}")]
    JurisdictionViolation(String),
    #[error("Mandate already revoked")]
    AlreadyRevoked,
}

#[derive(Debug, Clone)]
pub struct Mandate {
    pub id: Uuid,
    pub intent_hash: [u8; 32],
    pub public_key: [u8; 32],
    pub signature: [u8; 64],
    pub jurisdiction: String,
    pub action_scope: Vec<String>,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

impl Mandate {
    pub fn is_expired(&self) -> bool {
        Utc::now() > self.expires_at
    }

    pub fn validate(&self) -> Result<(), MandateError> {
        if self.is_expired() {
            return Err(MandateError::Expired);
        }
        verify_signature(&self.public_key, &self.intent_hash, &self.signature)?;
        Ok(())
    }

    pub fn action_allowed(&self, action: &str) -> bool {
        self.action_scope.iter().any(|scope| {
            if scope.ends_with('*') {
                let prefix = &scope[..scope.len() - 1];
                action.starts_with(prefix)
            } else {
                scope == action
            }
        })
    }
}

pub trait MandateStore: Send + Sync {
    fn get_mandate(&self, id: Uuid) -> Result<Option<Mandate>, MandateError>;
    fn insert_mandate(&self, mandate: Mandate) -> Result<(), MandateError>;
    fn revoke_mandate(&self, id: Uuid) -> Result<(), MandateError>;
    fn is_revoked(&self, id: Uuid) -> bool;
}

pub struct DashMapStore {
    mandates: Arc<DashMap<Uuid, Mandate>>,
    revoked: Arc<DashMap<Uuid, DateTime<Utc>>>,
}

impl DashMapStore {
    pub fn new() -> Self {
        Self {
            mandates: Arc::new(DashMap::new()),
            revoked: Arc::new(DashMap::new()),
        }
    }
}

impl Default for DashMapStore {
    fn default() -> Self {
        Self::new()
    }
}

impl MandateStore for DashMapStore {
    fn get_mandate(&self, id: Uuid) -> Result<Option<Mandate>, MandateError> {
        if self.is_revoked(id) {
            return Err(MandateError::AlreadyRevoked);
        }
        Ok(self.mandates.get(&id).map(|m| m.clone()))
    }

    fn insert_mandate(&self, mandate: Mandate) -> Result<(), MandateError> {
        mandate.validate()?;
        self.mandates.insert(mandate.id, mandate);
        Ok(())
    }

    fn revoke_mandate(&self, id: Uuid) -> Result<(), MandateError> {
        if !self.mandates.contains_key(&id) {
            return Err(MandateError::NotFound);
        }
        self.revoked.insert(id, Utc::now());
        self.mandates.remove(&id);
        Ok(())
    }

    fn is_revoked(&self, id: Uuid) -> bool {
        self.revoked.contains_key(&id)
    }
}
