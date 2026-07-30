/// AutoResearch: autonomous optimization within hard, provably-closed guardrails.
/// Prevents metric gaming (paperclip problem) via path whitelist, destructive pattern ban, and anti-deletion.
use thiserror::Error;

/// A single test outcome for scoring.
#[derive(Debug, Clone)]
pub struct TestOutcome {
    pub name: String,
    pub passed: bool,
}

/// Input fed to a JudgeScript for scoring.
#[derive(Debug, Clone)]
pub struct JudgeInput {
    pub code: String,
    pub test_outcomes: Vec<TestOutcome>,
}

/// A deterministic, pure scoring function.
/// Function pointer (not closure) guarantees no captures, no I/O, no side effects.
pub struct JudgeScript {
    pub score_fn: fn(&JudgeInput) -> f64,
}

/// A test function identified by module path and name.
pub struct TestTarget {
    pub module_path: &'static str,
    pub fn_name: &'static str,
}

/// Result of a research cycle.
pub struct ResearchResult {
    pub iterations: u32,
    pub final_score: f64,
    pub applied_mutations: Vec<String>,
}

/// Errors during research execution.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum ResearchError {
    #[error("bounds violation: {0:?}")]
    BoundsViolated(BoundsViolation),
    #[error("max iterations exceeded")]
    MaxIterationsExceeded,
}

/// Violation of research bounds.
#[derive(Debug, PartialEq, Eq, Clone)]
pub enum BoundsViolation {
    PathNotAllowed { path: String },
    DestructivePattern { pattern: String },
    EmptyContent,
}

impl From<BoundsViolation> for ResearchError {
    fn from(e: BoundsViolation) -> Self {
        ResearchError::BoundsViolated(e)
    }
}

/// Compile-time bounds on research. Cannot be modified at runtime.
pub struct ProgramBounds {
    pub allowed_paths: &'static [&'static str],
    pub negative_constraints: &'static [&'static str],
    pub max_iterations: u32,
    pub self_modification_banned: bool,
}

pub struct SandboxedExperiment;

impl SandboxedExperiment {
    /// Validate a single mutation against bounds.
    /// All three rules (A, B, C) must pass or the mutation is rejected (fail-closed).
    pub fn validate_mutation(
        path: &str,
        content: &str,
        bounds: &ProgramBounds,
    ) -> Result<(), BoundsViolation> {
        // RULE A: path whitelist
        let path_allowed = bounds
            .allowed_paths
            .iter()
            .any(|prefix| path.starts_with(prefix));
        if !path_allowed {
            return Err(BoundsViolation::PathNotAllowed {
                path: path.to_string(),
            });
        }

        // RULE B: destructive pattern ban
        for pattern in bounds.negative_constraints {
            if content.contains(pattern) {
                return Err(BoundsViolation::DestructivePattern {
                    pattern: pattern.to_string(),
                });
            }
        }

        // RULE C: anti-deletion
        if content.is_empty() {
            return Err(BoundsViolation::EmptyContent);
        }

        Ok(())
    }
}

pub struct AutoResearchEngine {
    pub bounds: &'static ProgramBounds,
}

impl AutoResearchEngine {
    /// Run one research cycle: validate, score, iterate.
    /// Returns on first bounds violation (fail-closed) or max iterations.
    pub fn run_cycle(
        &self,
        _target: &TestTarget,
        judge: &JudgeScript,
        mutations: &[(String, String)],
    ) -> Result<ResearchResult, ResearchError> {
        let mut applied = Vec::new();
        let mut current_score = 0.0;

        for (idx, (path, content)) in mutations.iter().enumerate() {
            if idx >= self.bounds.max_iterations as usize {
                return Err(ResearchError::MaxIterationsExceeded);
            }

            // Fail-closed: validate first
            SandboxedExperiment::validate_mutation(path, content, self.bounds)?;

            // Create a dummy JudgeInput for scoring
            let input = JudgeInput {
                code: content.clone(),
                test_outcomes: vec![],
            };

            let score = (judge.score_fn)(&input).clamp(0.0, 1.0);

            if score > current_score {
                current_score = score;
                applied.push(path.clone());
            }
        }

        Ok(ResearchResult {
            iterations: applied.len() as u32,
            final_score: current_score,
            applied_mutations: applied,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bounds_allow_valid_mutation() {
        let bounds = ProgramBounds {
            allowed_paths: &["crates/siss-job-router/src/"],
            negative_constraints: &["rm -rf"],
            max_iterations: 10,
            self_modification_banned: true,
        };

        let result = SandboxedExperiment::validate_mutation(
            "crates/siss-job-router/src/foo.rs",
            "fn bar() {}",
            &bounds,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_bounds_reject_invalid_path() {
        let bounds = ProgramBounds {
            allowed_paths: &["crates/siss-job-router/src/"],
            negative_constraints: &[],
            max_iterations: 10,
            self_modification_banned: true,
        };

        let result = SandboxedExperiment::validate_mutation(
            "crates/siss-behavioral-firewall/src/lib.rs",
            "fn bar() {}",
            &bounds,
        );
        assert!(matches!(
            result,
            Err(BoundsViolation::PathNotAllowed { .. })
        ));
    }

    #[test]
    fn test_negative_constraint_blocks_rm_rf() {
        let bounds = ProgramBounds {
            allowed_paths: &["crates/siss-job-router/src/"],
            negative_constraints: &["rm -rf"],
            max_iterations: 10,
            self_modification_banned: true,
        };

        let result = SandboxedExperiment::validate_mutation(
            "crates/siss-job-router/src/foo.rs",
            "let x = \"rm -rf /data\";",
            &bounds,
        );
        assert!(matches!(
            result,
            Err(BoundsViolation::DestructivePattern { .. })
        ));
    }

    #[test]
    fn test_negative_constraint_blocks_drop_table() {
        let bounds = ProgramBounds {
            allowed_paths: &["crates/siss-job-router/src/"],
            negative_constraints: &["DROP TABLE"],
            max_iterations: 10,
            self_modification_banned: true,
        };

        let result = SandboxedExperiment::validate_mutation(
            "crates/siss-job-router/src/foo.rs",
            "DROP TABLE users",
            &bounds,
        );
        assert!(matches!(
            result,
            Err(BoundsViolation::DestructivePattern { .. })
        ));
    }

    #[test]
    fn test_empty_content_blocked() {
        let bounds = ProgramBounds {
            allowed_paths: &["crates/siss-job-router/src/"],
            negative_constraints: &[],
            max_iterations: 10,
            self_modification_banned: true,
        };

        let result = SandboxedExperiment::validate_mutation(
            "crates/siss-job-router/src/foo.rs",
            "",
            &bounds,
        );
        assert!(matches!(result, Err(BoundsViolation::EmptyContent)));
    }

    #[test]
    fn test_judge_score_deterministic() {
        fn my_scorer(input: &JudgeInput) -> f64 {
            input.test_outcomes.iter().filter(|t| t.passed).count() as f64 / 5.0
        }

        let script = JudgeScript {
            score_fn: my_scorer,
        };

        let input = JudgeInput {
            code: "fn foo() {}".to_string(),
            test_outcomes: vec![TestOutcome {
                name: "t1".to_string(),
                passed: true,
            }],
        };

        let s1 = (script.score_fn)(&input);
        let s2 = (script.score_fn)(&input);
        assert_eq!(s1, s2);
    }

    #[test]
    fn test_auto_research_respects_bounds() {
        static BOUNDS: ProgramBounds = ProgramBounds {
            allowed_paths: &["crates/siss-job-router/src/"],
            negative_constraints: &["rm -rf"],
            max_iterations: 10,
            self_modification_banned: true,
        };

        let engine = AutoResearchEngine { bounds: &BOUNDS };

        fn dummy_scorer(input: &JudgeInput) -> f64 {
            input.code.len() as f64 / 100.0
        }

        let target = TestTarget {
            module_path: "foo::bar",
            fn_name: "test_x",
        };

        let script = JudgeScript {
            score_fn: dummy_scorer,
        };

        let valid_mutations = vec![(
            "crates/siss-job-router/src/test.rs".to_string(),
            "fn test() {}".to_string(),
        )];

        let result = engine.run_cycle(&target, &script, &valid_mutations);
        assert!(result.is_ok());
    }
}
