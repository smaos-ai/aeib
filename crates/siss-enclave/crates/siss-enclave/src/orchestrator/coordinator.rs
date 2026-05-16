use crate::memory::ZonalMemory;
use crate::swarm::RecursiveMasDispatcher;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TaskCategory {
    Summarize,
    Classify,
    Extract,
}

impl TaskCategory {
    pub fn primary_skill(&self) -> &'static str {
        match self {
            TaskCategory::Summarize => "summarize",
            TaskCategory::Classify => "classify",
            TaskCategory::Extract => "extract",
        }
    }
}

struct TaskMetadata {
    category: TaskCategory,
    current_skill_index: usize,
    created_at: std::time::Instant,
}

pub struct Coordinator {
    dispatcher: Arc<RecursiveMasDispatcher>,
    zonal_memory: Arc<ZonalMemory>,
    fallback_chains: Arc<RwLock<HashMap<TaskCategory, Vec<String>>>>,
    task_metadata: Arc<RwLock<HashMap<Uuid, TaskMetadata>>>,
}

impl Coordinator {
    pub fn new(
        dispatcher: Arc<RecursiveMasDispatcher>,
        zonal_memory: Arc<ZonalMemory>,
    ) -> Self {
        let mut chains = HashMap::new();

        chains.insert(
            TaskCategory::Summarize,
            vec!["summarize".to_string(), "fallback_test".to_string(), "fallback_retry".to_string()],
        );
        chains.insert(
            TaskCategory::Classify,
            vec!["classify".to_string()],
        );
        chains.insert(
            TaskCategory::Extract,
            vec!["extract".to_string()],
        );

        Self {
            dispatcher,
            zonal_memory,
            fallback_chains: Arc::new(RwLock::new(chains)),
            task_metadata: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn category_to_skill(&self, category: TaskCategory) -> &'static str {
        category.primary_skill()
    }

    pub async fn register_fallback_chain(
        &self,
        category: TaskCategory,
        chain: Vec<String>,
    ) {
        let mut chains = self.fallback_chains.write().await;
        chains.insert(category, chain);
    }

    pub async fn dispatch_with_fallback(
        &self,
        category: TaskCategory,
        context_refs: Vec<Uuid>,
        token_budget: i64,
    ) -> Uuid {
        let task_id = Uuid::new_v4();
        let chains = self.fallback_chains.read().await;
        let chain = chains
            .get(&category)
            .cloned()
            .unwrap_or_else(|| vec![category.primary_skill().to_string()]);
        drop(chains);

        let mut metadata = self.task_metadata.write().await;
        metadata.insert(
            task_id,
            TaskMetadata {
                category,
                current_skill_index: 0,
                created_at: std::time::Instant::now(),
            },
        );
        drop(metadata);

        let dispatcher = Arc::clone(&self.dispatcher);
        let zonal = Arc::clone(&self.zonal_memory);
        let metadata_map = Arc::clone(&self.task_metadata);
        let chain_clone = chain.clone();

        tokio::spawn(async move {
            let mut attempt = 0;
            let max_attempts = chain_clone.len();

            loop {
                if attempt >= max_attempts {
                    break;
                }

                let skill_id = &chain_clone[attempt];
                let result = dispatcher
                    .dispatch(skill_id, context_refs.clone(), token_budget)
                    .await;

                match result {
                    Ok(_worker_task_id) => {
                        let mut metadata = metadata_map.write().await;
                        if let Some(meta) = metadata.get_mut(&task_id) {
                            meta.current_skill_index = attempt;
                        }
                        drop(metadata);
                        break;
                    }
                    Err(_) => {
                        attempt += 1;
                        if attempt >= max_attempts {
                            break;
                        }
                    }
                }
            }

            let _ = zonal.fog_snapshot();
        });

        task_id
    }

    pub async fn aggregate_results(&self, task_ids: Vec<Uuid>) -> Vec<Uuid> {
        let snapshot = self.zonal_memory.fog_snapshot();
        snapshot
            .layers
            .values()
            .flat_map(|entries| entries.iter())
            .map(|e| e.id)
            .take(task_ids.len())
            .collect()
    }
}
