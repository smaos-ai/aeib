/// Phase 13: Cycle Forensics — Severity Scoring and Weakest Link Detection
/// Analyzes detected cycles to identify severity, weakest link, and cycle metrics.
use crate::repo::reputation_graph::ReputationGraph;
use uuid::Uuid;

/// Represents a detected reputation cycle with forensic analysis.
#[derive(Debug, Clone)]
pub struct ReputationCycle {
    pub cycle_nodes: Vec<Uuid>,
    pub severity: String, // "critical" | "high" | "medium" | "low"
    pub weakest_link_id: Uuid,
    pub weakest_link_ceiling: u32,
    pub base_score: f64,
    pub trust_density: f64,
    pub cycle_length: usize,
}

impl ReputationCycle {
    /// Analyze a strongly connected component (cycle) to compute severity, weakest link, and metrics.
    ///
    /// # Algorithm
    /// 1. Find weakest link: node with minimum ceiling_tier in the cycle
    /// 2. Compute trust_density: average in-degree / total nodes
    /// 3. Compute base_score: min_tier_in_cycle × trust_density
    /// 4. Assign severity:
    ///    - "critical" if base_score > 80 AND cycle_length ≤ 3
    ///    - "high" if base_score > 60
    ///    - "medium" if base_score > 40
    ///    - "low" otherwise
    pub fn analyze_cycle(
        cycle_nodes: Vec<Uuid>,
        graph: &ReputationGraph,
    ) -> Result<ReputationCycle, String> {
        if cycle_nodes.is_empty() {
            return Err("Empty cycle".to_string());
        }

        if cycle_nodes.len() < 2 {
            return Err("Cycle must have at least 2 nodes".to_string());
        }

        // Find weakest link (minimum ceiling_tier in cycle)
        // Deterministic tiebreaker: when ceiling_tiers are equal, use destination UUID (lexicographically smallest wins)
        let mut weakest_link_id = cycle_nodes[0];
        let mut weakest_link_ceiling = u32::MAX;
        let mut weakest_dest_id = Uuid::nil();  // overwritten on first valid edge

        for node_id in &cycle_nodes {
            if let Some(outgoing) = graph.outgoing_edges(*node_id) {
                for edge in outgoing {
                    // Check if this edge is part of the cycle (goes to another cycle node)
                    if cycle_nodes.contains(&edge.to_sovereign) {
                        let is_weaker = edge.ceiling_tier < weakest_link_ceiling;
                        let is_tie_broken = edge.ceiling_tier == weakest_link_ceiling
                            && edge.to_sovereign < weakest_dest_id;
                        if is_weaker || is_tie_broken {
                            weakest_link_ceiling = edge.ceiling_tier;
                            weakest_link_id = *node_id;
                            weakest_dest_id = edge.to_sovereign;
                        }
                    }
                }
            }
        }

        // Handle case where no internal edges found (shouldn't happen for valid SCC)
        if weakest_link_ceiling == u32::MAX {
            return Err("No internal edges found in cycle".to_string());
        }

        // Compute trust_density: average in-degree of cycle nodes within the cycle
        let mut total_internal_degree = 0;
        for node_id in &cycle_nodes {
            if let Some(incoming) = graph.incoming_edges(*node_id) {
                let internal_edges = incoming
                    .iter()
                    .filter(|e| cycle_nodes.contains(&e.from_sovereign))
                    .count();
                total_internal_degree += internal_edges;
            }
        }

        let cycle_length = cycle_nodes.len();
        let avg_internal_degree = if cycle_length > 0 {
            total_internal_degree as f64 / cycle_length as f64
        } else {
            0.0
        };

        // trust_density: ratio of average internal degree to max possible (cycle_length - 1)
        let max_degree = (cycle_length - 1) as f64;
        let trust_density = if max_degree > 0.0 {
            avg_internal_degree / max_degree
        } else {
            0.0
        };

        // base_score: min_tier × trust_density
        // Normalized to 0-100 scale where 100 = all nodes connected at max tier
        let base_score = (weakest_link_ceiling as f64 / 100.0) * trust_density * 100.0;

        // Assign severity based on base_score and cycle_length
        let severity = if base_score > 80.0 && cycle_length <= 3 {
            "critical".to_string()
        } else if base_score > 60.0 {
            "high".to_string()
        } else if base_score > 40.0 {
            "medium".to_string()
        } else {
            "low".to_string()
        };

        Ok(ReputationCycle {
            cycle_nodes,
            severity,
            weakest_link_id,
            weakest_link_ceiling,
            base_score,
            trust_density,
            cycle_length,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::repo::reputation_graph::GraphEdge;

    #[test]
    fn test_weakest_link_identification() {
        // Create cycle: A→B (ceiling 80), B→C (ceiling 50), C→A (ceiling 100)
        // Weakest link is B→C with ceiling 50
        let mut graph = ReputationGraph::new();

        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();

        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());

        graph.add_edge(GraphEdge {
            from_sovereign: a,
            to_sovereign: b,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 80,
            transitivity_depth: 1,
            status: "active".to_string(),
        });

        graph.add_edge(GraphEdge {
            from_sovereign: b,
            to_sovereign: c,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 50,
            transitivity_depth: 1,
            status: "active".to_string(),
        });

        graph.add_edge(GraphEdge {
            from_sovereign: c,
            to_sovereign: a,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        });

        let cycle = vec![a, b, c];
        let result = ReputationCycle::analyze_cycle(cycle, &graph);

        assert!(result.is_ok(), "Cycle analysis should succeed");
        let cycle = result.unwrap();
        assert_eq!(
            cycle.weakest_link_ceiling, 50,
            "Weakest link ceiling should be 50"
        );
        assert_eq!(cycle.weakest_link_id, b, "Weakest link should be B");
    }

    #[test]
    fn test_cycle_severity_critical() {
        // Create fully connected 3-node cycle with high ceiling tiers
        // Should be "critical" (base_score > 80 AND length ≤ 3)
        let mut graph = ReputationGraph::new();

        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();

        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());

        // Fully connected triangle with high ceilings
        for (from, to) in [(a, b), (a, c), (b, a), (b, c), (c, a), (c, b)] {
            graph.add_edge(GraphEdge {
                from_sovereign: from,
                to_sovereign: to,
                delegation_grant_id: Uuid::new_v4(),
                ceiling_tier: 95,
                transitivity_depth: 1,
                status: "active".to_string(),
            });
        }

        let cycle = vec![a, b, c];
        let result = ReputationCycle::analyze_cycle(cycle, &graph);

        assert!(result.is_ok());
        let cycle = result.unwrap();
        assert_eq!(cycle.severity, "critical", "Severity should be critical");
        assert!(cycle.base_score > 80.0, "Base score should be > 80");
    }

    #[test]
    fn test_cycle_severity_high() {
        // Create fully connected 4-node cycle (each node connects to all others)
        // with medium-high ceilings (75). Should be "high" (base_score > 60 && <= 80)
        // With 4 nodes: ceiling=75, trust_density=1.0 → base_score=75
        let mut graph = ReputationGraph::new();

        let nodes: Vec<Uuid> = (0..4).map(|_| Uuid::new_v4()).collect();
        for id in &nodes {
            graph.add_node(*id, id.to_string());
        }

        // Create fully connected cycle (all nodes connected to all others)
        for i in 0..nodes.len() {
            for j in 0..nodes.len() {
                if i != j {
                    graph.add_edge(GraphEdge {
                        from_sovereign: nodes[i],
                        to_sovereign: nodes[j],
                        delegation_grant_id: Uuid::new_v4(),
                        ceiling_tier: 75,
                        transitivity_depth: 1,
                        status: "active".to_string(),
                    });
                }
            }
        }

        let result = ReputationCycle::analyze_cycle(nodes.clone(), &graph);

        assert!(result.is_ok());
        let cycle = result.unwrap();
        assert_eq!(
            cycle.severity, "high",
            "Fully connected 4-node cycle should be high"
        );
        assert!(
            cycle.base_score > 60.0 && cycle.base_score <= 80.0,
            "Base score should be between 60 and 80 for fully connected 4-node cycle with ceiling 75"
        );
    }

    #[test]
    fn test_cycle_severity_low() {
        // Create simple 2-node cycle with low ceilings
        // Should be "low"
        let mut graph = ReputationGraph::new();

        let a = Uuid::new_v4();
        let b = Uuid::new_v4();

        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());

        graph.add_edge(GraphEdge {
            from_sovereign: a,
            to_sovereign: b,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 20,
            transitivity_depth: 1,
            status: "active".to_string(),
        });

        graph.add_edge(GraphEdge {
            from_sovereign: b,
            to_sovereign: a,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 20,
            transitivity_depth: 1,
            status: "active".to_string(),
        });

        let cycle = vec![a, b];
        let result = ReputationCycle::analyze_cycle(cycle, &graph);

        assert!(result.is_ok());
        let cycle = result.unwrap();
        assert_eq!(cycle.severity, "low", "Severity should be low");
    }

    #[test]
    fn test_cycle_empty_rejects() {
        let graph = ReputationGraph::new();
        let result = ReputationCycle::analyze_cycle(vec![], &graph);

        assert!(result.is_err(), "Empty cycle should be rejected");
    }

    #[test]
    fn test_cycle_single_node_rejects() {
        let mut graph = ReputationGraph::new();
        let a = Uuid::new_v4();
        graph.add_node(a, "a".to_string());

        let result = ReputationCycle::analyze_cycle(vec![a], &graph);

        assert!(result.is_err(), "Single-node cycle should be rejected");
    }

    #[test]
    fn test_trust_density_calculation() {
        // Create partial cycle: A→B, B→C, C→A, but only A↔B are bidirectional
        let mut graph = ReputationGraph::new();

        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();

        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());

        // A↔B bidirectional, then B→C→A
        for (from, to) in [(a, b), (b, a), (b, c), (c, a)] {
            graph.add_edge(GraphEdge {
                from_sovereign: from,
                to_sovereign: to,
                delegation_grant_id: Uuid::new_v4(),
                ceiling_tier: 100,
                transitivity_depth: 1,
                status: "active".to_string(),
            });
        }

        let cycle = vec![a, b, c];
        let result = ReputationCycle::analyze_cycle(cycle, &graph);

        assert!(result.is_ok());
        let cycle_data = result.unwrap();
        // With 3 nodes and 4 internal edges, avg degree = 4/3 ≈ 1.33
        // Max degree = 2, so trust_density ≈ 0.67
        assert!(
            cycle_data.trust_density > 0.5,
            "Trust density should reflect partial connectivity"
        );
    }

    #[test]
    fn test_weakest_link_tiebreaker_identical_ceilings() {
        // 3-node cycle all with ceiling_tier = 50; tiebreaker is destination UUID
        let mut graph = ReputationGraph::new();

        // Control UUIDs: a < b < c lexicographically
        // Create cycle where if tiebreaking isn't working, we'd get random results
        let a = Uuid::from_bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]);
        let b = Uuid::from_bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02]);
        let c = Uuid::from_bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03]);

        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());

        // A→B, B→C, C→A all ceiling_tier = 50
        for (from, to) in [(a, b), (b, c), (c, a)] {
            graph.add_edge(GraphEdge {
                from_sovereign: from,
                to_sovereign: to,
                delegation_grant_id: Uuid::new_v4(),
                ceiling_tier: 50,
                transitivity_depth: 1,
                status: "active".to_string(),
            });
        }

        let cycle = vec![a, b, c];
        let result = ReputationCycle::analyze_cycle(cycle, &graph);

        assert!(result.is_ok());
        let cycle_data = result.unwrap();
        // All edges have ceiling_tier=50; tiebreaker picks edge to smallest-UUID dest
        // That's C→A (dest=A=smallest). So weakest_link_id should be C.
        assert_eq!(
            cycle_data.weakest_link_id, c,
            "Weakest link should be C (the edge C→A has smallest dest UUID)"
        );
        assert_eq!(cycle_data.weakest_link_ceiling, 50);
    }

    #[test]
    fn test_determinism_10x_repeat() {
        // Run analyze_cycle 10 times on identical input; assert identical output
        let mut graph = ReputationGraph::new();

        let a = Uuid::new_v4();
        let b = Uuid::new_v4();
        let c = Uuid::new_v4();

        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());
        graph.add_node(c, "c".to_string());

        // Mix: A→B (tier 30), B→C (tier 30), C→A (tier 50)
        graph.add_edge(GraphEdge {
            from_sovereign: a,
            to_sovereign: b,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 30,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        graph.add_edge(GraphEdge {
            from_sovereign: b,
            to_sovereign: c,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 30,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        graph.add_edge(GraphEdge {
            from_sovereign: c,
            to_sovereign: a,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 50,
            transitivity_depth: 1,
            status: "active".to_string(),
        });

        let cycle = vec![a, b, c];

        let mut results = Vec::new();
        for _ in 0..10 {
            let result = ReputationCycle::analyze_cycle(cycle.clone(), &graph);
            assert!(result.is_ok());
            results.push(result.unwrap());
        }

        // All 10 results should have identical weakest_link_id and ceiling
        for result in &results[1..] {
            assert_eq!(
                result.weakest_link_id, results[0].weakest_link_id,
                "Weakest link ID should be deterministic"
            );
            assert_eq!(
                result.weakest_link_ceiling, results[0].weakest_link_ceiling,
                "Weakest link ceiling should be deterministic"
            );
            assert_eq!(
                result.severity, results[0].severity,
                "Severity should be deterministic"
            );
        }
    }

    #[test]
    fn test_tiebreaker_resolves_to_lexicographically_smallest_dest() {
        // 2-node cycle A↔B with identical ceilings; verify dest UUID determines winner
        let mut graph = ReputationGraph::new();

        let a = Uuid::from_bytes([0xff; 16]);  // largest UUID
        let b = Uuid::from_bytes([0x00; 16]);  // smallest UUID

        graph.add_node(a, "a".to_string());
        graph.add_node(b, "b".to_string());

        // A→B (dest=B=smallest), B→A (dest=A=largest)
        // With tier tie, A→B should win because B < A
        graph.add_edge(GraphEdge {
            from_sovereign: a,
            to_sovereign: b,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        });
        graph.add_edge(GraphEdge {
            from_sovereign: b,
            to_sovereign: a,
            delegation_grant_id: Uuid::new_v4(),
            ceiling_tier: 100,
            transitivity_depth: 1,
            status: "active".to_string(),
        });

        let cycle = vec![a, b];
        let result = ReputationCycle::analyze_cycle(cycle, &graph);

        assert!(result.is_ok());
        let cycle_data = result.unwrap();
        // Weakest link source is A (because A→B has dest=B which is smaller than dest=A from B→A)
        assert_eq!(
            cycle_data.weakest_link_id, a,
            "Edge to smallest-dest-UUID should win tiebreaker (A→B where dest=B)"
        );
    }

    #[test]
    fn test_5_node_cycle_mixed_tiers_with_tie() {
        // 5-node cycle: 3 nodes with unique tiers, 2 with tied tier
        let mut graph = ReputationGraph::new();

        let nodes: Vec<Uuid> = (0..5)
            .map(|i| {
                Uuid::from_bytes([
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, i as u8,
                ])
            })
            .collect();

        for node in &nodes {
            graph.add_node(*node, node.to_string());
        }

        // Create chain: 0→1(tier 10), 1→2(tier 10), 2→3(tier 50), 3→4(tier 20), 4→0(tier 30)
        // Edges 0→1 and 1→2 both tier 10. Tiebreaker: 1→2 has dest=2, 0→1 has dest=1.
        // So 0→1 (dest=1 < dest=2) should win.
        let edges = vec![
            (0, 1, 10),
            (1, 2, 10),
            (2, 3, 50),
            (3, 4, 20),
            (4, 0, 30),
        ];

        for (from_idx, to_idx, tier) in edges {
            graph.add_edge(GraphEdge {
                from_sovereign: nodes[from_idx],
                to_sovereign: nodes[to_idx],
                delegation_grant_id: Uuid::new_v4(),
                ceiling_tier: tier,
                transitivity_depth: 1,
                status: "active".to_string(),
            });
        }

        let cycle = nodes.clone();
        let result = ReputationCycle::analyze_cycle(cycle, &graph);

        assert!(result.is_ok());
        let cycle_data = result.unwrap();
        assert_eq!(
            cycle_data.weakest_link_ceiling, 10,
            "Weakest tier is 10"
        );
        // Two edges with tier 10: 0→1 (dest=1) and 1→2 (dest=2)
        // 0→1 should win (dest=1 < dest=2)
        assert_eq!(
            cycle_data.weakest_link_id, nodes[0],
            "Edge 0→1 should win tiebreaker (dest=1 < dest=2)"
        );
    }
}
