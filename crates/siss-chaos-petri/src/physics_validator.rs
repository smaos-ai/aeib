//! Hardware-in-the-loop physics validation
//!
//! Validates agent actions for physical safety:
//! - Position bounds (workspace constraints)
//! - Velocity limits (control safety)
//! - Safety margins (collision avoidance)
//! - Graceful degradation (clip_action modifies infeasible commands)
//!
//! Used by hardware interfaces to prevent unsafe robot movements.

use serde::{Deserialize, Serialize};

/// Action to validate: position + velocity in 3D workspace
#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq)]
pub struct Action {
    /// Position [X, Y, Z] in workspace (meters)
    pub position: [f32; 3],
    /// Velocity [Vx, Vy, Vz] (meters/second)
    pub velocity: [f32; 3],
}

/// World constraints for validation
#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq)]
pub struct WorldState {
    /// Minimum corner of workspace [X, Y, Z]
    pub bounds_min: [f32; 3],
    /// Maximum corner of workspace [X, Y, Z]
    pub bounds_max: [f32; 3],
    /// Maximum allowed velocity magnitude (m/s)
    pub max_velocity: f32,
}

/// Validation metrics for analysis
#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq)]
pub struct ValidationMetrics {
    /// Distance to nearest boundary (meters)
    pub distance_to_boundary: f32,
    /// Magnitude of velocity vector (m/s)
    pub velocity_magnitude: f32,
    /// Feasibility score: velocity_actual / max_velocity (0.0 to 1.0)
    pub feasibility_score: f32,
}

/// Result of action validation
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ValidationResult {
    /// True if action passes all checks
    pub is_valid: bool,
    /// Error message if invalid, empty if valid
    pub error: String,
    /// Metrics computed during validation
    pub metrics: ValidationMetrics,
}

/// Hardware-in-the-loop physics validator
///
/// Ensures agent actions are safe before sending to real hardware.
/// Uses graceful degradation: clip_action() modifies infeasible commands
/// rather than rejecting them outright.
#[derive(Clone, Debug)]
pub struct PhysicsValidator {
    /// Safety margin in meters (1cm buffer by default)
    safety_margin: f32,
}

impl PhysicsValidator {
    /// Create new physics validator with default safety margin (0.01m)
    pub fn new() -> Self {
        Self {
            safety_margin: 0.01,
        }
    }

    /// Create validator with custom safety margin
    pub fn with_margin(margin: f32) -> Self {
        Self {
            safety_margin: margin,
        }
    }

    /// Validate action against world constraints
    ///
    /// Checks:
    /// 1. Position within bounds (with safety margin)
    /// 2. Velocity magnitude within limit
    ///
    /// Returns ValidationResult with metrics computed regardless of validity.
    pub fn validate_action(&self, action: &Action, world: &WorldState) -> ValidationResult {
        let vel_mag = self.velocity_magnitude(action.velocity);
        let dist_boundary = self.compute_distance_to_boundary(&action.position, world);
        let feasibility = self.compute_feasibility_score(vel_mag, world.max_velocity);

        let metrics = ValidationMetrics {
            distance_to_boundary: dist_boundary,
            velocity_magnitude: vel_mag,
            feasibility_score: feasibility,
        };

        // Check bounds with safety margin
        if !self.is_within_bounds(&action.position, world) {
            return ValidationResult {
                is_valid: false,
                error: "Position exceeds workspace bounds".to_string(),
                metrics,
            };
        }

        // Check safety margin (with epsilon tolerance for floating-point precision)
        let epsilon = 1e-6;
        if dist_boundary < self.safety_margin - epsilon {
            return ValidationResult {
                is_valid: false,
                error: format!(
                    "Position too close to boundary ({}m from edge, require {}m margin)",
                    dist_boundary, self.safety_margin
                ),
                metrics,
            };
        }

        // Check velocity limit
        if vel_mag > world.max_velocity + 1e-5 {
            return ValidationResult {
                is_valid: false,
                error: format!(
                    "Velocity exceeds limit ({:.3} m/s > {:.3} m/s)",
                    vel_mag, world.max_velocity
                ),
                metrics,
            };
        }

        ValidationResult {
            is_valid: true,
            error: String::new(),
            metrics,
        }
    }

    /// Clip infeasible action to make it valid
    ///
    /// Graceful degradation:
    /// 1. Clamp position to bounds
    /// 2. Scale velocity if exceeds limit
    ///
    /// Returned action will pass validate_action() or be at safety margin boundary.
    pub fn clip_action(&self, action: &Action, world: &WorldState) -> Action {
        let mut pos = action.position;
        let mut vel = action.velocity;

        // Clamp position to bounds
        for i in 0..3 {
            pos[i] = pos[i]
                .max(world.bounds_min[i] + self.safety_margin)
                .min(world.bounds_max[i] - self.safety_margin);
        }

        // Scale velocity if needed
        let vel_mag = self.velocity_magnitude(vel);
        if vel_mag > world.max_velocity {
            let scale = world.max_velocity / vel_mag;
            for i in 0..3 {
                vel[i] *= scale;
            }
        }

        Action {
            position: pos,
            velocity: vel,
        }
    }

    /// Compute velocity magnitude
    fn velocity_magnitude(&self, velocity: [f32; 3]) -> f32 {
        (velocity[0].powi(2) + velocity[1].powi(2) + velocity[2].powi(2)).sqrt()
    }

    /// Compute distance to nearest boundary
    ///
    /// Returns minimum distance from position to any face of bounds box.
    fn compute_distance_to_boundary(&self, position: &[f32; 3], world: &WorldState) -> f32 {
        let dist_x_min = (position[0] - world.bounds_min[0]).abs();
        let dist_x_max = (world.bounds_max[0] - position[0]).abs();
        let dist_y_min = (position[1] - world.bounds_min[1]).abs();
        let dist_y_max = (world.bounds_max[1] - position[1]).abs();
        let dist_z_min = (position[2] - world.bounds_min[2]).abs();
        let dist_z_max = (world.bounds_max[2] - position[2]).abs();

        dist_x_min
            .min(dist_x_max)
            .min(dist_y_min)
            .min(dist_y_max)
            .min(dist_z_min)
            .min(dist_z_max)
    }

    /// Compute feasibility score (velocity vs max)
    ///
    /// Returns ratio: velocity_magnitude / max_velocity, clamped to [0.0, 1.0]
    fn compute_feasibility_score(&self, velocity_mag: f32, max_velocity: f32) -> f32 {
        if max_velocity <= 0.0 {
            return 0.0;
        }
        (velocity_mag / max_velocity).min(1.0)
    }

    /// Check if position is within bounds (not including safety margin)
    fn is_within_bounds(&self, position: &[f32; 3], world: &WorldState) -> bool {
        position[0] >= world.bounds_min[0]
            && position[0] <= world.bounds_max[0]
            && position[1] >= world.bounds_min[1]
            && position[1] <= world.bounds_max[1]
            && position[2] >= world.bounds_min[2]
            && position[2] <= world.bounds_max[2]
    }
}

impl Default for PhysicsValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_velocity_magnitude() {
        let validator = PhysicsValidator::new();
        assert!((validator.velocity_magnitude([3.0, 4.0, 0.0]) - 5.0).abs() < 0.001);
        assert!((validator.velocity_magnitude([1.0, 1.0, 1.0]) - 1.732).abs() < 0.01);
        assert_eq!(validator.velocity_magnitude([0.0, 0.0, 0.0]), 0.0);
    }

    #[test]
    fn test_distance_to_boundary_center() {
        let validator = PhysicsValidator::new();
        let world = WorldState {
            bounds_min: [0.0, 0.0, 0.0],
            bounds_max: [10.0, 10.0, 10.0],
            max_velocity: 1.0,
        };
        let dist = validator.compute_distance_to_boundary(&[5.0, 5.0, 5.0], &world);
        assert_eq!(dist, 5.0);
    }

    #[test]
    fn test_distance_to_boundary_corner() {
        let validator = PhysicsValidator::new();
        let world = WorldState {
            bounds_min: [0.0, 0.0, 0.0],
            bounds_max: [10.0, 10.0, 10.0],
            max_velocity: 1.0,
        };
        let dist = validator.compute_distance_to_boundary(&[0.0, 5.0, 5.0], &world);
        assert_eq!(dist, 0.0);
    }

    #[test]
    fn test_feasibility_score_half_velocity() {
        let validator = PhysicsValidator::new();
        let score = validator.compute_feasibility_score(0.5, 1.0);
        assert_eq!(score, 0.5);
    }

    #[test]
    fn test_feasibility_score_exceeds_max() {
        let validator = PhysicsValidator::new();
        let score = validator.compute_feasibility_score(2.0, 1.0);
        assert_eq!(score, 1.0); // Clamped to 1.0
    }

    #[test]
    fn test_is_within_bounds() {
        let validator = PhysicsValidator::new();
        let world = WorldState {
            bounds_min: [0.0, 0.0, 0.0],
            bounds_max: [1.0, 1.0, 1.0],
            max_velocity: 1.0,
        };
        assert!(validator.is_within_bounds(&[0.5, 0.5, 0.5], &world));
        assert!(!validator.is_within_bounds(&[-0.1, 0.5, 0.5], &world));
        assert!(!validator.is_within_bounds(&[1.1, 0.5, 0.5], &world));
    }
}
