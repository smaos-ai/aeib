use crate::refresh::{
    AttestationRefreshResponse, RateLimitConstraints, error_budget_exhausted,
    error_concurrent_limit_exceeded, error_rate_limit_exceeded,
};

/// Phase 7: ConstraintResolver — Active Membrane for Budget & Rate Limit Enforcement
///
/// Pure, stateless struct that composes token budget and rate limit constraints.
/// Returns deterministic error responses from Task 25 error builders (fail-closed).
///
/// This is the core policy enforcement layer bridging repository state (budget from DB)
/// to gatekeeper validation (cost calculations) to handler decisions.
#[derive(Debug, Clone)]
pub struct ConstraintResolver {
    /// Token budget state from sessions table (Task 24 schema)
    pub token_budget_initial: u64,
    pub token_budget_remaining: u64,
    pub token_budget_consumed: u64,

    /// Parsed rate limit constraints from sessions.rate_limits JSONB
    pub rate_limits: RateLimitConstraints,

    /// Current active child session count (for concurrent_sessions enforcement)
    pub current_child_sessions: u32,
}

impl ConstraintResolver {
    /// Create a new ConstraintResolver with loaded state
    pub fn new(
        token_budget_initial: u64,
        token_budget_remaining: u64,
        token_budget_consumed: u64,
        rate_limits: RateLimitConstraints,
        current_child_sessions: u32,
    ) -> Self {
        Self {
            token_budget_initial,
            token_budget_remaining,
            token_budget_consumed,
            rate_limits,
            current_child_sessions,
        }
    }

    /// Enforce token budget constraint
    ///
    /// Verifies that the requested cost does not exceed remaining budget.
    /// Edge case: exact balance match (remaining == requested) passes successfully.
    ///
    /// Returns:
    /// - `Ok(())` if `requested_cost <= token_budget_remaining`
    /// - `Err` with reason "budget_exhausted" if `requested_cost > token_budget_remaining`
    pub fn enforce_budget(&self, requested_cost: u64) -> Result<(), AttestationRefreshResponse> {
        if requested_cost > self.token_budget_remaining {
            return Err(error_budget_exhausted(
                self.token_budget_initial,
                self.token_budget_remaining,
            ));
        }
        Ok(())
    }

    /// Validate rate limit constraints (burst protection)
    ///
    /// Enforces the burst size ceiling if configured.
    /// If no rate limits are configured, passes automatically.
    ///
    /// Returns:
    /// - `Ok(())` if no burst_size configured OR `requested_cost <= burst_size`
    /// - `Err` with reason "rate_limit_exceeded" if `requested_cost > burst_size`
    pub fn validate_rate_limit(&self, requested_cost: u64) -> Result<(), AttestationRefreshResponse> {
        // If no rate limit constraints configured, pass through
        if self.rate_limits.burst_size.is_none() && self.rate_limits.rate_limit.is_none() {
            return Ok(());
        }

        // Check burst size if configured
        if let Some(burst_size) = self.rate_limits.burst_size {
            if requested_cost > burst_size {
                let limit_str = self.rate_limits.rate_limit.as_deref().unwrap_or("configured limit");
                return Err(error_rate_limit_exceeded(limit_str));
            }
        }

        Ok(())
    }

    /// Enforce concurrent session ceiling
    ///
    /// Verifies that the current child session count does not exceed the ceiling.
    /// Uses >= comparison: if current equals max, we're at limit and deny.
    ///
    /// Returns:
    /// - `Ok(())` if no concurrent_sessions limit OR `current_child_sessions < max`
    /// - `Err` with reason "concurrent_limit_exceeded" if `current_child_sessions >= max`
    pub fn enforce_concurrent_sessions(&self) -> Result<(), AttestationRefreshResponse> {
        if let Some(max_concurrent) = self.rate_limits.concurrent_sessions {
            if self.current_child_sessions >= max_concurrent {
                return Err(error_concurrent_limit_exceeded(max_concurrent));
            }
        }
        Ok(())
    }

    /// Validate all constraints in composition (Most-Restrictive-Wins)
    ///
    /// Evaluates all constraints in order of criticality:
    /// 1. Budget (core resource, checked first)
    /// 2. Rate limit burst (per-request ceiling)
    /// 3. Concurrent sessions (session ceiling)
    ///
    /// Returns `Ok(())` only if ALL constraints are satisfied.
    /// Returns first violated constraint's error (fail-closed).
    ///
    /// This is the main entry point for handlers (Task 27).
    pub fn validate_all_constraints(&self, requested_cost: u64) -> Result<(), AttestationRefreshResponse> {
        // Check budget first (most fundamental resource)
        self.enforce_budget(requested_cost)?;

        // Check rate limit second (per-request burst protection)
        self.validate_rate_limit(requested_cost)?;

        // Check concurrent sessions last (session ceiling)
        self.enforce_concurrent_sessions()?;

        Ok(())
    }

    /// Compute the effective ceiling across all constraints
    ///
    /// Returns the minimum of:
    /// - `token_budget_remaining`
    /// - `burst_size` (if configured, else u64::MAX)
    ///
    /// Useful for handlers to report available capacity without committing to a charge.
    pub fn effective_ceiling(&self) -> u64 {
        let budget_ceiling = self.token_budget_remaining;
        let burst_ceiling = self.rate_limits.burst_size.unwrap_or(u64::MAX);
        std::cmp::min(budget_ceiling, burst_ceiling)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_enforce_budget_sufficient() {
        // Budget remaining (100) > requested (50) → should pass
        let resolver = ConstraintResolver::new(
            1000,  // initial
            100,   // remaining
            900,   // consumed
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        assert!(resolver.enforce_budget(50).is_ok());
    }

    #[test]
    fn test_enforce_budget_exact_match() {
        // Budget remaining (75) == requested (75) → zero balance after, should pass
        let resolver = ConstraintResolver::new(
            1000,  // initial
            75,    // remaining
            925,   // consumed
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        assert!(resolver.enforce_budget(75).is_ok());
    }

    #[test]
    fn test_enforce_budget_exhausted() {
        // Budget remaining (50) < requested (100) → should fail
        let resolver = ConstraintResolver::new(
            1000,  // initial
            50,    // remaining
            950,   // consumed
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let result = resolver.enforce_budget(100);
        assert!(result.is_err());

        match result {
            Err(AttestationRefreshResponse::Error(err)) => {
                assert_eq!(err.reason, "budget_exhausted");
                assert_eq!(err.status, "denied");
            }
            _ => panic!("Expected error response with budget_exhausted reason"),
        }
    }

    #[test]
    fn test_validate_rate_limit_no_constraints() {
        // No rate limit constraints configured → should always pass
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        assert!(resolver.validate_rate_limit(1000).is_ok());
    }

    #[test]
    fn test_validate_rate_limit_within_burst() {
        // Cost (30) < burst_size (100) → should pass
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: Some("1000/min".to_string()),
                burst_size: Some(100),
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        assert!(resolver.validate_rate_limit(30).is_ok());
    }

    #[test]
    fn test_validate_rate_limit_burst_exceeded() {
        // Cost (150) > burst_size (100) → should fail
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: Some("1000/min".to_string()),
                burst_size: Some(100),
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let result = resolver.validate_rate_limit(150);
        assert!(result.is_err());

        match result {
            Err(AttestationRefreshResponse::Error(err)) => {
                assert_eq!(err.reason, "rate_limit_exceeded");
                assert!(err.detail.contains("1000/min"));
            }
            _ => panic!("Expected error response with rate_limit_exceeded reason"),
        }
    }

    #[test]
    fn test_validate_all_constraints_budget_wins() {
        // Budget remaining (30) < burst_size (100)
        // Request 50 tokens → budget constraint binds first, should fail with budget_exhausted
        let resolver = ConstraintResolver::new(
            1000,  // initial
            30,    // remaining (more restrictive)
            970,   // consumed
            RateLimitConstraints {
                rate_limit: Some("1000/min".to_string()),
                burst_size: Some(100),  // less restrictive
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let result = resolver.validate_all_constraints(50);
        assert!(result.is_err());

        match result {
            Err(AttestationRefreshResponse::Error(err)) => {
                // Budget check runs first, so budget_exhausted error is returned
                assert_eq!(err.reason, "budget_exhausted");
            }
            _ => panic!("Expected budget_exhausted error"),
        }
    }

    #[test]
    fn test_validate_all_constraints_rate_limit_wins() {
        // Budget remaining (200) > burst_size (50)
        // Request 75 tokens → rate limit constraint binds first, should fail with rate_limit_exceeded
        let resolver = ConstraintResolver::new(
            1000,  // initial
            200,   // remaining (less restrictive)
            800,   // consumed
            RateLimitConstraints {
                rate_limit: Some("1000/min".to_string()),
                burst_size: Some(50),  // more restrictive
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let result = resolver.validate_all_constraints(75);
        assert!(result.is_err());

        match result {
            Err(AttestationRefreshResponse::Error(err)) => {
                // Rate limit check runs second, so rate_limit_exceeded error is returned
                assert_eq!(err.reason, "rate_limit_exceeded");
            }
            _ => panic!("Expected rate_limit_exceeded error"),
        }
    }

    // ====== Phase 7 Integration Unit Tests (Group B: 8 Additional Tests) ======

    #[test]
    fn test_effective_ceiling_budget_only_no_burst() {
        // No burst_size configured → ceiling = remaining budget
        let resolver = ConstraintResolver::new(
            1000,
            500,    // remaining budget
            500,
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,  // no burst configured
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let ceiling = resolver.effective_ceiling();
        assert_eq!(ceiling, 500, "Ceiling should equal remaining budget when no burst");
    }

    #[test]
    fn test_effective_ceiling_burst_lower_than_budget() {
        // burst_size (200) < remaining budget (500) → ceiling = burst
        let resolver = ConstraintResolver::new(
            1000,
            500,    // remaining budget (higher)
            500,
            RateLimitConstraints {
                rate_limit: Some("200/sec".to_string()),
                burst_size: Some(200),  // lower than budget
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let ceiling = resolver.effective_ceiling();
        assert_eq!(ceiling, 200, "Ceiling should equal burst when burst < budget");
    }

    #[test]
    fn test_effective_ceiling_budget_lower_than_burst() {
        // burst_size (1000) > remaining budget (300) → ceiling = budget
        let resolver = ConstraintResolver::new(
            1000,
            300,    // remaining budget (lower)
            700,
            RateLimitConstraints {
                rate_limit: None,
                burst_size: Some(1000),  // higher than budget
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let ceiling = resolver.effective_ceiling();
        assert_eq!(ceiling, 300, "Ceiling should equal budget when budget < burst");
    }

    #[test]
    fn test_concurrent_sessions_one_below_max_passes() {
        // current=9, max=10 → Ok (not at ceiling yet)
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: Some(10),  // max 10
            },
            9,  // current: one below max
        );

        let result = resolver.enforce_concurrent_sessions();
        assert!(result.is_ok(), "Should pass when below max");
    }

    #[test]
    fn test_concurrent_sessions_at_max_fails() {
        // current=10, max=10 → Err (at ceiling)
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: Some(10),  // max 10
            },
            10,  // current: exactly at max (should fail with >=)
        );

        let result = resolver.enforce_concurrent_sessions();
        assert!(result.is_err(), "Should fail when at max");

        match result {
            Err(AttestationRefreshResponse::Error(err)) => {
                assert_eq!(err.reason, "concurrent_limit_exceeded");
            }
            _ => panic!("Expected concurrent_limit_exceeded error"),
        }
    }

    #[test]
    fn test_all_constraints_pass_simultaneously() {
        // All three constraints satisfied: budget ok, rate ok, concurrent ok
        let resolver = ConstraintResolver::new(
            1000,
            500,   // plenty of budget
            500,
            RateLimitConstraints {
                rate_limit: Some("1000/min".to_string()),
                burst_size: Some(200),  // allows our request
                min_interval_ms: None,
                concurrent_sessions: Some(10),  // far below limit
            },
            5,  // well below max
        );

        let result = resolver.validate_all_constraints(100);  // small request
        assert!(result.is_ok(), "All constraints pass → should be Ok");
    }

    #[test]
    fn test_validate_rate_limit_with_rate_limit_string_but_no_burst() {
        // rate_limit="1000/min" but burst_size=None → no constraint (burst not configured)
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: Some("1000/min".to_string()),  // configured
                burst_size: None,  // NOT configured
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let result = resolver.validate_rate_limit(999_999);  // huge request
        assert!(result.is_ok(), "No burst_size configured → rate limit check is no-op");
    }

    #[test]
    fn test_effective_ceiling_zero_budget_zero_ceiling() {
        // remaining=0 → ceiling=0, next enforce_budget(1) fails
        let resolver = ConstraintResolver::new(
            1000,
            0,  // zero budget remaining
            1000,
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let ceiling = resolver.effective_ceiling();
        assert_eq!(ceiling, 0, "Ceiling is zero when budget exhausted");

        // Verify next check fails
        let result = resolver.enforce_budget(1);
        assert!(result.is_err(), "Any cost > 0 should fail with zero budget");

        match result {
            Err(AttestationRefreshResponse::Error(err)) => {
                assert_eq!(err.reason, "budget_exhausted");
            }
            _ => panic!("Expected budget_exhausted error"),
        }
    }

    #[test]
    fn test_enforce_concurrent_sessions_zero_limit_no_ceiling() {
        // concurrent_sessions=None (no limit) → always passes
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: None,
                burst_size: None,
                min_interval_ms: None,
                concurrent_sessions: None,  // no limit
            },
            999,  // absurdly high current count
        );

        let result = resolver.enforce_concurrent_sessions();
        assert!(result.is_ok(), "No concurrent limit → always passes regardless of current count");
    }

    #[test]
    fn test_validate_rate_limit_exact_burst_match() {
        // requested_cost == burst_size → should pass (not > burst)
        let resolver = ConstraintResolver::new(
            1000,
            500,
            500,
            RateLimitConstraints {
                rate_limit: Some("1000/min".to_string()),
                burst_size: Some(100),  // exact match
                min_interval_ms: None,
                concurrent_sessions: None,
            },
            0,
        );

        let result = resolver.validate_rate_limit(100);  // exactly equal to burst
        assert!(result.is_ok(), "Cost equal to burst_size should pass (not >)");
    }
}
