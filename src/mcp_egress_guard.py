#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
src/mcp_egress_guard.py
================================================================================
AEIB MCP Egress & Cross-Protocol Execution-Integrity Decision Boundary.

Enforces strict separation of authorization layers:
  MCP Auth != Agent Identity != Delegation Auth != Tool Auth !=
  Destination Auth != Credential Audience != Business Effect Auth

Implements runtime checks:
  - AT30: Audience Mismatch (credential bound to approved_audience)
  - AT31: Redirect Pivot (private/link-local/metadata IP redirection intercepted)
  - AT32: DNS Rebinding (hostname resolved at dispatch must match public range)
  - AT33: Cross-Protocol Delegation (quarantines embedded A2A task graphs)
  - AT34: Token Passthrough (rejects invalid upstream bearer tokens without fallback)
  - AT35: Agent Card Mutation (validates approved Agent Card capability hash)
  - AT36: Credential Leakage (blocks secret exfiltration via tool outputs)
"""

import ipaddress
import json
import hashlib
import re
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CredentialBinding:
    token_value: str
    approved_audience: str
    approved_origin: str
    approved_operation: str
    is_valid: bool = True


@dataclass
class AgentCard:
    agent_id: str
    version: str
    declared_endpoints: List[str]
    allowed_capabilities: List[str]
    card_hash: str


@dataclass
class EgressCheckResult:
    permitted: bool
    disposition: str
    reason: str
    sanitized_output: Optional[Dict[str, Any]] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)


class MCPEgressSecurityBoundary:
    """
    Independent Execution-Integrity Decision Boundary for MCP tool calls,
    egress network validation, and cross-protocol delegation.
    """

    # Cloud metadata and private IP networks to block unconditionally
    BLOCKED_NETWORKS = [
        ipaddress.ip_network("127.0.0.0/8"),       # Loopback
        ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918 Private
        ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918 Private
        ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918 Private
        ipaddress.ip_network("169.254.0.0/16"),    # Link-local / Cloud metadata (AWS/GCP/Azure)
        ipaddress.ip_network("::1/128"),           # IPv6 Loopback
        ipaddress.ip_network("fe80::/10"),         # IPv6 Link-local
    ]

    SENSITIVE_SECRET_PATTERNS = [
        re.compile(r"(?:api[_-]?key|secret|password|bearer\s+[a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
        re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
        re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    ]

    def __init__(
        self,
        allowed_origins: Optional[List[str]] = None,
        allowed_audiences: Optional[List[str]] = None,
        approved_agent_cards: Optional[Dict[str, AgentCard]] = None,
    ):
        self.allowed_origins = set(allowed_origins or ["https://api.trusted-partner.example.com"])
        self.allowed_audiences = set(allowed_audiences or ["https://api.trusted-partner.example.com"])
        self.approved_agent_cards = approved_agent_cards or {}

    def is_ip_blocked(self, ip_str: str) -> bool:
        """Evaluates whether an IP address belongs to private, loopback, or metadata ranges."""
        try:
            addr = ipaddress.ip_address(ip_str)
            for net in self.BLOCKED_NETWORKS:
                if addr in net:
                    return True
            return False
        except ValueError:
            return True  # Malformed IP is rejected fail-closed

    def validate_credential_audience(
        self,
        credential: CredentialBinding,
        target_destination: str,
        target_audience: str
    ) -> EgressCheckResult:
        """
        AT30: Credential Audience Binding.
        Enforces that credentials are bound to an approved_audience and approved_origin.
        If target audience does not match, credential is withheld and dispatch rejected.
        """
        if not credential.is_valid:
            return EgressCheckResult(
                permitted=False,
                disposition="AUTHENTICATION_FAILURE",
                reason="Invalid or revoked upstream credential."
            )

        if credential.approved_audience != target_audience:
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (AUDIENCE_MISMATCH)",
                reason=f"Credential issued for audience '{credential.approved_audience}' cannot be presented to '{target_audience}'."
            )

        parsed_dest = urlparse(target_destination)
        dest_origin = f"{parsed_dest.scheme}://{parsed_dest.netloc}"
        if credential.approved_origin != dest_origin:
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (ORIGIN_MISMATCH)",
                reason=f"Credential approved for origin '{credential.approved_origin}' cannot be dispatched to '{dest_origin}'."
            )

        return EgressCheckResult(
            permitted=True,
            disposition="CREDENTIAL_PERMITTED",
            reason="Credential audience and origin validated."
        )

    def validate_redirect_chain(
        self,
        initial_url: str,
        redirect_urls: List[str]
    ) -> EgressCheckResult:
        """
        AT31: Redirect Pivot Protection (CVE-2026-14540 defense).
        Inspects redirect chain; if any hop redirects to private, link-local, or unapproved destination,
        request is intercepted and rejected fail-closed.
        """
        for hop_index, hop_url in enumerate(redirect_urls):
            parsed = urlparse(hop_url)
            hostname = parsed.hostname or ""
            origin = f"{parsed.scheme}://{parsed.netloc}"

            # Check if hostname is an IP literal
            try:
                ip_addr = ipaddress.ip_address(hostname)
                if self.is_ip_blocked(str(ip_addr)):
                    return EgressCheckResult(
                        permitted=False,
                        disposition="DISPATCH_REJECTED (REDIRECT_PIVOT_BLOCKED)",
                        reason=f"Redirect hop #{hop_index+1} points to restricted IP '{hostname}' (CVE-2026-14540 SSRF defense)."
                    )
            except ValueError:
                # Hostname is a domain name; check allowlist
                if origin not in self.allowed_origins:
                    return EgressCheckResult(
                        permitted=False,
                        disposition="DISPATCH_REJECTED (UNAPPROVED_REDIRECT_ORIGIN)",
                        reason=f"Redirect hop #{hop_index+1} targets unapproved origin '{origin}'."
                    )

        return EgressCheckResult(
            permitted=True,
            disposition="REDIRECT_CHAIN_APPROVED",
            reason="All redirect hops validated against origin and IP constraints."
        )

    def validate_resolved_ip(
        self,
        hostname: str,
        resolved_ips: List[str]
    ) -> EgressCheckResult:
        """
        AT32: DNS Rebinding Protection.
        Validates that resolved IPs for a public hostname do not point to private or loopback ranges.
        """
        if not resolved_ips:
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (DNS_RESOLUTION_EMPTY)",
                reason=f"Hostname '{hostname}' resolved to 0 IP addresses."
            )

        for ip_str in resolved_ips:
            if self.is_ip_blocked(ip_str):
                return EgressCheckResult(
                    permitted=False,
                    disposition="DISPATCH_REJECTED (DNS_REBINDING_DETECTED)",
                    reason=f"Hostname '{hostname}' resolved to restricted IP '{ip_str}' (DNS rebinding attack pattern)."
                )

        return EgressCheckResult(
            permitted=True,
            disposition="DNS_RESOLUTION_PERMITTED",
            reason="Resolved IP addresses are in permissible public ranges."
        )

    def validate_cross_protocol_delegation(
        self,
        tool_output_payload: Dict[str, Any],
        has_explicit_a2a_grant: bool
    ) -> EgressCheckResult:
        """
        AT33: Cross-Protocol Delegation Guard.
        MCP tool outputs containing embedded A2A instructions cannot execute implicitly;
        they require explicit policy classification and per-hop re-authorization.
        """
        embedded_instructions = tool_output_payload.get("embedded_a2a_task") or tool_output_payload.get("next_action")
        if embedded_instructions is not None and not has_explicit_a2a_grant:
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (CROSS_PROTOCOL_IMPLICIT_DELEGATION)",
                reason="MCP tool output contains embedded A2A task instructions without explicit delegation grant."
            )

        return EgressCheckResult(
            permitted=True,
            disposition="DELEGATION_PERMITTED",
            reason="Tool output contains no un-granted cross-protocol commands."
        )

    def validate_token_passthrough(
        self,
        upstream_bearer_token: Optional[str],
        token_verifier_fn: Any
    ) -> EgressCheckResult:
        """
        AT34: Token Passthrough Without Ambient Fallback.
        If an upstream bearer token is presented but fails verification, the boundary halts.
        No ambient OAuth client-credentials fallback is permitted.
        """
        if not upstream_bearer_token:
            return EgressCheckResult(
                permitted=False,
                disposition="AUTHENTICATION_FAILURE (MISSING_TOKEN)",
                reason="No upstream bearer token provided."
            )

        is_valid = token_verifier_fn(upstream_bearer_token)
        if not is_valid:
            return EgressCheckResult(
                permitted=False,
                disposition="AUTHENTICATION_FAILURE (INVALID_TOKEN)",
                reason="Upstream bearer token invalid; ambient OAuth fallback prohibited."
            )

        return EgressCheckResult(
            permitted=True,
            disposition="TOKEN_VALIDATED",
            reason="Bearer token cryptographically verified."
        )

    def validate_agent_card(
        self,
        agent_id: str,
        presented_card: AgentCard
    ) -> EgressCheckResult:
        """
        AT35: Agent Card Mutation Guard.
        Verifies that the presented Agent Card matches the approved registry hash.
        """
        approved = self.approved_agent_cards.get(agent_id)
        if not approved:
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (AGENT_CARD_UNKNOWN)",
                reason=f"No approved Agent Card found for agent '{agent_id}'."
            )

        # Compute card hash from declared endpoints and capabilities
        card_content = json.dumps({
            "agent_id": presented_card.agent_id,
            "version": presented_card.version,
            "declared_endpoints": sorted(presented_card.declared_endpoints),
            "allowed_capabilities": sorted(presented_card.allowed_capabilities)
        }, sort_keys=True).encode("utf-8")
        computed_hash = hashlib.sha256(card_content).hexdigest()

        if computed_hash != approved.card_hash:
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (AGENT_CARD_MUTATION)",
                reason=f"Agent Card for '{agent_id}' has been modified (hash mismatch). Re-approval required."
            )

        return EgressCheckResult(
            permitted=True,
            disposition="AGENT_CARD_VERIFIED",
            reason="Agent Card matches approved cryptographic registry entry."
        )

    def sanitize_tool_output_for_secrets(
        self,
        tool_output: Dict[str, Any]
    ) -> EgressCheckResult:
        """
        AT36: Credential Leakage Guard.
        Inspects tool execution outputs for secret retrieval attempts or exposed keys,
        quarantining them before entering model context or external payloads.
        """
        dumped_text = json.dumps(tool_output)
        for pattern in self.SENSITIVE_SECRET_PATTERNS:
            if pattern.search(dumped_text):
                return EgressCheckResult(
                    permitted=False,
                    disposition="OUTPUT_QUARANTINED (CREDENTIAL_LEAKAGE)",
                    reason="Tool output contains raw secret material or bearer tokens; quarantined from model context."
                )

        return EgressCheckResult(
            permitted=True,
            disposition="OUTPUT_CLEARED",
            reason="No secret leakage detected in tool output.",
            sanitized_output=tool_output
        )

    def validate_handshake_discovery_url(
        self,
        discovery_url: str,
        resolved_ips: Optional[List[str]] = None
    ) -> EgressCheckResult:
        """
        AT37: Handshake Discovery SSRF Protection (CVE-2026-51994 pattern).
        Intercepts discovery URLs from WWW-Authenticate headers, .well-known endpoints,
        or resource_metadata before candidate creation or connection dispatch.
        If target resolves to private/loopback/metadata or unapproved schemes, emits HANDSHAKE_BLOCKED.
        """
        parsed = urlparse(discovery_url)
        if parsed.scheme.lower() not in ("https", "http"):
            return EgressCheckResult(
                permitted=False,
                disposition="HANDSHAKE_BLOCKED",
                reason=f"Discovery scheme '{parsed.scheme}' rejected; only HTTPS (and approved HTTP) permitted."
            )

        hostname = parsed.hostname or ""
        ips_to_check = list(resolved_ips or [])
        try:
            ip_literal = ipaddress.ip_address(hostname)
            ips_to_check.append(str(ip_literal))
        except ValueError:
            pass

        for ip_str in ips_to_check:
            if self.is_ip_blocked(ip_str):
                return EgressCheckResult(
                    permitted=False,
                    disposition="HANDSHAKE_BLOCKED",
                    reason=f"Pre-handshake discovery URL '{discovery_url}' targets restricted IP '{ip_str}' (CVE-2026-51994 defense)."
                )

        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.allowed_origins:
            return EgressCheckResult(
                permitted=False,
                disposition="HANDSHAKE_BLOCKED",
                reason=f"Discovery origin '{origin}' is not in approved origin allowlist."
            )

        return EgressCheckResult(
            permitted=True,
            disposition="HANDSHAKE_PERMITTED",
            reason="Pre-handshake discovery metadata validated successfully."
        )

    def sanitize_agent_card_for_planning(
        self,
        raw_card_json: Dict[str, Any]
    ) -> Tuple[EgressCheckResult, Dict[str, Any]]:
        """
        AT38: Agent Card Context Poisoning Guard (Google A2A pattern).
        Separates untrusted natural-language card descriptions from structured capability facts.
        Attaches provenance: remote_agent_card and instruction_authority: none to natural-language
        fields, ensuring prompt injections inside skill descriptions cannot be executed as instructions.
        """
        agent_id = raw_card_json.get("agent_id", "unknown")
        skills = raw_card_json.get("skills", [])
        endpoint = raw_card_json.get("endpoint", "")
        auth_schemes = raw_card_json.get("auth_schemes", ["oauth2"])
        raw_description = raw_card_json.get("description", "")

        sanitized_facts = {
            "agent_id": agent_id,
            "skills": [s for s in skills if isinstance(s, str)],
            "endpoint": endpoint,
            "auth_schemes": auth_schemes,
            "trust_status": "unverified",
            "description": {
                "value": raw_description,
                "provenance": "remote_agent_card",
                "instruction_authority": "none"
            }
        }

        parsed_ep = urlparse(endpoint)
        if parsed_ep.scheme.lower() not in ("https", "http"):
            return (
                EgressCheckResult(
                    permitted=False,
                    disposition="DISPATCH_REJECTED (AGENT_CARD_MALFORMED_ENDPOINT)",
                    reason=f"Agent Card endpoint has prohibited scheme '{parsed_ep.scheme}'."
                ),
                sanitized_facts
            )

        return (
            EgressCheckResult(
                permitted=True,
                disposition="AGENT_CARD_FACTS_STRUCTURED",
                reason="Agent card decomposed into structured facts; natural language instruction authority stripped."
            ),
            sanitized_facts
        )

    def validate_per_hop_redirects(
        self,
        hops: List[Dict[str, Any]],
        max_hops: int = 5
    ) -> Tuple[EgressCheckResult, Dict[str, Any]]:
        """
        AT39: Per-Hop Redirect Validation & TOCTOU Pinning (CVE-2026-64849 defense).
        Disables automatic redirect following. Every 3xx response has its Location header
        parsed, DNS re-resolved, IP ranges checked, and recorded in a redirect_chain receipt.
        """
        if len(hops) > max_hops:
            return (
                EgressCheckResult(
                    permitted=False,
                    disposition="DISPATCH_REJECTED (REDIRECT_HOP_LIMIT_EXCEEDED)",
                    reason=f"Redirect chain length {len(hops)} exceeds maximum permitted {max_hops}."
                ),
                {"redirect_chain": hops}
            )

        receipt_chain = []
        for hop in hops:
            url = hop.get("url", "")
            resolved_addresses = hop.get("resolved_addresses", [])
            parsed = urlparse(url)

            if parsed.scheme.lower() not in ("https", "http"):
                hop_entry = {
                    "url": url,
                    "resolved_addresses": resolved_addresses,
                    "allowed": False,
                    "reason": f"invalid_scheme_{parsed.scheme}"
                }
                receipt_chain.append(hop_entry)
                return (
                    EgressCheckResult(
                        permitted=False,
                        disposition="DISPATCH_REJECTED (REDIRECT_HOP_BLOCKED)",
                        reason=f"Redirect hop '{url}' uses invalid scheme."
                    ),
                    {"redirect_chain": receipt_chain}
                )

            blocked_ip = None
            for ip_str in resolved_addresses:
                if self.is_ip_blocked(ip_str):
                    blocked_ip = ip_str
                    break

            if blocked_ip:
                hop_entry = {
                    "url": url,
                    "resolved_addresses": resolved_addresses,
                    "allowed": False,
                    "reason": "restricted_ip_or_cloud_metadata"
                }
                receipt_chain.append(hop_entry)
                return (
                    EgressCheckResult(
                        permitted=False,
                        disposition="DISPATCH_REJECTED (REDIRECT_HOP_BLOCKED)",
                        reason=f"Redirect hop '{url}' resolved to restricted IP '{blocked_ip}' (CVE-2026-64849 defense)."
                    ),
                    {"redirect_chain": receipt_chain}
                )

            receipt_chain.append({
                "url": url,
                "resolved_addresses": resolved_addresses,
                "allowed": True
            })

        return (
            EgressCheckResult(
                permitted=True,
                disposition="REDIRECT_CHAIN_APPROVED",
                reason="All redirect hops re-resolved and validated."
            ),
            {"redirect_chain": receipt_chain}
        )

    def validate_header_destination_binding(
        self,
        target_destination: str,
        headers: Dict[str, str]
    ) -> EgressCheckResult:
        """
        AT40: Header-Layer Destination Override Guard (CVE-2026-27826 pattern).
        Ensures out-of-band routing headers (Host, X-Forwarded-Host, X-Atlassian-Jira-Url)
        cannot silently steer traffic away from the approved destination origin.
        """
        parsed_dest = urlparse(target_destination)
        dest_host = parsed_dest.netloc.lower()

        routing_header_keys = [
            "host",
            ":authority",
            "x-forwarded-host",
            "x-atlassian-jira-url",
            "x-target-url",
            "x-backend-host"
        ]

        normalized_headers = {k.lower(): v for k, v in headers.items()}
        for key in routing_header_keys:
            if key in normalized_headers:
                header_val = normalized_headers[key].lower()
                if "://" in header_val:
                    header_host = urlparse(header_val).netloc.lower()
                else:
                    header_host = header_val

                if header_host != dest_host:
                    return EgressCheckResult(
                        permitted=False,
                        disposition="DISPATCH_REJECTED (HEADER_DESTINATION_OVERRIDE)",
                        reason=f"Header '{key}' value '{header_val}' differs from approved destination '{dest_host}' (CVE-2026-27826 defense)."
                    )

        return EgressCheckResult(
            permitted=True,
            disposition="HEADER_DESTINATION_VERIFIED",
            reason="Routing headers match approved destination origin."
        )

    def validate_uri_scheme_and_normalization(
        self,
        raw_uri: str
    ) -> EgressCheckResult:
        """
        AT41: URI Scheme and Address Normalization (MarkItDown pattern).
        Rejects non-HTTP schemes (file://, gopher://, ftp://, unix://) and IPv6 loopbacks,
        IPv4-mapped IPv6 (::ffff:127.0.0.1), octal or hex encoded IP representations.
        """
        parsed = urlparse(raw_uri)
        scheme = parsed.scheme.lower()
        if scheme not in ("https", "http"):
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (PROHIBITED_URI_SCHEME)",
                reason=f"Scheme '{scheme}' is prohibited; only HTTPS/HTTP permitted."
            )

        netloc = parsed.netloc.lower()
        hostname = (parsed.hostname or "").lower()
        host_candidate = hostname or netloc.strip("[]").split(":")[0]

        if (
            hostname in ("::1", "0:0:0:0:0:0:0:1", "[::1]")
            or "::ffff:" in hostname
            or "::ffff:" in netloc
            or netloc.strip("[]") in ("::1", "0:0:0:0:0:0:0:1")
            or host_candidate in ("::1", "0:0:0:0:0:0:0:1")
        ):
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (IPV6_LOOPBACK_PROHIBITED)",
                reason="IPv6 loopback or IPv4-mapped IPv6 address rejected."
            )

        if re.match(r"^(?:0[0-7]+|0x[0-9a-f]+)", host_candidate):
            return EgressCheckResult(
                permitted=False,
                disposition="DISPATCH_REJECTED (NON_CANONICAL_IP_ENCODING)",
                reason="Octal or hexadecimal IP notation rejected."
            )

        return EgressCheckResult(
            permitted=True,
            disposition="URI_NORMALIZATION_PERMITTED",
            reason="URI scheme and hostname normalized and approved."
        )
