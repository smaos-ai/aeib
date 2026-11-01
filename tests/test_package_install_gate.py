"""Tests for src/package_install_gate.py (lockfile-pinned install gate)."""

import json

import pytest

from src import package_install_gate as g
from src.package_install_gate import (
    CARGO, NPM, PYPI, InstallDecision, LockfileParseError, PackageInstallGate,
    PinnedAllowlist, build_allowlist_from_lockfiles, damerau_levenshtein,
    discover_lockfiles, normalize_name,
)


@pytest.fixture()
def gate():
    allow = PinnedAllowlist.from_pins({
        PYPI: [("requests", "2.31.0"), ("Typing_Extensions", "4.9.0"), ("numpy", "1.26.4")],
        NPM: [("lodash", "4.17.21"), ("@types/node", "20.11.5")],
        CARGO: [("serde", "1.0.197"), ("tokio", "1.36.0")],
    })
    return PackageInstallGate(allow)


def _codes(res):
    return [f.reason_code for f in res.findings]


# ---------------------------------------------------------------- allow path
@pytest.mark.parametrize("argv", [
    ["pip", "install", "requests==2.31.0"],
    ["pip3", "install", "-q", "requests==2.31.0"],
    ["/usr/bin/pip3.12", "install", "requests==2.31.0"],
    ["python3", "-m", "pip", "install", "requests==2.31.0"],
    ["python", "-m", "pip", "install", "requests[socks]==2.31.0"],
    ["uv", "pip", "install", "requests==2.31.0"],
    ["uv", "add", "--dev", "requests==2.31.0"],
    ["uv", "add", "--group", "lint", "requests==2.31.0"],
    ["uv", "add", "--group=lint", "requests==2.31.0"],
    ["poetry", "add", "requests@2.31.0"],
    ["poetry", "add", "requests@==2.31.0"],
    ["poetry", "add", "requests==2.31.0"],
    ["pip", "install", "typing-extensions==4.9.0"],
    ["pip", "install", "TYPING.extensions==4.9.0"],
    ["npm", "i", "lodash@4.17.21"],
    ["npm", "install", "-D", "lodash@4.17.21"],
    ["npm", "add", "lodash@=4.17.21"],
    ["pnpm", "add", "@types/node@20.11.5"],
    ["yarn", "add", "lodash@4.17.21"],
    ["cargo", "add", "serde@=1.0.197"],
    ["cargo", "add", "-F", "derive", "serde@=1.0.197"],
    ["cargo", "install", "tokio@1.36.0"],
    ["cargo", "install", "tokio", "--version", "1.36.0"],
    ["cargo", "install", "tokio", "--version=1.36.0"],
    ["cargo", "install", "tokio", "--version", "=1.36.0"],
    ["pip", "install", "--", "requests==2.31.0"],
])
def test_allowed(gate, argv):
    res = gate.evaluate(argv)
    assert res.decision is InstallDecision.ALLOW, res
    assert res.reason_code == g.PKG_ALLOWED
    assert res.allowed is True
    assert res.findings == ()
    assert len(res.packages) == 1


def test_allowed_records_package_details(gate):
    res = gate.evaluate(["pip", "install", "Typing_Extensions==4.9.0", "numpy==1.26.4"])
    assert res.allowed
    assert res.manager == "pip"
    assert [(p.name, p.version, p.ecosystem) for p in res.packages] == [
        ("typing-extensions", "4.9.0", PYPI), ("numpy", "1.26.4", PYPI)]
    assert res.packages[0].raw == "Typing_Extensions==4.9.0"


@pytest.mark.parametrize("argv,manager", [
    (["uv", "add", "requests==2.31.0"], "uv add"),
    (["poetry", "add", "requests==2.31.0"], "poetry add"),
    (["yarn", "add", "lodash@4.17.21"], "npm"),
    (["cargo", "add", "serde@=1.0.197"], "cargo add"),
    (["cargo", "install", "tokio@1.36.0"], "cargo install"),
])
def test_manager_identified(gate, argv, manager):
    assert gate.evaluate(argv).manager == manager


# ------------------------------------------------------------ not applicable
@pytest.mark.parametrize("argv", [
    ["ls", "-la"], ["pip", "list"], ["pip", "--version"], ["python3", "script.py"],
    ["python3", "-m", "pip", "list"], ["python3", "-m", "venv", "install"],
    ["python3", "-c", "pip", "install"],
    ["uv", "run", "pytest"], ["uv", "pip", "list"], ["poetry", "install"],
    ["npm", "ci"], ["npm", "run", "install"], ["pnpm", "run", "x"], ["yarn", "install"],
    ["cargo", "build"], ["cargo", "test"], ["pip"], ["uv"], ["npm"], ["pnpm"],
])
def test_not_applicable(gate, argv):
    res = gate.evaluate(argv)
    assert res.decision is InstallDecision.NOT_APPLICABLE
    assert res.reason_code == g.PKG_NOT_AN_INSTALL_COMMAND
    assert res.allowed is False


# ------------------------------------------------------------------ deny path
@pytest.mark.parametrize("argv,code", [
    (["pip", "install", "requests"], g.ERR_UNPINNED_VERSION),
    (["pip", "install", "requests>=2.0"], g.ERR_UNPINNED_VERSION),
    (["pip", "install", "requests~=2.31"], g.ERR_UNPINNED_VERSION),
    (["pip", "install", "requests===2.31.0"], g.ERR_UNPINNED_VERSION),
    (["pip", "install", "requests==2.*"], g.ERR_UNPINNED_VERSION),
    (["pip", "install", "requests=="], g.ERR_UNPINNED_VERSION),
    (["poetry", "add", "requests@^2.31.0"], g.ERR_UNPINNED_VERSION),
    (["poetry", "add", "requests@latest"], g.ERR_UNPINNED_VERSION),
    (["poetry", "add", "requests@"], g.ERR_UNPINNED_VERSION),
    (["npm", "i", "lodash"], g.ERR_UNPINNED_VERSION),
    (["npm", "i", "lodash@^4.17.21"], g.ERR_UNPINNED_VERSION),
    (["npm", "i", "lodash@latest"], g.ERR_UNPINNED_VERSION),
    (["npm", "i", "lodash@"], g.ERR_UNPINNED_VERSION),
    (["npm", "i", "lodash@==4.17.21"], g.ERR_UNPINNED_VERSION),
    (["npm", "i", "lodash@4.17"], g.ERR_UNPINNED_VERSION),
    (["cargo", "add", "serde@1.0.197"], g.ERR_UNPINNED_VERSION),
    (["cargo", "add", "serde"], g.ERR_UNPINNED_VERSION),
    (["cargo", "add", "serde@=1.0"], g.ERR_UNPINNED_VERSION),
    (["cargo", "install", "tokio@^1.36.0"], g.ERR_UNPINNED_VERSION),
    (["cargo", "install", "tokio", "--version", "~1.36"], g.ERR_UNPINNED_VERSION),
    (["pip", "install", "requests==2.30.0"], g.ERR_VERSION_NOT_IN_LOCKFILE),
    (["npm", "i", "lodash@4.17.20"], g.ERR_VERSION_NOT_IN_LOCKFILE),
    (["cargo", "add", "serde@=1.0.196"], g.ERR_VERSION_NOT_IN_LOCKFILE),
    (["pip", "install", "huggingface-cli==0.1.0"], g.ERR_UNKNOWN_PACKAGE),
    (["npm", "i", "react-codeshift@1.0.0"], g.ERR_UNKNOWN_PACKAGE),
    (["cargo", "add", "rand@=0.8.5"], g.ERR_UNKNOWN_PACKAGE),
    (["pip", "install", "reqeusts==2.31.0"], g.ERR_TYPOSQUAT_SUSPECTED),
    (["pip", "install", "request==2.31.0"], g.ERR_TYPOSQUAT_SUSPECTED),
    (["pip", "install", "requestss==2.31.0"], g.ERR_TYPOSQUAT_SUSPECTED),
    (["pip", "install", "nunpy==1.26.4"], g.ERR_TYPOSQUAT_SUSPECTED),
    (["npm", "i", "lodahs@4.17.21"], g.ERR_TYPOSQUAT_SUSPECTED),
    (["cargo", "add", "serd@=1.0.197"], g.ERR_TYPOSQUAT_SUSPECTED),
    (["pip", "install", "git+https://github.com/x/requests"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "https://evil.example/requests-2.31.0.tar.gz"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "./local_pkg"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "/abs/pkg"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "requests-2.31.0-py3-none-any.whl"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "requests @ https://evil.example/r.whl"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "requests@https://evil.example/r"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "-e", "."], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "--editable=.", "requests==2.31.0"], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "-r", "requirements.txt"], g.ERR_URL_VCS_PATH_INSTALL),
    (["poetry", "add", "-e", "requests==2.31.0"], g.ERR_URL_VCS_PATH_INSTALL),
    (["npm", "i", "file:../x"], g.ERR_URL_VCS_PATH_INSTALL),
    (["npm", "i", "github:user/repo"], g.ERR_URL_VCS_PATH_INSTALL),
    (["npm", "i", "user/repo"], g.ERR_URL_VCS_PATH_INSTALL),
    (["npm", "i", "lodash@npm:evil@1.0.0"], g.ERR_UNPINNED_VERSION),
    (["npm", "i", "npm:lodash@4.17.21"], g.ERR_URL_VCS_PATH_INSTALL),
    (["npm", "i", "./pkg.tgz"], g.ERR_URL_VCS_PATH_INSTALL),
    (["cargo", "add", "--git", "https://github.com/x/serde", "serde"], g.ERR_URL_VCS_PATH_INSTALL),
    (["cargo", "install", "--path", "."], g.ERR_URL_VCS_PATH_INSTALL),
    (["pip", "install", "--index-url", "https://evil.example/simple", "requests==2.31.0"], g.ERR_INDEX_OVERRIDE),
    (["pip", "install", "--extra-index-url=https://evil.example/simple", "requests==2.31.0"], g.ERR_INDEX_OVERRIDE),
    (["pip", "install", "-i", "https://evil.example/simple", "requests==2.31.0"], g.ERR_INDEX_OVERRIDE),
    (["pip", "install", "--no-index", "requests==2.31.0"], g.ERR_INDEX_OVERRIDE),
    (["uv", "add", "--index", "https://evil.example", "requests==2.31.0"], g.ERR_INDEX_OVERRIDE),
    (["poetry", "add", "--source", "evil", "requests==2.31.0"], g.ERR_INDEX_OVERRIDE),
    (["npm", "i", "--registry", "https://evil.example", "lodash@4.17.21"], g.ERR_INDEX_OVERRIDE),
    (["yarn", "add", "--registry=https://evil.example", "lodash@4.17.21"], g.ERR_INDEX_OVERRIDE),
    (["cargo", "add", "--registry", "evil", "serde@=1.0.197"], g.ERR_INDEX_OVERRIDE),
    (["pip", "install", "--pre", "requests==2.31.0"], g.ERR_UNSUPPORTED_OPTION),
    (["npm", "i", "--force", "lodash@4.17.21"], g.ERR_UNSUPPORTED_OPTION),
    (["pip", "install"], g.ERR_NO_PACKAGES_SPECIFIED),
    (["npm", "install"], g.ERR_NO_PACKAGES_SPECIFIED),
    (["pip", "install", "requests;python_version>'3'"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "requests==2.31.0", "&&", "curl", "x"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "$(curl x)"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "`id`"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "a|b"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "a\nb"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "a\rb"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "a\x00b"], g.ERR_SHELL_METACHARACTER),
    (["pip", "install", "-req!==1"], g.ERR_UNSUPPORTED_OPTION),
    (["pip", "install", "re!q==1"], g.ERR_INVALID_PACKAGE_NAME),
    (["pip", "install", "-bad-"], g.ERR_UNSUPPORTED_OPTION),
    (["pip", "install", "bad-==1.0"], g.ERR_INVALID_PACKAGE_NAME),
    (["pip", "install", "[x]==1.0"], g.ERR_INVALID_PACKAGE_NAME),
    (["pip", "install", "requests@2.31.0"], g.ERR_INVALID_PACKAGE_NAME),
    (["poetry", "add", "requests^2.31.0"], g.ERR_INVALID_PACKAGE_NAME),
    (["npm", "i", "UPPER@1.0.0"], g.ERR_INVALID_PACKAGE_NAME),
    (["cargo", "add", "1serde@=1.0.0"], g.ERR_INVALID_PACKAGE_NAME),
    (["uv", "add", "--group"], g.ERR_PARSE_ERROR),
    (["pip", "install", ""], g.ERR_URL_VCS_PATH_INSTALL),
])
def test_denied(gate, argv, code):
    res = gate.evaluate(argv)
    assert res.decision is InstallDecision.DENY, res
    assert res.reason_code == code, res
    assert res.allowed is False


def test_environment_marker_is_parse_error_when_not_shell_char(gate):
    res = g.PackageInstallGate(gate.allowlist)._evaluate_spec(g._PIP, "requests==2.31.0 ;x", None)
    assert res[0] is None
    assert res[1].reason_code == g.ERR_PARSE_ERROR


def test_shell_string_rejected(gate):
    for cmd in ("pip install requests==2.31.0", b"pip install x", "pip install x; rm -rf /"):
        res = gate.evaluate(cmd)
        assert res.decision is InstallDecision.DENY
        assert res.reason_code == g.ERR_SHELL_STRING_REJECTED


def test_metachar_finding_reports_token(gate):
    res = gate.evaluate(["pip", "install", "a;b"])
    assert res.findings[0].spec == "a;b"
    assert res.findings[0].reason_code == g.ERR_SHELL_METACHARACTER


@pytest.mark.parametrize("bad", [[], None, 5, ["pip", "install", 3], ("pip", None)])
def test_malformed_argv_fail_closed(gate, bad):
    res = gate.evaluate(bad)
    assert res.decision is InstallDecision.DENY
    assert res.reason_code in (g.ERR_EMPTY_ARGV, g.ERR_PARSE_ERROR)


def test_empty_argv_code(gate):
    assert gate.evaluate([]).reason_code == g.ERR_EMPTY_ARGV
    assert gate.evaluate(None).reason_code == g.ERR_PARSE_ERROR
    assert gate.evaluate(("pip", None)).reason_code == g.ERR_PARSE_ERROR


def test_all_findings_collected_and_first_is_reason(gate):
    res = gate.evaluate(["pip", "install", "--index-url", "https://x", "reqeusts==1",
                         "requests", "unknownpkgzz==1.0"])
    assert _codes(res) == [g.ERR_INDEX_OVERRIDE, g.ERR_TYPOSQUAT_SUSPECTED,
                           g.ERR_UNPINNED_VERSION, g.ERR_UNKNOWN_PACKAGE]
    assert res.reason_code == g.ERR_INDEX_OVERRIDE
    assert [p.name for p in res.packages] == ["reqeusts", "requests", "unknownpkgzz"]


def test_index_flag_value_consumed(gate):
    # the URL after --index-url must not be parsed as a package spec
    res = gate.evaluate(["pip", "install", "--index-url", "evilpkg", "requests==2.31.0"])
    assert _codes(res) == [g.ERR_INDEX_OVERRIDE]
    res = gate.evaluate(["pip", "install", "--index-url=evilpkg", "requests==2.31.0"])
    assert _codes(res) == [g.ERR_INDEX_OVERRIDE]
    assert [p.name for p in res.packages] == ["requests"]
    res = gate.evaluate(["pip", "install", "--no-index", "requests==2.31.0"])
    assert [p.name for p in res.packages] == ["requests"]


def test_source_flag_value_consumed(gate):
    res = gate.evaluate(["cargo", "add", "--path", "zzz", "serde@=1.0.197"])
    assert _codes(res) == [g.ERR_URL_VCS_PATH_INSTALL]
    assert [p.name for p in res.packages] == ["serde"]
    res = gate.evaluate(["cargo", "add", "--path=zzz", "serde@=1.0.197"])
    assert _codes(res) == [g.ERR_URL_VCS_PATH_INSTALL]
    assert [p.name for p in res.packages] == ["serde"]


def test_source_bool_flag_does_not_consume(gate):
    res = gate.evaluate(["poetry", "add", "-e", "requests==2.31.0"])
    assert _codes(res) == [g.ERR_URL_VCS_PATH_INSTALL]
    assert [p.name for p in res.packages] == ["requests"]


def test_value_flag_value_not_treated_as_package(gate):
    res = gate.evaluate(["uv", "add", "--group", "zzzunknown", "requests==2.31.0"])
    assert res.allowed
    assert [p.name for p in res.packages] == ["requests"]


def test_bool_flag_followed_by_package(gate):
    res = gate.evaluate(["pip", "install", "--user", "requests==2.31.0"])
    assert res.allowed and [p.name for p in res.packages] == ["requests"]


def test_unsupported_option_does_not_consume_next(gate):
    res = gate.evaluate(["pip", "install", "--pre", "zzzunknown==1.0"])
    assert _codes(res) == [g.ERR_UNSUPPORTED_OPTION, g.ERR_UNKNOWN_PACKAGE]


def test_dash_alone_is_spec(gate):
    res = gate.evaluate(["pip", "install", "-"])
    assert _codes(res) == [g.ERR_INVALID_PACKAGE_NAME]


def test_double_dash_stops_option_parsing(gate):
    res = gate.evaluate(["pip", "install", "--", "--pre"])
    assert _codes(res) == [g.ERR_INVALID_PACKAGE_NAME]


def test_cargo_version_flag_only_for_install(gate):
    # cargo add does not take --version; it is an unsupported option there
    res = gate.evaluate(["cargo", "add", "serde", "--version", "1.0.197"])
    assert g.ERR_UNSUPPORTED_OPTION in _codes(res)
    # --version applies to a bare name, not to a name that already has '@'
    res = gate.evaluate(["cargo", "install", "tokio@^1", "--version", "1.36.0"])
    assert _codes(res) == [g.ERR_UNPINNED_VERSION]


def test_cargo_add_bare_version_is_caret(gate):
    assert g._cargo_exact("1.0.197", g._CARGO_ADD) is None
    assert g._cargo_exact("1.0.197", g._CARGO_INSTALL) == "1.0.197"
    assert g._cargo_exact("=1.0.197", g._CARGO_ADD) == "1.0.197"
    assert g._cargo_exact("= 1.0.197", g._CARGO_ADD) == "1.0.197"
    assert g._cargo_exact("=1.0", g._CARGO_ADD) is None


def test_typosquat_detail_and_distance(gate):
    res = gate.evaluate(["pip", "install", "reqeusts==2.31.0"])
    assert "requests" in res.findings[0].detail
    assert damerau_levenshtein("requests", "reqeusts") == 1
    assert damerau_levenshtein("abc", "abc") == 0
    assert damerau_levenshtein("", "ab") == 2
    assert damerau_levenshtein("ab", "") == 2
    assert damerau_levenshtein("kitten", "sitting") == 3
    assert damerau_levenshtein("ab", "ba") == 1
    assert damerau_levenshtein("abcd", "acbd") == 1
    assert damerau_levenshtein("ca", "abc") == 3
    assert damerau_levenshtein("a", "b") == 1
    assert damerau_levenshtein("abc", "abd") == 1
    assert damerau_levenshtein("abc", "ab") == 1


def test_typosquat_not_across_ecosystems(gate):
    # 'lodahs' is near npm 'lodash' but pip ecosystem has no 'lodash'
    res = gate.evaluate(["pip", "install", "lodahs==1.0"])
    assert res.reason_code == g.ERR_UNKNOWN_PACKAGE


def test_distance_two_is_unknown_not_typosquat(gate):
    assert gate.evaluate(["pip", "install", "rqeusts==1.0"]).reason_code == g.ERR_UNKNOWN_PACKAGE


def test_version_mismatch_detail(gate):
    res = gate.evaluate(["pip", "install", "requests==2.30.0"])
    assert "2.31.0" in res.findings[0].detail


def test_normalize_name():
    assert normalize_name(PYPI, "Typing__Extensions.x") == "typing-extensions-x"
    assert normalize_name(CARGO, "Serde_JSON") == "serde-json"
    assert normalize_name(NPM, "@Types/Node") == "@types/node"
    assert normalize_name(NPM, "a_b.c") == "a_b.c"


def test_allowlist_rejects_non_allowlist():
    with pytest.raises(TypeError):
        PackageInstallGate({"pypi": {}})


def test_allowlist_versions_lookup():
    allow = PinnedAllowlist.from_pins({PYPI: [("A_b", "1"), ("a-b", "2")]})
    assert allow.versions(PYPI, "a.B") == frozenset({"1", "2"})
    assert allow.versions(NPM, "a-b") is None
    assert list(allow.names(PYPI)) == ["a-b"]
    assert list(allow.names(CARGO)) == []


def test_empty_allowlist_denies_everything():
    gate = PackageInstallGate(PinnedAllowlist({}))
    assert gate.evaluate(["pip", "install", "requests==2.31.0"]).reason_code == g.ERR_UNKNOWN_PACKAGE


# ------------------------------------------------------------------ lockfiles
def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_lockfile_parsers_and_discovery(tmp_path):
    _write(tmp_path / "requirements.txt",
           "# comment\nrequests==2.31.0  # pinned\nflask>=2\n-r other.txt\n"
           "Typing_Extensions[x]==4.9.0 ; python_version>'3' \\\n    --hash=sha256:abc\n\n")
    _write(tmp_path / "requirements-dev.txt", "pytest == 8.0.0\n")
    _write(tmp_path / "uv.lock", '[[package]]\nname = "numpy"\nversion = "1.26.4"\n')
    _write(tmp_path / "poetry.lock", '[[package]]\nname = "attrs"\nversion = "23.2.0"\n')
    _write(tmp_path / "Cargo.lock", 'version = 3\n[[package]]\nname = "serde"\nversion = "1.0.197"\n')
    _write(tmp_path / "package-lock.json", json.dumps({
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "root", "version": "0.0.0"},
            "node_modules/lodash": {"version": "4.17.21"},
            "node_modules/@types/node": {"version": "20.11.5"},
            "node_modules/a/node_modules/b": {"version": "1.0.0"},
            "node_modules/linked": {"link": True, "version": "9.9.9"},
            "node_modules/bad": "notadict",
        }}))
    _write(tmp_path / "README.md", "requests==9.9.9\n")
    (tmp_path / "requirements.d").mkdir()
    found = discover_lockfiles(str(tmp_path))
    assert [p.rsplit("/", 1)[-1] for p in found] == [
        "Cargo.lock", "package-lock.json", "poetry.lock", "requirements-dev.txt",
        "requirements.txt", "uv.lock"]
    gate = PackageInstallGate.from_workspace(str(tmp_path))
    allow = gate.allowlist
    assert allow.versions(PYPI, "requests") == frozenset({"2.31.0"})
    assert allow.versions(PYPI, "typing-extensions") == frozenset({"4.9.0"})
    assert allow.versions(PYPI, "pytest") == frozenset({"8.0.0"})
    assert allow.versions(PYPI, "flask") is None
    assert allow.versions(PYPI, "numpy") == frozenset({"1.26.4"})
    assert allow.versions(PYPI, "attrs") == frozenset({"23.2.0"})
    assert allow.versions(CARGO, "serde") == frozenset({"1.0.197"})
    assert allow.versions(NPM, "lodash") == frozenset({"4.17.21"})
    assert allow.versions(NPM, "@types/node") == frozenset({"20.11.5"})
    assert allow.versions(NPM, "b") == frozenset({"1.0.0"})
    assert allow.versions(NPM, "root") == frozenset({"0.0.0"}) or allow.versions(NPM, "root") is None
    assert allow.versions(NPM, "linked") is None
    assert len(allow.sources) == 6
    assert gate.evaluate(["pip", "install", "pytest==8.0.0"]).allowed
    assert gate.evaluate(["npm", "i", "lodash@4.17.21"]).allowed


def test_package_lock_root_entry_skipped(tmp_path):
    p = _write(tmp_path / "package-lock.json", json.dumps({"packages": {
        "": {"name": "myapp", "version": "1.0.0"}}}))
    assert build_allowlist_from_lockfiles([p]).versions(NPM, "myapp") is None


def test_package_lock_v1(tmp_path):
    p = _write(tmp_path / "package-lock.json", json.dumps({
        "lockfileVersion": 1,
        "dependencies": {
            "lodash": {"version": "4.17.21",
                       "dependencies": {"inner": {"version": "2.0.0"}}},
            "weird": "x",
            "nover": {"dependencies": "x"},
        }}))
    allow = build_allowlist_from_lockfiles([p])
    assert allow.versions(NPM, "lodash") == frozenset({"4.17.21"})
    assert allow.versions(NPM, "inner") == frozenset({"2.0.0"})
    assert allow.versions(NPM, "nover") is None


def test_package_lock_meta_name_preferred(tmp_path):
    p = _write(tmp_path / "package-lock.json", json.dumps({"packages": {
        "node_modules/alias": {"name": "real", "version": "1.0.0"}}}))
    allow = build_allowlist_from_lockfiles([p])
    assert allow.versions(NPM, "real") == frozenset({"1.0.0"})
    assert allow.versions(NPM, "alias") is None


@pytest.mark.parametrize("fname,content", [
    ("package-lock.json", "{not json"),
    ("package-lock.json", "[]"),
    ("package-lock.json", '{"lockfileVersion": 3}'),
    ("Cargo.lock", "[[package]\nname="),
    ("Cargo.lock", 'package = "x"\n'),
    ("uv.lock", '[[package]]\nname = "x"\n'),
    ("poetry.lock", '[[package]]\nname = 3\nversion = "1"\n'),
    ("poetry.lock", 'package = [1]\n'),
    ("Pipfile.lock", "{}"),
])
def test_lockfile_parse_errors_fail_closed(tmp_path, fname, content):
    p = _write(tmp_path / fname, content)
    with pytest.raises(LockfileParseError):
        build_allowlist_from_lockfiles([p])


def test_missing_lockfile_fail_closed(tmp_path):
    with pytest.raises(LockfileParseError):
        build_allowlist_from_lockfiles([str(tmp_path / "requirements.txt")])


def test_from_workspace_fails_closed_on_bad_lockfile(tmp_path):
    _write(tmp_path / "Cargo.lock", "[[[")
    with pytest.raises(LockfileParseError):
        PackageInstallGate.from_workspace(str(tmp_path))


def test_toml_without_packages_is_empty(tmp_path):
    p = _write(tmp_path / "uv.lock", "version = 1\n")
    assert build_allowlist_from_lockfiles([p]).entries == {}


def test_repo_lockfiles_parse():
    """The repository's own top-level lockfiles must parse with stdlib only."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gate = PackageInstallGate.from_workspace(root)
    assert isinstance(gate.allowlist, PinnedAllowlist)
    assert list(gate.allowlist.sources) == discover_lockfiles(root)


def test_cargo_double_at_is_unpinned(gate):
    res = gate.evaluate(["cargo", "add", "serde@=1.0.197@x"])
    assert res.reason_code == g.ERR_UNPINNED_VERSION


def test_result_types_are_immutable(gate):
    import dataclasses
    res = gate.evaluate(["pip", "install", "requests==2.31.0", "zzzunknown==1.0"])
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.decision = InstallDecision.ALLOW
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.packages[0].version = "9.9.9"
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.findings[0].reason_code = g.PKG_ALLOWED
    with pytest.raises(dataclasses.FrozenInstanceError):
        gate.allowlist.entries = {}


def test_pep508_direct_reference_with_spaces(gate):
    res = gate._evaluate_spec(g._PIP, "requests @https://x", None)
    assert res[1].reason_code == g.ERR_URL_VCS_PATH_INSTALL
    res = gate._evaluate_spec(g._PIP, "requests @ x", None)
    assert res[1].reason_code == g.ERR_URL_VCS_PATH_INSTALL


def test_python_m_pip_shapes(gate):
    assert gate.evaluate(["python3", "-m", "pip"]).decision is InstallDecision.NOT_APPLICABLE
    assert gate.evaluate(["python3", "-m"]).decision is InstallDecision.NOT_APPLICABLE
    assert gate.evaluate(["python3", "-m", "pip", "install"]).reason_code == g.ERR_NO_PACKAGES_SPECIFIED


@pytest.mark.parametrize("exe", ["PIP", "Pip3", "pip.exe", "PIP3.EXE", "C:\\Py\\Scripts\\pip.exe",
                                 "Python3", "NPM", "Cargo.exe"])
def test_executable_name_case_and_exe_suffix(gate, exe):
    if exe.lower().startswith("python"):
        argv = [exe, "-m", "pip", "install", "evilpkg==1.0"]
    elif exe.lower().startswith("npm"):
        argv = [exe, "i", "evilpkg@1.0.0"]
    elif exe.lower().startswith("cargo"):
        argv = [exe, "add", "evilpkg@=1.0.0"]
    else:
        argv = [exe, "install", "evilpkg==1.0"]
    res = gate.evaluate(argv)
    assert res.decision is InstallDecision.DENY
    assert res.reason_code == g.ERR_UNKNOWN_PACKAGE
