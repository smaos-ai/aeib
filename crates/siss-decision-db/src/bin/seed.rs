use chrono::Utc;
use siss_decision_db::{Task, TaskDb, TaskStatus, TaskStream};
use std::fs;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db_path = ".smaos/tasks.db";

    fs::create_dir_all(".smaos")?;

    let db = TaskDb::new(db_path)?;

    let seed_tasks = vec![
        Task {
            id: "IL-01".to_string(),
            title: "Israel Trip: Zysman Law Patent Meeting".to_string(),
            status: TaskStatus::InProgress,
            stream: TaskStream::StreamC,
            priority: 10,
            assignee: Some("Andrii".to_string()),
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        },
        Task {
            id: "IL-02".to_string(),
            title: "Israel Trip: Defense Ministry Demo".to_string(),
            status: TaskStatus::InProgress,
            stream: TaskStream::StreamC,
            priority: 10,
            assignee: Some("Andrii".to_string()),
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        },
        Task {
            id: "DB-1".to_string(),
            title: "Rebuild DECISION-DB with persistent tasks.db".to_string(),
            status: TaskStatus::InProgress,
            stream: TaskStream::StreamB,
            priority: 9,
            assignee: Some("Agent B".to_string()),
            created_at: Utc::now().to_rfc3339(),
            updated_at: Utc::now().to_rfc3339(),
        },
    ];

    for task in seed_tasks {
        db.create_task(task)?;
    }

    println!("✓ Seeded 3 tasks to {}", db_path);
    Ok(())
}
