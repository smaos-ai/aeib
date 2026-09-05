/// iWorld-Bench: Compile-Time Geometric Trajectory Validation
/// Type-state pattern ensures trajectories are validated before dispatch.
/// Unvalidated trajectories cannot be passed to execution functions (compile error).
use std::marker::PhantomData;

#[derive(Debug, Clone, PartialEq)]
pub struct Point3D {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

pub struct BoundingBox {
    pub x_range: (f64, f64),
    pub y_range: (f64, f64),
    pub z_range: (f64, f64),
}

pub struct GeometricBounds {
    pub x_range: (f64, f64),
    pub y_range: (f64, f64),
    pub z_range: (f64, f64),
    pub obstacle_zones: &'static [BoundingBox],
}

#[derive(Debug, Clone)]
pub struct Trajectory {
    pub waypoints: Vec<Point3D>,
}

// Type-state markers
pub struct Unvalidated;
pub struct Validated;

pub struct TypedTrajectory<S> {
    pub trajectory: Trajectory,
    _state: PhantomData<S>,
}

#[derive(Debug, PartialEq)]
pub enum GeometricViolation {
    OutOfBounds { point: Point3D },
    ObstacleCollision { point: Point3D, zone_index: usize },
    EmptyTrajectory,
}

pub struct TrajectoryValidator;

impl TypedTrajectory<Unvalidated> {
    pub fn new(trajectory: Trajectory) -> Self {
        TypedTrajectory {
            trajectory,
            _state: PhantomData,
        }
    }
}

impl TrajectoryValidator {
    /// RULE A: waypoints must not be empty → Err(EmptyTrajectory)
    /// RULE B: each waypoint within GeometricBounds x/y/z ranges → Err(OutOfBounds)
    /// RULE C: each waypoint must not intersect any obstacle_zone → Err(ObstacleCollision)
    /// On Ok: consumes TypedTrajectory<Unvalidated>, returns TypedTrajectory<Validated>
    pub fn validate(
        trajectory: TypedTrajectory<Unvalidated>,
        bounds: &GeometricBounds,
    ) -> Result<TypedTrajectory<Validated>, GeometricViolation> {
        // RULE A: Check empty
        if trajectory.trajectory.waypoints.is_empty() {
            return Err(GeometricViolation::EmptyTrajectory);
        }

        // RULE B & C: Validate each waypoint
        for waypoint in &trajectory.trajectory.waypoints {
            // RULE B: Check bounds
            if waypoint.x < bounds.x_range.0
                || waypoint.x > bounds.x_range.1
                || waypoint.y < bounds.y_range.0
                || waypoint.y > bounds.y_range.1
                || waypoint.z < bounds.z_range.0
                || waypoint.z > bounds.z_range.1
            {
                return Err(GeometricViolation::OutOfBounds {
                    point: waypoint.clone(),
                });
            }

            // RULE C: Check obstacle zones
            for (idx, zone) in bounds.obstacle_zones.iter().enumerate() {
                if Self::intersects(waypoint, zone) {
                    return Err(GeometricViolation::ObstacleCollision {
                        point: waypoint.clone(),
                        zone_index: idx,
                    });
                }
            }
        }

        Ok(TypedTrajectory {
            trajectory: trajectory.trajectory,
            _state: PhantomData,
        })
    }

    fn intersects(point: &Point3D, bbox: &BoundingBox) -> bool {
        point.x >= bbox.x_range.0
            && point.x <= bbox.x_range.1
            && point.y >= bbox.y_range.0
            && point.y <= bbox.y_range.1
            && point.z >= bbox.z_range.0
            && point.z <= bbox.z_range.1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_trajectory() {
        let bounds = GeometricBounds {
            x_range: (0.0, 100.0),
            y_range: (0.0, 100.0),
            z_range: (0.0, 10.0),
            obstacle_zones: &[],
        };

        let trajectory = Trajectory {
            waypoints: vec![
                Point3D {
                    x: 10.0,
                    y: 10.0,
                    z: 5.0,
                },
                Point3D {
                    x: 50.0,
                    y: 50.0,
                    z: 8.0,
                },
            ],
        };

        let unvalidated = TypedTrajectory::new(trajectory);
        let result = TrajectoryValidator::validate(unvalidated, &bounds);
        assert!(result.is_ok());
    }

    #[test]
    fn test_out_of_bounds() {
        let bounds = GeometricBounds {
            x_range: (0.0, 100.0),
            y_range: (0.0, 100.0),
            z_range: (0.0, 10.0),
            obstacle_zones: &[],
        };

        let trajectory = Trajectory {
            waypoints: vec![Point3D {
                x: 150.0,
                y: 50.0,
                z: 5.0,
            }],
        };

        let unvalidated = TypedTrajectory::new(trajectory);
        let result = TrajectoryValidator::validate(unvalidated, &bounds);
        assert!(matches!(
            result,
            Err(GeometricViolation::OutOfBounds { .. })
        ));
    }

    #[test]
    fn test_obstacle_collision() {
        let bounds = GeometricBounds {
            x_range: (0.0, 100.0),
            y_range: (0.0, 100.0),
            z_range: (0.0, 10.0),
            obstacle_zones: &[BoundingBox {
                x_range: (40.0, 60.0),
                y_range: (40.0, 60.0),
                z_range: (0.0, 10.0),
            }],
        };

        let trajectory = Trajectory {
            waypoints: vec![Point3D {
                x: 50.0,
                y: 50.0,
                z: 5.0,
            }],
        };

        let unvalidated = TypedTrajectory::new(trajectory);
        let result = TrajectoryValidator::validate(unvalidated, &bounds);
        assert!(matches!(
            result,
            Err(GeometricViolation::ObstacleCollision { zone_index: 0, .. })
        ));
    }

    #[test]
    fn test_empty_trajectory() {
        let bounds = GeometricBounds {
            x_range: (0.0, 100.0),
            y_range: (0.0, 100.0),
            z_range: (0.0, 10.0),
            obstacle_zones: &[],
        };

        let trajectory = Trajectory { waypoints: vec![] };

        let unvalidated = TypedTrajectory::new(trajectory);
        let result = TrajectoryValidator::validate(unvalidated, &bounds);
        assert!(matches!(result, Err(GeometricViolation::EmptyTrajectory)));
    }
}
