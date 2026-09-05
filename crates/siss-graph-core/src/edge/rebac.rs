use crate::edge::{EdgeRecord, EdgeType};
use crate::node::NodeId;

/// The result of a ReBAC access check.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AccessDecision {
    Allow,
    Deny,
    NoMatch,
}

/// Evaluate ReBAC access for a given permission type.
/// `direct_edges` = edges directly on the Persona.
/// `team_edges` = edges on Teams the Persona belongs to (via ACTS_AS -> User -> MEMBER_OF -> Team).
///
/// Resolution order (per spec section 4.4):
/// 1. Check direct Persona edges for DENY — if found, return Deny.
/// 2. Check team edges for DENY — if found, return Deny.
/// 3. Check direct Persona edges for ALLOW — if found, return Allow.
/// 4. Check team edges for ALLOW — if found, return Allow.
/// 5. No match = implicit deny.
pub fn evaluate_access(
    target_id: NodeId,
    allow_type: EdgeType,
    deny_type: EdgeType,
    direct_edges: &[EdgeRecord],
    team_edges: &[EdgeRecord],
) -> AccessDecision {
    // Step 1+2: Check all DENY edges first (direct then team)
    for edge in direct_edges.iter().chain(team_edges.iter()) {
        if edge.edge_type == deny_type && edge.target_id == target_id {
            return AccessDecision::Deny;
        }
    }

    // Step 3+4: Check all ALLOW edges (direct then team)
    for edge in direct_edges.iter().chain(team_edges.iter()) {
        if edge.edge_type == allow_type && edge.target_id == target_id {
            return AccessDecision::Allow;
        }
    }

    // Step 5: No match
    AccessDecision::NoMatch
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_edge(target: NodeId, edge_type: EdgeType, tenant: NodeId) -> EdgeRecord {
        EdgeRecord::new(NodeId::new(), target, edge_type, tenant)
    }

    #[test]
    fn test_direct_allow() {
        let tenant = NodeId::new();
        let target = NodeId::new();
        let direct = vec![make_edge(target, EdgeType::CanRead, tenant)];
        let result = evaluate_access(target, EdgeType::CanRead, EdgeType::DenyRead, &direct, &[]);
        assert_eq!(result, AccessDecision::Allow);
    }

    #[test]
    fn test_direct_deny_overrides_team_allow() {
        let tenant = NodeId::new();
        let target = NodeId::new();
        let direct = vec![make_edge(target, EdgeType::DenyRead, tenant)];
        let team = vec![make_edge(target, EdgeType::CanRead, tenant)];
        let result = evaluate_access(
            target,
            EdgeType::CanRead,
            EdgeType::DenyRead,
            &direct,
            &team,
        );
        assert_eq!(result, AccessDecision::Deny);
    }

    #[test]
    fn test_team_allow_when_no_direct() {
        let tenant = NodeId::new();
        let target = NodeId::new();
        let team = vec![make_edge(target, EdgeType::CanRead, tenant)];
        let result = evaluate_access(target, EdgeType::CanRead, EdgeType::DenyRead, &[], &team);
        assert_eq!(result, AccessDecision::Allow);
    }

    #[test]
    fn test_no_match_returns_implicit_deny() {
        let target = NodeId::new();
        let result = evaluate_access(target, EdgeType::CanRead, EdgeType::DenyRead, &[], &[]);
        assert_eq!(result, AccessDecision::NoMatch);
    }

    #[test]
    fn test_team_deny_overrides_direct_allow() {
        let tenant = NodeId::new();
        let target = NodeId::new();
        let direct = vec![make_edge(target, EdgeType::CanRead, tenant)];
        let team = vec![make_edge(target, EdgeType::DenyRead, tenant)];
        let result = evaluate_access(
            target,
            EdgeType::CanRead,
            EdgeType::DenyRead,
            &direct,
            &team,
        );
        assert_eq!(result, AccessDecision::Deny);
    }
}
