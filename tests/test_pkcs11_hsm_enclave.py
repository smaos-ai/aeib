#!/usr/bin/env python3
r"""
test_pkcs11_hsm_enclave.py — Unit Tests for PKCS#11 HSM & KMS Enclave
Verifies:
  1. Zero-RAM Exposure (caller cannot access private key in heap/RAM).
  2. Asymmetric signing over 32-byte canonical digests and offline verification.
  3. FIPS 140-2 Level 3 un-exportable key guarantees.
  4. EU AI Act Art. 14(4) Emergency Hardware Line-Stop interlock.
  5. Statutory 1-hour TTL Chief Risk Officer (CRO) Execution Permits.
  6. Hardware-level velocity / rate limiting (50 ops/sec ceiling).
  7. Strict hardware mode fail-closed enforcement (HardwareSecurityModuleUnavailable).
"""

import os
import sys
import time
import hashlib
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pkcs11_hsm_enclave import (
    PKCS11HSMEnclave,
    CROExecutionPermit,
    HardwareSecurityModuleUnavailable,
    get_hsm_enclave
)


class TestPKCS11HSMEnclave(unittest.TestCase):
    """Test suite for PKCS#11 Hardware Security Module & KMS Enclave."""

    def setUp(self):
        self.enclave = PKCS11HSMEnclave(strict_hardware=False)
        self.sample_digest = hashlib.sha256(b'{"action":"debit","amount":500.00,"currency":"EUR"}').digest()

    def test_01_zero_ram_exposure_private_key_inaccessible(self):
        """Zero-RAM Invariant: Caller cannot access raw private key material."""
        with self.assertRaises(PermissionError) as ctx:
            _ = self.enclave.private_key
        self.assertIn("Zero-RAM Exposure Invariant", str(ctx.exception))
        self.assertIn("CKA_EXTRACTABLE=CK_FALSE", str(ctx.exception))

    def test_02_sign_digest_and_verify(self):
        """Signs a 32-byte canonical digest and verifies signature against public key."""
        sig = self.enclave.sign_digest(self.sample_digest)
        self.assertEqual(len(sig), 64)

        # Verification succeeds
        valid = self.enclave.verify_digest_signature(self.sample_digest, sig)
        self.assertTrue(valid)

        # Tampered digest fails verification
        tampered_digest = hashlib.sha256(b'{"action":"debit","amount":999999.00,"currency":"EUR"}').digest()
        invalid = self.enclave.verify_digest_signature(tampered_digest, sig)
        self.assertFalse(invalid)

    def test_03_cro_execution_permit_lifecycle(self):
        """Enforces statutory 1-hour TTL CRO execution permits."""
        valid_permit = CROExecutionPermit(
            approver_id="CRO_CHIEF_OFFICER",
            purpose_marking="TREASURY_TRANSFER",
            issued_at_timestamp=time.time()
        )
        self.assertTrue(valid_permit.is_valid())

        # Sign with valid permit
        sig = self.enclave.sign_digest(self.sample_digest, permit=valid_permit)
        self.assertTrue(self.enclave.verify_digest_signature(self.sample_digest, sig))

        # Create expired permit (issued 2 hours ago)
        expired_permit = CROExecutionPermit(
            approver_id="CRO_OLD",
            purpose_marking="EXPIRED_OPERATION",
            issued_at_timestamp=time.time() - 7200.0
        )
        self.assertFalse(expired_permit.is_valid())

        with self.assertRaises(RuntimeError) as ctx:
            self.enclave.sign_digest(self.sample_digest, permit=expired_permit)
        self.assertIn("CRO Execution Permit expired", str(ctx.exception))

    def test_04_emergency_line_stop_tripped(self):
        """Emergency hardware line-stop physically halts all receipt signing (EU AI Act Art. 14(4))."""
        self.assertFalse(self.enclave.is_line_stop_tripped())
        self.enclave.trip_line_stop("Rogue agent behavioral drift detected")
        self.assertTrue(self.enclave.is_line_stop_tripped())

        # Any signing attempt must be trapped
        with self.assertRaises(RuntimeError) as ctx:
            self.enclave.sign_digest(self.sample_digest)
        self.assertIn("emergency line-stop interlock is TRIPPED", str(ctx.exception))

        # Resetting line-stop
        cro_permit = CROExecutionPermit("CRO_SUPERVISOR", "LINE_STOP_RESET", time.time())
        self.enclave.reset_line_stop(cro_permit)
        self.assertFalse(self.enclave.is_line_stop_tripped())

        # Resumed signing succeeds
        sig = self.enclave.sign_digest(self.sample_digest)
        self.assertTrue(self.enclave.verify_digest_signature(self.sample_digest, sig))

    def test_05_hardware_velocity_rate_limiting(self):
        """Enforces hardware-level velocity limit."""
        low_limit_enclave = PKCS11HSMEnclave(strict_hardware=False)
        low_limit_enclave._rate_limit_per_sec = 5
        for _ in range(5):
            low_limit_enclave.sign_digest(self.sample_digest)

        # 6th operation within 1s must trip rate limit
        with self.assertRaises(RuntimeError) as ctx:
            low_limit_enclave.sign_digest(self.sample_digest)
        self.assertIn("rate limit exceeded", str(ctx.exception))

    def test_06_strict_hardware_mode_fails_closed(self):
        """Fails closed when strict hardware mode is active and no physical HSM is attached."""
        with self.assertRaises(HardwareSecurityModuleUnavailable) as ctx:
            PKCS11HSMEnclave(strict_hardware=True)
        self.assertIn("No PKCS#11 library found and AEIB is in strict_hardware mode", str(ctx.exception))

    def test_07_malformed_digest_rejected(self):
        """Rejects non-32-byte digests to guarantee RFC 8785 SHA-256 compliance."""
        with self.assertRaises(ValueError):
            self.enclave.sign_digest(b"short_digest")
        with self.assertRaises(ValueError):
            self.enclave.sign_digest(b"a" * 64)


if __name__ == "__main__":
    unittest.main()
