use crate::{AgentBinaryTree, KalmanState};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SwarmState {
    pub swarm_id: Uuid,
    pub agent_count: usize,
    pub is_healthy: bool,
    pub created_at: u64,
    pub capsule_id: Option<Uuid>,
    pub agent_tree_root: Option<Box<AgentTreeNode>>,
    pub observer_state: Option<KalmanState>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AgentTreeNode {
    pub node_id: usize,
    pub agent_id: Option<Uuid>,
    pub left: Option<Box<AgentTreeNode>>,
    pub right: Option<Box<AgentTreeNode>>,
}

impl SwarmState {
    pub fn new(swarm_id: Uuid) -> Self {
        let created_at = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            swarm_id,
            agent_count: 0,
            is_healthy: true,
            created_at,
            capsule_id: None,
            agent_tree_root: None,
            observer_state: None,
        }
    }

    pub fn set_capsule(&mut self, capsule_id: Uuid) {
        self.capsule_id = Some(capsule_id);
    }

    pub fn set_agent_tree(&mut self, root: AgentTreeNode) {
        self.agent_tree_root = Some(Box::new(root));
    }

    pub fn set_observer_state(&mut self, observer: KalmanState) {
        self.observer_state = Some(observer);
    }

    pub fn with_capsule_id(mut self, capsule_id: Uuid) -> Self {
        self.capsule_id = Some(capsule_id);
        self
    }

    pub fn with_observer_state(mut self, observer: KalmanState) -> Self {
        self.observer_state = Some(observer);
        self
    }

    pub fn update_agent_count(&mut self, count: usize) {
        self.agent_count = count;
    }

    pub fn mark_unhealthy(&mut self) {
        self.is_healthy = false;
    }

    pub fn mark_healthy(&mut self) {
        self.is_healthy = true;
    }

    pub fn capsule_active(&self) -> bool {
        self.capsule_id.is_some()
    }

    pub fn has_agent_tree(&self) -> bool {
        self.agent_tree_root.is_some()
    }

    pub fn has_observer(&self) -> bool {
        self.observer_state.is_some()
    }

    pub fn all_components_initialized(&self) -> bool {
        self.capsule_id.is_some() && self.agent_tree_root.is_some() && self.observer_state.is_some()
    }
}

impl Default for SwarmState {
    fn default() -> Self {
        Self::new(Uuid::new_v4())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_swarm_state_creation() {
        let swarm_id = Uuid::new_v4();
        let state = SwarmState::new(swarm_id);
        assert_eq!(state.swarm_id, swarm_id);
        assert_eq!(state.agent_count, 0);
        assert!(state.is_healthy);
    }

    #[test]
    fn test_swarm_state_set_capsule() {
        let mut state = SwarmState::new(Uuid::new_v4());
        let capsule_id = Uuid::new_v4();
        state.set_capsule(capsule_id);
        assert_eq!(state.capsule_id, Some(capsule_id));
        assert!(state.capsule_active());
    }

    #[test]
    fn test_swarm_state_with_capsule_id() {
        let capsule_id = Uuid::new_v4();
        let state = SwarmState::new(Uuid::new_v4()).with_capsule_id(capsule_id);
        assert_eq!(state.capsule_id, Some(capsule_id));
    }

    #[test]
    fn test_swarm_state_set_observer() {
        let mut state = SwarmState::new(Uuid::new_v4());
        let observer = KalmanState::new();
        state.set_observer_state(observer);
        assert!(state.has_observer());
    }

    #[test]
    fn test_swarm_state_with_observer() {
        let observer = KalmanState::new();
        let state = SwarmState::new(Uuid::new_v4()).with_observer_state(observer);
        assert!(state.has_observer());
    }

    #[test]
    fn test_swarm_state_update_agent_count() {
        let mut state = SwarmState::new(Uuid::new_v4());
        state.update_agent_count(10);
        assert_eq!(state.agent_count, 10);
    }

    #[test]
    fn test_swarm_state_health_management() {
        let mut state = SwarmState::new(Uuid::new_v4());
        assert!(state.is_healthy);
        state.mark_unhealthy();
        assert!(!state.is_healthy);
        state.mark_healthy();
        assert!(state.is_healthy);
    }

    #[test]
    fn test_swarm_state_components_initialized() {
        let mut state = SwarmState::new(Uuid::new_v4());
        assert!(!state.all_components_initialized());

        state.set_capsule(Uuid::new_v4());
        assert!(!state.all_components_initialized());

        state.set_observer_state(KalmanState::new());
        assert!(!state.all_components_initialized());

        state.set_agent_tree(AgentTreeNode {
            node_id: 0,
            agent_id: Some(Uuid::new_v4()),
            left: None,
            right: None,
        });
        assert!(state.all_components_initialized());
    }

    #[test]
    fn test_agent_tree_node_creation() {
        let agent_id = Uuid::new_v4();
        let node = AgentTreeNode {
            node_id: 0,
            agent_id: Some(agent_id),
            left: None,
            right: None,
        };
        assert_eq!(node.node_id, 0);
        assert_eq!(node.agent_id, Some(agent_id));
    }
}
