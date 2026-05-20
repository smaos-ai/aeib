#!/usr/bin/env node
/**
 * Phase 27: PostToolUse Dispatcher Report
 *
 * Reports tool execution results to the dispatcher.
 * Responsibilities:
 * - Track tool execution completion
 * - Update current task progress
 * - Check if task is complete and trigger next in queue
 * - Report state changes back to dispatcher
 *
 * Input: JSON on stdin with { tool_name, tool_use_id, output, execution_time_ms, error }
 * Output: JSON to stdout with { status, nextTask?, taskComplete? }
 * Exit Code: 0 on success
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

// ============================================================================
// Configuration
// ============================================================================

const TASK_QUEUE_FILE = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'task_queue.json'
);

const DISPATCHER_STATE_FILE = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'dispatcher_state.json'
);

const AGENT_CONTEXT_DIR = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'agent_context'
);

const DISPATCHER_ENABLED = process.env.DISPATCHER_ACTIVE === 'true';
const CURRENT_AGENT_ID = process.env.AGENT_ID || 'manual-agent';

// ============================================================================
// File I/O Utilities
// ============================================================================

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
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
    console.error(`[DISPATCHER_REPORT] Failed to read task queue: ${error.message}`);
    return { tasks: [], in_progress: [] };
  }
}

function writeTaskQueue(queue) {
  try {
    ensureDir(path.dirname(TASK_QUEUE_FILE));
    fs.writeFileSync(TASK_QUEUE_FILE, JSON.stringify(queue, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error(`[DISPATCHER_REPORT] Failed to write task queue: ${error.message}`);
    return false;
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
    console.error(`[DISPATCHER_REPORT] Failed to read state file: ${error.message}`);
    return null;
  }
}

function writeDispatcherState(state) {
  try {
    ensureDir(path.dirname(DISPATCHER_STATE_FILE));
    fs.writeFileSync(DISPATCHER_STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error(`[DISPATCHER_REPORT] Failed to write state file: ${error.message}`);
    return false;
  }
}

// ============================================================================
// Task Progress Tracking
// ============================================================================

function getCurrentTask(queue) {
  const inProgress = queue.in_progress || [];
  return inProgress.find(task => task.agent_id === CURRENT_AGENT_ID);
}

function recordToolExecution(currentTask, toolExecution) {
  if (!currentTask) return null;

  // Initialize execution log if needed
  if (!currentTask.executions) {
    currentTask.executions = [];
  }

  // Record this tool execution
  const execution = {
    timestamp: new Date().toISOString(),
    tool_name: toolExecution.tool_name,
    tool_use_id: toolExecution.tool_use_id,
    execution_time_ms: toolExecution.execution_time_ms,
    has_error: !!toolExecution.error,
  };

  currentTask.executions.push(execution);

  // Update last execution time
  currentTask.last_execution_at = execution.timestamp;

  return currentTask;
}

function checkIfTaskComplete(currentTask) {
  if (!currentTask) return false;

  // Task is complete if it has a completion_signal or all sub-tasks are done
  if (currentTask.completion_signal) {
    return true;
  }

  if (currentTask.subtasks) {
    return currentTask.subtasks.every(st => st.completed);
  }

  return false;
}

function promoteNextTask(queue) {
  if (!queue.tasks || queue.tasks.length === 0) {
    return null;
  }

  // Take the first pending task and move it to in_progress
  const nextTask = queue.tasks.shift();
  nextTask.agent_id = CURRENT_AGENT_ID;
  nextTask.started_at = new Date().toISOString();

  if (!queue.in_progress) {
    queue.in_progress = [];
  }
  queue.in_progress.push(nextTask);

  return nextTask;
}

// ============================================================================
// Report Logic
// ============================================================================

function reportToolExecution(toolExecution) {
  // If dispatcher is not enabled, skip reporting
  if (!DISPATCHER_ENABLED) {
    return {
      status: 'skipped',
      reason: 'Dispatcher not active',
    };
  }

  // Read current queue and state
  const queue = readTaskQueue();
  const state = readDispatcherState();

  const currentTask = getCurrentTask(queue);

  if (!currentTask) {
    return {
      status: 'no_active_task',
      warning: 'Tool executed but no active task found',
    };
  }

  // Record this tool execution in the task
  const updatedTask = recordToolExecution(currentTask, toolExecution);

  // Check if the task is now complete
  const isTaskComplete = checkIfTaskComplete(updatedTask);

  let result = {
    status: 'reported',
    task_id: currentTask.task_id,
    execution_count: updatedTask.executions.length,
  };

  if (isTaskComplete) {
    // Mark task as completed
    updatedTask.completed_at = new Date().toISOString();
    updatedTask.status = 'completed';

    // Remove from in_progress
    queue.in_progress = queue.in_progress.filter(t => t.task_id !== currentTask.task_id);

    result.taskComplete = true;
    result.completedTask = currentTask.task_id;

    // Try to promote next task
    const nextTask = promoteNextTask(queue);

    if (nextTask) {
      result.nextTask = {
        task_id: nextTask.task_id,
        description: nextTask.description,
        agent_id: CURRENT_AGENT_ID,
      };
    } else if (queue.tasks.length === 0 && queue.in_progress.length === 0) {
      // All tasks complete
      result.allTasksComplete = true;

      if (state) {
        state.auto_dispatch_running = false;
        state.dispatch_completed_at = new Date().toISOString();
        writeDispatcherState(state);
      }
    }
  }

  // Persist updated queue
  const writeSuccess = writeTaskQueue(queue);
  result.queuePersisted = writeSuccess;

  return result;
}

// ============================================================================
// Main Entry Point
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
        const request = JSON.parse(inputBuffer);
        const result = reportToolExecution(request);

        console.log(JSON.stringify(result));
        process.exit(0);
      } catch (error) {
        const errorResponse = {
          status: 'error',
          message: error instanceof Error ? error.message : String(error),
        };
        console.log(JSON.stringify(errorResponse));
        process.exit(0); // Always exit 0 to not block tool flow
      }

      resolve();
    });

    rl.on('error', (error) => {
      reject(error);
    });
  });
}

main().catch((error) => {
  console.error('Fatal error in dispatcher report:', error);
  process.exit(0);
});
