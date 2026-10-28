# Fixture (intentionally bad): CI003 verifiers that accept every input.


def verify_signature(sig):
    _ = sig
    return True


def validate_receipt(receipt):
    """Claims to validate a receipt."""
    _ = receipt
    return {"valid": True, "reason": "ok"}


class Checker:
    def is_valid_chain(self, chain):
        print("checking chain", len(chain))
        return True
