use thiserror::Error;

#[derive(Error, Debug)]
pub enum RoboticsError {
    #[error("Robot not connected")]
    NotConnected,
    #[error("Trajectory invalid: {0}")]
    InvalidTrajectory(String),
    #[error("Safety boundary violated: {0}")]
    SafetyViolation(String),
    #[error("Control error: {0}")]
    ControlError(String),
    #[error("Simulation error: {0}")]
    SimulationError(String),
    #[error("Hardware error: {0}")]
    HardwareError(String),
    #[error("Network error: {0}")]
    NetworkError(String),
    #[error("Configuration error: {0}")]
    ConfigError(String),
}

pub type Result<T> = std::result::Result<T, RoboticsError>;
