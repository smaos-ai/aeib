use chrono::{DateTime, Utc};
use serde::{Serialize, Deserialize};
use std::collections::{HashMap, HashSet};
use uuid::Uuid;
use sha2::{Sha256, Digest};

/// Phase 82: Sovereign Knowledge Graph
/// GitNexus-integrated knowledge graph tracking code symbols, relationships, and impact chains.
/// Enables deterministic codebase-aware decision making for the CapsuleCommitActor.

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Symbol {
    pub id: Uuid,
    pub name: String,
    pub file_path: String,
    pub symbol_type: SymbolType,
    pub hash: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum SymbolType {
    Function,
    Struct,
    Enum,
    Trait,
    Module,
    Constant,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Edge {
    pub id: Uuid,
    pub source: Uuid,
    pub target: Uuid,
    pub edge_type: EdgeType,
    pub confidence: f64,
    pub created_at: DateTime<Utc>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum EdgeType {
    Calls,
    CallsAsync,
    References,
    Implements,
    UsedBy,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Cluster {
    pub id: Uuid,
    pub name: String,
    pub symbols: Vec<Uuid>,
    pub description: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ImpactChain {
    pub id: Uuid,
    pub changed_symbol: Uuid,
    pub affected_symbols: Vec<(Uuid, DepthLevel)>,
    pub risk_level: RiskLevel,
    pub confidence: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum DepthLevel {
    Direct,      // 1 hop
    Indirect,    // 2 hops
    Transitive,  // 3+ hops
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

pub struct SovereignKG {
    symbols: HashMap<Uuid, Symbol>,
    edges: HashMap<Uuid, Edge>,
    clusters: HashMap<Uuid, Cluster>,
    impact_chains: HashMap<Uuid, ImpactChain>,
    symbol_by_name: HashMap<String, Uuid>,
}

impl SovereignKG {
    pub fn new() -> Self {
        Self {
            symbols: HashMap::new(),
            edges: HashMap::new(),
            clusters: HashMap::new(),
            impact_chains: HashMap::new(),
            symbol_by_name: HashMap::new(),
        }
    }

    pub fn add_symbol(&mut self, name: String, file_path: String, symbol_type: SymbolType) -> Uuid {
        let id = Uuid::new_v4();
        let hash = Self::compute_symbol_hash(&name, &file_path);

        let symbol = Symbol {
            id,
            name: name.clone(),
            file_path,
            symbol_type,
            hash,
            created_at: Utc::now(),
        };

        self.symbol_by_name.insert(name, id);
        self.symbols.insert(id, symbol);
        id
    }

    pub fn add_edge(&mut self, source: Uuid, target: Uuid, edge_type: EdgeType, confidence: f64) -> Result<Uuid, String> {
        if !self.symbols.contains_key(&source) || !self.symbols.contains_key(&target) {
            return Err("Source or target symbol not found".to_string());
        }

        let id = Uuid::new_v4();
        let edge = Edge {
            id,
            source,
            target,
            edge_type,
            confidence,
            created_at: Utc::now(),
        };

        self.edges.insert(id, edge);
        self.recompute_impact_chains(source);
        Ok(id)
    }

    pub fn create_cluster(&mut self, name: String, description: String) -> Uuid {
        let id = Uuid::new_v4();
        self.clusters.insert(
            id,
            Cluster {
                id,
                name,
                symbols: Vec::new(),
                description,
            },
        );
        id
    }

    pub fn add_symbol_to_cluster(&mut self, cluster_id: Uuid, symbol_id: Uuid) -> Result<(), String> {
        if !self.symbols.contains_key(&symbol_id) {
            return Err("Symbol not found".to_string());
        }

        self.clusters
            .get_mut(&cluster_id)
            .ok_or("Cluster not found".to_string())?
            .symbols
            .push(symbol_id);

        Ok(())
    }

    pub fn query_impact(&self, symbol_id: Uuid) -> Option<ImpactChain> {
        self.impact_chains
            .values()
            .filter(|ic| ic.changed_symbol == symbol_id)
            .max_by_key(|ic| ic.affected_symbols.len())
            .cloned()
    }

    pub fn detect_changes(&self, affected_symbols: &[String]) -> Vec<ImpactChain> {
        affected_symbols
            .iter()
            .filter_map(|name| {
                self.symbol_by_name
                    .get(name)
                    .and_then(|id| self.query_impact(*id))
            })
            .collect()
    }

    pub fn cluster_intersection(&self, symbols_a: &[String], symbols_b: &[String]) -> bool {
        let clusters_a: HashSet<Uuid> = symbols_a
            .iter()
            .filter_map(|name| {
                self.symbol_by_name.get(name).and_then(|id| {
                    self.clusters
                        .values()
                        .find(|c| c.symbols.contains(id))
                        .map(|c| c.id)
                })
            })
            .collect();

        let clusters_b: HashSet<Uuid> = symbols_b
            .iter()
            .filter_map(|name| {
                self.symbol_by_name.get(name).and_then(|id| {
                    self.clusters
                        .values()
                        .find(|c| c.symbols.contains(id))
                        .map(|c| c.id)
                })
            })
            .collect();

        !clusters_a.intersection(&clusters_b).next().is_none()
    }

    fn recompute_impact_chains(&mut self, symbol_id: Uuid) {
        let affected = self.traverse_impact(symbol_id, 0);
        let risk = Self::assess_risk(&affected);
        let confidence = self.compute_chain_confidence(&affected);

        let chain = ImpactChain {
            id: Uuid::new_v4(),
            changed_symbol: symbol_id,
            affected_symbols: affected,
            risk_level: risk,
            confidence,
        };

        self.impact_chains.insert(chain.id, chain);
    }

    fn traverse_impact(&self, symbol_id: Uuid, depth: usize) -> Vec<(Uuid, DepthLevel)> {
        let mut affected = Vec::new();
        let max_depth = 3;

        if depth > max_depth {
            return affected;
        }

        let depth_level = match depth {
            0 => DepthLevel::Direct,
            1 => DepthLevel::Indirect,
            _ => DepthLevel::Transitive,
        };

        for edge in self.edges.values() {
            if edge.source == symbol_id && edge.edge_type == EdgeType::Calls {
                affected.push((edge.target, depth_level.clone()));
                let downstream = self.traverse_impact(edge.target, depth + 1);
                affected.extend(downstream);
            }
        }

        affected
    }

    fn assess_risk(affected: &[(Uuid, DepthLevel)]) -> RiskLevel {
        let direct_count = affected.iter().filter(|(_, d)| d == &DepthLevel::Direct).count();
        let total_count = affected.len();

        match (direct_count, total_count) {
            (0, _) => RiskLevel::Low,
            (1..=2, 0..=5) => RiskLevel::Low,
            (1..=2, 6..=10) => RiskLevel::Medium,
            (3..=5, _) => RiskLevel::Medium,
            (6..=10, _) => RiskLevel::High,
            _ => RiskLevel::Critical,
        }
    }

    fn compute_chain_confidence(&self, affected: &[(Uuid, DepthLevel)]) -> f64 {
        if affected.is_empty() {
            return 1.0;
        }

        let direct_confidence: f64 = affected
            .iter()
            .filter(|(_, d)| d == &DepthLevel::Direct)
            .filter_map(|(id, _)| {
                self.edges
                    .values()
                    .find(|e| e.target == *id)
                    .map(|e| e.confidence)
            })
            .sum::<f64>()
            / affected.len().max(1) as f64;

        (direct_confidence * 0.9).min(1.0)
    }

    fn compute_symbol_hash(name: &str, file_path: &str) -> String {
        let input = format!("{}:{}", name, file_path);
        let mut hasher = Sha256::new();
        hasher.update(input.as_bytes());
        hex::encode(hasher.finalize())
    }

    pub fn symbol_count(&self) -> usize {
        self.symbols.len()
    }

    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    pub fn cluster_count(&self) -> usize {
        self.clusters.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_kg_creates_symbols() {
        let mut kg = SovereignKG::new();
        let id = kg.add_symbol("function_a".to_string(), "lib.rs".to_string(), SymbolType::Function);
        assert_eq!(kg.symbol_count(), 1);
        assert!(kg.symbols.contains_key(&id));
    }

    #[test]
    fn test_kg_adds_edges_between_symbols() {
        let mut kg = SovereignKG::new();
        let a = kg.add_symbol("func_a".to_string(), "lib.rs".to_string(), SymbolType::Function);
        let b = kg.add_symbol("func_b".to_string(), "lib.rs".to_string(), SymbolType::Function);

        let result = kg.add_edge(a, b, EdgeType::Calls, 0.95);
        assert!(result.is_ok());
        assert_eq!(kg.edge_count(), 1);
    }

    #[test]
    fn test_kg_rejects_edge_with_missing_symbol() {
        let mut kg = SovereignKG::new();
        let a = kg.add_symbol("func_a".to_string(), "lib.rs".to_string(), SymbolType::Function);
        let fake_id = Uuid::new_v4();

        let result = kg.add_edge(a, fake_id, EdgeType::Calls, 0.95);
        assert!(result.is_err());
    }

    #[test]
    fn test_kg_organizes_symbols_into_clusters() {
        let mut kg = SovereignKG::new();
        let cluster_id = kg.create_cluster("auth".to_string(), "Authentication module".to_string());
        let sym_id = kg.add_symbol("login".to_string(), "auth.rs".to_string(), SymbolType::Function);

        let result = kg.add_symbol_to_cluster(cluster_id, sym_id);
        assert!(result.is_ok());
        assert_eq!(kg.cluster_count(), 1);
    }

    #[test]
    fn test_kg_detects_cluster_intersection() {
        let mut kg = SovereignKG::new();
        let cluster = kg.create_cluster("auth".to_string(), "Auth module".to_string());

        let sym1 = kg.add_symbol("login".to_string(), "auth.rs".to_string(), SymbolType::Function);
        let sym2 = kg.add_symbol("logout".to_string(), "auth.rs".to_string(), SymbolType::Function);
        let sym3 = kg.add_symbol("other".to_string(), "other.rs".to_string(), SymbolType::Function);

        kg.add_symbol_to_cluster(cluster, sym1).ok();
        kg.add_symbol_to_cluster(cluster, sym2).ok();

        let intersects = kg.cluster_intersection(&["login".to_string()], &["logout".to_string()]);
        assert!(intersects, "Should detect intersection in same cluster");

        let no_intersect = kg.cluster_intersection(&["login".to_string()], &["other".to_string()]);
        assert!(!no_intersect, "Should not intersect across different clusters");
    }

    #[test]
    fn test_kg_computes_impact_chains() {
        let mut kg = SovereignKG::new();
        let a = kg.add_symbol("a".to_string(), "lib.rs".to_string(), SymbolType::Function);
        let b = kg.add_symbol("b".to_string(), "lib.rs".to_string(), SymbolType::Function);
        let c = kg.add_symbol("c".to_string(), "lib.rs".to_string(), SymbolType::Function);

        kg.add_edge(a, b, EdgeType::Calls, 0.95).ok();
        kg.add_edge(b, c, EdgeType::Calls, 0.90).ok();

        let impact = kg.query_impact(a);
        assert!(impact.is_some());
        assert!(impact.unwrap().affected_symbols.len() > 0);
    }

    #[test]
    fn test_kg_risk_level_increases_with_affected_count() {
        let mut kg = SovereignKG::new();
        let root = kg.add_symbol("root".to_string(), "lib.rs".to_string(), SymbolType::Function);

        for i in 0..15 {
            let id = kg.add_symbol(
                format!("func_{}", i),
                "lib.rs".to_string(),
                SymbolType::Function,
            );
            kg.add_edge(root, id, EdgeType::Calls, 0.90).ok();
        }

        let impact = kg.query_impact(root);
        assert!(impact.is_some());
        if let Some(chain) = impact {
            assert_eq!(chain.risk_level, RiskLevel::Critical);
        }
    }

    #[test]
    fn test_kg_detects_changes_across_symbols() {
        let mut kg = SovereignKG::new();
        let login = kg.add_symbol("login".to_string(), "auth.rs".to_string(), SymbolType::Function);
        let logout = kg.add_symbol("logout".to_string(), "auth.rs".to_string(), SymbolType::Function);
        let other = kg.add_symbol("other".to_string(), "lib.rs".to_string(), SymbolType::Function);

        kg.add_edge(login, other, EdgeType::Calls, 0.95).ok();
        kg.add_edge(logout, other, EdgeType::Calls, 0.90).ok();

        let changes = kg.detect_changes(&["login".to_string(), "logout".to_string()]);
        assert_eq!(changes.len(), 2);
    }
}
