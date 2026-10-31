#!/usr/bin/env python3
"""Mac M3 Pro -> iPhone 16 Pro Max Secure Enclave RPC Client.

Communicates with the iPhone's `NotaryRPCServer` over USB-C personal hotspot,
local network, or TCP link.

Key capabilities:
1. `fetch_enclave_pubkey_hex()`: Fetches the iPhone's A18 Pro Secure Enclave
   NIST P-256 public key in uncompressed ANSI X9.63 format via `GET /pubkey`.
2. `request_faceid_warrant()`: Sends the canonical RFC 8785 JCS proposal bytes
   via `POST /approve`, awaiting FaceID authentication or explicit human veto.
3. Cryptographic and WYSIWYS verification of the received `EnclaveSignedWarrant`
   before releasing the Mac's T3 execution latch.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    T3LatchReleaseVerdict,
    sha256_jcs_caid,
)


DEFAULT_NOTARY_PORT = 8080


class IPhoneNotaryRPCClient:
    """Client for out-of-band biometric authorization on iPhone 16 Pro Max."""

    def __init__(
        self,
        iphone_host: str,
        port: int = DEFAULT_NOTARY_PORT,
        pinned_enclave_pubkey_x963_hex: str = "",
    ) -> None:
        if not isinstance(iphone_host, str) or not iphone_host.strip():
            raise ValueError("ERR_EMPTY_IPHONE_HOST")
        if type(port) is not int or port <= 0 or port > 65535:
            raise ValueError("ERR_INVALID_PORT")

        self.iphone_host = iphone_host.strip()
        self.port = port
        self.base_url = f"http://{self.iphone_host}:{self.port}"
        self.pinned_pubkey_hex = pinned_enclave_pubkey_x963_hex.strip()

    def fetch_enclave_pubkey_hex(self, timeout_sec: int = 5) -> str:
        """Fetch the pinned hardware P-256 public key from the iPhone."""
        url = f"{self.base_url}/pubkey"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.read().decode("utf-8").strip()

    def request_faceid_warrant(
        self,
        proposal: T3ActionProposal,
        timeout_sec: int = 60,
        current_epoch_sec: Optional[int] = None,
        sig_verifier_fn: Optional[Callable[[str, bytes, str], bool]] = None,
    ) -> T3LatchReleaseVerdict:
        """Sends canonical RFC 8785 JCS bytes to the iPhone and awaits FaceID authorization."""
        canonical_bytes = proposal.to_canonical_jcs_bytes()
        expected_caid = sha256_jcs_caid(canonical_bytes)
        now_sec = current_epoch_sec if current_epoch_sec is not None else int(time.time())

        def _halt(reason: str) -> T3LatchReleaseVerdict:
            receipt = sha256_jcs_caid(
                {
                    "expected_caid": expected_caid,
                    "latch_released": False,
                    "reason_code": reason,
                }
            )
            return T3LatchReleaseVerdict(False, reason, expected_caid, receipt)

        url = f"{self.base_url}/approve"
        req = urllib.request.Request(
            url,
            data=canonical_bytes,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(canonical_bytes)),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw_body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="replace")
            if http_err.code == 403 and "HALT_HUMAN_VETOED_ON_IPHONE" in err_body:
                return _halt("HALT_HUMAN_VETOED_ON_IPHONE")
            return _halt(f"HALT_IPHONE_HTTP_ERROR:{http_err.code}")
        except (TimeoutError, socket.timeout):
            return _halt("HALT_IPHONE_FACEID_TIMEOUT")
        except urllib.error.URLError as url_err:
            if isinstance(url_err.reason, (TimeoutError, socket.timeout)) or "timed out" in str(url_err.reason):
                return _halt("HALT_IPHONE_FACEID_TIMEOUT")
            return _halt(f"HALT_IPHONE_TRANSPORT_UNREACHABLE:{url_err.reason}")

        try:
            warrant_dict = json.loads(raw_body)
            warrant = EnclaveSignedWarrant(
                canonical_payload_utf8=warrant_dict["canonical_payload_utf8"],
                payload_sha256_caid=warrant_dict["payload_sha256_caid"],
                public_key_x963_hex=warrant_dict["public_key_x963_hex"],
                signature_der_hex=warrant_dict["signature_der_hex"],
                algorithm=warrant_dict["algorithm"],
            )
        except (KeyError, ValueError, TypeError):
            return _halt("HALT_MALFORMED_WARRANT_JSON")

        return MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
            expected_proposal=proposal,
            warrant=warrant,
            pinned_enclave_pubkey_x963_hex=self.pinned_pubkey_hex,
            current_epoch_sec=now_sec,
            sig_verifier_fn=sig_verifier_fn,
        )
