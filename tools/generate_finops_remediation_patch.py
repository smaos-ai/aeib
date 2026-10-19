#!/usr/bin/env python3
"""
tools/generate_finops_remediation_patch.py
================================================================================
Generates 1-Click Client Remediation Patches for Claude Code & Cursor.
Emits ready-to-apply unified diff patches and configuration payloads for
deploying ContextCart MCP and setting output token bounds.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def generate_patch(output_patch_path: str, server_script_path: str | None = None) -> str:
    """Generates an RFC-compliant git/diff fix.patch configuring .mcp.json and .claude/settings.json."""
    if not server_script_path:
        server_script_path = str((REPO_ROOT / "contextcart-mcp" / "server.py").resolve())

    patch_lines = [
        "diff --git a/.mcp.json b/.mcp.json",
        "new file mode 100644",
        "--- /dev/null",
        "+++ b/.mcp.json",
        "@@ -0,0 +1,9 @@",
        "+{",
        '+  "mcpServers": {',
        '+    "contextcart": {',
        '+      "command": "python3",',
        f'+      "args": ["{server_script_path}"]',
        "+    }",
        "+  }",
        "+}",
        "",
        "diff --git a/.claude/settings.json b/.claude/settings.json",
        "new file mode 100644",
        "--- /dev/null",
        "+++ b/.claude/settings.json",
        "@@ -0,0 +1,7 @@",
        "+{",
        '+  "max_output_tokens": 1500,',
        '+  "enable_tool_search": true,',
        '+  "contextcart_governance": true',
        "+}",
    ]
    content = "\n".join(patch_lines) + "\n"
    target = Path(output_patch_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return content


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate 1-Click FinOps Remediation fix.patch"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="fix.patch",
        help="Output patch path (default: fix.patch)",
    )
    parser.add_argument(
        "--server-path",
        type=str,
        default=None,
        help="Optional custom path to contextcart-mcp/server.py",
    )

    args = parser.parse_args()
    content = generate_patch(args.output, args.server_path)
    print(f"[✓] Remediation patch written to: {args.output} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
