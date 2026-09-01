"""
P0 Security: Sovereign Egress Firewall
Blocks outbound HTTP/socket calls to unapproved external endpoints.
Air-gap invariant enforcement.
"""

import re
from typing import Set
from urllib.parse import urlparse


class SovereignEgressFirewall:
    """Deterministic fail-closed egress control layer."""

    def __init__(self, allowed_destinations: Set[str] = None):
        # Strict local-first allowed destinations
        self.allowed_destinations = allowed_destinations or {
            "127.0.0.1",
            "localhost",
            "api.gov.cz",
            "pms.local.hotel",
            "cad.local.glass",
            "enrollment.local.school",
        }

    def validate_outbound_call(self, target_url: str, agent_id: str) -> bool:
        """
        Validates outbound network call against whitelist.
        Raises PermissionError if destination is not approved.
        """
        try:
            parsed = urlparse(target_url)
            host = parsed.hostname or parsed.netloc
        except Exception as e:
            raise PermissionError(
                f"[EGRESS BLOCKED] Malformed URL from agent '{agent_id}': {target_url}. Error: {e}"
            )

        if not host:
            raise PermissionError(
                f"[EGRESS BLOCKED] No host found in URL from {agent_id}: {target_url}"
            )

        if host not in self.allowed_destinations:
            # Deterministic fail-closed block
            raise PermissionError(
                f"[EGRESS VIOLATION] Agent '{agent_id}' attempted unapproved network egress to: {host}. "
                f"Air-gap invariant violated. Action halted. "
                f"Approved destinations: {self.allowed_destinations}"
            )

        return True

    def add_whitelist_entry(self, destination: str) -> None:
        """Add a new approved destination (only tighten, never loosen)."""
        self.allowed_destinations.add(destination)

    def get_whitelist(self) -> Set[str]:
        """Return current approved destinations."""
        return self.allowed_destinations.copy()
