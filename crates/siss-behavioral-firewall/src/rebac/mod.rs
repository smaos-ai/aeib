use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::sync::Arc;
use std::time::SystemTime;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SovereignIdentity(pub Uuid);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum RelationType {
    Owner,
    Operator,
    Observer,
    Delegate,
    Participant,
    Initiator,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PolicyResource {
    Agent(Uuid),
    Task(Uuid),
    ConsentGrant(Uuid),
    ArbitrationCycle(Uuid),
    FeedbackChannel(Uuid),
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PolicyAction {
    Spawn,
    Pause,
    Resume,
    Abort,
    Terminate,
    AssignTask,
    CancelTask,
    FinalizeTask,
    InitiateConsent,
    VoteConsent,
    RevokeGrant,
    ReadMetrics,
    StreamEvents,
    CreatePolicy,
    UpdatePolicy,
    DeletePolicy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DenyReason {
    ReBAC(String),
    AP2(String),
    TemporalViolation(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Relationship {
    pub id: Uuid,
    pub from: SovereignIdentity,
    pub to_resource: PolicyResource,
    pub rel_type: RelationType,
    pub created_at: SystemTime,
    pub expires_at: Option<SystemTime>,
    pub revoked_at: Option<SystemTime>,
}

impl Relationship {
    pub fn is_expired(&self) -> bool {
        if let Some(expires) = self.expires_at {
            SystemTime::now() > expires
        } else {
            false
        }
    }

    pub fn is_active(&self) -> bool {
        !self.is_expired() && self.revoked_at.is_none()
    }
}

#[derive(Debug, Clone)]
pub enum ReBACError {
    Database(String),
    NotFound,
    AlreadyExists,
    CycleDetected,
    MaxDepthExceeded,
}

impl std::fmt::Display for ReBACError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReBACError::Database(e) => write!(f, "Database error: {}", e),
            ReBACError::NotFound => write!(f, "Relationship not found"),
            ReBACError::AlreadyExists => write!(f, "Relationship already exists"),
            ReBACError::CycleDetected => write!(f, "Cycle detected in delegation"),
            ReBACError::MaxDepthExceeded => write!(f, "Max delegation depth exceeded"),
        }
    }
}

impl std::error::Error for ReBACError {}

pub struct ReBAC {
    // in-memory graph: (from_sovereign, to_resource) -> Vec<Relationship>
    relationships: Arc<dashmap::DashMap<(SovereignIdentity, PolicyResource), Vec<Relationship>>>,
    all_relationships: Arc<dashmap::DashMap<Uuid, Relationship>>,
}

impl ReBAC {
    pub fn new() -> Self {
        ReBAC {
            relationships: Arc::new(dashmap::DashMap::new()),
            all_relationships: Arc::new(dashmap::DashMap::new()),
        }
    }

    pub fn grant_relationship(
        &self,
        from: SovereignIdentity,
        to: PolicyResource,
        rel_type: RelationType,
        expires_at: Option<SystemTime>,
    ) -> Result<Uuid, ReBACError> {
        let rel_id = Uuid::new_v4();

        let relationship = Relationship {
            id: rel_id,
            from,
            to_resource: to.clone(),
            rel_type,
            created_at: SystemTime::now(),
            expires_at,
            revoked_at: None,
        };

        let key = (from, to.clone());
        let mut entry = self.relationships.entry(key).or_insert_with(Vec::new);
        entry.push(relationship.clone());

        self.all_relationships.insert(rel_id, relationship);

        Ok(rel_id)
    }

    pub fn revoke_relationship(&self, rel_id: Uuid) -> Result<(), ReBACError> {
        if let Some(mut rel) = self.all_relationships.get_mut(&rel_id) {
            rel.revoked_at = Some(SystemTime::now());
            Ok(())
        } else {
            Err(ReBACError::NotFound)
        }
    }

    pub fn verify_relationship(
        &self,
        from: SovereignIdentity,
        to: PolicyResource,
        action: PolicyAction,
    ) -> Result<String, DenyReason> {
        let key = (from, to.clone());

        if let Some(rels) = self.relationships.get(&key) {
            for rel in rels.iter() {
                // Check if relationship is revoked in all_relationships (authoritative source)
                if let Some(authoritative_rel) = self.all_relationships.get(&rel.id) {
                    if authoritative_rel.is_active()
                        && Self::action_allowed_for_relation(&action, authoritative_rel.rel_type)
                    {
                        return Ok(format!(
                            "{:?} permits {:?}",
                            authoritative_rel.rel_type, action
                        ));
                    }
                } else if rel.is_active()
                    && Self::action_allowed_for_relation(&action, rel.rel_type)
                {
                    return Ok(format!("{:?} permits {:?}", rel.rel_type, action));
                }
            }
        }

        Err(DenyReason::ReBAC(format!(
            "No valid relationship to perform {:?} on {:?}",
            action, to
        )))
    }

    fn action_allowed_for_relation(action: &PolicyAction, rel_type: RelationType) -> bool {
        match (action, rel_type) {
            // Owner can do anything
            (_, RelationType::Owner) => true,

            // Operator can manage lifecycle
            (
                PolicyAction::Pause
                | PolicyAction::Resume
                | PolicyAction::Abort
                | PolicyAction::AssignTask
                | PolicyAction::CancelTask,
                RelationType::Operator,
            ) => true,

            // Observer can only read
            (PolicyAction::ReadMetrics | PolicyAction::StreamEvents, RelationType::Observer) => {
                true
            }

            // Delegate can create/update policies
            (PolicyAction::CreatePolicy | PolicyAction::UpdatePolicy, RelationType::Delegate) => {
                true
            }

            // Participant can vote
            (PolicyAction::VoteConsent, RelationType::Participant) => true,

            // Initiator can cancel their own work
            (PolicyAction::CancelTask | PolicyAction::Abort, RelationType::Initiator) => true,

            _ => false,
        }
    }

    pub fn list_relationships(&self, from: SovereignIdentity) -> Vec<Relationship> {
        let mut result = Vec::new();
        for entry in self.relationships.iter() {
            if entry.key().0 == from {
                result.extend(entry.value().clone());
            }
        }
        result
    }

    pub fn detect_cycle(
        &self,
        from: &SovereignIdentity,
        to: &SovereignIdentity,
    ) -> Result<(), ReBACError> {
        let mut visited = HashSet::new();
        self.dfs(from, to, 0, &mut visited)
    }

    fn dfs(
        &self,
        current: &SovereignIdentity,
        target: &SovereignIdentity,
        depth: usize,
        visited: &mut HashSet<SovereignIdentity>,
    ) -> Result<(), ReBACError> {
        // Check depth BEFORE incrementing (so depth 0, 1, 2, 3 are valid, 4+ is too deep)
        if depth > 3 {
            return Err(ReBACError::MaxDepthExceeded);
        }

        // If we've visited this node before in this path, we have a cycle
        if visited.contains(current) {
            return Err(ReBACError::CycleDetected);
        }

        visited.insert(*current);

        // Get all delegation relationships from current
        let rels = self.list_relationships(*current);
        for rel in rels {
            if rel.rel_type == RelationType::Delegate && rel.is_active() {
                if let PolicyResource::Agent(agent_id) = rel.to_resource {
                    let next = SovereignIdentity(agent_id);

                    // If we reach the target at any depth > 3, it's too deep
                    if next == *target && depth + 1 > 3 {
                        return Err(ReBACError::MaxDepthExceeded);
                    }

                    // Recursively check delegation chains
                    let mut new_visited = visited.clone();
                    let result = self.dfs(&next, target, depth + 1, &mut new_visited);

                    // If any path finds a cycle or depth violation, propagate error
                    if result.is_err() {
                        return result;
                    }
                }
            }
        }

        // No cycle detected
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Helper function to create a SovereignIdentity
    fn sovereign(id: u64) -> SovereignIdentity {
        SovereignIdentity(Uuid::from_u64_pair(id, 0))
    }

    fn agent(id: u64) -> PolicyResource {
        PolicyResource::Agent(Uuid::from_u64_pair(id, 0))
    }

    fn task(id: u64) -> PolicyResource {
        PolicyResource::Task(Uuid::from_u64_pair(id, 0))
    }

    // ============================================================================
    // RED PHASE TEST SUITE: 16 COMPREHENSIVE TESTS
    // ============================================================================

    // TEST 1: Owner relationship - can perform all actions
    #[test]
    fn test_owner_can_perform_all_actions() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
            .unwrap();

        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Pause)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Resume)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Abort)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::CreatePolicy)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::VoteConsent)
                .is_ok()
        );
    }

    // TEST 2: Operator relationship - can manage lifecycle
    #[test]
    fn test_operator_can_manage_lifecycle() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Operator, None)
            .unwrap();

        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Pause)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Resume)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Abort)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::AssignTask)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::CancelTask)
                .is_ok()
        );

        // Operator cannot spawn
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 3: Observer relationship - read-only access
    #[test]
    fn test_observer_can_read_only() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Observer, None)
            .unwrap();

        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::ReadMetrics)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::StreamEvents)
                .is_ok()
        );

        // Observer cannot modify
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Pause)
                .is_err()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Abort)
                .is_err()
        );
    }

    // TEST 4: Delegate relationship - can grant permissions
    #[test]
    fn test_delegate_can_create_policies() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Delegate, None)
            .unwrap();

        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::CreatePolicy)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::UpdatePolicy)
                .is_ok()
        );

        // Delegate cannot spawn
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 5: Participant relationship - can vote on consensus
    #[test]
    fn test_participant_can_vote() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let g1 = PolicyResource::ConsentGrant(Uuid::new_v4());

        rebac
            .grant_relationship(s1, g1.clone(), RelationType::Participant, None)
            .unwrap();

        assert!(
            rebac
                .verify_relationship(s1, g1.clone(), PolicyAction::VoteConsent)
                .is_ok()
        );

        // Participant cannot spawn
        assert!(
            rebac
                .verify_relationship(s1, g1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 6: Initiator relationship - can cancel own work
    #[test]
    fn test_initiator_can_cancel_own_work() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let t1 = task(1);

        rebac
            .grant_relationship(s1, t1.clone(), RelationType::Initiator, None)
            .unwrap();

        assert!(
            rebac
                .verify_relationship(s1, t1.clone(), PolicyAction::CancelTask)
                .is_ok()
        );
        assert!(
            rebac
                .verify_relationship(s1, t1.clone(), PolicyAction::Abort)
                .is_ok()
        );

        // Initiator cannot spawn
        assert!(
            rebac
                .verify_relationship(s1, t1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 7: Expired relationship - fail-closed (DENY)
    #[test]
    fn test_expired_relationship_denied() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        // Grant with expiry in the past
        let expired_time = SystemTime::now() - std::time::Duration::from_secs(60);
        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Owner, Some(expired_time))
            .unwrap();

        // Must be denied (fail-closed)
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 8: Revoked relationship - fail-closed (DENY)
    #[test]
    fn test_revoked_relationship_denied() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        let rel_id = rebac
            .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
            .unwrap();

        // Verify it works initially
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_ok()
        );

        // Revoke it
        rebac.revoke_relationship(rel_id).unwrap();

        // Must be denied after revocation
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 9: Unknown relationship - fail-closed (DENY)
    #[test]
    fn test_unknown_relationship_denied() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let s2 = sovereign(2);
        let a1 = agent(1);

        // s1 has no relationship to a1
        // s2 grants a relationship to a1 (but not s1)
        rebac
            .grant_relationship(s2, a1.clone(), RelationType::Owner, None)
            .unwrap();

        // s1 should be denied
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 10: List relationships for a sovereign
    #[test]
    fn test_list_relationships() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);
        let a2 = agent(2);
        let t1 = task(1);

        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
            .unwrap();
        rebac
            .grant_relationship(s1, a2.clone(), RelationType::Operator, None)
            .unwrap();
        rebac
            .grant_relationship(s1, t1.clone(), RelationType::Initiator, None)
            .unwrap();

        let rels = rebac.list_relationships(s1);
        assert_eq!(rels.len(), 3);
        assert!(rels.iter().any(|r| r.rel_type == RelationType::Owner));
        assert!(rels.iter().any(|r| r.rel_type == RelationType::Operator));
        assert!(rels.iter().any(|r| r.rel_type == RelationType::Initiator));
    }

    // TEST 11: Transitive delegation (A -> B -> C) depth 2, no cycle
    #[test]
    fn test_transitive_delegation_depth_2_allowed() {
        let rebac = ReBAC::new();
        let s_a = sovereign(1);
        let s_b = sovereign(2);
        let s_c = sovereign(3);

        // A delegates to B (via Agent resource that represents B)
        rebac
            .grant_relationship(
                s_a,
                PolicyResource::Agent(s_b.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();

        // B delegates to C (via Agent resource that represents C)
        rebac
            .grant_relationship(
                s_b,
                PolicyResource::Agent(s_c.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();

        // No cycle (A -> B -> C is valid delegation chain at depth 2)
        assert!(rebac.detect_cycle(&s_a, &s_c).is_ok());
    }

    // TEST 12: Direct cycle (A -> B -> A) depth 2, cycle detected
    #[test]
    fn test_direct_cycle_detection() {
        let rebac = ReBAC::new();
        let s_a = sovereign(1);
        let s_b = sovereign(2);

        // A delegates to B (via agent)
        rebac
            .grant_relationship(
                s_a,
                PolicyResource::Agent(s_b.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();

        // B delegates back to A (creating cycle)
        rebac
            .grant_relationship(
                s_b,
                PolicyResource::Agent(s_a.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();

        // Cycle must be detected
        assert!(rebac.detect_cycle(&s_a, &s_b).is_err());
    }

    // TEST 13: Depth limit (A -> B -> C -> D -> E) exceeds max_depth 3
    #[test]
    fn test_delegation_depth_limit_3() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let s2 = sovereign(2);
        let s3 = sovereign(3);
        let s4 = sovereign(4);
        let s5 = sovereign(5);

        // Chain: s1 -> s2 -> s3 -> s4 -> s5 (depth 4, exceeds limit 3)
        rebac
            .grant_relationship(
                s1,
                PolicyResource::Agent(s2.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();
        rebac
            .grant_relationship(
                s2,
                PolicyResource::Agent(s3.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();
        rebac
            .grant_relationship(
                s3,
                PolicyResource::Agent(s4.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();
        rebac
            .grant_relationship(
                s4,
                PolicyResource::Agent(s5.0),
                RelationType::Delegate,
                None,
            )
            .unwrap();

        // Should detect max depth exceeded when traversing from s1 to s5
        assert!(rebac.detect_cycle(&s1, &s5).is_err());
    }

    // TEST 14: Multiple relationships to same resource, only one active
    #[test]
    fn test_multiple_relationships_only_active_counted() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        // Grant with expiry in past (inactive)
        let past = SystemTime::now() - std::time::Duration::from_secs(60);
        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Operator, Some(past))
            .unwrap();

        // Grant new active relationship
        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
            .unwrap();

        // Should use the active Owner relationship
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_ok()
        );
    }

    // TEST 15: Fail-closed on unrecognized action
    #[test]
    fn test_unrecognized_relationship_type_action_denied() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let a1 = agent(1);

        // Observer cannot perform Spawn
        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Observer, None)
            .unwrap();

        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_err()
        );
    }

    // TEST 16: Concurrent relationships from multiple sovereigns
    #[test]
    fn test_multiple_sovereigns_independent_rels() {
        let rebac = ReBAC::new();
        let s1 = sovereign(1);
        let s2 = sovereign(2);
        let a1 = agent(1);

        rebac
            .grant_relationship(s1, a1.clone(), RelationType::Owner, None)
            .unwrap();
        rebac
            .grant_relationship(s2, a1.clone(), RelationType::Observer, None)
            .unwrap();

        // s1 is Owner, can spawn
        assert!(
            rebac
                .verify_relationship(s1, a1.clone(), PolicyAction::Spawn)
                .is_ok()
        );

        // s2 is Observer, cannot spawn
        assert!(
            rebac
                .verify_relationship(s2, a1.clone(), PolicyAction::Spawn)
                .is_err()
        );

        // s2 can read
        assert!(
            rebac
                .verify_relationship(s2, a1.clone(), PolicyAction::ReadMetrics)
                .is_ok()
        );
    }
}

pub mod pg;
