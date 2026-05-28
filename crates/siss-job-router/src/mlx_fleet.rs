/// Wave 2: Rapid-MLX Fleet Topology
/// Physical Apple Silicon compute nodes configured as a local-only fleet.

use std::net::UnixStream;
use std::time::Duration;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NodeId(pub String);

/// A single Apple Silicon node in the facility.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MlxNode {
    pub id: NodeId,
    pub socket_path: &'static str,
    pub memory_gb: u8,
    pub max_concurrent_tasks: u8,
}

pub struct MlxNodeClient;

impl MlxNodeClient {
    /// Probe socket availability with 100ms timeout.
    pub fn probe_socket(path: &str) -> bool {
        match UnixStream::connect(path) {
            Ok(stream) => {
                let _ = stream.set_read_timeout(Some(Duration::from_millis(100)));
                true
            }
            Err(_) => false,
        }
    }
}

/// A fleet of local MLX nodes. Static, compile-time declared.
pub struct MlxFleet {
    pub nodes: &'static [MlxNode],
    pub locality_zone: &'static str,
}

#[derive(Debug, PartialEq, Eq)]
pub enum FleetError {
    FleetEmpty,
    NoCapacityAvailable,
}

pub struct FleetRouter;

impl FleetRouter {
    /// Route to the reachable node with the most memory (greedy largest-first).
    /// Filters by socket reachability before selecting max-memory node.
    pub fn route(fleet: &MlxFleet, _task_tokens: u32) -> Result<&'static MlxNode, FleetError> {
        if fleet.nodes.is_empty() {
            return Err(FleetError::FleetEmpty);
        }

        // Filter reachable nodes via socket probe
        let reachable: Vec<_> = fleet
            .nodes
            .iter()
            .filter(|node| MlxNodeClient::probe_socket(node.socket_path))
            .collect();

        if reachable.is_empty() {
            return Err(FleetError::NoCapacityAvailable);
        }

        // Greedy largest-first: select reachable node with max memory_gb
        let selected = reachable
            .iter()
            .max_by_key(|node| node.memory_gb)
            .ok_or(FleetError::NoCapacityAvailable)?;

        Ok(selected)
    }
}

/// Proof that the fleet is local-only: no socket_path contains cloud endpoints.
pub fn assert_no_cloud_leak(fleet: &MlxFleet) -> bool {
    fleet.nodes.iter().all(|n| {
        !n.socket_path.contains("https://") && !n.socket_path.contains("http://")
            && !n.socket_path.contains("cloud")
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_route_to_largest_memory() {
        let node1 = MlxNode {
            id: NodeId("node1".to_string()),
            socket_path: "/var/run/node1.sock",
            memory_gb: 16,
            max_concurrent_tasks: 4,
        };

        let node2 = MlxNode {
            id: NodeId("node2".to_string()),
            socket_path: "/var/run/node2.sock",
            memory_gb: 64,
            max_concurrent_tasks: 8,
        };

        let nodes: &'static [MlxNode] = Box::leak(Box::new([node1, node2]));

        let fleet = MlxFleet {
            nodes,
            locality_zone: "facility-il",
        };

        let result = FleetRouter::route(&fleet, 500);
        assert!(result.is_ok());
        let selected = result.unwrap();
        assert_eq!(selected.memory_gb, 64);
    }

    #[test]
    fn test_fleet_empty_error() {
        let fleet = MlxFleet {
            nodes: &[],
            locality_zone: "facility-il",
        };

        let result = FleetRouter::route(&fleet, 500);
        assert_eq!(result, Err(FleetError::FleetEmpty));
    }

    #[test]
    fn test_assert_no_cloud_leak_passes_local() {
        let node = MlxNode {
            id: NodeId("node1".to_string()),
            socket_path: "/var/run/mlx.sock",
            memory_gb: 64,
            max_concurrent_tasks: 8,
        };

        let nodes: &'static [MlxNode] = Box::leak(Box::new([node]));

        let fleet = MlxFleet {
            nodes,
            locality_zone: "facility-il",
        };

        assert!(assert_no_cloud_leak(&fleet));
    }

    #[test]
    fn test_assert_no_cloud_leak_fails_https() {
        let node = MlxNode {
            id: NodeId("node1".to_string()),
            socket_path: "https://remote.cloud/mlx.sock",
            memory_gb: 64,
            max_concurrent_tasks: 8,
        };

        let nodes: &'static [MlxNode] = Box::leak(Box::new([node]));

        let fleet = MlxFleet {
            nodes,
            locality_zone: "facility-il",
        };

        assert!(!assert_no_cloud_leak(&fleet));
    }
}
