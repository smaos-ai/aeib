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
    pub delegated_to: Vec<Uuid>,
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

    pub fn add_delegation(&mut self, delegated_agent_id: Uuid) -> Result<(), SwarmCoordinatorError> {
        if self.delegation_count >= self.max_agents {
            return Err(SwarmCoordinatorError::DelegationLimitExceeded);
        }

        self.delegated_to.push(delegated_agent_id);
        self.delegation_count += 1;

        Ok(())
    }
}
