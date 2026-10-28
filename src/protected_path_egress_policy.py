#!/usr/bin/env python3
"""
src/protected_path_egress_policy.py - Agent write-path and egress policy.

Prototype control with two independent checks:

(a) Path writes. A proposed write target is resolved with os.path.realpath
    against a workspace root. Containment is decided with
    os.path.commonpath on resolved paths (never a string-prefix test, so
    '/repo-evil' is not inside '/repo'). Targets that escape the root
    (via '..' or symlinks) are denied. Targets that are agent / CI / VCS
    configuration (e.g. .cursor/**, .claude/**, **/mcp.json,
    .github/workflows/**, .git/**, AGENTS.md, .env*) return
    REQUIRES_APPROVAL: a human must approve them out of band. Matching is
    case-insensitive (case-insensitive filesystems such as default macOS
    APFS map '.Cursor/MCP.json' to the same file) and is evaluated on both
    the lexical and the symlink-resolved relative path.

(b) Egress. Default-deny host:port allowlist. Hosts are normalised
    (trailing dot stripped, IDNA-encoded, lowercased) and matched exactly;
    a wildcard applies only when the allowlist entry is explicitly written
    as '*.example.com' (subdomains only, never the apex). IP literals in
    loopback / private / link-local / metadata / unique-local ranges are
    denied unless that exact IP:port is explicitly allowlisted.

Limits under the stated model: this evaluates the host string requested by
the agent. It does not resolve DNS, so DNS-rebinding must still be checked
at connect time (see src/mcp_egress_guard.validate_resolved_ip). No network
access is performed by this module.
"""

from __future__ import annotations

import ipaddress
import os
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Iterable, Optional, Tuple, Union
from urllib.parse import urlsplit

try:
    from src.mcp_egress_guard import MCPEgressSecurityBoundary
except ImportError:  # pythonpath = src
    from mcp_egress_guard import MCPEgressSecurityBoundary


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


# Path reason codes
PATH_ALLOWED = "PATH_ALLOWED"
PATH_PROTECTED_REQUIRES_APPROVAL = "PATH_PROTECTED_REQUIRES_APPROVAL"
ERR_PATH_INVALID = "ERR_PATH_INVALID"
ERR_PATH_ESCAPES_WORKSPACE = "ERR_PATH_ESCAPES_WORKSPACE"
ERR_PATH_IS_WORKSPACE_ROOT = "ERR_PATH_IS_WORKSPACE_ROOT"

# Egress reason codes
EGRESS_ALLOWED = "EGRESS_ALLOWED"
ERR_EGRESS_NOT_ALLOWLISTED = "ERR_EGRESS_NOT_ALLOWLISTED"
ERR_EGRESS_INVALID_PORT = "ERR_EGRESS_INVALID_PORT"
ERR_EGRESS_INVALID_HOST = "ERR_EGRESS_INVALID_HOST"
ERR_EGRESS_PRIVATE_IP_LITERAL = "ERR_EGRESS_PRIVATE_IP_LITERAL"
ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST = "ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST"
ERR_EGRESS_URL_USERINFO = "ERR_EGRESS_URL_USERINFO"
ERR_EGRESS_UNSUPPORTED_SCHEME = "ERR_EGRESS_UNSUPPORTED_SCHEME"

# Directory names that are agent/VCS configuration at any depth.
_PROTECTED_DIR_NAMES = frozenset({".cursor", ".claude", ".agents", ".git"})
# Exact file basenames protected at any depth.
_PROTECTED_BASENAMES = frozenset({
    "mcp.json", ".mcp.json", ".gitlab-ci.yml", "agents.md", "claude.md", "truth_manifesto.md",
})
# Adjacent directory pairs protected at any depth.
_PROTECTED_DIR_PAIRS = frozenset({
    (".github", "workflows"), ("scripts", "hooks"), ("docs", "truth"),
})

# Reuse the repository's existing blocked set and add ranges it does not
# cover (unique-local IPv6, "this network", CGNAT incl. some cloud metadata).
BLOCKED_NETWORKS: Tuple[Union[ipaddress.IPv4Network, ipaddress.IPv6Network], ...] = tuple(
    MCPEgressSecurityBoundary.BLOCKED_NETWORKS
) + (
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::/128"),
)

_NUMERIC_HOST = re.compile(r"^(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]*|[0-9]+))*$")
_HOST_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_DEFAULT_PORTS = {"https": 443, "http": 80, "wss": 443, "ws": 80}


@dataclass(frozen=True)
class PathPolicyResult:
    decision: PolicyDecision
    reason_code: str
    resolved_path: Optional[str] = None
    relative_path: Optional[str] = None
    matched_rule: Optional[str] = None


@dataclass(frozen=True)
class EgressPolicyResult:
    decision: PolicyDecision
    reason_code: str
    host: Optional[str] = None
    port: Optional[int] = None
    matched_entry: Optional[str] = None


def _protected_rule(rel_posix: str) -> Optional[str]:
    parts = [p.casefold() for p in rel_posix.split("/") if p not in ("", ".")]
    base = parts[-1] if parts else ""
    rules = [f"dir:{p}" for p in parts if p in _PROTECTED_DIR_NAMES]
    rules += [f"dir:{a}/{b}" for a, b in zip(parts, parts[1:]) if (a, b) in _PROTECTED_DIR_PAIRS]
    rules += [f"file:{base}"] if base in _PROTECTED_BASENAMES else []
    rules += ["file:.env*"] if base.startswith(".env") else []
    return rules[0] if rules else None


def normalize_host(host: str) -> str:
    """Lowercase + IDNA (stdlib codec) + strip one trailing dot. Raises ValueError."""
    if not isinstance(host, str):
        raise ValueError("host must be a string")
    h = host.strip()
    if h != host or any(c.isspace() for c in h):
        raise ValueError("whitespace in host")
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    try:
        return ipaddress.ip_address(h).compressed
    except ValueError:
        pass
    if h.endswith("."):
        h = h[:-1]
    h = unicodedata.normalize("NFKC", h).lower()
    try:
        ascii_host = h.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError(f"IDNA encoding failed: {exc}") from exc
    labels = ascii_host.split(".")
    if not all(_HOST_LABEL.match(lbl) for lbl in labels):
        raise ValueError("invalid DNS label")
    return ascii_host


def _ip_blocked(addr: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return any(addr in net for net in BLOCKED_NETWORKS if net.version == addr.version)


def _valid_port(port: object) -> bool:
    return isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535


class ProtectedPathEgressPolicy:
    """Write-path containment/protection plus default-deny egress."""

    def __init__(self, workspace_root: str,
                 egress_allowlist: Iterable[Union[str, Tuple[str, int]]] = ()) -> None:
        root = os.path.realpath(workspace_root)
        if not os.path.isdir(root):
            raise ValueError(f"workspace root is not a directory: {workspace_root!r}")
        self.workspace_root = root
        self._lexical_root = os.path.normpath(os.path.abspath(workspace_root))
        exact = set()
        wild = set()
        for entry in egress_allowlist:
            host, port = self._parse_entry(entry)
            if host.startswith("*."):
                wild.add((normalize_host(host[2:]), port))
            else:
                exact.add((normalize_host(host), port))
        self._exact: FrozenSet[Tuple[str, int]] = frozenset(exact)
        self._wild: FrozenSet[Tuple[str, int]] = frozenset(wild)

    @staticmethod
    def _parse_entry(entry: Union[str, Tuple[str, int]]) -> Tuple[str, int]:
        if isinstance(entry, tuple):
            try:
                host, port = entry
            except ValueError:
                raise ValueError(f"allowlist entry must be (host, port): {entry!r}") from None
        elif isinstance(entry, str):
            host, sep, port_s = entry.rpartition(":")
            if not sep or not port_s.isdigit():
                raise ValueError(f"allowlist entry must be host:port: {entry!r}")
            port = int(port_s)
        else:
            raise ValueError(f"unsupported allowlist entry: {entry!r}")
        if not isinstance(host, str) or not _valid_port(port):
            raise ValueError(f"invalid allowlist entry: {entry!r}")
        return host, port

    # ------------------------------------------------------------------ paths
    def evaluate_write(self, path: str) -> PathPolicyResult:
        if not isinstance(path, str) or not path or "\x00" in path:
            return PathPolicyResult(PolicyDecision.DENY, ERR_PATH_INVALID)
        root = self.workspace_root
        joined = path if os.path.isabs(path) else os.path.join(root, path)
        lexical = os.path.normpath(os.path.abspath(joined))
        resolved = os.path.realpath(joined)
        # Containment is decided on the symlink-resolved path only.
        if os.path.commonpath([root, resolved]) != root:
            return PathPolicyResult(PolicyDecision.DENY, ERR_PATH_ESCAPES_WORKSPACE,
                                    resolved_path=resolved)
        rel_resolved = os.path.relpath(resolved, root).replace(os.sep, "/")
        if rel_resolved == ".":
            return PathPolicyResult(PolicyDecision.DENY, ERR_PATH_IS_WORKSPACE_ROOT,
                                    resolved_path=resolved, relative_path=".")
        # The lexical (pre-symlink) name is also checked, relative to either
        # spelling of the root, so a protected name cannot hide behind a link.
        rule = _protected_rule(rel_resolved)
        for lroot in (root, self._lexical_root):
            if rule is None and os.path.commonpath([lroot, lexical]) == lroot:
                rule = _protected_rule(os.path.relpath(lexical, lroot).replace(os.sep, "/"))
        if rule is not None:
            return PathPolicyResult(PolicyDecision.REQUIRES_APPROVAL,
                                    PATH_PROTECTED_REQUIRES_APPROVAL,
                                    resolved_path=resolved, relative_path=rel_resolved,
                                    matched_rule=rule)
        return PathPolicyResult(PolicyDecision.ALLOW, PATH_ALLOWED,
                                resolved_path=resolved, relative_path=rel_resolved)

    # ----------------------------------------------------------------- egress
    def evaluate_egress(self, host: str, port: int) -> EgressPolicyResult:
        if not _valid_port(port):
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_INVALID_PORT)
        try:
            norm = normalize_host(host)
        except ValueError:
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_INVALID_HOST, port=port)
        try:
            addr = ipaddress.ip_address(norm)
        except ValueError:
            addr = None
        if addr is not None:
            if (norm, port) in self._exact:
                return EgressPolicyResult(PolicyDecision.ALLOW, EGRESS_ALLOWED, norm, port,
                                          f"{norm}:{port}")
            code = ERR_EGRESS_PRIVATE_IP_LITERAL if _ip_blocked(addr) else ERR_EGRESS_NOT_ALLOWLISTED
            return EgressPolicyResult(PolicyDecision.DENY, code, norm, port)
        if _NUMERIC_HOST.match(norm):
            # e.g. '2130706433' or '0x7f.1': some resolvers treat these as IPs.
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_AMBIGUOUS_NUMERIC_HOST,
                                      norm, port)
        if (norm, port) in self._exact:
            return EgressPolicyResult(PolicyDecision.ALLOW, EGRESS_ALLOWED, norm, port,
                                      f"{norm}:{port}")
        for suffix, wport in self._wild:
            if wport == port and norm.endswith("." + suffix):
                return EgressPolicyResult(PolicyDecision.ALLOW, EGRESS_ALLOWED, norm, port,
                                          f"*.{suffix}:{wport}")
        return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_NOT_ALLOWLISTED, norm, port)

    def evaluate_url(self, url: str) -> EgressPolicyResult:
        if not isinstance(url, str):
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_INVALID_HOST)
        try:
            parts = urlsplit(url)
            scheme = parts.scheme.lower()
            port = parts.port
            hostname = parts.hostname
        except (ValueError, AttributeError, TypeError):
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_INVALID_HOST)
        if scheme not in _DEFAULT_PORTS:
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_UNSUPPORTED_SCHEME)
        if "@" in parts.netloc:
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_URL_USERINFO)
        if not hostname:
            return EgressPolicyResult(PolicyDecision.DENY, ERR_EGRESS_INVALID_HOST)
        return self.evaluate_egress(hostname, port if port is not None else _DEFAULT_PORTS[scheme])
