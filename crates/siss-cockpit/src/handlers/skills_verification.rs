/// Phase 29: Lean 4 Formal Verification & Skills 2.0
/// RED phase: Failing tests for SKILL.md parsing, Goal-Driven Execution limits, formal verification

use serde::{Deserialize, Serialize};

/// SKILL.md Payload — Declarative skill specification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillPayload {
    pub name: String,
    pub version: String,
    pub goal: String,
    pub max_execution_depth: u32,
    pub max_token_budget: u32,
}

/// Goal-Driven Execution context for formal verification
#[derive(Debug, Clone)]
pub struct ExecutionContext {
    pub skill: SkillPayload,
    pub tokens_consumed: u32,
    pub depth: u32,
}

impl ExecutionContext {
    pub fn new(skill: SkillPayload) -> Self {
        ExecutionContext {
            skill,
            tokens_consumed: 0,
            depth: 0,
        }
    }

    /// Verify execution state against formal constraints
    /// Fail-closed: rejects malformed states (429-equivalent)
    pub fn verify(&self) -> Result<(), VerificationError> {
        if self.depth > self.skill.max_execution_depth {
            return Err(VerificationError::DepthExceeded);
        }
        if self.tokens_consumed > self.skill.max_token_budget {
            return Err(VerificationError::BudgetExceeded);
        }
        Ok(())
    }

    /// Parse and validate SKILL.md payload
    pub fn parse_skill_payload(payload: &str) -> Result<SkillPayload, ParseError> {
        let parsed: serde_json::Value = serde_json::from_str(payload)
            .map_err(|_| ParseError::InvalidJson)?;

        let name = parsed
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or(ParseError::MissingField)?
            .to_string();

        let version = parsed
            .get("version")
            .and_then(|v| v.as_str())
            .ok_or(ParseError::MissingField)?
            .to_string();

        // Validate semver format: must contain dots
        if !version.contains('.') {
            return Err(ParseError::InvalidVersion);
        }

        let goal = parsed
            .get("goal")
            .and_then(|v| v.as_str())
            .ok_or(ParseError::MissingField)?
            .to_string();

        let max_execution_depth = parsed
            .get("max_execution_depth")
            .and_then(|v| v.as_u64())
            .ok_or(ParseError::MissingField)? as u32;

        let max_token_budget = parsed
            .get("max_token_budget")
            .and_then(|v| v.as_u64())
            .ok_or(ParseError::MissingField)? as u32;

        Ok(SkillPayload {
            name,
            version,
            goal,
            max_execution_depth,
            max_token_budget,
        })
    }
}

#[derive(Debug, Clone)]
pub enum VerificationError {
    DepthExceeded,
    BudgetExceeded,
    MalformedState,
}

#[derive(Debug, Clone)]
pub enum ParseError {
    InvalidJson,
    MissingField,
    InvalidVersion,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_skill_payload_parsing_valid() {
        // GIVEN valid SKILL.md JSON payload
        // WHEN parsed with SkillPayload::parse_skill_payload()
        // THEN returns SkillPayload with all fields populated

        let payload_json = r#"{
            "name": "test-skill",
            "version": "1.0.0",
            "goal": "Test formal verification",
            "max_execution_depth": 10,
            "max_token_budget": 1000
        }"#;

        let result = ExecutionContext::parse_skill_payload(payload_json);
        assert!(result.is_ok());

        let skill = result.unwrap();
        assert_eq!(skill.name, "test-skill");
        assert_eq!(skill.version, "1.0.0");
        assert_eq!(skill.max_execution_depth, 10);
        assert_eq!(skill.max_token_budget, 1000);
    }

    #[test]
    fn test_skill_payload_parsing_rejects_invalid_json() {
        // GIVEN malformed SKILL.md JSON (missing closing brace)
        // WHEN parsed
        // THEN returns ParseError::InvalidJson
        // AND no partial state is created (fail-closed)

        let invalid_json = r#"{"name": "test-skill", "version": "1.0.0""#;

        let result = ExecutionContext::parse_skill_payload(invalid_json);
        assert!(result.is_err());
    }

    #[test]
    fn test_skill_payload_parsing_rejects_missing_fields() {
        // GIVEN SKILL.md JSON missing required field (max_token_budget)
        // WHEN parsed
        // THEN returns ParseError::MissingField
        // AND execution context is NOT initialized (fail-closed)

        let incomplete_json = r#"{
            "name": "test-skill",
            "version": "1.0.0",
            "goal": "Test"
        }"#;

        let result = ExecutionContext::parse_skill_payload(incomplete_json);
        assert!(result.is_err());
    }

    #[test]
    fn test_goal_driven_execution_rejects_depth_overflow() {
        // GIVEN execution context with max_execution_depth=5
        // WHEN depth incremented to 6
        // THEN verify() returns VerificationError::DepthExceeded
        // AND execution is rejected (fail-closed, no state mutation)

        let skill = SkillPayload {
            name: "depth-test".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test depth limits".to_string(),
            max_execution_depth: 5,
            max_token_budget: 1000,
        };

        let mut ctx = ExecutionContext::new(skill);
        ctx.depth = 6;

        let result = ctx.verify();
        assert!(result.is_err());
    }

    #[test]
    fn test_goal_driven_execution_rejects_budget_overflow() {
        // GIVEN execution context with max_token_budget=100
        // WHEN tokens_consumed incremented to 101
        // THEN verify() returns VerificationError::BudgetExceeded
        // AND execution rejected (fail-closed)

        let skill = SkillPayload {
            name: "budget-test".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test budget limits".to_string(),
            max_execution_depth: 10,
            max_token_budget: 100,
        };

        let mut ctx = ExecutionContext::new(skill);
        ctx.tokens_consumed = 101;

        let result = ctx.verify();
        assert!(result.is_err());
    }

    #[test]
    fn test_formal_verification_accepts_valid_state() {
        // GIVEN execution context within all constraints
        // WHEN verify() called
        // THEN returns Ok(())
        // AND execution proceeds to next step

        let skill = SkillPayload {
            name: "valid-test".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test valid state".to_string(),
            max_execution_depth: 10,
            max_token_budget: 1000,
        };

        let ctx = ExecutionContext::new(skill);
        let result = ctx.verify();
        assert!(result.is_ok());
    }

    #[test]
    fn test_formal_verification_rejects_malformed_version() {
        // GIVEN SKILL.md with invalid version string (not semver)
        // WHEN parsed
        // THEN returns ParseError::InvalidVersion
        // AND prevents execution of skill with invalid version (fail-closed)

        let malformed_version = r#"{
            "name": "test-skill",
            "version": "invalid-version",
            "goal": "Test",
            "max_execution_depth": 10,
            "max_token_budget": 1000
        }"#;

        let result = ExecutionContext::parse_skill_payload(malformed_version);
        assert!(result.is_err());
    }
}
