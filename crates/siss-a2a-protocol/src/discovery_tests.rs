/// Track D: Unit Tests for Discovery Registry & Capability Queries

#[cfg(test)]
mod discovery_registry_tests {
    use crate::discovery::{PeerDiscovery, PeerManifest, PeerCapability};
    use crate::integration::AgentRegistry;
    use chrono::Utc;

    fn create_test_manifest(agent_id: &str, capabilities: Vec<&str>) -> PeerManifest {
        PeerManifest {
            agent_id: agent_id.to_string(),
            uri: format!("http://localhost:9000/{}", agent_id),
            pubkey: format!("pubkey_{}", agent_id),
            capabilities: capabilities
                .iter()
                .map(|cap| PeerCapability {
                    name: cap.to_string(),
                    version: "1.0".to_string(),
                    available: true,
                })
                .collect(),
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        }
    }

    #[test]
    fn test_agent_registration() {
        // GIVEN: a discovery system
        let registry = AgentRegistry::new();

        // WHEN: we register an agent
        let manifest = create_test_manifest("agent-1", vec!["planning"]);
        registry
            .register("agent-1".to_string(), manifest.clone(), "pubkey_1".to_string())
            .expect("register");

        // THEN: the agent is retrievable
        let agent = registry.get("agent-1").expect("get");
        assert_eq!(agent.agent_id, "agent-1");
        assert_eq!(agent.manifest.agent_id, "agent-1");
    }

    #[test]
    fn test_capability_query() {
        // GIVEN: discovery with multiple agents registered
        let registry = std::sync::Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry);

        let veto_manifest = create_test_manifest("compliance-1", vec!["veto", "evaluate"]);
        let plan_manifest = create_test_manifest("planner-1", vec!["planning", "delegate"]);

        discovery.cache_peer(veto_manifest);
        discovery.cache_peer(plan_manifest);

        // WHEN: we query for agents with "veto" capability
        let veto_agents = discovery.discover_by_capability("veto");

        // THEN: only compliance agent is returned
        assert_eq!(veto_agents.len(), 1);
        assert_eq!(veto_agents[0].agent_id, "compliance-1");
    }

    #[test]
    fn test_unknown_agent_not_found() {
        // GIVEN: a discovery system
        let registry = AgentRegistry::new();

        // WHEN: we query for an agent that doesn't exist
        let result = registry.get("unknown-agent");

        // THEN: an error is returned
        assert!(result.is_err());
    }

    #[test]
    fn test_manifest_ttl_expiry() {
        // GIVEN: a manifest with short TTL
        let mut manifest = create_test_manifest("agent-1", vec![]);
        manifest.ttl_secs = 0; // Already expired

        // WHEN: we check expiry
        let is_expired = manifest.is_expired();

        // THEN: manifest is considered expired
        assert!(is_expired);
    }

    #[test]
    fn test_manifest_ttl_valid() {
        // GIVEN: a manifest with long TTL
        let manifest = create_test_manifest("agent-1", vec![]);
        // ttl_secs = 3600 (1 hour)

        // WHEN: we check expiry
        let is_expired = manifest.is_expired();

        // THEN: manifest is not expired
        assert!(!is_expired);
    }

    #[test]
    fn test_capability_not_available() {
        // GIVEN: a discovery system with agent having unavailable capability
        let registry = std::sync::Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry);
        let mut manifest = create_test_manifest("agent-1", vec!["evaluate"]);
        manifest.capabilities[0].available = false; // Mark as unavailable

        discovery.cache_peer(manifest);

        // WHEN: we query for that capability
        let agents = discovery.discover_by_capability("evaluate");

        // THEN: agent is not returned
        assert_eq!(agents.len(), 0);
    }

    #[test]
    fn test_multiple_capabilities() {
        // GIVEN: agents with multiple capabilities
        let registry = std::sync::Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry);
        let manifest = create_test_manifest(
            "multi-agent",
            vec!["veto", "evaluate", "approve", "delegate"],
        );
        discovery.cache_peer(manifest);

        // WHEN: we query for each capability
        let veto = discovery.discover_by_capability("veto");
        let evaluate = discovery.discover_by_capability("evaluate");
        let approve = discovery.discover_by_capability("approve");
        let delegate = discovery.discover_by_capability("delegate");

        // THEN: agent appears in all queries
        assert_eq!(veto.len(), 1);
        assert_eq!(evaluate.len(), 1);
        assert_eq!(approve.len(), 1);
        assert_eq!(delegate.len(), 1);
    }

    #[test]
    fn test_discover_multiple_agents_same_capability() {
        // GIVEN: multiple agents with same capability
        let registry = std::sync::Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry);
        let agent1 = create_test_manifest("agent-1", vec!["execute"]);
        let agent2 = create_test_manifest("agent-2", vec!["execute"]);
        let agent3 = create_test_manifest("agent-3", vec!["execute"]);

        discovery.cache_peer(agent1);
        discovery.cache_peer(agent2);
        discovery.cache_peer(agent3);

        // WHEN: we query for "execute"
        let agents = discovery.discover_by_capability("execute");

        // THEN: all three agents are returned
        assert_eq!(agents.len(), 3);
        let ids: Vec<String> = agents.iter().map(|a| a.agent_id.clone()).collect();
        assert!(ids.contains(&"agent-1".to_string()));
        assert!(ids.contains(&"agent-2".to_string()));
        assert!(ids.contains(&"agent-3".to_string()));
    }

    #[test]
    fn test_cache_persistence() {
        // GIVEN: a discovery system with cached agents
        let registry = std::sync::Arc::new(AgentRegistry::new());
        let discovery = PeerDiscovery::new(registry);
        let manifest = create_test_manifest("agent-1", vec!["test"]);
        discovery.cache_peer(manifest);

        // WHEN: we cache another agent
        let manifest2 = create_test_manifest("agent-2", vec!["test"]);
        discovery.cache_peer(manifest2);

        // THEN: both agents are still in cache
        let agents = discovery.discover_by_capability("test");
        assert_eq!(agents.len(), 2);
    }

    #[test]
    fn test_concurrent_registry_registration() {
        // GIVEN: a registry
        let registry = std::sync::Arc::new(AgentRegistry::new());

        // WHEN: 10 agents register concurrently
        let mut handles = vec![];
        for i in 0..10 {
            let registry_clone = registry.clone();
            let handle = std::thread::spawn(move || {
                let manifest = create_test_manifest(&format!("agent-{}", i), vec!["test"]);
                let agent_id = format!("agent-{}", i);
                registry_clone
                    .register(agent_id, manifest, format!("pubkey_{}", i))
                    .expect("register")
            });
            handles.push(handle);
        }

        // THEN: all threads complete successfully
        for handle in handles {
            handle.join().expect("join");
        }

        // AND: all agents are registered
        let agents = registry.list().expect("list");
        assert_eq!(agents.len(), 10);
    }
}
