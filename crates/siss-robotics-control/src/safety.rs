use crate::error::{RoboticsError, Result};
use crate::Trajectory;
use serde::{Deserialize, Serialize};

/// 3D bounding box
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BoundingBox {
    pub min: [f64; 3],
    pub max: [f64; 3],
}

impl Default for BoundingBox {
    fn default() -> Self {
        Self {
            min: [-2.0, -2.0, -2.0],
            max: [2.0, 2.0, 2.0],
        }
    }
}

impl BoundingBox {
    /// Check if point is inside bounding box
    pub fn contains_point(&self, p: &[f64; 3]) -> bool {
        p[0] >= self.min[0]
            && p[0] <= self.max[0]
            && p[1] >= self.min[1]
            && p[1] <= self.max[1]
            && p[2] >= self.min[2]
            && p[2] <= self.max[2]
    }
}

/// Joint limit constraints
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JointLimits {
    /// 6 joints
    pub min_positions: Vec<f64>,
    pub max_positions: Vec<f64>,
}

impl Default for JointLimits {
    fn default() -> Self {
        // UR10e typical joint limits (radians)
        Self {
            min_positions: vec![-std::f64::consts::PI; 6],
            max_positions: vec![std::f64::consts::PI; 6],
        }
    }
}

impl JointLimits {
    /// Validate joint positions
    pub fn validate(&self, positions: &[f64]) -> bool {
        if positions.len() != self.min_positions.len() {
            return false;
        }
        positions
            .iter()
            .zip(self.min_positions.iter())
            .zip(self.max_positions.iter())
            .all(|((p, min), max)| p >= min && p <= max)
    }
}

/// Safety boundary validator
pub struct SafetyBoundary {
    workspace: BoundingBox,
    joint_limits: JointLimits,
}

impl Default for SafetyBoundary {
    fn default() -> Self {
        Self {
            workspace: BoundingBox::default(),
            joint_limits: JointLimits::default(),
        }
    }
}

impl SafetyBoundary {
    /// Create safety boundary
    pub fn new(workspace: BoundingBox, joint_limits: JointLimits) -> Self {
        Self {
            workspace,
            joint_limits,
        }
    }

    /// Validate trajectory against safety constraints
    pub fn validate_trajectory(&self, trajectory: &Trajectory) -> Result<()> {
        for waypoint in &trajectory.waypoints {
            // Check joint limits
            if !self.joint_limits.validate(&waypoint.joint_positions) {
                return Err(RoboticsError::SafetyViolation(
                    "Joint limits exceeded".into(),
                ));
            }

            // Check workspace bounds
            if !self.workspace.contains_point(&waypoint.position) {
                return Err(RoboticsError::SafetyViolation(
                    "End effector outside workspace".into(),
                ));
            }
        }

        Ok(())
    }

    /// Validate single waypoint
    pub fn validate_waypoint(
        &self,
        position: &[f64; 3],
        joint_positions: &[f64],
    ) -> Result<()> {
        if !self.joint_limits.validate(joint_positions) {
            return Err(RoboticsError::SafetyViolation(
                "Joint limits exceeded".into(),
            ));
        }
        if !self.workspace.contains_point(position) {
            return Err(RoboticsError::SafetyViolation(
                "Position outside workspace".into(),
            ));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bounding_box_contains() {
        let bbox = BoundingBox::default();
        assert!(bbox.contains_point(&[0.0, 0.0, 0.0]));
        assert!(!bbox.contains_point(&[3.0, 0.0, 0.0]));
    }

    #[test]
    fn test_joint_limits_validation() {
        let limits = JointLimits::default();
        assert!(limits.validate(&vec![0.0; 6]));
        assert!(!limits.validate(&vec![0.0; 5]));
    }

    #[test]
    fn test_safety_boundary_validation() {
        let boundary = SafetyBoundary::default();
        let valid_pos = [0.0, 0.0, 0.0];
        let valid_joints = vec![0.0; 6];

        assert!(boundary
            .validate_waypoint(&valid_pos, &valid_joints)
            .is_ok());

        let invalid_pos = [10.0, 0.0, 0.0];
        assert!(boundary
            .validate_waypoint(&invalid_pos, &valid_joints)
            .is_err());
    }
}
