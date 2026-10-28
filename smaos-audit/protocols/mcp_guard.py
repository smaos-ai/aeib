#!/usr/bin/env python3
"""
protocols/mcp_guard.py — Moat 10: In-Line MCP Wire Firewall & Drift Sentinel
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Features:
  1. Computes SHA-256 over all tool names and schemas at initialization.
  2. Intercepts MCP JSON-RPC requests (tools/list, notifications/tools/list_changed)
     to detect unauthorized tool expansions (OWASP MCP03 Rug Pulls).
  3. Freezes execution on drift, classifying the anomaly as INVALID_INPUT / REFUSED.
  4. Redacts static keys and credentials from tool response bodies.

Zero external dependencies (pure Python standard library).
"""

import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple


class SecurityViolationError(Exception):
    """Raised when an MCP server attempts an unannounced runtime tool mutation or rug pull."""
    pass


CREDENTIAL_PATTERNS = [
    (re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"gh[pousr]-[a-zA-Z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)(api[_-]?key|secret|password|token|bearer)\s*=\s*['\"]?([a-zA-Z0-9_\-\.\/+=]{8,})['\"]?"), r"\1=[REDACTED_SECRET]"),
    (re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"), "[REDACTED_JWT_TOKEN]")
]


class MCPDriftSentinel:
    """
    Monitors MCP stdio/SSE connections and freezes execution on schema drift or rug pulls.
    """

    def __init__(self, fail_closed: bool = True):
        self.initial_tool_hash: str = ""
        self.is_frozen: bool = False
        self.fail_closed = fail_closed
        self.audit_log: List[Dict[str, Any]] = []

    def hash_tools(self, tools_list: list) -> str:
        """Compute canonical SHA-256 of all tool names and schemas at initialization."""
        canonical = json.dumps(tools_list, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def intercept_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Intercept MCP JSON-RPC requests to detect unauthorized tool expansion."""
        if method in ("tools/list", "notifications/tools/list_changed"):
            current_hash = self.hash_tools(params.get("tools", []))
            
            if self.initial_tool_hash == "":
                self.initial_tool_hash = current_hash
                return params  # First run, establish baseline
            
            if current_hash != self.initial_tool_hash:
                self.is_frozen = True
                msg = (
                    f"[CRITICAL] MCP Tool Drift Detected (Rug Pull). "
                    f"Expected: {self.initial_tool_hash[:8]}, Got: {current_hash[:8]}. "
                    f"Execution frozen. Classifying as INVALID_INPUT."
                )
                self.audit_log.append({
                    "event": "TOOL_DRIFT_RUG_PULL",
                    "disposition": "INVALID_INPUT",
                    "expected_hash": self.initial_tool_hash,
                    "got_hash": current_hash,
                    "timestamp": time.time(),
                })
                raise SecurityViolationError(msg)
        
        if self.is_frozen:
            raise SecurityViolationError("Execution frozen due to prior MCP tool drift.")
            
        return params

    def redact_credentials(self, text: str) -> str:
        """Scrub sensitive credentials and environment variables from payload text."""
        cleaned = text
        for pattern, replacement in CREDENTIAL_PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)
        return cleaned

    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect and sanitize MCP tool execution response bodies."""
        result = response.get("result", {})
        if "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if item.get("type") == "text" and "text" in item:
                    item["text"] = self.redact_credentials(item["text"])
        return response
