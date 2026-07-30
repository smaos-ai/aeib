use std::collections::HashMap;

/// Network segmentation zones
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum NetworkZone {
    AirGapped,         // Isolated from internet
    InternalSegmented, // Internal network, segmented
    MilitaryNetwork,   // JWICS/NIPRNet/SIPRNet compatible
    GovernmentCloud,   // FedRAMP authorized
}

/// SISS node deployment in air-gapped topology
#[derive(Debug, Clone)]
pub struct SissNode {
    pub node_id: String,
    pub crate_name: String,
    pub zone: NetworkZone,
    pub encryption: String,
    pub attestation_capable: bool,
}

/// Air-gapped network topology
#[derive(Debug, Clone)]
pub struct AirGappedNetwork {
    pub nodes: HashMap<String, SissNode>,
    pub network_segments: HashMap<String, Vec<String>>, // segment -> node_ids
}

impl AirGappedNetwork {
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
            network_segments: HashMap::new(),
        }
    }

    /// CMMC Level 2 compliant deployment topology
    pub fn cmmc_level2_topology() -> Self {
        let mut net = Self::new();

        // Control Plane (Isolated segment)
        let control_nodes = vec![
            SissNode {
                node_id: "ctl-0".to_string(),
                crate_name: "siss-gatekeeper".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "TLS 1.3 + AEAD".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "ctl-1".to_string(),
                crate_name: "siss-job-router".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "TLS 1.3 + AEAD".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "ctl-2".to_string(),
                crate_name: "siss-decision-db".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "AES-256-GCM at-rest".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "ctl-3".to_string(),
                crate_name: "siss-orchestrator".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "TLS 1.3 + AEAD".to_string(),
                attestation_capable: true,
            },
        ];

        // Data Plane (Isolated segment)
        let data_nodes = vec![
            SissNode {
                node_id: "data-0".to_string(),
                crate_name: "siss-enclave".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "AES-256-GCM".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "data-1".to_string(),
                crate_name: "siss-audit-archiver".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "AES-256-GCM at-rest".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "data-2".to_string(),
                crate_name: "siss-trust-mesh".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "AES-256-GCM".to_string(),
                attestation_capable: true,
            },
        ];

        // Monitoring Plane (Isolated segment)
        let monitor_nodes = vec![
            SissNode {
                node_id: "mon-0".to_string(),
                crate_name: "siss-otel-tracer".to_string(),
                zone: NetworkZone::InternalSegmented,
                encryption: "TLS 1.3".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "mon-1".to_string(),
                crate_name: "siss-behavioral-firewall".to_string(),
                zone: NetworkZone::AirGapped,
                encryption: "TLS 1.3 + AEAD".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "mon-2".to_string(),
                crate_name: "siss-event-log".to_string(),
                zone: NetworkZone::InternalSegmented,
                encryption: "TLS 1.3".to_string(),
                attestation_capable: true,
            },
        ];

        // Edge Gateways (Boundary protection)
        let edge_nodes = vec![
            SissNode {
                node_id: "edge-0".to_string(),
                crate_name: "siss-job-router::edge_gateway".to_string(),
                zone: NetworkZone::InternalSegmented,
                encryption: "TLS 1.3 + MUTUAL AUTH".to_string(),
                attestation_capable: true,
            },
            SissNode {
                node_id: "edge-1".to_string(),
                crate_name: "siss-remote-gateway".to_string(),
                zone: NetworkZone::MilitaryNetwork,
                encryption: "TLS 1.3 Suite B".to_string(),
                attestation_capable: true,
            },
        ];

        // Add all nodes
        for node in control_nodes
            .iter()
            .chain(data_nodes.iter())
            .chain(monitor_nodes.iter())
            .chain(edge_nodes.iter())
        {
            net.nodes.insert(node.node_id.clone(), node.clone());
        }

        // Define network segments
        net.network_segments.insert(
            "control_plane".to_string(),
            control_nodes.iter().map(|n| n.node_id.clone()).collect(),
        );
        net.network_segments.insert(
            "data_plane".to_string(),
            data_nodes.iter().map(|n| n.node_id.clone()).collect(),
        );
        net.network_segments.insert(
            "monitoring_plane".to_string(),
            monitor_nodes.iter().map(|n| n.node_id.clone()).collect(),
        );
        net.network_segments.insert(
            "edge_boundary".to_string(),
            edge_nodes.iter().map(|n| n.node_id.clone()).collect(),
        );

        net
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn segment_count(&self) -> usize {
        self.network_segments.len()
    }

    pub fn get_nodes_in_segment(&self, segment: &str) -> Option<Vec<&SissNode>> {
        self.network_segments.get(segment).map(|node_ids| {
            node_ids
                .iter()
                .filter_map(|id| self.nodes.get(id))
                .collect()
        })
    }
}

impl Default for AirGappedNetwork {
    fn default() -> Self {
        Self::new()
    }
}

/// Deployment topology documentation
#[derive(Debug, Clone)]
pub struct DeploymentTopology {
    pub network: AirGappedNetwork,
    pub network_diagram_ascii: String,
    pub security_zones: Vec<String>,
}

impl DeploymentTopology {
    pub fn cmmc_level2() -> Self {
        let network = AirGappedNetwork::cmmc_level2_topology();

        let diagram = r#"
CMMC Level 2 Air-Gapped Deployment Topology
============================================

                     ┌─────────────────────────────────────────┐
                     │   EXTERNAL NETWORK (Internet)          │
                     └──────────────┬──────────────────────────┘
                                    │ [TLS 1.3 + MFA]
                     ┌──────────────▼──────────────────────────┐
                     │  EDGE BOUNDARY SEGMENT                  │
                     │  ├─ edge-0 (edge_gateway/TLS 1.3)      │
                     │  └─ edge-1 (remote_gateway/Suite B)    │
                     └──────────────┬──────────────────────────┘
                                    │ [Air-Gapped Firewall]
        ┌───────────────────────────┼────────────────────────────┐
        │                           │                            │
        │                    [INTERNAL NETWORK]                  │
        │     [No direct internet access from core nodes]        │
        │                                                         │
    ┌───▼─────────────────┐  ┌──────────────────┐  ┌──────────┐ │
    │ CONTROL PLANE       │  │  DATA PLANE      │  │ MONITOR  │ │
    │ (Isolated Segment)  │  │ (Isolated)       │  │ (Segment)│ │
    │                     │  │                  │  │          │ │
    │ ctl-0: gatekeeper  │  │ data-0: enclave │  │mon-0:OTel│ │
    │ ctl-1: job-router  │  │ data-1: auditor │  │mon-1:FW  │ │
    │ ctl-2: decision-db │  │                  │  │          │ │
    │                     │  │ [AES-256-GCM]    │  │ [TLS 1.3]│ │
    │ [TLS 1.3 + AEAD]    │  │ [Immutable Logs] │  │          │ │
    │ [Attestation]       │  │ [Attestation]    │  │[Anomaly  │ │
    └─────┬───────────────┘  └────────┬─────────┘  │ Detection│ │
          │                           │            └──────────┘ │
          │ [Internal VPN 1.3]        │[Seg Protocol]           │
          └───────────────┬───────────┘                         │
                          │                                     │
                    [Data Flow Control]                         │
                    [No Lateral Movement]                       │
                                                                │
└────────────────────────────────────────────────────────────────┘
        "#
        .to_string();

        Self {
            network,
            network_diagram_ascii: diagram,
            security_zones: vec![
                "AirGapped".to_string(),
                "InternalSegmented".to_string(),
                "MilitaryNetwork".to_string(),
            ],
        }
    }

    pub fn validate_topology(&self) -> Result<String, String> {
        // Validate all nodes are in segments
        let all_node_ids: std::collections::HashSet<_> =
            self.network.nodes.keys().cloned().collect();
        let segmented_ids: std::collections::HashSet<_> = self
            .network
            .network_segments
            .values()
            .flat_map(|ids| ids.iter().cloned())
            .collect();

        if all_node_ids != segmented_ids {
            return Err("Not all nodes are assigned to segments".to_string());
        }

        // Validate air-gapped network has boundary
        let boundary = self.network.get_nodes_in_segment("edge_boundary");
        if boundary.is_none() || boundary.unwrap().is_empty() {
            return Err("Missing edge boundary segment".to_string());
        }

        Ok("Topology validation passed".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deployment_topology_valid() {
        let topo = DeploymentTopology::cmmc_level2();
        assert!(topo.validate_topology().is_ok());
    }

    #[test]
    fn test_network_has_control_plane() {
        let topo = DeploymentTopology::cmmc_level2();
        assert!(topo.network.get_nodes_in_segment("control_plane").is_some());
        let cp = topo.network.get_nodes_in_segment("control_plane").unwrap();
        assert!(cp.len() >= 3, "Control plane must have at least 3 nodes");
    }

    #[test]
    fn test_network_has_data_plane() {
        let topo = DeploymentTopology::cmmc_level2();
        assert!(topo.network.get_nodes_in_segment("data_plane").is_some());
    }

    #[test]
    fn test_network_has_monitoring_plane() {
        let topo = DeploymentTopology::cmmc_level2();
        assert!(topo
            .network
            .get_nodes_in_segment("monitoring_plane")
            .is_some());
    }

    #[test]
    fn test_network_has_edge_boundary() {
        let topo = DeploymentTopology::cmmc_level2();
        let boundary = topo.network.get_nodes_in_segment("edge_boundary");
        assert!(boundary.is_some());
        assert!(boundary.unwrap().len() >= 2);
    }

    #[test]
    fn test_all_nodes_have_encryption() {
        let topo = DeploymentTopology::cmmc_level2();
        for node in topo.network.nodes.values() {
            assert!(!node.encryption.is_empty());
            assert!(
                node.encryption.contains("TLS")
                    || node.encryption.contains("AES")
                    || node.encryption.contains("Suite B")
            );
        }
    }

    #[test]
    fn test_all_nodes_support_attestation() {
        let topo = DeploymentTopology::cmmc_level2();
        for node in topo.network.nodes.values() {
            assert!(node.attestation_capable);
        }
    }

    #[test]
    fn test_network_node_count() {
        let topo = DeploymentTopology::cmmc_level2();
        assert!(
            topo.network.node_count() >= 11,
            "Must have 11+ nodes for CMMC Level 2"
        );
    }

    #[test]
    fn test_network_segment_count() {
        let topo = DeploymentTopology::cmmc_level2();
        assert_eq!(
            topo.network.segment_count(),
            4,
            "Must have 4 network segments"
        );
    }
}
