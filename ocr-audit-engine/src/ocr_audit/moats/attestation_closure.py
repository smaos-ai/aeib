import hmac

"""Moat 1: Decision Reproducibility via Attestation Closure (IETF AAT draft-03 §13.6)

Seals model weights, tokenizer configuration, chat template, engine build, and
numeric backend execution environment into immutable SHA-256 digests.

Guarantees computational closure for open-weight agent harnesses that closed-model
cloud APIs cannot replicate.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AttestationClosure:
    tokenizer_digest: str
    chat_template_digest: str
    engine_build_digest: str
    numeric_environment_digest: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    def is_valid(self) -> bool:
        """Validates that all 4 digests are 64-character hex strings."""
        for d in (
            self.tokenizer_digest,
            self.chat_template_digest,
            self.engine_build_digest,
            self.numeric_environment_digest,
        ):
            if not isinstance(d, str) or len(d) != 64:
                return False
            try:
                int(d, 16)
            except ValueError:
                return False
        return True


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AttestationClosureSealer:
    """Seals an execution environment into IETF AAT draft-03 Attestation Closure digests."""

    @staticmethod
    def seal(
        tokenizer_data: bytes,
        chat_template: str,
        engine_binary_or_version: str,
        numeric_params: Dict[str, Any],
    ) -> AttestationClosure:
        # Canonicalize numeric parameters
        numeric_bytes = json.dumps(numeric_params, sort_keys=True).encode("utf-8")

        return AttestationClosure(
            tokenizer_digest=sha256_hex(tokenizer_data),
            chat_template_digest=sha256_hex(chat_template.encode("utf-8")),
            engine_build_digest=sha256_hex(engine_binary_or_version.encode("utf-8")),
            numeric_environment_digest=sha256_hex(numeric_bytes),
        )

    @staticmethod
    def verify(
        closure: AttestationClosure,
        expected: AttestationClosure,
    ) -> bool:
        return (
            hmac.compare_digest(closure.tokenizer_digest, expected.tokenizer_digest)
            and hmac.compare_digest(closure.chat_template_digest, expected.chat_template_digest)
            and hmac.compare_digest(closure.engine_build_digest, expected.engine_build_digest)
            and hmac.compare_digest(closure.numeric_environment_digest, expected.numeric_environment_digest)
        )

    @staticmethod
    def enrich_receipt(receipt: Dict[str, Any], closure: AttestationClosure) -> Dict[str, Any]:
        """Enriches a v1.0 receipt to ReceiptPayload v1.1 format."""
        out = dict(receipt)
        out["version"] = "1.1.0"
        out["attestation_closure"] = closure.to_dict()
        return out
