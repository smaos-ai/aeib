#[cfg(test)]
mod persistence_tests {
    use siss_capsule_commit::{CapsuleDB, CommitmentCapsule};
    use uuid::Uuid;

    #[test]
    fn test_capsule_written_immutably_to_sqlite() {
        let capsule = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["handleLogin".to_string()],
            target_files: vec!["src/auth.rs".to_string()],
            git_diff: "diff --git a/src/auth.rs".to_string(),
            cluster_tags: vec!["auth-cluster".to_string()],
            created_at: 1716566400,
            capsule_hash: "sha256-abc123".to_string(),
        };

        let mut db = CapsuleDB::new(":memory:").unwrap();
        db.write_capsule(&capsule).unwrap();

        let retrieved = db.read_capsule(capsule.capsule_id).unwrap();
        assert_eq!(retrieved.capsule_hash, capsule.capsule_hash);

        // Verify: Cannot be overwritten (immutable)
        let tampered = CommitmentCapsule {
            capsule_hash: "sha256-evil".to_string(),
            ..capsule.clone()
        };
        let result = db.write_capsule(&tampered);
        assert!(result.is_err(), "Should reject duplicate ID write");
    }
}
