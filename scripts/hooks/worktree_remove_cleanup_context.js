#!/usr/bin/env node
/**
 * Phase 27: WorktreeRemove Dispatcher Cleanup
 *
 * Cleans up dispatcher metadata when a worktree is removed.
 * Cleanup actions:
 * - Deregister agent from active agents
 * - Remove agent context files
 * - Release protected file locks
 * - Archive task completion metadata
 * - Signal task completion to queue
 *
 * Input: JSON on stdin with { worktree_path, worktree_name, action }
 * Output: JSON to stdout with { status, cleaned_up_files, context_archived }
 * Exit Code: 0 on success
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

// ============================================================================
// Configuration
// ============================================================================

const AGENT_CONTEXT_DIR = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'agent_context'
);

const AGENT_ARCHIVE_DIR = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'agent_archive'
);

const DISPATCHER_STATE_FILE = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'dispatcher_state.json'
);

const TASK_QUEUE_FILE = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'task_queue.json'
);

const CURRENT_AGENT_ID = process.env.AGENT_ID || 'unknown-agent';
const DISPATCHER_ENABLED = process.env.DISPATCHER_ACTIVE === 'true';

// ============================================================================
// Utilities
// ============================================================================

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function readDispatcherState() {
  try {
    if (!fs.existsSync(DISPATCHER_STATE_FILE)) {
      return null;
    }
    const content = fs.readFileSync(DISPATCHER_STATE_FILE, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    console.error(`[WORKTREE_REMOVE] Failed to read state file: ${error.message}`);
    return null;
  }
}

function writeDispatcherState(state) {
  try {
    ensureDir(path.dirname(DISPATCHER_STATE_FILE));
    fs.writeFileSync(DISPATCHER_STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error(`[WORKTREE_REMOVE] Failed to write state file: ${error.message}`);
    return false;
  }
}

function readTaskQueue() {
  try {
    if (!fs.existsSync(TASK_QUEUE_FILE)) {
      return { tasks: [], in_progress: [] };
    }
    const content = fs.readFileSync(TASK_QUEUE_FILE, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    console.error(`[WORKTREE_REMOVE] Failed to read task queue: ${error.message}`);
    return { tasks: [], in_progress: [] };
  }
}

function writeTaskQueue(queue) {
  try {
    ensureDir(path.dirname(TASK_QUEUE_FILE));
    fs.writeFileSync(TASK_QUEUE_FILE, JSON.stringify(queue, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error(`[WORKTREE_REMOVE] Failed to write task queue: ${error.message}`);
    return false;
  }
}

// ============================================================================
// Cleanup Logic
// ============================================================================

function deregisterAgent(state) {
  if (!state || !state.active_agents) {
    return 0;
  }

  const previousLength = state.active_agents.length;
  state.active_agents = state.active_agents.filter(a => a.agent_id !== CURRENT_AGENT_ID);

  return previousLength - state.active_agents.length;
}

function archiveAgentContext() {
  try {
    const contextFile = path.join(AGENT_CONTEXT_DIR, `${CURRENT_AGENT_ID}.json`);

    if (!fs.existsSync(contextFile)) {
      return { archived: false, reason: 'Context file not found' };
    }

    // Read the context
    const content = fs.readFileSync(contextFile, 'utf-8');
    const context = JSON.parse(content);

    // Archive it with timestamp
    ensureDir(AGENT_ARCHIVE_DIR);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const archiveFile = path.join(AGENT_ARCHIVE_DIR, `${CURRENT_AGENT_ID}-${timestamp}.json`);

    context.archived_at = new Date().toISOString();
    fs.writeFileSync(archiveFile, JSON.stringify(context, null, 2), 'utf-8');

    // Remove original
    fs.unlinkSync(contextFile);

    return {
      archived: true,
      archive_file: archiveFile,
    };
  } catch (error) {
    console.error(`[WORKTREE_REMOVE] Failed to archive context: ${error.message}`);
    return { archived: false, error: error.message };
  }
}

function releaseProtectedFiles(state) {
  if (!state || !state.protected_file_sets) {
    return 0;
  }

  if (state.protected_file_sets[CURRENT_AGENT_ID]) {
    const fileCount = state.protected_file_sets[CURRENT_AGENT_ID].length;
    delete state.protected_file_sets[CURRENT_AGENT_ID];
    return fileCount;
  }

  return 0;
}

function archiveTaskCompletion(queue) {
  const inProgress = queue.in_progress || [];
  const taskIndex = inProgress.findIndex(t => t.agent_id === CURRENT_AGENT_ID);

  if (taskIndex === -1) {
    return { archived: false, reason: 'No active task found' };
  }

  const task = inProgress[taskIndex];

  // Mark as completed if not already
  if (task.status !== 'completed') {
    task.status = 'completed';
    task.completed_at = new Date().toISOString();
  }

  // Move to completed tasks if we track them
  if (!queue.completed) {
    queue.completed = [];
  }

  queue.completed.push({
    ...task,
    archived_at: new Date().toISOString(),
  });

  // Remove from in_progress
  queue.in_progress.splice(taskIndex, 1);

  return {
    archived: true,
    task_id: task.task_id,
  };
}

// ============================================================================
// Main Cleanup Orchestration
// ============================================================================

function cleanupWorktreeContext(worktreeData) {
  // If dispatcher is not enabled, skip cleanup
  if (!DISPATCHER_ENABLED) {
    return {
      status: 'skipped',
      reason: 'Dispatcher not active',
    };
  }

  const result = {
    status: 'cleaned',
    cleaned_items: {},
  };

  // 1. Read current state
  const state = readDispatcherState();
  const queue = readTaskQueue();

  // 2. Deregister agent from active agents
  if (state) {
    const deregistered = deregisterAgent(state);
    result.cleaned_items.agents_deregistered = deregistered;
  }

  // 3. Release protected files
  if (state) {
    const filesReleased = releaseProtectedFiles(state);
    result.cleaned_items.files_released = filesReleased;
  }

  // 4. Archive agent context
  const archiveResult = archiveAgentContext();
  result.context_archived = archiveResult.archived;
  if (archiveResult.archive_file) {
    result.cleaned_items.archive_file = archiveResult.archive_file;
  }

  // 5. Archive task if active
  const taskResult = archiveTaskCompletion(queue);
  result.cleaned_items.task_archived = taskResult.archived;
  if (taskResult.task_id) {
    result.cleaned_items.archived_task_id = taskResult.task_id;
  }

  // 6. Persist state changes
  if (state) {
    writeDispatcherState(state);
  }
  writeTaskQueue(queue);

  result.state_persisted = true;

  return result;
}

// ============================================================================
// Entry Point
// ============================================================================

async function main() {
  return new Promise((resolve, reject) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: false,
    });

    let inputBuffer = '';

    rl.on('line', (line) => {
      inputBuffer += line;
    });

    rl.on('close', () => {
      try {
        const worktreeData = JSON.parse(inputBuffer);
        const result = cleanupWorktreeContext(worktreeData);

        console.log(JSON.stringify(result));
        process.exit(0);
      } catch (error) {
        const errorResponse = {
          status: 'error',
          message: error instanceof Error ? error.message : String(error),
        };
        console.log(JSON.stringify(errorResponse));
        process.exit(0);
      }

      resolve();
    });

    rl.on('error', (error) => {
      reject(error);
    });
  });
}

main().catch((error) => {
  console.error('Fatal error in worktree remove hook:', error);
  process.exit(0);
});
