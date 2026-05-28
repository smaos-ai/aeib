use uuid::Uuid;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::process::Command;

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct AgentHealth {
    pub agent_id: Uuid,
    pub is_healthy: bool,
    pub last_probe_ms: u32,
}

#[derive(Clone, Debug)]
pub enum IsolationError {
    EmptyTree,
    NoHealthyAgents,
    ProbeTimeout,
    ProcessKillFailed(String),
    ProcessNotFound,
}

pub struct AgentProcessRegistry {
    pid_map: HashMap<Uuid, u32>,
}

impl AgentProcessRegistry {
    pub fn new() -> Self {
        Self {
            pid_map: HashMap::new(),
        }
    }

    pub fn register_agent_pid(&mut self, agent_id: Uuid, pid: u32) {
        self.pid_map.insert(agent_id, pid);
    }

    pub fn kill_agent_process(&mut self, agent_id: Uuid) -> Result<(), IsolationError> {
        let pid = self.pid_map.get(&agent_id)
            .copied()
            .ok_or(IsolationError::ProcessNotFound)?;

        let output = Command::new("kill")
            .args(&["-TERM", &pid.to_string()])
            .output()
            .map_err(|e| IsolationError::ProcessKillFailed(e.to_string()))?;

        if !output.status.success() {
            return Err(IsolationError::ProcessKillFailed(
                String::from_utf8_lossy(&output.stderr).to_string()
            ));
        }

        self.pid_map.remove(&agent_id);
        Ok(())
    }
}

impl Default for AgentProcessRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AgentTreeNode {
    pub node_id: usize,
    pub agent_id: Option<Uuid>,
    pub left: Option<Box<AgentTreeNode>>,
    pub right: Option<Box<AgentTreeNode>>,
    pub health: Option<AgentHealth>,
    pub subtree_health_ok: bool,
}

impl AgentTreeNode {
    fn with_agent(node_id: usize, agent_id: Uuid, health: AgentHealth) -> Self {
        Self {
            node_id,
            agent_id: Some(agent_id),
            left: None,
            right: None,
            health: Some(health),
            subtree_health_ok: health.is_healthy,
        }
    }

    fn aggregate_health(&mut self) {
        let mut all_ok = true;
        if let Some(ref health) = self.health {
            all_ok = health.is_healthy;
        }
        if let Some(ref left) = self.left {
            all_ok = all_ok && left.subtree_health_ok;
        }
        if let Some(ref right) = self.right {
            all_ok = all_ok && right.subtree_health_ok;
        }
        self.subtree_health_ok = all_ok;
    }
}

pub struct AgentBinaryTree {
    root: Option<Box<AgentTreeNode>>,
    node_count: usize,
    max_depth: usize,
}

impl AgentBinaryTree {
    pub fn new() -> Self {
        Self {
            root: None,
            node_count: 0,
            max_depth: 0,
        }
    }

    pub fn insert_agent(&mut self, agent_id: Uuid, health: AgentHealth) -> Result<(), IsolationError> {
        if self.root.is_none() {
            self.root = Some(Box::new(AgentTreeNode::with_agent(0, agent_id, health)));
            self.node_count = 1;
            self.max_depth = 1;
        } else {
            self.node_count += 1;
            let depth = ((self.node_count as f64).log2().ceil() + 1.0) as usize;
            if depth > self.max_depth {
                self.max_depth = depth;
            }
            Self::insert_at_index(
                self.root.as_mut().unwrap(),
                self.node_count,
                agent_id,
                health,
            );
        }
        Ok(())
    }

    fn insert_at_index(
        node: &mut AgentTreeNode,
        insert_idx: usize,
        agent_id: Uuid,
        health: AgentHealth,
    ) {
        let left_idx = node.node_id * 2 + 1;
        let right_idx = node.node_id * 2 + 2;

        if insert_idx == left_idx {
            node.left = Some(Box::new(AgentTreeNode::with_agent(left_idx, agent_id, health)));
            node.aggregate_health();
            return;
        }

        if insert_idx == right_idx {
            node.right = Some(Box::new(AgentTreeNode::with_agent(right_idx, agent_id, health)));
            node.aggregate_health();
            return;
        }

        if insert_idx < left_idx {
            return;
        }

        if left_idx < insert_idx && insert_idx < right_idx {
            if let Some(ref mut left) = node.left {
                Self::insert_at_index(left, insert_idx, agent_id, health);
                node.aggregate_health();
            }
            return;
        }

        if insert_idx >= right_idx {
            if let Some(ref mut right) = node.right {
                Self::insert_at_index(right, insert_idx, agent_id, health);
                node.aggregate_health();
            }
        }
    }

    pub fn isolate_failure(&self, symptom: &str) -> Result<Uuid, IsolationError> {
        self.root
            .as_ref()
            .ok_or(IsolationError::EmptyTree)
            .and_then(|root| {
                self.binary_search_isolate(root, symptom, 0)
                    .ok_or(IsolationError::NoHealthyAgents)
            })
    }

    fn binary_search_isolate(&self, node: &AgentTreeNode, _symptom: &str, depth: usize) -> Option<Uuid> {
        if depth > self.max_depth {
            return None;
        }

        if !node.subtree_health_ok {
            if let Some(left) = &node.left {
                if !left.subtree_health_ok {
                    return self.binary_search_isolate(left, _symptom, depth + 1);
                }
            }
            if let Some(right) = &node.right {
                if !right.subtree_health_ok {
                    return self.binary_search_isolate(right, _symptom, depth + 1);
                }
            }
            if let Some(agent_id) = node.agent_id {
                return Some(agent_id);
            }
        }

        node.agent_id
    }

    pub fn update_agent_health(&mut self, agent_id: Uuid, health: AgentHealth) -> Result<(), IsolationError> {
        if let Some(root) = self.root.as_mut() {
            Self::update_recursive(root, agent_id, health);
            Ok(())
        } else {
            Err(IsolationError::EmptyTree)
        }
    }

    fn update_recursive(node: &mut AgentTreeNode, agent_id: Uuid, health: AgentHealth) {
        if node.agent_id == Some(agent_id) {
            node.health = Some(health);
        }
        if let Some(left) = &mut node.left {
            Self::update_recursive(left, agent_id, health.clone());
        }
        if let Some(right) = &mut node.right {
            Self::update_recursive(right, agent_id, health.clone());
        }
        node.aggregate_health();
    }

    pub fn tree_depth(&self) -> usize {
        self.max_depth
    }

    pub fn agent_count(&self) -> usize {
        self.node_count
    }

    pub fn subtree_health_ok(&self) -> bool {
        self.root.as_ref().map(|r| r.subtree_health_ok).unwrap_or(true)
    }

    pub fn isolate_and_kill(&mut self, _symptom: &str, registry: &mut AgentProcessRegistry) -> Result<Uuid, IsolationError> {
        let agent_id = self.isolate_failure(_symptom)?;
        registry.kill_agent_process(agent_id)?;
        Ok(agent_id)
    }
}

impl Default for AgentBinaryTree {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_tree_isolate_fails() {
        let tree = AgentBinaryTree::new();
        assert!(matches!(tree.isolate_failure("symptom"), Err(IsolationError::EmptyTree)));
    }

    #[test]
    fn test_single_agent_insertion() {
        let mut tree = AgentBinaryTree::new();
        let agent_id = Uuid::new_v4();
        let health = AgentHealth {
            agent_id,
            is_healthy: true,
            last_probe_ms: 50,
        };
        tree.insert_agent(agent_id, health).unwrap();
        assert_eq!(tree.agent_count(), 1);
        assert_eq!(tree.tree_depth(), 1);
    }

    #[test]
    fn test_multiple_agent_insertion() {
        let mut tree = AgentBinaryTree::new();
        for _i in 0..5 {
            let agent_id = Uuid::new_v4();
            let health = AgentHealth {
                agent_id,
                is_healthy: true,
                last_probe_ms: 50,
            };
            tree.insert_agent(agent_id, health).unwrap();
        }
        assert_eq!(tree.agent_count(), 5);
        assert!(tree.tree_depth() <= 4);
    }

    #[test]
    fn test_tree_depth_logarithmic() {
        let mut tree = AgentBinaryTree::new();
        for _i in 0..16 {
            let agent_id = Uuid::new_v4();
            let health = AgentHealth {
                agent_id,
                is_healthy: true,
                last_probe_ms: 50,
            };
            tree.insert_agent(agent_id, health).unwrap();
        }
        assert!(tree.tree_depth() <= 5);
    }

    #[test]
    fn test_healthy_tree_returns_any_agent() {
        let mut tree = AgentBinaryTree::new();
        let agent_id = Uuid::new_v4();
        let health = AgentHealth {
            agent_id,
            is_healthy: true,
            last_probe_ms: 50,
        };
        tree.insert_agent(agent_id, health).unwrap();
        let result = tree.isolate_failure("symptom").unwrap();
        assert_eq!(result, agent_id);
    }

    #[test]
    fn test_update_agent_health() {
        let mut tree = AgentBinaryTree::new();
        let agent_id = Uuid::new_v4();
        let health = AgentHealth {
            agent_id,
            is_healthy: true,
            last_probe_ms: 50,
        };
        tree.insert_agent(agent_id, health).unwrap();
        let updated_health = AgentHealth {
            agent_id,
            is_healthy: false,
            last_probe_ms: 60,
        };
        tree.update_agent_health(agent_id, updated_health).unwrap();
        assert!(!tree.subtree_health_ok());
    }

    #[test]
    fn test_unhealthy_agent_detection() {
        let mut tree = AgentBinaryTree::new();
        let healthy_agent = Uuid::new_v4();
        let unhealthy_agent = Uuid::new_v4();

        let health_ok = AgentHealth {
            agent_id: healthy_agent,
            is_healthy: true,
            last_probe_ms: 50,
        };
        tree.insert_agent(healthy_agent, health_ok).unwrap();

        let health_bad = AgentHealth {
            agent_id: unhealthy_agent,
            is_healthy: false,
            last_probe_ms: 150,
        };
        tree.insert_agent(unhealthy_agent, health_bad).unwrap();
        assert!(!tree.subtree_health_ok());
    }

    #[test]
    fn test_aggregate_health_propagation() {
        let mut tree = AgentBinaryTree::new();
        for _i in 0..3 {
            let agent_id = Uuid::new_v4();
            let health = AgentHealth {
                agent_id,
                is_healthy: true,
                last_probe_ms: 50,
            };
            tree.insert_agent(agent_id, health).unwrap();
        }
        assert!(tree.subtree_health_ok());
    }

    #[test]
    fn test_isolate_failure_bsearch_depth_bound() {
        let mut tree = AgentBinaryTree::new();
        let mut agent_ids = vec![];
        for _i in 0..32 {
            let agent_id = Uuid::new_v4();
            agent_ids.push(agent_id);
            let health = AgentHealth {
                agent_id,
                is_healthy: true,
                last_probe_ms: 50,
            };
            tree.insert_agent(agent_id, health).unwrap();
        }
        let result = tree.isolate_failure("any_symptom").unwrap();
        assert!(agent_ids.contains(&result));
        assert!(tree.tree_depth() <= 6);
    }

    #[test]
    fn test_large_tree_depth_still_logarithmic() {
        let mut tree = AgentBinaryTree::new();
        for _i in 0..64 {
            let agent_id = Uuid::new_v4();
            let health = AgentHealth {
                agent_id,
                is_healthy: true,
                last_probe_ms: 50,
            };
            tree.insert_agent(agent_id, health).unwrap();
        }
        assert!(tree.tree_depth() <= 8);
    }
}
