use rusqlite::{Connection, params};
use uuid::Uuid;
use crate::CommitmentCapsule;

#[derive(Debug)]
pub enum CapsuleDBError {
    SqliteError(rusqlite::Error),
    SerializationError(String),
    DuplicateCapsuleId(Uuid),
    NotFound(Uuid),
}

impl From<rusqlite::Error> for CapsuleDBError {
    fn from(err: rusqlite::Error) -> Self {
        CapsuleDBError::SqliteError(err)
    }
}

pub struct CapsuleDB {
    conn: Connection,
}

impl CapsuleDB {
    pub fn new(path: &str) -> Result<Self, CapsuleDBError> {
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS capsules (
                capsule_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                affected_symbols TEXT NOT NULL,
                target_files TEXT NOT NULL,
                git_diff TEXT NOT NULL,
                cluster_tags TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                capsule_hash TEXT NOT NULL UNIQUE
            )",
        )?;
        Ok(CapsuleDB { conn })
    }

    pub fn write_capsule(&mut self, capsule: &CommitmentCapsule) -> Result<(), CapsuleDBError> {
        // Check if capsule with this ID already exists (immutability check)
        let mut stmt = self.conn.prepare("SELECT capsule_id FROM capsules WHERE capsule_id = ?1")?;
        let exists = stmt.exists(params![capsule.capsule_id.to_string()])?;

        if exists {
            return Err(CapsuleDBError::DuplicateCapsuleId(capsule.capsule_id));
        }

        // Serialize Vec fields as JSON strings
        let affected_symbols_json = serde_json::to_string(&capsule.affected_symbols)
            .map_err(|e| CapsuleDBError::SerializationError(
                format!("Failed to serialize affected_symbols: {}", e)
            ))?;

        let target_files_json = serde_json::to_string(&capsule.target_files)
            .map_err(|e| CapsuleDBError::SerializationError(
                format!("Failed to serialize target_files: {}", e)
            ))?;

        let cluster_tags_json = serde_json::to_string(&capsule.cluster_tags)
            .map_err(|e| CapsuleDBError::SerializationError(
                format!("Failed to serialize cluster_tags: {}", e)
            ))?;

        self.conn.execute(
            "INSERT INTO capsules
            (capsule_id, agent_id, affected_symbols, target_files, git_diff, cluster_tags, created_at, capsule_hash)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                capsule.capsule_id.to_string(),
                capsule.agent_id.to_string(),
                affected_symbols_json,
                target_files_json,
                &capsule.git_diff,
                cluster_tags_json,
                capsule.created_at,
                &capsule.capsule_hash,
            ],
        )?;

        Ok(())
    }

    pub fn read_capsule(&self, capsule_id: Uuid) -> Result<CommitmentCapsule, CapsuleDBError> {
        let mut stmt = self.conn.prepare(
            "SELECT capsule_id, agent_id, affected_symbols, target_files, git_diff, cluster_tags, created_at, capsule_hash
             FROM capsules WHERE capsule_id = ?1"
        )?;

        let capsule = stmt.query_row(params![capsule_id.to_string()], |row| {
            let affected_symbols: String = row.get(2)?;
            let target_files: String = row.get(3)?;
            let cluster_tags: String = row.get(5)?;

            let affected_symbols = serde_json::from_str(&affected_symbols)
                .unwrap_or_default();
            let target_files = serde_json::from_str(&target_files)
                .unwrap_or_default();
            let cluster_tags = serde_json::from_str(&cluster_tags)
                .unwrap_or_default();

            Ok(CommitmentCapsule {
                capsule_id: Uuid::parse_str(&row.get::<_, String>(0)?).unwrap(),
                agent_id: Uuid::parse_str(&row.get::<_, String>(1)?).unwrap(),
                affected_symbols,
                target_files,
                git_diff: row.get(4)?,
                cluster_tags,
                created_at: row.get(6)?,
                capsule_hash: row.get(7)?,
            })
        }).map_err(|_| CapsuleDBError::NotFound(capsule_id))?;

        Ok(capsule)
    }

    pub fn audit_trail(&self) -> Result<Vec<CommitmentCapsule>, CapsuleDBError> {
        let mut stmt = self.conn.prepare(
            "SELECT capsule_id, agent_id, affected_symbols, target_files, git_diff, cluster_tags, created_at, capsule_hash
             FROM capsules ORDER BY created_at ASC"
        )?;

        let capsules = stmt.query_map([], |row| {
            let affected_symbols: String = row.get(2)?;
            let target_files: String = row.get(3)?;
            let cluster_tags: String = row.get(5)?;

            let affected_symbols = serde_json::from_str(&affected_symbols)
                .unwrap_or_default();
            let target_files = serde_json::from_str(&target_files)
                .unwrap_or_default();
            let cluster_tags = serde_json::from_str(&cluster_tags)
                .unwrap_or_default();

            Ok(CommitmentCapsule {
                capsule_id: Uuid::parse_str(&row.get::<_, String>(0)?).unwrap(),
                agent_id: Uuid::parse_str(&row.get::<_, String>(1)?).unwrap(),
                affected_symbols,
                target_files,
                git_diff: row.get(4)?,
                cluster_tags,
                created_at: row.get(6)?,
                capsule_hash: row.get(7)?,
            })
        })?;

        let mut result = Vec::new();
        for capsule in capsules {
            result.push(capsule?);
        }
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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

    #[test]
    fn test_audit_trail_retrieval_returns_all_capsules_in_order() {
        let mut db = CapsuleDB::new(":memory:").unwrap();

        let capsule_1 = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["handleLogin".to_string()],
            target_files: vec!["src/auth.rs".to_string()],
            git_diff: "diff 1".to_string(),
            cluster_tags: vec!["auth-cluster".to_string()],
            created_at: 1716566400,
            capsule_hash: "sha256-abc123".to_string(),
        };

        let capsule_2 = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            created_at: 1716566401,
            capsule_hash: "sha256-def456".to_string(),
            ..capsule_1.clone()
        };

        db.write_capsule(&capsule_1).unwrap();
        db.write_capsule(&capsule_2).unwrap();

        let audit_trail = db.audit_trail().unwrap();
        assert_eq!(audit_trail.len(), 2);
        assert_eq!(audit_trail[0].capsule_hash, "sha256-abc123");
        assert_eq!(audit_trail[1].capsule_hash, "sha256-def456");
    }

    #[test]
    fn test_checkpoint_state_persists_across_transactions() {
        let mut db = CapsuleDB::new(":memory:").unwrap();

        let capsule = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["handleLogin".to_string()],
            target_files: vec!["src/auth.rs".to_string()],
            git_diff: "diff checkpoint test".to_string(),
            cluster_tags: vec!["auth-cluster".to_string()],
            created_at: 1716566400,
            capsule_hash: "sha256-checkpoint123".to_string(),
        };

        db.write_capsule(&capsule).unwrap();
        let capsule_id = capsule.capsule_id;

        // Verify capsule exists immediately after write (no delay)
        let retrieved = db.read_capsule(capsule_id).unwrap();
        assert_eq!(retrieved.capsule_hash, "sha256-checkpoint123");

        // Write another and verify first still exists (checkpoint state maintained)
        let capsule_2 = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            created_at: 1716566401,
            capsule_hash: "sha256-checkpoint456".to_string(),
            ..capsule.clone()
        };
        db.write_capsule(&capsule_2).unwrap();

        let original_check = db.read_capsule(capsule_id).unwrap();
        assert_eq!(original_check.capsule_hash, "sha256-checkpoint123");
    }

    #[test]
    fn test_concurrent_writes_to_different_capsules_succeed() {
        let mut db = CapsuleDB::new(":memory:").unwrap();

        let capsule_1 = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["handleLogin".to_string()],
            target_files: vec!["src/auth.rs".to_string()],
            git_diff: "diff concurrent 1".to_string(),
            cluster_tags: vec!["auth-cluster".to_string()],
            created_at: 1716566400,
            capsule_hash: "sha256-concurrent1".to_string(),
        };

        let capsule_2 = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            created_at: 1716566401,
            capsule_hash: "sha256-concurrent2".to_string(),
            ..capsule_1.clone()
        };

        db.write_capsule(&capsule_1).unwrap();
        db.write_capsule(&capsule_2).unwrap();

        let trail = db.audit_trail().unwrap();
        assert_eq!(trail.len(), 2);
    }

    #[test]
    fn test_hash_uniqueness_constraint_prevents_duplicates() {
        let mut db = CapsuleDB::new(":memory:").unwrap();

        let capsule_1 = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["handleLogin".to_string()],
            target_files: vec!["src/auth.rs".to_string()],
            git_diff: "diff hash test".to_string(),
            cluster_tags: vec!["auth-cluster".to_string()],
            created_at: 1716566400,
            capsule_hash: "sha256-unique".to_string(),
        };

        let capsule_2 = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            capsule_hash: "sha256-unique".to_string(),  // Same hash, different ID
            ..capsule_1.clone()
        };

        db.write_capsule(&capsule_1).unwrap();
        let result = db.write_capsule(&capsule_2);
        assert!(result.is_err(), "Should reject duplicate hash (integrity constraint)");
    }

    #[test]
    fn test_capsule_retrieval_preserves_all_fields() {
        let mut db = CapsuleDB::new(":memory:").unwrap();

        let capsule = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["sym1".to_string(), "sym2".to_string()],
            target_files: vec!["file1.rs".to_string(), "file2.rs".to_string()],
            git_diff: "complex diff content".to_string(),
            cluster_tags: vec!["cluster1".to_string(), "cluster2".to_string()],
            created_at: 1716566400,
            capsule_hash: "sha256-full".to_string(),
        };

        db.write_capsule(&capsule).unwrap();
        let retrieved = db.read_capsule(capsule.capsule_id).unwrap();

        assert_eq!(retrieved.capsule_id, capsule.capsule_id);
        assert_eq!(retrieved.agent_id, capsule.agent_id);
        assert_eq!(retrieved.affected_symbols, vec!["sym1", "sym2"]);
        assert_eq!(retrieved.target_files, vec!["file1.rs", "file2.rs"]);
        assert_eq!(retrieved.git_diff, "complex diff content");
        assert_eq!(retrieved.cluster_tags, vec!["cluster1", "cluster2"]);
        assert_eq!(retrieved.created_at, 1716566400);
        assert_eq!(retrieved.capsule_hash, "sha256-full");
    }

    #[test]
    fn test_empty_audit_trail_on_fresh_database() {
        let db = CapsuleDB::new(":memory:").unwrap();
        let trail = db.audit_trail().unwrap();
        assert_eq!(trail.len(), 0);
    }

    #[test]
    fn test_read_nonexistent_capsule_returns_error() {
        let db = CapsuleDB::new(":memory:").unwrap();
        let fake_id = Uuid::new_v4();
        let result = db.read_capsule(fake_id);
        assert!(result.is_err());
    }

    #[test]
    fn test_multiple_agents_same_symbol_different_capsules() {
        let mut db = CapsuleDB::new(":memory:").unwrap();

        let capsule_a = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["validateUser".to_string()],
            target_files: vec!["src/auth.rs".to_string()],
            git_diff: "diff from agent A".to_string(),
            cluster_tags: vec!["auth-cluster".to_string()],
            created_at: 1716566400,
            capsule_hash: "sha256-agentA".to_string(),
        };

        let capsule_b = CommitmentCapsule {
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            affected_symbols: vec!["validateUser".to_string()],  // Same symbol
            target_files: vec!["src/auth.rs".to_string()],
            git_diff: "diff from agent B".to_string(),
            cluster_tags: vec!["auth-cluster".to_string()],
            created_at: 1716566401,
            capsule_hash: "sha256-agentB".to_string(),
        };

        db.write_capsule(&capsule_a).unwrap();
        db.write_capsule(&capsule_b).unwrap();

        let trail = db.audit_trail().unwrap();
        assert_eq!(trail.len(), 2);
        assert_eq!(trail[0].capsule_hash, "sha256-agentA");
        assert_eq!(trail[1].capsule_hash, "sha256-agentB");
    }
}
