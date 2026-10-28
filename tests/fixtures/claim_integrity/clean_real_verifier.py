# Fixture (clean): verifiers with real conditions or raising primitives.
from cryptography.exceptions import InvalidSignature


def verify_signature(public_key, signature, message):
    try:
        public_key.verify(signature, message)
    except InvalidSignature:
        return False
    return True


def verify_with_raise(public_key, signature, message):
    public_key.verify(signature, message)
    return True


def check_threshold(value, limit):
    if value > limit:
        return {"ok": False, "reason": "over limit"}
    return {"ok": True, "reason": "within limit"}


def validate_receipt(receipt):
    return {"valid": receipt.get("sig") is not None}
