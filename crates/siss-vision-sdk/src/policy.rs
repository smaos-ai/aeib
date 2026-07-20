use crate::{CreatorPolicy, VisionError, Result};
use uuid::Uuid;
use std::collections::HashMap;
use parking_lot::RwLock;

pub struct CreatorPolicyStore {
    test_mode: bool,
    policies: RwLock<HashMap<Uuid, CreatorPolicy>>,
}

impl CreatorPolicyStore {
    pub fn new(test_mode: bool) -> Self {
        Self {
            test_mode,
            policies: RwLock::new(HashMap::new()),
        }
    }

    pub async fn save_policy(
        &self,
        creator_id: Uuid,
        policy: &CreatorPolicy,
    ) -> Result<()> {
        self.policies.write().insert(creator_id, policy.clone());
        Ok(())
    }

    pub async fn load_policy(
        &self,
        creator_id: Uuid,
    ) -> Result<CreatorPolicy> {
        self.policies
            .read()
            .get(&creator_id)
            .cloned()
            .ok_or_else(|| VisionError::PolicyError("Policy not found".to_string()))
    }

    pub async fn delete_policy(
        &self,
        creator_id: Uuid,
    ) -> Result<()> {
        self.policies.write().remove(&creator_id);
        Ok(())
    }
}
