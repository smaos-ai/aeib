/// CycleDetector: Detects cycles in policy DAGs using Tarjan's algorithm.
///
/// Tarjan's algorithm identifies Strongly Connected Components (SCCs) in O(V+E) time.
/// A non-empty SCC indicates a cycle (nodes that can reach each other).

use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Node {
    pub id: String,
}

impl Node {
    pub fn new(id: String) -> Self {
        Node { id }
    }
}

#[derive(Debug, Clone)]
pub struct Graph {
    nodes: HashSet<String>,
    edges: HashMap<String, Vec<String>>, // adjacency list
}

impl Graph {
    pub fn new() -> Self {
        Graph {
            nodes: HashSet::new(),
            edges: HashMap::new(),
        }
    }

    pub fn add_node(&mut self, node: Node) {
        self.nodes.insert(node.id.clone());
        self.edges.entry(node.id).or_insert_with(Vec::new);
    }

    pub fn add_edge(&mut self, from: String, to: String) {
        self.edges.entry(from).or_insert_with(Vec::new).push(to);
    }

    pub fn get_successors(&self, node_id: &str) -> Vec<String> {
        self.edges
            .get(node_id)
            .cloned()
            .unwrap_or_default()
    }

    pub fn nodes(&self) -> impl Iterator<Item = &String> {
        self.nodes.iter()
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }
}

impl Default for Graph {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone)]
pub struct CycleDetector;

impl CycleDetector {
    pub fn new() -> Self {
        CycleDetector
    }

    /// Find all cycles in the graph using Tarjan's algorithm.
    /// Returns a Vec of SCCs (each SCC is a Vec of node IDs).
    /// An SCC with size > 1 indicates a cycle, or size == 1 with self-loop.
    pub fn find_cycles(&self, graph: &Graph) -> Vec<Vec<String>> {
        let mut state = TarjanState::new();

        for node_id in graph.nodes() {
            if !state.on_stack.contains(node_id) && state.index_map.get(node_id).is_none() {
                self.strongconnect(node_id, graph, &mut state);
            }
        }

        state.sccs
    }

    fn strongconnect(
        &self,
        node_id: &str,
        graph: &Graph,
        state: &mut TarjanState,
    ) {
        let index = state.index;
        state.index += 1;

        state.index_map.insert(node_id.to_string(), index);
        state.lowlink_map.insert(node_id.to_string(), index);
        state.stack.push(node_id.to_string());
        state.on_stack.insert(node_id.to_string());

        for successor_id in &graph.get_successors(node_id) {
            if state.index_map.get(successor_id).is_none() {
                // Not yet visited
                self.strongconnect(successor_id, graph, state);

                let lowlink_successor = state.lowlink_map.get(successor_id).copied().unwrap_or(0);
                let lowlink_curr = state.lowlink_map.entry(node_id.to_string()).or_insert(0);
                *lowlink_curr = (*lowlink_curr).min(lowlink_successor);
            } else if state.on_stack.contains(successor_id) {
                // Back edge - part of SCC
                let index_successor = state.index_map.get(successor_id).copied().unwrap_or(0);
                let lowlink_curr = state.lowlink_map.entry(node_id.to_string()).or_insert(0);
                *lowlink_curr = (*lowlink_curr).min(index_successor);
            }
        }

        // If node_id is a root node, pop the stack and create SCC
        let node_index = state.index_map.get(node_id).copied().unwrap_or(0);
        let node_lowlink = state.lowlink_map.get(node_id).copied().unwrap_or(0);

        if node_lowlink == node_index {
            let mut scc = Vec::new();
            loop {
                let w = state.stack.pop().unwrap_or_default();
                state.on_stack.remove(&w);
                scc.push(w.clone());

                if w == node_id {
                    break;
                }
            }

            // Include SCCs with size > 1 (genuine cycles) or size == 1 with self-loop
            if scc.len() > 1 {
                state.sccs.push(scc);
            } else if scc.len() == 1 {
                // Check for self-loop
                let node = &scc[0];
                if graph.get_successors(node).contains(node) {
                    state.sccs.push(scc);
                }
            }
        }
    }
}

impl Default for CycleDetector {
    fn default() -> Self {
        Self::new()
    }
}

struct TarjanState {
    index: usize,
    stack: Vec<String>,
    on_stack: HashSet<String>,
    index_map: HashMap<String, usize>,
    lowlink_map: HashMap<String, usize>,
    sccs: Vec<Vec<String>>,
}

impl TarjanState {
    fn new() -> Self {
        TarjanState {
            index: 0,
            stack: Vec::new(),
            on_stack: HashSet::new(),
            index_map: HashMap::new(),
            lowlink_map: HashMap::new(),
            sccs: Vec::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_linear_chain() {
        let mut graph = Graph::new();
        graph.add_node(Node::new("a".into()));
        graph.add_node(Node::new("b".into()));
        graph.add_node(Node::new("c".into()));

        graph.add_edge("a".into(), "b".into());
        graph.add_edge("b".into(), "c".into());

        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert!(cycles.is_empty());
    }

    #[test]
    fn test_self_loop() {
        let mut graph = Graph::new();
        graph.add_node(Node::new("a".into()));
        graph.add_edge("a".into(), "a".into());

        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert_eq!(cycles.len(), 1);
    }

    #[test]
    fn test_two_node_cycle() {
        let mut graph = Graph::new();
        graph.add_node(Node::new("a".into()));
        graph.add_node(Node::new("b".into()));

        graph.add_edge("a".into(), "b".into());
        graph.add_edge("b".into(), "a".into());

        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert_eq!(cycles.len(), 1);
        assert_eq!(cycles[0].len(), 2);
    }

    #[test]
    fn test_diamond_dag() {
        let mut graph = Graph::new();
        graph.add_node(Node::new("a".into()));
        graph.add_node(Node::new("b".into()));
        graph.add_node(Node::new("c".into()));
        graph.add_node(Node::new("d".into()));

        graph.add_edge("a".into(), "b".into());
        graph.add_edge("a".into(), "c".into());
        graph.add_edge("b".into(), "d".into());
        graph.add_edge("c".into(), "d".into());

        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert!(cycles.is_empty());
    }

    #[test]
    fn test_three_node_cycle() {
        let mut graph = Graph::new();
        graph.add_node(Node::new("a".into()));
        graph.add_node(Node::new("b".into()));
        graph.add_node(Node::new("c".into()));

        graph.add_edge("a".into(), "b".into());
        graph.add_edge("b".into(), "c".into());
        graph.add_edge("c".into(), "a".into());

        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert_eq!(cycles.len(), 1);
        assert_eq!(cycles[0].len(), 3);
    }

    #[test]
    fn test_multiple_cycles() {
        let mut graph = Graph::new();
        graph.add_node(Node::new("a".into()));
        graph.add_node(Node::new("b".into()));
        graph.add_node(Node::new("c".into()));
        graph.add_node(Node::new("d".into()));

        // Cycle 1: a <-> b
        graph.add_edge("a".into(), "b".into());
        graph.add_edge("b".into(), "a".into());

        // Cycle 2: c <-> d
        graph.add_edge("c".into(), "d".into());
        graph.add_edge("d".into(), "c".into());

        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert_eq!(cycles.len(), 2);
    }

    #[test]
    fn test_empty_graph() {
        let graph = Graph::new();
        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert!(cycles.is_empty());
    }

    #[test]
    fn test_single_node() {
        let mut graph = Graph::new();
        graph.add_node(Node::new("a".into()));

        let detector = CycleDetector::new();
        let cycles = detector.find_cycles(&graph);
        assert!(cycles.is_empty());
    }
}
