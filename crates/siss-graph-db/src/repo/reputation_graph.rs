use serde::{Deserialize, Serialize};
/// Phase 13: Reputation Graph Construction
/// Builds in-memory graph from Phase 12 delegation grants for cycle detection.
use sqlx::PgPool;
use std::collections::HashMap;
use uuid::Uuid;

/// Represents a sovereignty node in the reputation graph.
#[derive(Debug, Clone, Eq, PartialEq, Hash)]
pub struct GraphNode {
    pub sovereign_id: Uuid,
    pub name: String,
}

/// Represents a delegation grant edge (A grants to B).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEdge {
    pub from_sovereign: Uuid,
    pub to_sovereign: Uuid,
    pub delegation_grant_id: Uuid,
    pub ceiling_tier: u32,
    pub transitivity_depth: i16,
    pub status: String, // "active" | "revoked" | "expired"
}

/// The in-memory reputation graph (adjacency list representation).
#[derive(Debug, Clone)]
pub struct ReputationGraph {
    pub nodes: HashMap<Uuid, GraphNode>,
    pub adjacency: HashMap<Uuid, Vec<GraphEdge>>, // from_id → [edges]
    pub reverse_adjacency: HashMap<Uuid, Vec<GraphEdge>>, // to_id → [edges]
}

impl ReputationGraph {
    /// Create a new empty graph.
    pub fn new() -> Self {
        ReputationGraph {
            nodes: HashMap::new(),
            adjacency: HashMap::new(),
            reverse_adjacency: HashMap::new(),
        }
    }

    /// Add a sovereignty node to the graph.
    pub fn add_node(&mut self, sovereign_id: Uuid, name: String) {
        self.nodes
            .insert(sovereign_id, GraphNode { sovereign_id, name });
        self.adjacency.entry(sovereign_id).or_insert_with(Vec::new);
        self.reverse_adjacency
            .entry(sovereign_id)
            .or_insert_with(Vec::new);
    }

    /// Add a delegation edge to the graph.
    pub fn add_edge(&mut self, edge: GraphEdge) {
        self.adjacency
            .entry(edge.from_sovereign)
            .or_insert_with(Vec::new)
            .push(edge.clone());
        self.reverse_adjacency
            .entry(edge.to_sovereign)
            .or_insert_with(Vec::new)
            .push(edge);
    }

    /// Get outgoing edges from a node.
    pub fn outgoing_edges(&self, from: Uuid) -> Option<&Vec<GraphEdge>> {
        self.adjacency.get(&from)
    }

    /// Get incoming edges to a node.
    pub fn incoming_edges(&self, to: Uuid) -> Option<&Vec<GraphEdge>> {
        self.reverse_adjacency.get(&to)
    }

    /// Get all node IDs in the graph.
    pub fn all_nodes(&self) -> Vec<Uuid> {
        self.nodes.keys().copied().collect()
    }

    /// Get node count.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Get edge count.
    pub fn edge_count(&self) -> usize {
        self.adjacency.values().map(|v| v.len()).sum()
    }
}

impl Default for ReputationGraph {
    fn default() -> Self {
        Self::new()
    }
}

/// Errors that can occur during graph construction.
#[derive(Debug)]
pub enum GraphError {
    DatabaseError(sqlx::Error),
    EmptyGraph,
    InvalidNode(Uuid),
}

impl std::fmt::Display for GraphError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            GraphError::DatabaseError(e) => write!(f, "Database error: {}", e),
            GraphError::EmptyGraph => write!(f, "Graph is empty"),
            GraphError::InvalidNode(id) => write!(f, "Invalid node: {}", id),
        }
    }
}

impl std::error::Error for GraphError {}

impl From<sqlx::Error> for GraphError {
    fn from(err: sqlx::Error) -> Self {
        GraphError::DatabaseError(err)
    }
}

/// Build reputation graph from Phase 12 delegation data.
///
/// Queries memory_objects.delegation_cross for active grants and constructs
/// in-memory adjacency list representation for cycle detection.
pub async fn build_reputation_graph_from_db(pool: &PgPool) -> Result<ReputationGraph, GraphError> {
    let mut graph = ReputationGraph::new();

    // 1. Load all active sovereigns
    let sovereigns: Vec<(Uuid, String)> =
        sqlx::query_as("SELECT id, name FROM sovereigns WHERE status = 'active'")
            .fetch_all(pool)
            .await?;

    for (id, name) in sovereigns {
        graph.add_node(id, name);
    }

    // 2. Load all active cross-sovereign delegation grants
    let grants: Vec<(Uuid, Uuid, Uuid, i16, i16)> = sqlx::query_as(
        "SELECT id, grantor_sovereign_id, grantee_sovereign_id, ceiling_tier, transitivity_depth \
         FROM cross_sovereign_delegation_grants \
         WHERE status = 'active' AND revoked_at IS NULL",
    )
    .fetch_all(pool)
    .await?;

    for (grant_id, from, to, ceiling, depth) in grants {
        let edge = GraphEdge {
            from_sovereign: from,
            to_sovereign: to,
            delegation_grant_id: grant_id,
            ceiling_tier: ceiling as u32,
            transitivity_depth: depth,
            status: "active".to_string(),
        };
        graph.add_edge(edge);
    }

    Ok(graph)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_graph_construction() {
        let mut graph = ReputationGraph::new();

        let a = Uuid::new_v4();
        let b = Uuid::new_v4();

        graph.add_node(a, "alice".to_string());
        graph.add_node(b, "bob".to_string());

        let edge = GraphEdge {
            from_sovereign: a,
            to_sovereign: b,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        };

        graph.add_edge(edge);

        assert_eq!(graph.node_count(), 2);
        assert_eq!(graph.edge_count(), 1);
        assert!(graph.outgoing_edges(a).is_some());
        assert!(graph.incoming_edges(b).is_some());
    }

    #[test]
    fn test_graph_empty() {
        let graph = ReputationGraph::new();
        assert_eq!(graph.node_count(), 0);
        assert_eq!(graph.edge_count(), 0);
    }
}
