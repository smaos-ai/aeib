#!/usr/bin/env node
/**
 * Phase 39: PostToolUse Format Validator Hook
 * Validates file formatting after tool execution
 * Exit code 0 = validation passed
 * Exit code 1 = validation failed (format issues detected)
 */

const fs = require('fs');
const path = require('path');

// Get input from environment or arguments
const filePathArg = process.argv[2] || process.env.CLAUDE_FILE_PATH || '';
const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

// If no file path provided, pass validation
if (!filePathArg) {
    process.exit(0);
}

// Normalize file path
const filePath = path.isAbsolute(filePathArg) ? filePathArg : path.join(projectDir, filePathArg);

// Fail-closed: Validate file exists before processing
try {
    if (!fs.existsSync(filePath)) {
        console.error(`⚠️  PostToolUse: File not found: ${filePath}`);
        process.exit(0); // Not an error, file may have been deleted
    }
} catch (err) {
    console.error(`❌ PostToolUse validator error: ${err.message}`);
    process.exit(1);
}

// Read file content
let content;
try {
    content = fs.readFileSync(filePath, 'utf8');
} catch (err) {
    console.error(`❌ PostToolUse: Unable to read file: ${err.message}`);
    process.exit(1);
}

// Fail-closed: Validate formatting rules
const issues = [];

// Check for trailing whitespace
if (content.match(/[ \t]+\n/)) {
    issues.push('Trailing whitespace detected');
}

// Check for tabs (use spaces instead)
if (content.match(/\t/)) {
    issues.push('Tabs detected (use spaces for indentation)');
}

// Check for multiple consecutive blank lines
if (content.match(/\n\n\n+/)) {
    issues.push('Multiple consecutive blank lines detected');
}

// Check for missing final newline (most files should end with newline)
if (content.length > 0 && !content.endsWith('\n')) {
    // JavaScript and shell scripts typically end with newline
    // Binary files and certain configs might not
    const ext = path.extname(filePath);
    if (['.js', '.ts', '.tsx', '.sh', '.md', '.json', '.rs'].includes(ext)) {
        issues.push('Missing final newline');
    }
}

// Report issues (fail-closed)
if (issues.length > 0) {
    console.warn(`⚠️  PostToolUse formatting issues detected in ${path.basename(filePath)}:`);
    issues.forEach(issue => console.warn(`   - ${issue}`));
    // Don't fail on format issues (advisory only)
    process.exit(0);
}

// Validation passed
process.exit(0);
