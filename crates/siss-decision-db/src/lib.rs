pub mod schema;
pub mod merkle;
pub mod db;

pub use db::{TaskDb, TaskStatus, TaskStream, Task, DbError};

#[derive(Debug)]
pub struct TaskDbConfig {
    pub db_path: String,
}

impl Default for TaskDbConfig {
    fn default() -> Self {
        Self {
            db_path: ".smaos/tasks.db".to_string(),
        }
    }
}
