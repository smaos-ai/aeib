#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
src/eo1_effect_key.py
================================================================================
Schema-declared effect keys for the EO1 pre-dispatch interlock (prototype).

Problem (evaluated in benchmarks/eo1_real_duplicate_benchmark.py, fault F8):
``src.eo1_write_before_execute.compute_caid`` hashes the RFC 8785 JCS bytes of the
*entire* tool-call payload. ACRFence (arXiv:2603.20625) describes how, after a crash /
restore, an LLM agent re-generates a semantically identical tool call whose incidental
fields differ (memo wording, a fresh client request UUID, a timestamp, reordered optional
list items). Such a retry gets a new full-payload CAID and is not stopped by the latch.

This module derives the CAID from a per-tool ``EffectKeySchema`` instead:

  * ``identity_fields`` are declared JSON paths that define the effect (e.g. recipient
    account, ``amount_minor`` + currency, business reference). Every other field is
    treated as incidental and does not enter the key.
  * each identity field names a normalizer (NFC, casefold+NFC, integer minor units,
    ISO 4217 currency, IBAN whitespace removal + mod-97 check). Normalizers fail closed
    on values they cannot interpret (floats for money, malformed IBANs, nested objects).
  * ``effect_class`` is one of idempotent / reversible / compensable / irreversible.
    The taxonomy is taken from arXiv:2604.23283; here it is declared metadata and is
    reported, it does not relax the latch on its own.

Fail-closed rules (as configured, evaluated in tests/test_eo1_effect_key.py):
  * tool without a schema -> ``UnknownToolSchemaError`` unless the registry was built with
    ``allow_full_payload_fallback=True``; the fallback keys on the full payload inside a
    separate domain tag, so it can never equal an effect key.
  * declared identity field missing, ``None``, or not normalizable -> refused.

Interlock binding: ``PreDispatchIntentInterlock.dispatch`` computes
``compute_caid(payload)`` over whatever ``payload`` it is given. ``resolve_dispatch_key``
therefore returns ``interlock_payload`` = the effect-key preimage; passing it as the
interlock ``payload`` (and sending the raw tool call from ``dispatch_fn``) makes the
interlock's CAID equal ``compute_effect_caid``. The ledger's ``payload_digest`` then
binds the effect identity, not the raw request bytes. ``bind_effect_key`` returns an
``EffectKeyBinding`` that carries both the effect CAID and ``raw_payload_digest`` =
sha256(JCS(raw arguments)); callers that need to audit the exact request bytes store the
latter next to the former (adapters/mcp/idempotent_mcp_proxy.py does this).

Domain separation: the preimage is the JCS object
``{"domain", "schema_id", "schema_version", "schema_digest", "tool", "identity"}``. The
interlock's public API hashes ``JCS(payload)`` with no byte prefix, so separation is by
the ``domain`` member inside the canonical object. A raw payload dispatched directly
(without this module) to the same ledger could only collide with an effect key if it
reproduced that exact object; keep one keying mode per ledger.

Limits (stated, not hidden):
  * the key is only as good as the declared identity fields. If a regenerated retry also
    changes the business reference, the effect key splits (a duplicate is possible); two
    distinct intended effects with identical identity fields are merged (the second one is
    refused). tests/data/effect_key_pairs.json is a hand-written labelled set, not field
    data.
  * MCP tool annotations are untrusted hints. ``idempotentHint`` is reported; it removes
    the latch only when the caller opts in (``honor_idempotent_hint=True``) AND the schema
    declares ``effect_class=idempotent``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

from src.eo1_write_before_execute import compute_caid  # noqa: E402
from src.jcs_canonicalizer import encode_jcs  # noqa: E402

EFFECT_KEY_DOMAIN = "aeib.eo1.effect_key.v1"
FULL_PAYLOAD_DOMAIN = "aeib.eo1.full_payload_fallback.v1"
SCHEMA_DIGEST_DOMAIN = "aeib.eo1.effect_key_schema.v1"
EFFECT_CLASS_TAXONOMY_SOURCE = "arXiv:2604.23283"
REGENERATED_RETRY_SOURCE = "arXiv:2603.20625"

MAX_SAFE_INTEGER = 2 ** 53 - 1  # I-JSON (RFC 7493) interoperable integer range
MAX_IDENTIFIER_CHARS = 1024

KEY_MODE_EFFECT = "EFFECT_KEY"
KEY_MODE_FULL_PAYLOAD = "FULL_PAYLOAD_FALLBACK"


class EffectClass(str, Enum):
    """Effect taxonomy (source: arXiv:2604.23283). Declared per tool; reported, never trusted to relax a latch alone."""
    IDEMPOTENT = "idempotent"
    REVERSIBLE = "reversible"
    COMPENSABLE = "compensable"
    IRREVERSIBLE = "irreversible"


class EffectKeyError(ValueError):
    """Base class: the effect key could not be derived; the caller must not dispatch."""


class UnknownToolSchemaError(EffectKeyError):
    """No EffectKeySchema is registered for the tool and full-payload fallback is not enabled."""


class MissingIdentityFieldError(EffectKeyError):
    """A declared identity field is absent or null in the payload."""


class InvalidIdentityValueError(EffectKeyError):
    """A declared identity field holds a value its normalizer refuses."""


class SchemaDefinitionError(EffectKeyError):
    """An EffectKeySchema or registry definition is malformed."""


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

_DIGITS_RE = re.compile(r"^[+-]?[0-9]+$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$")
_IBAN_WHITESPACE_RE = re.compile(r"\s+")


def _require_text(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise InvalidIdentityValueError(f"identity field {path!r} must be a string, got {type(value).__name__}")
    return value


def _bounded(text: str, path: str) -> str:
    if not text:
        raise InvalidIdentityValueError(f"identity field {path!r} is empty after normalization")
    if len(text) > MAX_IDENTIFIER_CHARS:
        raise InvalidIdentityValueError(f"identity field {path!r} exceeds {MAX_IDENTIFIER_CHARS} characters")
    return text


def normalize_exact_nfc(value: Any, path: str) -> str:
    """Case-preserving identifier: NFC + strip surrounding whitespace (business references)."""
    return _bounded(unicodedata.normalize("NFC", _require_text(value, path)).strip(), path)


def normalize_casefold_nfc(value: Any, path: str) -> str:
    """Case-insensitive identifier (e-mail, handle, project key): NFC(casefold(NFC(s))) + strip."""
    text = unicodedata.normalize("NFC", _require_text(value, path)).strip()
    return _bounded(unicodedata.normalize("NFC", text.casefold()), path)


def normalize_minor_units(value: Any, path: str) -> int:
    """Integer minor units (cents). Floats, bools and decimal strings are refused; |x| <= 2**53-1."""
    if isinstance(value, bool):
        raise InvalidIdentityValueError(f"identity field {path!r} must be integer minor units, got bool")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and _DIGITS_RE.match(value.strip()):
        number = int(value.strip())
    else:
        raise InvalidIdentityValueError(
            f"identity field {path!r} must be integer minor units (int or digit string), got {value!r}"
        )
    if abs(number) > MAX_SAFE_INTEGER:
        raise InvalidIdentityValueError(f"identity field {path!r} is outside the I-JSON safe integer range")
    return number


def normalize_currency(value: Any, path: str) -> str:
    """ISO 4217 alphabetic code: strip + upper, must be three ASCII letters."""
    code = _require_text(value, path).strip().upper()
    if not _CURRENCY_RE.match(code):
        raise InvalidIdentityValueError(f"identity field {path!r} is not a 3-letter currency code: {value!r}")
    return code


def iban_checksum_valid(iban: str) -> bool:
    """ISO 13616 mod-97 check over an already compact, upper-case IBAN."""
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(digits) % 97 == 1


def normalize_iban(value: Any, path: str) -> str:
    """IBAN: remove all whitespace, upper-case, structural check and mod-97 check."""
    compact = _IBAN_WHITESPACE_RE.sub("", _require_text(value, path)).upper()
    if not _IBAN_RE.match(compact) or not iban_checksum_valid(compact):
        raise InvalidIdentityValueError(f"identity field {path!r} is not a valid IBAN")
    return compact


def normalize_boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidIdentityValueError(f"identity field {path!r} must be a JSON boolean, got {type(value).__name__}")
    return value


NORMALIZERS: Mapping[str, Callable[[Any, str], Any]] = {
    "exact_nfc": normalize_exact_nfc,
    "casefold_nfc": normalize_casefold_nfc,
    "minor_units": normalize_minor_units,
    "currency_iso4217": normalize_currency,
    "iban": normalize_iban,
    "boolean": normalize_boolean,
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentityField:
    """A dot-separated JSON object path (no array indexing) plus the normalizer applied to its value."""
    path: str
    normalizer: str = "exact_nfc"

    def segments(self) -> Tuple[str, ...]:
        return tuple(self.path.split("."))

    def descriptor(self) -> Dict[str, str]:
        return {"normalizer": self.normalizer, "path": self.path}


@dataclass(frozen=True)
class EffectKeySchema:
    tool: str
    schema_id: str
    schema_version: str
    identity_fields: Tuple[IdentityField, ...]
    effect_class: EffectClass

    def __post_init__(self) -> None:
        for name in ("tool", "schema_id", "schema_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise SchemaDefinitionError(f"EffectKeySchema.{name} must be a non-empty string")
        if not isinstance(self.effect_class, EffectClass):
            raise SchemaDefinitionError("EffectKeySchema.effect_class must be an EffectClass")
        fields = tuple(self.identity_fields)
        if not fields:
            raise SchemaDefinitionError(f"schema {self.schema_id!r} declares no identity fields")
        seen = set()
        for f in fields:
            if not isinstance(f, IdentityField):
                raise SchemaDefinitionError("identity_fields must contain IdentityField instances")
            if not f.path or any(not seg for seg in f.segments()):
                raise SchemaDefinitionError(f"identity field path {f.path!r} has an empty segment")
            if f.normalizer not in NORMALIZERS:
                raise SchemaDefinitionError(f"unknown normalizer {f.normalizer!r} for {f.path!r}")
            if f.path in seen:
                raise SchemaDefinitionError(f"identity field {f.path!r} declared twice")
            seen.add(f.path)
        object.__setattr__(self, "identity_fields", fields)

    def descriptor(self) -> Dict[str, Any]:
        """Order-insensitive canonical description; any change to it changes ``digest()`` and every key."""
        return {
            "domain": SCHEMA_DIGEST_DOMAIN,
            "effect_class": self.effect_class.value,
            "identity_fields": sorted((f.descriptor() for f in self.identity_fields), key=lambda d: d["path"]),
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "tool": self.tool,
        }

    def digest(self) -> str:
        return hashlib.sha256(encode_jcs(self.descriptor())).hexdigest()

    @classmethod
    def from_dict(cls, doc: Mapping[str, Any]) -> "EffectKeySchema":
        try:
            fields = tuple(IdentityField(path=f["path"], normalizer=f.get("normalizer", "exact_nfc"))
                           for f in doc["identity_fields"])
            return cls(tool=doc["tool"], schema_id=doc["schema_id"], schema_version=doc["schema_version"],
                       identity_fields=fields, effect_class=EffectClass(doc["effect_class"]))
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, SchemaDefinitionError):
                raise
            raise SchemaDefinitionError(f"malformed schema document: {exc}") from exc


class EffectKeySchemaRegistry:
    """Tool name -> EffectKeySchema. Re-registering a tool is refused (no silent override)."""

    def __init__(self, schemas: Iterable[EffectKeySchema] = (), allow_full_payload_fallback: bool = False):
        self._schemas: Dict[str, EffectKeySchema] = {}
        self.allow_full_payload_fallback = bool(allow_full_payload_fallback)
        for schema in schemas:
            self.register(schema)

    def register(self, schema: EffectKeySchema) -> None:
        if not isinstance(schema, EffectKeySchema):
            raise SchemaDefinitionError("register() expects an EffectKeySchema")
        if schema.tool in self._schemas:
            raise SchemaDefinitionError(f"tool {schema.tool!r} already has schema {self._schemas[schema.tool].schema_id!r}")
        self._schemas[schema.tool] = schema

    def get(self, tool: str) -> Optional[EffectKeySchema]:
        return self._schemas.get(tool)

    def tools(self) -> List[str]:
        return sorted(self._schemas)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def _lookup(payload: Any, f: IdentityField, tool: str) -> Any:
    node = payload
    for seg in f.segments():
        if not isinstance(node, dict) or seg not in node:
            raise MissingIdentityFieldError(f"tool {tool!r}: identity field {f.path!r} is missing")
        node = node[seg]
    if node is None:
        raise MissingIdentityFieldError(f"tool {tool!r}: identity field {f.path!r} is null")
    if isinstance(node, (dict, list, float)):
        raise InvalidIdentityValueError(
            f"tool {tool!r}: identity field {f.path!r} must be a scalar string/int/bool, got {type(node).__name__}"
        )
    return node


def normalized_identity(schema: EffectKeySchema, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidIdentityValueError(f"tool {schema.tool!r}: payload must be a JSON object")
    return {f.path: NORMALIZERS[f.normalizer](_lookup(payload, f, schema.tool), f.path) for f in schema.identity_fields}


def effect_key_preimage(tool: str, payload: Any, registry: EffectKeySchemaRegistry) -> Dict[str, Any]:
    """The JCS object whose SHA-256 is the effect CAID. Raises UnknownToolSchemaError when no schema exists."""
    schema = registry.get(tool)
    if schema is None:
        raise UnknownToolSchemaError(f"no EffectKeySchema registered for tool {tool!r}; refusing to derive a key")
    return {
        "domain": EFFECT_KEY_DOMAIN,
        "identity": normalized_identity(schema, payload),
        "schema_digest": schema.digest(),
        "schema_id": schema.schema_id,
        "schema_version": schema.schema_version,
        "tool": tool,
    }


def compute_effect_caid(tool: str, payload: Any, schema_registry: EffectKeySchemaRegistry) -> str:
    """sha256(JCS(effect_key_preimage)). Equals compute_caid(preimage), i.e. what the interlock computes."""
    return hashlib.sha256(encode_jcs(effect_key_preimage(tool, payload, schema_registry))).hexdigest()


def full_payload_fallback_preimage(tool: str, payload: Any) -> Dict[str, Any]:
    return {"domain": FULL_PAYLOAD_DOMAIN, "payload": payload, "tool": tool}


@dataclass(frozen=True)
class McpHintReport:
    """MCP tool annotations as observed. Values that are not JSON booleans are recorded as None (absent)."""
    idempotent_hint: Optional[bool] = None
    destructive_hint: Optional[bool] = None
    read_only_hint: Optional[bool] = None
    open_world_hint: Optional[bool] = None

    @classmethod
    def from_annotations(cls, annotations: Optional[Mapping[str, Any]]) -> "McpHintReport":
        if not isinstance(annotations, Mapping):
            return cls()

        def _b(name: str) -> Optional[bool]:
            value = annotations.get(name)
            return value if isinstance(value, bool) else None

        return cls(_b("idempotentHint"), _b("destructiveHint"), _b("readOnlyHint"), _b("openWorldHint"))


@dataclass(frozen=True)
class EffectKeyResolution:
    caid: str
    interlock_payload: Dict[str, Any]
    key_mode: str
    tool: str
    schema_id: Optional[str]
    schema_digest: Optional[str]
    effect_class: Optional[EffectClass]
    latch_required: bool
    hints: McpHintReport = field(default_factory=McpHintReport)
    notes: Tuple[str, ...] = ()


def resolve_dispatch_key(
    tool: str,
    payload: Any,
    registry: EffectKeySchemaRegistry,
    annotations: Optional[Mapping[str, Any]] = None,
    honor_idempotent_hint: bool = False,
) -> EffectKeyResolution:
    """
    Resolves the CAID and the payload to hand to PreDispatchIntentInterlock.

    ``latch_required`` is False only when honor_idempotent_hint is True, the MCP annotation
    ``idempotentHint`` is the JSON boolean true, and the schema declares effect_class idempotent.
    Every other combination (including the fallback path) keeps the latch.
    """
    hints = McpHintReport.from_annotations(annotations)
    schema = registry.get(tool)
    if schema is None:
        if not registry.allow_full_payload_fallback:
            raise UnknownToolSchemaError(f"no EffectKeySchema registered for tool {tool!r}; refusing to derive a key")
        preimage = full_payload_fallback_preimage(tool, payload)
        return EffectKeyResolution(
            caid=compute_caid(preimage), interlock_payload=preimage, key_mode=KEY_MODE_FULL_PAYLOAD, tool=tool,
            schema_id=None, schema_digest=None, effect_class=None, latch_required=True, hints=hints,
            notes=("no schema: full-payload fallback (regenerated retries are not merged)",),
        )
    preimage = effect_key_preimage(tool, payload, registry)
    notes: List[str] = []
    latch_required = True
    if hints.idempotent_hint is True:
        if honor_idempotent_hint and schema.effect_class is EffectClass.IDEMPOTENT:
            latch_required = False
            notes.append("idempotentHint honoured: caller opted in and schema declares idempotent")
        else:
            notes.append("idempotentHint observed and reported only (untrusted hint); latch kept")
    return EffectKeyResolution(
        caid=compute_caid(preimage), interlock_payload=preimage, key_mode=KEY_MODE_EFFECT, tool=tool,
        schema_id=schema.schema_id, schema_digest=preimage["schema_digest"], effect_class=schema.effect_class,
        latch_required=latch_required, hints=hints, notes=tuple(notes),
    )


# Alias used by callers that name the registry by role rather than content.
EffectKeyRegistry = EffectKeySchemaRegistry


def raw_payload_digest(payload: Mapping[str, Any]) -> str:
    """sha256 over the RFC 8785 JCS bytes of the full raw tool-call arguments (audit binding, not identity)."""
    if not isinstance(payload, Mapping):
        raise InvalidIdentityValueError("raw payload must be a JSON object")
    return hashlib.sha256(encode_jcs(dict(payload))).hexdigest()


@dataclass(frozen=True)
class EffectKeyBinding:
    """
    Pairs the effect CAID (identity: merges regenerated retries) with the digest of the exact raw
    arguments that were presented (audit: differs between regenerated retries). Storing both lets
    an auditor check the raw request bytes while the latch keys on the effect.
    """
    effect_caid: str
    preimage: Dict[str, Any]
    raw_payload_digest: str
    effect_class: Optional[EffectClass]
    hint_observation: McpHintReport
    latch_required: bool
    key_mode: str
    schema_id: Optional[str]
    schema_digest: Optional[str]


def bind_effect_key(
    tool: str,
    payload: Mapping[str, Any],
    registry: EffectKeySchemaRegistry,
    annotations: Optional[Mapping[str, Any]] = None,
    honor_idempotent_hint: bool = False,
) -> EffectKeyBinding:
    """Resolves the effect CAID (same rules as resolve_dispatch_key) and binds the raw-argument digest."""
    if not isinstance(payload, Mapping):
        raise InvalidIdentityValueError(f"tool {tool!r}: payload must be a JSON object")
    resolution = resolve_dispatch_key(tool, dict(payload), registry, annotations=annotations,
                                      honor_idempotent_hint=honor_idempotent_hint)
    return EffectKeyBinding(
        effect_caid=resolution.caid,
        preimage=resolution.interlock_payload,
        raw_payload_digest=raw_payload_digest(payload),
        effect_class=resolution.effect_class,
        hint_observation=resolution.hints,
        latch_required=resolution.latch_required,
        key_mode=resolution.key_mode,
        schema_id=resolution.schema_id,
        schema_digest=resolution.schema_digest,
    )


# ---------------------------------------------------------------------------
# Labelled-pair evaluation (false splits / false merges)
# ---------------------------------------------------------------------------

LABEL_SAME = "same_effect"
LABEL_DIFFERENT = "different_effect"


def _full_payload_key(tool: str, payload: Any) -> str:
    return compute_caid(payload)


def evaluate_pairs(pairs: Sequence[Mapping[str, Any]], registry: EffectKeySchemaRegistry) -> Dict[str, Any]:
    """
    Confusion counts for the current full-payload CAID and for the effect-key CAID.
    false_split = same effect, different key; false_merge = different effects, same key.
    A pair where the effect key refuses either side is counted under ``refused`` (fail closed).
    """
    keyers: Dict[str, Callable[[str, Any], str]] = {
        "full_payload_caid": _full_payload_key,
        "effect_key_caid": lambda tool, p: compute_effect_caid(tool, p, registry),
    }
    out: Dict[str, Any] = {"pairs": len(pairs), "labels": {LABEL_SAME: 0, LABEL_DIFFERENT: 0}}
    for pair in pairs:
        if pair["label"] not in (LABEL_SAME, LABEL_DIFFERENT):
            raise ValueError(f"pair {pair.get('id')!r} has unknown label {pair['label']!r}")
        out["labels"][pair["label"]] += 1
    for name, keyer in keyers.items():
        counts = {"same_key_same_effect": 0, "false_split": 0, "false_merge": 0,
                  "diff_key_diff_effect": 0, "refused": 0}
        details: List[Dict[str, str]] = []
        for pair in pairs:
            try:
                same_key = keyer(pair["tool"], pair["a"]) == keyer(pair["tool"], pair["b"])
            except EffectKeyError as exc:
                counts["refused"] += 1
                details.append({"id": pair["id"], "result": "refused", "reason": type(exc).__name__})
                continue
            if pair["label"] == LABEL_SAME:
                cell = "same_key_same_effect" if same_key else "false_split"
            else:
                cell = "false_merge" if same_key else "diff_key_diff_effect"
            counts[cell] += 1
            if cell in ("false_split", "false_merge"):
                details.append({"id": pair["id"], "result": cell})
        out[name] = {"counts": counts, "errors": details}
    return out


def load_pairs_file(path: Path) -> Tuple[EffectKeySchemaRegistry, List[Dict[str, Any]]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    registry = EffectKeySchemaRegistry(EffectKeySchema.from_dict(s) for s in doc["schemas"])
    return registry, list(doc["pairs"])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate full-payload vs effect-key CAID on labelled pairs.")
    ap.add_argument("--pairs", default=str(ROOT / "tests" / "data" / "effect_key_pairs.json"))
    args = ap.parse_args(argv)
    registry, pairs = load_pairs_file(Path(args.pairs))
    report = evaluate_pairs(pairs, registry)
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
