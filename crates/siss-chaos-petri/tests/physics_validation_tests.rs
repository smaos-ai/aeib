use siss_chaos_petri::physics_validator::{Action, PhysicsValidator, WorldState};

#[test]
fn test_physics_validator_valid_action() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [0.5, 0.5, 0.5],
        velocity: [0.5, 0.5, 0.5],
    };

    let result = validator.validate_action(&action, &world);
    assert!(result.is_valid, "Valid action should pass validation");
    assert!(result.error.is_empty(), "No error for valid action");
    assert!(result.metrics.feasibility_score > 0.0);
    assert!(result.metrics.feasibility_score <= 1.0);
}

#[test]
fn test_physics_validator_out_of_bounds_negative() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [-0.5, 0.5, 0.5],
        velocity: [0.5, 0.5, 0.5],
    };

    let result = validator.validate_action(&action, &world);
    assert!(!result.is_valid, "Out-of-bounds action should fail");
    assert!(result.error.contains("bounds"), "Error should mention bounds");
}

#[test]
fn test_physics_validator_out_of_bounds_positive() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [1.5, 0.5, 0.5],
        velocity: [0.5, 0.5, 0.5],
    };

    let result = validator.validate_action(&action, &world);
    assert!(!result.is_valid, "Out-of-bounds action should fail");
    assert!(result.error.contains("bounds"), "Error should mention bounds");
}

#[test]
fn test_physics_validator_velocity_limit_exceeded() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [0.5, 0.5, 0.5],
        velocity: [1.0, 1.0, 1.0], // sqrt(3) ≈ 1.732, exceeds limit
    };

    let result = validator.validate_action(&action, &world);
    assert!(!result.is_valid, "Excessive velocity should fail");
    assert!(
        result.error.contains("velocity") || result.error.contains("exceeds"),
        "Error should mention velocity"
    );
}

#[test]
fn test_physics_validator_safety_margin_enforced() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    // Position at exact boundary (0.0) - should fail due to safety margin
    let action = Action {
        position: [0.0, 0.5, 0.5],
        velocity: [0.1, 0.1, 0.1],
    };

    let result = validator.validate_action(&action, &world);
    assert!(!result.is_valid, "Action at boundary should fail due to safety margin");
    assert!(
        result.metrics.distance_to_boundary < 0.01,
        "Distance to boundary should be near zero"
    );
}

#[test]
fn test_physics_validator_clip_action_position() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [1.5, 0.5, 0.5],
        velocity: [0.5, 0.5, 0.5],
    };

    let clipped = validator.clip_action(&action, &world);
    assert!(clipped.position[0] <= 1.0, "Position should be clipped to bounds");
    assert!(clipped.position[0] >= 0.0, "Position should be clipped to bounds");

    // Verify clipped action is valid
    let result = validator.validate_action(&clipped, &world);
    assert!(result.is_valid, "Clipped action should be valid");
}

#[test]
fn test_physics_validator_clip_action_velocity() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [0.5, 0.5, 0.5],
        velocity: [1.0, 1.0, 1.0], // sqrt(3) ≈ 1.732
    };

    let clipped = validator.clip_action(&action, &world);
    let vel_mag = (clipped.velocity[0].powi(2)
        + clipped.velocity[1].powi(2)
        + clipped.velocity[2].powi(2))
        .sqrt();
    assert!(vel_mag <= world.max_velocity + 1e-5, "Velocity should be scaled");

    // Verify clipped action is valid
    let result = validator.validate_action(&clipped, &world);
    assert!(result.is_valid, "Clipped action should be valid");
}

#[test]
fn test_physics_validator_distance_to_boundary() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [0.2, 0.5, 0.5],
        velocity: [0.1, 0.1, 0.1],
    };

    let result = validator.validate_action(&action, &world);
    assert!(result.metrics.distance_to_boundary > 0.0, "Distance should be positive");
    assert!(
        result.metrics.distance_to_boundary <= 0.2,
        "Distance should be near position to closest boundary"
    );
}

#[test]
fn test_physics_validator_velocity_magnitude() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };
    let action = Action {
        position: [0.5, 0.5, 0.5],
        velocity: [0.3, 0.4, 0.0],
    };

    let result = validator.validate_action(&action, &world);
    let expected_mag = 0.5; // sqrt(0.3^2 + 0.4^2) = sqrt(0.25) = 0.5
    assert!((result.metrics.velocity_magnitude - expected_mag).abs() < 0.001, "Velocity magnitude should match");
}

#[test]
fn test_physics_validator_feasibility_score() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [0.0, 0.0, 0.0],
        bounds_max: [1.0, 1.0, 1.0],
        max_velocity: 1.0,
    };

    // Half max velocity
    let action = Action {
        position: [0.5, 0.5, 0.5],
        velocity: [0.25, 0.25, 0.25],
    };

    let result = validator.validate_action(&action, &world);
    // sqrt(3 * 0.25^2) ≈ 0.433
    assert!(result.metrics.feasibility_score > 0.4);
    assert!(result.metrics.feasibility_score < 0.5, "Feasibility should be ~ 43%");
}

#[test]
fn test_physics_validator_multiple_validations() {
    let validator = PhysicsValidator::new();
    let world = WorldState {
        bounds_min: [-10.0, -10.0, -10.0],
        bounds_max: [10.0, 10.0, 10.0],
        max_velocity: 2.0,
    };

    // Valid action
    let action1 = Action {
        position: [5.0, 5.0, 5.0],
        velocity: [1.0, 0.0, 0.0],
    };
    let result1 = validator.validate_action(&action1, &world);
    assert!(result1.is_valid, "Action 1 should be valid");

    // Invalid action (out of bounds)
    let action2 = Action {
        position: [15.0, 0.0, 0.0],
        velocity: [1.0, 0.0, 0.0],
    };
    let result2 = validator.validate_action(&action2, &world);
    assert!(!result2.is_valid, "Action 2 should be invalid");

    // Valid action with high velocity
    let action3 = Action {
        position: [0.0, 0.0, 0.0],
        velocity: [1.0, 1.0, 0.0],
    };
    let result3 = validator.validate_action(&action3, &world);
    assert!(result3.is_valid, "Action 3 should be valid");
}
