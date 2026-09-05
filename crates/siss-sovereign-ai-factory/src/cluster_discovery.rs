//! Local network cluster discovery via mDNS (air-gap only)

use crate::error::Result;
use crate::types::NodeInfo;
use std::net::IpAddr;
use std::str::FromStr;
use tracing::debug;

/// Cluster discovery service (mDNS-based, local network only)
pub struct ClusterDiscovery {
    mdns_domain: String,
    local_only: bool,
}

impl ClusterDiscovery {
    pub fn new(mdns_domain: String, local_only: bool) -> Self {
        Self {
            mdns_domain,
            local_only,
        }
    }

    /// Discover nodes on local network
    pub async fn discover(&self) -> Result<Vec<NodeInfo>> {
        // In production, this would use actual mDNS (mdns-sd crate)
        // For now, return simulated discovery results
        debug!(
            "Discovering nodes on domain: {} (local_only={})",
            self.mdns_domain, self.local_only
        );

        if self.local_only && !self.is_valid_local_domain(&self.mdns_domain) {
            return Err(crate::Error::AirGapViolation(
                "mDNS domain is not local-only".to_string(),
            ));
        }

        Ok(vec![])
    }

    /// Register this node on mDNS
    pub async fn register(&self, node_id: crate::types::NodeId, hostname: &str, local_ip: IpAddr, port: u16) -> Result<()> {
        debug!(
            "Registering node {} on mDNS: {}:{} -> {}",
            node_id.0, hostname, port, local_ip
        );

        if self.local_only && !self.is_valid_local_ip(&local_ip) {
            return Err(crate::Error::AirGapViolation(
                format!("IP {} is not local", local_ip),
            ));
        }

        Ok(())
    }

    /// Check if domain is local-only
    fn is_valid_local_domain(&self, domain: &str) -> bool {
        domain.ends_with(".local")
    }

    /// Check if IP is on local network (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    pub fn is_valid_local_ip(&self, ip: &IpAddr) -> bool {
        match ip {
            IpAddr::V4(v4) => {
                let octets = v4.octets();
                octets[0] == 10
                    || (octets[0] == 172 && octets[1] >= 16 && octets[1] < 32)
                    || (octets[0] == 192 && octets[1] == 168)
            }
            IpAddr::V6(v6) => v6.is_loopback() || v6.is_unicast_link_local(),
        }
    }

    /// Validate air-gap: no external DNS, no cloud IPs
    pub fn validate_air_gap(&self) -> Result<()> {
        if !self.local_only {
            return Err(crate::Error::AirGapViolation(
                "Cluster not configured for air-gap mode".to_string(),
            ));
        }

        if !self.is_valid_local_domain(&self.mdns_domain) {
            return Err(crate::Error::AirGapViolation(
                "Invalid local domain".to_string(),
            ));
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::NodeId;
    use std::str::FromStr;

    #[test]
    fn test_is_valid_local_domain() {
        let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);

        assert!(discovery.is_valid_local_domain("sovereign-ai.local"));
        assert!(discovery.is_valid_local_domain("cluster.local"));
        assert!(!discovery.is_valid_local_domain("example.com"));
        assert!(!discovery.is_valid_local_domain("google.com"));
    }

    #[test]
    fn test_is_valid_local_ip_ipv4() {
        let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);

        // Private ranges
        assert!(discovery.is_valid_local_ip(&IpAddr::from_str("10.0.0.1").unwrap()));
        assert!(discovery.is_valid_local_ip(&IpAddr::from_str("172.16.0.1").unwrap()));
        assert!(discovery.is_valid_local_ip(&IpAddr::from_str("192.168.1.1").unwrap()));

        // Public IPs (invalid for air-gap)
        assert!(!discovery.is_valid_local_ip(&IpAddr::from_str("8.8.8.8").unwrap()));
        assert!(!discovery.is_valid_local_ip(&IpAddr::from_str("1.1.1.1").unwrap()));
    }

    #[test]
    fn test_is_valid_local_ip_ipv6() {
        let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);

        // Link-local IPv6
        assert!(discovery.is_valid_local_ip(&IpAddr::from_str("fe80::1").unwrap()));
    }

    #[test]
    fn test_validate_air_gap_valid() {
        let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);
        assert!(discovery.validate_air_gap().is_ok());
    }

    #[test]
    fn test_validate_air_gap_not_local() {
        let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), false);
        assert!(discovery.validate_air_gap().is_err());
    }

    #[test]
    fn test_validate_air_gap_invalid_domain() {
        let discovery = ClusterDiscovery::new("example.com".to_string(), true);
        assert!(discovery.validate_air_gap().is_err());
    }

    #[tokio::test]
    async fn test_register_valid_local_ip() {
        let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);
        let node_id = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.100").unwrap();

        let result = discovery
            .register(node_id, "mac-studio-1", ip, 8080)
            .await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_register_public_ip_fails() {
        let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);
        let node_id = NodeId::new();
        let ip = IpAddr::from_str("8.8.8.8").unwrap();

        let result = discovery
            .register(node_id, "bad-node", ip, 8080)
            .await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_discover_validates_air_gap() {
        let discovery = ClusterDiscovery::new("example.com".to_string(), true);
        let result = discovery.discover().await;
        assert!(result.is_err());
    }
}
