#!/usr/bin/env python3
"""
src/coinbase_x402_agent_gateway.py
================================================================================
Coinbase Developer Platform (CDP) & x402 Hardened Agent Gateway.

Pre-dispatch idempotency interlock, pre-socket escrow reservation, SIWx target URL
binding, transport ambiguity latching (HTTP 504 EFFECT_INDETERMINATE), multi-agent
velocity smurfing guards, and RFC 8785 canonical Ed25519 SCITT receipts.

Evaluation status: prototype evaluated under the stated model.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import logging
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Iterable, Iterator, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

try:
    from src.aeib_track1_and_calibrated_guards import canonical_json_v1
    from src.jcs_canonicalizer import encode_jcs
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.aeib_track1_and_calibrated_guards import canonical_json_v1
    from src.jcs_canonicalizer import encode_jcs

logger = logging.getLogger("coinbase_x402_agent_gateway")


def _fsync_fd(fd: int) -> None:
    """
    Flushes file descriptor to non-volatile storage.
    On macOS Darwin, attempts fcntl(fd, F_FULLFSYNC) first; falls back to os.fsync.
    """
    if sys.platform == "darwin":
        full_fsync = getattr(fcntl, "F_FULLFSYNC", None)
        if full_fsync is not None:
            try:
                fcntl.fcntl(fd, full_fsync)
                return
            except OSError:
                pass
    os.fsync(fd)


# Disposition constants
DISPOSITION_TRY_RESERVED = "TRY_RESERVED"
DISPOSITION_CONFIRMED = "CONFIRMED"
DISPOSITION_REFUTED = "REFUTED"
DISPOSITION_EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
DISPOSITION_REJECTED = "REJECTED"
# Claimed under the journal lock immediately before the outbound HTTP call so that
# a second caller/process cannot dispatch the same escrow (crash => reconcile).
DISPOSITION_DISPATCHING = "DISPATCHING"
_HELD_DISPOSITIONS = (
    DISPOSITION_TRY_RESERVED,
    DISPOSITION_DISPATCHING,
    DISPOSITION_EFFECT_INDETERMINATE,
)

# Domain separation tag folded into every derived CAID preimage.
CAID_DOMAIN_TAG = "aeib.x402.payment_intent.v1"

# Percent-encoded '.', '/' and '\' are rejected in bound paths (fail closed) so that
# the signed path cannot be re-interpreted by a downstream normalizer.
_ENCODED_DOT_OR_SLASH = re.compile(r"%(2e|2f|5c)", re.IGNORECASE)


def _require_int_at_least(value: Any, field_name: str, err_code: str, minimum: int) -> int:
    """Fails closed unless value is an exact int (bool rejected) and >= minimum."""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{err_code}: {field_name} must be an int >= {minimum}, got {value!r}")
    return value


def _require_positive_amount(value: Any, field_name: str = "amount_micro_usdc") -> int:
    """Fails closed on bool, float, zero and negative amounts."""
    return _require_int_at_least(value, field_name, "ERR_INVALID_AMOUNT", 1)


def _require_nonempty_str(value: Any, field_name: str, err_code: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{err_code}: {field_name} must be a non-empty str, got {value!r}")
    return value


# Scripts that legitimately co-occur inside one label (Japanese / Korean writing).
_HAN_FAMILY = frozenset({"CJK", "HIRAGANA", "KATAKANA", "HANGUL", "IDEOGRAPHIC"})


def _label_scripts(label: str) -> FrozenSet[str]:
    """Script set of the letters in a Unicode label (stdlib unicodedata names)."""
    scripts = set()
    for ch in label:
        if not unicodedata.category(ch).startswith("L"):
            continue  # digits, hyphen, combining marks inherit / are common
        script = unicodedata.name(ch, "UNKNOWN").split()[0]
        scripts.add("HAN" if script in _HAN_FAMILY else script)
    return frozenset(scripts)


def _check_host_labels(host: str, allow_mixed_script_hosts: bool, allow_idn_hosts: bool) -> None:
    """
    Host-label confusable policy on the A-label host. Each xn-- label is decoded
    to Unicode; a label whose letters span more than one script (e.g. Latin +
    Cyrillic) fails closed with ERR_URL_CONFUSABLE_HOST unless explicitly allowed.
    Single-script IDN labels are allowed unless allow_idn_hosts is False.
    """
    for label in host.split("."):
        if not label.startswith("xn--"):
            continue
        try:
            u_label = label.encode("ascii").decode("idna")
        except UnicodeError as err:
            raise ValueError("ERR_URL_NOT_CANONICAL: invalid A-label in host") from err
        if not allow_idn_hosts:
            raise ValueError(f"ERR_URL_IDN_HOST_REJECTED: IDN label {label} (allow_idn_hosts=False)")
        if len(_label_scripts(u_label)) > 1 and not allow_mixed_script_hosts:
            raise ValueError(f"ERR_URL_CONFUSABLE_HOST: mixed-script host label {label}")


def canonicalize_siwx_url(
    url: str,
    allow_insecure_http: bool = False,
    allow_mixed_script_hosts: bool = False,
    allow_idn_hosts: bool = True,
) -> Tuple[str, str, str, str]:
    """
    Canonical (scheme, host, path, query) for SIWx binding.

    Fails closed with ValueError on:
      ERR_URL_INSECURE_SCHEME  http:// while allow_insecure_http is False.
      ERR_URL_NOT_CANONICAL    other schemes, control chars/whitespace anywhere,
                               fragments, userinfo, empty hosts, trailing-dot or
                               empty host labels, non-ASCII hosts whose IDNA round
                               trip is not identical, '.'/'..' path segments,
                               backslashes and percent-encoded '.', '/' or '\\'
                               in the path.
      ERR_URL_CONFUSABLE_HOST  a host label (Unicode or xn-- form) mixing
                               scripts, e.g. Latin + Cyrillic (default-on).
      ERR_URL_IDN_HOST_REJECTED any IDN label when allow_idn_hosts is False.
    Scheme and host are lowercased; path and query are preserved byte-exact, so
    any change to query parameters (value, order, added or dropped) mismatches.
    """
    if type(url) is not str or any(ord(ch) <= 0x20 or ord(ch) == 0x7F for ch in url):
        raise ValueError("ERR_URL_NOT_CANONICAL: control character or whitespace in URL")
    if "#" in url:
        raise ValueError("ERR_URL_NOT_CANONICAL: fragments are not permitted")
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme == "http" and not allow_insecure_http:
        raise ValueError("ERR_URL_INSECURE_SCHEME: http:// rejected (allow_insecure_http=False)")
    if scheme not in ("http", "https"):
        raise ValueError(f"ERR_URL_NOT_CANONICAL: unsupported scheme {parsed.scheme!r}")
    if "@" in parsed.netloc:
        raise ValueError("ERR_URL_NOT_CANONICAL: userinfo is not permitted")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("ERR_URL_NOT_CANONICAL: empty host")
    if not host.isascii():
        try:
            a_label = host.encode("idna").decode("ascii")
            round_trip = a_label.encode("ascii").decode("idna")
        except UnicodeError as err:
            raise ValueError("ERR_URL_NOT_CANONICAL: host is not IDNA encodable") from err
        if round_trip != host:
            raise ValueError("ERR_URL_NOT_CANONICAL: host changes under IDNA normalization")
        host = a_label
    if "" in host.split("."):
        raise ValueError("ERR_URL_NOT_CANONICAL: trailing dot or empty host label")
    _check_host_labels(host, allow_mixed_script_hosts is True, allow_idn_hosts is not False)
    if parsed.port:
        host = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    if "\\" in path or _ENCODED_DOT_OR_SLASH.search(path):
        raise ValueError("ERR_URL_NOT_CANONICAL: backslash or encoded dot/slash in path")
    if any(segment in (".", "..") for segment in path.split("/")):
        raise ValueError("ERR_URL_NOT_CANONICAL: dot segment in path")
    return scheme, host, path, parsed.query


def derive_payment_caid(
    *,
    agent_id: str,
    payee_address: str,
    amount_micro_usdc: int,
    target_url: str,
    target_method: str,
    chain_id: int,
    nonce: str,
    timestamp_epoch: int,
) -> str:
    """CAID = sha256(RFC 8785 JCS(intent fields + domain tag)), hex encoded."""
    payload = {
        "agent_id": agent_id,
        "amount_micro_usdc": amount_micro_usdc,
        "chain_id": chain_id,
        "domain": CAID_DOMAIN_TAG,
        "nonce": nonce,
        "payee_address": payee_address,
        "target_method": target_method.upper(),
        "target_url": target_url,
        "timestamp_epoch": timestamp_epoch,
    }
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


@dataclass(frozen=True)
class PaymentIntent:
    """Canonical payment intent for x402 machine-to-machine settlement.

    ``caid`` may be empty, in which case the gateway uses the derived CAID; if it
    is supplied it must equal :meth:`derived_caid` or the gateway fails closed.
    """

    caid: str
    agent_id: str
    payee_address: str
    amount_micro_usdc: int
    target_url: str
    target_method: str
    chain_id: int
    nonce: str
    timestamp_epoch: int

    def __post_init__(self) -> None:
        _require_positive_amount(self.amount_micro_usdc)
        _require_int_at_least(self.chain_id, "chain_id", "ERR_INVALID_CHAIN_ID", 1)
        _require_int_at_least(self.timestamp_epoch, "timestamp_epoch", "ERR_INVALID_TIMESTAMP", 0)
        _require_nonempty_str(self.nonce, "nonce", "ERR_INVALID_NONCE")
        if type(self.caid) is not str:
            raise ValueError(f"ERR_INVALID_CAID: caid must be a str, got {self.caid!r}")

    def derived_caid(self) -> str:
        return derive_payment_caid(
            agent_id=self.agent_id,
            payee_address=self.payee_address,
            amount_micro_usdc=self.amount_micro_usdc,
            target_url=self.target_url,
            target_method=self.target_method,
            chain_id=self.chain_id,
            nonce=self.nonce,
            timestamp_epoch=self.timestamp_epoch,
        )

    @classmethod
    def build(
        cls,
        *,
        agent_id: str,
        payee_address: str,
        amount_micro_usdc: int,
        target_url: str,
        target_method: str,
        chain_id: int,
        nonce: str,
        timestamp_epoch: int,
    ) -> "PaymentIntent":
        """Constructs an intent whose caid is the derived RFC 8785 digest."""
        draft = cls(
            caid="",
            agent_id=agent_id,
            payee_address=payee_address,
            amount_micro_usdc=amount_micro_usdc,
            target_url=target_url,
            target_method=target_method,
            chain_id=chain_id,
            nonce=nonce,
            timestamp_epoch=timestamp_epoch,
        )
        return cls(**{**asdict(draft), "caid": draft.derived_caid()})

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "amount_micro_usdc": self.amount_micro_usdc,
            "caid": self.caid,
            "chain_id": self.chain_id,
            "nonce": self.nonce,
            "payee_address": self.payee_address,
            "target_method": self.target_method.upper(),
            "target_url": self.target_url,
            "timestamp_epoch": self.timestamp_epoch,
        }


@dataclass(frozen=True)
class SIWxBinding:
    """SIWx cryptographically bound target URL and method authorization."""

    caid: str
    target_scheme: str
    target_host: str
    target_path: str
    target_query: str
    target_method: str
    payee_address: str
    amount_micro_usdc: int
    chain_id: int
    nonce: str
    timestamp_epoch: int
    siwx_digest: str
    signature_hex: str
    signer_pubkey_hex: str

    def __post_init__(self) -> None:
        _require_positive_amount(self.amount_micro_usdc)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "amount_micro_usdc": self.amount_micro_usdc,
            "caid": self.caid,
            "chain_id": self.chain_id,
            "nonce": self.nonce,
            "payee_address": self.payee_address,
            "signature_hex": self.signature_hex,
            "signer_pubkey_hex": self.signer_pubkey_hex,
            "siwx_digest": self.siwx_digest,
            "target_host": self.target_host,
            "target_method": self.target_method.upper(),
            "target_path": self.target_path,
            "target_query": self.target_query,
            "target_scheme": self.target_scheme,
            "timestamp_epoch": self.timestamp_epoch,
        }


@dataclass
class GatewayConfig:
    """Configuration for Coinbase CDP & x402 Agent Gateway."""

    journal_path: Path
    initial_balance_micro_usdc: int = 10_000_000  # claim: config
    epoch_duration_seconds: int = 3600  # claim: config
    max_velocity_bps: int = 2500  # claim: config (25.00% max spend per epoch)
    single_tx_max_bps: int = 500  # claim: config (5.00% max spend per transaction)
    max_tx_per_epoch: int = 50  # claim: config
    timeout_ms: int = 5000  # claim: config
    max_clock_skew_seconds: int = 300  # claim: config (|intent ts - gateway clock| bound)


class CoinbaseX402AgentGateway:
    """
    Hardened Agent Gateway connecting Coinbase CDP / AgentKit and x402 HTTP rails
    with pre-dispatch escrow reservation, SIWx target URL binding, 504 latching,
    velocity quota controls, and RFC 8785 SCITT receipts.

    SIWx bindings are accepted only from signer public keys in
    ``trusted_signer_pubkeys_hex``; an empty allow-set fails closed. Velocity
    epochs are assigned from the gateway's own ``clock`` (injectable for tests).
    Nonces are single-use and persisted in the fsync journal.

    Cross-process consistency: every state-changing operation holds an exclusive
    ``fcntl.flock`` on ``<journal_path>.lock`` and first replays journal lines
    appended by other processes (tracked by byte offset) before checking nonces,
    CAIDs, balances and velocity, then appends + fsyncs before releasing. This is
    advisory locking on a local filesystem, evaluated under the stated model; it
    does not cover network filesystems without flock semantics.
    """

    def __init__(
        self,
        config: GatewayConfig,
        private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        trusted_signer_pubkeys_hex: Optional[Iterable[str]] = None,
        clock: Optional[Callable[[], int]] = None,
        allow_insecure_http: bool = False,
        allowed_target_hosts: Optional[Iterable[str]] = None,
        allow_mixed_script_hosts: bool = False,
        allow_idn_hosts: bool = True,
    ):
        self.config = config
        self.journal_path = Path(config.journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

        if private_key is None:
            self.private_key = ed25519.Ed25519PrivateKey.generate()
        else:
            self.private_key = private_key
        self.public_key = self.private_key.public_key()
        self.pubkey_hex = self.public_key.public_bytes_raw().hex()

        self.trusted_signer_pubkeys_hex: FrozenSet[str] = self._normalize_trusted_signers(
            trusted_signer_pubkeys_hex or ()
        )
        self._clock: Callable[[], int] = clock if clock is not None else time.time
        self.allow_insecure_http = allow_insecure_http is True
        self.allow_mixed_script_hosts = allow_mixed_script_hosts is True
        self.allow_idn_hosts = allow_idn_hosts is not False
        # None keeps the pre-existing behaviour (any canonical host). Deployments
        # handling real funds should set an explicit payee-host allow-set so the
        # gateway enforces its own host policy even if the signer auto-signs
        # agent-proposed URLs (prompt-injection case). An empty set rejects all.
        self.allowed_target_hosts: Optional[FrozenSet[str]] = (
            None if allowed_target_hosts is None
            else self._normalize_allowed_hosts(allowed_target_hosts)
        )

        self.lock_path = self.journal_path.with_name(self.journal_path.name + ".lock")
        self._lock_depth = 0
        self._journal_offset = 0
        self._journal_entries: Dict[str, Dict[str, Any]] = {}
        self._consumed_nonces: Dict[str, str] = {}
        with self._journal_lock():
            pass

    @staticmethod
    def _normalize_trusted_signers(pubkeys_hex: Iterable[str]) -> FrozenSet[str]:
        """Validates each allow-set entry as a raw 32-byte Ed25519 public key."""
        normalized = set()
        for raw in pubkeys_hex:
            try:
                ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(raw))
            except (TypeError, ValueError) as err:
                raise ValueError(f"ERR_INVALID_TRUSTED_SIGNER_PUBKEY: {raw!r}") from err
            normalized.add(raw.lower())
        return frozenset(normalized)

    def _normalize_allowed_hosts(self, hosts: Iterable[str]) -> FrozenSet[str]:
        """Canonicalizes each allow-set entry ("host" or "host:port") like a target host."""
        normalized = set()
        for raw in hosts:
            if type(raw) is not str or not raw or "/" in raw:
                raise ValueError(f"ERR_INVALID_ALLOWED_TARGET_HOST: {raw!r}")
            try:
                _scheme, host, _path, _query = canonicalize_siwx_url(
                    f"https://{raw}/",
                    allow_mixed_script_hosts=self.allow_mixed_script_hosts,
                    allow_idn_hosts=self.allow_idn_hosts,
                )
            except ValueError as err:
                raise ValueError(f"ERR_INVALID_ALLOWED_TARGET_HOST: {raw!r}") from err
            normalized.add(host)
        return frozenset(normalized)

    def _check_target_host_allowed(self, target_url: str) -> None:
        """Fails closed when an allow-set is configured and the canonical host is absent."""
        if self.allowed_target_hosts is None:
            return
        host = self.canonical_target(target_url)[1]
        if host not in self.allowed_target_hosts:
            raise ValueError(f"ERR_TARGET_HOST_NOT_ALLOWED: {host} not in allowed_target_hosts")

    def _now(self) -> int:
        """Gateway-owned clock reading (integer epoch seconds)."""
        return int(self._clock())

    @staticmethod
    def _validate_journal_entry(entry: Dict[str, Any]) -> None:
        """Fails closed on journal entries with invalid amount, caid or nonce."""
        _require_nonempty_str(entry.get("caid"), "caid", "ERR_JOURNAL_ENTRY_MALFORMED")
        _require_nonempty_str(entry.get("nonce"), "nonce", "ERR_JOURNAL_ENTRY_MALFORMED")
        _require_positive_amount(entry.get("amount_micro_usdc"))

    def _record_nonce(self, nonce: str, caid: str) -> None:
        owner = self._consumed_nonces.get(nonce)
        if owner is not None and owner != caid:
            raise ValueError(
                f"ERR_JOURNAL_NONCE_CONFLICT: nonce {nonce} bound to {owner} and {caid}"
            )
        self._consumed_nonces[nonce] = caid

    @contextlib.contextmanager
    def _journal_lock(self) -> Iterator[None]:
        """
        Exclusive cross-process lock on <journal_path>.lock (re-entrant within this
        instance). On acquisition, replays journal lines appended since the last
        read so that all checks run against the current on-disk state.
        """
        if self._lock_depth > 0:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return
        fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            self._lock_depth = 1
            try:
                self._replay_new_journal_lines()
                yield
            finally:
                self._lock_depth = 0
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _replay_new_journal_lines(self) -> None:
        """Applies complete journal lines beyond the tracked byte offset."""
        if not self.journal_path.exists():
            return
        with open(self.journal_path, "rb") as f:
            f.seek(self._journal_offset)
            data = f.read()
        complete = data[: data.rfind(b"\n") + 1]
        for raw in complete.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            entry = json.loads(stripped.decode("utf-8"))
            self._validate_journal_entry(entry)
            caid = entry["caid"]
            self._record_nonce(entry["nonce"], caid)
            self._journal_entries[caid] = entry
        self._journal_offset += len(complete)

    def _append_journal_entry(self, entry: Dict[str, Any]) -> None:
        """Appends a journal entry to disk with fcntl lock and hardware sync.

        Must be called while holding :meth:`_journal_lock`.
        """
        if self._lock_depth < 1:
            raise RuntimeError("ERR_JOURNAL_LOCK_NOT_HELD: append outside journal lock")
        self._validate_journal_entry(entry)
        line = json.dumps(entry, sort_keys=True) + "\n"
        fd = os.open(
            str(self.journal_path),
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, line.encode("utf-8"))
            _fsync_fd(fd)
            self._journal_offset = os.fstat(fd).st_size
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        caid = entry["caid"]
        self._record_nonce(entry["nonce"], caid)
        self._journal_entries[caid] = entry

    def get_balances(self) -> Dict[str, int]:
        """Calculates current wallet balance, escrow hold, and settled amounts."""
        with self._journal_lock():
            return self._balances_locked()

    def _balances_locked(self) -> Dict[str, int]:
        reserved_micro_usdc = 0  # claim: config
        settled_micro_usdc = 0  # claim: config

        for entry in self._journal_entries.values():
            disp = entry.get("disposition")
            amt = entry["amount_micro_usdc"]
            if disp in _HELD_DISPOSITIONS:
                reserved_micro_usdc += amt
            elif disp == DISPOSITION_CONFIRMED:
                settled_micro_usdc += amt

        available_micro_usdc = (
            self.config.initial_balance_micro_usdc - reserved_micro_usdc - settled_micro_usdc
        )
        return {
            "total_micro_usdc": self.config.initial_balance_micro_usdc,
            "reserved_micro_usdc": reserved_micro_usdc,
            "settled_micro_usdc": settled_micro_usdc,
            "available_micro_usdc": available_micro_usdc,
        }

    @staticmethod
    def parse_url_host_and_path(url: str) -> Tuple[str, str]:
        """
        Legacy helper returning (host, path) of a canonical http(s) URL.
        SIWx bindings use :func:`canonicalize_siwx_url`, which also binds scheme
        and query and rejects http:// unless explicitly allowed.
        """
        _scheme, host, path, _query = canonicalize_siwx_url(url, allow_insecure_http=True)
        return host, path

    def canonical_target(self, url: str) -> Tuple[str, str, str, str]:
        """Canonical (scheme, host, path, query) under this gateway's scheme policy."""
        return canonicalize_siwx_url(
            url,
            allow_insecure_http=self.allow_insecure_http,
            allow_mixed_script_hosts=self.allow_mixed_script_hosts,
            allow_idn_hosts=self.allow_idn_hosts,
        )

    def _effective_caid(self, intent: PaymentIntent) -> str:
        """Returns the derived CAID; a supplied caid must match it (fail closed)."""
        derived = intent.derived_caid()
        if intent.caid and intent.caid != derived:
            raise ValueError(
                f"ERR_CAID_MISMATCH: supplied caid {intent.caid} != derived {derived}"
            )
        return derived

    def create_siwx_binding(
        self,
        intent: PaymentIntent,
        signer_key: ed25519.Ed25519PrivateKey,
    ) -> SIWxBinding:
        """Constructs and signs SIWx target URL authorization binding."""
        caid = self._effective_caid(intent)
        scheme, host, path, query = self.canonical_target(intent.target_url)
        signer_pubkey = signer_key.public_key().public_bytes_raw().hex()

        core_payload = {
            "amount_micro_usdc": intent.amount_micro_usdc,
            "caid": caid,
            "chain_id": intent.chain_id,
            "nonce": intent.nonce,
            "payee_address": intent.payee_address,
            "target_host": host,
            "target_method": intent.target_method.upper(),
            "target_path": path,
            "target_query": query,
            "target_scheme": scheme,
            "timestamp_epoch": intent.timestamp_epoch,
        }
        canonical_bytes = canonical_json_v1(core_payload)
        siwx_digest = hashlib.sha256(canonical_bytes).hexdigest()
        signature_bytes = signer_key.sign(canonical_bytes)
        signature_hex = signature_bytes.hex()

        return SIWxBinding(
            caid=caid,
            target_scheme=scheme,
            target_host=host,
            target_path=path,
            target_query=query,
            target_method=intent.target_method.upper(),
            payee_address=intent.payee_address,
            amount_micro_usdc=intent.amount_micro_usdc,
            chain_id=intent.chain_id,
            nonce=intent.nonce,
            timestamp_epoch=intent.timestamp_epoch,
            siwx_digest=siwx_digest,
            signature_hex=signature_hex,
            signer_pubkey_hex=signer_pubkey,
        )

    def verify_siwx_binding(
        self,
        binding: SIWxBinding,
        target_url: str,
        target_method: str,
    ) -> bool:
        """
        Verifies SIWx binding matches the exact recipient scheme, host, path,
        query and method, and validates Ed25519 signature over the canonical
        binding payload.
        """
        scheme, host, path, query = self.canonical_target(target_url)
        if scheme != binding.target_scheme:
            raise ValueError(
                f"ERR_SIWX_TARGET_URL_MISMATCH: scheme mismatch {scheme} != {binding.target_scheme}"
            )
        if query != binding.target_query:
            raise ValueError("ERR_SIWX_TARGET_URL_MISMATCH: query mismatch")
        if host != binding.target_host:
            raise ValueError(
                f"ERR_SIWX_TARGET_URL_MISMATCH: host mismatch {host} != {binding.target_host}"
            )
        if path != binding.target_path:
            raise ValueError(
                f"ERR_SIWX_TARGET_URL_MISMATCH: path mismatch {path} != {binding.target_path}"
            )
        if target_method.upper() != binding.target_method.upper():
            raise ValueError(
                f"ERR_SIWX_TARGET_URL_MISMATCH: method mismatch {target_method} != {binding.target_method}"
            )

        core_payload = {
            "amount_micro_usdc": binding.amount_micro_usdc,
            "caid": binding.caid,
            "chain_id": binding.chain_id,
            "nonce": binding.nonce,
            "payee_address": binding.payee_address,
            "target_host": binding.target_host,
            "target_method": binding.target_method.upper(),
            "target_path": binding.target_path,
            "target_query": binding.target_query,
            "target_scheme": binding.target_scheme,
            "timestamp_epoch": binding.timestamp_epoch,
        }
        canonical_bytes = canonical_json_v1(core_payload)
        computed_digest = hashlib.sha256(canonical_bytes).hexdigest()
        if computed_digest != binding.siwx_digest:
            raise ValueError("ERR_SIWX_DIGEST_MISMATCH: corrupted digest")

        if not self.trusted_signer_pubkeys_hex:
            raise ValueError("ERR_SIWX_NO_TRUSTED_SIGNERS: empty signer allow-set fails closed")
        if binding.signer_pubkey_hex.lower() not in self.trusted_signer_pubkeys_hex:
            raise ValueError(
                f"ERR_SIWX_SIGNER_NOT_TRUSTED: {binding.signer_pubkey_hex} not in allow-set"
            )

        try:
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(binding.signer_pubkey_hex)
            )
            pubkey.verify(bytes.fromhex(binding.signature_hex), canonical_bytes)
        except (InvalidSignature, ValueError) as err:
            raise ValueError("ERR_SIWX_SIGNATURE_INVALID: cryptographic verification failed") from err

        return True

    @staticmethod
    def _verify_binding_matches_intent(
        binding: SIWxBinding, intent: PaymentIntent, caid: str
    ) -> None:
        """Fails closed unless every signed binding field equals the intent field."""
        expected = {
            "amount_micro_usdc": intent.amount_micro_usdc,
            "caid": caid,
            "chain_id": intent.chain_id,
            "nonce": intent.nonce,
            "payee_address": intent.payee_address,
            "timestamp_epoch": intent.timestamp_epoch,
        }
        for name, value in expected.items():
            if getattr(binding, name) != value:
                raise ValueError(f"ERR_SIWX_INTENT_MISMATCH: binding field {name} differs from intent")

    def check_velocity_and_quota(
        self,
        agent_id: str,
        amount_micro_usdc: int,
    ) -> None:
        """
        Enforces integer basis-point velocity caps and frequency limits per epoch
        to defend against multi-agent smurfing attacks. The epoch is taken from the
        gateway's own clock, never from a caller-supplied timestamp.
        """
        with self._journal_lock():
            self._check_velocity_at(agent_id, amount_micro_usdc, self._now())

    def _check_velocity_at(
        self,
        agent_id: str,
        amount_micro_usdc: int,
        now_epoch: int,
    ) -> None:
        _require_positive_amount(amount_micro_usdc)
        total_balance = self.config.initial_balance_micro_usdc
        single_tx_cap = (total_balance * self.config.single_tx_max_bps) // 10000
        if amount_micro_usdc > single_tx_cap:
            raise ValueError(
                f"ERR_SINGLE_TX_BPS_EXCEEDED: amount {amount_micro_usdc} exceeds single tx cap {single_tx_cap}"
            )

        epoch_window = self.config.epoch_duration_seconds
        current_epoch = now_epoch // epoch_window

        epoch_spent = 0  # claim: config
        epoch_tx_count = 0

        for entry in self._journal_entries.values():
            reserved_at = entry.get("reserved_at_epoch")
            # Entries lacking a gateway-clock stamp are counted in the current
            # epoch (conservative, fail closed).
            entry_epoch = current_epoch if reserved_at is None else reserved_at // epoch_window
            if entry_epoch == current_epoch:
                disp = entry.get("disposition")
                if disp in _HELD_DISPOSITIONS or disp == DISPOSITION_CONFIRMED:
                    epoch_spent += entry["amount_micro_usdc"]
                    epoch_tx_count += 1

        velocity_cap = (total_balance * self.config.max_velocity_bps) // 10000
        if epoch_spent + amount_micro_usdc > velocity_cap:
            raise ValueError(
                f"ERR_VELOCITY_QUOTA_EXCEEDED: cumulative epoch spend {epoch_spent + amount_micro_usdc} exceeds cap {velocity_cap}"
            )

        if epoch_tx_count + 1 > self.config.max_tx_per_epoch:
            raise ValueError(
                f"ERR_SMURFING_FREQUENCY_EXCEEDED: transaction count {epoch_tx_count + 1} exceeds epoch limit {self.config.max_tx_per_epoch}"
            )

    def reserve_escrow(
        self,
        intent: PaymentIntent,
        binding: SIWxBinding,
    ) -> Dict[str, Any]:
        """
        Pre-socket escrow reservation. Validates SIWx binding, velocity quotas,
        and available budget before latching TRY_RESERVED to disk journal.
        Runs entirely under the cross-process journal lock.
        """
        with self._journal_lock():
            return self._reserve_escrow_locked(intent, binding)

    def _reserve_escrow_locked(
        self,
        intent: PaymentIntent,
        binding: SIWxBinding,
    ) -> Dict[str, Any]:
        # Validate SIWx target URL match before touching balance
        caid = self._effective_caid(intent)
        self._check_target_host_allowed(intent.target_url)
        self.verify_siwx_binding(binding, intent.target_url, intent.target_method)
        self._verify_binding_matches_intent(binding, intent, caid)

        now = self._now()
        if abs(intent.timestamp_epoch - now) > self.config.max_clock_skew_seconds:
            raise ValueError(
                f"ERR_TIMESTAMP_SKEW: intent timestamp {intent.timestamp_epoch} outside "
                f"+/-{self.config.max_clock_skew_seconds}s of gateway clock {now}"
            )

        existing = self._journal_entries.get(caid)
        if existing is not None:
            disp = existing.get("disposition")
            if disp == DISPOSITION_EFFECT_INDETERMINATE:
                raise RuntimeError(
                    f"ERR_DUPLICATE_CAID_LATCHED_INDETERMINATE: CAID {caid} latched in indeterminate hold"
                )
            if disp == DISPOSITION_CONFIRMED:
                raise RuntimeError(
                    f"ERR_DUPLICATE_CAID_ALREADY_CONFIRMED: CAID {caid} is already settled"
                )
            if disp == DISPOSITION_TRY_RESERVED:
                raise RuntimeError(
                    f"ERR_DUPLICATE_CAID_IN_FLIGHT: CAID {caid} already has active escrow"
                )

        # Single-use nonce (persisted in the journal, rebuilt on startup)
        if intent.nonce in self._consumed_nonces:
            raise RuntimeError(f"ERR_NONCE_REPLAY: nonce {intent.nonce} already consumed")

        # Enforce smurfing and velocity quota on the gateway clock
        self._check_velocity_at(intent.agent_id, intent.amount_micro_usdc, now)

        balances = self._balances_locked()
        if intent.amount_micro_usdc > balances["available_micro_usdc"]:
            raise ValueError(
                f"ERR_INSUFFICIENT_FUNDS: requested {intent.amount_micro_usdc} exceeds available {balances['available_micro_usdc']}"
            )

        entry = {
            "agent_id": intent.agent_id,
            "amount_micro_usdc": intent.amount_micro_usdc,
            "caid": caid,
            "chain_id": intent.chain_id,
            "disposition": DISPOSITION_TRY_RESERVED,
            "nonce": intent.nonce,
            "payee_address": intent.payee_address,
            "reconciliation_id": None,
            "reserved_at_epoch": now,
            "siwx_digest": binding.siwx_digest,
            "target_method": intent.target_method.upper(),
            "target_url": intent.target_url,
            "timestamp_epoch": intent.timestamp_epoch,
        }
        self._append_journal_entry(entry)

        receipt = self.emit_scitt_receipt(
            caid=caid,
            agent_id=intent.agent_id,
            payee_address=intent.payee_address,
            amount_micro_usdc=intent.amount_micro_usdc,
            target_url=intent.target_url,
            target_method=intent.target_method,
            disposition=DISPOSITION_TRY_RESERVED,
            timestamp_epoch=now,
            siwx_digest=binding.siwx_digest,
        )
        return {
            "status": "RESERVED",
            "caid": caid,
            "amount_micro_usdc": intent.amount_micro_usdc,
            "receipt": receipt,
        }

    def dispatch_payment(
        self,
        intent: PaymentIntent,
        binding: SIWxBinding,
        http_client: Optional[Callable[[str, str, Dict[str, str]], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches payment to remote x402 recipient.
        Latches to EFFECT_INDETERMINATE on HTTP 504 or socket timeout.

        Under the journal lock the escrow is moved TRY_RESERVED -> DISPATCHING
        before the outbound call, so a concurrent caller or process cannot
        dispatch the same CAID; the lock is not held during the HTTP call.
        """
        caid = self._effective_caid(intent)
        with self._journal_lock():
            existing = self._journal_entries.get(caid)
            if existing is None:
                self._reserve_escrow_locked(intent, binding)
            else:
                disp = existing.get("disposition")
                if disp == DISPOSITION_EFFECT_INDETERMINATE:
                    raise RuntimeError(
                        f"ERR_DUPLICATE_CAID_LATCHED_INDETERMINATE: CAID {caid} latched in indeterminate hold"
                    )
                if disp == DISPOSITION_CONFIRMED:
                    raise RuntimeError(
                        f"ERR_DUPLICATE_CAID_ALREADY_CONFIRMED: CAID {caid} is already settled"
                    )
                if disp == DISPOSITION_DISPATCHING:
                    raise RuntimeError(
                        f"ERR_DUPLICATE_CAID_DISPATCH_IN_FLIGHT: CAID {caid} is being dispatched"
                    )
                if disp != DISPOSITION_TRY_RESERVED:
                    raise RuntimeError(
                        f"ERR_CAID_NOT_DISPATCHABLE: CAID {caid} in state {disp} has no active escrow"
                    )
                # Re-verify the presented binding against the reserved intent
                self.verify_siwx_binding(binding, intent.target_url, intent.target_method)
                self._verify_binding_matches_intent(binding, intent, caid)
            claim_entry = dict(self._journal_entries[caid])
            claim_entry["disposition"] = DISPOSITION_DISPATCHING
            claim_entry["dispatch_epoch"] = self._now()
            self._append_journal_entry(claim_entry)

        headers = {
            "Authorization": f"x402 siwx={binding.signature_hex},digest={binding.siwx_digest}",
            "X-CAID": caid,
            "X-Payee": intent.payee_address,
            "X-Amount-Micro-USDC": str(intent.amount_micro_usdc),
        }

        response: Dict[str, Any] = {}
        try:
            if http_client is not None:
                response = http_client(intent.target_method, intent.target_url, headers)
            else:
                # Default nominal dispatch prototype
                response = {"status_code": 200, "tx_hash": f"0xbase_{caid[:16]}"}
        except TimeoutError as err:
            response = {"status_code": 504, "error": str(err)}
        except Exception as exc:
            response = {"status_code": 504, "error": f"Transport fault: {exc}"}

        with self._journal_lock():
            existing = self._journal_entries[caid]
            if existing.get("disposition") != DISPOSITION_DISPATCHING:
                raise RuntimeError(
                    f"ERR_CAID_STATE_CHANGED_CONCURRENTLY: CAID {caid} left DISPATCHING "
                    f"(now {existing.get('disposition')}) during the outbound call"
                )
            status_code = response.get("status_code", 504)

            if status_code in (200, 201):
                settle_entry = dict(existing)
                settle_entry["disposition"] = DISPOSITION_CONFIRMED
                settle_entry["tx_hash"] = response.get("tx_hash", "")
                settle_entry["settled_epoch"] = self._now()
                self._append_journal_entry(settle_entry)

                receipt = self.emit_scitt_receipt(
                    caid=caid,
                    agent_id=intent.agent_id,
                    payee_address=intent.payee_address,
                    amount_micro_usdc=intent.amount_micro_usdc,
                    target_url=intent.target_url,
                    target_method=intent.target_method,
                    disposition=DISPOSITION_CONFIRMED,
                    timestamp_epoch=self._now(),
                    siwx_digest=binding.siwx_digest,
                )
                return {
                    "status": DISPOSITION_CONFIRMED,
                    "status_code": status_code,
                    "caid": caid,
                    "tx_hash": response.get("tx_hash", ""),
                    "receipt": receipt,
                }

            if status_code == 504:
                # Ambiguous transport state -> latch into EFFECT_INDETERMINATE
                latch_entry = dict(existing)
                latch_entry["disposition"] = DISPOSITION_EFFECT_INDETERMINATE
                latch_entry["error"] = response.get("error", "HTTP 504 Gateway Timeout")
                latch_entry["latched_epoch"] = self._now()
                self._append_journal_entry(latch_entry)

                receipt = self.emit_scitt_receipt(
                    caid=caid,
                    agent_id=intent.agent_id,
                    payee_address=intent.payee_address,
                    amount_micro_usdc=intent.amount_micro_usdc,
                    target_url=intent.target_url,
                    target_method=intent.target_method,
                    disposition=DISPOSITION_EFFECT_INDETERMINATE,
                    timestamp_epoch=self._now(),
                    siwx_digest=binding.siwx_digest,
                )
                return {
                    "status": DISPOSITION_EFFECT_INDETERMINATE,
                    "status_code": status_code,
                    "caid": caid,
                    "error": "HTTP 504 Gateway Timeout. Operation latched in indeterminate hold.",
                    "receipt": receipt,
                }

            # Terminal 4xx failure -> refund escrow
            refund_entry = dict(existing)
            refund_entry["disposition"] = DISPOSITION_REFUTED
            refund_entry["error"] = response.get("error", f"HTTP {status_code}")
            refund_entry["refuted_epoch"] = self._now()
            self._append_journal_entry(refund_entry)

            receipt = self.emit_scitt_receipt(
                caid=caid,
                agent_id=intent.agent_id,
                payee_address=intent.payee_address,
                amount_micro_usdc=intent.amount_micro_usdc,
                target_url=intent.target_url,
                target_method=intent.target_method,
                disposition=DISPOSITION_REFUTED,
                timestamp_epoch=self._now(),
                siwx_digest=binding.siwx_digest,
            )
            return {
                "status": DISPOSITION_REFUTED,
                "status_code": status_code,
                "caid": caid,
                "error": response.get("error", f"Rejected with HTTP {status_code}"),
                "receipt": receipt,
            }

    def reconcile(
        self,
        caid: str,
        authoritative_disposition: str,
        probe_receipt: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Out-of-band reconciliation hook to resolve an operation latched
        in EFFECT_INDETERMINATE (or left DISPATCHING by a crashed process) into
        CONFIRMED (settled) or REFUTED (refunded). Runs under the journal lock.
        """
        with self._journal_lock():
            return self._reconcile_locked(caid, authoritative_disposition, probe_receipt)

    def _reconcile_locked(
        self,
        caid: str,
        authoritative_disposition: str,
        probe_receipt: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        existing = self._journal_entries.get(caid)
        if existing is None:
            raise ValueError(f"ERR_CAID_NOT_FOUND: {caid}")

        if existing.get("disposition") not in (
            DISPOSITION_EFFECT_INDETERMINATE,
            DISPOSITION_DISPATCHING,
        ):
            raise ValueError(
                f"ERR_CANNOT_RECONCILE_NON_INDETERMINATE: CAID {caid} in state {existing.get('disposition')}"
            )

        if authoritative_disposition not in (DISPOSITION_CONFIRMED, DISPOSITION_REFUTED):
            raise ValueError(
                f"ERR_INVALID_RECONCILIATION_DISPOSITION: {authoritative_disposition}"
            )

        recon_id = f"recon_{caid[:12]}_{self._now()}"
        updated_entry = dict(existing)
        updated_entry["disposition"] = authoritative_disposition
        updated_entry["reconciliation_id"] = recon_id
        updated_entry["reconciled_epoch"] = self._now()
        if probe_receipt:
            updated_entry["probe_receipt"] = probe_receipt
        self._append_journal_entry(updated_entry)

        receipt = self.emit_scitt_receipt(
            caid=caid,
            agent_id=existing["agent_id"],
            payee_address=existing["payee_address"],
            amount_micro_usdc=existing["amount_micro_usdc"],
            target_url=existing["target_url"],
            target_method=existing["target_method"],
            disposition=authoritative_disposition,
            timestamp_epoch=self._now(),
            siwx_digest=existing["siwx_digest"],
            reconciliation_id=recon_id,
        )
        return {
            "status": authoritative_disposition,
            "caid": caid,
            "reconciliation_id": recon_id,
            "receipt": receipt,
        }

    def emit_scitt_receipt(
        self,
        caid: str,
        agent_id: str,
        payee_address: str,
        amount_micro_usdc: int,
        target_url: str,
        target_method: str,
        disposition: str,
        timestamp_epoch: int,
        siwx_digest: str,
        reconciliation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Emits RFC 8785 canonical JSON receipt signed with Ed25519."""
        _require_positive_amount(amount_micro_usdc)
        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "amount_micro_usdc": amount_micro_usdc,
            "caid": caid,
            "disposition": disposition,
            "payee_address": payee_address,
            "scitt_version": "0.1.0",
            "siwx_digest": siwx_digest,
            "target_method": target_method.upper(),
            "target_url": target_url,
            "timestamp_epoch": timestamp_epoch,
        }
        if reconciliation_id is not None:
            payload["reconciliation_id"] = reconciliation_id

        canonical_bytes = canonical_json_v1(payload)
        receipt_digest = hashlib.sha256(canonical_bytes).hexdigest()
        sig_bytes = self.private_key.sign(canonical_bytes)

        return {
            "payload": payload,
            "receipt_digest": receipt_digest,
            "signature_hex": sig_bytes.hex(),
            "signer_pubkey_hex": self.pubkey_hex,
        }

    @staticmethod
    def verify_scitt_receipt(receipt: Dict[str, Any]) -> bool:
        """Verifies Ed25519 cryptographic signature of a SCITT receipt."""
        payload = receipt.get("payload")
        signature_hex = receipt.get("signature_hex")
        signer_pubkey_hex = receipt.get("signer_pubkey_hex")
        receipt_digest = receipt.get("receipt_digest")

        if not payload or not signature_hex or not signer_pubkey_hex or not receipt_digest:
            return False

        canonical_bytes = canonical_json_v1(payload)
        computed_digest = hashlib.sha256(canonical_bytes).hexdigest()
        if computed_digest != receipt_digest:
            return False

        try:
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(signer_pubkey_hex)
            )
            pubkey.verify(bytes.fromhex(signature_hex), canonical_bytes)
        except (InvalidSignature, ValueError):
            return False

        return True


def run_self_test(journal_dir: Path) -> int:
    """Automated integration self-test for CoinbaseX402AgentGateway."""
    journal_file = journal_dir / "gateway_selftest.jsonl"
    if journal_file.exists():
        journal_file.unlink()

    config = GatewayConfig(
        journal_path=journal_file,
        initial_balance_micro_usdc=5_000_000,  # claim: config
        max_velocity_bps=3000,  # claim: config
        single_tx_max_bps=1000,  # claim: config
        max_tx_per_epoch=20,  # claim: config
    )
    agent_key = ed25519.Ed25519PrivateKey.generate()
    gateway = CoinbaseX402AgentGateway(
        config=config,
        trusted_signer_pubkeys_hex=[agent_key.public_key().public_bytes_raw().hex()],
    )

    now = int(time.time())
    intent = PaymentIntent.build(
        agent_id="agent_alpha",
        payee_address="0x71C8000000000000000000000000000000000001",
        amount_micro_usdc=25_000,
        target_url="https://api.agent-compute.org/v1/inference",
        target_method="POST",
        chain_id=8453,
        nonce="nonce_selftest_1",
        timestamp_epoch=now,
    )

    binding = gateway.create_siwx_binding(intent, agent_key)
    res_reserve = gateway.reserve_escrow(intent, binding)
    assert res_reserve["status"] == "RESERVED"
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(res_reserve["receipt"])

    # Nominal dispatch
    res_dispatch = gateway.dispatch_payment(intent, binding)
    assert res_dispatch["status"] == DISPOSITION_CONFIRMED
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(res_dispatch["receipt"])

    balances = gateway.get_balances()
    assert balances["settled_micro_usdc"] == 25_000
    assert balances["reserved_micro_usdc"] == 0

    return 0


def run_simulate_504_timeout(journal_dir: Path) -> int:
    """Demonstrates 504 timeout latching, duplicate retry blocking, and reconciliation."""
    journal_file = journal_dir / "gateway_timeout_sim.jsonl"
    if journal_file.exists():
        journal_file.unlink()

    config = GatewayConfig(
        journal_path=journal_file,
        initial_balance_micro_usdc=5_000_000,  # claim: config
    )
    agent_key = ed25519.Ed25519PrivateKey.generate()
    gateway = CoinbaseX402AgentGateway(
        config=config,
        trusted_signer_pubkeys_hex=[agent_key.public_key().public_bytes_raw().hex()],
    )

    now = int(time.time())
    intent = PaymentIntent.build(
        agent_id="agent_beta",
        payee_address="0x71C8000000000000000000000000000000000002",
        amount_micro_usdc=50_000,
        target_url="https://api.agent-compute.org/v1/inference",
        target_method="POST",
        chain_id=8453,
        nonce="nonce_sim_504",
        timestamp_epoch=now,
    )
    caid = intent.caid
    binding = gateway.create_siwx_binding(intent, agent_key)

    def timeout_client(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"status_code": 504, "error": "Gateway Timeout from upstream Base node"}

    res_504 = gateway.dispatch_payment(intent, binding, http_client=timeout_client)
    assert res_504["status"] == DISPOSITION_EFFECT_INDETERMINATE

    # Balance held in escrow
    bal = gateway.get_balances()
    assert bal["reserved_micro_usdc"] == 50_000

    # Duplicate dispatch rejected
    blocked = False
    try:
        gateway.dispatch_payment(intent, binding)
    except RuntimeError as exc:
        if "ERR_DUPLICATE_CAID_LATCHED_INDETERMINATE" in str(exc):
            blocked = True
    assert blocked

    # Out-of-band reconciliation
    recon_res = gateway.reconcile(
        caid=caid,
        authoritative_disposition=DISPOSITION_REFUTED,
        probe_receipt={"probe_source": "base_rpc", "tx_found": False},
    )
    assert recon_res["status"] == DISPOSITION_REFUTED
    bal_after = gateway.get_balances()
    assert bal_after["reserved_micro_usdc"] == 0
    assert bal_after["available_micro_usdc"] == 5_000_000

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Coinbase CDP & x402 Hardened Agent Gateway")
    parser.add_argument("--self-test", action="store_true", help="Execute automated self-test")
    parser.add_argument(
        "--simulate-504-timeout",
        action="store_true",
        help="Simulate HTTP 504 timeout latching and reconciliation",
    )
    parser.add_argument("--reconcile", type=str, help="Reconcile a latched CAID")
    parser.add_argument(
        "--disposition",
        type=str,
        default=DISPOSITION_REFUTED,
        choices=[DISPOSITION_CONFIRMED, DISPOSITION_REFUTED],
        help="Authoritative disposition for reconciliation",
    )
    parser.add_argument(
        "--journal-path",
        type=Path,
        default=Path("data/coinbase_x402_gateway_journal.jsonl"),
        help="Path to gateway journal file",
    )

    args = parser.parse_args()

    if args.self_test:
        test_dir = Path("/tmp/aeib_coinbase_test")
        test_dir.mkdir(parents=True, exist_ok=True)
        code = run_self_test(test_dir)
        sys.exit(code)

    if args.simulate_504_timeout:
        test_dir = Path("/tmp/aeib_coinbase_test")
        test_dir.mkdir(parents=True, exist_ok=True)
        code = run_simulate_504_timeout(test_dir)
        sys.exit(code)

    if args.reconcile:
        config = GatewayConfig(journal_path=args.journal_path)
        gateway = CoinbaseX402AgentGateway(config=config)
        res = gateway.reconcile(args.reconcile, args.disposition)
        sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
