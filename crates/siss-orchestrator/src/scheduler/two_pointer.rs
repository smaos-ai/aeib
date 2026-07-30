use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DispatchTask {
    pub task_id: Uuid,
    pub capsule_id: Uuid,
    pub agent_id: Uuid,
    pub symbol: String,
}

#[derive(Clone, Debug)]
pub enum DispatchError {
    NoReadyTasks,
    DependencyNotResolved { symbol: String },
    QueueEmpty,
}

pub struct TwoPointerScheduler {
    ready_queue: VecDeque<DispatchTask>,
    waiting_queue: HashMap<Uuid, Vec<DispatchTask>>,
    head: usize,
    tail: usize,
    resolved_symbols: std::collections::HashSet<String>,
    total_ops: u64,
}

impl TwoPointerScheduler {
    pub fn new() -> Self {
        Self {
            ready_queue: VecDeque::new(),
            waiting_queue: HashMap::new(),
            head: 0,
            tail: 0,
            resolved_symbols: std::collections::HashSet::new(),
            total_ops: 0,
        }
    }

    pub fn enqueue(&mut self, task: DispatchTask) {
        self.ready_queue.push_back(task);
        self.tail += 1;
    }

    pub fn dispatch_next(&mut self) -> Result<DispatchTask, DispatchError> {
        if self.ready_queue.is_empty() {
            return Err(DispatchError::NoReadyTasks);
        }

        let task = self
            .ready_queue
            .pop_front()
            .ok_or(DispatchError::QueueEmpty)?;
        self.head += 1;
        self.total_ops += 1;

        Ok(task)
    }

    pub fn resolve_dependency(
        &mut self,
        symbol: String,
        capsule_id: Uuid,
    ) -> Result<(), DispatchError> {
        self.resolved_symbols.insert(symbol.clone());
        self.total_ops += 1;

        if let Some(waiting_tasks) = self.waiting_queue.remove(&capsule_id) {
            for task in waiting_tasks {
                self.ready_queue.push_back(task);
                self.tail += 1;
            }
        }

        Ok(())
    }

    pub fn enqueue_waiting(&mut self, task: DispatchTask, capsule_id: Uuid) {
        self.waiting_queue
            .entry(capsule_id)
            .or_insert_with(Vec::new)
            .push(task);
    }

    pub fn is_symbol_resolved(&self, symbol: &str) -> bool {
        self.resolved_symbols.contains(symbol)
    }

    pub fn amortized_cost_per_op(&self) -> f64 {
        if self.total_ops == 0 {
            return 0.0;
        }
        (self.head + self.tail) as f64 / self.total_ops as f64
    }

    pub fn ready_queue_len(&self) -> usize {
        self.ready_queue.len()
    }

    pub fn waiting_queue_len(&self) -> usize {
        self.waiting_queue.len()
    }

    pub fn head_position(&self) -> usize {
        self.head
    }

    pub fn tail_position(&self) -> usize {
        self.tail
    }

    pub fn total_operations(&self) -> u64 {
        self.total_ops
    }
}

impl Default for TwoPointerScheduler {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dispatch_single_task() {
        let mut scheduler = TwoPointerScheduler::new();
        let task = DispatchTask {
            task_id: Uuid::new_v4(),
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            symbol: "test".to_string(),
        };
        scheduler.enqueue(task.clone());
        let dispatched = scheduler.dispatch_next().unwrap();
        assert_eq!(dispatched.task_id, task.task_id);
    }

    #[test]
    fn test_dispatch_empty_queue() {
        let mut scheduler = TwoPointerScheduler::new();
        assert!(matches!(
            scheduler.dispatch_next(),
            Err(DispatchError::NoReadyTasks)
        ));
    }

    #[test]
    fn test_resolve_dependency_moves_waiting_to_ready() {
        let mut scheduler = TwoPointerScheduler::new();
        let capsule_id = Uuid::new_v4();
        let task = DispatchTask {
            task_id: Uuid::new_v4(),
            capsule_id,
            agent_id: Uuid::new_v4(),
            symbol: "dep_task".to_string(),
        };
        scheduler.enqueue_waiting(task.clone(), capsule_id);
        assert_eq!(scheduler.waiting_queue_len(), 1);
        scheduler
            .resolve_dependency("symbol".to_string(), capsule_id)
            .unwrap();
        assert_eq!(scheduler.waiting_queue_len(), 0);
        assert_eq!(scheduler.ready_queue_len(), 1);
    }

    #[test]
    fn test_symbol_resolution_tracking() {
        let mut scheduler = TwoPointerScheduler::new();
        assert!(!scheduler.is_symbol_resolved("foo"));
        scheduler
            .resolve_dependency("foo".to_string(), Uuid::new_v4())
            .unwrap();
        assert!(scheduler.is_symbol_resolved("foo"));
    }

    #[test]
    fn test_amortized_cost_single_op() {
        let mut scheduler = TwoPointerScheduler::new();
        let task = DispatchTask {
            task_id: Uuid::new_v4(),
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            symbol: "test".to_string(),
        };
        scheduler.enqueue(task);
        let _ = scheduler.dispatch_next();
        let cost = scheduler.amortized_cost_per_op();
        assert!(cost <= 2.0);
    }

    #[test]
    fn test_amortized_cost_linear_operations() {
        let mut scheduler = TwoPointerScheduler::new();
        for i in 0..100 {
            let task = DispatchTask {
                task_id: Uuid::new_v4(),
                capsule_id: Uuid::new_v4(),
                agent_id: Uuid::new_v4(),
                symbol: format!("sym_{}", i),
            };
            scheduler.enqueue(task);
        }
        for _ in 0..100 {
            let _ = scheduler.dispatch_next();
        }
        let cost = scheduler.amortized_cost_per_op();
        assert!(cost <= 2.0);
    }

    #[test]
    fn test_head_tail_pointer_advancement() {
        let mut scheduler = TwoPointerScheduler::new();
        let task1 = DispatchTask {
            task_id: Uuid::new_v4(),
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            symbol: "t1".to_string(),
        };
        scheduler.enqueue(task1);
        assert_eq!(scheduler.head_position(), 0);
        assert_eq!(scheduler.tail_position(), 1);
        let _ = scheduler.dispatch_next();
        assert_eq!(scheduler.head_position(), 1);
    }

    #[test]
    fn test_multiple_tasks_fifo_order() {
        let mut scheduler = TwoPointerScheduler::new();
        let mut task_ids = vec![];
        for i in 0..5 {
            let id = Uuid::new_v4();
            task_ids.push(id);
            let task = DispatchTask {
                task_id: id,
                capsule_id: Uuid::new_v4(),
                agent_id: Uuid::new_v4(),
                symbol: format!("sym_{}", i),
            };
            scheduler.enqueue(task);
        }
        for expected_id in task_ids {
            let dispatched = scheduler.dispatch_next().unwrap();
            assert_eq!(dispatched.task_id, expected_id);
        }
    }

    #[test]
    fn test_resolve_dependency_with_multiple_waiting_tasks() {
        let mut scheduler = TwoPointerScheduler::new();
        let capsule_id = Uuid::new_v4();
        let mut task_ids = vec![];
        for i in 0..3 {
            let id = Uuid::new_v4();
            task_ids.push(id);
            let task = DispatchTask {
                task_id: id,
                capsule_id,
                agent_id: Uuid::new_v4(),
                symbol: format!("task_{}", i),
            };
            scheduler.enqueue_waiting(task, capsule_id);
        }
        scheduler
            .resolve_dependency("symbol".to_string(), capsule_id)
            .unwrap();
        assert_eq!(scheduler.ready_queue_len(), 3);
        for expected_id in task_ids {
            let dispatched = scheduler.dispatch_next().unwrap();
            assert_eq!(dispatched.task_id, expected_id);
        }
    }

    #[test]
    fn test_amortized_cost_with_mixed_operations() {
        let mut scheduler = TwoPointerScheduler::new();
        for i in 0..50 {
            let task = DispatchTask {
                task_id: Uuid::new_v4(),
                capsule_id: Uuid::new_v4(),
                agent_id: Uuid::new_v4(),
                symbol: format!("sym_{}", i),
            };
            scheduler.enqueue(task);
        }
        for i in 0..50 {
            let _ = scheduler.dispatch_next();
            if i % 10 == 0 {
                let _ = scheduler.resolve_dependency(format!("dep_{}", i), Uuid::new_v4());
            }
        }
        let cost = scheduler.amortized_cost_per_op();
        assert!(cost <= 2.0, "Amortized cost {} exceeds bound", cost);
    }
}
