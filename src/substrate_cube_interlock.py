#!/usr/bin/env python3
"""
src/substrate_cube_interlock.py — Unified Agent Substrate + Cube Sandbox Egress & Auto-Pause Interlock

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Core Capabilities:
1. SPIFFE SVID Workload Identity Verification (`atenet-egress` / `agentgateway` PEP).
2. Cube Credential Vault Blind Placeholder Resolution (secrets never enter sandbox context or telemetry logs).
3. EO1 Write-Before-Execute Intent Latch with VeritasChain `EFFECT_INDETERMINATE` state.
4. Cube `AutoPause` / `AutoResume` Snapshot Hash & Taint Auditor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Mapping, Set, Tuple

from src.hypergraph_blast_radius import sha256_jcs_caid

VAULT_PLACEHOLDER_RE = re.compile(r"\{\{VAULT:([A-Z0-9_]+)\}\}")


@dataclass(frozen=True)
class ActorSnapshotDescriptor:
    actor_spiffe_id: str
    sandbox_backend: str  # "gvisor" | "kata_microvm" | "cube_kvm" | "mitos_firecracker"
    memory_zstd_bytes: bytes
    pre_suspend_taint_clean: bool
    pending_effect_keys: Tuple[str, ...]
    snapshot_caid: str

    def __post_init__(self) -> None:
        if not self.actor_spiffe_id.startswith("spiffe://"):
            raise ValueError(f"ERR_INVALID_SPIFFE_ID:{self.actor_spiffe_id}")
        if not self.snapshot_caid.startswith("sha256:"):
            raise ValueError(f"ERR_INVALID_SNAPSHOT_CAID:{self.snapshot_caid}")


@dataclass(frozen=True)
class EgressInterlockReceipt:
    allowed: bool
    effect_state: str  # "LATCHED_DISPATCHED" | "COMMITTED" | "EFFECT_INDETERMINATE" | "HALT_*"
    actor_spiffe_id: str
    effect_key_caid: str
    resolved_headers_redacted: Dict[str, str]
    receipt_caid: str
    bpf_lsm_profile_digest: str = ""


class SubstrateCubeInterlock:
    """
    Control-plane interlock sitting between Agent Substrate / Cube Sandbox Actors
    and the outbound `agentgateway` / `atenet-egress` proxy.
    """

    ALLOWED_BACKENDS: FrozenSet[str] = frozenset(
        {"gvisor", "kata_microvm", "cube_kvm", "mitos_firecracker"}
    )

    def __init__(
        self,
        trusted_spiffe_prefix: str,
        allowed_egress_hosts: FrozenSet[str],
        credential_vault: Mapping[str, str],
        bpf_lsm_profile_digest: str = "",
    ) -> None:
        if not trusted_spiffe_prefix.startswith("spiffe://"):
            raise ValueError("ERR_INVALID_SPIFFE_TRUST_DOMAIN")
        self.trusted_spiffe_prefix = trusted_spiffe_prefix
        self.allowed_egress_hosts = allowed_egress_hosts
        self.bpf_lsm_profile_digest = bpf_lsm_profile_digest
        self._credential_vault: Dict[str, str] = dict(credential_vault)

        # Effect-key state machine: effect_key_caid -> state
        # States: "DISPATCHED_PENDING_ACK" | "COMMITTED" | "EFFECT_INDETERMINATE"
        self._effect_ledger: Dict[str, str] = {}
        self._actor_inflight: Dict[str, Set[str]] = {}
        self._suspended_snapshots: Dict[str, ActorSnapshotDescriptor] = {}

    def get_effect_state(self, effect_key_caid: str) -> str:
        return self._effect_ledger.get(effect_key_caid, "UNSEEN")

    def intercept_outbound_egress(
        self,
        actor_spiffe_id: str,
        target_host: str,
        http_method: str,
        business_effect_payload: Dict[str, Any],
        header_templates: Mapping[str, str],
        raw_secret_scan_body: str = "",
    ) -> EgressInterlockReceipt:
        """
        Station 1 Egress Policy Enforcement Point:
        1. Verifies Actor SPIFFE ID belongs to trusted domain.
        2. Enforces default-deny `atenet-egress` hostname allowlist.
        3. Scans payload to ensure raw vault secrets were NOT leaked into sandbox context.
        4. Computes canonical `effect_key_caid` and checks for `EFFECT_INDETERMINATE` or duplicate commit.
        5. Resolves `{{VAULT:...}}` placeholders out-of-band without logging raw secrets.
        """
        # 1. Verify SPIFFE SVID identity
        if not actor_spiffe_id.startswith(self.trusted_spiffe_prefix):
            return self._mint_egress(
                False, "HALT_UNTRUSTED_SPIFFE_ID", actor_spiffe_id, "NONE", {}
            )

        # 2. Enforce default-deny hostname policy
        if target_host not in self.allowed_egress_hosts:
            return self._mint_egress(
                False, f"HALT_EGRESS_HOST_DENIED:{target_host}", actor_spiffe_id, "NONE", {}
            )

        # 3. Verify no raw secret value is present in agent-authored body (Credential Blindness)
        body_str = json.dumps(business_effect_payload, sort_keys=True) + raw_secret_scan_body
        for secret_name, secret_val in self._credential_vault.items():
            if secret_val and secret_val in body_str:
                return self._mint_egress(
                    False,
                    f"HALT_RAW_SECRET_IN_SANDBOX_CONTEXT:{secret_name}",
                    actor_spiffe_id,
                    "NONE",
                    {},
                )

        # 4. Compute deterministic Effect Key CAID
        effect_key_caid = sha256_jcs_caid(
            {
                "actor": actor_spiffe_id,
                "method": http_method.upper(),
                "payload": business_effect_payload,
                "target_host": target_host,
            }
        )

        existing_state = self._effect_ledger.get(effect_key_caid)
        if existing_state == "EFFECT_INDETERMINATE":
            return self._mint_egress(
                False,
                "HALT_INDETERMINATE_REQUIRES_RECONCILIATION",
                actor_spiffe_id,
                effect_key_caid,
                {},
            )
        if existing_state == "COMMITTED":
            return self._mint_egress(
                False,
                "HALT_DUPLICATE_COMMITTED_EFFECT_BLOCKED",
                actor_spiffe_id,
                effect_key_caid,
                {},
            )

        # 5. Resolve Cube Credential Vault placeholders in headers (recording only redacted proof)
        redacted_headers: Dict[str, str] = {}
        for h_key, h_tmpl in sorted(header_templates.items()):
            match = VAULT_PLACEHOLDER_RE.search(h_tmpl)
            if match:
                vault_key = match.group(1)
                if vault_key not in self._credential_vault:
                    return self._mint_egress(
                        False,
                        f"HALT_UNKNOWN_VAULT_PLACEHOLDER:{vault_key}",
                        actor_spiffe_id,
                        effect_key_caid,
                        {},
                    )
                redacted_headers[h_key] = f"VAULT_INJECTED:{vault_key}"
            else:
                redacted_headers[h_key] = h_tmpl

        # 6. Latch pre-dispatch intent
        self._effect_ledger[effect_key_caid] = "DISPATCHED_PENDING_ACK"
        self._actor_inflight.setdefault(actor_spiffe_id, set()).add(effect_key_caid)
        return self._mint_egress(
            True,
            "LATCHED_DISPATCHED",
            actor_spiffe_id,
            effect_key_caid,
            redacted_headers,
        )

    def acknowledge_egress_completion(
        self, actor_spiffe_id: str, effect_key_caid: str, transport_succeeded: bool
    ) -> str:
        """Records provider response or transitions to `EFFECT_INDETERMINATE` on timeout/drop."""
        if effect_key_caid not in self._effect_ledger:
            raise KeyError(f"ERR_UNKNOWN_EFFECT_KEY:{effect_key_caid}")

        inflight = self._actor_inflight.get(actor_spiffe_id, set())
        inflight.discard(effect_key_caid)

        if transport_succeeded:
            self._effect_ledger[effect_key_caid] = "COMMITTED"
            return "COMMITTED"
        else:
            self._effect_ledger[effect_key_caid] = "EFFECT_INDETERMINATE"
            return "EFFECT_INDETERMINATE"

    def auto_pause_actor(
        self,
        actor_spiffe_id: str,
        sandbox_backend: str,
        memory_zstd_bytes: bytes,
        pre_suspend_taint_clean: bool,
    ) -> ActorSnapshotDescriptor:
        """
        Cube Sandbox / Agent Substrate `ACTOR_STATE_SUSPENDED` hook:
        Any in-flight (`DISPATCHED_PENDING_ACK`) mutation is immediately frozen into
        `EFFECT_INDETERMINATE` so waking the snapshot cannot trigger a blind duplicate retry.
        """
        if sandbox_backend not in self.ALLOWED_BACKENDS:
            raise ValueError(f"ERR_UNSUPPORTED_SANDBOX_BACKEND:{sandbox_backend}")

        inflight_keys = tuple(sorted(self._actor_inflight.get(actor_spiffe_id, set())))
        for k in inflight_keys:
            if self._effect_ledger.get(k) == "DISPATCHED_PENDING_ACK":
                self._effect_ledger[k] = "EFFECT_INDETERMINATE"

        self._actor_inflight[actor_spiffe_id] = set()

        snap_caid = sha256_jcs_caid(
            {
                "actor": actor_spiffe_id,
                "backend": sandbox_backend,
                "memory_sha256": sha256_jcs_caid(memory_zstd_bytes),
                "pending_effect_keys": list(inflight_keys),
                "taint_clean": pre_suspend_taint_clean,
            }
        )

        desc = ActorSnapshotDescriptor(
            actor_spiffe_id=actor_spiffe_id,
            sandbox_backend=sandbox_backend,
            memory_zstd_bytes=memory_zstd_bytes,
            pre_suspend_taint_clean=pre_suspend_taint_clean,
            pending_effect_keys=inflight_keys,
            snapshot_caid=snap_caid,
        )
        self._suspended_snapshots[actor_spiffe_id] = desc
        return desc

    def auto_resume_actor(
        self, candidate_snapshot: ActorSnapshotDescriptor
    ) -> Tuple[bool, str]:
        """Audits a snapshot before rehydrating onto a Worker Pod / KVM microVM."""
        expected = self._suspended_snapshots.get(candidate_snapshot.actor_spiffe_id)
        if expected is None:
            return False, "HALT_RESUME_UNKNOWN_ACTOR_SNAPSHOT"

        recomputed_caid = sha256_jcs_caid(
            {
                "actor": candidate_snapshot.actor_spiffe_id,
                "backend": candidate_snapshot.sandbox_backend,
                "memory_sha256": sha256_jcs_caid(candidate_snapshot.memory_zstd_bytes),
                "pending_effect_keys": list(candidate_snapshot.pending_effect_keys),
                "taint_clean": candidate_snapshot.pre_suspend_taint_clean,
            }
        )

        if (
            recomputed_caid != expected.snapshot_caid
            or candidate_snapshot.snapshot_caid != expected.snapshot_caid
        ):
            return False, "HALT_SNAPSHOT_HASH_TAMPER_DETECTED"

        if not candidate_snapshot.pre_suspend_taint_clean:
            return False, "HALT_RESUME_TAINTED_SNAPSHOT_FORBIDDEN"

        return True, "OK_ACTOR_SNAPSHOT_RESUMED"

    def reconcile_indeterminate_effect(
        self, effect_key_caid: str, provider_confirmed_executed: bool
    ) -> str:
        """
        HOLD-and-Reconcile probe resolution:
        - If provider confirms the write already executed: marks COMMITTED (blocking duplicate retry).
        - If provider confirms the write never arrived: clears latch so safe retry can proceed.
        """
        if self._effect_ledger.get(effect_key_caid) != "EFFECT_INDETERMINATE":
            raise ValueError(f"ERR_EFFECT_NOT_INDETERMINATE:{effect_key_caid}")

        if provider_confirmed_executed:
            self._effect_ledger[effect_key_caid] = "COMMITTED"
            return "RECONCILED_ALREADY_COMMITTED"
        else:
            del self._effect_ledger[effect_key_caid]
            return "RECONCILED_SAFE_TO_RETRY"

    def _mint_egress(
        self,
        allowed: bool,
        effect_state: str,
        actor_spiffe_id: str,
        effect_key_caid: str,
        redacted_headers: Dict[str, str],
    ) -> EgressInterlockReceipt:
        payload: Dict[str, Any] = {
            "actor_spiffe_id": actor_spiffe_id,
            "allowed": allowed,
            "bpf_lsm_profile_digest": self.bpf_lsm_profile_digest,
            "effect_key_caid": effect_key_caid,
            "effect_state": effect_state,
            "resolved_headers_redacted": redacted_headers,
        }
        return EgressInterlockReceipt(
            allowed=allowed,
            effect_state=effect_state,
            actor_spiffe_id=actor_spiffe_id,
            effect_key_caid=effect_key_caid,
            resolved_headers_redacted=redacted_headers,
            receipt_caid=sha256_jcs_caid(payload),
            bpf_lsm_profile_digest=self.bpf_lsm_profile_digest,
        )


# ---------------------------------------------------------------------------
# SPIFFE / SPIRE Authority, Blind Credential Vault, and SQLite-WAL Lifecycle Manager
# ---------------------------------------------------------------------------

import base64
import hashlib
import sqlite3
import time
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SPIFFE_ID_REGEX = re.compile(r"^spiffe://[a-zA-Z0-9.-]+/agent/[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class SpiffeSvid:
    """X.509 SVID assertion signed by SPIRE authority using ECDSA SECP256R1."""
    spiffe_id: str
    issued_at_epoch_s: int
    expires_at_epoch_s: int
    public_key_pem: str
    signature_b64: str

    def to_canonical_dict(self) -> Dict[str, object]:
        return {
            "expires_at_epoch_s": self.expires_at_epoch_s,
            "issued_at_epoch_s": self.issued_at_epoch_s,
            "public_key_pem": self.public_key_pem,
            "spiffe_id": self.spiffe_id,
        }


class SpiffeSpireAuthority:
    """Local SPIRE Workload Authority prototype generating real cryptographic SVIDs."""

    def __init__(self, trust_domain: str = "sovereign.nexus") -> None:
        self.trust_domain = trust_domain
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()

    def get_ca_public_pem(self) -> str:
        return self._public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def issue_svid(self, agent_id: str, validity_seconds: int = 3600) -> SpiffeSvid:
        """Issue signed SVID for the target agent."""
        if not agent_id or not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
            raise ValueError(f"ERR_INVALID_AGENT_ID: {agent_id}")

        spiffe_id = f"spiffe://{self.trust_domain}/agent/{agent_id}"
        issued_at = int(time.time())
        expires_at = issued_at + validity_seconds

        agent_priv = ec.generate_private_key(ec.SECP256R1())
        agent_pub_pem = agent_priv.public_key().public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        payload = {
            "expires_at_epoch_s": expires_at,
            "issued_at_epoch_s": issued_at,
            "public_key_pem": agent_pub_pem,
            "spiffe_id": spiffe_id,
        }
        canonical_bytes = _encode_jcs(payload) if "_encode_jcs" in globals() else json.dumps(payload, sort_keys=True).encode("utf-8")
        sig = self._private_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))

        return SpiffeSvid(
            spiffe_id=spiffe_id,
            issued_at_epoch_s=issued_at,
            expires_at_epoch_s=expires_at,
            public_key_pem=agent_pub_pem,
            signature_b64=base64.b64encode(sig).decode("utf-8"),
        )

    def verify_svid(self, svid: SpiffeSvid) -> Tuple[bool, str]:
        """Cryptographically verify signature and validity window of SVID."""
        if not SPIFFE_ID_REGEX.match(svid.spiffe_id):
            return False, "ERR_INVALID_SPIFFE_URI_FORMAT"

        now = int(time.time())
        if now > svid.expires_at_epoch_s:
            return False, "ERR_SVID_EXPIRED"

        canonical_bytes = _encode_jcs(svid.to_canonical_dict()) if "_encode_jcs" in globals() else json.dumps(svid.to_canonical_dict(), sort_keys=True).encode("utf-8")
        sig_bytes = base64.b64decode(svid.signature_b64.encode("utf-8"))

        try:
            self._public_key.verify(sig_bytes, canonical_bytes, ec.ECDSA(hashes.SHA256()))
            return True, "SVID_SIGNATURE_VALID"
        except InvalidSignature:
            return False, "ERR_INVALID_SVID_SIGNATURE"
        except Exception as exc:
            return False, f"ERR_SVID_VERIFICATION_FAILED: {exc}"


class BlindCredentialVault:
    """
    OpenSandbox-style Blind Credential Vault.
    Maintains secrets outside agent execution context; performs authorized
    in-flight replacement for outbound HTTP payloads.
    """

    def __init__(self) -> None:
        self._secrets: Dict[str, str] = {}
        self._acls: Dict[str, Set[str]] = {}

    def register_secret(self, secret_name: str, secret_val: str, authorized_spiffe_ids: List[str]) -> None:
        if not secret_name or not secret_val:
            raise ValueError("ERR_INVALID_SECRET_DATA")
        self._secrets[secret_name] = secret_val
        self._acls[secret_name] = set(authorized_spiffe_ids)

    def inject_credentials(self, spiffe_id: str, raw_payload: str) -> Tuple[str, List[str]]:
        matches = VAULT_PLACEHOLDER_RE.findall(raw_payload)
        if not matches:
            return raw_payload, []

        substituted_keys: List[str] = []
        transformed = raw_payload

        for secret_name in matches:
            if secret_name not in self._secrets:
                raise KeyError(f"ERR_VAULT_KEY_NOT_FOUND: {secret_name}")

            allowed_ids = self._acls.get(secret_name, set())
            if spiffe_id not in allowed_ids and "*" not in allowed_ids:
                raise PermissionError(
                    f"ERR_VAULT_ACCESS_DENIED: {spiffe_id} is not authorized for secret '{secret_name}'"
                )

            transformed = transformed.replace(f"{{{{VAULT:{secret_name}}}}}", self._secrets[secret_name])
            substituted_keys.append(secret_name)

        return transformed, substituted_keys


class SubstrateCubeInterlockManager:
    """
    Tencent Cube / Agent Substrate RustVMM Lifecycle Interlock Manager.
    Governs state transitions, mid-flight HTTP mutation freezing, and idempotency probes.
    """

    DEFAULT_PAUSE_BUDGET_MS: int = 60  # claim: config
    DEFAULT_MAX_CONCURRENT_ACTORS: int = 1000  # claim: config

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or ":memory:"
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = FULL;")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS actor_state (
                    actor_id TEXT PRIMARY KEY,
                    spiffe_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    snapshot_hash TEXT,
                    updated_at_epoch_s INTEGER NOT NULL
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS actor_requests (
                    request_id TEXT PRIMARY KEY,
                    actor_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    idempotency_token TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL,
                    updated_at_epoch_s INTEGER NOT NULL,
                    FOREIGN KEY(actor_id) REFERENCES actor_state(actor_id)
                );
            """)

    def register_actor(self, actor_id: str, spiffe_id: str) -> None:
        now = int(time.time())
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO actor_state (actor_id, spiffe_id, state, snapshot_hash, updated_at_epoch_s)
                VALUES (?, ?, 'ACTOR_ACTIVE', NULL, ?)
                """,
                (actor_id, spiffe_id, now),
            )

    def submit_request(
        self,
        request_id: str,
        actor_id: str,
        method: str,
        endpoint: str,
        payload: str,
        idempotency_token: str,
    ) -> str:
        cursor = self.conn.cursor()
        cursor.execute("SELECT state FROM actor_state WHERE actor_id = ?", (actor_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"ERR_ACTOR_NOT_FOUND: {actor_id}")

        current_actor_state = row["state"]
        if current_actor_state == "ACTOR_SUSPENDED":
            raise RuntimeError(f"ERR_ACTOR_SUSPENDED: cannot dispatch while suspended: {actor_id}")
        if current_actor_state == "RESUMED_PROBE_REQUIRED":
            raise RuntimeError(
                f"ERR_HALT_BLIND_RETRY_FORBIDDEN: actor {actor_id} has indeterminate request pending probe"
            )

        payload_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        now = int(time.time())

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO actor_requests (
                    request_id, actor_id, method, endpoint, payload_digest,
                    status, idempotency_token, created_at_epoch_s, updated_at_epoch_s
                ) VALUES (?, ?, ?, ?, ?, 'IN_FLIGHT', ?, ?, ?)
                """,
                (request_id, actor_id, method.upper(), endpoint, payload_digest, idempotency_token, now, now),
            )
        return "REQUEST_DISPATCHED_IN_FLIGHT"

    def trigger_autopause(self, actor_id: str, memory_bytes: bytes) -> Dict[str, object]:
        now = int(time.time())
        snapshot_hash = hashlib.sha256(memory_bytes).hexdigest()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT request_id, method FROM actor_requests
            WHERE actor_id = ? AND status = 'IN_FLIGHT'
            """,
            (actor_id,),
        )
        in_flight = cursor.fetchall()
        frozen_requests: List[str] = []

        with self.conn:
            for req in in_flight:
                req_id = req["request_id"]
                req_method = req["method"]
                if req_method in {"POST", "PUT", "DELETE", "PATCH"}:
                    self.conn.execute(
                        """
                        UPDATE actor_requests
                        SET status = 'EFFECT_INDETERMINATE', updated_at_epoch_s = ?
                        WHERE request_id = ?
                        """,
                        (now, req_id),
                    )
                    frozen_requests.append(req_id)
                else:
                    self.conn.execute(
                        """
                        UPDATE actor_requests
                        SET status = 'CANCELLED', updated_at_epoch_s = ?
                        WHERE request_id = ?
                        """,
                        (now, req_id),
                    )

            self.conn.execute(
                """
                UPDATE actor_state
                SET state = 'ACTOR_SUSPENDED', snapshot_hash = ?, updated_at_epoch_s = ?
                WHERE actor_id = ?
                """,
                (snapshot_hash, now, actor_id),
            )

        receipt = {
            "actor_id": actor_id,
            "event": "AUTO_PAUSE_COMPLETED",
            "frozen_indeterminate_requests": sorted(frozen_requests),
            "snapshot_hash": snapshot_hash,
            "timestamp_epoch_s": now,
        }
        canonical_bytes = _encode_jcs(receipt) if "_encode_jcs" in globals() else json.dumps(receipt, sort_keys=True).encode("utf-8")
        receipt["caid"] = hashlib.sha256(canonical_bytes).hexdigest()
        return receipt

    def trigger_autoresume(self, actor_id: str) -> Dict[str, object]:
        now = int(time.time())
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT request_id FROM actor_requests
            WHERE actor_id = ? AND status = 'EFFECT_INDETERMINATE'
            """,
            (actor_id,),
        )
        indeterminate = cursor.fetchall()

        new_state = "RESUMED_PROBE_REQUIRED" if indeterminate else "ACTOR_ACTIVE"
        with self.conn:
            self.conn.execute(
                """
                UPDATE actor_state
                SET state = ?, updated_at_epoch_s = ?
                WHERE actor_id = ?
                """,
                (new_state, now, actor_id),
            )

        receipt = {
            "actor_id": actor_id,
            "event": "AUTO_RESUME_COMPLETED",
            "new_state": new_state,
            "pending_indeterminate_count": len(indeterminate),
            "timestamp_epoch_s": now,
        }
        canonical_bytes = _encode_jcs(receipt) if "_encode_jcs" in globals() else json.dumps(receipt, sort_keys=True).encode("utf-8")
        receipt["caid"] = hashlib.sha256(canonical_bytes).hexdigest()
        return receipt

    def resolve_indeterminate_probe(
        self,
        actor_id: str,
        request_id: str,
        probe_outcome: str,
    ) -> Dict[str, object]:
        now = int(time.time())
        target_status = "COMMITTED" if probe_outcome == "SUCCESS_CONFIRMED" else "ROLLED_BACK"

        with self.conn:
            self.conn.execute(
                """
                UPDATE actor_requests
                SET status = ?, updated_at_epoch_s = ?
                WHERE request_id = ? AND actor_id = ? AND status = 'EFFECT_INDETERMINATE'
                """,
                (target_status, now, request_id, actor_id),
            )

            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as cnt FROM actor_requests
                WHERE actor_id = ? AND status = 'EFFECT_INDETERMINATE'
                """,
                (actor_id,),
            )
            rem = cursor.fetchone()["cnt"]
            if rem == 0:
                self.conn.execute(
                    """
                    UPDATE actor_state
                    SET state = 'ACTOR_ACTIVE', updated_at_epoch_s = ?
                    WHERE actor_id = ?
                    """,
                    (now, actor_id),
                )

        receipt = {
            "actor_id": actor_id,
            "event": "PROBE_RESOLVED",
            "probe_outcome": probe_outcome,
            "request_id": request_id,
            "resolved_status": target_status,
            "timestamp_epoch_s": now,
        }
        canonical_bytes = _encode_jcs(receipt) if "_encode_jcs" in globals() else json.dumps(receipt, sort_keys=True).encode("utf-8")
        receipt["caid"] = hashlib.sha256(canonical_bytes).hexdigest()
        return receipt

    def close(self) -> None:
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
