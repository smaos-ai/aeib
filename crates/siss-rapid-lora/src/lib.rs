use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

/// A request to update LoRA weights with memory pressure consideration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoraUpdateRequest {
    pub session_id: Uuid,
    pub signal_count: usize,
    pub memory_pressure_pct: f64,
}

/// Decision result from a LoRA update request
#[derive(Debug, Clone, PartialEq)]
pub enum LoraDecision {
    Queued,
    Deferred(String),
}

/// Error types for LoRA operations
#[derive(Debug, Error, PartialEq)]
pub enum LoraError {
    #[error("Memory pressure too high: {0}%")]
    MemoryPressureTooHigh(f64),

    #[error("No signals provided in request")]
    NoSignals,
}

/// Rapid LoRA update manager with memory pressure gating
pub struct RapidLora {
    #[allow(dead_code)]
    pressure_limit_pct: f64,
}

impl RapidLora {
    /// Create a new RapidLora instance with the specified pressure limit
    pub fn new(pressure_limit_pct: f64) -> Self {
        RapidLora { pressure_limit_pct }
    }

    /// Process a LoRA update request
    pub fn request_update(&self, req: LoraUpdateRequest) -> Result<LoraDecision, LoraError> {
        if req.signal_count == 0 {
            return Err(LoraError::NoSignals);
        }

        if req.memory_pressure_pct >= self.pressure_limit_pct {
            return Err(LoraError::MemoryPressureTooHigh(req.memory_pressure_pct));
        }

        Ok(LoraDecision::Queued)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_high_memory_pressure_rejected() {
        let lora = RapidLora::new(85.0);
        let request = LoraUpdateRequest {
            session_id: Uuid::new_v4(),
            signal_count: 5,
            memory_pressure_pct: 90.0,
        };

        let result = lora.request_update(request);
        assert_eq!(result, Err(LoraError::MemoryPressureTooHigh(90.0)));
    }

    #[test]
    fn test_empty_signals_rejected() {
        let lora = RapidLora::new(85.0);
        let request = LoraUpdateRequest {
            session_id: Uuid::new_v4(),
            signal_count: 0,
            memory_pressure_pct: 50.0,
        };

        let result = lora.request_update(request);
        assert_eq!(result, Err(LoraError::NoSignals));
    }

    #[test]
    fn test_valid_request_returns_queued() {
        let lora = RapidLora::new(85.0);
        let request = LoraUpdateRequest {
            session_id: Uuid::new_v4(),
            signal_count: 5,
            memory_pressure_pct: 50.0,
        };

        let result = lora.request_update(request);
        assert_eq!(result, Ok(LoraDecision::Queued));
    }
}
