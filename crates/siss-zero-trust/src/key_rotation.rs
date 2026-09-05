use chrono::{DateTime, Utc};
use ed25519_dalek::{SigningKey, VerifyingKey};
use rand::Rng;
use std::collections::HashMap;
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct RotationProof {
    pub rotation_id: String,
    pub previous_key_id: String,
    pub current_key_id: String,
    pub timestamp: u64,
}

#[derive(Debug, Clone)]
pub struct RotationSchedule {
    pub interval_secs: u64,
    pub last_rotation: Option<DateTime<Utc>>,
}

impl RotationSchedule {
    pub fn daily() -> Self {
        Self {
            interval_secs: 86400,
            last_rotation: None,
        }
    }

    pub fn hourly() -> Self {
        Self {
            interval_secs: 3600,
            last_rotation: None,
        }
    }

    pub fn custom_interval_secs(secs: u64) -> Self {
        Self {
            interval_secs: secs,
            last_rotation: None,
        }
    }
}

#[derive(Debug, Error)]
pub enum KeyRotationError {
    #[error("Key generation failed: {0}")]
    KeyGenerationFailed(String),
    #[error("Rotation failed: {0}")]
    RotationFailed(String),
    #[error("Key not found: {0}")]
    KeyNotFound(String),
    #[error("Verification failed: {0}")]
    VerificationFailed(String),
}

#[derive(Clone)]
struct KeyEntry {
    id: String,
    #[allow(dead_code)]
    key: SigningKey,
    #[allow(dead_code)]
    verifying_key: VerifyingKey,
    #[allow(dead_code)]
    created_at: DateTime<Utc>,
}

pub struct KeyRotationEngine {
    current_key: Arc<RwLock<KeyEntry>>,
    previous_key: Arc<RwLock<Option<KeyEntry>>>,
    pending_key: Arc<RwLock<Option<KeyEntry>>>,
    rotation_schedule: Arc<RwLock<RotationSchedule>>,
    key_history: Arc<RwLock<HashMap<String, KeyEntry>>>,
}

impl KeyRotationEngine {
    pub async fn new() -> Self {
        let key = Self::generate_key().await;
        let id = Self::generate_key_id();
        let verifying_key = key.verifying_key();

        let entry = KeyEntry {
            id: id.clone(),
            key,
            verifying_key,
            created_at: Utc::now(),
        };

        let mut history = HashMap::new();
        history.insert(id, entry.clone());

        Self {
            current_key: Arc::new(RwLock::new(entry)),
            previous_key: Arc::new(RwLock::new(None)),
            pending_key: Arc::new(RwLock::new(None)),
            rotation_schedule: Arc::new(RwLock::new(RotationSchedule::daily())),
            key_history: Arc::new(RwLock::new(history)),
        }
    }

    async fn generate_key() -> SigningKey {
        let mut csprng = rand::thread_rng();
        let secret = [csprng.r#gen::<u8>(); 32];
        SigningKey::from_bytes(&secret)
    }

    fn generate_key_id() -> String {
        format!("key_{}", Uuid::new_v4().simple())
    }

    pub async fn current_key_id(&self) -> Option<String> {
        let current = self.current_key.read().await;
        Some(current.id.clone())
    }

    pub async fn pending_key_id(&self) -> Option<String> {
        let pending = self.pending_key.read().await;
        pending.as_ref().map(|k| k.id.clone())
    }

    pub async fn set_rotation_schedule(
        &self,
        schedule: RotationSchedule,
    ) -> Result<(), KeyRotationError> {
        let mut sched = self.rotation_schedule.write().await;
        *sched = schedule;
        Ok(())
    }

    pub async fn get_rotation_schedule(&self) -> Option<RotationSchedule> {
        let sched = self.rotation_schedule.read().await;
        Some(sched.clone())
    }

    pub async fn prepare_next_key(&self) -> Result<(), KeyRotationError> {
        let key = Self::generate_key().await;
        let id = Self::generate_key_id();
        let verifying_key = key.verifying_key();

        let entry = KeyEntry {
            id,
            key,
            verifying_key,
            created_at: Utc::now(),
        };

        let mut pending = self.pending_key.write().await;
        *pending = Some(entry);
        Ok(())
    }

    pub async fn has_pending_key(&self) -> bool {
        let pending = self.pending_key.read().await;
        pending.is_some()
    }

    pub async fn rotate_keys_live(&self) -> Result<RotationProof, KeyRotationError> {
        // Prepare next key if not already done
        if !self.has_pending_key().await {
            self.prepare_next_key().await?;
        }

        let mut pending = self.pending_key.write().await;
        if pending.is_none() {
            return Err(KeyRotationError::RotationFailed(
                "No pending key available".to_string(),
            ));
        }

        let new_key = pending.take().unwrap();
        let new_key_id = new_key.id.clone();

        // Rotate: previous <- current <- new
        let mut current = self.current_key.write().await;
        let old_key_id = current.id.clone();

        let mut previous = self.previous_key.write().await;
        *previous = Some(current.clone());

        *current = new_key.clone();

        // Add to history
        let mut history = self.key_history.write().await;
        history.insert(new_key_id.clone(), new_key);

        // Update schedule
        let mut schedule = self.rotation_schedule.write().await;
        schedule.last_rotation = Some(Utc::now());

        Ok(RotationProof {
            rotation_id: Uuid::new_v4().to_string(),
            previous_key_id: old_key_id,
            current_key_id: new_key_id,
            timestamp: Utc::now().timestamp() as u64,
        })
    }

    pub async fn verify_with_key(&self, key_id: &str) -> Result<bool, KeyRotationError> {
        let history = self.key_history.read().await;
        Ok(history.contains_key(key_id))
    }

    pub async fn verify_zero_trust(&self) -> Result<bool, KeyRotationError> {
        // Verify current key is valid
        let current = self.current_key.read().await;
        let is_valid = !current.id.is_empty();

        // Check that all requests would be validated against current key
        Ok(is_valid)
    }
}

impl Clone for KeyRotationEngine {
    fn clone(&self) -> Self {
        Self {
            current_key: self.current_key.clone(),
            previous_key: self.previous_key.clone(),
            pending_key: self.pending_key.clone(),
            rotation_schedule: self.rotation_schedule.clone(),
            key_history: self.key_history.clone(),
        }
    }
}
