#!/usr/bin/env python3
"""
src/package_install_gate.py - Agent package-install gate (slopsquatting control).

Prototype control. An agent-proposed package-manager invocation (argv list,
never a shell string) is parsed locally and permitted only when every
requested package is present, at an exact pinned version, in an allowlist
built from lockfiles that already exist in the workspace.

Threat basis (as reported, see docs/security/AGENT_ACTION_CONTROLS.md):
LLM-recommended package names that do not exist ("package hallucination" /
slopsquatting) can be registered by an attacker; typosquat-like names,
unpinned versions, URL/VCS/path installs and index overrides are other
routes to installing code that was never reviewed.

Scope under the stated model:
  * pip / pip3 / pipX.Y / python -m pip / uv pip install / uv add /
    poetry add / npm i|install|add / pnpm add|install|i / yarn add /
    cargo add / cargo install.
  * Lockfiles parsed with the stdlib only: requirements*.txt (== pins),
    poetry.lock, uv.lock, Cargo.lock (tomllib), package-lock.json (json).
  * Commands not recognised as an install are reported NOT_APPLICABLE; the
    caller decides what to do with them. Anything recognised as an install
    that cannot be parsed is denied (fail closed).

No network access is performed; nothing here contacts a registry.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


class InstallDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# Typed reason codes.
PKG_ALLOWED = "PKG_ALLOWED"
PKG_NOT_AN_INSTALL_COMMAND = "PKG_NOT_AN_INSTALL_COMMAND"
ERR_SHELL_STRING_REJECTED = "ERR_SHELL_STRING_REJECTED"
ERR_SHELL_METACHARACTER = "ERR_SHELL_METACHARACTER"
ERR_EMPTY_ARGV = "ERR_EMPTY_ARGV"
ERR_PARSE_ERROR = "ERR_PARSE_ERROR"
ERR_NO_PACKAGES_SPECIFIED = "ERR_NO_PACKAGES_SPECIFIED"
ERR_UNSUPPORTED_OPTION = "ERR_UNSUPPORTED_OPTION"
ERR_INDEX_OVERRIDE = "ERR_INDEX_OVERRIDE"
ERR_URL_VCS_PATH_INSTALL = "ERR_URL_VCS_PATH_INSTALL"
ERR_INVALID_PACKAGE_NAME = "ERR_INVALID_PACKAGE_NAME"
ERR_TYPOSQUAT_SUSPECTED = "ERR_TYPOSQUAT_SUSPECTED"
ERR_UNKNOWN_PACKAGE = "ERR_UNKNOWN_PACKAGE"
ERR_UNPINNED_VERSION = "ERR_UNPINNED_VERSION"
ERR_VERSION_NOT_IN_LOCKFILE = "ERR_VERSION_NOT_IN_LOCKFILE"

PYPI = "pypi"
NPM = "npm"
CARGO = "cargo"

# Characters that only carry meaning to a shell. argv elements containing
# them indicate the caller tried to smuggle a shell construct.
_SHELL_METACHARS = frozenset(";|&`$\n\r\x00")

_PEP508_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_NPM_NAME = re.compile(r"^(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$")
_CARGO_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_EXACT_SEMVER = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
# PEP 440 public version, permissive but operator-free.
_PEP440_EXACT = re.compile(r"^[0-9]+(?:\.[0-9]+)*(?:[A-Za-z0-9.+!-]*)$")
_PYTHON_EXE = re.compile(r"^python(?:\d+(?:\.\d+)?)?$")
_PIP_EXE = re.compile(r"^pip(?:\d+(?:\.\d+)?)?$")

_URLISH_PREFIXES = (
    "http://", "https://", "git+", "git:", "git@", "hg+", "svn+", "bzr+",
    "file:", "link:", "portal:", "npm:", "github:", "gitlab:", "bitbucket:",
    "./", "../", "/", "~", ".\\",
)
_ARCHIVE_SUFFIXES = (".whl", ".tar.gz", ".tgz", ".zip", ".tar.bz2", ".crate")


class LockfileParseError(ValueError):
    """Raised (fail closed) when a lockfile exists but cannot be parsed."""


def normalize_name(ecosystem: str, name: str) -> str:
    """Registry-equivalence normalisation used for allowlist comparison."""
    if ecosystem == PYPI:
        return re.sub(r"[-_.]+", "-", name).lower()
    if ecosystem == CARGO:
        return name.replace("_", "-").lower()
    return name.lower()


def damerau_levenshtein(a: str, b: str) -> int:
    """Optimal-string-alignment Damerau-Levenshtein distance."""
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


@dataclass(frozen=True)
class PinnedAllowlist:
    """ecosystem -> normalised name -> frozenset of exact versions."""

    entries: Mapping[str, Mapping[str, FrozenSet[str]]]
    sources: Tuple[str, ...] = ()

    def versions(self, ecosystem: str, name: str) -> Optional[FrozenSet[str]]:
        return self.entries.get(ecosystem, {}).get(normalize_name(ecosystem, name))

    def names(self, ecosystem: str) -> Iterable[str]:
        return self.entries.get(ecosystem, {}).keys()

    @staticmethod
    def from_pins(pins: Mapping[str, Iterable[Tuple[str, str]]]) -> "PinnedAllowlist":
        acc: Dict[str, Dict[str, Set[str]]] = {}
        for eco, pairs in pins.items():
            for name, version in pairs:
                acc.setdefault(eco, {}).setdefault(normalize_name(eco, name), set()).add(version)
        return PinnedAllowlist(
            {e: {n: frozenset(v) for n, v in m.items()} for e, m in acc.items()}
        )


# --------------------------------------------------------------------------
# Lockfile parsers (stdlib only, fail closed)
# --------------------------------------------------------------------------

def _parse_requirements(text: str) -> List[Tuple[str, str]]:
    pins: List[Tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip().rstrip("\\").strip()
        if not line:
            continue
        spec = line.split(";", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*==\s*([^\s,]+)$", spec)
        if m:
            pins.append((m.group(1), m.group(2)))
    return pins


def _parse_toml_packages(text: str) -> List[Tuple[str, str]]:
    data = tomllib.loads(text)
    pkgs = data.get("package", [])
    if not isinstance(pkgs, list):
        raise LockfileParseError("[[package]] is not an array")
    out: List[Tuple[str, str]] = []
    for pkg in pkgs:
        if not isinstance(pkg, dict) or not isinstance(pkg.get("name"), str) or not isinstance(pkg.get("version"), str):
            raise LockfileParseError("package entry lacks string name/version")
        out.append((pkg["name"], pkg["version"]))
    return out


def _parse_package_lock(text: str) -> List[Tuple[str, str]]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise LockfileParseError("package-lock root is not an object")
    out: List[Tuple[str, str]] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for key, meta in packages.items():
            if not key or not isinstance(meta, dict):
                continue
            name = meta.get("name") or key.rsplit("node_modules/", 1)[-1]
            version = meta.get("version")
            if isinstance(version, str) and isinstance(name, str) and not meta.get("link"):
                out.append((name, version))
        return out
    deps = data.get("dependencies")
    if isinstance(deps, dict):  # lockfileVersion 1
        stack = list(deps.items())
        while stack:
            name, meta = stack.pop()
            if isinstance(meta, dict):
                if isinstance(meta.get("version"), str):
                    out.append((name, meta["version"]))
                nested = meta.get("dependencies")
                if isinstance(nested, dict):
                    stack.extend(nested.items())
        return out
    raise LockfileParseError("package-lock has neither 'packages' nor 'dependencies'")


def build_allowlist_from_lockfiles(paths: Sequence[str]) -> PinnedAllowlist:
    """Parse the given lockfiles. Any unreadable/unparseable file raises."""
    acc: Dict[str, List[Tuple[str, str]]] = {}
    used: List[str] = []
    for path in paths:
        base = os.path.basename(path)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            if base.startswith("requirements") and base.endswith(".txt"):
                eco, pins = PYPI, _parse_requirements(text)
            elif base in ("poetry.lock", "uv.lock"):
                eco, pins = PYPI, _parse_toml_packages(text)
            elif base == "Cargo.lock":
                eco, pins = CARGO, _parse_toml_packages(text)
            elif base == "package-lock.json":
                eco, pins = NPM, _parse_package_lock(text)
            else:
                raise LockfileParseError(f"unsupported lockfile type: {base}")
        except LockfileParseError:
            raise
        except (OSError, UnicodeDecodeError, ValueError, tomllib.TOMLDecodeError) as exc:
            raise LockfileParseError(f"{path}: {exc}") from exc
        acc.setdefault(eco, []).extend(pins)
        used.append(path)
    allow = PinnedAllowlist.from_pins(acc)
    return PinnedAllowlist(allow.entries, tuple(used))


def discover_lockfiles(workspace_root: str) -> List[str]:
    """Top-level lockfiles in workspace_root (no recursion)."""
    found = []
    for entry in sorted(os.listdir(workspace_root)):
        full = os.path.join(workspace_root, entry)
        if not os.path.isfile(full):
            continue
        if (entry.startswith("requirements") and entry.endswith(".txt")) or entry in (
            "poetry.lock", "uv.lock", "Cargo.lock", "package-lock.json",
        ):
            found.append(full)
    return found


# --------------------------------------------------------------------------
# Command parsing
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _ManagerSpec:
    ecosystem: str
    manager: str
    bool_flags: FrozenSet[str]
    value_flags: FrozenSet[str]
    index_flags: FrozenSet[str]
    source_flags: FrozenSet[str]  # URL/VCS/path selectors (may take a value)
    source_bool_flags: FrozenSet[str] = frozenset()
    pinned_by_bare_version: bool = True  # cargo add requires '=' prefix


_PIP = _ManagerSpec(
    PYPI, "pip",
    bool_flags=frozenset({"-q", "--quiet", "-v", "--verbose", "-U", "--upgrade",
                          "--user", "--no-deps", "--dry-run", "--require-hashes",
                          "--no-cache-dir", "--only-binary=:all:", "--system"}),
    value_flags=frozenset(),
    index_flags=frozenset({"-i", "--index-url", "--extra-index-url", "--find-links",
                           "-f", "--trusted-host", "--index", "--default-index",
                           "--no-index"}),
    source_flags=frozenset({"-e", "--editable", "-r", "--requirement", "-c",
                            "--constraint"}),
)
_UV_ADD = _ManagerSpec(
    PYPI, "uv add",
    bool_flags=frozenset({"-q", "--quiet", "-v", "--verbose", "--dev", "--frozen",
                          "--locked", "--no-sync", "--dry-run"}),
    value_flags=frozenset({"--group", "--optional"}),
    index_flags=frozenset({"--index", "--index-url", "--extra-index-url",
                           "--default-index", "--find-links", "-f", "--no-index"}),
    source_flags=frozenset({"--editable", "-r", "--requirements", "--path",
                            "--git", "--branch", "--tag", "--rev", "-e"}),
)
_POETRY_ADD = _ManagerSpec(
    PYPI, "poetry add",
    bool_flags=frozenset({"-q", "--quiet", "-v", "--verbose", "-D", "--dev",
                          "--dry-run", "--lock", "-n", "--no-interaction"}),
    value_flags=frozenset({"-G", "--group", "-E", "--extras"}),
    index_flags=frozenset({"--source"}),
    source_flags=frozenset(),
    source_bool_flags=frozenset({"-e", "--editable"}),
)
_NPM = _ManagerSpec(
    NPM, "npm",
    bool_flags=frozenset({"-D", "--save-dev", "-E", "--save-exact", "-O",
                          "--save-optional", "--no-save", "--ignore-scripts",
                          "--dry-run", "-S", "--save", "--silent", "--dev",
                          "--exact", "--prefer-offline", "--offline"}),
    value_flags=frozenset(),
    index_flags=frozenset({"--registry"}),
    source_flags=frozenset(),
)
_CARGO_ADD = _ManagerSpec(
    CARGO, "cargo add",
    bool_flags=frozenset({"-q", "--quiet", "-v", "--verbose", "--dev", "--build",
                          "--dry-run", "--locked", "--offline", "--frozen",
                          "--no-default-features"}),
    value_flags=frozenset({"-F", "--features", "-p", "--package", "--target"}),
    index_flags=frozenset({"--registry", "--index"}),
    source_flags=frozenset({"--git", "--path", "--branch", "--tag", "--rev"}),
    pinned_by_bare_version=False,
)
_CARGO_INSTALL = _ManagerSpec(
    CARGO, "cargo install",
    bool_flags=frozenset({"-q", "--quiet", "-v", "--verbose", "--locked",
                          "--offline", "--frozen", "--force", "-f",
                          "--no-default-features"}),
    value_flags=frozenset({"-F", "--features", "--version", "--vers", "--target",
                           "--root"}),
    index_flags=frozenset({"--registry", "--index"}),
    source_flags=frozenset({"--git", "--path", "--branch", "--tag", "--rev"}),
)


def _identify(argv: Sequence[str]) -> Optional[Tuple[_ManagerSpec, int]]:
    """Return (spec, index of first argument after the install subcommand) or None."""
    # Case-folded and '.exe'-stripped: on case-insensitive filesystems
    # 'PIP' or 'pip.exe' launch the same installer.
    exe = os.path.basename(argv[0].replace("\\", "/")).casefold()
    if exe.endswith(".exe"):
        exe = exe[:-4]
    rest = list(argv[1:])
    if _PYTHON_EXE.match(exe):
        if rest[:3] == ["-m", "pip", "install"]:
            return _PIP, 4
        return None
    if _PIP_EXE.match(exe):
        return (_PIP, 2) if rest[:1] == ["install"] else None
    if exe == "uv":
        if rest[:2] == ["pip", "install"]:
            return _PIP, 3
        if rest[:1] == ["add"]:
            return _UV_ADD, 2
        return None
    if exe == "poetry":
        return (_POETRY_ADD, 2) if rest[:1] == ["add"] else None
    if exe == "npm":
        return (_NPM, 2) if rest[:1] and rest[0] in ("i", "install", "add") else None
    if exe == "pnpm":
        return (_NPM, 2) if rest[:1] and rest[0] in ("add", "install", "i") else None
    if exe == "yarn":
        return (_NPM, 2) if rest[:1] == ["add"] else None
    if exe == "cargo":
        if rest[:1] == ["add"]:
            return _CARGO_ADD, 2
        if rest[:1] == ["install"]:
            return _CARGO_INSTALL, 2
    return None


def _looks_like_source(spec: str) -> bool:
    low = spec.lower()
    if "://" in low or low.startswith(_URLISH_PREFIXES):
        return True
    if low.endswith(_ARCHIVE_SUFFIXES):
        return True
    if re.search(r"\s@\s*\S", spec):
        return True  # PEP 508 direct reference "name @ url"
    return False


@dataclass(frozen=True)
class RequestedPackage:
    raw: str
    ecosystem: str
    name: str
    version: Optional[str]


@dataclass(frozen=True)
class PackageFinding:
    spec: str
    reason_code: str
    detail: str


@dataclass(frozen=True)
class InstallGateResult:
    decision: InstallDecision
    reason_code: str
    manager: Optional[str] = None
    packages: Tuple[RequestedPackage, ...] = ()
    findings: Tuple[PackageFinding, ...] = field(default_factory=tuple)

    @property
    def allowed(self) -> bool:
        return self.decision is InstallDecision.ALLOW


def _split_pypi(spec: str, mspec: _ManagerSpec) -> Tuple[str, Optional[str], Optional[str]]:
    """Return (name, exact_version or None, error_code or None)."""
    body = spec
    if ";" in body:
        return body, None, ERR_PARSE_ERROR
    m = re.match(r"^([^\[\]=<>!~@\s]+)(\[[A-Za-z0-9,._-]*\])?(.*)$", body)
    if not m:
        return body, None, ERR_INVALID_PACKAGE_NAME
    name, rest = m.group(1), m.group(3).strip()
    if not rest:
        return name, None, None
    if rest.startswith("==") and not rest.startswith("==="):
        ver = rest[2:].strip()
        if ver and "*" not in ver and _PEP440_EXACT.match(ver):
            return name, ver, None
        return name, None, None
    if mspec is _POETRY_ADD and rest.startswith("@"):
        ver = rest[1:].strip()
        if ver.startswith("=="):
            ver = ver[2:].strip()
        if ver and _PEP440_EXACT.match(ver):
            return name, ver, None
        return name, None, None
    if re.match(r"^(?:===|==|!=|~=|>=|<=|>|<)", rest):
        return name, None, None  # any other PEP 440 operator => unpinned
    return name, None, ERR_INVALID_PACKAGE_NAME


def _split_npm(spec: str) -> Tuple[str, Optional[str], Optional[str]]:
    scoped = spec.startswith("@")
    body = spec[1:] if scoped else spec
    if "@" in body:
        name_part, ver = body.split("@", 1)
    else:
        name_part, ver = body, None
    name = ("@" if scoped else "") + name_part
    if not scoped and "/" in name:
        return name, None, ERR_URL_VCS_PATH_INSTALL  # github shorthand user/repo
    if ver is None or ver == "":
        return name, None, None
    if _EXACT_SEMVER.match(ver.lstrip("=")) and not ver.startswith("=="):
        return name, ver.lstrip("="), None
    return name, None, None


def _split_cargo(spec: str, mspec: _ManagerSpec) -> Tuple[str, Optional[str], Optional[str]]:
    if "@" not in spec:
        return spec, None, None
    name, ver = spec.split("@", 1)
    return name, _cargo_exact(ver, mspec), None


def _cargo_exact(ver: str, mspec: _ManagerSpec) -> Optional[str]:
    """'=X.Y.Z' is exact everywhere; bare 'X.Y.Z' is exact only for cargo install."""
    if ver.startswith("="):
        core = ver[1:].strip()
    else:
        core = ver if mspec.pinned_by_bare_version else ""
    return core if _EXACT_SEMVER.match(core) else None


def _valid_name(ecosystem: str, name: str) -> bool:
    if ecosystem == PYPI:
        return bool(_PEP508_NAME.match(name))
    if ecosystem == NPM:
        return bool(_NPM_NAME.match(name))
    return bool(_CARGO_NAME.match(name))


class PackageInstallGate:
    """Deny-by-default install gate backed by a lockfile-derived allowlist."""

    def __init__(self, allowlist: PinnedAllowlist) -> None:
        if not isinstance(allowlist, PinnedAllowlist):
            raise TypeError("allowlist must be a PinnedAllowlist")
        self.allowlist = allowlist

    @classmethod
    def from_workspace(cls, workspace_root: str) -> "PackageInstallGate":
        return cls(build_allowlist_from_lockfiles(discover_lockfiles(workspace_root)))

    # ---------------------------------------------------------------
    def evaluate(self, command_argv: Sequence[str]) -> InstallGateResult:
        if isinstance(command_argv, (str, bytes)):
            return InstallGateResult(InstallDecision.DENY, ERR_SHELL_STRING_REJECTED)
        try:
            argv = list(command_argv)
        except TypeError:
            return InstallGateResult(InstallDecision.DENY, ERR_PARSE_ERROR)
        if not argv:
            return InstallGateResult(InstallDecision.DENY, ERR_EMPTY_ARGV)
        if not all(isinstance(a, str) for a in argv):
            return InstallGateResult(InstallDecision.DENY, ERR_PARSE_ERROR)
        for a in argv:
            if any(ch in _SHELL_METACHARS for ch in a):
                return InstallGateResult(
                    InstallDecision.DENY, ERR_SHELL_METACHARACTER,
                    findings=(PackageFinding(a, ERR_SHELL_METACHARACTER, "shell metacharacter in argv"),),
                )
        match = _identify(argv)
        if match is None:
            return InstallGateResult(InstallDecision.NOT_APPLICABLE, PKG_NOT_AN_INSTALL_COMMAND)
        mspec, start = match
        return self._evaluate_install(mspec, argv[start:])

    # ---------------------------------------------------------------
    def _evaluate_install(self, mspec: _ManagerSpec, args: List[str]) -> InstallGateResult:
        findings: List[PackageFinding] = []
        specs: List[str] = []
        cargo_version: Optional[str] = None
        i = 0
        while i < len(args):
            tok = args[i]
            if tok == "--":
                specs.extend(args[i + 1:])
                break
            if tok.startswith("-") and tok != "-":
                flag, has_eq, value = tok.partition("=")
                if tok in mspec.bool_flags:
                    i += 1
                    continue
                if flag in mspec.index_flags:
                    findings.append(PackageFinding(tok, ERR_INDEX_OVERRIDE, "package index/registry override"))
                    i += 1 if (has_eq or flag == "--no-index") else 2
                    continue
                if flag in mspec.source_flags:
                    findings.append(PackageFinding(tok, ERR_URL_VCS_PATH_INSTALL, "URL/VCS/path/file source selector"))
                    i += 1 if has_eq else 2
                    continue
                if flag in mspec.source_bool_flags:
                    findings.append(PackageFinding(tok, ERR_URL_VCS_PATH_INSTALL, "editable/path install"))
                    i += 1
                    continue
                if flag in mspec.value_flags:
                    if not has_eq:
                        if i + 1 >= len(args):
                            findings.append(PackageFinding(tok, ERR_PARSE_ERROR, "option missing value"))
                            break
                        value = args[i + 1]
                        i += 1
                    if mspec is _CARGO_INSTALL and flag in ("--version", "--vers"):
                        cargo_version = value
                    i += 1
                    continue
                findings.append(PackageFinding(tok, ERR_UNSUPPORTED_OPTION, "option not on the reviewed list"))
                i += 1
                continue
            specs.append(tok)
            i += 1

        packages: List[RequestedPackage] = []
        for spec in specs:
            pkg, finding = self._evaluate_spec(mspec, spec, cargo_version)
            if pkg is not None:
                packages.append(pkg)
            if finding is not None:
                findings.append(finding)

        if not specs and not findings:
            findings.append(PackageFinding("", ERR_NO_PACKAGES_SPECIFIED, "install without explicit packages"))
        if findings:
            return InstallGateResult(InstallDecision.DENY, findings[0].reason_code,
                                     mspec.manager, tuple(packages), tuple(findings))
        return InstallGateResult(InstallDecision.ALLOW, PKG_ALLOWED, mspec.manager, tuple(packages))

    def _evaluate_spec(self, mspec: _ManagerSpec, spec: str,
                       cargo_version: Optional[str]) -> Tuple[Optional[RequestedPackage], Optional[PackageFinding]]:
        eco = mspec.ecosystem
        if not spec or _looks_like_source(spec):
            return None, PackageFinding(spec, ERR_URL_VCS_PATH_INSTALL, "URL/VCS/path/archive spec")
        if eco == PYPI:
            name, version, err = _split_pypi(spec, mspec)
        elif eco == NPM:
            name, version, err = _split_npm(spec)
        else:
            name, version, err = _split_cargo(spec, mspec)
            if version is None and "@" not in spec and cargo_version is not None:
                version = _cargo_exact(cargo_version, mspec)
        if err is not None:
            return None, PackageFinding(spec, err, "could not parse package spec")
        if not _valid_name(eco, name):
            return None, PackageFinding(spec, ERR_INVALID_PACKAGE_NAME, "name fails registry grammar")
        pkg = RequestedPackage(spec, eco, normalize_name(eco, name), version)
        versions = self.allowlist.versions(eco, name)
        if versions is None:
            near = self._nearest_allowlisted(eco, pkg.name)
            if near is not None:
                return pkg, PackageFinding(spec, ERR_TYPOSQUAT_SUSPECTED,
                                           f"distance 1 from allowlisted {near!r}")
            return pkg, PackageFinding(spec, ERR_UNKNOWN_PACKAGE, "name not in lockfile allowlist")
        if version is None:
            return pkg, PackageFinding(spec, ERR_UNPINNED_VERSION, "exact version pin required")
        if version not in versions:
            return pkg, PackageFinding(spec, ERR_VERSION_NOT_IN_LOCKFILE,
                                       f"locked versions: {sorted(versions)}")
        return pkg, None

    def _nearest_allowlisted(self, eco: str, norm_name: str) -> Optional[str]:
        for known in sorted(self.allowlist.names(eco)):
            # Only reached for names absent from the allowlist, so distance 0
            # is impossible here; distance exactly 1 is the lookalike signal.
            if damerau_levenshtein(known, norm_name) == 1:
                return known
        return None
