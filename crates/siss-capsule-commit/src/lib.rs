pub mod actor;
pub mod orchestration;
pub mod persistence;
pub mod prepare;

pub use actor::{CapsuleCommitActor, CapsuleEntry};
pub use orchestration::capsule_commit_actor::{
    ActorError, ClusterIntersection, CommitmentCapsule, GitNexusCapsuleCommitActor, MergeDecision,
};
pub use persistence::{
    AuditLogEntry, CapsuleDB, CapsuleDBError, MultiRegionDB, Region, SLAMonitor, VectorClock,
};
pub use prepare::{PrepareRequest, PrepareToken};

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_prepare_valid_capsule_returns_token() {
        let req = PrepareRequest {
            capsule_id: Uuid::new_v4(),
            budget_limit: 1000,
            budget_spent: 500,
            risk_class: 5,
        };

        let result = req.validate();
        assert!(result.is_ok(), "Valid prepare should return token");
        let token = result.unwrap();
        assert_eq!(token.capsule_id, req.capsule_id);
    }

    #[test]
    fn test_prepare_budget_exceeded_returns_err() {
        let req = PrepareRequest {
            capsule_id: Uuid::new_v4(),
            budget_limit: 100,
            budget_spent: 100, // equals limit → must reject (fail-closed)
            risk_class: 5,
        };

        let result = req.validate();
        assert!(
            result.is_err(),
            "Budget exhausted must return Err (fail-closed)"
        );
    }

    #[test]
    fn test_commit_increments_committed_count() {
        let mut actor = CapsuleCommitActor::new();
        let capsule_id = Uuid::new_v4();

        let req = PrepareRequest {
            capsule_id,
            budget_limit: 1000,
            budget_spent: 500,
            risk_class: 5,
        };

        let token = req.validate().expect("Valid request");
        let commit_result = actor.commit(token);
        assert!(
            commit_result.is_ok(),
            "Commit with valid token must succeed"
        );
        assert_eq!(actor.committed_count(), 1, "One commit recorded");

        let abort_token = req.validate().expect("Another valid request");
        actor.abort(abort_token).expect("Abort succeeds");
        assert_eq!(actor.committed_count(), 1, "Abort does not increment count");
    }
}
