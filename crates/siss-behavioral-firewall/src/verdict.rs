use siss_graph_core::node::governance::Severity;

use crate::types::{Verdict, Violation};

pub fn render_verdict(violations: &[Violation]) -> Verdict {
    if violations.is_empty() {
        return Verdict::Clear;
    }

    let worst = violations
        .iter()
        .map(|v| severity_rank(v.severity))
        .max()
        .unwrap_or(0);

    match worst {
        0 => Verdict::Clear,
        1 => Verdict::Blocked,
        2 => Verdict::CriticalBlocked,
        _ => Verdict::Clear,
    }
}

fn severity_rank(s: Severity) -> u8 {
    match s {
        Severity::Advisory => 0,
        Severity::Enforced => 1,
        Severity::Critical => 2,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_violation(severity: Severity) -> Violation {
        Violation {
            checker: "test".into(),
            severity,
            message: "test".into(),
        }
    }

    #[test]
    fn test_no_violations_clear() {
        assert_eq!(render_verdict(&[]), Verdict::Clear);
    }

    #[test]
    fn test_advisory_only_clear() {
        assert_eq!(
            render_verdict(&[make_violation(Severity::Advisory)]),
            Verdict::Clear
        );
    }

    #[test]
    fn test_enforced_blocked() {
        assert_eq!(
            render_verdict(&[make_violation(Severity::Enforced)]),
            Verdict::Blocked
        );
    }

    #[test]
    fn test_critical_critical_blocked() {
        assert_eq!(
            render_verdict(&[make_violation(Severity::Critical)]),
            Verdict::CriticalBlocked
        );
    }

    #[test]
    fn test_mixed_worst_wins() {
        let v = vec![
            make_violation(Severity::Advisory),
            make_violation(Severity::Enforced),
            make_violation(Severity::Critical),
        ];
        assert_eq!(render_verdict(&v), Verdict::CriticalBlocked);
    }

    #[test]
    fn test_advisory_and_enforced_blocked() {
        let v = vec![
            make_violation(Severity::Advisory),
            make_violation(Severity::Enforced),
        ];
        assert_eq!(render_verdict(&v), Verdict::Blocked);
    }
}
