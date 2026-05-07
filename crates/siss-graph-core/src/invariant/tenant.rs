use thiserror::Error;

use crate::node::NodeId;

#[derive(Debug, Error)]
#[error("cross-tenant operation denied: source tenant {source_id} != target tenant {target_id}")]
pub struct TenantViolation {
    pub source_id: uuid::Uuid,
    pub target_id: uuid::Uuid,
}

impl TenantViolation {
    pub fn new(source: NodeId, target: NodeId) -> Self {
        Self {
            source_id: source.0,
            target_id: target.0,
        }
    }
}

/// Verify that two entities belong to the same tenant.
/// Returns Ok(()) if they match, Err(TenantViolation) if they don't.
pub fn check_tenant_isolation(source_tenant: NodeId, target_tenant: NodeId) -> Result<(), TenantViolation> {
    if source_tenant == target_tenant {
        Ok(())
    } else {
        Err(TenantViolation::new(source_tenant, target_tenant))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_same_tenant_allowed() {
        let tenant = NodeId::new();
        assert!(check_tenant_isolation(tenant, tenant).is_ok());
    }

    #[test]
    fn test_cross_tenant_denied() {
        let t1 = NodeId::new();
        let t2 = NodeId::new();
        let result = check_tenant_isolation(t1, t2);
        assert!(result.is_err());
    }
}
