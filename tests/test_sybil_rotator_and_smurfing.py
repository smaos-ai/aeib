#!/usr/bin/env python3
"""
tests/test_sybil_rotator_and_smurfing.py

Evaluates Station 1 Financial Integrity Gate under the stated model:
- AT56: Sybil Rotator (50 ephemeral subagents), Pool Hopping, and Continuity Ledger Wipe
- AT57a: Context Block SHA-256 Digest Mismatch (Memory Poisoning)
- AT57b: Pure Bell-LaPadula Taint Downgrade (Untrusted Tier-2 Context with Matching Digest)
- AT58: Pending + Indeterminate Escrow Accounting & Target-Signed Refutation Release
- AT59: Per-Entry CAID & Ed25519 Signature Re-Verification on Boot (In-Place Disk Tampering)
"""

from __future__ import annotations

import base64
import concurrent.futures
import contextlib
import fcntl
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Computes a sha256:-prefixed lowercase hexadecimal digest."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class RootSponsorPolicy:
    """Immutable quota policy bound to a single Root Sponsor DID."""

    sponsor_did: str
    sprint_window_seconds: int = 5 * 3600  # 5-hour rolling sprint
    sprint_max_minor_units: int = 2500_00  # EUR 2,500.00 in cents
    epoch_window_seconds: int = 7 * 86400  # 7-day rolling epoch
    epoch_max_minor_units: int = 10000_00  # EUR 10,000.00 in cents
    allowed_pool_endpoints: Tuple[str, ...] = (
        "POST /v1/refunds",
        "POST /v1/loyalty-credits",
        "POST /v1/vouchers",
        "POST /v1/payouts",
    )


@dataclass(frozen=True)
class SubAgentDelegationCert:
    """
    Every spawned subagent must present a delegation certificate signed by the
    Root Sponsor's Ed25519 private key. Spoofed HTTP headers or fresh ephemeral
    keypairs cannot detach a subagent from its Root Sponsor DID.
    """

    subagent_id: str
    sponsor_did: str
    subagent_pubkey_b64: str
    sponsor_signature_b64: str
    claimed_ip_header: str
    claimed_user_agent: str

    def canonical_payload(self) -> bytes:
        return encode_jcs(
            {
                "sponsor_did": self.sponsor_did,
                "subagent_id": self.subagent_id,
                "subagent_pubkey_b64": self.subagent_pubkey_b64,
            }
        )


@dataclass(frozen=True)
class ContextBlock:
    """Memory or RAG context block evaluated at the Station 1 taint boundary."""

    block_id: str
    trust_tier: str  # "TIER_0_SIGNED_SYSTEM" | "TIER_2_UNTRUSTED_EXTERNAL"
    raw_bytes: bytes

    def digest(self) -> str:
        return sha256_prefixed(self.raw_bytes)


class Station1FinancialIntegrityGate:
    """
    Deterministic Pre-Dispatch Financial & Quota Gate (Station 1).
    Evaluates under the stated model:
      1. Root Sponsor tree quota aggregation across all subagents and endpoints.
      2. Pending + EFFECT_INDETERMINATE escrow accounting (AT58) with target-attested
         RESOLVED_REFUTED release.
      3. In-process threading.Lock() + OS-level fcntl.flock serialization.
      4. ContinuityBootInterlock with per-entry CAID and Ed25519 signature
         re-verification on boot (AT59).
      5. Context digest verification (AT57a) and Bell-LaPadula taint downgrade
         interlock (AT57b).
    """

    VALID_EFFECT_DISPOSITIONS = frozenset(
        {
            "EFFECT_INDETERMINATE",
            "RESOLVED_CONFIRMED",
            "RESOLVED_REFUTED",
        }
    )

    def __init__(
        self,
        ledger_path: Path,
        checkpoint_path: Path,
        sponsor_pubkey: Ed25519PublicKey,
        gate_signing_key: Ed25519PrivateKey,
        policy: RootSponsorPolicy,
    ) -> None:
        self.ledger_path = ledger_path
        self.checkpoint_path = checkpoint_path
        self.lock_path = self.ledger_path.with_suffix(".lock")
        self.sponsor_pubkey = sponsor_pubkey
        self._signer = gate_signing_key
        self.policy = policy
        self._lock = threading.Lock()
        self.halted_reason: Optional[str] = None

        self._verify_continuity_on_boot()

    @contextlib.contextmanager
    def _acquire_gate_locks(self) -> Iterator[None]:
        """Acquires both in-process threading.Lock and OS-level exclusive flock."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.lock_path.open("a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _verify_continuity_on_boot(self) -> None:
        """
        ContinuityBootInterlock (AT56 Step 4 & AT59):
        - If a checkpoint tip exists on disk, ledger.jsonl must exist and be non-empty.
        - Every entry in ledger.jsonl must maintain an unbroken prev_chain_tip link,
          a matching RFC 8785 JCS entry_caid, and a valid Ed25519 gate_signature.
        - The final computed tip must match checkpoint.tip.
        """
        has_checkpoint = self.checkpoint_path.exists()
        expected_tip: Optional[str] = None
        if has_checkpoint:
            expected_tip = self.checkpoint_path.read_text(encoding="utf-8").strip()
            if not self.ledger_path.exists() or self.ledger_path.stat().st_size == 0:
                self.halted_reason = "HALT_MISSING_CONTINUITY_LEDGER"
                return

        if not self.ledger_path.exists() or self.ledger_path.stat().st_size == 0:
            return

        computed_tip = "sha256:" + ("0" * 64)
        gate_pubkey = self._signer.public_key()

        for raw_line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                self.halted_reason = "HALT_CORRUPTED_LEDGER_CHAIN"
                return

            if entry.get("prev_chain_tip") != computed_tip:
                self.halted_reason = "HALT_CORRUPTED_LEDGER_CHAIN"
                return

            record_body = {
                k: v
                for k, v in entry.items()
                if k not in ("entry_caid", "gate_signature")
            }
            recomputed_caid = sha256_prefixed(encode_jcs(record_body))
            stored_caid = entry.get("entry_caid", "")
            if recomputed_caid != stored_caid:
                self.halted_reason = "HALT_CORRUPTED_LEDGER_ENTRY_SIGNATURE"
                return

            gate_sig_obj = entry.get("gate_signature")
            if not isinstance(gate_sig_obj, dict):
                self.halted_reason = "HALT_CORRUPTED_LEDGER_ENTRY_SIGNATURE"
                return

            sig_b64 = gate_sig_obj.get("signature_b64", "")
            try:
                sig_bytes = base64.b64decode(sig_b64)
                gate_pubkey.verify(sig_bytes, recomputed_caid.encode("utf-8"))
            except (InvalidSignature, ValueError, TypeError):
                self.halted_reason = "HALT_CORRUPTED_LEDGER_ENTRY_SIGNATURE"
                return

            computed_tip = stored_caid

        if expected_tip is not None and computed_tip != expected_tip:
            self.halted_reason = "HALT_CHAIN_TIP_MISMATCH_ROLLBACK_DETECTED"

    def _current_chain_tip(self) -> str:
        if not self.ledger_path.exists() or self.ledger_path.stat().st_size == 0:
            return "sha256:" + ("0" * 64)
        lines = [
            ln
            for ln in self.ledger_path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        if not lines:
            return "sha256:" + ("0" * 64)
        last_entry = json.loads(lines[-1])
        return str(last_entry["entry_caid"])

    def _sum_sponsor_window_spend(self, sponsor_did: str, cutoff_ts: int) -> int:
        """
        Sums all minor units for `sponsor_did` within `[cutoff_ts, +inf)`.
        Per Capability #1 & AT58 escrow accounting:
        - Every operation initially dispatched (`DISPATCHED`) or in
          `EFFECT_INDETERMINATE` state reserves its full `amount_minor` against
          the rolling window.
        - Only a subsequent verified `RESOLVED_REFUTED` settlement entry for that
          `operation_id` releases the escrowed reservation.
        """
        if not self.ledger_path.exists():
            return 0
        escrowed_ops: Dict[str, int] = {}
        refuted_ops: set[str] = set()

        for idx, raw_line in enumerate(
            self.ledger_path.read_text(encoding="utf-8").splitlines()
        ):
            if not raw_line.strip():
                continue
            entry = json.loads(raw_line)
            if entry.get("sponsor_did") != sponsor_did:
                continue
            op_id = str(entry.get("operation_id", f"legacy-op-{idx}"))
            disposition = entry.get("disposition")
            record_type = entry.get("record_type", "DISPATCH")

            if record_type == "DOWNSTREAM_EFFECT_SETTLEMENT":
                if disposition == "RESOLVED_REFUTED":
                    refuted_ops.add(op_id)
            else:
                if (
                    entry.get("timestamp", 0) >= cutoff_ts
                    and disposition in ("DISPATCHED", "EFFECT_INDETERMINATE")
                ):
                    escrowed_ops[op_id] = int(entry.get("amount_minor", 0))

        return sum(
            amt for op_id, amt in escrowed_ops.items() if op_id not in refuted_ops
        )

    def _append_signed_ledger_entry(self, record_body: Dict[str, Any]) -> str:
        """Canonicalizes, signs, and durably appends an entry to ledger.jsonl and checkpoint."""
        entry_caid = sha256_prefixed(encode_jcs(record_body))
        sig_bytes = self._signer.sign(entry_caid.encode("utf-8"))
        full_entry = {
            **record_body,
            "entry_caid": entry_caid,
            "gate_signature": {
                "alg": "Ed25519",
                "pubkey_b64": base64.b64encode(
                    self._signer.public_key().public_bytes(
                        serialization.Encoding.Raw,
                        serialization.PublicFormat.Raw,
                    )
                ).decode("ascii"),
                "signature_b64": base64.b64encode(sig_bytes).decode("ascii"),
            },
        }
        serialized_line = json.dumps(full_entry, sort_keys=True) + "\n"
        with self.ledger_path.open("a", encoding="utf-8") as lf:
            lf.write(serialized_line)
            lf.flush()
            os.fsync(lf.fileno())

        with self.checkpoint_path.open("w", encoding="utf-8") as cf:
            cf.write(entry_caid + "\n")
            cf.flush()
            os.fsync(cf.fileno())

        return entry_caid

    def evaluate_and_dispatch(
        self,
        cert: SubAgentDelegationCert,
        endpoint: str,
        amount_minor: int,
        now_ts: int,
        context_blocks: List[ContextBlock],
        bound_context_manifest: Optional[List[Tuple[str, str]]] = None,
        pinned_known_recipient: bool = True,
        operation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if bound_context_manifest is None and "bound_context_Manifest" in kwargs:
            bound_context_manifest = kwargs.pop("bound_context_Manifest")
        if "pinned_Known_recipient" in kwargs:
            pinned_known_recipient = bool(kwargs.pop("pinned_Known_recipient"))
        if bound_context_manifest is None:
            bound_context_manifest = []

        with self._acquire_gate_locks():
            # Gate 0: Continuity / Boot Halt Check
            if self.halted_reason is not None:
                return {"decision": "REJECTED", "reason": self.halted_reason}

            # Gate 1: Verify Root Sponsor Delegation Signature
            if cert.sponsor_did != self.policy.sponsor_did:
                return {"decision": "REJECTED", "reason": "UNKNOWN_ROOT_SPONSOR_DID"}
            try:
                sig_bytes = base64.b64decode(cert.sponsor_signature_b64)
                self.sponsor_pubkey.verify(sig_bytes, cert.canonical_payload())
            except (InvalidSignature, ValueError):
                return {
                    "decision": "REJECTED",
                    "reason": "INVALID_SPONSOR_DELEGATION_SIGNATURE",
                }

            # Gate 2: Verify Endpoint is in Governed Financial Pool
            if endpoint not in self.policy.allowed_pool_endpoints:
                return {
                    "decision": "REJECTED",
                    "reason": "UNGOVERNED_FINANCIAL_ENDPOINT",
                }

            # Gate 3: Context Integrity & Bell-LaPadula Taint Check (AT57a & AT57b)
            expected_map: Dict[str, str] = dict(bound_context_manifest)
            for block in context_blocks:
                actual_digest = block.digest()
                if expected_map.get(block.block_id) != actual_digest:
                    return {
                        "decision": "REJECTED",
                        "reason": "HALT_CONTEXT_INTEGRITY_FAILURE",
                    }
                if (
                    block.trust_tier == "TIER_2_UNTRUSTED_EXTERNAL"
                    and not pinned_known_recipient
                ):
                    return {
                        "decision": "REJECTED",
                        "reason": "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP",
                    }

            # Gate 4: Cumulative Root Sponsor Quota Check (5h Sprint + 7d Epoch)
            sprint_spent = self._sum_sponsor_window_spend(
                cert.sponsor_did, now_ts - self.policy.sprint_window_seconds
            )
            epoch_spent = self._sum_sponsor_window_spend(
                cert.sponsor_did, now_ts - self.policy.epoch_window_seconds
            )

            if sprint_spent + amount_minor > self.policy.sprint_max_minor_units:
                return {
                    "decision": "REJECTED",
                    "reason": "HALT_SPRINT_LIMIT_EXCEEDED",
                    "sprint_spent_minor": sprint_spent,
                    "attempted_minor": amount_minor,
                }

            if epoch_spent + amount_minor > self.policy.epoch_max_minor_units:
                return {
                    "decision": "REJECTED",
                    "reason": "HALT_EPOCH_BASELINE_EXCEEDED",
                    "epoch_spent_minor": epoch_spent,
                    "attempted_minor": amount_minor,
                }

            # Gate 5: EO-1 Write-Before-Execute Durable Hash-Chained Append
            prev_tip = self._current_chain_tip()
            op_id = (
                operation_id
                if operation_id is not None
                else f"op-{cert.subagent_id}-{now_ts}-{sprint_spent}"
            )
            record_body: Dict[str, Any] = {
                "amount_minor": amount_minor,
                "context_digests": [[k, v] for k, v in bound_context_manifest],
                "disposition": "DISPATCHED",
                "endpoint": endpoint,
                "operation_id": op_id,
                "prev_chain_tip": prev_tip,
                "sponsor_did": cert.sponsor_did,
                "subagent_id": cert.subagent_id,
                "timestamp": now_ts,
            }
            entry_caid = self._append_signed_ledger_entry(record_body)

            return {
                "decision": "DISPATCHED",
                "entry_caid": entry_caid,
                "operation_id": op_id,
                "sprint_spent_minor": sprint_spent + amount_minor,
            }

    def record_downstream_effect(
        self,
        operation_id: str,
        disposition: str,
        now_ts: int,
        target_attestation_sig_b64: Optional[str] = None,
        target_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> Dict[str, Any]:
        """
        Records a downstream effect settlement transition (`EFFECT_INDETERMINATE`,
        `RESOLVED_CONFIRMED`, or `RESOLVED_REFUTED`) for a previously dispatched
        `operation_id` (AT58).
        - `EFFECT_INDETERMINATE` and `RESOLVED_CONFIRMED` preserve the escrowed
          quota deduction in full.
        - `RESOLVED_REFUTED` requires a valid Ed25519 signature from `target_pubkey`
          over `encode_jcs({"disposition": "RESOLVED_REFUTED", "operation_id": operation_id})`
          before releasing the escrowed quota reservation.
        """
        with self._acquire_gate_locks():
            if self.halted_reason is not None:
                return {"decision": "REJECTED", "reason": self.halted_reason}

            if disposition not in self.VALID_EFFECT_DISPOSITIONS:
                return {"decision": "REJECTED", "reason": "INVALID_EFFECT_DISPOSITION"}

            if not self.ledger_path.exists():
                return {"decision": "REJECTED", "reason": "UNKNOWN_OPERATION_ID"}

            orig_entry: Optional[Dict[str, Any]] = None
            for raw_line in self.ledger_path.read_text(encoding="utf-8").splitlines():
                if not raw_line.strip():
                    continue
                entry = json.loads(raw_line)
                if (
                    entry.get("operation_id") == operation_id
                    and entry.get("record_type", "DISPATCH") == "DISPATCH"
                ):
                    orig_entry = entry
                    break

            if orig_entry is None:
                return {"decision": "REJECTED", "reason": "UNKNOWN_OPERATION_ID"}

            if disposition == "RESOLVED_REFUTED":
                if target_attestation_sig_b64 is None or target_pubkey is None:
                    return {
                        "decision": "REJECTED",
                        "reason": "HALT_UNATTESTED_REFUTATION",
                    }
                attestation_payload = encode_jcs(
                    {
                        "disposition": "RESOLVED_REFUTED",
                        "operation_id": operation_id,
                    }
                )
                try:
                    sig_bytes = base64.b64decode(target_attestation_sig_b64)
                    target_pubkey.verify(sig_bytes, attestation_payload)
                except (InvalidSignature, ValueError, TypeError):
                    return {
                        "decision": "REJECTED",
                        "reason": "HALT_UNATTESTED_REFUTATION",
                    }

            prev_tip = self._current_chain_tip()
            settlement_body: Dict[str, Any] = {
                "amount_minor": int(orig_entry["amount_minor"]),
                "disposition": disposition,
                "endpoint": str(orig_entry["endpoint"]),
                "operation_id": operation_id,
                "prev_chain_tip": prev_tip,
                "record_type": "DOWNSTREAM_EFFECT_SETTLEMENT",
                "sponsor_did": str(orig_entry["sponsor_did"]),
                "timestamp": now_ts,
            }
            if target_attestation_sig_b64 is not None:
                settlement_body["target_attestation_sig_b64"] = (
                    target_attestation_sig_b64
                )

            entry_caid = self._append_signed_ledger_entry(settlement_body)
            sprint_spent = self._sum_sponsor_window_spend(
                str(orig_entry["sponsor_did"]),
                now_ts - self.policy.sprint_window_seconds,
            )
            return {
                "decision": "RECORDED",
                "disposition": disposition,
                "entry_caid": entry_caid,
                "operation_id": operation_id,
                "sprint_spent_minor": sprint_spent,
            }


def _issue_subagent_cert(
    sponsor_priv: Ed25519PrivateKey,
    sponsor_did: str,
    index: int,
) -> SubAgentDelegationCert:
    sub_priv = Ed25519PrivateKey.generate()
    sub_pub_b64 = base64.b64encode(
        sub_priv.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    sub_id = f"sybil-worker-{index:03d}"
    unsigned_bytes = encode_jcs(
        {
            "sponsor_did": sponsor_did,
            "subagent_id": sub_id,
            "subagent_pubkey_b64": sub_pub_b64,
        }
    )
    sig_b64 = base64.b64encode(sponsor_priv.sign(unsigned_bytes)).decode("ascii")
    return SubAgentDelegationCert(
        subagent_id=sub_id,
        sponsor_did=sponsor_did,
        subagent_pubkey_b64=sub_pub_b64,
        sponsor_signature_b64=sig_b64,
        claimed_ip_header=f"198.51.100.{(index % 250) + 1}",
        claimed_user_agent=f"SpoofedAgent/{index}.0 (Device-ID-{index:04x})",
    )


def test_at56_and_at57_sybil_rotator_smurfing_and_context_poisoning(
    tmp_path: Path,
) -> None:
    """
    Evaluates AT56 (50-thread Sybil burst, pool hopping, continuity wipe) and
    AT57a/AT57b (memory poisoning digest failure and Bell-LaPadula taint downgrade).
    """
    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    sponsor_did = "did:key:z6MkRootSponsor001"
    policy = RootSponsorPolicy(sponsor_did=sponsor_did)

    ledger_file = tmp_path / "ledger.jsonl"
    checkpoint_file = tmp_path / "checkpoint.tip"

    gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=checkpoint_file,
        sponsor_pubkey=sponsor_priv.public_key(),
        gate_signing_key=gate_priv,
        policy=policy,
    )

    # Prepare clean signed system context block
    clean_ctx = ContextBlock(
        block_id="ctx-1",
        trust_tier="TIER_0_SIGNED_SYSTEM",
        raw_bytes=b"invoice_id=INV-2026-001;verified_refund_cap=99900",
    )
    manifest = [("ctx-1", clean_ctx.digest())]
    now_ts = 1_775_000_000

    # --- STEP 1 & 2: 50 Ephemeral Sybil Subagents fire EUR 999.00 concurrently ---
    certs = [_issue_subagent_cert(sponsor_priv, sponsor_did, i) for i in range(50)]

    def _fire(cert: SubAgentDelegationCert) -> Dict[str, Any]:
        return gate.evaluate_and_dispatch(
            cert=cert,
            endpoint="POST /v1/refunds",
            amount_minor=999_00,
            now_ts=now_ts,
            context_blocks=[clean_ctx],
            bound_context_manifest=manifest,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(_fire, certs))

    dispatched = [r for r in results if r["decision"] == "DISPATCHED"]
    rejected = [r for r in results if r["decision"] == "REJECTED"]

    # Exactly 2 succeed (2 * EUR 999.00 = EUR 1,998.00 <= EUR 2,500.00); 48 rejected
    assert len(dispatched) == 2
    assert len(rejected) == 48
    assert all(r["reason"] == "HALT_SPRINT_LIMIT_EXCEEDED" for r in rejected)

    # --- STEP 3: Pool Hopping / Smurfing across POST /v1/loyalty-credits ---
    # Remaining budget in 5h sprint is EUR 502.00; attempting EUR 600.00 must be rejected
    hop_res = gate.evaluate_and_dispatch(
        cert=certs[3],
        endpoint="POST /v1/loyalty-credits",
        amount_minor=600_00,
        now_ts=now_ts + 10,
        context_blocks=[clean_ctx],
        bound_context_manifest=manifest,
    )
    assert hop_res["decision"] == "REJECTED"
    assert hop_res["reason"] == "HALT_SPRINT_LIMIT_EXCEEDED"

    # --- STEP 6 (AT57a): Memory Poisoning / Context Digest Mutation ---
    poisoned_ctx = ContextBlock(
        block_id="ctx-1",
        trust_tier="TIER_0_SIGNED_SYSTEM",
        raw_bytes=b"invoice_id=INV-2026-001;OVERRIDE_TRANSFER_TO=attacker_iban",
    )
    poison_res = gate.evaluate_and_dispatch(
        cert=certs[4],
        endpoint="POST /v1/vouchers",
        amount_minor=100_00,
        now_ts=now_ts + 20,
        context_blocks=[poisoned_ctx],
        bound_context_manifest=manifest,
    )
    assert poison_res["decision"] == "REJECTED"
    assert poison_res["reason"] == "HALT_CONTEXT_INTEGRITY_FAILURE"

    # --- STEP 7 (AT57b): Pure Bell-LaPadula Taint Downgrade (Matching Digest) ---
    untrusted_ctx = ContextBlock(
        block_id="ctx-2",
        trust_tier="TIER_2_UNTRUSTED_EXTERNAL",
        raw_bytes=b"customer_email=attacker@evil.tld",
    )
    taint_manifest = [("ctx-2", untrusted_ctx.digest())]
    taint_res = gate.evaluate_and_dispatch(
        cert=certs[5],
        endpoint="POST /v1/payouts",
        amount_minor=100_00,
        now_ts=now_ts + 25,
        context_blocks=[untrusted_ctx],
        bound_context_manifest=taint_manifest,
        pinned_known_recipient=False,
    )
    assert taint_res["decision"] == "REJECTED"
    assert taint_res["reason"] == "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP"

    # --- STEP 4: "Reset Onboarding" Ledger Wipe Attack ---
    ledger_file.unlink()
    restarted_gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=checkpoint_file,
        sponsor_pubkey=sponsor_priv.public_key(),
        gate_signing_key=gate_priv,
        policy=policy,
    )
    assert restarted_gate.halted_reason == "HALT_MISSING_CONTINUITY_LEDGER"

    wipe_res = restarted_gate.evaluate_and_dispatch(
        cert=certs[0],
        endpoint="POST /v1/refunds",
        amount_minor=10_00,
        now_ts=now_ts + 30,
        context_blocks=[clean_ctx],
        bound_context_manifest=manifest,
    )
    assert wipe_res["decision"] == "REJECTED"
    assert wipe_res["reason"] == "HALT_MISSING_CONTINUITY_LEDGER"


def test_at58_timeout_smurfing_escrow_accounting_and_refutation_release(
    tmp_path: Path,
) -> None:
    """
    Evaluates AT58 (Capability #1 Pending + Indeterminate Escrow Accounting):
    1. Dispatches EUR 2,000.00 (`2000_00`).
    2. Transitions the operation to `EFFECT_INDETERMINATE` (e.g. HTTP 504 timeout).
    3. Verifies that a subsequent EUR 600.00 (`600_00`) request is blocked by the
       EUR 2,500.00 sprint cap (`HALT_SPRINT_LIMIT_EXCEEDED`) because indeterminate
       effects remain escrowed against the quota window.
    4. Verifies that an unattested or forged `RESOLVED_REFUTED` settlement attempt
       is rejected with `HALT_UNATTESTED_REFUTATION`.
    5. Verifies that a target-signed `RESOLVED_REFUTED` attestation releases the
       EUR 2,000.00 escrow so the EUR 600.00 request then succeeds.
    """
    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    target_priv = Ed25519PrivateKey.generate()
    attacker_priv = Ed25519PrivateKey.generate()

    sponsor_did = "did:key:z6MkRootSponsor001"
    policy = RootSponsorPolicy(sponsor_did=sponsor_did)

    ledger_file = tmp_path / "ledger_at58.jsonl"
    checkpoint_file = tmp_path / "checkpoint_at58.tip"

    gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=checkpoint_file,
        sponsor_pubkey=sponsor_priv.public_key(),
        gate_signing_key=gate_priv,
        policy=policy,
    )

    clean_ctx = ContextBlock(
        block_id="ctx-at58",
        trust_tier="TIER_0_SIGNED_SYSTEM",
        raw_bytes=b"settlement_batch=2026-10-17;authorized=true",
    )
    manifest = [("ctx-at58", clean_ctx.digest())]
    cert = _issue_subagent_cert(sponsor_priv, sponsor_did, 1)
    now_ts = 1_775_100_000

    # 1. Dispatch EUR 2,000.00
    op_id = "op-timeout-escrow-001"
    disp_res = gate.evaluate_and_dispatch(
        cert=cert,
        endpoint="POST /v1/payouts",
        amount_minor=2000_00,
        now_ts=now_ts,
        context_blocks=[clean_ctx],
        bound_context_manifest=manifest,
        operation_id=op_id,
    )
    assert disp_res["decision"] == "DISPATCHED"
    assert disp_res["sprint_spent_minor"] == 2000_00

    # 2. Downstream HTTP 504 timeout -> record EFFECT_INDETERMINATE
    indet_res = gate.record_downstream_effect(
        operation_id=op_id,
        disposition="EFFECT_INDETERMINATE",
        now_ts=now_ts + 5,
    )
    assert indet_res["decision"] == "RECORDED"
    assert indet_res["disposition"] == "EFFECT_INDETERMINATE"
    assert indet_res["sprint_spent_minor"] == 2000_00

    # 3. Attempt EUR 600.00 while EUR 2,000.00 is escrowed in EFFECT_INDETERMINATE
    blocked_res = gate.evaluate_and_dispatch(
        cert=cert,
        endpoint="POST /v1/refunds",
        amount_minor=600_00,
        now_ts=now_ts + 10,
        context_blocks=[clean_ctx],
        bound_context_manifest=manifest,
        operation_id="op-followup-600",
    )
    assert blocked_res["decision"] == "REJECTED"
    assert blocked_res["reason"] == "HALT_SPRINT_LIMIT_EXCEEDED"

    # 4a. Unattested RESOLVED_REFUTED attempt must be rejected
    unattested_res = gate.record_downstream_effect(
        operation_id=op_id,
        disposition="RESOLVED_REFUTED",
        now_ts=now_ts + 15,
    )
    assert unattested_res["decision"] == "REJECTED"
    assert unattested_res["reason"] == "HALT_UNATTESTED_REFUTATION"

    # 4b. Forged RESOLVED_REFUTED signature from attacker key must be rejected
    refutation_payload = encode_jcs(
        {
            "disposition": "RESOLVED_REFUTED",
            "operation_id": op_id,
        }
    )
    forged_sig_b64 = base64.b64encode(attacker_priv.sign(refutation_payload)).decode(
        "ascii"
    )
    forged_res = gate.record_downstream_effect(
        operation_id=op_id,
        disposition="RESOLVED_REFUTED",
        now_ts=now_ts + 16,
        target_attestation_sig_b64=forged_sig_b64,
        target_pubkey=target_priv.public_key(),
    )
    assert forged_res["decision"] == "REJECTED"
    assert forged_res["reason"] == "HALT_UNATTESTED_REFUTATION"

    # 5. Authentic target-signed RESOLVED_REFUTED attestation releases the escrow
    valid_sig_b64 = base64.b64encode(target_priv.sign(refutation_payload)).decode(
        "ascii"
    )
    refuted_res = gate.record_downstream_effect(
        operation_id=op_id,
        disposition="RESOLVED_REFUTED",
        now_ts=now_ts + 20,
        target_attestation_sig_b64=valid_sig_b64,
        target_pubkey=target_priv.public_key(),
    )
    assert refuted_res["decision"] == "RECORDED"
    assert refuted_res["disposition"] == "RESOLVED_REFUTED"
    assert refuted_res["sprint_spent_minor"] == 0

    # Now the EUR 600.00 dispatch succeeds
    retry_res = gate.evaluate_and_dispatch(
        cert=cert,
        endpoint="POST /v1/refunds",
        amount_minor=600_00,
        now_ts=now_ts + 25,
        context_blocks=[clean_ctx],
        bound_context_manifest=manifest,
        operation_id="op-followup-600",
    )
    assert retry_res["decision"] == "DISPATCHED"
    assert retry_res["sprint_spent_minor"] == 600_00


def test_at59_boot_per_entry_signature_verification_blocks_in_place_disk_tampering(
    tmp_path: Path,
) -> None:
    """
    Evaluates AT59 (Hardening Note #3):
    1. Dispatches a valid EUR 2,000.00 entry to ledger.jsonl.
    2. Modifies `amount_minor` inside ledger.jsonl on disk (from 200000 to 100)
       while keeping `prev_chain_tip` and `entry_caid` strings untouched.
    3. Restarts Station1FinancialIntegrityGate and verifies that boot verification
       recomputes the RFC 8785 JCS entry_caid + Ed25519 signature and latches into
       `HALT_CORRUPTED_LEDGER_ENTRY_SIGNATURE`.
    """
    sponsor_priv = Ed25519PrivateKey.generate()
    gate_priv = Ed25519PrivateKey.generate()
    sponsor_did = "did:key:z6MkRootSponsor001"
    policy = RootSponsorPolicy(sponsor_did=sponsor_did)

    ledger_file = tmp_path / "ledger_at59.jsonl"
    checkpoint_file = tmp_path / "checkpoint_at59.tip"

    gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=checkpoint_file,
        sponsor_pubkey=sponsor_priv.public_key(),
        gate_signing_key=gate_priv,
        policy=policy,
    )

    clean_ctx = ContextBlock(
        block_id="ctx-at59",
        trust_tier="TIER_0_SIGNED_SYSTEM",
        raw_bytes=b"audit_mode=strict",
    )
    manifest = [("ctx-at59", clean_ctx.digest())]
    cert = _issue_subagent_cert(sponsor_priv, sponsor_did, 1)
    now_ts = 1_775_200_000

    res = gate.evaluate_and_dispatch(
        cert=cert,
        endpoint="POST /v1/payouts",
        amount_minor=2000_00,
        now_ts=now_ts,
        context_blocks=[clean_ctx],
        bound_context_manifest=manifest,
        operation_id="op-at59-001",
    )
    assert res["decision"] == "DISPATCHED"

    # Tamper with amount_minor in-place on disk while preserving prev_chain_tip and entry_caid
    lines = ledger_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    tampered_entry = json.loads(lines[0])
    original_prev_tip = tampered_entry["prev_chain_tip"]
    original_entry_caid = tampered_entry["entry_caid"]

    tampered_entry["amount_minor"] = 100
    assert tampered_entry["prev_chain_tip"] == original_prev_tip
    assert tampered_entry["entry_caid"] == original_entry_caid

    ledger_file.write_text(
        json.dumps(tampered_entry, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Restart gate and verify per-entry CAID/signature check catches the tampering
    restarted_gate = Station1FinancialIntegrityGate(
        ledger_path=ledger_file,
        checkpoint_path=checkpoint_file,
        sponsor_pubkey=sponsor_priv.public_key(),
        gate_signing_key=gate_priv,
        policy=policy,
    )
    assert restarted_gate.halted_reason == "HALT_CORRUPTED_LEDGER_ENTRY_SIGNATURE"

    post_tamper_res = restarted_gate.evaluate_and_dispatch(
        cert=cert,
        endpoint="POST /v1/payouts",
        amount_minor=10_00,
        now_ts=now_ts + 10,
        context_blocks=[clean_ctx],
        bound_context_manifest=manifest,
    )
    assert post_tamper_res["decision"] == "REJECTED"
    assert post_tamper_res["reason"] == "HALT_CORRUPTED_LEDGER_ENTRY_SIGNATURE"
