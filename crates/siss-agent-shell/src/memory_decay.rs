/// Phase 52: Memory Decay Engine — Atrophy-based garbage collection
/// Applies geometric decay to unreinforced knowledge atoms.
use crate::swarm_knowledge::KnowledgeAtom;
use chrono::DateTime;
use chrono::Utc;
use uuid::Uuid;

pub struct DecayConfig {
    pub gc_threshold: f64,
    pub stability_hours: f64,
}

impl Default for DecayConfig {
    fn default() -> Self {
        DecayConfig {
            gc_threshold: 0.10,
            stability_hours: 48.0,
        }
    }
}

pub struct DecayEngine;

impl DecayEngine {
    /// Run one decay pass over a slice of atoms.
    /// RULE 1: atoms with effective_confidence(now) < gc_threshold → added to gc_eligible
    /// RULE 2: atoms above threshold → counted in survived
    /// RULE 3: input slice is NOT mutated
    /// Returns (survived: usize, gc_eligible: Vec<Uuid>)
    pub fn run_pass(
        atoms: &[KnowledgeAtom],
        config: &DecayConfig,
        now: DateTime<Utc>,
    ) -> (usize, Vec<Uuid>) {
        let mut survived = 0;
        let mut gc_eligible = Vec::new();

        for atom in atoms {
            if atom.is_gc_eligible(now, config.gc_threshold) {
                gc_eligible.push(atom.atom_id);
            } else {
                survived += 1;
            }
        }

        (survived, gc_eligible)
    }
}
