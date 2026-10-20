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
tools/ebv_state_machine_checker.py — Formal Graph Model Checker for EBV.

Formally evaluates the state machine declared in specs/ebv-state-machine-v0.json:
1. Invariant 1: No Blind Retries (No directed path from EFFECT_INDETERMINATE to DISPATCHED
   without first transitioning through an authoritative resolution state CONFIRMED or REFUTED).
2. Invariant 2: Terminal Reachability & Deadlock-Freedom (All non-terminal states can reach
   at least one terminal state).
3. Invariant 3: Absorbing Sinks (Terminal states have zero outbound execution transitions).
"""

import json
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC_PATH = REPO_ROOT / "specs" / "ebv-state-machine-v0.json"


@dataclass(frozen=True)
class ModelCheckingResult:
    all_invariants_held: bool
    no_blind_retries_held: bool
    deadlock_free: bool
    terminal_reachability_held: bool
    absorbing_sinks_held: bool
    violations: List[str]


class EBVStateMachineChecker:
    """Performs graph reachability and temporal invariant verification on EBV specifications."""

    def __init__(self, spec_data: Dict[str, Any]) -> None:
        sm = spec_data.get("ebv_state_machine", {})
        self.states: Dict[str, Dict[str, Any]] = sm.get("states", {})
        self.transitions: List[Dict[str, Any]] = sm.get("transitions", [])

        # Build adjacency graph
        self.adj: Dict[str, List[str]] = defaultdict(list)
        for t in self.transitions:
            src = t.get("from")
            dst = t.get("to")
            if src == "*":
                for s in self.states.keys():
                    if not self.states[s].get("terminal", False):
                        self.adj[s].append(dst)
            elif src and dst:
                self.adj[src].append(dst)

    @classmethod
    def from_file(cls, path: Path = DEFAULT_SPEC_PATH) -> "EBVStateMachineChecker":
        if not path.is_file():
            raise FileNotFoundError(f"State machine specification not found at {path}")
        content = json.loads(path.read_text(encoding="utf-8"))
        return cls(content)

    def verify_no_blind_retries(self) -> Tuple[bool, List[str]]:
        """
        Evaluates whether an agent can cycle from EFFECT_INDETERMINATE directly
        back to DISPATCHED without first passing through an authoritative state.
        """
        violations = []
        visited = set()
        queue = deque([("EFFECT_INDETERMINATE", ["EFFECT_INDETERMINATE"])])

        while queue:
            curr, path = queue.popleft()
            if curr == "DISPATCHED" and len(path) > 1:
                # Check if path passed through resolution states
                passed_resolution = any(s in ("CONFIRMED", "REFUTED") for s in path[1:-1])
                if not passed_resolution:
                    violations.append(
                        f"BLIND_RETRY_CYCLE_DETECTED: path {' -> '.join(path)} bypasses resolution"
                    )

            for neighbor in self.adj.get(curr, []):
                # Only explore paths if neighbor is not a terminal state
                if neighbor not in ("CONFIRMED", "REFUTED", "HALTED") and (curr, neighbor) not in visited:
                    visited.add((curr, neighbor))
                    queue.append((neighbor, path + [neighbor]))

        return len(violations) == 0, violations

    def verify_terminal_reachability(self) -> Tuple[bool, List[str]]:
        """Verifies that every non-terminal state can reach at least one terminal state."""
        violations = []
        terminals = {s for s, meta in self.states.items() if meta.get("terminal", False)}

        for state, meta in self.states.items():
            if meta.get("terminal", False):
                continue

            # BFS from state looking for any terminal
            visited = set()
            queue = deque([state])
            reached_terminal = False

            while queue:
                curr = queue.popleft()
                if curr in terminals:
                    reached_terminal = True
                    break
                for nxt in self.adj.get(curr, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)

            if not reached_terminal:
                violations.append(f"DEADLOCK_OR_UNREACHABLE_TERMINAL: state '{state}' has no path to terminal state")

        return len(violations) == 0, violations

    def verify_absorbing_sinks(self) -> Tuple[bool, List[str]]:
        """Verifies that terminal states have zero outbound edges."""
        violations = []
        for state, meta in self.states.items():
            if meta.get("terminal", False):
                outbound = self.adj.get(state, [])
                if outbound:
                    violations.append(
                        f"NON_ABSORBING_TERMINAL: terminal state '{state}' has outbound transitions to {outbound}"
                    )
        return len(violations) == 0, violations

    def run_all_checks(self) -> ModelCheckingResult:
        all_violations = []

        no_retries_ok, v1 = self.verify_no_blind_retries()
        all_violations.extend(v1)

        reach_ok, v2 = self.verify_terminal_reachability()
        all_violations.extend(v2)

        sinks_ok, v3 = self.verify_absorbing_sinks()
        all_violations.extend(v3)

        deadlock_free = reach_ok

        all_held = no_retries_ok and reach_ok and sinks_ok

        return ModelCheckingResult(
            all_invariants_held=all_held,
            no_blind_retries_held=no_retries_ok,
            deadlock_free=deadlock_free,
            terminal_reachability_held=reach_ok,
            absorbing_sinks_held=sinks_ok,
            violations=all_violations,
        )


def main():
    checker = EBVStateMachineChecker.from_file()
    res = checker.run_all_checks()
    print("=" * 70)
    print("  EBV STATE MACHINE FORMAL MODEL CHECKER")
    print("=" * 70)
    print(f"No Blind Retries Invariant : {'PASSED' if res.no_blind_retries_held else 'FAILED'}")
    print(f"Deadlock-Freedom           : {'PASSED' if res.deadlock_free else 'FAILED'}")
    print(f"Terminal Reachability      : {'PASSED' if res.terminal_reachability_held else 'FAILED'}")
    print(f"Absorbing Sinks            : {'PASSED' if res.absorbing_sinks_held else 'FAILED'}")
    print(f"Overall Disposition        : {'ALL_INVARIANTS_HELD' if res.all_invariants_held else 'VIOLATIONS_FOUND'}")
    print("=" * 70)

    if not res.all_invariants_held:
        for v in res.violations:
            print(f"[!] {v}")
        sys.exit(1)


if __name__ == "__main__":
    main()
