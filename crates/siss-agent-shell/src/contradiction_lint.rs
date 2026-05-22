/// Phase 60: Contradiction Lint — Automated Graph Linter

use crate::crdt_sync::{CrdtSync, ProvenanceFork};
use crate::swarm_knowledge::KnowledgeAtom;
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq)]
pub enum LintResult {
    Clean,
    Conflict { fork: ProvenanceFork },
}

#[derive(Debug, Clone)]
pub struct LintReport {
    pub total_atoms: usize,
    pub conflict_count: usize,
    pub forks: Vec<ProvenanceFork>,
}

pub struct ContradictionLint;

impl ContradictionLint {
    /// RULE 1: Compare two atoms for the same symbol_path from different factories.
    ///   Same content → LintResult::Clean
    ///   Different content → LintResult::Conflict { fork: ProvenanceFork { resolved: false } }
    ///   Delegates content comparison + fork creation to CrdtSync::merge
    pub fn lint_pair(
        atom_a: &KnowledgeAtom,
        factory_a: Uuid,
        atom_b: &KnowledgeAtom,
        factory_b: Uuid,
    ) -> LintResult {
        let merge_result = CrdtSync::merge(atom_a.clone(), factory_a, atom_b.clone(), factory_b);

        if let Some(fork) = merge_result.fork {
            LintResult::Conflict { fork }
        } else {
            LintResult::Clean
        }
    }

    /// RULE 2: Group input atoms by symbol_path; for each group with ≥2 atoms,
    ///   run lint_pair on consecutive pairs.
    /// RULE 3: Each conflict → ProvenanceFork { resolved: false } appended to forks.
    /// RULE 4: LintReport.conflict_count == LintReport.forks.len() always.
    pub fn lint_batch(atoms: &[(KnowledgeAtom, Uuid)]) -> LintReport {
        let mut grouped: HashMap<String, Vec<(KnowledgeAtom, Uuid)>> = HashMap::new();

        for (atom, factory_id) in atoms {
            grouped
                .entry(atom.symbol_path.clone())
                .or_insert_with(Vec::new)
                .push((atom.clone(), *factory_id));
        }

        let mut forks = Vec::new();

        for (_symbol_path, group) in grouped {
            if group.len() < 2 {
                continue;
            }

            for i in 0..group.len() - 1 {
                let result = Self::lint_pair(&group[i].0, group[i].1, &group[i + 1].0, group[i + 1].1);
                if let LintResult::Conflict { fork } = result {
                    forks.push(fork);
                }
            }
        }

        let conflict_count = forks.len();

        LintReport {
            total_atoms: atoms.len(),
            conflict_count,
            forks,
        }
    }
}
