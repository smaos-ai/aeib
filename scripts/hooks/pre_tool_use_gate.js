#!/usr/bin/env node
/**
 * Phase 26B: PreToolUse Security Gate
 *
 * The $\delta^+ safety gate that intercepts every tool call before execution.
 *
 * Input: JSON on stdin with { tool_name, tool_input }
 * Output: JSON to stdout with { permissionDecision, reason?, updatedInput? }
 * Exit Code: 0 if allowed, 2 if denied
 */

const fs = require('fs');
const readline = require('readline');

// ============================================================================
// Blacklist Patterns
// ============================================================================

const DESTRUCTIVE_PATTERNS = [
  /rm\s+-rf/i,
  /rm\s+-f\s*\/\s*\*/i,  // rm -f /*
  /dd\s+if=/i,           // dd (disk operations)
  /mkfs/i,               // mkfs (format filesystem)
  /shred/i,              // shred (secure delete)
  /dd\s+of=\/dev\/.*zero/i, // dd to device
];

const SQL_DESTRUCTIVE_PATTERNS = [
  /drop\s+table/i,
  /truncate\s+table/i,
  /drop\s+database/i,
  /delete\s+from\s+\*/i,
  /purge/i,
];

const PROTECTED_PATHS = [
  '.git',
  '.claude/skills',
  '.claude/CLAUDE.md',
];

// ============================================================================
// Core Gate Logic
// ============================================================================

function isToolInputString(input) {
  return typeof input === 'string';
}

function checkDestructiveCommand(input) {
  // Check for shell destructive commands
  for (const pattern of DESTRUCTIVE_PATTERNS) {
    if (pattern.test(input)) {
      return `Blocked: destructive command detected`;
    }
  }

  // Check for SQL destructive commands
  for (const pattern of SQL_DESTRUCTIVE_PATTERNS) {
    if (pattern.test(input)) {
      return `Blocked: SQL destructive command detected`;
    }
  }

  return null;
}

function checkProtectedPathAccess(input) {
  for (const path of PROTECTED_PATHS) {
    if (input.includes(path)) {
      return `Blocked: access to protected path '${path}' is forbidden`;
    }
  }
  return null;
}

function checkBashToolUse(toolInput) {
  if (!isToolInputString(toolInput)) {
    return null;
  }

  // Check for destructive commands
  const destructiveReason = checkDestructiveCommand(toolInput);
  if (destructiveReason) {
    return destructiveReason;
  }

  // Check for protected path access
  const pathReason = checkProtectedPathAccess(toolInput);
  if (pathReason) {
    return pathReason;
  }

  return null;
}

function checkWriteToolUse(toolInput) {
  if (isToolInputString(toolInput)) {
    // If it's a string, check it directly
    const pathReason = checkProtectedPathAccess(toolInput);
    if (pathReason) {
      return pathReason;
    }
  } else if (typeof toolInput === 'object' && toolInput !== null) {
    // If it's an object, check the file_path field
    const filePath = toolInput.file_path;
    if (typeof filePath === 'string') {
      // Check for protected path access in file_path
      for (const path of PROTECTED_PATHS) {
        if (filePath.includes(path)) {
          return `Blocked: cannot write to protected path '${path}'`;
        }
      }
    }
  }

  return null;
}

function checkEditToolUse(toolInput) {
  if (isToolInputString(toolInput)) {
    const pathReason = checkProtectedPathAccess(toolInput);
    if (pathReason) {
      return pathReason;
    }
  } else if (typeof toolInput === 'object' && toolInput !== null) {
    const filePath = toolInput.file_path;
    if (typeof filePath === 'string') {
      for (const path of PROTECTED_PATHS) {
        if (filePath.includes(path)) {
          return `Blocked: cannot edit protected path '${path}'`;
        }
      }
    }
  }

  return null;
}

function evaluateToolUse(request) {
  const { tool_name, tool_input } = request;

  let denialReason = null;

  // Route to appropriate checker based on tool type
  switch (tool_name) {
    case 'Bash':
      denialReason = checkBashToolUse(tool_input);
      break;

    case 'Write':
      denialReason = checkWriteToolUse(tool_input);
      break;

    case 'Edit':
      denialReason = checkEditToolUse(tool_input);
      break;

    default:
      // Unknown tools are allowed by default
      break;
  }

  if (denialReason) {
    return {
      permissionDecision: 'deny',
      reason: denialReason,
    };
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
        // Parse the incoming request
        const request = JSON.parse(inputBuffer);

        // Evaluate the tool use
        const response = evaluateToolUse(request);

        // Output the decision
        console.log(JSON.stringify(response));

        // Exit with appropriate code
        if (response.permissionDecision === 'deny') {
          process.exit(2);
        } else {
          process.exit(0);
        }
      } catch (error) {
        // If we can't parse the request, deny it
        const errorResponse = {
          permissionDecision: 'deny',
          reason: `Failed to parse tool request: ${error instanceof Error ? error.message : String(error)}`,
        };
        console.log(JSON.stringify(errorResponse));
        process.exit(2);
      }

      resolve();
    });

    rl.on('error', (error) => {
      reject(error);
    });
  });
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
