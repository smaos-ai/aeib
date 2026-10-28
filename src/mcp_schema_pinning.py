#!/usr/bin/env python3
r"""
mcp_schema_pinning.py - MCP Tool Schema Pinning & Integrity (Acceptance Test 14)

Binds each approved MCP tool schema to a canonical digest computed as
SHA256(JCS(schema)) using the repository's single canonicalization source of
truth (src/jcs_canonicalizer.encode_jcs), so key order and whitespace cannot
smuggle a mutation past review, while any semantic change to descriptions,
parameters, default values, or endpoints changes the digest.

On mismatch the verifier raises SchemaMutationRejected, whose .code is
MCP_SCHEMA_MUTATION_REJECTED, so CI and gateway layers can alert on the
exact rejection reason.

Zero-mock: digests are real SHA-256 over real RFC 8785 bytes; there are no
shortcuts or test-only branches.
"""

import hashlib
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:  # direct script execution / pythonpath = src
    from jcs_canonicalizer import encode_jcs

MCP_SCHEMA_MUTATION_REJECTED = "MCP_SCHEMA_MUTATION_REJECTED"


class SchemaMutationRejected(ValueError):
    """Raised when a tool schema no longer matches its approved pin."""

    def __init__(self, tool_name: str, expected: str, actual: str) -> None:
        self.code = MCP_SCHEMA_MUTATION_REJECTED
        self.tool_name = tool_name
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"{MCP_SCHEMA_MUTATION_REJECTED}: tool {tool_name!r} schema "
            f"digest changed (approved {expected}, observed {actual})"
        )


class UnknownToolRejected(ValueError):
    """Raised fail-closed when no approved pin exists for the tool."""

    def __init__(self, tool_name: str) -> None:
        self.code = MCP_SCHEMA_MUTATION_REJECTED
        self.tool_name = tool_name
        super().__init__(
            f"{MCP_SCHEMA_MUTATION_REJECTED}: no approved schema pin for "
            f"tool {tool_name!r} (fail closed)"
        )


def compute_tool_schema_hash(schema: dict) -> str:
    """
    Canonical tool_schema_hash = SHA256(JCS(schema)), hex-encoded with a
    sha256: prefix. Uses encode_jcs so the digest is byte-identical to every
    other canonicalization in the repository (UTF-16 code-unit key order,
    ECMAScript number rules, no normalization inside JCS).
    """
    if not isinstance(schema, dict):
        raise TypeError("schema must be a JSON object")
    canonical = encode_jcs(schema)
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


class ToolSchemaPins:
    """Registry of approved tool schema digests (pin once, verify always)."""

    def __init__(self) -> None:
        self._pins = {}

    def pin(self, tool_name: str, schema: dict) -> str:
        """Approve the current schema; returns the recorded digest."""
        digest = compute_tool_schema_hash(schema)
        self._pins[tool_name] = digest
        return digest

    def verify(self, tool_name: str, schema: dict) -> str:
        """
        Verify a schema against its approved pin.
        Raises SchemaMutationRejected on any semantic change and
        UnknownToolRejected fail-closed when no pin exists.
        """
        expected = self._pins.get(tool_name)
        if expected is None:
            raise UnknownToolRejected(tool_name)
        actual = compute_tool_schema_hash(schema)
        if actual != expected:
            raise SchemaMutationRejected(tool_name, expected, actual)
        return actual

    def pinned(self, tool_name: str) -> bool:
        return tool_name in self._pins


# ---------------------------------------------------------------------------
# Tool-definition pinning across servers (rug-pull and shadowing detection)
# ---------------------------------------------------------------------------
# A tool *definition* is the part of an MCP `tools/list` entry the model or the
# host reads when choosing a tool: name + title + description + inputSchema +
# annotations (behaviour hints such as destructiveHint / idempotentHint).
# Changing any of these after approval ("rug pull") or registering the same
# tool name on a second server ("shadowing") alters model or host behaviour
# without changing any call site, so both are reported as typed findings.

TOOL_DEFINITION_FIELDS = ("name", "title", "description", "inputSchema", "annotations")


class ToolDefinitionInvalid(ValueError):
    """Raised when a tool entry lacks a string name or an object inputSchema."""


class ToolDriftKind(str, Enum):
    DEFINITION_CHANGED = "DEFINITION_CHANGED"
    TOOL_ADDED = "TOOL_ADDED"
    TOOL_REMOVED = "TOOL_REMOVED"
    DUPLICATE_IN_SERVER = "DUPLICATE_IN_SERVER"
    SHADOWED_ACROSS_SERVERS = "SHADOWED_ACROSS_SERVERS"
    UNPINNED_SERVER = "UNPINNED_SERVER"
    INVALID_DEFINITION = "INVALID_DEFINITION"


@dataclass(frozen=True)
class ToolDefinitionFinding:
    kind: ToolDriftKind
    server_id: str
    tool_name: str
    expected: Optional[str] = None
    observed: Optional[str] = None
    other_server_id: Optional[str] = None


@dataclass(frozen=True)
class ToolSetCheckResult:
    server_id: str
    digests: Mapping[str, str]
    findings: Tuple[ToolDefinitionFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


def compute_tool_definition_digest(tool: dict) -> str:
    """sha256:<hex> of JCS({name, title?, description?, inputSchema, annotations?}) via encode_jcs."""
    if not isinstance(tool, dict):
        raise ToolDefinitionInvalid("tool definition must be a JSON object")
    name = tool.get("name")
    schema = tool.get("inputSchema")
    if not isinstance(name, str) or not name:
        raise ToolDefinitionInvalid("tool definition requires a non-empty string name")
    if not isinstance(schema, dict):
        raise ToolDefinitionInvalid(f"tool {name!r} requires an object inputSchema")
    if "description" in tool and not isinstance(tool["description"], str):
        raise ToolDefinitionInvalid(f"tool {name!r} description must be a string")
    if "title" in tool and not isinstance(tool["title"], str):
        raise ToolDefinitionInvalid(f"tool {name!r} title must be a string")
    if "annotations" in tool and not isinstance(tool["annotations"], dict):
        raise ToolDefinitionInvalid(f"tool {name!r} annotations must be an object")
    projection = {k: tool[k] for k in TOOL_DEFINITION_FIELDS if k in tool}
    return "sha256:" + hashlib.sha256(encode_jcs(projection)).hexdigest()


def shadow_key(tool_name: str) -> str:
    """Comparison key for cross-server collisions (NFKC + casefold)."""
    return unicodedata.normalize("NFKC", tool_name).casefold()


def detect_shadowing(servers: Mapping[str, Iterable[dict]]) -> List[ToolDefinitionFinding]:
    """Report every tool name (NFKC/casefold) offered by more than one server."""
    owners: Dict[str, Tuple[str, str]] = {}
    findings: List[ToolDefinitionFinding] = []
    for server_id in sorted(servers):
        seen_here = set()
        for tool in servers[server_id]:
            name = tool.get("name") if isinstance(tool, dict) else None
            if not isinstance(name, str):
                continue
            key = shadow_key(name)
            if key in seen_here:
                continue
            seen_here.add(key)
            if key in owners:
                findings.append(ToolDefinitionFinding(
                    ToolDriftKind.SHADOWED_ACROSS_SERVERS, server_id, name,
                    other_server_id=owners[key][0]))
            else:
                owners[key] = (server_id, name)
    return findings


class ToolDefinitionPinSet:
    """Approved tool definitions per server; verify every tools/list result."""

    def __init__(self) -> None:
        self._servers: Dict[str, Dict[str, str]] = {}

    def _digest_all(self, server_id: str, tools: Iterable[dict]
                    ) -> Tuple[Dict[str, str], List[ToolDefinitionFinding]]:
        digests: Dict[str, str] = {}
        findings: List[ToolDefinitionFinding] = []
        seen = set()
        for tool in tools:
            try:
                digest = compute_tool_definition_digest(tool)
            except ToolDefinitionInvalid:
                raw = tool.get("name") if isinstance(tool, dict) else None
                findings.append(ToolDefinitionFinding(
                    ToolDriftKind.INVALID_DEFINITION, server_id,
                    raw if isinstance(raw, str) else ""))
                continue
            name = tool["name"]
            if shadow_key(name) in seen:
                findings.append(ToolDefinitionFinding(
                    ToolDriftKind.DUPLICATE_IN_SERVER, server_id, name, observed=digest))
                continue
            seen.add(shadow_key(name))
            digests[name] = digest
        return digests, findings

    def _owner_of(self, name: str, exclude: str) -> Optional[str]:
        key = shadow_key(name)
        owners = [sid for sid in sorted(self._servers)
                  if sid != exclude and any(shadow_key(n) == key for n in self._servers[sid])]
        return owners[0] if owners else None

    def pin_server(self, server_id: str, tools: Iterable[dict]) -> ToolSetCheckResult:
        """Approve a server's tool set. Pins are recorded only when no findings."""
        digests, findings = self._digest_all(server_id, tools)
        for name in sorted(digests):
            other = self._owner_of(name, server_id)
            if other is not None:
                findings.append(ToolDefinitionFinding(
                    ToolDriftKind.SHADOWED_ACROSS_SERVERS, server_id, name,
                    observed=digests[name], other_server_id=other))
        if not findings:
            self._servers[server_id] = dict(digests)
        return ToolSetCheckResult(server_id, digests, tuple(findings))

    def check_server(self, server_id: str, tools: Iterable[dict]) -> ToolSetCheckResult:
        """Compare an observed tools/list result with the approved pins."""
        digests, findings = self._digest_all(server_id, tools)
        pinned = self._servers.get(server_id)
        if pinned is None:
            findings.append(ToolDefinitionFinding(ToolDriftKind.UNPINNED_SERVER, server_id, ""))
            return ToolSetCheckResult(server_id, digests, tuple(findings))
        for name in sorted(digests):
            expected = pinned.get(name)
            if expected is None:
                other = self._owner_of(name, server_id)
                kind = (ToolDriftKind.SHADOWED_ACROSS_SERVERS if other is not None
                        else ToolDriftKind.TOOL_ADDED)
                findings.append(ToolDefinitionFinding(
                    kind, server_id, name, observed=digests[name], other_server_id=other))
            elif expected != digests[name]:
                findings.append(ToolDefinitionFinding(
                    ToolDriftKind.DEFINITION_CHANGED, server_id, name,
                    expected=expected, observed=digests[name]))
        for name in sorted(set(pinned) - set(digests)):
            findings.append(ToolDefinitionFinding(
                ToolDriftKind.TOOL_REMOVED, server_id, name, expected=pinned[name]))
        return ToolSetCheckResult(server_id, digests, tuple(findings))

    def pinned_digests(self, server_id: str) -> Dict[str, str]:
        return dict(self._servers.get(server_id, {}))
