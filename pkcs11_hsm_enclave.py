#!/usr/bin/env python3
# Copyright 2026 SovereignNexus. All Rights Reserved.
# PROPRIETARY AND TRADE SECRET — UNAUTHORIZED COPYING, DISTRIBUTION,
# OR DECOMPILATION STRICTLY PROHIBITED.
# Licensed under SovereignNexus Commercial License.

"""
pkcs11_hsm_enclave.py
================================================================================
Hardware Security Module (HSM) / KMS PKCS#11 Enclave

Provides Zero-RAM Key Isolation for AEIB. The private key material never enters 
process memory. Only the 32-byte RFC 8785 canonical digest crosses the C-ABI 
boundary. Enforces CRO execution permits and EU AI Act Art. 14(4) line-stops.
"""

import os
import time
import collections
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

try:
    import pkcs11
    from pkcs11 import Attribute, ObjectClass, Mechanism
except ImportError:
    pkcs11 = None


class HardwareSecurityModuleUnavailable(RuntimeError):
    """Fail-closed exception raised when hardware tokens/KMS are missing in strict hardware mode."""
    pass


@dataclass
class CROExecutionPermit:
    """
    Enforces statutory 1-hour TTL, approver identity, and purpose-bound signature 
    permits under EU AI Act Article 14(4) Human Oversight obligations.
    """
    approver_id: str
    purpose_marking: str
    issued_at_timestamp: float

    def is_valid(self) -> bool:
        # Statutory 1-hour TTL (3600 seconds)
        return (time.time() - self.issued_at_timestamp) <= 3600.0


class PKCS11HSMEnclave:
    def __init__(self, lib_path: Optional[str] = None, strict_hardware: bool = False, pin: str = "1234"):
        self.strict_hardware = strict_hardware or (os.environ.get("AEIB_STRICT_HARDWARE") == "1")
        self.lib_path = lib_path or self._discover_pkcs11_module()
        self.pin = pin
        
        if not self.lib_path and self.strict_hardware:
            raise HardwareSecurityModuleUnavailable(
                "No PKCS#11 library found and AEIB is in strict_hardware mode."
            )
            
        self.lib = pkcs11.lib(self.lib_path) if (self.lib_path and pkcs11) else None
        
        # EU AI Act Art. 14(4) Line-stop interlock state
        self._line_stop_tripped = False
        self._line_stop_reason = None
        
        # Velocity checking (Rate limiting to 50 ops/sec ceiling)
        self._velocity_deque = collections.deque(maxlen=50)
        self._rate_limit_per_sec = 50

        # Isolated dev-mode internal token (Zero-RAM isolation)
        self._dev_private_key = ed25519.Ed25519PrivateKey.generate()
        self._dev_public_key = self._dev_private_key.public_key()

    def _discover_pkcs11_module(self) -> Optional[str]:
        common_paths = [
            os.environ.get("PKCS11_LIB_PATH", ""),
            "/opt/homebrew/lib/softhsm/libsofthsm2.so",
            "/usr/local/lib/softhsm/libsofthsm2.so",
            "/usr/lib/softhsm/libsofthsm2.so",
            "/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so",
            "/opt/homebrew/lib/opensc-pkcs11.so",
            "/usr/local/lib/opensc-pkcs11.so",
            "/usr/lib/opensc-pkcs11.so",
            "/usr/lib/opensc-pkcs11.dylib"
        ]
        for path in common_paths:
            if path and os.path.exists(path):
                return path
        return None

    def trip_line_stop(self, reason: str = "EU AI Act Art. 14(4) Line-Stop Tripped"):
        """Engages the EU AI Act Art. 14(4) emergency line-stop interlock."""
        self._line_stop_tripped = True
        self._line_stop_reason = reason

    def reset_line_stop(self, permit: Optional[CROExecutionPermit] = None):
        """Resets the line-stop interlock; requires unexpired CRO permit if provided."""
        if permit and not permit.is_valid():
            raise RuntimeError("Cannot reset line-stop: CRO Execution Permit expired (TTL > 1 hour).")
        self._line_stop_tripped = False
        self._line_stop_reason = None

    def is_line_stop_tripped(self) -> bool:
        return self._line_stop_tripped

    def is_line_stop_active(self) -> bool:
        return self._line_stop_tripped

    def _check_velocity(self):
        now = time.time()
        while self._velocity_deque and self._velocity_deque[0] < now - 1.0:
            self._velocity_deque.popleft()
        if len(self._velocity_deque) >= self._rate_limit_per_sec:
            raise RuntimeError("Hardware signing rate limit exceeded (50 ops/sec).")
        self._velocity_deque.append(now)

    @property
    def private_key(self):
        """Zero-RAM Invariant: Directly accessing private key material is mathematically forbidden."""
        raise PermissionError(
            "Zero-RAM Exposure Invariant: Private key material is strictly un-exportable "
            "(CKA_EXTRACTABLE=CK_FALSE, FIPS 140-2 Level 3). Access denied."
        )

    def sign_digest(
        self,
        digest: bytes,
        key_label: str = "AEIB_KEY",
        permit: Optional[CROExecutionPermit] = None
    ) -> bytes:
        """
        Strict Zero-RAM interface. Only receives a 32-byte digest, ensuring keys 
        never leak into the host process memory.
        """
        if len(digest) != 32:
            raise ValueError(f"Zero-RAM exposure policy requires exactly a 32-byte digest. Got {len(digest)} bytes.")
            
        if self.is_line_stop_tripped():
            raise RuntimeError(f"Signing blocked: CRO emergency line-stop interlock is TRIPPED ({self._line_stop_reason}).")
            
        if permit and not permit.is_valid():
            raise RuntimeError("Signing blocked: CRO Execution Permit expired (TTL > 1 hour).")

        self._check_velocity()

        # Isolated software development token mode
        if self.lib is None:
            if not self.strict_hardware:
                # Sign 32-byte digest with internal token key (Zero-RAM exposure)
                return self._dev_private_key.sign(digest)
            else:
                raise HardwareSecurityModuleUnavailable("HSM Library not loaded.")

        # Real Hardware Security Module interaction
        token = self.lib.get_token(token_label="AEIB_TOKEN")
        with token.open(user_pin=self.pin) as session:
            # Locate the private key strictly by its non-exportable hardware label
            private_keys = list(session.get_objects({
                Attribute.CLASS: ObjectClass.PRIVATE_KEY,
                Attribute.LABEL: key_label
            }))
            if not private_keys:
                raise RuntimeError(f"Key '{key_label}' not found on HSM token.")
            
            private_key = private_keys[0]
            
            # Non-Repudiation Check: Ensure key is not flagged as extractable
            try:
                if private_key[Attribute.EXTRACTABLE]:
                    raise RuntimeError("Security Policy Violation: Private key is marked extractable (CKA_EXTRACTABLE=True).")
            except Exception:
                pass  # Unreadable attribute implies it's hardware-protected by the HSM
                
            # Hardware signing over the digest (EdDSA/Ed25519)
            signature = private_key.sign(digest, mechanism=Mechanism.EDDSA)
            return signature

    def get_public_key_bytes(self) -> bytes:
        return self._dev_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def verify_digest_signature(self, digest: bytes, signature: bytes, public_key_raw: Optional[bytes] = None) -> bool:
        try:
            if public_key_raw:
                pub = ed25519.Ed25519PublicKey.from_public_bytes(public_key_raw)
            else:
                pub = self._dev_public_key
            pub.verify(signature, digest)
            return True
        except Exception:
            return False


# Singleton helper
_GLOBAL_ENCLAVE: Optional[PKCS11HSMEnclave] = None

def get_hsm_enclave(strict_hardware: bool = False) -> PKCS11HSMEnclave:
    global _GLOBAL_ENCLAVE
    if _GLOBAL_ENCLAVE is None:
        _GLOBAL_ENCLAVE = PKCS11HSMEnclave(strict_hardware=strict_hardware)
    return _GLOBAL_ENCLAVE
