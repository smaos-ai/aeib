/// Wave 2: Deterministic Skill Execution
/// A static registry of edge skills with whitelisted argument prefixes.
/// No shell interpolation, no arbitrary concatenation—only template substitution with validated args.

pub struct EdgeSkill {
    pub name: &'static str,
    pub command_template: &'static str,
    pub allowed_arg_prefixes: &'static [&'static str],
}

pub struct SkillRegistry {
    pub skills: &'static [EdgeSkill],
}

pub struct ToolInvocation {
    pub skill_name: String,
    pub args: Vec<String>,
}

pub struct ValidatedCommand {
    pub skill_name: String,
    pub resolved_command: String,
}

#[derive(Debug, PartialEq, Eq)]
pub enum SkillError {
    SkillNotFound { name: String },
    HallucinatedArgs { arg: String, reason: String },
}

pub struct SkillExecutor;

impl SkillExecutor {
    /// Validate a tool invocation against a static skill registry.
    /// RULE A: skill_name must exist in registry
    /// RULE B: each arg must start_with one of skill.allowed_arg_prefixes
    /// On success: returns ValidatedCommand with template-substituted resolved_command
    pub fn validate_invocation(
        invocation: &ToolInvocation,
        registry: &SkillRegistry,
    ) -> Result<ValidatedCommand, SkillError> {
        // RULE A: Find skill in registry
        let skill = registry
            .skills
            .iter()
            .find(|s| s.name == invocation.skill_name)
            .ok_or_else(|| SkillError::SkillNotFound {
                name: invocation.skill_name.clone(),
            })?;

        // RULE B: Validate each arg against allowed prefixes
        for arg in &invocation.args {
            let is_valid = skill
                .allowed_arg_prefixes
                .iter()
                .any(|prefix| arg.starts_with(prefix));

            if !is_valid {
                return Err(SkillError::HallucinatedArgs {
                    arg: arg.clone(),
                    reason: format!(
                        "arg does not match any allowed prefix: {:?}",
                        skill.allowed_arg_prefixes
                    ),
                });
            }
        }

        // Template substitution: simple {placeholder} replacement
        let mut resolved = skill.command_template.to_string();
        for (i, arg) in invocation.args.iter().enumerate() {
            let placeholder = format!("{{{}}}", i);
            resolved = resolved.replace(&placeholder, arg);
        }

        // Handle {device_id} for single-arg case
        if invocation.args.len() == 1 && skill.command_template.contains("{device_id}") {
            resolved = skill.command_template.replace("{device_id}", &invocation.args[0]);
        }

        // Handle {device_id} {value} for two-arg case
        if invocation.args.len() == 2 && skill.command_template.contains("{device_id}") {
            resolved = skill
                .command_template
                .replace("{device_id}", &invocation.args[0])
                .replace("{value}", &invocation.args[1]);
        }

        Ok(ValidatedCommand {
            skill_name: invocation.skill_name.clone(),
            resolved_command: resolved,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_known_skill_valid_arg() {
        let registry = SkillRegistry {
            skills: &[EdgeSkill {
                name: "sensor_read",
                command_template: "sensor_read {device_id}",
                allowed_arg_prefixes: &["SENSOR_", "DEVICE_"],
            }],
        };

        let invocation = ToolInvocation {
            skill_name: "sensor_read".to_string(),
            args: vec!["SENSOR_042".to_string()],
        };

        let result = SkillExecutor::validate_invocation(&invocation, &registry);
        assert!(result.is_ok());
        let cmd = result.unwrap();
        assert_eq!(cmd.skill_name, "sensor_read");
        assert!(cmd.resolved_command.contains("SENSOR_042"));
    }

    #[test]
    fn test_unknown_skill() {
        let registry = SkillRegistry {
            skills: &[EdgeSkill {
                name: "sensor_read",
                command_template: "sensor_read {device_id}",
                allowed_arg_prefixes: &["SENSOR_"],
            }],
        };

        let invocation = ToolInvocation {
            skill_name: "rm_rf".to_string(),
            args: vec![],
        };

        assert!(matches!(
            SkillExecutor::validate_invocation(&invocation, &registry),
            Err(SkillError::SkillNotFound { name }) if name == "rm_rf"
        ));
    }

    #[test]
    fn test_hallucinated_arg() {
        let registry = SkillRegistry {
            skills: &[EdgeSkill {
                name: "sensor_read",
                command_template: "sensor_read {device_id}",
                allowed_arg_prefixes: &["SENSOR_", "DEVICE_"],
            }],
        };

        let invocation = ToolInvocation {
            skill_name: "sensor_read".to_string(),
            args: vec!["rm -rf /data".to_string()],
        };

        assert!(matches!(
            SkillExecutor::validate_invocation(&invocation, &registry),
            Err(SkillError::HallucinatedArgs { .. })
        ));
    }
}
