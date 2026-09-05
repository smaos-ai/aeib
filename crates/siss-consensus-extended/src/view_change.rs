use crate::error::{ConsensusError, Result};
use serde::{Deserialize, Serialize};

/// View change state
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ViewChangeState {
    Normal,
    ViewChanging,
    NewViewReady,
}

/// View change info
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ViewChangeInfo {
    pub new_view: u64,
    pub state: ViewChangeState,
    pub supporters: Vec<u32>,
    pub timeout_at: i64,
}

impl ViewChangeInfo {
    /// Create new view change
    pub fn new(new_view: u64, timeout_ms: u64) -> Self {
        let timeout_at = chrono::Utc::now().timestamp_millis() as i64 + timeout_ms as i64;
        Self {
            new_view,
            state: ViewChangeState::ViewChanging,
            supporters: Vec::new(),
            timeout_at,
        }
    }

    /// Add supporter to view change
    pub fn add_supporter(&mut self, node_id: u32) -> Result<()> {
        if self.supporters.contains(&node_id) {
            return Err(ConsensusError::DuplicateMessage);
        }
        self.supporters.push(node_id);
        Ok(())
    }

    /// Check if quorum reached
    pub fn is_quorum(&self, quorum_size: u32) -> bool {
        self.supporters.len() as u32 >= quorum_size
    }

    /// Check if timeout expired
    pub fn is_timeout_expired(&self) -> bool {
        chrono::Utc::now().timestamp_millis() as i64 > self.timeout_at
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_view_change_creation() {
        let vc = ViewChangeInfo::new(1, 5000);
        assert_eq!(vc.new_view, 1);
        assert_eq!(vc.state, ViewChangeState::ViewChanging);
        assert!(vc.supporters.is_empty());
    }

    #[test]
    fn test_add_supporter() {
        let mut vc = ViewChangeInfo::new(1, 5000);
        assert!(vc.add_supporter(0).is_ok());
        assert!(vc.add_supporter(1).is_ok());
        assert!(vc.add_supporter(0).is_err()); // Duplicate
    }

    #[test]
    fn test_quorum_check() {
        let mut vc = ViewChangeInfo::new(1, 5000);
        vc.add_supporter(0).unwrap();
        assert!(!vc.is_quorum(2));
        vc.add_supporter(1).unwrap();
        assert!(vc.is_quorum(2));
    }
}
