use crate::error::{RoboticsError, Result};
use serde::{Deserialize, Serialize};

/// Trajectory waypoint
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Waypoint {
    /// Joint angles (radians)
    pub joint_positions: Vec<f64>,
    /// Target end effector position [x, y, z]
    pub position: [f64; 3],
    /// Target orientation (roll, pitch, yaw)
    pub orientation: [f64; 3],
    /// Time to reach this waypoint (seconds)
    pub duration: f64,
}

impl Waypoint {
    /// Create new waypoint
    pub fn new(
        joint_positions: Vec<f64>,
        position: [f64; 3],
        orientation: [f64; 3],
        duration: f64,
    ) -> Result<Self> {
        if joint_positions.len() != 6 {
            return Err(RoboticsError::InvalidTrajectory(
                "Must have 6 joint positions".into(),
            ));
        }
        if duration <= 0.0 {
            return Err(RoboticsError::InvalidTrajectory(
                "Duration must be positive".into(),
            ));
        }
        Ok(Self {
            joint_positions,
            position,
            orientation,
            duration,
        })
    }
}

/// Complete trajectory
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Trajectory {
    pub waypoints: Vec<Waypoint>,
    pub name: String,
    pub total_duration: f64,
}

impl Trajectory {
    /// Create new trajectory
    pub fn new(name: String) -> Self {
        Self {
            waypoints: Vec::new(),
            name,
            total_duration: 0.0,
        }
    }

    /// Add waypoint to trajectory
    pub fn add_waypoint(&mut self, waypoint: Waypoint) -> Result<()> {
        self.waypoints.push(waypoint.clone());
        self.total_duration += waypoint.duration;
        Ok(())
    }

    /// Validate trajectory continuity
    pub fn validate(&self) -> Result<()> {
        if self.waypoints.is_empty() {
            return Err(RoboticsError::InvalidTrajectory(
                "Trajectory has no waypoints".into(),
            ));
        }

        // Check for reasonable joint velocity (simple heuristic)
        for window in self.waypoints.windows(2) {
            let prev = &window[0];
            let curr = &window[1];

            for (p, c) in prev.joint_positions.iter().zip(&curr.joint_positions) {
                let delta = (c - p).abs();
                let max_velocity = 180.0_f64.to_radians(); // degrees/sec to radians/sec
                let velocity = delta / curr.duration;

                if velocity > max_velocity {
                    return Err(RoboticsError::InvalidTrajectory(
                        format!("Joint velocity {} exceeds max {}", velocity, max_velocity),
                    ));
                }
            }
        }

        Ok(())
    }

    /// Get waypoint at time t
    pub fn interpolate(&self, t: f64) -> Result<Waypoint> {
        if t < 0.0 || t > self.total_duration {
            return Err(RoboticsError::InvalidTrajectory(
                "Time out of trajectory bounds".into(),
            ));
        }

        let mut elapsed = 0.0;
        for (i, wp) in self.waypoints.iter().enumerate() {
            if elapsed + wp.duration >= t {
                // Linear interpolation between waypoint i and i+1
                if i == self.waypoints.len() - 1 {
                    return Ok(wp.clone());
                }

                let next = &self.waypoints[i + 1];
                let alpha = (t - elapsed) / wp.duration;

                let mut interp_joints = vec![0.0; 6];
                for j in 0..6 {
                    interp_joints[j] =
                        wp.joint_positions[j] * (1.0 - alpha) + next.joint_positions[j] * alpha;
                }

                let interp_pos = [
                    wp.position[0] * (1.0 - alpha) + next.position[0] * alpha,
                    wp.position[1] * (1.0 - alpha) + next.position[1] * alpha,
                    wp.position[2] * (1.0 - alpha) + next.position[2] * alpha,
                ];

                return Ok(Waypoint::new(
                    interp_joints,
                    interp_pos,
                    wp.orientation,
                    wp.duration,
                )?);
            }
            elapsed += wp.duration;
        }

        Ok(self.waypoints.last().unwrap().clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_waypoint_creation() {
        let wp = Waypoint::new(
            vec![0.0; 6],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            1.0,
        ).unwrap();
        assert_eq!(wp.duration, 1.0);
    }

    #[test]
    fn test_waypoint_invalid_joints() {
        let result = Waypoint::new(
            vec![0.0; 5], // Wrong count
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            1.0,
        );
        assert!(result.is_err());
    }

    #[test]
    fn test_trajectory_creation() {
        let traj = Trajectory::new("test".to_string());
        assert_eq!(traj.waypoints.len(), 0);
    }

    #[test]
    fn test_trajectory_add_waypoint() {
        let mut traj = Trajectory::new("test".to_string());
        let wp = Waypoint::new(
            vec![0.0; 6],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            1.0,
        ).unwrap();
        traj.add_waypoint(wp).unwrap();
        assert_eq!(traj.waypoints.len(), 1);
        assert_eq!(traj.total_duration, 1.0);
    }

    #[test]
    fn test_trajectory_validation() {
        let mut traj = Trajectory::new("test".to_string());
        let result = traj.validate();
        assert!(result.is_err()); // Empty trajectory
    }

    #[test]
    fn test_trajectory_interpolation() {
        let mut traj = Trajectory::new("test".to_string());
        let wp1 = Waypoint::new(
            vec![0.0; 6],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            1.0,
        ).unwrap();
        let wp2 = Waypoint::new(
            vec![1.0; 6],
            [1.0, 1.0, 1.0],
            [0.0, 0.0, 0.0],
            1.0,
        ).unwrap();
        traj.add_waypoint(wp1).unwrap();
        traj.add_waypoint(wp2).unwrap();

        let interp = traj.interpolate(1.5).unwrap();
        assert!(interp.position[0] > 0.4 && interp.position[0] < 0.6);
    }
}
