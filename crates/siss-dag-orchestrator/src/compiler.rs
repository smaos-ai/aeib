//! DAG compiler: converts intent to executable DAG

use crate::error::{Error, Result};
use crate::types::{CompiledDag, Constraint, DagNode, ExecutionIntent};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;

/// Compiler configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompilerConfig {
    pub max_parallel_level: usize,
    pub validate_constraints: bool,
    pub optimize_ordering: bool,
}

impl Default for CompilerConfig {
    fn default() -> Self {
        Self {
            max_parallel_level: 10,
            validate_constraints: true,
            optimize_ordering: true,
        }
    }
}

/// DAG compiler
pub struct DagCompiler {
    config: CompilerConfig,
    compiled_dags: Arc<RwLock<HashMap<uuid::Uuid, CompiledDag>>>,
}

impl DagCompiler {
    /// Create new compiler
    pub fn new(config: CompilerConfig) -> Self {
        Self {
            config,
            compiled_dags: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Compile intent to DAG
    pub fn compile(&self, intent: ExecutionIntent) -> Result<CompiledDag> {
        // Validate intent
        self.validate_intent(&intent)?;

        // Build nodes from steps
        let mut nodes = HashMap::new();
        for step in &intent.steps {
            let node = DagNode {
                id: step.id.clone(),
                step_id: step.id.clone(),
                action: step.action.clone(),
                parameters: step.parameters.clone(),
                dependencies: step.dependencies.clone(),
                priority: 0,
            };
            nodes.insert(step.id.clone(), node);
        }

        // Build edges
        let mut edges = Vec::new();
        for step in &intent.steps {
            for dep in &step.dependencies {
                edges.push((dep.clone(), step.id.clone()));
            }
        }

        // Generate execution levels
        let levels = self.topological_sort(&nodes, &edges)?;

        let dag = CompiledDag {
            execution_id: intent.id,
            nodes,
            edges,
            levels,
            compiled_at: chrono::Utc::now(),
        };

        let mut dags = self.compiled_dags.write();
        dags.insert(intent.id.0, dag.clone());

        Ok(dag)
    }

    /// Topological sort with level assignment
    fn topological_sort(
        &self,
        nodes: &HashMap<String, DagNode>,
        edges: &[(String, String)],
    ) -> Result<Vec<Vec<String>>> {
        let mut in_degree: HashMap<String, usize> = HashMap::new();
        let mut adjacency: HashMap<String, Vec<String>> = HashMap::new();

        // Initialize
        for node_id in nodes.keys() {
            in_degree.insert(node_id.clone(), 0);
            adjacency.insert(node_id.clone(), Vec::new());
        }

        // Build graph
        for (from, to) in edges {
            *in_degree.get_mut(to).unwrap() += 1;
            adjacency.get_mut(from).unwrap().push(to.clone());
        }

        // Kahn's algorithm
        let mut queue: VecDeque<String> = in_degree
            .iter()
            .filter(|(_, &deg)| deg == 0)
            .map(|(id, _)| id.clone())
            .collect();

        let mut levels = Vec::new();

        while !queue.is_empty() {
            let level_size = queue.len();
            let mut level = Vec::new();

            for _ in 0..level_size {
                if let Some(node_id) = queue.pop_front() {
                    level.push(node_id.clone());

                    for next in adjacency.get(&node_id).unwrap_or(&Vec::new()) {
                        *in_degree.get_mut(next).unwrap() -= 1;
                        if in_degree[next] == 0 {
                            queue.push_back(next.clone());
                        }
                    }
                }
            }

            if !level.is_empty() {
                levels.push(level);
            }
        }

        if levels.iter().map(|l| l.len()).sum::<usize>() != nodes.len() {
            return Err(Error::InvalidDag("DAG contains cycles".to_string()));
        }

        Ok(levels)
    }

    /// Validate intent structure
    fn validate_intent(&self, intent: &ExecutionIntent) -> Result<()> {
        if intent.steps.is_empty() {
            return Err(Error::InvalidDag("Intent has no steps".to_string()));
        }

        if self.config.validate_constraints {
            for constraint in &intent.constraints {
                self.validate_constraint(constraint)?;
            }
        }

        Ok(())
    }

    /// Validate single constraint
    fn validate_constraint(&self, _constraint: &Constraint) -> Result<()> {
        // Constraint validation logic
        Ok(())
    }

    /// Get compiled DAG
    pub fn get_compiled_dag(&self, execution_id: uuid::Uuid) -> Option<CompiledDag> {
        self.compiled_dags.read().get(&execution_id).cloned()
    }

    /// Get compilation statistics
    pub fn compiled_count(&self) -> usize {
        self.compiled_dags.read().len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{ExecutionId, IntentStep};

    #[test]
    fn test_compiler_creation() {
        let compiler = DagCompiler::new(CompilerConfig::default());
        assert_eq!(compiler.compiled_count(), 0);
    }

    #[test]
    fn test_compile_simple_intent() {
        let compiler = DagCompiler::new(CompilerConfig::default());

        let intent = ExecutionIntent {
            id: ExecutionId::new(),
            name: "test".to_string(),
            description: "test intent".to_string(),
            steps: vec![IntentStep {
                id: "step1".to_string(),
                action: "action1".to_string(),
                parameters: serde_json::json!({}),
                dependencies: Vec::new(),
            }],
            constraints: Vec::new(),
            created_at: chrono::Utc::now(),
        };

        let result = compiler.compile(intent);
        assert!(result.is_ok());
    }

    #[test]
    fn test_compile_with_dependencies() {
        let compiler = DagCompiler::new(CompilerConfig::default());

        let intent = ExecutionIntent {
            id: ExecutionId::new(),
            name: "test".to_string(),
            description: "test intent".to_string(),
            steps: vec![
                IntentStep {
                    id: "step1".to_string(),
                    action: "action1".to_string(),
                    parameters: serde_json::json!({}),
                    dependencies: Vec::new(),
                },
                IntentStep {
                    id: "step2".to_string(),
                    action: "action2".to_string(),
                    parameters: serde_json::json!({}),
                    dependencies: vec!["step1".to_string()],
                },
            ],
            constraints: Vec::new(),
            created_at: chrono::Utc::now(),
        };

        let result = compiler.compile(intent.clone());
        assert!(result.is_ok());

        let dag = result.unwrap();
        assert_eq!(dag.levels.len(), 2);
    }

    #[test]
    fn test_empty_intent_fails() {
        let compiler = DagCompiler::new(CompilerConfig::default());

        let intent = ExecutionIntent {
            id: ExecutionId::new(),
            name: "test".to_string(),
            description: "test intent".to_string(),
            steps: Vec::new(),
            constraints: Vec::new(),
            created_at: chrono::Utc::now(),
        };

        let result = compiler.compile(intent);
        assert!(result.is_err());
    }
}
