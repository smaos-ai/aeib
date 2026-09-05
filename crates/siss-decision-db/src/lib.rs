pub mod db;
pub mod merkle;
pub mod schema;

pub use db::{DbError, Task, TaskDb, TaskStatus, TaskStream};

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
