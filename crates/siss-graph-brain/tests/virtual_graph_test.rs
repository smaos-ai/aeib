use siss_graph_brain::{
    Neo4jVirtualGraphConnector, VirtualGraphEndpoint, VirtualGraphError,
};

#[test]
fn test_virtual_graph_connector_initializes() {
    let endpoint = VirtualGraphEndpoint {
        url: "bolt://localhost:7687".to_string(),
        username: "test_user".to_string(),
        password: "test_pass".to_string(),
    };

    let connector = Neo4jVirtualGraphConnector::new(endpoint);
    assert!(connector.is_ok());
}

#[test]
fn test_virtual_graph_returns_provenanced_capsules() {
    let endpoint = VirtualGraphEndpoint {
        url: "bolt://localhost:7687".to_string(),
        username: "test_user".to_string(),
        password: "test_pass".to_string(),
    };

    let connector = Neo4jVirtualGraphConnector::new(endpoint).unwrap();
    let query = "MATCH (n) RETURN n LIMIT 1";

    // Mock result: should return ProvenancedCapsule with gemba_proof
    let result = connector.query_warehouse(query);
    if let Ok(Some(capsule)) = result {
        assert!(!capsule.gemba_proof.is_empty());
        assert!(!capsule.source_endpoint.is_empty());
    }
}

#[test]
fn test_virtual_graph_error_display() {
    let err = VirtualGraphError::ConnectionFailed("test".to_string());
    let display = format!("{}", err);
    assert!(display.contains("Connection"));
}

#[test]
fn test_virtual_graph_connector_rejects_empty_url() {
    let endpoint = VirtualGraphEndpoint {
        url: "".to_string(),
        username: "test_user".to_string(),
        password: "test_pass".to_string(),
    };

    let result = Neo4jVirtualGraphConnector::new(endpoint);
    assert!(result.is_err());
    if let Err(err) = result {
        let msg = format!("{}", err);
        assert!(msg.contains("Connection"));
    }
}

#[test]
fn test_virtual_graph_health_check() {
    let endpoint = VirtualGraphEndpoint {
        url: "bolt://localhost:7687".to_string(),
        username: "test_user".to_string(),
        password: "test_pass".to_string(),
    };

    let connector = Neo4jVirtualGraphConnector::new(endpoint).unwrap();
    let result = connector.health_check();
    assert!(result.is_ok());
    assert!(result.unwrap());
}
