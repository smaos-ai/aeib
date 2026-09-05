use parking_lot::RwLock;
use std::collections::HashSet;
use std::sync::Arc;
use std::time::{Duration, Instant};

pub struct ViewChangeManager {
    #[allow(dead_code)]
    node_id: String,
    nodes: Vec<String>,
    view: Arc<RwLock<u64>>,
    leader: Arc<RwLock<Option<String>>>,
    timeout_duration: Duration,
    last_heartbeat: Arc<RwLock<Instant>>,
    isolated_nodes: Arc<RwLock<HashSet<String>>>,
    view_change_state: Arc<RwLock<String>>,
    view_change_votes: Arc<RwLock<HashSet<String>>>,
}

impl ViewChangeManager {
    pub fn new(node_id: String, nodes: Vec<String>, timeout_duration: Duration) -> Self {
        Self {
            node_id,
            nodes,
            view: Arc::new(RwLock::new(0)),
            leader: Arc::new(RwLock::new(None)),
            timeout_duration,
            last_heartbeat: Arc::new(RwLock::new(Instant::now())),
            isolated_nodes: Arc::new(RwLock::new(HashSet::new())),
            view_change_state: Arc::new(RwLock::new("idle".to_string())),
            view_change_votes: Arc::new(RwLock::new(HashSet::new())),
        }
    }

    pub fn current_view(&self) -> u64 {
        *self.view.read()
    }

    pub fn current_leader(&self) -> Option<String> {
        self.leader.read().clone()
    }

    pub fn set_leader(&self, leader: String) {
        let mut l = self.leader.write();
        *l = Some(leader);
        let mut hb = self.last_heartbeat.write();
        *hb = Instant::now();
    }

    pub fn is_view_change_needed(&self) -> bool {
        let hb = self.last_heartbeat.read();
        hb.elapsed() > self.timeout_duration
    }

    pub fn simulate_timeout(&self) {
        let mut hb = self.last_heartbeat.write();
        *hb = Instant::now() - Duration::from_secs(3);
    }

    pub fn initiate_view_change(&self) {
        let mut state = self.view_change_state.write();
        *state = "started".to_string();

        let mut view = self.view.write();
        *view += 1;

        if let Some(current_leader) = self.leader.read().clone() {
            let mut isolated = self.isolated_nodes.write();
            isolated.insert(current_leader);
        }
    }

    pub fn view_change_state(&self) -> String {
        self.view_change_state.read().clone()
    }

    pub fn elect_new_leader(&self, new_leader: String) {
        let mut leader = self.leader.write();
        *leader = Some(new_leader);

        let mut state = self.view_change_state.write();
        *state = "completed".to_string();
    }

    pub fn is_node_isolated(&self, node_id: &str) -> bool {
        let isolated = self.isolated_nodes.read();
        isolated.contains(node_id)
    }

    pub fn acknowledge_view_change(&self, node_id: String) {
        let mut votes = self.view_change_votes.write();
        votes.insert(node_id);
    }

    pub fn has_quorum_for_view_change(&self) -> bool {
        let votes = self.view_change_votes.read();
        let quorum_needed = (self.nodes.len() / 2) + 1;
        votes.len() >= quorum_needed
    }
}
