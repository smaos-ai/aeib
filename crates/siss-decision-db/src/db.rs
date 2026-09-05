use chrono::Utc;
use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum DbError {
    #[error("SQLite error: {0}")]
    Sqlite(String),
    #[error("Task not found: {0}")]
    NotFound(String),
    #[error("Chain integrity violation: {0}")]
    ChainIntegrityViolation(String),
}

impl From<rusqlite::Error> for DbError {
    fn from(err: rusqlite::Error) -> Self {
        DbError::Sqlite(err.to_string())
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum TaskStatus {
    Pending,
    InProgress,
    Completed,
    Archived,
}

impl TaskStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            TaskStatus::Pending => "pending",
            TaskStatus::InProgress => "in_progress",
            TaskStatus::Completed => "completed",
            TaskStatus::Archived => "archived",
        }
    }
}

impl std::str::FromStr for TaskStatus {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "pending" => Ok(TaskStatus::Pending),
            "in_progress" => Ok(TaskStatus::InProgress),
            "completed" => Ok(TaskStatus::Completed),
            "archived" => Ok(TaskStatus::Archived),
            _ => Err(format!("Unknown status: {}", s)),
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum TaskStream {
    StreamA,
    StreamB,
    StreamC,
}

impl TaskStream {
    pub fn as_str(&self) -> &'static str {
        match self {
            TaskStream::StreamA => "stream_a",
            TaskStream::StreamB => "stream_b",
            TaskStream::StreamC => "stream_c",
        }
    }
}

impl std::str::FromStr for TaskStream {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "stream_a" => Ok(TaskStream::StreamA),
            "stream_b" => Ok(TaskStream::StreamB),
            "stream_c" => Ok(TaskStream::StreamC),
            _ => Err(format!("Unknown stream: {}", s)),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: String,
    pub title: String,
    pub status: TaskStatus,
    pub stream: TaskStream,
    pub priority: u32,
    pub assignee: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

pub struct TaskDb {
    pub(crate) conn: Mutex<Connection>,
}

impl TaskDb {
    pub fn new(db_path: &str) -> Result<Self, DbError> {
        let conn = Connection::open(db_path)?;
        conn.execute_batch(crate::schema::SCHEMA_DDL)?;
        Ok(TaskDb {
            conn: Mutex::new(conn),
        })
    }

    pub fn create_task(&self, task: Task) -> Result<(), DbError> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO tasks (id, title, status, stream, priority, assignee, created_at, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                &task.id,
                &task.title,
                task.status.as_str(),
                task.stream.as_str(),
                task.priority,
                &task.assignee,
                &task.created_at,
                &task.updated_at,
            ],
        )?;
        Ok(())
    }

    pub fn update_task_status(&self, task_id: &str, status: TaskStatus) -> Result<(), DbError> {
        let conn = self.conn.lock().unwrap();
        let rows = conn.execute(
            "UPDATE tasks SET status = ?1, updated_at = ?2 WHERE id = ?3",
            params![status.as_str(), Utc::now().to_rfc3339(), task_id],
        )?;
        if rows == 0 {
            return Err(DbError::NotFound(task_id.to_string()));
        }
        Ok(())
    }

    pub fn list_pending(&self) -> Result<Vec<Task>, DbError> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, title, status, stream, priority, assignee, created_at, updated_at
             FROM tasks WHERE status = 'pending' ORDER BY priority DESC",
        )?;
        let tasks = stmt.query_map([], |row| {
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                status: row.get::<_, String>(2)?.parse().unwrap(),
                stream: row.get::<_, String>(3)?.parse().unwrap(),
                priority: row.get(4)?,
                assignee: row.get(5)?,
                created_at: row.get(6)?,
                updated_at: row.get(7)?,
            })
        })?;
        let mut result = vec![];
        for task in tasks {
            result.push(task?);
        }
        Ok(result)
    }

    pub fn list_by_stream(&self, stream: TaskStream) -> Result<Vec<Task>, DbError> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, title, status, stream, priority, assignee, created_at, updated_at
             FROM tasks WHERE stream = ?1 ORDER BY priority DESC",
        )?;
        let tasks = stmt.query_map(params![stream.as_str()], |row| {
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                status: row.get::<_, String>(2)?.parse().unwrap(),
                stream: row.get::<_, String>(3)?.parse().unwrap(),
                priority: row.get(4)?,
                assignee: row.get(5)?,
                created_at: row.get(6)?,
                updated_at: row.get(7)?,
            })
        })?;
        let mut result = vec![];
        for task in tasks {
            result.push(task?);
        }
        Ok(result)
    }

    pub fn list_by_priority(&self) -> Result<Vec<Task>, DbError> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, title, status, stream, priority, assignee, created_at, updated_at
             FROM tasks ORDER BY priority DESC, created_at ASC",
        )?;
        let tasks = stmt.query_map([], |row| {
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                status: row.get::<_, String>(2)?.parse().unwrap(),
                stream: row.get::<_, String>(3)?.parse().unwrap(),
                priority: row.get(4)?,
                assignee: row.get(5)?,
                created_at: row.get(6)?,
                updated_at: row.get(7)?,
            })
        })?;
        let mut result = vec![];
        for task in tasks {
            result.push(task?);
        }
        Ok(result)
    }

    pub fn get_merkle_root(&self) -> Result<Option<String>, DbError> {
        let conn = self.conn.lock().unwrap();
        let mut stmt =
            conn.prepare("SELECT merkle_hash FROM decisions ORDER BY rowid DESC LIMIT 1")?;
        let hash = stmt.query_row([], |row| row.get::<_, String>(0));
        match hash {
            Ok(h) => Ok(Some(h)),
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(DbError::Sqlite(e.to_string())),
        }
    }

    pub fn verify_chain(&self) -> Result<(), DbError> {
        let conn = self.conn.lock().unwrap();
        let mut stmt =
            conn.prepare("SELECT merkle_hash, body FROM decisions ORDER BY rowid ASC")?;
        let entries: Vec<(String, String)> = stmt
            .query_map([], |row| Ok((row.get(0)?, row.get(1)?)))?
            .collect::<Result<Vec<_>, _>>()?;

        crate::merkle::verify_chain(&entries).map_err(DbError::ChainIntegrityViolation)
    }

    pub fn archive_task(&self, task_id: &str) -> Result<(), DbError> {
        self.update_task_status(task_id, TaskStatus::Archived)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use uuid::Uuid;

    fn setup_test_db() -> (TaskDb, String) {
        let _ = fs::create_dir_all(".smaos");
        let path = format!(".smaos/test-{}.db", Uuid::new_v4());
        let db = TaskDb::new(&path).unwrap();
        (db, path)
    }

    #[test]
    fn test_create_task() {
        let (db, _path) = setup_test_db();
        let task = Task {
            id: Uuid::new_v4().to_string(),
            title: "Test Task".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamA,
            priority: 1,
            assignee: Some("Alice".to_string()),
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        assert!(db.create_task(task.clone()).is_ok());
    }

    #[test]
    fn test_update_task_status() {
        let (db, _path) = setup_test_db();
        let task_id = Uuid::new_v4().to_string();
        let task = Task {
            id: task_id.clone(),
            title: "Test".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamB,
            priority: 2,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        db.create_task(task).unwrap();
        assert!(
            db.update_task_status(&task_id, TaskStatus::InProgress)
                .is_ok()
        );
    }

    #[test]
    fn test_list_pending() {
        let (db, _path) = setup_test_db();
        let task1 = Task {
            id: Uuid::new_v4().to_string(),
            title: "Task 1".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamA,
            priority: 1,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        let task2 = Task {
            id: Uuid::new_v4().to_string(),
            title: "Task 2".to_string(),
            status: TaskStatus::Completed,
            stream: TaskStream::StreamB,
            priority: 2,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        db.create_task(task1).unwrap();
        db.create_task(task2).unwrap();
        let pending = db.list_pending().unwrap();
        assert_eq!(pending.len(), 1);
        assert_eq!(pending[0].status, TaskStatus::Pending);
    }

    #[test]
    fn test_list_by_stream() {
        let (db, _path) = setup_test_db();
        let task = Task {
            id: Uuid::new_v4().to_string(),
            title: "Stream Task".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamC,
            priority: 3,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        db.create_task(task).unwrap();
        let stream_c = db.list_by_stream(TaskStream::StreamC).unwrap();
        assert_eq!(stream_c.len(), 1);
    }

    #[test]
    fn test_list_by_priority() {
        let (db, _path) = setup_test_db();
        let high = Task {
            id: Uuid::new_v4().to_string(),
            title: "High Priority".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamA,
            priority: 10,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        let low = Task {
            id: Uuid::new_v4().to_string(),
            title: "Low Priority".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamA,
            priority: 1,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        db.create_task(high).unwrap();
        db.create_task(low).unwrap();
        let ordered = db.list_by_priority().unwrap();
        assert_eq!(ordered[0].priority, 10);
        assert_eq!(ordered[1].priority, 1);
    }

    #[test]
    fn test_merkle_hash_computation() {
        let hash1 = crate::merkle::compute_hash("0", "content1");
        let hash2 = crate::merkle::compute_hash(&hash1, "content2");
        assert_ne!(hash1, hash2);
        assert_eq!(hash1.len(), 64);
        assert_eq!(hash2.len(), 64);
    }

    #[test]
    fn test_merkle_chain_verification() {
        let mut hash = "0".to_string();
        let mut entries = vec![];
        for i in 0..5 {
            let content = format!("entry_{}", i);
            hash = crate::merkle::compute_hash(&hash, &content);
            entries.push((hash.clone(), content));
        }
        assert!(crate::merkle::verify_chain(&entries).is_ok());
    }

    #[test]
    fn test_merkle_chain_tampering_detection() {
        let hash1 = crate::merkle::compute_hash("0", "original");
        let hash2 = crate::merkle::compute_hash(&hash1, "content2");
        let mut entries = vec![
            (hash1.clone(), "original".to_string()),
            (hash2.clone(), "content2".to_string()),
        ];
        entries[0].1 = "tampered".to_string();
        assert!(crate::merkle::verify_chain(&entries).is_err());
    }

    #[test]
    fn test_archive_task() {
        let (db, _path) = setup_test_db();
        let task_id = Uuid::new_v4().to_string();
        let task = Task {
            id: task_id.clone(),
            title: "Archive Test".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamA,
            priority: 1,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        db.create_task(task).unwrap();
        assert!(db.archive_task(&task_id).is_ok());
    }

    #[test]
    fn test_concurrent_writes() {
        let (db, _path) = setup_test_db();
        let db = std::sync::Arc::new(db);
        let handles: Vec<_> = (0..5)
            .map(|i| {
                let db_clone = db.clone();
                std::thread::spawn(move || {
                    let task = Task {
                        id: Uuid::new_v4().to_string(),
                        title: format!("Concurrent Task {}", i),
                        status: TaskStatus::Pending,
                        stream: TaskStream::StreamA,
                        priority: i,
                        assignee: None,
                        created_at: Utc::now().to_rfc3339(),
                        updated_at: Utc::now().to_rfc3339(),
                    };
                    db_clone.create_task(task)
                })
            })
            .collect();

        for handle in handles {
            assert!(handle.join().unwrap().is_ok());
        }
    }

    #[test]
    fn test_status_transitions() {
        let (db, _path) = setup_test_db();
        let task_id = Uuid::new_v4().to_string();
        let task = Task {
            id: task_id.clone(),
            title: "Transition Test".to_string(),
            status: TaskStatus::Pending,
            stream: TaskStream::StreamB,
            priority: 1,
            assignee: None,
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        };
        db.create_task(task).unwrap();

        assert!(
            db.update_task_status(&task_id, TaskStatus::InProgress)
                .is_ok()
        );
        assert!(
            db.update_task_status(&task_id, TaskStatus::Completed)
                .is_ok()
        );
        assert!(db.archive_task(&task_id).is_ok());
    }

    #[test]
    fn test_update_nonexistent_task_fails() {
        let (db, _path) = setup_test_db();
        let nonexistent_id = "nonexistent-task-id";
        let result = db.update_task_status(nonexistent_id, TaskStatus::InProgress);
        assert!(matches!(result, Err(DbError::NotFound(_))));
    }
}
