#!/usr/bin/env python3
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
aei_core/model/state.py
State and disposition taxonomy for Agent Execution Integrity (AEIB).
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class DispositionState(str, Enum):
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"
    DISPATCHED_UNCONFIRMED = "DISPATCHED_UNCONFIRMED"
    RECONCILIATION_NOT_FOUND = "RECONCILIATION_NOT_FOUND"
    RECONCILIATION_CONFLICT = "RECONCILIATION_CONFLICT"
    PROBE_TIMEOUT = "PROBE_TIMEOUT"
    PROBE_EXCEPTION = "PROBE_EXCEPTION"
    COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED = "COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED"
    PROBE_1_FAILED = "PROBE_1_FAILED"
    PROBE_2_FAILED = "PROBE_2_FAILED"
    PROBE_3_FAILED = "PROBE_3_FAILED"
    LOCKED_OUT = "LOCKED_OUT"
    THROTTLED = "THROTTLED"
    ALLOWED = "ALLOWED"


@dataclass
class ReconciliationState:
    caid: str
    disposition: str
    probe_attempts: int
    requires_further_probing: bool
    is_terminal: bool
    context: Dict[str, Any]
