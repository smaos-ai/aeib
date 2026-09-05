#!/usr/bin/env node
/**
 * Phase 27: PreToolUse Dispatcher Gate
 *
 * Intercepts tool calls when dispatcher is active.
 * Checks:
 * - If auto-dispatch is running, gate manual tool use (advisory only)
 * - Block conflicting writes during merge phase
 * - Verify task ownership matches current agent
 *
 * Input: JSON on stdin with { tool_name, tool_input }
 * Output: JSON to stdout with { permissionDecision, reason?, warning? }
 * Exit Code: 0 if allowed, 1 if warned, 2 if blocked
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

// ============================================================================
// Configuration
// ============================================================================

const DISPATCHER_STATE_FILE = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'dispatcher_state.json'
);

const DISPATCHER_ENABLED = process.env.DISPATCHER_ACTIVE === 'true';
const CURRENT_AGENT_ID = process.env.AGENT_ID || 'manual-agent';
const TASK_QUEUE_FILE = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'task_queue.json'
);

// ============================================================================
// State Management
// ============================================================================

function readDispatcherState() {
  try {
    if (!fs.existsSync(DISPATCHER_STATE_FILE)) {
      return null;
    }
    const content = fs.readFileSync(DISPATCHER_STATE_FILE, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    console.error(`[DISPATCHER_GATE] Failed to read state file: ${error.message}`);
    return null;
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
    console.error(`[DISPATCHER_GATE] Failed to read task queue: ${error.message}`);
    return { tasks: [], in_progress: [] };
  }
}

function getCurrentTask() {
  const queue = readTaskQueue();
  const inProgress = queue.in_progress || [];

  // Find the current task owned by this agent
  return inProgress.find(task => task.agent_id === CURRENT_AGENT_ID);
}

// ============================================================================
// Conflict Detection
// ============================================================================

function checkMergeConflict(state) {
  if (!state) return null;

  // If merge phase is active and this is a write tool, flag it
  if (state.merge_in_progress) {
    return {
      blocked: true,
      reason: 'Merge phase in progress; manual writes are blocked until completion',
    };
  }

  return null;
}

function checkTaskOwnership(state, currentTask) {
  if (!state || !state.auto_dispatch_running) {
    return null;
  }

  // If auto-dispatch is running but no task is owned by this agent, warn
  if (state.auto_dispatch_running && !currentTask) {
    return {
      warning: true,
      reason: 'Auto-dispatch is running but no task is owned by this agent',
      advisory: 'Manual tool use during auto-dispatch may conflict with agent tasks',
    };
  }

  return null;
}

function detectConflictingWrites(toolInput, state) {
  // For Write/Edit tools, check if we're modifying files in use by other agents
  if (!state || !state.protected_file_sets) {
    return null;
  }

  if (typeof toolInput === 'object' && toolInput.file_path) {
    const filePath = toolInput.file_path;

    // Check each agent's protected files
    for (const [agentId, fileSet] of Object.entries(state.protected_file_sets)) {
      if (agentId === CURRENT_AGENT_ID) continue;

      if (fileSet.includes(filePath)) {
        return {
          blocked: true,
          reason: `File ${filePath} is currently locked by agent ${agentId}`,
        };
      }
    }
  }

  return null;
}

// ============================================================================
// Gate Logic
// ============================================================================

function evaluateToolUse(request) {
  // If dispatcher is not enabled, pass through
  if (!DISPATCHER_ENABLED) {
    return {
      permissionDecision: 'allow',
    };
  }

  const { tool_name, tool_input } = request;

  // Read dispatcher state
  const state = readDispatcherState();
  const currentTask = getCurrentTask();

  // Check for merge conflicts (hard block)
  const mergeConflict = checkMergeConflict(state);
  if (mergeConflict && mergeConflict.blocked) {
    return {
      permissionDecision: 'deny',
      reason: mergeConflict.reason,
    };
  }

  // Check for task ownership conflicts (soft warning)
  const ownershipIssue = checkTaskOwnership(state, currentTask);
  if (ownershipIssue && ownershipIssue.warning) {
    return {
      permissionDecision: 'allow',
      warning: ownershipIssue.reason,
      advisory: ownershipIssue.advisory,
    };
  }

  // Check for file conflicts (hard block on write tools)
  if ((tool_name === 'Write' || tool_name === 'Edit') && state) {
    const fileConflict = detectConflictingWrites(tool_input, state);
    if (fileConflict && fileConflict.blocked) {
      return {
        permissionDecision: 'deny',
        reason: fileConflict.reason,
      };
    }
  }

  return {
    permissionDecision: 'allow',
  };
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
        const response = evaluateToolUse(request);

        console.log(JSON.stringify(response));

        // Exit codes:
        // 0 = allow
        // 1 = allow with warning
        // 2 = deny
        if (response.permissionDecision === 'deny') {
          process.exit(2);
        } else if (response.warning) {
          process.exit(1);
        } else {
          process.exit(0);
        }
      } catch (error) {
        const errorResponse = {
          permissionDecision: 'allow',
          warning: 'Dispatcher gate encountered an error; proceeding with caution',
          error: error instanceof Error ? error.message : String(error),
        };
        console.log(JSON.stringify(errorResponse));
        process.exit(1);
      }

      resolve();
    });

    rl.on('error', (error) => {
      reject(error);
    });
  });
}

main().catch((error) => {
  console.error('Fatal error in dispatcher gate:', error);
  process.exit(1);
});
