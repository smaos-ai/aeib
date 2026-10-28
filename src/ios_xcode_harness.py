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
ios_xcode_harness.py — Typed Xcode / Swift toolchain wrapper (Wave 8 prototype).

Evaluated under the stated model:
- Only enum-typed actions map to fixed argv templates (no shell, no string eval).
- workspace_root and every path-like argument are resolved with realpath and
  must stay inside the configured root (defeats `..`, prefix spoofing such as
  /repo-evil vs /repo, and symlink redirects).
- Child env is rebuilt from scratch (credential starvation: no AWS_*, GITHUB_*,
  App Store Connect keys are inherited). HOME is pointed at the workspace.
- Missing binaries fail closed with HALT_XCODE_TOOLCHAIN_UNAVAILABLE.

This is process isolation, not a sandbox, unless sandbox_mode is
"seatbelt_required" (the default): then argv is run under macOS
/usr/bin/sandbox-exec with an SBPL profile that denies all network and denies
file writes outside the workspace and the per-user temp/cache dirs (enforcement
observed on this host with swiftc and nc). Limits: reads are not restricted;
sandbox-exec is deprecated by Apple; `simctl` asks the CoreSimulator daemon
(outside the sandbox) to act, so `simctl erase` still changes host-wide
simulator state; the child still runs with the caller's uid.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from src.ios_steward_guard import IOSProposal, IOSStewardGuard
from src.xctest_tamper_guard import ALLOW as XCTEST_ALLOW, XCTestTamperGuard


class XcodeActionType(str, Enum):
    BUILD_SCHEME = "BUILD_SCHEME"
    RUN_TESTS = "RUN_TESTS"
    BOOT_SIMULATOR = "BOOT_SIMULATOR"
    WIPE_SIMULATOR_STATE = "WIPE_SIMULATOR_STATE"
    SWIFT_TYPECHECK = "SWIFT_TYPECHECK"


@dataclass(frozen=True)
class XcodeToolCallRequest:
    action: XcodeActionType
    workspace_root: str
    target_name: str
    scheme_name: Optional[str] = None
    simulator_udid: Optional[str] = None
    extra_arguments: Tuple[str, ...] = ()
    workspace_file: Optional[str] = None


_SANITIZED_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
_SANDBOX_EXEC = "/usr/bin/sandbox-exec"
SANDBOX_SEATBELT_REQUIRED = "seatbelt_required"
SANDBOX_PROCESS_ISOLATION_ONLY = "process_isolation_only"


def _darwin_user_dir(name: str) -> Optional[str]:
    """Per-user temp/cache dir via getconf (e.g. DARWIN_USER_CACHE_DIR)."""
    try:
        res = subprocess.run(["/usr/bin/getconf", name], capture_output=True, text=True,
                             timeout=5, check=False, env={"PATH": _SANITIZED_PATH})
    except (OSError, subprocess.TimeoutExpired):
        return
    path = res.stdout.strip()
    if res.returncode != 0 or not path or not os.path.isdir(path):
        return
    return os.path.realpath(path)


class SovereignXcodeHarness:
    ALLOWED_ACTIONS: FrozenSet[XcodeActionType] = frozenset(XcodeActionType)

    _SAFE_ARG_RE = re.compile(r"^[A-Za-z0-9_\-./=:@]+$")
    _UDID_RE = re.compile(
        r"^(?:booted|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
    )
    _SCHEME_RE = re.compile(r"^[A-Za-z0-9_\-.]+$")

    def __init__(
        self,
        workspace_root: str,
        developer_dir: Optional[str] = None,
        tool_search_path: Optional[str] = None,
        sandbox_mode: str = SANDBOX_SEATBELT_REQUIRED,
        allow_simulator_wipe: bool = False,
    ) -> None:
        if not isinstance(workspace_root, str) or not workspace_root.strip():
            raise ValueError("ERR_INVALID_WORKSPACE_ROOT")
        if sandbox_mode not in (SANDBOX_SEATBELT_REQUIRED, SANDBOX_PROCESS_ISOLATION_ONLY):
            raise ValueError("ERR_INVALID_SANDBOX_MODE")
        if type(allow_simulator_wipe) is not bool:
            raise ValueError("ERR_INVALID_SIMULATOR_WIPE_FLAG")
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.tool_search_path = tool_search_path if tool_search_path is not None else _SANITIZED_PATH
        self.developer_dir = self._detect_developer_dir(developer_dir)
        self.sandbox_mode = sandbox_mode
        self.allow_simulator_wipe = allow_simulator_wipe

    def seatbelt_profile(self) -> Tuple[str, List[str]]:
        """SBPL profile + `-D` parameter args. Deny all network; deny file
        writes except the workspace, the per-user cache dir (for Clang/Swift
        SDK module cache) and /dev/null; then re-deny writes to
        <workspace>/.git (later SBPL rules win). `TMPDIR` is pointed at the
        workspace in `sanitized_env()`, so the host-wide per-user temp dir
        (`DARWIN_USER_TEMP_DIR`) is not opened for writes. Paths are passed as
        -D parameters, never spliced into the profile text."""
        writable = [self.workspace_root]
        cache_dir = _darwin_user_dir("DARWIN_USER_CACHE_DIR")
        if cache_dir:
            writable.append(cache_dir)
        params: List[str] = []
        rules = []
        for idx, path in enumerate(writable):
            if "\x00" in path or "\n" in path:
                raise ValueError("ERR_PATH_NOT_SAFE_FOR_SBPL")
            params += ["-D", f"WRITABLE_{idx}={path}"]
            rules.append(f'(subpath (param "WRITABLE_{idx}"))')
        profile = (
            "(version 1)(allow default)(deny network*)(deny file-write*)"
            f'(allow file-write* {" ".join(rules)} (literal "/dev/null"))'
            '(deny file-write* (subpath (string-append (param "WRITABLE_0") "/.git")))'
        )
        return profile, params

    def wrap_argv(self, cmd: List[str]) -> Tuple[Optional[List[str]], str]:
        """Prefix argv with sandbox-exec when seatbelt is required (fail closed)."""
        if self.sandbox_mode == SANDBOX_PROCESS_ISOLATION_ONLY:
            return list(cmd), ""
        if not os.path.isfile(_SANDBOX_EXEC):
            return None, "HALT_SEATBELT_UNAVAILABLE"
        try:
            profile, params = self.seatbelt_profile()
        except ValueError as exc:
            return None, f"HALT_SEATBELT_PROFILE_INVALID:{exc}"
        return [_SANDBOX_EXEC, *params, "-p", profile, *cmd], ""

    @staticmethod
    def _detect_developer_dir(explicit: Optional[str]) -> Optional[str]:
        candidates = [explicit, os.environ.get("DEVELOPER_DIR"),
                      "/Applications/Xcode.app/Contents/Developer",
                      "/Library/Developer/CommandLineTools"]
        for c in candidates:
            if c and os.path.isdir(c):
                return os.path.realpath(c)
        return

    def _inside_root(self, path: str) -> bool:
        full = os.path.realpath(os.path.join(self.workspace_root, path))
        return os.path.commonpath([self.workspace_root, full]) == self.workspace_root

    def _validate_argument(self, arg: object) -> bool:
        return (
            isinstance(arg, str)
            and bool(self._SAFE_ARG_RE.match(arg))
            and all(
                self._inside_root(part)
                for part in arg.split("=")
                if "/" in part or part.startswith("..")
            )
        )

    def build_command(self, request: XcodeToolCallRequest) -> Tuple[Optional[List[str]], str]:
        """Pure validation + argv construction (no execution)."""
        if not isinstance(request.action, XcodeActionType):
            return None, f"HALT_UNSUPPORTED_XCODE_ACTION:{request.action}"
        if not isinstance(request.workspace_root, str) or not request.workspace_root.strip():
            return None, "HALT_WORKSPACE_BOUNDARY_VIOLATION:EMPTY"
        target_ws = os.path.realpath(os.path.abspath(request.workspace_root))
        if os.path.commonpath([self.workspace_root, target_ws]) != self.workspace_root:
            return None, "HALT_WORKSPACE_BOUNDARY_VIOLATION:ESCAPES_ROOT"
        for arg in request.extra_arguments:
            if not self._validate_argument(arg):
                return None, f"HALT_UNSAFE_TOOLCHAIN_ARGUMENT:{arg}"

        action = request.action
        if action in (XcodeActionType.BUILD_SCHEME, XcodeActionType.RUN_TESTS):
            if not isinstance(request.scheme_name, str) or not self._SCHEME_RE.match(request.scheme_name):
                return None, "HALT_MISSING_OR_INVALID_SCHEME_NAME"
        if action in (XcodeActionType.BOOT_SIMULATOR, XcodeActionType.WIPE_SIMULATOR_STATE):
            if not isinstance(request.simulator_udid, str) or not self._UDID_RE.match(request.simulator_udid):
                return None, "HALT_MISSING_OR_INVALID_SIMULATOR_UDID"

        if action == XcodeActionType.BUILD_SCHEME:
            ws_file = request.workspace_file or "App.xcworkspace"
            if not self._validate_argument(ws_file):
                return None, f"HALT_UNSAFE_TOOLCHAIN_ARGUMENT:{ws_file}"
            return ["xcodebuild", "build", "-scheme", request.scheme_name,
                    "-workspace", os.path.join(target_ws, ws_file), *request.extra_arguments], ""
        if action == XcodeActionType.RUN_TESTS:
            sim_id = request.simulator_udid or "booted"
            if not self._UDID_RE.match(sim_id):
                return None, f"HALT_INVALID_SIMULATOR_UDID:{sim_id}"
            return ["xcodebuild", "test", "-scheme", request.scheme_name,
                    "-destination", f"platform=iOS Simulator,id={sim_id}", *request.extra_arguments], ""
        if action == XcodeActionType.BOOT_SIMULATOR:
            return ["xcrun", "simctl", "boot", request.simulator_udid], ""
        if action == XcodeActionType.WIPE_SIMULATOR_STATE:
            if not self.allow_simulator_wipe:
                return None, "HALT_SIMULATOR_WIPE_NOT_AUTHORIZED"
            return ["xcrun", "simctl", "erase", request.simulator_udid], ""
        # SWIFT_TYPECHECK: -typecheck writes no output artifacts.
        if request.extra_arguments:
            return ["swiftc", "-typecheck", *request.extra_arguments], ""
        return ["swiftc", "-version"], ""

    def sanitized_env(self) -> Dict[str, str]:
        env = {"PATH": _SANITIZED_PATH, "HOME": self.workspace_root,
               "TMPDIR": self.workspace_root,
               "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"}
        if self.developer_dir:
            env["DEVELOPER_DIR"] = self.developer_dir
        return env

    def dispatch_guarded_tool(
        self,
        request: XcodeToolCallRequest,
        proposals: Sequence[IOSProposal] = (),
        approver_public_key_hex: Optional[str] = None,
        timeout: float = 120.0,
    ) -> Tuple[bool, str, str]:
        """PreToolUse / pre-dispatch chain: runs IOSStewardGuard on any proposed
        diffs and XCTestTamperGuard.evaluate_worktree() on the real git
        worktree before invoking the sandboxed toolchain."""
        steward = IOSStewardGuard(approver_public_key_hex)
        for prop in proposals:
            ok, reason = steward.evaluate_ios_proposal(prop)
            if not ok:
                return False, "", reason
        tamper_guard = XCTestTamperGuard(self.workspace_root)
        for verdict in tamper_guard.evaluate_worktree():
            if verdict.disposition != XCTEST_ALLOW:
                return False, "", f"HALT_WORKTREE_XCTEST_TAMPER:{verdict.reason}"
        return self.dispatch_sandboxed_tool(request, timeout=timeout)

    def dispatch_sandboxed_tool(
        self, request: XcodeToolCallRequest, timeout: float = 120.0
    ) -> Tuple[bool, str, str]:
        cmd, reason = self.build_command(request)
        if cmd is None:
            return False, "", reason
        binary = shutil.which(cmd[0], path=self.tool_search_path)
        if binary is None:
            return False, "", f"HALT_XCODE_TOOLCHAIN_UNAVAILABLE:{cmd[0]}"
        argv, reason = self.wrap_argv([binary, *cmd[1:]])
        if argv is None:
            return False, "", reason
        try:
            res = subprocess.run(argv, cwd=self.workspace_root, env=self.sanitized_env(),
                                 capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return False, "", "HALT_TOOLCHAIN_TIMEOUT_EXPIRED"
        except OSError as exc:
            return False, "", f"HALT_TOOLCHAIN_EXCEPTION:{type(exc).__name__}"
        if res.returncode == 0:
            return True, res.stdout, "OK_TOOL_EXECUTION_SUCCESS"
        return False, res.stdout, f"HALT_PROCESS_EXIT_NON_ZERO:{res.returncode}"
