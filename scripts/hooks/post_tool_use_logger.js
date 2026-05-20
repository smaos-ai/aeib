#!/usr/bin/env node
/**
 * Phase 26B: PostToolUse Provenance Logger
 *
 * Captures the result of tool execution and logs it for audit trail.
 * Creates an immutable record in the SISS graph via the Axum API.
 *
 * Input: JSON on stdin with { tool_name, tool_use_id, output, execution_time_ms }
 * Output: JSON confirmation to stdout
 * Exit Code: 0 on success (even if API is unavailable)
 */

const fs = require('fs');
const readline = require('readline');
const path = require('path');
const https = require('https');
const http = require('http');

// ============================================================================
// Configuration
// ============================================================================

const API_BASE_URL = process.env.SISS_API_URL || 'http://localhost:3000';
const AUDIT_LOG_PATH = path.join(
  process.env.HOME || '/tmp',
  '.claude',
  'agent-shell',
  'audit.log'
);

// ============================================================================
// Logging Functions
// ============================================================================

function ensureAuditLogDirectory() {
  const dir = path.dirname(AUDIT_LOG_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function writeAuditLog(entry) {
  try {
    ensureAuditLogDirectory();

    const timestamp = new Date().toISOString();
    const logLine = JSON.stringify({
      timestamp,
      ...entry,
    });

    fs.appendFileSync(AUDIT_LOG_PATH, logLine + '\n', 'utf-8');
    return true;
  } catch (error) {
    console.error(`[FALLBACK] Failed to write audit log: ${error}`);
    return false;
  }
}

// ============================================================================
// HTTP Post Helper
// ============================================================================

function postToApi(endpoint, payload) {
  return new Promise((resolve) => {
    const url = new URL(endpoint, API_BASE_URL);
    const isHttps = url.protocol === 'https:';
    const client = isHttps ? https : http;

    const postData = JSON.stringify(payload);

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData),
      },
      timeout: 5000, // 5-second timeout for API call
    };

    const req = client.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        resolve({
          success: res.statusCode >= 200 && res.statusCode < 300,
          statusCode: res.statusCode,
          body: data,
        });
      });
    });

    req.on('error', (error) => {
      // API unavailable; we'll fall back to audit log
      console.error(`[API_UNAVAILABLE] POST ${endpoint}: ${error.message}`);
      resolve({ success: false, error: error.message });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ success: false, error: 'timeout' });
    });

    req.write(postData);
    req.end();
  });
}

// ============================================================================
// Main Logic
// ============================================================================

async function logToolExecution(request) {
  const { tool_name, tool_use_id, output, execution_time_ms, error } = request;

  // Prepare audit entry
  const auditEntry = {
    tool_name,
    tool_use_id,
    execution_time_ms,
    has_error: !!error,
    output_length: output ? output.length : 0,
  };

  // If there's an error, include a sanitized version
  if (error) {
    auditEntry.error_type = typeof error === 'string' ? error : error.type || 'unknown';
  }

  // First, try to post to the API
  const apiPayload = {
    ...auditEntry,
    timestamp: new Date().toISOString(),
  };

  console.error(`[LOGGING] Tool execution: ${tool_name} (${tool_use_id})`);
  const apiResult = await postToApi('/api/graph/projections/audit', apiPayload);

  if (!apiResult.success) {
    console.error(
      `[FALLBACK] API POST failed: ${apiResult.error || apiResult.statusCode}. Falling back to audit log.`
    );
  }

  // Always write to local audit log as fallback
  const logSuccess = writeAuditLog(auditEntry);

  // Return success if either API or local log worked
  return {
    api_success: apiResult.success,
    log_success: logSuccess,
    message: apiResult.success
      ? 'Logged to API'
      : 'Logged to fallback audit trail',
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

    rl.on('close', async () => {
      try {
        // Parse the incoming request
        const request = JSON.parse(inputBuffer);

        // Log the execution
        const result = await logToolExecution(request);

        // Output confirmation
        console.log(
          JSON.stringify({
            status: 'logged',
            ...result,
          })
        );

        // Always exit 0 to indicate the hook completed successfully
        // Even if the API is down, we've logged to the fallback audit trail
        process.exit(0);
      } catch (error) {
        console.error(
          `[ERROR] Failed to process tool execution log: ${error instanceof Error ? error.message : String(error)}`
        );

        // Still exit 0 to not block the main agent flow
        console.log(
          JSON.stringify({
            status: 'error',
            message: error instanceof Error ? error.message : String(error),
          })
        );

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
  console.error('Fatal error:', error);
  // Even on fatal error, exit gracefully
  process.exit(0);
});
