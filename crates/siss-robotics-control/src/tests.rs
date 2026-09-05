#[cfg(test)]
mod integration_tests {
    use crate::{RoboticsController, RobotConfig, Trajectory, Waypoint};

    #[tokio::test]
    async fn test_robotics_controller_simulation() {
        let config = RobotConfig::default();
        let controller = RoboticsController::new(config, true).unwrap();

        let mut traj = Trajectory::new("test-move".to_string());
        let wp = Waypoint::new(
            vec![0.0; 6],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            0.1,
        ).unwrap();
        traj.add_waypoint(wp).unwrap();

        let result = controller.execute_trajectory(traj).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_trajectory_safety_validation() {
        let config = RobotConfig::default();
        let controller = RoboticsController::new(config, true).unwrap();

        let mut traj = Trajectory::new("unsafe-move".to_string());
        // Out-of-workspace position
        let wp = Waypoint::new(
            vec![0.0; 6],
            [100.0, 100.0, 100.0], // Way outside bounds
            [0.0, 0.0, 0.0],
            1.0,
        ).unwrap();
        traj.add_waypoint(wp).unwrap();

        let result = controller.execute_trajectory(traj).await;
        assert!(result.is_err()); // Should be rejected by safety
    }

    #[tokio::test]
    async fn test_emergency_stop() {
        let config = RobotConfig::default();
        let controller = RoboticsController::new(config, true).unwrap();

        let result = controller.emergency_stop().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_robot_state_query() {
        let config = RobotConfig::default();
        let controller = RoboticsController::new(config, true).unwrap();

        let state = controller.robot_state().await.unwrap();
        assert_eq!(state.joint_states.len(), 6);
        assert!(!state.is_moving);
    }

    #[tokio::test]
    async fn test_mode_switching() {
        let config = RobotConfig::default();
        let mut controller = RoboticsController::new(config, false).unwrap();
        assert!(!controller.use_simulation);

        controller.use_simulation_mode();
        assert!(controller.use_simulation);

        controller.use_hardware_mode();
        assert!(!controller.use_simulation);
    }

    #[tokio::test]
    async fn test_multi_waypoint_trajectory() {
        let config = RobotConfig::default();
        let controller = RoboticsController::new(config, true).unwrap();

        let mut traj = Trajectory::new("multi-point".to_string());
        for i in 0..3 {
            let wp = Waypoint::new(
                vec![(i as f64) * 0.1; 6],
                [(i as f64) * 0.1, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                0.5,
            ).unwrap();
            traj.add_waypoint(wp).unwrap();
        }

        let result = controller.execute_trajectory(traj).await;
        assert!(result.is_ok());
    }
}
