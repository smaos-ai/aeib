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
src/tinyfish_runner.py
================================================================================
TinyFish Browser Context Profiles Architecture & Remote Session Runner.

Implements Section 10.3 of the AEIB Track B Specification:
  - Ephemeral vs Persistent Profile management (`use_profile=True`, `profile_id`, `use_vault=True`)
  - Strict tenant and origin isolation (`allowed_origins`, `tenant`, `profile_owner`)
  - Credential scope containment (scoped cookies/tokens prevented from cross-origin leakage)
  - Cryptographic destruction receipts signed via Ed25519 over RFC 8785 JCS
"""

import uuid
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


def encode_rfc8785_jcs(data: Any) -> bytes:
    """Canonical JSON encoding per RFC 8785, delegated to the single-source
    reference (src.jcs_canonicalizer.encode_jcs). The previous local
    json.dumps(sort_keys=True) copy diverged on non-BMP key order (UTF-16
    sort), exponent format (1.5e-07 vs 1.5e-7) and -0."""
    return encode_jcs(data)


@dataclass
class TinyFishProfileConfig:
    profile_id: str
    tenant: str
    profile_owner: str
    allowed_origins: List[str]
    credential_scope: Dict[str, str] = field(default_factory=dict)
    use_vault: bool = True
    ttl_seconds: int = 3600


@dataclass
class TinyFishSession:
    session_id: str
    profile_id: str
    tenant: str
    profile_owner: str
    allowed_origins: List[str]
    cookies: Dict[str, str]
    local_storage: Dict[str, str]
    is_ephemeral: bool
    created_at_iso: str
    active: bool = True


@dataclass
class ProfileDestructionReceipt:
    profile_id: str
    session_id: str
    tenant: str
    destroyed_at_iso: str
    signer_public_key_hex: str
    signature_hex: str


class TinyFishSessionManager:
    """
    Manages TinyFish browser sessions, context profiles, and cryptographic destruction.
    """
    def __init__(self, signing_private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        self.signing_key = signing_private_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key_hex = self.signing_key.public_key().public_bytes_raw().hex()
        self.persistent_profiles: Dict[str, TinyFishProfileConfig] = {}
        self.profile_storage: Dict[str, Dict[str, str]] = {}  # profile_id -> storage state
        self.active_sessions: Dict[str, TinyFishSession] = {}

    def register_profile(self, config: TinyFishProfileConfig) -> None:
        """Registers a persistent context profile with explicit tenant and origin boundaries."""
        self.persistent_profiles[config.profile_id] = config
        if config.profile_id not in self.profile_storage:
            self.profile_storage[config.profile_id] = {}

    def create_session(
        self,
        tenant: str,
        profile_owner: str,
        profile_id: Optional[str] = None,
        use_profile: bool = False,
        ephemeral_allowed_origins: Optional[List[str]] = None
    ) -> TinyFishSession:
        """
        Launches a TinyFish remote browser session.
        If use_profile=True, binds to persistent storage; otherwise, creates ephemeral context.
        """
        session_id = f"tfish_sess_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        if use_profile and profile_id:
            profile = self.persistent_profiles.get(profile_id)
            if not profile:
                raise ValueError(f"Profile '{profile_id}' not found in registry")
            if profile.tenant != tenant:
                raise PermissionError(f"Cross-tenant profile access denied: profile is {profile.tenant}, caller is {tenant}")

            # Load persistent storage into session
            session = TinyFishSession(
                session_id=session_id,
                profile_id=profile_id,
                tenant=tenant,
                profile_owner=profile_owner,
                allowed_origins=list(profile.allowed_origins),
                cookies=dict(profile.credential_scope),
                local_storage=dict(self.profile_storage.get(profile_id, {})),
                is_ephemeral=False,
                created_at_iso=now_iso
            )
        else:
            # Ephemeral session with fresh storage
            eff_profile_id = profile_id or f"ephemeral_{uuid.uuid4().hex[:8]}"
            session = TinyFishSession(
                session_id=session_id,
                profile_id=eff_profile_id,
                tenant=tenant,
                profile_owner=profile_owner,
                allowed_origins=list(ephemeral_allowed_origins or ["https://default.example.com"]),
                cookies={},
                local_storage={},
                is_ephemeral=True,
                created_at_iso=now_iso
            )

        self.active_sessions[session_id] = session
        return session

    def navigate_and_dispatch(
        self,
        session: TinyFishSession,
        target_url: str,
        action_verb: str,
        action_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates browser navigation and action dispatch within the scoped session.
        Enforces origin allowlisting and credential scoping.
        """
        if not session.active:
            raise RuntimeError(f"Session '{session.session_id}' has already been terminated.")

        parsed = urlparse(target_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in session.allowed_origins:
            return {
                "status": "DISPATCH_REJECTED",
                "reason": f"Target origin '{origin}' is not permitted by session allowed_origins.",
                "disposition": "DISPATCH_REJECTED (ORIGIN_RESTRICTED)"
            }

        # Action permitted within authorized session context
        return {
            "status": "ACTION_DISPATCHED",
            "session_id": session.session_id,
            "profile_id": session.profile_id,
            "origin": origin,
            "verb": action_verb,
            "cookies_applied": len(session.cookies)
        }

    def terminate_session(self, session: TinyFishSession) -> ProfileDestructionReceipt:
        """
        Destroys the browser session context and generates a cryptographically signed
        destruction receipt (Ed25519 over RFC 8785 JCS).
        """
        session.active = False
        session.cookies.clear()
        session.local_storage.clear()
        if session.session_id in self.active_sessions:
            del self.active_sessions[session.session_id]

        destroyed_at_iso = datetime.now(timezone.utc).isoformat()
        receipt_payload = {
            "destruction_event": "TINYFISH_PROFILE_SESSION_DESTROYED",
            "profile_id": session.profile_id,
            "session_id": session.session_id,
            "tenant": session.tenant,
            "profile_owner": session.profile_owner,
            "is_ephemeral": session.is_ephemeral,
            "destroyed_at": destroyed_at_iso
        }

        canonical_bytes = encode_rfc8785_jcs(receipt_payload)
        sig = self.signing_key.sign(canonical_bytes)

        return ProfileDestructionReceipt(
            profile_id=session.profile_id,
            session_id=session.session_id,
            tenant=session.tenant,
            destroyed_at_iso=destroyed_at_iso,
            signer_public_key_hex=self.public_key_hex,
            signature_hex=sig.hex()
        )
