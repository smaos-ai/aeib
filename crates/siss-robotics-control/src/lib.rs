//! # SISS Robotics Control
//! UR10e cobot interface with MuJoCo physics simulation.
//! Real hardware control (when available), simulation fallback.
//!
//! Integration point for Phase 3 hardware systems - real hardware available Sep 2026+.

pub mod robot;
pub mod trajectory;
pub mod safety;
pub mod simulation;
pub mod error;

pub use robot::{Robot, RobotState, RobotConfig};
pub use trajectory::{Trajectory, Waypoint};
pub use safety::SafetyBoundary;
pub use simulation::SimulationEngine;
pub use error::{RoboticsError, Result};

#[cfg(test)]
mod tests;

use std::sync::Arc;
use tokio::sync::RwLock;

/// Robotics system controller
pub struct RoboticsController {
    robot: Arc<RwLock<Robot>>,
    sim_engine: Arc<SimulationEngine>,
    use_simulation: bool,
    safety_boundary: Arc<SafetyBoundary>,
}

impl RoboticsController {
    /// Create new robotics controller
    pub fn new(config: RobotConfig, use_simulation: bool) -> Result<Self> {
        let robot = Robot::new(config)?;
        let sim_engine = SimulationEngine::new();
        let safety_boundary = SafetyBoundary::default();

        Ok(Self {
            robot: Arc::new(RwLock::new(robot)),
            sim_engine: Arc::new(sim_engine),
            use_simulation,
            safety_boundary: Arc::new(safety_boundary),
        })
    }

    /// Execute trajectory
    pub async fn execute_trajectory(&self, trajectory: Trajectory) -> Result<()> {
        // Check safety
        self.safety_boundary.validate_trajectory(&trajectory)?;

        if self.use_simulation {
            // Run in simulation
            self.sim_engine.simulate(&trajectory).await?;
        } else {
            // Send to real robot (UR10e API)
            let mut robot = self.robot.write().await;
            robot.execute_trajectory(&trajectory).await?;
        }

        Ok(())
    }

    /// Get robot state
    pub async fn robot_state(&self) -> Result<RobotState> {
        let robot = self.robot.read().await;
        Ok(robot.state().clone())
    }

    /// Emergency stop
    pub async fn emergency_stop(&self) -> Result<()> {
        let mut robot = self.robot.write().await;
        robot.emergency_stop().await
    }

    /// Get simulation engine
    pub fn simulator(&self) -> Arc<SimulationEngine> {
        self.sim_engine.clone()
    }

    /// Switch to simulation mode
    pub fn use_simulation_mode(&mut self) {
        self.use_simulation = true;
    }

    /// Switch to hardware mode
    pub fn use_hardware_mode(&mut self) {
        self.use_simulation = false;
    }
}

#[cfg(test)]
mod controller_tests {
    use super::*;

    #[tokio::test]
    async fn test_controller_creation() {
        let config = RobotConfig::default();
        let controller = RoboticsController::new(config, true).unwrap();
        assert!(controller.use_simulation);
    }

    #[tokio::test]
    async fn test_controller_mode_switching() {
        let config = RobotConfig::default();
        let mut controller = RoboticsController::new(config, true).unwrap();
        assert!(controller.use_simulation);

        controller.use_hardware_mode();
        assert!(!controller.use_simulation);

        controller.use_simulation_mode();
        assert!(controller.use_simulation);
    }

    #[tokio::test]
    async fn test_controller_robot_state() {
        let config = RobotConfig::default();
        let controller = RoboticsController::new(config, true).unwrap();
        let state = controller.robot_state().await.unwrap();
        assert!(!state.is_moving);
    }
}
