"""
contextcart-mcp
================================================================================
Deterministic MCP research boundary & AST symbol slicer that prevents
context window bloat in Claude Code, Cursor, and Windsurf.
"""

from __future__ import annotations

from .ast_slicer import AstSymbolSlicer
from .server import (
    estimate_tokens,
    handle_audit_context_efficiency,
    handle_brainstorm_options,
    handle_evidence_pack,
    handle_research_brief,
    handle_slice_symbol,
    process_jsonrpc_message,
)

__version__ = "1.0.0"

__all__ = [
    "AstSymbolSlicer",
    "handle_research_brief",
    "handle_brainstorm_options",
    "handle_evidence_pack",
    "handle_slice_symbol",
    "handle_audit_context_efficiency",
    "estimate_tokens",
    "process_jsonrpc_message",
    "__version__",
]
