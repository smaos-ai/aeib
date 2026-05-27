use uuid::Uuid;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, PartialEq)]
struct TopicCluster {
    id: String,
    members: Vec<Uuid>,
    topic_tags: Vec<String>,
    fault_domain: String,
}

#[derive(Clone, Debug)]
struct ClusterManager {
    clusters: HashMap<String, TopicCluster>,
    agent_to_cluster: HashMap<Uuid, String>,
}

impl ClusterManager {
    fn new() -> Self {
        Self {
            clusters: HashMap::new(),
            agent_to_cluster: HashMap::new(),
        }
    }

    fn register_cluster(&mut self, cluster: TopicCluster) -> Result<(), String> {
        if self.clusters.contains_key(&cluster.id) {
            return Err("Cluster already exists".to_string());
        }
        self.clusters.insert(cluster.id.clone(), cluster);
        Ok(())
    }

    fn add_agent_to_cluster(&mut self, agent_id: Uuid, cluster_id: &str) -> Result<(), String> {
        let cluster = self.clusters.get_mut(cluster_id)
            .ok_or("Cluster not found".to_string())?;

        if !cluster.members.contains(&agent_id) {
            cluster.members.push(agent_id);
        }
        self.agent_to_cluster.insert(agent_id, cluster_id.to_string());
        Ok(())
    }

    fn isolate_cluster(&self, cluster_id: &str) -> Result<Vec<Uuid>, String> {
        let cluster = self.clusters.get(cluster_id)
            .ok_or("Cluster not found".to_string())?;
        Ok(cluster.members.clone())
    }

    fn get_cluster_for_agent(&self, agent_id: Uuid) -> Option<String> {
        self.agent_to_cluster.get(&agent_id).cloned()
    }

    fn cluster_count(&self) -> usize {
        self.clusters.len()
    }

    fn agents_in_cluster(&self, cluster_id: &str) -> Result<usize, String> {
        self.clusters.get(cluster_id)
            .map(|c| c.members.len())
            .ok_or("Cluster not found".to_string())
    }

    fn get_fault_domain(&self, cluster_id: &str) -> Result<String, String> {
        self.clusters.get(cluster_id)
            .map(|c| c.fault_domain.clone())
            .ok_or("Cluster not found".to_string())
    }

    fn find_clusters_by_topic(&self, topic: &str) -> Vec<String> {
        self.clusters
            .iter()
            .filter(|(_, c)| c.topic_tags.contains(&topic.to_string()))
            .map(|(id, _)| id.clone())
            .collect()
    }

    fn get_isolated_clusters(&self, fault_domain: &str) -> Vec<String> {
        self.clusters
            .iter()
            .filter(|(_, c)| c.fault_domain == fault_domain)
            .map(|(id, _)| id.clone())
            .collect()
    }
}

#[test]
fn test_phase_3_5_cluster_creation() {
    let mut manager = ClusterManager::new();
    let cluster = TopicCluster {
        id: "auth_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["authentication".to_string()],
        fault_domain: "auth_domain".to_string(),
    };

    assert!(manager.register_cluster(cluster).is_ok());
    assert_eq!(manager.cluster_count(), 1);
}

#[test]
fn test_phase_3_5_duplicate_cluster_rejected() {
    let mut manager = ClusterManager::new();
    let cluster = TopicCluster {
        id: "auth_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["authentication".to_string()],
        fault_domain: "auth_domain".to_string(),
    };

    assert!(manager.register_cluster(cluster.clone()).is_ok());
    assert!(manager.register_cluster(cluster).is_err());
}

#[test]
fn test_phase_3_5_agent_assignment_to_cluster() {
    let mut manager = ClusterManager::new();
    let cluster = TopicCluster {
        id: "compute_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["computation".to_string()],
        fault_domain: "compute_domain".to_string(),
    };
    manager.register_cluster(cluster).unwrap();

    let agent_id = Uuid::new_v4();
    assert!(manager.add_agent_to_cluster(agent_id, "compute_cluster").is_ok());
    assert_eq!(manager.agents_in_cluster("compute_cluster").unwrap(), 1);
}

#[test]
fn test_phase_3_5_agent_to_cluster_mapping() {
    let mut manager = ClusterManager::new();
    let cluster = TopicCluster {
        id: "storage_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["storage".to_string()],
        fault_domain: "storage_domain".to_string(),
    };
    manager.register_cluster(cluster).unwrap();

    let agent_id = Uuid::new_v4();
    manager.add_agent_to_cluster(agent_id, "storage_cluster").unwrap();

    let cluster_id = manager.get_cluster_for_agent(agent_id);
    assert_eq!(cluster_id, Some("storage_cluster".to_string()));
}

#[test]
fn test_phase_3_5_cluster_isolation() {
    let mut manager = ClusterManager::new();
    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();
    let agent3 = Uuid::new_v4();

    let cluster = TopicCluster {
        id: "isolated_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["isolation_test".to_string()],
        fault_domain: "isolated_domain".to_string(),
    };
    manager.register_cluster(cluster).unwrap();

    manager.add_agent_to_cluster(agent1, "isolated_cluster").unwrap();
    manager.add_agent_to_cluster(agent2, "isolated_cluster").unwrap();
    manager.add_agent_to_cluster(agent3, "isolated_cluster").unwrap();

    let isolated_agents = manager.isolate_cluster("isolated_cluster").unwrap();
    assert_eq!(isolated_agents.len(), 3);
    assert!(isolated_agents.contains(&agent1));
    assert!(isolated_agents.contains(&agent2));
    assert!(isolated_agents.contains(&agent3));
}

#[test]
fn test_phase_3_5_multiple_clusters_independent() {
    let mut manager = ClusterManager::new();

    let cluster1 = TopicCluster {
        id: "cluster1".to_string(),
        members: vec![],
        topic_tags: vec!["topic1".to_string()],
        fault_domain: "domain1".to_string(),
    };
    let cluster2 = TopicCluster {
        id: "cluster2".to_string(),
        members: vec![],
        topic_tags: vec!["topic2".to_string()],
        fault_domain: "domain2".to_string(),
    };

    manager.register_cluster(cluster1).unwrap();
    manager.register_cluster(cluster2).unwrap();

    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();

    manager.add_agent_to_cluster(agent1, "cluster1").unwrap();
    manager.add_agent_to_cluster(agent2, "cluster2").unwrap();

    assert_eq!(manager.agents_in_cluster("cluster1").unwrap(), 1);
    assert_eq!(manager.agents_in_cluster("cluster2").unwrap(), 1);
}

#[test]
fn test_phase_3_5_topic_based_cluster_lookup() {
    let mut manager = ClusterManager::new();

    let cluster1 = TopicCluster {
        id: "auth_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["authentication".to_string(), "security".to_string()],
        fault_domain: "auth_domain".to_string(),
    };
    let cluster2 = TopicCluster {
        id: "compute_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["computation".to_string()],
        fault_domain: "compute_domain".to_string(),
    };

    manager.register_cluster(cluster1).unwrap();
    manager.register_cluster(cluster2).unwrap();

    let auth_clusters = manager.find_clusters_by_topic("authentication");
    assert_eq!(auth_clusters.len(), 1);
    assert!(auth_clusters.contains(&"auth_cluster".to_string()));

    let security_clusters = manager.find_clusters_by_topic("security");
    assert_eq!(security_clusters.len(), 1);

    let compute_clusters = manager.find_clusters_by_topic("computation");
    assert_eq!(compute_clusters.len(), 1);
}

#[test]
fn test_phase_3_5_fault_domain_isolation_grouping() {
    let mut manager = ClusterManager::new();

    let cluster1 = TopicCluster {
        id: "cluster1".to_string(),
        members: vec![],
        topic_tags: vec!["topic1".to_string()],
        fault_domain: "zone_a".to_string(),
    };
    let cluster2 = TopicCluster {
        id: "cluster2".to_string(),
        members: vec![],
        topic_tags: vec!["topic2".to_string()],
        fault_domain: "zone_a".to_string(),
    };
    let cluster3 = TopicCluster {
        id: "cluster3".to_string(),
        members: vec![],
        topic_tags: vec!["topic3".to_string()],
        fault_domain: "zone_b".to_string(),
    };

    manager.register_cluster(cluster1).unwrap();
    manager.register_cluster(cluster2).unwrap();
    manager.register_cluster(cluster3).unwrap();

    let zone_a_clusters = manager.get_isolated_clusters("zone_a");
    assert_eq!(zone_a_clusters.len(), 2);
    assert!(zone_a_clusters.contains(&"cluster1".to_string()));
    assert!(zone_a_clusters.contains(&"cluster2".to_string()));

    let zone_b_clusters = manager.get_isolated_clusters("zone_b");
    assert_eq!(zone_b_clusters.len(), 1);
    assert!(zone_b_clusters.contains(&"cluster3".to_string()));
}

#[test]
fn test_phase_3_5_fault_domain_attribution() {
    let mut manager = ClusterManager::new();
    let cluster = TopicCluster {
        id: "fault_test_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["test".to_string()],
        fault_domain: "expected_domain".to_string(),
    };

    manager.register_cluster(cluster).unwrap();
    let domain = manager.get_fault_domain("fault_test_cluster").unwrap();
    assert_eq!(domain, "expected_domain");
}

#[test]
fn test_phase_3_5_duplicate_agent_idempotent() {
    let mut manager = ClusterManager::new();
    let cluster = TopicCluster {
        id: "idempotent_cluster".to_string(),
        members: vec![],
        topic_tags: vec!["test".to_string()],
        fault_domain: "domain".to_string(),
    };
    manager.register_cluster(cluster).unwrap();

    let agent_id = Uuid::new_v4();
    manager.add_agent_to_cluster(agent_id, "idempotent_cluster").unwrap();
    manager.add_agent_to_cluster(agent_id, "idempotent_cluster").unwrap();

    assert_eq!(manager.agents_in_cluster("idempotent_cluster").unwrap(), 1);
}
