#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
ios_incident_emitter.py — iOS Crash Log Parser & Ed25519 Incident Notice Emitter (Wave 8 prototype).

Evaluated under the stated model: parses iOS Simulator and device crash logs (.ips format),
extracts diagnostic crash telemetry (process name, exception type, fault address), maps
signals to severity tiers, and emits Ed25519-signed incident notices serialized using RFC 8785 JCS.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs

_SHA256_CAID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _is_strict_int(value: Any) -> bool:
    return type(value) is int


class IOSIncidentEmitter:
    """
    Parses crash logs and emits cryptographically signed iOS incident notices.
    """

    VALID_SEVERITY_TIERS: FrozenSet[str] = frozenset(
        {
            "SEV_1_CRITICAL",
            "SEV_2_HIGH",
            "SEV_3_MEDIUM",
            "SEV_4_LOW",
        }
    )

    REQUIRED_ACTION_TAKEN: str = "FAIL_CLOSED_KERNEL_OR_HOOK_VETO"

    _SIGNED_FIELDS: Tuple[str, ...] = (
        "action_taken",
        "containment_latency_us",
        "evidence_bundle_caid",
        "exception_type",
        "fault_address",
        "halt_reason_code",
        "incident_id",
        "issuer_public_key_hex",
        "process_name",
        "severity_tier",
    )

    MAX_IPS_BYTES: int = 8 * 1024 * 1024

    @classmethod
    def _parse_json_ips(cls, ips_content: str) -> Optional[Tuple[str, str, str, str]]:
        """Modern .ips (observed on this host, macOS 27.2): line 1 is a JSON
        header, the rest is a JSON body with procName, exception{type,signal,
        codes,subtype}, termination{namespace,code,indicator}. Returns
        (process_name, exception_type, fault_address, signal_text) or None."""
        head, sep, body = ips_content.partition("\n")
        if not sep:
            return None
        try:
            header = json.loads(head)
            payload = json.loads(body)
        except ValueError:
            return None
        if not isinstance(header, dict) or not isinstance(payload, dict):
            return None
        exc = payload.get("exception") if isinstance(payload.get("exception"), dict) else {}
        term = payload.get("termination") if isinstance(payload.get("termination"), dict) else {}
        proc = payload.get("procName") or header.get("app_name") or header.get("name")
        exc_type = str(exc.get("type") or "UNKNOWN_EXCEPTION")
        signal = str(exc.get("signal") or "")
        codes = str(exc.get("codes") or "")
        subtype = str(exc.get("subtype") or "")
        addr_m = re.search(r"at\s+(0x[0-9a-fA-F]+)", subtype)
        fault = addr_m.group(1) if addr_m else "0x0"
        signal_text = " ".join(
            [exc_type, signal, codes, subtype, str(term.get("namespace") or ""),
             hex(term["code"]) if type(term.get("code")) is int else str(term.get("code") or ""),
             str(term.get("indicator") or ""),
             str(payload.get("asi") or "")]
        )
        label = f"{exc_type} ({signal})" if signal else exc_type
        return (str(proc) if proc else "unknown_process"), label, fault, signal_text

    @classmethod
    def parse_ips_crash_report(cls, ips_content: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Parses a JSON .ips report (two-part format) or legacy text crash log
        into a severity tier, reason code, and extracted metadata.
        """
        if not isinstance(ips_content, str) or not ips_content.strip():
            return "SEV_4_LOW", "HALT_IOS_EMPTY_CRASH_REPORT", {"parsed_successfully": False}
        if len(ips_content.encode("utf-8")) > cls.MAX_IPS_BYTES:
            return "SEV_3_MEDIUM", "HALT_IOS_CRASH_REPORT_OVERSIZE", {"parsed_successfully": False}

        parsed = cls._parse_json_ips(ips_content)
        if parsed is not None:
            process_name, exception_type, fault_address, signal_text = parsed
            fmt = "ips_json"
        else:
            proc_match = re.search(r"Process:\s*([a-zA-Z0-9_\-\.]+)", ips_content)
            process_name = proc_match.group(1) if proc_match else "unknown_process"
            exc_match = re.search(r"Exception Type:\s*([^\n\r]+)", ips_content)
            exception_type = exc_match.group(1).strip() if exc_match else "UNKNOWN_EXCEPTION"
            addr_match = re.search(r"(?:Fault Address|KERN_INVALID_ADDRESS at)\s*(0x[0-9a-fA-F]+)", ips_content)
            fault_address = addr_match.group(1) if addr_match else "0x0"
            signal_text = ips_content
            fmt = "legacy_text"
        raw_length = len(ips_content)
        ips_content = signal_text

        # Signal mapping
        if "EXC_BAD_ACCESS" in ips_content or "SIGSEGV" in ips_content or "SIGBUS" in ips_content:
            severity = "SEV_1_CRITICAL"
            reason = "HALT_IOS_MEMORY_FAULT_EXC_BAD_ACCESS"
        elif "Fatal error" in ips_content or "Swift/Unsafe" in ips_content:
            severity = "SEV_1_CRITICAL"
            reason = "HALT_IOS_SWIFT_FATAL_ERROR"
        elif "0x8badf00d" in ips_content:
            severity = "SEV_2_HIGH"
            reason = "HALT_IOS_WATCHDOG_TIMEOUT"
        elif "0xdead10cc" in ips_content:
            severity = "SEV_2_HIGH"
            reason = "HALT_IOS_BACKGROUND_LOCK_VIOLATION"
        else:
            severity = "SEV_3_MEDIUM"
            reason = "HALT_IOS_UNKNOWN_CRASH_SIGNAL"

        metadata = {
            "exception_type": exception_type,
            "fault_address": fault_address,
            "format": fmt,
            "parsed_successfully": True,
            "process_name": process_name,
            "raw_length": raw_length,
        }
        return severity, reason, metadata

    @classmethod
    def _body_invariants_hold(cls, body: Dict[str, Any]) -> bool:
        latency = body.get("containment_latency_us")
        halt_code = body.get("halt_reason_code")
        incident_id = body.get("incident_id")
        caid = body.get("evidence_bundle_caid")

        return (
            body.get("severity_tier") in cls.VALID_SEVERITY_TIERS
            and body.get("action_taken") == cls.REQUIRED_ACTION_TAKEN
            and _is_strict_int(latency)
            and latency >= 0
            and isinstance(halt_code, str)
            and halt_code.startswith("HALT_")
            and isinstance(incident_id, str)
            and bool(incident_id.strip())
            and isinstance(caid, str)
            and bool(_SHA256_CAID_RE.match(caid))
            and isinstance(body.get("process_name"), str)
            and bool(body.get("process_name").strip())
            and isinstance(body.get("exception_type"), str)
            and bool(body.get("exception_type").strip())
            and isinstance(body.get("fault_address"), str)
            and bool(body.get("fault_address").strip())
            and isinstance(body.get("issuer_public_key_hex"), str)
            and len(body.get("issuer_public_key_hex")) == 64
        )

    @classmethod
    def emit_incident_notice(
        cls,
        incident_id: str,
        severity_tier: str,
        halt_reason_code: str,
        process_name: str,
        exception_type: str,
        fault_address: str,
        containment_latency_us: int,
        evidence_bundle_caid: str,
        signing_key: Ed25519PrivateKey,
    ) -> Dict[str, Any]:
        """
        Emits an Ed25519-signed incident notice using RFC 8785 canonical serialization.
        """
        body: Dict[str, Any] = {
            "action_taken": cls.REQUIRED_ACTION_TAKEN,
            "containment_latency_us": containment_latency_us,
            "evidence_bundle_caid": evidence_bundle_caid,
            "exception_type": exception_type,
            "fault_address": fault_address,
            "halt_reason_code": halt_reason_code,
            "incident_id": incident_id,
            "issuer_public_key_hex": signing_key.public_key().public_bytes_raw().hex(),
            "process_name": process_name,
            "severity_tier": severity_tier,
        }

        if not cls._body_invariants_hold(body):
            raise ValueError("ERR_INVALID_IOS_INCIDENT_NOTICE_FIELDS")

        canonical_bytes = encode_jcs(body)
        notification_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        signature_hex = signing_key.sign(canonical_bytes).hex()

        notice = dict(body)
        notice["notification_caid"] = notification_caid
        notice["signature_hex"] = signature_hex
        return notice

    @classmethod
    def verify_incident_notice(
        cls,
        notice: Dict[str, Any],
        trusted_issuer_public_key_hex: str,
    ) -> bool:
        """
        Verifies the exact key set, field invariants, pinned issuer public key,
        JCS notification CAID, and real Ed25519 cryptographic signature.
        """
        expected_keys = set(cls._SIGNED_FIELDS) | {"notification_caid", "signature_hex"}
        if set(notice.keys()) != expected_keys:
            return False

        body = {k: notice[k] for k in cls._SIGNED_FIELDS}
        if not cls._body_invariants_hold(body):
            return False

        if not hmac.compare_digest(
            str(body["issuer_public_key_hex"]), trusted_issuer_public_key_hex
        ):
            return False

        canonical_bytes = encode_jcs(body)
        expected_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        if not hmac.compare_digest(str(notice["notification_caid"]), expected_caid):
            return False

        try:
            pubkey = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(trusted_issuer_public_key_hex)
            )
            pubkey.verify(
                bytes.fromhex(str(notice["signature_hex"])),
                canonical_bytes,
            )
        except (InvalidSignature, ValueError):
            return False

        return True
