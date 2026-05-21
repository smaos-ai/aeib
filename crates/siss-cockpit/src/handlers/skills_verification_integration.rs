/// Phase 29 REFACTOR: Skills 2.0 Integration Tests
/// End-to-end testing for SKILL.md parsing, verification, and CIPO-cycle integration

#[cfg(test)]
mod integration_tests {
    use crate::handlers::skills_verification::{ExecutionContext, SkillPayload, VerificationError, ParseError};

    #[test]
    fn test_skills_2_0_payload_end_to_end_valid() {
        // GIVEN valid SKILL.md JSON payload
        // WHEN parsed and verified
        // THEN execution context created and ready for dispatch

        let skill_json = r#"{
            "name": "data-extraction",
            "version": "2.1.0",
            "goal": "Extract structured data from unstructured text",
            "max_execution_depth": 10,
            "max_token_budget": 5000
        }"#;

        let skill = ExecutionContext::parse_skill_payload(skill_json).unwrap();
        let ctx = ExecutionContext::new(skill);

        assert_eq!(ctx.skill.name, "data-extraction");
        assert_eq!(ctx.skill.version, "2.1.0");
        assert_eq!(ctx.depth, 0);
        assert_eq!(ctx.tokens_consumed, 0);

        let verify = ctx.verify();
        assert!(verify.is_ok());
    }

    #[test]
    fn test_skills_2_0_cipo_cycle_constraint_enforcement() {
        // GIVEN CIPO-cycle (Correction-Oriented Policy Optimization)
        // WHEN skill execution increments depth and tokens
        // THEN verify() enforces mathematical bounds at each step
        // AND fail-closed on constraint violation

        let skill = SkillPayload {
            name: "cipo-test".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test CIPO constraints".to_string(),
            max_execution_depth: 5,
            max_token_budget: 100,
        };

        let mut ctx = ExecutionContext::new(skill);

        // Step 1: Increment depth within bounds
        ctx.depth = 2;
        ctx.tokens_consumed = 30;
        assert!(ctx.verify().is_ok());

        // Step 2: Increment further within bounds
        ctx.depth = 4;
        ctx.tokens_consumed = 70;
        assert!(ctx.verify().is_ok());

        // Step 3: Exceed depth bound
        ctx.depth = 6;
        let result = ctx.verify();
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), VerificationError::DepthExceeded));
    }

    #[test]
    fn test_skills_2_0_token_budget_enforcement_strict() {
        // GIVEN skill with max_token_budget=50
        // WHEN tokens_consumed equals exactly 50
        // THEN verify() succeeds (at boundary)
        // WHEN tokens_consumed exceeds 50
        // THEN verify() fails with BudgetExceeded (fail-closed)

        let skill = SkillPayload {
            name: "budget-strict".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test strict budget".to_string(),
            max_execution_depth: 10,
            max_token_budget: 50,
        };

        let mut ctx = ExecutionContext::new(skill);

        // At boundary: should succeed
        ctx.tokens_consumed = 50;
        assert!(ctx.verify().is_ok());

        // Over boundary: should fail
        ctx.tokens_consumed = 51;
        let result = ctx.verify();
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), VerificationError::BudgetExceeded));
    }

    #[test]
    fn test_skills_verification_rejects_unsigned_integer_fields() {
        // GIVEN SKILL.md with negative integer in max_token_budget
        // WHEN parsed
        // THEN returns ParseError (JSON deserialization fails on type mismatch)
        // AND execution prevented (fail-closed)

        let invalid_budget = r#"{
            "name": "test",
            "version": "1.0.0",
            "goal": "Test",
            "max_execution_depth": 10,
            "max_token_budget": -100
        }"#;

        let result = ExecutionContext::parse_skill_payload(invalid_budget);
        // Negative numbers won't deserialize to u32, so this should fail
        assert!(result.is_err());
    }

    #[test]
    fn test_skills_middleware_applies_constraints_per_skill() {
        // GIVEN multiple distinct skills with different constraints
        // WHEN each skill creates independent execution context
        // THEN constraints are NOT shared (per-skill isolation)
        // AND verification is independent

        let skill_a_json = r#"{
            "name": "skill-a",
            "version": "1.0.0",
            "goal": "Task A",
            "max_execution_depth": 5,
            "max_token_budget": 100
        }"#;

        let skill_b_json = r#"{
            "name": "skill-b",
            "version": "1.0.0",
            "goal": "Task B",
            "max_execution_depth": 20,
            "max_token_budget": 5000
        }"#;

        let skill_a = ExecutionContext::parse_skill_payload(skill_a_json).unwrap();
        let skill_b = ExecutionContext::parse_skill_payload(skill_b_json).unwrap();

        let mut ctx_a = ExecutionContext::new(skill_a);
        let mut ctx_b = ExecutionContext::new(skill_b);

        // Set depth to 10: OK for skill_b, but exceeds skill_a's max
        ctx_a.depth = 10;
        ctx_b.depth = 10;

        assert!(ctx_a.verify().is_err()); // Skill A: depth 10 > max 5
        assert!(ctx_b.verify().is_ok());  // Skill B: depth 10 <= max 20
    }

    #[test]
    fn test_skills_version_semver_validation_strict() {
        // GIVEN SKILL.md version strings
        // WHEN validated
        // THEN semver format accepted (must contain at least one dot)
        // AND versions without dots rejected with ParseError::InvalidVersion

        let versions = vec![
            ("1.0.0", true),      // Valid: major.minor.patch
            ("2.1", true),        // Valid: major.minor
            ("3", false),         // Invalid: no dot
            ("v1.0.0", true),     // Valid: contains dots (prefix allowed, validation is permissive)
            ("1.0.0-rc.1", true), // Valid: contains dots
            ("1..0", true),       // Valid: has dots (weak validation, but catches most cases)
            ("noversion", false), // Invalid: no dots
        ];

        for (version_str, should_pass) in versions {
            let payload = format!(
                r#"{{
                    "name": "test",
                    "version": "{}",
                    "goal": "Test",
                    "max_execution_depth": 10,
                    "max_token_budget": 1000
                }}"#,
                version_str
            );

            let result = ExecutionContext::parse_skill_payload(&payload);
            if should_pass {
                assert!(result.is_ok(), "Version {} should be valid", version_str);
            } else {
                assert!(result.is_err(), "Version {} should be invalid", version_str);
            }
        }
    }

    #[test]
    fn test_goal_driven_execution_initial_state_valid() {
        // GIVEN skill created with parse_skill_payload()
        // WHEN ExecutionContext initialized
        // THEN initial state (depth=0, tokens=0) always passes verify()
        // AND execution ready to proceed

        let skill_json = r#"{
            "name": "initial-state",
            "version": "1.0.0",
            "goal": "Test initial state",
            "max_execution_depth": 1,
            "max_token_budget": 1
        }"#;

        let skill = ExecutionContext::parse_skill_payload(skill_json).unwrap();
        let ctx = ExecutionContext::new(skill);

        assert_eq!(ctx.depth, 0);
        assert_eq!(ctx.tokens_consumed, 0);
        assert!(ctx.verify().is_ok(), "Initial state must always be valid");
    }
}
