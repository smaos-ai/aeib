/// Phase 51: Worktree Sandbox Membrane (Branch Exclusivity Proof)
/// Atomic allocation guard preventing two agents from occupying the same git branch.
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use uuid::Uuid;

/// Exclusive ownership token for a git branch.
/// NOT Clone — holding this token means the agent has exclusive access to the branch.
/// The only way to free the branch is via SandboxAllocator::release(sandbox).
#[derive(Debug)]
pub struct WorktreeSandbox {
    pub agent_id: Uuid,
    pub branch: String,
    pub worktree_path: String,
}

#[derive(Debug, PartialEq, Eq)]
pub enum SandboxError {
    BranchAlreadyAllocated { branch: String, held_by: Uuid },
}

pub struct SandboxAllocator {
    allocated: Arc<Mutex<HashMap<String, Uuid>>>,
}

impl SandboxAllocator {
    pub fn new() -> Self {
        SandboxAllocator {
            allocated: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// RULE 1: branch already in map → Err(BranchAlreadyAllocated { branch, held_by })
    /// RULE 2: Insert (branch → agent_id) atomically under Mutex lock
    /// RULE 3: Return Ok(WorktreeSandbox { agent_id, branch, worktree_path })
    pub fn allocate(
        &self,
        agent_id: Uuid,
        branch: &str,
        worktree_path: &str,
    ) -> Result<WorktreeSandbox, SandboxError> {
        let mut map = self.allocated.lock().unwrap();

        if let Some(&held_by) = map.get(branch) {
            return Err(SandboxError::BranchAlreadyAllocated {
                branch: branch.to_string(),
                held_by,
            });
        }

        map.insert(branch.to_string(), agent_id);

        Ok(WorktreeSandbox {
            agent_id,
            branch: branch.to_string(),
            worktree_path: worktree_path.to_string(),
        })
    }

    /// Removes branch from allocation map — next allocate() call for this branch will succeed.
    pub fn release(&self, sandbox: WorktreeSandbox) {
        let mut map = self.allocated.lock().unwrap();
        map.remove(&sandbox.branch);
    }

    pub fn is_allocated(&self, branch: &str) -> bool {
        let map = self.allocated.lock().unwrap();
        map.contains_key(branch)
    }
}

impl Default for SandboxAllocator {
    fn default() -> Self {
        Self::new()
    }
}
