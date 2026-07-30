use uuid::Uuid;
use crate::errors::SwarmCoordinatorError;

#[derive(Debug, Clone)]
pub struct MongeGapBound {
    pub agent_id: Uuid,
    pub current_depth: usize,
    pub delegation_count: usize,
    pub parent_hash: [u8; 32],
    pub max_depth: usize,
    pub max_agents: usize,
    pub delegated_to: Vec<Uuid>,  // Track delegations for cycle detection
}

impl MongeGapBound {
    pub fn new(agent_id: Uuid) -> Self {
        Self {
            agent_id,
            current_depth: 0,
            delegation_count: 0,
            parent_hash: [0u8; 32],
            max_depth: 3,
            max_agents: 5,
            delegated_to: Vec::new(),
        }
    }

    pub fn is_within_bounds(&self) -> bool {
        self.current_depth <= self.max_depth && self.delegation_count <= self.max_agents
    }

    pub fn add_delegation(&mut self, target_agent_id: Uuid) -> Result<(), SwarmCoordinatorError> {
        if !self.is_within_bounds() {
            return Err(SwarmCoordinatorError::BoundsExceeded(
                format!(
                    "depth {} > max {}, agents {} >= max {}",
                    self.current_depth, self.max_depth, self.delegation_count, self.max_agents
                ),
            ));
        }

        if self.delegation_count >= self.max_agents {
            return Err(SwarmCoordinatorError::DelegationLimitReached);
        }

        self.delegated_to.push(target_agent_id);
        self.delegation_count += 1;
        Ok(())
    }

    pub fn can_delegate_to(&self, _target_agent_id: Uuid) -> Result<(), SwarmCoordinatorError> {
        if !self.is_within_bounds() {
            return Err(SwarmCoordinatorError::BoundsExceeded(
                format!(
                    "depth {} > max {}, agents {} >= max {}",
                    self.current_depth, self.max_depth, self.delegation_count, self.max_agents
                ),
            ));
        }
        Ok(())
    }
}
