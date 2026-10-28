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
tests/test_rssi_harness_evolver.py
================================================================================
Falsification & Verification Suite for the RRSI Harness Evolver.
Proves that the harness can learn valid constraints while remaining mathematically
immune to agent reward-hacking, invalid regexes, and regression-inducing rules.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.rssi_harness_evolver import (
    FailureTrace,
    HaltSource,
    HarnessPatch,
    RRSIEvolverEngine,
)

CORPUS = [
    "import json\n# A long comment line to ensure the text length exceeds sixty characters strictly\ndata = json.loads(payload)",
    "def calculate_tax(income):\n    return income * 0.2",
    "class UserSchema:\n    age: int = 18",
    "from pathlib import Path\np = Path('/tmp/file.txt')",
]


def test_failure_trace_and_patch_immutability() -> None:
    """Verifies that FailureTrace and HarnessPatch are frozen dataclasses."""
    import dataclasses
    trace = FailureTrace(
        trace_id="tr-000",
        source=HaltSource.AST_ORACLE,
        halt_code="HALT_IMMUTABLE",
        offender_payload="pass",
        eo1_intent_hash="sha256:000",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.trace_id = "mutated"  # type: ignore

    patch = HarnessPatch(
        patch_id="patch-000",
        target_gate="AST_ORACLE",
        rule_type="AST_REGEX_BAN",
        rule_expression="ban",
        safety_regression_hash="hash",
        issuer_public_key_hex="00" * 32,
        evolution_receipt_b64="AA==",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        patch.patch_id = "mutated"  # type: ignore


def test_rssi_learns_schema_constraint() -> None:
    """Evolver learns a new schema constraint from a schema drift failure trace."""
    engine = RRSIEvolverEngine(known_good_corpus=CORPUS)
    trace = FailureTrace(
        trace_id="tr-001",
        source=HaltSource.SCHEMA_GATE,
        halt_code="HALT_SCHEMA_DRIFT_DETECTED:age_field_missing",
        offender_payload="{'name': 'Alice'}",
        eo1_intent_hash="sha256:abc12345",
    )

    patch = engine.synthesize_and_validate_patch(
        trace=trace,
        proposed_rule="age: int = Field(..., gt=0)",
        proposed_type="PYDANTIC_CONSTRAINT",
    )

    expected_patch_id = f"patch-{__import__('hashlib').sha256(b'tr-001').hexdigest()[:12]}"
    assert patch.patch_id == expected_patch_id
    assert len(patch.patch_id) == 18
    assert patch.target_gate == "SCHEMA_GATE"
    assert patch.rule_type == "PYDANTIC_CONSTRAINT"
    verification = patch.verify_receipt()
    assert verification is True
    assert type(verification) is bool
    assert len(engine.active_patches) == 1


def test_rssi_learns_valid_ast_regex_ban() -> None:
    """Evolver learns a valid AST regex ban that does not match known-good code."""
    engine = RRSIEvolverEngine(known_good_corpus=CORPUS)
    trace = FailureTrace(
        trace_id="tr-002",
        source=HaltSource.AST_ORACLE,
        halt_code="HALT_AST_FORBIDDEN_CALL:dangerous_system_call",
        offender_payload="dangerous_system_call('/tmp')",
        eo1_intent_hash="sha256:def67890",
    )

    patch = engine.synthesize_and_validate_patch(
        trace=trace,
        proposed_rule=r"dangerous_system_call\(",
        proposed_type="AST_REGEX_BAN",
    )

    expected_patch_id = f"patch-{__import__('hashlib').sha256(b'tr-002').hexdigest()[:12]}"
    assert patch.patch_id == expected_patch_id
    assert len(patch.patch_id) == 18
    assert patch.rule_type == "AST_REGEX_BAN"
    assert patch.verify_receipt() is True


def test_rssi_blocks_reward_hacking_eval_allowance() -> None:
    """Agent tries to 'learn' that eval() should be allowed to pass a failing test."""
    engine = RRSIEvolverEngine(known_good_corpus=CORPUS)
    trace = FailureTrace(
        trace_id="tr-003",
        source=HaltSource.AST_ORACLE,
        halt_code="HALT_AST_FORBIDDEN_CALL:eval",
        offender_payload="result = eval(user_input)",
        eo1_intent_hash="sha256:hack123",
    )

    with pytest.raises(ValueError, match="HALT_RRSI_REWARD_HACKING"):
        engine.synthesize_and_validate_patch(
            trace=trace,
            proposed_rule="ALLOW: eval(code)",
            proposed_type="AST_REGEX_BAN",
        )


def test_rssi_blocks_reward_hacking_subprocess_allowance() -> None:
    """Agent tries to allow subprocess calls."""
    engine = RRSIEvolverEngine(known_good_corpus=CORPUS)
    trace = FailureTrace(
        trace_id="tr-004",
        source=HaltSource.AST_ORACLE,
        halt_code="HALT_AST_FORBIDDEN_CALL:subprocess",
        offender_payload="subprocess.run(['ls'])",
        eo1_intent_hash="sha256:hack456",
    )

    with pytest.raises(ValueError, match="HALT_RRSI_REWARD_HACKING"):
        engine.synthesize_and_validate_patch(
            trace=trace,
            proposed_rule="subprocess.Popen",
            proposed_type="AST_REGEX_BAN",
        )


def test_rssi_blocks_regression_against_known_good_corpus() -> None:
    """Proposed rule is so broad it flags standard library imports in the known-good corpus."""
    engine = RRSIEvolverEngine(known_good_corpus=CORPUS)
    trace = FailureTrace(
        trace_id="tr-005",
        source=HaltSource.AST_ORACLE,
        halt_code="HALT_AST_SUSPICIOUS_IMPORT",
        offender_payload="import evil_module",
        eo1_intent_hash="sha256:imp789",
    )

    # Proposing to ban all imports breaks 'import json' in the corpus
    with pytest.raises(ValueError) as exc:
        engine.synthesize_and_validate_patch(
            trace=trace,
            proposed_rule=r"import\s+.*",
            proposed_type="AST_REGEX_BAN",
        )
    expected_msg = f"HALT_RRSI_REGRESSION_FAILURE: Proposed ban rule flags known-good code: {CORPUS[0][:50]}..."
    assert str(exc.value) == expected_msg


def test_rssi_rejects_invalid_regex_syntax() -> None:
    """Evolver rejects syntactically malformed regex patterns fail-closed."""
    engine = RRSIEvolverEngine(known_good_corpus=CORPUS)
    trace = FailureTrace(
        trace_id="tr-006",
        source=HaltSource.AST_ORACLE,
        halt_code="HALT_AST_MALFORMED",
        offender_payload="some_bad_call",
        eo1_intent_hash="sha256:badregex",
    )

    with pytest.raises(ValueError, match="HALT_RRSI_INVALID_REGEX"):
        engine.synthesize_and_validate_patch(
            trace=trace,
            proposed_rule=r"[a-z(",  # Unclosed parenthesis
            proposed_type="AST_REGEX_BAN",
        )


def test_harness_patch_tampered_receipt_fails_verification() -> None:
    """Tampering with patch rule or signature invalidates receipt verification."""
    engine = RRSIEvolverEngine(known_good_corpus=CORPUS)
    trace = FailureTrace(
        trace_id="tr-007",
        source=HaltSource.EPISTEMIC_TAINT,
        halt_code="HALT_TAINT_OVERFLOW",
        offender_payload="tainted_input",
        eo1_intent_hash="sha256:taint1",
    )
    patch = engine.synthesize_and_validate_patch(
        trace=trace,
        proposed_rule="taint_level_must_be_clean",
        proposed_type="TAINT_HEURISTIC",
    )
    assert patch.verify_receipt() is True

    # Mutated patch expression fails verification
    tampered = HarnessPatch(
        patch_id=patch.patch_id,
        target_gate=patch.target_gate,
        rule_type=patch.rule_type,
        rule_expression="taint_level_ALLOW_ANYTHING",
        safety_regression_hash=patch.safety_regression_hash,
        issuer_public_key_hex=patch.issuer_public_key_hex,
        evolution_receipt_b64=patch.evolution_receipt_b64,
    )
    assert tampered.verify_receipt() is False
