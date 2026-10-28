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
tests/test_eo1_effect_key.py
================================================================================
Evaluates src/eo1_effect_key.py (no mocks):

  - normalizers accept / refuse at their boundaries (fail closed);
  - schema validation, schema digest sensitivity, registry refusal of re-registration;
  - effect CAID merges regenerated retries and splits distinct effects;
  - unknown tool / missing identity field refuse; full-payload fallback only when enabled;
  - MCP idempotentHint is reported, and relaxes the latch only on explicit opt-in;
  - binding to the REAL PreDispatchIntentInterlock: a regenerated retry after a real wire
    fault (connection refused on a closed loopback port) is refused under the effect key and
    is NOT refused under the full-payload CAID;
  - red-team: confusable characters, oversize identifiers, out-of-range integers, a fallback
    payload that mimics an effect-key preimage, canonicalization of IBAN / currency / NFD;
  - the hand-written labelled pair file: zero false merges for the effect key.
"""

from __future__ import annotations

import copy
import hashlib
import json
import socket
import sys
import unicodedata
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import eo1_effect_key as ek  # noqa: E402
from src.eo1_effect_key import (  # noqa: E402
    EFFECT_KEY_DOMAIN,
    FULL_PAYLOAD_DOMAIN,
    KEY_MODE_EFFECT,
    KEY_MODE_FULL_PAYLOAD,
    MAX_IDENTIFIER_CHARS,
    MAX_SAFE_INTEGER,
    EffectClass,
    EffectKeyError,
    EffectKeySchema,
    EffectKeySchemaRegistry,
    IdentityField,
    InvalidIdentityValueError,
    McpHintReport,
    MissingIdentityFieldError,
    SchemaDefinitionError,
    UnknownToolSchemaError,
    compute_effect_caid,
    effect_key_preimage,
    evaluate_pairs,
    full_payload_fallback_preimage,
    iban_checksum_valid,
    load_pairs_file,
    normalize_boolean,
    normalize_casefold_nfc,
    normalize_currency,
    normalize_exact_nfc,
    normalize_iban,
    normalize_minor_units,
    resolve_dispatch_key,
)
from src.eo1_write_before_execute import (  # noqa: E402
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
)

PAIRS_PATH = ROOT / "tests" / "data" / "effect_key_pairs.json"
TOOL = "payments.sepa_transfer"


def pay_schema(version: str = "1", effect_class: EffectClass = EffectClass.IRREVERSIBLE,
               tool: str = TOOL) -> EffectKeySchema:
    return EffectKeySchema(
        tool=tool, schema_id=f"{tool}.effect", schema_version=version, effect_class=effect_class,
        identity_fields=(
            IdentityField("creditor.iban", "iban"),
            IdentityField("amount_minor", "minor_units"),
            IdentityField("currency", "currency_iso4217"),
            IdentityField("end_to_end_id", "exact_nfc"),
        ),
    )


BASE = {
    "creditor": {"iban": "DE89 3704 0044 0532 0130 00", "name": "Acme GmbH"},
    "amount_minor": 125000,
    "currency": "EUR",
    "end_to_end_id": "INV-2026-0042",
    "remittance_info": "Invoice 2026-0042",
    "client_request_id": "0b6f6c4e-5d1a-4f0e-9a51-2f0e7c9d1a11",
    "labels": ["ap", "q4"],
}


def regenerated(payload):
    out = copy.deepcopy(payload)
    out["remittance_info"] = "Payment for invoice 2026-0042 (resent)"
    out["client_request_id"] = "5a4b3c2d-1e0f-4a9b-8c7d-6e5f4a3b2c1d"
    out["labels"] = list(reversed(out["labels"]))
    return out


@pytest.fixture
def registry():
    return EffectKeySchemaRegistry([pay_schema()])


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def test_exact_nfc_strips_and_composes_but_keeps_case():
    assert normalize_exact_nfc("  INV-1 ", "p") == "INV-1"
    assert normalize_exact_nfc(unicodedata.normalize("NFD", "caf\u00e9"), "p") == "caf\u00e9"
    assert normalize_exact_nfc("Inv-1", "p") != normalize_exact_nfc("inv-1", "p")


@pytest.mark.parametrize("bad", [None, 7, 1.5, b"x", ["a"]])
def test_text_normalizers_refuse_non_strings(bad):
    for fn in (normalize_exact_nfc, normalize_casefold_nfc, normalize_currency, normalize_iban):
        with pytest.raises(InvalidIdentityValueError):
            fn(bad, "p")


def test_identifier_length_bounds():
    assert MAX_IDENTIFIER_CHARS == 1024
    assert normalize_exact_nfc("b" * 1024, "p") == "b" * 1024
    with pytest.raises(InvalidIdentityValueError):
        normalize_exact_nfc("b" * 1025, "p")
    assert normalize_exact_nfc("a" * MAX_IDENTIFIER_CHARS, "p") == "a" * MAX_IDENTIFIER_CHARS
    with pytest.raises(InvalidIdentityValueError):
        normalize_exact_nfc("a" * (MAX_IDENTIFIER_CHARS + 1), "p")
    with pytest.raises(InvalidIdentityValueError):
        normalize_casefold_nfc("A" * (MAX_IDENTIFIER_CHARS + 1), "p")
    for blank in ("", "   "):
        with pytest.raises(InvalidIdentityValueError):
            normalize_exact_nfc(blank, "p")
        with pytest.raises(InvalidIdentityValueError):
            normalize_casefold_nfc(blank, "p")


def test_casefold_nfc():
    assert normalize_casefold_nfc(" Jane.Doe@Example.COM ", "p") == "jane.doe@example.com"
    assert normalize_casefold_nfc("Stra\u00dfe", "p") == "strasse"
    nfd = unicodedata.normalize("NFD", "JOS\u00c9")
    assert normalize_casefold_nfc(nfd, "p") == "jos\u00e9"
    assert unicodedata.is_normalized("NFC", normalize_casefold_nfc(nfd, "p"))


def test_minor_units_accepts_ints_and_digit_strings():
    assert MAX_SAFE_INTEGER == 9007199254740991
    assert normalize_minor_units(9007199254740991, "p") == 9007199254740991
    assert normalize_minor_units(-9007199254740991, "p") == -9007199254740991
    for over in (9007199254740992, -9007199254740992, "9007199254740992"):
        with pytest.raises(InvalidIdentityValueError):
            normalize_minor_units(over, "p")
    assert normalize_minor_units(125000, "p") == 125000
    assert normalize_minor_units("125000", "p") == 125000
    assert normalize_minor_units(" 42 ", "p") == 42
    assert normalize_minor_units("+5", "p") == 5
    assert normalize_minor_units("-5", "p") == -5
    assert normalize_minor_units(0, "p") == 0
    assert normalize_minor_units(MAX_SAFE_INTEGER, "p") == MAX_SAFE_INTEGER
    assert normalize_minor_units(-MAX_SAFE_INTEGER, "p") == -MAX_SAFE_INTEGER


@pytest.mark.parametrize("bad", [12.5, 1250.0, True, False, "12.50", "1e3", "", "abc", None, [1],
                                 MAX_SAFE_INTEGER + 1, -(MAX_SAFE_INTEGER + 1), str(MAX_SAFE_INTEGER + 1)])
def test_minor_units_refuses(bad):
    with pytest.raises(InvalidIdentityValueError):
        normalize_minor_units(bad, "p")


def test_currency():
    assert normalize_currency(" eur ", "p") == "EUR"
    assert normalize_currency("usd", "p") == "USD"
    for bad in ("EU", "EURO", "E1R", "", "\u20ac\u20ac\u20ac"):
        with pytest.raises(InvalidIdentityValueError):
            normalize_currency(bad, "p")


def test_iban():
    assert normalize_iban("DE89 3704 0044 0532 0130 00", "p") == "DE89370400440532013000"
    assert normalize_iban("de89\t3704 0044\n0532 0130 00", "p") == "DE89370400440532013000"
    assert normalize_iban("GB82 WEST 1234 5698 7654 32", "p") == "GB82WEST12345698765432"
    assert iban_checksum_valid("DE89370400440532013000")
    assert not iban_checksum_valid("DE89370400440532013001")
    for bad in ("DE89 3704 0044 0532 0130 01", "DE89", "1289370400440532013000", "DE8937040044053201300!",
                "DEXX370400440532013000", "DE89" + "1" * 31):
        with pytest.raises(InvalidIdentityValueError):
            normalize_iban(bad, "p")


def test_boolean():
    assert normalize_boolean(True, "p") is True
    assert normalize_boolean(False, "p") is False
    for bad in (1, 0, "true", None):
        with pytest.raises(InvalidIdentityValueError):
            normalize_boolean(bad, "p")


def test_normalizer_errors_are_effect_key_errors():
    assert issubclass(InvalidIdentityValueError, EffectKeyError)
    assert issubclass(MissingIdentityFieldError, EffectKeyError)
    assert issubclass(UnknownToolSchemaError, EffectKeyError)
    assert issubclass(SchemaDefinitionError, EffectKeyError)
    assert issubclass(EffectKeyError, ValueError)


# ---------------------------------------------------------------------------
# Schemas and registry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kwargs", [
    {"identity_fields": ()},
    {"identity_fields": (IdentityField("a"), IdentityField("a"))},
    {"identity_fields": (IdentityField("a", "no_such_normalizer"),)},
    {"identity_fields": (IdentityField("a..b"),)},
    {"identity_fields": (IdentityField(".a"),)},
    {"identity_fields": (IdentityField(""),)},
    {"identity_fields": ("a",)},
    {"tool": "  "},
    {"schema_id": ""},
    {"schema_version": ""},
    {"tool": 5},
    {"effect_class": "irreversible"},
])
def test_schema_definition_refused(kwargs):
    base = dict(tool="t", schema_id="s", schema_version="1", identity_fields=(IdentityField("a"),),
                effect_class=EffectClass.IRREVERSIBLE)
    base.update(kwargs)
    with pytest.raises(SchemaDefinitionError):
        EffectKeySchema(**base)


def test_schema_digest_sensitivity():
    d = pay_schema().digest()
    assert d == pay_schema().digest()
    assert len(d) == 64
    assert pay_schema(version="2").digest() != d
    assert pay_schema(effect_class=EffectClass.COMPENSABLE).digest() != d
    assert pay_schema(tool="other.tool").digest() != d
    changed_norm = EffectKeySchema(
        tool=TOOL, schema_id=f"{TOOL}.effect", schema_version="1", effect_class=EffectClass.IRREVERSIBLE,
        identity_fields=(IdentityField("creditor.iban", "exact_nfc"), IdentityField("amount_minor", "minor_units"),
                         IdentityField("currency", "currency_iso4217"), IdentityField("end_to_end_id", "exact_nfc")))
    assert changed_norm.digest() != d
    reordered = EffectKeySchema(
        tool=TOOL, schema_id=f"{TOOL}.effect", schema_version="1", effect_class=EffectClass.IRREVERSIBLE,
        identity_fields=tuple(reversed(pay_schema().identity_fields)))
    assert reordered.digest() == d
    assert pay_schema().descriptor()["domain"] == ek.SCHEMA_DIGEST_DOMAIN


def test_schema_from_dict_roundtrip_and_refusals():
    doc = {"tool": TOOL, "schema_id": f"{TOOL}.effect", "schema_version": "1", "effect_class": "irreversible",
           "identity_fields": [{"path": f.path, "normalizer": f.normalizer} for f in pay_schema().identity_fields]}
    assert EffectKeySchema.from_dict(doc).digest() == pay_schema().digest()
    defaulted = EffectKeySchema.from_dict({**doc, "identity_fields": [{"path": "x"}]})
    assert defaulted.identity_fields[0].normalizer == "exact_nfc"
    for broken in ({**doc, "effect_class": "sometimes"}, {k: v for k, v in doc.items() if k != "tool"},
                   {**doc, "identity_fields": [{"normalizer": "iban"}]}, {**doc, "identity_fields": 5},
                   {**doc, "identity_fields": [{"path": "a", "normalizer": "bogus"}]}):
        with pytest.raises(SchemaDefinitionError):
            EffectKeySchema.from_dict(broken)


def test_schema_objects_are_immutable(registry):
    import dataclasses
    schema = pay_schema()
    with pytest.raises(dataclasses.FrozenInstanceError):
        schema.schema_version = "2"
    with pytest.raises(dataclasses.FrozenInstanceError):
        schema.identity_fields[0].normalizer = "exact_nfc"
    res = resolve_dispatch_key(TOOL, BASE, registry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.latch_required = False
    hints = McpHintReport.from_annotations({"idempotentHint": True})
    with pytest.raises(dataclasses.FrozenInstanceError):
        hints.idempotent_hint = False


def test_registry():
    reg = EffectKeySchemaRegistry([pay_schema()])
    assert reg.get(TOOL) is not None
    assert reg.get("nope") is None
    assert reg.allow_full_payload_fallback is False
    with pytest.raises(SchemaDefinitionError):
        reg.register(pay_schema(version="2"))
    with pytest.raises(SchemaDefinitionError):
        reg.register({"tool": "x"})
    reg.register(pay_schema(tool="a.first"))
    assert reg.tools() == ["a.first", TOOL]


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def test_regenerated_retry_merges_under_effect_key_but_not_full_payload(registry):
    retry = regenerated(BASE)
    assert compute_effect_caid(TOOL, BASE, registry) == compute_effect_caid(TOOL, retry, registry)
    assert compute_caid(BASE) != compute_caid(retry)


@pytest.mark.parametrize("field_path,value", [
    ("amount_minor", 125001), ("currency", "USD"), ("end_to_end_id", "INV-2026-0043"),
    ("creditor.iban", "GB82 WEST 1234 5698 7654 32"),
])
def test_distinct_effects_split(registry, field_path, value):
    other = copy.deepcopy(BASE)
    node = other
    segs = field_path.split(".")
    for seg in segs[:-1]:
        node = node[seg]
    node[segs[-1]] = value
    assert compute_effect_caid(TOOL, BASE, registry) != compute_effect_caid(TOOL, other, registry)


def test_canonicalized_identity_merges(registry):
    variant = copy.deepcopy(BASE)
    variant["creditor"]["iban"] = "de89370400440532013000"
    variant["currency"] = "eur"
    variant["amount_minor"] = "125000"
    variant["end_to_end_id"] = " INV-2026-0042 "
    assert compute_effect_caid(TOOL, BASE, registry) == compute_effect_caid(TOOL, variant, registry)


def test_preimage_structure_and_interlock_binding(registry):
    pre = effect_key_preimage(TOOL, BASE, registry)
    assert pre == {
        "domain": EFFECT_KEY_DOMAIN,
        "identity": {"amount_minor": 125000, "creditor.iban": "DE89370400440532013000", "currency": "EUR",
                     "end_to_end_id": "INV-2026-0042"},
        "schema_digest": pay_schema().digest(),
        "schema_id": f"{TOOL}.effect",
        "schema_version": "1",
        "tool": TOOL,
    }
    caid = compute_effect_caid(TOOL, BASE, registry)
    assert caid == compute_caid(pre)
    from src.jcs_canonicalizer import encode_jcs
    assert caid == hashlib.sha256(encode_jcs(pre)).hexdigest()


def test_schema_change_changes_key():
    v1 = compute_effect_caid(TOOL, BASE, EffectKeySchemaRegistry([pay_schema("1")]))
    v2 = compute_effect_caid(TOOL, BASE, EffectKeySchemaRegistry([pay_schema("2")]))
    cls = compute_effect_caid(TOOL, BASE, EffectKeySchemaRegistry([pay_schema(effect_class=EffectClass.REVERSIBLE)]))
    assert len({v1, v2, cls}) == 3


def test_tool_name_is_bound():
    reg = EffectKeySchemaRegistry([pay_schema(tool="a"), pay_schema(tool="b")])
    assert compute_effect_caid("a", BASE, reg) != compute_effect_caid("b", BASE, reg)


def test_unknown_tool_refused_by_default(registry):
    with pytest.raises(UnknownToolSchemaError):
        compute_effect_caid("unknown.tool", BASE, registry)
    with pytest.raises(UnknownToolSchemaError):
        resolve_dispatch_key("unknown.tool", BASE, registry)


@pytest.mark.parametrize("mutate,exc", [
    (lambda p: p.pop("end_to_end_id"), MissingIdentityFieldError),
    (lambda p: p.__setitem__("end_to_end_id", None), MissingIdentityFieldError),
    (lambda p: p["creditor"].pop("iban"), MissingIdentityFieldError),
    (lambda p: p.__setitem__("creditor", "DE89370400440532013000"), MissingIdentityFieldError),
    (lambda p: p.__setitem__("creditor", None), MissingIdentityFieldError),
    (lambda p: p.__setitem__("end_to_end_id", {"ref": "INV"}), InvalidIdentityValueError),
    (lambda p: p.__setitem__("end_to_end_id", ["INV"]), InvalidIdentityValueError),
    (lambda p: p.__setitem__("amount_minor", 1250.0), InvalidIdentityValueError),
    (lambda p: p.__setitem__("currency", "EURO"), InvalidIdentityValueError),
])
def test_missing_or_invalid_identity_refused(registry, mutate, exc):
    payload = copy.deepcopy(BASE)
    mutate(payload)
    with pytest.raises(exc):
        compute_effect_caid(TOOL, payload, registry)
    with pytest.raises(exc):
        resolve_dispatch_key(TOOL, payload, registry)


@pytest.mark.parametrize("payload", [None, [], "x", 5])
def test_non_object_payload_refused(registry, payload):
    with pytest.raises(InvalidIdentityValueError):
        compute_effect_caid(TOOL, payload, registry)


def test_full_payload_fallback_only_when_enabled():
    reg = EffectKeySchemaRegistry([pay_schema()], allow_full_payload_fallback=True)
    res = resolve_dispatch_key("legacy.tool", BASE, reg)
    assert res.key_mode == KEY_MODE_FULL_PAYLOAD
    assert res.latch_required is True
    assert res.schema_id is None and res.effect_class is None and res.schema_digest is None
    assert res.interlock_payload == {"domain": FULL_PAYLOAD_DOMAIN, "payload": BASE, "tool": "legacy.tool"}
    assert res.caid == compute_caid(full_payload_fallback_preimage("legacy.tool", BASE))
    assert res.caid != compute_caid(BASE)
    assert res.caid != resolve_dispatch_key("legacy.tool", regenerated(BASE), reg).caid
    assert res.notes
    # A tool with a schema still uses the effect key even when fallback is enabled.
    assert resolve_dispatch_key(TOOL, BASE, reg).key_mode == KEY_MODE_EFFECT
    # compute_effect_caid itself never falls back.
    with pytest.raises(UnknownToolSchemaError):
        compute_effect_caid("legacy.tool", BASE, reg)


def test_resolution_fields(registry):
    res = resolve_dispatch_key(TOOL, BASE, registry)
    assert res.key_mode == KEY_MODE_EFFECT
    assert res.caid == compute_effect_caid(TOOL, BASE, registry)
    assert res.interlock_payload == effect_key_preimage(TOOL, BASE, registry)
    assert res.schema_id == f"{TOOL}.effect"
    assert res.schema_digest == pay_schema().digest()
    assert res.effect_class is EffectClass.IRREVERSIBLE
    assert res.latch_required is True
    assert res.hints == McpHintReport()
    assert res.notes == ()
    assert res.tool == TOOL


# ---------------------------------------------------------------------------
# MCP annotations (untrusted hints)
# ---------------------------------------------------------------------------


def test_hint_report_parsing():
    rep = McpHintReport.from_annotations({"idempotentHint": True, "destructiveHint": False,
                                          "readOnlyHint": "yes", "openWorldHint": True})
    assert rep == McpHintReport(idempotent_hint=True, destructive_hint=False, read_only_hint=None,
                                open_world_hint=True)
    assert McpHintReport.from_annotations(None) == McpHintReport()
    assert McpHintReport.from_annotations(["idempotentHint"]) == McpHintReport()


def test_idempotent_hint_reported_but_latch_kept_by_default(registry):
    res = resolve_dispatch_key(TOOL, BASE, registry, annotations={"idempotentHint": True})
    assert res.hints.idempotent_hint is True
    assert res.latch_required is True
    assert any("reported only" in n for n in res.notes)


def test_idempotent_hint_honoured_only_for_declared_idempotent_schema():
    idem = EffectKeySchemaRegistry([pay_schema(effect_class=EffectClass.IDEMPOTENT)])
    irr = EffectKeySchemaRegistry([pay_schema(effect_class=EffectClass.IRREVERSIBLE)])
    hint = {"idempotentHint": True}
    assert resolve_dispatch_key(TOOL, BASE, idem, annotations=hint, honor_idempotent_hint=True).latch_required is False
    assert resolve_dispatch_key(TOOL, BASE, idem, annotations=hint).latch_required is True
    assert resolve_dispatch_key(TOOL, BASE, irr, annotations=hint, honor_idempotent_hint=True).latch_required is True
    assert resolve_dispatch_key(TOOL, BASE, idem, annotations={"idempotentHint": "true"},
                                honor_idempotent_hint=True).latch_required is True
    assert resolve_dispatch_key(TOOL, BASE, idem, annotations={"idempotentHint": False},
                                honor_idempotent_hint=True).latch_required is True
    honoured = resolve_dispatch_key(TOOL, BASE, idem, annotations=hint, honor_idempotent_hint=True)
    assert any("honoured" in n for n in honoured.notes)
    fallback = EffectKeySchemaRegistry([], allow_full_payload_fallback=True)
    assert resolve_dispatch_key("x", BASE, fallback, annotations=hint,
                                honor_idempotent_hint=True).latch_required is True


# ---------------------------------------------------------------------------
# Red-team: canonicalization divergence, oversize input, mimicry
# ---------------------------------------------------------------------------


def test_confusable_business_ref_is_not_merged(registry):
    cyrillic = copy.deepcopy(BASE)
    cyrillic["end_to_end_id"] = "\u0406NV-2026-0042"  # Cyrillic capital I (U+0406), not Latin I
    assert compute_effect_caid(TOOL, BASE, registry) != compute_effect_caid(TOOL, cyrillic, registry)


def test_oversize_identity_refused(registry):
    big = copy.deepcopy(BASE)
    big["end_to_end_id"] = "X" * 100_000
    with pytest.raises(InvalidIdentityValueError):
        compute_effect_caid(TOOL, big, registry)


def test_identity_value_cannot_forge_structure(registry):
    forged = copy.deepcopy(BASE)
    forged["end_to_end_id"] = 'INV-2026-0042","currency":"EUR'
    forged["domain"] = "attacker"
    forged["schema_digest"] = "0" * 64
    assert compute_effect_caid(TOOL, forged, registry) != compute_effect_caid(TOOL, BASE, registry)
    plain = copy.deepcopy(BASE)
    plain["domain"] = "attacker"
    assert compute_effect_caid(TOOL, plain, registry) == compute_effect_caid(TOOL, BASE, registry)


def test_fallback_payload_mimicking_effect_preimage_does_not_collide(registry):
    mimic = effect_key_preimage(TOOL, BASE, registry)
    reg = EffectKeySchemaRegistry([pay_schema()], allow_full_payload_fallback=True)
    res = resolve_dispatch_key(TOOL + ".legacy", mimic, reg)
    assert res.caid != compute_effect_caid(TOOL, BASE, registry)


# ---------------------------------------------------------------------------
# Binding to the real interlock
# ---------------------------------------------------------------------------


def _closed_loopback_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wire_to_closed_port(port: int):
    def send():
        conn = socket.create_connection(("127.0.0.1", port), timeout=1.0)
        conn.close()
        return {"status_code": 200}
    return send


def _interlock(tmp_path: Path, key: Ed25519PrivateKey) -> PreDispatchIntentInterlock:
    return PreDispatchIntentInterlock(
        ledger_path=tmp_path / "eo1_ledger.jsonl", output_state_dir=tmp_path / "state",
        boundary_private_key=key, authority_id="test-effect-key", auto_recover=True,
    )


@pytest.mark.parametrize("keying", ["effect", "full"])
def test_real_interlock_regenerated_retry_after_wire_fault(tmp_path, registry, keying):
    key = Ed25519PrivateKey.generate()
    port = _closed_loopback_port()
    uri = f"http://127.0.0.1:{port}/effect"

    def interlock_payload(p):
        return resolve_dispatch_key(TOOL, p, registry).interlock_payload if keying == "effect" else p

    first = _interlock(tmp_path, key)
    with pytest.raises(RuntimeError) as fault:
        first.dispatch(uri, TOOL, interlock_payload(BASE), dispatch_fn=_wire_to_closed_port(port))
    assert not isinstance(fault.value, LatchedCaidExecutionHaltedError)
    expected_caid = compute_effect_caid(TOOL, BASE, registry) if keying == "effect" else compute_caid(BASE)
    assert expected_caid in first.get_latched_caids()

    restarted = _interlock(tmp_path, key)  # crash / restore: new process state over the same ledger
    sent = []

    def record_send():
        sent.append(1)
        return {"status_code": 200}

    retry = regenerated(BASE)
    if keying == "effect":
        with pytest.raises(LatchedCaidExecutionHaltedError):
            restarted.dispatch(uri, TOOL, interlock_payload(retry), dispatch_fn=record_send)
        assert sent == []
    else:
        result = restarted.dispatch(uri, TOOL, interlock_payload(retry), dispatch_fn=record_send)
        assert sent == [1]  # the full-payload CAID let the regenerated retry through
        assert result.caid == compute_caid(retry)


# ---------------------------------------------------------------------------
# Raw-bytes audit binding
# ---------------------------------------------------------------------------


def test_bind_effect_key_same_effect_caid_distinct_raw_digest(registry):
    from src.jcs_canonicalizer import encode_jcs
    retry = regenerated(BASE)
    b1 = ek.bind_effect_key(TOOL, BASE, registry)
    b2 = ek.bind_effect_key(TOOL, retry, registry)
    assert b1.effect_caid == b2.effect_caid == compute_effect_caid(TOOL, BASE, registry)
    assert b1.raw_payload_digest != b2.raw_payload_digest
    assert b1.raw_payload_digest == hashlib.sha256(encode_jcs(dict(BASE))).hexdigest()
    assert b2.raw_payload_digest == hashlib.sha256(encode_jcs(dict(retry))).hexdigest()
    assert b1.raw_payload_digest == ek.raw_payload_digest(BASE)
    assert b1.preimage == effect_key_preimage(TOOL, BASE, registry)
    assert b1.effect_class is EffectClass.IRREVERSIBLE
    assert b1.hint_observation == McpHintReport()
    assert b1.latch_required is True
    assert b1.key_mode == KEY_MODE_EFFECT
    assert b1.schema_id == f"{TOOL}.effect"
    assert b1.schema_digest == pay_schema().digest()
    assert ek.EffectKeyRegistry is EffectKeySchemaRegistry


def test_bind_effect_key_refusals_and_hints():
    idem = EffectKeySchemaRegistry([pay_schema(effect_class=EffectClass.IDEMPOTENT)])
    b = ek.bind_effect_key(TOOL, BASE, idem, annotations={"idempotentHint": True}, honor_idempotent_hint=True)
    assert b.latch_required is False and b.hint_observation.idempotent_hint is True
    assert ek.bind_effect_key(TOOL, BASE, idem, annotations={"idempotentHint": True}).latch_required is True
    with pytest.raises(UnknownToolSchemaError):
        ek.bind_effect_key("unknown.tool", BASE, idem)
    with pytest.raises(MissingIdentityFieldError):
        ek.bind_effect_key(TOOL, {k: v for k, v in BASE.items() if k != "currency"}, idem)
    for bad in (None, [1], "x"):
        with pytest.raises(InvalidIdentityValueError):
            ek.bind_effect_key(TOOL, bad, idem)
        with pytest.raises(InvalidIdentityValueError):
            ek.raw_payload_digest(bad)
    fb = ek.bind_effect_key("legacy", BASE, EffectKeySchemaRegistry([], allow_full_payload_fallback=True))
    assert fb.key_mode == KEY_MODE_FULL_PAYLOAD and fb.effect_class is None and fb.schema_id is None
    assert fb.raw_payload_digest == ek.raw_payload_digest(BASE)
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.effect_caid = "0" * 64


# ---------------------------------------------------------------------------
# Labelled pairs
# ---------------------------------------------------------------------------

INLINE_PAIRS = [
    {"id": "s1", "label": "same_effect", "tool": TOOL, "a": BASE, "b": regenerated(BASE)},
    {"id": "s2", "label": "same_effect", "tool": TOOL, "a": BASE, "b": {**BASE, "end_to_end_id": "INV-R1"}},
    {"id": "s3", "label": "same_effect", "tool": TOOL, "a": BASE, "b": {**BASE, "amount_minor": 1250.0}},
    {"id": "s4", "label": "same_effect", "tool": TOOL, "a": BASE, "b": copy.deepcopy(BASE)},
    {"id": "d1", "label": "different_effect", "tool": TOOL, "a": BASE, "b": {**BASE, "amount_minor": 1}},
    {"id": "d2", "label": "different_effect", "tool": TOOL, "a": BASE, "b": {**BASE, "remittance_info": "z"}},
]


def test_evaluate_pairs_inline(registry):
    rep = evaluate_pairs(INLINE_PAIRS, registry)
    assert rep["pairs"] == 6
    assert rep["labels"] == {"same_effect": 4, "different_effect": 2}
    assert rep["full_payload_caid"]["counts"] == {"same_key_same_effect": 1, "false_split": 3, "false_merge": 0,
                                                  "diff_key_diff_effect": 2, "refused": 0}
    # d2 is a deliberately mislabelled pair (only incidental memo differs) to show a false merge is detected.
    assert rep["effect_key_caid"]["counts"] == {"same_key_same_effect": 2, "false_split": 1, "false_merge": 1,
                                                "diff_key_diff_effect": 1, "refused": 1}
    errors = {e["id"]: e for e in rep["effect_key_caid"]["errors"]}
    assert errors["s2"]["result"] == "false_split"
    assert errors["d2"]["result"] == "false_merge"
    assert errors["s3"] == {"id": "s3", "result": "refused", "reason": "InvalidIdentityValueError"}
    assert set(errors) == {"s2", "s3", "d2"}
    with pytest.raises(ValueError):
        evaluate_pairs([{**INLINE_PAIRS[0], "label": "maybe"}], registry)


@pytest.mark.skipif(not PAIRS_PATH.exists(), reason="labelled pair file absent (e.g. mutation-gate shadow root)")
def test_labelled_pair_file_zero_false_merges():
    reg, pairs = load_pairs_file(PAIRS_PATH)
    assert len(pairs) >= 50
    assert len({p["id"] for p in pairs}) == len(pairs)
    rep = evaluate_pairs(pairs, reg)
    for name in ("full_payload_caid", "effect_key_caid"):
        counts = rep[name]["counts"]
        assert sum(counts.values()) == len(pairs)
        assert counts["false_merge"] == 0
    assert rep["effect_key_caid"]["counts"]["false_split"] < rep["full_payload_caid"]["counts"]["false_split"]
    doc = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    assert "NOT field data" in doc["description"]


def test_load_pairs_file_and_cli_on_temp_file(tmp_path, capsys):
    """Runs without tests/data (the mutation-gate shadow root does not copy it)."""
    schema = pay_schema()
    doc = {
        "schemas": [{"tool": schema.tool, "schema_id": schema.schema_id, "schema_version": schema.schema_version,
                     "effect_class": schema.effect_class.value,
                     "identity_fields": [f.descriptor() for f in schema.identity_fields]}],
        "pairs": INLINE_PAIRS,
    }
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    reg, pairs = load_pairs_file(path)
    assert reg.tools() == [TOOL]
    assert reg.get(TOOL).digest() == schema.digest()
    assert len(pairs) == len(INLINE_PAIRS)
    assert ek.main(["--pairs", str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == json.loads(json.dumps(evaluate_pairs(INLINE_PAIRS, reg)))
    assert out["effect_key_caid"]["counts"]["false_merge"] == 1
    # The module entry point (python3 -m src.eo1_effect_key) prints the same report.
    import os
    import subprocess
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run([sys.executable, "-m", "src.eo1_effect_key", "--pairs", str(path)], cwd=str(ROOT),
                          env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-500:]
    assert json.loads(proc.stdout) == out
    # Report text is deterministic (sorted keys, 2-space indent) so runs can be diffed.
    assert proc.stdout == json.dumps(out, indent=2, sort_keys=True) + "\n"


@pytest.mark.skipif(not PAIRS_PATH.exists(), reason="labelled pair file absent (e.g. mutation-gate shadow root)")
def test_cli_main_prints_report(capsys):
    assert ek.main(["--pairs", str(PAIRS_PATH)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["effect_key_caid"]["counts"]["false_merge"] == 0
