use serde::{Deserialize, Serialize};

/// Skills 2.0: Declarative skill specification with execution bounds.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillPayload {
    pub name: String,
    pub version: String,
    pub goal: String,
    pub max_execution_depth: u32,
    pub max_token_budget: u32,
}

/// CIPO execution context: tracks depth and token consumption against skill bounds.
#[derive(Debug, Clone)]
pub struct CipoContext {
    pub skill: SkillPayload,
    pub tokens_consumed: u32,
    pub depth: u32,
}

/// CIPO constraint violation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CipoError {
    DepthExceeded,
    BudgetExceeded,
}

/// Skill payload parsing error.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SkillParseError {
    InvalidJson,
    MissingField,
    InvalidVersion,
}

impl CipoContext {
    pub fn new(skill: SkillPayload) -> Self {
        CipoContext {
            skill,
            tokens_consumed: 0,
            depth: 0,
        }
    }

    pub fn verify(&self) -> Result<(), CipoError> {
        if self.depth > self.skill.max_execution_depth {
            return Err(CipoError::DepthExceeded);
        }
        if self.tokens_consumed > self.skill.max_token_budget {
            return Err(CipoError::BudgetExceeded);
        }
        Ok(())
    }

    pub fn parse_skill_payload(payload: &str) -> Result<SkillPayload, SkillParseError> {
        let parsed: serde_json::Value =
            serde_json::from_str(payload).map_err(|_| SkillParseError::InvalidJson)?;

        let name = parsed
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or(SkillParseError::MissingField)?
            .to_string();

        let version = parsed
            .get("version")
            .and_then(|v| v.as_str())
            .ok_or(SkillParseError::MissingField)?
            .to_string();

        if !version.contains('.') {
            return Err(SkillParseError::InvalidVersion);
        }

        let goal = parsed
            .get("goal")
            .and_then(|v| v.as_str())
            .ok_or(SkillParseError::MissingField)?
            .to_string();

        let max_execution_depth = parsed
            .get("max_execution_depth")
            .and_then(|v| v.as_u64())
            .ok_or(SkillParseError::MissingField)? as u32;

        let max_token_budget = parsed
            .get("max_token_budget")
            .and_then(|v| v.as_u64())
            .ok_or(SkillParseError::MissingField)? as u32;

        Ok(SkillPayload {
            name,
            version,
            goal,
            max_execution_depth,
            max_token_budget,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_skill_payload_parsing_valid() {
        let payload_json = r#"{
            "name": "test-skill",
            "version": "1.0.0",
            "goal": "Test CIPO",
            "max_execution_depth": 10,
            "max_token_budget": 1000
        }"#;

        let result = CipoContext::parse_skill_payload(payload_json);
        assert!(result.is_ok());
        let skill = result.unwrap();
        assert_eq!(skill.name, "test-skill");
        assert_eq!(skill.version, "1.0.0");
        assert_eq!(skill.max_execution_depth, 10);
        assert_eq!(skill.max_token_budget, 1000);
    }

    #[test]
    fn test_cipo_context_initial_state_valid() {
        let skill = SkillPayload {
            name: "test".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test".to_string(),
            max_execution_depth: 5,
            max_token_budget: 100,
        };

        let ctx = CipoContext::new(skill);
        assert_eq!(ctx.depth, 0);
        assert_eq!(ctx.tokens_consumed, 0);
        assert!(ctx.verify().is_ok());
    }

    #[test]
    fn test_cipo_depth_exceeded() {
        let skill = SkillPayload {
            name: "test".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test".to_string(),
            max_execution_depth: 5,
            max_token_budget: 1000,
        };

        let mut ctx = CipoContext::new(skill);
        ctx.depth = 6;
        assert!(ctx.verify().is_err());
        assert_eq!(ctx.verify().unwrap_err(), CipoError::DepthExceeded);
    }

    #[test]
    fn test_cipo_budget_exceeded() {
        let skill = SkillPayload {
            name: "test".to_string(),
            version: "1.0.0".to_string(),
            goal: "Test".to_string(),
            max_execution_depth: 10,
            max_token_budget: 100,
        };

        let mut ctx = CipoContext::new(skill);
        ctx.tokens_consumed = 101;
        assert!(ctx.verify().is_err());
        assert_eq!(ctx.verify().unwrap_err(), CipoError::BudgetExceeded);
    }
}
