use dashmap::DashMap;
use parking_lot::Mutex;
use std::collections::VecDeque;
use std::sync::Arc;
use std::time::Duration;
use uuid::Uuid;

use crate::a2a_protocol::A2AMessage;
use crate::agent_metadata::AgentMetadata;
use crate::bounds::MongeGapBound;
use crate::conflict_resolver::ConflictResolver;
use crate::errors::SwarmCoordinatorError;

pub struct SwarmCoordinator {
    local_agent_id: Uuid,
    agents: Arc<DashMap<Uuid, AgentMetadata>>,
    monge_bounds: Arc<DashMap<Uuid, MongeGapBound>>,
    message_queues: Arc<DashMap<Uuid, Arc<Mutex<VecDeque<A2AMessage>>>>>,
}

impl SwarmCoordinator {
    pub fn new(local_agent_id: Uuid) -> Self {
        Self {
            local_agent_id,
            agents: Arc::new(DashMap::new()),
            monge_bounds: Arc::new(DashMap::new()),
            message_queues: Arc::new(DashMap::new()),
        }
    }

    pub fn local_agent_id(&self) -> Uuid {
        self.local_agent_id
    }

    pub fn register_agent(
        &self,
        agent_id: Uuid,
        public_key: [u8; 32],
    ) -> Result<(), SwarmCoordinatorError> {
        if self.agents.contains_key(&agent_id) {
            return Err(SwarmCoordinatorError::AgentNotFound(
                "Agent already registered".to_string(),
            ));
        }

        let metadata = AgentMetadata::new(agent_id, public_key);
        self.agents.insert(agent_id, metadata);

        let bound = MongeGapBound::new(agent_id);
        self.monge_bounds.insert(agent_id, bound);

        Ok(())
    }

    pub fn get_agent(&self, agent_id: Uuid) -> Result<AgentMetadata, SwarmCoordinatorError> {
        self.agents
            .get(&agent_id)
            .map(|entry| entry.value().clone())
            .ok_or_else(|| SwarmCoordinatorError::AgentNotFound(agent_id.to_string()))
    }

    pub fn get_bounds(&self, agent_id: Uuid) -> Result<MongeGapBound, SwarmCoordinatorError> {
        self.monge_bounds
            .get(&agent_id)
            .map(|entry| entry.value().clone())
            .ok_or_else(|| SwarmCoordinatorError::AgentNotFound(agent_id.to_string()))
    }

    pub fn delegate(
        &self,
        from_agent_id: Uuid,
        to_agent_id: Uuid,
    ) -> Result<(), SwarmCoordinatorError> {
        if from_agent_id == to_agent_id {
            return Err(SwarmCoordinatorError::CycleDetected(
                "Agent cannot delegate to itself".to_string(),
            ));
        }

        if !self.agents.contains_key(&from_agent_id) {
            return Err(SwarmCoordinatorError::AgentNotFound(
                from_agent_id.to_string(),
            ));
        }

        if !self.agents.contains_key(&to_agent_id) {
            return Err(SwarmCoordinatorError::AgentNotFound(
                to_agent_id.to_string(),
            ));
        }

        if self.detect_cycle(to_agent_id, from_agent_id, 0)? {
            return Err(SwarmCoordinatorError::CycleDetected(
                "Delegation would create a cycle".to_string(),
            ));
        }

        {
            let mut from_bound = self
                .monge_bounds
                .get_mut(&from_agent_id)
                .ok_or_else(|| SwarmCoordinatorError::AgentNotFound(from_agent_id.to_string()))?;

            from_bound.add_delegation(to_agent_id)?;
        }

        {
            let from_bound = self.monge_bounds.get(&from_agent_id).unwrap();
            let new_depth = from_bound.current_depth + 1;

            if new_depth > 3 {
                return Err(SwarmCoordinatorError::DepthLimitExceeded);
            }

            if let Some(mut to_bound) = self.monge_bounds.get_mut(&to_agent_id) {
                to_bound.current_depth = new_depth;
            }
        }

        Ok(())
    }

    fn detect_cycle(
        &self,
        current: Uuid,
        target: Uuid,
        depth: usize,
    ) -> Result<bool, SwarmCoordinatorError> {
        if depth > 3 {
            return Ok(false);
        }

        if let Some(bound) = self.monge_bounds.get(&current) {
            for delegated in &bound.delegated_to {
                if *delegated == target {
                    return Ok(true);
                }

                if self.detect_cycle(*delegated, target, depth + 1)? {
                    return Ok(true);
                }
            }
        }

        Ok(false)
    }

    pub fn send_message(&self, msg: A2AMessage) -> Result<(), SwarmCoordinatorError> {
        if !self.agents.contains_key(&msg.from_agent_id) {
            return Err(SwarmCoordinatorError::AgentNotFound(
                msg.from_agent_id.to_string(),
            ));
        }

        if !self.agents.contains_key(&msg.to_agent_id) {
            return Err(SwarmCoordinatorError::AgentNotFound(
                msg.to_agent_id.to_string(),
            ));
        }

        let queue = self
            .message_queues
            .entry(msg.to_agent_id)
            .or_insert_with(|| Arc::new(Mutex::new(VecDeque::new())))
            .clone();

        let mut q = queue.lock();

        if q.len() >= 1000 {
            q.pop_front();
        }

        q.push_back(msg);
        Ok(())
    }

    pub fn process_message(
        &self,
        agent_id: Uuid,
    ) -> Result<Option<A2AMessage>, SwarmCoordinatorError> {
        if !self.agents.contains_key(&agent_id) {
            return Err(SwarmCoordinatorError::AgentNotFound(agent_id.to_string()));
        }

        if let Some(queue_entry) = self.message_queues.get(&agent_id) {
            let queue = queue_entry.clone();
            let mut q = queue.lock();
            Ok(q.pop_front())
        } else {
            Ok(None)
        }
    }

    pub fn get_queue_depth(&self, agent_id: Uuid) -> Result<usize, SwarmCoordinatorError> {
        if !self.agents.contains_key(&agent_id) {
            return Err(SwarmCoordinatorError::AgentNotFound(agent_id.to_string()));
        }

        if let Some(queue_entry) = self.message_queues.get(&agent_id) {
            let queue = queue_entry.clone();
            let q = queue.lock();
            Ok(q.len())
        } else {
            Ok(0)
        }
    }

    pub fn resolve_conflict(&self, msg1: &A2AMessage, msg2: &A2AMessage) -> A2AMessage {
        let resolver = ConflictResolver::new(crate::ConflictStrategy::HighestHash);
        resolver.resolve(msg1, msg2)
    }

    pub fn resolve_conflict_by_timestamp(
        &self,
        msg1: &A2AMessage,
        msg2: &A2AMessage,
    ) -> A2AMessage {
        let resolver = ConflictResolver::new(crate::ConflictStrategy::VectorClock);
        resolver.resolve(msg1, msg2)
    }

    pub fn send_message_with_timeout(
        &self,
        msg: A2AMessage,
        _timeout: Duration,
    ) -> Result<(), SwarmCoordinatorError> {
        self.send_message(msg)
    }
}
