/// Phase 58: CRDT Sync — Provenance-forking knowledge merge

use crate::swarm_knowledge::KnowledgeAtom;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProvenanceFork {
    pub fork_id: Uuid,
    pub base_atom_id: Uuid,
    pub actor_a_hash: String,
    pub actor_b_hash: String,
    pub actor_a_factory_id: Uuid,
    pub actor_b_factory_id: Uuid,
    pub forked_at: chrono::DateTime<chrono::Utc>,
    pub resolved: bool,
}

#[derive(Debug, Clone)]
pub struct CrdtMergeResult {
    pub merged: KnowledgeAtom,
    pub fork: Option<ProvenanceFork>,
}

pub struct CrdtSync;

impl CrdtSync {
    /// Merge two knowledge atoms from different factories.
    /// RULE 1: Same content → no fork
    /// RULE 2: Different content → LWW by discovered_at
    /// RULE 3: Empty content never wins
    /// RULE 4: G-Counter: take max of reinforcement_count
    /// RULE 5: On collision → create ProvenanceFork with resolved=false
    pub fn merge(
        atom_a: KnowledgeAtom,
        factory_a: Uuid,
        atom_b: KnowledgeAtom,
        factory_b: Uuid,
    ) -> CrdtMergeResult {
        let content_same = atom_a.content == atom_b.content;
        let hash_a = &atom_a.provenance_hash;
        let hash_b = &atom_b.provenance_hash;

        // Determine winner via LWW (Last-Write-Wins)
        let (winner, loser, _winner_factory, _loser_factory) = if !content_same {
            // Collision: use timestamp + empty-content guard
            if atom_a.content.is_empty() && !atom_b.content.is_empty() {
                (atom_b.clone(), atom_a.clone(), factory_b, factory_a)
            } else if atom_b.content.is_empty() && !atom_a.content.is_empty() {
                (atom_a.clone(), atom_b.clone(), factory_a, factory_b)
            } else if atom_a.discovered_at > atom_b.discovered_at {
                (atom_a.clone(), atom_b.clone(), factory_a, factory_b)
            } else if atom_b.discovered_at > atom_a.discovered_at {
                (atom_b.clone(), atom_a.clone(), factory_b, factory_a)
            } else {
                // Tie-breaker: factory_a wins
                (atom_a.clone(), atom_b.clone(), factory_a, factory_b)
            }
        } else {
            // No collision: use first atom
            (atom_a.clone(), atom_b.clone(), factory_a, factory_b)
        };

        // Merged atom: winner content, max count
        let mut merged = winner.clone();
        merged.reinforcement_count = merged.reinforcement_count.max(loser.reinforcement_count);

        // Fork detection
        let fork = if content_same {
            None
        } else {
            Some(ProvenanceFork {
                fork_id: Uuid::new_v4(),
                base_atom_id: atom_a.atom_id,
                actor_a_hash: hash_a.clone(),
                actor_b_hash: hash_b.clone(),
                actor_a_factory_id: factory_a,
                actor_b_factory_id: factory_b,
                forked_at: chrono::Utc::now(),
                resolved: false,
            })
        };

        CrdtMergeResult { merged, fork }
    }

    /// Merge a batch of atoms pairwise.
    pub fn merge_batch(
        atoms: Vec<(KnowledgeAtom, Uuid)>,
    ) -> (KnowledgeAtom, Vec<ProvenanceFork>) {
        let mut forks = Vec::new();

        if atoms.is_empty() {
            panic!("merge_batch requires at least one atom");
        }

        let (mut merged, factory) = atoms[0].clone();

        for (atom, factory_id) in atoms.iter().skip(1) {
            let result = Self::merge(merged.clone(), factory, atom.clone(), *factory_id);
            merged = result.merged;
            if let Some(fork) = result.fork {
                forks.push(fork);
            }
        }

        (merged, forks)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_crdt_sync_merge() {
        // Placeholder test
    }
}
