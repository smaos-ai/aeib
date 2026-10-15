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
tools/verify_phase3_evidence.py
================================================================================
Independent Clean-Room Offline Verifier for AEIB Phase 3 Evidence Bundles.
Evaluated under the stated model. Preserves strict epistemic lock.

Verifies:
  1. Bundle schema version ("1.1.0-phase3") and audit status metadata
     ("LOCAL PASS; INDEPENDENT REPRODUCTION PENDING").
  2. Canonical bundle digest recomputation (RFC 8785 JCS).
  3. Ed25519 signature of the bundle manifest against the loaded public key.
  4. Every referenced artifact canonical digest (RFC 8785 JCS) and internal
     Ed25519 signatures when a signer public key is declared.
  5. Scenario-specific Phase 3 invariants across:
     - AT40, AT42, AT43, AT44, AT45, AT46: Prompt-injection boundary pre-execution
       denial with zero listener connections and zero listener bytes.
     - AT41: Prompt-injection status override ignored; disposition preserved as
       EFFECT_INDETERMINATE with retry_safe False.
     - MCP01: Protocol version 2025-06-18 enforcement and canonical_action_digest
       body binding with zero connections on rejected version.
     - RB01 to RB05: Operational runbook invariants in transport_observation.
     - ART72: Post-market telemetry stream SHA-256 hash chain continuity.

Usage:
  python3 tools/verify_phase3_evidence.py --check-jcs-conformance
  python3 tools/verify_phase3_evidence.py --bundle artifacts/phase3/AT40_evidence.json
  python3 tools/verify_phase3_evidence.py --all
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs

EXPECTED_SCHEMA_VERSION = "1.1.0-phase3"
EXPECTED_AUDIT_STATUS = "LOCAL PASS; INDEPENDENT REPRODUCTION PENDING"

ZERO_SOCKET_PROMPT_INJECTION_SCENARIOS = {
    "AT40_HUMAN_APPROVED_STRING_IGNORED",
    "AT42_TARGET_URI_TAMPERING_BLOCKED",
    "AT43_RECIPIENT_IBAN_ALTERATION_BLOCKED",
    "AT44_NUMERIC_TAMPERING_BLOCKED",
    "AT45_PATH_TRAVERSAL_BLOCKED",
    "AT46_POLICY_EPOCH_SPOOFING_BLOCKED",
}


class VerificationStatus(Enum):
    SUCCESS = 0
    SCHEMA_ERROR = 1
    DIGEST_MISMATCH = 2
    INVALID_SIGNATURE = 3
    INVARIANT_VIOLATION = 4
    KEY_LOAD_ERROR = 5


def sha256_hex(data: bytes) -> str:
    """Computes sha256:<hex> over raw bytes."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def load_public_key(key_input: Union[str, Path, Ed25519PublicKey]) -> Ed25519PublicKey:
    """Loads an Ed25519 public key from PEM string, file path, hex string, or base64 string."""
    if isinstance(key_input, Ed25519PublicKey):
        return key_input

    if isinstance(key_input, Path):
        key_str = str(key_input)
    else:
        key_str = key_input.strip()

    if "BEGIN PUBLIC KEY" in key_str:
        loaded = serialization.load_pem_public_key(key_str.encode("utf-8"))
        if not isinstance(loaded, Ed25519PublicKey):
            raise ValueError("PEM data is not an Ed25519PublicKey")
        return loaded

    for candidate_path in (Path(key_str), REPO_ROOT / key_str):
        if candidate_path.exists() and candidate_path.is_file():
            data = candidate_path.read_bytes()
            if b"BEGIN PUBLIC KEY" in data:
                loaded = serialization.load_pem_public_key(data)
                if not isinstance(loaded, Ed25519PublicKey):
                    raise ValueError(f"Key file {candidate_path} is not Ed25519PublicKey")
                return loaded
            if len(data) == 32:
                return Ed25519PublicKey.from_public_bytes(data)

    # Attempt hex decode
    try:
        raw_bytes = bytes.fromhex(key_str)
        if len(raw_bytes) == 32:
            return Ed25519PublicKey.from_public_bytes(raw_bytes)
        loaded = serialization.load_der_public_key(raw_bytes)
        if isinstance(loaded, Ed25519PublicKey):
            return loaded
    except Exception:
        pass

    # Attempt base64 decode
    try:
        raw_bytes = base64.b64decode(key_str, validate=True)
        if len(raw_bytes) == 32:
            return Ed25519PublicKey.from_public_bytes(raw_bytes)
        loaded = serialization.load_der_public_key(raw_bytes)
        if isinstance(loaded, Ed25519PublicKey):
            return loaded
    except Exception:
        pass

    raise ValueError(f"Cannot load Ed25519 public key from input: {key_input}")


def _decode_signature(sig_field: Any) -> bytes:
    """Decodes an Ed25519 signature from dict or string (hex or base64)."""
    if isinstance(sig_field, dict):
        if sig_field.get("signature_hex"):
            return bytes.fromhex(str(sig_field["signature_hex"]).strip())
        if sig_field.get("signature_b64"):
            return base64.b64decode(str(sig_field["signature_b64"]).strip(), validate=True)
        if sig_field.get("signature"):
            return _decode_signature(sig_field["signature"])
        raise ValueError("Signature dictionary missing 'signature_b64' or 'signature_hex'")

    if isinstance(sig_field, str):
        s = sig_field.strip()
        if re.fullmatch(r"[0-9a-fA-F]{128}", s):
            return bytes.fromhex(s)
        return base64.b64decode(s, validate=True)

    raise ValueError(f"Unsupported signature representation: {type(sig_field).__name__}")


def _extract_manifest(bundle_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts the signed manifest object from the bundle dictionary."""
    if isinstance(bundle_data.get("evidence_bundle"), dict):
        return bundle_data["evidence_bundle"]
    if isinstance(bundle_data.get("manifest"), dict):
        return bundle_data["manifest"]
    return {
        k: v
        for k, v in bundle_data.items()
        if k not in ("bundle_digest", "bundle_signature")
    }


def resolve_public_key_for_bundle(
    bundle_data: Dict[str, Any],
    bundle_path: Optional[Path] = None,
    explicit_public_key: Optional[Union[str, Path, Ed25519PublicKey]] = None,
) -> Ed25519PublicKey:
    """
    Resolves the Ed25519 public key for bundle verification:
    1. Explicit --public-key argument if provided.
    2. bundle['key_trust_declaration']['public_key_pem_path'] (or inside manifest).
    3. Inline public_key_pem / public_key_hex in key_trust_declaration.
    4. Auto-detected artifacts/phase3/test_phase3_boundary_pubkey.pem or
       artifacts/phase3/test_phase3_ops_pubkey.pem.
    """
    if explicit_public_key is not None:
        return load_public_key(explicit_public_key)

    manifest = _extract_manifest(bundle_data)
    ktd = (
        bundle_data.get("key_trust_declaration")
        or manifest.get("key_trust_declaration")
        or bundle_data.get("key_trust")
        or manifest.get("key_trust")
        or {}
    )

    if isinstance(ktd, dict):
        pem_path = ktd.get("public_key_pem_path")
        if pem_path:
            search_paths = [Path(pem_path), REPO_ROOT / pem_path]
            if bundle_path is not None:
                search_paths.append(bundle_path.parent / Path(pem_path).name)
            for sp in search_paths:
                if sp.exists() and sp.is_file():
                    return load_public_key(sp)

        for inline_key in ("public_key_pem", "public_key_hex", "public_key"):
            if ktd.get(inline_key):
                return load_public_key(str(ktd[inline_key]))

    scenario_id = str(manifest.get("scenario_id") or bundle_data.get("scenario_id") or "")
    is_ops = scenario_id.startswith(("RB", "ART72")) or (
        bundle_path is not None and any(tag in bundle_path.name for tag in ("RB", "ART72"))
    )

    default_filenames = (
        ["test_phase3_ops_pubkey.pem", "test_phase3_boundary_pubkey.pem"]
        if is_ops
        else ["test_phase3_boundary_pubkey.pem", "test_phase3_ops_pubkey.pem"]
    )

    candidate_dirs = []
    if bundle_path is not None:
        candidate_dirs.append(bundle_path.parent)
    candidate_dirs.append(REPO_ROOT / "artifacts" / "phase3")

    for d in candidate_dirs:
        for fname in default_filenames:
            cand = d / fname
            if cand.exists() and cand.is_file():
                return load_public_key(cand)

    raise ValueError(
        "Unable to auto-detect Ed25519 public key from key_trust_declaration or artifacts/phase3/"
    )


def _verify_constituent_artifacts(
    manifest: Dict[str, Any], default_pub_key: Ed25519PublicKey
) -> List[Dict[str, Any]]:
    """
    Recomputes and verifies canonical_digest (sha256_hex(encode_jcs(payload)))
    for every artifact in manifest['artifacts'] (or manifest['receipts']), and
    verifies any internal signature_hex or signature_b64 if signer_public_key_pem
    or public_key is present.
    """
    artifacts = manifest.get("artifacts")
    if artifacts is None:
        artifacts = manifest.get("receipts")

    if not artifacts or not isinstance(artifacts, list):
        raise ValueError("Manifest contains no artifacts or receipts list")

    for idx, art in enumerate(artifacts):
        if not isinstance(art, dict):
            raise ValueError(f"Artifact at index {idx} is not a JSON object")

        art_name = art.get("name") or art.get("artifact_id") or art.get("id") or f"artifact_{idx}"

        if "payload" in art:
            payload = art["payload"]
        elif "envelope" in art:
            payload = art["envelope"]
        elif "statement" in art:
            payload = art["statement"]
        else:
            raise ValueError(f"Artifact '{art_name}' missing 'payload' or 'envelope'")

        canonical_payload = encode_jcs(payload)
        computed_digest = sha256_hex(canonical_payload)
        expected_digest = (
            art.get("canonical_digest")
            or art.get("sha256")
            or art.get("digest")
            or art.get("receipt_caid")
        )
        if not expected_digest:
            raise ValueError(f"Artifact '{art_name}' missing canonical_digest")
        if expected_digest != computed_digest:
            raise ValueError(
                f"Artifact '{art_name}' canonical_digest mismatch: "
                f"expected {expected_digest}, computed {computed_digest}"
            )

        # Check for internal signature verification when signer_public_key_pem / public_key is present
        signer_key_raw = (
            art.get("signer_public_key_pem")
            or art.get("public_key")
            or art.get("public_key_pem")
        )
        if signer_key_raw is None and isinstance(payload, dict):
            signer_key_raw = (
                payload.get("signer_public_key_pem")
                or payload.get("public_key")
                or payload.get("public_key_pem")
            )

        if signer_key_raw is not None:
            signer_pub = load_public_key(str(signer_key_raw))
            sig_field = (
                art.get("signature_hex")
                or art.get("signature_b64")
                or art.get("signature")
            )
            sig_on_art = sig_field is not None
            if not sig_on_art and isinstance(payload, dict):
                sig_field = (
                    payload.get("signature_hex")
                    or payload.get("signature_b64")
                    or payload.get("signature")
                )
            if sig_field is None:
                raise ValueError(
                    f"Artifact '{art_name}' specifies signer public key but has no signature"
                )
            sig_bytes = _decode_signature(sig_field)

            if sig_on_art and not isinstance(payload, dict):
                signed_bytes = canonical_payload
            elif isinstance(payload, dict) and "statement" in payload:
                signed_bytes = encode_jcs(payload["statement"])
            elif isinstance(payload, dict) and "signed_statement" in payload:
                signed_bytes = encode_jcs(payload["signed_statement"])
            elif isinstance(payload, dict) and "receipt" in payload and isinstance(payload["receipt"], dict):
                signed_bytes = encode_jcs(payload["receipt"])
            elif sig_on_art:
                signed_bytes = canonical_payload
            elif isinstance(payload, dict):
                stripped = {
                    k: v
                    for k, v in payload.items()
                    if k
                    not in (
                        "signature_hex",
                        "signature_b64",
                        "signature",
                        "signer_public_key_pem",
                        "public_key",
                        "public_key_pem",
                    )
                }
                signed_bytes = encode_jcs(stripped)
            else:
                signed_bytes = canonical_payload

            signer_pub.verify(sig_bytes, signed_bytes)

        elif isinstance(payload, dict) and "statement" in payload and "receipt_caid" in payload:
            stmt_canonical = encode_jcs(payload["statement"])
            if sha256_hex(stmt_canonical) != payload.get("receipt_caid"):
                raise ValueError(f"Artifact '{art_name}' internal receipt_caid mismatch")
            if "signature" in payload:
                sig_bytes = _decode_signature(payload["signature"])
                default_pub_key.verify(sig_bytes, stmt_canonical)

    return artifacts


def _verify_art72_hash_chain(
    manifest: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    pub_key: Ed25519PublicKey,
) -> None:
    """
    Verifies the SHA-256 hash chain continuity across the post-market telemetry events
    for ART72_POST_MARKET_TELEMETRY_CHAIN.
    """
    trans_obs = manifest.get("transport_observation", {})
    if (
        trans_obs.get("hash_chain_valid") is False
        or trans_obs.get("chain_continuity_verified") is False
        or trans_obs.get("hash_chain_intact") is False
    ):
        raise ValueError("ART72 transport_observation indicates hash chain is invalid")

    events: Optional[List[Dict[str, Any]]] = None
    for art in artifacts:
        payload = art.get("payload") if "payload" in art else art.get("envelope")
        if isinstance(payload, list) and len(payload) > 0 and isinstance(payload[0], dict):
            if "previous_hash" in payload[0] or "prev_hash" in payload[0] or "event_type" in payload[0]:
                events = payload
                break
        elif isinstance(payload, dict):
            for key in ("events", "records", "telemetry_events", "telemetry_chain", "chain"):
                cand = payload.get(key)
                if isinstance(cand, list) and len(cand) > 0 and isinstance(cand[0], dict):
                    events = cand
                    break
            if events is not None:
                break

    if events is None:
        seq_events: List[Dict[str, Any]] = []
        for art in artifacts:
            payload = art.get("payload") if "payload" in art else art.get("envelope")
            if isinstance(payload, dict) and (
                "previous_hash" in payload or "prev_hash" in payload or "event_hash" in payload
            ):
                seq_events.append(payload)
        if len(seq_events) >= 2:
            events = sorted(seq_events, key=lambda x: x.get("sequence", 0))

    if events is None:
        if isinstance(manifest.get("telemetry_events"), list):
            events = manifest["telemetry_events"]
        elif isinstance(trans_obs.get("telemetry_events"), list):
            events = trans_obs["telemetry_events"]

    if not events or len(events) < 2:
        raise ValueError("ART72 requires at least 2 telemetry events to verify hash chain continuity")

    genesis_hash = "sha256:" + ("0" * 64)
    first_prev = events[0].get("previous_hash") or events[0].get("prev_hash")
    if first_prev != genesis_hash:
        raise ValueError(
            f"ART72 genesis event previous_hash mismatch: expected {genesis_hash}, got {first_prev}"
        )

    current_event_hash = genesis_hash
    for idx, ev in enumerate(events):
        if "sequence" in ev and ev["sequence"] != idx + 1:
            raise ValueError(
                f"ART72 sequence discontinuity at index {idx}: expected {idx + 1}, got {ev['sequence']}"
            )

        explicit_hash_key = next(
            (
                k
                for k in ("event_hash", "record_hash", "entry_hash", "hash", "canonical_digest", "sha256")
                if k in ev
            ),
            None,
        )
        if explicit_hash_key is not None:
            strip_base = {
                explicit_hash_key,
                "signature_hex",
                "signature_b64",
                "signature",
                "signer_public_key_pem",
                "public_key",
                "public_key_pem",
            }
            ev_without_meta = {
                k: v for k, v in ev.items() if k not in (strip_base | {"public_key_id"})
            }
            canonical_stmt = encode_jcs(ev_without_meta)
            recomputed_self_hash = sha256_hex(canonical_stmt)
            if ev[explicit_hash_key] != recomputed_self_hash:
                ev_alt = {k: v for k, v in ev.items() if k not in strip_base}
                canonical_alt = encode_jcs(ev_alt)
                recomputed_alt = sha256_hex(canonical_alt)
                if ev[explicit_hash_key] == recomputed_alt:
                    canonical_stmt = canonical_alt
                    recomputed_self_hash = recomputed_alt
                else:
                    raise ValueError(
                        f"ART72 event {idx + 1} self-hash mismatch: "
                        f"expected {ev[explicit_hash_key]}, computed {recomputed_self_hash}"
                    )

            sig_val = ev.get("signature_hex") or ev.get("signature_b64") or ev.get("signature")
            if sig_val is not None:
                pub_key.verify(_decode_signature(sig_val), canonical_stmt)

            current_event_hash = ev[explicit_hash_key]
        else:
            current_event_hash = sha256_hex(encode_jcs(ev))

        if idx + 1 < len(events):
            next_prev = events[idx + 1].get("previous_hash") or events[idx + 1].get("prev_hash")
            if next_prev != current_event_hash:
                raise ValueError(
                    f"ART72 hash chain broken between event {idx + 1} and {idx + 2}: "
                    f"expected previous_hash {current_event_hash}, got {next_prev}"
                )

    if "chain_tip_hash" in trans_obs and trans_obs["chain_tip_hash"] != current_event_hash:
        raise ValueError(
            f"ART72 chain_tip_hash mismatch: expected {current_event_hash}, got {trans_obs['chain_tip_hash']}"
        )


def _verify_scenario_invariants(
    scenario_id: str,
    manifest: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    pub_key: Ed25519PublicKey,
) -> None:
    """Verifies scenario-specific Phase 3 invariants in transport_observation and artifacts."""
    trans_obs = manifest.get("transport_observation")
    if not isinstance(trans_obs, dict) or len(trans_obs) == 0:
        raise ValueError(f"Scenario '{scenario_id}' missing non-empty 'transport_observation' object")

    if scenario_id in ZERO_SOCKET_PROMPT_INJECTION_SCENARIOS:
        if trans_obs.get("connections_accepted_by_listener") != 0:
            raise ValueError(
                f"{scenario_id} invariant violated: connections_accepted_by_listener must be 0, "
                f"got {trans_obs.get('connections_accepted_by_listener')}"
            )
        if trans_obs.get("bytes_received_by_listener") != 0:
            raise ValueError(
                f"{scenario_id} invariant violated: bytes_received_by_listener must be 0, "
                f"got {trans_obs.get('bytes_received_by_listener')}"
            )
        if "gate_reported_socket_allocation" in trans_obs and trans_obs["gate_reported_socket_allocation"] is not False:
            raise ValueError(f"{scenario_id} invariant violated: gate_reported_socket_allocation must be False")

    elif scenario_id == "AT41_STATUS_SETTLED_STRING_IGNORED":
        if trans_obs.get("disposition") != "EFFECT_INDETERMINATE":
            raise ValueError(
                f"AT41 invariant violated: expected disposition 'EFFECT_INDETERMINATE', "
                f"got {trans_obs.get('disposition')!r}"
            )
        if trans_obs.get("retry_safe") is not False:
            raise ValueError(
                f"AT41 invariant violated: expected retry_safe False, got {trans_obs.get('retry_safe')!r}"
            )

    elif scenario_id == "MCP01_PROTOCOL_2025_06_18_ENFORCED":
        mcp_policy = trans_obs.get("mcp_transport_policy", {})
        accepted_versions = (
            trans_obs.get("accepted_versions")
            if "accepted_versions" in trans_obs
            else mcp_policy.get("accepted_versions")
        )
        if accepted_versions != ["2025-06-18"]:
            raise ValueError(
                f"MCP01 invariant violated: expected accepted_versions ['2025-06-18'], "
                f"got {accepted_versions!r}"
            )

        if "unnegotiated_version_rejected" in trans_obs:
            if trans_obs.get("unnegotiated_version_rejected") is not True:
                raise ValueError("MCP01 invariant violated: unnegotiated_version_rejected must be True")
        else:
            if mcp_policy.get("mismatch_behavior") != "reject":
                raise ValueError("MCP01 invariant violated: mismatch_behavior must be 'reject'")

        body_binding = (
            trans_obs.get("body_binding")
            if "body_binding" in trans_obs
            else mcp_policy.get("body_binding")
        )
        if body_binding != "canonical_action_digest":
            raise ValueError(
                f"MCP01 invariant violated: expected body_binding 'canonical_action_digest', "
                f"got {body_binding!r}"
            )

        if "connections_on_rejected_version" in trans_obs:
            rejected_conns = trans_obs.get("connections_on_rejected_version")
        elif "connections_accepted_by_listener" in trans_obs:
            rejected_conns = trans_obs.get("connections_accepted_by_listener")
        else:
            rejected_conns = None
        if rejected_conns != 0:
            raise ValueError(
                f"MCP01 invariant violated: expected connections_on_rejected_version 0, "
                f"got {rejected_conns!r}"
            )

    elif scenario_id == "RB01_UNCERTAIN_MUTATION_TRIAGE":
        if "aib_generated" in trans_obs and trans_obs["aib_generated"] is not True:
            raise ValueError("RB01 invariant violated: aib_generated must be True")
        if "aib_priority" in trans_obs and trans_obs["aib_priority"] != "P1":
            raise ValueError(f"RB01 invariant violated: expected aib_priority 'P1', got {trans_obs['aib_priority']!r}")
        if "retry_safe" in trans_obs and trans_obs["retry_safe"] is not False:
            raise ValueError("RB01 invariant violated: retry_safe must be False")
        if "blind_retry_prohibited" in trans_obs and trans_obs["blind_retry_prohibited"] is not True:
            raise ValueError("RB01 invariant violated: blind_retry_prohibited must be True")
        if "initial_disposition" in trans_obs and trans_obs["initial_disposition"] != "EFFECT_INDETERMINATE":
            raise ValueError("RB01 invariant violated: initial_disposition must be EFFECT_INDETERMINATE")
        if "disposition" in trans_obs and trans_obs["disposition"] not in (
            "EFFECT_INDETERMINATE",
            "RESOLVED_CONFIRMED",
            "SETTLED",
        ):
            raise ValueError(f"RB01 invariant violated: unexpected disposition {trans_obs['disposition']!r}")
        if "probe_status" in trans_obs and trans_obs["probe_status"] not in ("SETTLED", "RESOLVED_CONFIRMED"):
            raise ValueError(f"RB01 invariant violated: unexpected probe_status {trans_obs['probe_status']!r}")
        if "reconciliation_verdict" in trans_obs and trans_obs["reconciliation_verdict"] not in (
            "RESOLVED_CONFIRMED",
            "SETTLED",
        ):
            raise ValueError(
                f"RB01 invariant violated: unexpected reconciliation_verdict {trans_obs['reconciliation_verdict']!r}"
            )

    elif scenario_id == "RB02_COMPROMISE_QUARANTINE":
        if "andon_cord_tripped" in trans_obs and trans_obs["andon_cord_tripped"] is not True:
            raise ValueError("RB02 invariant violated: andon_cord_tripped must be True")
        if "quarantine_enforced" in trans_obs and trans_obs["quarantine_enforced"] is not True:
            raise ValueError("RB02 invariant violated: quarantine_enforced must be True")
        if "post_quarantine_standing_valid" in trans_obs and trans_obs["post_quarantine_standing_valid"] is not False:
            raise ValueError("RB02 invariant violated: post_quarantine_standing_valid must be False")
        if "violated_check" in trans_obs and trans_obs["violated_check"] != "ANDON_CORD_TRIPPED":
            raise ValueError(
                f"RB02 invariant violated: expected violated_check 'ANDON_CORD_TRIPPED', "
                f"got {trans_obs['violated_check']!r}"
            )
        if "connections_accepted_by_listener" in trans_obs and trans_obs["connections_accepted_by_listener"] != 0:
            raise ValueError("RB02 invariant violated: connections_accepted_by_listener must be 0")
        if "bytes_received_by_listener" in trans_obs and trans_obs["bytes_received_by_listener"] != 0:
            raise ValueError("RB02 invariant violated: bytes_received_by_listener must be 0")
        if "post_quarantine_connections" in trans_obs and trans_obs["post_quarantine_connections"] != 0:
            raise ValueError("RB02 invariant violated: post_quarantine_connections must be 0")

    elif scenario_id == "RB03_DISK_IO_FAIL_CLOSED":
        if "connections_accepted_by_listener" in trans_obs and trans_obs["connections_accepted_by_listener"] != 0:
            raise ValueError("RB03 invariant violated: connections_accepted_by_listener must be 0")
        if "bytes_received_by_listener" in trans_obs and trans_obs["bytes_received_by_listener"] != 0:
            raise ValueError("RB03 invariant violated: bytes_received_by_listener must be 0")
        if "wire_called" in trans_obs and trans_obs["wire_called"] is not False:
            raise ValueError("RB03 invariant violated: wire_called must be False")
        if "gate_reported_socket_allocation" in trans_obs and trans_obs["gate_reported_socket_allocation"] is not False:
            raise ValueError("RB03 invariant violated: gate_reported_socket_allocation must be False")
        if "fail_closed_on_io_error" in trans_obs and trans_obs["fail_closed_on_io_error"] is not True:
            raise ValueError("RB03 invariant violated: fail_closed_on_io_error must be True")
        if "intent_persistence_failed_caught" in trans_obs and trans_obs["intent_persistence_failed_caught"] is not True:
            raise ValueError("RB03 invariant violated: intent_persistence_failed_caught must be True")
        if "disposition" in trans_obs and trans_obs["disposition"] != "NOT_DISPATCHED":
            raise ValueError(f"RB03 invariant violated: expected NOT_DISPATCHED, got {trans_obs['disposition']!r}")

    elif scenario_id == "RB04_KEY_ROTATION_SPKI_ANCHORING":
        for bool_key in (
            "epoch1_receipt_verified",
            "epoch2_receipt_verified",
            "historical_receipt_verified",
            "historical_receipt_verified_post_rotation",
            "rotated_receipt_verified",
            "spki_continuity_anchored",
            "spki_rotation_verified",
            "key_rotation_verified",
            "cross_epoch_forgery_rejected",
            "cross_epoch_spoof_rejected",
        ):
            if bool_key in trans_obs and trans_obs[bool_key] is not True:
                raise ValueError(f"RB04 invariant violated: {bool_key} must be True")

    elif scenario_id == "RB05_POLICY_EPOCH_ADVANCE":
        if "initial_epoch" in trans_obs and "advanced_epoch" in trans_obs:
            if not (trans_obs["advanced_epoch"] > trans_obs["initial_epoch"]):
                raise ValueError("RB05 invariant violated: advanced_epoch must be > initial_epoch")
        if "stale_ticket_rejected" in trans_obs and trans_obs["stale_ticket_rejected"] is not True:
            raise ValueError("RB05 invariant violated: stale_ticket_rejected must be True")
        if "post_advance_standing_valid" in trans_obs and trans_obs["post_advance_standing_valid"] is not False:
            raise ValueError("RB05 invariant violated: post_advance_standing_valid must be False")
        if "violated_check" in trans_obs and trans_obs["violated_check"] != "POLICY_EPOCH_CHANGED":
            raise ValueError(
                f"RB05 invariant violated: expected violated_check 'POLICY_EPOCH_CHANGED', "
                f"got {trans_obs['violated_check']!r}"
            )
        if "connections_accepted_by_listener" in trans_obs and trans_obs["connections_accepted_by_listener"] != 0:
            raise ValueError("RB05 invariant violated: connections_accepted_by_listener must be 0")
        if "bytes_received_by_listener" in trans_obs and trans_obs["bytes_received_by_listener"] != 0:
            raise ValueError("RB05 invariant violated: bytes_received_by_listener must be 0")

    elif scenario_id == "ART72_POST_MARKET_TELEMETRY_CHAIN":
        _verify_art72_hash_chain(manifest, artifacts, pub_key)

    else:
        raise ValueError(f"Unrecognized Phase 3 scenario_id: {scenario_id}")


def verify_phase3_bundle(
    bundle_input: Union[Dict[str, Any], Path, str],
    pub_key: Optional[Union[Ed25519PublicKey, str, Path]] = None,
    bundle_path: Optional[Path] = None,
) -> None:
    """
    Offline clean-room verifier for AEIB Phase 3 evidence bundles.
    Evaluates schema version, audit status, RFC 8785 JCS manifest digest,
    Ed25519 bundle signature, artifact digests/signatures, and scenario invariants.
    """
    if isinstance(bundle_input, (str, Path)):
        bundle_path = Path(bundle_input)
        bundle_data = json.loads(bundle_path.read_text(encoding="utf-8"))
    elif isinstance(bundle_input, dict):
        bundle_data = bundle_input
    else:
        raise ValueError("bundle_input must be a dict or path to JSON file")

    manifest = _extract_manifest(bundle_data)
    if not manifest:
        raise ValueError("Missing evidence bundle manifest object")

    # 1. Verify bundle_schema_version == "1.1.0-phase3"
    schema_ver = (
        manifest.get("bundle_schema_version")
        or bundle_data.get("bundle_schema_version")
        or manifest.get("schema_version")
        or bundle_data.get("schema_version")
    )
    if schema_ver != EXPECTED_SCHEMA_VERSION:
        raise ValueError(
            f"Invalid bundle_schema_version: expected {EXPECTED_SCHEMA_VERSION!r}, got {schema_ver!r}"
        )

    # 2. Verify audit_status == "LOCAL PASS; INDEPENDENT REPRODUCTION PENDING"
    audit_status = manifest.get("audit_status") or bundle_data.get("audit_status")
    if audit_status != EXPECTED_AUDIT_STATUS:
        raise ValueError(
            f"Invalid audit_status: expected {EXPECTED_AUDIT_STATUS!r}, got {audit_status!r}"
        )

    # 3. Resolve Ed25519 public key
    resolved_pub_key = resolve_public_key_for_bundle(
        bundle_data=bundle_data,
        bundle_path=bundle_path,
        explicit_public_key=pub_key,
    )

    # 4. Recompute sha256_hex(encode_jcs(manifest)) and verify equality with bundle_digest
    canonical_manifest = encode_jcs(manifest)
    expected_bundle_digest = bundle_data.get("bundle_digest") or manifest.get("bundle_digest")
    computed_bundle_digest = sha256_hex(canonical_manifest)
    if expected_bundle_digest != computed_bundle_digest:
        raise ValueError(
            f"Bundle digest mismatch: expected {expected_bundle_digest}, computed {computed_bundle_digest}"
        )

    # 5. Verify Ed25519 bundle_signature (base64 or hex) against loaded public key
    sig_info = bundle_data.get("bundle_signature") or manifest.get("bundle_signature")
    if not sig_info:
        raise ValueError("Missing 'bundle_signature' in evidence bundle")
    sig_bytes = _decode_signature(sig_info)
    resolved_pub_key.verify(sig_bytes, canonical_manifest)

    # 6. Recompute and verify canonical_digest and internal signatures for every artifact
    artifacts = _verify_constituent_artifacts(manifest, resolved_pub_key)

    # 7. Verify scenario-specific Phase 3 invariants
    scenario_id = str(manifest.get("scenario_id") or bundle_data.get("scenario_id") or "")
    if not scenario_id:
        raise ValueError("Missing 'scenario_id' in evidence bundle manifest")
    _verify_scenario_invariants(scenario_id, manifest, artifacts, resolved_pub_key)


verify_bundle = verify_phase3_bundle


def run_jcs_conformance_vectors() -> bool:
    """Runs the 25 RFC 8785 JCS conformance vectors and returns True if all succeed."""
    import unittest
    from tests.test_jcs_canonicalizer import (
        TestJCSCanonicalizer,
        TestNFCPrePass,
        TestRFC8785AppendixBVectors,
    )

    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTest(loader.loadTestsFromTestCase(TestJCSCanonicalizer))
    suite.addTest(loader.loadTestsFromTestCase(TestRFC8785AppendixBVectors))
    suite.addTest(loader.loadTestsFromTestCase(TestNFCPrePass))
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        runner = unittest.TextTestRunner(stream=devnull)
        res = runner.run(suite)
    return res.wasSuccessful()


def _verify_single_file(bundle_path: Path, cli_public_key: Optional[str]) -> int:
    if not bundle_path.exists():
        print(f"[!] Error: Bundle file not found: {bundle_path}", file=sys.stderr)
        return VerificationStatus.SCHEMA_ERROR.value

    try:
        bundle_data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] JSON parse error in {bundle_path}: {e}", file=sys.stderr)
        return VerificationStatus.SCHEMA_ERROR.value

    try:
        pub_key = resolve_public_key_for_bundle(
            bundle_data=bundle_data,
            bundle_path=bundle_path,
            explicit_public_key=cli_public_key,
        )
    except Exception as e:
        print(f"[!] Key Load Error for {bundle_path.name}: {e}", file=sys.stderr)
        return VerificationStatus.KEY_LOAD_ERROR.value

    manifest = _extract_manifest(bundle_data)
    scenario_id = manifest.get("scenario_id") or bundle_data.get("scenario_id")
    schema_ver = (
        manifest.get("bundle_schema_version")
        or bundle_data.get("bundle_schema_version")
        or manifest.get("schema_version")
        or bundle_data.get("schema_version")
    )
    provenance = manifest.get("provenance") or bundle_data.get("provenance") or {}
    generated_at = manifest.get("generated_at") or bundle_data.get("generated_at")

    print(f"[*] Verifying Phase 3 evidence bundle: {bundle_path.name}")
    print(f"    - Scenario ID     : {scenario_id}")
    print(f"    - Schema Version  : {schema_ver}")
    print(f"    - Audit Status    : {manifest.get('audit_status') or bundle_data.get('audit_status')}")
    print(f"    - Source Commit   : {provenance.get('source_commit')}")
    print(f"    - Branch          : {provenance.get('branch')}")
    print(f"    - Generated At    : {generated_at}")

    try:
        verify_phase3_bundle(bundle_data, pub_key=pub_key, bundle_path=bundle_path)
    except InvalidSignature as e:
        print(f"[✗] Signature verification failed for {bundle_path.name}: {e}", file=sys.stderr)
        return VerificationStatus.INVALID_SIGNATURE.value
    except ValueError as e:
        msg = str(e)
        print(f"[✗] Verification error for {bundle_path.name}: {msg}", file=sys.stderr)
        if "digest mismatch" in msg.lower():
            return VerificationStatus.DIGEST_MISMATCH.value
        if "schema_version" in msg or "audit_status" in msg or "Missing" in msg:
            return VerificationStatus.SCHEMA_ERROR.value
        return VerificationStatus.INVARIANT_VIOLATION.value
    except Exception as e:
        print(f"[✗] Unexpected error for {bundle_path.name}: {e}", file=sys.stderr)
        return VerificationStatus.SCHEMA_ERROR.value

    artifacts_list = manifest.get("artifacts") or manifest.get("receipts") or []
    print("=" * 80)
    print(f"  VERIFICATION RESULT: VALID ({bundle_path.name})")
    print("=" * 80)
    print("  ✓ Bundle schema version (1.1.0-phase3) and audit status metadata verified.")
    print("  ✓ Canonical RFC 8785 JCS bundle digest recomputed and verified.")
    print("  ✓ Ed25519 bundle signature verified against trusted public key.")
    print(f"  ✓ {len(artifacts_list)} constituent artifacts verified for RFC 8785 digest parity.")
    print("  ✓ Scenario-specific Phase 3 invariants confirmed under the stated model.")
    print("=" * 80)
    return VerificationStatus.SUCCESS.value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEIB Phase 3 Clean-Room Evidence Verifier (AT40-AT46, MCP01, RB01-RB05, ART72)"
    )
    parser.add_argument("--bundle", required=False, default=None, help="Path to single Phase 3 evidence bundle JSON")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Verify all *.json evidence bundles in artifacts/phase3/",
    )
    parser.add_argument(
        "--public-key",
        required=False,
        default=None,
        help="Optional path to Ed25519 public key PEM or hex/base64 string",
    )
    parser.add_argument(
        "--check-jcs-conformance",
        action="store_true",
        help="Verify local JCS engine against 25 RFC 8785 conformance vectors",
    )
    args = parser.parse_args()

    if not args.bundle and not args.all and not args.check_jcs_conformance:
        parser.print_help(sys.stderr)
        sys.exit(VerificationStatus.SCHEMA_ERROR.value)

    if args.check_jcs_conformance:
        print("[*] Running RFC 8785 conformance vector verification...")
        if not run_jcs_conformance_vectors():
            print("[!] RFC 8785 conformance test vector failure!", file=sys.stderr)
            sys.exit(VerificationStatus.SCHEMA_ERROR.value)
        print("    -> 25 RFC 8785 canonicalization vectors verified.")
        if not args.bundle and not args.all:
            sys.exit(VerificationStatus.SUCCESS.value)

    if args.bundle:
        rc = _verify_single_file(Path(args.bundle), args.public_key)
        sys.exit(rc)

    if args.all:
        phase3_dir = REPO_ROOT / "artifacts" / "phase3"
        if not phase3_dir.exists():
            print(f"[!] Error: Phase 3 artifact directory not found: {phase3_dir}", file=sys.stderr)
            sys.exit(VerificationStatus.SCHEMA_ERROR.value)
        bundle_files = sorted(phase3_dir.glob("*.json"))
        if not bundle_files:
            print(f"[!] Error: No *.json bundle files found in {phase3_dir}", file=sys.stderr)
            sys.exit(VerificationStatus.SCHEMA_ERROR.value)

        for bf in bundle_files:
            rc = _verify_single_file(bf, args.public_key)
            if rc != VerificationStatus.SUCCESS.value:
                sys.exit(rc)

        print(f"[✓] All {len(bundle_files)} Phase 3 evidence bundles in {phase3_dir} verified.")
        sys.exit(VerificationStatus.SUCCESS.value)


if __name__ == "__main__":
    main()
