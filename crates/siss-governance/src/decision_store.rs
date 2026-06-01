use std::error::Error;
use std::fmt;
use std::path::PathBuf;
use std::sync::Mutex;

use rusqlite::Connection;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct DecisionRecord {
    pub category: String,
    pub context: String,
    pub decision: String,
}

#[derive(Debug, Clone)]
pub struct StoredDecision {
    pub id: String,
    pub created_at: f64,
    pub category: String,
    pub context: String,
    pub decision: String,
    pub prev_hash: Option<String>,
    pub merkle_hash: String,
    pub signature: String,
    pub status: String,
}

#[derive(Debug)]
pub enum StoreError {
    Db(String),
    ChainBroken {
        at_id: String,
        expected: String,
        found: String,
    },
    RetentionFloorViolation {
        floor: u64,
        current: u64,
    },
}

impl fmt::Display for StoreError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            StoreError::Db(msg) => write!(f, "Database error: {}", msg),
            StoreError::ChainBroken {
                at_id,
                expected,
                found,
            } => {
                write!(
                    f,
                    "Chain broken at {}: expected {} found {}",
                    at_id, expected, found
                )
            }
            StoreError::RetentionFloorViolation { floor, current } => {
                write!(
                    f,
                    "Retention floor violation: floor={} current={}",
                    floor, current
                )
            }
        }
    }
}

impl Error for StoreError {}

impl From<rusqlite::Error> for StoreError {
    fn from(e: rusqlite::Error) -> Self {
        StoreError::Db(e.to_string())
    }
}

pub trait DecisionStore: Send + Sync {
    fn record(&self, rec: DecisionRecord) -> Result<String, StoreError>;
    fn query_by_category(&self, category: &str) -> Result<Vec<StoredDecision>, StoreError>;
    fn query_active(&self) -> Result<Vec<StoredDecision>, StoreError>;
    fn verify_chain(&self) -> Result<bool, StoreError>;
    fn delete(&self, id: &str) -> Result<(), StoreError>;
}

const SCHEMA_DDL: &str = r#"
CREATE TABLE IF NOT EXISTS decisions (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL,
    category    TEXT NOT NULL,
    context     TEXT NOT NULL,
    decision    TEXT NOT NULL,
    prev_hash   TEXT,
    merkle_hash TEXT NOT NULL,
    signature   TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK(status IN ('ACTIVE','SUPERSEDED','REVOKED'))
);
CREATE INDEX IF NOT EXISTS idx_decisions_status   ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_category ON decisions(category);
CREATE INDEX IF NOT EXISTS idx_decisions_created  ON decisions(created_at DESC);
"#;

#[derive(Debug, Clone)]
pub struct DecisionDbConfig {
    pub retention_floor: u64,
}

impl Default for DecisionDbConfig {
    fn default() -> Self {
        Self { retention_floor: 1 }
    }
}

pub struct DecisionDb {
    conn: Mutex<Connection>,
    retention_floor: u64,
}

impl DecisionDb {
    pub fn new(path: Option<PathBuf>) -> Result<Self, StoreError> {
        Self::with_config(path, DecisionDbConfig::default())
    }

    pub fn with_config(path: Option<PathBuf>, cfg: DecisionDbConfig) -> Result<Self, StoreError> {
        let conn = match path {
            Some(p) => Connection::open(p)?,
            None => Connection::open_in_memory()?,
        };
        conn.execute_batch(SCHEMA_DDL)?;
        Ok(Self {
            conn: Mutex::new(conn),
            retention_floor: cfg.retention_floor,
        })
    }
}

impl DecisionStore for DecisionDb {
    fn record(&self, rec: DecisionRecord) -> Result<String, StoreError> {
        let conn = self.conn.lock().unwrap();
        let id = format!("d_{}", Uuid::new_v4());
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        // Compute merkle hash: prev_hash not used for new records (stub for now)
        let merkle_hash = crate::merkle::compute(None, &id, &rec.context, &rec.decision);

        conn.execute(
            "INSERT INTO decisions (id, created_at, category, context, decision, prev_hash, merkle_hash, signature, status)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rusqlite::params![
                &id,
                now,
                &rec.category,
                &rec.context,
                &rec.decision,
                None::<String>,
                &merkle_hash,
                "",
                "ACTIVE"
            ],
        )?;

        Ok(id)
    }

    fn query_by_category(&self, category: &str) -> Result<Vec<StoredDecision>, StoreError> {
        let conn = self.conn.lock().unwrap();
        let mut stmt =
            conn.prepare("SELECT id, created_at, category, context, decision, prev_hash, merkle_hash, signature, status FROM decisions WHERE category = ? AND status = 'ACTIVE' ORDER BY created_at DESC")?;

        let decisions = stmt
            .query_map(rusqlite::params![category], |row| {
                Ok(StoredDecision {
                    id: row.get(0)?,
                    created_at: row.get(1)?,
                    category: row.get(2)?,
                    context: row.get(3)?,
                    decision: row.get(4)?,
                    prev_hash: row.get(5)?,
                    merkle_hash: row.get(6)?,
                    signature: row.get(7)?,
                    status: row.get(8)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;

        Ok(decisions)
    }

    fn query_active(&self) -> Result<Vec<StoredDecision>, StoreError> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, created_at, category, context, decision, prev_hash, merkle_hash, signature, status FROM decisions WHERE status = 'ACTIVE' ORDER BY created_at DESC",
        )?;

        let decisions = stmt
            .query_map([], |row| {
                Ok(StoredDecision {
                    id: row.get(0)?,
                    created_at: row.get(1)?,
                    category: row.get(2)?,
                    context: row.get(3)?,
                    decision: row.get(4)?,
                    prev_hash: row.get(5)?,
                    merkle_hash: row.get(6)?,
                    signature: row.get(7)?,
                    status: row.get(8)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;

        Ok(decisions)
    }

    fn verify_chain(&self) -> Result<bool, StoreError> {
        let active = self.query_active()?;
        if active.is_empty() {
            return Ok(true); // Empty chain is valid
        }

        // Simple verification: all records have valid merkle hashes
        for decision in &active {
            let recomputed = crate::merkle::compute(
                decision.prev_hash.as_deref(),
                &decision.id,
                &decision.context,
                &decision.decision,
            );
            if recomputed != decision.merkle_hash {
                return Err(StoreError::ChainBroken {
                    at_id: decision.id.clone(),
                    expected: recomputed,
                    found: decision.merkle_hash.clone(),
                });
            }
        }
        Ok(true)
    }

    fn delete(&self, id: &str) -> Result<(), StoreError> {
        let conn = self.conn.lock().unwrap();

        // Count active records (before attempting delete)
        let count: u64 = conn.query_row(
            "SELECT COUNT(*) FROM decisions WHERE status = 'ACTIVE'",
            [],
            |row| row.get(0),
        )?;

        // Enforce floor constraint (fail-closed)
        if count <= self.retention_floor {
            return Err(StoreError::RetentionFloorViolation {
                floor: self.retention_floor,
                current: count,
            });
        }

        // Soft-delete: mark as REVOKED (preserves Merkle chain integrity)
        conn.execute(
            "UPDATE decisions SET status = 'REVOKED' WHERE id = ? AND status = 'ACTIVE'",
            rusqlite::params![id],
        )?;

        Ok(())
    }
}

pub fn fixture_decisions() -> Vec<DecisionRecord> {
    vec![
        DecisionRecord {
            category: "architecture".into(),
            context: "Local sovereignty requires zero cloud dependency".into(),
            decision: "Use rusqlite bundled for all local decision storage".into(),
        },
        DecisionRecord {
            category: "protocol".into(),
            context: "Unverified inputs can corrupt the decision chain".into(),
            decision: "Fail-closed: reject any record missing required fields".into(),
        },
        DecisionRecord {
            category: "scope".into(),
            context: "Phase DB-1 is foundation only; complexity added incrementally".into(),
            decision: "Phase DB-1 ships SQLite layer only; no vector store or cloud".into(),
        },
    ]
}
