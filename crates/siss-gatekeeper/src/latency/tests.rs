#[cfg(test)]
mod tests {
    use crate::latency::{LatencyConstitution, LatencyTier, ConstitutionVerdict};

    #[test]
    fn test_tier0_passes_within_20ns() {
        let constitution = LatencyConstitution::default();
        let result = constitution.check(LatencyTier::Tier0, 20);
        assert_eq!(result, ConstitutionVerdict::WithinBudget);
    }

    #[test]
    fn test_tier0_fails_at_21ns() {
        let constitution = LatencyConstitution::default();
        let result = constitution.check(LatencyTier::Tier0, 21);
        match result {
            ConstitutionVerdict::SLOViolation {
                tier,
                budget_nanos,
                elapsed_nanos,
            } => {
                assert_eq!(tier, LatencyTier::Tier0);
                assert_eq!(budget_nanos, 20);
                assert_eq!(elapsed_nanos, 21);
            }
            _ => panic!("expected SLOViolation"),
        }
    }

    #[test]
    fn test_tier1_passes_within_10ms() {
        let constitution = LatencyConstitution::default();
        let result = constitution.check(LatencyTier::Tier1, 10_000_000);
        assert_eq!(result, ConstitutionVerdict::WithinBudget);
    }

    #[test]
    fn test_tier1_fails_at_11ms() {
        let constitution = LatencyConstitution::default();
        let result = constitution.check(LatencyTier::Tier1, 10_000_001);
        match result {
            ConstitutionVerdict::SLOViolation {
                tier,
                budget_nanos,
                elapsed_nanos,
            } => {
                assert_eq!(tier, LatencyTier::Tier1);
                assert_eq!(budget_nanos, 10_000_000);
                assert_eq!(elapsed_nanos, 10_000_001);
            }
            _ => panic!("expected SLOViolation"),
        }
    }

    #[test]
    fn test_tier2_never_fails() {
        let constitution = LatencyConstitution::default();
        let result = constitution.check(LatencyTier::Tier2, u64::MAX);
        assert_eq!(result, ConstitutionVerdict::WithinBudget);
    }

    #[test]
    fn test_classify_authorization_is_tier1() {
        let tier = LatencyConstitution::classify_operation("authorize");
        assert_eq!(tier, LatencyTier::Tier1);
    }
}
