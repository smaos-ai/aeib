use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum AccessControlError {
    #[error("Permission denied for operation {operation} on {resource}")]
    PermissionDenied { operation: String, resource: String },
    #[error("Invalid customer namespace")]
    InvalidCustomerNamespace,
    #[error("Role not found: {0}")]
    RoleNotFound(String),
}

/// Permissions that can be granted to customers
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Permission {
    Query,
    Write,
    Delete,
    ManageKeys,
    ViewAuditLog,
}

/// Roles with predefined permission sets
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Role {
    Admin,      // All permissions
    Analyst,    // Query, ViewAuditLog
    Operator,   // Query, Write
    Reader,     // Query only
}

impl Role {
    /// Get default permissions for this role
    pub fn permissions(&self) -> Vec<Permission> {
        match self {
            Role::Admin => vec![
                Permission::Query,
                Permission::Write,
                Permission::Delete,
                Permission::ManageKeys,
                Permission::ViewAuditLog,
            ],
            Role::Analyst => vec![Permission::Query, Permission::ViewAuditLog],
            Role::Operator => vec![Permission::Query, Permission::Write],
            Role::Reader => vec![Permission::Query],
        }
    }
}

/// Customer namespace for data isolation
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CustomerNamespace {
    id: String,
}

impl CustomerNamespace {
    pub fn new(id: String) -> Self {
        Self { id }
    }

    pub fn id(&self) -> &str {
        &self.id
    }
}

/// RBAC policy entry
#[derive(Clone, Debug)]
struct ACLEntry {
    customer: CustomerNamespace,
    role: Role,
    permissions: Vec<Permission>,
}

/// Role-Based Access Control for multi-customer isolation
pub struct AccessControl {
    acl: HashMap<String, Vec<ACLEntry>>,
}

impl AccessControl {
    pub fn new() -> Self {
        Self {
            acl: HashMap::new(),
        }
    }

    /// Grant a permission to a customer with a specific role
    pub fn grant_permission(
        &mut self,
        customer: CustomerNamespace,
        permission: Permission,
        role: Role,
    ) -> Result<(), AccessControlError> {
        let customer_key = customer.id().to_string();

        let permissions = role.permissions();
        if !permissions.contains(&permission) {
            return Err(AccessControlError::RoleNotFound(format!(
                "Permission {:?} not in role {:?}",
                permission, role
            )));
        }

        let entry = ACLEntry {
            customer: customer.clone(),
            role,
            permissions,
        };

        self.acl
            .entry(customer_key)
            .or_insert_with(Vec::new)
            .push(entry);

        Ok(())
    }

    /// Check if a customer can perform an operation on another customer's data
    pub fn check_access(
        &self,
        actor_customer: &CustomerNamespace,
        target_customer: &CustomerNamespace,
        permission: Permission,
    ) -> bool {
        // Cross-customer access is always denied
        if actor_customer != target_customer {
            return false;
        }

        // Check if the actor's customer has the required permission
        let customer_key = actor_customer.id();
        if let Some(entries) = self.acl.get(customer_key) {
            entries
                .iter()
                .any(|entry| entry.permissions.contains(&permission))
        } else {
            false
        }
    }

    /// Check if a customer can query a capsule
    pub fn can_query_capsule(
        &self,
        customer: &CustomerNamespace,
        capsule_owner: &CustomerNamespace,
    ) -> bool {
        // Only the owning customer can query
        if customer != capsule_owner {
            return false;
        }

        self.check_access(customer, capsule_owner, Permission::Query)
    }

    /// Revoke all permissions for a customer
    pub fn revoke_customer(
        &mut self,
        customer: &CustomerNamespace,
    ) -> Result<(), AccessControlError> {
        self.acl.remove(customer.id());
        Ok(())
    }

    /// Get all roles for a customer
    pub fn get_customer_roles(&self, customer: &CustomerNamespace) -> Vec<Role> {
        self.acl
            .get(customer.id())
            .map(|entries| entries.iter().map(|e| e.role.clone()).collect())
            .unwrap_or_default()
    }
}

impl Default for AccessControl {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_role_permissions() {
        assert!(Role::Admin.permissions().contains(&Permission::Delete));
        assert!(!Role::Reader.permissions().contains(&Permission::Delete));
        assert!(Role::Reader.permissions().contains(&Permission::Query));
    }

    #[test]
    fn test_customer_namespace_isolation() {
        let customer_a = CustomerNamespace::new("customer_a".to_string());
        let customer_b = CustomerNamespace::new("customer_b".to_string());

        assert_ne!(customer_a, customer_b);
    }

    #[test]
    fn test_grant_permission() {
        let mut ac = AccessControl::new();
        let customer = CustomerNamespace::new("test_customer".to_string());

        let result = ac.grant_permission(customer.clone(), Permission::Query, Role::Reader);
        assert!(result.is_ok());

        let roles = ac.get_customer_roles(&customer);
        assert!(!roles.is_empty());
    }

    #[test]
    fn test_same_customer_can_access() {
        let mut ac = AccessControl::new();
        let customer = CustomerNamespace::new("customer_a".to_string());

        ac.grant_permission(customer.clone(), Permission::Query, Role::Reader)
            .expect("Grant should succeed");

        let can_access = ac.check_access(&customer, &customer, Permission::Query);
        assert!(can_access);
    }

    #[test]
    fn test_cross_customer_access_denied() {
        let mut ac = AccessControl::new();
        let customer_a = CustomerNamespace::new("customer_a".to_string());
        let customer_b = CustomerNamespace::new("customer_b".to_string());

        ac.grant_permission(customer_a.clone(), Permission::Query, Role::Admin)
            .expect("Grant should succeed");

        // Even Admin should not access another customer's data
        let can_access = ac.check_access(&customer_a, &customer_b, Permission::Query);
        assert!(!can_access);
    }

    #[test]
    fn test_reader_cannot_write() {
        let mut ac = AccessControl::new();
        let customer = CustomerNamespace::new("customer_a".to_string());

        ac.grant_permission(customer.clone(), Permission::Query, Role::Reader)
            .expect("Grant should succeed");

        let can_write = ac.check_access(&customer, &customer, Permission::Write);
        assert!(!can_write);
    }

    #[test]
    fn test_admin_can_do_everything() {
        let mut ac = AccessControl::new();
        let customer = CustomerNamespace::new("admin_customer".to_string());

        ac.grant_permission(customer.clone(), Permission::Query, Role::Admin)
            .expect("Grant should succeed");

        assert!(ac.check_access(&customer, &customer, Permission::Query));
        assert!(ac.check_access(&customer, &customer, Permission::Write));
        assert!(ac.check_access(&customer, &customer, Permission::Delete));
        assert!(ac.check_access(&customer, &customer, Permission::ManageKeys));
        assert!(ac.check_access(&customer, &customer, Permission::ViewAuditLog));
    }

    #[test]
    fn test_revoke_customer() {
        let mut ac = AccessControl::new();
        let customer = CustomerNamespace::new("customer_a".to_string());

        ac.grant_permission(customer.clone(), Permission::Query, Role::Reader)
            .expect("Grant should succeed");

        ac.revoke_customer(&customer).expect("Revoke should succeed");

        let roles = ac.get_customer_roles(&customer);
        assert!(roles.is_empty());
    }

    #[test]
    fn test_can_query_capsule_isolation() {
        let mut ac = AccessControl::new();
        let owner = CustomerNamespace::new("owner".to_string());
        let other = CustomerNamespace::new("other".to_string());

        ac.grant_permission(owner.clone(), Permission::Query, Role::Reader)
            .expect("Grant owner should succeed");
        ac.grant_permission(other.clone(), Permission::Query, Role::Admin)
            .expect("Grant other should succeed");

        // Owner can query their own capsule
        assert!(ac.can_query_capsule(&owner, &owner));

        // Other cannot query owner's capsule (even as Admin)
        assert!(!ac.can_query_capsule(&other, &owner));
    }
}
