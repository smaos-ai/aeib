#!/usr/bin/env python3
"""
dpop_token_exchange_gate.py — RFC 8693 Token Exchange & RFC 9449 DPoP Sidecar Gate
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)

Implements a prototype Zero-Credential Sidecar Identity & Sender-Constrained Token
architecture under the stated model:
1. RFC 7638 / RFC 8785 JWK Thumbprint (`compute_ed25519_jwk_thumbprint`) over Ed25519 OKP keys.
2. RFC 8693 OAuth 2.0 Token Exchange (`RFC8693TokenExchangeServer`) producing down-scoped,
   single-operation tokens with nested `act` delegation lineage, RFC 8707 `aud` target binding,
   RFC 8785 JCS `caid` payload digest binding, monotonic budget attenuation, and `cnf.jkt`
   sender constraint bound to the AEIB Station 2 sidecar public key.
3. RFC 9449 DPoP Proof Generator & Verifier (`RFC9449DPoPProver`, `RFC9449DPoPVerifier`)
   verifying AS and sidecar Ed25519 signatures, `cnf.jkt` thumbprint binding, `ath` access token
   hash binding, HTTP method (`htm`) and target URI (`htu`), `caid` wire payload integrity,
   single-use `jti` replay prevention, and `policy_epoch` freshness.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
import uuid
from typing import Any, Dict, Iterable, Optional, Set, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


class DPoPTokenExchangeError(ValueError):
    """Base exception for RFC 8693 token exchange and RFC 9449 DPoP verification errors."""


class DPoPBindingError(DPoPTokenExchangeError):
    """Raised when RFC 9449 DPoP sender constraint or dispatch binding verification fails."""


class TokenExchangePrivilegeError(DPoPBindingError):
    """Raised when a subagent requests budget or scope exceeding the sponsor ceiling."""


class TargetBindingMismatchError(DPoPBindingError):
    """Raised when HTTP method (htm) or RFC 8707 target resource URI (htu/aud) mismatches."""


class PayloadCaidMismatchError(DPoPBindingError):
    """Raised when the wire payload RFC 8785 JCS SHA-256 digest does not match caid."""


class DPoPReplayError(DPoPBindingError):
    """Raised when a DPoP proof or execution token jti nonce is replayed."""


class PolicyEpochError(DPoPBindingError):
    """Raised when an execution token carries a stale or mismatched policy_epoch."""


class AccessTokenHashError(DPoPBindingError):
    """Raised when the DPoP proof ath claim does not match the access token SHA-256 hash."""


def _b64url_encode(raw: bytes) -> str:
    """Encodes raw bytes into unpadded base64url ASCII string per RFC 7515."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    """Decodes an unpadded base64url string into raw bytes."""
    if not isinstance(encoded, str) or not encoded:
        raise DPoPBindingError("Expected non-empty base64url string")
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
    except Exception as exc:
        raise DPoPBindingError(f"Malformed base64url encoding: {exc}") from exc


def ed25519_public_key_to_jwk(pubkey: ed25519.Ed25519PublicKey) -> Dict[str, str]:
    """Converts an Ed25519PublicKey into its minimal RFC 8037 OKP JWK dictionary."""
    if not isinstance(pubkey, ed25519.Ed25519PublicKey):
        raise TypeError("Expected ed25519.Ed25519PublicKey instance")
    raw_pub = pubkey.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "crv": "Ed25519",
        "kty": "OKP",
        "x": _b64url_encode(raw_pub),
    }


def ed25519_public_key_from_jwk(jwk: Dict[str, Any]) -> ed25519.Ed25519PublicKey:
    """Reconstructs an Ed25519PublicKey from an RFC 8037 OKP JWK dictionary."""
    if not isinstance(jwk, dict):
        raise DPoPBindingError("JWK must be a dictionary")
    if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
        raise DPoPBindingError("JWK must specify kty='OKP' and crv='Ed25519'")
    x_val = jwk.get("x")
    if not isinstance(x_val, str) or not x_val:
        raise DPoPBindingError("JWK missing base64url public key coordinate 'x'")
    raw_pub = _b64url_decode(x_val)
    if len(raw_pub) != 32:
        raise DPoPBindingError(f"Ed25519 public key must be 32 bytes, observed {len(raw_pub)}")
    try:
        return ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
    except Exception as exc:
        raise DPoPBindingError(f"Invalid Ed25519 public key bytes in JWK: {exc}") from exc


def compute_ed25519_jwk_thumbprint(
    key_or_jwk: Union[ed25519.Ed25519PublicKey, Dict[str, Any], bytes]
) -> str:
    """
    Computes the canonical RFC 7638 / RFC 8785 JCS SHA-256 base64url thumbprint (`jkt`)
    of an Ed25519 public key:
        {"crv":"Ed25519","kty":"OKP","x":"<base64url_raw_pub>"}
    """
    if isinstance(key_or_jwk, ed25519.Ed25519PublicKey):
        canonical_jwk = ed25519_public_key_to_jwk(key_or_jwk)
    elif isinstance(key_or_jwk, bytes):
        if len(key_or_jwk) != 32:
            raise DPoPBindingError("Raw Ed25519 public key must be exactly 32 bytes")
        pub = ed25519.Ed25519PublicKey.from_public_bytes(key_or_jwk)
        canonical_jwk = ed25519_public_key_to_jwk(pub)
    elif isinstance(key_or_jwk, dict):
        pub = ed25519_public_key_from_jwk(key_or_jwk)
        canonical_jwk = ed25519_public_key_to_jwk(pub)
    else:
        raise TypeError("Expected Ed25519PublicKey, JWK dict, or 32-byte raw public key")

    jcs_bytes = encode_jcs(canonical_jwk)
    digest = hashlib.sha256(jcs_bytes).digest()
    return _b64url_encode(digest)


def compute_payload_caid(wire_payload: Dict[str, Any]) -> str:
    """Computes the RFC 8785 JCS SHA-256 hex digest (`caid`) of a wire mutation payload."""
    if not isinstance(wire_payload, dict):
        raise DPoPBindingError("Wire mutation payload must be a JSON object dictionary")
    return hashlib.sha256(encode_jcs(wire_payload)).hexdigest()


def _normalize_and_validate_htu(uri: str) -> str:
    """
    Validates that a target URI conforms to RFC 8707 / RFC 9449 Section 4.2:
    scheme and host must be present, and query/fragment components are forbidden.
    """
    if not isinstance(uri, str) or not uri:
        raise TargetBindingMismatchError("Target URI must be a non-empty string")
    parsed = urllib.parse.urlsplit(uri)
    if not parsed.scheme or not parsed.netloc:
        raise TargetBindingMismatchError(f"Target URI must include scheme and authority: {uri!r}")
    if parsed.query or parsed.fragment:
        raise TargetBindingMismatchError(
            f"RFC 9449 htu / RFC 8707 aud URI must not contain query or fragment: {uri!r}"
        )
    return uri


class RFC8693TokenExchangeServer:
    """
    RFC 8693 OAuth 2.0 Token Exchange Engine for the AEIB Zero-Credential Sidecar Gate.

    Exchanges a `root_sponsor` grant (`subject_token`) and a subagent `actor_token`
    into a down-scoped, single-operation, sender-constrained execution token bound
    via `cnf.jkt` to the AEIB Station 2 sidecar's Ed25519 public key.
    """

    def __init__(
        self,
        as_privkey: ed25519.Ed25519PrivateKey,
        issuer: str = "https://as.sovereignnexus.internal/v1/token",
        active_policy_epoch: int = 1,
    ) -> None:
        if not isinstance(as_privkey, ed25519.Ed25519PrivateKey):
            raise TypeError("as_privkey must be an ed25519.Ed25519PrivateKey")
        self._as_privkey = as_privkey
        self.as_pubkey = as_privkey.public_key()
        self.issuer = issuer
        self.active_policy_epoch = active_policy_epoch

    def create_root_sponsor_grant(
        self,
        root_sponsor_did: str,
        budget_ceiling_minor_units: int,
        allowed_audiences: Optional[Iterable[str]] = None,
        policy_epoch: Optional[int] = None,
        ttl_seconds: int = 300,
        iat: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Creates an AS-signed root sponsor subject_token grant."""
        if not root_sponsor_did or not isinstance(root_sponsor_did, str):
            raise DPoPBindingError("root_sponsor_did must be a non-empty string")
        if not isinstance(budget_ceiling_minor_units, int) or budget_ceiling_minor_units <= 0:
            raise TokenExchangePrivilegeError("Sponsor budget ceiling must be a positive integer")

        now = int(time.time()) if iat is None else int(iat)
        epoch = self.active_policy_epoch if policy_epoch is None else int(policy_epoch)
        claims: Dict[str, Any] = {
            "iss": self.issuer,
            "sub": root_sponsor_did,
            "token_use": "subject_token",
            "budget_ceiling_minor_units": budget_ceiling_minor_units,
            "policy_epoch": epoch,
            "iat": now,
            "exp": now + int(ttl_seconds),
            "jti": f"sponsor-{uuid.uuid4().hex}",
        }
        if allowed_audiences is not None:
            claims["allowed_audiences"] = [_normalize_and_validate_htu(u) for u in allowed_audiences]

        sig = self._as_privkey.sign(encode_jcs(claims))
        signed_grant = dict(claims)
        signed_grant["signature"] = _b64url_encode(sig)
        return signed_grant

    def create_actor_token(
        self,
        subagent_did: str,
        parent_agent_did: str,
        parent_budget_ceiling_minor_units: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Creates an actor_token representing the invoking subagent and its parent lineage."""
        if not subagent_did or not isinstance(subagent_did, str):
            raise DPoPBindingError("subagent_did must be a non-empty string")
        if not parent_agent_did or not isinstance(parent_agent_did, str):
            raise DPoPBindingError("parent_agent_did must be a non-empty string")
        actor: Dict[str, Any] = {
            "sub": subagent_did,
            "parent_sub": parent_agent_did,
            "token_use": "actor_token",
        }
        if parent_budget_ceiling_minor_units is not None:
            actor["parent_budget_ceiling_minor_units"] = int(parent_budget_ceiling_minor_units)
        return actor

    def _verify_subject_token(self, subject_token: Dict[str, Any]) -> None:
        """Verifies the signature (if signed by AS) and structural validity of subject_token."""
        if not isinstance(subject_token, dict):
            raise DPoPBindingError("subject_token must be a dictionary")
        if "signature" in subject_token:
            token_copy = dict(subject_token)
            sig_b64 = token_copy.pop("signature")
            sig_bytes = _b64url_decode(sig_b64)
            try:
                self.as_pubkey.verify(sig_bytes, encode_jcs(token_copy))
            except InvalidSignature as exc:
                raise DPoPBindingError("Invalid AS signature on subject_token") from exc

    def exchange_token(
        self,
        subject_token: Dict[str, Any],
        actor_token: Dict[str, Any],
        aud: str,
        wire_payload: Dict[str, Any],
        requested_budget_minor_units: int,
        sidecar_pubkey_or_jkt: Union[ed25519.Ed25519PublicKey, Dict[str, Any], str],
        *,
        jti: Optional[str] = None,
        iat: Optional[int] = None,
        ttl_seconds: int = 60,
        policy_epoch: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Exchanges a `root_sponsor` subject_token and a subagent actor_token into a
        down-scoped, single-operation, sender-constrained execution token signed by the AS.
        """
        self._verify_subject_token(subject_token)

        root_sponsor_did = subject_token.get("sub")
        if not isinstance(root_sponsor_did, str) or not root_sponsor_did:
            raise DPoPBindingError("subject_token missing root_sponsor 'sub'")

        sponsor_ceiling = subject_token.get("budget_ceiling_minor_units")
        if not isinstance(sponsor_ceiling, int) or sponsor_ceiling <= 0:
            raise TokenExchangePrivilegeError("subject_token missing valid budget_ceiling_minor_units")

        if (
            not isinstance(requested_budget_minor_units, int)
            or isinstance(requested_budget_minor_units, bool)
            or requested_budget_minor_units <= 0
        ):
            raise TokenExchangePrivilegeError("requested_budget_minor_units must be a positive integer")

        if requested_budget_minor_units > sponsor_ceiling:
            raise TokenExchangePrivilegeError(
                f"Subagent privilege escalation blocked: requested_budget ({requested_budget_minor_units}) "
                f"exceeds root_sponsor_ceiling ({sponsor_ceiling})"
            )

        if not isinstance(actor_token, dict):
            raise DPoPBindingError("actor_token must be a dictionary")
        subagent_did = actor_token.get("sub")
        parent_agent_did = actor_token.get("parent_sub")
        if not isinstance(subagent_did, str) or not subagent_did:
            raise DPoPBindingError("actor_token missing subagent 'sub'")
        if not isinstance(parent_agent_did, str) or not parent_agent_did:
            raise DPoPBindingError("actor_token missing 'parent_sub' delegation claim")

        parent_ceiling = actor_token.get("parent_budget_ceiling_minor_units")
        if parent_ceiling is not None:
            if not isinstance(parent_ceiling, int) or requested_budget_minor_units > parent_ceiling:
                raise TokenExchangePrivilegeError(
                    f"Subagent privilege escalation blocked: requested_budget ({requested_budget_minor_units}) "
                    f"exceeds parent_agent_ceiling ({parent_ceiling})"
                )

        # Check wire payload amount if present against attenuated ceiling
        for amount_field in ("amount", "amount_minor_units"):
            if amount_field in wire_payload:
                wire_amount = wire_payload[amount_field]
                if isinstance(wire_amount, (int, float)) and not isinstance(wire_amount, bool):
                    if wire_amount > requested_budget_minor_units:
                        raise TokenExchangePrivilegeError(
                            f"Wire payload {amount_field} ({wire_amount}) exceeds requested budget ceiling "
                            f"({requested_budget_minor_units})"
                        )

        canonical_aud = _normalize_and_validate_htu(aud)
        allowed_audiences = subject_token.get("allowed_audiences")
        if allowed_audiences is not None and canonical_aud not in allowed_audiences:
            raise TargetBindingMismatchError(
                f"Target resource audience {canonical_aud!r} not permitted by subject_token"
            )

        effective_epoch = (
            int(policy_epoch)
            if policy_epoch is not None
            else int(subject_token.get("policy_epoch", self.active_policy_epoch))
        )
        if effective_epoch < self.active_policy_epoch:
            raise PolicyEpochError(
                f"Stale policy_epoch ({effective_epoch}) during token exchange; "
                f"active_policy_epoch is {self.active_policy_epoch}"
            )

        if isinstance(sidecar_pubkey_or_jkt, str):
            if not sidecar_pubkey_or_jkt:
                raise DPoPBindingError("sidecar_dpop_jkt must be a non-empty string")
            sidecar_jkt = sidecar_pubkey_or_jkt
        else:
            sidecar_jkt = compute_ed25519_jwk_thumbprint(sidecar_pubkey_or_jkt)

        caid = compute_payload_caid(wire_payload)
        now = int(time.time()) if iat is None else int(iat)
        token_jti = jti if jti is not None else f"tx-{uuid.uuid4().hex}"

        claims: Dict[str, Any] = {
            "iss": self.issuer,
            "sub": root_sponsor_did,
            "aud": canonical_aud,
            "act": {
                "sub": subagent_did,
                "parent_sub": parent_agent_did,
            },
            "cnf": {
                "jkt": sidecar_jkt,
            },
            "caid": caid,
            "budget_ceiling_minor_units": requested_budget_minor_units,
            "jti": token_jti,
            "iat": now,
            "exp": now + int(ttl_seconds),
            "policy_epoch": effective_epoch,
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "token_type": "DPoP",
        }

        sig_bytes = self._as_privkey.sign(encode_jcs(claims))
        exchanged_token = dict(claims)
        exchanged_token["signature"] = _b64url_encode(sig_bytes)
        return exchanged_token


def create_dpop_proof(
    sidecar_privkey: ed25519.Ed25519PrivateKey,
    htm: str,
    htu: str,
    access_token_bytes: Union[bytes, Dict[str, Any]],
    caid: str,
    jti: str,
    iat: int,
) -> Dict[str, Any]:
    """
    Produces an Ed25519-signed RFC 9449 DPoP proof binding the HTTP method (`htm`),
    target URI without query/fragment (`htu`), SHA-256 base64url hash of the access
    token (`ath`), action `caid`, unique nonce `jti`, and timestamp `iat` to the
    AEIB Station 2 sidecar's public key JWK.
    """
    if not isinstance(sidecar_privkey, ed25519.Ed25519PrivateKey):
        raise TypeError("sidecar_privkey must be an ed25519.Ed25519PrivateKey")
    if not isinstance(htm, str) or not htm.strip():
        raise TargetBindingMismatchError("HTTP method (htm) must be a non-empty string")
    canonical_htu = _normalize_and_validate_htu(htu)

    if isinstance(access_token_bytes, dict):
        raw_token_bytes = encode_jcs(access_token_bytes)
    elif isinstance(access_token_bytes, bytes):
        raw_token_bytes = access_token_bytes
    else:
        raise TypeError("access_token_bytes must be canonical bytes or an access_token dict")

    if not isinstance(caid, str) or not caid:
        raise PayloadCaidMismatchError("caid must be a non-empty hex SHA-256 string")
    if not isinstance(jti, str) or not jti:
        raise DPoPBindingError("jti must be a non-empty unique nonce string")
    if not isinstance(iat, int) or isinstance(iat, bool):
        raise DPoPBindingError("iat must be an integer UNIX timestamp")

    ath = _b64url_encode(hashlib.sha256(raw_token_bytes).digest())
    sidecar_jwk = ed25519_public_key_to_jwk(sidecar_privkey.public_key())

    proof_claims: Dict[str, Any] = {
        "typ": "dpop+jwt",
        "alg": "EdDSA",
        "jwk": sidecar_jwk,
        "htm": htm.upper(),
        "htu": canonical_htu,
        "ath": ath,
        "caid": caid,
        "jti": jti,
        "iat": iat,
    }

    sig_bytes = sidecar_privkey.sign(encode_jcs(proof_claims))
    proof = dict(proof_claims)
    proof["signature"] = _b64url_encode(sig_bytes)
    return proof


class RFC9449DPoPProver:
    """
    AEIB Station 2 Sidecar RFC 9449 DPoP Prover.
    Holds the sidecar's isolated Ed25519 key pair and generates single-use DPoP proofs.
    """

    def __init__(self, sidecar_privkey: Optional[ed25519.Ed25519PrivateKey] = None) -> None:
        self._sidecar_privkey = sidecar_privkey or ed25519.Ed25519PrivateKey.generate()
        self.sidecar_pubkey = self._sidecar_privkey.public_key()
        self.jkt = compute_ed25519_jwk_thumbprint(self.sidecar_pubkey)

    @staticmethod
    def create_dpop_proof(
        sidecar_privkey: ed25519.Ed25519PrivateKey,
        htm: str,
        htu: str,
        access_token_bytes: Union[bytes, Dict[str, Any]],
        caid: str,
        jti: str,
        iat: int,
    ) -> Dict[str, Any]:
        """Static/instance helper delegating to `create_dpop_proof`."""
        return create_dpop_proof(
            sidecar_privkey=sidecar_privkey,
            htm=htm,
            htu=htu,
            access_token_bytes=access_token_bytes,
            caid=caid,
            jti=jti,
            iat=iat,
        )

    def prove_for_token(
        self,
        access_token: Dict[str, Any],
        htm: str,
        htu: str,
        jti: Optional[str] = None,
        iat: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generates a DPoP proof using this sidecar instance's private key."""
        return create_dpop_proof(
            sidecar_privkey=self._sidecar_privkey,
            htm=htm,
            htu=htu,
            access_token_bytes=encode_jcs(access_token),
            caid=str(access_token.get("caid", "")),
            jti=jti or f"dpop-{uuid.uuid4().hex}",
            iat=int(time.time()) if iat is None else int(iat),
        )


class RFC9449DPoPVerifier:
    """
    RFC 9449 DPoP & RFC 8693 Sender-Constrained Dispatch Verifier.

    Enforces:
      1. Authorization Server Ed25519 signature on `access_token`;
      2. DPoP proof Ed25519 signature using the embedded JWK;
      3. Sender constraint: `compute_ed25519_jwk_thumbprint(dpop_pubkey) == access_token["cnf"]["jkt"]`;
      4. Access token hash binding (`ath == base64url(sha256(encode_jcs(access_token)))`);
      5. Exact HTTP method (`htm`) and RFC 8707 target URI (`htu == access_token["aud"]`);
      6. Exact RFC 8785 JCS `caid` match against `wire_payload`;
      7. Single-use `jti` replay cache and `policy_epoch` freshness.
    """

    def __init__(self) -> None:
        self._consumed_dpop_jtis: Set[str] = set()
        self._consumed_token_jtis: Set[str] = set()

    def verify_dpop_bound_dispatch(
        self,
        access_token: Dict[str, Any],
        dpop_proof: Dict[str, Any],
        expected_htm: str,
        expected_htu: str,
        wire_payload: Dict[str, Any],
        as_pubkey: ed25519.Ed25519PublicKey,
        active_policy_epoch: int,
    ) -> Dict[str, Any]:
        """Verifies a sender-constrained access token and DPoP proof before executing dispatch."""
        if not isinstance(access_token, dict):
            raise DPoPBindingError("access_token must be a dictionary")
        if not isinstance(dpop_proof, dict):
            raise DPoPBindingError("dpop_proof must be a dictionary")
        if not isinstance(as_pubkey, ed25519.Ed25519PublicKey):
            raise TypeError("as_pubkey must be an ed25519.Ed25519PublicKey")

        # 1. Verify Authorization Server Ed25519 signature on access_token
        if "signature" not in access_token:
            raise DPoPBindingError("access_token missing AS signature")
        token_claims = dict(access_token)
        token_sig_b64 = token_claims.pop("signature")
        token_sig_bytes = _b64url_decode(token_sig_b64)
        try:
            as_pubkey.verify(token_sig_bytes, encode_jcs(token_claims))
        except InvalidSignature as exc:
            raise DPoPBindingError("Invalid Authorization Server Ed25519 signature on access_token") from exc

        # 2. Verify DPoP proof Ed25519 signature using embedded JWK
        if dpop_proof.get("typ") != "dpop+jwt" or dpop_proof.get("alg") != "EdDSA":
            raise DPoPBindingError("DPoP proof must declare typ='dpop+jwt' and alg='EdDSA'")
        if "signature" not in dpop_proof:
            raise DPoPBindingError("dpop_proof missing Ed25519 signature")
        embedded_jwk = dpop_proof.get("jwk")
        if not isinstance(embedded_jwk, dict):
            raise DPoPBindingError("dpop_proof missing embedded public key JWK")

        dpop_pubkey = ed25519_public_key_from_jwk(embedded_jwk)
        proof_claims = dict(dpop_proof)
        proof_sig_b64 = proof_claims.pop("signature")
        proof_sig_bytes = _b64url_decode(proof_sig_b64)
        try:
            dpop_pubkey.verify(proof_sig_bytes, encode_jcs(proof_claims))
        except InvalidSignature as exc:
            raise DPoPBindingError("Invalid DPoP proof Ed25519 signature") from exc

        # 3. Verify sender constraint: JWK thumbprint matches access_token["cnf"]["jkt"]
        computed_jkt = compute_ed25519_jwk_thumbprint(dpop_pubkey)
        cnf_claim = access_token.get("cnf")
        if not isinstance(cnf_claim, dict) or not isinstance(cnf_claim.get("jkt"), str):
            raise DPoPBindingError("access_token missing cnf.jkt sender constraint claim")
        expected_jkt = cnf_claim["jkt"]
        if not hmac.compare_digest(computed_jkt, expected_jkt):
            raise DPoPBindingError(
                f"Sender constraint violation: DPoP key JWK thumbprint ({computed_jkt}) "
                f"does not match access_token cnf.jkt ({expected_jkt})"
            )

        # 4. Verify access token hash binding: ath == base64url(sha256(encode_jcs(access_token)))
        expected_ath = _b64url_encode(hashlib.sha256(encode_jcs(access_token)).digest())
        proof_ath = dpop_proof.get("ath")
        if not isinstance(proof_ath, str) or not hmac.compare_digest(proof_ath, expected_ath):
            raise AccessTokenHashError(
                "DPoP proof ath mismatch: access token hash binding check failed"
            )

        # 5. Verify exact HTTP method (htm) and RFC 8707 target URI (htu == access_token["aud"])
        canonical_expected_htu = _normalize_and_validate_htu(expected_htu)
        proof_htm = dpop_proof.get("htm")
        proof_htu = dpop_proof.get("htu")
        token_aud = access_token.get("aud")
        if not isinstance(proof_htm, str) or proof_htm.upper() != expected_htm.upper():
            raise TargetBindingMismatchError(
                f"DPoP HTTP method mismatch: proof htm={proof_htm!r}, expected={expected_htm.upper()!r}"
            )
        if proof_htu != canonical_expected_htu or token_aud != canonical_expected_htu:
            raise TargetBindingMismatchError(
                f"RFC 8707 / RFC 9449 target URI mismatch: proof htu={proof_htu!r}, "
                f"token aud={token_aud!r}, expected={canonical_expected_htu!r}"
            )

        # 6. Verify exact RFC 8785 JCS caid match against wire_payload
        computed_caid = compute_payload_caid(wire_payload)
        token_caid = access_token.get("caid")
        proof_caid = dpop_proof.get("caid")
        if not isinstance(token_caid, str) or not hmac.compare_digest(token_caid, computed_caid):
            raise PayloadCaidMismatchError(
                f"Wire payload caid ({computed_caid}) does not match access_token caid ({token_caid})"
            )
        if not isinstance(proof_caid, str) or not hmac.compare_digest(proof_caid, computed_caid):
            raise PayloadCaidMismatchError(
                f"Wire payload caid ({computed_caid}) does not match dpop_proof caid ({proof_caid})"
            )

        # Also enforce budget ceiling against wire_payload if amount field is present
        budget_ceiling = access_token.get("budget_ceiling_minor_units")
        if isinstance(budget_ceiling, int):
            for amount_field in ("amount", "amount_minor_units"):
                if amount_field in wire_payload:
                    val = wire_payload[amount_field]
                    if isinstance(val, (int, float)) and not isinstance(val, bool) and val > budget_ceiling:
                        raise TokenExchangePrivilegeError(
                            f"Wire payload {amount_field} ({val}) exceeds token budget ceiling ({budget_ceiling})"
                        )

        # 7. Verify policy_epoch freshness and single-use jti replay cache
        token_epoch = access_token.get("policy_epoch")
        if not isinstance(token_epoch, int) or token_epoch != active_policy_epoch:
            raise PolicyEpochError(
                f"Policy epoch mismatch: token policy_epoch={token_epoch!r}, "
                f"active_policy_epoch={active_policy_epoch!r}"
            )

        proof_jti = dpop_proof.get("jti")
        token_jti = access_token.get("jti")
        if not isinstance(proof_jti, str) or not proof_jti:
            raise DPoPBindingError("dpop_proof missing non-empty jti claim")
        if not isinstance(token_jti, str) or not token_jti:
            raise DPoPBindingError("access_token missing non-empty jti claim")

        if proof_jti in self._consumed_dpop_jtis:
            raise DPoPReplayError(f"Replayed DPoP proof jti nonce detected: {proof_jti!r}")
        if token_jti in self._consumed_token_jtis:
            raise DPoPReplayError(f"Replayed single-operation access_token jti detected: {token_jti!r}")

        self._consumed_dpop_jtis.add(proof_jti)
        self._consumed_token_jtis.add(token_jti)

        return {
            "verified": True,
            "sub": access_token["sub"],
            "act": access_token["act"],
            "aud": token_aud,
            "htm": expected_htm.upper(),
            "caid": computed_caid,
            "cnf_jkt": computed_jkt,
            "dpop_jti": proof_jti,
            "token_jti": token_jti,
            "policy_epoch": token_epoch,
            "budget_ceiling_minor_units": budget_ceiling,
        }


_DEFAULT_VERIFIER = RFC9449DPoPVerifier()


def verify_dpop_bound_dispatch(
    access_token: Dict[str, Any],
    dpop_proof: Dict[str, Any],
    expected_htm: str,
    expected_htu: str,
    wire_payload: Dict[str, Any],
    as_pubkey: ed25519.Ed25519PublicKey,
    active_policy_epoch: int,
    *,
    verifier: Optional[RFC9449DPoPVerifier] = None,
) -> Dict[str, Any]:
    """
    Module-level entry point for RFC 9449 DPoP sender-constrained dispatch verification.
    Uses the provided `RFC9449DPoPVerifier` instance or the module-level replay-tracking verifier.
    """
    active_verifier = verifier if verifier is not None else _DEFAULT_VERIFIER
    return active_verifier.verify_dpop_bound_dispatch(
        access_token=access_token,
        dpop_proof=dpop_proof,
        expected_htm=expected_htm,
        expected_htu=expected_htu,
        wire_payload=wire_payload,
        as_pubkey=as_pubkey,
        active_policy_epoch=active_policy_epoch,
    )
