"""
macOS Seatbelt (sandbox-exec) argv builder for running untrusted child processes (prototype).

`build_seatbelt_argv` prefixes a command with `/usr/bin/sandbox-exec` and an SBPL
profile that, under the stated model:
  - denies all network operations (unless `allow_network=True`);
  - denies file writes everywhere except the given writable roots and `/dev/null`;
  - denies file reads AND writes under the given deny-read roots (these rules come
    last, so they also win over a writable root that contains them);
  - optionally (`allow_process_fork=False`) denies `process-fork`, appended as the
    final rule. On this host (macOS 27.2) `os.fork()`, `subprocess.run` (which uses
    posix_spawn) and `os.posix_spawn` were observed to fail with EPERM under that
    rule, while the wrapped interpreter still started (exec is not fork) and ran
    pure computation. The default (`True`) leaves the profile byte-identical to the
    builder before this flag existed.

Paths are realpath'd and passed as `-D` parameters; they are never spliced into the
SBPL text, so quotes or parentheses in a path cannot change the profile. Paths with
NUL or newline characters, empty paths and relative paths are rejected (ValueError).

Honest limitations:
  - `sandbox-exec` is deprecated by Apple; it is still shipped and observed to work on
    this host, but Apple may change or remove it.
  - The profile is allow-default (not deny-default): process execution, IPC, Mach
    lookups and reads outside the deny-read roots remain allowed; process creation
    is allowed too unless `allow_process_fork=False`.
  - Memory limits are not enforced on macOS (RLIMIT_AS is not honoured and Seatbelt
    does not limit memory).
  - This is process isolation, not a sandbox: a containment layer for buggy code,
    not a full sandbox for adversarial code. Without Seatbelt (non-macOS hosts, or a
    caller that runs the child without this wrapper) forking is not blocked.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable, List, Sequence

SANDBOX_EXEC_PATH = "/usr/bin/sandbox-exec"

# Per-user credential / config locations that an untrusted child should not read.
SENSITIVE_HOME_ENTRIES = (
    ".ssh",
    ".aws",
    ".gnupg",
    ".config",
    ".netrc",
    ".docker",
    ".kube",
    os.path.join("Library", "Keychains"),
)


def seatbelt_available(sandbox_exec_path: str = SANDBOX_EXEC_PATH, platform: str = sys.platform) -> bool:
    """True only on darwin when `sandbox_exec_path` is an executable regular file."""
    if platform != "darwin":
        return False
    return os.path.isfile(sandbox_exec_path) and os.access(sandbox_exec_path, os.X_OK)


def _safe_realpath(path: str) -> str:
    """Validates a path for use as an SBPL `-D` parameter and returns its realpath."""
    if not isinstance(path, str):
        raise ValueError("ERR_PATH_NOT_STRING")
    if "\x00" in path or "\n" in path or "\r" in path:
        raise ValueError("ERR_PATH_NOT_SAFE_FOR_SBPL")
    if not os.path.isabs(path):
        raise ValueError("ERR_PATH_NOT_ABSOLUTE")
    resolved = os.path.realpath(path)
    if "\x00" in resolved or "\n" in resolved or "\r" in resolved:
        raise ValueError("ERR_PATH_NOT_SAFE_FOR_SBPL")
    return resolved


def build_seatbelt_argv(
    cmd: Sequence[str],
    writable_roots: Iterable[str],
    deny_read_roots: Iterable[str],
    allow_network: bool = False,
    sandbox_exec_path: str = SANDBOX_EXEC_PATH,
    allow_process_fork: bool = True,
) -> List[str]:
    """
    Returns `[sandbox_exec_path, -D ..., -p <profile>, *cmd]` (see module docstring).

    `allow_process_fork=False` appends `(deny process-fork)` so the wrapped process
    cannot fork or posix_spawn descendants (observed on this host, see module
    docstring); a non-bool raises ValueError("ERR_ALLOW_PROCESS_FORK_NOT_BOOL").
    sandbox-exec is deprecated by Apple; this is process isolation, not a sandbox.
    """
    cmd_list = list(cmd)
    if not cmd_list or not all(isinstance(c, str) for c in cmd_list):
        raise ValueError("ERR_CMD_INVALID")
    if cmd_list[0].startswith("-"):
        # sandbox-exec would parse it as one of its own options.
        raise ValueError("ERR_CMD_LOOKS_LIKE_OPTION")
    if type(allow_network) is not bool:
        raise ValueError("ERR_ALLOW_NETWORK_NOT_BOOL")
    if type(allow_process_fork) is not bool:
        raise ValueError("ERR_ALLOW_PROCESS_FORK_NOT_BOOL")

    params: List[str] = []
    write_rules: List[str] = []
    for idx, path in enumerate(writable_roots):
        params += ["-D", f"W_{idx}={_safe_realpath(path)}"]
        write_rules.append(f'(subpath (param "W_{idx}"))')
    deny_rules: List[str] = []
    for idx, path in enumerate(deny_read_roots):
        params += ["-D", f"R_{idx}={_safe_realpath(path)}"]
        deny_rules.append(f'(subpath (param "R_{idx}"))')

    profile = "(version 1)(allow default)"
    if not allow_network:
        profile += "(deny network*)"
    profile += "(deny file-write*)"
    write_rules.append('(literal "/dev/null")')
    profile += "(allow file-write* " + " ".join(write_rules) + ")"
    if deny_rules:
        profile += f'(deny file-read* file-write* {" ".join(deny_rules)})'
    if not allow_process_fork:
        profile += "(deny process-fork)"
    return [sandbox_exec_path, *params, "-p", profile, *cmd_list]


def _is_same_or_under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def sensitive_home_deny_roots(home: str, keep_readable: Iterable[str]) -> List[str]:
    """
    Existing entries of SENSITIVE_HOME_ENTRIES under `home`, realpath'd.

    An entry is skipped when any `keep_readable` path (e.g. the interpreter,
    sys.prefix, the child's temp cwd) is equal to or under it, so the child can
    still start and run. Returns a sorted, de-duplicated list.
    """
    keep = [os.path.realpath(k) for k in keep_readable]
    roots = set()
    for entry in SENSITIVE_HOME_ENTRIES:
        candidate = os.path.join(home, entry)
        if not os.path.lexists(candidate):
            continue
        resolved = os.path.realpath(candidate)
        if any(_is_same_or_under(k, resolved) for k in keep):
            continue
        roots.add(resolved)
    return sorted(roots)
