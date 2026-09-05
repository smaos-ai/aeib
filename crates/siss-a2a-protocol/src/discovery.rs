use async_trait::async_trait;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use crate::error::Result;
use crate::integration::AgentRegistry;

/// Peer capability descriptor
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerCapability {
    /// Capability name (e.g., "compliance-gate", "evidence-collection")
    pub name: String,
    /// Capability version
    pub version: String,
    /// Whether capability is currently available
    pub available: bool,
}

/// Peer agent manifest (published to /.well-known/agent.json)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerManifest {
    /// Agent ID
    pub agent_id: String,
    /// Agent URI (http/localhost for local, https for remote)
    pub uri: String,
    /// Ed25519 public key (hex-encoded) for signature verification
    pub pubkey: String,
    /// Agent capabilities
    pub capabilities: Vec<PeerCapability>,
    /// Last updated timestamp
    pub updated_at: DateTime<Utc>,
    /// TTL in seconds (manifest expiry)
    pub ttl_secs: u64,
    /// Certificate chain (PKI validation)
    pub cert_chain: Option<Vec<String>>,
}

impl PeerManifest {
    /// Check if manifest is expired
    pub fn is_expired(&self) -> bool {
        let elapsed = Utc::now()
            .signed_duration_since(self.updated_at)
            .num_seconds() as u64;
        elapsed >= self.ttl_secs
    }

    /// Check if agent has specific capability
    pub fn has_capability(&self, name: &str) -> bool {
        self.capabilities
            .iter()
            .any(|c| c.name == name && c.available)
    }
}

/// Peer discovery interface
#[async_trait]
pub trait DiscoveryBackend: Send + Sync {
    /// Query peer manifest from /.well-known/agent.json
    async fn fetch_peer_manifest(&self, agent_uri: &str) -> crate::Result<PeerManifest>;

    /// Validate peer certificate chain
    async fn validate_peer_cert(&self, manifest: &PeerManifest) -> crate::Result<bool>;

    /// Register local peer in service registry
    async fn register_peer(&self, manifest: PeerManifest) -> crate::Result<()>;

    /// Deregister local peer
    async fn deregister_peer(&self, agent_id: &str) -> crate::Result<()>;
}

/// In-memory peer manifest cache
pub struct PeerCache {
    manifests: Arc<DashMap<String, PeerManifest>>,
}

impl PeerCache {
    /// Create new cache
    pub fn new() -> Self {
        PeerCache {
            manifests: Arc::new(DashMap::new()),
        }
    }

    /// Add or update peer manifest
    pub fn set(&self, agent_id: String, manifest: PeerManifest) {
        self.manifests.insert(agent_id, manifest);
    }

    /// Get peer manifest by agent ID
    pub fn get(&self, agent_id: &str) -> Option<PeerManifest> {
        self.manifests
            .get(agent_id)
            .filter(|m| !m.is_expired())
            .map(|m| m.clone())
    }

    /// Invalidate expired entries
    pub fn prune_expired(&self) {
        self.manifests.retain(|_, m| !m.is_expired());
    }

    /// List all active peers
    pub fn list_peers(&self) -> Vec<PeerManifest> {
        self.manifests
            .iter()
            .filter(|entry| !entry.is_expired())
            .map(|entry| entry.value().clone())
            .collect()
    }
}

/// Concrete peer discovery via siss-consensus-monitor + siss-vault-integration
pub struct PeerDiscovery {
    cache: PeerCache,
    local_manifest: Option<PeerManifest>,
    registry: Arc<AgentRegistry>,
}

impl PeerDiscovery {
    /// Create new peer discovery with agent registry
    pub fn new(registry: Arc<AgentRegistry>) -> Self {
        PeerDiscovery {
            cache: PeerCache::new(),
            local_manifest: None,
            registry,
        }
    }

    /// Set local agent manifest
    pub fn set_local_manifest(&mut self, manifest: PeerManifest) {
        self.local_manifest = Some(manifest);
    }

    /// Get peer manifest from cache or network
    pub async fn get_peer(&self, agent_id: &str) -> crate::Result<PeerManifest> {
        // Check cache first
        if let Some(manifest) = self.cache.get(agent_id) {
            return Ok(manifest);
        }

        // Cache miss: would query siss-consensus-monitor + siss-vault-integration
        // Placeholder for Phase 2B Part 1 integration
        Err(crate::A2AError::PeerNotFound(agent_id.to_string()))
    }

    /// Discover peers matching capability
    pub fn discover_by_capability(&self, capability: &str) -> Vec<PeerManifest> {
        self.cache
            .list_peers()
            .into_iter()
            .filter(|m| m.has_capability(capability))
            .collect()
    }

    /// Cache peer manifest after discovery
    pub fn cache_peer(&self, manifest: PeerManifest) {
        self.cache.set(manifest.agent_id.clone(), manifest);
    }

    /// Prune expired manifests from cache
    pub fn prune_cache(&self) {
        self.cache.prune_expired();
    }

    /// Register agent in the registry and cache manifest
    ///
    /// Called during agent startup to register capabilities and public key.
    /// Stores manifest in both AgentRegistry and local cache.
    pub fn register_agent(
        &self,
        agent_id: String,
        uri: String,
        capabilities: Vec<PeerCapability>,
        pubkey_hex: String,
        ttl_secs: u64,
    ) -> Result<()> {
        let manifest = PeerManifest {
            agent_id: agent_id.clone(),
            uri,
            pubkey: pubkey_hex.clone(),
            capabilities,
            updated_at: Utc::now(),
            ttl_secs,
            cert_chain: None,
        };

        // Register in agent registry
        self.registry
            .register(agent_id.clone(), manifest.clone(), pubkey_hex)?;

        // Cache locally
        self.cache_peer(manifest);

        Ok(())
    }

    /// Discover peers with a specific capability
    ///
    /// Enhanced to query registry first, then return all manifests with capability.
    pub fn discover_by_capability_enhanced(&self, capability_name: &str) -> Result<Vec<PeerManifest>> {
        // Get all registered agents from registry
        let registered = self.registry.list()?;

        // Filter by capability and collect manifests
        let peers: Vec<PeerManifest> = registered
            .iter()
            .filter(|agent| agent.manifest.has_capability(capability_name))
            .map(|agent| agent.manifest.clone())
            .collect();

        Ok(peers)
    }

    /// Refresh agent manifest TTL and update timestamp
    ///
    /// Called periodically to keep agent manifest fresh.
    /// Re-signs manifest with latest timestamp.
    pub fn refresh_manifest(&self, agent_id: &str) -> Result<()> {
        // Get agent from registry
        let agent = self.registry.get(agent_id)?;

        // Create updated manifest with new timestamp
        let mut updated_manifest = agent.manifest.clone();
        updated_manifest.updated_at = Utc::now();

        // Re-register with updated manifest (registry will overwrite)
        self.registry.register(
            agent_id.to_string(),
            updated_manifest.clone(),
            agent.pubkey_hex.clone(),
        )?;

        // Update cache
        self.cache_peer(updated_manifest);

        Ok(())
    }

    /// Validate agent public key against registered key
    ///
    /// Used during handoff verification to ensure key matches registry.
    /// Prevents unauthorized agents from impersonating registered peers.
    pub fn validate_agent_pubkey(&self, agent_id: &str, pubkey_hex: &str) -> Result<bool> {
        let agent = self.registry.get(agent_id)?;

        // Compare provided key with registered key
        Ok(agent.pubkey_hex == pubkey_hex)
    }
}

impl Default for PeerDiscovery {
    fn default() -> Self {
        Self::new(Arc::new(AgentRegistry::new()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_agent() {
        let registry = Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry.clone());

        let result = discovery.register_agent(
            "planner-1".to_string(),
            "http://localhost:9000".to_string(),
            vec![PeerCapability {
                name: "intent-classify".to_string(),
                version: "1.0".to_string(),
                available: true,
            }],
            "ed25519_pubkey_planner".to_string(),
            3600,
        );

        assert!(result.is_ok());

        // Verify agent is in registry
        let agent = registry.get("planner-1").expect("agent not found");
        assert_eq!(agent.agent_id, "planner-1");
        assert_eq!(agent.pubkey_hex, "ed25519_pubkey_planner");
        assert_eq!(agent.manifest.uri, "http://localhost:9000");
    }

    #[test]
    fn test_discover_capability() {
        let registry = Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry.clone());

        // Register compliance agent with veto capability
        discovery
            .register_agent(
                "compliance-1".to_string(),
                "http://localhost:9001".to_string(),
                vec![PeerCapability {
                    name: "veto".to_string(),
                    version: "1.0".to_string(),
                    available: true,
                }],
                "ed25519_pubkey_compliance".to_string(),
                3600,
            )
            .expect("register compliance");

        // Register evidence agent with collection capability
        discovery
            .register_agent(
                "evidence-1".to_string(),
                "http://localhost:9002".to_string(),
                vec![PeerCapability {
                    name: "collect-evidence".to_string(),
                    version: "1.0".to_string(),
                    available: true,
                }],
                "ed25519_pubkey_evidence".to_string(),
                3600,
            )
            .expect("register evidence");

        // Discover agents with veto capability
        let veto_agents = discovery.discover_by_capability_enhanced("veto").expect("discover");
        assert_eq!(veto_agents.len(), 1);
        assert_eq!(veto_agents[0].agent_id, "compliance-1");

        // Discover agents with evidence capability
        let evidence_agents = discovery
            .discover_by_capability_enhanced("collect-evidence")
            .expect("discover");
        assert_eq!(evidence_agents.len(), 1);
        assert_eq!(evidence_agents[0].agent_id, "evidence-1");
    }

    #[test]
    fn test_manifest_ttl_expiry() {
        let manifest = PeerManifest {
            agent_id: "test-agent".to_string(),
            uri: "http://localhost:9000".to_string(),
            pubkey: "abcd1234".to_string(),
            capabilities: vec![],
            updated_at: Utc::now(),
            ttl_secs: 0, // Expired immediately
            cert_chain: None,
        };
        assert!(manifest.is_expired());

        let manifest_valid = PeerManifest {
            agent_id: "test-agent-2".to_string(),
            uri: "http://localhost:9000".to_string(),
            pubkey: "abcd1234".to_string(),
            capabilities: vec![],
            updated_at: Utc::now(),
            ttl_secs: 3600, // Valid for 1 hour
            cert_chain: None,
        };
        assert!(!manifest_valid.is_expired());
    }

    #[test]
    fn test_pubkey_validation() {
        let registry = Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry.clone());

        // Register agent with specific pubkey
        discovery
            .register_agent(
                "auth-agent".to_string(),
                "http://localhost:9003".to_string(),
                vec![PeerCapability {
                    name: "authorize".to_string(),
                    version: "1.0".to_string(),
                    available: true,
                }],
                "ed25519_pubkey_auth_correct".to_string(),
                3600,
            )
            .expect("register");

        // Validate correct pubkey
        let valid = discovery
            .validate_agent_pubkey("auth-agent", "ed25519_pubkey_auth_correct")
            .expect("validate correct");
        assert!(valid);

        // Validate wrong pubkey
        let invalid = discovery
            .validate_agent_pubkey("auth-agent", "ed25519_pubkey_auth_wrong")
            .expect("validate wrong");
        assert!(!invalid);

        // Validate non-existent agent
        let not_found = discovery.validate_agent_pubkey("nonexistent", "any_key");
        assert!(not_found.is_err());
    }

    #[test]
    fn test_refresh_manifest() {
        let registry = Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry.clone());

        let original_time = Utc::now();

        // Register agent
        discovery
            .register_agent(
                "refresh-agent".to_string(),
                "http://localhost:9004".to_string(),
                vec![],
                "ed25519_pubkey_refresh".to_string(),
                3600,
            )
            .expect("register");

        // Get original manifest
        let agent_before = registry.get("refresh-agent").expect("get before");
        assert!(agent_before.manifest.updated_at >= original_time);

        // Wait a tiny bit and refresh
        std::thread::sleep(std::time::Duration::from_millis(10));

        discovery.refresh_manifest("refresh-agent").expect("refresh");

        // Get refreshed manifest
        let agent_after = registry.get("refresh-agent").expect("get after");
        assert!(agent_after.manifest.updated_at > agent_before.manifest.updated_at);
    }
}
