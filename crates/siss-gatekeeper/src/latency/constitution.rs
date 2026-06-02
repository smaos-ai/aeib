/// Latency tier classification for SLO enforcement.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LatencyTier {
    /// Tier 0: Immutable routing (20 nanoseconds budget)
    Tier0,
    /// Tier 1: Elastic policy (10 milliseconds budget)
    Tier1,
    /// Tier 2: Async research (unlimited budget)
    Tier2,
}

/// Service Level Objective for a specific latency tier.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LatencySLO {
    pub tier: LatencyTier,
    pub budget_nanos: u64,
}

/// Verdict returned by latency constitution checks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConstitutionVerdict {
    WithinBudget,
    SLOViolation {
        tier: LatencyTier,
        budget_nanos: u64,
        elapsed_nanos: u64,
    },
}

/// Latency Constitution: Three-tier SLO enforcement.
#[derive(Debug, Clone)]
pub struct LatencyConstitution {
    slos: [LatencySLO; 3],
}

impl LatencyConstitution {
    /// Create a default constitution with three tiers:
    /// - Tier0: 20 nanoseconds (immutable routing)
    /// - Tier1: 10 milliseconds (elastic policy)
    /// - Tier2: u64::MAX (async research, no limit)
    pub const fn default() -> Self {
        Self {
            slos: [
                LatencySLO {
                    tier: LatencyTier::Tier0,
                    budget_nanos: 20,
                },
                LatencySLO {
                    tier: LatencyTier::Tier1,
                    budget_nanos: 10_000_000, // 10 milliseconds
                },
                LatencySLO {
                    tier: LatencyTier::Tier2,
                    budget_nanos: u64::MAX,
                },
            ],
        }
    }

    /// Check if an elapsed time violates the SLO for the given tier.
    pub fn check(&self, tier: LatencyTier, elapsed_nanos: u64) -> ConstitutionVerdict {
        let slo = self
            .slos
            .iter()
            .find(|slo| slo.tier == tier)
            .expect("tier must exist in slos array");

        if elapsed_nanos <= slo.budget_nanos {
            ConstitutionVerdict::WithinBudget
        } else {
            ConstitutionVerdict::SLOViolation {
                tier,
                budget_nanos: slo.budget_nanos,
                elapsed_nanos,
            }
        }
    }

    /// Classify an operation string to its latency tier.
    /// - "authorize" → Tier1 (elastic policy)
    /// - Other operations → Tier2 (async research, no limit)
    pub fn classify_operation(op: &str) -> LatencyTier {
        match op {
            "authorize" => LatencyTier::Tier1,
            _ => LatencyTier::Tier2,
        }
    }
}

#[cfg(test)]
#[path = "tests.rs"]
mod tests;
