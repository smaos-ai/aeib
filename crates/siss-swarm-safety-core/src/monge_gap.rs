//! MongeGap: Security boundary enforcement

use crate::error::{Error, Result};
use crate::types::{AgentId, BoundaryConstraint, SecurityLevel};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Security boundary definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityBoundary {
    pub id: String,
    pub name: String,
    pub level: SecurityLevel,
    pub constraints: Vec<BoundaryConstraint>,
}

/// MongeGap: Enforces security boundaries between agents
pub struct MongeGap {
    boundaries: Arc<RwLock<HashMap<SecurityLevel, SecurityBoundary>>>,
    constraints: Arc<RwLock<Vec<BoundaryConstraint>>>,
    violation_log: Arc<RwLock<Vec<BoundaryViolation>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BoundaryViolation {
    source_agent: AgentId,
    target_agent: AgentId,
    source_level: SecurityLevel,
    target_level: SecurityLevel,
    timestamp: chrono::DateTime<chrono::Utc>,
    reason: String,
}

impl MongeGap {
    /// Create new security boundary enforcer
    pub fn new() -> Self {
        let mut boundaries = HashMap::new();

        // Default boundaries for each security level
        boundaries.insert(
            SecurityLevel::Public,
            SecurityBoundary {
                id: "boundary_public".to_string(),
                name: "Public Boundary".to_string(),
                level: SecurityLevel::Public,
                constraints: Vec::new(),
            },
        );

        boundaries.insert(
            SecurityLevel::Internal,
            SecurityBoundary {
                id: "boundary_internal".to_string(),
                name: "Internal Boundary".to_string(),
                level: SecurityLevel::Internal,
                constraints: Vec::new(),
            },
        );

        boundaries.insert(
            SecurityLevel::Restricted,
            SecurityBoundary {
                id: "boundary_restricted".to_string(),
                name: "Restricted Boundary".to_string(),
                level: SecurityLevel::Restricted,
                constraints: Vec::new(),
            },
        );

        boundaries.insert(
            SecurityLevel::Secret,
            SecurityBoundary {
                id: "boundary_secret".to_string(),
                name: "Secret Boundary".to_string(),
                level: SecurityLevel::Secret,
                constraints: Vec::new(),
            },
        );

        let mut constraints = Vec::new();
        constraints.extend(Self::default_constraints());

        Self {
            boundaries: Arc::new(RwLock::new(boundaries)),
            constraints: Arc::new(RwLock::new(constraints)),
            violation_log: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Check if communication between agents is allowed
    pub fn check_boundary(
        &self,
        source_id: AgentId,
        source_level: SecurityLevel,
        target_id: AgentId,
        target_level: SecurityLevel,
    ) -> Result<()> {
        let constraints = self.constraints.read();

        for constraint in constraints.iter() {
            if constraint.source_security_level == source_level
                && constraint.target_security_level == target_level
            {
                if !constraint.allowed {
                    let violation = BoundaryViolation {
                        source_agent: source_id,
                        target_agent: target_id,
                        source_level,
                        target_level,
                        timestamp: chrono::Utc::now(),
                        reason: format!(
                            "Communication blocked: {} -> {}",
                            source_level as u8, target_level as u8
                        ),
                    };

                    let mut log = self.violation_log.write();
                    log.push(violation.clone());

                    return Err(Error::SecurityBreach(format!(
                        "Boundary violation: {} cannot communicate with {}",
                        source_level as u8, target_level as u8
                    )));
                }
            }
        }

        Ok(())
    }

    /// Register custom boundary constraint
    pub fn register_constraint(&self, constraint: BoundaryConstraint) -> Result<()> {
        let mut constraints = self.constraints.write();
        constraints.push(constraint);
        Ok(())
    }

    /// Get security boundary for level
    pub fn get_boundary(&self, level: SecurityLevel) -> Option<SecurityBoundary> {
        self.boundaries.read().get(&level).cloned()
    }

    /// Get violation log
    pub fn violation_count(&self) -> usize {
        self.violation_log.read().len()
    }

    fn default_constraints() -> Vec<BoundaryConstraint> {
        vec![
            // Public agents can only talk to other public/internal agents
            BoundaryConstraint {
                id: "public_to_public".to_string(),
                source_security_level: SecurityLevel::Public,
                target_security_level: SecurityLevel::Public,
                allowed: true,
            },
            BoundaryConstraint {
                id: "public_to_internal".to_string(),
                source_security_level: SecurityLevel::Public,
                target_security_level: SecurityLevel::Internal,
                allowed: true,
            },
            BoundaryConstraint {
                id: "public_to_restricted".to_string(),
                source_security_level: SecurityLevel::Public,
                target_security_level: SecurityLevel::Restricted,
                allowed: false,
            },
            BoundaryConstraint {
                id: "public_to_secret".to_string(),
                source_security_level: SecurityLevel::Public,
                target_security_level: SecurityLevel::Secret,
                allowed: false,
            },
            // Internal agents have wider access
            BoundaryConstraint {
                id: "internal_to_public".to_string(),
                source_security_level: SecurityLevel::Internal,
                target_security_level: SecurityLevel::Public,
                allowed: true,
            },
            BoundaryConstraint {
                id: "internal_to_internal".to_string(),
                source_security_level: SecurityLevel::Internal,
                target_security_level: SecurityLevel::Internal,
                allowed: true,
            },
            BoundaryConstraint {
                id: "internal_to_restricted".to_string(),
                source_security_level: SecurityLevel::Internal,
                target_security_level: SecurityLevel::Restricted,
                allowed: true,
            },
            BoundaryConstraint {
                id: "internal_to_secret".to_string(),
                source_security_level: SecurityLevel::Internal,
                target_security_level: SecurityLevel::Secret,
                allowed: false,
            },
            // Restricted agents can access internal and restricted
            BoundaryConstraint {
                id: "restricted_to_restricted".to_string(),
                source_security_level: SecurityLevel::Restricted,
                target_security_level: SecurityLevel::Restricted,
                allowed: true,
            },
            BoundaryConstraint {
                id: "restricted_to_internal".to_string(),
                source_security_level: SecurityLevel::Restricted,
                target_security_level: SecurityLevel::Internal,
                allowed: true,
            },
            // Secret agents can access everything
            BoundaryConstraint {
                id: "secret_to_all".to_string(),
                source_security_level: SecurityLevel::Secret,
                target_security_level: SecurityLevel::Public,
                allowed: true,
            },
        ]
    }
}

impl Default for MongeGap {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_monge_gap_creation() {
        let gap = MongeGap::new();
        assert_eq!(gap.violation_count(), 0);
    }

    #[test]
    fn test_allowed_boundary() {
        let gap = MongeGap::new();
        let result = gap.check_boundary(
            AgentId::new(),
            SecurityLevel::Public,
            AgentId::new(),
            SecurityLevel::Public,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_blocked_boundary() {
        let gap = MongeGap::new();
        let result = gap.check_boundary(
            AgentId::new(),
            SecurityLevel::Public,
            AgentId::new(),
            SecurityLevel::Secret,
        );
        assert!(result.is_err());
        assert_eq!(gap.violation_count(), 1);
    }

    #[test]
    fn test_get_boundary() {
        let gap = MongeGap::new();
        let boundary = gap.get_boundary(SecurityLevel::Public);
        assert!(boundary.is_some());
        assert_eq!(boundary.unwrap().level, SecurityLevel::Public);
    }
}
