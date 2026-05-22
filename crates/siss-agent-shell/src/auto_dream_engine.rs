/// Phase 60: Auto Dream Engine — Nightly Consolidation Cycle

use crate::crdt_sync::CrdtSync;
use crate::memory_decay::{DecayConfig, DecayEngine};
use crate::swarm_knowledge::{KnowledgeAtom, KnowledgeKind};
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct DreamEntry {
    pub atom_id: Uuid,
    pub symbol_path: String,
    pub confidence: f64,
    pub kind: KnowledgeKind,
    pub discovered_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct DreamIndex {
    pub entries: Vec<DreamEntry>,
    pub built_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct DreamReport {
    pub pruned_count: usize,
    pub merged_count: usize,
    pub survived_count: usize,
    pub index_entry_count: usize,
}

pub struct AutoDreamEngine;

impl AutoDreamEngine {
    /// RULE 1: Delegate to DecayEngine::run_pass to find gc-eligible atom_ids
    /// RULE 2: Partition: atoms with id in gc_eligible → pruned; others → survivors
    /// RULE 3: Group survivors by symbol_path; merge pairs with same path via CrdtSync::merge
    ///   LWW winner survives; ProvenanceFork captured when content differs
    /// RULE 4: Return (survivors_after_merge, DreamReport)
    pub fn consolidate(
        atoms: &[KnowledgeAtom],
        config: &DecayConfig,
        now: DateTime<Utc>,
    ) -> (Vec<KnowledgeAtom>, DreamReport) {
        let (_survived_initial, gc_eligible_ids) = DecayEngine::run_pass(atoms, config, now);
        let gc_set: std::collections::HashSet<Uuid> = gc_eligible_ids.into_iter().collect();

        let survivors: Vec<KnowledgeAtom> = atoms
            .iter()
            .filter(|atom| !gc_set.contains(&atom.atom_id))
            .cloned()
            .collect();

        let pruned_count = atoms.len().saturating_sub(survivors.len());

        let mut grouped: HashMap<String, Vec<(KnowledgeAtom, Uuid)>> = HashMap::new();
        for atom in survivors.iter() {
            grouped
                .entry(atom.symbol_path.clone())
                .or_insert_with(Vec::new)
                .push((atom.clone(), Uuid::nil()));
        }

        let mut merged_atoms = Vec::new();
        let mut merged_count = 0;

        for (_symbol_path, group) in grouped {
            if group.is_empty() {
                continue;
            }

            if group.len() == 1 {
                merged_atoms.push(group[0].0.clone());
            } else {
                let (final_atom, _forks) = CrdtSync::merge_batch(group.clone());
                merged_atoms.push(final_atom);
                merged_count += group.len() - 1;
            }
        }

        let survived_count = merged_atoms.len();

        let report = DreamReport {
            pruned_count,
            merged_count,
            survived_count,
            index_entry_count: 0,
        };

        (merged_atoms, report)
    }

    /// RULE 5: Sort by effective_confidence(now) DESC, take first 200
    /// RULE 6: DreamIndex.entries.len() is always <= 200 (structural invariant)
    pub fn rebuild_index(atoms: &[KnowledgeAtom], now: DateTime<Utc>) -> DreamIndex {
        let mut entries: Vec<DreamEntry> = atoms
            .iter()
            .map(|atom| DreamEntry {
                atom_id: atom.atom_id,
                symbol_path: atom.symbol_path.clone(),
                confidence: atom.effective_confidence(now),
                kind: atom.kind.clone(),
                discovered_at: atom.discovered_at,
            })
            .collect();

        entries.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap_or(std::cmp::Ordering::Equal));
        entries.truncate(200);

        DreamIndex {
            entries,
            built_at: now,
        }
    }
}