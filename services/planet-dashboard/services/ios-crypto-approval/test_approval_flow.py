#!/usr/bin/env python3
"""
Mock implementation of cryptographic approval flow for testing without iPhone.
Simulates: approval prompt → FaceID → P256 signing → Vision API submission.
"""

import json
import hashlib
import base64
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Installing cryptography library...")
    import subprocess
    subprocess.check_call(["pip", "install", "cryptography"])
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend


# MARK: - Enums & Data Classes

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    VERIFIED = "verified"


@dataclass
class GovernanceRequest:
    """Payload sent to Vision API /v1/govern"""
    capsule_hash: str
    signature: str
    public_key: str
    timestamp: str
    algorithm: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


@dataclass
class GovernanceResponse:
    """Response from Vision API"""
    approval_id: str
    status: str
    verified: bool
    timestamp: str


# MARK: - Secure Enclave P256 Mock

class SecureEnclaveP256Mock:
    """Mock Secure Enclave P256 key operations for testing"""

    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        self.public_key = self.private_key.public_key()
        print("[✓] Secure Enclave P256 private key generated (mock)")

    def sign(self, message: bytes) -> bytes:
        """Sign message with P256 private key"""
        signature = self.private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        print(f"[✓] ECDSA P256 signature generated: {base64.b64encode(signature).decode()[:64]}...")
        return signature

    def get_public_key_pem(self) -> str:
        """Export public key as PEM"""
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode()

    def verify_signature(self, message: bytes, signature: bytes) -> bool:
        """Verify signature (for testing)"""
        try:
            self.public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False


# MARK: - Approval Flow Steps

class CryptographicApprovalFlow:
    """Mock implementation of cryptographic approval flow"""

    def __init__(self):
        self.secure_enclave = SecureEnclaveP256Mock()
        self.user_approved = False
        self.biometric_auth_success = False

    @staticmethod
    def hash_capsule(capsule_content: str) -> Tuple[bytes, str]:
        """Hash capsule content with SHA256"""
        data = capsule_content.encode("utf-8")
        hash_obj = hashlib.sha256(data)
        hash_bytes = hash_obj.digest()
        hash_b64 = base64.b64encode(hash_bytes).decode()
        print(f"[✓] Capsule hash (SHA256): {hash_b64}")
        return hash_bytes, hash_b64

    def prompt_for_approval(self, message: str = "Approve this decision?") -> bool:
        """Simulate user approval prompt"""
        print(f"\n[USER PROMPT] {message}")
        response = input("User response (yes/no): ").strip().lower()
        self.user_approved = response in ("yes", "y", "approve")
        print(f"[{'✓' if self.user_approved else '✗'}] User approval: {self.user_approved}")
        return self.user_approved

    def authenticate_with_biometrics(self) -> bool:
        """Simulate FaceID authentication"""
        print("\n[BIOMETRIC AUTH] Simulating FaceID...")
        # In test mode, auto-approve; in production, require actual auth
        self.biometric_auth_success = True
        print("[✓] FaceID authentication successful (mock)")
        return self.biometric_auth_success

    def sign_capsule_hash(self, capsule_hash: bytes) -> bytes:
        """Sign capsule hash with P256 private key"""
        print("\n[SIGNING] Signing capsule hash with Secure Enclave P256...")
        signature = self.secure_enclave.sign(capsule_hash)
        return signature

    async def submit_to_vision_api(
        self,
        capsule_hash: str,
        signature: str,
        public_key_pem: str,
        endpoint: str = "https://api.vision.example.com/v1/govern",
    ) -> GovernanceResponse:
        """
        Mock submission to Vision API /v1/govern endpoint.
        In real flow, this would be an actual HTTP POST.
        """
        print(f"\n[API SUBMISSION] POST {endpoint}")

        request = GovernanceRequest(
            capsule_hash=capsule_hash,
            signature=signature,
            public_key=public_key_pem,
            timestamp=datetime.now(timezone.utc).isoformat(),
            algorithm="ECDSA-P256",
        )

        print(f"[REQUEST PAYLOAD]\n{request.to_json()}")

        # Simulate Vision API response
        approval_id = f"approval_{hashlib.sha256(capsule_hash.encode()).hexdigest()[:16]}"
        response = GovernanceResponse(
            approval_id=approval_id,
            status="verified",
            verified=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        print(f"\n[✓] Vision API response (HTTP 200):")
        print(json.dumps(asdict(response), indent=2))

        return response

    async def execute_full_flow(self, capsule_content: str) -> Optional[GovernanceResponse]:
        """
        Execute complete approval flow:
        1. Generate/retrieve Secure Enclave key
        2. Prompt user for approval
        3. Authenticate with FaceID
        4. Hash capsule content
        5. Sign with P256
        6. Submit to Vision API
        """
        print("=" * 70)
        print("CRYPTOGRAPHIC APPROVAL FLOW - FULL EXECUTION")
        print("=" * 70)

        # Step 1: Key generation (already done in __init__)
        print("\n[STEP 1] Secure Enclave Key Generation")
        print("[✓] P256 private key loaded from Secure Enclave")

        # Step 2: User approval prompt
        print("\n[STEP 2] User Approval Prompt")
        if not self.prompt_for_approval():
            print("[✗] User denied approval. Aborting flow.")
            return None

        # Step 3: Biometric authentication
        print("\n[STEP 3] FaceID Authentication")
        if not self.authenticate_with_biometrics():
            print("[✗] Biometric authentication failed. Aborting flow.")
            return None

        # Step 4: Hash capsule
        print("\n[STEP 4] Capsule Hashing")
        capsule_hash_bytes, capsule_hash_b64 = self.hash_capsule(capsule_content)

        # Step 5: Sign capsule hash
        print("\n[STEP 5] P256 Signing")
        signature_bytes = self.sign_capsule_hash(capsule_hash_bytes)
        signature_b64 = base64.b64encode(signature_bytes).decode()

        # Verify signature (sanity check)
        is_valid = self.secure_enclave.verify_signature(capsule_hash_bytes, signature_bytes)
        print(f"[{'✓' if is_valid else '✗'}] Signature verification: {is_valid}")

        # Step 6: Submit to Vision API
        print("\n[STEP 6] Vision API Submission")
        public_key_pem = self.secure_enclave.get_public_key_pem()
        response = await self.submit_to_vision_api(
            capsule_hash=capsule_hash_b64,
            signature=signature_b64,
            public_key_pem=public_key_pem,
        )

        print("\n" + "=" * 70)
        print("FLOW COMPLETE - APPROVAL VERIFIED")
        print("=" * 70)

        return response


# MARK: - Test Scenarios

async def test_successful_approval():
    """Test: User approves, biometric succeeds, sign & submit"""
    print("\n\nTEST 1: Successful Approval Flow")
    print("-" * 70)

    flow = CryptographicApprovalFlow()
    result = await flow.execute_full_flow("governance_decision_capsule_v1")

    assert result is not None, "Expected successful approval"
    assert result.verified, "Expected verified response"
    print("[PASSED] ✓ Successful approval flow\n")


async def test_user_denial():
    """Test: User denies approval"""
    print("\n\nTEST 2: User Denial")
    print("-" * 70)

    flow = CryptographicApprovalFlow()

    # Override to simulate denial
    original_prompt = flow.prompt_for_approval

    def mock_denial(*args, **kwargs):
        print("[USER PROMPT] Approve this decision?")
        print("User response (yes/no): no")
        flow.user_approved = False
        print("[✗] User approval: False")
        return False

    flow.prompt_for_approval = mock_denial

    result = await flow.execute_full_flow("governance_decision_capsule_v1")

    assert result is None, "Expected None on user denial"
    print("[PASSED] ✓ User denial handled correctly\n")


async def test_signature_verification():
    """Test: Verify signature integrity"""
    print("\n\nTEST 3: Signature Verification")
    print("-" * 70)

    se = SecureEnclaveP256Mock()
    test_data = b"test_capsule_hash"

    # Sign
    signature = se.sign(test_data)
    print(f"[✓] Signature created: {base64.b64encode(signature).decode()[:64]}...")

    # Verify correct data
    is_valid = se.verify_signature(test_data, signature)
    assert is_valid, "Expected valid signature"
    print("[✓] Signature verification: PASSED")

    # Verify corrupted data
    corrupted_data = b"corrupted_capsule_hash"
    is_valid_corrupted = se.verify_signature(corrupted_data, signature)
    assert not is_valid_corrupted, "Expected invalid signature for corrupted data"
    print("[✓] Corrupted data rejection: PASSED\n")


# MARK: - Main Test Runner

async def main():
    """Run all test scenarios"""
    print("\n" + "=" * 70)
    print("CRYPTOGRAPHIC APPROVAL FLOW - TEST SUITE")
    print("=" * 70)

    try:
        await test_successful_approval()
        await test_user_denial()
        await test_signature_verification()

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70 + "\n")

    except AssertionError as e:
        print(f"\n[FAILED] ✗ {e}\n")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] ✗ {e}\n")
        exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
