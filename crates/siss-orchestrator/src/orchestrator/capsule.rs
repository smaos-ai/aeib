use uuid::Uuid;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::{HashMap, HashSet};

const MAX_CAPSULE_SCOPE: usize = 50;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum CapsuleError {
    ScopeExceeded { actual: usize, max: usize },
    CyclicDependency { symbols: Vec<String> },
    InvalidHash { expected: String, actual: String },
    EmptySymbols,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Capsule {
    pub capsule_id: Uuid,
    pub agent_id: Uuid,
    pub affected_symbols: Vec<String>,
    pub target_files: Vec<String>,
    pub git_diff: String,
    pub cluster_tags: Vec<String>,
    pub created_at: u64,
    pub capsule_hash: String,
    pub dependencies: HashMap<String, Vec<String>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CommitmentCapsule {
    pub capsule_id: Uuid,
    pub agent_id: Uuid,
    pub affected_symbols: Vec<String>,
    pub target_files: Vec<String>,
    pub git_diff: String,
    pub cluster_tags: Vec<String>,
    pub created_at: u64,
    pub capsule_hash: String,
    pub dependencies: HashMap<String, Vec<String>>,
}

impl CommitmentCapsule {
    pub fn new(
        agent_id: Uuid,
        affected_symbols: Vec<String>,
        target_files: Vec<String>,
        git_diff: String,
        cluster_tags: Vec<String>,
        dependencies: HashMap<String, Vec<String>>,
    ) -> Result<Self, CapsuleError> {
        if affected_symbols.is_empty() {
            return Err(CapsuleError::EmptySymbols);
        }

        if affected_symbols.len() > MAX_CAPSULE_SCOPE {
            return Err(CapsuleError::ScopeExceeded {
                actual: affected_symbols.len(),
                max: MAX_CAPSULE_SCOPE,
            });
        }

        Self::validate_acyclic(&dependencies)?;

        let capsule_id = Uuid::new_v4();
        let created_at = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let payload = format!(
            "{:?}{}{}",
            affected_symbols, git_diff, created_at
        );
        let capsule_hash = scope_hash(&payload);

        Ok(CommitmentCapsule {
            capsule_id,
            agent_id,
            affected_symbols,
            target_files,
            git_diff,
            cluster_tags,
            created_at,
            capsule_hash,
            dependencies,
        })
    }

    fn validate_acyclic(
        dependencies: &HashMap<String, Vec<String>>,
    ) -> Result<(), CapsuleError> {
        let mut visited = HashSet::new();
        let mut rec_stack = HashSet::new();

        for symbol in dependencies.keys() {
            if !visited.contains(symbol) {
                Self::dfs_cycle_check(symbol, dependencies, &mut visited, &mut rec_stack)?;
            }
        }

        Ok(())
    }

    fn dfs_cycle_check(
        node: &str,
        dependencies: &HashMap<String, Vec<String>>,
        visited: &mut HashSet<String>,
        rec_stack: &mut HashSet<String>,
    ) -> Result<(), CapsuleError> {
        visited.insert(node.to_string());
        rec_stack.insert(node.to_string());

        if let Some(deps) = dependencies.get(node) {
            for dep in deps {
                if !visited.contains(dep) {
                    Self::dfs_cycle_check(dep, dependencies, visited, rec_stack)?;
                } else if rec_stack.contains(dep) {
                    return Err(CapsuleError::CyclicDependency {
                        symbols: vec![node.to_string(), dep.clone()],
                    });
                }
            }
        }

        rec_stack.remove(node);
        Ok(())
    }

    pub fn verify_hash(&self) -> Result<(), CapsuleError> {
        let payload = format!(
            "{:?}{}{}",
            self.affected_symbols, self.git_diff, self.created_at
        );
        let computed_hash = scope_hash(&payload);

        if computed_hash == self.capsule_hash {
            Ok(())
        } else {
            Err(CapsuleError::InvalidHash {
                expected: self.capsule_hash.clone(),
                actual: computed_hash,
            })
        }
    }

    pub fn to_capsule(&self) -> Result<Capsule, CapsuleError> {
        self.verify_hash()?;
        Ok(Capsule {
            capsule_id: self.capsule_id,
            agent_id: self.agent_id,
            affected_symbols: self.affected_symbols.clone(),
            target_files: self.target_files.clone(),
            git_diff: self.git_diff.clone(),
            cluster_tags: self.cluster_tags.clone(),
            created_at: self.created_at,
            capsule_hash: self.capsule_hash.clone(),
            dependencies: self.dependencies.clone(),
        })
    }
}

pub fn scope_hash(payload: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[macro_export]
macro_rules! invariant_capsule_locality {
    ($capsule:expr) => {
        assert!(
            $capsule.affected_symbols.len() <= 50,
            "Capsule scope exceeded: {} > 50",
            $capsule.affected_symbols.len()
        );
        assert!(
            !$capsule.affected_symbols.is_empty(),
            "Capsule must have at least one affected symbol"
        );
    };
}

#[macro_export]
macro_rules! invariant_acyclic {
    ($dependencies:expr) => {
        {
            let mut visited = std::collections::HashSet::new();
            let mut rec_stack = std::collections::HashSet::new();
            for symbol in $dependencies.keys() {
                if !visited.contains(symbol) {
                    fn check_cycle(
                        node: &str,
                        deps: &std::collections::HashMap<String, Vec<String>>,
                        visited: &mut std::collections::HashSet<String>,
                        rec_stack: &mut std::collections::HashSet<String>,
                    ) -> bool {
                        visited.insert(node.to_string());
                        rec_stack.insert(node.to_string());
                        if let Some(node_deps) = deps.get(node) {
                            for dep in node_deps {
                                if !visited.contains(dep) {
                                    if !check_cycle(dep, deps, visited, rec_stack) {
                                        return false;
                                    }
                                } else if rec_stack.contains(dep) {
                                    return false;
                                }
                            }
                        }
                        rec_stack.remove(node);
                        true
                    }
                    assert!(
                        check_cycle(symbol, $dependencies, &mut visited, &mut rec_stack),
                        "Cyclic dependency detected"
                    );
                }
            }
        }
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capsule_creation_valid() {
        let capsule = CommitmentCapsule::new(
            Uuid::new_v4(),
            vec!["handleLogin".to_string()],
            vec!["auth.rs".to_string()],
            "diff content".to_string(),
            vec!["auth-cluster".to_string()],
            HashMap::new(),
        );
        assert!(capsule.is_ok());
    }

    #[test]
    fn test_capsule_empty_symbols_error() {
        let result = CommitmentCapsule::new(
            Uuid::new_v4(),
            vec![],
            vec![],
            "diff".to_string(),
            vec![],
            HashMap::new(),
        );
        assert!(matches!(result, Err(CapsuleError::EmptySymbols)));
    }

    #[test]
    fn test_capsule_scope_exceeded() {
        let symbols = (0..=50).map(|i| format!("sym_{}", i)).collect();
        let result = CommitmentCapsule::new(
            Uuid::new_v4(),
            symbols,
            vec![],
            "diff".to_string(),
            vec![],
            HashMap::new(),
        );
        assert!(matches!(result, Err(CapsuleError::ScopeExceeded { .. })));
    }

    #[test]
    fn test_scope_hash_deterministic() {
        let hash1 = scope_hash("test_payload");
        let hash2 = scope_hash("test_payload");
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_scope_hash_differs() {
        let hash1 = scope_hash("payload1");
        let hash2 = scope_hash("payload2");
        assert_ne!(hash1, hash2);
    }

    #[test]
    fn test_hash_verification_success() {
        let capsule = CommitmentCapsule::new(
            Uuid::new_v4(),
            vec!["test".to_string()],
            vec![],
            "diff".to_string(),
            vec![],
            HashMap::new(),
        ).unwrap();
        assert!(capsule.verify_hash().is_ok());
    }

    #[test]
    fn test_hash_verification_failure() {
        let mut capsule = CommitmentCapsule::new(
            Uuid::new_v4(),
            vec!["test".to_string()],
            vec![],
            "diff".to_string(),
            vec![],
            HashMap::new(),
        ).unwrap();
        capsule.capsule_hash = "invalid_hash".to_string();
        assert!(capsule.verify_hash().is_err());
    }

    #[test]
    fn test_acyclic_dag_valid() {
        let mut deps = HashMap::new();
        deps.insert("a".to_string(), vec!["b".to_string()]);
        deps.insert("b".to_string(), vec!["c".to_string()]);
        deps.insert("c".to_string(), vec![]);

        let result = CommitmentCapsule::new(
            Uuid::new_v4(),
            vec!["a".to_string()],
            vec![],
            "diff".to_string(),
            vec![],
            deps,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_acyclic_dag_cycle() {
        let mut deps = HashMap::new();
        deps.insert("a".to_string(), vec!["b".to_string()]);
        deps.insert("b".to_string(), vec!["a".to_string()]);

        let result = CommitmentCapsule::new(
            Uuid::new_v4(),
            vec!["a".to_string()],
            vec![],
            "diff".to_string(),
            vec![],
            deps,
        );
        assert!(matches!(result, Err(CapsuleError::CyclicDependency { .. })));
    }

    #[test]
    fn test_invariant_locality_macro() {
        let capsule = CommitmentCapsule::new(
            Uuid::new_v4(),
            vec!["test".to_string()],
            vec![],
            "diff".to_string(),
            vec![],
            HashMap::new(),
        ).unwrap();
        invariant_capsule_locality!(&capsule);
    }
}
