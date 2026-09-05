use crate::error::{RoboticsError, Result};
use crate::Trajectory;
use serde::{Deserialize, Serialize};

/// Simulation frame (state snapshot)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SimFrame {
    pub time: f64,
    pub joint_positions: Vec<f64>,
    pub joint_velocities: Vec<f64>,
    pub position: [f64; 3],
    pub orientation: [f64; 3],
}

/// Physics engine simulation (MuJoCo-compatible API)
pub struct SimulationEngine {
    /// Simulation timestep (seconds)
    timestep: f64,
    /// Gravity (m/s^2)
    gravity: f64,
    /// Simulation frames
    frames: std::sync::Arc<std::sync::Mutex<Vec<SimFrame>>>,
}

impl SimulationEngine {
    /// Create new simulation engine
    pub fn new() -> Self {
        Self {
            timestep: 0.001,
            gravity: 9.81,
            frames: std::sync::Arc::new(std::sync::Mutex::new(Vec::new())),
        }
    }

    /// Simulate trajectory
    pub async fn simulate(&self, trajectory: &Trajectory) -> Result<()> {
        // Validate trajectory first
        trajectory.validate()?;

        let mut frames = self.frames.lock().unwrap();
        frames.clear();

        let mut time = 0.0;

        // Simulate with small timesteps
        while time <= trajectory.total_duration {
            let waypoint = trajectory.interpolate(time)?;

            let frame = SimFrame {
                time,
                joint_positions: waypoint.joint_positions.clone(),
                joint_velocities: vec![0.0; 6], // Simplified (no velocity calc)
                position: waypoint.position,
                orientation: waypoint.orientation,
            };

            frames.push(frame);
            time += self.timestep;
        }

        Ok(())
    }

    /// Get simulation frames
    pub fn get_frames(&self) -> Vec<SimFrame> {
        self.frames.lock().unwrap().clone()
    }

    /// Get frame count
    pub fn frame_count(&self) -> usize {
        self.frames.lock().unwrap().len()
    }

    /// Verify no collisions (stub for Jun 2027)
    pub fn check_collisions(&self) -> Result<bool> {
        // TODO: Jun 2027 - Implement actual collision detection via MuJoCo
        Ok(false) // No collisions found
    }

    /// Export simulation results to JSON
    pub fn export_json(&self) -> Result<String> {
        let frames = self.frames.lock().unwrap();
        serde_json::to_string(&*frames)
            .map_err(|e| RoboticsError::SimulationError(e.to_string()))
    }
}

impl Default for SimulationEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Trajectory, Waypoint};

    #[tokio::test]
    async fn test_simulation_engine_creation() {
        let engine = SimulationEngine::new();
        assert_eq!(engine.timestep, 0.001);
    }

    #[tokio::test]
    async fn test_simple_trajectory_simulation() {
        let engine = SimulationEngine::new();

        let mut traj = Trajectory::new("test".to_string());
        let wp = Waypoint::new(
            vec![0.0; 6],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            0.1,
        ).unwrap();
        traj.add_waypoint(wp).unwrap();

        let result = engine.simulate(&traj).await;
        assert!(result.is_ok());
        assert!(engine.frame_count() > 0);
    }

    #[tokio::test]
    async fn test_simulation_export() {
        let engine = SimulationEngine::new();

        let mut traj = Trajectory::new("test".to_string());
        let wp = Waypoint::new(
            vec![0.0; 6],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            0.05,
        ).unwrap();
        traj.add_waypoint(wp).unwrap();

        engine.simulate(&traj).await.unwrap();

        let json = engine.export_json();
        assert!(json.is_ok());
    }

    #[tokio::test]
    async fn test_collision_check() {
        let engine = SimulationEngine::new();
        let result = engine.check_collisions();
        assert!(result.is_ok());
    }
}
