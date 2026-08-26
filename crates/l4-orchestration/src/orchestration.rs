use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Checkpoint {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub state: String,
    pub action: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PilotState {
    pub request_id: String,
    pub current_state: String,
    pub checkpoints: Vec<Checkpoint>,
    pub requires_human_escalation: bool,
}

pub trait Pilot {
    fn flow(&self) -> Result<Vec<Checkpoint>, String>;
    fn human_escalation(&self) -> bool;
    fn state(&self) -> PilotState;
}

pub struct HotelPilot {
    request_id: String,
    checkpoints: Vec<Checkpoint>,
}

pub struct GlassPilot {
    request_id: String,
    checkpoints: Vec<Checkpoint>,
}

pub struct SchoolPilot {
    request_id: String,
    checkpoints: Vec<Checkpoint>,
}

impl HotelPilot {
    pub fn new() -> Self {
        Self {
            request_id: Uuid::new_v4().to_string(),
            checkpoints: Vec::new(),
        }
    }
}

impl Default for HotelPilot {
    fn default() -> Self {
        Self::new()
    }
}

impl Pilot for HotelPilot {
    fn flow(&self) -> Result<Vec<Checkpoint>, String> {
        let mut checkpoints = vec![
            Checkpoint {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                state: "REQUEST".to_string(),
                action: "Received credit scoring request".to_string(),
            },
            Checkpoint {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                state: "VALIDATE".to_string(),
                action: "Validating application".to_string(),
            },
            Checkpoint {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                state: "EVALUATE".to_string(),
                action: "Evaluating applicant".to_string(),
            },
            Checkpoint {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                state: "DECIDE".to_string(),
                action: "Making decision".to_string(),
            },
            Checkpoint {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now(),
                state: "APPROVED".to_string(),
                action: "Credit approved".to_string(),
            },
        ];
        Ok(checkpoints)
    }

    fn human_escalation(&self) -> bool {
        false
    }

    fn state(&self) -> PilotState {
        PilotState {
            request_id: self.request_id.clone(),
            current_state: "APPROVED".to_string(),
            checkpoints: vec![],
            requires_human_escalation: false,
        }
    }
}

impl GlassPilot {
    pub fn new() -> Self {
        Self {
            request_id: Uuid::new_v4().to_string(),
            checkpoints: Vec::new(),
        }
    }
}

impl Default for GlassPilot {
    fn default() -> Self {
        Self::new()
    }
}

impl Pilot for GlassPilot {
    fn flow(&self) -> Result<Vec<Checkpoint>, String> {
        Ok(vec![])
    }

    fn human_escalation(&self) -> bool {
        false
    }

    fn state(&self) -> PilotState {
        PilotState {
            request_id: self.request_id.clone(),
            current_state: "IDLE".to_string(),
            checkpoints: vec![],
            requires_human_escalation: false,
        }
    }
}

impl SchoolPilot {
    pub fn new() -> Self {
        Self {
            request_id: Uuid::new_v4().to_string(),
            checkpoints: Vec::new(),
        }
    }
}

impl Default for SchoolPilot {
    fn default() -> Self {
        Self::new()
    }
}

impl Pilot for SchoolPilot {
    fn flow(&self) -> Result<Vec<Checkpoint>, String> {
        Ok(vec![])
    }

    fn human_escalation(&self) -> bool {
        false
    }

    fn state(&self) -> PilotState {
        PilotState {
            request_id: self.request_id.clone(),
            current_state: "IDLE".to_string(),
            checkpoints: vec![],
            requires_human_escalation: false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hotel_flow() {
        let pilot = HotelPilot::new();
        let result = pilot.flow();
        assert!(result.is_ok());
        let checkpoints = result.unwrap();
        assert!(checkpoints.len() >= 5);
    }

    #[test]
    fn test_hotel_human_escalation() {
        let pilot = HotelPilot::new();
        assert!(!pilot.human_escalation());
    }

    #[test]
    fn test_hotel_state() {
        let pilot = HotelPilot::new();
        let state = pilot.state();
        assert_eq!(state.current_state, "APPROVED");
    }
}
