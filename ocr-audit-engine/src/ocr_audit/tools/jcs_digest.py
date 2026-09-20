"""Tool 2: CompareJCSDigest — Computes RFC 8785 JSON Canonicalization Scheme hashes."""

import hashlib
import hmac
import json
from typing import Any, Dict, Optional


def jcs_canonicalize(data: Any) -> bytes:
    """Canonicalizes JSON according to RFC 8785 (JCS)."""
    if isinstance(data, dict):
        sorted_keys = sorted(data.keys())
        items = []
        for k in sorted_keys:
            key_bytes = json.dumps(k, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            val_bytes = jcs_canonicalize(data[k])
            items.append(key_bytes + b":" + val_bytes)
        return b"{" + b",".join(items) + b"}"
    elif isinstance(data, list):
        return b"[" + b",".join(jcs_canonicalize(x) for x in data) + b"]"
    elif isinstance(data, str):
        return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    elif isinstance(data, (int, float, bool)) or data is None:
        return json.dumps(data, separators=(",", ":")).encode("utf-8")
    else:
        return json.dumps(str(data), separators=(",", ":")).encode("utf-8")


def jcs_digest(data: Any) -> str:
    """Returns the hex SHA-256 digest of RFC 8785 canonical bytes."""
    return hashlib.sha256(jcs_canonicalize(data)).hexdigest()


def compare_jcs_digest(record: Dict[str, Any], expected_digest: Optional[str] = None) -> Dict[str, Any]:
    """Computes RFC 8785 hash deltas between dispatched payload and claimed digest."""
    payload_to_hash = {k: v for k, v in record.items() if not k.startswith("_")}
    computed = jcs_digest(payload_to_hash)
    claimed = expected_digest or record.get("expected_digest") or record.get("intent_digest")
    
    if not claimed:
        match = True
    else:
        try:
            match = hmac.compare_digest(computed.encode('utf-8').lower(), str(claimed).encode('utf-8').lower())
        except (TypeError, ValueError):
            match = False

    return {
        "computed_digest": computed,
        "claimed_digest": claimed,
        "match": match,
        "tampered": not match if claimed else False,
    }
