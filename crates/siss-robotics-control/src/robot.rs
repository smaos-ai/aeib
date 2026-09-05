use crate::error::{RoboticsError, Result};
use crate::Trajectory;
use serde::{Deserialize, Serialize};
use std::net::IpAddr;

/// UR10e robot configuration
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RobotConfig {
    /// Robot IP address
    pub ip_address: String,
    /// UR script port (typically 29999)
    pub port: u16,
    /// Max joint speed (deg/s)
    pub max_joint_speed: f64,
    /// Max linear speed (m/s)
    pub max_linear_speed: f64,
    /// Payload capacity (kg)
    pub payload_kg: f64,
}

impl Default for RobotConfig {
    fn default() -> Self {
        Self {
            ip_address: "192.168.1.10".to_string(),
            port: 29999,
            max_joint_speed: 180.0,
            max_linear_speed: 1.0,
            payload_kg: 10.0,
        }
    }
}

/// Joint state
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JointState {
    pub position: f64, // radians
    pub velocity: f64,
    pub torque: f64,
}

/// End effector state
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EndEffectorState {
    pub position: [f64; 3], // x, y, z in meters
    pub orientation: [f64; 3], // roll, pitch, yaw in radians
}

/// Robot operational state
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RobotState {
    pub joint_states: Vec<JointState>,
    pub end_effector: EndEffectorState,
    pub is_moving: bool,
    pub timestamp: i64,
}

/// UR10e Robot
pub struct Robot {
    config: RobotConfig,
    state: RobotState,
    connected: bool,
}

impl Robot {
    /// Create new robot
    pub fn new(config: RobotConfig) -> Result<Self> {
        // Validate config
        config.ip_address.parse::<IpAddr>()
            .map_err(|_| RoboticsError::ConfigError("Invalid IP address".into()))?;

        let state = RobotState {
            joint_states: vec![JointState {
                position: 0.0,
                velocity: 0.0,
                torque: 0.0,
            }; 6], // UR10e has 6 joints
            end_effector: EndEffectorState {
                position: [0.0, 0.0, 0.0],
                orientation: [0.0, 0.0, 0.0],
            },
            is_moving: false,
            timestamp: chrono::Utc::now().timestamp(),
        };

        Ok(Self {
            config,
            state,
            connected: false,
        })
    }

    /// Connect to robot (UR10e network interface)
    pub async fn connect(&mut self) -> Result<()> {
        // TODO: Jun 2027 - Real UR+ API connection
        // For now: just mark as connected
        self.connected = true;
        Ok(())
    }

    /// Disconnect
    pub async fn disconnect(&mut self) -> Result<()> {
        self.connected = false;
        Ok(())
    }

    /// Execute trajectory
    pub async fn execute_trajectory(&mut self, trajectory: &Trajectory) -> Result<()> {
        if !self.connected {
            return Err(RoboticsError::NotConnected);
        }

        self.state.is_moving = true;

        // TODO: Jun 2027 - Send to UR10e controller via URScript
        // For now: simulate execution
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

        self.state.is_moving = false;
        self.state.timestamp = chrono::Utc::now().timestamp();

        Ok(())
    }

    /// Emergency stop
    pub async fn emergency_stop(&mut self) -> Result<()> {
        self.state.is_moving = false;
        // TODO: Jun 2027 - Send emergency stop to robot
        Ok(())
    }

    /// Get current state
    pub fn state(&self) -> &RobotState {
        &self.state
    }

    /// Check if connected
    pub fn is_connected(&self) -> bool {
        self.connected
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_robot_config_default() {
        let config = RobotConfig::default();
        assert_eq!(config.port, 29999);
        assert_eq!(config.payload_kg, 10.0);
    }

    #[test]
    fn test_robot_creation() {
        let config = RobotConfig::default();
        let robot = Robot::new(config).unwrap();
        assert!(!robot.is_connected());
        assert_eq!(robot.state().joint_states.len(), 6);
    }

    #[test]
    fn test_robot_invalid_config() {
        let mut config = RobotConfig::default();
        config.ip_address = "invalid_ip".to_string();
        let result = Robot::new(config);
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_robot_connect() {
        let config = RobotConfig::default();
        let mut robot = Robot::new(config).unwrap();
        assert!(robot.connect().await.is_ok());
        assert!(robot.is_connected());
    }

    #[tokio::test]
    async fn test_robot_emergency_stop() {
        let config = RobotConfig::default();
        let mut robot = Robot::new(config).unwrap();
        robot.state.is_moving = true;
        robot.emergency_stop().await.unwrap();
        assert!(!robot.state.is_moving);
    }
}
