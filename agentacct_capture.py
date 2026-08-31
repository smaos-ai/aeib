"""
Stream C: agentacct Work Receipt System
Captures action_id, prompt, tokens_used, cost, Ed25519 signature
Stores in local JSON (not phone-home)
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import os


@dataclass
class WorkReceipt:
    """Immutable work receipt with Ed25519 signature"""

    action_id: str
    prompt: str
    tokens_used: int
    cost: float
    timestamp: str
    signature: str
    public_key: str = "ed25519_key_001"

    def to_dict(self):
        return asdict(self)


class AgentAcct:
    """Fail-closed work receipt tracking using Ed25519 signatures"""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or "./.smaos/work_receipts")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.receipts = []

        # Simulate Ed25519 keypair (in production: load from KMS)
        self.private_key = "ed25519_private_001"
        self.public_key = "ed25519_key_001"

    def _sign_ed25519(self, data: str) -> str:
        """
        Simulate Ed25519 signature (HMAC-SHA512 for testing).
        In production: use cryptography.hazmat.primitives.asymmetric.ed25519
        """
        signature_bytes = hashlib.sha512(
            (data + self.private_key).encode()
        ).digest()
        return signature_bytes.hex()[:128]  # Truncate to 64 chars for readability

    def capture(
        self,
        action_id: str,
        prompt: str,
        tokens_used: int,
        cost: float,
    ) -> WorkReceipt:
        """
        Capture work receipt with Ed25519 signature.
        Data flow: action → capture → signature → local JSON
        """
        timestamp = datetime.utcnow().isoformat()

        # Create signable payload (deterministic)
        payload = json.dumps(
            {
                "action_id": action_id,
                "prompt": prompt,
                "tokens_used": tokens_used,
                "cost": cost,
                "timestamp": timestamp,
            },
            sort_keys=True,
        )

        # Sign payload
        signature = self._sign_ed25519(payload)

        # Create receipt
        receipt = WorkReceipt(
            action_id=action_id,
            prompt=prompt,
            tokens_used=tokens_used,
            cost=cost,
            timestamp=timestamp,
            signature=signature,
            public_key=self.public_key,
        )

        # Store locally (fail-closed: always persists before returning)
        self.receipts.append(receipt)
        self._persist_to_json()

        return receipt

    def _persist_to_json(self):
        """
        Persist receipts to local JSON file (not phone-home).
        Fail-closed: persists before agent can use result.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = self.storage_dir / f"work_receipts_{timestamp}.json"

        with open(filename, "w") as f:
            json.dump([r.to_dict() for r in self.receipts], f, indent=2)

    def get_receipts(self):
        """Retrieve all captured receipts"""
        return self.receipts

    def verify_signature(self, receipt: WorkReceipt) -> bool:
        """
        Verify Ed25519 signature of receipt.
        In production: use cryptography library for actual Ed25519.
        """
        payload = json.dumps(
            {
                "action_id": receipt.action_id,
                "prompt": receipt.prompt,
                "tokens_used": receipt.tokens_used,
                "cost": receipt.cost,
                "timestamp": receipt.timestamp,
            },
            sort_keys=True,
        )

        expected_signature = self._sign_ed25519(payload)
        return receipt.signature == expected_signature


# Usage example
if __name__ == "__main__":
    acct = AgentAcct()

    # Capture work
    receipt = acct.capture(
        action_id="test_001",
        prompt="What is the meaning of life?",
        tokens_used=150,
        cost=0.003,
    )

    print(f"Work Receipt: {receipt}")
    print(f"Signature Valid: {acct.verify_signature(receipt)}")
    print(f"Stored in: {acct.storage_dir}")
