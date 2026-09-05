use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum ReBAcError {
    #[error("Role not found: {0}")]
    RoleNotFound(Uuid),
    #[error("User not found: {0}")]
    UserNotFound(Uuid),
    #[error("Permission denied")]
    PermissionDenied,
    #[error("ReBAC operation failed")]
    OperationFailed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Role {
    pub id: Uuid,
    pub role_name: String,
    pub permissions: Vec<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserRole {
    pub user_id: Uuid,
    pub role_id: Uuid,
    pub assigned_at: chrono::DateTime<chrono::Utc>,
}

pub struct ReBAC {
    roles: DashMap<Uuid, Role>,
    user_roles: DashMap<Uuid, Vec<Uuid>>, // user_id -> [role_ids]
}

impl ReBAC {
    pub fn new() -> Self {
        Self {
            roles: DashMap::new(),
            user_roles: DashMap::new(),
        }
    }

    /// Create a new role with permissions
    pub fn create_role(
        &self,
        role_id: Uuid,
        role_name: String,
        permissions: Vec<String>,
    ) -> Result<Role, ReBAcError> {
        let role = Role {
            id: role_id,
            role_name,
            permissions,
            created_at: chrono::Utc::now(),
        };

        self.roles.insert(role_id, role.clone());
        Ok(role)
    }

    /// Assign a role to a user
    pub fn assign_role_to_user(&self, user_id: Uuid, role_id: Uuid) -> Result<bool, ReBAcError> {
        // Verify role exists
        if !self.roles.contains_key(&role_id) {
            return Err(ReBAcError::RoleNotFound(role_id));
        }

        // Add role to user
        self.user_roles
            .entry(user_id)
            .or_insert_with(Vec::new)
            .push(role_id);

        Ok(true)
    }

    /// Check if a user has a specific permission
    pub fn has_permission(&self, user_id: Uuid, permission: &str) -> Result<bool, ReBAcError> {
        // Get user's roles
        if let Some(role_ids) = self.user_roles.get(&user_id) {
            for role_id in role_ids.iter() {
                if let Some(role) = self.roles.get(role_id) {
                    if role.permissions.contains(&permission.to_string()) {
                        return Ok(true);
                    }
                }
            }
        }

        Ok(false)
    }

    /// Get all permissions for a user
    pub fn get_user_permissions(&self, user_id: Uuid) -> Result<Vec<String>, ReBAcError> {
        let mut permissions = Vec::new();

        if let Some(role_ids) = self.user_roles.get(&user_id) {
            for role_id in role_ids.iter() {
                if let Some(role) = self.roles.get(role_id) {
                    permissions.extend(role.permissions.clone());
                }
            }
        }

        // Remove duplicates
        permissions.sort();
        permissions.dedup();

        Ok(permissions)
    }

    /// Add a permission to a role
    pub fn add_permission_to_role(
        &self,
        role_id: Uuid,
        permission: String,
    ) -> Result<(), ReBAcError> {
        let mut role = self
            .roles
            .get_mut(&role_id)
            .ok_or(ReBAcError::RoleNotFound(role_id))?;

        if !role.permissions.contains(&permission) {
            role.permissions.push(permission);
        }

        Ok(())
    }

    /// Get a role by ID
    pub fn get_role(&self, role_id: Uuid) -> Result<Role, ReBAcError> {
        self.roles
            .get(&role_id)
            .map(|r| r.clone())
            .ok_or(ReBAcError::RoleNotFound(role_id))
    }

    /// Get all roles for a user
    pub fn get_user_roles(&self, user_id: Uuid) -> Result<Vec<Role>, ReBAcError> {
        let mut roles = Vec::new();

        if let Some(role_ids) = self.user_roles.get(&user_id) {
            for role_id in role_ids.iter() {
                if let Some(role) = self.roles.get(role_id) {
                    roles.push(role.clone());
                }
            }
        }

        Ok(roles)
    }

    /// Remove a role from a user
    pub fn remove_role_from_user(&self, user_id: Uuid, role_id: Uuid) -> Result<bool, ReBAcError> {
        if let Some(mut roles) = self.user_roles.get_mut(&user_id) {
            if let Some(pos) = roles.iter().position(|r| *r == role_id) {
                roles.remove(pos);
                return Ok(true);
            }
        }

        Ok(false)
    }

    /// Check claim approval hierarchy
    pub fn can_approve_claim(&self, user_id: Uuid, claim_amount: u64) -> Result<bool, ReBAcError> {
        // Determine required approval level based on claim amount
        let required_permission = match claim_amount {
            0..=50_000_00 => "claim:approve_basic",
            50_000_01..=500_000_00 => "claim:approve_standard",
            500_000_01..=5_000_000_00 => "claim:approve_high",
            _ => "claim:approve_critical",
        };

        self.has_permission(user_id, required_permission)
    }

    /// Create standard claim workflow roles
    pub fn setup_claim_workflow(&self) -> Result<(), ReBAcError> {
        // Analyst role
        let analyst_role = Uuid::new_v4();
        self.create_role(
            analyst_role,
            "claims_analyst".to_string(),
            vec!["claim:read".to_string(), "claim:analyze".to_string()],
        )?;

        // Reviewer role
        let reviewer_role = Uuid::new_v4();
        self.create_role(
            reviewer_role,
            "claims_reviewer".to_string(),
            vec![
                "claim:read".to_string(),
                "claim:review".to_string(),
                "claim:approve_basic".to_string(),
            ],
        )?;

        // Manager role
        let manager_role = Uuid::new_v4();
        self.create_role(
            manager_role,
            "claims_manager".to_string(),
            vec![
                "claim:read".to_string(),
                "claim:review".to_string(),
                "claim:approve_standard".to_string(),
                "claim:override".to_string(),
            ],
        )?;

        Ok(())
    }
}

impl Default for ReBAC {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_role_creation_and_assignment() {
        let rebac = ReBAC::new();
        let role_id = Uuid::new_v4();
        let user_id = Uuid::new_v4();

        let role = rebac
            .create_role(role_id, "test_role".to_string(), vec!["perm1".to_string()])
            .unwrap();
        assert_eq!(role.role_name, "test_role");

        rebac.assign_role_to_user(user_id, role_id).unwrap();
        assert!(rebac.has_permission(user_id, "perm1").unwrap());
    }

    #[test]
    fn test_permission_check() {
        let rebac = ReBAC::new();
        let role_id = Uuid::new_v4();
        let user_id = Uuid::new_v4();

        rebac
            .create_role(role_id, "reader".to_string(), vec!["read".to_string()])
            .unwrap();

        rebac.assign_role_to_user(user_id, role_id).unwrap();

        assert!(rebac.has_permission(user_id, "read").unwrap());
        assert!(!rebac.has_permission(user_id, "write").unwrap());
    }
}
