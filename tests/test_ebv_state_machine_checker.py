# Copyright 2026 SovereignNexus Project
#
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
tests/test_ebv_state_machine_checker.py — Tests for EBVStateMachineChecker.

Validates that:
- Shipped EBV specification passes all model-checking checks.
- Artificially injected blind retry cycles fail verification.
- Artificially injected deadlocks fail verification.
- Artificially injected transitions out of terminal states fail verification.
"""

import copy
import json
import pytest
from pathlib import Path
from tools.ebv_state_machine_checker import EBVStateMachineChecker, DEFAULT_SPEC_PATH


@pytest.fixture
def base_spec_dict():
    return json.loads(DEFAULT_SPEC_PATH.read_text(encoding="utf-8"))


def test_shipped_spec_passes_all_invariants():
    checker = EBVStateMachineChecker.from_file(DEFAULT_SPEC_PATH)
    res = checker.run_all_checks()
    assert res.all_invariants_held is True
    assert res.no_blind_retries_held is True
    assert res.deadlock_free is True
    assert res.absorbing_sinks_held is True
    assert len(res.violations) == 0


def test_injected_blind_retry_cycle_detected(base_spec_dict):
    mutated = copy.deepcopy(base_spec_dict)
    # Inject an unauthorized direct retry transition
    mutated["ebv_state_machine"]["transitions"].append({
        "from": "EFFECT_INDETERMINATE",
        "to": "DISPATCHED",
        "trigger": "unauthorized_blind_retry",
        "condition": "retry_blindly",
    })

    checker = EBVStateMachineChecker(mutated)
    res = checker.run_all_checks()
    assert res.all_invariants_held is False
    assert res.no_blind_retries_held is False
    assert any("BLIND_RETRY_CYCLE_DETECTED" in v for v in res.violations)


def test_injected_deadlock_detected(base_spec_dict):
    mutated = copy.deepcopy(base_spec_dict)
    # Add a deadlocked non-terminal state
    mutated["ebv_state_machine"]["states"]["DEADLOCK_TRAP"] = {
        "description": "Unreachable trap",
        "is_effective": False,
        "terminal": False,
    }
    # No outbound transitions from DEADLOCK_TRAP

    checker = EBVStateMachineChecker(mutated)
    res = checker.run_all_checks()
    assert res.all_invariants_held is False
    assert res.terminal_reachability_held is False
    assert any("DEADLOCK_OR_UNREACHABLE_TERMINAL" in v for v in res.violations)


def test_non_absorbing_terminal_detected(base_spec_dict):
    mutated = copy.deepcopy(base_spec_dict)
    # Add transition out of terminal state CONFIRMED
    mutated["ebv_state_machine"]["transitions"].append({
        "from": "CONFIRMED",
        "to": "PROPOSED",
        "trigger": "illegal_reopen",
        "condition": "none",
    })

    checker = EBVStateMachineChecker(mutated)
    res = checker.run_all_checks()
    assert res.all_invariants_held is False
    assert res.absorbing_sinks_held is False
    assert any("NON_ABSORBING_TERMINAL" in v for v in res.violations)
