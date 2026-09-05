use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Policy {
    pub id: Uuid,
    pub tenant_id: Uuid,
    pub category: String, // "egress", "consent", "audit"
    pub rules: Value,     // Arbitrary JSON schema
    pub version: i32,
    pub inheritance_parent_id: Option<Uuid>,
    pub published_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
}

impl Policy {
    pub fn new(
        tenant_id: Uuid,
        category: String,
        rules: Value,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            tenant_id,
            category,
            rules,
            version: 1,
            inheritance_parent_id: None,
            published_at: None,
            created_at: Utc::now(),
        }
    }

    pub fn with_parent(
        tenant_id: Uuid,
        category: String,
        rules: Value,
        parent_id: Uuid,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            tenant_id,
            category,
            rules,
            version: 1,
            inheritance_parent_id: Some(parent_id),
            published_at: None,
            created_at: Utc::now(),
        }
    }

    pub fn publish(&mut self) {
        self.published_at = Some(Utc::now());
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyVersion {
    pub id: Uuid,
    pub policy_id: Uuid,
    pub version_number: i32,
    pub rules: Value,
    pub created_by: Option<String>,
    pub change_summary: Option<String>,
    pub created_at: DateTime<Utc>,
}

impl PolicyVersion {
    pub fn new(
        policy_id: Uuid,
        version_number: i32,
        rules: Value,
        created_by: Option<String>,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            policy_id,
            version_number,
            rules,
            created_by,
            change_summary: None,
            created_at: Utc::now(),
        }
    }
}

pub struct PolicyRegistry {
    policies: HashMap<Uuid, Policy>,
    versions: HashMap<Uuid, Vec<PolicyVersion>>,
    tenant_policies: HashMap<Uuid, Vec<Uuid>>,
}

impl PolicyRegistry {
    pub fn new() -> Self {
        Self {
            policies: HashMap::new(),
            versions: HashMap::new(),
            tenant_policies: HashMap::new(),
        }
    }

    pub fn create_policy(
        &mut self,
        tenant_id: Uuid,
        category: String,
        rules: Value,
    ) -> Policy {
        let policy = Policy::new(tenant_id, category, rules);
        let policy_id = policy.id;

        self.versions.insert(policy_id, vec![
            PolicyVersion::new(policy_id, 1, policy.rules.clone(), None),
        ]);

        self.policies.insert(policy_id, policy.clone());

        self.tenant_policies
            .entry(tenant_id)
            .or_insert_with(Vec::new)
            .push(policy_id);

        policy
    }

    pub fn create_override(
        &mut self,
        tenant_id: Uuid,
        parent_policy_id: Uuid,
        rules_override: Value,
    ) -> Option<Policy> {
        if self.policies.contains_key(&parent_policy_id) {
            if let Some(parent) = self.policies.get(&parent_policy_id) {
                let policy = Policy::with_parent(
                    tenant_id,
                    parent.category.clone(),
                    rules_override,
                    parent_policy_id,
                );

                let policy_id = policy.id;
                self.versions.insert(policy_id, vec![
                    PolicyVersion::new(policy_id, 1, policy.rules.clone(), None),
                ]);

                self.policies.insert(policy_id, policy.clone());

                self.tenant_policies
                    .entry(tenant_id)
                    .or_insert_with(Vec::new)
                    .push(policy_id);

                return Some(policy);
            }
        }

        None
    }

    pub fn publish_policy(&mut self, policy_id: Uuid) -> Option<Policy> {
        if let Some(policy) = self.policies.get_mut(&policy_id) {
            policy.publish();
            Some(policy.clone())
        } else {
            None
        }
    }

    pub fn get_policy(&self, policy_id: Uuid) -> Option<Policy> {
        self.policies.get(&policy_id).cloned()
    }

    pub fn get_policy_version(
        &self,
        policy_id: Uuid,
        version_number: i32,
    ) -> Option<PolicyVersion> {
        self.versions
            .get(&policy_id)
            .and_then(|versions| {
                versions
                    .iter()
                    .find(|v| v.version_number == version_number)
                    .cloned()
            })
    }

    pub fn update_policy_rules(
        &mut self,
        policy_id: Uuid,
        new_rules: Value,
    ) -> Option<Policy> {
        if let Some(policy) = self.policies.get_mut(&policy_id) {
            let new_version_num = policy.version + 1;
            policy.version = new_version_num;
            policy.rules = new_rules.clone();
            policy.published_at = None; // Unpublish on update

            if let Some(versions) = self.versions.get_mut(&policy_id) {
                versions.push(PolicyVersion::new(
                    policy_id,
                    new_version_num,
                    new_rules,
                    None,
                ));
            }

            Some(policy.clone())
        } else {
            None
        }
    }

    pub fn list_tenant_policies(&self, tenant_id: Uuid) -> Vec<Policy> {
        self.tenant_policies
            .get(&tenant_id)
            .map(|policy_ids| {
                policy_ids
                    .iter()
                    .filter_map(|&id| self.policies.get(&id).cloned())
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn list_policy_versions(&self, policy_id: Uuid) -> Vec<PolicyVersion> {
        self.versions
            .get(&policy_id)
            .cloned()
            .unwrap_or_default()
    }

    pub fn resolve_effective_policy(
        &self,
        policy_id: Uuid,
    ) -> Option<Value> {
        if let Some(policy) = self.policies.get(&policy_id) {
            if let Some(parent_id) = policy.inheritance_parent_id {
                if let Some(parent) = self.policies.get(&parent_id) {
                    return Some(merge_policies(&parent.rules, &policy.rules));
                }
            }
            Some(policy.rules.clone())
        } else {
            None
        }
    }

    pub fn count_tenant_policies(&self, tenant_id: Uuid) -> usize {
        self.tenant_policies
            .get(&tenant_id)
            .map(|ids| ids.len())
            .unwrap_or(0)
    }

    pub fn count_policy_versions(&self, policy_id: Uuid) -> usize {
        self.versions
            .get(&policy_id)
            .map(|versions| versions.len())
            .unwrap_or(0)
    }
}

impl Default for PolicyRegistry {
    fn default() -> Self {
        Self::new()
    }
}

fn merge_policies(parent: &Value, child: &Value) -> Value {
    match (parent, child) {
        (Value::Object(p), Value::Object(c)) => {
            let mut merged = p.clone();
            for (key, value) in c {
                merged[key] = value.clone();
            }
            Value::Object(merged)
        }
        _ => child.clone(),
    }
}
