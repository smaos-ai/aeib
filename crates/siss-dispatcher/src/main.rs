use clap::{Parser, Subcommand};
use chrono::Utc;
use siss_dispatcher::types::{ExecutorConfig, Task, TaskStatus};
use siss_dispatcher::Executor;
use std::path::PathBuf;
use uuid::Uuid;

#[derive(Parser)]
#[command(name = "dispatcher")]
#[command(about = "Multi-worktree task dispatcher", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    #[arg(global = true, long, default_value = ".dispatcher/config.json")]
    config: PathBuf,
}

#[derive(Subcommand)]
enum Commands {
    /// Spawn N concurrent agents
    Spawn {
        #[arg(value_name = "COUNT")]
        count: u32,
    },

    /// Add task to queue
    QueueAdd {
        /// Task specification as JSON
        #[arg(value_name = "TASK_JSON")]
        task_json: String,
    },

    /// Show all agent and task statuses
    Status,

    /// Orchestrate merge of completed tasks
    Merge,

    /// Run dispatch loop until completion
    Run,

    /// Cleanup all agent worktrees
    Cleanup,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let cli = Cli::parse();

    // Load or create config
    let config = if cli.config.exists() {
        let content = std::fs::read_to_string(&cli.config)?;
        serde_json::from_str(&content)?
    } else {
        ExecutorConfig::default()
    };

    let mut executor = Executor::new(config).await?;

    match cli.command {
        Commands::Spawn { count } => {
            let agents = executor.spawn_agents(count).await?;
            println!("Spawned {} agents:", agents.len());
            for agent in agents {
                println!(
                    "  Agent {} [{}]: {}",
                    agent.index, agent.id, agent.status as u8
                );
            }
        }

        Commands::QueueAdd { task_json } => {
            let task_spec: serde_json::Value =
                serde_json::from_str(&task_json)?;

            let task = Task {
                id: Uuid::new_v4(),
                name: task_spec
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("unnamed")
                    .to_string(),
                description: task_spec
                    .get("description")
                    .and_then(|v| v.as_str())
                    .map(String::from),
                specification: task_spec,
                status: TaskStatus::Pending,
                assigned_to: None,
                retry_count: 0,
                created_at: Utc::now(),
                started_at: None,
                completed_at: None,
                dependencies: vec![],
            };

            executor.queue_task(task.clone()).await?;
            println!("Added task {} to queue", task.id);
        }

        Commands::Status => {
            let (pending, in_progress, completed) =
                executor.queue_status();

            println!("Queue Status:");
            println!("  Pending: {}", pending);
            println!("  In Progress: {}", in_progress);
            println!("  Completed: {}", completed);

            println!("\nAgent Status:");
            let agents = executor.agents_status();
            for agent in agents {
                println!(
                    "  Agent {} [index={}]: {:?}",
                    agent.id, agent.index, agent.status
                );
                if let Some(task_id) = agent.assigned_task {
                    println!("    Assigned task: {}", task_id);
                }
                if let Some(path) = agent.worktree_path {
                    println!("    Worktree: {}", path);
                }
            }
        }

        Commands::Merge => {
            let results = executor.merge_completed_tasks().await?;

            println!("Merge Results:");
            for result in results {
                println!(
                    "  Task {}: {}",
                    result.task_id,
                    if result.success { "SUCCESS" } else { "FAILED" }
                );
                if !result.conflicts.is_empty() {
                    println!("    Conflicts: {:?}", result.conflicts);
                }
                if let Some(error) = result.error {
                    println!("    Error: {}", error);
                }
            }
        }

        Commands::Run => {
            println!("Starting dispatch loop...");
            executor.run_loop(None).await?;
            println!("Dispatch complete");
        }

        Commands::Cleanup => {
            executor.cleanup_agents().await?;
            println!("Cleanup complete");
        }
    }

    Ok(())
}
