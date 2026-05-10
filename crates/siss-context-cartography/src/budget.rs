use crate::types::MemoryEntry;

/// Trim a list of memory entries to fit within the given token budget.
/// Removes entries from the end of the list (lowest priority) first.
pub fn trim_to_budget(
    entries: Vec<MemoryEntry>,
    available_tokens: i64,
    tokens_per_char: f64,
) -> (Vec<MemoryEntry>, i64) {
    let mut kept = Vec::new();
    let mut total = 0i64;

    for entry in entries {
        let tokens = entry.estimate_tokens(tokens_per_char);
        if total + tokens <= available_tokens {
            total += tokens;
            kept.push(entry);
        } else {
            break;
        }
    }

    (kept, total)
}

/// Apply token budget across all three tiers in priority order.
pub fn apply_budget(
    procedural: Vec<MemoryEntry>,
    semantic: Vec<MemoryEntry>,
    episodic: Vec<MemoryEntry>,
    token_budget: i64,
    tokens_per_char: f64,
) -> (Vec<MemoryEntry>, Vec<MemoryEntry>, Vec<MemoryEntry>, i64) {
    let mut remaining = token_budget;

    let (proc_trimmed, proc_tokens) = trim_to_budget(procedural, remaining, tokens_per_char);
    remaining -= proc_tokens;

    let (sem_trimmed, sem_tokens) = trim_to_budget(semantic, remaining, tokens_per_char);
    remaining -= sem_tokens;

    let (epi_trimmed, epi_tokens) = trim_to_budget(episodic, remaining, tokens_per_char);

    let total = proc_tokens + sem_tokens + epi_tokens;
    (proc_trimmed, sem_trimmed, epi_trimmed, total)
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::memory::ConsolidationTier;
    use uuid::Uuid;

    fn make_entry(content: &str, tier: ConsolidationTier) -> MemoryEntry {
        MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: content.into(),
            confidence_score: 0.9,
            tier,
        }
    }

    #[test]
    fn test_trim_all_fit() {
        let entries = vec![
            make_entry("hello", ConsolidationTier::Semantic),
            make_entry("world", ConsolidationTier::Semantic),
        ];
        let (kept, total) = trim_to_budget(entries, 100, 0.25);
        assert_eq!(kept.len(), 2);
        assert_eq!(total, 4);
    }

    #[test]
    fn test_trim_partial_fit() {
        let entries = vec![
            make_entry("aaaa", ConsolidationTier::Semantic),
            make_entry("bbbb", ConsolidationTier::Semantic),
            make_entry("cccc", ConsolidationTier::Semantic),
        ];
        let (kept, total) = trim_to_budget(entries, 2, 0.25);
        assert_eq!(kept.len(), 2);
        assert_eq!(total, 2);
    }

    #[test]
    fn test_trim_none_fit() {
        let entries = vec![make_entry(
            "a very long content string that exceeds the budget",
            ConsolidationTier::Semantic,
        )];
        let (kept, total) = trim_to_budget(entries, 1, 0.25);
        assert_eq!(kept.len(), 0);
        assert_eq!(total, 0);
    }

    #[test]
    fn test_apply_budget_all_tiers() {
        let proc = vec![make_entry("proc1", ConsolidationTier::Procedural)];
        let sem = vec![make_entry("sem01", ConsolidationTier::Semantic)];
        let epi = vec![make_entry("epi01", ConsolidationTier::Episodic)];

        let (p, s, e, total) = apply_budget(proc, sem, epi, 100, 0.25);
        assert_eq!(p.len(), 1);
        assert_eq!(s.len(), 1);
        assert_eq!(e.len(), 1);
        assert_eq!(total, 6);
    }

    #[test]
    fn test_apply_budget_episodic_trimmed_first() {
        let proc = vec![make_entry("proc", ConsolidationTier::Procedural)];
        let sem = vec![make_entry("sema", ConsolidationTier::Semantic)];
        let epi = vec![make_entry("epis", ConsolidationTier::Episodic)];

        let (p, s, e, total) = apply_budget(proc, sem, epi, 2, 0.25);
        assert_eq!(p.len(), 1);
        assert_eq!(s.len(), 1);
        assert_eq!(e.len(), 0);
        assert_eq!(total, 2);
    }

    #[test]
    fn test_apply_budget_semantic_and_episodic_trimmed() {
        let proc = vec![make_entry(
            "procedural workflow step one",
            ConsolidationTier::Procedural,
        )];
        let sem = vec![make_entry("sem", ConsolidationTier::Semantic)];
        let epi = vec![make_entry("epi", ConsolidationTier::Episodic)];

        let (p, s, e, total) = apply_budget(proc, sem, epi, 7, 0.25);
        assert_eq!(p.len(), 1);
        assert_eq!(s.len(), 0);
        assert_eq!(e.len(), 0);
        assert_eq!(total, 7);
    }

    #[test]
    fn test_empty_memories() {
        let (p, s, e, total) = apply_budget(vec![], vec![], vec![], 100, 0.25);
        assert_eq!(p.len(), 0);
        assert_eq!(s.len(), 0);
        assert_eq!(e.len(), 0);
        assert_eq!(total, 0);
    }
}
