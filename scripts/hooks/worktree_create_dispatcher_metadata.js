#!/usr/bin/env node
/**
 * Phase 27: WorktreeCreate Dispatcher Metadata
 *
 * Initializes dispatcher metadata when a new worktree is created.
 * Sets up:
 * - Agent context tracking
 * - Protected file sets
 * - Task metadata binding
 * - Isolation markers for merge strategy
 *
 * Input: JSON on stdin with { worktree_path, worktree_name, branch_name }
 * Output: JSON to stdout with { status, metadata_initialized }
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

const DISPATCHER_STATE_FILE = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'dispatcher',
  'dispatcher_state.json'
);

const CURRENT_AGENT_ID = process.env.AGENT_ID || `agent-${Date.now()}`;
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
    console.error(`[WORKTREE_CREATE] Failed to read state file: ${error.message}`);
    return null;
  }
}

function writeDispatcherState(state) {
  try {
    ensureDir(path.dirname(DISPATCHER_STATE_FILE));
    fs.writeFileSync(DISPATCHER_STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error(`[WORKTREE_CREATE] Failed to write state file: ${error.message}`);
    return false;
  }
}

// ============================================================================
// Metadata Initialization
// ============================================================================

function createAgentContext(worktreeData) {
  return {
    agent_id: CURRENT_AGENT_ID,
    worktree_path: worktreeData.worktree_path,
    worktree_name: worktreeData.worktree_name,
    branch_name: worktreeData.branch_name,
    created_at: new Date().toISOString(),
    protected_files: [],
    status: 'active',
    isolation_level: 'worktree',
    merge_strategy_compatible: true,
  };
}

function registerAgentContext(agentContext) {
  try {
    ensureDir(AGENT_CONTEXT_DIR);

    // Write agent-specific context file
    const contextFile = path.join(AGENT_CONTEXT_DIR, `${CURRENT_AGENT_ID}.json`);
    fs.writeFileSync(contextFile, JSON.stringify(agentContext, null, 2), 'utf-8');

    // Update dispatcher state to register this agent
    const state = readDispatcherState() || {};

    if (!state.active_agents) {
      state.active_agents = [];
    }

    // Check if agent already registered
    const existingAgent = state.active_agents.find(a => a.agent_id === CURRENT_AGENT_ID);

    if (!existingAgent) {
      state.active_agents.push({
        agent_id: CURRENT_AGENT_ID,
        worktree_name: agentContext.worktree_name,
        registered_at: new Date().toISOString(),
      });
    }

    writeDispatcherState(state);

    return true;
  } catch (error) {
    console.error(`[WORKTREE_CREATE] Failed to register agent context: ${error.message}`);
    return false;
  }
}

// ============================================================================
// Main Logic
// ============================================================================

function initializeWorktreeMetadata(worktreeData) {
  // If dispatcher is not enabled, skip initialization
  if (!DISPATCHER_ENABLED) {
    return {
      status: 'skipped',
      reason: 'Dispatcher not active',
    };
  }

  // Create agent context
  const agentContext = createAgentContext(worktreeData);

  // Register it
  const registered = registerAgentContext(agentContext);

  if (!registered) {
    return {
      status: 'warning',
      reason: 'Failed to register agent context',
      metadata_initialized: false,
    };
  }

  return {
    status: 'initialized',
    agent_id: CURRENT_AGENT_ID,
    metadata_initialized: true,
    context: {
      worktree_path: agentContext.worktree_path,
      worktree_name: agentContext.worktree_name,
      branch_name: agentContext.branch_name,
    },
  };
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
        const result = initializeWorktreeMetadata(worktreeData);

        console.log(JSON.stringify(result));
        process.exit(0);
      } catch (error) {
        const errorResponse = {
          status: 'error',
          message: error instanceof Error ? error.message : String(error),
          metadata_initialized: false,
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
  console.error('Fatal error in worktree create hook:', error);
  process.exit(0);
});
