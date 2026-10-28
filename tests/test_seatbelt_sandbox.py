"""
Tests for src/seatbelt_sandbox.py.

Behavioural tests run the real /usr/bin/sandbox-exec against real files and a real
local TCP listener (no mocks). Each denial test has a control run without the
sandbox (or without the specific rule) showing the operation succeeds otherwise,
so a passing denial is not an artefact of the test setup. Tests needing
sandbox-exec are skipped with a reason when it is absent.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

from src.seatbelt_sandbox import (
    SANDBOX_EXEC_PATH,
    SENSITIVE_HOME_ENTRIES,
    build_seatbelt_argv,
    seatbelt_available,
    sensitive_home_deny_roots,
)

requires_seatbelt = pytest.mark.skipif(
    not seatbelt_available(), reason="macOS /usr/bin/sandbox-exec not available on this host"
)

_CHILD = r'''
import sys
op, target = sys.argv[1], sys.argv[2]
try:
    if op == "write":
        with open(target, "w") as fh:
            fh.write("child-wrote")
    elif op == "read":
        with open(target) as fh:
            fh.read()
    elif op == "connect":
        import socket
        s = socket.create_connection(("127.0.0.1", int(target)), timeout=3)
        s.close()
    print("OK")
except BaseException as exc:
    print("ERR:" + type(exc).__name__)
'''


def _run(argv: List[str]) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=30, env={})
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _child_cmd(op: str, target: str) -> List[str]:
    return [sys.executable, "-I", "-c", _CHILD, op, target]


def _listener() -> Tuple[socket.socket, int]:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    return srv, srv.getsockname()[1]


# ---------------------------------------------------------------------------
# Behaviour under the real sandbox-exec
# ---------------------------------------------------------------------------
@requires_seatbelt
def test_writes_inside_root_allowed_outside_denied(tmp_path: Path) -> None:
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()

    # Control: without the sandbox the child can write outside.
    assert _run(_child_cmd("write", str(outside / "control.txt"))) == "OK"
    assert (outside / "control.txt").read_text() == "child-wrote"

    argv_in = build_seatbelt_argv(_child_cmd("write", str(inside / "a.txt")), [str(inside)], [])
    assert _run(argv_in) == "OK"
    assert (inside / "a.txt").read_text() == "child-wrote"

    argv_out = build_seatbelt_argv(_child_cmd("write", str(outside / "b.txt")), [str(inside)], [])
    assert _run(argv_out) == "ERR:PermissionError"
    assert not (outside / "b.txt").exists()

    # /dev/null stays writable.
    argv_null = build_seatbelt_argv(_child_cmd("write", "/dev/null"), [str(inside)], [])
    assert _run(argv_null) == "OK"


@requires_seatbelt
def test_network_to_local_listener_denied_unless_allowed(tmp_path: Path) -> None:
    srv, port = _listener()
    try:
        # Control: reachable without the sandbox.
        assert _run(_child_cmd("connect", str(port))) == "OK"
        denied = build_seatbelt_argv(_child_cmd("connect", str(port)), [str(tmp_path)], [])
        assert _run(denied) == "ERR:PermissionError"
        allowed = build_seatbelt_argv(
            _child_cmd("connect", str(port)), [str(tmp_path)], [], allow_network=True
        )
        assert _run(allowed) == "OK"
    finally:
        srv.close()


@requires_seatbelt
def test_read_inside_deny_root_denied(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    planted = secret_dir / "id_planted"
    planted.write_text("planted-secret")
    other = tmp_path / "other.txt"
    other.write_text("public")

    # Control: readable when not listed as a deny root.
    assert _run(build_seatbelt_argv(_child_cmd("read", str(planted)), [str(tmp_path)], [])) == "OK"

    argv = build_seatbelt_argv(_child_cmd("read", str(planted)), [str(tmp_path)], [str(secret_dir)])
    assert _run(argv) == "ERR:PermissionError"
    # Reads outside the deny root remain allowed (allow-default profile).
    argv_other = build_seatbelt_argv(_child_cmd("read", str(other)), [str(tmp_path)], [str(secret_dir)])
    assert _run(argv_other) == "OK"
    # Deny rules come last, so they win over a writable root that contains them.
    argv_w = build_seatbelt_argv(
        _child_cmd("write", str(secret_dir / "new.txt")), [str(tmp_path)], [str(secret_dir)]
    )
    assert _run(argv_w) == "ERR:PermissionError"
    assert not (secret_dir / "new.txt").exists()


@requires_seatbelt
def test_symlinked_root_is_realpathed(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    argv = build_seatbelt_argv(_child_cmd("write", str(link / "x.txt")), [str(link)], [])
    assert f"W_0={os.path.realpath(real)}" in argv
    assert _run(argv) == "OK"
    assert (real / "x.txt").read_text() == "child-wrote"


@requires_seatbelt
def test_path_with_quote_and_parens_is_not_spliced(tmp_path: Path) -> None:
    hostile = tmp_path / 'a"b) (allow file-write* (subpath "/")) ("'
    hostile.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    argv = build_seatbelt_argv(_child_cmd("write", str(hostile / "ok.txt")), [str(hostile)], [])
    profile = argv[argv.index("-p") + 1]
    assert str(hostile) not in profile
    assert _run(argv) == "OK"
    assert (hostile / "ok.txt").read_text() == "child-wrote"
    argv_out = build_seatbelt_argv(_child_cmd("write", str(outside / "no.txt")), [str(hostile)], [])
    assert _run(argv_out) == "ERR:PermissionError"
    assert not (outside / "no.txt").exists()


# ---------------------------------------------------------------------------
# Argv / profile construction (pure)
# ---------------------------------------------------------------------------
def test_exact_argv_and_profile_shape(tmp_path: Path) -> None:
    w = tmp_path / "w"
    r1 = tmp_path / "r1"
    r2 = tmp_path / "r2"
    for d in (w, r1, r2):
        d.mkdir()
    rw, rr1, rr2 = (os.path.realpath(p) for p in (w, r1, r2))
    argv = build_seatbelt_argv(["/bin/echo", "hi"], [str(w)], [str(r1), str(r2)])
    assert argv == [
        SANDBOX_EXEC_PATH,
        "-D", f"W_0={rw}",
        "-D", f"R_0={rr1}",
        "-D", f"R_1={rr2}",
        "-p",
        "(version 1)(allow default)(deny network*)(deny file-write*)"
        '(allow file-write* (subpath (param "W_0")) (literal "/dev/null"))'
        '(deny file-read* file-write* (subpath (param "R_0")) (subpath (param "R_1")))',
        "/bin/echo", "hi",
    ]
    no_deny = build_seatbelt_argv(["/bin/echo"], [], [], allow_network=True, sandbox_exec_path="/x/sb")
    assert no_deny == [
        "/x/sb",
        "-p",
        '(version 1)(allow default)(deny file-write*)(allow file-write* (literal "/dev/null"))',
        "/bin/echo",
    ]


@pytest.mark.parametrize(
    "bad_path, code",
    [
        ("/tmp/a\nb", "ERR_PATH_NOT_SAFE_FOR_SBPL"),
        ("/tmp/a\rb", "ERR_PATH_NOT_SAFE_FOR_SBPL"),
        ("/tmp/a\x00b", "ERR_PATH_NOT_SAFE_FOR_SBPL"),
        ("relative/dir", "ERR_PATH_NOT_ABSOLUTE"),
        ("", "ERR_PATH_NOT_ABSOLUTE"),
    ],
)
def test_unsafe_paths_rejected(bad_path: str, code: str) -> None:
    with pytest.raises(ValueError, match=code):
        build_seatbelt_argv(["/bin/echo"], [bad_path], [])
    with pytest.raises(ValueError, match=code):
        build_seatbelt_argv(["/bin/echo"], ["/tmp"], [bad_path])


def test_non_string_path_and_bad_cmd_rejected() -> None:
    with pytest.raises(ValueError, match="ERR_PATH_NOT_STRING"):
        build_seatbelt_argv(["/bin/echo"], [b"/tmp"], [])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="ERR_CMD_INVALID"):
        build_seatbelt_argv([], ["/tmp"], [])
    with pytest.raises(ValueError, match="ERR_CMD_INVALID"):
        build_seatbelt_argv(["/bin/echo", 3], ["/tmp"], [])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="ERR_CMD_LOOKS_LIKE_OPTION"):
        build_seatbelt_argv(["-f", "/etc/passwd"], ["/tmp"], [])
    with pytest.raises(ValueError, match="ERR_ALLOW_NETWORK_NOT_BOOL"):
        build_seatbelt_argv(["/bin/echo"], ["/tmp"], [], allow_network=1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Opt-in `(deny process-fork)` (allow_process_fork=False)
# ---------------------------------------------------------------------------
_OLD_DEFAULT_PROFILE = (
    "(version 1)(allow default)(deny network*)(deny file-write*)"
    '(allow file-write* (subpath (param "W_0")) (literal "/dev/null"))'
    '(deny file-read* file-write* (subpath (param "R_0")))'
)


def test_default_profile_byte_identical_to_pre_fork_flag_builder(tmp_path: Path) -> None:
    w = tmp_path / "w"
    r = tmp_path / "r"
    w.mkdir()
    r.mkdir()
    rw, rr = os.path.realpath(w), os.path.realpath(r)
    old_argv = [SANDBOX_EXEC_PATH, "-D", f"W_0={rw}", "-D", f"R_0={rr}", "-p", _OLD_DEFAULT_PROFILE, "/bin/echo"]
    assert build_seatbelt_argv(["/bin/echo"], [str(w)], [str(r)]) == old_argv
    assert build_seatbelt_argv(["/bin/echo"], [str(w)], [str(r)], allow_process_fork=True) == old_argv
    assert "process-fork" not in build_seatbelt_argv(["/bin/echo"], [], [], allow_network=True)[2]


def test_deny_fork_profile_appends_rule_last(tmp_path: Path) -> None:
    w = tmp_path / "w"
    r = tmp_path / "r"
    w.mkdir()
    r.mkdir()
    argv = build_seatbelt_argv(["/bin/echo", "x"], [str(w)], [str(r)], allow_process_fork=False)
    assert argv[argv.index("-p") + 1] == _OLD_DEFAULT_PROFILE + "(deny process-fork)"
    assert argv[-2:] == ["/bin/echo", "x"]
    bare = build_seatbelt_argv(["/bin/echo"], [], [], allow_network=True, allow_process_fork=False)
    assert bare[2] == '(version 1)(allow default)(deny file-write*)(allow file-write* (literal "/dev/null"))(deny process-fork)'


@pytest.mark.parametrize("bad", [0, 1, None, "False", 0.0])
def test_non_bool_allow_process_fork_rejected(bad: object) -> None:
    with pytest.raises(ValueError, match="ERR_ALLOW_PROCESS_FORK_NOT_BOOL"):
        build_seatbelt_argv(["/bin/echo"], ["/tmp"], [], allow_process_fork=bad)  # type: ignore[arg-type]


_FORK_CHILD = r'''
import os, subprocess, sys
op = sys.argv[1]
try:
    if op == "pure":
        assert sum(i * i for i in range(100000)) == 333328333350000
    elif op == "fork":
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
    elif op == "subprocess":
        subprocess.run(["/usr/bin/true"], capture_output=True, check=True)
    elif op == "posix_spawn":
        pid = os.posix_spawn("/usr/bin/true", ["/usr/bin/true"], {})
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
    print("OK")
except BaseException as exc:
    print("ERR:" + type(exc).__name__)
'''


@requires_seatbelt
def test_deny_process_fork_blocks_fork_and_spawn_but_child_runs(tmp_path: Path) -> None:
    for op in ("fork", "subprocess", "posix_spawn"):
        cmd = [sys.executable, "-I", "-c", _FORK_CHILD, op]
        # Control: the default profile still lets the child fork/spawn.
        assert _run(build_seatbelt_argv(cmd, [str(tmp_path)], [])) == "OK", op
        denied = build_seatbelt_argv(cmd, [str(tmp_path)], [], allow_process_fork=False)
        assert _run(denied) == "ERR:PermissionError", op
    # The interpreter itself still starts (exec is not fork) and computes.
    pure = build_seatbelt_argv([sys.executable, "-I", "-c", _FORK_CHILD, "pure"], [str(tmp_path)], [], allow_process_fork=False)
    assert _run(pure) == "OK"


def test_seatbelt_available_checks_executable_file(tmp_path: Path) -> None:
    assert seatbelt_available(str(tmp_path / "missing")) is False
    assert seatbelt_available(str(tmp_path)) is False  # a directory
    plain = tmp_path / "plain"
    plain.write_text("#!/bin/sh\n")
    plain.chmod(0o644)
    assert seatbelt_available(str(plain)) is False
    if sys.platform == "darwin":
        plain.chmod(0o755)
        assert seatbelt_available(str(plain)) is True
        assert seatbelt_available() is os.path.isfile(SANDBOX_EXEC_PATH)
    else:
        assert seatbelt_available() is False
    # Non-darwin platforms are never reported available, even for an executable file.
    plain.chmod(0o755)
    assert seatbelt_available(str(plain), platform="linux") is False
    assert seatbelt_available(str(plain), platform="darwin") is True


def test_symlink_resolving_to_newline_path_rejected(tmp_path: Path) -> None:
    evil_target = tmp_path / "evil\ndir"
    evil_target.mkdir()
    link = tmp_path / "innocent"
    link.symlink_to(evil_target, target_is_directory=True)
    with pytest.raises(ValueError, match="ERR_PATH_NOT_SAFE_FOR_SBPL"):
        build_seatbelt_argv(["/bin/echo"], [str(link)], [])
    cr_target = tmp_path / "evil\rdir"
    cr_target.mkdir()
    cr_link = tmp_path / "innocent_cr"
    cr_link.symlink_to(cr_target, target_is_directory=True)
    with pytest.raises(ValueError, match="ERR_PATH_NOT_SAFE_FOR_SBPL"):
        build_seatbelt_argv(["/bin/echo"], [], [str(cr_link)])


def test_sensitive_home_deny_roots_keeps_interpreter_paths_readable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".ssh").mkdir()
    (home / ".gnupg").mkdir()
    (home / ".netrc").write_text("machine x")
    (home / "Library" / "Keychains").mkdir(parents=True)
    # .config contains a (pretend) interpreter prefix -> must stay readable.
    (home / ".config" / "py" / "bin").mkdir(parents=True)
    # .aws is a symlink -> its realpath target is denied.
    aws_target = tmp_path / "aws_real"
    aws_target.mkdir()
    (home / ".aws").symlink_to(aws_target, target_is_directory=True)
    # .docker exists and equals a keep path -> skipped.
    (home / ".docker").mkdir()
    # A sibling whose name only shares a prefix with .ssh must not shield .ssh.
    (home / ".ssh-other").mkdir()
    # .kube is absent -> not listed.

    keep = [
        str(home / ".config" / "py" / "bin" / "python3"),
        str(home / ".docker"),
        str(home / ".ssh-other" / "x"),
    ]
    roots = sensitive_home_deny_roots(str(home), keep)
    rh = os.path.realpath(home)
    assert roots == sorted([
        os.path.realpath(aws_target),
        os.path.join(rh, ".gnupg"),
        os.path.join(rh, ".netrc"),
        os.path.join(rh, ".ssh"),
        os.path.join(rh, "Library", "Keychains"),
    ])
    # Without keep paths, .config and .docker are denied too.
    all_roots = sensitive_home_deny_roots(str(home), [])
    assert os.path.join(rh, ".config") in all_roots
    assert os.path.join(rh, ".docker") in all_roots
    assert len(all_roots) == 7
    # A broken symlink still counts as existing (lexists) and is denied.
    (home / ".kube").symlink_to(tmp_path / "nowhere")
    assert os.path.realpath(home / ".kube") in sensitive_home_deny_roots(str(home), [])
    assert ".ssh" in SENSITIVE_HOME_ENTRIES and os.path.join("Library", "Keychains") in SENSITIVE_HOME_ENTRIES
