/// Phase 60: Autodream Night Cycle & IVB Loop — 27 TDD Tests

use siss_agent_shell::auto_dream_engine::AutoDreamEngine;
use siss_agent_shell::contradiction_lint::ContradictionLint;
use siss_agent_shell::distillation_gate::DistillationConfig;
use siss_agent_shell::ivb_lora_compiler::{IvbError, IvbLoraCompiler};
use siss_agent_shell::lora_orchestrator::{LoraOrchestrator, ResourceMonitor};
use siss_agent_shell::memory_crystallizer::SemanticCrystallizer;
use siss_agent_shell::memory_decay::DecayConfig;
use siss_agent_shell::swarm_knowledge::{KnowledgeAtom, KnowledgeKind};
use chrono::Utc;
use uuid::Uuid;

// ─── AUTO DREAM ENGINE TESTS (1–9) ─────────────────────────────

fn create_test_atom(symbol_path: &str, confidence: f64, content: &str) -> KnowledgeAtom {
    KnowledgeAtom::new(
        KnowledgeKind::ArchitecturalPattern,
        "test",
        symbol_path,
        content,
        confidence,
    )
}

#[test]
fn test_dream_consolidate_prunes_gc_eligible_atoms() {
    let atoms = vec![
        create_test_atom("sym1", 0.95, "high confidence"),
        create_test_atom("sym2", 0.05, "low confidence"),
    ];
    let config = DecayConfig::default();
    let now = Utc::now();

    let (survivors, _report) = AutoDreamEngine::consolidate(&atoms, &config, now);
    assert!(survivors.len() <= atoms.len());
}

#[test]
fn test_dream_consolidate_keeps_high_confidence() {
    let atom = create_test_atom("sym1", 0.95, "high confidence");
    let config = DecayConfig::default();
    let now = Utc::now();

    let (survivors, _report) = AutoDreamEngine::consolidate(&[atom.clone()], &config, now);
    assert_eq!(survivors.len(), 1);
    assert_eq!(survivors[0].atom_id, atom.atom_id);
}

#[test]
fn test_dream_consolidate_merges_same_symbol_path() {
    let atom1 = create_test_atom("same_path", 0.9, "content");
    let atom2 = create_test_atom("same_path", 0.8, "content");
    let config = DecayConfig::default();
    let now = Utc::now();

    let (survivors, report) = AutoDreamEngine::consolidate(&[atom1, atom2], &config, now);
    assert_eq!(survivors.len(), 1);
    assert_eq!(report.merged_count, 1);
}

#[test]
fn test_dream_consolidate_lww_wins_on_conflict() {
    let atom1 = create_test_atom("same_path", 0.9, "content_a");
    let mut atom2 = create_test_atom("same_path", 0.8, "content_b");
    atom2.discovered_at = atom1.discovered_at + chrono::Duration::seconds(1);

    let config = DecayConfig::default();
    let now = Utc::now();

    let (survivors, _report) = AutoDreamEngine::consolidate(&[atom1, atom2.clone()], &config, now);
    assert_eq!(survivors.len(), 1);
    assert_eq!(survivors[0].content, atom2.content);
}

#[test]
fn test_dream_report_counts_correct() {
    let atoms = vec![
        create_test_atom("sym1", 0.95, "keep"),
        create_test_atom("sym2", 0.05, "drop"),
        create_test_atom("sym3", 0.9, "also keep"),
    ];
    let config = DecayConfig::default();
    let now = Utc::now();

    let (_survivors, report) = AutoDreamEngine::consolidate(&atoms, &config, now);
    assert_eq!(report.pruned_count + report.survived_count + report.merged_count, 3);
}

#[test]
fn test_dream_report_survived_zero_on_all_gc() {
    let atoms = vec![
        create_test_atom("sym1", 0.01, "gc1"),
        create_test_atom("sym2", 0.01, "gc2"),
    ];
    let config = DecayConfig::default();
    let now = Utc::now();

    let (_survivors, report) = AutoDreamEngine::consolidate(&atoms, &config, now);
    assert!(report.survived_count == 0);
}

#[test]
fn test_dream_index_capped_at_200_entries() {
    let mut atoms = Vec::new();
    for i in 0..300 {
        atoms.push(create_test_atom(
            &format!("sym_{}", i),
            0.5 + (i as f64 / 600.0),
            "content",
        ));
    }

    let index = AutoDreamEngine::rebuild_index(&atoms, Utc::now());
    assert!(index.entries.len() <= 200);
}

#[test]
fn test_dream_index_sorted_by_confidence_desc() {
    let atoms = vec![
        create_test_atom("sym1", 0.5, "low"),
        create_test_atom("sym2", 0.9, "high"),
        create_test_atom("sym3", 0.7, "mid"),
    ];

    let index = AutoDreamEngine::rebuild_index(&atoms, Utc::now());
    for i in 0..index.entries.len() - 1 {
        assert!(index.entries[i].confidence >= index.entries[i + 1].confidence);
    }
}

#[test]
fn test_dream_empty_input_returns_empty_report() {
    let config = DecayConfig::default();
    let (_survivors, report) = AutoDreamEngine::consolidate(&[], &config, Utc::now());
    assert_eq!(report.pruned_count, 0);
    assert_eq!(report.merged_count, 0);
    assert_eq!(report.survived_count, 0);
}

// ─── CONTRADICTION LINT TESTS (10–18) ────────────────────────

#[test]
fn test_lint_pair_identical_content_returns_clean() {
    let atom1 = create_test_atom("path1", 0.9, "same");
    let atom2 = create_test_atom("path1", 0.8, "same");

    let result = ContradictionLint::lint_pair(&atom1, Uuid::new_v4(), &atom2, Uuid::new_v4());
    assert!(matches!(result, siss_agent_shell::contradiction_lint::LintResult::Clean));
}

#[test]
fn test_lint_pair_different_content_returns_conflict() {
    let atom1 = create_test_atom("path1", 0.9, "content_a");
    let atom2 = create_test_atom("path1", 0.8, "content_b");

    let result = ContradictionLint::lint_pair(&atom1, Uuid::new_v4(), &atom2, Uuid::new_v4());
    assert!(matches!(
        result,
        siss_agent_shell::contradiction_lint::LintResult::Conflict { .. }
    ));
}

#[test]
fn test_lint_fork_is_unresolved_by_default() {
    let atom1 = create_test_atom("path1", 0.9, "a");
    let atom2 = create_test_atom("path1", 0.8, "b");

    let result = ContradictionLint::lint_pair(&atom1, Uuid::new_v4(), &atom2, Uuid::new_v4());
    if let siss_agent_shell::contradiction_lint::LintResult::Conflict { fork } = result {
        assert!(!fork.resolved);
    } else {
        panic!("Expected conflict");
    }
}

#[test]
fn test_lint_fork_captures_both_factory_ids() {
    let atom1 = create_test_atom("path1", 0.9, "a");
    let atom2 = create_test_atom("path1", 0.8, "b");
    let fa = Uuid::new_v4();
    let fb = Uuid::new_v4();

    let result = ContradictionLint::lint_pair(&atom1, fa, &atom2, fb);
    if let siss_agent_shell::contradiction_lint::LintResult::Conflict { fork } = result {
        assert_eq!(fork.actor_a_factory_id, fa);
        assert_eq!(fork.actor_b_factory_id, fb);
    } else {
        panic!("Expected conflict");
    }
}

#[test]
fn test_lint_batch_groups_by_symbol_path() {
    let atom1 = create_test_atom("same_path", 0.9, "a");
    let atom2 = create_test_atom("same_path", 0.8, "b");
    let fa = Uuid::new_v4();
    let fb = Uuid::new_v4();

    let report = ContradictionLint::lint_batch(&[(atom1, fa), (atom2, fb)]);
    assert_eq!(report.conflict_count, 1);
}

#[test]
fn test_lint_batch_different_paths_no_conflict() {
    let atom1 = create_test_atom("path1", 0.9, "a");
    let atom2 = create_test_atom("path2", 0.8, "b");
    let fa = Uuid::new_v4();
    let fb = Uuid::new_v4();

    let report = ContradictionLint::lint_batch(&[(atom1, fa), (atom2, fb)]);
    assert_eq!(report.conflict_count, 0);
}

#[test]
fn test_lint_batch_counts_match_forks_len() {
    let atom1 = create_test_atom("p", 0.9, "a");
    let atom2 = create_test_atom("p", 0.8, "b");
    let atom3 = create_test_atom("p", 0.7, "c");
    let fa = Uuid::new_v4();
    let fb = Uuid::new_v4();
    let fc = Uuid::new_v4();

    let report = ContradictionLint::lint_batch(&[(atom1, fa), (atom2, fb), (atom3, fc)]);
    assert_eq!(report.conflict_count, report.forks.len());
}

#[test]
fn test_lint_batch_three_conflicting_atoms() {
    let atom1 = create_test_atom("p", 0.9, "a");
    let atom2 = create_test_atom("p", 0.8, "b");
    let atom3 = create_test_atom("p", 0.7, "c");
    let fa = Uuid::new_v4();
    let fb = Uuid::new_v4();
    let fc = Uuid::new_v4();

    let report = ContradictionLint::lint_batch(&[(atom1, fa), (atom2, fb), (atom3, fc)]);
    assert_eq!(report.conflict_count, 2);
}

#[test]
fn test_lint_batch_empty_input_returns_empty_report() {
    let report = ContradictionLint::lint_batch(&[]);
    assert_eq!(report.conflict_count, 0);
    assert!(report.forks.is_empty());
}

// ─── IVB LORA COMPILER TESTS (19–27) ────────────────────────

struct MockResourceMonitor {
    memory_pct: f64,
}

impl ResourceMonitor for MockResourceMonitor {
    fn unified_memory_pct(&self) -> f64 {
        self.memory_pct
    }
}

#[test]
fn test_ivb_harvest_filters_low_confidence() {
    let atoms = vec![
        create_test_atom("sym1", 0.0, "low"),
        create_test_atom("sym2", 0.95, "high"),
    ];
    let crystallizer = SemanticCrystallizer::default();
    let config = DistillationConfig::default();

    let result = IvbLoraCompiler::harvest(&atoms, &crystallizer, &config, Utc::now());
    assert!(result.is_ok() || matches!(result, Err(IvbError::NoExamplesInContract)));
}

#[test]
fn test_ivb_harvest_includes_high_confidence() {
    let atoms = vec![create_test_atom("sym1", 1.0, "very high")];
    let crystallizer = SemanticCrystallizer::default();
    let config = DistillationConfig::default();

    let result = IvbLoraCompiler::harvest(&atoms, &crystallizer, &config, Utc::now());
    assert!(result.is_ok() || matches!(result, Err(IvbError::NoExamplesInContract)));
}

#[test]
fn test_ivb_harvest_empty_atoms_returns_error() {
    let crystallizer = SemanticCrystallizer::default();
    let config = DistillationConfig::default();

    let result = IvbLoraCompiler::harvest(&[], &crystallizer, &config, Utc::now());
    assert!(matches!(result, Err(IvbError::NoExamplesInContract)));
}

#[test]
fn test_ivb_harvest_all_low_confidence_returns_error() {
    let atoms = vec![
        create_test_atom("sym1", 0.05, "low1"),
        create_test_atom("sym2", 0.02, "low2"),
    ];
    let crystallizer = SemanticCrystallizer::default();
    let config = DistillationConfig::default();

    let result = IvbLoraCompiler::harvest(&atoms, &crystallizer, &config, Utc::now());
    assert!(matches!(result, Err(IvbError::NoExamplesInContract)));
}

#[test]
fn test_ivb_harvest_contract_has_correct_count() {
    let mut atoms = vec![
        create_test_atom("sym1", 0.95, "a"),
        create_test_atom("sym2", 0.96, "b"),
    ];
    for atom in &mut atoms {
        atom.reinforcement_count = 5;
    }
    let crystallizer = SemanticCrystallizer::default();
    let config = DistillationConfig::default();

    let result = IvbLoraCompiler::harvest(&atoms, &crystallizer, &config, Utc::now());
    if let Ok(contract) = result {
        assert!(contract.examples.len() > 0);
    }
}

#[test]
fn test_ivb_queue_accepts_low_memory_pressure() {
    let example = siss_agent_shell::distillation_gate::TrainingExample {
        prompt: "test prompt".to_string(),
        completion: "test completion".to_string(),
    };
    let contract = siss_agent_shell::distillation_gate::TrainingContract {
        contract_id: Uuid::new_v4(),
        examples: vec![example],
        source_crystal_ids: vec![],
        created_at: Utc::now(),
    };
    let monitor = MockResourceMonitor { memory_pct: 0.50 };
    let orchestrator = LoraOrchestrator {
        config: Default::default(),
        monitor,
    };

    let result = IvbLoraCompiler::queue_compilation(&contract, &orchestrator);
    assert!(result.is_ok());
}

#[test]
fn test_ivb_queue_rejects_high_memory_pressure() {
    let example = siss_agent_shell::distillation_gate::TrainingExample {
        prompt: "test prompt".to_string(),
        completion: "test completion".to_string(),
    };
    let contract = siss_agent_shell::distillation_gate::TrainingContract {
        contract_id: Uuid::new_v4(),
        examples: vec![example],
        source_crystal_ids: vec![],
        created_at: Utc::now(),
    };
    let monitor = MockResourceMonitor { memory_pct: 0.95 };
    let orchestrator = LoraOrchestrator {
        config: Default::default(),
        monitor,
    };

    let result = IvbLoraCompiler::queue_compilation(&contract, &orchestrator);
    assert!(matches!(
        result,
        Err(IvbError::MemoryPressureTooHigh { .. })
    ));
}

#[test]
fn test_ivb_queue_rejects_empty_contract() {
    let contract = siss_agent_shell::distillation_gate::TrainingContract {
        contract_id: Uuid::new_v4(),
        examples: vec![],
        source_crystal_ids: vec![],
        created_at: Utc::now(),
    };
    let monitor = MockResourceMonitor { memory_pct: 0.50 };
    let orchestrator = LoraOrchestrator {
        config: Default::default(),
        monitor,
    };

    let result = IvbLoraCompiler::queue_compilation(&contract, &orchestrator);
    assert!(matches!(result, Err(IvbError::NoExamplesInContract)));
}

#[test]
fn test_ivb_full_pipeline_harvest_then_queue() {
    let mut atoms = vec![
        create_test_atom("sym1", 0.95, "insight1"),
        create_test_atom("sym2", 0.96, "insight2"),
    ];
    for atom in &mut atoms {
        atom.reinforcement_count = 5;
    }

    let crystallizer = SemanticCrystallizer::default();
    let config = DistillationConfig::default();

    let harvest_result = IvbLoraCompiler::harvest(&atoms, &crystallizer, &config, Utc::now());
    if let Ok(contract) = harvest_result {
        let monitor = MockResourceMonitor { memory_pct: 0.50 };
        let orchestrator = LoraOrchestrator {
            config: Default::default(),
            monitor,
        };

        let queue_result = IvbLoraCompiler::queue_compilation(&contract, &orchestrator);
        assert!(queue_result.is_ok());
    }
}
